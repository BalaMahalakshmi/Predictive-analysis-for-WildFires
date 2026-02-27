import folium
import os
import time
import pandas as pd
from config import LOCATIONS, ALERT_LOG_PATH

# Tamil Nadu center — default view
TN_LAT  = 11.1271
TN_LON  = 78.6569
TN_ZOOM = 7   # shows all of Tamil Nadu nicely

INDIA_LAT  = 20.5937
INDIA_LON  = 78.9629

RISK_COLOR = {
    "CRITICAL": "#DC2626",
    "HIGH"    : "#EA580C",
    "MEDIUM"  : "#D97706",
    "LOW"     : "#16A34A",
    "UNKNOWN" : "#3B82F6",
}
FOLIUM_COLOR = {
    "CRITICAL": "red",
    "HIGH"    : "orange",
    "MEDIUM"  : "beige",
    "LOW"     : "green",
    "UNKNOWN" : "blue",
}
CIRCLE_RADIUS = {
    "CRITICAL": 20000,
    "HIGH"    : 15000,
    "MEDIUM"  : 12000,
    "LOW"     : 10000,
    "UNKNOWN" : 8000,
}
ZOOM_LEVEL = {
    "CRITICAL": 12,
    "HIGH"    : 11,
    "MEDIUM"  : 10,
    "LOW"     : 10,
    "UNKNOWN" : 10,
}


def _make_map(lat, lon, zoom):
    """Create a folium map centered at given location."""
    return folium.Map(
        location   = [lat, lon],
        zoom_start = zoom,
        tiles      = "OpenStreetMap",
    )


def _popup_html(result):
    risk  = result["risk"]["level"]
    color = RISK_COLOR.get(risk, "#3B82F6")
    prob  = round(result["probability"] * 100, 1)
    w     = result["weather"]
    f     = result["fwi"]
    maps  = result["maps_url"]
    return (
        '<div style="font-family:Segoe UI,sans-serif;background:#0F172A;color:#F1F5F9;'
        'border-radius:10px;padding:14px;min-width:260px;border:2px solid ' + color + ';">'
        '<div style="font-size:15px;font-weight:900;color:' + color + ';margin-bottom:8px;">'
        + result["location"] + '</div>'
        '<div style="background:' + color + '22;border:1px solid ' + color + ';'
        'border-radius:6px;padding:8px;text-align:center;margin-bottom:10px;">'
        '<span style="font-size:20px;font-weight:900;color:' + color + ';">' + risk + '</span>'
        '<span style="color:#94A3B8;font-size:12px;margin-left:8px;">' + str(prob) + '% fire probability</span>'
        '</div>'
        '<table style="width:100%;font-size:12px;">'
        '<tr><td style="color:#94A3B8;padding:3px;">Temp</td>'
        '<td style="font-weight:bold;padding:3px;">' + str(w["Temperature"]) + ' C</td>'
        '<td style="color:#94A3B8;padding:3px;">Humidity</td>'
        '<td style="font-weight:bold;padding:3px;">' + str(w["RH"]) + '%</td></tr>'
        '<tr><td style="color:#94A3B8;padding:3px;">Wind</td>'
        '<td style="font-weight:bold;padding:3px;">' + str(w["Ws"]) + ' km/h</td>'
        '<td style="color:#94A3B8;padding:3px;">Rain</td>'
        '<td style="font-weight:bold;padding:3px;">' + str(w["Rain"]) + ' mm</td></tr>'
        '<tr><td style="color:#94A3B8;padding:3px;">FWI</td>'
        '<td style="font-weight:bold;color:' + color + ';padding:3px;">' + str(f["FWI"]) + '</td>'
        '<td style="color:#94A3B8;padding:3px;">Time</td>'
        '<td style="color:#64748B;font-size:10px;padding:3px;">' + str(result["timestamp"]) + '</td></tr>'
        '</table>'
        '<div style="margin-top:10px;">'
        '<a href="' + maps + '" target="_blank" style="color:' + color + ';font-size:11px;'
        'text-decoration:none;border:1px solid ' + color + '44;padding:3px 8px;border-radius:5px;">'
        'Open in Google Maps</a></div></div>'
    )


def _add_pin(m, result):
    lat    = result["lat"]
    lon    = result["lon"]
    risk   = result["risk"]["level"]
    prob   = round(result["probability"] * 100, 1)
    hc     = RISK_COLOR.get(risk, "#3B82F6")
    fc     = FOLIUM_COLOR.get(risk, "blue")
    radius = CIRCLE_RADIUS.get(risk, 8000)
    tip    = result["location"] + " — " + risk + " (" + str(prob) + "%)"
    popup  = folium.Popup(_popup_html(result), max_width=300)

    folium.Circle(location=[lat,lon], radius=radius*2.5,
                  color=hc, fill=True, fill_color=hc, fill_opacity=0.06, weight=1).add_to(m)
    folium.Circle(location=[lat,lon], radius=radius,
                  color=hc, fill=True, fill_color=hc, fill_opacity=0.40, weight=3,
                  popup=popup, tooltip=folium.Tooltip(tip)).add_to(m)
    folium.Marker(location=[lat,lon],
                  icon=folium.Icon(color=fc,
                                   icon="fire" if risk in ["HIGH","CRITICAL"] else "info-sign",
                                   prefix="glyphicon"),
                  popup=popup, tooltip=tip).add_to(m)
    return m


def _add_legend(m):
    html = (
        '<div style="position:fixed;bottom:36px;right:16px;'
        'background:rgba(15,23,42,0.93);border:1px solid #334155;'
        'border-radius:10px;padding:12px 16px;z-index:9999;'
        'font-family:Segoe UI,sans-serif;font-size:12px;color:#F1F5F9;">'
        '<div style="font-weight:bold;color:#94A3B8;letter-spacing:2px;font-size:10px;margin-bottom:8px;">RISK LEVELS</div>'
        '<div style="margin:4px 0;"><span style="color:#DC2626;font-size:14px;">&#9679;</span>&nbsp; CRITICAL — Alert Sent</div>'
        '<div style="margin:4px 0;"><span style="color:#EA580C;font-size:14px;">&#9679;</span>&nbsp; HIGH — Alert Sent</div>'
        '<div style="margin:4px 0;"><span style="color:#D97706;font-size:14px;">&#9679;</span>&nbsp; MEDIUM — Monitoring</div>'
        '<div style="margin:4px 0;"><span style="color:#16A34A;font-size:14px;">&#9679;</span>&nbsp; LOW — Safe</div>'
        '</div>'
    )
    m.get_root().html.add_child(folium.Element(html))
    return m


def _inject_zoom(html, lat, lon, zoom):
    """Inject JS to force map zoom — bypasses all Streamlit caching."""
    js = (
        '<script>'
        'window.addEventListener("load", function() {'
        '  setTimeout(function() {'
        '    var maps = Object.values(window).filter(function(v) {'
        '      return v && v._leaflet_id !== undefined;'
        '    });'
        '    maps.forEach(function(m) {'
        '      try { m.setView([' + str(lat) + ',' + str(lon) + '],' + str(zoom) + '); } catch(e) {}'
        '    });'
        '  }, 500);'
        '});'
        '</script>'
    )
    return html.replace("</body>", js + "</body>")


def get_map_html(m, force_lat=None, force_lon=None, force_zoom=None):
    """Convert folium map to HTML string, optionally injecting force-zoom JS."""
    html = m.get_root().render()
    if force_lat is not None:
        html = _inject_zoom(html, force_lat, force_lon, force_zoom)
    return html


# ══════════════════════════════════════════════════════════════════
# PUBLIC MAP BUILDERS
# ══════════════════════════════════════════════════════════════════

def build_tamilnadu_map():
    """
    Default map — shows full Tamil Nadu.
    Shown before any prediction is made.
    """
    m = _make_map(TN_LAT, TN_LON, TN_ZOOM)

    # Tamil Nadu boundary highlight
    folium.Rectangle(
        bounds=[[8.0, 76.2], [13.6, 80.4]],
        color="#EF4444", fill=True,
        fill_color="#EF4444", fill_opacity=0.04,
        weight=2, dash_array="6 4",
        tooltip="Tamil Nadu"
    ).add_to(m)

    # Title overlay
    title = (
        '<div style="position:fixed;top:14px;left:50%;transform:translateX(-50%);'
        'background:rgba(15,23,42,0.92);border:1px solid #EF4444;border-radius:8px;'
        'padding:7px 20px;z-index:9999;font-family:Segoe UI,sans-serif;'
        'font-size:13px;font-weight:bold;color:#F1F5F9;white-space:nowrap;">'
        '🔥 Wildfire Risk Monitor — Tamil Nadu'
        '<span style="color:#64748B;font-size:11px;font-weight:normal;">'
        ' | Search a city or forest on the left</span></div>'
    )
    m.get_root().html.add_child(folium.Element(title))
    return get_map_html(m, TN_LAT, TN_LON, TN_ZOOM)


def build_live_map(result):
    """Zooms to predicted location with risk circles."""
    lat  = result["lat"]
    lon  = result["lon"]
    risk = result["risk"]["level"]
    zoom = ZOOM_LEVEL.get(risk, 10)

    m = _make_map(lat, lon, zoom)
    m = _add_pin(m, result)
    m = _add_legend(m)
    return get_map_html(m, lat, lon, zoom)


def build_multizone_map(predictions):
    """All zones on Tamil Nadu map."""
    valid = [r for r in predictions if r]
    if not valid:
        return build_tamilnadu_map()

    m = _make_map(TN_LAT, TN_LON, TN_ZOOM)
    for r in valid:
        m = _add_pin(m, r)

    lats = [r["lat"] for r in valid]
    lons = [r["lon"] for r in valid]
    m.fit_bounds([
        [min(lats)-0.5, min(lons)-0.5],
        [max(lats)+0.5, max(lons)+0.5]
    ])
    m = _add_legend(m)
    return get_map_html(m)


def build_history_heatmap():
    """Heatmap from prediction CSV."""
    if not os.path.exists(ALERT_LOG_PATH) or os.path.getsize(ALERT_LOG_PATH) == 0:
        return build_tamilnadu_map()
    try:
        from folium.plugins import HeatMap
        df = pd.read_csv(ALERT_LOG_PATH, engine="python", on_bad_lines="skip")
        if df.empty or "lat" not in df.columns:
            return build_tamilnadu_map()
        wt = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        df["weight"] = df["risk_level"].map(wt).fillna(1)
        m = _make_map(TN_LAT, TN_LON, TN_ZOOM)
        HeatMap([[r["lat"],r["lon"],r["weight"]] for _,r in df.iterrows()],
                radius=35, blur=25, max_zoom=12,
                gradient={"0.2":"#16A34A","0.4":"#D97706","0.7":"#EA580C","1.0":"#DC2626"}
                ).add_to(m)
        for _, row in df.drop_duplicates("location").iterrows():
            folium.Marker([row["lat"],row["lon"]],
                          icon=folium.Icon(color="white",icon="map-marker"),
                          tooltip=str(row["location"])).add_to(m)
        return get_map_html(m, TN_LAT, TN_LON, TN_ZOOM)
    except Exception:
        return build_tamilnadu_map()


def build_mini_map(lat, lon, name, risk="UNKNOWN"):
    """Sidebar preview — always zooms to location."""
    hc = RISK_COLOR.get(risk, "#3B82F6")
    fc = FOLIUM_COLOR.get(risk, "blue")
    m  = _make_map(lat, lon, 9)
    folium.Marker([lat,lon], icon=folium.Icon(color=fc,icon="map-marker",prefix="glyphicon"),
                  tooltip=name).add_to(m)
    folium.Circle([lat,lon], radius=8000, color=hc, fill=True, fill_opacity=0.25, weight=2).add_to(m)
    return get_map_html(m, lat, lon, 9)