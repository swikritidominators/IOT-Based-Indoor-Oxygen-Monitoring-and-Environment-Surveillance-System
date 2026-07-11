# ============================================================
# config.py — Central configuration for entire ML project
# ============================================================
# USAGE: Import this in every script instead of hardcoding
#   from config import FIREBASE_URL, DB_PATHS, THRESHOLDS
#
# WHEN TO UPDATE:
#   - Firebase URL changed        → update FIREBASE_URL
#   - New service key             → update KEY_PATH
#   - Room changed                → update ROOM_ID
#   - Thresholds need tuning      → update THRESHOLDS
#   - Adding real data            → update DATA_SOURCE_FILTER
# ============================================================

import os

# ── Firebase ─────────────────────────────────────────────────
FIREBASE_URL = "https://iot-cfees-default-rtdb.asia-southeast1.firebasedatabase.app"
KEY_PATH     = "serviceAccountKey.json"   # keep this file OUT of git

# ── Room identifier ──────────────────────────────────────────
ROOM_ID = "room1"

# ── Firebase paths (auto-built from ROOM_ID) ─────────────────
DB_PATHS = {
    "sensors"     : f"/sensors/{ROOM_ID}/readings",
    "predictions" : f"/predictions/{ROOM_ID}/readings",
    "alerts"      : f"/alerts/{ROOM_ID}",
    "occupancy"   : f"/occupancy/{ROOM_ID}/readings",
}

# ── Data source filter ────────────────────────────────────────
# Controls which records are used for ML training/inference
# Stage 1 (synthetic only):   ["synthetic"]
# Stage 2 (mixed):            ["synthetic", "esp32_main_01"]
# Stage 3 (real only):        ["esp32_main_01"]
# None = use all records regardless of source
DATA_SOURCE_FILTER = ["synthetic"]      # ← update as real data arrives


'''
# Change from:
DATA_SOURCE_FILTER = ["synthetic"]

# To (mixed training - first week of real data):
DATA_SOURCE_FILTER = ["synthetic", "esp32_main_01"]

# To (real only - final paper results):
DATA_SOURCE_FILTER = ["esp32_main_01"]
'''

# ESP32 device ID (must match what the hardware sends)
ESP32_DEVICE_ID = "esp32_main_01"

# ── ML model paths ────────────────────────────────────────────
MODEL_PATHS = {
    "xgb_5min"  : "model_xgb_5min.pkl",
    "xgb_10min" : "model_xgb_10min.pkl",
    "rf_5min"   : "model_rf_5min.pkl",
    "iso"       : "anomaly_iso_model.pkl",
    "scaler"    : "feature_scaler.pkl",
}

# ── Data files ────────────────────────────────────────────────
DATA_FILES = {
    "synthetic"     : "synthetic_data.csv",
    "featured"      : "featured_data.csv",
    "train"         : "train_data.csv",
    "test"          : "test_data.csv",
    "phase4_results": "phase4_results.csv",
}

# ── Sampling ──────────────────────────────────────────────────
FREQ_MINUTES     = 5      # sensor reading frequency
FETCH_N_RECORDS  = 25     # records to fetch per production cycle
MIN_RECORDS      = 15     # minimum before running ML

# ── O2 thresholds ─────────────────────────────────────────────
# Based on OSHA 1910.146 and physiological literature
THRESHOLDS = {
    "o2_critical"    : 19.5,   # OSHA oxygen-deficient threshold
    "o2_warning"     : 20.0,   # early warning — cognitive effects begin
    "o2_normal"      : 20.5,   # lower bound of normal
    "o2_atmospheric" : 20.946, # NIST standard atmospheric O2
    "rapid_drop_rate": 0.10,   # % O2 per 5-min interval
}

# ── Anomaly detection ─────────────────────────────────────────
ANOMALY = {
    "iso_contamination"  : 0.05,
    "cusum_slack_mult"   : 0.5,
    "cusum_thresh_mult"  : 5.0,
}

# ── Production loop ───────────────────────────────────────────
PRODUCTION = {
    "cycle_seconds" : 300,          # 5 minutes
    "log_file"      : "production.log",
    "model_version" : "v1_synthetic",  # update when retrained on real data
}

# ── Synthetic data generation ─────────────────────────────────
SYNTHETIC = {
    "n_hours"       : 180,
    "freq_min"      : 5,
    "room_volume_m3": 45.0,
    "k"             : 0.015,    # depletion constant (calibrate from real data)
    "start_date"    : "2026-06-01 08:00:00",
}

# ── Validation helper ─────────────────────────────────────────
def validate_config():
    """Check all required files exist before running."""
    issues = []
    if not os.path.exists(KEY_PATH):
        issues.append(f"Service account key not found: {KEY_PATH}")
    if issues:
        print("CONFIG ISSUES:")
        for i in issues:
            print(f"  - {i}")
        return False
    print(f"Config OK — Firebase: {FIREBASE_URL}")
    print(f"Data filter: {DATA_SOURCE_FILTER}")
    return True

if __name__ == "__main__":
    validate_config()
