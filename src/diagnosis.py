def _issue(severity, title, detail, penalty):
    return {"severity": severity, "title": title, "detail": detail, "penalty": penalty}


def _group_column(df):
    for col in ["Sub-Category", "Category", "Product"]:
        if col in df.columns:
            return col
    return None


def diagnose(df):
    """Return (health_score, issues). Score starts at 100, each issue deducts points."""
    issues = []

    # 1. Overall profit margin
    if "Profit" in df.columns:
        margin = df["Profit"].sum() / df["Sales"].sum() * 100
        if margin < 0:
            issues.append(_issue("critical", "Business is losing money",
                                 f"Overall profit margin is {margin:.1f}%.", 30))
        elif margin < 8:
            issues.append(_issue("warning", "Low profit margin",
                                 f"Overall profit margin is only {margin:.1f}%.", 15))

    # 2. Loss-making groups
    group_col = _group_column(df)
    if group_col and "Profit" in df.columns:
        profit_by = df.groupby(group_col)["Profit"].sum()
        losers = profit_by[profit_by < 0].sort_values()
        if len(losers) > 0:
            names = ", ".join(f"{n} (\\${v:,.0f})" for n, v in losers.head(5).items())
            issues.append(_issue("critical", f"{len(losers)} loss-making {group_col}(s)",
                                 f"These lose money: {names}.", min(25, 8 * len(losers))))

    # 3. Heavy discounts
    if "Discount" in df.columns and "Profit" in df.columns:
        heavy = df[df["Discount"] >= 0.3]
        if len(heavy) > 0 and heavy["Profit"].sum() < 0:
            share = len(heavy) / len(df) * 100
            issues.append(_issue("warning", "Heavy discounts are destroying profit",
                                 f"{share:.0f}% of orders have 30%+ discount and lose "
                                 f"${abs(heavy['Profit'].sum()):,.0f} in total.", 15))

    # 4. Declining trend (last 3 months vs previous 3)
    monthly = df.groupby("Month")["Sales"].sum()
    if len(monthly) >= 6:
        recent = monthly.iloc[-3:].mean()
        previous = monthly.iloc[-6:-3].mean()
        change = (recent - previous) / previous * 100
        if change < -10:
            issues.append(_issue("critical", "Sales are declining",
                                 f"Average monthly sales fell {abs(change):.1f}% in the last 3 months.", 20))
        elif change < 0:
            issues.append(_issue("warning", "Sales are slightly down",
                                 f"Average monthly sales fell {abs(change):.1f}% in the last 3 months.", 8))

    score = max(0, 100 - sum(i["penalty"] for i in issues))
    return score, issues


def health_label(score):
    if score >= 80:
        return "Healthy"
    if score >= 60:
        return "Needs attention"
    return "Critical"