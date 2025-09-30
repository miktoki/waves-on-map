# from textwrap import dedent
import base64
import logging
import os
import shutil
from datetime import timezone
from pathlib import Path
from textwrap import dedent
from typing import cast

import fasthtml.common as ft
import folium

from date_utils import OSLO_TZ, to_oslo
from wave_alert import CFG
from wave_alert import run as wave_alert_run

LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("app_log")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(_handler)
# --- Runtime env hardening for optional read-only deployments ---------------
# Enable by setting environment variable READONLY_DEPLOYMENT to one of: 1, true, yes.
READONLY_DEPLOYMENT = os.environ.get("READONLY_DEPLOYMENT", "").lower() in {
    "1",
    "true",
    "yes",
}
logger.info("App starting, READONLY_DEPLOYMENT=%s", READONLY_DEPLOYMENT)
if READONLY_DEPLOYMENT:
    # Some hosting platforms mount the app directory read-only; only /tmp is writable.
    # Matplotlib tries to create ~/.config/matplotlib or CWD/.config on first import, so redirect.
    MPL_DIR = Path("/tmp/mplconfig")
    try:
        MPL_DIR.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", str(MPL_DIR))
    except Exception as e:  # pragma: no cover - best effort safeguard
        print(f"[startup] Failed to prep MPLCONFIGDIR: {e}")

import matplotlib.colors as mcolors  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import sqlite_minutils  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from fasthtml.common import Div, Meta  # noqa: F401,E402

from waves_on_map.assets import (  # noqa: E402
    FAVICON_DATA_URL,
    MAP_DARK_CSS,
    MAP_RIGHT_CLICK_SCRIPT,
    WAVE_DETAIL_DARK_CSS,
)
from waves_on_map.fetch_data import fetch_forecast, fetch_waves  # noqa: E402
from waves_on_map.map import add_clickable_arrow, get_map  # noqa: E402
from waves_on_map.models import WaveData  # noqa: E402

# Preload weather SVG icons into memory to avoid separate HTTP requests and 404 issues
ICON_SVGS: dict[str, str] = {}
ICON_SVG_DATA_URIS: dict[str, str] = {}
try:
    svg_dir = Path(__file__).resolve().parent / "data" / "svg"
    if svg_dir.exists():
        for p in svg_dir.glob("*.svg"):
            try:
                raw = p.read_text(encoding="utf-8")
                ICON_SVGS[p.stem] = raw
                # Construct a compact data URI (base64 to avoid escaping issues)
                b64 = base64.b64encode(raw.encode("utf-8")).decode("ascii")
                ICON_SVG_DATA_URIS[p.stem] = f"data:image/svg+xml;base64,{b64}"
            except Exception as e:  # pragma: no cover - best effort
                print(f"[icons] Failed to load {p.name}: {e}")
    else:  # pragma: no cover
        print(f"[icons] svg dir missing: {svg_dir}")
except Exception as e:  # pragma: no cover
    print(f"[icons] preload error: {e}")


def build_metrics_badge(wind_sup: str, wave_sub: str) -> str:
    return dedent(
        f"""
        <span style='position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);display:flex;flex-direction:column;gap:6px;width:40px;pointer-events:none;z-index:2;'>
            <span style='display:flex;width:40px;align-items:center;justify-content:space-between;font-size:0.9rem;font-weight:700;color:#d4f4ff;letter-spacing:-.3px;text-shadow:0 0 4px rgba(0,0,0,.85);'>
                <span>💨</span><span style='margin-left:auto;'>{wind_sup}</span>
            </span>
            <span style='display:flex;width:40px;align-items:center;justify-content:space-between;font-size:0.85rem;font-weight:600;color:#9edbff;letter-spacing:-.3px;text-shadow:0 0 4px rgba(0,0,0,.85);'>
                <span>🌊</span><span style='margin-left:auto;'>{wave_sub}</span>
            </span>
        </span>
        """.strip()
    )


def build_icon_html(
    rotation: float, metrics_badge: str, days_ahead: int | None = None
) -> str:
    if days_ahead is None:
        days_ahead = 0
    day_label = f"<div style='position:absolute;left:50%;bottom:2px;transform:translate(-50%,0);font-size:.55rem;font-weight:600;color:#ffd1d1;background:rgba(40,8,10,.85);padding:2px 5px 2px;border:1px solid #ff6d6d;border-radius:8px;line-height:1;letter-spacing:.4px;box-shadow:0 2px 5px -2px rgba(0,0,0,.65);font-family:system-ui,sans-serif;pointer-events:none;'>+{days_ahead}</div>"
    return dedent(
        f"""
        <div style='position:relative;pointer-events:auto;font-family:system-ui,sans-serif;'>
            <div style='width:60px;height:60px;position:relative;padding:4px;background:#2a0e11;background:radial-gradient(circle at 42% 34%,rgba(255,120,120,.55),rgba(40,8,10,.94));border:2px solid #ff6d6d;border-radius:50%;box-shadow:0 3px 10px -4px rgba(0,0,0,.85),0 0 0 1px rgba(255,120,120,.45);overflow:hidden;box-sizing:border-box;'>
                <div style='position:absolute;top:50%;left:50%;transform:translate(-50%,-50%) rotate({rotation}deg);font-size:30px;line-height:1;color:#ff4d4d;filter:drop-shadow(0 0 5px rgba(0,0,0,.95));font-weight:800;text-shadow:0 0 7px rgba(255,120,120,.65);'>↑</div>
                {metrics_badge}
                {day_label}
            </div>
        </div>
        """.strip()
    )


if not READONLY_DEPLOYMENT:
    db_path = Path("data/weather.db")
elif not (db_path := Path("/tmp/data/weather.db")).exists():
    db_path.parent.mkdir(parents=True, exist_ok=True)
    for p in db_path.parent.glob(f"{db_path.name}*"):
        shutil.copy(p, db_path.parent)
db = ft.database(db_path)
waves: sqlite_minutils.Table = db.t.waves_highlights
locs: sqlite_minutils.Table = db.t.locations
# sqlite_minutils.python_a
if waves not in db.t:
    wave_columns = {
        name: field.annotation for name, field in WaveData.model_fields.items()
    }
    wave_columns.update(dict(id=int, loc_id=int))

    locs.create(
        dict(latitude=float, longitude=float, id=int, name=str, extra_thresh=float),
        pk="id",
    )
    waves.create(
        wave_columns,
        pk="id",
        foreign_keys=[("loc_id", "locations")],
    )


# TODO: move me
def value_to_hex(x, a, b, cmap_name="viridis"):
    # Normalize value to range [0,1]
    norm = (x - a) / (b - a)
    norm = max(0, min(1, norm))  # Clip values outside [a, b]

    # Get colormap
    cmap = plt.get_cmap(cmap_name)  # type: ignore

    # Convert to RGB
    rgb = cmap(norm)[:3]  # Ignore alpha if present

    # Convert to HEX
    return mcolors.rgb2hex(rgb)


def insert_wave_data(m: folium.Map):
    if not locs.count:
        from waves_on_map.init_locs import init_locs

        locs.insert_all(init_locs)

    for loc in locs(limit=100):  # type: ignore
        lat = loc["latitude"]
        lon = loc["longitude"]
        wi = fetch_waves(lat, lon)
        wd = max(wi.data, key=lambda ts: ts.sea_surface_wave_height)
        # Fetch weather to get wind speeds for superscript indicator
        forecast = fetch_forecast(lat, lon)
        # get max wind at same time as max wave height
        f_max = min(forecast.data, key=lambda dt: abs(wd.time - dt.time))
        max_wave_h = wd.sea_surface_wave_height
        wind_sup = (
            f"{f_max.wind_speed:.1f}" if f_max.wind_speed == f_max.wind_speed else "?"
        )
        wave_sub = str(round(max_wave_h, 1)) if max_wave_h == max_wave_h else "?"

        # Persist (or reuse) a highlight wave record for this location so we have a stable PK
        existing_wave = None

        for wave_row in waves(limit=5000):  # type: ignore # naive scan (small table expected)
            if wave_row.get("loc_id") == loc["id"]:
                existing_wave = wave_row
                break

        if existing_wave is None:
            wave_id = waves.count + 1
            waves.insert(
                {
                    "id": wave_id,
                    "loc_id": loc["id"],
                    "sea_surface_wave_from_direction": wd.sea_surface_wave_from_direction,
                    "sea_surface_wave_height": wd.sea_surface_wave_height,
                    "sea_water_speed": wd.sea_water_speed,
                    "sea_water_temperature": wd.sea_water_temperature,
                    "sea_water_to_direction": wd.sea_water_to_direction,
                    "time": wd.time,
                }
            )
        else:
            wave_id = existing_wave["id"]

        # Compose arrow popup with metrics badge
        metrics_badge = build_metrics_badge(wind_sup, wave_sub)
        from datetime import datetime

        days_ahead = (to_oslo(wd.time).date() - datetime.now(OSLO_TZ).date()).days
        metrics_badge += f"<span style='position:absolute;left:50%;bottom:2px;transform:translate(-50%,0);font-size:0.9rem;font-weight:600;color:#ffd1d1;line-height:1;letter-spacing:.4px;pointer-events:none;'>+{days_ahead}</span>"
        add_clickable_arrow(
            m,
            lat,
            lon,
            rotation=(180 + wd.sea_surface_wave_from_direction) % 360,
            popup_text=dedent(
                f"""
                {lat:.2f} {lon:.2f}<br>
                {"<br>".join(f"{k}: {v}" for k, v in wd.local_compact.items())}<br>
                <a href='/{wave_id}' style='color:#66b3ff;text-decoration:underline;'>Details ➜</a>
                """.strip()
            ),
            metrics_html=metrics_badge,
        )


# Create a base map for extracting static resources
base_map = get_map()
base_html = cast(str, base_map.get_root().render())
base_soup = BeautifulSoup(base_html, "html.parser")
scripts = [ft.Script(src=src) for _, src in base_map.default_js]
# Only include external CSS here; defer folium-generated <style> (map id specific) to request time
styles = [
    ft.Link(rel="stylesheet", href=href, type="text/css")
    for _, href in base_map.default_css
]

fastapp_common_hdrs = (
    *scripts,
    *styles,
    eval(ft.html2ft(str(base_soup.find(attrs={"name": "viewport"})))),
    ft.Link(rel="icon", type="image/svg+xml", href=FAVICON_DATA_URL),
    ft.Link(rel="shortcut icon", href=FAVICON_DATA_URL),
)

if SCHEDULED_TASKS := os.getenv("SCHEDULED_TASKS", ""):
    import threading
    from functools import partial

    wave_alert_run2 = partial(wave_alert_run, limit=CFG.get("limit_locations"))

    def run_scheduler():
        import time

        import schedule

        TWO_DAYS = 60 * 60 * 24 * 2
        wave_alert_run2()
        while True:
            schedule.every(2).days.at("16:00").do(wave_alert_run2)
            time.sleep(TWO_DAYS)  # Check every two days

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

if READONLY_DEPLOYMENT:
    app, rt = ft.fast_app(
        live=False,
        default_hdrs=False,
        hdrs=fastapp_common_hdrs,
        secret_key=os.environ.get("APP_SECRET_KEY", "dev-insecure-key-change-me"),
        key_fname="/tmp/.sesskey",
    )
else:
    app, rt = ft.fast_app(
        live=False,
        default_hdrs=False,
        hdrs=fastapp_common_hdrs,
    )
logger.info("App and router initialized")


@rt("/")
def get():
    # Create a fresh map for each request with all current data
    insert_wave_data(base_map)

    # Render the map with all markers
    html = cast(str, base_map.get_root().render())
    soup = BeautifulSoup(html, "html.parser")
    folium_map_div = soup.find("div", class_="folium-map")
    ft_map_div = ft.html2ft(str(folium_map_div))
    dynamic_styles: list = []  # type: ignore[var-annotated]
    for s in soup.find_all("style"):
        try:
            txt = s.get_text("", strip=True)
            if txt:
                dynamic_styles.append(ft.Style(txt))  # type: ignore[arg-type]
        except Exception:
            pass

    # Extract the map ID from the div
    map_id: str = folium_map_div.get("id")  # type: ignore

    # Enhanced right-click script (injected with placeholders replaced)
    right_click_script = MAP_RIGHT_CLICK_SCRIPT.replace(
        "MAP_ID_PLACEHOLDER", map_id
    ).replace("MAP_ID_LITERAL", map_id)

    dark_css = ft.Style(MAP_DARK_CSS)

    return (
        ft.Title("Map waves++"),
        dark_css,
        *dynamic_styles,
        eval(ft_map_div),
        ft.Script(code=str(soup.find_all("script")[-1].contents[0].strip())),  # type: ignore
        ft.Script(code=right_click_script),
        ft.Script(
            code=(
                """
        // Fallback robust contextmenu binding with dynamic marker insertion
        (function(){
            const mapId = """
                + repr(map_id)
                + """;
            function bindCtx(r=0){
                try{
                    const el=document.getElementById(mapId);
                    if(!el) return r<40?setTimeout(()=>bindCtx(r+1),100):null;
                    const m=el._leaflet_map||window[mapId]||window['map_'+mapId]||(window.L&&Object.values(window).find(v=>v&&v instanceof L.Map));
                    if(!m) return r<40?setTimeout(()=>bindCtx(r+1),100):null;
                    if(m.__ctxBound) return; m.__ctxBound=true;
                    m.on('contextmenu', e => {
                        const name = prompt('Enter location name:');
                        if(!name) return;
                        fetch('/add_location', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ latitude: e.latlng.lat, longitude: e.latlng.lng, name })
                        }).then(r => r.json()).then(j => {
                            if(!j.success){ alert('Failed: ' + (j.error||'unknown')); return; }
                            if(j.marker){
                                try {
                                    const icon = L.divIcon({ html: j.marker.icon_html });
                                    const marker = L.marker([j.marker.lat, j.marker.lon], { icon }).addTo(m);
                                    if(j.marker.popup_html){ marker.bindPopup(j.marker.popup_html).openPopup(); }
                                } catch(err) { console.error('dynamic marker add failed', err); location.reload(); }
                            } else {
                                location.reload();
                            }
                        }).catch(err => { console.error('add_location error', err); alert('Add failed'); });
                    });
                    console.debug('Right-click add-location bound');
                } catch(err) { console.error('bindCtx error', err); }
            }
            document.readyState==='loading' ? document.addEventListener('DOMContentLoaded', bindCtx) : bindCtx();
        })();
        """
            ),
        ),
    )


@rt("/add_location")
def post(data: dict):
    """API endpoint to add a new location to the database."""
    try:
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        name = data.get("name")

        if not (latitude and longitude and name):
            return {
                "success": False,
                "error": "Missing required data (latitude, longitude, or name)",
            }

        # Validate data types
        try:
            latitude = float(latitude)
            longitude = float(longitude)
            name = str(name).strip()
        except (ValueError, TypeError):
            return {"success": False, "error": "Invalid data format"}

        if not name:
            return {"success": False, "error": "Location name cannot be empty"}

        # Get the next available ID
        max_id = locs.count
        next_id = max_id + 1

        loc = dict(
            latitude=latitude,
            longitude=longitude,
            name=name,
            id=next_id,
            extra_thresh=0.0,
        )
        locs.insert(loc)

        # Build marker payload for immediate client insertion
        try:
            wi = fetch_waves(latitude, longitude)
            wd = max(wi.data, key=lambda ts: ts.sea_surface_wave_height)
            forecast = fetch_forecast(latitude, longitude)
            f_max = min(forecast.data, key=lambda dt: abs(wd.time - dt.time))
            max_wave_h = wd.sea_surface_wave_height
            wind_sup = (
                f"{f_max.wind_speed:.1f}"
                if f_max.wind_speed == f_max.wind_speed
                else "?"
            )
            wave_sub = str(max_wave_h)

            # Store wave data in database to get a wave_id for the Details link
            wave_id = waves.count + 1
            waves.insert(
                {
                    "id": wave_id,
                    "loc_id": next_id,
                    "sea_surface_wave_from_direction": wd.sea_surface_wave_from_direction,
                    "sea_surface_wave_height": wd.sea_surface_wave_height,
                    "sea_water_speed": wd.sea_water_speed,
                    "sea_water_temperature": wd.sea_water_temperature,
                    "sea_water_to_direction": wd.sea_water_to_direction,
                    "time": wd.time,
                }
            )

            metrics_badge = build_metrics_badge(wind_sup, wave_sub)
            rotation = (180 + wd.sea_surface_wave_from_direction) % 360
            from datetime import datetime

            days_ahead = (to_oslo(wd.time).date() - datetime.now(OSLO_TZ).date()).days
            icon_html = build_icon_html(rotation, metrics_badge, days_ahead)
            popup_html = dedent(
                f"""
                {latitude:.2f} {longitude:.2f}<br>
                {"<br>".join(f"{k}: {v}" for k, v in wd.compact.items())}<br>
                <a href='/{wave_id}' style='color:#66b3ff;text-decoration:underline;'>Details ➜</a>
                """.strip()
            )
            marker_payload = dict(
                lat=latitude,
                lon=longitude,
                icon_html=icon_html,
                popup_html=popup_html,
            )
        except Exception as e:
            print(f"Marker generation failed for new location {name}: {e}")
            marker_payload = None  # type: ignore

        return {
            "success": True,
            "message": "Location added successfully",
            "marker": marker_payload,
        }

    except Exception as e:
        print(f"Error adding location: {e}")
        return {"success": False, "error": f"Server error: {str(e)}"}


@rt("/{wave_id:int}")
def wave_detail(wave_id: int):
    """Display combined wave + weather details interleaved (one row per wave time)."""
    # Locate stored highlight wave row
    wave_row = None
    if hasattr(waves, "get"):
        try:
            wave_row = waves.get(wave_id)  # type: ignore
        except Exception:
            wave_row = None
    if not wave_row:  # fallback manual scan
        for wr in waves(limit=5000):  # type: ignore
            if wr.get("id") == wave_id:  # type: ignore
                wave_row = wr
                break
    if not wave_row:
        return ft.Div(ft.H2("Not found")), 404

    # Find linked location
    loc_row = None
    if hasattr(locs, "get"):
        try:
            loc_row = locs.get(wave_row["loc_id"])  # type: ignore
        except Exception:
            loc_row = None
    if not loc_row:
        return ft.Div(ft.H2("Location missing")), 404

    lat = loc_row["latitude"]
    lon = loc_row["longitude"]
    name = loc_row.get("name", f"Loc {loc_row['id']}")

    # Fetch fresh forecasts
    wi = fetch_waves(lat, lon)
    weather = fetch_forecast(lat, lon)

    from datetime import timedelta

    headers = [
        "Time",
        "Wave H (m)",
        "From",
        "To",
        "Water Temp (°C)",
        "Current (m/s)",
        "Symbol",
        "Air Temp (°C)",
        "Wind",
        "Wind Dir",
        "Cloud %",
        "RH %",
        "Precip (mm)",
    ]

    def wave_arrow_cell(deg: float, label: str):
        return ft.Span(
            "↑",
            cls="arrow",
            style=(
                f"display:inline-block;transform:rotate({(deg + 180) % 360}deg);"
                "filter:drop-shadow(0 0 4px #000);font-weight:700;"
                "font-size:20px;line-height:1;color:#f8fbff;"
            ),
            title=f"{label} {deg:.0f}°",
        )

    def weather_symbol_cell(symbol_code: str | None):
        if not symbol_code:
            return ft.Span("-", cls="wsym none")
        svg = ICON_SVG_DATA_URIS.get(symbol_code)
        if svg:
            return ft.Img(
                src=svg,
                alt=symbol_code,
                width="40",
                height="40",
                style="display:block;object-fit:contain;",
            )
        return ft.Span(symbol_code.replace("_", " "), cls="wsym missing")

    def wind_arrow_cell(deg: float):
        return ft.Span(
            "↑",
            cls="arrow",
            style=(
                f"display:inline-block;transform:rotate({(deg + 180) % 360}deg);"
                "font-weight:700;filter:drop-shadow(0 0 4px #000);"
                "font-size:20px;line-height:1;color:#f8fbff;"
            ),
            title=f"wind from {deg:.0f}°",
        )

    # Index weather times for nearest match (within 45 min tolerance)
    weather_list = list(weather.data)
    unused_weather = set(range(len(weather_list)))

    def find_weather_match(t):
        best_i = None
        best_dt = timedelta.max
        for i, w in enumerate(weather_list):
            if i not in unused_weather:
                continue
            diff = abs(w.time - t)
            if diff < best_dt:
                best_dt = diff
                best_i = i
        if best_i is not None and best_dt <= timedelta(minutes=45):
            unused_weather.remove(best_i)
            return weather_list[best_i]
        return None

    rows: list[ft.Tr] = []  # type: ignore
    for wv in wi.data:
        wm = find_weather_match(wv.time)
        rows.append(
            ft.Tr(
                ft.Td(to_oslo(wv.time).strftime("%a %-d %b %H:%M")),
                ft.Td(f"{wv.sea_surface_wave_height:.2f}"),
                ft.Td(wave_arrow_cell(wv.sea_surface_wave_from_direction, "from")),
                ft.Td(wave_arrow_cell(wv.sea_water_to_direction, "to")),
                ft.Td(f"{wv.sea_water_temperature:.1f}"),
                ft.Td(f"{wv.sea_water_speed:.2f}"),
                ft.Td(weather_symbol_cell(wm.symbol_code) if wm else ft.Span("-")),
                ft.Td(f"{wm.air_temperature:.1f}" if wm else "-"),
                ft.Td(f"{wm.wind_speed:.1f}" if wm else "-"),
                ft.Td(wind_arrow_cell(wm.wind_from_direction) if wm else ft.Span("-")),
                ft.Td(f"{wm.cloud_area_fraction:.0f}" if wm else "-"),
                ft.Td(f"{wm.relative_humidity:.0f}" if wm else "-"),
                ft.Td(
                    "–"
                    if (wm and wm.precipitation_amount != wm.precipitation_amount)
                    else (f"{wm.precipitation_amount:.1f}" if wm else "-")
                ),
            )
        )

    # Add remaining weather-only rows (time shown because no wave)
    for i in sorted(unused_weather):
        wm = weather_list[i]
        rows.append(
            ft.Tr(
                ft.Td(to_oslo(wm.time).strftime("%a %-d %b %H:%M")),
                ft.Td("-"),
                ft.Td("-"),
                ft.Td("-"),
                ft.Td("-"),
                ft.Td("-"),
                ft.Td(weather_symbol_cell(wm.symbol_code)),
                ft.Td(f"{wm.air_temperature:.1f}"),
                ft.Td(f"{wm.wind_speed:.1f}"),
                ft.Td(wind_arrow_cell(wm.wind_from_direction)),
                ft.Td(f"{wm.cloud_area_fraction:.0f}"),
                ft.Td(f"{wm.relative_humidity:.0f}"),
                ft.Td(
                    "–"
                    if wm.precipitation_amount != wm.precipitation_amount
                    else f"{wm.precipitation_amount:.1f}"
                ),
            )
        )

    # Final combined table (waves + matched weather + leftover weather-only rows)
    combined_table = ft.Table(
        ft.Thead(ft.Tr(*(ft.Th(h) for h in headers))),
        ft.Tbody(*rows),
        cls="waves-table combined",
    )

    table_scaling_css = ft.Style(
        """
        .waves-table.combined { border-collapse:separate; }
        .waves-table.combined th { font-size:.70rem; }
        .waves-table.combined td { font-size:.83rem; }
        .waves-table.combined td:nth-child(3),
        .waves-table.combined td:nth-child(4),
        .waves-table.combined td:nth-child(10) { text-align:center; width:48px; }
        .waves-table.combined td .arrow { font-size:20px; }
        @media (max-width:880px){
            .waves-table.combined td { font-size:.74rem; }
            .waves-table.combined td .arrow { font-size:18px; }
        }
        """
    )

    dark_css = ft.Style(WAVE_DETAIL_DARK_CSS)
    # Additional contrast overrides for dark theme legibility
    contrast_fix_css = ft.Style(
        """
        /* Accessibility / contrast fixes for wave detail view */
        .meta { color:#cfe9f7 !important; opacity:.95; }
        .meta span, .meta p { color:#cfe9f7 !important; }
        .grid { display:grid; gap:.85rem; grid-template-columns:repeat(auto-fit,minmax(110px,1fr)); margin:1.1rem 0 1.35rem; }
        .grid .card { background:#13232d; border:1px solid #224054; border-radius:12px; padding:.65rem .7rem .55rem; box-shadow:0 2px 4px -2px rgba(0,0,0,.55),0 0 0 1px rgba(120,200,255,.08); }
        .grid .card h3 { margin:0 0 .35rem; font-size:.62rem; text-transform:uppercase; letter-spacing:.55px; font-weight:600; color:#8fd1ff; opacity:.95; }
        .grid .card p { margin:0; font-size:.95rem; font-weight:600; letter-spacing:.3px; color:#f4fbff; text-shadow:0 0 4px rgba(0,0,0,.55); }
        h2, h1, h2 span, h2 strong { color:#e7f5ff !important; }
        h2 { letter-spacing:.5px; }
        a.back { color:#89d2ff !important; }
        a.back:hover { color:#b4e5ff !important; }
        .waves-table.combined th, .waves-table.combined td { color:#eef9ff; }
        .waves-table.combined td .arrow { color:#f8fbff; }
        footer.meta, .meta:last-of-type { color:#b8d7e6 !important; }
        @media (max-width:820px){
            .grid { gap:.65rem; }
            .grid .card { padding:.55rem .55rem .5rem; }
            .grid .card p { font-size:.9rem; }
        }
        """
    )

    latest = wi.data[0]
    summary_cards = ft.Div(
        ft.Div(
            ft.Div(
                ft.H3("Wave Height"),
                ft.P(f"{latest.sea_surface_wave_height:.2f} m"),
                cls="card",
            ),
            ft.Div(
                ft.H3("Water Temp"),
                ft.P(f"{latest.sea_water_temperature:.1f} °C"),
                cls="card",
            ),
            ft.Div(
                ft.H3("From Dir"),
                ft.P(f"{latest.sea_surface_wave_from_direction:.0f}°"),
                cls="card",
            ),
            ft.Div(
                ft.H3("To Dir"),
                ft.P(f"{latest.sea_water_to_direction:.0f}°"),
                cls="card",
            ),
            ft.Div(
                ft.H3("Speed"), ft.P(f"{latest.sea_water_speed:.2f} m/s"), cls="card"
            ),
            cls="grid",
        )
    )

    return (
        ft.Title(f"Waves · {name}"),
        dark_css,
        contrast_fix_css,
        table_scaling_css,
        ft.A("← Back to map", href="/", cls="back"),
        ft.H1(f"Wave forecast - {name}"),
        ft.Div(
            f"Lat {lat:.4f}, Lon {lon:.4f}",
            cls="meta",
        ),
        summary_cards,
        ft.H2("Waves + Weather"),
        combined_table,
        ft.Div(ft.P("Data: api.met.no - oceanforecast & locationforecast"), cls="meta"),
    )


@rt("/wx_icon/{name:str}")
def weather_icon(name: str):
    """Serve weather SVG icon by symbol code name (case-sensitive to filenames)."""
    # Basic security: disallow traversal
    if "/" in name or ".." in name:
        return "Bad Request", 400

    # Normalize filename
    if not name.endswith(".svg"):
        name = f"{name}.svg"

    # Static resolved icon directory (single known location)
    ICON_DIR = Path(__file__).resolve().parent / "data" / "svg"
    # Build cache of available icons (filenames) once
    if not hasattr(weather_icon, "_icon_cache"):
        try:
            weather_icon._icon_cache = {p.name: p for p in ICON_DIR.glob("*.svg")}
        except Exception:
            weather_icon._icon_cache = {}

    cache: dict = weather_icon._icon_cache  # type: ignore
    icon_path = cache.get(name)

    if icon_path is None or not icon_path.exists():
        # Debug print to diagnose missing icon issues
        print(f"[wx_icon] MISS {name}; dir={ICON_DIR} has={len(cache)} entries")
        placeholder = (
            "<svg xmlns='http://www.w3.org/2000/svg' width='42' height='42' viewBox='0 0 42 42'>"
            "<rect x='1' y='1' width='40' height='40' fill='none' stroke='#ff4d4d' stroke-width='2'/>"
            f"<text x='21' y='22' font-size='7' text-anchor='middle' fill='#ff4d4d'>{name[:2]}</text>"
            "</svg>"
        )
        hdrs = {
            "Content-Type": "image/svg+xml; charset=utf-8",
            "Cache-Control": "no-cache",
        }
        return placeholder, hdrs, 200  # return 200 so browser stops retrying

    try:
        data = icon_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[wx_icon] READ ERROR {name}: {e}")
        return "", 500

    hdrs = {
        "Content-Type": "image/svg+xml; charset=utf-8",
        "Cache-Control": "public, max-age=86400",
    }
    return data, hdrs


@rt("/tables")
def list_tables():
    """List available database tables with counts."""
    # sqlite_minutils stores tables under db.t; we can iterate attributes
    table_objs = []
    for tname in dir(db.t):  # type: ignore[attr-defined]
        if tname.startswith("_"):
            continue
        try:
            tbl = getattr(db.t, tname)
            # crude heuristic: has count attribute
            _ = tbl.count  # may raise
            table_objs.append((tname, tbl))
        except Exception:
            continue

    items = []
    for name_, tbl in sorted(table_objs):
        count = getattr(tbl, "count", 0)
        items.append(
            ft.Li(
                ft.A(name_, href=f"/table/{name_.lower()}"),
                ft.Span(str(count), cls="count"),
            )
        )

    supplemental = ft.Style(
        """
        ul.tables { list-style:none; padding:0; margin:0 0 1.2rem; display:grid; gap:.55rem; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); }
        ul.tables li { background:#121e27; border:1px solid #1d2731; border-radius:9px; padding:.65rem .75rem; font-size:.75rem; display:flex; justify-content:space-between; gap:.6rem; align-items:center; transition:background .18s ease,border-color .18s ease; }
        ul.tables li:hover { background:#1d2a34; border-color:#27455a; }
        ul.tables li a { flex:1; font-weight:600; letter-spacing:.4px; color:#89d2ff; }
        ul.tables li span.count { font-size:.6rem; opacity:.6; font-variant-numeric:tabular-nums; background:#1c2731; padding:2px 6px 3px; border-radius:6px; }
        .topbar { display:flex; gap:.9rem; align-items:center; margin-bottom:1rem; }
        .topbar a { font-size:.7rem; text-transform:uppercase; letter-spacing:.55px; opacity:.8; }
        """
    )

    return (
        ft.Title("Tables"),
        ft.Style(WAVE_DETAIL_DARK_CSS),
        supplemental,
        ft.Div(
            ft.Div(
                ft.H1("Tables"),
                ft.A("← Map", href="/"),
                cls="topbar",
            ),
            ft.Ul(*items, cls="tables"),
            ft.Div(ft.Span("Inspect stored data"), cls="meta"),
        ),
    )


@rt("/table/{table_name:str}")
def show_table(table_name: str):
    """Render rows of a specific table (limited) with unified dark theme."""
    tname = table_name.lower()
    target = None
    for attr in dir(db.t):
        if attr.lower() == tname:
            target = getattr(db.t, attr)
            break
    if target is None:
        return ft.Style(WAVE_DETAIL_DARK_CSS), ft.H1("Not found"), 404

    rows = list(target(limit=500))  # type: ignore
    cols = list(rows[0].keys()) if rows else []
    header = ft.Tr(*(ft.Th(c) for c in cols)) if cols else None
    body = [ft.Tr(*(ft.Td(str(r.get(c, ""))) for c in cols)) for r in rows]

    table_el = (
        ft.Div(
            ft.Table(
                ft.Thead(header) if header else None,
                ft.Tbody(*body),
                cls="db-table",
            ),
            cls="scroll-x",
        )
        if rows
        else ft.P("(empty table)")
    )

    supplemental = ft.Style(
        """
        .topbar { display:flex; gap:.9rem; align-items:center; margin-bottom:1rem; }
        .topbar a { font-size:.7rem; text-transform:uppercase; letter-spacing:.55px; opacity:.8; }
        table.db-table { border-collapse:separate; border-spacing:0; width:100%; max-width:100%; font-size:.72rem; background:#101820; border:1px solid #1d2731; border-radius:12px; overflow:hidden; }
        table.db-table thead { background:linear-gradient(180deg,#18232d,#141e26); }
    table.db-table th { text-align:left; padding:7px 9px; font-weight:600; border-bottom:1px solid #24313d; font-size:.65rem; letter-spacing:.4px; color:#f8fbff; }
        table.db-table td { padding:5px 9px; border-bottom:1px solid #1d2731; max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        table.db-table tbody tr:nth-child(odd) td { background:#121e27; }
        table.db-table tbody tr:nth-child(even) td { background:#0f1a22; }
        table.db-table tbody tr:hover td { background:#1d2a34; }
        .scroll-x { overflow-x:auto; padding-bottom:.5rem; }
        @media (max-width:820px){ table.db-table th, table.db-table td { padding:4px 6px; } }
        """
    )

    return (
        ft.Title(f"Table · {tname}"),
        ft.Style(WAVE_DETAIL_DARK_CSS),
        supplemental,
        ft.Div(
            ft.Div(
                ft.H1(tname),
                ft.A("← All tables", href="/tables"),
                ft.A("Map", href="/"),
                cls="topbar",
            ),
            table_el,
            ft.Div(ft.Span(f"Rows: {len(rows)}"), cls="meta"),
        ),
    )
