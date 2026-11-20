from io import BytesIO
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def _clean(text):
    """Escape characters that break reportlab paragraphs."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_pdf(kpis, score, label, issues, seg, recommendations=None):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Business Doctor Report")
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("AI Business Doctor - Report", styles["Title"]))
    story.append(Paragraph(f"Generated on {date.today():%d %b %Y}", styles["Normal"]))
    story.append(Spacer(1, 14))

    story.append(Paragraph(f"Business Health Score: {score}/100 ({label})", styles["Heading2"]))
    story.append(Spacer(1, 6))

    # KPI table
    story.append(Paragraph("Key Metrics", styles["Heading2"]))
    rows = [["Metric", "Value"]]
    for name, val in kpis.items():
        if "%" in name:
            rows.append([name, f"{val:.2f}%"])
        elif name in ("Rows", "Orders", "Customers"):
            rows.append([name, f"{val:,}"])
        else:
            rows.append([name, f"${val:,.0f}"])
    table = Table(rows, hAlign="LEFT", colWidths=[200, 150])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(table)
    story.append(Spacer(1, 14))

    # Problems
    story.append(Paragraph("Problems Detected", styles["Heading2"]))
    if issues:
        for i in issues:
            story.append(Paragraph(f"<b>{_clean(i['title'])}</b>: {_clean(i['detail'])}", styles["Normal"]))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("No major problems detected.", styles["Normal"]))
    story.append(Spacer(1, 10))

    # Segments
    if seg is not None:
        story.append(Paragraph("Customer Segments", styles["Heading2"]))
        for name, row in seg.iterrows():
            story.append(Paragraph(
                f"<b>{_clean(name)}</b>: {int(row['Customers'])} customers, "
                f"avg spend ${row['Monetary']:,.0f}. {_clean(row['Suggested action'])}",
                styles["Normal"],
            ))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 10))

    # Recommendations (optional)
    if recommendations:
        story.append(Paragraph("AI Recommendations", styles["Heading2"]))
        for line in recommendations.split("\n"):
            if line.strip():
                story.append(Paragraph(_clean(line.replace("**", "")), styles["Normal"]))
                story.append(Spacer(1, 3))

    doc.build(story)
    return buf.getvalue()