import folium
import os
import pandas as pd
from config import LOCATIONS, ALERT_LOG_PATH

# ── India center ───────────────────────────────────────────────────────────
INDIA_LAT  = 20.5937
INDIA_LON  = 78.9629
INDIA_ZOOM = 5

# ── Risk colors ────────────────────────────────────────────────────────────
RISK_COLOR = {
    'CRITICAL': '#DC2626',
    'HIGH'    : '#EA580C',
    'MEDIUM'  : '#D97706',
    'LOW'     : '#16A34A',
    'UNKNOWN' : '#3B82F6',
}
FOLIUM_COLOR = {
    'CRITICAL': 'red',
    'HIGH'    : 'orange',
    'MEDIUM'  : 'beige',
    'LOW'     : 'green',
    'UNKNOWN' : 'blue',
}
CIRCLE_RADIUS = {
    'CRITICAL': 25000,
    'HIGH'    : 18000,
    'MEDIUM'  : 13000,
    'LOW'     : 10000,
    'UNKNOWN' : 8000,
}
ZOOM_LEVEL = {
    'CRITICAL': 11,
    'HIGH'    : 10,
    'MEDIUM'  : 9,
    'LOW'     : 9,
    'UNKNOWN' : 9,
}


def _popup_html(result):
    """Rich HTML popup content."""
    risk  = result['risk']['level']
    color = RISK_COLOR.get(risk, '#3B82F6')
    prob  = round(result['probability'] * 100, 1)

    return (
        '<div style="font-family:Segoe UI,sans-serif;background:#0F172A;'
        'color:#F1F5F9;border-radius:10px;padding:14px;min-width:260px;'
        'border:2px solid ' + color + ';">'

        '<div style="font-size:15px;font-weight:900;color:' + color + ';margin-bottom:8px;">'
        + result['location'] +
        '</div>'

        '<div style="background:' + color + '22;border:1px solid ' + color + ';'
        'border-radius:6px;padding:8px;text-align:center;margin-bottom:10px;">'
        '<span style="font-size:20px;font-weight:900;color:' + color + ';">'
        + risk + '</span>'
        '<span style="color:#94A3B8;font-size:12px;margin-left:8px;">'
        + str(prob) + '% fire probability</span>'
        '</div>'

        '<table style="width:100%;font-size:12px;">'
        '<tr><td style="color:#94A3B8;padding:3px;">Temp</td>'
        '<td style="font-weight:bold;padding:3px;">'
        + str(result['weather']['Temperature']) + ' C</td>'
        '<td style="color:#94A3B8;padding:3px;">Humidity</td>'
        '<td style="font-weight:bold;padding:3px;">'
        + str(result['weather']['RH']) + '%</td></tr>'

        '<tr><td style="color:#94A3B8;padding:3px;">Wind</td>'
        '<td style="font-weight:bold;padding:3px;">'
        + str(result['weather']['Ws']) + ' km/h</td>'
        '<td style="color:#94A3B8;padding:3px;">Rain</td>'
        '<td style="font-weight:bold;padding:3px;">'
        + str(result['weather']['Rain']) + ' mm</td></tr>'

        '<tr><td style="color:#94A3B8;padding:3px;">FWI</td>'
        '<td style="font-weight:bold;color:' + color + ';padding:3px;">'
        + str(result['fwi']['FWI']) + '</td>'
        '<td style="color:#94A3B8;padding:3px;">Time</td>'
        '<td style="color:#64748B;font-size:10px;padding:3px;">'
        + str(result['timestamp']) + '</td></tr>'
        '</table>'

        '<div style="margin-top:10px;">'
        '<a href="https://maps.google.com/?q='
        + str(result['lat']) + ',' + str(result['lon'])
        + '" target="_blank" style="color:' + color + ';font-size:11px;'
        'text-decoration:none;border:1px solid ' + color + '44;'
        'padding:3px 8px;border-radius:5px;">Open in Google Maps</a>'
        '</div>'
        '</div>'
    )


def _add_pin(m, result):
    """Add circles + marker for one prediction result."""
    lat    = result['lat']
    lon    = result['lon']
    risk   = result['risk']['level']
    prob   = round(result['probability'] * 100, 1)
    hc     = RISK_COLOR.get(risk, '#3B82F6')
    fc     = FOLIUM_COLOR.get(risk, 'blue')
    radius = CIRCLE_RADIUS.get(risk, 8000)
    tip    = result['location'] + ' — ' + risk + ' (' + str(prob) + '%)'
    popup  = folium.Popup(_popup_html(result), max_width=300)

    # Outer glow
    folium.Circle(
        location=[lat, lon], radius=radius * 2.2,
        color=hc, fill=True, fill_color=hc,
        fill_opacity=0.06, weight=1
    ).add_to(m)

    # Inner circle
    folium.Circle(
        location=[lat, lon], radius=radius,
        color=hc, fill=True, fill_color=hc,
        fill_opacity=0.40, weight=3,
        popup=popup,
        tooltip=folium.Tooltip(tip, permanent=False)
    ).add_to(m)

    # Marker pin
    folium.Marker(
        location=[lat, lon],
        icon=folium.Icon(
            color  = fc,
            icon   = 'fire' if risk in ['HIGH', 'CRITICAL'] else 'info-sign',
            prefix = 'glyphicon'
        ),
        popup  = popup,
        tooltip= tip
    ).add_to(m)
    return m


def _add_legend(m):
    """Floating risk legend on map."""
    html = (
        '<div style="position:fixed;bottom:36px;right:16px;'
        'background:rgba(15,23,42,0.93);border:1px solid #334155;'
        'border-radius:10px;padding:12px 16px;z-index:9999;'
        'font-family:Segoe UI,sans-serif;font-size:12px;color:#F1F5F9;">'
        '<div style="font-weight:bold;color:#94A3B8;letter-spacing:2px;'
        'font-size:10px;margin-bottom:8px;">RISK LEVELS</div>'
        '<div style="margin:4px 0;"><span style="color:#DC2626;font-size:14px;">&#9679;</span>'
        '&nbsp; CRITICAL</div>'
        '<div style="margin:4px 0;"><span style="color:#EA580C;font-size:14px;">&#9679;</span>'
        '&nbsp; HIGH</div>'
        '<div style="margin:4px 0;"><span style="color:#D97706;font-size:14px;">&#9679;</span>'
        '&nbsp; MEDIUM</div>'
        '<div style="margin:4px 0;"><span style="color:#16A34A;font-size:14px;">&#9679;</span>'
        '&nbsp; LOW</div>'
        '</div>'
    )
    m.get_root().html.add_child(folium.Element(html))
    return m


def get_map_html(folium_map):
    """
    Convert folium map to HTML string.
    This is the KEY function — we render maps as HTML, not st_folium.
    st_folium causes blank maps on many setups.
    """
    return folium_map.get_root().render()


# ══════════════════════════════════════════════════════
#  PUBLIC MAP BUILDERS
# ══════════════════════════════════════════════════════

def build_india_map():
    """Default India overview — shown before any prediction."""
    m = folium.Map(
        location   = [INDIA_LAT, INDIA_LON],
        zoom_start = INDIA_ZOOM,
        tiles      = 'OpenStreetMap',
        width      = '100%',
        height     = '100%',
    )
    # Title overlay
    title = (
        '<div style="position:fixed;top:14px;left:50%;transform:translateX(-50%);'
        'background:rgba(15,23,42,0.92);border:1px solid #EF4444;border-radius:8px;'
        'padding:7px 20px;z-index:9999;font-family:Segoe UI,sans-serif;'
        'font-size:13px;font-weight:bold;color:#F1F5F9;white-space:nowrap;">'
        '🔥 Wildfire Risk Monitor — India &nbsp;'
        '<span style="color:#64748B;font-size:11px;font-weight:normal;">'
        '| Enter location &amp; click Analyze Now</span>'
        '</div>'
    )
    m.get_root().html.add_child(folium.Element(title))
    return m


def build_live_map(result):
    """
    Zooms directly into the predicted location.
    Red/orange/green circles show risk severity.
    """
    lat  = result['lat']
    lon  = result['lon']
    risk = result['risk']['level']
    zoom = ZOOM_LEVEL.get(risk, 9)

    m = folium.Map(
        location   = [lat, lon],   # ← center = user's location
        zoom_start = zoom,          # ← zoomed in
        tiles      = 'OpenStreetMap',
        width      = '100%',
        height     = '100%',
    )

    m = _add_pin(m, result)
    m = _add_legend(m)
    return m


def build_multizone_map(predictions):
    """All zones on India map with auto-fit bounds."""
    valid = [r for r in predictions if r is not None]
    if not valid:
        return build_india_map()

    m = folium.Map(
        location   = [INDIA_LAT, INDIA_LON],
        zoom_start = INDIA_ZOOM,
        tiles      = 'OpenStreetMap',
        width      = '100%',
        height     = '100%',
    )

    for result in valid:
        m = _add_pin(m, result)

    # Auto-fit to show all pins
    lats = [r['lat'] for r in valid]
    lons = [r['lon'] for r in valid]
    m.fit_bounds([
        [min(lats) - 1.5, min(lons) - 1.5],
        [max(lats) + 1.5, max(lons) + 1.5]
    ])

    m = _add_legend(m)
    return m


def build_history_heatmap():
    """Heatmap from CSV logs over India map."""
    if not os.path.exists(ALERT_LOG_PATH):
        return build_india_map()
    if os.path.getsize(ALERT_LOG_PATH) == 0:
        return build_india_map()

    try:
        from folium.plugins import HeatMap
        df = pd.read_csv(ALERT_LOG_PATH)
        if df.empty or 'lat' not in df.columns:
            return build_india_map()

        weight_map = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
        df['weight'] = df['risk_level'].map(weight_map).fillna(1)

        m = folium.Map(
            location   = [INDIA_LAT, INDIA_LON],
            zoom_start = INDIA_ZOOM,
            tiles      = 'OpenStreetMap',
            width      = '100%',
            height     = '100%',
        )

        HeatMap(
            [[r['lat'], r['lon'], r['weight']] for _, r in df.iterrows()],
            radius=35, blur=25, max_zoom=12,
            gradient={
                '0.2': '#16A34A',
                '0.4': '#D97706',
                '0.7': '#EA580C',
                '1.0': '#DC2626',
            }
        ).add_to(m)

        for _, row in df.drop_duplicates('location').iterrows():
            folium.Marker(
                location=[row['lat'], row['lon']],
                icon=folium.Icon(color='white', icon='map-marker'),
                tooltip=str(row['location'])
            ).add_to(m)

        return m
    except Exception:
        return build_india_map()


def build_mini_map(lat, lon, location_name, risk_level='UNKNOWN'):
    """Small preview map — always zooms to given location."""
    hc = RISK_COLOR.get(risk_level, '#3B82F6')
    fc = FOLIUM_COLOR.get(risk_level, 'blue')

    m = folium.Map(
        location   = [lat, lon],
        zoom_start = 8,
        tiles      = 'OpenStreetMap',
        width      = '100%',
        height     = '100%',
    )
    folium.Marker(
        location=[lat, lon],
        icon=folium.Icon(color=fc, icon='map-marker', prefix='glyphicon'),
        tooltip=location_name,
    ).add_to(m)
    folium.Circle(
        location=[lat, lon], radius=8000,
        color=hc, fill=True, fill_opacity=0.25, weight=2
    ).add_to(m)
    return m