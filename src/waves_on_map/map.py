import json
from pathlib import Path

import folium
import topojson


def get_map():
    """Create a folium map with CartoDB dark matter tiles."""
    # dark_url = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"

    m = folium.Map(
        location=[59.8739721, 10.7449325],  # could be based on something smarter
        min_zoom=9,
        max_zoom=15,
        disable_3d=True,
        zoom_start=13,
        tiles="CartoDB dark_matter",
        attr="© OpenStreetMap contributors © CartoDB",
    )
    # m = add_json_lines(m, Path("data/Kommuner-L-Oslo-Nesodden.topojson"))
    return m
    # folium.TileLayer(
    #     tiles=dark_url,
    #     attr="© OpenStreetMap © CartoDB",
    #     name="CartoDB Dark All",
    #     overlay=False,
    #     control=True,
    # ).add_to(m)


def add_json_lines(m, path: Path):
    """Create a folium map with local GeoJSON data."""

    try:
        with open(path, "r") as f:
            data = json.load(f)

        if path.suffix == ".topojson":
            with open(path, "r") as f:
                data = topojson.Topology(data, object_name="Kommuner").to_geojson()

        folium.GeoJson(
            data,
            style_function=lambda feature: {
                "color": "yellow",
                "weight": 3,
                "opacity": 0.9,
            },
        ).add_to(m)

    except Exception as e:
        print(f"Error loading local data: {e}")

    return m


def add_clickable_arrow(
    map_obj,
    lat,
    lng,
    rotation: float = 0,
    popup_text: str = "Arrow Info",
    color: str = "#ff4d4d",
    metrics_html: str | None = None,
):
    """Add a clickable rotated arrow marker with optional metrics inside a round badge."""
    if metrics_html:
        html = f"""
<div style='position:relative;pointer-events:auto;font-family:system-ui,sans-serif;'>
                    <div style='width:60px;height:60px;position:relative;padding:4px;background:#2a0e11;background:radial-gradient(circle at 42% 34%,rgba(255,120,120,.55),rgba(40,8,10,.94));border:2px solid #ff6d6d;border-radius:50%;box-shadow:0 3px 10px -4px rgba(0,0,0,.85),0 0 0 1px rgba(255,120,120,.45);overflow:hidden;box-sizing:border-box;'>
                        <div style='position:absolute;top:50%;left:50%;transform:translate(-50%,-50%) rotate({rotation}deg);font-size:30px;line-height:1;color:{color};filter:drop-shadow(0 0 5px rgba(0,0,0,.95));font-weight:800;text-shadow:0 0 7px rgba(255,120,120,.65);'>↑</div>
                        {metrics_html}
                    </div>
</div>
""".strip()
        icon = folium.DivIcon(html=html)
    else:
        icon = folium.Icon(icon="arrow-up", prefix="fa", color="red")

    popup = folium.Popup(
        f"<div style='font:12px/1.3 system-ui,sans-serif;color:#e6edf3;'><b>Arrow Details</b><br>Rotation: {rotation}°<br>{popup_text}</div>",
        max_width=220,
    )

    marker = folium.Marker(location=[lat, lng], icon=icon, popup=popup)
    marker.add_to(map_obj)
    return marker
