import sys
import os
import pytest
# ensure project root is on sys.path so local modules (db, utils) can be imported when running pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db import verify_time_zone, fetch_rows_from_db, ensure_schema


def test_verify_time_zone_runs():
    # Should not raise; prints diagnostic information.
    verify_time_zone()


def test_fetch_rows_returns_list():
    # Ensure schema exists first (idempotent)
    ensure_schema()
    rows = fetch_rows_from_db(limit=1)
    assert isinstance(rows, list)
