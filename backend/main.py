import io
import json
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from src.cleaning import clean_data, detect_columns, load_file
from src.chatbot import answer_question
from src.database import run_query, save_to_db
from src.diagnosis import diagnose, health_label
from src.forecasting import forecast_sales
from src.kpis import compute_kpis, monthly_trend
from src.recommender import build_summary, get_recommendations
from src.report import build_pdf
from src.segmentation import segment_customers

app = FastAPI(title="AI Business Doctor API", version="1.0")

# In-memory state for the most recently uploaded dataset (single-user demo)
STATE = {}


class ChatRequest(BaseModel):
    question: str


class SQLRequest(BaseModel):
    sql: str


def _records(df):
    """DataFrame -> plain JSON-safe list of dicts."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _need_data():
    if "df" not in STATE:
        raise HTTPException(status_code=400, detail="No dataset uploaded yet. Call POST /upload first.")
    return STATE["df"]


# ---------- SECURITY: allow only read-only SELECT queries ----------
_BANNED_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|replace|truncate|vacuum|reindex)\b",
    re.IGNORECASE,
)


def _is_safe_select(sql: str) -> bool:
    s = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)   # remove /* comments */
    s = re.sub(r"--[^\n]*", " ", s)                  # remove -- comments
    s = s.strip().rstrip(";").strip()
    if not s or ";" in s:                            # empty or multiple statements
        return False
    if not re.match(r"(?is)^(select|with)\b", s):    # must start with SELECT / WITH
        return False
    return not _BANNED_SQL.search(s)


@app.get("/health")
def health():
    return {"status": "ok", "dataset_loaded": "df" in STATE}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    content = await file.read()
    buf = io.BytesIO(content)
    buf.name = file.filename
    try:
        raw = load_file(buf)
        mapping = detect_columns(raw)
        if "Date" not in mapping or "Sales" not in mapping:
            raise ValueError("Could not detect Date and Sales columns.")
        df = clean_data(raw, mapping)
        rows_saved = save_to_db(df)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    STATE.clear()
    STATE["df"] = df
    STATE["mapping"] = mapping
    return {"rows": int(len(df)), "rows_saved_to_db": int(rows_saved), "detected_columns": mapping}


@app.get("/kpis")
def kpis():
    df = _need_data()
    k = compute_kpis(df)
    return {"kpis": {name: float(v) for name, v in k.items()},
            "monthly_trend": _records(monthly_trend(df))}


@app.get("/diagnosis")
def diagnosis():
    df = _need_data()
    score, issues = diagnose(df)
    return {"score": int(score), "label": health_label(score), "issues": issues}


@app.get("/segments")
def segments():
    df = _need_data()
    res = segment_customers(df)
    if res is None:
        raise HTTPException(status_code=422, detail="Segmentation needs Customer and Order columns.")
    STATE["seg"] = res[1]
    return {"segments": _records(res[1].reset_index())}


@app.get("/forecast")
def forecast():
    df = _need_data()
    res = forecast_sales(df)
    if res is None:
        raise HTTPException(status_code=422, detail="Not enough monthly data for a forecast.")
    STATE["forecast"] = res
    hist, fut = res["history"], res["future"]
    return {
        "model_used": res["model_used"],
        "random_forest_scores": {k: float(v) for k, v in res["rf_scores"].items()},
        "baseline_scores": {k: float(v) for k, v in res["baseline_scores"].items()},
        "history": {"dates": [d.strftime("%Y-%m-%d") for d in hist.index],
                    "values": [float(v) for v in hist.values]},
        "future": {"dates": [d.strftime("%Y-%m-%d") for d in fut["Date"]],
                   "values": [float(v) for v in fut["Forecast"]]},
    }


@app.post("/chat")
def chat(req: ChatRequest):
    _need_data()
    try:
        answer, sql, _ = answer_question(req.question)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI service problem: {e}")
    return {"answer": answer, "sql": sql}


@app.post("/recommendations")
def recommendations():
    df = _need_data()
    k = compute_kpis(df)
    score, issues = diagnose(df)
    seg = STATE.get("seg")
    if seg is None:
        res = segment_customers(df)
        seg = res[1] if res else None
    fc = STATE.get("forecast")
    if fc is None:
        fc = forecast_sales(df)
    try:
        text = get_recommendations(build_summary(k, score, issues, fc, seg))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI service problem: {e}")
    STATE["recs"] = text
    return {"recommendations": text}


@app.get("/report")
def report():
    df = _need_data()
    k = compute_kpis(df)
    score, issues = diagnose(df)
    seg = STATE.get("seg")
    if seg is None:
        res = segment_customers(df)
        seg = res[1] if res else None
    pdf = build_pdf(k, score, health_label(score), issues, seg, STATE.get("recs"))
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=business_report.pdf"})


@app.post("/query")
def query(req: SQLRequest):
    _need_data()
    # SECURITY FIX: block anything except a single read-only SELECT
    if not _is_safe_select(req.sql):
        raise HTTPException(status_code=400, detail="Only a single read-only SELECT query is allowed.")
    try:
        return {"rows": _records(run_query(req.sql))}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))