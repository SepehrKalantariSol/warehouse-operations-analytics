"""
Shared dashboard utilities: paths, colour palette, and cached data loaders.
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

def page_config(title: str) -> None:
    from components import load_css
    st.set_page_config(
        page_title=f"{title} | Warehouse Analytics",
        page_icon="🏭",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    load_css()


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
