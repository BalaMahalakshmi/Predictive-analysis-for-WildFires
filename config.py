import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ── API Keys ───────────────────────────────────────────────────────────────

# OpenWeatherMap — https://openweathermap.org/api (free)
OWM_API_KEY = os.getenv('OWM_API_KEY', '')

# Fast2SMS — https://fast2sms.com (FREE Indian SMS API — best for India!)
# Sign up free → Dashboard → Dev API → copy key → add to .env
FAST2SMS_API_KEY = os.getenv('FAST2SMS_API_KEY', '')

# Twilio SMS — https://www.twilio.com (optional, paid)
TWILIO_SID   = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_FROM  = os.getenv('TWILIO_FROM_NUMBER', '')

# Gmail alerts — for email alerts + fallback
GMAIL_ADDRESS   = os.getenv('GMAIL_ADDRESS', '')
GMAIL_PASSWORD  = os.getenv('GMAIL_APP_PASSWORD', '')
ALERT_RECEIVERS = os.getenv('ALERT_RECEIVERS', '').split(',')

# NASA FIRMS satellite — https://firms.modaps.eosdis.nasa.gov/api/ (free)
NASA_KEY = os.getenv('NASA_FIRMS_KEY', '')

# ── Model paths ────────────────────────────────────────────────────────────
MODEL_PATH  = 'models/wildfire_model.pkl'
SCALER_PATH = 'models/wildfire_scaler.pkl'

# ── Feature columns (must match your training data exactly) ────────────────
FEATURE_COLS = [
    'Temperature', 'RH', 'Ws', 'Rain',
    'FFMC', 'DMC', 'DC', 'ISI', 'BUI', 'FWI'
]

# ── Risk thresholds ────────────────────────────────────────────────────────
RISK_LEVELS = {
    'LOW'     : (0.00, 0.25),
    'MEDIUM'  : (0.25, 0.50),
    'HIGH'    : (0.50, 0.75),
    'CRITICAL': (0.75, 1.01),
}

# ── Monitored locations ────────────────────────────────────────────────────
LOCATIONS = [
    {'name': 'Bejaia Region',  'lat': 36.75, 'lon': 5.06},
    {'name': 'Sidi Bel Abbes', 'lat': 35.19, 'lon': -0.63},
    {'name': 'Tizi Ouzou',     'lat': 36.71, 'lon': 4.04},
]

# ── Emergency contacts for SMS ─────────────────────────────────────────────
EMERGENCY_CONTACTS = {
    'Fire Station': os.getenv('FIRE_STATION_NUMBER', '+213XXXXXXXXX'),
    'Police'      : os.getenv('POLICE_NUMBER',       '+213XXXXXXXXX'),
}

# ── Scheduler ──────────────────────────────────────────────────────────────
CHECK_INTERVAL_MINUTES = 15
ALERT_COOLDOWN_MINUTES = 60

# ── Log file ───────────────────────────────────────────────────────────────
ALERT_LOG_PATH = 'logs/alerts.csv'