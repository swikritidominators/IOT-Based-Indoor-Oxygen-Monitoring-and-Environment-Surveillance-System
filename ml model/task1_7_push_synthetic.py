# ============================================================
# TASK 1.7 — Push Synthetic Data to Firebase
# ============================================================
# HOW TO RUN:
#   python task1_7_push_synthetic.py
#   (Run AFTER task1_6 — needs synthetic_data.csv to exist)
#
# WHAT IT DOES:
#   Uploads your synthetic_data.csv to Firebase under
#   /sensors/room1/readings in batches.
#   Each record is pushed with its own auto-generated key.
#
# CONCEPT — Why batch writes instead of one-by-one:
#   Pushing 2160 records one at a time = 2160 HTTP requests.
#   Firebase Admin SDK supports update() which sends multiple
#   key-value pairs in a single request — much faster.
#   We batch in groups of 100 to stay within request size limits.
#
# HOW LONG IT TAKES:
#   ~2160 records in batches of 100 = ~22 batches
#   Expect 30-90 seconds depending on network speed.
#
# EXPECTED OUTPUT:
#   Pushing 2160 synthetic records to Firebase...
#   Batch 1/22 (records 1-100)... done
#   Batch 2/22 (records 101-200)... done
#   ...
#   All records pushed successfully!
#   Total pushed: 2160
# ============================================================

import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import json
import time
import math

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://iot-cfees-default-rtdb.asia-southeast1.firebasedatabase.app"
        })
    return db


def push_dataframe_to_firebase(df: pd.DataFrame,
                                firebase_path: str = "/sensors/room1/readings",
                                batch_size: int = 100,
                                delay_sec: float = 0.3):
    """
    Push a DataFrame to Firebase in batches.

    Args:
        df          : DataFrame to push. Each row becomes one record.
        firebase_path: Firebase path to write to.
        batch_size  : Number of records per batch request.
        delay_sec   : Delay between batches (prevents rate limit errors).
    """
    database = init_firebase()
    ref = database.reference(firebase_path)

    total = len(df)
    n_batches = math.ceil(total / batch_size)
    total_pushed = 0

    print(f"Pushing {total} records to Firebase path: {firebase_path}")
    print(f"Batch size: {batch_size} | Total batches: {n_batches}")
    print()

    for batch_num in range(n_batches):
        start = batch_num * batch_size
        end = min(start + batch_size, total)
        batch_df = df.iloc[start:end]

        # Build a dict of {auto_key: record_dict} for batch update
        batch_data = {}
        for _, row in batch_df.iterrows():
            # Convert row to dict, handle non-serializable types
            record = {}
            for col, val in row.items():
                if pd.isna(val):
                    continue  # skip NaN values — Firebase doesn't accept them
                if hasattr(val, 'isoformat'):  # datetime
                    record[col] = val.isoformat()
                elif isinstance(val, (int, float)):
                    record[col] = round(float(val), 6)
                else:
                    record[col] = str(val)

            # Push individual record to get a Firebase auto-key
            new_ref = ref.push(record)
            batch_data[new_ref.key] = record
            total_pushed += 1

        print(f"  Batch {batch_num+1}/{n_batches} "
              f"(records {start+1}–{end})... done [{total_pushed} total]")
        time.sleep(delay_sec)

    return total_pushed


if __name__ == "__main__":
    # Load the CSV generated in task1_6
    try:
        df = pd.read_csv("synthetic_data.csv")
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        print(f"Loaded {len(df)} records from synthetic_data.csv")
        print(f"Columns: {list(df.columns)}")
        print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    except FileNotFoundError:
        print("ERROR: synthetic_data.csv not found.")
        print("Run task1_6_synthetic_generator.py first.")
        exit(1)

    # Ask user to confirm before pushing (safety check)
    print(f"\nAbout to push {len(df)} records to Firebase.")
    print("This will ADD to existing data (not overwrite).")
    confirm = input("Type 'yes' to continue: ").strip().lower()
    if confirm != "yes":
        print("Cancelled.")
        exit(0)

    start_time = time.time()
    total = push_dataframe_to_firebase(
        df,
        firebase_path="/sensors/room1/readings",
        batch_size=100,
        delay_sec=0.2
    )
    elapsed = time.time() - start_time

    print(f"\n{'='*50}")
    print(f"Upload complete!")
    print(f"Total records pushed : {total}")
    print(f"Time taken           : {elapsed:.1f} seconds")
    print(f"\nVerify at:")
    print(f"  https://console.firebase.google.com/project/iot-cfees/database")
    print(f"  Navigate to: sensors > room1 > readings")
    print(f"\nNEXT: Run task1_8_verify_roundtrip.py to confirm data integrity.")
