import smtplib
import logging
import csv
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import (
    TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, EMERGENCY_CONTACTS,
    GMAIL_ADDRESS, GMAIL_PASSWORD, ALERT_RECEIVERS,
    ALERT_LOG_PATH
)

logger = logging.getLogger(__name__)


def _build_alert_message(result):
    """Build alert message string — Python 3.10 compatible."""
    separator = '=' * 40
    level     = result['risk']['level']
    location  = result['location']
    timestamp = result['timestamp']
    prob      = result['probability'] * 100
    status    = result['risk']['status']
    temp      = result['weather']['Temperature']
    rh        = result['weather']['RH']
    ws        = result['weather']['Ws']
    fwi_val   = result['fwi']['FWI']
    maps      = result['maps_url']
    lat       = result['lat']
    lon       = result['lon']

    return (
        'WILDFIRE ALERT - ' + level + ' RISK\n' +
        separator + '\n' +
        'Location  : ' + location + '\n' +
        'GPS       : ' + str(lat) + ', ' + str(lon) + '\n' +
        'Time      : ' + timestamp + '\n' +
        'Fire Prob : ' + str(round(prob, 1)) + '%\n' +
        'Status    : ' + status + '\n' +
        'Temp      : ' + str(temp) + 'C\n' +
        'Humidity  : ' + str(rh) + '%\n' +
        'Wind      : ' + str(ws) + ' km/h\n' +
        'FWI       : ' + str(fwi_val) + '\n' +
        'Map       : ' + maps + '\n' +
        'ACTION    : DEPLOY FIRE WATCH TEAMS IMMEDIATELY'
    )


def log_prediction(result, channels_sent=None):
    """
    ★ CORE FUNCTION ★
    Saves EVERY prediction to CSV automatically —
    LOW, MEDIUM, HIGH, CRITICAL — all of them, always.
    Called after every single prediction run.
    """
    if channels_sent is None:
        channels_sent = []

    # Create logs folder if it doesn't exist
    os.makedirs('logs', exist_ok=True)

    # Check if file exists AND has content
    file_exists = (
        os.path.exists(ALERT_LOG_PATH) and
        os.path.getsize(ALERT_LOG_PATH) > 0
    )

    with open(ALERT_LOG_PATH, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Write header row only once (first time)
        if not file_exists:
            writer.writerow([
                'timestamp',
                'location',
                'lat',
                'lon',
                'temperature_c',
                'humidity_pct',
                'wind_kmh',
                'rain_mm',
                'ffmc',
                'dmc',
                'dc',
                'isi',
                'bui',
                'fwi',
                'fire_probability_pct',
                'prediction',
                'risk_level',
                'alert_sent',
                'channels'
            ])

        # Write data row for EVERY prediction
        writer.writerow([
            result['timestamp'],
            result['location'],
            result['lat'],
            result['lon'],
            result['weather']['Temperature'],
            result['weather']['RH'],
            result['weather']['Ws'],
            result['weather']['Rain'],
            result['fwi']['FFMC'],
            result['fwi']['DMC'],
            result['fwi']['DC'],
            result['fwi']['ISI'],
            result['fwi']['BUI'],
            result['fwi']['FWI'],
            round(result['probability'] * 100, 2),
            'FIRE' if result['prediction'] == 1 else 'NO FIRE',
            result['risk']['level'],
            'YES' if channels_sent else 'NO',
            '|'.join(channels_sent) if channels_sent else 'none'
        ])

    logger.info(
        'Saved to CSV --> ' +
        result['location'] + ' | ' +
        result['risk']['level'] + ' | ' +
        str(round(result['probability'] * 100, 1)) + '%'
    )


def send_sms(result):
    """Send SMS via Twilio — only for HIGH / CRITICAL."""
    if not TWILIO_SID or not TWILIO_TOKEN:
        logger.warning('Twilio not configured — skipping SMS.')
        return {}

    try:
        from twilio.rest import Client
        client = Client(TWILIO_SID, TWILIO_TOKEN)

        level    = result['risk']['level']
        location = result['location']
        prob     = result['probability'] * 100
        maps_url = result['maps_url']

        message_body = (
            '[WILDFIRE ' + level + '] ' +
            location + ' | ' +
            'Fire prob: ' + str(round(prob, 0)) + '% | ' +
            'Map: ' + maps_url
        )

        statuses = {}
        for name, number in EMERGENCY_CONTACTS.items():
            try:
                client.messages.create(
                    body=message_body,
                    from_=TWILIO_FROM,
                    to=number
                )
                statuses[name] = 'sent'
                logger.info('SMS sent to ' + name)
            except Exception as e:
                statuses[name] = 'failed'
                logger.error('SMS to ' + name + ' failed: ' + str(e))
        return statuses

    except ImportError:
        logger.warning('Twilio not installed — skipping SMS.')
        return {}


def send_email(result):
    """Send email alert via Gmail — only for HIGH / CRITICAL."""
    if not GMAIL_ADDRESS or not GMAIL_PASSWORD:
        logger.warning('Gmail not configured — skipping email.')
        return False

    level    = result['risk']['level']
    location = result['location']
    subject  = '[WILDFIRE ALERT] ' + level + ' RISK - ' + location
    body     = _build_alert_message(result)

    msg            = MIMEMultipart()
    msg['Subject'] = subject
    msg['From']    = GMAIL_ADDRESS
    msg['To']      = ', '.join(ALERT_RECEIVERS)
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
            smtp.sendmail(GMAIL_ADDRESS, ALERT_RECEIVERS, msg.as_string())
        logger.info('Email alert sent!')
        return True
    except Exception as e:
        logger.error('Email failed: ' + str(e))
        return False


def dispatch_alerts(result):
    """
    Master dispatcher — called after EVERY prediction.

    Flow:
    ┌─────────────────────────────────────────────┐
    │  Every prediction (ALL risk levels)          │
    │       │                                      │
    │       ├──► log_prediction() ──► CSV saved   │
    │       │                                      │
    │       └──► IF HIGH or CRITICAL:              │
    │               ├──► send_email()              │
    │               └──► send_sms()                │
    └─────────────────────────────────────────────┘
    """
    sent = []

    # ── Send alerts only for HIGH / CRITICAL ──────────────────────────────
    if result['risk']['should_alert']:
        logger.warning(
            'EMERGENCY: ' + result['location'] +
            ' risk level is ' + result['risk']['level']
        )
        if send_email(result):
            sent.append('email')

        sms_status = send_sms(result)
        if any(v == 'sent' for v in sms_status.values()):
            sent.append('sms')
    else:
        logger.info(
            result['location'] + ' | ' +
            result['risk']['level'] + ' | Monitoring only.'
        )

    # ── ALWAYS save to CSV regardless of risk level ───────────────────────
    log_prediction(result, sent)