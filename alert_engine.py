"""
alert_engine.py  —  Wildfire Alert Engine
Sends alerts via Gmail email (100% free, 100% reliable).
You receive alert emails on your phone via Gmail app.
"""
import smtplib, logging, csv, os, re, json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import GMAIL_ADDRESS, GMAIL_PASSWORD, ALERT_LOG_PATH

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
    "timestamp","location","lat","lon",
    "temperature_c","humidity_pct","wind_kmh","rain_mm",
    "ffmc","dmc","dc","isi","bui","fwi",
    "fire_probability_pct","prediction","risk_level","alert_sent","channels"
]

# File to save contacts entered in the app
CONTACTS_FILE = "contacts.json"


# ── Save / Load contacts ───────────────────────────────────────────────────
def save_contacts(contacts: dict):
    with open(CONTACTS_FILE, "w") as f:
        json.dump(contacts, f, indent=2)

def load_contacts() -> dict:
    if os.path.exists(CONTACTS_FILE):
        try:
            return json.load(open(CONTACTS_FILE))
        except Exception:
            pass
    return {}


# ── Alert message body ─────────────────────────────────────────────────────
def _alert_body(result):
    risk  = result["risk"]["level"]
    prob  = round(result["probability"] * 100, 1)
    w     = result["weather"]
    f     = result["fwi"]
    loc   = result["location"].split("|")[0].strip()
    maps  = result.get("maps_url", "")

    emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(risk, "🔥")

    lines = [
        emoji + " WILDFIRE " + risk + " RISK ALERT",
        "=" * 45,
        "",
        "📍 Location  : " + loc,
        "🕐 Time      : " + result["timestamp"],
        "🔥 Fire Risk : " + str(prob) + "% probability",
        "",
        "🌡️  LIVE WEATHER",
        "   Temperature : " + str(w["Temperature"]) + " °C",
        "   Humidity    : " + str(w["RH"]) + " %",
        "   Wind Speed  : " + str(w["Ws"]) + " km/h",
        "   Rainfall    : " + str(w["Rain"]) + " mm",
        "",
        "📊 FIRE WEATHER INDEX (FWI)",
        "   FFMC : " + str(f["FFMC"]) + "   (Fine Fuel Moisture)",
        "   DMC  : " + str(f["DMC"])  + "   (Duff Moisture)",
        "   DC   : " + str(f["DC"])   + "   (Drought Code)",
        "   ISI  : " + str(f["ISI"])  + "   (Initial Spread Index)",
        "   BUI  : " + str(f["BUI"])  + "   (Buildup Index)",
        "   FWI  : " + str(f["FWI"])  + "   (Fire Weather Index)",
        "",
        "=" * 45,
    ]

    if risk in ["HIGH", "CRITICAL"]:
        lines += [
            "⚠️  IMMEDIATE ACTION REQUIRED",
            "   • Alert fire station — Call 101",
            "   • Dispatch emergency teams",
            "   • Evacuate nearby areas",
            "   • Call emergency services — 112",
            "",
        ]
    else:
        lines += [
            "ℹ️  Monitor situation. No immediate action needed.",
            "",
        ]

    if maps:
        lines += ["🗺️  Location Map: " + maps, ""]

    lines += [
        "─" * 45,
        "Sent by: Real-Time Wildfire Detection System",
        "Tamil Nadu Forest & Wildlife Monitoring",
    ]
    return "\n".join(lines)


def _alert_subject(result):
    risk = result["risk"]["level"]
    loc  = result["location"].split("|")[0].strip()
    prob = round(result["probability"] * 100, 1)
    prefix = {"CRITICAL": "🔴 CRITICAL", "HIGH": "🟠 HIGH",
              "MEDIUM": "🟡 MEDIUM", "LOW": "🟢 LOW"}.get(risk, risk)
    return prefix + " WILDFIRE — " + loc + " (" + str(prob) + "%)"


# ── Core email sender ──────────────────────────────────────────────────────
def _get_gmail_creds():
    """
    Get Gmail credentials in this priority order:
    1. contacts.json (saved by the app UI — most reliable)
    2. .env file values
    """
    # Priority 1: contacts.json saved by the app
    try:
        contacts = load_contacts()
        j_email = contacts.get("sender_email", "").strip()
        j_pass  = contacts.get("sender_pass",  "").strip()
        if j_email and j_pass:
            return j_email, j_pass
    except Exception:
        pass
    # Priority 2: .env file
    env_email = GMAIL_ADDRESS.strip()
    env_pass  = GMAIL_PASSWORD.strip()
    if env_email and env_pass:
        return env_email, env_pass
    return "", ""


def _send_email(to_address: str, subject: str, body: str):
    """
    Send one email via Gmail SMTP.
    Reads credentials from app UI (session state) or .env file.
    Returns (True, "OK") or (False, "error message")
    """
    gmail_addr, gmail_pass = _get_gmail_creds()

    if not gmail_addr or not gmail_pass:
        return False, (
            "Gmail not set up yet!\n"
            "Go to Alert Contacts tab → enter your Gmail + App Password → "
            "click Test Gmail Connection first."
        )

    to_address = to_address.strip()
    if not to_address:
        return False, "Empty email address"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = gmail_addr
        msg["To"]      = to_address
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
            smtp.login(gmail_addr, gmail_pass)
            smtp.sendmail(gmail_addr, [to_address], msg.as_string())

        logger.info("Email sent → " + to_address)
        return True, "Email sent to " + to_address

    except smtplib.SMTPAuthenticationError:
        return False, (
            "Gmail login failed!\n"
            "You need a Gmail App Password (not your normal password).\n"
            "Steps: myaccount.google.com → Security → "
            "2-Step Verification ON → App Passwords → Generate"
        )
    except smtplib.SMTPRecipientsRefused:
        return False, "Invalid email address: " + to_address
    except smtplib.SMTPException as e:
        return False, "SMTP error: " + str(e)
    except OSError as e:
        return False, "Connection failed (check internet): " + str(e)
    except Exception as e:
        return False, "Unexpected error: " + str(e)


# ── Public API ─────────────────────────────────────────────────────────────
def send_alert_to_contact(result, email_address: str):
    """
    Send wildfire alert email to one contact.
    Returns (status_code, message)
      status_code: "sent" | "failed" | "invalid" | "no_gmail"
    """
    email_address = email_address.strip()

    if not email_address:
        return "invalid", "No email address provided"

    if "@" not in email_address or "." not in email_address.split("@")[-1]:
        return "invalid", (
            "'" + email_address + "' is not a valid email address.\n"
            "Enter like: yourname@gmail.com"
        )

    if not GMAIL_ADDRESS or not GMAIL_PASSWORD:
        return "no_gmail", (
            "Gmail not configured.\n"
            "Add to your .env file:\n"
            "  GMAIL_ADDRESS=yourname@gmail.com\n"
            "  GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx"
        )

    ok, msg = _send_email(
        to_address = email_address,
        subject    = _alert_subject(result),
        body       = _alert_body(result),
    )
    return ("sent" if ok else "failed"), msg


# kept for backward compatibility — app.py calls send_sms_direct
def send_sms_direct(result, contact: str, carrier="airtel"):
    return send_alert_to_contact(result, contact)


def dispatch_alerts(result):
    """Auto-called after every prediction. Saves CSV + emails all saved contacts if HIGH/CRITICAL."""
    sent = []

    if result["risk"]["should_alert"]:
        contacts = load_contacts()
        email_fields = ["your_email", "fire_station_email",
                        "police_email", "forest_officer_email", "extra1_email"]
        for field in email_fields:
            addr = contacts.get(field, "").strip()
            if addr and "@" in addr:
                code, msg = send_alert_to_contact(result, addr)
                if code == "sent":
                    sent.append("email:" + field)

    log_prediction(result, sent)
    return sent


def log_prediction(result, channels_sent=None):
    if channels_sent is None:
        channels_sent = []
    log_dir = os.path.dirname(ALERT_LOG_PATH)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    write_header = (not os.path.exists(ALERT_LOG_PATH)
                    or os.path.getsize(ALERT_LOG_PATH) == 0)
    with open(ALERT_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        if write_header:
            writer.writerow(CSV_COLUMNS)
        w   = result["weather"]
        fwi = result["fwi"]
        writer.writerow([
            result["timestamp"], result["location"],
            result["lat"], result["lon"],
            w["Temperature"], w["RH"], w["Ws"], w["Rain"],
            fwi["FFMC"], fwi["DMC"], fwi["DC"],
            fwi["ISI"], fwi["BUI"], fwi["FWI"],
            round(result["probability"] * 100, 2),
            "FIRE" if result["prediction"] == 1 else "NO FIRE",
            result["risk"]["level"],
            "YES" if channels_sent else "NO",
            "|".join(channels_sent) if channels_sent else "none",
        ])