import folium
import os
import pandas as pd
from config import LOCATIONS, ALERT_LOG_PATH

TN_LAT  = 11.1271
TN_LON  = 78.6569
TN_ZOOM = 7

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


def _popup_html(result):
    risk  = result["risk"]["level"]
    color = RISK_COLOR.get(risk, "#3B82F6")
    prob  = round(result["probability"] * 100, 1)
    w     = result["weather"]
    f     = result["fwi"]
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
        '<tr><td style="color:#94A3B8;">Temp</td><td style="font-weight:bold;">' + str(w["Temperature"]) + ' C</td>'
        '<td style="color:#94A3B8;">Humidity</td><td style="font-weight:bold;">' + str(w["RH"]) + '%</td></tr>'
        '<tr><td style="color:#94A3B8;">Wind</td><td style="font-weight:bold;">' + str(w["Ws"]) + ' km/h</td>'
        '<td style="color:#94A3B8;">Rain</td><td style="font-weight:bold;">' + str(w["Rain"]) + ' mm</td></tr>'
        '<tr><td style="color:#94A3B8;">FWI</td><td style="font-weight:bold;color:' + color + ';">' + str(f["FWI"]) + '</td>'
        '<td style="color:#94A3B8;">GPS</td><td style="color:#64748B;font-size:10px;">'
        + str(result["lat"]) + ',' + str(result["lon"]) + '</td></tr>'
        '</table>'
        '<div style="margin-top:10px;">'
        '<a href="https://maps.google.com/?q=' + str(result["lat"]) + ',' + str(result["lon"])
        + '" target="_blank" style="color:' + color + ';font-size:11px;text-decoration:none;'
        'border:1px solid ' + color + '44;padding:3px 8px;border-radius:5px;">Open Google Maps</a>'
        '</div></div>'
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


def _legend_html():
    return (
        '<div style="position:fixed;bottom:30px;right:10px;'
        'background:rgba(15,23,42,0.95);border:1px solid #334155;'
        'border-radius:10px;padding:12px 16px;z-index:9999;'
        'font-family:Segoe UI,sans-serif;font-size:12px;color:#F1F5F9;">'
        '<b style="color:#94A3B8;font-size:10px;letter-spacing:2px;">RISK LEVELS</b><br><br>'
        '<span style="color:#DC2626;">&#9679;</span> CRITICAL — Alert Sent<br>'
        '<span style="color:#EA580C;">&#9679;</span> HIGH — Alert Sent<br>'
        '<span style="color:#D97706;">&#9679;</span> MEDIUM — Monitoring<br>'
        '<span style="color:#16A34A;">&#9679;</span> LOW — Safe'
        '</div>'
    )


def get_map_html(folium_map, center_lat=None, center_lon=None, zoom=None):
    """
    Render folium map to full standalone HTML page.
    Uses full-page approach so the map fills completely — no blank areas.
    """
    # Get the folium HTML
    raw_html = folium_map.get_root().render()

    # Wrap in full page HTML that fills the iframe completely
    full_html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ width:100%; height:100%; overflow:hidden; background:#0F172A; }}
  .folium-map {{ position:absolute; top:0; left:0; width:100%; height:100%; }}
</style>
</head>
<body>
{raw}
<script>
// Force map to fill entire space and zoom to location
window.onload = function() {{
  setTimeout(function() {{
    // Find all leaflet maps and resize + re-center them
    for (var key in window) {{
      try {{
        var obj = window[key];
        if (obj && obj._leaflet_id && obj.setView && obj.invalidateSize) {{
          obj.invalidateSize(true);
          {setview}
        }}
      }} catch(e) {{}}
    }}
  }}, 200);
}};
</script>
</body>
</html>""".format(
        raw=raw_html,
        setview=(
            "obj.setView([" + str(center_lat) + "," + str(center_lon) + "]," + str(zoom) + ");"
            if center_lat is not None else ""
        )
    )
    return full_html


# ═══════════════════════════════════════════════
# PUBLIC BUILDERS
# ═══════════════════════════════════════════════

def build_tamilnadu_map():
    """Default Tamil Nadu overview map."""
    m = folium.Map(
        location=[TN_LAT, TN_LON],
        zoom_start=TN_ZOOM,
        tiles="OpenStreetMap",
    )
    # Red dashed rectangle around Tamil Nadu
    folium.Rectangle(
        bounds=[[8.0, 76.2], [13.6, 80.4]],
        color="#EF4444", fill=True,
        fill_color="#EF4444", fill_opacity=0.03,
        weight=2, dash_array="8 4",
        tooltip="Tamil Nadu — Search any location"
    ).add_to(m)
    m.get_root().html.add_child(folium.Element(
        '<div style="position:fixed;top:10px;left:50%;transform:translateX(-50%);'
        'background:rgba(15,23,42,0.93);border:1px solid #EF4444;border-radius:8px;'
        'padding:7px 18px;z-index:9999;font-family:Segoe UI,sans-serif;'
        'font-size:13px;font-weight:bold;color:#F1F5F9;white-space:nowrap;">'
        '🔥 Wildfire Monitor — Tamil Nadu'
        '<span style="color:#64748B;font-size:11px;font-weight:normal;margin-left:8px;">'
        '| Search a place and click Analyze</span></div>'
    ))
    return get_map_html(m, TN_LAT, TN_LON, TN_ZOOM)


def build_live_map(result):
    """Map zoomed to predicted location."""
    lat  = result["lat"]
    lon  = result["lon"]
    risk = result["risk"]["level"]
    zoom = ZOOM_LEVEL.get(risk, 10)
    m    = folium.Map(location=[lat, lon], zoom_start=zoom, tiles="OpenStreetMap")
    m    = _add_pin(m, result)
    m.get_root().html.add_child(folium.Element(_legend_html()))
    return get_map_html(m, lat, lon, zoom)


def build_multizone_map(predictions):
    valid = [r for r in predictions if r]
    if not valid:
        return build_tamilnadu_map()
    m = folium.Map(location=[TN_LAT, TN_LON], zoom_start=TN_ZOOM, tiles="OpenStreetMap")
    for r in valid:
        m = _add_pin(m, r)
    lats = [r["lat"] for r in valid]
    lons = [r["lon"] for r in valid]
    m.fit_bounds([[min(lats)-0.5, min(lons)-0.5], [max(lats)+0.5, max(lons)+0.5]])
    m.get_root().html.add_child(folium.Element(_legend_html()))
    return get_map_html(m)


def build_history_heatmap():
    if not os.path.exists(ALERT_LOG_PATH) or os.path.getsize(ALERT_LOG_PATH) == 0:
        return build_tamilnadu_map()
    try:
        from folium.plugins import HeatMap
        df = pd.read_csv(ALERT_LOG_PATH, engine="python", on_bad_lines="skip")
        if df.empty or "lat" not in df.columns:
            return build_tamilnadu_map()
        wt = {"CRITICAL":4,"HIGH":3,"MEDIUM":2,"LOW":1}
        df["weight"] = df["risk_level"].map(wt).fillna(1)
        m = folium.Map(location=[TN_LAT, TN_LON], zoom_start=TN_ZOOM, tiles="OpenStreetMap")
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
    hc = RISK_COLOR.get(risk, "#3B82F6")
    fc = FOLIUM_COLOR.get(risk, "blue")
    m  = folium.Map(location=[lat, lon], zoom_start=9, tiles="OpenStreetMap")
    folium.Marker([lat,lon], icon=folium.Icon(color=fc,icon="map-marker",prefix="glyphicon"),
                  tooltip=name).add_to(m)
    folium.Circle([lat,lon], radius=8000, color=hc, fill=True, fill_opacity=0.25, weight=2).add_to(m)
    return get_map_html(m, lat, lon, 9)


# ═══════════════════════════════════════════════
# AUTO MONITOR MAP — shows all zones at once
# ═══════════════════════════════════════════════

def build_automonitor_map(predictions, last_updated=""):
    """
    Full Tamil Nadu map showing ALL 40 zones with live risk.
    predictions: list of result dicts (or None for pending zones).
    Shows color-coded pins for every zone simultaneously.
    """
    m = folium.Map(location=[TN_LAT, TN_LON], zoom_start=TN_ZOOM,
                   tiles="OpenStreetMap")

    # Count by risk
    counts = {"CRITICAL":0, "HIGH":0, "MEDIUM":0, "LOW":0, "PENDING":0}

    for r in predictions:
        if r is None:
            counts["PENDING"] += 1
            continue
        risk = r["risk"]["level"]
        counts[risk] = counts.get(risk, 0) + 1
        m = _add_pin(m, r)

    # ── Top status bar ────────────────────────────────────────────────────
    alert_count = counts["CRITICAL"] + counts["HIGH"]
    if alert_count > 0:
        bar_bg    = "rgba(127,29,29,0.95)"
        bar_border= "#DC2626"
        bar_msg   = ("🔴 FIRE ALERT — " + str(alert_count) +
                     " zone(s) HIGH/CRITICAL risk! Alerts sent.")
        bar_color = "#FCA5A5"
    else:
        bar_bg    = "rgba(5,46,22,0.95)"
        bar_border= "#16A34A"
        bar_msg   = "✅ ALL CLEAR — No fire risk detected across Tamil Nadu"
        bar_color = "#86EFAC"

    status_html = (
        '<div style="position:fixed;top:10px;left:50%;transform:translateX(-50%);'
        'background:' + bar_bg + ';border:2px solid ' + bar_border + ';'
        'border-radius:10px;padding:8px 20px;z-index:9999;'
        'font-family:Segoe UI,sans-serif;text-align:center;white-space:nowrap;">'
        '<div style="font-size:14px;font-weight:900;color:' + bar_color + ';">'
        + bar_msg + '</div>'
        '<div style="font-size:11px;color:#94A3B8;margin-top:3px;">'
        '🔴 Critical:' + str(counts["CRITICAL"]) +
        ' &nbsp;🟠 High:' + str(counts["HIGH"]) +
        ' &nbsp;🟡 Medium:' + str(counts["MEDIUM"]) +
        ' &nbsp;🟢 Low:' + str(counts["LOW"]) +
        (' &nbsp;⏳ Pending:' + str(counts["PENDING"]) if counts["PENDING"] > 0 else '') +
        (' &nbsp;|&nbsp; Updated: ' + last_updated if last_updated else '') +
        '</div></div>'
    )
    m.get_root().html.add_child(folium.Element(status_html))

    # ── Legend ────────────────────────────────────────────────────────────
    legend = (
        '<div style="position:fixed;bottom:30px;right:10px;'
        'background:rgba(15,23,42,0.95);border:1px solid #334155;'
        'border-radius:10px;padding:14px 18px;z-index:9999;'
        'font-family:Segoe UI,sans-serif;font-size:12px;color:#F1F5F9;">'
        '<b style="color:#94A3B8;font-size:10px;letter-spacing:2px;">RISK LEVELS</b><br><br>'
        '<span style="color:#DC2626;font-size:16px;">&#9679;</span> '
        '<b style="color:#DC2626;">CRITICAL</b> — Alert Sent<br>'
        '<span style="color:#EA580C;font-size:16px;">&#9679;</span> '
        '<b style="color:#EA580C;">HIGH</b> — Alert Sent<br>'
        '<span style="color:#D97706;font-size:16px;">&#9679;</span> '
        '<b style="color:#D97706;">MEDIUM</b> — Monitor<br>'
        '<span style="color:#16A34A;font-size:16px;">&#9679;</span> '
        '<b style="color:#16A34A;">LOW</b> — Safe<br>'
        '<br><span style="color:#64748B;font-size:11px;">'
        '📍 Click any pin for details</span>'
        '</div>'
    )
    m.get_root().html.add_child(folium.Element(legend))

    return get_map_html(m, TN_LAT, TN_LON, TN_ZOOM)