import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from src.cleaning import load_file, detect_columns, clean_data, CANDIDATES
from src.kpis import compute_kpis, monthly_trend, group_summary
from src.forecasting import forecast_sales

from src.diagnosis import diagnose, health_label

st.set_page_config(page_title="AI Business Doctor", page_icon="🧠", layout="wide")
st.title("🧠 AI-Powered Business Doctor")

uploaded = st.sidebar.file_uploader("Upload CSV / Excel", type=["csv", "xlsx", "xls"])

if uploaded is None:
    st.info("Upload a business dataset (CSV / Excel) from the sidebar to begin.")
    st.stop()

raw = load_file(uploaded)
st.sidebar.success(f"Loaded: {raw.shape[0]:,} rows, {raw.shape[1]} columns")

# Auto-detect columns, and let the user override them
detected = detect_columns(raw)
st.sidebar.subheader("Column Mapping")
mapping = {}
for role in CANDIDATES:
    options = ["-- none --"] + list(raw.columns)
    default = options.index(detected[role]) if role in detected else 0
    choice = st.sidebar.selectbox(
        role,
        options,
        index=default,
        key=f"map_{role}_{uploaded.name}_{uploaded.size}",
    )
    if choice != "-- none --":
        mapping[role] = choice

if "Date" not in mapping or "Sales" not in mapping:
    st.error("Please select at least the Date and Sales columns.")
    st.stop()

df = clean_data(raw, mapping)

# KPI cards
k = compute_kpis(df)
cols = st.columns(len(k))
for col, (name, val) in zip(cols, k.items()):
    if "%" in name:
        col.metric(name, f"{val:.2f}%")
    elif name in ("Rows", "Orders", "Customers"):
        col.metric(name, f"{val:,}")
    else:
        col.metric(name, f"${val:,.0f}")
# Business diagnosis
score, issues = diagnose(df)

st.subheader("🩺 Business Health Check")
left, right = st.columns([1, 2])

with left:
    gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": health_label(score)},
        gauge={"axis": {"range": [0, 100]}},
    ))
    gauge.update_layout(height=280, margin=dict(t=60, b=0, l=20, r=20))
    st.plotly_chart(gauge, width="stretch")

with right:
    if not issues:
        st.success("No major problems detected.")
    for i in issues:
        message = f"**{i['title']}**: {i['detail']}"
        if i["severity"] == "critical":
            st.error(message)
        else:
            st.warning(message)
y_cols = [c for c in ["Sales", "Profit"] if c in df.columns]

# Charts
st.plotly_chart(
    px.line(monthly_trend(df), x="Month", y=y_cols, title="Monthly Trend"),
    width="stretch",
)

if "Category" in df.columns:
    st.plotly_chart(
        px.bar(
            group_summary(df, "Category"),
            x="Category",
            y=y_cols,
            barmode="group",
            title="Category Performance",
        ),
        width="stretch",
    )

# Sales forecast
st.subheader("📈 Sales Forecast (next 6 months)")
result = forecast_sales(df)

if result is None:
    st.info("Not enough monthly data to build a forecast (need about 2.5 years).")
else:
    hist = result["history"]
    fut = result["future"]

    fig = go.Figure()
    fig.add_scatter(x=hist.index, y=hist.values, name="Actual")
    fig.add_scatter(x=fut["Date"], y=fut["Forecast"], name="Forecast", line=dict(dash="dash"))
    fig.update_layout(title=f"Model used: {result['model_used']}")
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    r, b = result["rf_scores"], result["baseline_scores"]
    c1.metric("Random Forest MAPE", f"{r['MAPE']:.1f}%")
    c2.metric("Baseline MAPE", f"{b['MAPE']:.1f}%")

with st.expander("View cleaned data"):
    st.dataframe(df.head(100))
    