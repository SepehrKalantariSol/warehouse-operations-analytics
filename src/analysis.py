"""
Warehouse Analytics Engine

All analysis is driven by SQL queries against warehouse.db so the dashboard
can call these functions directly without reloading CSVs.

Public API:
    get_connection()             → sqlite3 context manager
    summary_kpis()              → dict of headline metrics
    zone_performance()          → DataFrame, ranked by delay rate
    shift_performance()         → DataFrame
    congestion_impact()         → DataFrame + multiplier column
    equipment_impact()          → DataFrame
    experience_vs_delay()       → DataFrame (experience buckets)
    priority_performance()      → DataFrame
    monthly_trend()             → DataFrame (time series)
    weekly_heatmap()            → pivot DataFrame (zone × day_of_week)
    slow_orders()               → top-5% worst orders by time_ratio
    bottleneck_summary()        → composite ranked bottleneck table
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "warehouse.db"


# ── Connection ─────────────────────────────────────────────────────────────────

@contextmanager
def get_connection(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _q(conn: sqlite3.Connection, sql: str) -> pd.DataFrame:
    """Execute SQL and return a DataFrame."""
    return pd.read_sql_query(sql, conn)


# ── KPIs ───────────────────────────────────────────────────────────────────────

def summary_kpis(conn: sqlite3.Connection) -> dict:
    """Headline metrics for the overview page."""
    row = _q(conn, """
        SELECT
            COUNT(*)                                AS total_orders,
            SUM(delayed)                            AS total_delayed,
            COUNT(*) - SUM(delayed)                 AS total_on_time,
            ROUND(AVG(delayed) * 100, 1)            AS delay_rate_pct,
            ROUND(AVG(total_time), 1)               AS avg_total_time_min,
            ROUND(AVG(picking_time), 1)             AS avg_picking_time_min,
            ROUND(AVG(packing_time), 1)             AS avg_packing_time_min,
            ROUND(AVG(time_ratio), 3)               AS avg_time_ratio,
            ROUND(AVG(items_count), 1)              AS avg_items_per_order,
            ROUND(AVG(distance_travelled), 1)       AS avg_distance_m
        FROM orders
    """).iloc[0]
    return dict(row)


# ── Zone analysis ──────────────────────────────────────────────────────────────

def zone_performance(conn: sqlite3.Connection) -> pd.DataFrame:
    """Per-zone KPIs ranked by delay rate descending."""
    return _q(conn, """
        SELECT
            zone,
            COUNT(*)                                AS total_orders,
            SUM(delayed)                            AS delayed_orders,
            ROUND(AVG(delayed) * 100, 1)            AS delay_rate_pct,
            ROUND(AVG(total_time), 1)               AS avg_total_time,
            ROUND(AVG(picking_time), 1)             AS avg_picking_time,
            ROUND(AVG(packing_time), 1)             AS avg_packing_time,
            ROUND(AVG(time_ratio), 3)               AS avg_time_ratio,
            ROUND(AVG(workload_index), 1)           AS avg_workload,
            ROUND(AVG(pick_time_per_item), 3)       AS avg_pick_per_item
        FROM orders
        GROUP BY zone
        ORDER BY delay_rate_pct DESC
    """)


# ── Shift analysis ─────────────────────────────────────────────────────────────

def shift_performance(conn: sqlite3.Connection) -> pd.DataFrame:
    return _q(conn, """
        SELECT
            shift,
            COUNT(*)                                AS total_orders,
            SUM(delayed)                            AS delayed_orders,
            ROUND(AVG(delayed) * 100, 1)            AS delay_rate_pct,
            ROUND(AVG(total_time), 1)               AS avg_total_time,
            ROUND(AVG(picking_time), 1)             AS avg_picking_time,
            ROUND(AVG(packing_time), 1)             AS avg_packing_time,
            ROUND(AVG(items_count), 1)              AS avg_items,
            ROUND(AVG(picker_experience), 1)        AS avg_experience
        FROM orders
        GROUP BY shift
        ORDER BY
            CASE shift
                WHEN 'Morning' THEN 0
                WHEN 'Evening' THEN 1
                WHEN 'Night'   THEN 2
            END
    """)


# ── Congestion impact ──────────────────────────────────────────────────────────

def congestion_impact(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Returns per-congestion-level stats plus a 'pick_time_multiplier' column
    showing pick time relative to the Low congestion baseline.
    """
    df = _q(conn, """
        SELECT
            congestion_level,
            COUNT(*)                                AS total_orders,
            ROUND(AVG(delayed) * 100, 1)            AS delay_rate_pct,
            ROUND(AVG(picking_time), 2)             AS avg_picking_time,
            ROUND(AVG(packing_time), 2)             AS avg_packing_time,
            ROUND(AVG(total_time), 2)               AS avg_total_time,
            ROUND(AVG(time_ratio), 3)               AS avg_time_ratio
        FROM orders
        GROUP BY congestion_level
        ORDER BY
            CASE congestion_level
                WHEN 'Low'    THEN 0
                WHEN 'Medium' THEN 1
                WHEN 'High'   THEN 2
            END
    """)
    baseline = df.loc[df["congestion_level"] == "Low", "avg_picking_time"].values[0]
    df["pick_time_multiplier"] = (df["avg_picking_time"] / baseline).round(2)
    delay_baseline = df.loc[df["congestion_level"] == "Low", "delay_rate_pct"].values[0]
    df["delay_multiplier"] = (df["delay_rate_pct"] / delay_baseline).round(2)
    return df


# ── Equipment impact ───────────────────────────────────────────────────────────

def equipment_impact(conn: sqlite3.Connection) -> pd.DataFrame:
    df = _q(conn, """
        SELECT
            CASE WHEN equipment_available = 1 THEN 'Available'
                 ELSE 'Unavailable' END             AS equipment_status,
            COUNT(*)                                AS total_orders,
            ROUND(AVG(delayed) * 100, 1)            AS delay_rate_pct,
            ROUND(AVG(packing_time), 2)             AS avg_packing_time,
            ROUND(AVG(picking_time), 2)             AS avg_picking_time,
            ROUND(AVG(total_time), 2)               AS avg_total_time
        FROM orders
        GROUP BY equipment_available
        ORDER BY equipment_available DESC
    """)
    baseline = df.loc[df["equipment_status"] == "Available", "avg_packing_time"].values[0]
    df["pack_time_multiplier"] = (df["avg_packing_time"] / baseline).round(2)
    return df


# ── Picker experience vs delay ─────────────────────────────────────────────────

def experience_vs_delay(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Buckets picker experience (1–3 Junior, 4–6 Mid, 7–10 Senior)
    and shows delay rate + picking efficiency per bucket.
    """
    return _q(conn, """
        SELECT
            CASE
                WHEN picker_experience <= 3 THEN '1–3 (Junior)'
                WHEN picker_experience <= 6 THEN '4–6 (Mid)'
                ELSE '7–10 (Senior)'
            END                                     AS experience_band,
            COUNT(*)                                AS total_orders,
            ROUND(AVG(delayed) * 100, 1)            AS delay_rate_pct,
            ROUND(AVG(picking_time), 2)             AS avg_picking_time,
            ROUND(AVG(pick_time_per_item), 3)       AS avg_pick_per_item,
            ROUND(AVG(picker_experience), 1)        AS avg_experience
        FROM orders
        GROUP BY experience_band
        ORDER BY avg_experience
    """)


# ── Priority performance ───────────────────────────────────────────────────────

def priority_performance(conn: sqlite3.Connection) -> pd.DataFrame:
    return _q(conn, """
        SELECT
            order_priority,
            COUNT(*)                                AS total_orders,
            ROUND(AVG(delayed) * 100, 1)            AS delay_rate_pct,
            ROUND(AVG(total_time), 1)               AS avg_total_time,
            AVG(target_time)                        AS target_time_min,
            ROUND(AVG(time_over_target), 1)         AS avg_time_over_target
        FROM orders
        GROUP BY order_priority
        ORDER BY
            CASE order_priority
                WHEN 'Urgent' THEN 0 WHEN 'High' THEN 1
                WHEN 'Medium' THEN 2 WHEN 'Low'  THEN 3
            END
    """)


# ── Time series ────────────────────────────────────────────────────────────────

def monthly_trend(conn: sqlite3.Connection) -> pd.DataFrame:
    """Monthly order volume + delay trend for time-series chart."""
    df = _q(conn, """
        SELECT
            STRFTIME('%Y-%m', order_date)           AS year_month,
            COUNT(*)                                AS total_orders,
            SUM(delayed)                            AS delayed_orders,
            ROUND(AVG(delayed) * 100, 1)            AS delay_rate_pct,
            ROUND(AVG(total_time), 1)               AS avg_total_time
        FROM orders
        GROUP BY year_month
        ORDER BY year_month
    """)
    df["year_month"] = pd.to_datetime(df["year_month"])
    return df


def day_of_week_trend(conn: sqlite3.Connection) -> pd.DataFrame:
    """Average delay rate by day of week (0=Mon … 6=Sun)."""
    df = _q(conn, """
        SELECT
            order_day_of_week,
            COUNT(*)                                AS total_orders,
            ROUND(AVG(delayed) * 100, 1)            AS delay_rate_pct,
            ROUND(AVG(total_time), 1)               AS avg_total_time
        FROM orders
        GROUP BY order_day_of_week
        ORDER BY order_day_of_week
    """)
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    df["day_name"] = df["order_day_of_week"].map(lambda i: day_names[i])
    return df


# ── Heatmap ────────────────────────────────────────────────────────────────────

def zone_shift_heatmap(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Returns a pivot table: zones as rows, shifts as columns,
    values = delay_rate_pct. Ready to pass to Plotly imshow.
    """
    df = _q(conn, """
        SELECT
            zone,
            shift,
            ROUND(AVG(delayed) * 100, 1)            AS delay_rate_pct
        FROM orders
        GROUP BY zone, shift
    """)
    return df.pivot(index="zone", columns="shift", values="delay_rate_pct")


# ── Slow orders ────────────────────────────────────────────────────────────────

def slow_orders(conn: sqlite3.Connection, top_n: int = 100) -> pd.DataFrame:
    """Top N orders by time_ratio — used to surface extreme bottleneck cases."""
    return _q(conn, f"""
        SELECT
            order_id,
            order_date,
            zone,
            shift,
            order_priority,
            items_count,
            congestion_level,
            equipment_available,
            picker_experience,
            picking_time,
            packing_time,
            total_time,
            target_time,
            time_ratio,
            time_over_target
        FROM orders
        WHERE delayed = 1
        ORDER BY time_ratio DESC
        LIMIT {top_n}
    """)


# ── Composite bottleneck summary ───────────────────────────────────────────────

def bottleneck_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Composite zone-level bottleneck score:
        score = 0.4 × normalised_delay_rate
              + 0.4 × normalised_avg_time_ratio
              + 0.2 × normalised_avg_pick_per_item

    Score 0–100; higher = bigger bottleneck.
    """
    df = zone_performance(conn)

    def _norm(series: pd.Series) -> pd.Series:
        lo, hi = series.min(), series.max()
        return ((series - lo) / (hi - lo)) if hi > lo else pd.Series(0.0, index=series.index)

    df["bottleneck_score"] = (
        0.40 * _norm(df["delay_rate_pct"])
        + 0.40 * _norm(df["avg_time_ratio"])
        + 0.20 * _norm(df["avg_pick_per_item"])
    ).mul(100).round(1)

    return df[["zone", "delay_rate_pct", "avg_time_ratio", "avg_pick_per_item", "bottleneck_score"]].sort_values(
        "bottleneck_score", ascending=False
    )


# ── CLI summary ────────────────────────────────────────────────────────────────

def _print_section(title: str, df_or_dict) -> None:
    print(f"\n{'═' * 55}")
    print(f"  {title}")
    print(f"{'═' * 55}")
    if isinstance(df_or_dict, dict):
        for k, v in df_or_dict.items():
            print(f"  {k:<30} {v}")
    else:
        print(df_or_dict.to_string(index=False))


def main() -> None:
    with get_connection() as conn:
        _print_section("HEADLINE KPIs", summary_kpis(conn))
        _print_section("ZONE PERFORMANCE", zone_performance(conn))
        _print_section("SHIFT PERFORMANCE", shift_performance(conn))
        _print_section("CONGESTION IMPACT", congestion_impact(conn))
        _print_section("EQUIPMENT IMPACT", equipment_impact(conn))
        _print_section("EXPERIENCE vs DELAY", experience_vs_delay(conn))
        _print_section("PRIORITY PERFORMANCE", priority_performance(conn))
        _print_section("BOTTLENECK SCORES (composite)", bottleneck_summary(conn))


if __name__ == "__main__":
    main()
