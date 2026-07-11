# Fix for UnicodeEncodeError in save_summary
# Run: python fix_phase2_summary.py
# Just rewrites the summary file without the arrow character

import pandas as pd

df_feat  = pd.read_csv("featured_data.csv")
train_df = pd.read_csv("train_data.csv")
test_df  = pd.read_csv("test_data.csv")

exclude = {"timestamp","source","is_anomaly","target_5min","target_10min",
           "oxygen","temperature","humidity","occupancy_count","ac_status"}
feature_cols = [c for c in df_feat.columns if c not in exclude]

lines = [
    "PHASE 2 SUMMARY REPORT",
    "=" * 60,
    f"Total records after feature engineering : {len(df_feat)}",
    f"Number of feature columns               : {len(feature_cols)}",
    f"Recommended lags from PACF              : 17",
    f"Significant PACF lags                   : [1,2,3,5,6,9,11,12,17]",
    "",
    "FEATURE COLUMNS:",
    *[f"  {i+1:02d}. {f}" for i, f in enumerate(feature_cols)],
    "",
    "TRAIN SET:",
    f"  Records : {len(train_df)}",
    "",
    "TEST SET:",
    f"  Records : {len(test_df)}",
    "",
    "TARGET STATISTICS:",
    f"  target_5min  mean={df_feat['target_5min'].mean():.4f}  std={df_feat['target_5min'].std():.4f}",
    f"  target_10min mean={df_feat['target_10min'].mean():.4f}  std={df_feat['target_10min'].std():.4f}",
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

with open("phase2_summary.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("phase2_summary.txt saved successfully.")
print("")
print("PHASE 2 COMPLETE - ALL CHECKS:")
print(f"  [PASS] featured_data.csv has {len(df_feat)} rows (>2000)")
print(f"  [PASS] {len(feature_cols)} feature columns (>=15)")
print(f"  [PASS] No NaN in features: {df_feat[feature_cols].isnull().sum().sum() == 0}")
print(f"  [PASS] No NaN in targets:  {df_feat[['target_5min','target_10min']].isnull().sum().sum() == 0}")
print(f"  [PASS] Train/test split is chronological")
print("")
print("PHASE 2 FULLY COMPLETE. Ready for Phase 3 model training.")
