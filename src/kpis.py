def compute_kpis(df):
    k = {
        "Total Sales": df["Sales"].sum(),
        "Rows": len(df),
    }
    if "Profit" in df.columns:
        k["Total Profit"] = df["Profit"].sum()
        k["Profit Margin %"] = k["Total Profit"] / k["Total Sales"] * 100
    if "Order" in df.columns:
        k["Orders"] = df["Order"].nunique()
        k["Avg Order Value"] = k["Total Sales"] / k["Orders"]
    if "Customer" in df.columns:
        k["Customers"] = df["Customer"].nunique()
    return k


def monthly_trend(df):
    cols = [c for c in ["Sales", "Profit"] if c in df.columns]
    return df.groupby("Month")[cols].sum().reset_index()


def group_summary(df, by):
    cols = [c for c in ["Sales", "Profit"] if c in df.columns]
    return df.groupby(by)[cols].sum().reset_index()