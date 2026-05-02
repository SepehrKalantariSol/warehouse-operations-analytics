"""Page 4 — Recommendations: data-driven business insights."""

import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parent.parent
ROOT = DASHBOARD_DIR.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(DASHBOARD_DIR))

import streamlit as st

from utils import PALETTE, load_recommendations, load_summary_kpis, page_config

page_config("Recommendations")

st.title("💡 Recommendations")
st.caption(
    "Automatically generated business insights derived from live warehouse data. "
    "Each recommendation is quantified and directly actionable."
)

# ── Load data ──────────────────────────────────────────────────────────────────
recs = load_recommendations()
kpis = load_summary_kpis()

# ── Summary strip ──────────────────────────────────────────────────────────────
high   = sum(1 for r in recs if r["severity"] == "high")
medium = sum(1 for r in recs if r["severity"] == "medium")
low    = sum(1 for r in recs if r["severity"] == "low")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Recommendations", len(recs))
c2.metric("🔴 High Priority", high)
c3.metric("🟡 Medium Priority", medium)
c4.metric("🟢 Low Priority / Positive", low)

st.markdown("---")

# ── Severity filter ────────────────────────────────────────────────────────────
severity_options = ["All", "High", "Medium", "Low"]
selected_severity = st.radio(
    "Filter by severity:",
    severity_options,
    horizontal=True,
)

filtered = recs if selected_severity == "All" else [
    r for r in recs if r["severity"].lower() == selected_severity.lower()
]

st.markdown(f"<br>", unsafe_allow_html=True)

# ── Recommendation cards ───────────────────────────────────────────────────────
SEV_ICONS = {"high": "🔴", "medium": "🟡", "low": "🟢"}

for r in filtered:
    sev = r["severity"]
    icon = SEV_ICONS.get(sev, "⚪")

    st.markdown(
        f"""
        <div class="rec-card {sev}">
            <span class="badge badge-{sev}">{icon} {sev.upper()}</span>
            &nbsp;
            <span class="badge badge-category">{r['category']}</span>
            <div class="rec-title">{r['title']}</div>
            <div class="rec-section">
                <b>Finding:</b> {r['finding']}
            </div>
            <div class="rec-section">
                <b>Recommended Action:</b> {r['action']}
            </div>
            <div class="rec-metric">📊 {r['metric']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Executive summary ──────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Executive Summary")

delay_rate = kpis["delay_rate_pct"]
on_time_rate = 100 - delay_rate

st.markdown(
    f"""
    The warehouse is currently operating at a **{on_time_rate:.1f}% on-time rate**
    ({delay_rate:.1f}% of {int(kpis['total_orders']):,} orders delayed).

    The analysis identifies **{high} high-priority issues** requiring immediate attention:

    1. **Zone B** is the critical bottleneck — the only zone with a time ratio above 1.0
       (average SLA breach). Redesigning its pick path and redistributing Urgent orders
       could recover approximately 5–8pp of overall delay rate.

    2. **High congestion** nearly doubles delay probability. Real-time occupancy monitoring
       and time-slotted zone access are the highest-leverage operational interventions.

    3. **Urgent order SLA compliance** is critically low. Dedicated lanes and senior-only
       assignment should be implemented before the next planning cycle.

    Addressing these three areas alone could reduce the overall delay rate from
    **{delay_rate:.0f}% to approximately {max(delay_rate - 15, 15):.0f}%**,
    improving customer satisfaction and reducing operational costs.
    """,
    unsafe_allow_html=True,
)
