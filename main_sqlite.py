from fastapi import FastAPI
from datetime import datetime
from fastapi.responses import HTMLResponse
import sqlite3
import time

app = FastAPI()

conn = sqlite3.connect("door.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS door_events (
    device_id VARCHAR(50),
    state VARCHAR(20),
    rssi INT,            -- Received Signal Strength Indicator
    snr DECIMAL(5,2),    -- Signal-to-Noise Ratio, e.g., 7.25
    battery DECIMAL(4,2),-- Battery voltage in volts, e.g., 3.87
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
""")
conn.commit()


@app.post("/door")
def receive_event(event: dict):
    device_id = event.get("device_id", "UNKNOWN")
    state     = event.get("state", "")
    rssi      = event.get("rssi", 0)
    snr       = event.get("snr", 0.0)
    battery   = event.get("battery", 0.0)
    now = int(time.time())  # seconds since 1970-01-01
    cursor.execute("""
        INSERT INTO door_events (device_id, state, rssi, snr, battery, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (device_id, state, rssi, snr, battery, now))
    conn.commit()
    return {"status": "ok"}

@app.get("/events", response_class=HTMLResponse)
def show_events():
    cursor.execute("SELECT * FROM door_events ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    html = """
    <html>
    <head>
        <title>Door Events</title>
        <style>
            table { border-collapse: collapse; width: 80%; margin: auto; }
            th, td { border: 1px solid black; padding: 8px; text-align: center; }
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>
        <h2 style="text-align:center;">Door Events</h2>
        <table>
            <tr>
                <th>ID</th>
                <th>Device</th>
                <th>State</th>
                <th>RSSI</th>
                <th>SNR</th>
                <th>Timestamp</th>
            </tr>
    """
    
    for row in rows:
         # Optional: format nicely
        ts_epoch = row[5]  # timestamp returned as integer
        ts_formatted = datetime.fromtimestamp(int(ts_epoch)).strftime('%d/%m/%Y %H:%M:%S')
        
        html += f"""
            <tr>
                <td>{row[0]}</td>
                <td>{row[1]}</td>
                <td>{row[2]}</td>
                <td>{row[3]}</td>
                <td>{row[4]}</td>
                <td>{ts_formatted}</td>
            </tr>
        """
    
    html += """
        </table>
    </body>
    </html>
    """
    return html


@app.get("/test", response_class=HTMLResponse)
def test():
    return "<h1>HELLO</h1>"