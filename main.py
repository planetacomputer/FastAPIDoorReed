from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from datetime import datetime
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import mysql.connector
from mysql.connector import pooling
from dbconfig import DB_CONFIG  # <-- import credentials
import locale

# Set Spanish locale
locale.setlocale(locale.LC_TIME, "es_ES.utf8")  # Linux / macOS
# For Windows, use "Spanish_Spain.1252"

app = FastAPI()

# Create a pool of 5 connections
pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="door_pool",
    pool_size=5,
    **DB_CONFIG
)

# -----------------------------
# Create table if not exists
# -----------------------------
conn = pool.get_connection()
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS door_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(50),
    state VARCHAR(20),
    rssi INT,            -- Received Signal Strength Indicator
    snr DECIMAL(5,2),    -- Signal-to-Noise Ratio, e.g., 7.25
    battery DECIMAL(4,2),-- Battery voltage in volts, e.g., 3.87
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")
conn.commit()
cursor.close()
conn.close()

@app.post("/door")
def receive_event(event: dict):
    conn = pool.get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO door_events (device_id, state, rssi, snr, battery) VALUES (%s, %s, %s, %s, %s)",
        (event["device_id"], event["state"], event["rssi"], event["snr"], event["battery"])
    )
    conn.commit()

    cursor.close()
    conn.close()  # returns connection to pool

    return {"status": "saved"}

app.mount("/static", StaticFiles(directory="static"), name="static")
# Templates
templates = Jinja2Templates(directory="templates")

@app.get("/events", response_class=HTMLResponse)
def show_events(request: Request):
    conn = pool.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM door_events ORDER BY timestamp DESC LIMIT 50")
    rows = cursor.fetchall()
    for row in rows:
        # Format directly to string in Spanish
        row["timestamp_str"] = row["timestamp"].strftime("%a %d %b %H:%M")
    cursor.close()
    conn.close()

    # Pass a dict with request + any variables for the template
    return templates.TemplateResponse(request=request, name="events.html", context={"rows": rows})