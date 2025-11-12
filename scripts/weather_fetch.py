import requests
import psycopg2
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import os
from psycopg2.extras import execute_values
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time

# ============ Timezone Setup (IST) ============
IST = timezone(timedelta(hours=5, minutes=30))

# ============ Logging Setup ============
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../logs'))
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = os.path.join(LOG_DIR, f"weather_log_{datetime.now(IST).strftime('%Y-%m-%d')}.log")

# Configure logging to include IST timestamps
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.info("🌦️ Hourly weather fetch script started (IST).")

# ============ Load Environment ============
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

# ============ Safe Getter ============
def safe_get(data, key):
    """Return first hourly value if available, else None."""
    try:
        values = data.get("hourly", {}).get(key, [])
        return values[0] if values else None
    except Exception:
        return None

# ============ City List ============
cities = [
    {"name": "Mumbai", "lat": 19.0760, "lon": 72.8777},
    {"name": "Delhi", "lat": 28.7041, "lon": 77.1025},
    {"name": "Bengaluru", "lat": 12.9716, "lon": 77.5946},
    {"name": "Chennai", "lat": 13.0827, "lon": 80.2707},
    {"name": "Kolkata", "lat": 22.5726, "lon": 88.3639},
    {"name": "Hyderabad", "lat": 17.3850, "lon": 78.4867},
    {"name": "Lucknow", "lat": 26.8467, "lon": 80.9462},
    {"name": "Jaipur", "lat": 26.9124, "lon": 75.7873},
    {"name": "Bhopal", "lat": 23.2599, "lon": 77.4126},
    {"name": "Patna", "lat": 25.5941, "lon": 85.1376},
    {"name": "Gandhinagar", "lat": 23.2156, "lon": 72.6369},
    {"name": "Chandigarh", "lat": 30.7333, "lon": 76.7794},
    {"name": "Bhubaneswar", "lat": 20.2961, "lon": 85.8245},
    {"name": "Thiruvananthapuram", "lat": 8.5241, "lon": 76.9366},
    {"name": "Dispur", "lat": 26.1433, "lon": 91.7898},
    {"name": "Imphal", "lat": 24.8170, "lon": 93.9368},
    {"name": "Agartala", "lat": 23.8315, "lon": 91.2868},
    {"name": "Aizawl", "lat": 23.7271, "lon": 92.7176},
    {"name": "Shillong", "lat": 25.5788, "lon": 91.8933},
    {"name": "Kohima", "lat": 25.6747, "lon": 94.1100},
    {"name": "Gangtok", "lat": 27.3389, "lon": 88.6065},
    {"name": "Itanagar", "lat": 27.0844, "lon": 93.6053},
    {"name": "Dehradun", "lat": 30.3165, "lon": 78.0322},
    {"name": "Raipur", "lat": 21.2514, "lon": 81.6296},
    {"name": "Ranchi", "lat": 23.3441, "lon": 85.3096},
    {"name": "Panaji", "lat": 15.4909, "lon": 73.8278},
    {"name": "Puducherry", "lat": 11.9416, "lon": 79.8083},
    {"name": "Port Blair", "lat": 11.6234, "lon": 92.7265},
    {"name": "Kavaratti", "lat": 10.5667, "lon": 72.6420},
    {"name": "Srinagar", "lat": 34.0837, "lon": 74.7973},
    {"name": "Leh", "lat": 34.1526, "lon": 77.5770}
]

# ============ Fetch Weather Data ============
def fetch_city_data(city):
    LAT, LON, CITY = city["lat"], city["lon"], city["name"]
    urls = {
        "weather": f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m,relativehumidity_2m,windspeed_10m",
        "air": f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&hourly=pm10,pm2_5,nitrogen_dioxide,ozone"
    }

    try:
        weather = requests.get(urls["weather"], timeout=10).json()
        air = requests.get(urls["air"], timeout=10).json()

        ist_now = datetime.now(IST)

        logging.info(f"Fetched data for {CITY} at {ist_now}.")
        return (
            CITY,
            safe_get(weather, "temperature_2m"),
            safe_get(weather, "relativehumidity_2m"),
            safe_get(weather, "windspeed_10m"),
            safe_get(air, "pm10"),
            safe_get(air, "pm2_5"),
            safe_get(air, "nitrogen_dioxide"),
            safe_get(air, "ozone"),
            ist_now
        )
    except Exception as e:
        logging.error(f"Error fetching data for {CITY}: {e}")
        return (CITY, None, None, None, None, None, None, None, datetime.now(IST))

# ============ Parallel Fetch ============
results = []
with ThreadPoolExecutor(max_workers=6) as executor:
    futures = [executor.submit(fetch_city_data, c) for c in cities]
    for f in as_completed(futures):
        r = f.result()
        if r:
            results.append(r)
        time.sleep(0.1)  # slight delay to avoid rate limiting

# ============ Database Insert ============
try:
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    execute_values(cur, """
        INSERT INTO weather_data
        (city, temperature, humidity, wind_speed, pm10, pm2_5, nitrogen_dioxide, ozone, timestamp)
        VALUES %s
    """, results)
    conn.commit()

    logging.info(f"Inserted {len(results)} records successfully at {datetime.now(IST)} (IST).")
    print(f"Inserted {len(results)} records successfully.")
except Exception as e:
    logging.error(f"Database insert failed: {e}")
    print(f"Database insert failed: {e}")
finally:
    if 'cur' in locals(): cur.close()
    if 'conn' in locals(): conn.close()

logging.info("Script completed successfully (IST).")
print("Script completed successfully.")
