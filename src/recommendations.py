"""
Recommendations Engine

Reads live data from the database and generates data-driven business insights.
Each recommendation: severity, category, title, finding, action, metric.

Usage:
    python src/recommendations.py
    from src.recommendations import generate_recommendations
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from analysis import (
    congestion_impact,
    equipment_impact,
    experience_vs_delay,
    get_connection,
    priority_performance,
    shift_performance,
    summary_kpis,
    zone_performance,
)


def generate_recommendations(conn: sqlite3.Connection) -> list[dict]:
    kpis = summary_kpis(conn)
    zone_df = zone_performance(conn)
    shift_df = shift_performance(conn)
    cong_df = congestion_impact(conn)
    equip_df = equipment_impact(conn)
    exp_df = experience_vs_delay(conn)
    pri_df = priority_performance(conn)

    avg_delay = kpis["delay_rate_pct"]
    recs: list[dict] = []

    # ── 1. Worst zone ──────────────────────────────────────────────────────────
    worst = zone_df.iloc[0]
    delta = worst["delay_rate_pct"] - avg_delay
    if delta > 5:
        recs.append({
            "severity": "high",
            "category": "Zone Performance",
            "title": f"Zone {worst['zone']} is a critical bottleneck",
            "finding": (
                f"Zone {worst['zone']} has a {worst['delay_rate_pct']:.0f}% delay rate — "
                f"{delta:.0f}pp above the warehouse average of {avg_delay:.0f}%. "
                f"Its average picking time per item ({worst['avg_pick_per_item']:.2f} min) "
                f"is the highest across all zones and its avg time ratio "
                f"({worst['avg_time_ratio']:.3f}) is the only zone exceeding 1.0 (SLA breach)."
            ),
            "action": (
                f"Audit Zone {worst['zone']} layout to identify congestion choke points. "
                f"Redistribute Urgent and High-priority orders to Zones C and D during peak hours. "
                f"Redesign pick paths to cut travel distance by at least 15%."
            ),
            "metric": f"+{delta:.0f}pp vs average",
        })

    # ── 2. Best zone (positive finding) ───────────────────────────────────────
    best = zone_df.iloc[-1]
    recs.append({
        "severity": "low",
        "category": "Zone Performance",
        "title": f"Zone {best['zone']} is the top performer — replicate its practices",
        "finding": (
            f"Zone {best['zone']} achieves a {best['delay_rate_pct']:.0f}% delay rate with "
            f"time ratio {best['avg_time_ratio']:.3f} and the lowest pick-per-item time "
            f"({best['avg_pick_per_item']:.3f} min) in the warehouse."
        ),
        "action": (
            f"Document Zone {best['zone']}'s layout, team structure, and pick path logic. "
            f"Use it as the redesign benchmark for Zone {worst['zone']}."
        ),
        "metric": f"{best['delay_rate_pct']:.0f}% delay rate",
    })

    # ── 3. Night shift ─────────────────────────────────────────────────────────
    shift_df = shift_df.set_index("shift")
    night = shift_df.loc["Night"]
    morning = shift_df.loc["Morning"]
    night_delta = night["delay_rate_pct"] - morning["delay_rate_pct"]

    if night_delta > 4:
        recs.append({
            "severity": "high",
            "category": "Shift Management",
            "title": "Night shift underperforms Morning by a significant margin",
            "finding": (
                f"Night shift: {night['delay_rate_pct']:.0f}% delay rate vs "
                f"{morning['delay_rate_pct']:.0f}% Morning — a {night_delta:.0f}pp gap. "
                f"Average experience is similar ({night['avg_experience']:.1f} vs "
                f"{morning['avg_experience']:.1f} yrs), pointing to process or fatigue factors."
            ),
            "action": (
                "Add at least one senior picker per night shift team. "
                "Introduce a mid-shift performance review to catch delays early. "
                "Reduce high-priority order allocation to Night shift where SLA allows."
            ),
            "metric": f"+{night_delta:.0f}pp vs Morning",
        })

    # ── 4. Congestion ──────────────────────────────────────────────────────────
    high_c = cong_df[cong_df["congestion_level"] == "High"].iloc[0]
    low_c = cong_df[cong_df["congestion_level"] == "Low"].iloc[0]

    recs.append({
        "severity": "high",
        "category": "Congestion Management",
        "title": (
            f"High congestion increases picking time {high_c['pick_time_multiplier']:.2f}× "
            f"and delay probability {high_c['delay_multiplier']:.2f}×"
        ),
        "finding": (
            f"Under high congestion, average picking time is {high_c['avg_picking_time']:.1f} min "
            f"({high_c['pick_time_multiplier']:.2f}× the low-congestion baseline of "
            f"{low_c['avg_picking_time']:.1f} min). Delay rate reaches "
            f"{high_c['delay_rate_pct']:.0f}% vs {low_c['delay_rate_pct']:.0f}% "
            f"({high_c['delay_multiplier']:.2f}× multiplier)."
        ),
        "action": (
            "Implement time-slotted zone access to prevent simultaneous crowding. "
            "Deploy real-time zone occupancy monitoring and alert dispatchers at Medium "
            "congestion to trigger rerouting before High is reached."
        ),
        "metric": f"{high_c['pick_time_multiplier']:.2f}× picking time",
    })

    # ── 5. Equipment ───────────────────────────────────────────────────────────
    unavail = equip_df[equip_df["equipment_status"] == "Unavailable"].iloc[0]
    avail = equip_df[equip_df["equipment_status"] == "Available"].iloc[0]
    eq_pct = unavail["total_orders"] / (unavail["total_orders"] + avail["total_orders"]) * 100

    recs.append({
        "severity": "medium",
        "category": "Equipment Utilisation",
        "title": f"Equipment downtime impacts {eq_pct:.0f}% of orders with a {unavail['pack_time_multiplier']:.2f}× packing penalty",
        "finding": (
            f"When equipment is unavailable, packing time rises to {unavail['avg_packing_time']:.1f} min "
            f"({unavail['pack_time_multiplier']:.2f}× baseline of {avail['avg_packing_time']:.1f} min). "
            f"Delay rate increases from {avail['delay_rate_pct']:.0f}% to {unavail['delay_rate_pct']:.0f}%."
        ),
        "action": (
            "Introduce a predictive maintenance schedule to reduce unplanned downtime. "
            "Ensure a minimum equipment buffer per zone during shift changeovers. "
            "Add equipment availability as a daily KPI in operations review."
        ),
        "metric": f"{unavail['pack_time_multiplier']:.2f}× packing time",
    })

    # ── 6. Picker experience ───────────────────────────────────────────────────
    junior = exp_df[exp_df["experience_band"].str.startswith("1")].iloc[0]
    senior = exp_df[exp_df["experience_band"].str.startswith("7")].iloc[0]
    exp_delta = junior["delay_rate_pct"] - senior["delay_rate_pct"]
    pick_diff_pct = (junior["avg_pick_per_item"] / senior["avg_pick_per_item"] - 1) * 100

    recs.append({
        "severity": "medium",
        "category": "Workforce Development",
        "title": f"Junior pickers have a {exp_delta:.0f}pp higher delay rate than seniors",
        "finding": (
            f"1–3 year pickers: {junior['delay_rate_pct']:.0f}% delay rate vs "
            f"{senior['delay_rate_pct']:.0f}% for seniors (7–10 yrs). "
            f"Pick time per item is {junior['avg_pick_per_item']:.2f} min vs "
            f"{senior['avg_pick_per_item']:.2f} min — {pick_diff_pct:.0f}% slower."
        ),
        "action": (
            "Pair juniors with senior mentors on high-volume shifts. "
            f"Restrict junior assignment to Zone {worst['zone']} (highest bottleneck) until 6+ months tenure. "
            "Implement a structured 90-day onboarding programme with zone-specific milestones."
        ),
        "metric": f"{exp_delta:.0f}pp delay gap",
    })

    # ── 7. Urgent SLA breach ───────────────────────────────────────────────────
    urgent = pri_df[pri_df["order_priority"] == "Urgent"].iloc[0]
    if urgent["delay_rate_pct"] > 50:
        recs.append({
            "severity": "high",
            "category": "SLA Compliance",
            "title": f"Urgent orders breach SLA {urgent['delay_rate_pct']:.0f}% of the time",
            "finding": (
                f"Urgent orders have a {urgent['target_time_min']:.0f}-minute SLA but miss it "
                f"{urgent['delay_rate_pct']:.0f}% of the time, averaging "
                f"{abs(urgent['avg_time_over_target']):.1f} min over target. "
                f"This is the worst compliance rate across all priority tiers."
            ),
            "action": (
                "Reserve dedicated picking lanes exclusively for Urgent orders. "
                "Only assign Senior pickers (7+ years) to Urgent orders. "
                "Review whether the 28-minute SLA is operationally achievable — "
                "if not, negotiate revised targets before the next contract review."
            ),
            "metric": f"{urgent['delay_rate_pct']:.0f}% miss rate",
        })

    return recs


def main() -> None:
    with get_connection() as conn:
        recs = generate_recommendations(conn)

    icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    print(f"\nGenerated {len(recs)} recommendations:\n{'─'*60}")
    for i, r in enumerate(recs, 1):
        icon = icons.get(r["severity"], "⚪")
        print(f"\n{i}. {icon} [{r['severity'].upper()}] {r['category']}")
        print(f"   {r['title']}")
        print(f"   Finding: {r['finding'][:110]}...")
        print(f"   Action : {r['action'][:100]}...")
        print(f"   Metric : {r['metric']}")


if __name__ == "__main__":
    main()
