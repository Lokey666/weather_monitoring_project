import requests
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
import os
from psycopg2.extras import execute_values
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time

# ============ Logging Setup ============
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../logs'))
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = os.path.join(LOG_DIR, f"weather_log_{datetime.now().strftime('%Y-%m-%d')}.log")

logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logging.info("Hourly weather fetch script started.")

# ============ Environment Setup ============
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

# ============ City List ============
cities = [
    {"name": "Mumbai", "lat": 19.0760, "lon": 72.8777},
    {"name": "Delhi", "lat": 28.7041, "lon": 77.1025},
    {"name": "Bengaluru", "lat": 12.9716, "lon": 77.5946},
    {"name": "Chennai", "lat": 13.0827, "lon": 80.2707},
    {"name": "Kolkata", "lat": 22.5726, "lon": 88.3639},
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
        return (
            CITY,
            weather["hourly"]["temperature_2m"][0],
            weather["hourly"]["relativehumidity_2m"][0],
            weather["hourly"]["windspeed_10m"][0],
            air["hourly"]["pm10"][0],
            air["hourly"]["pm2_5"][0],
            air["hourly"]["nitrogen_dioxide"][0],
            air["hourly"]["ozone"][0],
            datetime.now()
        )
    except Exception as e:
        logging.error(f"Error fetching data for {CITY}: {e}")
        return None

# ============ Parallel Fetch ============
results = []
with ThreadPoolExecutor(max_workers=5) as executor:
    for f in as_completed([executor.submit(fetch_city_data, c) for c in cities]):
        r = f.result()
        if r: results.append(r)
        time.sleep(0.2)

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
    print(f"Inserted {len(results)} records.")
    logging.info(f"Inserted {len(results)} records.")
except Exception as e:
    print(f"Database insert failed: {e}")
    logging.error(f"Database insert failed: {e}")
finally:
    if 'cur' in locals(): cur.close()
    if 'conn' in locals(): conn.close()

logging.info("Script completed successfully.")
print("Script completed successfully.")
