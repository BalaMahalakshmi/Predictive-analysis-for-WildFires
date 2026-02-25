import joblib
import pandas as pd
import logging
from datetime import datetime
 
from config import MODEL_PATH, SCALER_PATH, FEATURE_COLS, RISK_LEVELS
from weather_api import get_live_weather
from fwi_calcii import FWICalculator
 
logger = logging.getLogger(__name__)
 
# ── Load model once at startup ─────────────────────────────────────────
try:
    MODEL  = joblib.load(MODEL_PATH)
    SCALER = joblib.load(SCALER_PATH)
    logger.info('Model and scaler loaded successfully.')
except FileNotFoundError as e:
    raise SystemExit(f'Cannot find model file: {e}. Run Step 0 first!')
 
 
def get_risk_level(probability: float) -> dict:
    """Map probability to risk level metadata."""
    for level, (lo, hi) in RISK_LEVELS.items():
        if lo <= probability < hi:
            emoji_map = { 'LOW':'green', 'MEDIUM':'yellow', 'HIGH':'orange', 'CRITICAL':'red' }
            icon_map  = { 'LOW':'OK', 'MEDIUM':'CAUTION', 'HIGH':'WARNING', 'CRITICAL':'EMERGENCY' }
            return {
                'level'   : level,
                'color'   : emoji_map[level],
                'status'  : icon_map[level],
                'should_alert': level in ['HIGH', 'CRITICAL']
            }
    return { 'level':'UNKNOWN', 'color':'gray', 'status':'N/A', 'should_alert':False }
 
 
def predict_for_location(lat: float, lon: float, name: str) -> dict | None:
    """
    Full pipeline for one location:
    weather fetch --> FWI calculation --> scale --> model --> risk
    """
    # 1. Live weather
    weather = get_live_weather(lat, lon)
    if weather is None:
        logger.warning(f'Skipping {name} — weather fetch failed.')
        return None
 
    # 2. FWI indices
    month = datetime.now().month
    calc  = FWICalculator()
    fwi   = calc.calculate(
        temp=weather['Temperature'],
        rh=weather['RH'],
        ws=weather['Ws'],
        rain=weather['Rain'],
        month=month
    )
 
    # 3. Combine into model features
    features = {
        'Temperature': weather['Temperature'],
        'RH'         : weather['RH'],
        'Ws'         : weather['Ws'],
        'Rain'       : weather['Rain'],
        **fwi
    }
    input_df  = pd.DataFrame([features])[FEATURE_COLS]
    scaled    = SCALER.transform(input_df)
 
    # 4. Predict
    probability = float(MODEL.predict_proba(scaled)[0][1])
    prediction  = int(MODEL.predict(scaled)[0])
    risk        = get_risk_level(probability)
 
    # 5. Return full result
    return {
        'location'   : name,
        'lat'        : lat,
        'lon'        : lon,
        'timestamp'  : datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'weather'    : weather,
        'fwi'        : fwi,
        'probability': round(probability, 4),
        'prediction' : prediction,
        'risk'       : risk,
        'maps_url'   : f'https://maps.google.com/?q={lat},{lon}'
    }
 
 
# ── Quick test ────────────────────────────────────────────────────────
if __name__ == '__main__':
    result = predict_for_location(lat=36.75, lon=5.06, name='Bejaia Region')
    if result:
        print(f'Location  : {result["location"]}')
        print(f'Risk Level: {result["risk"]["level"]}')
        print(f'Fire Prob : {result["probability"]*100:.1f}%')
        print(f'Prediction: {"FIRE" if result["prediction"]==1 else "NO FIRE"}')
