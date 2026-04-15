from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime, timedelta
import calendar
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
from utils import compute_row_display_fields, compute_group_time_span, compute_groups_metadata
from db import get_connection, insert_event_db, fetch_rows_from_db, fetch_rows_for_month, pool, _SESSION_TIME_ZONE, verify_time_zone, ensure_schema
import locale

# Set Spanish locale
locale.setlocale(locale.LC_TIME, "es_ES.utf8")  # Linux / macOS
# For Windows, use "Spanish_Spain.1252"

app = FastAPI()

 

# Active websocket connections
ws_connections: set = set()

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


# fetch_rows_from_db is provided by db.py; imported above


@app.post("/door")
async def receive_event(event: dict):
    # Insert into DB on a thread to avoid blocking
    inserted = await asyncio.to_thread(insert_event_db, event)

    # compute display fields
    compute_row_display_fields(inserted)
    # prepare JSON-serializable payload
    payload = dict(inserted)
    # include a compact date key so clients can quickly decide which calendar cell
    # should receive this update (format: YYYY-MM-DD)
    try:
        payload["date_key"] = inserted["timestamp"].strftime("%Y-%m-%d")
    except Exception:
        # fallback: try to extract from timestamp_str if possible (not ideal)
        payload["date_key"] = None
    # determine if this event is beyond 3 hours from the first event of that day
    try:
        date_str = inserted["timestamp"].strftime("%Y-%m-%d")
        conn2 = get_connection()
        cur2 = conn2.cursor()
        cur2.execute("SELECT MIN(timestamp) FROM door_events WHERE DATE(timestamp) = %s", (date_str,))
        row = cur2.fetchone()
        cur2.close()
        conn2.close()
        first_ts = row[0] if row and row[0] is not None else None
        if isinstance(first_ts, datetime):
            out_of_window = (inserted["timestamp"] - first_ts) > timedelta(hours=3)
        else:
            out_of_window = False
    except Exception:
        out_of_window = False
    payload["out_of_window"] = out_of_window
    payload["timestamp"] = payload["timestamp_str"]
    payload["flash"] = True

    # broadcast
    asyncio.create_task(broadcast_payload(payload))

    return {"status": "saved"}

app.mount("/static", StaticFiles(directory="static"), name="static")
# Serve the top-level `fonts/` directory at `/fonts` so Font Awesome's
# relative paths (e.g. ../fonts/fontawesome-webfont.woff2) resolve correctly.
# If you moved font files into `static/fonts`, serve them at `/fonts` by
# mounting that folder. This keeps Font Awesome's relative URLs working.
app.mount("/fonts", StaticFiles(directory="static/fonts"), name="fonts")
# Templates
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def startup_check_time_zone():
    """Delegate time-zone verification to db.verify_time_zone()."""
    try:
        # Ensure DB schema exists first (safe to call repeatedly)
        try:
            ensure_schema()
        except Exception as e:
            print("Warning: ensure_schema() failed:", e)
        # then verify session time zone
        verify_time_zone()
    except Exception as e:
        print("Warning: error while verifying DB time zone on startup:", e)

@app.get("/events", response_class=HTMLResponse)
def show_events(request: Request):
    rows = fetch_rows_from_db(limit=250)
    return templates.TemplateResponse(request=request, name="events.html", context={"rows": rows})


@app.get("/", include_in_schema=False)
def root_redirect():
    """Default entrance: redirect root to the calendar view."""
    return RedirectResponse(url="/puerta_calendar")

@app.get("/puerta_calendar", response_class=HTMLResponse)
def show_puerta_calendar(request: Request):
    """Render events for a month inside a calendar grid. Query params: year, month (ints)."""
    # parse year/month from query params, default to current
    q = request.query_params
    now = datetime.now()
    try:
        year = int(q.get('year', now.year))
    except Exception:
        year = now.year
    try:
        month = int(q.get('month', now.month))
    except Exception:
        month = now.month

    # fetch rows for the requested month directly from DB (more efficient)
    rows = fetch_rows_for_month(year, month, limit=5000)

    # get the most recent event overall (not limited to the month) so the
    # calendar header can display the latest door state
    latest = fetch_rows_from_db(limit=1)
    if latest:
        try:
            lr = latest[0]
            last_state_raw = lr.get('state')
            last_state_label = 'ABIERTA' if str(last_state_raw) == '0' else 'CERRADA'
        except Exception:
            last_state_raw = None
            last_state_label = '--'
    else:
        last_state_raw = None
        last_state_label = '--'

    # build groups for the requested month
    from collections import OrderedDict
    groups = OrderedDict()
    for row in rows:
        try:
            ts_dt = row.get('timestamp')
            if ts_dt.year != year or ts_dt.month != month:
                continue
            day_key = ts_dt.strftime("%Y-%m-%d")
            day_label = ts_dt.strftime("%A %d %b %Y")
        except Exception:
            continue
        if day_key not in groups:
            groups[day_key] = {"label": day_label, "rows": []}
        groups[day_key]["rows"].append(row)

    # compute same per-group metadata as /puerta (first/last times and minutes label)
    try:
        compute_groups_metadata(groups, window_hours=3)
    except Exception:
        # keep previous defaults if helper fails
        for key, g in groups.items():
            g["minutes_span"] = g.get("minutes_span", 0)
            g["minutes_span_label"] = g.get("minutes_span_label", "0 min")
            g["first_time"] = g.get("first_time", "--:--")
            g["last_time"] = g.get("last_time", "--:--")

    # prepare a calendar weeks grid for the month
    cal = calendar.Calendar(firstweekday=0)  # Monday=0
    month_days = cal.monthdayscalendar(year, month)
    # each week is a list of day numbers (0 means padding day)

    # build weeks structure with day info and events list
    weeks = []
    for week in month_days:
        week_cells = []
        for d in week:
            if d == 0:
                week_cells.append({"day": 0, "date_key": None, "events": []})
            else:
                date_key = f"{year:04d}-{month:02d}-{d:02d}"
                grp = groups.get(date_key)
                events = grp["rows"] if grp else []
                meta = {
                    "day": d,
                    "date_key": date_key,
                    "events": events,
                    "first_time": grp.get("first_time") if grp else "--:--",
                    "last_time": grp.get("last_time") if grp else "--:--",
                    "minutes_span_label": grp.get("minutes_span_label") if grp else "0 min",
                }
                week_cells.append(meta)
        weeks.append(week_cells)

    # compute weekly totals (sum of minutes_span for each week) and attach
    # `week_total_minutes` to the Sunday cell so templates can display it.
    try:
        # compute_weeks_totals mutates weeks in-place
        from utils import compute_weeks_totals
        compute_weeks_totals(weeks, groups)
    except Exception:
        pass

    # helper: previous and next month for navigation
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1

    context = {
        "year": year,
        "month": month,
    "month_name": datetime(year, month, 1).strftime("%B").capitalize(),
        "weeks": weeks,
        "groups": groups,
        "last_state": last_state_raw,
        "last_state_label": last_state_label,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
    }
    # provide today's key so templates do not rely on now() helper
    context["today_key"] = now.strftime("%Y-%m-%d")
    return templates.TemplateResponse(request=request, name="puerta_calendar.html", context=context)


@app.get("/puerta_list", response_class=HTMLResponse)
def show_puerta_list(request: Request):
    """Render events grouped by day for a month as a vertical list with collapsible day sections.
    Query params: year, month (ints)."""
    q = request.query_params
    now_dt = datetime.now()
    try:
        year = int(q.get('year', now_dt.year))
    except Exception:
        year = now_dt.year
    try:
        month = int(q.get('month', now_dt.month))
    except Exception:
        month = now_dt.month

    # fetch rows for the requested month directly from DB (more efficient)
    rows = fetch_rows_for_month(year, month, limit=5000)

    # fetch latest overall event for header badge
    latest = fetch_rows_from_db(limit=1)
    if latest:
        try:
            lr = latest[0]
            last_state_raw = lr.get('state')
            last_state_label = 'ABIERTA' if str(last_state_raw) == '0' else 'CERRADA'
        except Exception:
            last_state_raw = None
            last_state_label = '--'
    else:
        last_state_raw = None
        last_state_label = '--'

    from collections import OrderedDict
    groups = OrderedDict()
    for row in rows:
        try:
            ts_dt = row.get('timestamp')
            if ts_dt.year != year or ts_dt.month != month:
                continue
            day_key = ts_dt.strftime("%Y-%m-%d")
            day_label = ts_dt.strftime("%A %d %b %Y")
        except Exception:
            continue
        if day_key not in groups:
            groups[day_key] = {"label": day_label, "rows": []}
        groups[day_key]["rows"].append(row)

    # compute per-group metadata
    try:
        compute_groups_metadata(groups, window_hours=3)
    except Exception:
        for key, g in groups.items():
            g["minutes_span"] = g.get("minutes_span", 0)
            g["minutes_span_label"] = g.get("minutes_span_label", "0 min")
            g["first_time"] = g.get("first_time", "--:--")
            g["last_time"] = g.get("last_time", "--:--")

    # navigation
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1

    context = {
        "year": year,
        "month": month,
    "month_name": datetime(year, month, 1).strftime("%B").capitalize(),
        "groups": groups,
        "last_state": last_state_raw,
        "last_state_label": last_state_label,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "today_key": now_dt.strftime("%Y-%m-%d")
    }
    return templates.TemplateResponse(request=request, name="puerta_list.html", context=context)


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