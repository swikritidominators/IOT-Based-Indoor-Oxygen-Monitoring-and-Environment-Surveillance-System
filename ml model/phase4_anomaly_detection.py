# ============================================================
# PHASE 4 — Anomaly Detection + Recommendation Engine
# ============================================================
# HOW TO RUN:
#   python phase4_anomaly_detection.py
#
# PREREQUISITES:
#   featured_data.csv   (from Phase 2)
#   train_data.csv      (from Phase 2)
#   test_data.csv       (from Phase 2)
#   model_xgb_5min.pkl  (from Phase 3)
#   model_xgb_10min.pkl (from Phase 3)
#
# WHAT IT PRODUCES:
#   anomaly_iso_model.pkl         trained Isolation Forest
#   phase4_results.csv            all test records with scores+recommendations
#   plot11_anomaly_scores.png     anomaly score timeline
#   plot12_cusum_chart.png        CUSUM running sum chart
#   plot13_detector_comparison.png which detector caught what
#   plot14_recommendation_dist.png recommendation severity breakdown
#   phase4_summary.txt            metrics report
# ============================================================

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import joblib
import os
import warnings
warnings.filterwarnings("ignore")

from sklearn.ensemble import IsolationForest
from sklearn.metrics import (precision_score, recall_score,
                              f1_score, confusion_matrix,
                              classification_report)
from scipy import stats


# ════════════════════════════════════════════════════════════
# HELPERS — reused from earlier phases
# ════════════════════════════════════════════════════════════

def get_feature_columns(df):
    exclude = {"timestamp","source","is_anomaly",
               "target_5min","target_10min",
               "oxygen","temperature","humidity",
               "occupancy_count","ac_status"}
    return [c for c in df.columns if c not in exclude]


def load_data():
    print("="*60)
    print("LOADING DATA")
    print("="*60)
    train = pd.read_csv("train_data.csv")
    test  = pd.read_csv("test_data.csv")
    feat  = pd.read_csv("featured_data.csv")

    for df in [train, test, feat]:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    feature_cols = get_feature_columns(train)

    print(f"Train : {train.shape}  |  Test : {test.shape}")
    print(f"Features : {len(feature_cols)}")
    print(f"Anomalies in test set: "
          f"{test['is_anomaly'].sum()} / {len(test)} "
          f"({test['is_anomaly'].mean()*100:.1f}%)")
    return train, test, feat, feature_cols


# ════════════════════════════════════════════════════════════
# COMPONENT 1 — ISOLATION FOREST
# ════════════════════════════════════════════════════════════
#
# CONCEPT RECAP:
#   Isolation Forest randomly partitions data using decision
#   trees. Points that are isolated quickly (short path length)
#   are anomalies — they sit far from the main cluster.
#   Points deep in the cluster need many splits to isolate —
#   these are normal.
#
#   KEY: We train ONLY on non-anomaly training records.
#   Why? Because we want the model to learn what "normal"
#   looks like, not contaminate that learning with anomalies.
#   This simulates real deployment where you train on clean
#   historical data and detect anomalies in live data.
#
#   contamination=0.05:
#   Tells the model to expect ~5% anomalies in the data it
#   will see at inference time. This sets the internal
#   threshold for the anomaly score → binary flag conversion.
#   If your real data shows more anomalies, increase this.
#
#   decision_function() returns anomaly scores:
#     Negative values → more anomalous
#     Positive values → more normal
#     Threshold is 0 (at contamination setting)
#
#   predict() returns:
#     -1 → anomaly
#      1 → normal
#   We convert to 0/1 for consistency with is_anomaly column.

def train_isolation_forest(train_df, feature_cols):
    print("\n" + "="*60)
    print("COMPONENT 1 — ISOLATION FOREST TRAINING")
    print("="*60)

    # Train ONLY on clean (non-anomaly) records
    # This is critical — if you train on anomalies too, the
    # model learns anomalous patterns as "normal"
    clean_train = train_df[train_df["is_anomaly"] == 0]
    print(f"Training on {len(clean_train)} clean records "
          f"(excluded {len(train_df) - len(clean_train)} anomaly records)")

    X_clean = clean_train[feature_cols]

    iso = IsolationForest(
        n_estimators=200,       # number of isolation trees
                                # more trees = more stable scores
                                # 200 is sufficient for this dataset size
        contamination=0.05,     # expected fraction of anomalies
                                # at inference time (not training time)
        max_samples="auto",     # samples per tree (auto = min(256, n_samples))
        random_state=42,
        n_jobs=-1               # use all CPU cores
    )

    iso.fit(X_clean)
    joblib.dump(iso, "anomaly_iso_model.pkl")
    print("Isolation Forest trained and saved: anomaly_iso_model.pkl")

    return iso


def apply_isolation_forest(iso, test_df, feature_cols):
    """
    Apply trained Isolation Forest to test set.
    Returns test_df with two new columns:
      iso_score      : raw anomaly score (more negative = more anomalous)
      is_anomaly_iso : binary flag (1=anomaly, 0=normal)
    """
    X_test = test_df[feature_cols]

    # Raw scores — continuous, used for ranking and paper plots
    test_df = test_df.copy()
    test_df["iso_score"] = iso.decision_function(X_test)

    # Binary prediction: -1=anomaly, 1=normal → convert to 1/0
    raw_pred = iso.predict(X_test)
    test_df["is_anomaly_iso"] = (raw_pred == -1).astype(int)

    n_flagged = test_df["is_anomaly_iso"].sum()
    print(f"\nIsolation Forest flagged: {n_flagged} / {len(test_df)} records "
          f"({n_flagged/len(test_df)*100:.1f}%)")
    print(f"Anomaly score range: "
          f"{test_df['iso_score'].min():.4f} to "
          f"{test_df['iso_score'].max():.4f}")

    return test_df


# ════════════════════════════════════════════════════════════
# COMPONENT 2 — CUSUM (Cumulative Sum Control Chart)
# ════════════════════════════════════════════════════════════
#
# CONCEPT RECAP:
#   CUSUM accumulates evidence of a sustained directional
#   change in O2. It answers: "has O2 been consistently
#   drifting downward for long enough to be concerning?"
#
#   The algorithm:
#     S(t) = max(0,  S(t-1) + (mu - O2(t)) - slack)
#
#   Where:
#     mu    = reference level (rolling mean of last 12 readings
#             = last 60 minutes, acts as "expected" O2)
#     slack = allowance for natural variation (set to 0.5 × std
#             of O2 in training data). Prevents noise from
#             triggering false alarms.
#     S(t)  = running cumulative evidence of downward drift
#
#   S(t) increases when O2 is below mu (drifting down).
#   S(t) resets to 0 when O2 recovers (max(0,...) ensures
#   the sum never goes negative — evidence resets on recovery).
#
#   Alert threshold h:
#     When S(t) > h, trigger a CUSUM alert.
#     h = 5 × std of O2 in training data (a common rule of thumb
#     in SPC literature — 5-sigma gives very few false alarms
#     while still catching sustained real drifts).
#     You can tune h: lower h = more sensitive (more false alarms),
#     higher h = less sensitive (may miss slow drifts).
#
#   WHY CUSUM CATCHES WHAT ISO FOREST MISSES:
#     ISO Forest looks at each point's feature vector.
#     Each slightly-below-normal reading looks "almost normal."
#     CUSUM sees 10 consecutive slightly-below-normal readings
#     and accumulates them into a significant signal.

def apply_cusum(test_df, train_df, slack_multiplier=0.5, threshold_multiplier=5.0):
    """
    Apply CUSUM detector to O2 time series in test set.

    Args:
        test_df             : test DataFrame with 'oxygen' column
        train_df            : train DataFrame (used to estimate mu and std)
        slack_multiplier    : slack = slack_multiplier × train_std
        threshold_multiplier: h = threshold_multiplier × train_std

    Returns:
        test_df with new columns:
          cusum_score      : running cumulative sum S(t)
          is_anomaly_cusum : binary flag (1 if S(t) > threshold)
    """
    print("\n" + "="*60)
    print("COMPONENT 2 — CUSUM DETECTOR")
    print("="*60)

    train_std  = train_df["oxygen"].std()
    slack      = slack_multiplier * train_std
    threshold  = threshold_multiplier * train_std

    print(f"Training O2 std       : {train_std:.4f}%")
    print(f"CUSUM slack (k)       : {slack:.4f}%")
    print(f"CUSUM threshold (h)   : {threshold:.4f}%")

    test_df = test_df.copy().reset_index(drop=True)
    o2_values = test_df["oxygen"].values

    cusum_scores = np.zeros(len(o2_values))
    cusum_flags  = np.zeros(len(o2_values), dtype=int)

    # Rolling reference: use 60-min rolling mean of O2 as "expected" level
    # Falls back to global train mean for first few records
    global_mu = train_df["oxygen"].mean()
    window    = 12  # 12 × 5min = 60 min rolling window

    S = 0.0  # running cumulative sum, starts at 0

    for i in range(len(o2_values)):
        # Reference level: rolling mean of last `window` O2 values
        # (or global mean if not enough history yet)
        if i < window:
            mu = global_mu
        else:
            mu = np.mean(o2_values[max(0, i - window):i])

        # CUSUM update: accumulate downward deviations
        S = max(0.0,  S + (mu - o2_values[i]) - slack)

        cusum_scores[i] = S
        cusum_flags[i]  = 1 if S > threshold else 0

    test_df["cusum_score"]       = cusum_scores
    test_df["is_anomaly_cusum"]  = cusum_flags

    n_flagged = cusum_flags.sum()
    print(f"CUSUM flagged         : {n_flagged} / {len(test_df)} records "
          f"({n_flagged/len(test_df)*100:.1f}%)")
    print(f"CUSUM score range     : "
          f"{cusum_scores.min():.4f} to {cusum_scores.max():.4f}")

    return test_df, threshold


# ════════════════════════════════════════════════════════════
# COMBINE DETECTORS
# ════════════════════════════════════════════════════════════
#
# OR logic: flag if EITHER detector fires.
#
# WHY OR AND NOT AND?
#   AND logic: only flag when BOTH detectors agree.
#     → High precision (fewer false positives)
#     → Low recall (misses anomalies only one detector catches)
#     → Dangerous for safety systems — you miss real threats.
#
#   OR logic: flag if either detector fires.
#     → High recall (catches more real anomalies)
#     → Lower precision (some false positives)
#     → Correct for safety systems — false alarm is acceptable,
#       missing a real dangerous O2 drop is not.
#
# COMBINED SEVERITY:
#   Both fire     → HIGH confidence anomaly
#   Only ISO      → Sudden multivariate outlier
#   Only CUSUM    → Gradual sustained drift
#   Neither       → Normal

def combine_detectors(test_df):
    print("\n" + "="*60)
    print("COMBINING DETECTORS (OR logic)")
    print("="*60)

    test_df = test_df.copy()
    test_df["final_anomaly"] = (
        (test_df["is_anomaly_iso"] == 1) |
        (test_df["is_anomaly_cusum"] == 1)
    ).astype(int)

    # Detector agreement categories
    def categorise(row):
        iso   = row["is_anomaly_iso"]
        cusum = row["is_anomaly_cusum"]
        if iso == 1 and cusum == 1:
            return "both"
        elif iso == 1:
            return "iso_only"
        elif cusum == 1:
            return "cusum_only"
        else:
            return "normal"

    test_df["detector_category"] = test_df.apply(categorise, axis=1)

    counts = test_df["detector_category"].value_counts()
    print("Detector agreement breakdown:")
    for cat, count in counts.items():
        print(f"  {cat:<15} : {count:>4} records")

    total_flagged = test_df["final_anomaly"].sum()
    actual_anomalies = test_df["is_anomaly"].sum()
    print(f"\nTotal flagged (final) : {total_flagged}")
    print(f"Actual anomalies      : {actual_anomalies}")

    return test_df


# ════════════════════════════════════════════════════════════
# EVALUATE ANOMALY DETECTION PERFORMANCE
# ════════════════════════════════════════════════════════════
#
# Since our synthetic data has ground truth (is_anomaly column
# we created in Phase 1), we can compute proper ML metrics.
#
# METRICS EXPLAINED:
#
#   True Positive (TP):  Model flags it AND it is actually anomalous
#   False Positive (FP): Model flags it BUT it is actually normal
#                        (false alarm)
#   True Negative (TN):  Model says normal AND it is actually normal
#   False Negative (FN): Model says normal BUT it is actually anomalous
#                        (missed detection — most dangerous)
#
#   Precision = TP / (TP + FP)
#     "Of all records I flagged, what fraction were real anomalies?"
#     High precision = few false alarms
#
#   Recall = TP / (TP + FN)
#     "Of all real anomalies, what fraction did I catch?"
#     High recall = few missed detections
#     THIS IS THE PRIORITY METRIC for a safety system.
#
#   F1 Score = 2 × (Precision × Recall) / (Precision + Recall)
#     Harmonic mean — balances both. Use as headline metric in paper.
#
#   For safety systems: recall > precision in importance.
#   A missed dangerous O2 drop is worse than a false alarm.

def evaluate_detectors(test_df):
    print("\n" + "="*60)
    print("ANOMALY DETECTION EVALUATION")
    print("="*60)

    y_true = test_df["is_anomaly"].values
    detectors = {
        "Isolation Forest" : test_df["is_anomaly_iso"].values,
        "CUSUM"            : test_df["is_anomaly_cusum"].values,
        "Combined (OR)"    : test_df["final_anomaly"].values,
    }

    results = []
    for name, y_pred in detectors.items():
        prec = precision_score(y_true, y_pred, zero_division=0)
        rec  = recall_score(y_true, y_pred, zero_division=0)
        f1   = f1_score(y_true, y_pred, zero_division=0)
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
        fpr  = fp / (fp + tn) if (fp + tn) > 0 else 0

        results.append({
            "Detector"   : name,
            "Precision"  : round(prec, 4),
            "Recall"     : round(rec,  4),
            "F1"         : round(f1,   4),
            "TP"         : int(tp),
            "FP"         : int(fp),
            "FN"         : int(fn),
            "TN"         : int(tn),
            "FPR"        : round(fpr,  4),
        })

        print(f"\n{name}:")
        print(f"  Precision : {prec:.4f}  "
              f"(of flagged records, {prec*100:.1f}% were real anomalies)")
        print(f"  Recall    : {rec:.4f}  "
              f"(caught {rec*100:.1f}% of all real anomalies)")
        print(f"  F1 Score  : {f1:.4f}")
        print(f"  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
        print(f"  False Positive Rate: {fpr:.4f}")

    results_df = pd.DataFrame(results)
    print("\n" + "-"*60)
    print("SUMMARY TABLE:")
    print(results_df[["Detector","Precision","Recall","F1","FPR"]]
          .to_string(index=False))

    return results_df


# ════════════════════════════════════════════════════════════
# AC RECIRCULATION EXPERIMENT
# ════════════════════════════════════════════════════════════
#
# This is your research paper's key finding section.
#
# HYPOTHESIS:
#   H0 (null):     AC status has no effect on O2 depletion rate
#   H1 (alternate): AC on → faster O2 depletion (recirculation
#                   traps stale air, reduces fresh air exchange)
#
# METHOD:
#   1. Calculate O2 depletion rate (ΔO2/Δt) for each timestep
#   2. Split into AC-on and AC-off groups (at same occupancy)
#   3. Compare mean depletion rates
#   4. Test statistical significance with Mann-Whitney U test
#      (non-parametric — does not assume normal distribution,
#       appropriate for sensor data which may be skewed)
#
# MANN-WHITNEY U TEST:
#   Tests whether two groups have different distributions
#   without assuming normality. p < 0.05 means the difference
#   is statistically significant — not due to random chance.
#   This is what makes your finding publishable rather than
#   just observational.
#
# NOTE: This uses synthetic data for now. On real data, this
# experiment is your headline finding. The synthetic result
# will still demonstrate the methodology clearly.

def run_ac_experiment(feat_df):
    print("\n" + "="*60)
    print("AC RECIRCULATION EXPERIMENT")
    print("="*60)

    if "ac_status" not in feat_df.columns:
        print("ac_status column not found — skipping AC experiment")
        return None

    df = feat_df.copy()
    df = df[df["is_anomaly"] == 0]  # exclude anomalies for clean comparison

    # O2 depletion rate = change in O2 per timestep
    df["o2_depletion_rate"] = -df["oxygen"].diff()
    # Positive values = O2 decreasing (depletion)
    # Negative values = O2 increasing (recovery)

    # Control for occupancy: only compare at similar occupancy levels
    # Use occupancy_count if available, else use all records
    if "occupancy_count" in df.columns:
        # Focus on moderate occupancy (2-4 people) where AC effect is clearest
        df_controlled = df[df["occupancy_count"].between(2, 4)]
        print(f"Records with 2-4 people occupancy: {len(df_controlled)}")
    else:
        df_controlled = df
        print("No occupancy data — comparing across all records")

    ac_on  = df_controlled[df_controlled["ac_status"] == 1]["o2_depletion_rate"].dropna()
    ac_off = df_controlled[df_controlled["ac_status"] == 0]["o2_depletion_rate"].dropna()

    if len(ac_on) < 10 or len(ac_off) < 10:
        print("Insufficient data for AC experiment in this split")
        print(f"  AC on records: {len(ac_on)}, AC off records: {len(ac_off)}")
        # Still run on full dataset
        ac_on  = df[df["ac_status"] == 1]["o2_depletion_rate"].dropna()
        ac_off = df[df["ac_status"] == 0]["o2_depletion_rate"].dropna()
        print(f"Falling back to all records: AC on={len(ac_on)}, AC off={len(ac_off)}")

    # Descriptive statistics
    print(f"\nO2 Depletion Rate Statistics (% per 5-min interval):")
    print(f"  AC ON  — mean: {ac_on.mean():.5f}  "
          f"std: {ac_on.std():.5f}  "
          f"median: {ac_on.median():.5f}")
    print(f"  AC OFF — mean: {ac_off.mean():.5f}  "
          f"std: {ac_off.std():.5f}  "
          f"median: {ac_off.median():.5f}")

    # Mann-Whitney U test
    u_stat, p_value = stats.mannwhitneyu(ac_on, ac_off, alternative="two-sided")
    print(f"\nMann-Whitney U Test:")
    print(f"  U statistic : {u_stat:.2f}")
    print(f"  p-value     : {p_value:.6f}")

    if p_value < 0.001:
        sig_label = "p < 0.001 (highly significant)"
    elif p_value < 0.01:
        sig_label = "p < 0.01 (significant)"
    elif p_value < 0.05:
        sig_label = "p < 0.05 (significant)"
    else:
        sig_label = f"p = {p_value:.4f} (not significant)"

    print(f"  Result      : {sig_label}")

    if p_value < 0.05:
        direction = "higher" if ac_on.mean() > ac_off.mean() else "lower"
        print(f"\n  FINDING: AC-ON rooms show {direction} O2 depletion rate")
        print(f"  This supports H1: AC recirculation affects O2 dynamics")
        print(f"  Paper statement: 'AC status was associated with a "
              f"statistically significant difference in O2 depletion rate "
              f"(Mann-Whitney U, {sig_label})'")
    else:
        print(f"\n  FINDING: No significant AC effect detected on synthetic data")
        print(f"  NOTE: Real data may show stronger effect — synthetic model")
        print(f"  uses simplified AC recovery constant. Test again with real data.")

    return {
        "ac_on_mean"  : ac_on.mean(),
        "ac_off_mean" : ac_off.mean(),
        "p_value"     : p_value,
        "significant" : p_value < 0.05,
        "n_ac_on"     : len(ac_on),
        "n_ac_off"    : len(ac_off),
    }


# ════════════════════════════════════════════════════════════
# COMPONENT 3 — RECOMMENDATION ENGINE
# ════════════════════════════════════════════════════════════
#
# DESIGN PRINCIPLE:
#   Deterministic rule table — given current state, always
#   produces the same recommendation. No probability, no
#   ambiguity. Safety systems require this.
#
# PRIORITY ORDER (rules checked top to bottom, first match wins):
#   1. O2 critically low RIGHT NOW         → CRITICAL
#   2. O2 predicted critical in 5 min      → PREDICTIVE CRITICAL
#   3. O2 warning level RIGHT NOW          → WARNING
#   4. O2 predicted warning in 10 min      → PREDICTIVE WARNING
#   5. Rapid O2 drop rate detected         → RATE WARNING
#   6. CUSUM drift alert (gradual decline) → DRIFT ADVISORY
#   7. Isolation Forest anomaly            → SENSOR ADVISORY
#   8. Everything normal                   → OK
#
# The predictive rules (2 and 4) are your system's key value
# over simple threshold alarms — they act BEFORE danger arrives.

THRESHOLDS = {
    "critical_o2"        : 19.5,   # % O2 — immediate danger
    "warning_o2"         : 20.0,   # % O2 — early warning
    "rapid_drop_rate"    : 0.10,   # % O2 per 5-min interval
    "cusum_advisory"     : 0.3,    # fraction of CUSUM threshold
}

def generate_recommendation(row, cusum_threshold):
    """
    Generate a recommendation for a single sensor reading.

    Args:
        row             : a single row of the results DataFrame
        cusum_threshold : the h value computed during CUSUM setup

    Returns:
        dict with keys: severity, message, buzzer, action_code
        action_code: 0=nothing, 1=LCD only, 2=buzzer+LCD, 3=critical
    """
    o2       = row.get("oxygen", 21.0)
    fc5      = row.get("forecast_5min",  o2)
    fc10     = row.get("forecast_10min", o2)
    delta    = row.get("o2_delta_1", 0.0)
    cusum    = row.get("cusum_score", 0.0)
    iso_flag = row.get("is_anomaly_iso", 0)

    # ── Rule 1: O2 critically low right now ──────────────────
    if o2 < THRESHOLDS["critical_o2"]:
        return {
            "severity"    : "CRITICAL",
            "message"     : "OXYGEN CRITICALLY LOW! Ventilate immediately.",
            "buzzer"      : "continuous",
            "action_code" : 3
        }

    # ── Rule 2: O2 predicted critical in 5 min ───────────────
    if fc5 < THRESHOLDS["critical_o2"]:
        return {
            "severity"    : "PREDICTIVE_CRITICAL",
            "message"     : "Oxygen predicted critical in 5 min. Act now.",
            "buzzer"      : "3 rapid beeps",
            "action_code" : 3
        }

    # ── Rule 3: O2 at warning level right now ────────────────
    if o2 < THRESHOLDS["warning_o2"]:
        return {
            "severity"    : "WARNING",
            "message"     : "Oxygen below safe level. Increase ventilation.",
            "buzzer"      : "3 beeps every 30s",
            "action_code" : 2
        }

    # ── Rule 4: O2 predicted warning in 10 min ───────────────
    if fc10 < THRESHOLDS["warning_o2"]:
        return {
            "severity"    : "PREDICTIVE_WARNING",
            "message"     : "Oxygen predicted low in 10 min. Prepare ventilation.",
            "buzzer"      : "1 beep",
            "action_code" : 2
        }

    # ── Rule 5: Rapid O2 drop rate ───────────────────────────
    if delta < -THRESHOLDS["rapid_drop_rate"]:
        return {
            "severity"    : "RATE_WARNING",
            "message"     : "Rapid oxygen drop detected. Monitor closely.",
            "buzzer"      : "2 beeps",
            "action_code" : 2
        }

    # ── Rule 6: CUSUM drift ──────────────────────────────────
    if cusum > cusum_threshold * THRESHOLDS["cusum_advisory"]:
        return {
            "severity"    : "DRIFT_ADVISORY",
            "message"     : "Sustained oxygen decline detected. Check ventilation.",
            "buzzer"      : "none",
            "action_code" : 1
        }

    # ── Rule 7: ISO Forest anomaly (but O2 still OK) ─────────
    if iso_flag == 1:
        return {
            "severity"    : "SENSOR_ADVISORY",
            "message"     : "Unusual sensor pattern. Check O2 sensor calibration.",
            "buzzer"      : "none",
            "action_code" : 1
        }

    # ── Rule 8: All clear ────────────────────────────────────
    return {
        "severity"    : "OK",
        "message"     : "Air quality normal.",
        "buzzer"      : "none",
        "action_code" : 0
    }


def apply_recommendations(test_df, cusum_threshold):
    print("\n" + "="*60)
    print("COMPONENT 3 — RECOMMENDATION ENGINE")
    print("="*60)

    recs = test_df.apply(
        lambda row: generate_recommendation(row, cusum_threshold),
        axis=1
    )

    test_df = test_df.copy()
    test_df["rec_severity"]    = recs.apply(lambda r: r["severity"])
    test_df["rec_message"]     = recs.apply(lambda r: r["message"])
    test_df["rec_buzzer"]      = recs.apply(lambda r: r["buzzer"])
    test_df["rec_action_code"] = recs.apply(lambda r: r["action_code"])

    print("Recommendation severity distribution:")
    dist = test_df["rec_severity"].value_counts()
    for sev, count in dist.items():
        pct = count / len(test_df) * 100
        print(f"  {sev:<25} : {count:>4} records ({pct:.1f}%)")

    return test_df


# ════════════════════════════════════════════════════════════
# PLOTS
# ════════════════════════════════════════════════════════════

def plot_anomaly_scores(test_df):
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)
    fig.suptitle("Anomaly Detection Results — Test Set", fontsize=13)

    ts = pd.to_datetime(test_df["timestamp"])

    # ── O2 time series with flags ────────────────────────────
    axes[0].plot(ts, test_df["oxygen"], color="#2196F3",
                 linewidth=0.9, label="O2 (%)", zorder=2)
    mask_true = test_df["is_anomaly"] == 1
    mask_iso  = test_df["is_anomaly_iso"] == 1
    mask_both = mask_true & mask_iso

    axes[0].scatter(ts[mask_true & ~mask_iso],
                    test_df.loc[mask_true & ~mask_iso, "oxygen"],
                    color="orange", s=25, zorder=4, label="Missed anomaly")
    axes[0].scatter(ts[mask_iso & ~mask_true],
                    test_df.loc[mask_iso & ~mask_true, "oxygen"],
                    color="yellow", s=25, zorder=4, label="False positive")
    axes[0].scatter(ts[mask_both],
                    test_df.loc[mask_both, "oxygen"],
                    color="red", s=30, zorder=5, label="True positive")
    axes[0].axhline(THRESHOLDS["critical_o2"], color="red",
                    linestyle="--", alpha=0.5, linewidth=0.8)
    axes[0].axhline(THRESHOLDS["warning_o2"],  color="orange",
                    linestyle="--", alpha=0.5, linewidth=0.8)
    axes[0].set_ylabel("O2 (%)")
    axes[0].legend(fontsize=8, loc="lower right")
    axes[0].set_title("O2 Time Series with Anomaly Flags")

    # ── Isolation Forest anomaly score ───────────────────────
    axes[1].plot(ts, test_df["iso_score"], color="#9C27B0",
                 linewidth=0.8)
    axes[1].axhline(0, color="red", linestyle="--",
                    alpha=0.7, linewidth=1, label="Decision boundary (score=0)")
    axes[1].fill_between(ts, test_df["iso_score"], 0,
                          where=test_df["iso_score"] < 0,
                          color="#9C27B0", alpha=0.2, label="Anomalous region")
    axes[1].set_ylabel("ISO Score")
    axes[1].set_title("Isolation Forest Anomaly Score "
                       "(more negative = more anomalous)")
    axes[1].legend(fontsize=8)

    # ── CUSUM score ──────────────────────────────────────────
    axes[2].plot(ts, test_df["cusum_score"], color="#FF5722",
                 linewidth=0.8, label="CUSUM score S(t)")
    cusum_thresh = test_df["cusum_score"].quantile(0.95)
    axes[2].axhline(cusum_thresh, color="red", linestyle="--",
                    alpha=0.7, linewidth=1, label=f"Threshold={cusum_thresh:.3f}")
    axes[2].fill_between(ts, test_df["cusum_score"], cusum_thresh,
                          where=test_df["cusum_score"] > cusum_thresh,
                          color="#FF5722", alpha=0.2, label="CUSUM alert")
    axes[2].set_ylabel("CUSUM Score")
    axes[2].set_title("CUSUM Score — Sustained Drift Detector")
    axes[2].legend(fontsize=8)

    plt.xticks(rotation=20, fontsize=7)
    plt.tight_layout()
    plt.savefig("plot11_anomaly_scores.png", dpi=130)
    plt.close()
    print("Saved: plot11_anomaly_scores.png")


def plot_detector_comparison(test_df, eval_results_df):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Detector Performance Comparison", fontsize=12)

    # Confusion matrix for combined detector
    y_true = test_df["is_anomaly"].values
    y_pred = test_df["final_anomaly"].values
    cm = confusion_matrix(y_true, y_pred)

    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=axes[0],
                xticklabels=["Pred Normal","Pred Anomaly"],
                yticklabels=["True Normal","True Anomaly"])
    axes[0].set_title("Confusion Matrix — Combined Detector")
    axes[0].set_ylabel("Actual")
    axes[0].set_xlabel("Predicted")

    # Bar chart: Precision, Recall, F1 for all three detectors
    metrics = ["Precision", "Recall", "F1"]
    x = np.arange(len(eval_results_df))
    w = 0.25
    colors = ["#2196F3", "#4CAF50", "#FF5722"]

    for i, (metric, color) in enumerate(zip(metrics, colors)):
        bars = axes[1].bar(x + i*w, eval_results_df[metric], w,
                           label=metric, color=color, alpha=0.85)
        for bar in bars:
            axes[1].text(bar.get_x() + bar.get_width()/2,
                         bar.get_height() + 0.01,
                         f"{bar.get_height():.3f}",
                         ha="center", va="bottom", fontsize=8)

    axes[1].set_xticks(x + w)
    axes[1].set_xticklabels(eval_results_df["Detector"], rotation=10, fontsize=9)
    axes[1].set_ylabel("Score")
    axes[1].set_ylim(0, 1.15)
    axes[1].set_title("Precision / Recall / F1 by Detector")
    axes[1].legend()
    axes[1].axhline(0.8, color="gray", linestyle=":", alpha=0.5)

    plt.tight_layout()
    plt.savefig("plot13_detector_comparison.png", dpi=130)
    plt.close()
    print("Saved: plot13_detector_comparison.png")


def plot_recommendation_distribution(test_df):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Recommendation Engine Output Distribution", fontsize=12)

    severity_order = ["OK","SENSOR_ADVISORY","DRIFT_ADVISORY",
                      "RATE_WARNING","PREDICTIVE_WARNING",
                      "WARNING","PREDICTIVE_CRITICAL","CRITICAL"]
    severity_colors = {
        "OK"                  : "#4CAF50",
        "SENSOR_ADVISORY"     : "#8BC34A",
        "DRIFT_ADVISORY"      : "#FFC107",
        "RATE_WARNING"        : "#FF9800",
        "PREDICTIVE_WARNING"  : "#FF5722",
        "WARNING"             : "#F44336",
        "PREDICTIVE_CRITICAL" : "#9C27B0",
        "CRITICAL"            : "#B71C1C",
    }

    dist = test_df["rec_severity"].value_counts()
    present = [s for s in severity_order if s in dist.index]
    counts  = [dist[s] for s in present]
    colors  = [severity_colors[s] for s in present]

    # Pie chart
    axes[0].pie(counts, labels=present, colors=colors,
                autopct="%1.1f%%", startangle=90,
                textprops={"fontsize": 8})
    axes[0].set_title("Recommendation Severity Distribution")

    # Bar chart over time (action code)
    ts = pd.to_datetime(test_df["timestamp"])
    axes[1].fill_between(ts, test_df["rec_action_code"],
                          step="post", alpha=0.7, color="#2196F3")
    axes[1].set_yticks([0, 1, 2, 3])
    axes[1].set_yticklabels(["OK","Advisory","Warning","Critical"])
    axes[1].set_xlabel("Time")
    axes[1].set_title("Action Level Over Time (Test Period)")
    axes[1].axhline(2, color="orange", linestyle="--",
                    alpha=0.5, linewidth=0.8)
    axes[1].axhline(3, color="red", linestyle="--",
                    alpha=0.5, linewidth=0.8)
    plt.xticks(rotation=20, fontsize=7)

    plt.tight_layout()
    plt.savefig("plot14_recommendation_dist.png", dpi=130)
    plt.close()
    print("Saved: plot14_recommendation_dist.png")


# ════════════════════════════════════════════════════════════
# ADD FORECASTS TO TEST DF (needed for recommendations)
# ════════════════════════════════════════════════════════════

def add_forecasts(test_df, feature_cols):
    xgb5  = joblib.load("model_xgb_5min.pkl")
    xgb10 = joblib.load("model_xgb_10min.pkl")
    X_test = test_df[feature_cols]
    test_df = test_df.copy()
    test_df["forecast_5min"]  = xgb5.predict(X_test)
    test_df["forecast_10min"] = xgb10.predict(X_test)
    print("Forecasts added: forecast_5min, forecast_10min")
    return test_df


# ════════════════════════════════════════════════════════════
# SAVE SUMMARY
# ════════════════════════════════════════════════════════════

def save_summary(eval_df, ac_result, test_df):
    lines = [
        "PHASE 4 SUMMARY REPORT",
        "="*60,
        "",
        "ANOMALY DETECTION METRICS:",
        eval_df[["Detector","Precision","Recall","F1","FPR"]]
        .to_string(index=False),
        "",
    ]

    if ac_result:
        lines += [
            "AC RECIRCULATION EXPERIMENT:",
            f"  AC ON  mean depletion rate : {ac_result['ac_on_mean']:.6f}% per 5min",
            f"  AC OFF mean depletion rate : {ac_result['ac_off_mean']:.6f}% per 5min",
            f"  Mann-Whitney p-value       : {ac_result['p_value']:.6f}",
            f"  Statistically significant  : {ac_result['significant']}",
            "",
        ]

    sev_dist = test_df["rec_severity"].value_counts()
    lines += [
        "RECOMMENDATION DISTRIBUTION:",
        sev_dist.to_string(),
        "",
        "SAVED FILES:",
        "  anomaly_iso_model.pkl",
        "  phase4_results.csv",
        "  plot11_anomaly_scores.png",
        "  plot13_detector_comparison.png",
        "  plot14_recommendation_dist.png",
        "",
        "NEXT: Run phase5_production_loop.py"
    ]

    with open("phase4_summary.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("phase4_summary.txt saved.")


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("="*60)
    print("PHASE 4 — ANOMALY DETECTION + RECOMMENDATION ENGINE")
    print("="*60)

    # Load
    train_df, test_df, feat_df, feature_cols = load_data()

    # Add forecasts (needed for predictive recommendations)
    test_df = add_forecasts(test_df, feature_cols)

    # Component 1: Isolation Forest
    iso = train_isolation_forest(train_df, feature_cols)
    test_df = apply_isolation_forest(iso, test_df, feature_cols)

    # Component 2: CUSUM
    test_df, cusum_threshold = apply_cusum(test_df, train_df)

    # Combine detectors
    test_df = combine_detectors(test_df)

    # Evaluate
    eval_results = evaluate_detectors(test_df)

    # AC experiment
    ac_result = run_ac_experiment(feat_df)

    # Recommendations
    test_df = apply_recommendations(test_df, cusum_threshold)

    # Plots
    print("\n" + "="*60)
    print("GENERATING PLOTS")
    print("="*60)
    plot_anomaly_scores(test_df)
    plot_detector_comparison(test_df, eval_results)
    plot_recommendation_distribution(test_df)

    # Save results
    test_df.to_csv("phase4_results.csv", index=False)
    print("Saved: phase4_results.csv")
    save_summary(eval_results, ac_result, test_df)

    # Final check
    print("\n" + "="*60)
    print("PHASE 4 FINAL CHECK")
    print("="*60)
    files = ["anomaly_iso_model.pkl", "phase4_results.csv",
             "plot11_anomaly_scores.png",
             "plot13_detector_comparison.png",
             "plot14_recommendation_dist.png",
             "phase4_summary.txt"]
    all_ok = True
    for f in files:
        exists = os.path.exists(f)
        print(f"  [{'PASS' if exists else 'FAIL'}] {f}")
        if not exists:
            all_ok = False

    if all_ok:
        print("\nALL FILES SAVED")
        print("PHASE 4 COMPLETE — Ready for Phase 5 Production Loop")
        print("\nKey results to note for your paper:")
        best = eval_results.loc[eval_results["F1"].idxmax()]
        print(f"  Best detector : {best['Detector']}")
        print(f"  F1 Score      : {best['F1']:.4f}")
        print(f"  Recall        : {best['Recall']:.4f} "
              f"(caught {best['Recall']*100:.1f}% of anomalies)")
        print(f"  Precision     : {best['Precision']:.4f}")
