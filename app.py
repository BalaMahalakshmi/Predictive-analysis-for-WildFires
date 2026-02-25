import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from datetime import datetime
import os
 
from config import LOCATIONS, ALERT_LOG_PATH
from predictor import predict_for_location
from alert_engine import dispatch_alerts
from satellite import get_satellite_hotspots
 
# ── Page config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title = 'Wildfire Alert System',
    page_icon  = '',
    layout     = 'wide',
    initial_sidebar_state = 'expanded'
)
 
# ── Custom CSS ─────────────────────────────────────────────────────────
st.markdown('''
<style>
  .stMetric { background:#1E293B; border-radius:8px; padding:12px; }
  .risk-critical { color:#EF4444; font-size:2rem; font-weight:bold; }
  .risk-high     { color:#F97316; font-size:2rem; font-weight:bold; }
  .risk-medium   { color:#EAB308; font-size:2rem; font-weight:bold; }
  .risk-low      { color:#22C55E; font-size:2rem; font-weight:bold; }
</style>''', unsafe_allow_html=True)
 
# ── Sidebar ────────────────────────────────────────────────────────────
st.sidebar.image('https://img.icons8.com/color/96/fire.png', width=80)
st.sidebar.title('Wildfire Alert System')
st.sidebar.markdown('---')
 
# Location selector
loc_names = [l['name'] for l in LOCATIONS] + ['Custom Location']
selected  = st.sidebar.selectbox('Select Location', loc_names)
 
if selected == 'Custom Location':
    lat  = st.sidebar.number_input('Latitude',  value=36.75, format='%.4f')
    lon  = st.sidebar.number_input('Longitude', value=5.06,  format='%.4f')
    name = st.sidebar.text_input('Location Name', 'Custom Zone')
else:
    loc  = next(l for l in LOCATIONS if l['name'] == selected)
    lat, lon, name = loc['lat'], loc['lon'], loc['name']
 
auto_refresh = st.sidebar.checkbox('Auto Refresh (every 15 min)', value=False)
show_sat     = st.sidebar.checkbox('Show Satellite Fire Data',     value=True)
st.sidebar.markdown('---')
st.sidebar.info('Data source: OpenWeatherMap + NASA FIRMS')
 
# ── Main header ────────────────────────────────────────────────────────
st.title('Real-Time Wildfire Detection & Emergency Alert System')
st.caption(f'Monitoring: {name}  |  GPS: {lat}, {lon}  |  Updated: {datetime.now().strftime("%H:%M:%S")}')
st.markdown('---')
 
# ── Predict button ─────────────────────────────────────────────────────
col_btn, col_time = st.columns([1, 3])
with col_btn:
    run_predict = st.button('Analyze Now', type='primary', use_container_width=True)
 
if run_predict or auto_refresh:
    with st.spinner(f'Fetching live data for {name}...'):
        result = predict_for_location(lat=lat, lon=lon, name=name)
 
    if result is None:
        st.error('Could not fetch weather data. Check your OWM_API_KEY and internet connection.')
        st.stop()
 
    # ── Risk banner ───────────────────────────────────────────────────
    risk_level = result['risk']['level']
    prob_pct   = result['probability'] * 100
 
    color_map = {'LOW':'success', 'MEDIUM':'warning', 'HIGH':'warning', 'CRITICAL':'error'}
    banner_fn = {'LOW':st.success, 'MEDIUM':st.warning, 'HIGH':st.warning, 'CRITICAL':st.error}
    banner_fn[risk_level](f'{risk_level} RISK — Fire Probability: {prob_pct:.1f}%')
 
    # ── Metric row ────────────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric('Temperature', f'{result["weather"]["Temperature"]}C')
    c2.metric('Humidity',    f'{result["weather"]["RH"]}%')
    c3.metric('Wind Speed',  f'{result["weather"]["Ws"]} km/h')
    c4.metric('Rain',        f'{result["weather"]["Rain"]} mm')
    c5.metric('FWI',         result['fwi']['FWI'])
    c6.metric('Fire Risk',   f'{prob_pct:.1f}%')
    st.markdown('')
 
    # ── Gauge + Map side by side ──────────────────────────────────────
    col_gauge, col_map = st.columns([1, 2])
 
    with col_gauge:
        st.subheader('Risk Gauge')
        fig = go.Figure(go.Indicator(
            mode  = 'gauge+number+delta',
            value = prob_pct,
            title = {'text': 'Fire Probability (%)', 'font': {'size': 14}},
            delta = {'reference': 50},
            gauge = {
                'axis'  : {'range': [0, 100], 'tickwidth': 1},
                'bar'   : {'color': 'darkred'},
                'bgcolor': 'white',
                'steps' : [
                    {'range': [0,  25], 'color': '#D1FAE5'},
                    {'range': [25, 50], 'color': '#FEF9C3'},
                    {'range': [50, 75], 'color': '#FFEDD5'},
                    {'range': [75,100], 'color': '#FEE2E2'},
                ],
                'threshold': {
                    'line' : {'color': 'red', 'width': 4},
                    'thickness': 0.75, 'value': 75
                }
            }
        ))
        fig.update_layout(height=320, margin=dict(t=40,b=10,l=10,r=10))
        st.plotly_chart(fig, use_container_width=True)
 
    with col_map:
        st.subheader('Location Map')
        pin_color = {'LOW':'green','MEDIUM':'orange','HIGH':'red','CRITICAL':'darkred'}.get(risk_level,'gray')
        m = folium.Map(location=[lat, lon], zoom_start=9, tiles='OpenStreetMap')
        folium.CircleMarker(
            location=[lat, lon], radius=20, color=pin_color,
            fill=True, fill_color=pin_color, fill_opacity=0.4,
            popup=f'<b>{name}</b><br>{risk_level} RISK<br>{prob_pct:.1f}% fire probability'
        ).add_to(m)
        folium.Marker(
            location=[lat, lon],
            popup=f'{name}: {risk_level}',
            icon=folium.Icon(color=pin_color, icon='fire')
        ).add_to(m)
 
        if show_sat:
            hotspots = get_satellite_hotspots(lat, lon)
            if hotspots is not None:
                for _, row in hotspots.iterrows():
                    folium.CircleMarker(
                        location=[row['latitude'], row['longitude']],
                        radius=8, color='yellow', fill=True,
                        popup=f'Satellite Fire Hotspot | Confidence: {row.get("confidence","N/A")}%'
                    ).add_to(m)
 
        st_folium(m, width=600, height=320)
 
    # ── FWI breakdown table ───────────────────────────────────────────
    st.subheader('Fire Weather Index Breakdown')
    fwi_df = pd.DataFrame([result['fwi']]).T.reset_index()
    fwi_df.columns = ['Index', 'Value']
    fwi_df['Meaning'] = ['Fine Fuel Moisture', 'Duff Moisture Code', 'Drought Code',
                          'Initial Spread Index', 'Buildup Index', 'Fire Weather Index']
    st.dataframe(fwi_df, use_container_width=True, hide_index=True)
 
    # ── Alert dispatch ────────────────────────────────────────────────
    st.markdown('---')
    st.subheader('Emergency Alert Control')
    col_a, col_b = st.columns(2)
    with col_a:
        if result['risk']['should_alert']:
            if st.button('Send Emergency Alerts Now', type='primary'):
                with st.spinner('Sending alerts...'):
                    dispatch_alerts(result)
                st.success('Alerts dispatched via Telegram, SMS, and Email!')
        else:
            st.info(f'Risk level {risk_level} — no alert required.')
    with col_b:
        if st.button('Force Send Alert (Manual Override)'):
            result['risk']['should_alert'] = True
            dispatch_alerts(result)
            st.success('Manual alert sent!')
 
# ── Alert history ─────────────────────────────────────────────────────
st.markdown('---')
st.subheader('Alert History Log')
if os.path.exists(ALERT_LOG_PATH):
    try:
        log_df = pd.read_csv(ALERT_LOG_PATH)
        if log_df.empty or len(log_df.columns) == 0:
            st.info('No alerts have been sent yet. Alert history will appear here.')
        else:
            st.dataframe(
                log_df.sort_values('timestamp', ascending=False).head(50),
                use_container_width=True, hide_index=True
            )
    except Exception:
        st.info('No alerts have been sent yet. Alert history will appear here.')
else:
    st.info('No alerts have been sent yet. Alert history will appear here.')
 
# ── Footer ────────────────────────────────────────────────────────────
st.markdown('---')
st.caption('Wildfire Alert System | Data: OpenWeatherMap + NASA FIRMS | Model: XGBoost/Random Forest')
