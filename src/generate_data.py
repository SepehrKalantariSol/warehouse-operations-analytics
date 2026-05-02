"""
Warehouse Operations Data Generator

Simulates 18 months of realistic warehouse order data with embedded patterns:
- Zone B is chronically slow (picking bottleneck)
- Night shift has the highest delay rate
- High congestion roughly doubles delay probability
- Low picker experience correlates with slower picking times
- Equipment unavailability adds significant time overhead
"""

import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(seed=42)

# ── Constants ─────────────────────────────────────────────────────────────────

N_ORDERS = 5_000
START_DATE = "2024-01-01"
END_DATE = "2025-06-30"

ZONES = ["A", "B", "C", "D", "E"]
SHIFTS = ["Morning", "Evening", "Night"]
PRIORITIES = ["Low", "Medium", "High", "Urgent"]

# Relative picking-time multipliers per zone (B is the bottleneck zone)
ZONE_PICKING_FACTOR = {"A": 1.00, "B": 1.35, "C": 1.05, "D": 0.95, "E": 1.10}

# Shift-level base delay probability adjustments
SHIFT_DELAY_BIAS = {"Morning": -0.05, "Evening": 0.00, "Night": +0.12}

# Priority target times (minutes) — tighter SLA for urgent orders
PRIORITY_TARGET = {"Low": 55, "Medium": 45, "High": 38, "Urgent": 28}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clamp(arr: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return np.clip(arr, lo, hi)


def _choice(options: list, size: int, p: list | None = None) -> np.ndarray:
    return RNG.choice(options, size=size, p=p)


# ── Column generators ─────────────────────────────────────────────────────────

def generate_orders(n: int) -> pd.DataFrame:
    dates = pd.date_range(START_DATE, END_DATE, periods=n)
    # Inject realistic weekly seasonality (higher volume Mon–Wed)
    day_weights = np.array([1.3, 1.2, 1.1, 1.0, 0.9, 0.7, 0.6])
    date_weights = np.array([day_weights[d.weekday()] for d in dates])
    date_weights /= date_weights.sum()
    sampled_dates = RNG.choice(dates, size=n, replace=False, p=date_weights)

    shifts = _choice(SHIFTS, n, p=[0.40, 0.35, 0.25])
    zones = _choice(ZONES, n, p=[0.25, 0.20, 0.22, 0.18, 0.15])
    priorities = _choice(PRIORITIES, n, p=[0.20, 0.40, 0.28, 0.12])

    return pd.DataFrame(
        {
            "order_id": [f"ORD-{i:05d}" for i in range(1, n + 1)],
            "order_date": np.sort(sampled_dates),
            "shift": shifts,
            "zone": zones,
            "order_priority": priorities,
        }
    )


def generate_operational_features(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)

    df["items_count"] = RNG.integers(1, 51, size=n)
    df["picker_experience"] = RNG.integers(1, 11, size=n)  # 1–10 years
    df["distance_travelled"] = (
        RNG.normal(loc=150, scale=40, size=n).clip(30, 400).round(1)
    )
    df["congestion_level"] = _choice(
        ["Low", "Medium", "High"], n, p=[0.45, 0.35, 0.20]
    )
    df["equipment_available"] = _choice([True, False], n, p=[0.82, 0.18])

    return df


def generate_times(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)

    zone_factor = df["zone"].map(ZONE_PICKING_FACTOR).to_numpy()
    experience_factor = 1 - (df["picker_experience"] - 1) / 18  # 1→1.0, 10→0.5
    congestion_factor = df["congestion_level"].map(
        {"Low": 1.00, "Medium": 1.18, "High": 1.45}
    ).to_numpy()
    equipment_factor = np.where(df["equipment_available"], 1.00, 1.30)

    base_pick = df["items_count"] * 0.6 + df["distance_travelled"] * 0.05
    noise_pick = RNG.normal(0, 2.5, size=n)
    picking_time = (
        base_pick * zone_factor * experience_factor * congestion_factor
        + noise_pick
    ).clip(3, 120)

    base_pack = df["items_count"] * 0.4 + RNG.normal(5, 1.5, size=n)
    noise_pack = RNG.normal(0, 1.8, size=n)
    packing_time = (base_pack * equipment_factor + noise_pack).clip(2, 60)

    df["picking_time"] = picking_time.round(2)
    df["packing_time"] = packing_time.round(2)
    df["total_time"] = (df["picking_time"] + df["packing_time"]).round(2)
    df["target_time"] = df["order_priority"].map(PRIORITY_TARGET)

    return df


def generate_delay_label(df: pd.DataFrame) -> pd.DataFrame:
    """
    Delay is primarily driven by total_time vs target_time, with a stochastic
    component to reflect real-world unpredictability (unrecorded incidents, etc.)
    """
    time_ratio = df["total_time"] / df["target_time"]
    shift_bias = df["shift"].map(SHIFT_DELAY_BIAS).to_numpy()

    # Sigmoid-based probability centred around time_ratio = 1.0
    log_odds = 6 * (time_ratio - 1.0) + shift_bias * 3
    p_delay = 1 / (1 + np.exp(-log_odds))

    df["delayed"] = RNG.binomial(1, p_delay).astype(int)
    return df


# ── Validation ────────────────────────────────────────────────────────────────

def validate(df: pd.DataFrame) -> None:
    assert df.isnull().sum().sum() == 0, "Unexpected nulls in dataset"
    assert df["order_id"].is_unique, "Duplicate order IDs detected"
    assert 0.10 <= df["delayed"].mean() <= 0.60, "Delay rate outside plausible range"
    assert (df["total_time"] > 0).all(), "Non-positive total_time values"
    print(f"  Validation passed — delay rate: {df['delayed'].mean():.1%}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    print("Generating warehouse operations dataset...")

    df = generate_orders(N_ORDERS)
    df = generate_operational_features(df)
    df = generate_times(df)
    df = generate_delay_label(df)

    validate(df)

    out_path = Path(__file__).parent.parent / "data" / "warehouse_orders.csv"
    df.to_csv(out_path, index=False)

    print(f"  Saved {len(df):,} rows → {out_path}")
    print(f"  Columns : {list(df.columns)}")
    print(f"  Date range: {df['order_date'].min().date()} → {df['order_date'].max().date()}")
    print("\nSample:")
    print(df.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
