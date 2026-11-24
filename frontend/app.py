import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import api_client as api

st.set_page_config(page_title="AI Business Doctor", page_icon="🧠", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 2rem; max-width: 1250px;}
    .hero {background: linear-gradient(90deg, #4F46E5 0%, #7C3AED 100%);
           padding: 1.4rem 1.8rem; border-radius: 14px; color: white; margin-bottom: 1.2rem;}
    .hero h1 {margin: 0; font-size: 2rem; color: white;}
    .hero p {margin: 0.3rem 0 0 0; opacity: 0.9;}
    [data-testid="stMetric"] {background: #F3F4F8; border-radius: 12px; padding: 0.8rem 1rem;}
    button[data-baseweb="tab"] {font-size: 1rem; font-weight: 600;}
    </style>
    <div class="hero">
        <h1>🧠 AI Business Doctor</h1>
        <p>Upload your sales data. Get a health check, forecast, customer segments and AI advice.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


def money(text):
    return str(text).replace("$", "\\$")


def safe_get(path):
    """Returns (data, error_message)."""
    try:
        return api.get(path), None
    except Exception as e:
        return None, str(e)


# ---------------- Sidebar ----------------
st.sidebar.header("📂 Data")
uploaded = st.sidebar.file_uploader("Upload CSV / Excel", type=["csv", "xlsx", "xls"])

try:
    api.get("/health")
except Exception:
    st.error("Cannot reach the backend API. If it is hosted on Render, wait about a minute and refresh "
             "(free instances sleep when idle). Locally, start it with: "
             "python -m uvicorn backend.main:app --port 8000")
    st.stop()

if uploaded is None:
    st.info("👈 Upload a business dataset (CSV / Excel) from the sidebar to begin.")
    st.stop()

file_key = f"{uploaded.name}_{uploaded.size}"
if st.session_state.get("file_key") != file_key:
    with st.spinner("Uploading and cleaning data..."):
        try:
            info = api.upload(uploaded.name, uploaded.getvalue())
        except Exception as e:
            st.error(f"Could not process this file: {e}")
            st.stop()
    st.session_state.file_key = file_key
    st.session_state.info = info
    st.session_state.recs = None
    st.session_state.chat = []

info = st.session_state.info
st.sidebar.success(f"{info['rows']:,} rows loaded and saved to the database")
with st.sidebar.expander("Detected columns"):
    st.json(info["detected_columns"])

# ---------------- Data from API ----------------
kpi_data, kpi_err = safe_get("/kpis")
diag, diag_err = safe_get("/diagnosis")
seg_data, seg_err = safe_get("/segments")
fc, fc_err = safe_get("/forecast")

if kpi_err:
    st.error(f"Could not load KPIs: {kpi_err}")
    st.stop()

tab_over, tab_cust, tab_fc, tab_ai, tab_data = st.tabs(
    ["📊 Overview", "👥 Customers", "📈 Forecast", "🤖 AI Assistant", "📄 Report & Data"]
)

# ===== Overview =====
with tab_over:
    kpis = kpi_data["kpis"]
    metric_cols = st.columns(len(kpis))
    for col, (name, val) in zip(metric_cols, kpis.items()):
        if "%" in name:
            col.metric(name, f"{val:.2f}%")
        elif name in ("Rows", "Orders", "Customers"):
            col.metric(name, f"{int(val):,}")
        else:
            col.metric(name, f"${val:,.0f}")

    st.subheader("🩺 Business Health Check")
    if diag_err:
        st.warning(f"Health check unavailable: {diag_err}")
    else:
        left, right = st.columns([1, 2])
        score = diag["score"]
        with left:
            color = "#16A34A" if score >= 80 else "#F59E0B" if score >= 60 else "#DC2626"
            gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=score, title={"text": diag["label"]},
                gauge={"axis": {"range": [0, 100]}, "bar": {"color": color}},
            ))
            gauge.update_layout(height=260, margin=dict(t=60, b=0, l=20, r=20))
            st.plotly_chart(gauge, width="stretch")
        with right:
            if not diag["issues"]:
                st.success("No major problems detected.")
            for i in diag["issues"]:
                message = money(f"**{i['title']}**: {i['detail']}")
                (st.error if i["severity"] == "critical" else st.warning)(message)

    trend = pd.DataFrame(kpi_data["monthly_trend"])
    y_cols = [c for c in ["Sales", "Profit"] if c in trend.columns]
    fig = px.line(trend, x="Month", y=y_cols, title="Monthly Trend")
    fig.update_layout(legend_title_text="")
    st.plotly_chart(fig, width="stretch")

# ===== Customers =====
with tab_cust:
    st.subheader("Customer Segments (RFM + KMeans)")
    if seg_err:
        st.info(f"Customer segmentation not available: {seg_err}")
    else:
        seg = pd.DataFrame(seg_data["segments"])
        s1, s2 = st.columns(2)
        with s1:
            st.plotly_chart(px.pie(seg, names="Segment", values="Customers",
                                   title="Customers per segment", hole=0.45), width="stretch")
        with s2:
            st.plotly_chart(px.bar(seg, x="Segment", y="TotalRevenue", color="Segment",
                                   title="Revenue per segment"), width="stretch")
        st.markdown("**Suggested action per segment**")
        for _, row in seg.iterrows():
            st.markdown(money(f"- **{row['Segment']}** ({int(row['Customers'])} customers): "
                              f"{row['Suggested action']}"))
        with st.expander("Segment table"):
            st.dataframe(seg, width="stretch")

# ===== Forecast =====
with tab_fc:
    st.subheader("Sales Forecast (next 6 months)")
    if fc_err:
        st.info(f"Forecast not available: {fc_err}")
    else:
        fig = go.Figure()
        fig.add_scatter(x=fc["history"]["dates"], y=fc["history"]["values"], name="Actual")
        fig.add_scatter(x=fc["future"]["dates"], y=fc["future"]["values"], name="Forecast",
                        line=dict(dash="dash"))
        fig.update_layout(title=f"Model used: {fc['model_used']}")
        st.plotly_chart(fig, width="stretch")

        m1, m2, m3 = st.columns(3)
        m1.metric("Random Forest MAPE", f"{fc['random_forest_scores']['MAPE']:.1f}%")
        m2.metric("Baseline MAPE", f"{fc['baseline_scores']['MAPE']:.1f}%")
        avg = sum(fc["future"]["values"]) / len(fc["future"]["values"])
        m3.metric("Avg forecast / month", f"${avg:,.0f}")
        st.caption("MAPE = average percentage error on the last 6 months. Lower is better.")

# ===== AI Assistant =====
with tab_ai:
    st.subheader("💊 AI Recommendations")
    if st.button("Generate recommendations", type="primary"):
        with st.spinner("Writing recommendations..."):
            try:
                st.session_state.recs = api.post("/recommendations")["recommendations"]
            except Exception as e:
                st.error(f"AI service problem: {e}")

    if st.session_state.get("recs"):
        with st.container(border=True):
            st.markdown(money(st.session_state.recs))

    st.divider()
    st.subheader("💬 Ask your Business Doctor")
    st.caption("Ask anything about your uploaded data.")

    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.write(money(msg["text"]))
            if msg.get("sql"):
                with st.expander("SQL used"):
                    st.code(msg["sql"], language="sql")

    question = st.chat_input("Ask about your data, e.g. Top 5 products by sales")
    if question:
        st.session_state.chat.append({"role": "user", "text": question})
        with st.spinner("Thinking..."):
            try:
                out = api.post("/chat", {"question": question})
                answer, used_sql = out["answer"], out["sql"]
            except Exception as e:
                answer, used_sql = f"Sorry, the AI service had a problem: {e}", None
        st.session_state.chat.append({"role": "assistant", "text": answer, "sql": used_sql})
        st.rerun()

# ===== Report & Data =====
with tab_data:
    st.subheader("📄 PDF Report")
    try:
        st.download_button("⬇️ Download PDF report", api.get_pdf(),
                           file_name="business_report.pdf", mime="application/pdf")
        st.caption("Tip: generate recommendations on the AI Assistant tab first to include them.")
    except Exception as e:
        st.warning(f"PDF report could not be created: {e}")

    st.divider()
    st.subheader("🗄️ Run a SQL query")
    sql_text = st.text_area("SELECT query", "SELECT * FROM sales LIMIT 10")
    if st.button("Run query"):
        try:
            rows = api.post("/query", {"sql": sql_text})["rows"]
            st.dataframe(pd.DataFrame(rows), width="stretch")
        except Exception as e:
            st.error(f"Query failed: {e}")