import requests
import io
import logging
from datetime import datetime
 
import pandas as pd
 
from config import NASA_KEY
 
logger = logging.getLogger(__name__)
 
FIRMS_URL = 'https://firms.modaps.eosdis.nasa.gov/api/area/csv'
 
 
def get_satellite_hotspots(lat: float, lon: float, radius_deg: float = 0.5) -> pd.DataFrame | None:
    """
    Query NASA FIRMS for active fire hotspots within radius of location.
    radius_deg: degrees of lat/lon to search (0.5 deg ~ 55 km)
    Returns DataFrame with hotspot details or None if no fires / error.
    """
    if not NASA_KEY:
        logger.warning('NASA_FIRMS_KEY not configured.')
        return None
 
    # Bounding box: lon_min,lat_min,lon_max,lat_max
    area = f'{lon-radius_deg},{lat-radius_deg},{lon+radius_deg},{lat+radius_deg}'
 
    params = {
        'key'      : NASA_KEY,
        'source'   : 'VIIRS_SNPP_NRT',  # Near Real-Time satellite
        'area'     : area,
        'day_range': 1,                 # Last 24 hours
    }
 
    try:
        response = requests.get(FIRMS_URL, params=params, timeout=15)
        response.raise_for_status()
 
        content = response.text.strip()
        if not content or content.startswith('No data'):
            logger.info(f'No satellite fire detections near ({lat}, {lon})')
            return None
 
        df = pd.read_csv(io.StringIO(content))
        logger.warning(f'{len(df)} active fire hotspots detected near ({lat}, {lon})!')
        return df
 
    except Exception as e:
        logger.error(f'NASA FIRMS API error: {e}')
        return None
 
 
def check_satellites_for_locations(locations: list) -> dict:
    """Check all monitored locations for satellite-detected fires."""
    results = {}
    for loc in locations:
        hotspots = get_satellite_hotspots(loc['lat'], loc['lon'])
        results[loc['name']] = {
            'has_fire'     : hotspots is not None,
            'hotspot_count': len(hotspots) if hotspots is not None else 0,
            'hotspots'     : hotspots,
        }
    return results
 
 
# ── Quick test ────────────────────────────────────────────────────────
if __name__ == '__main__':
    spots = get_satellite_hotspots(lat=36.75, lon=5.06)
    if spots is not None:
        print(f'{len(spots)} active fire hotspots detected by satellite!')
        print(spots[['latitude','longitude','bright_ti4','confidence']].head())
    else:
        print('No active fire hotspots in this area right now.')
