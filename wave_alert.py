"""Wave & weather alert script.

Aggregates all wave exceedances (wave height >= threshold AND within opening_hours) across all
locations in a single email per run. For every exceedance, a ±3h window of wave data is included;
overlapping windows are merged so that each wave time appears at most once. A nearest matching
weather record is attached per selected wave time (also deduplicated). If no exceedances occur,
no email is sent.

Configuration: provided via `alert_config.toml` (override path with ALERT_CONFIG env var).
Example keys:
    wave_threshold = 0.5
    opening_hours = "Mo-Fr 05:00-17:00; Sa-Su 07:00-12:00"  # or "24/7"
    limit_locations = 5  # optional
    [smtp]
    host = "smtp.gmail.com"
    port = 587
    user = "me@example.com"
    pass = "app_password"
    to   = "recipient@example.com"   # optional (defaults to user)
    from = "alerts@example.com"      # optional

Usage:
    python wave_alert.py

Email Subject format:
    Wave Alerts · <N locations> · <M exceedances> (Threshold >= X.Ym)
"""

from __future__ import annotations

import html as _html
import os
import smtplib
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import List, Tuple
from zoneinfo import ZoneInfo

import tomli

from waves_on_map.fetch_data import fetch_forecast, fetch_waves

CONFIG_PATH = Path(os.getenv("ALERT_CONFIG", "alert_config.toml"))


def load_config():
    base = {
        "wave_threshold": 0.5,
        # OSM-style opening hours spec, e.g. "Mo-Fr 05:00-17:00; Sa-Su 07:00-12:00" or "24/7"
        "opening_hours": None,
        "smtp": {
            "host": "smtp.gmail.com",
            "port": 587,
            "user": None,
            "pass": None,
            "to": None,
            "from": None,
        },
        "limit_locations": None,
    }
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("rb") as f:
                data = tomli.load(f)
            # shallow merge
            for k, v in data.items():
                if k == "smtp" and isinstance(v, dict):
                    base["smtp"].update(v)
                else:
                    base[k] = v
        except Exception as e:  # pragma: no cover
            print(f"[alert] Failed to load config {CONFIG_PATH}: {e}; using defaults")
    else:
        print(f"[alert] Config file not found: {CONFIG_PATH}; using defaults")
    return base


CFG = load_config()

WAVE_THRESHOLD = float(CFG.get("wave_threshold", 0.5))


def _parse_opening_hours(spec: str) -> Callable[[datetime], bool]:
    """Return callable(dt) -> bool implementing a minimal subset of OSM opening_hours.

    Supported forms:
      - 24/7
      - Day ranges & lists: Mo-Fr, Sa-Su, Mo,We,Fr
      - Multiple rules separated by ';'
      - Time ranges per rule: HH:MM-HH:MM[,HH:MM-HH:MM...]
      - 'off' to mark days closed
    Unspecified days default to closed (unless 24/7).
    """
    spec = spec.strip()
    if not spec:
        return lambda x: True

    days_map: dict[int, list[tuple[int, int]]] = {i: [] for i in range(7)}  # 0=Mon
    if spec.lower() == "24/7":
        for i in range(7):
            days_map[i] = [(0, 24 * 60)]

        def always(dt):
            return True

        return always
    DAY_IDX = {k: i for i, k in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"])}
    import re

    rule_sep = [r.strip() for r in spec.split(";") if r.strip()]
    time_pat = re.compile(r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})")
    for rule in rule_sep:
        # Split day part and times
        parts = rule.split()
        if not parts:
            continue
        # Detect if first token has a digit -> implies no day spec (apply all days)
        if any(ch.isdigit() for ch in parts[0]):
            day_tokens = ["ALL"]
            time_tokens = parts
        else:
            day_tokens = parts[0].split(",")
            time_tokens = parts[1:] if len(parts) > 1 else []
        # Expand days
        days: list[int] = []
        for tok in day_tokens:
            tok = tok.strip()
            if tok == "ALL":
                days = list(range(7))
                break
            if "-" in tok:
                a, b = tok.split("-", 1)
                if a in DAY_IDX and b in DAY_IDX:
                    ai, bi = DAY_IDX[a], DAY_IDX[b]
                    if ai <= bi:
                        days.extend(range(ai, bi + 1))
                    else:  # wrap (unlikely in typical usage)
                        days.extend(list(range(ai, 7)) + list(range(0, bi + 1)))
            elif tok in DAY_IDX:
                days.append(DAY_IDX[tok])
        if not days:
            days = list(range(7))  # fallback
        # If 'off' present => clear entries for these days
        if any(t.lower() == "off" for t in time_tokens):
            for d in days:
                days_map[d] = []
            continue
        # Parse time ranges
        # Join remaining tokens with comma to allow both space and comma separation
        joined = ",".join(time_tokens)
        for m in time_pat.finditer(joined):
            h1, m1, h2, m2 = map(int, m.groups())
            start = h1 * 60 + m1
            end = h2 * 60 + m2
            if 0 <= start < 24 * 60 and 0 <= end <= 24 * 60 and start < end:
                for d in days:
                    days_map[d].append((start, end))
    # Normalize (merge overlapping) - simple sort
    for d in days_map:
        rngs = sorted(days_map[d])
        merged: list[tuple[int, int]] = []
        for s, e in rngs:
            if not merged or s > merged[-1][1]:
                merged.append((s, e))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        days_map[d] = merged

    def is_open(dt):
        day = dt.weekday()
        minute = dt.hour * 60 + dt.minute
        for s, e in days_map[day]:
            if s <= minute < e:
                return True
        return False

    return is_open


OPENING_HOURS_SPEC = CFG.get("opening_hours", "")
IS_OPEN: Callable[[datetime], bool] = _parse_opening_hours(OPENING_HOURS_SPEC)
UTC = timezone.utc
TIME_TZ_LABEL = "Europe/Oslo"
OSLO_TZ = ZoneInfo(TIME_TZ_LABEL)

DB_PATH = Path("data/weather.db")


@dataclass
class WaveRow:
    time: str
    height: float
    from_dir: float
    to_dir: float
    temp: float
    current: float


@dataclass
class WeatherRow:
    time: str
    air_temp: float
    wind_speed: float
    wind_from: float
    cloud: float
    rh: float
    precip: float | None
    symbol: str | None


def load_locations(limit: int | None = None) -> List[Tuple[int, float, float, str]]:
    if not DB_PATH.exists():
        raise SystemExit(f"DB missing at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, latitude, longitude, name FROM locations ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()
    if limit is not None:
        rows = rows[:limit]
    return [(r[0], float(r[1]), float(r[2]), r[3]) for r in rows]


def window_indices(center_idx: int, total: int, radius: int) -> range:
    start = max(0, center_idx - radius)
    end = min(total, center_idx + radius + 1)
    return range(start, end)


def nearest_weather(weather_list, target_time):
    return (
        min(weather_list, key=lambda w: abs(w.time - target_time))
        if weather_list
        else None
    )


def fmt_precip(val: float) -> str:
    return "-" if val != val else f"{val:.1f}"  # NaN check


def to_oslo(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(OSLO_TZ)


def build_combined_table(wave_objs, weather_map) -> tuple[str, str]:
    """Return (text_table, html_table) collocating wave + nearest weather per wave time.

    Text table is markdown-like for plaintext; HTML table uses inline CSS for email clients.
    Rows with wave height >= threshold are highlighted in HTML.
    """
    header_txt = (
        "Time | H(m) | From° | To° | WaterT°C | Current m/s | Sym | AirT°C | Wind m/s | WindFrom° | Cloud% | RH% | Precip mm",
        "-----|------|-------|-----|----------|-------------|-----|--------|----------|-----------|--------|-----|----------",
    )
    text_lines: list[str] = list(header_txt)
    # HTML table start
    html_parts = [
        "<table cellpadding='0' cellspacing='0' border='0' style='border-collapse:collapse;width:100%;max-width:980px;font:12px/1.35 system-ui,Arial,sans-serif;border:1px solid #1d2731;background:#0f1a22;'>",
        "<thead><tr style='background:#16232d;color:#f2f8fc;'>"
        "<th style='padding:6px 8px;text-align:left;'>Time</th>"
        "<th style='padding:6px 8px;text-align:right;'>H(m)</th>"
        "<th style='padding:6px 8px;text-align:right;'>From°</th>"
        "<th style='padding:6px 8px;text-align:right;'>To°</th>"
        "<th style='padding:6px 8px;text-align:right;'>WaterT°C</th>"
        "<th style='padding:6px 8px;text-align:right;'>Current</th>"
        "<th style='padding:6px 8px;text-align:center;'>Sym</th>"
        "<th style='padding:6px 8px;text-align:right;'>AirT°C</th>"
        "<th style='padding:6px 8px;text-align:right;'>Wind</th>"
        "<th style='padding:6px 8px;text-align:right;'>WindFrom°</th>"
        "<th style='padding:6px 8px;text-align:right;'>Cloud%</th>"
        "<th style='padding:6px 8px;text-align:right;'>RH%</th>"
        "<th style='padding:6px 8px;text-align:right;'>Precip</th>"
        "</tr></thead><tbody>",
    ]
    for idx, wv in enumerate(wave_objs):
        wt = None
        if weather_map:
            wt = min(weather_map.values(), key=lambda w: abs(w.time - wv.time))
        ldt = to_oslo(wv.time)
        h = wv.sea_surface_wave_height
        # Plain text
        text_lines.append(
            f"{ldt:%Y-%m-%d %H:%M} | {h:.2f} | {wv.sea_surface_wave_from_direction:.0f} | "
            f"{wv.sea_water_to_direction:.0f} | {wv.sea_water_temperature:.1f} | {wv.sea_water_speed:.2f} | "
            f"{(wt.symbol_code if wt and wt.symbol_code else '-'):>3} | "
            f"{(f'{wt.air_temperature:.1f}' if wt else '-'):>6} | "
            f"{(f'{wt.wind_speed:.1f}' if wt else '-'):>8} | "
            f"{(f'{wt.wind_from_direction:.0f}' if wt else '-'):>9} | "
            f"{(f'{wt.cloud_area_fraction:.0f}' if wt else '-'):>6} | "
            f"{(f'{wt.relative_humidity:.0f}' if wt else '-'):>3} | "
            f"{(fmt_precip(wt.precipitation_amount) if wt else '-'):>9}"
        )
        # HTML row
        zebra_bg = "#121e27" if idx % 2 == 0 else "#0f1a22"
        highlight = h >= WAVE_THRESHOLD
        row_style = f"background:{'#1f2f3a' if highlight else zebra_bg};" + (
            "font-weight:600;" if highlight else ""
        )

        def td(val, align="right"):
            return f"<td style='padding:5px 8px;text-align:{align};border-bottom:1px solid #1d2731;color:#e6edf3;white-space:nowrap;'>{_html.escape(str(val))}</td>"

        html_parts.append(
            "<tr style='"
            + row_style
            + "'>"
            + td(f"{ldt:%Y-%m-%d %H:%M}", "left")
            + td(f"{h:.2f}")
            + td(f"{wv.sea_surface_wave_from_direction:.0f}")
            + td(f"{wv.sea_water_to_direction:.0f}")
            + td(f"{wv.sea_water_temperature:.1f}")
            + td(f"{wv.sea_water_speed:.2f}")
            + td((wt.symbol_code if wt and wt.symbol_code else "-"), "center")
            + td(f"{wt.air_temperature:.1f}" if wt else "-")
            + td(f"{wt.wind_speed:.1f}" if wt else "-")
            + td(f"{wt.wind_from_direction:.0f}" if wt else "-")
            + td(f"{wt.cloud_area_fraction:.0f}" if wt else "-")
            + td(f"{wt.relative_humidity:.0f}" if wt else "-")
            + td(fmt_precip(wt.precipitation_amount) if wt else "-")
            + "</tr>"
        )
    html_parts.append("</tbody></table>")
    return "\n".join(text_lines), "".join(html_parts)


def send_email(subject: str, text_body: str, html_body: str | None = None):
    smtp_cfg = CFG.get("smtp", {})
    host = smtp_cfg.get("host") or "smtp.gmail.com"
    port = int(smtp_cfg.get("port") or 587)
    user = smtp_cfg.get("user")
    password = smtp_cfg.get("pass")
    to_addr = smtp_cfg.get("to") or user or ""
    from_addr = smtp_cfg.get("from") or user or ""

    if not (user and password and to_addr):
        print("[alert] Missing SMTP credentials or recipient; skip sending.")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    print(f"[alert] Sending email to {to_addr} with subject '{subject}'")
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls()
        s.login(user, password)
        s.send_message(msg)
    print("[alert] Email sent.")


def process_location(loc_id: int, lat: float, lon: float, name: str):
    """Return aggregated exceedance data for a location or None if no exceedances."""
    waves_info = fetch_waves(lat, lon)
    weather_info = fetch_forecast(lat, lon)
    wave_list = list(waves_info.data)
    weather_list = list(weather_info.data)

    exceed_indices = [
        i
        for i, w in enumerate(wave_list)
        if IS_OPEN(to_oslo(w.time)) and w.sea_surface_wave_height >= WAVE_THRESHOLD  # type: ignore
    ]
    if not exceed_indices:
        return None

    # Build merged wave index set including ±3h (±3 indices) around each exceedance index
    selected = set()
    for idx in exceed_indices:
        for j in window_indices(idx, len(wave_list), 3):
            selected.add(j)
    wave_objs = sorted((wave_list[i] for i in selected), key=lambda w: w.time)

    # Weather: pick nearest sample per selected wave time; dedupe by exact weather timestamp
    weather_map = {}
    for wv in wave_objs:
        wt = nearest_weather(weather_list, wv.time)
        if wt:
            weather_map.setdefault(wt.time, wt)

    combined_text, combined_html = build_combined_table(wave_objs, weather_map)
    return {
        "loc_id": loc_id,
        "name": name,
        "lat": lat,
        "lon": lon,
        "exceed_count": len(exceed_indices),
        "combined_table_text": combined_text,
        "combined_table_html": combined_html,
        "max_height": max(wave_list[i].sea_surface_wave_height for i in exceed_indices),
        "first_time": wave_list[exceed_indices[0]].time,
    }


def run(limit: int | None = None):
    locs = load_locations(limit=limit if limit else None)
    if not locs:
        print("[alert] No locations found.")
        return
    aggregates = []
    total_exceed = 0
    for loc_id, lat, lon, name in locs:
        print(f"[alert] Processing {name} ({lat:.3f},{lon:.3f})")
        try:
            agg = process_location(loc_id, lat, lon, name)
            if agg:
                aggregates.append(agg)
                total_exceed += agg["exceed_count"]
        except Exception as e:  # pragma: no cover
            print(f"[alert] Error processing {name}: {e}")

    if not aggregates:
        print("[alert] No exceedances; no email sent.")
        return

    # Build single email
    subject = f"Wave Alerts · {len(aggregates)} location(s) · {total_exceed} exceedance(s) (>= {WAVE_THRESHOLD:.2f}m) [{TIME_TZ_LABEL}]"
    sections = [
        f"Threshold: {WAVE_THRESHOLD:.2f} m",
        f"Opening hours spec: {OPENING_HOURS_SPEC or 'N/A'}",
        f"Times shown in {TIME_TZ_LABEL} (converted from UTC)",
        "",
    ]
    html_sections = [
        "<div style='background:#0b141b;padding:16px;font:14px system-ui,Arial,sans-serif;color:#dce8ef'>",
        "<h2 style='margin:0 0 10px;font:600 18px system-ui,Arial,sans-serif;color:#89d2ff'>Wave Alerts</h2>",
        f"<p style='margin:0 0 10px;font-size:12px;color:#9fb6c3'>Threshold: {WAVE_THRESHOLD:.2f} m<br>Opening hours: {_html.escape(OPENING_HOURS_SPEC or 'N/A')}<br>Times in {TIME_TZ_LABEL}</p>",
    ]
    for agg in sorted(aggregates, key=lambda a: a["first_time"]):
        first_local = to_oslo(agg["first_time"]) if agg.get("first_time") else None
        sections.append(
            f"=== {agg['name']} (lat={agg['lat']:.4f}, lon={agg['lon']:.4f}) | exceedances={agg['exceed_count']} | max={agg['max_height']:.2f}m | first={first_local:%Y-%m-%d %H:%M} ==="
        )
        sections.append("-- Waves + Weather (collocated) --")
        sections.append(agg["combined_table_text"])  # single table
        sections.append("")
        html_sections.append(
            f"<h3 style='margin:20px 0 6px;font:600 15px system-ui,Arial,sans-serif;color:#d4f4ff'>{_html.escape(agg['name'])} · exceedances={agg['exceed_count']} · max={agg['max_height']:.2f}m · first={first_local:%Y-%m-%d %H:%M}</h3>"
        )
        html_sections.append(agg["combined_table_html"])
    html_sections.append(
        "<p style='margin:18px 0 4px;font-size:11px;color:#6e8796'>Data: api.met.no (oceanforecast & locationforecast)</p>"
    )
    html_sections.append("</div>")
    body = "\n".join(sections)
    html_body = "".join(html_sections)
    send_email(subject, body, html_body)


if __name__ == "__main__":
    limit_cfg = CFG.get("limit_locations")
    limit = int(limit_cfg) if isinstance(limit_cfg, int) else None
    run(limit=limit)
