from datetime import datetime
import mysql.connector
from mysql.connector import pooling
from dbconfig import DB_CONFIG
from utils import compute_row_display_fields, local_tz_offset_str

# RSSI/SNR thresholds live in utils.py (used by compute_row_display_fields)

# Create a pool of 5 connections
pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="door_pool",
    pool_size=5,
    **DB_CONFIG
)

# Determine session timezone for connections
_SESSION_TIME_ZONE = local_tz_offset_str()


def get_connection():
    """Get a connection from the pool and set session time_zone to local offset."""
    conn = pool.get_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute("SET time_zone = %s", (_SESSION_TIME_ZONE,))
        except Exception:
            pass
        finally:
            cur.close()
    except Exception:
        pass
    return conn

def ensure_schema():
    """Create tables if they do not exist. Call from application startup to avoid import-time side-effects."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
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
    finally:
        cursor.close()
        conn.close()


# compute_row_display_fields is provided by utils.py and imported at top


def insert_event_db(ev: dict):
    """Insert event into DB (sync). Returns a dict with inserted values and timestamp as datetime."""
    # Accept Pydantic BaseModel or dict
    try:
        # Pydantic BaseModel has model_dump() in v2
        ev_dict = ev.model_dump()  # type: ignore
    except Exception:
        # fallback for plain dict-like inputs
        ev_dict = dict(ev) if ev is not None else {}

    conn = get_connection()
    cursor = conn.cursor()
    try:
        try:
            state_parts = ev_dict.get('state', '').split('|')
            state_val = state_parts[1]
            contador_val = int(state_parts[2])
            battery_val = int(state_parts[3])
        except Exception:
            state_val = ev_dict.get('state', '')
            contador_val = ev_dict.get('contador', 1)
            battery_val = ev_dict.get('battery', None)

        cursor.execute(
            "INSERT INTO door_events (device_id, state, contador, rssi, snr, battery) VALUES (%s, %s, %s, %s, %s, %s)",
            (ev_dict.get("device_id"), state_val, contador_val, ev_dict.get("rssi"), ev_dict.get("snr"), battery_val)
        )
        conn.commit()
        inserted = {
            "id": cursor.lastrowid,
            "device_id": ev_dict.get("device_id"),
            "state": state_val,
            "contador": contador_val,
            "rssi": ev_dict.get("rssi"),
            "snr": ev_dict.get("snr"),
            "battery": battery_val,
            "timestamp": datetime.now()
        }
        return inserted
    finally:
        cursor.close()
        conn.close()


def fetch_rows_from_db(limit=50):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM door_events ORDER BY timestamp DESC LIMIT %s", (limit,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    # convert DB row dicts into EventOut models with display fields
    rows_models = []
    for row in rows:
        try:
            rows_models.append(compute_row_display_fields(row))
        except Exception:
            # fallback: keep raw dict if conversion fails
            rows_models.append(row)
    return rows_models


def fetch_rows_for_month(year: int, month: int, limit: int = 5000):
    """Fetch rows whose timestamp falls within the given month.

    Uses a half-open interval [start, end) where end is the first day of the
    following month. Returns rows ordered newest -> oldest (timestamp DESC).
    """
    # compute start and end datetimes
    try:
        start = datetime(year, month, 1, 0, 0, 0)
        if month == 12:
            end = datetime(year + 1, 1, 1, 0, 0, 0)
        else:
            end = datetime(year, month + 1, 1, 0, 0, 0)
    except Exception:
        # fallback: return empty list on bad input
        return []

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM door_events WHERE timestamp >= %s AND timestamp < %s ORDER BY timestamp DESC LIMIT %s",
            (start, end, limit),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    rows_models = []
    for row in rows:
        try:
            rows_models.append(compute_row_display_fields(row))
        except Exception:
            rows_models.append(row)
    return rows_models


def verify_time_zone():
    """Print MySQL global/session time_zone and verify that our session TZ is applied.

    This is a best-effort diagnostic function meant to be called at app startup.
    """
    try:
        conn = pool.get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT @@global.time_zone, @@session.time_zone, NOW(), UTC_TIMESTAMP()")
            row = cur.fetchone()
            print(f"MySQL tz: global={row[0]} session={row[1]} now={row[2]} utc={row[3]} target={_SESSION_TIME_ZONE}")
        finally:
            cur.close()
            conn.close()

        conn2 = get_connection()
        cur2 = conn2.cursor()
        try:
            cur2.execute("SELECT @@session.time_zone, NOW(), UTC_TIMESTAMP()")
            r2 = cur2.fetchone()
            print(f"After set: session={r2[0]} now={r2[1]} utc={r2[2]}")
        finally:
            cur2.close()
            conn2.close()
    except Exception as e:
        print("Warning: could not verify MySQL time_zone:", e)
