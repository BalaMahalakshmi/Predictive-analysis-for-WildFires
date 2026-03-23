import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ───────────────────────────────────────────────────────────────
OWM_API_KEY     = os.getenv('OWM_API_KEY', '')
FAST2SMS_API_KEY= os.getenv('FAST2SMS_API_KEY', '')
TWILIO_SID      = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_TOKEN    = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_FROM     = os.getenv('TWILIO_FROM_NUMBER', '')
GMAIL_ADDRESS   = os.getenv('GMAIL_ADDRESS', '')
GMAIL_PASSWORD  = os.getenv('GMAIL_APP_PASSWORD', '')
ALERT_RECEIVERS = os.getenv('ALERT_RECEIVERS', '').split(',')
NASA_KEY        = os.getenv('NASA_FIRMS_KEY', '')

# ── Model paths ────────────────────────────────────────────────────────────
MODEL_PATH  = 'models/wildfire_model.pkl'
SCALER_PATH = 'models/wildfire_scaler.pkl'

FEATURE_COLS = ['Temperature','RH','Ws','Rain','FFMC','DMC','DC','ISI','BUI','FWI']

# ── Risk thresholds (Tamil Nadu Summer Calibrated) ─────────────────────────
# NOTE: The ML model was trained on Algerian forest data where normal summer
# temps are 15–28°C and humidity 40–70%. Tamil Nadu summer is much hotter
# (30–42°C) and drier (20–40% humidity), so the model naturally scores TN
# weather higher. These calibrated thresholds prevent false HIGH/CRITICAL
# alerts for normal Tamil Nadu summer conditions.
#
# PRESET OPTIONS (change ACTIVE_PRESET to switch):
#   'default'       → Original Algeria thresholds (causes false alarms in TN)
#   'tn_summer'     → Tamil Nadu Summer (RECOMMENDED for March–June)
#   'tn_sensitive'  → High Sensitivity (use during peak drought)
#   'tn_forest'     → Forest Reserve (ultra-sensitive for sanctuaries)

ACTIVE_PRESET = 'tn_summer'   # ← Change this to switch preset

THRESHOLD_PRESETS = {
    'default': {
        'LOW'     : (0.00, 0.25),
        'MEDIUM'  : (0.25, 0.50),
        'HIGH'    : (0.50, 0.75),
        'CRITICAL': (0.75, 1.01),
    },
    'tn_summer': {
        # Tamil Nadu Summer Calibrated — RECOMMENDED
        # LOW:      0–55%  (normal TN summer weather, no alert)
        # MEDIUM:  55–75%  (watch closely, no alert yet)
        # HIGH:    75–88%  (genuinely dangerous, send alert)
        # CRITICAL:88–100% (extreme fire risk, emergency alert)
        'LOW'     : (0.00, 0.55),
        'MEDIUM'  : (0.55, 0.75),
        'HIGH'    : (0.75, 0.88),
        'CRITICAL': (0.88, 1.01),
    },
    'tn_sensitive': {
        # Slightly more sensitive — use in peak April–May drought
        'LOW'     : (0.00, 0.45),
        'MEDIUM'  : (0.45, 0.65),
        'HIGH'    : (0.65, 0.82),
        'CRITICAL': (0.82, 1.01),
    },
    'tn_forest': {
        # Most sensitive — for tiger reserves and national parks only
        'LOW'     : (0.00, 0.40),
        'MEDIUM'  : (0.40, 0.60),
        'HIGH'    : (0.60, 0.78),
        'CRITICAL': (0.78, 1.01),
    },
}

# Active thresholds applied by the system
RISK_LEVELS = THRESHOLD_PRESETS[ACTIVE_PRESET]

# ── ALL Tamil Nadu monitoring zones (40 key locations) ────────────────────
LOCATIONS = [
    # Major Forest & Wildlife Sanctuaries
    {'name': 'Sathiyamangalam Forest',      'lat': 11.5167, 'lon': 77.2333},
    {'name': 'Mudumalai National Park',     'lat': 11.5671, 'lon': 76.6370},
    {'name': 'Anamalai Tiger Reserve',      'lat': 10.3167, 'lon': 77.0167},
    {'name': 'Nilgiris Biosphere Reserve',  'lat': 11.3500, 'lon': 76.7500},
    {'name': 'Kalakad Mundanthurai Reserve','lat':  8.4333, 'lon': 77.3500},
    {'name': 'Meghamalai Wildlife Sanctuary','lat':9.6333,  'lon': 77.3667},
    {'name': 'Grizzled Squirrel Sanctuary', 'lat':  9.4833, 'lon': 77.5167},
    {'name': 'Vellore Forest Division',     'lat': 12.9165, 'lon': 79.1325},
    {'name': 'Hosur Forest Division',       'lat': 12.7409, 'lon': 77.8253},
    {'name': 'Dharmapuri Forest',           'lat': 12.1211, 'lon': 78.1582},
    # Hill Stations
    {'name': 'Ooty (Udhagamandalam)',       'lat': 11.4102, 'lon': 76.6950},
    {'name': 'Kodaikanal',                  'lat':  10.2381,'lon': 77.4892},
    {'name': 'Yercaud',                     'lat': 11.7750, 'lon': 78.2083},
    {'name': 'Kolli Hills',                 'lat': 11.3167, 'lon': 78.3667},
    {'name': 'Sirumalai Hills',             'lat':  10.1833,'lon': 77.9167},
    {'name': 'Javvadhu Hills',              'lat': 12.4167, 'lon': 78.8000},
    {'name': 'Shervaroy Hills',             'lat': 11.7667, 'lon': 78.1833},
    # Districts & Cities
    {'name': 'Coimbatore',                  'lat': 11.0168, 'lon': 76.9558},
    {'name': 'Salem',                       'lat': 11.6643, 'lon': 78.1460},
    {'name': 'Erode',                       'lat': 11.3410, 'lon': 77.7172},
    {'name': 'Tiruppur',                    'lat': 11.1085, 'lon': 77.3411},
    {'name': 'Namakkal',                    'lat': 11.2167, 'lon': 78.1667},
    {'name': 'Krishnagiri',                 'lat': 12.5186, 'lon': 78.2137},
    {'name': 'Tirunelveli',                 'lat':  8.7139, 'lon': 77.7567},
    {'name': 'Madurai',                     'lat':  9.9252, 'lon': 78.1198},
    {'name': 'Trichy',                      'lat': 10.7905, 'lon': 78.7047},
    {'name': 'Thanjavur',                   'lat': 10.7870, 'lon': 79.1378},
    {'name': 'Dindigul',                    'lat': 10.3624, 'lon': 77.9695},
    {'name': 'Theni',                       'lat':  10.0104,'lon': 77.4767},
    {'name': 'Virudhunagar',                'lat':  9.5800, 'lon': 77.9624},
    {'name': 'Tenkasi',                     'lat':  8.9590, 'lon': 77.3152},
    {'name': 'Nagercoil',                   'lat':  8.1833, 'lon': 77.4167},
    {'name': 'Vellore',                     'lat': 12.9165, 'lon': 79.1325},
    {'name': 'Tiruvannamalai',              'lat': 12.2253, 'lon': 79.0747},
    {'name': 'Villupuram',                  'lat': 11.9392, 'lon': 79.4933},
    {'name': 'Cuddalore',                   'lat': 11.7480, 'lon': 79.7714},
    {'name': 'Perambalur',                  'lat': 11.2333, 'lon': 78.8833},
    {'name': 'Ariyalur',                    'lat': 11.1333, 'lon': 79.0833},
    {'name': 'Pudukkottai',                 'lat': 10.3833, 'lon': 78.8167},
    {'name': 'Ramanathapuram',              'lat':  9.3667, 'lon': 78.8333},
]

EMERGENCY_CONTACTS = {
    'Fire Station': os.getenv('FIRE_STATION_NUMBER', ''),
    'Police'      : os.getenv('POLICE_NUMBER', ''),
}

CHECK_INTERVAL_MINUTES = 15
ALERT_COOLDOWN_MINUTES = 60
ALERT_LOG_PATH = 'logs/alerts.csv'