from datetime import datetime

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
    
    # Battery
    try:
        row["battery_val"] = float(row.get("battery") if row.get("battery") is not 0 else "")
    except Exception:
        row["battery_val"] = 0.0    
    if row["battery_val"] >= 75:
        row["battery_status"] = "Good"
        row["battery_class"] = "w3-lime"
    elif row["battery_val"] <= 25:
        row["battery_status"] = "Poor"
        row["battery_class"] = "w3-deep-orange"
    else:
        row["battery_status"] = "Fair"
        row["battery_class"] = "w3-amber"


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

    Returns a tuple: (minutes_span:int, minutes_span_label:str, first_time:str, last_time:str)
    Mutates rows_for_day by setting each row['out_of_window'] = True/False.
    """
    from datetime import datetime, timedelta

    # initialize
    for r in rows_for_day:
        r["out_of_window"] = False

    if not rows_for_day:
        return 0, "0 min", "--:--", "--:--"

    # rows are expected newest -> oldest; first event (chronologically oldest)
    first_ts = rows_for_day[-1].get("timestamp")
    if not isinstance(first_ts, datetime):
        return 0, "0 min", "--:--", "--:--"

    # mark out_of_window
    window_td = timedelta(hours=window_hours)
    for r in rows_for_day:
        ts = r.get("timestamp")
        try:
            r["out_of_window"] = (ts - first_ts) > window_td
        except Exception:
            r["out_of_window"] = False

    # consider only in-window events
    in_window = [r for r in rows_for_day if not r.get("out_of_window")]
    if not in_window:
        return 0, "0 min", "--:--", "--:--"

    newest_in = in_window[0].get("timestamp")
    oldest_in = in_window[-1].get("timestamp")
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
