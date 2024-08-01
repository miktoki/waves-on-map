"""Centralized static assets (CSS/JS) for the waves-on-map app.

This keeps large multiline strings out of the route module to improve readability.
Add or modify styles/scripts here and import the needed constants in `app_map.py`.
"""

# --- Map page dark theme CSS ---
MAP_DARK_CSS = """
:root { color-scheme: dark; }
html, body { background:#0b1015 !important; color:#e6edf3; font-family:system-ui,sans-serif; margin:0; padding:0; }
body { position:relative; min-height:100vh; }
body::before { content:""; position:fixed; inset:0; background:#0b1015; background-image:radial-gradient(circle at 25% 18%, rgba(77,171,247,.08), transparent 60%), radial-gradient(circle at 78% 72%, rgba(130,207,255,.07), transparent 65%); pointer-events:none; }
a { color:#58a6ff; }
.folium-map, #map { outline:none; }
.leaflet-container { background:transparent !important; font:12px/1.4 system-ui,sans-serif; }
.leaflet-bar a, .leaflet-bar a:hover { background:#161b22; color:#e6edf3; border-bottom:1px solid #30363d; }
.leaflet-bar a:last-child { border-bottom:none; }
.leaflet-control-zoom, .leaflet-control-attribution { border:1px solid #30363d !important; }
.leaflet-control-attribution { background:#161b22 !important; color:#8b949e !important; }
.leaflet-control-attribution a { color:#58a6ff !important; }
.leaflet-popup-content-wrapper, .leaflet-popup-tip { background:#0b1218 !important; color:#e8f2f9 !important; border:1px solid #1d2b36 !important; box-shadow:0 6px 22px -8px rgba(0,0,0,.9),0 0 0 1px rgba(77,171,247,.15) !important; backdrop-filter:blur(4px); }
.leaflet-popup-content { background:transparent !important; }
.leaflet-popup-content { margin:8px 10px; }
.leaflet-marker-icon { filter:drop-shadow(0 0 2px #000); }
::selection { background:#1f6feb; color:#fff; }
""".strip()

# --- Favicon (inline SVG & data URL) ---
FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
    "<defs><linearGradient id='g' x1='0' x2='1' y1='0' y2='1'>"
    "<stop offset='0%' stop-color='#4dabf7'/><stop offset='100%' stop-color='#1e3a8a'/></linearGradient></defs>"
    "<rect width='64' height='64' rx='12' fill='#0d1117'/>"
    "<path d='M8 38q8-12 16 0t16 0 16 0' fill='none' stroke='url(#g)' stroke-width='6' stroke-linecap='round' stroke-linejoin='round'/>"
    "<path d='M8 26q8-12 16 0t16 0 16 0' fill='none' stroke='#82cfff' stroke-opacity='.55' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'/>"
    "</svg>"
)

try:
    import base64 as _b64

    FAVICON_DATA_URL = (
        "data:image/svg+xml;base64," + _b64.b64encode(FAVICON_SVG.encode()).decode()
    )
except Exception:  # pragma: no cover - fallback
    FAVICON_DATA_URL = "data:image/svg+xml;utf8," + FAVICON_SVG

# --- Wave detail page dark theme CSS ---
WAVE_DETAIL_DARK_CSS = """
:root { color-scheme: dark; }
html, body { background:#0b1015 !important; color:#d9e2ec; font-family:system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', Arial, sans-serif; margin:0; padding:0; -webkit-font-smoothing:antialiased; min-height:100%; }
body { min-height:100vh; padding:1.6rem clamp(0.8rem,2vw,2.2rem); display:flex; flex-direction:column; }
body > * { position:relative; z-index:1; }
body::before { content:""; position:fixed; inset:0; background:#0b1015; background-image:radial-gradient(circle at 25% 15%, rgba(77,171,247,.08), transparent 60%), radial-gradient(circle at 80% 70%, rgba(130,207,255,.07), transparent 65%); pointer-events:none; }
h1 { font-size:1.45rem; letter-spacing:.5px; margin:0 0 1rem; font-weight:600; background:linear-gradient(90deg,#4dabf7,#82cfff); -webkit-background-clip:text; color:transparent; }
a { color:#4dabf7; text-decoration:none; }
a:hover { text-decoration:underline; }
.back { display:inline-block; margin-bottom:1.1rem; font-size:0.78rem; letter-spacing:.5px; text-transform:uppercase; color:#82cfff; opacity:.85; }
.meta { font-size:0.75rem; opacity:0.65; margin-bottom:1.05rem; letter-spacing:.4px; }
.grid { display:flex; gap:0.9rem; flex-wrap:wrap; margin:0 0 1.1rem; }
.card { background:linear-gradient(145deg,#121a23,#0d141b); padding:0.8rem 0.95rem; border:1px solid #1d2731; border-radius:10px; min-width:140px; position:relative; box-shadow:0 2px 4px rgba(0,0,0,.4),0 4px 16px -6px rgba(0,0,0,.6); }
.card::after { content:""; position:absolute; inset:0; border-radius:inherit; pointer-events:none; background:linear-gradient(120deg,rgba(77,171,247,.15),rgba(130,207,255,0) 40%,rgba(130,207,255,.18)); mix-blend-mode:overlay; opacity:.6; }
.card h3 { font-size:0.63rem; text-transform:uppercase; letter-spacing:.55px; margin:0 0 5px; font-weight:600; opacity:.7; }
.card p { margin:0; font-size:0.92rem; color:#ebf4ff; font-weight:500; }
table.waves-table { border-collapse:separate; border-spacing:0; width:100%; max-width:960px; font-size:0.78rem; background:#101820; border:1px solid #1d2731; border-radius:12px; overflow:hidden; box-shadow:0 2px 4px rgba(0,0,0,.5), 0 8px 24px -10px rgba(0,0,0,.7); }
table.waves-table thead { background:linear-gradient(180deg,#18232d,#141e26); position:sticky; top:0; z-index:2; }
table.waves-table th { padding:9px 10px 8px; text-align:left; font-weight:600; letter-spacing:.5px; font-size:0.7rem; color:#c8d4e0; border-bottom:1px solid #24313d; backdrop-filter:blur(3px); }
table.waves-table tbody tr { transition:background .18s ease, transform .18s ease; }
/* Brightened row backgrounds */
table.waves-table tbody tr:nth-child(odd) td { background:#223649; }
table.waves-table tbody tr:nth-child(even) td { background:#274152; }
table.waves-table td { padding:7px 10px 6px; border-bottom:1px solid #1d2731; color:#f8fbff !important; }
/* Ensure any generic data tables also inherit bright text */
table.db-table td { color:#f8fbff !important; }
table.waves-table tbody tr:last-child td { border-bottom:none; }
table.waves-table tr:hover td { background:#254355; color:#ffffff; }
table.waves-table tr:hover { transform:translateY(-1px); }
table.waves-table td:nth-child(2) { font-weight:600; color:#ffffff; }
::-webkit-scrollbar { width:10px; height:10px; }
::-webkit-scrollbar-track { background:#0d141b; }
::-webkit-scrollbar-thumb { background:#1d2731; border-radius:6px; border:2px solid #0d141b; }
::-webkit-scrollbar-thumb:hover { background:#26323d; }
::selection { background:#276fb4; color:#fff; }
.leaflet-container { background:#0b1015 !important; }
@media (max-width:820px){
  body { padding:1rem 0.8rem 2.2rem; }
  .grid { gap:0.7rem; }
  table.waves-table { font-size:0.72rem; }
  table.waves-table th { padding:7px 8px 6px; }
  table.waves-table td { padding:5px 8px 5px; }
}
""".strip()

# --- Generic data tables dark theme (for /tables and /table/<table>) ---
TABLES_DARK_CSS = """
:root { color-scheme: dark; }
html, body { background:#0d1117; color:#e6edf3; margin:0; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Oxygen,Ubuntu,Cantarell,'Fira Sans','Droid Sans','Helvetica Neue',Arial,sans-serif; }
body { padding:1.4rem clamp(.7rem,2vw,2.1rem); }
h1 { margin:0 0 1rem; font-size:1.35rem; font-weight:600; letter-spacing:.5px; }
h2 { margin:1.8rem 0 .6rem; font-size:1rem; font-weight:600; letter-spacing:.4px; }
a { color:#58a6ff; text-decoration:none; }
a:hover { text-decoration:underline; }
.meta { font-size:.7rem; opacity:.55; letter-spacing:.4px; margin-top:1.2rem; }
ul.tables { list-style:none; padding:0; margin:0 0 1.2rem; display:grid; gap:.55rem; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); }
ul.tables li { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:.65rem .75rem; font-size:.8rem; display:flex; justify-content:space-between; gap:.6rem; align-items:center; }
ul.tables li a { flex:1; font-weight:500; }
ul.tables li span.count { font-size:.65rem; opacity:.65; font-variant-numeric:tabular-nums; }
table.db-table { border-collapse:separate; border-spacing:0; width:100%; max-width:100%; font-size:.72rem; background:#10161d; border:1px solid #30363d; border-radius:10px; overflow:hidden; }
table.db-table thead { background:#161b22; }
table.db-table th { text-align:left; padding:6px 9px; font-weight:600; border-bottom:1px solid #30363d; position:sticky; top:0; background:#161b22; color:#f8fbff; }
table.db-table td { padding:5px 9px; border-bottom:1px solid #262e36; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:#f8fbff; }
/* Brightened db-table rows (odd/even) */
table.db-table tbody tr:nth-child(odd) td { background:#223649; }
table.db-table tbody tr:nth-child(even) td { background:#274152; }
table.db-table tbody tr:hover td { background:#254355; color:#ffffff; }
.scroll-x { overflow-x:auto; padding-bottom:.4rem; }
.badge { background:#1f6feb22; color:#7fb7ff; padding:2px 7px 3px; border:1px solid #1f6feb55; font-size:.55rem; border-radius:999px; letter-spacing:.5px; text-transform:uppercase; }
.topbar { display:flex; flex-wrap:wrap; gap:.8rem; align-items:center; margin-bottom:1rem; }
.spacer { flex:1; }
@media (max-width:800px){ ul.tables { grid-template-columns:repeat(auto-fill,minmax(140px,1fr)); } table.db-table th, table.db-table td { padding:4px 6px; } }
""".strip()

# --- JavaScript: map right-click (simple used during map build via folium) ---
MAP_FOLIUM_INLINE_RIGHT_CLICK = """
<script>
document.addEventListener('DOMContentLoaded', function() {
    const map = document.querySelector('.folium-map')._leaflet_map;
    map.on('contextmenu', function(e) {
        const lat = e.latlng.lat;
        const lng = e.latlng.lng;
        const name = prompt("Enter location name:");
        if (name) {
            fetch('/add_location', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ latitude: lat, longitude: lng, name: name })
            }).then(response => {
                if (response.ok) {
                    alert("Location added successfully!");
                } else {
                    alert("Failed to add location.");
                }
            });
        }
    });
});
</script>
""".strip()

# --- JavaScript: enhanced right-click logic used in FastHTML root route ---
MAP_RIGHT_CLICK_SCRIPT = """
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(function() {
            let map = null;
            if (window[MAP_ID_PLACEHOLDER]) { map = window[MAP_ID_PLACEHOLDER]; }
            else if (window.map) { map = window.map; }
            else {
                for (let prop in window) {
                    try {
                        if (window[prop] && typeof window[prop] === 'object' && window[prop]._container) {
                            if (window[prop]._container.id === MAP_ID_LITERAL) { map = window[prop]; break; }
                        }
                    } catch(_){}
                }
            }
            if (map && typeof map.on === 'function') {
                map.on('contextmenu', function(e) {
                    e.originalEvent.preventDefault();
                    const lat = e.latlng.lat;
                    const lng = e.latlng.lng;
                    const name = prompt('Enter location name:');
                    if (name && name.trim()) {
                        fetch('/add_location', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ latitude: lat, longitude: lng, name: name.trim() })
                        }).then(r => {
                            if (r.ok) { alert('Location added successfully!'); location.reload(); }
                            else { alert('Failed to add location.'); }
                        }).catch(() => alert('Error adding location.'));
                    }
                });
            }
        }, 1200);
    });
""".strip()
