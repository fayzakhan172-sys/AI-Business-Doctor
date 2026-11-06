import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

ACTIONS = {
    "Champions": "Reward them: loyalty perks, early access to new products, referral offers.",
    "Loyal": "Keep them engaged: upsell and cross-sell, membership or points program.",
    "At-Risk": "Win them back: personalised discount or reminder email before they churn.",
    "Lost": "Low-cost reactivation only: one 'we miss you' campaign, then stop spending on them.",
}


def build_rfm(df):
    """One row per customer: Recency, Frequency, Monetary."""
    snapshot = df["Date"].max() + pd.Timedelta(days=1)
    return df.groupby("Customer").agg(
        Recency=("Date", lambda x: (snapshot - x.max()).days),
        Frequency=("Order", "nunique"),
        Monetary=("Sales", "sum"),
    )


def _name_clusters(summary):
    """Give each cluster a business name by ranking, so it never depends on cluster numbers."""
    names = {}
    remaining = list(summary.index)

    # Champions: highest spend
    champ = summary.loc[remaining, "Monetary"].idxmax()
    names[champ] = "Champions"
    remaining.remove(champ)

    # Lost: lowest spend
    lost = summary.loc[remaining, "Monetary"].idxmin()
    names[lost] = "Lost"
    remaining.remove(lost)

    # Of the rest: most recent = Loyal, other = At-Risk
    loyal = summary.loc[remaining, "Recency"].idxmin()
    names[loyal] = "Loyal"
    remaining.remove(loyal)

    for c in remaining:
        names[c] = "At-Risk"
    return names


def segment_customers(df, k=4):
    """Returns (rfm_with_segment, segment_summary) or None if data is not enough."""
    if "Customer" not in df.columns or "Order" not in df.columns:
        return None

    rfm = build_rfm(df)
    if len(rfm) < 20:
        return None

    X = StandardScaler().fit_transform(np.log1p(rfm))
    rfm["Cluster"] = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(X)

    summary = rfm.groupby("Cluster").agg(
        Customers=("Monetary", "size"),
        Recency=("Recency", "mean"),
        Frequency=("Frequency", "mean"),
        Monetary=("Monetary", "mean"),
    )
    names = _name_clusters(summary)
    rfm["Segment"] = rfm["Cluster"].map(names)

    seg = rfm.groupby("Segment").agg(
        Customers=("Monetary", "size"),
        Recency=("Recency", "mean"),
        Frequency=("Frequency", "mean"),
        Monetary=("Monetary", "mean"),
        TotalRevenue=("Monetary", "sum"),
    ).round(1)
    seg["Suggested action"] = seg.index.map(ACTIONS)
    return rfm, seg