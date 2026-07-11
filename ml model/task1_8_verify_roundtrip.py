# ============================================================
# TASK 1.8 — Verify Round-Trip: Firebase → DataFrame
# ============================================================
# HOW TO RUN:
#   python task1_8_verify_roundtrip.py
#   (Run AFTER task1_7 so Firebase has synthetic records)
#
# WHAT IT DOES:
#   1. Reads all records from Firebase
#   2. Compares count and stats against original synthetic_data.csv
#   3. Checks data integrity (no corruption, types preserved)
#   4. Confirms the data is ready for Phase 2 feature engineering
#
# THIS IS YOUR GREEN LIGHT TEST.
# If all checks pass here, Phase 1 is complete.
#
# EXPECTED OUTPUT:
#   Records in CSV         : 2160
#   Records in Firebase    : 2160
#   Match: PASS
#   O2 mean (CSV)          : 20.XXX
#   O2 mean (Firebase)     : 20.XXX
#   Difference             : < 0.001 — PASS
#   All types correct      : PASS
#   PHASE 1 COMPLETE — Ready for Phase 2 feature engineering.
# ============================================================

import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import numpy as np

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://iot-cfees-default-rtdb.asia-southeast1.firebasedatabase.app"
        })
    return db


def fetch_all_sensor_data():
    """Fetch all records from Firebase and return as DataFrame."""
    database = init_firebase()
    ref = database.reference("/sensors/room1/readings")
    raw = ref.get()

    if raw is None:
        return pd.DataFrame()

    df = pd.DataFrame(raw.values())
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")

    for col in ["oxygen", "temperature", "humidity"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 1 ROUND-TRIP VERIFICATION")
    print("=" * 60)

    # Load original CSV
    try:
        df_csv = pd.read_csv("synthetic_data.csv")
        df_csv["timestamp"] = pd.to_datetime(df_csv["timestamp"])
        print(f"\nOriginal CSV:")
        print(f"  Records    : {len(df_csv)}")
        print(f"  Columns    : {list(df_csv.columns)}")
    except FileNotFoundError:
        print("ERROR: synthetic_data.csv not found. Run task1_6 first.")
        exit(1)

    # Fetch from Firebase
    print("\nFetching from Firebase...")
    df_fb = fetch_all_sensor_data()

    # Filter to only synthetic records (ignore the manual test record from task1_4)
    if "source" in df_fb.columns:
        df_fb_synth = df_fb[df_fb["source"] == "synthetic"].reset_index(drop=True)
    else:
        df_fb_synth = df_fb

    print(f"\nFirebase (synthetic records only):")
    print(f"  Records    : {len(df_fb_synth)}")
    print(f"  Columns    : {list(df_fb_synth.columns)}")

    # ── Checks ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("INTEGRITY CHECKS")
    print("=" * 60)

    results = []

    # Check 1: Record count
    count_match = len(df_fb_synth) == len(df_csv)
    results.append(("Record count matches", count_match,
                    f"CSV={len(df_csv)}, Firebase={len(df_fb_synth)}"))

    # Check 2: O2 mean within tolerance
    if len(df_fb_synth) > 0 and "oxygen" in df_fb_synth.columns:
        o2_diff = abs(df_fb_synth["oxygen"].mean() - df_csv["oxygen"].mean())
        results.append(("O2 mean preserved (diff < 0.01)", o2_diff < 0.01,
                        f"diff={o2_diff:.6f}"))

    # Check 3: No nulls introduced
    if len(df_fb_synth) > 0:
        nulls = df_fb_synth[["oxygen","temperature","humidity"]].isnull().sum().sum()
        results.append(("No null values", nulls == 0, f"null count={nulls}"))

    # Check 4: O2 range still valid
    if len(df_fb_synth) > 0 and "oxygen" in df_fb_synth.columns:
        in_range = (df_fb_synth["oxygen"].min() >= 17.0 and
                    df_fb_synth["oxygen"].max() <= 21.5)
        results.append(("O2 values in valid range (17–21.5%)", in_range,
                        f"min={df_fb_synth['oxygen'].min():.3f}, "
                        f"max={df_fb_synth['oxygen'].max():.3f}"))

    # Check 5: Timestamp parsing
    if len(df_fb_synth) > 0:
        ts_ok = df_fb_synth["timestamp"].notna().all()
        results.append(("Timestamps parsed correctly", ts_ok,
                        f"NaT count={df_fb_synth['timestamp'].isna().sum()}"))

    # Print results
    all_passed = True
    for check, passed, detail in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {check}")
        print(f"         {detail}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("ALL CHECKS PASSED")
        print("PHASE 1 COMPLETE — Ready for Phase 2 Feature Engineering")
        print("=" * 60)
        print("\nWhat you have now:")
        print("  Firebase: /sensors/room1/readings — populated with synthetic data")
        print("  Firebase: /predictions/room1/readings — structure ready for ML output")
        print("  Local:    synthetic_data.csv — source of truth for model training")
        print("  Local:    plot1_o2_timeseries.png, plot2_correlations.png, "
              "plot3_distributions.png")
        print("\nPhase 2 will build on fetch_all_sensor_data() from this file.")
        print("Copy that function to your Phase 2 notebook.")
    else:
        print("SOME CHECKS FAILED — review errors above before proceeding")
        print("=" * 60)

    # Final summary stats
    if len(df_fb_synth) > 0:
        print(f"\nFinal data summary (from Firebase):")
        print(df_fb_synth[["oxygen","temperature","humidity"]].describe().round(3))
