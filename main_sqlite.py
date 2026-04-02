from fastapi import FastAPI
from datetime import datetime
from fastapi.responses import HTMLResponse
import sqlite3

app = FastAPI()

conn = sqlite3.connect("door.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS door_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT,
    state TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()


@app.post("/door")
def receive_event(event: dict):
    cursor.execute(
        "INSERT INTO door_events (device_id, state) VALUES (?, ?)",
        (event["device_id"], event["state"])
    )
    conn.commit()

    return {"status": "saved"}

@app.get("/events", response_class=HTMLResponse)
def show_events():
    cursor.execute("SELECT * FROM door_events ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    print(rows)
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
                <th>Timestamp</th>
            </tr>
    """

    for row in rows:
        html += f"""
            <tr>
                <td>{row[0]}</td>
                <td>{row[1]}</td>
                <td>{row[2]}</td>
                <td>{row[3]}</td>
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