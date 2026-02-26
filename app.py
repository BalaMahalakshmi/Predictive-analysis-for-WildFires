import streamlit as st
import streamlit.components.v1 as components   # ← KEY: renders HTML maps always
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os

from config import LOCATIONS, ALERT_LOG_PATH
from predictor import predict_for_location
from alert_engine import dispatch_alerts
from satellite import get_satellite_hotspots
from map_view import (
    build_india_map,
    build_live_map,
    build_multizone_map,
    build_history_heatmap,
    build_mini_map,
    get_map_html,
)

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title = 'Wildfire Alert System — India',
    page_icon  = '🔥',
    layout     = 'wide',
    initial_sidebar_state = 'expanded'
)

# ── CSS ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .stApp { background:#0F172A; color:#F1F5F9; }
  section[data-testid="stSidebar"] {
    background:#1E293B !important;
    border-right:1px solid #334155;
  }
  [data-testid="metric-container"] {
    background:#1E293B;
    border:1px solid #334155;
    border-radius:10px;
    padding:12px;
  }
  .stButton > button {
    background:#B91C1C !important;
    color:white !important;
    border:none !important;
    border-radius:8px !important;
    font-weight:bold !important;
    letter-spacing:1px !important;
  }
  .stButton > button:hover {
    background:#991B1B !important;
  }
  .stTabs [data-baseweb="tab"] {
    background:#1E293B;
    border-radius:8px 8px 0 0;
    color:#94A3B8;
    font-weight:bold;
  }
  .stTabs [aria-selected="true"] {
    background:#B91C1C !important;
    color:white !important;
  }
  hr { border-color:#334155; }
  iframe { border-radius: 10px; border: 1px solid #334155; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  HELPER — renders any folium map as HTML inside Streamlit
#  This ALWAYS works. No blank maps.
# ══════════════════════════════════════════════════════════════════
def show_map(folium_map, height=500):
    """Render folium map as HTML iframe — guaranteed to display."""
    html_content = get_map_html(folium_map)
    components.html(html_content, height=height, scrolling=False)


# ── Sidebar ────────────────────────────────────────────────────────────────
st.sidebar.markdown("""
<div style='text-align:center;padding:10px 0;'>
  <div style='font-size:44px;'>🔥</div>
  <div style='font-size:17px;font-weight:bold;color:#EF4444;margin-top:4px;'>
    WILDFIRE ALERT
  </div>
  <div style='font-size:11px;color:#64748B;margin-top:2px;'>
    Real-Time Detection — India
  </div>
</div>
""", unsafe_allow_html=True)
st.sidebar.markdown('---')

# ── Location input ─────────────────────────────────────────────────────────
st.sidebar.subheader('📍 Location')

input_method = st.sidebar.radio(
    'Input method',
    ['Choose from list', 'Enter any India location'],
    index=0
)

if input_method == 'Choose from list':
    selected = st.sidebar.selectbox(
        'Select Zone',
        [l['name'] for l in LOCATIONS]
    )
    loc = next(l for l in LOCATIONS if l['name'] == selected)
    lat, lon, name = loc['lat'], loc['lon'], loc['name']

else:
    name = st.sidebar.text_input(
        'Location Name',
        value       = 'Coimbatore',
        placeholder = 'e.g. Chennai, Bangalore, Mumbai...'
    )
    lat = st.sidebar.number_input(
        'Latitude',
        min_value = 6.0,
        max_value = 37.5,
        value     = 11.0168,
        format    = '%.4f',
        help      = 'India: 6.0 to 37.5'
    )
    lon = st.sidebar.number_input(
        'Longitude',
        min_value = 68.0,
        max_value = 97.5,
        value     = 76.9558,
        format    = '%.4f',
        help      = 'India: 68.0 to 97.5'
    )
    if not name.strip():
        name = 'Location (' + str(round(lat, 3)) + ', ' + str(round(lon, 3)) + ')'

st.sidebar.markdown('---')

# ── Sidebar mini map ───────────────────────────────────────────────────────
st.sidebar.subheader('📌 Preview')
mini_map = build_mini_map(lat, lon, name)
mini_html = get_map_html(mini_map)
components.html(mini_html, height=200, scrolling=False)   # ← always shows

st.sidebar.markdown('---')
st.sidebar.subheader('⚙️ Options')
show_sat = st.sidebar.checkbox('Show NASA Satellite Fires', value=False)
st.sidebar.markdown('---')
st.sidebar.caption('Weather: OpenWeatherMap\nSatellite: NASA FIRMS\nModel: XGBoost/RF')

# ── Header ─────────────────────────────────────────────────────────────────
st.markdown("""
<div style='background:linear-gradient(135deg,#1E293B,#0F172A);
            border:1px solid #334155;border-left:4px solid #EF4444;
            border-radius:12px;padding:18px 26px;margin-bottom:16px;'>
  <div style='font-size:24px;font-weight:900;color:#F8FAFC;'>
    🔥 Real-Time Wildfire Detection & Alert System — India
  </div>
  <div style='font-size:12px;color:#64748B;margin-top:4px;'>
    Live weather · ML prediction · Emergency alerts · Satellite detection
  </div>
</div>
""", unsafe_allow_html=True)

# ── TABS ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    '🔍  Live Analysis',
    '🗺️  India Map',
    '📋  History Log',
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — Live Analysis + Map
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('')

    # Location bar
    st.markdown(
        '<div style="background:#1E293B;border:1px solid #334155;'
        'border-radius:8px;padding:10px 16px;margin-bottom:14px;font-size:13px;">'
        '📍 <b style="color:#F1F5F9;">' + name + '</b>'
        ' &nbsp;|&nbsp; Lat: <b>' + str(round(lat, 4)) + '</b>'
        ' &nbsp;|&nbsp; Lon: <b>' + str(round(lon, 4)) + '</b>'
        '</div>',
        unsafe_allow_html=True
    )

    run_btn = st.button(
        '🔍  Analyze Now — ' + name,
        type             = 'primary',
        use_container_width = True
    )
    st.markdown('')

    if run_btn:
        with st.spinner('Fetching live weather for ' + name + '...'):
            result = predict_for_location(lat=lat, lon=lon, name=name)

        if result is None:
            st.error('Weather fetch failed. Check OWM_API_KEY in .env file.')
            st.stop()

        # Auto-save to CSV
        dispatch_alerts(result)

        risk_level = result['risk']['level']
        prob_pct   = round(result['probability'] * 100, 1)

        # Risk banner
        colors = {
            'CRITICAL': ('#7F1D1D','#FCA5A5','#DC2626'),
            'HIGH'    : ('#7C2D12','#FED7AA','#EA580C'),
            'MEDIUM'  : ('#78350F','#FDE68A','#D97706'),
            'LOW'     : ('#14532D','#BBF7D0','#16A34A'),
        }
        bg, fg, bd = colors.get(risk_level, ('#1E293B','#F1F5F9','#475569'))
        st.markdown(
            '<div style="background:' + bg + ';border:2px solid ' + bd + ';'
            'border-radius:10px;padding:14px;text-align:center;margin-bottom:14px;">'
            '<span style="font-size:28px;font-weight:900;color:' + fg + ';">'
            + risk_level + ' RISK</span>'
            '<span style="font-size:18px;color:' + bd + ';margin-left:14px;">'
            'Fire Probability: ' + str(prob_pct) + '%</span>'
            '<span style="font-size:13px;color:#94A3B8;margin-left:12px;">'
            '✓ Saved to CSV</span>'
            '</div>',
            unsafe_allow_html=True
        )

        # Weather metrics
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        c1.metric('🌡️ Temp',    str(result['weather']['Temperature']) + ' °C')
        c2.metric('💧 Humidity',str(result['weather']['RH']) + ' %')
        c3.metric('💨 Wind',    str(result['weather']['Ws']) + ' km/h')
        c4.metric('🌧️ Rain',    str(result['weather']['Rain']) + ' mm')
        c5.metric('🔥 FWI',     result['fwi']['FWI'])
        c6.metric('📊 Risk',    str(prob_pct) + ' %')
        st.markdown('')

        # Gauge + Map
        col_g, col_m = st.columns([1, 2])

        with col_g:
            st.subheader('Risk Gauge')
            gc = {
                'CRITICAL':'#DC2626','HIGH':'#EA580C',
                'MEDIUM':'#D97706','LOW':'#16A34A'
            }
            fig = go.Figure(go.Indicator(
                mode  = 'gauge+number',
                value = prob_pct,
                title = {'text':'Fire Probability (%)','font':{'size':13,'color':'#94A3B8'}},
                number= {'font':{'color':gc.get(risk_level,'#F1F5F9'),'size':44}},
                gauge = {
                    'axis'  : {'range':[0,100],'tickcolor':'#475569'},
                    'bar'   : {'color':gc.get(risk_level,'#6B7280'),'thickness':0.28},
                    'bgcolor': 'rgba(0,0,0,0)',
                    'bordercolor':'#334155',
                    'steps' : [
                        {'range':[0,25],'color':'#14532D'},
                        {'range':[25,50],'color':'#78350F'},
                        {'range':[50,75],'color':'#7C2D12'},
                        {'range':[75,100],'color':'#450A0A'},
                    ],
                    'threshold':{
                        'line':{'color':'#EF4444','width':4},
                        'thickness':0.75,'value':75
                    }
                }
            ))
            fig.update_layout(
                height=280,
                margin=dict(t=40,b=10,l=20,r=20),
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#F1F5F9')
            )
            st.plotly_chart(fig, use_container_width=True)

            # FWI table
            st.subheader('FWI Indices')
            st.dataframe(pd.DataFrame({
                'Index'  : ['FFMC','DMC','DC','ISI','BUI','FWI'],
                'Value'  : [
                    result['fwi']['FFMC'], result['fwi']['DMC'],
                    result['fwi']['DC'],   result['fwi']['ISI'],
                    result['fwi']['BUI'],  result['fwi']['FWI']
                ],
                'Meaning': [
                    'Fine Fuel Moisture','Duff Moisture',
                    'Drought Code','Initial Spread',
                    'Buildup Index','Fire Weather Index'
                ]
            }), use_container_width=True, hide_index=True)

        with col_m:
            st.subheader('📍 Map — ' + name)

            # Build map zoomed to location
            live_map = build_live_map(result)

            # Add satellite hotspots if enabled
            if show_sat:
                import folium as fl
                with st.spinner('Checking satellite...'):
                    hotspots = get_satellite_hotspots(lat, lon)
                if hotspots is not None:
                    for _, row in hotspots.iterrows():
                        fl.CircleMarker(
                            location=[row['latitude'], row['longitude']],
                            radius=8, color='#FACC15',
                            fill=True, fill_opacity=0.85,
                            tooltip='NASA Fire Hotspot'
                        ).add_to(live_map)
                    st.warning(str(len(hotspots)) + ' satellite hotspot(s) near this location!')

            # ← RENDER MAP — always works
            show_map(live_map, height=520)

        st.markdown('---')

        # Alert section
        col_a, col_b = st.columns(2)
        with col_a:
            if result['risk']['should_alert']:
                st.error(
                    risk_level + ' risk! '
                    'Email/SMS sent if configured in .env'
                )
            else:
                st.success(risk_level + ' — No emergency alert needed.')
        with col_b:
            if st.button('Force Send Alert', use_container_width=True):
                result['risk']['should_alert'] = True
                dispatch_alerts(result)
                st.success('Manual alert dispatched!')

    else:
        # ── Default view — India map ──────────────────────────────────────
        st.markdown(
            '<div style="background:#1E293B;border:1px solid #334155;'
            'border-radius:8px;padding:12px 18px;margin-bottom:14px;'
            'font-size:13px;color:#94A3B8;text-align:center;">'
            'India map shown below. '
            'Enter a location on the left and click '
            '<b style="color:#EF4444;">Analyze Now</b> to predict fire risk.'
            '</div>',
            unsafe_allow_html=True
        )
        # ← India map shown by default
        show_map(build_india_map(), height=540)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — India Map (multi-zone + heatmap)
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('')
    st.subheader('🗺️ India Wildfire Risk Map')

    map_mode = st.radio(
        'View Mode',
        ['All Monitored Zones', 'History Heatmap'],
        horizontal=True
    )
    st.markdown('')

    if map_mode == 'All Monitored Zones':
        st.caption(
            'Runs live predictions for all ' +
            str(len(LOCATIONS)) + ' configured zones.'
        )
        if st.button('Run All Zones Now', type='primary'):
            all_results = []
            prog  = st.progress(0)
            status = st.empty()
            for i, loc in enumerate(LOCATIONS):
                status.text('Analyzing ' + loc['name'] + '...')
                res = predict_for_location(
                    lat=loc['lat'], lon=loc['lon'], name=loc['name']
                )
                if res:
                    dispatch_alerts(res)
                    all_results.append(res)
                prog.progress((i + 1) / len(LOCATIONS))
            status.empty()
            prog.empty()

            if all_results:
                show_map(build_multizone_map(all_results), height=580)

                # Summary table
                st.markdown('### Zone Summary')
                st.dataframe(pd.DataFrame([{
                    'Location'   : r['location'],
                    'Risk Level' : r['risk']['level'],
                    'Fire Prob %': round(r['probability'] * 100, 1),
                    'Temp °C'    : r['weather']['Temperature'],
                    'Humidity %' : r['weather']['RH'],
                    'FWI'        : r['fwi']['FWI'],
                } for r in all_results]), use_container_width=True, hide_index=True)
            else:
                st.error('Could not fetch zone data. Check OWM_API_KEY.')
        else:
            show_map(build_india_map(), height=520)

    else:  # History Heatmap
        st.caption('Heatmap from all recorded predictions.')
        show_map(build_history_heatmap(), height=560)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — History Log
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('')
    st.subheader('📋 Prediction History')
    st.caption('Every prediction auto-saved — LOW, MEDIUM, HIGH, CRITICAL.')

    if (os.path.exists(ALERT_LOG_PATH) and
            os.path.getsize(ALERT_LOG_PATH) > 0):
        try:
            log_df = pd.read_csv(ALERT_LOG_PATH)
            if log_df.empty:
                st.info('No predictions yet.')
            else:
                total = len(log_df)
                m1,m2,m3,m4,m5 = st.columns(5)
                m1.metric('Total',    total)
                m2.metric('CRITICAL', len(log_df[log_df['risk_level']=='CRITICAL']))
                m3.metric('HIGH',     len(log_df[log_df['risk_level']=='HIGH']))
                m4.metric('MEDIUM',   len(log_df[log_df['risk_level']=='MEDIUM']))
                m5.metric('LOW',      len(log_df[log_df['risk_level']=='LOW']))
                st.markdown('')

                c1, c2 = st.columns(2)
                with c1:
                    rf = st.selectbox(
                        'Filter by Risk',
                        ['All','CRITICAL','HIGH','MEDIUM','LOW']
                    )
                with c2:
                    lf = st.selectbox(
                        'Filter by Location',
                        ['All'] + sorted(log_df['location'].unique().tolist())
                    )

                filtered = log_df.copy()
                if rf != 'All':
                    filtered = filtered[filtered['risk_level'] == rf]
                if lf != 'All':
                    filtered = filtered[filtered['location'] == lf]

                st.dataframe(
                    filtered.sort_values('timestamp', ascending=False),
                    use_container_width=True, hide_index=True
                )
                st.caption(
                    'Showing ' + str(len(filtered)) +
                    ' of ' + str(total) + ' records.'
                )

                st.download_button(
                    label     = '⬇️ Download CSV',
                    data      = log_df.to_csv(index=False).encode('utf-8'),
                    file_name = 'wildfire_' + datetime.now().strftime('%Y%m%d') + '.csv',
                    mime      = 'text/csv',
                    use_container_width=True
                )
        except Exception as e:
            st.error('Error: ' + str(e))
    else:
        st.info('No predictions yet. Run Analyze Now in Live Analysis tab!')

# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown('---')
st.markdown(
    '<div style="text-align:center;color:#475569;font-size:12px;">'
    'Wildfire Alert System — India &nbsp;|&nbsp; '
    'OpenWeatherMap + NASA FIRMS + XGBoost &nbsp;|&nbsp; '
    + datetime.now().strftime('%Y-%m-%d %H:%M') +
    '</div>',
    unsafe_allow_html=True
)