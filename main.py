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

# Thresholds for RSSI and SNR (tune these for your environment)
# RSSI: higher is better (in dBm, usually negative numbers: -70 is better than -100)
RSSI_GOOD = -80   # RSSI stronger (less negative) than -80 is good
RSSI_POOR = -100  # RSSI weaker than -100 is poor
# SNR: higher is better
SNR_GOOD = 5      # SNR above 5 is good
SNR_POOR = 0      # SNR below 0 is poor

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
        # timestamp from MySQL is a datetime object
        row["timestamp_str"] = row["timestamp"].strftime("%a %d %b %H:%M")

        # Compute RSSI status & CSS class
        try:
            rssi_val = float(row.get("rssi") if row.get("rssi") is not None else 0)
        except Exception:
            rssi_val = 0.0

        if rssi_val >= RSSI_GOOD:
            row["rssi_status"] = "Good"
            row["rssi_class"] = "w3-green"
        elif rssi_val <= RSSI_POOR:
            row["rssi_status"] = "Poor"
            row["rssi_class"] = "w3-red"
        else:
            row["rssi_status"] = "Fair"
            row["rssi_class"] = "w3-yellow"

        # Compute SNR status & CSS class
        try:
            snr_val = float(row.get("snr") if row.get("snr") is not None else 0)
        except Exception:
            snr_val = 0.0

        if snr_val >= SNR_GOOD:
            row["snr_status"] = "Good"
            row["snr_class"] = "w3-green"
        elif snr_val <= SNR_POOR:
            row["snr_status"] = "Poor"
            row["snr_class"] = "w3-red"
        else:
            row["snr_status"] = "Fair"
            row["snr_class"] = "w3-yellow"
    cursor.close()
    conn.close()

    # Pass a dict with request + any variables for the template
    return templates.TemplateResponse(request=request, name="events.html", context={"rows": rows})