from datetime import datetime
from typing import List
from models import EventOut

# Thresholds for RSSI and SNR (share with compute_row_display_fields)
RSSI_GOOD = -80   # RSSI stronger (less negative) than -80 is good
RSSI_POOR = -100  # RSSI weaker than -100 is poor
SNR_GOOD = 5      # SNR above 5 is good
SNR_POOR = 0      # SNR below 0 is poor


def format_timestamp(dt):
    try:
        return dt.strftime("%a %d %b %H:%M:%S")
    except Exception:
        return str(dt)


def compute_row_display_fields(row):
    """Accept a dict or EventOut and return an EventOut with display fields set.

    This function will convert a plain DB row dict into `EventOut` if needed,
    then compute `timestamp_str`, RSSI/SNR status and classes, mutating and
    returning the EventOut instance.
    """
    # convert dict to EventOut if necessary
    if isinstance(row, dict):
        try:
            model = EventOut(**row)
        except Exception:
            # fallback: create a minimal EventOut-like object
            model = EventOut(id=row.get('id', 0), device_id=row.get('device_id'), state=str(row.get('state', '')),
                             contador=row.get('contador'), rssi=row.get('rssi'), snr=row.get('snr'), battery=row.get('battery'),
                             timestamp=row.get('timestamp') or datetime.now())
    elif isinstance(row, EventOut):
        model = row
    else:
        # unsupported type; attempt to coerce
        model = EventOut(id=getattr(row, 'id', 0), device_id=getattr(row, 'device_id', None),
                         state=str(getattr(row, 'state', '')),
                         contador=getattr(row, 'contador', None), rssi=getattr(row, 'rssi', None),
                         snr=getattr(row, 'snr', None), battery=getattr(row, 'battery', None),
                         timestamp=getattr(row, 'timestamp', datetime.now()))

    # timestamp
    ts = getattr(model, 'timestamp', None)
    try:
        model.timestamp_str = format_timestamp(ts)
    except Exception:
        model.timestamp_str = str(ts)

    # RSSI
    try:
        rssi_val = float(model.rssi) if model.rssi is not None else 0.0
    except Exception:
        rssi_val = 0.0
    if rssi_val >= RSSI_GOOD:
        model.rssi_status = "Good"
        model.rssi_class = "w3-green"
    elif rssi_val <= RSSI_POOR:
        model.rssi_status = "Poor"
        model.rssi_class = "w3-red"
    else:
        model.rssi_status = "Fair"
        model.rssi_class = "w3-yellow"

    # SNR
    try:
        snr_val = float(model.snr) if model.snr is not None else 0.0
    except Exception:
        snr_val = 0.0
    if snr_val >= SNR_GOOD:
        model.snr_status = "Good"
        model.snr_class = "w3-teal"
    elif snr_val <= SNR_POOR:
        model.snr_status = "Poor"
        model.snr_class = "w3-pink"
    else:
        model.snr_status = "Fair"
        model.snr_class = "w3-khaki"

    return model


def local_tz_offset_str():
    """Compute local tz offset as +HH:MM or -HH:MM for MySQL session."""
    try:
        off = datetime.now().astimezone().utcoffset()
        if off is None:
            return '+00:00'
        total_minutes = int(off.total_seconds() // 60)
        sign = '+' if total_minutes >= 0 else '-'
        hh = abs(total_minutes) // 60
        mm = abs(total_minutes) % 60
        return f"{sign}{hh:02d}:{mm:02d}"
    except Exception:
        return '+00:00'


def compute_group_time_span(rows_for_day, window_hours=3):
    """Given a list of rows (newest->oldest), mark rows that are outside the
    time window (default 3 hours from the day's first event) and compute a
    minutes-span and human label plus first/last time strings.

    Accepts a list of EventOut or dicts and returns (minutes_span, label, first_time, last_time).
    Mutates EventOut instances by setting `out_of_window` boolean.
    """
    from datetime import timedelta

    # normalize to EventOut models
    models: List[EventOut] = []
    for item in rows_for_day:
        if isinstance(item, EventOut):
            models.append(item)
        else:
            try:
                models.append(compute_row_display_fields(item))
            except Exception:
                continue

    for m in models:
        m.out_of_window = False

    if not models:
        return 0, "0 min", "--:--", "--:--"

    first_ts = models[-1].timestamp
    if not isinstance(first_ts, datetime):
        return 0, "0 min", "--:--", "--:--"

    window_td = timedelta(hours=window_hours)
    for m in models:
        try:
            m.out_of_window = (m.timestamp - first_ts) > window_td
        except Exception:
            m.out_of_window = False

    in_window = [m for m in models if not m.out_of_window]
    if not in_window:
        return 0, "0 min", "--:--", "--:--"

    newest_in = in_window[0].timestamp
    oldest_in = in_window[-1].timestamp
    if isinstance(newest_in, datetime) and isinstance(oldest_in, datetime):
        delta_minutes = int((newest_in - oldest_in).total_seconds() / 60)
        first_time = oldest_in.strftime("%H:%M")
        last_time = newest_in.strftime("%H:%M")
    else:
        delta_minutes = 0
        first_time = "--:--"
        last_time = "--:--"

    if delta_minutes >= 60:
        hours = delta_minutes // 60
        minutes_only = delta_minutes % 60
        if minutes_only:
            label = f"{hours}h {minutes_only}m"
        else:
            label = f"{hours}h"
    else:
        label = f"{delta_minutes} min"

    return delta_minutes, label, first_time, last_time


def compute_weeks_totals(weeks, groups, sunday_index=6):
    """Given the `weeks` structure (list of weeks, each a list of cell dicts)
    and the `groups` mapping (date_key -> group metadata with minutes_span),
    compute the total minutes per week and attach `week_total_minutes` to
    the Sunday's cell (index sunday_index) when applicable.

    This mutates the `weeks` structure in-place.
    """
    for week in weeks:
        total = 0
        for cell in week:
            dk = cell.get("date_key")
            if dk and dk in groups:
                try:
                    total += int(groups[dk].get("minutes_span", 0) or 0)
                except Exception:
                    continue
        # attach to the sunday cell if it exists and has a day
        if len(week) > sunday_index:
            sunday_cell = week[sunday_index]
            if sunday_cell.get("day") and total > 0:
                sunday_cell["week_total_minutes"] = total
    return weeks


def compute_groups_metadata(groups, window_hours=3):
    """Populate each group's metadata by computing its minutes span and
    first/last time strings. This mutates `groups` in-place and returns it.
    """
    for key, g in groups.items():
        try:
            rows_for_day = g.get("rows", [])
            delta_minutes, label, first_time, last_time = compute_group_time_span(rows_for_day, window_hours=window_hours)
            g["minutes_span"] = delta_minutes
            g["minutes_span_label"] = label
            g["first_time"] = first_time
            g["last_time"] = last_time
        except Exception:
            g["minutes_span"] = 0
            g["minutes_span_label"] = "0 min"
            g["first_time"] = "--:--"
            g["last_time"] = "--:--"
    return groups
