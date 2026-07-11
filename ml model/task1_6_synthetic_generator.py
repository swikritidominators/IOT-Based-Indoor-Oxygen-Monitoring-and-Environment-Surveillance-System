# ============================================================
# TASK 1.6 — Synthetic Dataset Generator
# ============================================================
# HOW TO RUN:
#   python task1_6_synthetic_generator.py
#
# WHAT IT DOES:
#   Generates a realistic synthetic dataset of sensor readings
#   using physics-based O2 decay model + daily patterns.
#   Saves to synthetic_data.csv for inspection.
#   Plots the generated data so you can visually validate it.
#
# CONCEPTS USED:
#
#   1. O2 Decay Model (from ASHRAE / respiratory physiology):
#      O2(t) = O2(t-1) - k * occupancy * (Δt/60) / room_volume
#      where k=0.015 L/min per person per cubic meter (approximate)
#      Human O2 consumption at rest ≈ 0.3 L/min
#      Room 45m³ of air → 0.3/45000 * 100 ≈ 0.003% drop/min/person
#      With k tuned to produce realistic ~0.5% drop over 4 hours
#      with 3-4 people in the room.
#
#   2. Dalton's Law effect:
#      Higher humidity = more water vapor pressure = slightly lower
#      O2 partial pressure. Modeled as small negative correlation
#      between humidity and oxygen reading.
#
#   3. Temperature sensor cross-effect:
#      O2 electrochemical sensors are temperature-sensitive.
#      Modeled as small compensation term in the decay equation.
#
#   4. Ventilation events:
#      Door opens, AC switching on/off cause partial O2 recovery.
#      Simulated as random events (5% probability per timestep).
#
#   5. Anomaly injection:
#      5% of records get sudden O2 drops to simulate sensor
#      malfunction, window sealing, or heavy occupancy spikes.
#
# EXPECTED OUTPUT:
#   Generated 2160 records (5-min intervals over 7.5 days)
#   Saved to synthetic_data.csv
#   3 plots saved: o2_timeseries.png, correlations.png, distributions.png
# ============================================================

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import os

# ── reproducibility ─────────────────────────────────────────
np.random.seed(42)


def generate_synthetic_data(
    n_hours: int = 180,          # how many hours to simulate (180h ≈ 7.5 days)
    freq_min: int = 5,            # reading every 5 minutes (matches ESP32 plan)
    room_volume_m3: float = 45.0, # room volume in cubic meters
    k: float = 0.015,             # O2 depletion constant (tuned to literature)
    include_occupancy: bool = True,
    include_ac: bool = True,
    start_date: str = "2026-06-01 08:00:00",
) -> pd.DataFrame:
    """
    Generate a physics-informed synthetic sensor dataset.

    Returns:
        DataFrame with columns:
        timestamp, oxygen, temperature, humidity,
        occupancy_count (if include_occupancy),
        ac_status (if include_ac),
        is_anomaly, source
    """
    n = int(n_hours * 60 / freq_min)
    timestamps = pd.date_range(start=start_date, periods=n, freq=f"{freq_min}min")
    hour = timestamps.hour.values
    day = timestamps.dayofweek.values  # 0=Monday, 6=Sunday

    # ── Temperature: daily sine cycle + weekday/weekend + noise ──
    # Peaks around 2pm (~14:00), troughs around 5am (~5:00)
    temp_base = 23.0
    temp_daily_amp = 2.5
    temp = (temp_base
            + temp_daily_amp * np.sin(2 * np.pi * (hour - 5) / 24)
            + 0.5 * (day >= 5)  # slightly warmer on weekends (less AC use)
            + np.random.normal(0, 0.25, n))

    # ── Humidity: inversely correlated with temp, own daily pattern ──
    # Real rooms: humidity rises at night when temp drops
    hum = (55.0
           - 0.6 * (temp - temp_base)     # Dalton's law approximation
           + 3.0 * np.sin(2 * np.pi * (hour - 14) / 24)  # peak at 2am
           + np.random.normal(0, 1.2, n))
    hum = np.clip(hum, 30, 85)

    # ── Occupancy: working hours pattern (if requested) ──
    if include_occupancy:
        is_working_hour = ((hour >= 9) & (hour <= 18) & (day < 5))  # Mon-Fri 9-6
        is_lunch = ((hour >= 12) & (hour <= 13))
        occ_mean = np.where(is_working_hour, 3.5, 0.3)
        occ_mean = np.where(is_lunch, 1.5, occ_mean)  # fewer people during lunch
        occupancy = np.random.poisson(occ_mean).astype(float)
        occupancy = np.clip(occupancy, 0, 8)
    else:
        # If not tracking occupancy, assume average 2 people during day
        occupancy = np.where((hour >= 9) & (hour <= 18), 2.0, 0.5)

    # ── AC status: on during working hours (if requested) ──
    if include_ac:
        ac_status = ((hour >= 9) & (hour <= 19) & (day < 5)).astype(float)
        # Add some random AC failures/weekends
        random_off = np.random.rand(n) < 0.05
        ac_status = np.where(random_off, 0, ac_status)
    else:
        ac_status = np.zeros(n)

    # ── O2 Decay Model ──────────────────────────────────────────
    # Core equation:
    #   O2(t) = O2(t-1) - depletion + recovery + humidity_effect + noise
    #
    # depletion: proportional to occupancy, inversely to room volume
    # recovery: AC with fresh air partially replenishes O2
    # humidity_effect: electrochemical sensor reads lower when humid
    #                  (Dalton's Law — water vapor displaces O2 partial pressure)

    o2 = np.zeros(n)
    o2[0] = 20.9  # fresh air starting point

    for i in range(1, n):
        # How much O2 each person consumes per timestep
        depletion = k * occupancy[i] * (freq_min / 60) / room_volume_m3

        # AC in fresh-air mode recovers O2; recirculation mode doesn't
        # ac_status=1 → assume 20% fresh air mix → partial recovery
        recovery = 0.003 * ac_status[i]

        # Humidity effect on sensor reading (small, ~0.002% per 10% RH)
        hum_effect = -0.0002 * (hum[i] - 55)

        # Temperature compensation (sensor reads ~0.1% higher at 10°C above cal)
        temp_effect = 0.001 * (temp[i] - 23)

        # Random ventilation events (door opens, window ajar)
        vent_event = np.random.rand() < 0.04
        vent_recovery = np.random.uniform(0.05, 0.25) if vent_event else 0.0

        o2[i] = (o2[i - 1]
                 - depletion
                 + recovery
                 + hum_effect
                 + temp_effect
                 + vent_recovery
                 + np.random.normal(0, 0.012))  # sensor noise

        # Clamp to physically possible range
        o2[i] = np.clip(o2[i], 17.0, 21.0)

    # ── Anomaly Injection ────────────────────────────────────────
    # 5% of readings get anomalies; labeled so anomaly detection can be validated
    is_anomaly = np.zeros(n, dtype=int)
    n_anomalies = int(n * 0.05)
    anomaly_indices = np.random.choice(range(15, n - 5), n_anomalies, replace=False)

    for idx in anomaly_indices:
        anomaly_type = np.random.choice(["sudden_drop", "sensor_spike", "sustained_low"])
        if anomaly_type == "sudden_drop":
            o2[idx] = o2[idx - 1] - np.random.uniform(0.5, 1.2)
        elif anomaly_type == "sensor_spike":
            o2[idx] = o2[idx - 1] + np.random.uniform(0.4, 0.8)
        elif anomaly_type == "sustained_low":
            for j in range(idx, min(idx + 4, n)):
                o2[j] = max(17.5, o2[j] - 0.3)
                is_anomaly[j] = 1
        o2[idx] = np.clip(o2[idx], 17.0, 21.5)
        is_anomaly[idx] = 1

    # ── Assemble DataFrame ───────────────────────────────────────
    df = pd.DataFrame({
        "timestamp": timestamps,
        "oxygen": np.round(o2, 4),
        "temperature": np.round(temp, 3),
        "humidity": np.round(hum, 3),
        "is_anomaly": is_anomaly,
        "source": "synthetic"
    })

    if include_occupancy:
        df["occupancy_count"] = occupancy.astype(int)
    if include_ac:
        df["ac_status"] = ac_status.astype(int)

    return df


def validate_and_plot(df: pd.DataFrame, save_dir: str = "."):
    """
    Print statistics and generate 3 plots to validate synthetic data quality.
    """
    os.makedirs(save_dir, exist_ok=True)

    print("=" * 60)
    print("SYNTHETIC DATA VALIDATION REPORT")
    print("=" * 60)
    print(f"Total records   : {len(df)}")
    print(f"Time range      : {df['timestamp'].min()} → {df['timestamp'].max()}")
    print(f"Columns         : {list(df.columns)}")
    print(f"\nDescriptive Statistics:")
    print(df[["oxygen", "temperature", "humidity"]].describe().round(3))
    print(f"\nAnomalies injected: {df['is_anomaly'].sum()} "
          f"({df['is_anomaly'].mean()*100:.1f}%)")

    if "occupancy_count" in df.columns:
        print(f"\nOccupancy stats:")
        print(df["occupancy_count"].value_counts().sort_index().to_string())

    # ── Plot 1: Time series of all signals ───────────────────────
    fig, axes = plt.subplots(3, 1, figsize=(15, 9), sharex=True)
    fig.suptitle("Synthetic Sensor Data — Time Series", fontsize=14)

    axes[0].plot(df["timestamp"], df["oxygen"], color="#2196F3", linewidth=0.8, label="O2 %")
    anomaly_mask = df["is_anomaly"] == 1
    axes[0].scatter(df.loc[anomaly_mask, "timestamp"], df.loc[anomaly_mask, "oxygen"],
                    color="red", s=20, zorder=5, label="Anomaly")
    axes[0].axhline(20.5, color="orange", linestyle="--", alpha=0.6, label="Warning threshold")
    axes[0].axhline(19.5, color="red", linestyle="--", alpha=0.6, label="Critical threshold")
    axes[0].set_ylabel("O2 (%)")
    axes[0].legend(loc="lower right", fontsize=8)
    axes[0].set_ylim(17, 21.5)

    axes[1].plot(df["timestamp"], df["temperature"], color="#FF5722", linewidth=0.8)
    axes[1].set_ylabel("Temperature (°C)")

    axes[2].plot(df["timestamp"], df["humidity"], color="#4CAF50", linewidth=0.8)
    axes[2].set_ylabel("Humidity (%)")
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
    plt.xticks(rotation=30, fontsize=7)

    plt.tight_layout()
    path1 = os.path.join(save_dir, "plot1_o2_timeseries.png")
    plt.savefig(path1, dpi=120)
    plt.close()
    print(f"\nPlot saved: {path1}")

    # ── Plot 2: Correlation heatmap ──────────────────────────────
    corr_cols = ["oxygen", "temperature", "humidity"]
    if "occupancy_count" in df.columns:
        corr_cols.append("occupancy_count")
    if "ac_status" in df.columns:
        corr_cols.append("ac_status")

    fig, ax = plt.subplots(figsize=(7, 5))
    corr = df[corr_cols].corr()
    sns.heatmap(corr, annot=True, fmt=".3f", cmap="coolwarm", center=0,
                square=True, ax=ax, cbar_kws={"shrink": 0.8})
    ax.set_title("Feature Correlation Matrix (Synthetic Data)")
    plt.tight_layout()
    path2 = os.path.join(save_dir, "plot2_correlations.png")
    plt.savefig(path2, dpi=120)
    plt.close()
    print(f"Plot saved: {path2}")

    # ── Plot 3: O2 distribution by hour of day ───────────────────
    df["hour"] = df["timestamp"].dt.hour
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    df.groupby("hour")["oxygen"].mean().plot(kind="bar", ax=axes[0],
                                              color="#2196F3", edgecolor="white")
    axes[0].set_title("Mean O2 by Hour of Day")
    axes[0].set_xlabel("Hour")
    axes[0].set_ylabel("Mean O2 (%)")
    axes[0].axhline(df["oxygen"].mean(), color="red", linestyle="--", alpha=0.5)

    df["oxygen"].hist(bins=50, ax=axes[1], color="#2196F3", edgecolor="white")
    axes[1].set_title("O2 Distribution")
    axes[1].set_xlabel("O2 (%)")
    axes[1].set_ylabel("Count")
    axes[1].axvline(19.5, color="red", linestyle="--", label="Critical")
    axes[1].axvline(20.5, color="orange", linestyle="--", label="Warning")
    axes[1].legend()

    plt.tight_layout()
    path3 = os.path.join(save_dir, "plot3_distributions.png")
    plt.savefig(path3, dpi=120)
    plt.close()
    print(f"Plot saved: {path3}")

    return corr


if __name__ == "__main__":
    print("Generating synthetic dataset...")
    print("  n_hours=180 → ~7.5 days at 5-min intervals = 2160 records")
    print()

    df = generate_synthetic_data(
        n_hours=180,
        freq_min=5,
        room_volume_m3=45.0,
        k=0.015,
        include_occupancy=True,
        include_ac=True
    )

    # Save to CSV
    output_path = "synthetic_data.csv"
    df.to_csv(output_path, index=False)
    print(f"Dataset saved to: {output_path}")
    print(f"Shape: {df.shape}")

    # Validate
    corr = validate_and_plot(df, save_dir=".")

    print("\n" + "=" * 60)
    print("KEY CHECKS (should all pass):")
    print("=" * 60)
    checks = {
        "O2 stays in 17-21.5% range": (df["oxygen"].min() >= 17.0 and df["oxygen"].max() <= 21.5),
        "Temperature in 15-35°C range": (df["temperature"].min() >= 15 and df["temperature"].max() <= 35),
        "Humidity in 30-85% range": (df["humidity"].min() >= 30 and df["humidity"].max() <= 85),
        "Anomalies between 3-8%": (0.03 <= df["is_anomaly"].mean() <= 0.08),
        "O2-Humidity negative correlation": (corr.loc["oxygen","humidity"] < 0),
    }
    for check, result in checks.items():
        print(f"  {'PASS' if result else 'FAIL'} — {check}")

    print("\nNEXT: Run task1_7_push_synthetic.py to load this into Firebase.")
