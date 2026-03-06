"""
geocoder.py — finds ANY Tamil Nadu location including forests, villages, sanctuaries
Uses built-in TN places database + OpenStreetMap + OpenWeatherMap
"""
import requests
import logging
from config import OWM_API_KEY

logger = logging.getLogger(__name__)

TN_PLACES = {
    "sathiyamangalam"         : (11.5167, 77.2333, "Sathiyamangalam Forest"),
    "sathyamangalam"          : (11.5167, 77.2333, "Sathiyamangalam Forest"),
    "sathiyamangalam forest"  : (11.5167, 77.2333, "Sathiyamangalam Forest"),
    "sathiyamangalam wildlife": (11.5167, 77.2333, "Sathiyamangalam Wildlife Sanctuary"),
    "sathyamangalam wildlife" : (11.5167, 77.2333, "Sathiyamangalam Wildlife Sanctuary"),
    "mudumalai"               : (11.5670, 76.6370, "Mudumalai National Park"),
    "anamalai"                : (10.3667, 77.1000, "Anamalai Tiger Reserve"),
    "valparai"                : (10.3267, 76.9550, "Valparai"),
    "topslip"                 : (10.4150, 77.0980, "Top Slip Forest"),
    "kalakad"                 : (8.5833,  77.5333, "Kalakkad Tiger Reserve"),
    "meghamalai"              : (9.8833,  77.4333, "Meghamalai Wildlife Sanctuary"),
    "kolli hills"             : (11.2500, 78.3667, "Kolli Hills Forest"),
    "javadu hills"            : (12.3833, 78.8333, "Javadu Hills Forest"),
    "yelagiri"                : (12.5833, 78.6333, "Yelagiri Hills"),
    "pachamalai"              : (11.3667, 78.7500, "Pachamalai Forest"),
    "sirumalai"               : (10.1667, 77.9833, "Sirumalai Forest"),
    "shervaroy"               : (11.7500, 78.2167, "Shervaroy Hills"),
    "hosur forest"            : (12.7333, 77.8333, "Hosur Forest"),
    "coimbatore"              : (11.0168, 76.9558, "Coimbatore"),
    "chennai"                 : (13.0827, 80.2707, "Chennai"),
    "madurai"                 : (9.9252,  78.1198, "Madurai"),
    "salem"                   : (11.6643, 78.1460, "Salem"),
    "trichy"                  : (10.7905, 78.7047, "Trichy"),
    "tiruchirappalli"         : (10.7905, 78.7047, "Tiruchirappalli"),
    "ooty"                    : (11.4102, 76.6950, "Ooty"),
    "udhagamandalam"          : (11.4102, 76.6950, "Ooty (Udhagamandalam)"),
    "erode"                   : (11.3410, 77.7172, "Erode"),
    "tirunelveli"             : (8.7139,  77.7567, "Tirunelveli"),
    "vellore"                 : (12.9165, 79.1325, "Vellore"),
    "tirupur"                 : (11.1085, 77.3411, "Tirupur"),
    "dindigul"                : (10.3673, 77.9803, "Dindigul"),
    "thanjavur"               : (10.7870, 79.1378, "Thanjavur"),
    "kanchipuram"             : (12.8185, 79.6947, "Kanchipuram"),
    "kumbakonam"              : (10.9617, 79.3788, "Kumbakonam"),
    "nagercoil"               : (8.1833,  77.4119, "Nagercoil"),
    "dharmapuri"              : (12.1211, 78.1582, "Dharmapuri"),
    "krishnagiri"             : (12.5186, 78.2137, "Krishnagiri"),
    "namakkal"                : (11.2189, 78.1670, "Namakkal"),
    "kodaikanal"              : (10.2381, 77.4892, "Kodaikanal"),
    "yercaud"                 : (11.7750, 78.2117, "Yercaud"),
    "hogenakkal"              : (12.1024, 77.7929, "Hogenakkal"),
    "pollachi"                : (10.6543, 77.0074, "Pollachi"),
    "mettupalayam"            : (11.2986, 76.9434, "Mettupalayam"),
    "gobichettipalayam"       : (11.4546, 77.3536, "Gobichettipalayam"),
    "hosur"                   : (12.7409, 77.8253, "Hosur"),
    "nilgiris"                : (11.4916, 76.7337, "Nilgiris"),
    "gudalur"                 : (11.5000, 76.4833, "Gudalur"),
    "coonoor"                 : (11.3530, 76.7959, "Coonoor"),
    "sivakasi"                : (9.4536,  77.7991, "Sivakasi"),
    "theni"                   : (10.0104, 77.4770, "Theni"),
    "virudhunagar"            : (9.5851,  77.9624, "Virudhunagar"),
    "ramanathapuram"          : (9.3762,  78.8308, "Ramanathapuram"),
    "pudukkottai"             : (10.3797, 78.8201, "Pudukkottai"),
    "karaikudi"               : (10.0736, 78.7734, "Karaikudi"),
    "pondicherry"             : (11.9416, 79.8083, "Pondicherry"),
    "puducherry"              : (11.9416, 79.8083, "Puducherry"),
    "chidambaram"             : (11.3993, 79.6930, "Chidambaram"),
    "villupuram"              : (11.9389, 79.4928, "Villupuram"),
    "cuddalore"               : (11.7480, 79.7714, "Cuddalore"),
    "nagapattinam"            : (10.7672, 79.8449, "Nagapattinam"),
    "ariyalur"                : (11.1450, 79.0762, "Ariyalur"),
    "perambalur"              : (11.2329, 78.8797, "Perambalur"),
    "sivaganga"               : (9.8473,  78.4803, "Sivaganga"),
    "paramakudi"              : (9.5410,  78.5871, "Paramakudi"),
    "thoothukudi"             : (8.7642,  78.1348, "Thoothukudi"),
    "tuticorin"               : (8.7642,  78.1348, "Tuticorin"),
}

TN_CENTER = (11.1271, 78.6569, "Tamil Nadu")


def get_coordinates(place_name):
    raw = place_name.strip()
    key = raw.lower().strip()
    if not key:
        return None

    # Step 1: exact match in database
    if key in TN_PLACES:
        lat, lon, display = TN_PLACES[key]
        return {"lat": lat, "lon": lon, "display_name": display, "fallback": False}

    # Step 2: partial match in database
    for db_key, (lat, lon, display) in TN_PLACES.items():
        if key in db_key or db_key in key:
            return {"lat": lat, "lon": lon, "display_name": display, "fallback": False}

    # Step 3: OpenStreetMap Nominatim
    for query in [raw + ", Tamil Nadu, India", raw + ", India", raw]:
        result = _try_nominatim(query)
        if result:
            return result

    # Step 4: OpenWeatherMap
    for query in [raw + ", Tamil Nadu, India", raw + ", India", raw]:
        result = _try_owm(query)
        if result:
            return result

    # Step 5: NEVER fail — Tamil Nadu center
    lat, lon, display = TN_CENTER
    return {"lat": lat, "lon": lon, "display_name": raw + " (Tamil Nadu region)", "fallback": True}


def _try_nominatim(query):
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 3, "addressdetails": 1},
            headers={"User-Agent": "WildfireAlertSystem/1.0"},
            timeout=10
        )
        results = resp.json()
        if not results:
            return None
        b    = results[0]
        lat  = round(float(b["lat"]), 4)
        lon  = round(float(b["lon"]), 4)
        addr = b.get("address", {})
        name = (addr.get("nature_reserve") or addr.get("forest") or
                addr.get("village") or addr.get("town") or
                addr.get("city") or addr.get("county") or query.split(",")[0].strip())
        state   = addr.get("state", "Tamil Nadu")
        display = name + " | " + state
        return {"lat": lat, "lon": lon, "display_name": display, "fallback": False}
    except Exception:
        return None


def _try_owm(query):
    if not OWM_API_KEY:
        return None
    try:
        resp    = requests.get(
            "https://api.openweathermap.org/geo/1.0/direct",
            params={"q": query, "limit": 3, "appid": OWM_API_KEY},
            timeout=8
        )
        results = resp.json()
        if results:
            b = results[0]
            parts   = [b.get("name", query)]
            if b.get("state"):
                parts.append(b["state"])
            display = " | ".join(parts)
            return {"lat": round(b["lat"], 4), "lon": round(b["lon"], 4),
                    "display_name": display, "fallback": False}
    except Exception:
        pass
    return None 