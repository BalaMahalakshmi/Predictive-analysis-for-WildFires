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

CSV_COLUMNS = [
    "timestamp", "location", "lat", "lon",
    "temperature_c", "humidity_pct", "wind_kmh", "rain_mm",
    "ffmc", "dmc", "dc", "isi", "bui", "fwi",
    "fire_probability_pct", "prediction", "risk_level",
    "alert_sent", "channels"
]


def _build_alert_message(result):
    sep   = "=" * 40
    level = result["risk"]["level"]
    prob  = round(result["probability"] * 100, 1)
    w     = result["weather"]
    f     = result["fwi"]
    return (
        "WILDFIRE ALERT - " + level + " RISK\n" + sep + "\n"
        "Location  : " + result["location"] + "\n"
        "GPS       : " + str(result["lat"]) + ", " + str(result["lon"]) + "\n"
        "Time      : " + result["timestamp"] + "\n"
        "Fire Prob : " + str(prob) + "%\n"
        "Temp      : " + str(w["Temperature"]) + " C\n"
        "Humidity  : " + str(w["RH"]) + "%\n"
        "Wind      : " + str(w["Ws"]) + " km/h\n"
        "Rain      : " + str(w["Rain"]) + " mm\n"
        "FWI       : " + str(f["FWI"]) + "\n"
        "Map       : " + result["maps_url"] + "\n"
        "ACTION    : DEPLOY FIRE WATCH TEAMS IMMEDIATELY"
    )


def log_prediction(result, channels_sent=None):
    """
    Saves EVERY prediction to CSV automatically.
    Uses csv.QUOTE_ALL so location names with commas NEVER break the file.
    """
    if channels_sent is None:
        channels_sent = []

    log_dir = os.path.dirname(ALERT_LOG_PATH)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    write_header = (
        not os.path.exists(ALERT_LOG_PATH) or
        os.path.getsize(ALERT_LOG_PATH) == 0
    )

    with open(ALERT_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)  # ← FIXES the comma problem
        if write_header:
            writer.writerow(CSV_COLUMNS)
        w   = result["weather"]
        fwi = result["fwi"]
        writer.writerow([
            result["timestamp"],
            result["location"],
            result["lat"],
            result["lon"],
            w["Temperature"],
            w["RH"],
            w["Ws"],
            w["Rain"],
            fwi["FFMC"],
            fwi["DMC"],
            fwi["DC"],
            fwi["ISI"],
            fwi["BUI"],
            fwi["FWI"],
            round(result["probability"] * 100, 2),
            "FIRE" if result["prediction"] == 1 else "NO FIRE",
            result["risk"]["level"],
            "YES" if channels_sent else "NO",
            "|".join(channels_sent) if channels_sent else "none",
        ])

    logger.info(
        "Saved → " + result["location"] +
        " | " + result["risk"]["level"] +
        " | " + str(round(result["probability"] * 100, 1)) + "%"
    )


def send_sms(result):
    if not TWILIO_SID or not TWILIO_TOKEN:
        logger.warning("Twilio not configured.")
        return {}
    try:
        from twilio.rest import Client
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        body   = (
            "[WILDFIRE " + result["risk"]["level"] + "] " +
            result["location"] + " | " +
            str(round(result["probability"] * 100, 0)) + "% fire risk | " +
            result["maps_url"]
        )
        statuses = {}
        for name, number in EMERGENCY_CONTACTS.items():
            try:
                client.messages.create(body=body, from_=TWILIO_FROM, to=number)
                statuses[name] = "sent"
            except Exception as e:
                statuses[name] = "failed"
                logger.error("SMS failed: " + str(e))
        return statuses
    except ImportError:
        return {}


def send_email(result):
    if not GMAIL_ADDRESS or not GMAIL_PASSWORD:
        logger.warning("Gmail not configured.")
        return False
    try:
        msg            = MIMEMultipart()
        msg["Subject"] = "[WILDFIRE] " + result["risk"]["level"] + " — " + result["location"]
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = ", ".join(ALERT_RECEIVERS)
        msg.attach(MIMEText(_build_alert_message(result), "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
            smtp.sendmail(GMAIL_ADDRESS, ALERT_RECEIVERS, msg.as_string())
        return True
    except Exception as e:
        logger.error("Email failed: " + str(e))
        return False


def dispatch_alerts(result):
    """Called after EVERY prediction — saves CSV + sends alert if HIGH/CRITICAL."""
    sent = []
    if result["risk"]["should_alert"]:
        logger.warning("ALERT: " + result["location"] + " → " + result["risk"]["level"])
        if send_email(result):
            sent.append("email")
        sms = send_sms(result)
        if any(v == "sent" for v in sms.values()):
            sent.append("sms")
    else:
        logger.info(result["location"] + " → " + result["risk"]["level"])

    log_prediction(result, sent)