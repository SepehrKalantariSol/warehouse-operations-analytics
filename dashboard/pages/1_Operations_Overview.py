"""Page 1 — Operations Overview: KPIs, volume, and trend charts."""

import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parent.parent
ROOT = DASHBOARD_DIR.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(DASHBOARD_DIR))

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from utils import (
    CONG_COLORS,
    PALETTE,
    PLOTLY_LAYOUT,
    SHIFT_COLORS,
    ZONE_COLORS,
    kpi_card,
    load_monthly_trend,
    load_priority_performance,
    load_shift_performance,
    load_summary_kpis,
    load_zone_performance,
    page_config,
    section_header,
)

page_config("Operations Overview")

st.title("📊 Operations Overview")
st.caption("Warehouse-wide KPIs, order volume distribution, and monthly performance trends.")

# ── KPI row ────────────────────────────────────────────────────────────────────
kpis = load_summary_kpis()
c1, c2, c3, c4, c5 = st.columns(5)

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
        "Avg Total Time",
        f"{kpis['avg_total_time_min']:.0f} min",
        delta=f"Pick: {kpis['avg_picking_time_min']:.0f}  Pack: {kpis['avg_packing_time_min']:.0f}",
        accent=PALETTE["neutral"],
    )
with c4:
    kpi_card(
        "On-Time Orders",
        f"{int(kpis['total_on_time']):,}",
        delta=f"✅ {100 - kpis['delay_rate_pct']:.1f}% on-time",
        accent=PALETTE["success"],
    )
with c5:
    kpi_card(
        "Avg Items / Order",
        f"{kpis['avg_items_per_order']:.0f}",
        delta=f"Avg distance: {kpis['avg_distance_m']:.0f} m",
        accent=PALETTE["neutral"],
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── Volume and zone delay ──────────────────────────────────────────────────────
section_header("Order Distribution", "Volume by shift and delay rate by zone")
col1, col2 = st.columns(2)

with col1:
    shift_df = load_shift_performance()
    fig = px.bar(
        shift_df,
        x="shift",
        y="total_orders",
        color="shift",
        color_discrete_sequence=SHIFT_COLORS,
        text="total_orders",
        labels={"total_orders": "Orders", "shift": "Shift"},
        title="Orders by Shift",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(**PLOTLY_LAYOUT, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    zone_df = load_zone_performance()
    fig = px.bar(
        zone_df.sort_values("delay_rate_pct"),
        x="delay_rate_pct",
        y="zone",
        orientation="h",
        color="delay_rate_pct",
        color_continuous_scale=["#2A9D8F", "#F4A261", "#E63946"],
        text="delay_rate_pct",
        labels={"delay_rate_pct": "Delay Rate (%)", "zone": "Zone"},
        title="Delay Rate by Zone (%)",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(**PLOTLY_LAYOUT, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

# ── Monthly trend ──────────────────────────────────────────────────────────────
section_header("Monthly Trend", "Order volume and delay rate over time")
monthly = load_monthly_trend()

fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(
    go.Bar(
        x=monthly["year_month"],
        y=monthly["total_orders"],
        name="Orders",
        marker_color="#a8c8e8",
        opacity=0.8,
    ),
    secondary_y=False,
)
fig.add_trace(
    go.Scatter(
        x=monthly["year_month"],
        y=monthly["delay_rate_pct"],
        name="Delay Rate %",
        line=dict(color=PALETTE["danger"], width=2.5),
        mode="lines+markers",
        marker=dict(size=6),
    ),
    secondary_y=True,
)
fig.update_layout(
    **PLOTLY_LAYOUT,
    title="Monthly Orders & Delay Rate",
    legend=dict(x=0.01, y=0.99),
    hovermode="x unified",
)
fig.update_yaxes(title_text="Order Volume", secondary_y=False)
fig.update_yaxes(title_text="Delay Rate (%)", secondary_y=True)
st.plotly_chart(fig, use_container_width=True)

# ── Priority performance ───────────────────────────────────────────────────────
section_header("Priority SLA Performance", "How each priority tier performs against its SLA target")
pri_df = load_priority_performance()

col3, col4 = st.columns(2)

with col3:
    fig = px.bar(
        pri_df,
        x="order_priority",
        y="delay_rate_pct",
        color="delay_rate_pct",
        color_continuous_scale=["#2A9D8F", "#F4A261", "#E63946"],
        text="delay_rate_pct",
        labels={"delay_rate_pct": "Delay Rate (%)", "order_priority": "Priority"},
        title="Delay Rate by Priority",
        category_orders={"order_priority": ["Urgent", "High", "Medium", "Low"]},
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(**PLOTLY_LAYOUT, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

with col4:
    fig = px.bar(
        pri_df,
        x="order_priority",
        y=["avg_total_time", "target_time_min"],
        barmode="group",
        color_discrete_map={"avg_total_time": PALETTE["neutral"], "target_time_min": PALETTE["success"]},
        labels={"value": "Time (min)", "order_priority": "Priority", "variable": ""},
        title="Avg Time vs SLA Target (min)",
        category_orders={"order_priority": ["Urgent", "High", "Medium", "Low"]},
    )
    fig.update_layout(**PLOTLY_LAYOUT)
    newnames = {"avg_total_time": "Avg Total Time", "target_time_min": "SLA Target"}
    fig.for_each_trace(lambda t: t.update(name=newnames.get(t.name, t.name)))
    st.plotly_chart(fig, use_container_width=True)

# ── Shift performance table ────────────────────────────────────────────────────
section_header("Shift Performance Summary")
shift_display = load_shift_performance()[
    ["shift", "total_orders", "delay_rate_pct", "avg_total_time", "avg_picking_time", "avg_packing_time", "avg_experience"]
].rename(columns={
    "shift": "Shift",
    "total_orders": "Orders",
    "delay_rate_pct": "Delay Rate %",
    "avg_total_time": "Avg Time (min)",
    "avg_picking_time": "Avg Picking",
    "avg_packing_time": "Avg Packing",
    "avg_experience": "Avg Experience (yrs)",
})
st.dataframe(shift_display, use_container_width=True, hide_index=True)
