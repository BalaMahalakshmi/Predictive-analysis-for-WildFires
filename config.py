import os
from dotenv import load_dotenv
 
# Load .env file
load_dotenv()
 
# ── API Keys ──────────────────────────────────────────────────────────
OWM_API_KEY       = os.getenv('OWM_API_KEY')
TWILIO_SID        = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_TOKEN      = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_FROM       = os.getenv('TWILIO_FROM_NUMBER')
# TELEGRAM_TOKEN    = os.getenv('TELEGRAM_BOT_TOKEN')
# TELEGRAM_CHAT_ID  = os.getenv('TELEGRAM_CHAT_ID')
GMAIL_ADDRESS     = os.getenv('GMAIL_ADDRESS')
GMAIL_PASSWORD    = os.getenv('GMAIL_APP_PASSWORD')
ALERT_RECEIVERS   = os.getenv('ALERT_RECEIVERS', '').split(',')
NASA_KEY          = os.getenv('NASA_FIRMS_KEY')
 
# ── Model paths ────────────────────────────────────────────────────────
MODEL_PATH  = 'models/wildfire_model.pkl'
SCALER_PATH = 'models/wildfire_scaler.pkl'
 
# ── Feature columns (must match your training data exactly) ───────────
FEATURE_COLS = ['Temperature', 'RH', 'Ws', 'Rain', 'FFMC', 'DMC', 'DC', 'ISI', 'BUI', 'FWI']
 
# ── Risk thresholds ────────────────────────────────────────────────────
RISK_LEVELS = {
    'LOW'     : (0.00, 0.25),
    'MEDIUM'  : (0.25, 0.50),
    'HIGH'    : (0.50, 0.75),
    'CRITICAL': (0.75, 1.01),
}
 
# ── Monitored locations ────────────────────────────────────────────────
# Add as many locations as you want to monitor simultaneously
LOCATIONS = [
    {'name': 'Bejaia Region',   'lat': 36.75, 'lon': 5.06},
    {'name': 'Sidi Bel Abbes',  'lat': 35.19, 'lon': -0.63},
    {'name': 'Tizi Ouzou',      'lat': 36.71, 'lon': 4.04},
]
 
# ── Emergency contacts (phone numbers for SMS) ────────────────────────
EMERGENCY_CONTACTS = {
    'Fire Station Control' : os.getenv('FIRE_STATION_NUMBER', '+213XXXXXXXXX'),
    'Police Emergency'     : os.getenv('POLICE_NUMBER',       '+213XXXXXXXXX'),
    'Forest Department'    : os.getenv('FOREST_DEPT_NUMBER',  '+213XXXXXXXXX'),
}
 
# ── Scheduler ─────────────────────────────────────────────────────────
CHECK_INTERVAL_MINUTES = 15   # How often to run predictions
 
# ── Alert cooldown ─────────────────────────────────────────────────────
# Don't spam the same alert for same location within this many minutes
ALERT_COOLDOWN_MINUTES = 60
 
# ── Log file ──────────────────────────────────────────────────────────
ALERT_LOG_PATH = 'logs/alerts.csv'
