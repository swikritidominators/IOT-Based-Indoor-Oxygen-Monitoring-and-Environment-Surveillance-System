import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json")

firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://iot-cfees-default-rtdb.asia-southeast1.firebasedatabase.app'
})

# Create database structure
ref = db.reference("/")

ref.set({
    "sensors": {
        "room1": {
            "status": "initialized"
        }
    },
    "occupancy": {
        "room1": {
            "status": "initialized"
        }
    },
    "predictions": {
        "room1": {
            "status": "initialized"
        }
    },
    "alerts": {
        "room1": {
            "status": "initialized"
        }
    }
})
print("JSON structure created successfully!")
