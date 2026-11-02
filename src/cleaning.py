import pandas as pd

CANDIDATES = {
    "Date":     ["order date", "date", "invoicedate", "order_date"],
    "Sales":    ["sales", "revenue", "amount", "total"],
    "Profit":   ["profit"],
    "Customer": ["customer id", "customer_id", "customerid"],
    "Order":    ["order id", "order_id", "invoiceno", "invoice"],
    "Category": ["category"],
    "Product":  ["product name", "product", "sub-category"],
    "Discount": ["discount"],
}


def load_file(file):
    name = getattr(file, "name", str(file)).lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(file)
    try:
        return pd.read_csv(file)
    except UnicodeDecodeError:
        if hasattr(file, "seek"):
            file.seek(0)
        return pd.read_csv(file, encoding="latin1")


def detect_columns(df):
    lower = {c.lower().strip(): c for c in df.columns}
    mapping = {}
    for role, options in CANDIDATES.items():
        for opt in options:
            if opt in lower:
                mapping[role] = lower[opt]
                break
    return mapping


def clean_data(df, mapping):
    df = df.copy()
    df.columns = df.columns.str.strip()
    df = df.rename(columns={v: k for k, v in mapping.items()})
    df = df.drop_duplicates()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in ["Sales", "Profit", "Discount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Date", "Sales"])

    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    if "Profit" in df.columns:
        df["Profit Margin %"] = (df["Profit"] / df["Sales"] * 100).round(2)

    return df.reset_index(drop=True)