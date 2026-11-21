import pandas as pd

CANDIDATES = {
    "Date":     ["order date", "date", "invoicedate", "order_date", "invoice date", "transaction date",
                 "sale date", "purchase date", "orderdate", "time", "datetime", "created at"],
    "Sales":    ["sales", "revenue", "amount", "total", "total sales", "total amount", "total_price",
                 "sale amount", "net sales", "turnover", "line total"],
    "Profit":   ["profit", "net profit", "gain"],
    "Customer": ["customer id", "customer_id", "customerid", "customer", "client id", "user id", "cust id"],
    "Order":    ["order id", "order_id", "invoiceno", "invoice", "invoice no", "transaction id",
                 "order number", "orderid", "bill no"],
    "Category": ["category", "product category", "department", "type", "segment"],
    "Product":  ["product name", "product", "sub-category", "item", "item name", "description", "sku"],
    "Discount": ["discount", "discount %", "discount_rate"],
}


def _add_sales_if_missing(df):
    """If there is no sales/amount column but Quantity and Price exist, create Sales = Quantity * Price."""
    lower = {c.lower().strip(): c for c in df.columns}
    if any(opt in lower for opt in CANDIDATES["Sales"]):
        return df

    qty = next((lower[n] for n in ("quantity", "qty", "quantityordered") if n in lower), None)
    price = next((lower[n] for n in ("price", "unitprice", "unit price", "unit_price", "priceeach")
                  if n in lower), None)
    if qty and price:
        df = df.copy()
        q = pd.to_numeric(df[qty], errors="coerce")
        p = pd.to_numeric(df[price], errors="coerce")
        df["Sales"] = q * p
        df = df[(q > 0) & (p > 0)]  # drop returns / cancellations
    return df


def load_file(file):
    name = getattr(file, "name", str(file)).lower()
    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(file)
        return _add_sales_if_missing(df)

    df = None
    for enc in ("utf-8", "latin1", "cp1252"):
        try:
            if hasattr(file, "seek"):
                file.seek(0)
            df = pd.read_csv(file, encoding=enc)  # fast reader first
            if df.shape[1] == 1:  # wrong separator, let pandas detect it
                if hasattr(file, "seek"):
                    file.seek(0)
                df = pd.read_csv(file, encoding=enc, sep=None, engine="python")
            break
        except UnicodeDecodeError:
            continue
    if df is None:
        raise ValueError("Could not read this file. Please check the format.")
    return _add_sales_if_missing(df)


def detect_columns(df):
    lower = {c.lower().strip(): c for c in df.columns}
    mapping = {}
    used = set()
    for role, options in CANDIDATES.items():
        for opt in options:
            if opt in lower and lower[opt] not in used:
                mapping[role] = lower[opt]
                used.add(lower[opt])
                break

    # Fallback: find a date-like column by trying to parse it
    if "Date" not in mapping:
        for c in df.columns:
            if c in used or df[c].dtype != object:
                continue
            parsed = pd.to_datetime(df[c].head(50), errors="coerce")
            if parsed.notna().mean() > 0.8:
                mapping["Date"] = c
                used.add(c)
                break

    # Fallback: first numeric column for Sales (user can change it in the sidebar)
    if "Sales" not in mapping:
        for c in df.select_dtypes("number").columns:
            if c not in used:
                mapping["Sales"] = c
                used.add(c)
                break
    return mapping


def clean_data(df, mapping):
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    df = df.rename(columns={v: k for k, v in mapping.items()})
    df = df.loc[:, ~df.columns.duplicated()]
    df = df.drop_duplicates()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", format="mixed")
    for col in ["Sales", "Profit", "Discount"]:
        if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce"
            )

    df = df.dropna(subset=["Date", "Sales"])
    if df.empty:
        raise ValueError("No valid rows after cleaning. Check the Date and Sales column mapping.")

    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    if "Profit" in df.columns:
        df["Profit Margin %"] = (df["Profit"] / df["Sales"].replace(0, pd.NA) * 100).astype(float).round(2)

    return df.reset_index(drop=True)