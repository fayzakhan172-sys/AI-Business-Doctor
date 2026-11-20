from src.llm import ask_llm


def build_summary(kpis, score, issues, forecast, seg):
    """Turn analysis results into plain text for the LLM."""
    lines = [f"Health score: {score}/100"]
    lines.append("KPIs: " + ", ".join(
        f"{k}={v:,.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in kpis.items()
    ))

    if issues:
        lines.append("Problems found:")
        for i in issues:
            lines.append(f"- {i['title']}: {i['detail']}")

    if forecast is not None:
        future = forecast["future"]
        lines.append(
            f"Forecast next {len(future)} months: average ${future['Forecast'].mean():,.0f} per month "
            f"(model: {forecast['model_used']})."
        )

    if seg is not None:
        lines.append("Customer segments:")
        for name, row in seg.iterrows():
            lines.append(
                f"- {name}: {int(row['Customers'])} customers, "
                f"avg spend ${row['Monetary']:,.0f}, avg days since last order {row['Recency']:.0f}"
            )
    return "\n".join(lines)


def get_recommendations(summary):
    prompt = f"""You are a business consultant. Based ONLY on this analysis, give exactly 5
actionable recommendations, most important first. For each: one bold title, then 1-2 sentences
explaining what to do and why, using the numbers given. Do not invent numbers.

{summary}"""
    return ask_llm(prompt)