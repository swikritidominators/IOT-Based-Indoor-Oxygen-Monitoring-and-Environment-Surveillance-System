# ============================================================
# TASK 1.5 — Read Firebase Records Back into Pandas DataFrame
# ============================================================
# HOW TO RUN:
#   python task1_5_read_to_dataframe.py
#   (Run AFTER task1_4 so there is at least one record to read)
#
# WHAT IT DOES:
#   Reads all sensor readings from Firebase, converts to a
#   pandas DataFrame, parses timestamps, and runs basic checks.
#   This is the EXACT function your ML pipeline will reuse.
#
# CONCEPT — Why .values() and not the raw dict:
#   Firebase returns a dict like:
#   { "-O9xk3abc": {"timestamp":..., "oxygen":..., ...},
#     "-O9xk3def": {"timestamp":..., "oxygen":..., ...} }
#   The keys are Firebase push-IDs (not useful to ML).
#   pd.DataFrame(raw.values()) extracts just the record dicts.
#
# EXPECTED OUTPUT:
#   Loaded 1 records from Firebase
#   Columns: ['timestamp', 'oxygen', 'temperature', 'humidity', ...]
#   DataFrame preview:
#             timestamp  oxygen  temperature  humidity
#   0  2026-06-...       20.8    24.5         55.2
#
#   Data quality check:
#     Missing values: 0
#     O2 range: 20.8 to 20.8  (expected: 19.0 to 21.5)
# ============================================================

import firebase_admin
from firebase_admin import credentials, db
import pandas as pd

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://iot-cfees-default-rtdb.asia-southeast1.firebasedatabase.app"
        })
    return db

def fetch_sensor_data(n_records=None):
    """
    Fetch sensor readings from Firebase into a DataFrame.

    Args:
        n_records: int or None. If None, fetches all records.
                   If int, fetches last N records (most recent first).

    Returns:
        pandas DataFrame with columns:
        timestamp, oxygen, temperature, humidity
        (+ occupancy_count, ac_status if present)
    """
    database = init_firebase()
    ref = database.reference("/sensors/room1/readings")

    if n_records:
        raw = ref.order_by_key().limit_to_last(n_records).get()
    else:
        raw = ref.get()

    if raw is None:
        print("WARNING: No data found in /sensors/room1/readings")
        print("Run task1_4 first to write a test record.")
        return pd.DataFrame()

    # Convert Firebase dict → list of record dicts → DataFrame
    df = pd.DataFrame(raw.values())

    # Parse timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Convert numeric columns (Firebase sometimes returns strings)
    numeric_cols = ["oxygen", "temperature", "humidity"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Optional columns — only if present
    if "occupancy_count" in df.columns:
        df["occupancy_count"] = pd.to_numeric(df["occupancy_count"], errors="coerce")
    if "ac_status" in df.columns:
        df["ac_status"] = pd.to_numeric(df["ac_status"], errors="coerce")

    return df


def run_data_quality_check(df):
    """
    Print a data quality report.
    Helps catch sensor issues early (uncalibrated O2, stuck values, etc.)
    """
    print("\n" + "=" * 50)
    print("DATA QUALITY REPORT")
    print("=" * 50)
    print(f"Total records: {len(df)}")
    print(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"\nColumns present: {list(df.columns)}")

    print(f"\nMissing values:")
    print(df.isnull().sum())

    print(f"\nValue ranges:")
    for col in ["oxygen", "temperature", "humidity"]:
        if col in df.columns:
            expected = {"oxygen": (19.0, 21.5), "temperature": (15, 40), "humidity": (20, 90)}
            lo, hi = expected[col]
            out_of_range = ((df[col] < lo) | (df[col] > hi)).sum()
            print(f"  {col}: {df[col].min():.2f} to {df[col].max():.2f}  "
                  f"(expected {lo}–{hi})  "
                  f"[{out_of_range} out-of-range values]")

    print(f"\nDescriptive statistics:")
    print(df[["oxygen", "temperature", "humidity"]].describe().round(3))


if __name__ == "__main__":
    database = init_firebase()
    print("Fetching data from Firebase...")
    df = fetch_sensor_data()

    if df.empty:
        print("No data to show. Run task1_4.py first.")
    else:
        print(f"\nLoaded {len(df)} records from Firebase")
        print(f"Columns: {list(df.columns)}")
        print(f"\nDataFrame preview:")
        print(df.to_string())
        run_data_quality_check(df)
