"""Page 2 — Bottleneck Analysis: zones, congestion, equipment, and experience."""

import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parent.parent
ROOT = DASHBOARD_DIR.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(DASHBOARD_DIR))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import (
    PALETTE,
    PLOTLY_LAYOUT,
    ZONE_COLORS,
    load_bottleneck_summary,
    load_congestion_impact,
    load_equipment_impact,
    load_experience_vs_delay,
    load_slow_orders,
    load_zone_performance,
    load_zone_shift_heatmap,
    page_config,
    section_header,
)

page_config("Bottleneck Analysis")

st.title("🔍 Bottleneck Analysis")
st.caption("Identify where delays originate — by zone, congestion level, equipment, and picker experience.")

# ── Bottleneck scores ──────────────────────────────────────────────────────────
section_header(
    "Composite Bottleneck Score by Zone",
    "Score 0–100 combining delay rate (40%), time ratio (40%), and pick time per item (20%)",
)
bottleneck_df = load_bottleneck_summary()

fig = px.bar(
    bottleneck_df.sort_values("bottleneck_score"),
    x="bottleneck_score",
    y="zone",
    orientation="h",
    color="bottleneck_score",
    color_continuous_scale=["#2A9D8F", "#F4A261", "#E63946"],
    text="bottleneck_score",
    labels={"bottleneck_score": "Bottleneck Score", "zone": "Zone"},
    range_color=[0, 100],
)
fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
fig.update_layout(**PLOTLY_LAYOUT, coloraxis_showscale=False, height=280)
st.plotly_chart(fig, use_container_width=True)

# ── Zone × Shift heatmap ───────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    section_header("Zone × Shift Heatmap", "Delay rate % per zone-shift combination")
    pivot = load_zone_shift_heatmap()
    fig = px.imshow(
        pivot,
        color_continuous_scale=["#d4edda", "#fff3cd", "#f8d7da", "#E63946"],
        aspect="auto",
        text_auto=".1f",
        labels=dict(color="Delay Rate %"),
        zmin=20,
        zmax=65,
    )
    fig.update_layout(**PLOTLY_LAYOUT, height=300)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    section_header("Zone KPI Detail", "Ranked by delay rate")
    zone_df = load_zone_performance()[
        ["zone", "total_orders", "delay_rate_pct", "avg_total_time",
         "avg_picking_time", "avg_time_ratio", "avg_pick_per_item"]
    ].rename(columns={
        "zone": "Zone",
        "total_orders": "Orders",
        "delay_rate_pct": "Delay %",
        "avg_total_time": "Avg Time",
        "avg_picking_time": "Avg Pick",
        "avg_time_ratio": "Time Ratio",
        "avg_pick_per_item": "Pick/Item",
    })
    st.dataframe(
        zone_df,
        use_container_width=True,
        hide_index=True,
        height=300,
    )

st.markdown("---")

# ── Congestion impact ──────────────────────────────────────────────────────────
section_header(
    "Congestion Impact",
    "How congestion level affects picking time and delay probability",
)
cong_df = load_congestion_impact()
col3, col4 = st.columns(2)

with col3:
    fig = px.bar(
        cong_df,
        x="congestion_level",
        y="avg_picking_time",
        color="congestion_level",
        color_discrete_sequence=["#2A9D8F", "#F4A261", "#E63946"],
        text="pick_time_multiplier",
        labels={"avg_picking_time": "Avg Picking Time (min)", "congestion_level": "Congestion"},
        title="Picking Time by Congestion Level",
        category_orders={"congestion_level": ["Low", "Medium", "High"]},
    )
    fig.update_traces(texttemplate="%{text:.2f}×", textposition="outside")
    fig.update_layout(**PLOTLY_LAYOUT, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col4:
    fig = px.bar(
        cong_df,
        x="congestion_level",
        y="delay_rate_pct",
        color="congestion_level",
        color_discrete_sequence=["#2A9D8F", "#F4A261", "#E63946"],
        text="delay_multiplier",
        labels={"delay_rate_pct": "Delay Rate (%)", "congestion_level": "Congestion"},
        title="Delay Rate by Congestion Level",
        category_orders={"congestion_level": ["Low", "Medium", "High"]},
    )
    fig.update_traces(texttemplate="%{text:.2f}× baseline", textposition="outside")
    fig.update_layout(**PLOTLY_LAYOUT, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Equipment & experience ─────────────────────────────────────────────────────
col5, col6 = st.columns(2)

with col5:
    section_header("Equipment Impact", "Packing time and delay rate when equipment is unavailable")
    equip_df = load_equipment_impact()
    fig = px.bar(
        equip_df,
        x="equipment_status",
        y=["avg_picking_time", "avg_packing_time"],
        barmode="group",
        color_discrete_map={
            "avg_picking_time": PALETTE["neutral"],
            "avg_packing_time": PALETTE["danger"],
        },
        labels={"value": "Time (min)", "equipment_status": "Equipment", "variable": ""},
        title="Picking & Packing Time by Equipment Status",
    )
    newnames = {"avg_picking_time": "Picking Time", "avg_packing_time": "Packing Time"}
    fig.for_each_trace(lambda t: t.update(name=newnames.get(t.name, t.name)))

    # Annotate packing time multiplier
    for i, row in equip_df.iterrows():
        fig.add_annotation(
            x=row["equipment_status"],
            y=row["avg_packing_time"] + 0.5,
            text=f"{row['pack_time_multiplier']:.2f}×" if i == 1 else "baseline",
            showarrow=False,
            font=dict(size=11, color=PALETTE["danger"]),
        )
    fig.update_layout(**PLOTLY_LAYOUT)
    st.plotly_chart(fig, use_container_width=True)

with col6:
    section_header("Picker Experience vs Delay", "Delay rate and pick-per-item by experience band")
    exp_df = load_experience_vs_delay()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=exp_df["experience_band"],
        y=exp_df["delay_rate_pct"],
        name="Delay Rate %",
        marker_color=[PALETTE["danger"], PALETTE["warning"], PALETTE["success"]],
        text=exp_df["delay_rate_pct"],
        texttemplate="%{text:.1f}%",
        textposition="outside",
    ))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Delay Rate by Picker Experience Band",
        yaxis_title="Delay Rate (%)",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Slow orders table ──────────────────────────────────────────────────────────
section_header(
    "Top 50 Worst Delayed Orders",
    "Orders with highest time_ratio — greatest SLA breaches",
)
slow_df = load_slow_orders(50)[
    ["order_id", "zone", "shift", "order_priority", "congestion_level",
     "total_time", "target_time", "time_ratio", "time_over_target"]
].rename(columns={
    "order_id": "Order ID",
    "zone": "Zone",
    "shift": "Shift",
    "order_priority": "Priority",
    "congestion_level": "Congestion",
    "total_time": "Total (min)",
    "target_time": "Target (min)",
    "time_ratio": "Time Ratio",
    "time_over_target": "Over Target (min)",
})
st.dataframe(slow_df, use_container_width=True, hide_index=True, height=350)
