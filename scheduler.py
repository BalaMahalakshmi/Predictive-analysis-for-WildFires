import schedule
import time
import logging
from datetime import datetime, timedelta
 
from config import LOCATIONS, CHECK_INTERVAL_MINUTES, ALERT_COOLDOWN_MINUTES
from predictor import predict_for_location
from alert_engine import dispatch_alerts
from satellite import check_satellites_for_locations
 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/monitoring.log')
    ]
)
logger = logging.getLogger(__name__)
 
# Track last alert time per location to prevent spam
_last_alert_time: dict[str, datetime] = {}
 
 
def _can_alert(location_name: str) -> bool:
    """Return True if cooldown period has passed for this location."""
    last = _last_alert_time.get(location_name)
    if last is None:
        return True
    return datetime.now() - last > timedelta(minutes=ALERT_COOLDOWN_MINUTES)
 
 
def run_monitoring_cycle():
    """Single monitoring pass across all configured locations."""
    logger.info(f'--- Monitoring cycle started: {datetime.now().strftime("%H:%M:%S")} ---')
 
    # 1. ML prediction for each location
    for loc in LOCATIONS:
        result = predict_for_location(
            lat=loc['lat'], lon=loc['lon'], name=loc['name']
        )
 
        if result is None:
            continue
 
        level = result['risk']['level']
        prob  = result['probability'] * 100
        logger.info(f"{loc['name']:25} | {level:8} | {prob:.1f}%")
 
        # Send alert only if HIGH/CRITICAL and cooldown passed
        if result['risk']['should_alert'] and _can_alert(loc['name']):
            dispatch_alerts(result)
            _last_alert_time[loc['name']] = datetime.now()
 
    # 2. Satellite check
    satellite_results = check_satellites_for_locations(LOCATIONS)
    for name, sat in satellite_results.items():
        if sat['has_fire']:
            logger.warning(f'SATELLITE: {sat["hotspot_count"]} active fire(s) near {name}!')
 
    logger.info('--- Cycle complete ---')
 
 
def start_scheduler():
    """Start the continuous monitoring scheduler."""
    logger.info(f'Wildfire monitoring system started.')
    logger.info(f'Checking {len(LOCATIONS)} locations every {CHECK_INTERVAL_MINUTES} minutes.')
    logger.info(f'Locations: {[l["name"] for l in LOCATIONS]}')
 
    # Run immediately on startup
    run_monitoring_cycle()
 
    # Then schedule every N minutes
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(run_monitoring_cycle)
 
    while True:
        schedule.run_pending()
        time.sleep(30)  # Check every 30 seconds if any jobs pending
 
 
if __name__ == '__main__':
    start_scheduler()
