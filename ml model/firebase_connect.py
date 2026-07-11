# ============================================================
# firebase_connect.py — Single reusable Firebase connection
# ============================================================
# USAGE: Import in any script that needs Firebase
#   from firebase_connect import init_firebase, get_ref, fetch_sensor_data
#
# This replaces the repeated init code in every phase file.
# All scripts now import from here — change URL in config.py
# and it updates everywhere automatically.
# ============================================================

import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import numpy as np
from config import FIREBASE_URL, KEY_PATH, DB_PATHS, DATA_SOURCE_FILTER


def init_firebase():
    """
    Initialise Firebase app. Safe to call multiple times —
    checks if already initialised before creating a new app.
    """
    if not firebase_admin._apps:
        cred = credentials.Certificate(KEY_PATH)
        firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_URL})
    return db


def get_ref(path):
    """Get a Firebase database reference at the given path."""
    init_firebase()
    return db.reference(path)


def parse_timestamp_robust(ts_value):
    """Parse timestamp regardless of format or timezone."""
    try:
        parsed = pd.to_datetime(ts_value, utc=False)
        if parsed.tzinfo is None:
            parsed = parsed.tz_localize("UTC")
        return parsed
    except Exception:
        return pd.NaT


def fetch_sensor_data(n_records=None, source_filter=None):
    """
    Fetch sensor readings from Firebase into a clean DataFrame.

    Args:
        n_records     : int or None. Fetch last N records (None = all).
        source_filter : list of source values to include.
                        None = use DATA_SOURCE_FILTER from config.
                        []   = fetch all records regardless of source.

    Returns:
        Sorted DataFrame (oldest first) with parsed types.
    """
    init_firebase()
    ref = db.reference(DB_PATHS["sensors"])

    if n_records:
        raw = ref.order_by_key().limit_to_last(n_records).get()
    else:
        raw = ref.get()

    if raw is None:
        return pd.DataFrame()

    df = pd.DataFrame(raw.values())
    df["timestamp"] = df["timestamp"].apply(parse_timestamp_robust)

    for col in ["oxygen","temperature","humidity",
                "occupancy_count","ac_status","is_anomaly"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("timestamp").reset_index(drop=True)

    # Apply source filter
    filter_list = source_filter if source_filter is not None else DATA_SOURCE_FILTER
    if filter_list and "source" in df.columns:
        df = df[df["source"].isin(filter_list)].reset_index(drop=True)

    return df

'''
#this is new source filter - This way if source is missing or has a typo (e.g.we writes 
# "esp32_01" instead of "esp32_main_01"), you get a clear warning message instead of silent data loss.
# Apply source filter
filter_list = source_filter if source_filter is not None else DATA_SOURCE_FILTER
if filter_list and "source" in df.columns:
    df_filtered = df[df["source"].isin(filter_list)].reset_index(drop=True)
    
    # Safety check — warn if a lot of records got filtered out
    dropped = len(df) - len(df_filtered)
    if dropped > 0:
        unknown_sources = df[~df["source"].isin(filter_list)]["source"].unique()
        print(f"WARNING: {dropped} records excluded by source filter.")
        print(f"Unknown source values found: {unknown_sources}")
        print(f"If ESP32 data is missing, check DEVICE_ID in firmware matches config.py")
    
    df = df_filtered
'''


def write_prediction(record_dict):
    """Write a prediction record to /predictions/room1/readings."""
    init_firebase()
    ref = db.reference(DB_PATHS["predictions"])
    return ref.push(record_dict).key


def write_alert(alert_dict):
    """Write an alert record to /alerts/room1."""
    init_firebase()
    ref = db.reference(DB_PATHS["alerts"])
    return ref.push(alert_dict).key


def test_connection():
    """Quick connection test — run this after updating credentials."""
    import json
    init_firebase()
    root = db.reference("/").get()
    print("Firebase connected successfully!")
    print(f"URL: {FIREBASE_URL}")
    print(f"Database contents:")
    print(json.dumps(root, indent=2, default=str))
    return True


if __name__ == "__main__":
    test_connection()
