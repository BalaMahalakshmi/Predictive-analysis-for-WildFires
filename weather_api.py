import requests
import logging
from config import OWM_API_KEY
 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
 
def get_live_weather(lat: float, lon: float) -> dict | None:
    """
    Fetch live weather for a GPS coordinate.
    Returns a dict with Temperature, RH, Ws, Rain
    or None if the API call fails.
    """
    if not OWM_API_KEY:
        raise ValueError('OWM_API_KEY is missing from your .env file!')
 
    url = 'https://api.openweathermap.org/data/2.5/weather'
    params = {
        'lat'  : lat,
        'lon'  : lon,
        'appid': OWM_API_KEY,
        'units': 'metric'   # Celsius, km/h
    }
 
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
 
        weather = {
            'Temperature': round(data['main']['temp'],       2),
            'RH'         : round(data['main']['humidity'],   2),
            # Wind: API gives m/s, model needs km/h
            'Ws'         : round(data['wind']['speed'] * 3.6, 2),
            # Rain: API gives mm/last 1 hour (default 0 if no rain)
            'Rain'       : round(data.get('rain', {}).get('1h', 0.0), 2),
            'description': data['weather'][0]['description'].title(),
            'city_name'  : data.get('name', 'Unknown'),
        }
        logger.info(f'Weather fetched: {weather}')
        return weather
 
    except requests.exceptions.ConnectionError:
        logger.error('No internet connection. Cannot fetch weather.')
        return None
    except requests.exceptions.Timeout:
        logger.error('OpenWeatherMap API timed out.')
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(f'HTTP error from weather API: {e}')
        return None
 
 
def get_weather_forecast_5day(lat: float, lon: float) -> list:
    """
    Fetch 5-day / 3-hour forecast (40 data points).
    Used by LSTM forecasting module.
    """
    url = 'https://api.openweathermap.org/data/2.5/forecast'
    params = { 'lat':lat, 'lon':lon, 'appid':OWM_API_KEY, 'units':'metric' }
 
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        forecasts = response.json()['list']
 
        return [{
            'datetime'   : f['dt_txt'],
            'Temperature': f['main']['temp'],
            'RH'         : f['main']['humidity'],
            'Ws'         : f['wind']['speed'] * 3.6,
            'Rain'       : f.get('rain', {}).get('3h', 0) / 3,
        } for f in forecasts]
 
    except Exception as e:
        logger.error(f'Forecast API error: {e}')
        return []
 
 
# ── Quick test ────────────────────────────────────────────────────────
if __name__ == '__main__':
    result = get_live_weather(lat=36.75, lon=5.06)
    if result:
        print('Live weather data:')
        for key, val in result.items():
            print(f'  {key:15}: {val}')
