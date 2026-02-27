import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os
import time
import csv

from config import LOCATIONS, ALERT_LOG_PATH
from predictor import predict_for_location
from alert_engine import dispatch_alerts
from geocoder import get_coordinates
from map_view import (
    build_tamilnadu_map,
    build_live_map,
    build_multizone_map,
    build_history_heatmap,
)

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Wildfire Alert System",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Inter:wght@300;400;500;600&display=swap');

* { box-sizing: border-box; }

.stApp {
    background: #060B14;
    color: #E2E8F0;
    font-family: 'Inter', sans-serif;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0D1421 !important;
    border-right: 1px solid #1E3A5F !important;
}
section[data-testid="stSidebar"] * { color: #CBD5E1; }

/* Metrics */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #0D1421, #111827);
    border: 1px solid #1E3A5F;
    border-radius: 12px;
    padding: 14px !important;
}
[data-testid="stMetricValue"] { color: #F1F5F9 !important; font-family: 'Rajdhani', sans-serif !important; font-size: 1.6rem !important; }
[data-testid="stMetricLabel"] { color: #64748B !important; font-size: 0.75rem !important; }

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #DC2626, #991B1B) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    letter-spacing: 1.5px !important;
    padding: 0.6rem 1.5rem !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #EF4444, #DC2626) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(220,38,38,0.4) !important;
}

/* Text input */
.stTextInput > div > div > input {
    background: #0D1421 !important;
    border: 1px solid #1E3A5F !important;
    border-radius: 10px !important;
    color: #F1F5F9 !important;
    font-size: 1rem !important;
    padding: 0.6rem 1rem !important;
}
.stTextInput > div > div > input:focus {
    border-color: #EF4444 !important;
    box-shadow: 0 0 0 2px rgba(239,68,68,0.2) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #0D1421;
    border-radius: 10px;
    gap: 4px;
    padding: 4px;
    border: 1px solid #1E3A5F;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border-radius: 8px;
    color: #64748B;
    font-family: 'Rajdhani', sans-serif;
    font-weight: 600;
    font-size: 0.95rem;
    letter-spacing: 0.5px;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #DC2626, #991B1B) !important;
    color: white !important;
}

/* Dataframe */
[data-testid="stDataFrame"] {
    border: 1px solid #1E3A5F;
    border-radius: 10px;
}

/* Divider */
hr { border-color: #1E3A5F; }

/* Map iframe */
iframe {
    border-radius: 14px !important;
    border: 1px solid #1E3A5F !important;
}

/* Selectbox */
.stSelectbox > div > div {
    background: #0D1421 !important;
    border: 1px solid #1E3A5F !important;
    border-radius: 10px !important;
    color: #F1F5F9 !important;
}

/* Spinner */
.stSpinner { color: #EF4444 !important; }

/* Radio */
.stRadio label { color: #94A3B8 !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  Map renderer — unique key every call = no caching
# ══════════════════════════════════════════════════════════════════
def show_map(map_html, height=500):
    uid = "wf_map_" + str(int(time.time() * 1000))
    components.html(
        '<div id="' + uid + '">' + map_html + '</div>',
        height=height + 10,
        scrolling=False
    )


# ══════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════
st.sidebar.markdown("""
<div style="text-align:center; padding:20px 0 10px;">
    <div style="font-size:52px; filter:drop-shadow(0 0 20px #EF444488);">🔥</div>
    <div style="font-family:'Rajdhani',sans-serif; font-size:22px;
                font-weight:700; color:#EF4444; letter-spacing:3px; margin-top:6px;">
        WILDFIRE ALERT
    </div>
    <div style="font-size:11px; color:#334155; margin-top:3px; letter-spacing:1px;">
        REAL-TIME DETECTION SYSTEM
    </div>
</div>
<hr style="border-color:#1E3A5F; margin:10px 0;">
""", unsafe_allow_html=True)

# ── City Search Box ────────────────────────────────────────────────────────
st.sidebar.markdown("""
<div style="font-family:'Rajdhani',sans-serif; font-size:13px;
            color:#64748B; letter-spacing:2px; margin-bottom:6px;">
    SEARCH LOCATION
</div>
""", unsafe_allow_html=True)

city_input = st.sidebar.text_input(
    label       = "City or Town Name",
    value       = "",
    placeholder = "e.g. Coimbatore, Chennai, Ooty...",
    label_visibility = "collapsed"
)

search_btn = st.sidebar.button("🔍  Search Location", use_container_width=True)

# ── Location state ─────────────────────────────────────────────────────────
if "location" not in st.session_state:
    st.session_state.location = {
        "name": "India",
        "lat" : 20.5937,
        "lon" : 78.9629,
        "found": False,
    }

if search_btn and city_input.strip():
    with st.spinner("Finding " + city_input + "..."):
        geo = get_coordinates(city_input.strip())
    if geo:
        st.session_state.location = {
            "name" : geo["display_name"],
            "lat"  : geo["lat"],
            "lon"  : geo["lon"],
            "found": True,
        }
        st.sidebar.success("✅ Found: " + geo["display_name"])
    else:
        # Even if geocoder fails, show map at approximate Tamil Nadu center
        # so user always sees something useful
        st.sidebar.info(
            "📍 Using nearest Tamil Nadu location for: " + city_input.strip()
        )
        st.session_state.location = {
            "name" : city_input.strip() + " region - Tamil Nadu",
            "lat"  : 11.1271,
            "lon"  : 78.6569,
            "found": True,
        }

loc = st.session_state.location

# ── Location info card ─────────────────────────────────────────────────────
if loc["found"]:
    st.sidebar.markdown(
        '<div style="background:#0D1421;border:1px solid #1E3A5F;border-left:3px solid #EF4444;'
        'border-radius:8px;padding:10px 14px;margin:10px 0;">'
        '<div style="font-size:13px;font-weight:600;color:#F1F5F9;">' + loc["name"] + '</div>'
        '<div style="font-size:11px;color:#475569;margin-top:3px;">'
        'Lat: ' + str(loc["lat"]) + ' | Lon: ' + str(loc["lon"]) + '</div>'
        '</div>',
        unsafe_allow_html=True
    )

st.sidebar.markdown('<hr style="border-color:#1E3A5F;">', unsafe_allow_html=True)

# ── Quick city buttons ─────────────────────────────────────────────────────
st.sidebar.markdown("""
<div style="font-family:'Rajdhani',sans-serif; font-size:12px;
            color:#475569; letter-spacing:2px; margin-bottom:8px;">
    QUICK SELECT — TAMIL NADU
</div>
""", unsafe_allow_html=True)

tn_cities = [
    ("Coimbatore", 11.0168, 76.9558),
    ("Chennai",    13.0827, 80.2707),
    ("Madurai",     9.9252, 78.1198),
    ("Salem",      11.6643, 78.1460),
    ("Trichy",     10.7905, 78.7047),
    ("Ooty",       11.4102, 76.6950),
]

# 2 columns of quick buttons
col_q1, col_q2 = st.sidebar.columns(2)
for i, (city, clat, clon) in enumerate(tn_cities):
    col = col_q1 if i % 2 == 0 else col_q2
    if col.button(city, key="quick_" + city, use_container_width=True):
        st.session_state.location = {
            "name" : city + ", Tamil Nadu, India",
            "lat"  : clat,
            "lon"  : clon,
            "found": True,
        }
        st.rerun()

st.sidebar.markdown('<hr style="border-color:#1E3A5F;">', unsafe_allow_html=True)
show_sat = st.sidebar.checkbox("🛰️ Show NASA Satellite Fires", value=False)
st.sidebar.markdown("""
<div style="font-size:11px;color:#334155;text-align:center;margin-top:8px;">
    Weather: OpenWeatherMap API<br>
    Satellite: NASA FIRMS<br>
    Model: XGBoost / Random Forest
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  HEADER
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<div style="
    background: linear-gradient(135deg, #0D1421 0%, #060B14 100%);
    border: 1px solid #1E3A5F;
    border-left: 4px solid #EF4444;
    border-radius: 14px;
    padding: 20px 28px;
    margin-bottom: 20px;
    position: relative;
    overflow: hidden;
">
    <div style="position:absolute;top:-20px;right:-20px;width:120px;height:120px;
                background:radial-gradient(circle,#EF444422,transparent);
                border-radius:50%;"></div>
    <div style="font-family:'Rajdhani',sans-serif; font-size:26px;
                font-weight:700; color:#F8FAFC; letter-spacing:2px;">
        🔥 REAL-TIME WILDFIRE DETECTION & ALERT SYSTEM
    </div>
    <div style="font-size:12px; color:#475569; margin-top:6px; letter-spacing:0.5px;">
        Search any city &nbsp;→&nbsp; Live weather fetch &nbsp;→&nbsp;
        ML fire prediction &nbsp;→&nbsp; Auto alert to fire station &nbsp;→&nbsp; CSV saved
    </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs([
    "🔍  Live Analysis",
    "🗺️  India Map",
    "📋  History Log",
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — LIVE ANALYSIS
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("")

    if not loc["found"]:
        # ── Welcome screen ────────────────────────────────────────────────
        st.markdown("""
<div style="text-align:center; padding:60px 20px;">
    <div style="font-size:72px; margin-bottom:20px;
                filter:drop-shadow(0 0 30px #EF444466);">🔥</div>
    <div style="font-family:'Rajdhani',sans-serif; font-size:32px;
                font-weight:700; color:#F1F5F9; letter-spacing:2px;">
        WILDFIRE RISK PREDICTOR
    </div>
    <div style="font-size:14px; color:#475569; margin-top:10px; max-width:500px; margin-left:auto; margin-right:auto;">
        Type any city or town name in the search box on the left
        and click <span style="color:#EF4444;font-weight:600;">Search Location</span>
        to begin real-time wildfire risk analysis.
    </div>
    <div style="margin-top:40px; display:flex; justify-content:center; gap:30px; flex-wrap:wrap;">
        <div style="background:#0D1421;border:1px solid #1E3A5F;border-radius:10px;padding:16px 24px;text-align:center;">
            <div style="font-size:28px;">🌡️</div>
            <div style="font-size:12px;color:#64748B;margin-top:4px;">Live Weather</div>
        </div>
        <div style="background:#0D1421;border:1px solid #1E3A5F;border-radius:10px;padding:16px 24px;text-align:center;">
            <div style="font-size:28px;">🤖</div>
            <div style="font-size:12px;color:#64748B;margin-top:4px;">ML Prediction</div>
        </div>
        <div style="background:#0D1421;border:1px solid #1E3A5F;border-radius:10px;padding:16px 24px;text-align:center;">
            <div style="font-size:28px;">🚨</div>
            <div style="font-size:12px;color:#64748B;margin-top:4px;">Auto Alert</div>
        </div>
        <div style="background:#0D1421;border:1px solid #1E3A5F;border-radius:10px;padding:16px 24px;text-align:center;">
            <div style="font-size:28px;">📊</div>
            <div style="font-size:12px;color:#64748B;margin-top:4px;">CSV Saved</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
        show_map(build_tamilnadu_map(), height=480)

    else:
        # ── Location found — show analyze button ──────────────────────────
        st.markdown(
            '<div style="background:#0D1421;border:1px solid #1E3A5F;border-left:3px solid #EF4444;'
            'border-radius:10px;padding:12px 18px;margin-bottom:16px;">'
            '<span style="font-size:12px;color:#475569;font-family:Rajdhani,sans-serif;letter-spacing:2px;">SELECTED LOCATION</span><br>'
            '<span style="font-size:18px;font-weight:700;color:#F1F5F9;font-family:Rajdhani,sans-serif;">'
            + loc["name"] + '</span>'
            '<span style="font-size:12px;color:#475569;margin-left:14px;">'
            'Lat: ' + str(loc["lat"]) + '  |  Lon: ' + str(loc["lon"]) + '</span>'
            '</div>',
            unsafe_allow_html=True
        )

        analyze_btn = st.button(
            "🔥  ANALYZE WILDFIRE RISK FOR " + loc["name"].split(",")[0].upper(),
            type="primary",
            use_container_width=True
        )
        st.markdown("")

        if analyze_btn:
            with st.spinner("🌐 Fetching live weather for " + loc["name"] + "..."):
                result = predict_for_location(
                    lat  = loc["lat"],
                    lon  = loc["lon"],
                    name = loc["name"]
                )

            if result is None:
                st.error(
                    "❌ Could not fetch weather data. "
                    "Check your OWM_API_KEY in .env file and internet connection."
                )
                st.stop()

            # ── Auto-save + send alerts ───────────────────────────────────
            dispatch_alerts(result)

            risk_level = result["risk"]["level"]
            prob_pct   = round(result["probability"] * 100, 1)
            weather    = result["weather"]
            fwi        = result["fwi"]

            # ── Risk banner ───────────────────────────────────────────────
            risk_styles = {
                "CRITICAL": ("linear-gradient(135deg,#7F1D1D,#450A0A)",
                             "#FCA5A5", "#DC2626", "🔴 CRITICAL RISK — WILDFIRE IMMINENT"),
                "HIGH"    : ("linear-gradient(135deg,#7C2D12,#431407)",
                             "#FED7AA", "#EA580C", "🟠 HIGH RISK — FIRE CONDITIONS DANGEROUS"),
                "MEDIUM"  : ("linear-gradient(135deg,#78350F,#451A03)",
                             "#FDE68A", "#D97706", "🟡 MEDIUM RISK — MONITOR CONDITIONS"),
                "LOW"     : ("linear-gradient(135deg,#14532D,#052E16)",
                             "#BBF7D0", "#16A34A", "🟢 LOW RISK — CONDITIONS SAFE"),
            }
            bg, fg, bd, msg = risk_styles.get(
                risk_level,
                ("linear-gradient(135deg,#1E293B,#0F172A)", "#F1F5F9", "#475569", risk_level)
            )

            st.markdown(
                '<div style="background:' + bg + ';border:2px solid ' + bd + ';'
                'border-radius:14px;padding:20px 28px;margin-bottom:20px;'
                'box-shadow:0 0 30px ' + bd + '44;text-align:center;">'
                '<div style="font-family:Rajdhani,sans-serif;font-size:32px;'
                'font-weight:700;color:' + fg + ';letter-spacing:2px;">' + msg + '</div>'
                '<div style="font-size:14px;color:' + bd + ';margin-top:6px;">'
                'Fire Probability: <b>' + str(prob_pct) + '%</b>'
                ' &nbsp;|&nbsp; Location: <b>' + loc["name"] + '</b>'
                ' &nbsp;|&nbsp; ✅ Saved to CSV'
                '</div>'
                '</div>',
                unsafe_allow_html=True
            )

            # ── Weather metrics ───────────────────────────────────────────
            st.markdown("""
<div style="font-family:Rajdhani,sans-serif;font-size:12px;
            color:#475569;letter-spacing:2px;margin-bottom:10px;">
    LIVE WEATHER CONDITIONS
</div>
""", unsafe_allow_html=True)
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("🌡️ Temperature",  str(weather["Temperature"]) + " °C",
                      help="Dry hot temperature → higher fire risk")
            c2.metric("💧 Humidity",     str(weather["RH"]) + " %",
                      help="Low humidity → fire spreads faster")
            c3.metric("💨 Wind Speed",   str(weather["Ws"]) + " km/h",
                      help="High wind → fire spreads wider")
            c4.metric("🌧️ Rainfall",     str(weather["Rain"]) + " mm",
                      help="No rain → dry vegetation → fire fuel")
            st.markdown("")

            # ── FWI metrics ───────────────────────────────────────────────
            st.markdown("""
<div style="font-family:Rajdhani,sans-serif;font-size:12px;
            color:#475569;letter-spacing:2px;margin-bottom:10px;">
    FIRE WEATHER INDEX (FWI) COMPONENTS
</div>
""", unsafe_allow_html=True)
            f1,f2,f3,f4,f5,f6 = st.columns(6)
            f1.metric("FFMC", fwi["FFMC"], help="Fine Fuel Moisture Code")
            f2.metric("DMC",  fwi["DMC"],  help="Duff Moisture Code")
            f3.metric("DC",   fwi["DC"],   help="Drought Code")
            f4.metric("ISI",  fwi["ISI"],  help="Initial Spread Index")
            f5.metric("BUI",  fwi["BUI"],  help="Buildup Index")
            f6.metric("🔥 FWI", fwi["FWI"], help="Overall Fire Weather Index")
            st.markdown("")

            # ── Gauge + Map ───────────────────────────────────────────────
            col_g, col_m = st.columns([5, 7])

            with col_g:
                # Gauge
                gc = {
                    "CRITICAL": "#DC2626",
                    "HIGH"    : "#EA580C",
                    "MEDIUM"  : "#D97706",
                    "LOW"     : "#16A34A"
                }
                fig = go.Figure(go.Indicator(
                    mode  = "gauge+number",
                    value = prob_pct,
                    title = {"text": "Fire Probability %",
                             "font": {"size": 14, "color": "#64748B"}},
                    number= {"suffix": "%",
                             "font": {"color": gc.get(risk_level, "#F1F5F9"),
                                      "size": 52}},
                    gauge = {
                        "axis"  : {"range": [0, 100],
                                   "tickcolor": "#334155",
                                   "nticks": 5},
                        "bar"   : {"color": gc.get(risk_level, "#6B7280"),
                                   "thickness": 0.25},
                        "bgcolor"    : "rgba(0,0,0,0)",
                        "bordercolor": "#1E3A5F",
                        "borderwidth": 1,
                        "steps": [
                            {"range": [0,  25], "color": "#052E16"},
                            {"range": [25, 50], "color": "#451A03"},
                            {"range": [50, 75], "color": "#431407"},
                            {"range": [75,100], "color": "#450A0A"},
                        ],
                        "threshold": {
                            "line"     : {"color": "#EF4444", "width": 4},
                            "thickness": 0.75,
                            "value"    : 75
                        }
                    }
                ))
                fig.update_layout(
                    height=300,
                    margin=dict(t=50, b=20, l=30, r=30),
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#F1F5F9")
                )
                st.plotly_chart(fig, use_container_width=True)

                # Alert status box
                if result["risk"]["should_alert"]:
                    st.markdown(
                        '<div style="background:#450A0A;border:2px solid #DC2626;'
                        'border-radius:10px;padding:14px;text-align:center;">'
                        '<div style="font-family:Rajdhani,sans-serif;font-size:18px;'
                        'font-weight:700;color:#FCA5A5;letter-spacing:1px;">'
                        '🚨 EMERGENCY ALERT AUTO-SENT!</div>'
                        '<div style="font-size:12px;color:#EF4444;margin-top:6px;line-height:1.6;">'
                        '✅ SMS sent to Fire Station<br>'
                        '✅ Email sent to Emergency Contacts<br>'
                        '✅ Prediction saved to CSV'
                        '</div>'
                        '<div style="font-size:11px;color:#94A3B8;margin-top:8px;'
                        'border-top:1px solid #7F1D1D;padding-top:8px;">'
                        'What to do: Evacuate nearby areas · Call 101 (Fire) · Call 112 (Emergency)'
                        '</div>'
                        '</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        '<div style="background:#052E16;border:1px solid #16A34A;'
                        'border-radius:10px;padding:14px;text-align:center;">'
                        '<div style="font-family:Rajdhani,sans-serif;font-size:16px;'
                        'font-weight:700;color:#BBF7D0;letter-spacing:1px;">'
                        '✅ CONDITIONS SAFE</div>'
                        '<div style="font-size:12px;color:#16A34A;margin-top:4px;">'
                        'Risk level ' + risk_level + ' — Monitoring active | No alert needed'
                        '</div>'
                        '</div>',
                        unsafe_allow_html=True
                    )

                st.markdown("")
                if st.button("⚡ Force Send Alert", use_container_width=True):
                    result["risk"]["should_alert"] = True
                    dispatch_alerts(result)
                    st.success("Alert manually dispatched!")

            with col_m:
                st.markdown(
                    '<div style="font-family:Rajdhani,sans-serif;font-size:14px;'
                    'font-weight:600;color:#94A3B8;letter-spacing:1px;margin-bottom:8px;">'
                    '📍 MAP — ' + loc["name"].upper() + '</div>',
                    unsafe_allow_html=True
                )

                # Add satellite data if enabled
                import folium as fl
                live_map_html = build_live_map(result)

                if show_sat:
                    from satellite import get_satellite_hotspots
                    with st.spinner("Checking satellite data..."):
                        hotspots = get_satellite_hotspots(loc["lat"], loc["lon"])
                    if hotspots is not None:
                        st.warning("🛰️ " + str(len(hotspots)) + " satellite fire hotspot(s) detected nearby!")

                # ← Render map zoomed to exact city
                show_map(live_map_html, height=520)

        else:
            # Location selected but not analyzed yet
            st.markdown(
                '<div style="background:#0D1421;border:1px dashed #1E3A5F;'
                'border-radius:12px;padding:20px;text-align:center;color:#475569;">'
                'Click <b style="color:#EF4444;">ANALYZE</b> above to fetch live weather '
                'and predict wildfire risk for <b style="color:#94A3B8;">'
                + loc["name"] + '</b>'
                '</div>',
                unsafe_allow_html=True
            )
            st.markdown("")
            show_map(build_tamilnadu_map(), height=480)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — INDIA MAP
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("")
    st.markdown("""
<div style="font-family:Rajdhani,sans-serif;font-size:22px;font-weight:700;
            color:#F1F5F9;letter-spacing:2px;margin-bottom:4px;">
    🗺️ INDIA WILDFIRE RISK MAP
</div>
<div style="font-size:12px;color:#475569;margin-bottom:16px;">
    Monitor all zones simultaneously or view historical heatmap
</div>
""", unsafe_allow_html=True)

    map_mode = st.radio(
        "View Mode",
        ["All Monitored Zones", "History Heatmap"],
        horizontal=True
    )
    st.markdown("")

    if map_mode == "All Monitored Zones":
        if st.button("🔄  Run All Zones Now", type="primary"):
            all_results = []
            prog   = st.progress(0)
            status = st.empty()
            for i, zone in enumerate(LOCATIONS):
                status.text("Analyzing " + zone["name"] + "...")
                res = predict_for_location(zone["lat"], zone["lon"], zone["name"])
                if res:
                    dispatch_alerts(res)
                    all_results.append(res)
                prog.progress((i + 1) / len(LOCATIONS))
            status.empty()
            prog.empty()

            if all_results:
                show_map(build_multizone_map(all_results), height=560)
                st.markdown("### Zone Summary")
                st.dataframe(pd.DataFrame([{
                    "Location"   : r["location"],
                    "Risk"       : r["risk"]["level"],
                    "Fire Prob %" : round(r["probability"] * 100, 1),
                    "Temp °C"    : r["weather"]["Temperature"],
                    "Humidity %" : r["weather"]["RH"],
                    "Wind km/h"  : r["weather"]["Ws"],
                    "Rain mm"    : r["weather"]["Rain"],
                    "FWI"        : r["fwi"]["FWI"],
                } for r in all_results]), use_container_width=True, hide_index=True)
            else:
                st.error("Could not fetch any zone data. Check OWM_API_KEY.")
        else:
            show_map(build_tamilnadu_map(), height=520)

    else:
        st.caption("Heatmap built from all recorded predictions. Red = more HIGH/CRITICAL incidents.")
        show_map(build_history_heatmap(), height=560)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — HISTORY LOG
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("")
    st.markdown("""
<div style="font-family:Rajdhani,sans-serif;font-size:22px;font-weight:700;
            color:#F1F5F9;letter-spacing:2px;margin-bottom:4px;">
    📋 PREDICTION HISTORY LOG
</div>
<div style="font-size:12px;color:#475569;margin-bottom:8px;">
    Every prediction auto-saved — LOW · MEDIUM · HIGH · CRITICAL
</div>
""", unsafe_allow_html=True)

    # What is history log explanation
    with st.expander("ℹ️ What is History Log? Why is it useful?"):
        st.markdown("""
**History Log** automatically records every wildfire prediction you run.

**What gets saved for each prediction:**
- 📅 Date & Time of the check
- 📍 Location name and GPS coordinates
- 🌡️ Live weather: Temperature, Humidity, Wind Speed, Rainfall
- 🔥 FWI values: FFMC, DMC, DC, ISI, BUI, FWI
- 📊 Fire probability percentage
- 🚨 Risk level: LOW / MEDIUM / HIGH / CRITICAL
- 📲 Whether an alert was sent to fire station

**Why is it useful:**
- Track which areas are high risk over time
- Compare today's risk with yesterday or last week
- Identify patterns — which locations, which months are most dangerous
- Download CSV for research, reports, or government submission
- Evidence log if a fire actually occurs in that area

**Every click of Analyze = one row saved automatically.** No manual action needed.
        """)
    st.markdown("")

    if os.path.exists(ALERT_LOG_PATH) and os.path.getsize(ALERT_LOG_PATH) > 0:
        try:
            # Read with python engine which handles quoted fields correctly
            log_df = pd.read_csv(
                ALERT_LOG_PATH,
                engine       = "python",     # handles QUOTE_ALL format
                on_bad_lines = "skip",       # skip any corrupted old rows
                quoting      = csv.QUOTE_ALL if False else 0,  # auto-detect
            )
            if log_df.empty:
                st.info("No predictions yet. Search a city and click Analyze!")
            else:
                total = len(log_df)

                # Summary cards
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("📊 Total",    total)
                c2.metric("🔴 CRITICAL", len(log_df[log_df["risk_level"] == "CRITICAL"]))
                c3.metric("🟠 HIGH",     len(log_df[log_df["risk_level"] == "HIGH"]))
                c4.metric("🟡 MEDIUM",   len(log_df[log_df["risk_level"] == "MEDIUM"]))
                c5.metric("🟢 LOW",      len(log_df[log_df["risk_level"] == "LOW"]))
                st.markdown("")

                # Filters
                f1, f2 = st.columns(2)
                with f1:
                    rf = st.selectbox("Filter by Risk", ["All","CRITICAL","HIGH","MEDIUM","LOW"])
                with f2:
                    lf = st.selectbox(
                        "Filter by Location",
                        ["All"] + sorted(log_df["location"].unique().tolist())
                    )

                filtered = log_df.copy()
                if rf != "All":
                    filtered = filtered[filtered["risk_level"] == rf]
                if lf != "All":
                    filtered = filtered[filtered["location"] == lf]

                st.dataframe(
                    filtered.sort_values("timestamp", ascending=False),
                    use_container_width=True,
                    hide_index=True
                )
                st.caption("Showing " + str(len(filtered)) + " of " + str(total) + " records.")

                dl_col, reset_col = st.columns([3, 1])
                with dl_col:
                    st.download_button(
                        label    = "⬇️  Download Full CSV",
                        data     = log_df.to_csv(index=False).encode("utf-8"),
                        file_name= "wildfire_predictions_" + datetime.now().strftime("%Y%m%d") + ".csv",
                        mime     = "text/csv",
                        use_container_width=True
                    )
                with reset_col:
                    if st.button("🗑️ Reset Log", use_container_width=True,
                                 help="Delete corrupt/old CSV and start fresh"):
                        os.remove(ALERT_LOG_PATH)
                        st.success("Log cleared! Run predictions to start fresh.")
                        st.rerun()

        except Exception as e:
            st.error("CSV file is corrupted. Click Reset to fix it.")
            st.code("Error: " + str(e))
            if st.button("🗑️ Reset Corrupt CSV", type="primary"):
                os.remove(ALERT_LOG_PATH)
                st.success("Cleared! Run a prediction to create a fresh log.")
                st.rerun()
    else:
        st.markdown("""
<div style="text-align:center;padding:60px 20px;">
    <div style="font-size:48px;margin-bottom:16px;">📋</div>
    <div style="font-size:16px;color:#475569;">
        No predictions recorded yet.<br>
        Search a city and click Analyze to get started!
    </div>
</div>
""", unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown('<hr style="border-color:#1E3A5F;">', unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;color:#1E3A5F;font-size:11px;font-family:Rajdhani,sans-serif;letter-spacing:2px;">'
    'WILDFIRE ALERT SYSTEM &nbsp;|&nbsp; '
    'OPENWEATHERMAP + NASA FIRMS + XGBOOST &nbsp;|&nbsp; '
    + datetime.now().strftime("%Y-%m-%d %H:%M") +
    '</div>',
    unsafe_allow_html=True
)