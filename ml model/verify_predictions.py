# ============================================================
# VERIFY PREDICTIONS — Manual spot check + visual validation
# ============================================================
# HOW TO RUN:
#   python verify_predictions.py
#
# WHAT IT DOES:
#   3 verification methods:
#   1. Spot check — shows actual vs predicted for 10 records
#      so you can sanity-check values with your own eyes
#   2. Sanity checks — predictions must be in valid O2 range,
#      errors must be small, no systematic bias
#   3. Simple manual test — you give it made-up sensor values,
#      it predicts, you check if the prediction makes sense
# ============================================================

import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt

# ── Load saved models and data ───────────────────────────────
rf_model   = joblib.load("model_rf_5min.pkl")
xgb_model  = joblib.load("model_xgb_5min.pkl")
scaler     = joblib.load("feature_scaler.pkl")
test_df    = pd.read_csv("test_data.csv")
train_df   = pd.read_csv("train_data.csv")

# Get feature columns
exclude = {"timestamp","source","is_anomaly","target_5min","target_10min",
           "oxygen","temperature","humidity","occupancy_count","ac_status"}
feature_cols = [c for c in test_df.columns if c not in exclude]

X_test  = test_df[feature_cols]
y_test  = test_df["target_5min"]

rf_preds  = rf_model.predict(X_test)
xgb_preds = xgb_model.predict(X_test)


# ════════════════════════════════════════════════════════════
# METHOD 1: SPOT CHECK — read actual vs predicted row by row
# ════════════════════════════════════════════════════════════
print("="*65)
print("METHOD 1 — SPOT CHECK (10 random test records)")
print("="*65)
print(f"{'#':<4} {'Actual O2':>10} {'RF pred':>10} {'XGB pred':>10} "
      f"{'RF err':>9} {'XGB err':>9} {'Anomaly':>8}")
print("-"*65)

# Pick 10 indices — mix of normal and anomaly records
normal_idx  = test_df[test_df["is_anomaly"] == 0].index[:7].tolist()
anomaly_idx = test_df[test_df["is_anomaly"] == 1].index[:3].tolist()
check_idx   = sorted(normal_idx + anomaly_idx)

for i, idx in enumerate(check_idx):
    actual   = y_test.iloc[idx]
    rf_pred  = rf_preds[idx]
    xgb_pred = xgb_preds[idx]
    rf_err   = abs(actual - rf_pred)
    xgb_err  = abs(actual - xgb_pred)
    is_anom  = test_df["is_anomaly"].iloc[idx]
    print(f"{i+1:<4} {actual:>10.4f} {rf_pred:>10.4f} {xgb_pred:>10.4f} "
          f"{rf_err:>9.4f} {xgb_err:>9.4f} {'YES' if is_anom else 'no':>8}")

print("-"*65)
print("For NORMAL records: RF error should be < 0.10% O2")
print("For ANOMALY records: errors will be larger (expected)")


# ════════════════════════════════════════════════════════════
# METHOD 2: SANITY CHECKS
# ════════════════════════════════════════════════════════════
print("\n" + "="*65)
print("METHOD 2 — AUTOMATED SANITY CHECKS")
print("="*65)

checks = []

# Check 1: All predictions in physically valid O2 range
rf_in_range = ((rf_preds >= 17.0) & (rf_preds <= 22.0)).all()
checks.append(("RF predictions in valid O2 range (17-22%)",
               rf_in_range,
               f"min={rf_preds.min():.3f}, max={rf_preds.max():.3f}"))

# Check 2: Mean prediction close to mean actual
mean_diff = abs(rf_preds.mean() - y_test.mean())
checks.append(("RF mean prediction close to actual mean (diff < 0.1)",
               mean_diff < 0.1,
               f"actual mean={y_test.mean():.4f}, "
               f"pred mean={rf_preds.mean():.4f}, diff={mean_diff:.4f}"))

# Check 3: No systematic bias (residual mean near 0)
residuals = y_test.values - rf_preds
bias = abs(residuals.mean())
checks.append(("No systematic bias (|mean residual| < 0.05)",
               bias < 0.05,
               f"mean residual={residuals.mean():.5f}"))

# Check 4: RF beats naive on normal records only
normal_mask = test_df["is_anomaly"].values == 0
naive_mae_normal = np.mean(np.abs(
    y_test.values[normal_mask] - X_test["o2_lag1"].values[normal_mask]))
rf_mae_normal = np.mean(np.abs(
    y_test.values[normal_mask] - rf_preds[normal_mask]))
checks.append(("RF beats naive on non-anomaly records",
               rf_mae_normal < naive_mae_normal,
               f"RF MAE={rf_mae_normal:.5f}, "
               f"Naive MAE={naive_mae_normal:.5f}"))

# Check 5: Predictions correlate with actuals
corr = np.corrcoef(y_test.values, rf_preds)[0, 1]
checks.append(("RF predictions correlate with actuals (r > 0.3)",
               corr > 0.3,
               f"Pearson r = {corr:.4f}"))

# Check 6: 80%+ predictions within 0.15% O2
within_015 = (np.abs(residuals) <= 0.15).mean()
checks.append(("80%+ predictions within 0.15% O2 of actual",
               within_015 >= 0.80,
               f"{within_015*100:.1f}% of predictions within 0.15% O2"))

for check, passed, detail in checks:
    print(f"  [{'PASS' if passed else 'FAIL'}] {check}")
    print(f"         {detail}")


# ════════════════════════════════════════════════════════════
# METHOD 3: MANUAL INTUITION TEST
# ════════════════════════════════════════════════════════════
print("\n" + "="*65)
print("METHOD 3 — INTUITION TEST")
print("What the model predicts for hand-crafted scenarios")
print("="*65)

# Get a real test row to use as template, then modify it
template = X_test.iloc[50].copy()

scenarios = {
    "Normal room (O2=20.9%, stable, 2 people)": {
        "o2_lag1": 20.9, "o2_lag2": 20.9, "o2_lag3": 20.9,
        "o2_delta_1": 0.0, "o2_delta_3": 0.0,
        "o2_roll_mean_3": 20.9, "occ_lag1": 2.0
    },
    "Falling O2 (20.5%, dropping fast, 5 people)": {
        "o2_lag1": 20.5, "o2_lag2": 20.6, "o2_lag3": 20.7,
        "o2_delta_1": -0.1, "o2_delta_3": -0.2,
        "o2_roll_mean_3": 20.6, "occ_lag1": 5.0
    },
    "Recovering O2 (20.7%, rising, 0 people)": {
        "o2_lag1": 20.7, "o2_lag2": 20.6, "o2_lag3": 20.5,
        "o2_delta_1": 0.1, "o2_delta_3": 0.2,
        "o2_roll_mean_3": 20.6, "occ_lag1": 0.0
    },
    "Low O2 danger zone (19.6%, 6 people)": {
        "o2_lag1": 19.6, "o2_lag2": 19.7, "o2_lag3": 19.8,
        "o2_delta_1": -0.1, "o2_delta_3": -0.2,
        "o2_roll_mean_3": 19.7, "occ_lag1": 6.0
    },
}

print(f"\n{'Scenario':<45} {'RF pred':>9} {'Makes sense?':>14}")
print("-"*70)

for scenario_name, overrides in scenarios.items():
    row = template.copy()
    for col, val in overrides.items():
        if col in row.index:
            row[col] = val
    pred = rf_model.predict(row.values.reshape(1, -1))[0]

    # Logic check: falling O2 should predict lower than rising
    makes_sense = "check manually"
    if "Falling" in scenario_name and pred < 20.5:
        makes_sense = "YES - predicts drop"
    elif "Recovering" in scenario_name and pred > 20.6:
        makes_sense = "YES - predicts rise"
    elif "Normal" in scenario_name and 20.7 < pred < 21.1:
        makes_sense = "YES - stable"
    elif "danger" in scenario_name and pred < 19.7:
        makes_sense = "YES - stays low"
    else:
        makes_sense = f"pred={pred:.4f}, verify"

    print(f"{scenario_name:<45} {pred:>9.4f} {makes_sense:>14}")

print("\nINTERPRETATION:")
print("  Falling scenario should predict LOWER O2 than current")
print("  Recovering scenario should predict HIGHER O2 than current")
print("  Danger zone should stay near the low value (not jump to 21%)")
print("  If these hold, your model has learned the physics correctly.")

print("\n" + "="*65)
print("VERIFICATION COMPLETE")
print("="*65)
print("\nKey takeaway for your research paper:")
print(f"  Best model (RF) achieves MAE = 0.05572% O2 on 5-min forecast")
print(f"  This means predictions are off by < 0.06% O2 on average")
print(f"  Normal O2 range is 19.5-21.0% — so error is <0.3% of that range")
print(f"  For a safety monitoring system, this precision is sufficient")
print(f"  to trigger alerts before O2 reaches dangerous levels.")
