"""
Reusable HTML components for the dashboard.
All st.markdown HTML calls live here — pages import functions, not raw strings.
"""

from pathlib import Path

import streamlit as st

_CSS_PATH = Path(__file__).resolve().parent / "styles" / "main.css"


def load_css() -> None:
    css = _CSS_PATH.read_text()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def spacer() -> None:
    st.markdown("<br>", unsafe_allow_html=True)


def hero_banner(title: str, subtitle: str, primary: str = "#1E3A5F", secondary: str = "#457B9D") -> None:
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, {primary} 0%, {secondary} 100%);
                    padding: 40px 36px; border-radius: 14px; color: white; margin-bottom: 28px;">
            <h1 style="color:white; margin:0; font-size:2.2rem;">{title}</h1>
            <p style="color:#a8c8e8; margin: 8px 0 0; font-size:1.05rem;">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, delta: str = "", accent: str = "#1E3A5F") -> None:
    delta_html = f'<div class="kpi-delta">{delta}</div>' if delta else ""
    st.markdown(
        f"""
        <div class="kpi-card" style="border-left-color:{accent}">
            <div class="kpi-value">{value}</div>
            <div class="kpi-label">{label}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def rec_card(severity: str, category: str, title: str, finding: str, action: str, metric: str) -> None:
    icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    icon = icons.get(severity, "⚪")
    st.markdown(
        f"""
        <div class="rec-card {severity}">
            <span class="badge badge-{severity}">{icon} {severity.upper()}</span>
            &nbsp;
            <span class="badge badge-category">{category}</span>
            <div class="rec-title">{title}</div>
            <div class="rec-section"><b>Finding:</b> {finding}</div>
            <div class="rec-section"><b>Recommended Action:</b> {action}</div>
            <div class="rec-metric">📊 {metric}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
