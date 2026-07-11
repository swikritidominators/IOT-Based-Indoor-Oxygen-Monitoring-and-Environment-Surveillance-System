# ============================================================
# TASK 1.4 — Write a Test Sensor Record to Firebase
# ============================================================
# HOW TO RUN:
#   python task1_4_write_test_record.py
#
# WHAT IT DOES:
#   Simulates what the ESP32 will do — pushes a single sensor
#   reading to /sensors/room1/readings with all 4 fields.
#   Also writes to /predictions/room1/readings as a format test.
#
# CONCEPT — push() vs set():
#   ref.set(data)  → overwrites the node completely (dangerous)
#   ref.push(data) → creates a new child with auto-generated key
#                    like "-O9xk3abc123..." — this is what you use
#                    for time-series records so each reading gets
#                    its own unique key and nothing is overwritten.
#
# EXPECTED OUTPUT:
#   Sensor record written. Key: -O9xk3abc123...
#   Prediction record written. Key: -O9xk3def456...
#   Go check Firebase Console to see the new records!
# ============================================================

import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime, timezone

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://iot-cfees-default-rtdb.asia-southeast1.firebasedatabase.app"
        })
    return db

if __name__ == "__main__":
    database = init_firebase()

    # -------------------------------------------------------
    # Write a test SENSOR record
    # This is the format ESP32 will write in real deployment
    # -------------------------------------------------------
    sensor_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "oxygen": 20.8,           # % — normal room air
        "temperature": 24.5,      # °C
        "humidity": 55.2,         # %
        "source": "test_manual"   # so you can identify test records later
    }

    sensor_ref = database.reference("/sensors/room1/readings")
    new_key = sensor_ref.push(sensor_record)
    print(f"Sensor record written.")
    print(f"  Key: {new_key.key}")
    print(f"  Data: {sensor_record}")

    # -------------------------------------------------------
    # Write a test PREDICTION record
    # This is the format your ML script will write
    # -------------------------------------------------------
    prediction_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "based_on_reading_time": sensor_record["timestamp"],
        "oxygen_forecast_5min": 20.75,
        "oxygen_forecast_10min": 20.70,
        "anomaly_score": 0.12,
        "is_anomaly": 0,
        "recommendation_severity": "OK",
        "recommendation_message": "Air quality normal.",
        "source": "test_manual"
    }

    pred_ref = database.reference("/predictions/room1/readings")
    pred_key = pred_ref.push(prediction_record)
    print(f"\nPrediction record written.")
    print(f"  Key: {pred_key.key}")
    print(f"  Data: {prediction_record}")

    print("\nGo to Firebase Console and verify:")
    print("  https://console.firebase.google.com/project/iot-cfees/database")
    print("  Navigate to: sensors > room1 > readings")
