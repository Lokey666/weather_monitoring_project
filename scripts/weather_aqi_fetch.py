import requests
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# ============================== TIMEZONE SETTINGS ==============================
IST = timezone(timedelta(hours=5, minutes=30))

# ============================== LOAD ENV VARS ==============================
load_dotenv()
WEATHER_KEY = os.getenv("WEATHER_API_KEY")
DB_URL = os.getenv("DATABASE_URL")

if not WEATHER_KEY:
    raise Exception("Missing WEATHER_API_KEY in .env")

# ============================== CITY LIST ==============================
cities = [
    ("Mumbai", 19.0760, 72.8777),
    ("Delhi", 28.7041, 77.1025),
    ("Bengaluru", 12.9716, 77.5946),
    ("Chennai", 13.0827, 80.2707),
    ("Kolkata", 22.5726, 88.3639),
    ("Hyderabad", 17.3850, 78.4867),
    ("Pune", 18.5204, 73.8567),
    ("Ahmedabad", 23.0225, 72.5714),
    ("Jaipur", 26.9124, 75.7873),
    ("Lucknow", 26.8467, 80.9462),
    ("Patna", 25.5941, 85.1376),
    ("Indore", 22.7196, 75.8577),
    ("Bhopal", 23.2599, 77.4126),
    ("Surat", 21.1702, 72.8311),
    ("Dehradun", 30.3165, 78.0322)
]

# ============================== SAFE API FETCH ==============================
def fetch_json(url, retries=3, timeout=10):
    for _ in range(retries):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        time.sleep(1)
    return {}

# ============================== WEATHERAPI FETCH (ONLY SOURCE) ==============================
def fetch_weather(lat, lon):
    url = f"https://api.weatherapi.com/v1/current.json?key={WEATHER_KEY}&q={lat},{lon}&aqi=yes"
    data = fetch_json(url)

    if "error" in data:
        return None

    cur = data.get("current", {})
    aq = cur.get("air_quality", {})

    # Convert wind_kph → m/s (standard)
    try:
        wind_ms = cur.get("wind_kph") / 3.6
    except:
        wind_ms = None

    return {
        "temp": cur.get("temp_c"),
        "humidity": cur.get("humidity"),
        "wind": wind_ms,
        "pm10": aq.get("pm10"),
        "pm25": aq.get("pm2_5"),
        "no2": aq.get("no2"),
        "o3": aq.get("o3")
    }

# ============================== FETCH EACH CITY ==============================
def fetch_city(city):
    name, lat, lon = city

    w = fetch_weather(lat, lon)

    # If WeatherAPI fails → everything None
    if not w:
        w = {"temp": None, "humidity": None, "wind": None,
             "pm10": None, "pm25": None, "no2": None, "o3": None}

    # Always IST timestamp
    ts = datetime.now(IST)

    return (
        name,
        w["temp"],
        w["humidity"],
        w["wind"],
        w["pm10"],
        w["pm25"],
        w["no2"],
        w["o3"],
        ts
    )

# ============================== PARALLEL FETCH ==============================
def collect_all():
    results = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(fetch_city, c) for c in cities]
        for f in as_completed(futures):
            results.append(f.result())

    results.sort(key=lambda x: x[0])  # consistent ordering
    return results

# ============================== DB INSERT ==============================
def save_to_db(data):
    conn = None

    for _ in range(3):
        try:
            conn = psycopg2.connect(DB_URL)
            break
        except:
            time.sleep(2)

    if not conn:
        print("❌ Database connection failed.")
        return

    cur = conn.cursor()

    query = """
        INSERT INTO weather_data
        (city, temperature, humidity, wind_speed, pm10, pm2_5, nitrogen_dioxide, ozone, timestamp)
        VALUES %s
    """

    execute_values(cur, query, data)
    conn.commit()

    cur.close()
    conn.close()

# ============================== MAIN ==============================
if __name__ == "__main__":
    rows = collect_all()
    save_to_db(rows)
    print("✅ WeatherAPI-only data inserted successfully.")
