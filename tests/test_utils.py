import pytest
from datetime import datetime

from utils import compute_row_display_fields, compute_group_time_span, compute_weeks_totals


def test_compute_group_time_span_empty():
    rows = []
    minutes, label, first_time, last_time = compute_group_time_span(rows)
    assert minutes == 0
    assert label == "0 min"
    assert first_time == "--:--"
    assert last_time == "--:--"


def test_compute_group_time_span_basic():
    # newest -> oldest
    newest = datetime(2026, 4, 1, 9, 30, 0)
    oldest = datetime(2026, 4, 1, 8, 0, 0)
    rows = [{"timestamp": newest}, {"timestamp": oldest}]
    # convert to EventOut models using helper
    models = [compute_row_display_fields(r) for r in rows]

    minutes, label, first_time, last_time = compute_group_time_span(models)

    assert minutes == 90
    assert "1h" in label
    assert "30m" in label
    assert first_time == "08:00"
    assert last_time == "09:30"
    # ensure out_of_window flags are present and correct on models
    assert models[0].out_of_window is False
    assert models[1].out_of_window is False


def test_compute_group_time_span_out_of_window():
    # oldest at 00:00, mid at 02:00, newest at 05:00; window=3h
    newest = datetime(2026, 4, 2, 5, 0, 0)
    mid = datetime(2026, 4, 2, 2, 0, 0)
    oldest = datetime(2026, 4, 2, 0, 0, 0)
    rows = [{"timestamp": newest}, {"timestamp": mid}, {"timestamp": oldest}]
    models = [compute_row_display_fields(r) for r in rows]

    minutes, label, first_time, last_time = compute_group_time_span(models)

    # newest should be out_of_window, mid and oldest in window -> span 120 min
    assert models[0].out_of_window is True
    assert models[1].out_of_window is False
    assert models[2].out_of_window is False
    assert minutes == 120
    assert label == "2h"
    assert first_time == "00:00"
    assert last_time == "02:00"


def test_compute_weeks_totals_attach_to_sunday():
    # Build a fake groups mapping with minutes_span
    groups = {
        "2026-04-01": {"minutes_span": 30},
        "2026-04-07": {"minutes_span": 90},
    }
    # build a single week (7 cells, sunday at index 6)
    week = [
        {"day": 1, "date_key": "2026-03-30"},
        {"day": 2, "date_key": "2026-03-31"},
        {"day": 3, "date_key": "2026-04-01"},
        {"day": 4, "date_key": "2026-04-02"},
        {"day": 5, "date_key": "2026-04-03"},
        {"day": 6, "date_key": "2026-04-04"},
        {"day": 7, "date_key": "2026-04-07"},
    ]
    weeks = [week]

    compute_weeks_totals(weeks, groups)

    # Sunday is index 6 and should have week_total_minutes = 30 + 90 = 120
    assert weeks[0][6].get("week_total_minutes") == 120
