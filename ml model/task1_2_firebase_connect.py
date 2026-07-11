# ============================================================
# TASK 1.2 — Firebase Connection Test
# ============================================================
# HOW TO RUN:
#   python task1_2_firebase_connect.py
#
# WHAT IT DOES:
#   Connects to your Firebase project and reads the root node.
#   If you see the structure printed, connection is working.
#
# EXPECTED OUTPUT:
#   Firebase connected successfully!
#   Current database contents:
#   {'sensors': {'room1': {'status': 'initialized'}}, ...}
# ============================================================

import firebase_admin
from firebase_admin import credentials, db
import json

def init_firebase():
    """
    Initialize Firebase app.
    Called once — if already initialized, returns existing app.
    """
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://iot-cfees-default-rtdb.asia-southeast1.firebasedatabase.app"
        })
    return db

if __name__ == "__main__":
    try:
        database = init_firebase()
        print("Firebase connected successfully!")

        # Read the root of the database
        root_ref = database.reference("/")
        data = root_ref.get()

        print("\nCurrent database contents:")
        print(json.dumps(data, indent=2))

        # Confirm each expected node exists
        expected_nodes = ["sensors", "occupancy", "predictions", "alerts"]
        print("\nNode check:")
        for node in expected_nodes:
            exists = data is not None and node in data
            print(f"  /{node} : {'EXISTS' if exists else 'MISSING'}")

    except FileNotFoundError:
        print("ERROR: serviceAccountKey.json not found.")
        print("Make sure the file is in the same folder as this script.")
    except Exception as e:
        print(f"ERROR: {e}")
