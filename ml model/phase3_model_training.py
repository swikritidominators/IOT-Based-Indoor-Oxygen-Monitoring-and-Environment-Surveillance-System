# ============================================================
# PHASE 3 — Model Training, Comparison, and Evaluation
# ============================================================
# HOW TO RUN:
#   python phase3_model_training.py
#
# PREREQUISITES:
#   train_data.csv and test_data.csv must exist (from Phase 2)
#
# WHAT IT PRODUCES:
#   model_ridge_5min.pkl          saved Ridge model (5-min target)
#   model_rf_5min.pkl             saved Random Forest (5-min target)
#   model_xgb_5min.pkl            saved XGBoost (5-min target)
#   model_xgb_10min.pkl           saved XGBoost (10-min target)
#   model_comparison.csv          MAE/RMSE/R2 table for all models
#   plot7_model_comparison.png    bar chart of model metrics
#   plot8_actual_vs_pred.png      actual vs predicted O2 over time
#   plot9_feature_importance.png  top 20 features by XGBoost importance
#   plot10_residuals.png          error distribution analysis
#   phase3_summary.txt            full results report
#
# ============================================================

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
import joblib
import warnings
warnings.filterwarnings("ignore")

from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
import xgboost as xgb


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def get_feature_columns(df):
    """Same logic as Phase 2 — gets X feature columns."""
    exclude = {"timestamp","source","is_anomaly",
               "target_5min","target_10min",
               "oxygen","temperature","humidity",
               "occupancy_count","ac_status"}
    return [c for c in df.columns if c not in exclude]


def compute_metrics(y_true, y_pred, model_name, target_name):
    """
    Compute MAE, RMSE, R², and MAPE for a set of predictions.

    CONCEPT — What each metric means:
      MAE  (Mean Absolute Error):
        Average absolute difference between predicted and actual O2.
        In same units as O2 (%). MAE=0.05 means predictions are
        off by 0.05% O2 on average. Most interpretable metric.

      RMSE (Root Mean Squared Error):
        Like MAE but penalises large errors more (squares them first).
        If RMSE >> MAE, your model has occasional large errors.
        Also in % O2 units.

      R²   (R-squared / coefficient of determination):
        How much variance in O2 your model explains.
        R²=1.0 = perfect. R²=0.0 = no better than predicting the mean.
        R²<0 = worse than predicting the mean (bad model).

      MAPE (Mean Absolute Percentage Error):
        Error as a % of the actual value.
        Useful for comparing across different scales.
        MAPE=0.3% means predictions are 0.3% off relative to true O2.

      NAIVE IMPROVEMENT:
        How much better your model is vs. naive baseline.
        If naive MAE=0.08 and your MAE=0.04, improvement=50%.
        This is what you report in your paper as model contribution.
    """
    mae  = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2   = r2_score(y_true, y_pred)
    mape = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100

    return {
        "model":  model_name,
        "target": target_name,
        "MAE":    round(mae,  5),
        "RMSE":   round(rmse, 5),
        "R2":     round(r2,   5),
        "MAPE_%": round(mape, 5),
    }


# ═══════════════════════════════════════════════════════════
# TASK 3.1 — LOAD DATA
# ═══════════════════════════════════════════════════════════

def load_data():
    print("="*60)
    print("TASK 3.1 — LOADING TRAIN / TEST DATA")
    print("="*60)

    train = pd.read_csv("train_data.csv")
    test  = pd.read_csv("test_data.csv")

    train["timestamp"] = pd.to_datetime(train["timestamp"])
    test["timestamp"]  = pd.to_datetime(test["timestamp"])

    feature_cols = get_feature_columns(train)

    print(f"Train shape    : {train.shape}")
    print(f"Test shape     : {test.shape}")
    print(f"Feature count  : {len(feature_cols)}")
    print(f"Targets        : target_5min, target_10min")

    X_train = train[feature_cols]
    X_test  = test[feature_cols]
    y_train_5  = train["target_5min"]
    y_test_5   = test["target_5min"]
    y_train_10 = train["target_10min"]
    y_test_10  = test["target_10min"]

    return (X_train, X_test,
            y_train_5, y_test_5,
            y_train_10, y_test_10,
            feature_cols, train, test)


# ═══════════════════════════════════════════════════════════
# TASK 3.2 — TRAIN ALL MODELS
# ═══════════════════════════════════════════════════════════
#
# CONCEPT — Why these 4 models:
#
# NAIVE BASELINE:
#   Predicts target = current O2 (no change assumed).
#   The simplest possible "model". If your ML model can't beat
#   this, something is wrong. Always report this in papers.
#
# RIDGE REGRESSION:
#   Linear model with L2 regularisation (penalises large coefficients).
#   Assumes O2 is a linear combination of all features.
#   Fast to train, fully interpretable (each feature has one weight).
#   Needs StandardScaler because features are on different scales
#   (e.g., hour_sin is -1 to 1, o2_lag1 is ~20).
#   If Ridge performs well, your relationship is roughly linear.
#
# RANDOM FOREST:
#   Builds 200 decision trees on random subsets of data+features,
#   then averages predictions. Captures non-linear patterns.
#   More robust to outliers than linear models.
#   Naturally handles feature interactions (e.g., high occupancy
#   AND low AC status → faster O2 drop — RF can capture this).
#   No scaling needed (tree splits are scale-invariant).
#
# XGBOOST:
#   Gradient boosted trees — builds trees sequentially, each one
#   correcting the errors of the previous one.
#   Generally best on tabular sensor data with mixed features.
#   Faster than Random Forest for the same accuracy.
#   Has built-in regularisation (prevents overfitting on small datasets).
#   learning_rate=0.05: small steps = more careful learning = better
#   generalisation on limited real data later.

def train_all_models(X_train, X_test,
                     y_train_5, y_test_5,
                     y_train_10, y_test_10):
    print("\n" + "="*60)
    print("TASK 3.2 — TRAINING ALL MODELS")
    print("="*60)

    all_results = []
    trained_models = {}

    # ── Scale features (needed for Ridge only) ──────────────
    # CONCEPT: Ridge is sensitive to feature scale.
    # o2_lag1 ranges ~19-21 but hour_sin ranges -1 to 1.
    # Without scaling, Ridge over-weights large-scale features.
    # StandardScaler: subtracts mean, divides by std → all features
    # become zero-mean, unit-variance.
    # IMPORTANT: fit scaler on TRAIN only, transform both train+test.
    # Fitting on test too would leak test distribution into training.
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled  = scaler.transform(X_test)
    joblib.dump(scaler, "feature_scaler.pkl")
    print("Feature scaler saved: feature_scaler.pkl")

    # ── For each target: train all models ───────────────────
    targets = [
        ("5min",  y_train_5,  y_test_5),
        ("10min", y_train_10, y_test_10),
    ]

    for target_name, y_train, y_test in targets:
        print(f"\n--- Target: {target_name} ---")

        # 1. Naive baseline (no training needed)
        # For 5min: predict current O2 (o2_lag1 = last known value)
        naive_preds = X_test["o2_lag1"].values
        result = compute_metrics(y_test.values, naive_preds,
                                  "Naive", target_name)
        all_results.append(result)
        naive_mae = result["MAE"]
        print(f"  Naive    — MAE: {result['MAE']:.5f}  "
              f"RMSE: {result['RMSE']:.5f}  R2: {result['R2']:.5f}")

        # 2. Ridge Regression
        ridge = Ridge(alpha=1.0)
        ridge.fit(X_train_scaled, y_train)
        ridge_preds = ridge.predict(X_test_scaled)
        result = compute_metrics(y_test.values, ridge_preds,
                                  "Ridge", target_name)
        all_results.append(result)
        print(f"  Ridge    — MAE: {result['MAE']:.5f}  "
              f"RMSE: {result['RMSE']:.5f}  R2: {result['R2']:.5f}  "
              f"(vs naive: {(naive_mae - result['MAE'])/naive_mae*100:.1f}% better)")
        if target_name == "5min":
            joblib.dump(ridge, "model_ridge_5min.pkl")
            trained_models["ridge"] = ridge

        # 3. Random Forest
        print(f"  Training Random Forest (200 trees)...", end=" ", flush=True)
        rf = RandomForestRegressor(
            n_estimators=200,
            max_depth=10,
            min_samples_leaf=5,
            n_jobs=-1,          # use all CPU cores
            random_state=42
        )
        rf.fit(X_train, y_train)
        rf_preds = rf.predict(X_test)
        result = compute_metrics(y_test.values, rf_preds,
                                  "RandomForest", target_name)
        all_results.append(result)
        print(f"done")
        print(f"  RF       — MAE: {result['MAE']:.5f}  "
              f"RMSE: {result['RMSE']:.5f}  R2: {result['R2']:.5f}  "
              f"(vs naive: {(naive_mae - result['MAE'])/naive_mae*100:.1f}% better)")
        if target_name == "5min":
            joblib.dump(rf, "model_rf_5min.pkl")
            trained_models["rf"] = rf

        # 4. XGBoost
        print(f"  Training XGBoost...", end=" ", flush=True)
        xgb_model = xgb.XGBRegressor(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,          # use 80% of data per tree (prevents overfit)
            colsample_bytree=0.8,   # use 80% of features per tree
            min_child_weight=5,
            reg_alpha=0.1,          # L1 regularisation
            reg_lambda=1.0,         # L2 regularisation
            random_state=42,
            verbosity=0
        )
        xgb_model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )
        xgb_preds = xgb_model.predict(X_test)
        result = compute_metrics(y_test.values, xgb_preds,
                                  "XGBoost", target_name)
        all_results.append(result)
        print(f"done")
        print(f"  XGBoost  — MAE: {result['MAE']:.5f}  "
              f"RMSE: {result['RMSE']:.5f}  R2: {result['R2']:.5f}  "
              f"(vs naive: {(naive_mae - result['MAE'])/naive_mae*100:.1f}% better)")
        joblib.dump(xgb_model, f"model_xgb_{target_name}.pkl")
        if target_name == "5min":
            trained_models["xgb_5min"] = xgb_model
            trained_models["xgb_preds_5min"] = xgb_preds
            trained_models["naive_preds_5min"] = naive_preds
        else:
            trained_models["xgb_10min"] = xgb_model
            trained_models["xgb_preds_10min"] = xgb_preds

    results_df = pd.DataFrame(all_results)
    results_df.to_csv("model_comparison.csv", index=False)
    print(f"\nmodel_comparison.csv saved.")

    return results_df, trained_models


# ═══════════════════════════════════════════════════════════
# TASK 3.3 — VISUALISE RESULTS
# ═══════════════════════════════════════════════════════════

def plot_model_comparison(results_df):
    """
    Bar chart comparing all models on MAE and RMSE.
    Lower = better for both metrics.
    This plot goes directly in your research paper results section.
    """
    print("\n" + "="*60)
    print("TASK 3.3 — PLOTTING MODEL COMPARISON")
    print("="*60)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Model Comparison — Lower MAE/RMSE = Better Forecast",
                 fontsize=13)

    colors = {"Naive": "#9E9E9E", "Ridge": "#2196F3",
              "RandomForest": "#4CAF50", "XGBoost": "#FF5722"}

    for ax, target in zip(axes, ["5min", "10min"]):
        subset = results_df[results_df["target"] == target].copy()
        subset = subset.set_index("model")

        x = np.arange(len(subset))
        w = 0.35
        bars1 = ax.bar(x - w/2, subset["MAE"],  w, label="MAE",
                       color=[colors[m] for m in subset.index], alpha=0.85)
        bars2 = ax.bar(x + w/2, subset["RMSE"], w, label="RMSE",
                       color=[colors[m] for m in subset.index], alpha=0.5,
                       edgecolor="black", linewidth=0.5)

        ax.set_xticks(x)
        ax.set_xticklabels(subset.index, rotation=15)
        ax.set_ylabel("Error (% O2)")
        ax.set_title(f"{target} Oxygen Forecast")
        ax.legend()

        # Annotate bars with values
        for bar in bars1:
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + 0.0002,
                    f"{bar.get_height():.4f}",
                    ha="center", va="bottom", fontsize=7)

    plt.tight_layout()
    plt.savefig("plot7_model_comparison.png", dpi=130)
    plt.close()
    print("Saved: plot7_model_comparison.png")


def plot_actual_vs_predicted(test_df, xgb_preds_5min,
                              xgb_preds_10min, naive_preds):
    """
    Time series plot: actual O2 vs XGBoost predictions.
    Shows how well the model tracks real O2 variation.
    Zoomed view of first 200 test points for readability.
    """
    ts = pd.to_datetime(test_df["timestamp"])
    actual_5  = test_df["target_5min"].values
    actual_10 = test_df["target_10min"].values

    fig, axes = plt.subplots(2, 1, figsize=(15, 8), sharex=False)
    fig.suptitle("XGBoost Predictions vs Actual O2 Levels\n"
                 "(showing first 200 test records = ~17 hours)",
                 fontsize=12)

    n = min(200, len(ts))
    ts_plot = ts.iloc[:n]

    # 5-min forecast
    axes[0].plot(ts_plot, actual_5[:n], color="#2196F3",
                 linewidth=1.2, label="Actual O2", zorder=3)
    axes[0].plot(ts_plot, xgb_preds_5min[:n], color="#FF5722",
                 linewidth=1.0, linestyle="--", label="XGBoost 5-min forecast", zorder=2)
    axes[0].plot(ts_plot, naive_preds[:n], color="#9E9E9E",
                 linewidth=0.8, linestyle=":", label="Naive baseline", zorder=1)
    axes[0].axhline(19.5, color="red", linestyle="--", alpha=0.4, linewidth=0.8)
    axes[0].axhline(20.5, color="orange", linestyle="--", alpha=0.4, linewidth=0.8)
    axes[0].set_ylabel("O2 (%)")
    axes[0].set_title("5-minute forecast")
    axes[0].legend(fontsize=9)
    axes[0].set_ylim(19.0, 21.8)

    # 10-min forecast
    axes[1].plot(ts_plot, actual_10[:n], color="#2196F3",
                 linewidth=1.2, label="Actual O2 (10-min ahead)", zorder=3)
    axes[1].plot(ts_plot, xgb_preds_10min[:n], color="#9C27B0",
                 linewidth=1.0, linestyle="--", label="XGBoost 10-min forecast", zorder=2)
    axes[1].axhline(19.5, color="red", linestyle="--", alpha=0.4, linewidth=0.8,
                    label="Critical threshold")
    axes[1].axhline(20.5, color="orange", linestyle="--", alpha=0.4, linewidth=0.8,
                    label="Warning threshold")
    axes[1].set_ylabel("O2 (%)")
    axes[1].set_title("10-minute forecast")
    axes[1].legend(fontsize=9)
    axes[1].set_ylim(19.0, 21.8)

    plt.xticks(rotation=20, fontsize=8)
    plt.tight_layout()
    plt.savefig("plot8_actual_vs_pred.png", dpi=130)
    plt.close()
    print("Saved: plot8_actual_vs_pred.png")


def plot_feature_importance(xgb_model_5min, feature_cols, top_n=20):
    """
    Shows which features XGBoost relied on most.

    CONCEPT — Feature importance (gain):
      XGBoost tracks how much each feature reduced prediction error
      across all trees. "Gain" = average error reduction when that
      feature is used in a split.
      High gain = feature carries strong predictive signal.
      Near-zero gain = feature adds noise, could be removed.

    RESEARCH PAPER USE:
      This plot answers "which environmental/temporal factors
      most influence short-term O2 forecasting?" — a key
      research question in your paper.

      If o2_lag1 dominates: O2 is highly autocorrelated
      (recent past is the best predictor of near future).
      If temp/humidity features rank high: environmental conditions
      add predictive value beyond simple autocorrelation.
      If hour_cos/hour_sin rank high: strong diurnal pattern.
    """
    importances = xgb_model_5min.feature_importances_
    feat_imp = pd.DataFrame({
        "feature":    feature_cols,
        "importance": importances
    }).sort_values("importance", ascending=False).head(top_n)

    fig, ax = plt.subplots(figsize=(10, 7))
    colors = plt.cm.RdYlGn(np.linspace(0.3, 0.9, top_n))
    bars = ax.barh(feat_imp["feature"][::-1],
                   feat_imp["importance"][::-1],
                   color=colors[::-1], edgecolor="white")
    ax.set_xlabel("Feature Importance (Gain)")
    ax.set_title(f"XGBoost Feature Importance — Top {top_n} Features\n"
                 "(5-min O2 forecast model)")
    ax.axvline(feat_imp["importance"].mean(), color="red",
               linestyle="--", alpha=0.6, label="Mean importance")
    ax.legend()

    # Annotate values
    for bar, val in zip(bars, feat_imp["importance"][::-1]):
        ax.text(bar.get_width() + 0.0001, bar.get_y() + bar.get_height()/2,
                f"{val:.4f}", va="center", fontsize=7)

    plt.tight_layout()
    plt.savefig("plot9_feature_importance.png", dpi=130)
    plt.close()
    print("Saved: plot9_feature_importance.png")

    print("\nTop 10 most important features:")
    for i, row in feat_imp.head(10).iterrows():
        print(f"  {row['feature']:<25} {row['importance']:.6f}")

    return feat_imp


def plot_residuals(y_test_5, xgb_preds_5min, naive_preds):
    """
    Residual analysis — checks if prediction errors are random
    (good) or systematic (bad — means model is missing a pattern).

    CONCEPT — Residuals:
      residual = actual - predicted
      Good model: residuals look like random noise (normal distribution
      centered at 0, no pattern over time).
      Bad model: residuals show a pattern — means model is missing
      something systematic.

      Plotting residuals is standard practice in regression papers.
      If reviewers ask "how do you know your model isn't biased?",
      this plot is your answer.
    """
    residuals_xgb   = y_test_5.values - xgb_preds_5min
    residuals_naive = y_test_5.values - naive_preds

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    fig.suptitle("Residual Analysis — XGBoost 5-min Forecast", fontsize=12)

    # Residual distribution
    axes[0].hist(residuals_xgb, bins=40, color="#FF5722",
                 edgecolor="white", alpha=0.8, label="XGBoost")
    axes[0].hist(residuals_naive, bins=40, color="#9E9E9E",
                 edgecolor="white", alpha=0.5, label="Naive")
    axes[0].axvline(0, color="black", linestyle="--")
    axes[0].set_xlabel("Residual (actual - predicted) in % O2")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Error Distribution\n(should be centered at 0)")
    axes[0].legend()

    # Residuals over time
    axes[1].plot(residuals_xgb, color="#FF5722", linewidth=0.6,
                 alpha=0.8, label="XGBoost")
    axes[1].axhline(0, color="black", linestyle="--", linewidth=0.8)
    axes[1].axhline(residuals_xgb.std()*2, color="orange",
                    linestyle=":", alpha=0.6, label="+2 std")
    axes[1].axhline(-residuals_xgb.std()*2, color="orange",
                    linestyle=":", alpha=0.6, label="-2 std")
    axes[1].set_xlabel("Test record index")
    axes[1].set_ylabel("Residual (% O2)")
    axes[1].set_title("Residuals Over Time\n(should look random, no trend)")
    axes[1].legend(fontsize=8)

    # Predicted vs actual scatter
    axes[2].scatter(y_test_5.values, xgb_preds_5min,
                    alpha=0.3, s=8, color="#FF5722", label="XGBoost")
    lims = [min(y_test_5.min(), xgb_preds_5min.min()) - 0.1,
            max(y_test_5.max(), xgb_preds_5min.max()) + 0.1]
    axes[2].plot(lims, lims, "k--", linewidth=1, label="Perfect prediction")
    axes[2].set_xlabel("Actual O2 (%)")
    axes[2].set_ylabel("Predicted O2 (%)")
    axes[2].set_title("Predicted vs Actual\n(closer to diagonal = better)")
    axes[2].legend(fontsize=8)

    plt.tight_layout()
    plt.savefig("plot10_residuals.png", dpi=130)
    plt.close()
    print("Saved: plot10_residuals.png")

    print(f"\nResidual stats (XGBoost 5-min):")
    print(f"  Mean   : {residuals_xgb.mean():.6f}  (should be near 0)")
    print(f"  Std    : {residuals_xgb.std():.6f}")
    print(f"  Max err: {np.abs(residuals_xgb).max():.4f} % O2")
    print(f"  % errors > 0.1% O2: "
          f"{(np.abs(residuals_xgb) > 0.1).mean()*100:.1f}%")


# ═══════════════════════════════════════════════════════════
# TASK 3.4 — PRINT FINAL REPORT
# ═══════════════════════════════════════════════════════════

def print_final_report(results_df, feat_imp):
    print("\n" + "="*60)
    print("TASK 3.4 — FINAL RESULTS REPORT")
    print("="*60)

    print("\nCOMPLETE MODEL COMPARISON TABLE:")
    print(results_df.to_string(index=False))

    print("\n" + "-"*60)
    print("BEST MODEL SUMMARY:")

    for target in ["5min", "10min"]:
        subset = results_df[results_df["target"] == target]
        best = subset.loc[subset["MAE"].idxmin()]
        naive = subset[subset["model"] == "Naive"].iloc[0]
        improvement = (naive["MAE"] - best["MAE"]) / naive["MAE"] * 100
        print(f"\n  {target} forecast:")
        print(f"    Best model : {best['model']}")
        print(f"    MAE        : {best['MAE']:.5f} % O2")
        print(f"    RMSE       : {best['RMSE']:.5f} % O2")
        print(f"    R2         : {best['R2']:.5f}")
        print(f"    vs Naive   : {improvement:.1f}% MAE reduction")

    # Save report
    report_lines = [
        "PHASE 3 RESULTS REPORT",
        "="*60,
        "",
        "MODEL COMPARISON:",
        results_df.to_string(index=False),
        "",
        "TOP 10 FEATURES (XGBoost 5-min model):",
        feat_imp.head(10)[["feature","importance"]].to_string(index=False),
        "",
        "SAVED FILES:",
        "  model_ridge_5min.pkl",
        "  model_rf_5min.pkl",
        "  model_xgb_5min.pkl",
        "  model_xgb_10min.pkl",
        "  feature_scaler.pkl",
        "  model_comparison.csv",
        "  plot7_model_comparison.png",
        "  plot8_actual_vs_pred.png",
        "  plot9_feature_importance.png",
        "  plot10_residuals.png",
        "",
        "NEXT: Run phase4_anomaly_detection.py"
    ]
    with open("phase3_summary.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print("\nphase3_summary.txt saved.")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("="*60)
    print("PHASE 3 — MODEL TRAINING AND EVALUATION")
    print("="*60)
    print("This will take 1-3 minutes (Random Forest + XGBoost training)")
    print()

    # Load
    (X_train, X_test,
     y_train_5, y_test_5,
     y_train_10, y_test_10,
     feature_cols, train_df, test_df) = load_data()

    # Train + evaluate
    results_df, trained_models = train_all_models(
        X_train, X_test,
        y_train_5, y_test_5,
        y_train_10, y_test_10
    )

    # Plots
    plot_model_comparison(results_df)

    plot_actual_vs_predicted(
        test_df,
        trained_models["xgb_preds_5min"],
        trained_models["xgb_preds_10min"],
        trained_models["naive_preds_5min"]
    )

    feat_imp = plot_feature_importance(
        trained_models["xgb_5min"],
        feature_cols,
        top_n=20
    )

    plot_residuals(
        y_test_5,
        trained_models["xgb_preds_5min"],
        trained_models["naive_preds_5min"]
    )

    print_final_report(results_df, feat_imp)

    # Final check
    import os
    print("\n" + "="*60)
    print("PHASE 3 FINAL CHECK")
    print("="*60)
    files_needed = [
        "model_xgb_5min.pkl", "model_xgb_10min.pkl",
        "model_rf_5min.pkl",  "model_ridge_5min.pkl",
        "feature_scaler.pkl", "model_comparison.csv",
        "plot7_model_comparison.png", "plot8_actual_vs_pred.png",
        "plot9_feature_importance.png", "plot10_residuals.png"
    ]
    all_ok = True
    for f in files_needed:
        exists = os.path.exists(f)
        print(f"  [{'PASS' if exists else 'FAIL'}] {f}")
        if not exists:
            all_ok = False

    if all_ok:
        print("\nALL FILES SAVED")
        print("PHASE 3 COMPLETE - Ready for Phase 4 Anomaly Detection")
    else:
        print("\nSome files missing - check errors above")
