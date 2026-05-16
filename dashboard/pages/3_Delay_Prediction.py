"""Page 3 — Delay Prediction: ML model form and live inference."""

import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parent.parent
ROOT = DASHBOARD_DIR.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(DASHBOARD_DIR))

from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import PALETTE, PLOTLY_LAYOUT, load_ml_model, page_config, section_header

page_config("Delay Prediction")

# ── Encoding maps (must match preprocess.py exactly) ──────────────────────────
SHIFT_MAP      = {"Morning": 0, "Evening": 1, "Night": 2}
ZONE_MAP       = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}
PRIORITY_MAP   = {"Low": 0, "Medium": 1, "High": 2, "Urgent": 3}
CONGESTION_MAP = {"Low": 0, "Medium": 1, "High": 2}
PRIORITY_TARGET = {"Low": 55, "Medium": 45, "High": 38, "Urgent": 28}

PRE_ORDER_FEATURES = [
    "items_count", "picker_experience", "distance_travelled",
    "workload_index", "target_time", "is_experienced",
    "is_high_congestion", "equipment_penalty", "is_weekend",
    "order_month", "order_quarter", "order_day_of_week",
    "shift_encoded", "zone_encoded", "priority_encoded", "congestion_encoded",
]


def build_feature_vector(inputs: dict) -> list[float]:
    d: date = inputs["order_date"]
    quarter = (d.month - 1) // 3 + 1
    return [
        inputs["items_count"],
        inputs["picker_experience"],
        inputs["distance_travelled"],
        inputs["items_count"] * (inputs["distance_travelled"] / 100),   # workload_index
        PRIORITY_TARGET[inputs["order_priority"]],                       # target_time
        int(inputs["picker_experience"] >= 7),                           # is_experienced
        int(inputs["congestion_level"] == "High"),                       # is_high_congestion
        int(not inputs["equipment_available"]),                          # equipment_penalty
        int(d.weekday() >= 5),                                           # is_weekend
        d.month,                                                         # order_month
        quarter,                                                         # order_quarter
        d.weekday(),                                                     # order_day_of_week
        SHIFT_MAP[inputs["shift"]],
        ZONE_MAP[inputs["zone"]],
        PRIORITY_MAP[inputs["order_priority"]],
        CONGESTION_MAP[inputs["congestion_level"]],
    ]


def risk_gauge(probability: float) -> go.Figure:
    pct = probability * 100
    if pct < 35:
        color, label = PALETTE["success"], "LOW RISK"
    elif pct < 65:
        color, label = PALETTE["warning"], "MEDIUM RISK"
    else:
        color, label = PALETTE["danger"], "HIGH RISK"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number={"suffix": "%", "font": {"size": 42, "color": color}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#ccc"},
            "bar": {"color": color, "thickness": 0.25},
            "bgcolor": "white",
            "steps": [
                {"range": [0, 35],  "color": "#e8f5e9"},
                {"range": [35, 65], "color": "#fff8e1"},
                {"range": [65, 100],"color": "#ffebee"},
            ],
            "threshold": {
                "line": {"color": color, "width": 3},
                "thickness": 0.75,
                "value": pct,
            },
        },
        title={
            "text": f"Delay Risk<br><span style='font-size:0.8em;color:{color}'><b>{label}</b></span>",
            "font": {"size": 16},
        },
    ))
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=60, b=20))
    return fig


# ── Page layout ────────────────────────────────────────────────────────────────
st.title("🤖 Delay Prediction")
st.caption(
    "Enter order parameters to predict the probability of a delay. "
    "The model uses only pre-order features — no picking/packing times needed."
)

# Model status
try:
    model, meta = load_ml_model()
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Accuracy",  f"{meta['accuracy']:.1%}")
    col_m2.metric("Precision", f"{meta['precision']:.1%}")
    col_m3.metric("Recall",    f"{meta['recall']:.1%}")
    col_m4.metric("ROC-AUC",   f"{meta['roc_auc']:.3f}")
    model_ready = True
except FileNotFoundError:
    st.warning("Model not found. Run `python src/ml_model.py` first.")
    model_ready = False
    model, meta = None, {}

st.markdown("---")

# ── Input form ─────────────────────────────────────────────────────────────────
section_header("Order Parameters", "Fill in the details of the order to predict")

col_left, col_right = st.columns([1.1, 1])

with col_left:
    with st.form("prediction_form"):
        st.markdown("**Order details**")
        fc1, fc2 = st.columns(2)
        with fc1:
            zone = st.selectbox("Zone", ["A", "B", "C", "D", "E"])
            shift = st.selectbox("Shift", ["Morning", "Evening", "Night"])
            priority = st.selectbox("Order Priority", ["Low", "Medium", "High", "Urgent"])
            congestion = st.selectbox("Congestion Level", ["Low", "Medium", "High"])
        with fc2:
            items = st.slider("Items Count", 1, 50, 20)
            experience = st.slider("Picker Experience (yrs)", 1, 10, 5)
            distance = st.slider("Distance Travelled (m)", 30, 400, 150)
            equipment = st.checkbox("Equipment Available", value=True)
            order_date = st.date_input("Order Date", value=date.today())

        predict_btn = st.form_submit_button("🔍 Predict Delay Risk", use_container_width=True)

with col_right:
    if predict_btn and model_ready:
        inputs = {
            "zone": zone, "shift": shift, "order_priority": priority,
            "congestion_level": congestion, "items_count": items,
            "picker_experience": experience, "distance_travelled": distance,
            "equipment_available": equipment, "order_date": order_date,
        }
        features = build_feature_vector(inputs)
        prob = float(model.predict_proba(np.array(features).reshape(1, -1))[0, 1])

        # Gauge
        st.plotly_chart(risk_gauge(prob), use_container_width=True)

        # Risk factors (features pushing risk up)
        st.markdown("**Key risk factors for this order:**")
        risk_flags = []
        if zone == "B":
            risk_flags.append("🔴 Zone B — highest bottleneck zone (+12pp delay rate)")
        if shift == "Night":
            risk_flags.append("🔴 Night shift — 8pp higher delay rate than Morning")
        if congestion == "High":
            risk_flags.append("🔴 High congestion — 1.44× picking time")
        if not equipment:
            risk_flags.append("🟡 Equipment unavailable — 1.32× packing time")
        if experience <= 3:
            risk_flags.append("🟡 Junior picker — 20pp higher delay rate than seniors")
        if priority == "Urgent":
            risk_flags.append("🟡 Urgent priority — tightest SLA, 64.8% miss rate")
        if not risk_flags:
            risk_flags.append("🟢 No major risk factors detected for this order")

        for flag in risk_flags:
            st.markdown(f"- {flag}")
    elif predict_btn and not model_ready:
        st.error("Model unavailable. Run `python src/ml_model.py` to train it.")
    else:
        st.info("Fill in the order parameters on the left and click **Predict** to see the delay risk.")

# ── Feature importance ─────────────────────────────────────────────────────────
if model_ready and meta.get("feature_importance"):
    st.markdown("---")
    section_header("Feature Importance", "Which inputs drive the model's predictions most")

    imp_df = (
        pd.DataFrame.from_dict(meta["feature_importance"], orient="index", columns=["importance"])
        .reset_index()
        .rename(columns={"index": "feature"})
        .sort_values("importance")
    )

    # Human-readable labels
    labels = {
        "items_count": "Items Count",
        "picker_experience": "Picker Experience",
        "distance_travelled": "Distance Travelled",
        "workload_index": "Workload Index",
        "target_time": "SLA Target Time",
        "is_experienced": "Is Experienced (≥7 yrs)",
        "is_high_congestion": "High Congestion Flag",
        "equipment_penalty": "Equipment Unavailable",
        "is_weekend": "Is Weekend",
        "order_month": "Order Month",
        "order_quarter": "Order Quarter",
        "order_day_of_week": "Day of Week",
        "shift_encoded": "Shift",
        "zone_encoded": "Zone",
        "priority_encoded": "Order Priority",
        "congestion_encoded": "Congestion Level",
    }
    imp_df["feature_label"] = imp_df["feature"].map(labels).fillna(imp_df["feature"])

    fig = px.bar(
        imp_df,
        x="importance",
        y="feature_label",
        orientation="h",
        color="importance",
        color_continuous_scale=["#a8c8e8", PALETTE["primary"]],
        labels={"importance": "Feature Importance", "feature_label": ""},
        title="Random Forest Feature Importance (all features)",
    )
    fig.update_layout(**PLOTLY_LAYOUT, coloraxis_showscale=False, height=420)
    st.plotly_chart(fig, use_container_width=True)

    # Confusion matrix
    if "confusion_matrix" in meta:
        st.markdown("---")
        section_header("Confusion Matrix", f"Test set performance (n={meta.get('n_test', '?')})")
        cm = meta["confusion_matrix"]
        cm_labels = ["On-Time (0)", "Delayed (1)"]
        fig_cm = px.imshow(
            cm,
            x=cm_labels,
            y=cm_labels,
            color_continuous_scale=["white", PALETTE["primary"]],
            text_auto=True,
            labels=dict(x="Predicted", y="Actual", color="Count"),
            aspect="equal",
        )
        fig_cm.update_layout(**PLOTLY_LAYOUT, height=300)
        st.plotly_chart(fig_cm, use_container_width=False)
