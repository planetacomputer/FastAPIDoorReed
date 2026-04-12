from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from datetime import datetime
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import mysql.connector
import asyncio
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

# Active websocket connections
ws_connections: set = set()


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
    contador INT DEFAULT 1, -- Count of events for this device
    rssi INT,            -- Received Signal Strength Indicator
    snr DECIMAL(5,2),    -- Signal-to-Noise Ratio, e.g., 7.25
    battery DECIMAL(4,2),-- Battery voltage in volts, e.g., 3.87
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")
conn.commit()
cursor.close()
conn.close()


# --- Helpers to reduce duplication ---------------------------------
def format_timestamp(dt):
    try:
        return dt.strftime("%a %d %b %H:%M:%S")
    except Exception:
        return str(dt)


def compute_row_display_fields(row):
    """Mutate a row (dict) adding timestamp_str, rssi_status/rssi_class, snr_status/snr_class."""
    # timestamp
    ts = row.get("timestamp")
    row["timestamp_str"] = format_timestamp(ts)

    # RSSI
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

    # SNR
    try:
        snr_val = float(row.get("snr") if row.get("snr") is not None else 0)
    except Exception:
        snr_val = 0.0
    if snr_val >= SNR_GOOD:
        row["snr_status"] = "Good"
        row["snr_class"] = "w3-teal"
    elif snr_val <= SNR_POOR:
        row["snr_status"] = "Poor"
        row["snr_class"] = "w3-pink"
    else:
        row["snr_status"] = "Fair"
        row["snr_class"] = "w3-khaki"


def insert_event_db(ev: dict):
    """Insert event into DB (sync). Returns a dict with inserted values and timestamp as datetime."""
    conn = pool.get_connection()
    cursor = conn.cursor()
    try:
        try:
            state_parts = ev.get('state', '').split('|')
            state_val = state_parts[1]
            contador_val = int(state_parts[2])
        except Exception:
            state_val = ev.get('state', '')
            contador_val = ev.get('contador', 1)

        cursor.execute(
            "INSERT INTO door_events (device_id, state, contador, rssi, snr, battery) VALUES (%s, %s, %s, %s, %s, %s)",
            (ev.get("device_id"), state_val, contador_val, ev.get("rssi"), ev.get("snr"), ev.get("battery"))
        )
        conn.commit()
        inserted = {
            "id": cursor.lastrowid,
            "device_id": ev.get("device_id"),
            "state": state_val,
            "contador": contador_val,
            "rssi": ev.get("rssi"),
            "snr": ev.get("snr"),
            "battery": ev.get("battery"),
            "timestamp": datetime.now()
        }
        return inserted
    finally:
        cursor.close()
        conn.close()


async def broadcast_payload(payload: dict):
    """Broadcast payload to all connected websockets, pruning dead connections."""
    dead = []
    for ws in list(ws_connections):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for d in dead:
        ws_connections.discard(d)


def fetch_rows_from_db(limit=50):
    conn = pool.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM door_events ORDER BY timestamp DESC LIMIT %s", (limit,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    # compute display fields
    for row in rows:
        compute_row_display_fields(row)
    return rows


@app.post("/door")
async def receive_event(event: dict):
    # Insert into DB on a thread to avoid blocking
    inserted = await asyncio.to_thread(insert_event_db, event)

    # compute display fields
    compute_row_display_fields(inserted)
    # prepare JSON-serializable payload
    payload = dict(inserted)
    payload["timestamp"] = payload["timestamp_str"]
    payload["flash"] = True

    # broadcast
    asyncio.create_task(broadcast_payload(payload))

    return {"status": "saved"}

app.mount("/static", StaticFiles(directory="static"), name="static")
# Templates
templates = Jinja2Templates(directory="templates")

@app.get("/events", response_class=HTMLResponse)
def show_events(request: Request):
    rows = fetch_rows_from_db(limit=50)
    return templates.TemplateResponse(request=request, name="events.html", context={"rows": rows})


@app.get("/puerta", response_class=HTMLResponse)
def show_puerta(request: Request):
    """Render events grouped by day. Each day's rows are collapsible in the template."""
    rows = fetch_rows_from_db(limit=1000)
    from collections import OrderedDict
    groups = OrderedDict()
    for row in rows:
        # day key
        try:
            ts_dt = row.get("timestamp")
            day_key = ts_dt.strftime("%Y-%m-%d")
            day_label = ts_dt.strftime("%A %d %b %Y")
        except Exception:
            day_key = "unknown"
            day_label = "Unknown"
        if day_key not in groups:
            groups[day_key] = {"label": day_label, "rows": []}
        groups[day_key]["rows"].append(row)

    # compute minutes span per group (difference between first and last timestamps)
    for key, g in groups.items():
        try:
            rows_for_day = g["rows"]
            if rows_for_day:
                first_ts = rows_for_day[0].get("timestamp")
                last_ts = rows_for_day[-1].get("timestamp")
                if isinstance(first_ts, datetime) and isinstance(last_ts, datetime):
                    delta_minutes = int((first_ts - last_ts).total_seconds() / 60)
                else:
                    delta_minutes = 0
            else:
                delta_minutes = 0
        except Exception:
            delta_minutes = 0
        # store numeric span and human-friendly label (e.g., "1h 20m")
        g["minutes_span"] = delta_minutes
        if delta_minutes >= 60:
            hours = delta_minutes // 60
            minutes_only = delta_minutes % 60
            if minutes_only:
                g["minutes_span_label"] = f"{hours}h {minutes_only}m"
            else:
                g["minutes_span_label"] = f"{hours}h"
        else:
            g["minutes_span_label"] = f"{delta_minutes} min"

    # connections handled inside helpers

    return templates.TemplateResponse(request=request, name="puerta.html", context={"groups": groups})


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await websocket.accept()
    ws_connections.add(websocket)
    try:
        while True:
            # keep the connection open; client may send pings or messages (ignored)
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_connections.discard(websocket)
    except Exception:
        ws_connections.discard(websocket)