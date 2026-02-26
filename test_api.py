"""
Run this file to test your OpenWeatherMap API key.
Command: python test_api.py
"""
import os
import requests
from dotenv import load_dotenv

print("=" * 50)
print("  WILDFIRE SYSTEM — API KEY DEBUGGER")
print("=" * 50)

# Step 1 — Check .env file exists
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    print("\n✅ .env file found at:", env_path)
else:
    print("\n❌ .env file NOT found!")
    print("   Create a file called '.env' in your project folder.")
    print("   It should contain:")
    print("   OWM_API_KEY=your_key_here")
    exit()

# Step 2 — Load .env
load_dotenv(env_path)
api_key = os.getenv('OWM_API_KEY', '')

if not api_key:
    print("\n❌ OWM_API_KEY is EMPTY in your .env file!")
    print("   Open .env and make sure it looks like:")
    print("   OWM_API_KEY=abcd1234abcd1234abcd1234abcd1234")
    exit()
elif api_key == 'your_openweathermap_key_here':
    print("\n❌ You still have the placeholder key!")
    print("   Replace 'your_openweathermap_key_here' with your real key.")
    exit()
else:
    print("\n✅ OWM_API_KEY found:", api_key[:6] + "..." + api_key[-4:])

# Step 3 — Test the API call
print("\n⏳ Testing API call to OpenWeatherMap...")
url = "https://api.openweathermap.org/data/2.5/weather"
params = {
    'lat'  : 11.0168,   # Coimbatore
    'lon'  : 76.9558,
    'appid': api_key,
    'units': 'metric'
}

try:
    response = requests.get(url, params=params, timeout=10)
    data     = response.json()

    if response.status_code == 200:
        print("\n✅ API WORKS! Weather data received:")
        print("   City       :", data.get('name', 'N/A'))
        print("   Temperature:", data['main']['temp'], "°C")
        print("   Humidity   :", data['main']['humidity'], "%")
        print("   Wind Speed :", data['wind']['speed'], "m/s")
        print("\n🎉 Your API key is working correctly!")
        print("   Run: streamlit run app.py")

    elif response.status_code == 401:
        print("\n❌ ERROR 401 — Invalid API Key!")
        print("   Your key is wrong or not activated yet.")
        print("   FIX: Wait 10-30 minutes after creating the key.")
        print("   New OpenWeatherMap keys take time to activate.")

    elif response.status_code == 429:
        print("\n❌ ERROR 429 — Too many requests!")
        print("   You've exceeded the free limit. Wait 1 hour.")

    else:
        print("\n❌ ERROR", response.status_code)
        print("   Message:", data.get('message', 'Unknown error'))

except requests.exceptions.ConnectionError:
    print("\n❌ No internet connection!")
    print("   Check your WiFi/internet and try again.")

except requests.exceptions.Timeout:
    print("\n❌ Request timed out!")
    print("   Check your internet connection.")

except Exception as e:
    print("\n❌ Unexpected error:", str(e))

print("\n" + "=" * 50)