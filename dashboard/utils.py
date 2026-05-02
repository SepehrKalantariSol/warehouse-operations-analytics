"""
Shared dashboard utilities: paths, colour palette, CSS, and cached data loaders.
All pages import from here to keep loading logic in one place.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Path setup ─────────────────────────────────────────────────────────────────
DASHBOARD_DIR = Path(__file__).resolve().parent
ROOT = DASHBOARD_DIR.parent
sys.path.insert(0, str(ROOT / "src"))

DB_PATH = ROOT / "data" / "warehouse.db"
MODEL_PATH = ROOT / "models" / "delay_classifier.joblib"
METADATA_PATH = ROOT / "models" / "model_metadata.json"

# ── Colour palette ─────────────────────────────────────────────────────────────
PALETTE = {
    "primary": "#1E3A5F",
    "danger":  "#E63946",
    "warning": "#F4A261",
    "success": "#2A9D8F",
    "neutral": "#457B9D",
}
ZONE_COLORS  = ["#E63946", "#F4A261", "#2A9D8F", "#457B9D", "#1D3557"]
SHIFT_COLORS = ["#F4A261", "#457B9D", "#1E3A5F"]   # Morning, Evening, Night
CONG_COLORS  = ["#2A9D8F", "#F4A261", "#E63946"]   # Low, Medium, High

PLOTLY_LAYOUT = dict(
    font_family="Inter, sans-serif",
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=20, r=20, t=40, b=20),
    hoverlabel=dict(bgcolor="white", font_size=13),
)

# ── Global CSS ─────────────────────────────────────────────────────────────────
BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* KPI cards */
.kpi-card {
    background: white;
    border-radius: 10px;
    padding: 18px 22px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    border-left: 5px solid #1E3A5F;
    height: 100%;
}
.kpi-value { font-size: 2rem; font-weight: 700; color: #1E3A5F; line-height: 1.1; }
.kpi-label { font-size: 0.75rem; color: #6c757d; text-transform: uppercase;
             letter-spacing: 0.8px; margin-top: 4px; }
.kpi-delta { font-size: 0.82rem; margin-top: 3px; }

/* Recommendation cards */
.rec-card {
    background: white; border-radius: 10px; padding: 20px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.07); margin-bottom: 14px;
}
.rec-card.high   { border-left: 5px solid #E63946; }
.rec-card.medium { border-left: 5px solid #F4A261; }
.rec-card.low    { border-left: 5px solid #2A9D8F; }
.rec-title { font-size: 1rem; font-weight: 600; color: #1D3557; margin: 6px 0 10px; }
.rec-section { font-size: 0.85rem; color: #444; margin-bottom: 6px; }
.rec-metric {
    display: inline-block; background: #f0f4f8; color: #1E3A5F;
    font-weight: 600; font-size: 0.78rem; padding: 3px 10px;
    border-radius: 20px; margin-top: 8px;
}
.badge {
    display: inline-block; padding: 2px 10px; border-radius: 20px;
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.5px;
}
.badge-high   { background: #fde8ea; color: #E63946; }
.badge-medium { background: #fef4e8; color: #e07b00; }
.badge-low    { background: #e6f4f2; color: #2A9D8F; }
.badge-category { background: #e8eef4; color: #1E3A5F; }

/* Sidebar */
section[data-testid="stSidebar"] { background: #1D3557; }
section[data-testid="stSidebar"] * { color: white !important; }
section[data-testid="stSidebar"] .stSelectbox label { color: #a8c8e8 !important; }

/* Divider */
hr { border: none; border-top: 1px solid #e9ecef; margin: 16px 0; }
</style>
"""


def page_config(title: str) -> None:
    st.set_page_config(
        page_title=f"{title} | Warehouse Analytics",
        page_icon="🏭",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(BASE_CSS, unsafe_allow_html=True)


def kpi_card(
    label: str,
    value: str,
    delta: str = "",
    accent: str = "#1E3A5F",
) -> None:
    delta_html = f'<div class="kpi-delta">{delta}</div>' if delta else ""
    st.markdown(
        f"""<div class="kpi-card" style="border-left-color:{accent}">
            <div class="kpi-value">{value}</div>
            <div class="kpi-label">{label}</div>
            {delta_html}
        </div>""",
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "") -> None:
    st.markdown(f"### {title}")
    if subtitle:
        st.caption(subtitle)


# ── Cached data loaders ────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_summary_kpis() -> dict:
    from analysis import get_connection, summary_kpis
    with get_connection() as conn:
        return summary_kpis(conn)

@st.cache_data(ttl=300)
def load_zone_performance() -> pd.DataFrame:
    from analysis import get_connection, zone_performance
    with get_connection() as conn:
        return zone_performance(conn)

@st.cache_data(ttl=300)
def load_shift_performance() -> pd.DataFrame:
    from analysis import get_connection, shift_performance
    with get_connection() as conn:
        return shift_performance(conn)

@st.cache_data(ttl=300)
def load_congestion_impact() -> pd.DataFrame:
    from analysis import get_connection, congestion_impact
    with get_connection() as conn:
        return congestion_impact(conn)

@st.cache_data(ttl=300)
def load_equipment_impact() -> pd.DataFrame:
    from analysis import get_connection, equipment_impact
    with get_connection() as conn:
        return equipment_impact(conn)

@st.cache_data(ttl=300)
def load_experience_vs_delay() -> pd.DataFrame:
    from analysis import get_connection, experience_vs_delay
    with get_connection() as conn:
        return experience_vs_delay(conn)

@st.cache_data(ttl=300)
def load_priority_performance() -> pd.DataFrame:
    from analysis import get_connection, priority_performance
    with get_connection() as conn:
        return priority_performance(conn)

@st.cache_data(ttl=300)
def load_monthly_trend() -> pd.DataFrame:
    from analysis import get_connection, monthly_trend
    with get_connection() as conn:
        return monthly_trend(conn)

@st.cache_data(ttl=300)
def load_zone_shift_heatmap() -> pd.DataFrame:
    from analysis import get_connection, zone_shift_heatmap
    with get_connection() as conn:
        return zone_shift_heatmap(conn)

@st.cache_data(ttl=300)
def load_bottleneck_summary() -> pd.DataFrame:
    from analysis import get_connection, bottleneck_summary
    with get_connection() as conn:
        return bottleneck_summary(conn)

@st.cache_data(ttl=300)
def load_slow_orders(top_n: int = 50) -> pd.DataFrame:
    from analysis import get_connection, slow_orders
    with get_connection() as conn:
        return slow_orders(conn, top_n)

@st.cache_resource
def load_ml_model():
    import json
    import joblib
    model = joblib.load(MODEL_PATH)
    with open(METADATA_PATH) as f:
        metadata = json.load(f)
    return model, metadata

@st.cache_data(ttl=300)
def load_recommendations() -> list[dict]:
    from analysis import get_connection
    from recommendations import generate_recommendations
    with get_connection() as conn:
        return generate_recommendations(conn)
