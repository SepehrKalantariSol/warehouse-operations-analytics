"""
Data Preprocessing Pipeline

Stages:
  1. Load & validate raw CSV
  2. Clean (types, nulls, range checks)
  3. Engineer features (time-based, operational, derived ratios)
  4. Encode for ML (ordinal + binary encoding, no leakage)
  5. Persist: cleaned table + ml_features table → SQLite
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
RAW_CSV = ROOT / "data" / "warehouse_orders.csv"
DB_PATH = ROOT / "data" / "warehouse.db"

# ── 1. Load & validate ─────────────────────────────────────────────────────────

def load_raw(path: Path = RAW_CSV) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["order_date"])
    _validate_schema(df)
    return df


def _validate_schema(df: pd.DataFrame) -> None:
    required = {
        "order_id", "order_date", "shift", "zone", "order_priority",
        "items_count", "picker_experience", "distance_travelled",
        "congestion_level", "equipment_available",
        "picking_time", "packing_time", "total_time", "target_time", "delayed",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in raw data: {missing}")


# ── 2. Clean ───────────────────────────────────────────────────────────────────

def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Remove duplicates
    before = len(df)
    df.drop_duplicates(subset="order_id", keep="first", inplace=True)
    if len(df) < before:
        print(f"  Dropped {before - len(df)} duplicate order IDs")

    # Drop rows missing the target variable
    df.dropna(subset=["delayed"], inplace=True)

    # Type enforcement
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["equipment_available"] = df["equipment_available"].astype(bool)
    df["delayed"] = df["delayed"].astype(int)

    # Range guards — clip rather than drop to preserve volume
    df["items_count"] = df["items_count"].clip(1, 200)
    df["picker_experience"] = df["picker_experience"].clip(1, 10)
    df["distance_travelled"] = df["distance_travelled"].clip(10, 1000)
    df["picking_time"] = df["picking_time"].clip(1, 300)
    df["packing_time"] = df["packing_time"].clip(1, 120)

    # Recalculate total_time to stay consistent after any clipping
    df["total_time"] = (df["picking_time"] + df["packing_time"]).round(2)

    # Drop rows with unparseable dates
    null_dates = df["order_date"].isna().sum()
    if null_dates:
        print(f"  Dropped {null_dates} rows with invalid order_date")
        df.dropna(subset=["order_date"], inplace=True)

    df.reset_index(drop=True, inplace=True)
    return df


# ── 3. Feature engineering ─────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Time-based
    df["order_month"] = df["order_date"].dt.month
    df["order_quarter"] = df["order_date"].dt.quarter
    df["order_day_of_week"] = df["order_date"].dt.dayofweek   # Mon=0, Sun=6
    df["is_weekend"] = (df["order_day_of_week"] >= 5).astype(int)

    # Operational efficiency
    # time_ratio > 1 means order exceeded its SLA target
    df["time_ratio"] = (df["total_time"] / df["target_time"]).round(4)
    df["time_over_target"] = (df["total_time"] - df["target_time"]).round(2)

    # Complexity proxy: more items + longer distance = harder pick
    df["workload_index"] = (
        df["items_count"] * (df["distance_travelled"] / 100)
    ).round(2)

    # Experience bands
    df["is_experienced"] = (df["picker_experience"] >= 7).astype(int)

    # Congestion flag
    df["is_high_congestion"] = (df["congestion_level"] == "High").astype(int)

    # Equipment penalty flag
    df["equipment_penalty"] = (~df["equipment_available"]).astype(int)

    # Picking efficiency: time per item
    df["pick_time_per_item"] = (df["picking_time"] / df["items_count"]).round(3)

    return df


# ── 4. ML encoding ─────────────────────────────────────────────────────────────

# Ordinal maps chosen to reflect natural severity ordering
_SHIFT_MAP = {"Morning": 0, "Evening": 1, "Night": 2}
_PRIORITY_MAP = {"Low": 0, "Medium": 1, "High": 2, "Urgent": 3}
_CONGESTION_MAP = {"Low": 0, "Medium": 1, "High": 2}
_ZONE_MAP = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}

ML_FEATURES = [
    "items_count",
    "picker_experience",
    "distance_travelled",
    "picking_time",
    "packing_time",
    "total_time",
    "target_time",
    "time_ratio",
    "time_over_target",
    "workload_index",
    "pick_time_per_item",
    "is_experienced",
    "is_high_congestion",
    "equipment_penalty",
    "is_weekend",
    "order_month",
    "order_quarter",
    "order_day_of_week",
    "shift_encoded",
    "zone_encoded",
    "priority_encoded",
    "congestion_encoded",
    "delayed",          # target — kept last for easy splitting
]


def encode_for_ml(df: pd.DataFrame) -> pd.DataFrame:
    enc = df[["order_id"]].copy()

    enc["shift_encoded"] = df["shift"].map(_SHIFT_MAP)
    enc["zone_encoded"] = df["zone"].map(_ZONE_MAP)
    enc["priority_encoded"] = df["order_priority"].map(_PRIORITY_MAP)
    enc["congestion_encoded"] = df["congestion_level"].map(_CONGESTION_MAP)

    for col in ML_FEATURES:
        if col not in enc.columns:
            enc[col] = df[col]

    unmapped = enc[ML_FEATURES].isna().sum()
    if unmapped.any():
        bad = unmapped[unmapped > 0].to_dict()
        raise ValueError(f"NaNs after encoding (check category maps): {bad}")

    return enc[["order_id"] + ML_FEATURES]


# ── 5. Persist to SQLite ───────────────────────────────────────────────────────

def save_to_sqlite(
    df_clean: pd.DataFrame,
    df_ml: pd.DataFrame,
    db_path: Path = DB_PATH,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)

    # Human-readable orders table
    orders_cols = [
        "order_id", "order_date", "shift", "zone", "order_priority",
        "items_count", "picker_experience", "distance_travelled",
        "congestion_level", "equipment_available",
        "picking_time", "packing_time", "total_time", "target_time",
        "time_ratio", "time_over_target", "workload_index",
        "pick_time_per_item", "is_experienced", "is_high_congestion",
        "equipment_penalty", "order_month", "order_quarter",
        "order_day_of_week", "is_weekend", "delayed",
    ]
    df_clean[orders_cols].to_sql("orders", conn, if_exists="replace", index=False)

    # ML-ready features table
    df_ml.to_sql("ml_features", conn, if_exists="replace", index=False)

    # Indexes for common query patterns
    cur = conn.cursor()
    cur.executescript("""
        CREATE INDEX IF NOT EXISTS idx_orders_zone     ON orders(zone);
        CREATE INDEX IF NOT EXISTS idx_orders_shift    ON orders(shift);
        CREATE INDEX IF NOT EXISTS idx_orders_date     ON orders(order_date);
        CREATE INDEX IF NOT EXISTS idx_orders_delayed  ON orders(delayed);
        CREATE INDEX IF NOT EXISTS idx_ml_delayed      ON ml_features(delayed);
    """)
    conn.commit()
    conn.close()
    print(f"  Saved to SQLite → {db_path}")


# ── Summary report ─────────────────────────────────────────────────────────────

def print_summary(df: pd.DataFrame) -> None:
    print(f"\n{'─'*50}")
    print(f"  Rows          : {len(df):,}")
    print(f"  Columns       : {len(df.columns)}")
    print(f"  Date range    : {df['order_date'].min().date()} → {df['order_date'].max().date()}")
    print(f"  Delay rate    : {df['delayed'].mean():.1%}")
    print(f"  Avg time_ratio: {df['time_ratio'].mean():.3f}  (>1 = over SLA)")
    print(f"\n  Delay rate by zone:")
    print(
        df.groupby("zone")["delayed"]
        .mean()
        .mul(100)
        .round(1)
        .rename("delay_%")
        .sort_values(ascending=False)
        .to_string()
    )
    print(f"\n  Delay rate by shift:")
    print(
        df.groupby("shift")["delayed"]
        .mean()
        .mul(100)
        .round(1)
        .rename("delay_%")
        .sort_values(ascending=False)
        .to_string()
    )
    print(f"{'─'*50}\n")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    print("Loading raw data...")
    df_raw = load_raw()
    print(f"  Raw rows: {len(df_raw):,}")

    print("Cleaning...")
    df_clean = clean(df_raw)

    print("Engineering features...")
    df_clean = engineer_features(df_clean)

    print("Encoding for ML...")
    df_ml = encode_for_ml(df_clean)

    print("Saving to SQLite...")
    save_to_sqlite(df_clean, df_ml)

    print_summary(df_clean)

    # Also persist enriched CSV for notebooks / quick inspection
    out_csv = ROOT / "data" / "warehouse_orders_clean.csv"
    df_clean.to_csv(out_csv, index=False)
    print(f"  Enriched CSV → {out_csv}")


if __name__ == "__main__":
    main()
