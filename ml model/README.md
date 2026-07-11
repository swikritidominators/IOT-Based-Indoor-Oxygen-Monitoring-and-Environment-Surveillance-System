# Indoor Oxygen Monitoring and Forecasting System
### DRDO Internship Project — June 2026

> A real-time IoT + Machine Learning system that monitors indoor oxygen levels in enclosed air-conditioned rooms, predicts O2 concentration 5–10 minutes ahead, detects anomalies, and triggers automated alerts before dangerous thresholds are reached.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Hardware Setup](#3-hardware-setup)

5. [Repository Structure](#5-repository-structure)
6. [Prerequisites and Installation](#6-prerequisites-and-installation)
7. [Firebase Setup](#7-firebase-setup)
8. [Running the ML Pipeline](#8-running-the-ml-pipeline)
9. [Switching Between Synthetic and Real Data](#9-switching-between-synthetic-and-real-data)
10. [Production Loop](#10-production-loop)
11. [Frontend and Visualization](#11-frontend-and-visualization)

13. [Important Security Notes](#13-important-security-notes)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Project Overview

Enclosed air-conditioned rooms gradually deplete oxygen as occupants breathe and AC systems recirculate stale air. This system addresses the problem by:

- **Monitoring** oxygen (%), temperature (°C), and humidity (%) in real time using ESP32-based IoT hardware
- **Storing** all sensor data on Firebase Realtime Database via WiFi
- **Predicting** future oxygen levels 5 and 10 minutes ahead using machine learning
- **Detecting** anomalies — sudden drops, sensor faults, gradual drift
- **Alerting** occupants via LCD display and buzzer before O2 reaches dangerous levels
- **Visualizing** live data and predictions on a ThingSpeak dashboard and web frontend



**Key thresholds used (based on OSHA Standard 1910.146):**

| Level | O2 % | Action |
|---|---|---|
| Normal | > 20.5% | No action |
| Warning | 19.5 – 20.5% | Increase ventilation |
| Critical | < 19.5% | Immediate evacuation |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        HARDWARE LAYER                        │
│  ESP32 + DHT11 + O2 Sensor  →  reads every 1 minute         │
│  Averages DHT11 (3-sec readings) → pushes 1 record/min       │
└───────────────────────┬─────────────────────────────────────┘
                        │ WiFi / HTTP
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                     FIREBASE REALTIME DB                     │
│  /sensors/room1/readings     ← ESP32 writes here             │
│  /predictions/room1/readings ← ML script writes here         │
│  /alerts/room1               ← ML script writes alerts       │
│  /occupancy/room1/readings   ← optional camera data          │
└───────────┬─────────────────────────┬───────────────────────┘
            │                         │
            ▼                         ▼
┌───────────────────────┐   ┌─────────────────────────────────┐
│     ML PIPELINE       │   │         FRONTEND / DISPLAY       │
│  Python (local/server)│   │  ThingSpeak Dashboard            │
│  Runs every 5 minutes │   │  Web frontend (React/HTML)       │
│  Phase 1: Data setup  │   │  ESP32 LCD + Buzzer              │
│  Phase 2: Features    │   │  Shows: current O2, temp, hum    │
│  Phase 3: Forecasting │   │  Shows: predicted O2             │
│  Phase 4: Anomaly det.│   │  Shows: time series graph        │
│  Phase 5: Live loop   │   │  Shows: alerts and severity      │
└───────────────────────┘   └─────────────────────────────────┘
```

**Data flow for each ML cycle (every 5 minutes):**
```
Firebase /sensors  →  Fetch 25 records  →  Resample to 5-min  
→  Engineer 54 features  →  XGBoost forecast (5min + 10min)  
→  Isolation Forest + CUSUM anomaly detection  
→  Recommendation engine  →  Write to /predictions + /alerts
```

---

## 3. Hardware Setup

| Component | Model | Purpose | Connected To |
|---|---|---|---|
| ESP32 Dev Board | ESP32-WROOM-32 | Main controller, WiFi, sensor reads | — |
| ESP32-CAM | AI-Thinker OV2640 | Optional occupancy detection | Separate board |
| O2 Sensor | Electrochemical, analog output | Oxygen concentration | ESP32 GPIO34 (ADC1) |
| DHT11 | 3-pin module | Temperature + humidity | ESP32 GPIO4 |
| 16x2 LCD | I2C backpack (PCF8574) | Display readings and alerts | SDA→GPIO21, SCL→GPIO22 |
| Active Buzzer | 5V module | Audible alarm | ESP32 GPIO25 |

**Important wiring notes:**
- Use ADC1 pins only for O2 sensor (GPIO32–39) — ADC2 conflicts with WiFi
- LCD must have I2C backpack — plain 16x2 needs 6+ GPIO pins
- Power ESP32-CAM separately (draws 300–500mA during capture)
- O2 and DHT11 sensor should be placed at 1.0–1.5m height, away from AC vent

**ESP32 firmware must include this line in the Firebase push payload:**
```cpp
json.set("source", "esp32_main_01");
```
Without this, the ML pipeline cannot distinguish real data from synthetic data.

---


## 5. Repository Structure

```
oxygen_ml_project/
│
├── config.py                        ← Central config — edit this file only
├── firebase_connect.py              ← Reusable Firebase connection module
├── serviceAccountKey.json           ← SECRET — never commit to git (in .gitignore)
├── requirements.txt                 ← Python dependencies
├── .gitignore                       ← Must include serviceAccountKey.json
│
├── Phase 1 — Firebase + Synthetic Data
│   ├── task1_2_firebase_connect.py
│   ├── task1_3_read_firebase.py
│   ├── task1_4_write_test_record.py
│   ├── task1_5_read_to_dataframe.py
│   ├── task1_6_synthetic_generator.py
│   ├── task1_7_push_synthetic.py
│   ├── task1_8_verify_roundtrip.py
│   └── task1_fix_timestamps.py
│
├── Phase 2 — Feature Engineering
│   ├── phase2_feature_engineering.py
│   └── fix_phase2_summary.py
│
├── Phase 3 — Model Training
│   └── phase3_model_training.py
│
├── Phase 4 — Anomaly Detection
│   └── phase4_anomaly_detection.py
│
├── Phase 5 — Production Loop
│   └── phase5_production_loop.py
│
├── Data Files (generated, not committed to git)
│   ├── synthetic_data.csv
│   ├── featured_data.csv
│   ├── train_data.csv
│   └── test_data.csv
│
├── Trained Models (generated, not committed to git)
│   ├── model_xgb_5min.pkl
│   ├── model_xgb_10min.pkl
│   ├── model_rf_5min.pkl
│   ├── model_ridge_5min.pkl
│   ├── anomaly_iso_model.pkl
│   ├── feature_scaler.pkl
│   └── production_config.json
│
└── Plots (generated)
    ├── plot1_o2_timeseries.png
    ├── plot2_correlations.png
    ├── plot3_distributions.png
    ├── plot4_acf_pacf.png
    ├── plot5_feature_heatmap.png
    ├── plot6_target_analysis.png
    ├── plot7_model_comparison.png
    ├── plot8_actual_vs_pred.png
    ├── plot9_feature_importance.png
    ├── plot10_residuals.png
    ├── plot11_anomaly_scores.png
    ├── plot13_detector_comparison.png
    └── plot14_recommendation_dist.png
```

---

## 6. Prerequisites and Installation

**Python version:** 3.10 or higher

**Install all dependencies:**
```bash
pip install -r requirements.txt
```

**Contents of requirements.txt:**
```
firebase-admin
pandas
numpy
matplotlib
seaborn
scikit-learn
xgboost
statsmodels
joblib
scipy
```

**Verify installation:**
```bash
python -c "import firebase_admin, pandas, numpy, xgboost, sklearn; print('All OK')"
```

---

## 7. Firebase Setup

### 7.1 First-Time Setup

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Create a new project (or use existing: `iot-cfees`)
3. Enable Realtime Database → Create database → Start in test mode
4. Go to Project Settings → Service Accounts → Generate New Private Key
5. Save the downloaded file as `serviceAccountKey.json` in your project folder
6. **Immediately add to .gitignore:**
   ```bash
   echo "serviceAccountKey.json" >> .gitignore
   ```

### 7.2 Database Rules (for development)
In Firebase Console → Realtime Database → Rules:
```json
{
  "rules": {
    ".read": true,
    ".write": true
  }
}
```
> Tighten these rules before any production deployment.

### 7.3 Update config.py
Open `config.py` and set your Firebase URL:
```python
FIREBASE_URL = "https://iot-cfees-default-rtdb.asia-southeast1.firebasedatabase.app"
KEY_PATH     = "serviceAccountKey.json"
```

### 7.4 Test Connection
```bash
python firebase_connect.py
```
Expected output:
```
Firebase connected successfully!
URL: https://iot-cfees-default-rtdb.asia-southeast1.firebasedatabase.app
```

### 7.5 If You Need to Rotate Service Keys
If the key file is ever accidentally committed to git:
1. Revoke the old key: Firebase Console → Project Settings → Service Accounts → Delete key
2. Generate a new key and replace `serviceAccountKey.json`
3. Purge from git history using BFG Repo Cleaner:
   ```bash
   java -jar bfg.jar --delete-files serviceAccountKey.json your-repo.git
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   git push --force
   ```
4. Update `FIREBASE_URL` in `config.py` if project also changed

---

## 8. Running the ML Pipeline

Run phases **strictly in order**. Each phase depends on outputs of the previous one.

### Phase 1 — Firebase Integration and Synthetic Data
```bash
python task1_2_firebase_connect.py    # test connection
python task1_3_read_firebase.py       # inspect database structure
python task1_4_write_test_record.py   # write one test record
python task1_5_read_to_dataframe.py   # read back and verify
python task1_6_synthetic_generator.py # generate 2160 synthetic records
python task1_7_push_synthetic.py      # push to Firebase (type 'yes' when prompted)
python task1_8_verify_roundtrip.py    # verify data integrity
python task1_fix_timestamps.py        # fix timestamp parsing (Windows)
```
**Expected final output:** `PHASE 1 FULLY COMPLETE — All 6 checks PASSED`

### Phase 2 — Feature Engineering
```bash
python phase2_feature_engineering.py
python fix_phase2_summary.py          # fixes Windows unicode issue in summary file
```
**Expected output:** `PHASE 2 FULLY COMPLETE. Ready for Phase 3 model training.`
**Files produced:** `featured_data.csv`, `train_data.csv`, `test_data.csv`, 3 plots

### Phase 3 — Model Training
```bash
python phase3_model_training.py
```
**Expected output:** All 10 files saved, best model identified
**Expected results (synthetic data):**
- Random Forest 5-min MAE: ~0.055%
- XGBoost 5-min MAE: ~0.066%
- Random Forest beats naive by ~26%

**Files produced:** `model_xgb_5min.pkl`, `model_rf_5min.pkl`, `model_xgb_10min.pkl`, `model_comparison.csv`, 4 plots

### Phase 4 — Anomaly Detection
```bash
python phase4_anomaly_detection.py
```
**Expected output:** All 6 files saved
**Expected results (synthetic data):**
- Combined detector Recall: ~71.7%
- Combined detector F1: ~0.584
- AC experiment p-value: ~0.003 (significant)

**Files produced:** `anomaly_iso_model.pkl`, `phase4_results.csv`, 3 plots

### Phase 5 — Production Loop (Test Mode)
```bash
# Always test first
python phase5_production_loop.py --test
```
**Expected output:** `TEST PASSED — Production loop is ready to run.`
All fields printed with sensible values, latency < 5 seconds.

---

## 9. Switching Between Synthetic and Real Data

**This is the most important section for ongoing development.**

All data source control happens in **one place only** — `config.py` line 34:

```python
DATA_SOURCE_FILTER = ["synthetic"]        # Stage 1 — development only
```

### Stage 1 — Synthetic Data Only (Current)
Use during development before any real sensor data exists.
```python
# config.py
DATA_SOURCE_FILTER = ["synthetic"]
PRODUCTION = { "model_version": "v1_synthetic", ... }
```
No other changes needed anywhere.

---

### Stage 2 — Mixed (Synthetic + Real Data)
Use when ESP32 starts sending data but real dataset is still small (first 1–2 weeks).
Synthetic data augments the limited real data for better model training.

**Step 1:** Confirm ESP32 firmware includes source tag:
```cpp
json.set("source", "esp32_main_01");  // must be in ESP32 sketch
```

**Step 2:** Update `config.py`:
```python
DATA_SOURCE_FILTER = ["synthetic", "esp32_main_01"]
PRODUCTION = { "model_version": "v2_mixed", ... }
```

**Step 3:** Retrain all models on the combined dataset:
```bash
python phase2_feature_engineering.py
python fix_phase2_summary.py
python phase3_model_training.py
python phase4_anomaly_detection.py
python phase5_production_loop.py --test   # verify before full run
```

---

### Stage 3 — Real Data Only (Final Paper Results)
Use when 2+ weeks of real sensor data is available. This produces your final research paper metrics.

**Step 1:** Update `config.py`:
```python
DATA_SOURCE_FILTER = ["esp32_main_01"]
PRODUCTION = { "model_version": "v3_real", ... }
```

**Step 2:** Retrain:
```bash
python phase2_feature_engineering.py
python fix_phase2_summary.py
python phase3_model_training.py
python phase4_anomaly_detection.py
python phase5_production_loop.py --test
```

**Step 3:** Compare results across all three stages — this comparison is a key finding for the research paper.

---

### Checking What Data Is Currently in Firebase
```python
# Quick check — run in Python terminal
from firebase_connect import fetch_sensor_data
df = fetch_sensor_data(source_filter=[])   # empty list = fetch ALL sources
print(df["source"].value_counts())
```
Output tells you exactly how many records of each source type exist.

---

### If ESP32 Source Tag is Missing or Wrong
If real data arrives without a source tag, or with a different device ID, you will see:
```
WARNING: X records excluded by source filter.
Unknown source values found: ['your_actual_source_value']
```
Two options:
1. Fix the ESP32 firmware to send the correct source value and update `ESP32_DEVICE_ID` in `config.py`
2. Or temporarily use `source_filter=[]` to include all records regardless of source

---

## 10. Production Loop

### Starting the Live Loop
```bash
# Keep this terminal open and laptop connected to WiFi
python phase5_production_loop.py
```

The loop runs every 5 minutes automatically. Every cycle:
1. Fetches last 25 sensor records from Firebase
2. Resamples to 5-minute intervals if ESP32 sends more frequently
3. Engineers 54 features
4. Runs XGBoost 5-min and 10-min forecasts
5. Runs Isolation Forest + CUSUM anomaly detection
6. Generates severity recommendation
7. Writes prediction to `/predictions/room1/readings`
8. Writes alert to `/alerts/room1` if severity is not OK

**Terminal output every cycle:**
```
[12:45:00] O2=20.75% | Fc5=20.68% | Fc10=20.61% | Anomaly=no | Status=OK | Latency=1.54s
```

### Stopping the Loop
Press `Ctrl+C` — shuts down cleanly and prints session summary.

### Monitoring the Log
```bash
# Windows — follow log in real time
Get-Content production.log -Wait -Tail 20
```

### Preventing Laptop Sleep During Data Collection
Windows → Control Panel → Power Options → Change plan settings  
→ Set "Put the computer to sleep" to **Never** when plugged in.

### Prediction Record Format Written to Firebase
```json
{
  "timestamp"             : "2026-07-03T10:05:00+00:00",
  "based_on_reading_at"   : "2026-07-03T10:04:00+00:00",
  "predicted_for_5min"    : "2026-07-03T10:09:00+00:00",
  "predicted_for_10min"   : "2026-07-03T10:14:00+00:00",
  "oxygen_current"        : 20.75,
  "oxygen_forecast_5min"  : 20.68,
  "oxygen_forecast_10min" : 20.61,
  "iso_score"             : 0.031,
  "cusum_score"           : 0.0,
  "is_anomaly"            : 0,
  "rec_severity"          : "OK",
  "rec_message"           : "Air quality normal.",
  "rec_action_code"       : 0,
  "cycle_latency_sec"     : 1.54,
  "model_version"         : "xgb_v1_synthetic"
}
```

---

## 11. Frontend and Visualization

### ThingSpeak Dashboard
- Managed by Akansha
- Receives data via Firebase → Python sync script → ThingSpeak REST API
- Shows: live O2, temperature, humidity time series charts
- Public dashboard for sharing during demo

### Web Frontend
- Managed by Akansha and Swikriti
- Reads directly from Firebase `/sensors` and `/predictions` nodes
- Displays:
  - Current O2, temperature, humidity (latest record from `/sensors`)
  - Predicted O2 for next 5 and 10 minutes (from `/predictions`)
  - Time series graph with two lines: actual O2 and predicted O2
  - Alert badge showing current severity
  - Recommendation message

### ESP32 LCD and Buzzer (Hardware Alerts)
The ESP32 polls `/predictions/room1/readings` every 30 seconds.

| rec_action_code | LCD | Buzzer |
|---|---|---|
| 0 — OK | Shows current readings | Silent |
| 1 — Advisory | Shows advisory message | Silent |
| 2 — Warning | Shows warning message | 3 beeps every 30s |
| 3 — Critical | Flashing critical message | Continuous beep |

---



## 13. Important Security Notes

```
serviceAccountKey.json    → NEVER commit to git
                          → Already in .gitignore
                          → Gives full Firebase read/write access
                          → Rotate immediately if accidentally exposed
                          → See Section 7.5 for rotation procedure

Firebase Database Rules   → Currently set to open (development)
                          → Restrict before any public deployment

GitHub repository         → Make private until paper is submitted
                          → Do not share Firebase URL publicly
```

**If you see this warning, act immediately:**
```
GitHub Secret Scanning Alert: Firebase service account key detected
```
Follow Section 7.5 rotation procedure without delay.

---

## 14. Troubleshooting

### Firebase connection fails
```
Check 1: serviceAccountKey.json exists in project folder
Check 2: FIREBASE_URL in config.py matches your project
Check 3: Internet connection is active
Check 4: Firebase project is not paused (free tier has limits)
Fix:     python config.py  →  shows current config
         python firebase_connect.py  →  tests connection
```

### UnicodeEncodeError on Windows
```
Cause:   Windows cp1252 encoding cannot handle arrow characters (→)
Fix:     python fix_phase2_summary.py
Prevent: All file writes now use encoding="utf-8" 
```

### Phase 5 returns "Not enough data"
```
Cause:   Fewer than 15 records in Firebase after source filter
Check:   python -c "from firebase_connect import fetch_sensor_data; 
         df=fetch_sensor_data(source_filter=[]); print(df['source'].value_counts())"
Fix:     Run task1_7_push_synthetic.py to push synthetic data
         OR change DATA_SOURCE_FILTER in config.py to match actual sources
```

### Models not found error
```
Cause:   Phase 3 or Phase 4 not run yet, or run from wrong directory
Fix:     cd oxygen_ml_project  (must be in project folder)
         python phase3_model_training.py
         python phase4_anomaly_detection.py
```

### XGBoost UserWarning about feature names
```
Cause:   Sklearn version mismatch between training and inference
Effect:  None — predictions are correct, this is cosmetic only
Fix:     Add feature names explicitly (optional, not required)
```

### ESP32 data not appearing in ML pipeline
```
Cause 1: ESP32 firmware missing  json.set("source", "esp32_main_01")
Cause 2: Device ID in firmware doesn't match ESP32_DEVICE_ID in config.py
Cause 3: DATA_SOURCE_FILTER doesn't include the ESP32 source value
Fix:     Check firebase_connect.py WARNING output for unknown source values
         Update ESP32_DEVICE_ID in config.py to match firmware
```

### Production loop keeps skipping cycles
```
Cause:   Not enough records after resampling for lag features
         Need at least 13 rows after 5-min resample for lag-12 features
Fix:     Ensure ESP32 has been running for at least 65 minutes
         before starting the production loop
```

---

## Quick Reference — Most Used Commands

```bash
# Test Firebase connection
python firebase_connect.py

# Check current config
python config.py

# Full pipeline re-run (after data source change)
python phase2_feature_engineering.py
python fix_phase2_summary.py
python phase3_model_training.py
python phase4_anomaly_detection.py
python phase5_production_loop.py --test   # verify
python phase5_production_loop.py           # start live loop

# Check what data is in Firebase
python -c "from firebase_connect import fetch_sensor_data; df=fetch_sensor_data(source_filter=[]); print(df['source'].value_counts()); print(df.shape)"

# Stop production loop cleanly
Ctrl+C
```

---

*DRDO Internship Project — June/July 2026*  
*Team:  Akansha, Archi, Nancy, Swikriti*
