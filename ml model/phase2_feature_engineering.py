# ============================================================
# PHASE 2 — Feature Engineering (Single File, All Tasks)
# ============================================================
# HOW TO RUN:
#   python phase2_feature_engineering.py
#
# WHAT IT PRODUCES:
#   featured_data.csv         — full engineered dataset
#   train_data.csv            — 80% split (chronological)
#   test_data.csv             — 20% split (chronological)
#   plot4_acf_pacf.png        — tells you how many lags matter
#   plot5_feature_heatmap.png — feature correlation with targets
#   plot6_target_analysis.png — distribution of what we're predicting
#   phase2_summary.txt        — stats report for your records
#
# RUN ORDER: Run AFTER task1_fix_timestamps.py
#
# CONCEPTS EXPLAINED INLINE — read the comments as you go.
# ============================================================

import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
import warnings
warnings.filterwarnings("ignore")

# ── 0. Firebase init (reused from Phase 1 fix) ──────────────

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://iot-cfees-default-rtdb.asia-southeast1.firebasedatabase.app"
        })
    return db


def parse_timestamp_robust(ts_value):
    try:
        parsed = pd.to_datetime(ts_value, utc=False)
        if parsed.tzinfo is None:
            parsed = parsed.tz_localize("UTC")
        return parsed
    except Exception:
        return pd.NaT


def fetch_sensor_data_fixed(n_records=None):
    """Fetch from Firebase into clean DataFrame. Reused from Phase 1."""
    database = init_firebase()
    ref = database.reference("/sensors/room1/readings")
    raw = (ref.order_by_key().limit_to_last(n_records).get()
           if n_records else ref.get())
    if raw is None:
        return pd.DataFrame()
    df = pd.DataFrame(raw.values())
    df["timestamp"] = df["timestamp"].apply(parse_timestamp_robust)
    for col in ["oxygen","temperature","humidity",
                "occupancy_count","ac_status","is_anomaly"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("timestamp").reset_index(drop=True)


# ═══════════════════════════════════════════════════════════
# TASK 2.1 — ACF / PACF ANALYSIS
# ═══════════════════════════════════════════════════════════
#
# CONCEPT — What is ACF?
#   ACF (AutoCorrelation Function) measures how correlated O2
#   is with its own past values at different time lags.
#   Lag 1 = correlation of O2(t) with O2(t-1), i.e. 5 min ago.
#   Lag 3 = correlation with O2(t-3), i.e. 15 min ago.
#   If ACF at lag 6 is still high, 30 min ago still matters.
#
# CONCEPT — What is PACF?
#   PACF (Partial ACF) removes the "indirect" correlations.
#   Example: O2(t) is correlated with O2(t-2) partly BECAUSE
#   it's correlated with O2(t-1), which is correlated with O2(t-2).
#   PACF strips that indirect effect out.
#   WHERE PACF DROPS TO NEAR ZERO = how many direct lags you need.
#
# WHAT TO LOOK FOR IN THE PLOT:
#   Blue shaded region = 95% confidence interval (not significant)
#   Bars outside the blue region = significant lag
#   If PACF is significant at lags 1,2,3 but not 4+ → use 3 lags.
#
# WHY THIS MATTERS FOR YOUR RESEARCH PAPER:
#   Instead of saying "we used 6 lags because it seemed good",
#   you say "PACF analysis (Figure X) shows significant partial
#   autocorrelation up to lag N, justifying our use of N lag features."
#   That is proper scientific methodology.

def run_acf_pacf_analysis(df, save_path="plot4_acf_pacf.png"):
    """
    Run ACF and PACF on the O2 time series.
    Returns the last significant PACF lag as recommended n_lags.
    """
    print("\n" + "="*60)
    print("TASK 2.1 — ACF / PACF ANALYSIS")
    print("="*60)

    o2_series = df["oxygen"].dropna()
    n_lags_to_show = 30  # show up to 30 lags = 150 minutes back

    fig, axes = plt.subplots(2, 1, figsize=(12, 7))
    fig.suptitle("O2 Autocorrelation Analysis\n"
                 "(bars outside blue band = statistically significant lag)",
                 fontsize=13)

    plot_acf(o2_series, lags=n_lags_to_show, ax=axes[0],
             title="ACF — Total autocorrelation at each lag\n"
                   "(includes indirect effects)")
    axes[0].set_xlabel("Lag (1 lag = 5 minutes)")
    axes[0].set_ylabel("Correlation")

    plot_pacf(o2_series, lags=n_lags_to_show, ax=axes[1], method="ywm",
              title="PACF — Direct autocorrelation at each lag\n"
                    "(use this to decide how many lags to include as features)")
    axes[1].set_xlabel("Lag (1 lag = 5 minutes)")
    axes[1].set_ylabel("Partial Correlation")

    plt.tight_layout()
    plt.savefig(save_path, dpi=130)
    plt.close()
    print(f"ACF/PACF plot saved: {save_path}")
    print("OPEN THIS PLOT and look at PACF (bottom graph).")
    print("Count how many bars are OUTSIDE the blue shaded band.")

    # Compute PACF values programmatically to recommend n_lags
    from statsmodels.tsa.stattools import pacf
    pacf_vals, confint = pacf(o2_series, nlags=n_lags_to_show,
                               method="ywm", alpha=0.05)
    # Confidence interval half-width
    ci_half = confint[:, 1] - pacf_vals  # upper CI - point estimate
    significant_lags = [lag for lag in range(1, n_lags_to_show+1)
                        if abs(pacf_vals[lag]) > ci_half[lag]]

    recommended_lags = max(significant_lags) if significant_lags else 3

    print(f"\nPACF significant lags (outside 95% CI): {significant_lags}")
    print(f"Recommended n_lags for features       : {recommended_lags}")
    print(f"  → means: use O2 values from up to {recommended_lags * 5} minutes ago")
    print(f"  → feature names will be: o2_lag1 through o2_lag{recommended_lags}")

    return recommended_lags, significant_lags


# ═══════════════════════════════════════════════════════════
# TASK 2.2 — FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════
#
# CONCEPT — Why each feature type:
#
# LAG FEATURES (o2_lag1, o2_lag2, ...):
#   Gives the model explicit memory. Without these, the model
#   only sees current O2 and has no idea if it's been falling
#   for the last 20 minutes (danger) vs. just dipped briefly.
#
# RATE OF CHANGE (o2_delta_1, o2_delta_3):
#   First derivative of O2. Captures trend direction and speed.
#   o2_delta_1 = how much O2 changed in last 5 min (short trend)
#   o2_delta_3 = how much O2 changed in last 15 min (medium trend)
#   A model seeing O2=20.5 with delta=-0.1 should predict lower
#   than one seeing O2=20.5 with delta=+0.05.
#
# ROLLING MEAN (o2_roll_mean_3):
#   Smoothed version of recent O2 — reduces sensor noise effect.
#   3-step rolling mean = average of last 15 minutes.
#
# ROLLING STD (o2_roll_std_3):
#   Measures local volatility. High std = unstable/noisy readings.
#   Useful for anomaly detection too (anomalies = sudden high std).
#
# CYCLICAL TIME ENCODING (hour_sin, hour_cos):
#   Hour 0 and hour 23 are adjacent in real time but 23 apart
#   numerically. Sin/cos maps hour to a circle so the model
#   understands continuity across midnight.
#   hour_sin = sin(2π * hour / 24)
#   hour_cos = cos(2π * hour / 24)
#   Together they uniquely encode every hour on a unit circle.
#
# TARGETS (target_5min, target_10min):
#   What your model is trying to predict.
#   target_5min  = oxygen value 1 step ahead  (5 min into future)
#   target_10min = oxygen value 2 steps ahead (10 min into future)
#   Created by shifting oxygen column backward by 1 and 2 rows.

def engineer_features(df: pd.DataFrame, n_lags: int = 6) -> pd.DataFrame:
    """
    Add all ML features to the raw sensor DataFrame.

    Args:
        df     : DataFrame with at least: timestamp, oxygen, temperature, humidity
        n_lags : How many lag steps to create (from PACF analysis)

    Returns:
        DataFrame with original columns + all engineered features + targets.
        Rows with NaN (from lag/rolling operations) are dropped.
    """
    df = df.copy().sort_values("timestamp").reset_index(drop=True)

    # ── Lag features ────────────────────────────────────────
    # For lags: 1,2,3,6 always; add up to n_lags from PACF
    lag_steps = sorted(set([1, 2, 3, 6] + list(range(1, n_lags + 1))))
    lag_steps = [l for l in lag_steps if l <= 12]  # cap at 1 hour back

    for lag in lag_steps:
        df[f"o2_lag{lag}"]   = df["oxygen"].shift(lag)
        df[f"temp_lag{lag}"] = df["temperature"].shift(lag)
        df[f"hum_lag{lag}"]  = df["humidity"].shift(lag)

    # ── Rate of change ───────────────────────────────────────
    df["o2_delta_1"]  = df["oxygen"].diff(1)      # change over 5 min
    df["o2_delta_3"]  = df["oxygen"].diff(3)      # change over 15 min
    df["o2_delta_6"]  = df["oxygen"].diff(6)      # change over 30 min
    df["temp_delta_1"] = df["temperature"].diff(1)
    df["hum_delta_1"]  = df["humidity"].diff(1)

    # ── Rolling statistics ───────────────────────────────────
    df["o2_roll_mean_3"]  = df["oxygen"].rolling(3).mean()   # 15-min mean
    df["o2_roll_mean_6"]  = df["oxygen"].rolling(6).mean()   # 30-min mean
    df["o2_roll_std_3"]   = df["oxygen"].rolling(3).std()    # 15-min volatility
    df["temp_roll_mean_3"] = df["temperature"].rolling(3).mean()
    df["hum_roll_mean_3"]  = df["humidity"].rolling(3).mean()

    # ── Cyclical time encoding ───────────────────────────────
    hour = df["timestamp"].dt.hour.astype(float)
    df["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24)

    # Day of week (0=Mon, 6=Sun) — useful if occupancy varies by day
    dow = df["timestamp"].dt.dayofweek.astype(float)
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7)

    # ── Optional features (only if columns exist) ───────────
    if "occupancy_count" in df.columns:
        df["occ_lag1"]         = df["occupancy_count"].shift(1)
        df["occ_roll_mean_3"]  = df["occupancy_count"].rolling(3).mean()
        df["occ_delta_1"]      = df["occupancy_count"].diff(1)

    if "ac_status" in df.columns:
        df["ac_lag1"]          = df["ac_status"].shift(1)

    # ── TARGET VARIABLES ─────────────────────────────────────
    # shift(-1): the O2 value 1 row later = 5 minutes in the future
    # shift(-2): the O2 value 2 rows later = 10 minutes in the future
    # These rows CANNOT be at the end of the DataFrame (no future data there)
    df["target_5min"]  = df["oxygen"].shift(-1)
    df["target_10min"] = df["oxygen"].shift(-2)

    # ── Drop rows with NaN (from shift/rolling operations) ──
    # These appear at the START (lags) and END (targets) of the series
    n_before = len(df)
    df = df.dropna().reset_index(drop=True)
    n_after = len(df)
    print(f"  Rows before feature engineering : {n_before}")
    print(f"  Rows dropped (NaN from lags)    : {n_before - n_after}")
    print(f"  Rows after feature engineering  : {n_after}")

    return df


def get_feature_columns(df: pd.DataFrame) -> list:
    """
    Automatically build the feature column list from what exists in df.
    Excludes target columns, raw source columns, and metadata.
    Call this before training to get your X columns.
    """
    # Columns that are NOT features
    exclude = {"timestamp", "source", "is_anomaly",
               "target_5min", "target_10min",
               "oxygen", "temperature", "humidity"}
    # Also exclude raw optional columns (we have lag versions instead)
    if "occupancy_count" in df.columns:
        exclude.add("occupancy_count")
    if "ac_status" in df.columns:
        exclude.add("ac_status")

    feature_cols = [c for c in df.columns if c not in exclude]
    return feature_cols


# ═══════════════════════════════════════════════════════════
# TASK 2.3 — FEATURE VALIDATION (plots + stats)
# ═══════════════════════════════════════════════════════════

def validate_features(df: pd.DataFrame, feature_cols: list):
    """
    Generate correlation heatmap between features and targets.
    High correlation with target = useful feature.
    High correlation between two features = possible redundancy.
    """
    print("\n" + "="*60)
    print("TASK 2.3 — FEATURE VALIDATION")
    print("="*60)

    # Select key features + targets for heatmap (not all 25 — too cluttered)
    key_features = [
        "o2_lag1", "o2_lag2", "o2_lag3", "o2_lag6",
        "o2_delta_1", "o2_delta_3",
        "o2_roll_mean_3", "o2_roll_std_3",
        "temp_lag1", "hum_lag1",
        "hour_sin", "hour_cos",
        "target_5min", "target_10min"
    ]
    # Only include columns that actually exist
    key_features = [c for c in key_features if c in df.columns]

    corr = df[key_features].corr()

    fig, ax = plt.subplots(figsize=(12, 10))
    mask = np.zeros_like(corr, dtype=bool)  # show full matrix
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0,
                square=True, ax=ax, cbar_kws={"shrink": 0.7},
                annot_kws={"size": 7})
    ax.set_title("Feature Correlation Matrix\n"
                 "Bottom 2 rows show correlation with targets — higher = more useful",
                 fontsize=11)
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.yticks(fontsize=8)
    plt.tight_layout()
    plt.savefig("plot5_feature_heatmap.png", dpi=130)
    plt.close()
    print("Feature heatmap saved: plot5_feature_heatmap.png")

    # Print top features correlated with each target
    for target in ["target_5min", "target_10min"]:
        if target in corr:
            top = (corr[target]
                   .drop([target], errors="ignore")
                   .abs()
                   .sort_values(ascending=False)
                   .head(8))
            print(f"\nTop features correlated with {target}:")
            for feat, val in top.items():
                print(f"  {feat:<25} {val:.4f}")

    # Target distribution plot
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    fig.suptitle("Target Variable Distributions", fontsize=12)

    for ax, target, color in zip(axes,
                                  ["target_5min", "target_10min"],
                                  ["#2196F3", "#FF5722"]):
        if target in df.columns:
            df[target].hist(bins=50, ax=ax, color=color,
                            edgecolor="white", alpha=0.8)
            ax.axvline(df[target].mean(), color="black",
                       linestyle="--", label=f"mean={df[target].mean():.3f}")
            ax.axvline(19.5, color="red", linestyle="--",
                       alpha=0.6, label="critical=19.5")
            ax.set_title(f"{target}")
            ax.set_xlabel("O2 (%)")
            ax.set_ylabel("Count")
            ax.legend(fontsize=8)

    plt.tight_layout()
    plt.savefig("plot6_target_analysis.png", dpi=130)
    plt.close()
    print("Target analysis plot saved: plot6_target_analysis.png")

    return corr


# ═══════════════════════════════════════════════════════════
# TASK 2.4 — TRAIN / TEST SPLIT (chronological)
# ═══════════════════════════════════════════════════════════
#
# CONCEPT — Why NOT random split for time series:
#   If you randomly shuffle then split, some training samples
#   will come from AFTER test samples chronologically.
#   This means your model could indirectly "see the future"
#   during training — called DATA LEAKAGE.
#   Leakage gives you falsely optimistic metrics (e.g., R²=0.99)
#   that completely collapse when deployed on truly new data.
#
#   CORRECT approach: sort by time, take first 80% as train,
#   last 20% as test. This simulates real deployment — model
#   is always trained on past, evaluated on future.
#
# SPLIT RATIO: 80/20
#   With 2160 records → 1728 train, 432 test
#   432 test records × 5 min = 36 hours of test data
#   That's a reasonable evaluation window.

def chronological_split(df: pd.DataFrame,
                         train_ratio: float = 0.80):
    """
    Split DataFrame chronologically into train and test sets.
    NO shuffling — time order is preserved.
    """
    df = df.sort_values("timestamp").reset_index(drop=True)
    split_idx = int(len(df) * train_ratio)

    train = df.iloc[:split_idx].reset_index(drop=True)
    test  = df.iloc[split_idx:].reset_index(drop=True)

    print("\n" + "="*60)
    print("TASK 2.4 — TRAIN/TEST SPLIT")
    print("="*60)
    print(f"Total records  : {len(df)}")
    print(f"Train records  : {len(train)} "
          f"({train['timestamp'].min().date()} → {train['timestamp'].max().date()})")
    print(f"Test records   : {len(test)}  "
          f"({test['timestamp'].min().date()} → {test['timestamp'].max().date()})")
    print(f"Train %        : {len(train)/len(df)*100:.1f}%")
    print(f"Test %         : {len(test)/len(df)*100:.1f}%")
    print(f"\nTrain O2 stats: mean={train['oxygen'].mean():.4f}, "
          f"std={train['oxygen'].std():.4f}")
    print(f"Test  O2 stats: mean={test['oxygen'].mean():.4f},  "
          f"std={test['oxygen'].std():.4f}")
    print("(mean/std should be similar — if very different, data has strong trend)")

    return train, test


# ═══════════════════════════════════════════════════════════
# TASK 2.5 — SAVE AND SUMMARISE
# ═══════════════════════════════════════════════════════════

def save_summary(df, train, test, feature_cols, n_lags, sig_lags):
    """Write a text summary report for your records."""
    lines = [
        "PHASE 2 SUMMARY REPORT",
        "=" * 60,
        f"Total records after feature engineering : {len(df)}",
        f"Number of feature columns               : {len(feature_cols)}",
        f"Recommended lags from PACF              : {n_lags}",
        f"Significant PACF lags                   : {sig_lags}",
        "",
        "FEATURE COLUMNS:",
        *[f"  {i+1:02d}. {f}" for i, f in enumerate(feature_cols)],
        "",
        "TRAIN SET:",
        f"  Records : {len(train)}",
        f"  Range   : {train['timestamp'].min()} → {train['timestamp'].max()}",
        "",
        "TEST SET:",
        f"  Records : {len(test)}",
        f"  Range   : {test['timestamp'].min()} → {test['timestamp'].max()}",
        "",
        "TARGET STATISTICS:",
        f"  target_5min  — mean: {df['target_5min'].mean():.4f}, "
        f"std: {df['target_5min'].std():.4f}, "
        f"min: {df['target_5min'].min():.4f}, "
        f"max: {df['target_5min'].max():.4f}",
        f"  target_10min — mean: {df['target_10min'].mean():.4f}, "
        f"std: {df['target_10min'].std():.4f}, "
        f"min: {df['target_10min'].min():.4f}, "
        f"max: {df['target_10min'].max():.4f}",
        "",
        "FILES PRODUCED:",
        "  featured_data.csv",
        "  train_data.csv",
        "  test_data.csv",
        "  plot4_acf_pacf.png",
        "  plot5_feature_heatmap.png",
        "  plot6_target_analysis.png",
        "",
        "NEXT: Run phase3_model_training.py"
    ]
    with open("phase2_summary.txt", "w") as f:
        f.write("\n".join(lines))
    print("\nSummary saved: phase2_summary.txt")


# ═══════════════════════════════════════════════════════════
# MAIN — runs all tasks in order
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 2 — FEATURE ENGINEERING")
    print("=" * 60)

    # ── Load data ────────────────────────────────────────────
    print("\nLoading data from Firebase...")
    database = init_firebase()
    df_raw = fetch_sensor_data_fixed()

    # Filter to synthetic records only (exclude manual test record)
    if "source" in df_raw.columns:
        df_raw = df_raw[df_raw["source"] == "synthetic"].reset_index(drop=True)

    print(f"Loaded {len(df_raw)} synthetic records")
    print(f"Columns: {list(df_raw.columns)}")

    # ── Task 2.1: ACF/PACF ──────────────────────────────────
    n_lags, sig_lags = run_acf_pacf_analysis(df_raw)

    # ── Task 2.2: Feature engineering ───────────────────────
    print("\n" + "="*60)
    print("TASK 2.2 — FEATURE ENGINEERING")
    print("="*60)
    df_feat = engineer_features(df_raw, n_lags=n_lags)
    feature_cols = get_feature_columns(df_feat)
    print(f"\nTotal features created : {len(feature_cols)}")
    print("Feature columns:")
    for i, f in enumerate(feature_cols):
        print(f"  {i+1:02d}. {f}")

    # ── Task 2.3: Validate features ──────────────────────────
    corr = validate_features(df_feat, feature_cols)

    # ── Task 2.4: Train/test split ───────────────────────────
    train_df, test_df = chronological_split(df_feat, train_ratio=0.80)

    # ── Task 2.5: Save ───────────────────────────────────────
    df_feat.to_csv("featured_data.csv", index=False)
    train_df.to_csv("train_data.csv", index=False)
    test_df.to_csv("test_data.csv", index=False)
    print(f"\nfeatured_data.csv saved — shape: {df_feat.shape}")
    print(f"train_data.csv saved    — shape: {train_df.shape}")
    print(f"test_data.csv saved     — shape: {test_df.shape}")

    save_summary(df_feat, train_df, test_df, feature_cols, n_lags, sig_lags)

    # ── Final check ──────────────────────────────────────────
    print("\n" + "="*60)
    print("PHASE 2 COMPLETE — FINAL CHECK")
    print("="*60)
    checks = {
        "featured_data.csv has >2000 rows": len(df_feat) > 2000,
        "At least 15 feature columns": len(feature_cols) >= 15,
        "No NaN in feature columns": df_feat[feature_cols].isnull().sum().sum() == 0,
        "No NaN in targets": (df_feat[["target_5min","target_10min"]]
                               .isnull().sum().sum() == 0),
        "Train ends before test starts": (train_df["timestamp"].max() <
                                           test_df["timestamp"].min()),
    }
    all_ok = True
    for check, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {check}")
        if not passed:
            all_ok = False

    if all_ok:
        print("\nALL CHECKS PASSED")
        print("READY FOR PHASE 3 — MODEL TRAINING")
        print("\nOpen these plots to understand your data:")
        print("  plot4_acf_pacf.png       — how many lags matter")
        print("  plot5_feature_heatmap.png — which features matter most")
        print("  plot6_target_analysis.png — what you're predicting")
    else:
        print("\nSOME CHECKS FAILED — share output for debugging")
