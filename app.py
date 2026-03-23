import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os, time, json, csv

from config import LOCATIONS, ALERT_LOG_PATH, RISK_LEVELS

# ── Apply saved thresholds on startup ─────────────────────────────────────
def _apply_saved_thresholds():
    try:
        import config
        c = json.load(open('contacts.json')) if os.path.exists('contacts.json') else {}
        t = c.get('thresholds', {})
        # Default fallback = Tamil Nadu Summer calibrated values
        if t.get('high_min'):
            med  = t.get('medium_min', 55) / 100
            high = t.get('high_min',   75) / 100
            crit = t.get('critical_min',88) / 100
            config.RISK_LEVELS = {
                'LOW'     : (0.00, med),
                'MEDIUM'  : (med,  high),
                'HIGH'    : (high, crit),
                'CRITICAL': (crit, 1.01),
            }
    except Exception:
        pass
_apply_saved_thresholds()

from predictor    import predict_for_location
from alert_engine import dispatch_alerts, load_contacts, save_contacts, send_alert_to_contact
from geocoder     import get_coordinates
from map_view     import (build_tamilnadu_map, build_live_map,
                          build_multizone_map,  build_history_heatmap,
                          build_automonitor_map)
try:
    from telegram_alerts import send_telegram, test_telegram_connection
    TELEGRAM_OK = True
except ImportError:
    TELEGRAM_OK = False
    def send_telegram(r): return ("no_key", "Telegram module not found")
    def test_telegram_connection(t,c): return (False, "Telegram module not found")

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(page_title="Wildfire Alert System", page_icon="🔥",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Inter:wght@300;400;500;600&display=swap');
.stApp{background:#060B14;color:#E2E8F0;font-family:'Inter',sans-serif;}
section[data-testid="stSidebar"]{background:#0D1421!important;border-right:1px solid #1E3A5F!important;}
[data-testid="metric-container"]{background:linear-gradient(135deg,#0D1421,#111827);border:1px solid #1E3A5F;border-radius:12px;padding:14px!important;}
[data-testid="stMetricValue"]{color:#F1F5F9!important;font-family:'Rajdhani',sans-serif!important;font-size:1.6rem!important;}
[data-testid="stMetricLabel"]{color:#64748B!important;font-size:0.75rem!important;}
.stButton>button{background:linear-gradient(135deg,#DC2626,#991B1B)!important;color:white!important;border:none!important;border-radius:10px!important;font-family:'Rajdhani',sans-serif!important;font-weight:700!important;font-size:1rem!important;letter-spacing:1.5px!important;}
.stButton>button:hover{background:linear-gradient(135deg,#EF4444,#DC2626)!important;box-shadow:0 4px 20px rgba(220,38,38,0.4)!important;}
.stTextInput>div>div>input{background:#0D1421!important;border:1px solid #1E3A5F!important;border-radius:10px!important;color:#F1F5F9!important;}
.stTextInput>div>div>input:focus{border-color:#EF4444!important;}
.stTabs [data-baseweb="tab-list"]{background:#0D1421;border-radius:10px;gap:4px;padding:4px;border:1px solid #1E3A5F;}
.stTabs [data-baseweb="tab"]{background:transparent;border-radius:8px;color:#64748B;font-family:'Rajdhani',sans-serif;font-weight:600;}
.stTabs [aria-selected="true"]{background:linear-gradient(135deg,#DC2626,#991B1B)!important;color:white!important;}
hr{border-color:#1E3A5F;}
</style>""", unsafe_allow_html=True)


def show_map(html, height=560):
    import base64
    b64    = base64.b64encode(html.encode()).decode()
    iframe = (
        '<iframe src="data:text/html;base64,' + b64 + '" '
        'width="100%" height="' + str(height) + '" '
        'style="border:1px solid #1E3A5F;border-radius:12px;background:#0F172A;" '
        'frameborder="0" scrolling="no"></iframe>'
    )
    st.markdown(iframe, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# AUTO-MONITOR ENGINE
# All 40 Tamil Nadu zones scanned automatically
# ════════════════════════════════════════════════════════════════

def run_full_scan():
    """Scan all LOCATIONS, return list of result dicts."""
    results = []
    progress = st.progress(0, text="🔄 Scanning Tamil Nadu — 0 / " + str(len(LOCATIONS)))
    for i, loc in enumerate(LOCATIONS):
        progress.progress((i+1)/len(LOCATIONS),
                          text="🔄 Checking " + loc["name"] + " (" + str(i+1) + "/" + str(len(LOCATIONS)) + ")")
        try:
            r = predict_for_location(lat=loc["lat"], lon=loc["lon"], name=loc["name"])
            if r:
                results.append(r)
                # Auto-alert if HIGH or CRITICAL
                if r["risk"]["level"] in ["HIGH","CRITICAL"]:
                    dispatch_alerts(r)
                    if TELEGRAM_OK:
                        send_telegram(r)
        except Exception:
            pass
    progress.empty()
    return results


def _summary_counts(results):
    counts = {"CRITICAL":0,"HIGH":0,"MEDIUM":0,"LOW":0}
    for r in results:
        lvl = r["risk"]["level"]
        counts[lvl] = counts.get(lvl,0) + 1
    return counts


# ════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════
st.sidebar.markdown("""
<div style="text-align:center;padding:16px 0 8px;">
  <div style="font-size:48px;filter:drop-shadow(0 0 20px #EF444488);">🔥</div>
  <div style="font-family:'Rajdhani',sans-serif;font-size:20px;font-weight:700;
              color:#EF4444;letter-spacing:3px;margin-top:4px;">WILDFIRE ALERT</div>
  <div style="font-size:10px;color:#334155;letter-spacing:1px;">REAL-TIME DETECTION — TAMIL NADU</div>
</div>
<hr style="border-color:#1E3A5F;">
""", unsafe_allow_html=True)

# ── Auto-Monitor controls ──────────────────────────────────────────────────
st.sidebar.markdown('<div style="font-family:Rajdhani,sans-serif;font-size:12px;'
                    'color:#EF4444;letter-spacing:2px;margin-bottom:6px;">🗺️ AUTO MONITOR</div>',
                    unsafe_allow_html=True)

if st.sidebar.button("🔄  SCAN ALL 40 ZONES NOW", use_container_width=True, key="btn_scan_all"):
    st.session_state["trigger_scan"] = True

auto_on = st.sidebar.toggle("Auto-refresh every N minutes",
                             value=st.session_state.get("auto_on", False), key="auto_toggle")
st.session_state["auto_on"] = auto_on
if auto_on:
    interval = st.sidebar.selectbox("Interval", [5,10,15,30,60], index=2,
                                    format_func=lambda x: str(x)+" min", key="auto_interval")
    st.session_state["auto_interval"] = interval
    st.sidebar.markdown(
        '<div style="background:#052E16;border:1px solid #16A34A;border-radius:6px;'
        'padding:7px 10px;font-size:11px;color:#16A34A;">✅ Auto-scan every '
        + str(interval) + ' min — all 40 zones</div>', unsafe_allow_html=True)

st.sidebar.markdown('<hr style="border-color:#1E3A5F;">', unsafe_allow_html=True)

# ── Manual single location ─────────────────────────────────────────────────
st.sidebar.markdown('<div style="font-family:Rajdhani,sans-serif;font-size:12px;'
                    'color:#64748B;letter-spacing:2px;margin-bottom:6px;">🔍 SINGLE LOCATION</div>',
                    unsafe_allow_html=True)
city_input = st.sidebar.text_input("City", value="", placeholder="e.g. Mudumalai, Ooty...",
                                   label_visibility="collapsed")
search_btn = st.sidebar.button("🔍  Search & Analyze", use_container_width=True)

if "location" not in st.session_state:
    st.session_state.location = {"name":"Tamil Nadu","lat":11.1271,"lon":78.6569,"found":False}

if search_btn and city_input.strip():
    with st.spinner("Finding " + city_input + "..."):
        geo = get_coordinates(city_input.strip())
    if geo:
        st.session_state.location = {"name":geo["display_name"],"lat":geo["lat"],"lon":geo["lon"],"found":True}
    else:
        st.session_state.location = {"name":city_input+", Tamil Nadu","lat":11.1271,"lon":78.6569,"found":True}
    st.session_state["trigger_single"] = True

st.sidebar.markdown('<hr style="border-color:#1E3A5F;">', unsafe_allow_html=True)

# ── Quick select ───────────────────────────────────────────────────────────
st.sidebar.markdown('<div style="font-family:Rajdhani,sans-serif;font-size:11px;'
                    'color:#475569;letter-spacing:2px;margin-bottom:6px;">QUICK SELECT</div>',
                    unsafe_allow_html=True)
tn_cities = [("Coimbatore",11.0168,76.9558),("Chennai",13.0827,80.2707),
             ("Madurai",9.9252,78.1198),("Salem",11.6643,78.1460),
             ("Ooty",11.4102,76.6950),("Mudumalai",11.5671,76.6370)]
c1,c2 = st.sidebar.columns(2)
for i,(city,clat,clon) in enumerate(tn_cities):
    col = c1 if i%2==0 else c2
    if col.button(city, key="q_"+city, use_container_width=True):
        st.session_state.location = {"name":city+", Tamil Nadu","lat":clat,"lon":clon,"found":True}
        st.session_state["trigger_single"] = True
        st.rerun()

st.sidebar.markdown('<hr style="border-color:#1E3A5F;">', unsafe_allow_html=True)
st.sidebar.markdown("""
<div style="background:#0D1421;border:1px solid #EF444433;border-radius:8px;
            padding:9px 12px;text-align:center;">
  <div style="font-size:11px;color:#EF4444;font-family:Rajdhani,sans-serif;font-weight:700;">
    📧 ALERT CONTACTS
  </div>
  <div style="font-size:10px;color:#475569;margin-top:3px;">
    Configure in Alert Contacts tab →
  </div>
</div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════
# HEADER
# ════════════════════════════════════════════════════════════════
st.markdown("""
<div style="background:linear-gradient(135deg,#0D1421,#060B14);border:1px solid #1E3A5F;
            border-left:4px solid #EF4444;border-radius:14px;padding:18px 28px;margin-bottom:18px;">
  <div style="font-family:'Rajdhani',sans-serif;font-size:24px;font-weight:700;
              color:#F8FAFC;letter-spacing:2px;">
    🔥 REAL-TIME WILDFIRE DETECTION — TAMIL NADU
  </div>
  <div style="font-size:12px;color:#475569;margin-top:4px;">
    Auto-monitors 40 zones · Live weather · ML prediction · Instant alerts
  </div>
</div>""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🗺️  Live Monitor",
    "🔍  Single Location",
    "📋  History Log",
    "📧  Alert Contacts",
    "⚙️  Settings"
])


# ════════════════════════════════════════════════════════════════
# TAB 1 — LIVE MONITOR  (auto-scan all 40 zones)
# ════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("")

    # ── Auto-refresh timer ────────────────────────────────────────────────
    if auto_on:
        interval_sec = st.session_state.get("auto_interval", 15) * 60
        last_run     = st.session_state.get("auto_last_run", 0)
        now          = time.time()
        time_left    = max(0, int(interval_sec - (now - last_run)))
        tc1,tc2,tc3  = st.columns([4,1,1])
        with tc1:
            st.markdown(
                '<div style="background:#052E16;border:1px solid #16A34A;border-radius:8px;'
                'padding:8px 14px;font-size:12px;color:#16A34A;">'
                '⏱️ <b>AUTO MONITOR ON</b> — next scan in '
                '<b>' + str(time_left//60) + 'm ' + str(time_left%60) + 's</b>'
                ' — covering all 40 Tamil Nadu zones</div>',
                unsafe_allow_html=True)
        with tc2:
            if st.button("▶ Scan Now", key="scan_now_btn"):
                st.session_state["trigger_scan"] = True
                st.rerun()
        with tc3:
            if st.button("⏹ Stop", key="stop_auto_btn"):
                st.session_state["auto_on"] = False
                st.rerun()

        if now - last_run >= interval_sec:
            st.session_state["trigger_scan"] = True

    # ── Trigger scan ──────────────────────────────────────────────────────
    if st.session_state.pop("trigger_scan", False):
        with st.spinner("🔄 Scanning all 40 Tamil Nadu zones..."):
            results = run_full_scan()
        st.session_state["scan_results"] = results
        st.session_state["scan_time"]    = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        st.session_state["auto_last_run"]= time.time()

    results   = st.session_state.get("scan_results", [])
    scan_time = st.session_state.get("scan_time", "")

    # ── No scan yet — show start button ───────────────────────────────────
    if not results:
        st.markdown("""
<div style="text-align:center;padding:40px 20px;">
  <div style="font-size:72px;margin-bottom:16px;">🗺️</div>
  <div style="font-family:Rajdhani,sans-serif;font-size:26px;font-weight:700;color:#F1F5F9;">
    AUTOMATIC WILDFIRE MONITOR
  </div>
  <div style="font-size:14px;color:#475569;margin-top:8px;margin-bottom:28px;">
    Click the button below to scan all 40 Tamil Nadu zones at once.<br>
    Map shows live risk for every location. Alerts sent automatically for HIGH/CRITICAL zones.
  </div>
</div>""", unsafe_allow_html=True)
        if st.button("🔥  START MONITORING — SCAN ALL 40 ZONES",
                     type="primary", use_container_width=True, key="btn_first_scan"):
            st.session_state["trigger_scan"] = True
            st.rerun()
        show_map(build_tamilnadu_map(), height=480)

    else:
        # ── Summary stats ─────────────────────────────────────────────────
        counts = _summary_counts(results)
        alert_zones = [r for r in results if r["risk"]["level"] in ["HIGH","CRITICAL"]]

        s1,s2,s3,s4,s5 = st.columns(5)
        s1.metric("🔴 Critical",  counts["CRITICAL"])
        s2.metric("🟠 High",      counts["HIGH"])
        s3.metric("🟡 Medium",    counts["MEDIUM"])
        s4.metric("🟢 Low/Safe",  counts["LOW"])
        s5.metric("📍 Total",     len(results))

        # ── Alert banner ──────────────────────────────────────────────────
        if alert_zones:
            names = ", ".join([r["location"].split(",")[0] for r in alert_zones[:5]])
            st.markdown(
                '<div style="background:linear-gradient(135deg,#7F1D1D,#450A0A);'
                'border:2px solid #DC2626;border-radius:12px;padding:14px 20px;'
                'margin-bottom:14px;text-align:center;">'
                '<div style="font-family:Rajdhani,sans-serif;font-size:20px;font-weight:700;'
                'color:#FCA5A5;">🚨 FIRE ALERT — ' + str(len(alert_zones)) + ' ZONE(S) AT RISK</div>'
                '<div style="font-size:13px;color:#EF4444;margin-top:4px;">'
                + names + '</div>'
                '<div style="font-size:12px;color:#94A3B8;margin-top:6px;">'
                '📞 Call 101 (Fire Station) &nbsp;|&nbsp; 112 (Emergency)</div>'
                '</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="background:linear-gradient(135deg,#14532D,#052E16);'
                'border:2px solid #16A34A;border-radius:12px;padding:12px 20px;'
                'margin-bottom:14px;text-align:center;">'
                '<div style="font-family:Rajdhani,sans-serif;font-size:18px;font-weight:700;'
                'color:#86EFAC;">✅ ALL CLEAR — No fire risk detected across Tamil Nadu</div>'
                '<div style="font-size:12px;color:#4ADE80;margin-top:4px;">'
                'Last scan: ' + scan_time + ' — ' + str(len(results)) + ' zones checked</div>'
                '</div>', unsafe_allow_html=True)

        # ── Auto-monitor map ──────────────────────────────────────────────
        show_map(build_automonitor_map(results, scan_time), height=520)

        # ── Zone details table ────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div style="font-family:Rajdhani,sans-serif;font-size:14px;font-weight:700;'
                    'color:#94A3B8;letter-spacing:2px;margin-bottom:10px;">📊 ZONE DETAILS</div>',
                    unsafe_allow_html=True)

        RISK_ICON = {"CRITICAL":"🔴","HIGH":"🟠","MEDIUM":"🟡","LOW":"🟢"}
        rows = []
        for r in sorted(results, key=lambda x: -x["probability"]):
            rows.append({
                "Zone"        : r["location"].split("|")[0].strip(),
                "Risk"        : RISK_ICON.get(r["risk"]["level"],"") + " " + r["risk"]["level"],
                "Fire %"      : str(round(r["probability"]*100,1)) + "%",
                "Temp (°C)"   : r["weather"]["Temperature"],
                "Humidity %"  : r["weather"]["RH"],
                "Wind (km/h)" : r["weather"]["Ws"],
                "FWI"         : r["fwi"]["FWI"],
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True, height=320)

        rc1, rc2 = st.columns(2)
        with rc1:
            if st.button("🔄  Refresh Scan Now", use_container_width=True, key="btn_refresh"):
                st.session_state["trigger_scan"] = True
                st.rerun()
        with rc2:
            st.download_button(
                "⬇️  Download Results CSV",
                df.to_csv(index=False).encode(),
                "wildfire_scan_" + datetime.now().strftime("%Y%m%d_%H%M") + ".csv",
                "text/csv", use_container_width=True)

    # ── Auto-rerun if auto_on ─────────────────────────────────────────────
    if auto_on and results:
        interval_sec = st.session_state.get("auto_interval",15)*60
        last_run     = st.session_state.get("auto_last_run",0)
        if time.time() - last_run >= interval_sec:
            st.session_state["trigger_scan"] = True
            st.rerun()


# ════════════════════════════════════════════════════════════════
# TAB 2 — SINGLE LOCATION ANALYSIS
# ════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("")
    loc = st.session_state.location

    if st.session_state.pop("trigger_single", False) and loc["found"]:
        with st.spinner("Fetching live weather for " + loc["name"] + "..."):
            result = predict_for_location(lat=loc["lat"], lon=loc["lon"], name=loc["name"])
        st.session_state["single_result"] = result

    result = st.session_state.get("single_result", None)

    if not loc["found"] and result is None:
        st.markdown("""
<div style="text-align:center;padding:40px 20px;">
  <div style="font-size:60px;">🔍</div>
  <div style="font-family:Rajdhani,sans-serif;font-size:22px;font-weight:700;
              color:#F1F5F9;margin-top:12px;">SINGLE LOCATION ANALYSIS</div>
  <div style="font-size:13px;color:#475569;margin-top:8px;">
    Search any city, forest, or village from the sidebar →
  </div>
</div>""", unsafe_allow_html=True)
        show_map(build_tamilnadu_map(), height=460)

    elif loc["found"]:
        st.markdown(
            '<div style="background:#0D1421;border:1px solid #1E3A5F;border-left:3px solid #EF4444;'
            'border-radius:10px;padding:10px 18px;margin-bottom:14px;">'
            '<span style="font-size:12px;color:#475569;font-family:Rajdhani;letter-spacing:2px;">LOCATION</span><br>'
            '<span style="font-size:18px;font-weight:700;color:#F1F5F9;font-family:Rajdhani;">'
            + loc["name"] + '</span>'
            '<span style="font-size:11px;color:#475569;margin-left:12px;">'
            'Lat:' + str(loc["lat"]) + ' Lon:' + str(loc["lon"]) + '</span></div>',
            unsafe_allow_html=True)

        if st.button("🔥  ANALYZE — " + loc["name"].split("|")[0].split(",")[0].strip().upper(),
                     type="primary", use_container_width=True, key="btn_single_analyze"):
            with st.spinner("Fetching live data..."):
                result = predict_for_location(lat=loc["lat"], lon=loc["lon"], name=loc["name"])
            st.session_state["single_result"] = result

        if result:
            risk_level = result["risk"]["level"]
            prob_pct   = round(result["probability"]*100,1)
            dispatch_alerts(result)

            # Telegram
            if risk_level in ["HIGH","CRITICAL"] and TELEGRAM_OK:
                send_telegram(result)

            # Email contacts
            if risk_level in ["HIGH","CRITICAL"]:
                saved_c   = load_contacts()
                email_map = {
                    saved_c.get("your_name","You")              : saved_c.get("your_email",""),
                    saved_c.get("fire_name","Fire Station")     : saved_c.get("fire_station_email",""),
                    saved_c.get("police_name","Police")         : saved_c.get("police_email",""),
                    saved_c.get("forest_name","Forest Officer") : saved_c.get("forest_officer_email",""),
                }
                for cname, email in email_map.items():
                    if email.strip():
                        send_alert_to_contact(result, email.strip())

            # Risk banner
            risk_styles = {
                "CRITICAL":("linear-gradient(135deg,#7F1D1D,#450A0A)","#FCA5A5","#DC2626"),
                "HIGH"    :("linear-gradient(135deg,#7C2D12,#431407)","#FED7AA","#EA580C"),
                "MEDIUM"  :("linear-gradient(135deg,#78350F,#451A03)","#FDE68A","#D97706"),
                "LOW"     :("linear-gradient(135deg,#14532D,#052E16)","#BBF7D0","#16A34A"),
            }
            bg,fg,bd = risk_styles.get(risk_level,("#1E293B","#F1F5F9","#475569"))
            risk_msg = {
                "CRITICAL":"🔴 WILDFIRE IMMINENT — EVACUATE IMMEDIATELY",
                "HIGH"    :"🟠 DANGEROUS CONDITIONS — FIRE RISK VERY HIGH",
                "MEDIUM"  :"🟡 ELEVATED RISK — MONITOR CONDITIONS",
                "LOW"     :"🟢 SAFE CONDITIONS — LOW FIRE RISK",
            }
            st.markdown(
                '<div style="background:' + bg + ';border:2px solid ' + bd + ';border-radius:14px;'
                'padding:18px 28px;margin-bottom:18px;text-align:center;">'
                '<div style="font-family:Rajdhani,sans-serif;font-size:26px;font-weight:700;color:' + fg + ';">'
                + risk_msg.get(risk_level,risk_level) + '</div>'
                '<div style="font-size:13px;color:' + bd + ';margin-top:6px;">'
                'Fire Probability: <b>' + str(prob_pct) + '%</b>'
                ' | Location: <b>' + loc["name"].split("|")[0].strip() + '</b>'
                ' | ' + result["timestamp"] + '</div></div>',
                unsafe_allow_html=True)

            # Weather metrics
            w = result["weather"]
            f = result["fwi"]
            m1,m2,m3,m4 = st.columns(4)
            m1.metric("🌡️ Temperature", str(w["Temperature"])+" °C")
            m2.metric("💧 Humidity",    str(w["RH"])+"%")
            m3.metric("💨 Wind Speed",  str(w["Ws"])+" km/h")
            m4.metric("🌧️ Rainfall",    str(w["Rain"])+" mm")

            f1,f2,f3,f4,f5,f6 = st.columns(6)
            f1.metric("FFMC",str(f["FFMC"])); f2.metric("DMC",str(f["DMC"]))
            f3.metric("DC",  str(f["DC"]));   f4.metric("ISI",str(f["ISI"]))
            f5.metric("BUI", str(f["BUI"]));  f6.metric("FWI",str(f["FWI"]))

            # Gauge
            gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=prob_pct,
                title={"text":"Fire Probability %","font":{"color":"#94A3B8","size":13}},
                number={"font":{"color":bd,"size":36}},
                gauge={"axis":{"range":[0,100],"tickcolor":"#334155"},
                       "bar":{"color":bd},
                       "steps":[{"range":[0,25],"color":"#052E16"},
                                {"range":[25,50],"color":"#78350F"},
                                {"range":[50,75],"color":"#7C2D12"},
                                {"range":[75,100],"color":"#450A0A"}],
                       "threshold":{"line":{"color":bd,"width":4},"value":prob_pct}}))
            gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                 font={"color":"#F1F5F9"}, height=220, margin=dict(t=30,b=0,l=20,r=20))
            st.plotly_chart(gauge, use_container_width=True)

            show_map(build_live_map(result), height=460)


# ════════════════════════════════════════════════════════════════
# TAB 3 — HISTORY LOG
# ════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("")
    st.markdown('<div style="font-family:Rajdhani,sans-serif;font-size:20px;font-weight:700;'
                'color:#F1F5F9;letter-spacing:2px;margin-bottom:14px;">📋 PREDICTION HISTORY</div>',
                unsafe_allow_html=True)
    if os.path.exists(ALERT_LOG_PATH) and os.path.getsize(ALERT_LOG_PATH) > 0:
        try:
            log_df = pd.read_csv(ALERT_LOG_PATH, engine="python", on_bad_lines="skip")
            total  = len(log_df)
            h1,h2,h3,h4,h5 = st.columns(5)
            h1.metric("Total Scans",  total)
            h2.metric("🔴 Critical",  len(log_df[log_df["risk_level"]=="CRITICAL"]))
            h3.metric("🟠 High",      len(log_df[log_df["risk_level"]=="HIGH"]))
            h4.metric("🟡 Medium",    len(log_df[log_df["risk_level"]=="MEDIUM"]))
            h5.metric("🟢 Low",       len(log_df[log_df["risk_level"]=="LOW"]))
            st.markdown("")

            f1,f2 = st.columns(2)
            with f1: rf = st.selectbox("Filter Risk",["All","CRITICAL","HIGH","MEDIUM","LOW"])
            with f2: lf = st.selectbox("Filter Location",["All"]+sorted(log_df["location"].unique().tolist()))
            filtered = log_df.copy()
            if rf!="All": filtered = filtered[filtered["risk_level"]==rf]
            if lf!="All": filtered = filtered[filtered["location"]==lf]
            st.dataframe(filtered.sort_values("timestamp",ascending=False),
                         use_container_width=True, hide_index=True)
            st.caption("Showing "+str(len(filtered))+" of "+str(total)+" records.")

            dl,rst = st.columns([3,1])
            with dl:
                st.download_button("⬇️ Download CSV",
                    log_df.to_csv(index=False).encode(),
                    "wildfire_"+datetime.now().strftime("%Y%m%d")+".csv",
                    "text/csv", use_container_width=True)
            with rst:
                if st.button("🗑️ Reset Log", use_container_width=True):
                    os.remove(ALERT_LOG_PATH); st.success("Cleared!"); st.rerun()

            show_map(build_history_heatmap(), height=400)
        except Exception as e:
            st.error("CSV error. Click Reset.")
            if st.button("🗑️ Reset"):
                os.remove(ALERT_LOG_PATH); st.rerun()
    else:
        st.info("No predictions yet. Run a scan from Live Monitor tab!")


# ════════════════════════════════════════════════════════════════
# TAB 4 — ALERT CONTACTS
# ════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("")
    import smtplib as _smtplib
    saved_c = load_contacts()

    st.markdown('<div style="font-family:Rajdhani,sans-serif;font-size:22px;font-weight:700;'
                'color:#F1F5F9;letter-spacing:2px;margin-bottom:16px;">📧 ALERT CONTACTS</div>',
                unsafe_allow_html=True)

    # Gmail sender
    st.markdown('<div style="font-size:13px;color:#94A3B8;font-weight:700;'
                'margin-bottom:8px;">⚙️ STEP 1 — Gmail Sender Setup</div>',
                unsafe_allow_html=True)
    gc1,gc2 = st.columns(2)
    with gc1:
        inp_email = st.text_input("📧 Your Gmail (sender)",
            value=saved_c.get("sender_email",""), placeholder="yourname@gmail.com", key="inp_se")
    with gc2:
        inp_pass  = st.text_input("🔑 Gmail App Password",
            value=saved_c.get("sender_pass",""),
            placeholder="abcd efgh ijkl mnop",
            type="password", key="inp_sp",
            help="Get from myaccount.google.com/apppasswords")

    tc1,tc2 = st.columns(2)
    with tc1:
        if st.button("🔌 Test Connection", use_container_width=True, key="btn_tcon"):
            if not inp_email or not inp_pass:
                st.warning("Enter Gmail and App Password first!")
            else:
                try:
                    with _smtplib.SMTP_SSL("smtp.gmail.com",465,timeout=10) as s:
                        s.login(inp_email.strip(), inp_pass.strip())
                    saved_c["sender_email"]=inp_email.strip()
                    saved_c["sender_pass"] =inp_pass.strip()
                    save_contacts(saved_c)
                    st.success("✅ Gmail connected! Credentials saved.")
                    st.balloons()
                except _smtplib.SMTPAuthenticationError:
                    st.error("❌ Wrong App Password! Get it from myaccount.google.com/apppasswords")
                except Exception as e:
                    st.error("❌ Error: "+str(e))
    with tc2:
        if saved_c.get("sender_email"):
            st.success("✅ Gmail: "+saved_c["sender_email"])
        else:
            st.warning("⚠️ Gmail not saved yet")

    st.markdown("<hr style='border-color:#1E3A5F;margin:16px 0;'>", unsafe_allow_html=True)

    # Recipients
    st.markdown('<div style="font-size:13px;color:#94A3B8;font-weight:700;'
                'margin-bottom:8px;">📬 STEP 2 — Who Gets the Alert?</div>',
                unsafe_allow_html=True)
    ra,rb = st.columns(2, gap="large")
    with ra:
        st.markdown('<div style="font-size:11px;color:#EF4444;font-weight:700;margin-bottom:3px;">👤 YOU</div>', unsafe_allow_html=True)
        your_name  = st.text_input("Your Name",  value=saved_c.get("your_name",""),  placeholder="Ravi Kumar",           key="r_yn")
        your_email = st.text_input("Your Email", value=saved_c.get("your_email",""), placeholder="yourname@gmail.com",   key="r_ye")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div style="font-size:11px;color:#EA580C;font-weight:700;margin-bottom:3px;">🚒 FIRE STATION</div>', unsafe_allow_html=True)
        fire_name  = st.text_input("Fire Station Name",  value=saved_c.get("fire_name",""),          placeholder="Sathiyamangalam FS", key="r_fn")
        fire_email = st.text_input("Fire Station Email", value=saved_c.get("fire_station_email",""), placeholder="fs@tn.gov.in",       key="r_fe")
    with rb:
        st.markdown('<div style="font-size:11px;color:#3B82F6;font-weight:700;margin-bottom:3px;">👮 POLICE</div>', unsafe_allow_html=True)
        police_name  = st.text_input("Police Name",  value=saved_c.get("police_name",""),  placeholder="Gobichettipalayam Police", key="r_pn")
        police_email = st.text_input("Police Email", value=saved_c.get("police_email",""), placeholder="police@tn.gov.in",         key="r_pe")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div style="font-size:11px;color:#16A34A;font-weight:700;margin-bottom:3px;">🌿 FOREST OFFICER</div>', unsafe_allow_html=True)
        forest_name  = st.text_input("Forest Officer Name",  value=saved_c.get("forest_name",""),          placeholder="DFO Erode",           key="r_fon")
        forest_email = st.text_input("Forest Officer Email", value=saved_c.get("forest_officer_email",""), placeholder="dfo@forests.tn.gov.in",key="r_foe")

    st.markdown("<br>", unsafe_allow_html=True)
    sb1,sb2 = st.columns([2,1])
    with sb1:
        if st.button("💾 SAVE ALL CONTACTS", type="primary", use_container_width=True, key="btn_sac"):
            saved_c.update({
                "your_name":your_name,"your_email":your_email,
                "fire_name":fire_name,"fire_station_email":fire_email,
                "police_name":police_name,"police_email":police_email,
                "forest_name":forest_name,"forest_officer_email":forest_email,
            })
            save_contacts(saved_c)
            st.success("✅ Contacts saved! Alerts sent automatically on HIGH/CRITICAL.")
    with sb2:
        if st.button("📧 Test Email", use_container_width=True, key="btn_te"):
            all_em = [e for e in [your_email,fire_email,police_email,forest_email] if e.strip()]
            if not all_em:
                st.warning("Enter at least one email!")
            elif not saved_c.get("sender_email"):
                st.error("Save Gmail credentials first!")
            else:
                test_r = {
                    "location":"TEST","lat":11.12,"lon":78.65,
                    "timestamp":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "probability":0.72,"prediction":1,
                    "maps_url":"https://maps.google.com/?q=11.12,78.65",
                    "risk":{"level":"HIGH","should_alert":True},
                    "weather":{"Temperature":38,"RH":18,"Ws":22,"Rain":0},
                    "fwi":{"FFMC":91,"DMC":44,"DC":310,"ISI":17,"BUI":55,"FWI":45},
                }
                for em in all_em:
                    code,msg = send_alert_to_contact(test_r, em.strip())
                    if code=="sent": st.success("✅ Sent to "+em)
                    else: st.error("❌ Failed: "+msg)


# ════════════════════════════════════════════════════════════════
# TAB 5 — SETTINGS (Telegram + Threshold Tuning)
# ════════════════════════════════════════════════════════════════
with tab5:
    st.markdown("")
    saved_tg = load_contacts()

    # ── Telegram ──────────────────────────────────────────────────────────
    st.markdown('<div style="font-family:Rajdhani,sans-serif;font-size:20px;font-weight:700;'
                'color:#F1F5F9;letter-spacing:2px;margin-bottom:12px;">✈️ TELEGRAM ALERTS</div>',
                unsafe_allow_html=True)

    tg_ok = bool(saved_tg.get("telegram_token")) and bool(saved_tg.get("telegram_chat_id"))
    st.markdown(
        '<div style="background:#0D1421;border:1px solid '
        + ("#16A34A" if tg_ok else "#EF4444") + ';border-radius:8px;padding:10px 16px;'
        'margin-bottom:12px;font-size:13px;color:'
        + ("#16A34A" if tg_ok else "#EF4444") + ';font-weight:600;">'
        + ("✅ Telegram configured — instant alerts active!" if tg_ok
           else "❌ Not configured — follow steps below") + '</div>',
        unsafe_allow_html=True)

    st.markdown("""
<div style="background:#0D1421;border:1px solid #1E3A5F;border-radius:10px;padding:14px;margin-bottom:14px;">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
    <div style="background:#060B14;border:1px solid #334155;border-radius:8px;padding:12px;">
      <div style="color:#3B82F6;font-weight:700;font-size:12px;margin-bottom:8px;">Step 1 — Get Bot Token</div>
      <div style="font-size:12px;color:#94A3B8;line-height:2.2;">
        1. Open Telegram → search <b style="color:#F1F5F9;">@BotFather</b><br>
        2. Send: <b style="color:#FDE68A;">/newbot</b><br>
        3. Name: <b style="color:#FDE68A;">Wildfire Alert</b><br>
        4. Copy the <b style="color:#16A34A;">Token</b> it gives
      </div>
    </div>
    <div style="background:#060B14;border:1px solid #334155;border-radius:8px;padding:12px;">
      <div style="color:#3B82F6;font-weight:700;font-size:12px;margin-bottom:8px;">Step 2 — Get Chat ID</div>
      <div style="font-size:12px;color:#94A3B8;line-height:2.2;">
        1. Search <b style="color:#F1F5F9;">@userinfobot</b><br>
        2. Send: <b style="color:#FDE68A;">/start</b><br>
        3. Copy <b style="color:#16A34A;">Id: 123456789</b><br>
        4. Start your new bot too (send /start)
      </div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    tg1,tg2 = st.columns(2)
    with tg1:
        tg_token  = st.text_input("🤖 Bot Token", value=saved_tg.get("telegram_token",""),
                                   placeholder="123456789:ABCdef...", type="password", key="tg_tok")
    with tg2:
        tg_chatid = st.text_input("💬 Chat ID",   value=saved_tg.get("telegram_chat_id",""),
                                   placeholder="123456789", key="tg_cid")
    tb1,tb2 = st.columns(2)
    with tb1:
        if st.button("🔌 Test Telegram", use_container_width=True, key="btn_tg"):
            if not tg_token or not tg_chatid:
                st.warning("Enter Token and Chat ID!")
            else:
                ok,msg = test_telegram_connection(tg_token.strip(), tg_chatid.strip())
                if ok:
                    saved_tg["telegram_token"]  =tg_token.strip()
                    saved_tg["telegram_chat_id"]=tg_chatid.strip()
                    save_contacts(saved_tg)
                    st.success("✅ "+msg); st.balloons()
                else:
                    st.error("❌ "+msg)
                    st.info("💡 Make sure you sent /start to your bot first!")
    with tb2:
        if st.button("💾 Save Telegram", use_container_width=True, key="btn_tgsave"):
            if tg_token and tg_chatid:
                saved_tg["telegram_token"]  =tg_token.strip()
                saved_tg["telegram_chat_id"]=tg_chatid.strip()
                save_contacts(saved_tg); st.success("✅ Saved!")
            else:
                st.warning("Enter both Token and Chat ID!")

    st.markdown("<hr style='border-color:#1E3A5F;margin:24px 0;'>", unsafe_allow_html=True)

    # ── Risk Threshold Tuning ─────────────────────────────────────────────
    st.markdown('<div style="font-family:Rajdhani,sans-serif;font-size:20px;font-weight:700;'
                'color:#F1F5F9;letter-spacing:2px;margin-bottom:8px;">🎚️ RISK THRESHOLD TUNING</div>',
                unsafe_allow_html=True)
    st.markdown("""
<div style="background:#0D1421;border:1px solid #D97706;border-left:4px solid #D97706;
            border-radius:8px;padding:12px 16px;margin-bottom:14px;font-size:12px;color:#94A3B8;">
  <b style="color:#D97706;">Why tune?</b> Model trained on Algeria data.
  Tamil Nadu summers (35–45°C, very dry) need lower thresholds so alerts trigger earlier = safer forests.
</div>""", unsafe_allow_html=True)

    saved_t = saved_tg.get("thresholds",{"medium_min":25,"high_min":50,"critical_min":75})
    th1,th2,th3 = st.columns(3)
    with th1:
        st.markdown('<div style="text-align:center;color:#D97706;font-size:12px;font-weight:700;">🟡 MEDIUM starts at</div>', unsafe_allow_html=True)
        med_min  = st.slider("Med",  10,40, saved_t.get("medium_min",25),  5, key="sl_m", label_visibility="collapsed")
        st.markdown('<div style="text-align:center;font-size:24px;font-weight:700;color:#D97706;">'+str(med_min)+'%</div>', unsafe_allow_html=True)
    with th2:
        st.markdown('<div style="text-align:center;color:#EA580C;font-size:12px;font-weight:700;">🟠 HIGH starts at</div>', unsafe_allow_html=True)
        high_min = st.slider("High", 30,70, saved_t.get("high_min",50),    5, key="sl_h", label_visibility="collapsed")
        st.markdown('<div style="text-align:center;font-size:24px;font-weight:700;color:#EA580C;">'+str(high_min)+'%</div>', unsafe_allow_html=True)
    with th3:
        st.markdown('<div style="text-align:center;color:#DC2626;font-size:12px;font-weight:700;">🔴 CRITICAL starts at</div>', unsafe_allow_html=True)
        crit_min = st.slider("Crit", 50,90, saved_t.get("critical_min",75), 5, key="sl_c", label_visibility="collapsed")
        st.markdown('<div style="text-align:center;font-size:24px;font-weight:700;color:#DC2626;">'+str(crit_min)+'%</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    pc1,pc2,pc3,pc4 = st.columns(4)
    with pc1:
        st.markdown('<div style="text-align:center;font-size:10px;color:#475569;">DEFAULT</div>', unsafe_allow_html=True)
        if st.button("Algeria Default",    use_container_width=True, key="pr1"):
            saved_tg["thresholds"]={"medium_min":25,"high_min":50,"critical_min":75}; save_contacts(saved_tg); st.rerun()
    with pc2:
        st.markdown('<div style="text-align:center;font-size:10px;color:#D97706;">RECOMMENDED ⭐</div>', unsafe_allow_html=True)
        if st.button("Tamil Nadu Summer", use_container_width=True, key="pr2"):
            saved_tg["thresholds"]={"medium_min":55,"high_min":75,"critical_min":88}; save_contacts(saved_tg); st.rerun()
    with pc3:
        st.markdown('<div style="text-align:center;font-size:10px;color:#EA580C;">SENSITIVE</div>', unsafe_allow_html=True)
        if st.button("High Sensitivity",  use_container_width=True, key="pr3"):
            saved_tg["thresholds"]={"medium_min":45,"high_min":65,"critical_min":82}; save_contacts(saved_tg); st.rerun()
    with pc4:
        st.markdown('<div style="text-align:center;font-size:10px;color:#DC2626;">STRICT</div>', unsafe_allow_html=True)
        if st.button("Forest Reserve",    use_container_width=True, key="pr4"):
            saved_tg["thresholds"]={"medium_min":40,"high_min":60,"critical_min":78}; save_contacts(saved_tg); st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Save Thresholds", type="primary", use_container_width=True, key="btn_st"):
        if high_min<=med_min or crit_min<=high_min:
            st.error("❌ Must be: MEDIUM < HIGH < CRITICAL")
        else:
            saved_tg["thresholds"]={"medium_min":med_min,"high_min":high_min,"critical_min":crit_min}
            save_contacts(saved_tg)
            import config
            config.RISK_LEVELS={
                "LOW":(0.00,med_min/100),"MEDIUM":(med_min/100,high_min/100),
                "HIGH":(high_min/100,crit_min/100),"CRITICAL":(crit_min/100,1.01)}
            st.success("✅ Thresholds saved and applied immediately!")

    st.markdown("""
<div style="background:#0D1421;border:1px solid #334155;border-radius:8px;
            padding:12px 16px;margin-top:14px;font-size:12px;color:#64748B;">
  💡 <b style="color:#F1F5F9;">Tip:</b> Use <b>Tamil Nadu Summer</b> preset during March–June dry season.
  Switch to <b>Algeria Default</b> during monsoon (July–September).
</div>""", unsafe_allow_html=True)


# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown('<hr style="border-color:#1E3A5F;">', unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;color:#1E3A5F;font-size:11px;'
    'font-family:Rajdhani,sans-serif;letter-spacing:2px;">'
    'WILDFIRE ALERT SYSTEM — TAMIL NADU &nbsp;|&nbsp; '
    'OPENWEATHERMAP + NASA FIRMS + XGBOOST &nbsp;|&nbsp; '
    + datetime.now().strftime("%Y-%m-%d %H:%M") + '</div>',
    unsafe_allow_html=True)