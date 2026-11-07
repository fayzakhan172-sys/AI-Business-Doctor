import re

from src.database import run_query
from src.llm import ask_llm

SCHEMA = """
Table: sales (SQLite)
Columns: Row_ID, Order_ID, Date (text, format YYYY-MM-DD), Ship_Date, Ship_Mode,
Customer, Customer_Name, Segment, Country, City, State, Postal_Code, Region,
Product_ID, Category, Sub_Category, Product (product name), Sales, Quantity,
Discount, Profit, Year (integer), Month (text, format YYYY-MM), Profit_Margin_pct
"""

BLOCKED = ["insert", "update", "delete", "drop", "alter", "create", "attach", "pragma", "replace"]


def _clean_sql(text):
    """Remove markdown fences the model may add."""
    text = re.sub(r"```(?:sql)?", "", text, flags=re.IGNORECASE).replace("```", "")
    return text.strip().rstrip(";")


def _is_safe(sql):
    low = sql.lower()
    if not low.startswith("select"):
        return False
    if ";" in sql:  # no multiple statements
        return False
    return not any(re.search(rf"\b{w}\b", low) for w in BLOCKED)


def answer_question(question):
    """Returns (answer_text, sql, dataframe_or_None)."""
    sql_prompt = f"""You are a SQLite expert. Write ONE SQL SELECT query that answers the question.
{SCHEMA}
Rules: return only the SQL, no explanation, no markdown. Use only the columns above.
Limit results to 20 rows unless the question needs more.

Question: {question}"""

    sql = _clean_sql(ask_llm(sql_prompt))

    if not _is_safe(sql):
        return "I can only run read-only SELECT queries, so I could not answer that.", sql, None

    try:
        df = run_query(sql)
    except Exception as e:
        return f"The query failed: {e}. Make sure you clicked 'Save cleaned data to database' first.", sql, None

    if df.empty:
        return "The query returned no rows.", sql, df

    answer_prompt = f"""Question: {question}

SQL result (this is the real data):
{df.head(20).to_string(index=False)}

Answer the question in 2-4 simple sentences using ONLY the numbers above.
Do not invent any numbers. Use $ for money."""

    return ask_llm(answer_prompt), sql, df