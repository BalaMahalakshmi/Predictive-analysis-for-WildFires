import smtplib
import requests
import logging
import csv
import os
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import (
    TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, EMERGENCY_CONTACTS,
    GMAIL_ADDRESS, GMAIL_PASSWORD, ALERT_RECEIVERS,
    ALERT_LOG_PATH
)

logger = logging.getLogger(__name__)


def _build_alert_message(result):
    """Build a clear, informative alert message from prediction result."""
    r         = result
    separator = '=' * 40
    level     = r['risk']['level']
    location  = r['location']
    timestamp = r['timestamp']
    prob      = r['probability'] * 100
    status    = r['risk']['status']
    temp      = r['weather']['Temperature']
    rh        = r['weather']['RH']
    ws        = r['weather']['Ws']
    fwi_val   = r['fwi']['FWI']
    maps      = r['maps_url']
    lat       = r['lat']
    lon       = r['lon']

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


def send_sms(result):
    """Send SMS to all emergency contacts via Twilio."""
    if not TWILIO_SID or not TWILIO_TOKEN:
        logger.warning('Twilio not configured in .env — skipping SMS.')
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
                logger.info('SMS sent to ' + name + ' (' + number + ')')
            except Exception as e:
                statuses[name] = 'failed: ' + str(e)
                logger.error('SMS to ' + name + ' failed: ' + str(e))
        return statuses

    except ImportError:
        logger.warning('Twilio package not installed — skipping SMS.')
        return {}


def send_email(result):
    """Send email alert via Gmail SMTP."""
    if not GMAIL_ADDRESS or not GMAIL_PASSWORD:
        logger.warning('Gmail not configured in .env — skipping email.')
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
        logger.info('Email sent to ' + str(ALERT_RECEIVERS))
        return True
    except Exception as e:
        logger.error('Email failed: ' + str(e))
        return False


def log_alert(result, channels_sent):
    """Append alert record to CSV log file."""
    os.makedirs('logs', exist_ok=True)
    file_exists = os.path.exists(ALERT_LOG_PATH)

    with open(ALERT_LOG_PATH, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                'timestamp', 'location', 'lat', 'lon',
                'probability', 'risk_level', 'channels'
            ])
        writer.writerow([
            result['timestamp'],
            result['location'],
            result['lat'],
            result['lon'],
            result['probability'],
            result['risk']['level'],
            '|'.join(channels_sent)
        ])


def dispatch_alerts(result):
    """Master alert dispatcher — sends all configured alerts."""
    if not result['risk']['should_alert']:
        logger.info(
            result['location'] + ': ' +
            result['risk']['level'] + ' — no alert needed.'
        )
        return

    logger.warning(
        'ALERT: ' + result['location'] +
        ' is ' + result['risk']['level'] + '!'
    )
    sent = []

    # Email alert
    if send_email(result):
        sent.append('email')

    # SMS alert
    sms_status = send_sms(result)
    if any(v == 'sent' for v in sms_status.values()):
        sent.append('sms')

    # Log it
    log_alert(result, sent)
    logger.info('Alerts sent via: ' + str(sent))