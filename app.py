import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os, time, csv

from config import LOCATIONS, ALERT_LOG_PATH
from predictor import predict_for_location
from alert_engine import dispatch_alerts, send_sms_direct
from geocoder import get_coordinates
from map_view import (
    build_tamilnadu_map, build_live_map,
    build_multizone_map, build_history_heatmap,
)

st.set_page_config(page_title="Wildfire Alert System", page_icon="🔥",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Inter:wght@300;400;500;600&display=swap');
.stApp { background:#060B14; color:#E2E8F0; font-family:'Inter',sans-serif; }
section[data-testid="stSidebar"] { background:#0D1421 !important; border-right:1px solid #1E3A5F !important; }
[data-testid="metric-container"] { background:linear-gradient(135deg,#0D1421,#111827); border:1px solid #1E3A5F; border-radius:12px; padding:14px !important; }
[data-testid="stMetricValue"] { color:#F1F5F9 !important; font-family:'Rajdhani',sans-serif !important; font-size:1.6rem !important; }
[data-testid="stMetricLabel"] { color:#64748B !important; font-size:0.75rem !important; }
.stButton>button { background:linear-gradient(135deg,#DC2626,#991B1B) !important; color:white !important; border:none !important; border-radius:10px !important; font-family:'Rajdhani',sans-serif !important; font-weight:700 !important; font-size:1rem !important; letter-spacing:1.5px !important; }
.stButton>button:hover { background:linear-gradient(135deg,#EF4444,#DC2626) !important; box-shadow:0 4px 20px rgba(220,38,38,0.4) !important; }
.stTextInput>div>div>input { background:#0D1421 !important; border:1px solid #1E3A5F !important; border-radius:10px !important; color:#F1F5F9 !important; }
.stTextInput>div>div>input:focus { border-color:#EF4444 !important; }
.stTabs [data-baseweb="tab-list"] { background:#0D1421; border-radius:10px; gap:4px; padding:4px; border:1px solid #1E3A5F; }
.stTabs [data-baseweb="tab"] { background:transparent; border-radius:8px; color:#64748B; font-family:'Rajdhani',sans-serif; font-weight:600; }
.stTabs [aria-selected="true"] { background:linear-gradient(135deg,#DC2626,#991B1B) !important; color:white !important; }
hr { border-color:#1E3A5F; }
</style>
""", unsafe_allow_html=True)


def show_map(html, height=500):
    """Render map using srcdoc inside an iframe — guaranteed to show."""
    import base64
    b64 = base64.b64encode(html.encode()).decode()
    iframe = (
        '<iframe src="data:text/html;base64,' + b64 + '" '
        'width="100%" height="' + str(height) + '" '
        'style="border:1px solid #1E3A5F;border-radius:12px;background:#0F172A;" '
        'frameborder="0" scrolling="no"></iframe>'
    )
    st.markdown(iframe, unsafe_allow_html=True)


# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
st.sidebar.markdown("""
<div style="text-align:center;padding:20px 0 10px;">
  <div style="font-size:52px;filter:drop-shadow(0 0 20px #EF444488);">🔥</div>
  <div style="font-family:'Rajdhani',sans-serif;font-size:22px;font-weight:700;color:#EF4444;letter-spacing:3px;margin-top:6px;">WILDFIRE ALERT</div>
  <div style="font-size:11px;color:#334155;margin-top:3px;letter-spacing:1px;">REAL-TIME DETECTION SYSTEM</div>
</div>
<hr style="border-color:#1E3A5F;margin:10px 0;">
""", unsafe_allow_html=True)

st.sidebar.markdown('<div style="font-family:Rajdhani,sans-serif;font-size:13px;color:#64748B;letter-spacing:2px;margin-bottom:6px;">SEARCH LOCATION</div>', unsafe_allow_html=True)
city_input = st.sidebar.text_input("City", value="", placeholder="e.g. Sathiyamangalam, Ooty, Mudumalai...", label_visibility="collapsed")
search_btn = st.sidebar.button("🔍  Search Location", use_container_width=True)

if "location" not in st.session_state:
    st.session_state.location = {"name":"Tamil Nadu","lat":11.1271,"lon":78.6569,"found":False}

if search_btn and city_input.strip():
    with st.spinner("Finding " + city_input + "..."):
        geo = get_coordinates(city_input.strip())
    if geo:
        st.session_state.location = {"name":geo["display_name"],"lat":geo["lat"],"lon":geo["lon"],"found":True}
        st.sidebar.success("✅ Found: " + geo["display_name"])
    else:
        st.sidebar.info("Using Tamil Nadu region for: " + city_input)
        st.session_state.location = {"name":city_input+" - Tamil Nadu","lat":11.1271,"lon":78.6569,"found":True}

loc = st.session_state.location
if loc["found"]:
    st.sidebar.markdown(
        '<div style="background:#0D1421;border:1px solid #1E3A5F;border-left:3px solid #EF4444;border-radius:8px;padding:10px 14px;margin:10px 0;">'
        '<div style="font-size:13px;font-weight:600;color:#F1F5F9;">' + loc["name"] + '</div>'
        '<div style="font-size:11px;color:#475569;">Lat:' + str(loc["lat"]) + ' | Lon:' + str(loc["lon"]) + '</div></div>',
        unsafe_allow_html=True)

st.sidebar.markdown('<hr style="border-color:#1E3A5F;">', unsafe_allow_html=True)
st.sidebar.markdown('<div style="font-family:Rajdhani,sans-serif;font-size:12px;color:#475569;letter-spacing:2px;margin-bottom:8px;">QUICK SELECT — TAMIL NADU</div>', unsafe_allow_html=True)

tn_cities = [("Coimbatore",11.0168,76.9558),("Chennai",13.0827,80.2707),
             ("Madurai",9.9252,78.1198),("Salem",11.6643,78.1460),
             ("Ooty",11.4102,76.6950),("Trichy",10.7905,78.7047)]
c1,c2 = st.sidebar.columns(2)
for i,(city,clat,clon) in enumerate(tn_cities):
    col = c1 if i%2==0 else c2
    if col.button(city, key="q_"+city, use_container_width=True):
        st.session_state.location = {"name":city+", Tamil Nadu","lat":clat,"lon":clon,"found":True}
        st.rerun()

st.sidebar.markdown('<hr style="border-color:#1E3A5F;">', unsafe_allow_html=True)
st.sidebar.markdown("""
<div style="background:#0D1421;border:1px solid #EF444433;border-radius:8px;
            padding:10px 14px;text-align:center;">
  <div style="font-size:12px;color:#EF4444;font-family:Rajdhani,sans-serif;
              font-weight:700;letter-spacing:1px;">📱 ALERT CONTACTS</div>
  <div style="font-size:11px;color:#475569;margin-top:4px;">
    Add your number, fire station &amp; police<br>in the <b style="color:#F1F5F9;">Alert Contacts</b> tab →
  </div>
</div>
""", unsafe_allow_html=True)

# ─── HEADER ──────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#0D1421,#060B14);border:1px solid #1E3A5F;border-left:4px solid #EF4444;border-radius:14px;padding:20px 28px;margin-bottom:20px;">
  <div style="font-family:'Rajdhani',sans-serif;font-size:26px;font-weight:700;color:#F8FAFC;letter-spacing:2px;">
    🔥 REAL-TIME WILDFIRE DETECTION & ALERT SYSTEM — TAMIL NADU
  </div>
  <div style="font-size:12px;color:#475569;margin-top:6px;">
    Search any city/forest → Live weather → ML prediction → Auto SMS alert → CSV saved
  </div>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["🔍  Live Analysis","🗺️  Tamil Nadu Map","📋  History Log","📱  SMS Setup"])


# ═══════════════════════════════════════════════════════════════
# TAB 1 — LIVE ANALYSIS
# ═══════════════════════════════════════════════════════════════
with tab1:
    st.markdown("")
    if not loc["found"]:
        st.markdown("""
<div style="text-align:center;padding:50px 20px;">
  <div style="font-size:72px;margin-bottom:20px;">🔥</div>
  <div style="font-family:'Rajdhani',sans-serif;font-size:28px;font-weight:700;color:#F1F5F9;">WILDFIRE RISK PREDICTOR</div>
  <div style="font-size:14px;color:#475569;margin-top:10px;">Search any Tamil Nadu city, forest, or wildlife sanctuary on the left</div>
</div>""", unsafe_allow_html=True)
        show_map(build_tamilnadu_map(), height=460)
    else:
        st.markdown(
            '<div style="background:#0D1421;border:1px solid #1E3A5F;border-left:3px solid #EF4444;border-radius:10px;padding:12px 18px;margin-bottom:16px;">'
            '<span style="font-size:12px;color:#475569;font-family:Rajdhani;letter-spacing:2px;">SELECTED LOCATION</span><br>'
            '<span style="font-size:18px;font-weight:700;color:#F1F5F9;font-family:Rajdhani;">' + loc["name"] + '</span>'
            '<span style="font-size:12px;color:#475569;margin-left:14px;">Lat:' + str(loc["lat"]) + ' Lon:' + str(loc["lon"]) + '</span></div>',
            unsafe_allow_html=True)

        if st.button("🔥  ANALYZE WILDFIRE RISK FOR " + loc["name"].split("|")[0].split(",")[0].strip().upper(),
                     type="primary", use_container_width=True):
            with st.spinner("Fetching live weather for " + loc["name"] + "..."):
                result = predict_for_location(lat=loc["lat"], lon=loc["lon"], name=loc["name"])

            if result is None:
                st.error("❌ Weather fetch failed. Check OWM_API_KEY in .env file.")
                st.stop()

            risk_level = result["risk"]["level"]
            prob_pct   = round(result["probability"] * 100, 1)

            # Auto-dispatch (save CSV + send alerts if HIGH/CRITICAL)
            sent_channels = dispatch_alerts(result)

            # If contacts saved, send SMS to all of them
            sms_status = []
            if risk_level in ["HIGH", "CRITICAL"]:
                from alert_engine import send_sms_direct
                saved_c = st.session_state.get("contacts", {})
                all_numbers = {
                    "You"            : saved_c.get("your_number", ""),
                    "Fire Station"   : saved_c.get("fire_station", ""),
                    "Police"         : saved_c.get("police", ""),
                    "Forest Officer" : saved_c.get("forest_officer", ""),
                    saved_c.get("extra1_name","Extra") : saved_c.get("extra1_number", ""),
                }
                # Also check sidebar phone
                sidebar_phone = st.session_state.get("my_phone", "")
                if sidebar_phone and sidebar_phone not in all_numbers.values():
                    all_numbers["Sidebar Contact"] = sidebar_phone

                from alert_engine import load_contacts, send_alert_to_contact
                saved_c = load_contacts()
                email_map = {
                    saved_c.get('your_name','You')              : saved_c.get('your_email',''),
                    saved_c.get('fire_name','Fire Station')     : saved_c.get('fire_station_email',''),
                    saved_c.get('police_name','Police')         : saved_c.get('police_email',''),
                    saved_c.get('forest_name','Forest Officer') : saved_c.get('forest_officer_email',''),
                }
                for contact_name, email in email_map.items():
                    if email and email.strip():
                        code, msg = send_alert_to_contact(result, email.strip())
                        sms_status.append((contact_name, email, code, msg))

            # ── Risk Banner ──────────────────────────────────────────────────
            risk_styles = {
                "CRITICAL": ("linear-gradient(135deg,#7F1D1D,#450A0A)","#FCA5A5","#DC2626"),
                "HIGH"    : ("linear-gradient(135deg,#7C2D12,#431407)","#FED7AA","#EA580C"),
                "MEDIUM"  : ("linear-gradient(135deg,#78350F,#451A03)","#FDE68A","#D97706"),
                "LOW"     : ("linear-gradient(135deg,#14532D,#052E16)","#BBF7D0","#16A34A"),
            }
            bg,fg,bd = risk_styles.get(risk_level,("#1E293B","#F1F5F9","#475569"))

            risk_emoji = {"CRITICAL":"🔴","HIGH":"🟠","MEDIUM":"🟡","LOW":"🟢"}
            risk_msg   = {
                "CRITICAL": "WILDFIRE IMMINENT — EVACUATE IMMEDIATELY",
                "HIGH"    : "DANGEROUS CONDITIONS — FIRE RISK VERY HIGH",
                "MEDIUM"  : "ELEVATED RISK — MONITOR CONDITIONS",
                "LOW"     : "SAFE CONDITIONS — LOW FIRE RISK",
            }
            st.markdown(
                '<div style="background:' + bg + ';border:2px solid ' + bd + ';border-radius:14px;'
                'padding:20px 28px;margin-bottom:20px;box-shadow:0 0 30px ' + bd + '44;text-align:center;">'
                '<div style="font-family:Rajdhani,sans-serif;font-size:28px;font-weight:700;color:' + fg + ';letter-spacing:2px;">'
                + risk_emoji.get(risk_level,"") + " " + risk_msg.get(risk_level,risk_level) +
                '</div>'
                '<div style="font-size:14px;color:' + bd + ';margin-top:6px;">'
                'Fire Probability: <b>' + str(prob_pct) + '%</b>'
                ' &nbsp;|&nbsp; Location: <b>' + loc["name"].split("|")[0].strip() + '</b>'
                ' &nbsp;|&nbsp; ✅ Saved to CSV'
                '</div></div>',
                unsafe_allow_html=True)

            # ── Weather + FWI ────────────────────────────────────────────────
            w = result["weather"]
            f = result["fwi"]
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("🌡️ Temperature", str(w["Temperature"]) + " °C", help="Higher = more fire risk")
            c2.metric("💧 Humidity",    str(w["RH"]) + " %",           help="Lower = fire spreads faster")
            c3.metric("💨 Wind Speed",  str(w["Ws"]) + " km/h",        help="Higher wind = wider fire spread")
            c4.metric("🌧️ Rainfall",    str(w["Rain"]) + " mm",        help="No rain = dry fuel = fire risk")
            st.markdown("")
            f1,f2,f3,f4,f5,f6 = st.columns(6)
            f1.metric("FFMC", f["FFMC"], help="Fine Fuel Moisture Code")
            f2.metric("DMC",  f["DMC"],  help="Duff Moisture Code")
            f3.metric("DC",   f["DC"],   help="Drought Code")
            f4.metric("ISI",  f["ISI"],  help="Initial Spread Index")
            f5.metric("BUI",  f["BUI"],  help="Buildup Index")
            f6.metric("🔥 FWI", f["FWI"], help="Fire Weather Index — higher = more dangerous")
            st.markdown("")

            # ── Gauge + Map ──────────────────────────────────────────────────
            col_g, col_m = st.columns([5, 7])
            with col_g:
                gc = {"CRITICAL":"#DC2626","HIGH":"#EA580C","MEDIUM":"#D97706","LOW":"#16A34A"}
                fig = go.Figure(go.Indicator(
                    mode="gauge+number", value=prob_pct,
                    title={"text":"Fire Probability %","font":{"size":14,"color":"#64748B"}},
                    number={"suffix":"%","font":{"color":gc.get(risk_level,"#F1F5F9"),"size":52}},
                    gauge={
                        "axis":{"range":[0,100],"tickcolor":"#334155","nticks":5},
                        "bar":{"color":gc.get(risk_level,"#6B7280"),"thickness":0.25},
                        "bgcolor":"rgba(0,0,0,0)","bordercolor":"#1E3A5F","borderwidth":1,
                        "steps":[{"range":[0,25],"color":"#052E16"},{"range":[25,50],"color":"#451A03"},
                                 {"range":[50,75],"color":"#431407"},{"range":[75,100],"color":"#450A0A"}],
                        "threshold":{"line":{"color":"#EF4444","width":4},"thickness":0.75,"value":75}
                    }))
                fig.update_layout(height=280,margin=dict(t=50,b=20,l=30,r=30),
                                  paper_bgcolor="rgba(0,0,0,0)",font=dict(color="#F1F5F9"))
                st.plotly_chart(fig, use_container_width=True)

                # ── ALERT STATUS BOX ─────────────────────────────────────────
                if risk_level in ["HIGH", "CRITICAL"]:
                    # Build SMS status lines
                    sms_lines = ""
                    if sms_status:
                        for cname, cnum, cstatus, _cmsg in sms_status:
                            icon = "✅" if cstatus == "sent" else ("📋" if cstatus == "demo" else "❌")
                            sms_lines += icon + " SMS → " + cname + " (" + cnum[:7] + "***)<br>"
                    else:
                        sms_lines = "⚠️ No contacts saved — go to <b>Alert Contacts</b> tab to add numbers<br>"

                    st.markdown(
                        '<div style="background:#450A0A;border:2px solid #DC2626;border-radius:10px;padding:14px;">'
                        '<div style="font-family:Rajdhani,sans-serif;font-size:18px;font-weight:700;color:#FCA5A5;text-align:center;">🚨 EMERGENCY ALERT SENT!</div>'
                        '<div style="font-size:12px;color:#EF4444;margin-top:8px;line-height:2;">'
                        + sms_lines +
                        '📊 CSV → ✅ Saved automatically'
                        '</div>'
                        '<div style="margin-top:10px;padding-top:10px;border-top:1px solid #7F1D1D;font-size:12px;color:#94A3B8;text-align:center;">'
                        '📞 Call 101 (Fire) &nbsp;|&nbsp; 📞 112 (Emergency)<br>'
                        '🚶 Evacuate area &nbsp;|&nbsp; 🚒 Deploy fire teams'
                        '</div></div>',
                        unsafe_allow_html=True)
                else:
                    st.markdown(
                        '<div style="background:#052E16;border:1px solid #16A34A;border-radius:10px;padding:14px;text-align:center;">'
                        '<div style="font-family:Rajdhani,sans-serif;font-size:16px;font-weight:700;color:#BBF7D0;">✅ CONDITIONS SAFE</div>'
                        '<div style="font-size:12px;color:#16A34A;margin-top:4px;">'
                        + risk_level + ' risk — Monitoring active | No alert needed</div></div>',
                        unsafe_allow_html=True)

                st.markdown("")
                if st.button("⚡ Force Send Alert Now", use_container_width=True):
                    from alert_engine import send_sms_direct
                    saved_c  = st.session_state.get("contacts", {})
                    all_nums = {
                        "You"           : saved_c.get("your_number",""),
                        "Fire Station"  : saved_c.get("fire_station",""),
                        "Police"        : saved_c.get("police",""),
                        "Forest Officer": saved_c.get("forest_officer",""),
                        saved_c.get("extra1_name","Extra"): saved_c.get("extra1_number",""),
                    }
                    sidebar_phone = st.session_state.get("my_phone","")
                    if sidebar_phone:
                        all_nums["Sidebar"] = sidebar_phone

                    sent_any = False
                    for cname, num in all_nums.items():
                        if num and num.strip():
                            code, msg = send_sms_direct(result, num.strip())
                            if code == "sent":
                                st.success("✅ SMS sent to " + cname + " (" + num + ")")
                            elif code == "demo":
                                st.info("📋 Demo mode — " + cname + ". Configure Gmail to send real SMS.")
                            elif code == "invalid":
                                st.warning("⚠️ Invalid number for " + cname + ": " + msg)
                            else:
                                st.error("❌ Failed for " + cname + ": " + msg)
                            sent_any = True
                    if not sent_any:
                        st.warning("⚠️ No contacts saved! Go to Alert Contacts tab and add phone numbers.")

            with col_m:
                st.markdown(
                    '<div style="font-family:Rajdhani,sans-serif;font-size:14px;color:#94A3B8;letter-spacing:1px;margin-bottom:8px;">📍 MAP — ' + loc["name"].upper() + '</div>',
                    unsafe_allow_html=True)
                show_map(build_live_map(result), height=520)

        else:
            show_map(build_tamilnadu_map(), height=480)


# ═══════════════════════════════════════════════════════════════
# TAB 2 — TAMIL NADU MAP
# ═══════════════════════════════════════════════════════════════
with tab2:
    st.markdown("")
    st.markdown('<div style="font-family:Rajdhani,sans-serif;font-size:22px;font-weight:700;color:#F1F5F9;letter-spacing:2px;margin-bottom:16px;">🗺️ TAMIL NADU WILDFIRE RISK MAP</div>', unsafe_allow_html=True)
    mode = st.radio("View Mode",["All Monitored Zones","History Heatmap"],horizontal=True)
    st.markdown("")

    if mode == "All Monitored Zones":
        if st.button("🔄 Run All Zones Now", type="primary"):
            results, prog, status = [], st.progress(0), st.empty()
            for i, zone in enumerate(LOCATIONS):
                status.text("Analyzing " + zone["name"] + "...")
                res = predict_for_location(zone["lat"],zone["lon"],zone["name"])
                if res:
                    dispatch_alerts(res)
                    results.append(res)
                prog.progress((i+1)/len(LOCATIONS))
            status.empty(); prog.empty()
            if results:
                show_map(build_multizone_map(results), height=560)
                st.dataframe(pd.DataFrame([{
                    "Location":r["location"],"Risk":r["risk"]["level"],
                    "Fire Prob%":round(r["probability"]*100,1),
                    "Temp°C":r["weather"]["Temperature"],
                    "Humidity%":r["weather"]["RH"],"FWI":r["fwi"]["FWI"]
                } for r in results]), use_container_width=True, hide_index=True)
            else:
                st.error("Could not fetch zone data.")
        else:
            show_map(build_tamilnadu_map(), height=520)
    else:
        show_map(build_history_heatmap(), height=560)


# ═══════════════════════════════════════════════════════════════
# TAB 3 — HISTORY LOG
# ═══════════════════════════════════════════════════════════════
with tab3:
    st.markdown("")
    st.markdown('<div style="font-family:Rajdhani,sans-serif;font-size:22px;font-weight:700;color:#F1F5F9;letter-spacing:2px;margin-bottom:4px;">📋 PREDICTION HISTORY</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:12px;color:#475569;margin-bottom:8px;">Every prediction auto-saved — LOW · MEDIUM · HIGH · CRITICAL</div>', unsafe_allow_html=True)

    with st.expander("ℹ️ What is this log?"):
        st.markdown("""
**History Log** automatically saves every wildfire prediction you run.

**Each row contains:** Date/Time · Location · Temp · Humidity · Wind · Rain · FWI scores · Fire probability % · Risk level · Whether SMS was sent

**Uses:**
- 📊 Track high-risk zones over time
- 📅 Compare today vs last week
- 📝 Official report for forest department
- 🔍 Evidence if fire actually occurs
- 📥 Download CSV for research or government submission
        """)

    if os.path.exists(ALERT_LOG_PATH) and os.path.getsize(ALERT_LOG_PATH) > 0:
        try:
            log_df = pd.read_csv(ALERT_LOG_PATH, engine="python", on_bad_lines="skip")
            if not log_df.empty:
                total = len(log_df)
                m1,m2,m3,m4,m5 = st.columns(5)
                m1.metric("📊 Total", total)
                m2.metric("🔴 CRITICAL", len(log_df[log_df["risk_level"]=="CRITICAL"]))
                m3.metric("🟠 HIGH",     len(log_df[log_df["risk_level"]=="HIGH"]))
                m4.metric("🟡 MEDIUM",   len(log_df[log_df["risk_level"]=="MEDIUM"]))
                m5.metric("🟢 LOW",      len(log_df[log_df["risk_level"]=="LOW"]))
                st.markdown("")

                f1,f2 = st.columns(2)
                with f1: rf = st.selectbox("Filter Risk",["All","CRITICAL","HIGH","MEDIUM","LOW"])
                with f2: lf = st.selectbox("Filter Location",["All"]+sorted(log_df["location"].unique().tolist()))
                filtered = log_df.copy()
                if rf!="All": filtered = filtered[filtered["risk_level"]==rf]
                if lf!="All": filtered = filtered[filtered["location"]==lf]
                st.dataframe(filtered.sort_values("timestamp",ascending=False),use_container_width=True,hide_index=True)
                st.caption("Showing " + str(len(filtered)) + " of " + str(total) + " records.")

                dl,rst = st.columns([3,1])
                with dl:
                    st.download_button("⬇️ Download CSV", log_df.to_csv(index=False).encode(),
                                       "wildfire_"+datetime.now().strftime("%Y%m%d")+".csv","text/csv",use_container_width=True)
                with rst:
                    if st.button("🗑️ Reset Log", use_container_width=True):
                        os.remove(ALERT_LOG_PATH)
                        st.success("Cleared!")
                        st.rerun()
        except Exception as e:
            st.error("CSV corrupted. Click Reset to fix.")
            if st.button("🗑️ Reset Corrupt CSV", type="primary"):
                os.remove(ALERT_LOG_PATH)
                st.rerun()
    else:
        st.info("No predictions yet. Search a location and click Analyze!")


# ═══════════════════════════════════════════════════════════════
# TAB 4 — ALERT CONTACTS
# ═══════════════════════════════════════════════════════════════
with tab4:
    st.markdown("")
    from alert_engine import load_contacts, save_contacts, send_alert_to_contact
    import smtplib as _smtplib

    st.markdown('''
<div style="font-family:Rajdhani,sans-serif;font-size:24px;font-weight:700;
            color:#F1F5F9;letter-spacing:2px;margin-bottom:4px;">📧 ALERT CONTACTS</div>
<div style="font-size:13px;color:#475569;margin-bottom:20px;">
  When fire risk is <b style="color:#DC2626;">HIGH or CRITICAL</b> — email alert sent to all contacts automatically.
</div>
''', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════
    # GMAIL SENDER SETUP
    # ════════════════════════════════════════════════════════════
    st.markdown('''
<div style="background:#0D1421;border:1px solid #334155;border-left:4px solid #EF4444;
            border-radius:12px;padding:16px 20px;margin-bottom:16px;">
  <div style="font-family:Rajdhani,sans-serif;font-size:16px;font-weight:700;
              color:#F1F5F9;margin-bottom:4px;">⚙️ STEP 1 — Your Gmail (used to SEND alerts)</div>
  <div style="font-size:12px;color:#475569;">Enter your Gmail + App Password below. No .env editing needed.</div>
</div>
''', unsafe_allow_html=True)

    saved_c = load_contacts()

    gc1, gc2 = st.columns(2)
    with gc1:
        inp_email = st.text_input(
            "📧 Your Gmail Address",
            value = saved_c.get("sender_email", ""),
            placeholder = "yourname@gmail.com",
            key = "inp_sender_email"
        )
    with gc2:
        inp_pass = st.text_input(
            "🔑 Gmail App Password",
            value = saved_c.get("sender_pass", ""),
            placeholder = "abcd efgh ijkl mnop  (16 letters with spaces)",
            type = "password",
            key = "inp_sender_pass",
            help = "This is NOT your Gmail login password. Get it from myaccount.google.com/apppasswords"
        )

    tc1, tc2 = st.columns([1,2])
    with tc1:
        test_clicked = st.button("🔌 Test Connection", use_container_width=True, key="btn_test_conn")
    with tc2:
        save_creds_clicked = st.button("💾 Save Gmail Credentials", use_container_width=True, key="btn_save_creds")

    if save_creds_clicked:
        if not inp_email or not inp_pass:
            st.warning("⚠️ Enter both Gmail address and App Password!")
        else:
            saved_c["sender_email"] = inp_email.strip()
            saved_c["sender_pass"]  = inp_pass.strip()
            save_contacts(saved_c)
            st.success("✅ Gmail credentials saved!")

    if test_clicked:
        test_email = inp_email.strip()
        test_pass  = inp_pass.strip()
        if not test_email or not test_pass:
            st.warning("⚠️ Enter your Gmail and App Password first, then click Test.")
        else:
            with st.spinner("Testing Gmail connection..."):
                try:
                    with _smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as _smtp:
                        _smtp.login(test_email, test_pass)
                    # Save on success
                    saved_c["sender_email"] = test_email
                    saved_c["sender_pass"]  = test_pass
                    save_contacts(saved_c)
                    st.success("✅ Gmail connected successfully! Credentials saved automatically.")
                    st.balloons()
                except _smtplib.SMTPAuthenticationError:
                    st.error("❌ Wrong App Password!")
                    st.markdown('''
<div style="background:#1A0A0A;border:1px solid #DC2626;border-radius:10px;padding:16px;margin-top:8px;">
  <div style="color:#FCA5A5;font-weight:700;font-size:14px;margin-bottom:12px;">
    📋 How to get the correct App Password — follow exactly:
  </div>
  <div style="font-size:13px;color:#F1F5F9;line-height:2.6;">
    <b style="color:#FDE68A;">Step 1:</b> Open new browser tab<br>
    <b style="color:#FDE68A;">Step 2:</b> Go to this link exactly →
      <b style="color:#EF4444;font-size:14px;">myaccount.google.com/apppasswords</b><br>
    <b style="color:#FDE68A;">Step 3:</b> Sign in to Google if asked<br>
    <b style="color:#FDE68A;">Step 4:</b> You see a text box — type <b style="color:#16A34A;">Wildfire</b> → click <b>Create</b><br>
    <b style="color:#FDE68A;">Step 5:</b> A box pops up with <b style="color:#16A34A;">16 letters like: abcd efgh ijkl mnop</b><br>
    <b style="color:#FDE68A;">Step 6:</b> Copy those 16 letters (include the spaces)<br>
    <b style="color:#FDE68A;">Step 7:</b> Paste in the App Password box above → Test Connection<br>
  </div>
  <div style="margin-top:12px;padding-top:10px;border-top:1px solid #7F1D1D;
              font-size:12px;color:#94A3B8;">
    ⚠️ <b>Cannot find App Passwords?</b> First go to Security → turn ON 2-Step Verification → then try again<br>
    ⚠️ <b>The App Password looks like:</b> abcd efgh ijkl mnop — 4 groups of 4 letters with spaces
  </div>
</div>
''', unsafe_allow_html=True)
                except Exception as e:
                    st.error("❌ Connection error: " + str(e) + " — check your internet connection.")

    # Show current Gmail status
    current_email = saved_c.get("sender_email","")
    current_pass  = saved_c.get("sender_pass","")
    if current_email and current_pass:
        st.success("✅ Gmail ready: " + current_email + " — alerts will be sent from this account.")
    else:
        st.warning("⚠️ Gmail not saved yet — enter credentials above and click Save or Test Connection.")

    st.markdown("<hr style='border-color:#1E3A5F;margin:20px 0;'>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════
    # ALERT RECIPIENTS
    # ════════════════════════════════════════════════════════════
    st.markdown('''
<div style="background:#0D1421;border:1px solid #334155;border-left:4px solid #16A34A;
            border-radius:12px;padding:16px 20px;margin-bottom:16px;">
  <div style="font-family:Rajdhani,sans-serif;font-size:16px;font-weight:700;
              color:#F1F5F9;margin-bottom:4px;">📬 STEP 2 — Who Receives the Alert?</div>
  <div style="font-size:12px;color:#475569;">
    When HIGH or CRITICAL detected → email sent to ALL addresses below automatically. 📲 Install Gmail app on phone for instant notifications!
  </div>
</div>
''', unsafe_allow_html=True)

    ra, rb = st.columns(2, gap="large")
    with ra:
        st.markdown('<div style="font-size:12px;color:#EF4444;font-weight:700;margin-bottom:4px;">👤 YOUR EMAIL</div>', unsafe_allow_html=True)
        your_name  = st.text_input("Your Name",  value=saved_c.get("your_name",""),  placeholder="e.g. Ravi Kumar",    key="r_your_name")
        your_email = st.text_input("Your Email", value=saved_c.get("your_email",""), placeholder="yourname@gmail.com", key="r_your_email")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div style="font-size:12px;color:#EA580C;font-weight:700;margin-bottom:4px;">🚒 FIRE STATION EMAIL</div>', unsafe_allow_html=True)
        fire_name  = st.text_input("Fire Station Name",  value=saved_c.get("fire_name",""),           placeholder="e.g. Sathiyamangalam Fire Station", key="r_fire_name")
        fire_email = st.text_input("Fire Station Email", value=saved_c.get("fire_station_email",""),   placeholder="firestation@tn.gov.in",             key="r_fire_email")

    with rb:
        st.markdown('<div style="font-size:12px;color:#3B82F6;font-weight:700;margin-bottom:4px;">👮 POLICE EMAIL</div>', unsafe_allow_html=True)
        police_name  = st.text_input("Police Name",  value=saved_c.get("police_name",""),  placeholder="e.g. Gobichettipalayam Police", key="r_pol_name")
        police_email = st.text_input("Police Email", value=saved_c.get("police_email",""), placeholder="police@tn.gov.in",              key="r_pol_email")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div style="font-size:12px;color:#16A34A;font-weight:700;margin-bottom:4px;">🌿 FOREST OFFICER EMAIL</div>', unsafe_allow_html=True)
        forest_name  = st.text_input("Forest Officer Name",  value=saved_c.get("forest_name",""),           placeholder="e.g. DFO Erode Division",   key="r_fo_name")
        forest_email = st.text_input("Forest Officer Email", value=saved_c.get("forest_officer_email",""),   placeholder="dfo@forests.tn.gov.in",     key="r_fo_email")

    st.markdown("<br>", unsafe_allow_html=True)
    sb1, sb2 = st.columns([2,1])

    with sb1:
        if st.button("💾 SAVE ALL CONTACTS", type="primary", use_container_width=True, key="btn_save_contacts"):
            saved_c.update({
                "your_name": your_name, "your_email": your_email,
                "fire_name": fire_name, "fire_station_email": fire_email,
                "police_name": police_name, "police_email": police_email,
                "forest_name": forest_name, "forest_officer_email": forest_email,
            })
            save_contacts(saved_c)
            st.success("✅ All contacts saved! Alerts will go to all emails above when HIGH/CRITICAL detected.")

    with sb2:
        if st.button("📧 Send Test Email", use_container_width=True, key="btn_test_email"):
            all_emails = [e for e in [your_email, fire_email, police_email, forest_email] if e.strip()]
            if not all_emails:
                st.warning("⚠️ Enter at least one recipient email first!")
            elif not saved_c.get("sender_email") or not saved_c.get("sender_pass"):
                st.error("❌ Save Gmail credentials first (Step 1 above)!")
            else:
                test_result = {
                    "location":"TEST — Wildfire Alert System",
                    "lat":11.1271,"lon":78.6569,
                    "timestamp":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "probability":0.72,"prediction":1,
                    "maps_url":"https://maps.google.com/?q=11.1271,78.6569",
                    "risk":{"level":"HIGH","should_alert":True},
                    "weather":{"Temperature":38,"RH":18,"Ws":22,"Rain":0},
                    "fwi":{"FFMC":91,"DMC":44,"DC":310,"ISI":17,"BUI":55,"FWI":45},
                }
                for em in all_emails:
                    code, msg = send_alert_to_contact(test_result, em.strip())
                    if code == "sent":
                        st.success("✅ Test email sent → " + em + " — check your inbox now!")
                    else:
                        st.error("❌ Failed → " + em + ": " + msg)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Saved recipients display ──────────────────────────────────────────
    saved_c2    = load_contacts()
    recip_list  = [
        ("👤", saved_c2.get("your_name","You"),              saved_c2.get("your_email","")),
        ("🚒", saved_c2.get("fire_name","Fire Station"),     saved_c2.get("fire_station_email","")),
        ("👮", saved_c2.get("police_name","Police"),         saved_c2.get("police_email","")),
        ("🌿", saved_c2.get("forest_name","Forest Officer"), saved_c2.get("forest_officer_email","")),
    ]
    active = [(i,n,e) for i,n,e in recip_list if e.strip()]
    if active:
        st.markdown('<div style="font-family:Rajdhani,sans-serif;font-size:12px;color:#475569;letter-spacing:2px;margin-bottom:10px;">SAVED RECIPIENTS</div>', unsafe_allow_html=True)
        cols = st.columns(len(active))
        for idx,(icon,name,email) in enumerate(active):
            with cols[idx]:
                st.markdown(
                    '<div style="background:#0D1421;border:1px solid #1E3A5F;border-radius:10px;padding:14px;text-align:center;">' +
                    '<div style="font-size:26px;">' + icon + '</div>' +
                    '<div style="font-size:12px;font-weight:700;color:#F1F5F9;margin-top:6px;">' + name + '</div>' +
                    '<div style="font-size:11px;color:#16A34A;margin-top:4px;word-break:break-all;">' + email + '</div></div>',
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Email preview ─────────────────────────────────────────────────────
    st.markdown('''
<div style="background:#0D1421;border:1px solid #334155;border-radius:12px;padding:20px;">
  <div style="font-family:Rajdhani,sans-serif;font-size:13px;font-weight:700;
              color:#64748B;letter-spacing:2px;margin-bottom:12px;">📨 EMAIL YOU WILL RECEIVE</div>
  <div style="background:#060B14;border-left:4px solid #EF4444;border-radius:8px;
              padding:16px;font-size:12px;color:#F1F5F9;line-height:2.2;font-family:monospace;">
    <b style="color:#EF4444;">Subject: 🟠 HIGH WILDFIRE — Sathiyamangalam Forest (72%)</b><br><br>
    🟠 WILDFIRE HIGH RISK ALERT<br>
    📍 Location  : Sathiyamangalam Forest<br>
    🔥 Fire Risk : 72% probability<br>
    🌡️ Temp: 38°C | Humidity: 18% | Wind: 22 km/h | Rain: 0mm<br>
    ⚠️ IMMEDIATE ACTION: Call 101 (Fire) | 112 (Emergency)<br>
    🗺️ Map: https://maps.google.com/?q=11.5167,77.2333
  </div>
  <div style="font-size:12px;color:#475569;margin-top:10px;">
    📲 Install <b style="color:#F1F5F9;">Gmail app</b> on phone + turn ON notifications = instant alert like SMS!
  </div>
</div>
''', unsafe_allow_html=True)
st.markdown('<hr style="border-color:#1E3A5F;">', unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;color:#1E3A5F;font-size:11px;font-family:Rajdhani,sans-serif;letter-spacing:2px;">'
    'WILDFIRE ALERT SYSTEM — TAMIL NADU &nbsp;|&nbsp; OPENWEATHERMAP + NASA FIRMS + XGBOOST &nbsp;|&nbsp; '
    + datetime.now().strftime("%Y-%m-%d %H:%M") + '</div>',
    unsafe_allow_html=True)