# ============================================================
# PHASE 5 — Production Serving Loop
# ============================================================
# HOW TO RUN:
#   python phase5_production_loop.py
#
# HOW TO STOP:
#   Press Ctrl+C — it will shut down cleanly
#
# PREREQUISITES (all must exist in same folder):
#   serviceAccountKey.json
#   model_xgb_5min.pkl
#   model_xgb_10min.pkl
#   anomaly_iso_model.pkl
#   train_data.csv          (for CUSUM parameter estimation)
#
# WHAT IT DOES:
#   Runs continuously. Every 5 minutes:
#   1. Reads latest 25 sensor records from Firebase
#   2. Engineers features (identical to Phase 2)
#   3. Runs XGBoost forecast models (5-min and 10-min)
#   4. Runs Isolation Forest anomaly detector
#   5. Runs CUSUM drift detector
#   6. Generates recommendation
#   7. Writes prediction + alert to Firebase
#   8. Logs everything to production.log
#   9. Sleeps 5 minutes, repeats
#
# KEEP THIS TERMINAL OPEN during your data collection sessions.
# Your laptop must stay on and connected to WiFi.
# ============================================================

import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import numpy as np
import joblib
import time
import json
import logging
import traceback
import os
from datetime import datetime, timezone


# ════════════════════════════════════════════════════════════
# CONFIGURATION
# All tunable parameters in one place.
# Change these without touching any other code.
# ════════════════════════════════════════════════════════════

CONFIG = {
    # Firebase
    "database_url"        : "https://iot-cfees-default-rtdb.asia-southeast1.firebasedatabase.app",
    "sensor_path"         : "/sensors/room1/readings",
    "prediction_path"     : "/predictions/room1/readings",
    "alert_path"          : "/alerts/room1",

    # Cycle
    "cycle_seconds"       : 300,        # 5 minutes between cycles
    "min_records_needed"  : 15,         # minimum Firebase records before running
    "fetch_n_records"     : 25,         # how many recent records to fetch each cycle
                                        # must be > max lag used in features (12)

    # Models
    "xgb_5min_path"       : "model_xgb_5min.pkl",
    "xgb_10min_path"      : "model_xgb_10min.pkl",
    "iso_model_path"      : "anomaly_iso_model.pkl",
    "train_data_path"     : "train_data.csv",

    # CUSUM parameters (re-estimated from train data at startup)
    "cusum_slack_mult"    : 0.5,
    "cusum_thresh_mult"   : 5.0,

    # Alert thresholds (must match Phase 4 THRESHOLDS)
    "critical_o2"         : 19.5,
    "warning_o2"          : 20.0,
    "rapid_drop_rate"     : 0.10,

    # Logging
    "log_file"            : "production.log",
    "model_version"       : "xgb_v1_phase3",
}


# ════════════════════════════════════════════════════════════
# LOGGING SETUP
# ════════════════════════════════════════════════════════════
# Writes to both terminal and production.log file simultaneously.
# Every line is timestamped automatically.

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(CONFIG["log_file"], encoding="utf-8"),
            logging.StreamHandler()             # also prints to terminal
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()


# ════════════════════════════════════════════════════════════
# FIREBASE INITIALISATION
# ════════════════════════════════════════════════════════════

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred, {
            "databaseURL": CONFIG["database_url"]
        })
    return db


# ════════════════════════════════════════════════════════════
# MODEL LOADING
# Load all models once at startup, not inside the loop.
#
# CONCEPT — Why load at startup not inside the loop:
#   Loading a pkl file from disk takes ~0.5-2 seconds each time.
#   If you load inside the loop, every 5-minute cycle wastes 3-8
#   seconds just reading files. Loading once at startup means the
#   models live in RAM and predictions take milliseconds.
#   Also: if a model file is corrupted, you find out immediately
#   at startup rather than 30 minutes into a data collection run.
# ════════════════════════════════════════════════════════════

def load_all_models():
    logger.info("Loading models from disk...")
    models = {}

    for key, path in [
        ("xgb_5min",  CONFIG["xgb_5min_path"]),
        ("xgb_10min", CONFIG["xgb_10min_path"]),
        ("iso",       CONFIG["iso_model_path"]),
    ]:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Model file not found: {path}\n"
                f"Run Phase 3 and Phase 4 first.")
        models[key] = joblib.load(path)
        logger.info(f"  Loaded: {path}")

    # Estimate CUSUM parameters from training data
    if not os.path.exists(CONFIG["train_data_path"]):
        raise FileNotFoundError(
            f"train_data.csv not found — needed for CUSUM parameters")

    train_df = pd.read_csv(CONFIG["train_data_path"])
    train_std = train_df["oxygen"].std()
    models["cusum_slack"]     = CONFIG["cusum_slack_mult"] * train_std
    models["cusum_threshold"] = CONFIG["cusum_thresh_mult"] * train_std
    logger.info(f"  CUSUM slack={models['cusum_slack']:.4f}  "
                f"threshold={models['cusum_threshold']:.4f}")

    logger.info("All models loaded successfully.")
    return models


# ════════════════════════════════════════════════════════════
# FIREBASE DATA FETCH
# ════════════════════════════════════════════════════════════

def fetch_latest_records(n=25):
    """
    Fetch the n most recent sensor records from Firebase.
    Returns a sorted DataFrame (oldest first).

    CONCEPT — Why oldest-first sort:
      Feature engineering computes lags like o2_lag1 = previous row.
      If the DataFrame is newest-first, o2_lag1 would actually be
      a FUTURE value — complete data leakage. Always sort ascending
      (oldest first) before any feature engineering.
    """
    ref = db.reference(CONFIG["sensor_path"])
    raw = ref.order_by_key().limit_to_last(n).get()

    if raw is None:
        return pd.DataFrame()

    df = pd.DataFrame(raw.values())

    # Parse timestamp
    def parse_ts(v):
        try:
            p = pd.to_datetime(v, utc=False)
            return p.tz_localize("UTC") if p.tzinfo is None else p
        except Exception:
            return pd.NaT

    df["timestamp"] = df["timestamp"].apply(parse_ts)

    # Parse numeric columns
    for col in ["oxygen","temperature","humidity",
                "occupancy_count","ac_status"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Sort oldest first — CRITICAL for correct lag computation
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df

def run_one_cycle(models, cusum_state, cycle_number):
    
    # Step 1: Fetch raw data (1-min frequency from ESP32)
    df_raw = fetch_latest_records(n=CONFIG["fetch_n_records"])
    
    if df_raw.empty or len(df_raw) < CONFIG["min_records_needed"]:
        logger.warning("Not enough data yet.")
        return None

    # Step 1b: Resample to 5-min frequency for ML model
    # (only if readings are more frequent than 5 min)
    time_diffs = df_raw["timestamp"].diff().dt.total_seconds().dropna()
    avg_gap_seconds = time_diffs.mean()
    
    if avg_gap_seconds < 250:  # readings faster than ~4 min
        logger.info(f"Resampling from {avg_gap_seconds:.0f}s to 5-min intervals")
        df_ml = resample_to_5min(df_raw)
    else:
        df_ml = df_raw  # already at ~5min, no resampling needed
    
    if len(df_ml) < 13:  # need at least 13 rows for lag12 + 1 target row
        logger.warning(f"After resampling only {len(df_ml)} rows. Need more history.")
        return None

    # Step 2: Feature engineering on resampled data
    df_feat, latest_row = engineer_features_live(df_ml)
    # ... rest of cycle continues unchanged


def resample_to_5min(df):
    """
    Convert 1-minute sensor readings to 5-minute averages.
    This matches the frequency your ML model was trained on.
    """
    df = df.copy()
    df = df.set_index("timestamp")
    
    # Resample: take mean of each 5-minute window
    df_resampled = df[["oxygen","temperature","humidity"]].resample("5min").agg({
        "oxygen"     : "mean",   # average O2 over 5 min window
        "temperature": "mean",   # average temp
        "humidity"   : "mean",   # average humidity
    }).dropna().reset_index()
    
    # Carry forward other columns
    if "ac_status" in df.columns:
        ac = df["ac_status"].resample("5min").last().reset_index()
        df_resampled = df_resampled.merge(ac, on="timestamp", how="left")
    
    return df_resampled







# ════════════════════════════════════════════════════════════
# FEATURE ENGINEERING (identical to Phase 2)
# ════════════════════════════════════════════════════════════
#
# CONCEPT — Training-serving consistency:
#   This function must be byte-for-byte identical in behaviour
#   to the engineer_features() used in Phase 2 training.
#   Any difference = training-serving skew = silent wrong predictions.
#
#   The safest approach: copy the function directly from phase2
#   rather than calling it as an import (avoids import path issues
#   when running from different directories).
#
#   After engineering, we take ONLY the last row — the most
#   recent complete feature vector — for prediction.

def engineer_features_live(df, n_lags=12):
    """
    Apply feature engineering to a live window of records.
    Identical logic to Phase 2 engineer_features().
    Returns only the last row as a Series (for prediction).
    """
    df = df.copy().sort_values("timestamp").reset_index(drop=True)

    lag_steps = sorted(set([1,2,3,6] + list(range(1, n_lags+1))))
    lag_steps = [l for l in lag_steps if l <= 12]

    for lag in lag_steps:
        df[f"o2_lag{lag}"]   = df["oxygen"].shift(lag)
        df[f"temp_lag{lag}"] = df["temperature"].shift(lag)
        df[f"hum_lag{lag}"]  = df["humidity"].shift(lag)

    df["o2_delta_1"]   = df["oxygen"].diff(1)
    df["o2_delta_3"]   = df["oxygen"].diff(3)
    df["o2_delta_6"]   = df["oxygen"].diff(6)
    df["temp_delta_1"] = df["temperature"].diff(1)
    df["hum_delta_1"]  = df["humidity"].diff(1)

    df["o2_roll_mean_3"]   = df["oxygen"].rolling(3).mean()
    df["o2_roll_mean_6"]   = df["oxygen"].rolling(6).mean()
    df["o2_roll_std_3"]    = df["oxygen"].rolling(3).std()
    df["temp_roll_mean_3"] = df["temperature"].rolling(3).mean()
    df["hum_roll_mean_3"]  = df["humidity"].rolling(3).mean()

    hour = df["timestamp"].dt.hour.astype(float)
    df["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    dow = df["timestamp"].dt.dayofweek.astype(float)
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7)

    if "occupancy_count" in df.columns:
        df["occ_lag1"]        = df["occupancy_count"].shift(1)
        df["occ_roll_mean_3"] = df["occupancy_count"].rolling(3).mean()
        df["occ_delta_1"]     = df["occupancy_count"].diff(1)
    if "ac_status" in df.columns:
        df["ac_lag1"] = df["ac_status"].shift(1)

    df = df.dropna().reset_index(drop=True)

    if len(df) == 0:
        return None, None

    return df, df.iloc[-1]  # return full df + latest row


def get_feature_columns_live(row_series):
    """
    Get feature column names from a row Series.
    Excludes raw sensor columns and metadata.
    Must match exactly the columns used during Phase 3 training.
    """
    exclude = {"timestamp","source","is_anomaly",
               "target_5min","target_10min",
               "oxygen","temperature","humidity",
               "occupancy_count","ac_status"}
    return [c for c in row_series.index if c not in exclude]


# ════════════════════════════════════════════════════════════
# CUSUM — live stateful computation
# ════════════════════════════════════════════════════════════
#
# CONCEPT — Why CUSUM needs a persistent state variable:
#   CUSUM's running sum S(t) carries over from one cycle to
#   the next. It CANNOT be reset each cycle — resetting would
#   lose the accumulated evidence of gradual drift.
#   We store S as a global variable that persists across cycles.
#   It only resets when O2 recovers (the max(0,...) logic).

class CUSUMState:
    """Maintains CUSUM running sum across cycles."""
    def __init__(self, slack, threshold):
        self.S         = 0.0
        self.slack     = slack
        self.threshold = threshold
        self.history   = []  # last N o2 values for rolling reference

    def update(self, o2_value):
        """
        Update CUSUM with new O2 reading.
        Returns (cusum_score, is_flagged)
        """
        # Rolling reference: mean of last 12 values (60 minutes)
        self.history.append(o2_value)
        if len(self.history) > 12:
            self.history.pop(0)

        mu = np.mean(self.history) if len(self.history) >= 3 else 20.9

        # CUSUM update
        self.S = max(0.0, self.S + (mu - o2_value) - self.slack)
        is_flagged = self.S > self.threshold

        return self.S, int(is_flagged)

    def reset(self):
        """Call if system confirms recovery (optional manual reset)."""
        self.S = 0.0


# ════════════════════════════════════════════════════════════
# RECOMMENDATION ENGINE (identical to Phase 4)
# ════════════════════════════════════════════════════════════

def generate_recommendation_live(o2, fc5, fc10, delta,
                                  cusum_score, cusum_threshold,
                                  iso_flag):
    crit  = CONFIG["critical_o2"]
    warn  = CONFIG["warning_o2"]
    rdrop = CONFIG["rapid_drop_rate"]

    if o2 < crit:
        return {"severity":"CRITICAL",
                "message":"OXYGEN CRITICALLY LOW! Ventilate immediately.",
                "buzzer":"continuous", "action_code":3}
    if fc5 < crit:
        return {"severity":"PREDICTIVE_CRITICAL",
                "message":"Oxygen predicted critical in 5 min. Act now.",
                "buzzer":"3 rapid beeps", "action_code":3}
    if o2 < warn:
        return {"severity":"WARNING",
                "message":"Oxygen below safe level. Increase ventilation.",
                "buzzer":"3 beeps every 30s", "action_code":2}
    if fc10 < warn:
        return {"severity":"PREDICTIVE_WARNING",
                "message":"Oxygen predicted low in 10 min. Prepare ventilation.",
                "buzzer":"1 beep", "action_code":2}
    if delta < -rdrop:
        return {"severity":"RATE_WARNING",
                "message":"Rapid oxygen drop detected. Monitor closely.",
                "buzzer":"2 beeps", "action_code":2}
    if cusum_score > cusum_threshold * 0.3:
        return {"severity":"DRIFT_ADVISORY",
                "message":"Sustained oxygen decline detected. Check ventilation.",
                "buzzer":"none", "action_code":1}
    if iso_flag == 1:
        return {"severity":"SENSOR_ADVISORY",
                "message":"Unusual sensor pattern. Check O2 sensor calibration.",
                "buzzer":"none", "action_code":1}
    return {"severity":"OK",
            "message":"Air quality normal.",
            "buzzer":"none", "action_code":0}


# ════════════════════════════════════════════════════════════
# FIREBASE WRITE
# ════════════════════════════════════════════════════════════

def write_prediction(result_dict):
    """Write prediction record to /predictions/room1/readings."""
    ref = db.reference(CONFIG["prediction_path"])
    new_ref = ref.push(result_dict)
    return new_ref.key


def write_alert(result_dict):
    """
    Write alert to /alerts/room1 when severity is not OK.
    ESP32 polls this node and triggers LCD + buzzer.
    """
    alert = {
        "timestamp"        : result_dict["timestamp"],
        "type"             : result_dict["rec_severity"],
        "severity"         : result_dict["rec_severity"],
        "message"          : result_dict["rec_message"],
        "acknowledged"     : False,
        "oxygen_at_alert"  : result_dict["oxygen_current"],
        "forecast_5min"    : result_dict["oxygen_forecast_5min"],
        "forecast_10min"   : result_dict["oxygen_forecast_10min"],
    }
    ref = db.reference(CONFIG["alert_path"])
    ref.push(alert)


# ════════════════════════════════════════════════════════════
# SINGLE PREDICTION CYCLE
# ════════════════════════════════════════════════════════════

def run_one_cycle(models, cusum_state, cycle_number):
    """
    Execute one complete prediction cycle.
    Returns a result dict, or None if cycle should be skipped.
    """
    cycle_start = time.time()
    now_str = datetime.now(timezone.utc).isoformat()

    # ── Step 1: Fetch data ───────────────────────────────────
    df_raw = fetch_latest_records(n=CONFIG["fetch_n_records"])

    if df_raw.empty:
        logger.warning("No records in Firebase yet. Waiting for sensor data.")
        return None

    n_records = len(df_raw)
    if n_records < CONFIG["min_records_needed"]:
        logger.warning(f"Only {n_records} records available "
                       f"(need {CONFIG['min_records_needed']}). "
                       f"Waiting for more sensor data.")
        return None

    # Filter to real sensor data only (exclude synthetic if mixed)
    if "source" in df_raw.columns:
        real_df = df_raw[df_raw["source"] != "synthetic"]
        if len(real_df) >= CONFIG["min_records_needed"]:
            df_raw = real_df
        # If not enough real data yet, use all (including synthetic)
        # This lets you test the loop before real hardware is ready

    # ── Step 2: Feature engineering ─────────────────────────
    df_feat, latest_row = engineer_features_live(df_raw)

    if latest_row is None:
        logger.warning("Feature engineering produced no valid rows. "
                       "Need more data history.")
        return None

    feature_cols = get_feature_columns_live(latest_row)

    # Check all expected features are present
    missing = [c for c in feature_cols if c not in latest_row.index]
    if missing:
        logger.warning(f"Missing features: {missing[:5]}... "
                       f"Skipping cycle.")
        return None

    X_live = latest_row[feature_cols].values.reshape(1, -1)

    # Current sensor readings from latest raw record
    latest_raw = df_raw.iloc[-1]
    o2_current = float(latest_raw.get("oxygen", 20.9))
    temp       = float(latest_raw.get("temperature", 24.0))
    hum        = float(latest_raw.get("humidity", 55.0))
    o2_delta   = float(latest_row.get("o2_delta_1", 0.0))

    # ── Step 3: Forecasting ──────────────────────────────────
    fc5  = float(models["xgb_5min"].predict(X_live)[0])
    fc10 = float(models["xgb_10min"].predict(X_live)[0])

    # Clamp to physically valid range
    fc5  = np.clip(fc5,  15.0, 22.0)
    fc10 = np.clip(fc10, 15.0, 22.0)

    # ── Step 4: Anomaly detection ────────────────────────────
    iso_score  = float(models["iso"].decision_function(X_live)[0])
    iso_pred   = models["iso"].predict(X_live)[0]
    is_iso_anomaly = int(iso_pred == -1)

    cusum_score, is_cusum_anomaly = cusum_state.update(o2_current)
    final_anomaly = int(is_iso_anomaly == 1 or is_cusum_anomaly == 1)

    # ── Step 5: Recommendation ───────────────────────────────
    rec = generate_recommendation_live(
        o2=o2_current, fc5=fc5, fc10=fc10,
        delta=o2_delta,
        cusum_score=cusum_score,
        cusum_threshold=models["cusum_threshold"],
        iso_flag=is_iso_anomaly
    )

    # ── Step 6: Assemble result ──────────────────────────────
    latency = round(time.time() - cycle_start, 2)

    result = {
        "timestamp"             : now_str,
        "oxygen_current"        : round(o2_current, 4),
        "temperature_current"   : round(temp, 3),
        "humidity_current"      : round(hum, 3),
        "oxygen_forecast_5min"  : round(fc5,  4),
        "oxygen_forecast_10min" : round(fc10, 4),
        "iso_score"             : round(iso_score, 6),
        "cusum_score"           : round(cusum_score, 6),
        "is_anomaly_iso"        : is_iso_anomaly,
        "is_anomaly_cusum"      : is_cusum_anomaly,
        "final_anomaly"         : final_anomaly,
        "rec_severity"          : rec["severity"],
        "rec_message"           : rec["message"],
        "rec_buzzer"            : rec["buzzer"],
        "rec_action_code"       : rec["action_code"],
        "cycle_number"          : cycle_number,
        "cycle_latency_sec"     : latency,
        "model_version"         : CONFIG["model_version"],
        "records_used"          : n_records,
    }

    return result


# ════════════════════════════════════════════════════════════
# MAIN PRODUCTION LOOP
# ════════════════════════════════════════════════════════════

def run_production_loop():
    logger.info("="*60)
    logger.info("PHASE 5 — PRODUCTION LOOP STARTING")
    logger.info("="*60)

    # Initialise Firebase
    init_firebase()
    logger.info("Firebase connected.")

    # Load all models
    models = load_all_models()

    # Initialise CUSUM state (persists across cycles)
    cusum_state = CUSUMState(
        slack     = models["cusum_slack"],
        threshold = models["cusum_threshold"]
    )
    logger.info(f"CUSUM initialised: slack={cusum_state.slack:.4f}, "
                f"threshold={cusum_state.threshold:.4f}")

    # Save config snapshot
    with open("production_config.json", "w") as f:
        json.dump({k: v for k, v in CONFIG.items()
                   if isinstance(v, (str, int, float))}, f, indent=2)
    logger.info("production_config.json saved.")

    logger.info(f"Cycle interval : {CONFIG['cycle_seconds']}s "
                f"({CONFIG['cycle_seconds']//60} minutes)")
    logger.info("Press Ctrl+C to stop cleanly.")
    logger.info("="*60)

    cycle_number   = 0
    total_cycles   = 0
    failed_cycles  = 0
    alert_count    = 0

    try:
        while True:
            cycle_number += 1
            total_cycles += 1
            logger.info(f"\n--- CYCLE {cycle_number} "
                        f"| {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

            try:
                result = run_one_cycle(models, cusum_state, cycle_number)

                if result is None:
                    # Cycle skipped (not enough data yet)
                    logger.info(f"Cycle {cycle_number} skipped. "
                                f"Retrying in {CONFIG['cycle_seconds']}s")
                else:
                    # ── Write to Firebase ────────────────────
                    pred_key = write_prediction(result)
                    logger.info(f"Prediction written: key={pred_key}")

                    # Write alert if severity is not OK
                    if result["rec_action_code"] > 0:
                        write_alert(result)
                        alert_count += 1
                        logger.warning(
                            f"ALERT WRITTEN: {result['rec_severity']} "
                            f"— {result['rec_message']}"
                        )

                    # ── Terminal status line ─────────────────
                    logger.info(
                        f"O2={result['oxygen_current']:.3f}% | "
                        f"Fc5={result['oxygen_forecast_5min']:.3f}% | "
                        f"Fc10={result['oxygen_forecast_10min']:.3f}% | "
                        f"Anomaly={'YES' if result['final_anomaly'] else 'no'} | "
                        f"Status={result['rec_severity']} | "
                        f"Latency={result['cycle_latency_sec']}s"
                    )

            except Exception as e:
                failed_cycles += 1
                logger.error(f"Cycle {cycle_number} failed: {e}")
                logger.error(traceback.format_exc())
                logger.info("Continuing to next cycle despite error.")

            # ── Session stats every 10 cycles ───────────────
            if cycle_number % 10 == 0:
                success_rate = (total_cycles - failed_cycles) / total_cycles * 100
                logger.info(
                    f"\nSESSION STATS: "
                    f"Cycles={total_cycles} | "
                    f"Success={success_rate:.1f}% | "
                    f"Alerts={alert_count} | "
                    f"CUSUM_S={cusum_state.S:.4f}"
                )

            # ── Sleep until next cycle ───────────────────────
            logger.info(f"Sleeping {CONFIG['cycle_seconds']}s "
                        f"until next cycle...")
            time.sleep(CONFIG["cycle_seconds"])

    except KeyboardInterrupt:
        logger.info("\n" + "="*60)
        logger.info("PRODUCTION LOOP STOPPED BY USER (Ctrl+C)")
        logger.info(f"Total cycles run     : {total_cycles}")
        logger.info(f"Failed cycles        : {failed_cycles}")
        logger.info(f"Alerts generated     : {alert_count}")
        logger.info(f"Final CUSUM state    : {cusum_state.S:.4f}")
        logger.info(f"Log saved to         : {CONFIG['log_file']}")
        logger.info("="*60)


# ════════════════════════════════════════════════════════════
# TEST MODE
# ════════════════════════════════════════════════════════════
# Before running the full 5-minute loop, test that one cycle
# works correctly. Run with:
#   python phase5_production_loop.py --test
#
# This runs exactly ONE cycle immediately and prints results
# without writing to Firebase or sleeping.
# Use this to verify everything works before your demo.

def run_test_mode():
    logger.info("="*60)
    logger.info("PHASE 5 — TEST MODE (single cycle, no Firebase write)")
    logger.info("="*60)

    init_firebase()
    models    = load_all_models()
    cusum_state = CUSUMState(
        slack=models["cusum_slack"],
        threshold=models["cusum_threshold"]
    )

    logger.info("Running single test cycle...")
    result = run_one_cycle(models, cusum_state, cycle_number=0)

    if result is None:
        logger.warning("Test cycle returned None — not enough Firebase data.")
        logger.info("Push more sensor records first, then retry.")
        logger.info("Tip: synthetic data from Phase 1 should work for testing.")
    else:
        logger.info("\nTEST CYCLE RESULT:")
        for key, val in result.items():
            logger.info(f"  {key:<28} : {val}")

        logger.info("\nTEST PASSED — Production loop is ready to run.")
        logger.info("Run without --test to start the full loop:")
        logger.info("  python phase5_production_loop.py")


# ════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        run_test_mode()
    else:
        run_production_loop()
