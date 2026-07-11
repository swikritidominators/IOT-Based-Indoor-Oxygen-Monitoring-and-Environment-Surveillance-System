# ============================================================
# TASK 1.3 — Read Firebase Structure and Understand It
# ============================================================
# HOW TO RUN:
#   python task1_3_read_firebase.py
#
# WHAT IT DOES:
#   Reads each node separately and prints structure details.
#   Helps you understand exactly what paths exist before writing.
#
# EXPECTED OUTPUT:
#   Structure of /sensors/room1 : {'status': 'initialized'}
#   Structure of /predictions/room1 : {'status': 'initialized'}
#   ...
# ============================================================

import firebase_admin
from firebase_admin import credentials, db
import json

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://iot-cfees-default-rtdb.asia-southeast1.firebasedatabase.app"
        })
    return db

if __name__ == "__main__":
    database = init_firebase()

    # Read each node individually
    paths_to_check = [
        "/sensors/room1",
        "/occupancy/room1",
        "/predictions/room1",
        "/alerts/room1"
    ]

    print("=" * 50)
    print("FIREBASE DATABASE STRUCTURE INSPECTION")
    print("=" * 50)

    for path in paths_to_check:
        ref = database.reference(path)
        data = ref.get()
        print(f"\nPath: {path}")
        print(f"Type: {type(data).__name__}")
        print(f"Value: {json.dumps(data, indent=4)}")

    # Also show what keys exist under /sensors/room1/readings if any
    print("\n" + "=" * 50)
    print("Checking if any sensor readings exist yet...")
    readings_ref = database.reference("/sensors/room1/readings")
    readings = readings_ref.get()
    if readings:
        print(f"Found {len(readings)} existing readings")
        # Show the first one
        first_key = list(readings.keys())[0]
        print(f"Sample record key: {first_key}")
        print(f"Sample record value: {json.dumps(readings[first_key], indent=4)}")
    else:
        print("No readings yet — this is expected at this stage.")
        print("Task 1.4 will write the first test record.")
