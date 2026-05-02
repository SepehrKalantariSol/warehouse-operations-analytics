"""
Warehouse Operations Analytics — Home / Landing Page
Run: streamlit run dashboard/app.py  (from project root)
"""

import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parent
ROOT = DASHBOARD_DIR.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(DASHBOARD_DIR))

import streamlit as st
from utils import (
    BASE_CSS,
    PALETTE,
    kpi_card,
    load_summary_kpis,
    page_config,
)

page_config("Home")

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏭 Warehouse Analytics")
    st.markdown("---")
    st.markdown("**Navigation**")
    st.markdown(
        "Use the pages in the sidebar to explore:\n"
        "- 📊 Operations Overview\n"
        "- 🔍 Bottleneck Analysis\n"
        "- 🤖 Delay Prediction\n"
        "- 💡 Recommendations"
    )
    st.markdown("---")
    st.caption("Data: Jan 2024 – Jun 2025 · 5,000 orders")

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style="background: linear-gradient(135deg, {PALETTE['primary']} 0%, #457B9D 100%);
                padding: 40px 36px; border-radius: 14px; color: white; margin-bottom: 28px;">
        <h1 style="color:white; margin:0; font-size:2.2rem;">🏭 Warehouse Operations Analytics</h1>
        <p style="color:#a8c8e8; margin: 8px 0 0; font-size:1.05rem;">
            Production Intelligence Dashboard · BMW-Style Manufacturing Analytics
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Quick KPIs ─────────────────────────────────────────────────────────────────
try:
    kpis = load_summary_kpis()
    st.markdown("### Key Metrics at a Glance")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Total Orders", f"{int(kpis['total_orders']):,}", accent=PALETTE["primary"])
    with c2:
        kpi_card(
            "Delay Rate",
            f"{kpis['delay_rate_pct']:.1f}%",
            delta="🔴 Target: < 20%",
            accent=PALETTE["danger"],
        )
    with c3:
        kpi_card(
            "Avg Processing Time",
            f"{kpis['avg_total_time_min']:.0f} min",
            accent=PALETTE["neutral"],
        )
    with c4:
        kpi_card(
            "On-Time Orders",
            f"{int(kpis['total_on_time']):,}",
            delta=f"✅ {100 - kpis['delay_rate_pct']:.1f}% on-time rate",
            accent=PALETTE["success"],
        )
except Exception as e:
    st.error(f"Could not load KPIs: {e}. Ensure preprocess.py has been run.")

st.markdown("<br>", unsafe_allow_html=True)

# ── Project overview ───────────────────────────────────────────────────────────
st.markdown("### About This Project")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("""
    **What this dashboard does:**
    - Analyses 18 months of warehouse operations data (5,000 orders)
    - Identifies bottlenecks by zone, shift, and congestion level
    - Predicts order delays using a Random Forest model
    - Generates actionable business recommendations
    """)

with col_b:
    st.markdown("""
    **Tech stack:**
    - `Python` · `Pandas` · `NumPy` for data processing
    - `SQLite` for structured storage and SQL analytics
    - `Scikit-learn` for machine learning (RandomForest)
    - `Streamlit` + `Plotly` for interactive visualisation
    """)

st.markdown("---")

# ── Dataset snapshot ───────────────────────────────────────────────────────────
st.markdown("### Dataset Snapshot")
st.markdown("""
| Feature | Description |
|---|---|
| `zone` (A–E) | Warehouse zones — Zone B is the identified bottleneck |
| `shift` | Morning / Evening / Night — Night has the highest delay rate |
| `congestion_level` | Low / Medium / High — High congestion = 1.44× pick time |
| `picker_experience` | 1–10 years — Junior pickers have 20pp higher delay rate |
| `order_priority` | Low / Medium / High / Urgent — 64.8% of Urgent orders delayed |
| `delayed` | Target variable: 1 = missed SLA, 0 = on time |
""")

st.caption("Navigate using the sidebar to explore full analysis, predictions, and recommendations.")
