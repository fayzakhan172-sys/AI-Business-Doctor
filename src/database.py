from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "business.db"
engine = create_engine(f"sqlite:///{DB_PATH}")


def save_to_db(df, table="sales"):
    """Save the cleaned dataframe into the database (replaces the old table)."""
    out = df.copy()
    out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")
    out.columns = [c.replace(" ", "_").replace("-", "_").replace("%", "pct") for c in out.columns]
    out.to_sql(table, engine, if_exists="replace", index=False)
    return len(out)


def run_query(sql):
    """Run a read-only SELECT query and return a dataframe."""
    cleaned = sql.strip().rstrip(";")
    if not cleaned.lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")
    with engine.connect() as conn:
        return pd.read_sql(text(cleaned), conn)