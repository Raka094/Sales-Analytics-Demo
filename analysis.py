"""
Analysis functions, kept separate from the Streamlit page.

Why a separate file: the logic can be tested without the UI,
and the same functions could be reused in a notebook or another app.
"""

import pandas as pd


def abc_segmentation(
    df: pd.DataFrame,
    key: str = "customer_id",
    a_cut: float = 0.80,
    b_cut: float = 0.95,
) -> pd.DataFrame:
    """Classify each customer (or product) as A, B or C by revenue.

    A = the top items that together make up the first `a_cut` of revenue
    B = the next items, up to `b_cut`
    C = the rest (the long tail)
    """
    # 1. One row per customer: revenue, cost, volume.
    agg = (
        df.groupby(key, as_index=False)
        .agg(revenue_eur=("revenue_eur", "sum"),
             cost_eur=("cost_eur", "sum"),
             volume_kg=("volume_kg", "sum"))
        .sort_values("revenue_eur", ascending=False)
        .reset_index(drop=True)
    )

    # 2. Each customer's share, and the running (cumulative) share.
    total = agg["revenue_eur"].sum()
    agg["revenue_share"] = agg["revenue_eur"] / total
    agg["cum_share"] = agg["revenue_share"].cumsum()

    # 3. Classify on the share BEFORE this customer is added.
    #    Why: the customer that crosses the 80% line still belongs to A.
    #    Using cum_share directly would push it into B.
    share_before = agg["cum_share"] - agg["revenue_share"]
    agg["abc_class"] = "C"
    agg.loc[share_before < b_cut, "abc_class"] = "B"
    agg.loc[share_before < a_cut, "abc_class"] = "A"

    # 4. Margin per customer: revenue alone hides profitability.
    agg["margin_pct"] = (1 - agg["cost_eur"] / agg["revenue_eur"]) * 100
    agg["rank"] = agg.index + 1
    return agg


def abc_summary(seg: pd.DataFrame) -> pd.DataFrame:
    """One row per class: how many customers, how much revenue, what margin."""
    s = (
        seg.groupby("abc_class")
        .agg(count=("abc_class", "size"),
             revenue_eur=("revenue_eur", "sum"),
             cost_eur=("cost_eur", "sum"))
        .reindex(["A", "B", "C"])
    )
    s["count_share_%"] = s["count"] / s["count"].sum() * 100
    s["revenue_share_%"] = s["revenue_eur"] / s["revenue_eur"].sum() * 100
    # Margin from summed revenue and cost, NOT the average of customer margins.
    # Averaging percentages would give a small customer the same weight as a big one.
    s["margin_%"] = (1 - s["cost_eur"] / s["revenue_eur"]) * 100
    return s.drop(columns="cost_eur").reset_index()


SIZE_BANDS = ["Small", "Medium", "Large"]


def price_gap_analysis(df: pd.DataFrame, target_pct: float = 0.75,
                       min_gap_pct: float = 5.0) -> pd.DataFrame:
    """Find customers who pay less than comparable peers for the same product.

    Steps:
    1. Net price per customer and product = revenue / volume
       (volume-weighted, so one small order does not distort it).
    2. Peer group = same product + similar size (Small / Medium / Large by
       yearly volume of that product). Big buyers deserve lower prices,
       so comparing them with small buyers would be unfair.
    3. Target price = the chosen percentile of prices in the peer group
       (e.g. 75th: a quarter of peers already pay this or more).
    4. Opportunity = (target - actual price) x volume, only where the price
       is more than `min_gap_pct` below target. Small gaps are normal noise:
       by definition ~75% of any group sits below its own 75th percentile,
       so counting every small gap would overstate the opportunity.
    """
    cp = (
        df.groupby(["customer_id", "product_id", "product_family", "region", "industry"],
                   as_index=False)
        .agg(volume_kg=("volume_kg", "sum"), revenue_eur=("revenue_eur", "sum"))
    )
    cp["net_price"] = cp["revenue_eur"] / cp["volume_kg"]

    # Size band within each product, by percentile rank of volume.
    # rank(pct=True) works even when a product has only a few buyers.
    pct_rank = cp.groupby("product_id")["volume_kg"].rank(pct=True)
    cp["size_band"] = pd.cut(pct_rank, [0, 1 / 3, 2 / 3, 1.0], labels=SIZE_BANDS)

    group = cp.groupby(["product_id", "size_band"], observed=True)
    cp["peers"] = group["net_price"].transform("size")
    cp["peer_median"] = group["net_price"].transform("median")
    cp["target_price"] = group["net_price"].transform(lambda s: s.quantile(target_pct))

    # A peer group of 1-2 customers is not a fair comparison: no target.
    small = cp["peers"] < 3
    cp.loc[small, ["peer_median", "target_price"]] = float("nan")

    cp["gap_pct"] = (cp["net_price"] / cp["target_price"] - 1) * 100
    meaningful = cp["gap_pct"] <= -min_gap_pct
    cp["opportunity_eur"] = (
        (cp["target_price"] - cp["net_price"]).clip(lower=0) * cp["volume_kg"]
    ).where(meaningful, 0).fillna(0)
    return cp.sort_values("opportunity_eur", ascending=False).reset_index(drop=True)


def opportunity_by(cp: pd.DataFrame, col: str) -> pd.DataFrame:
    """Total pricing opportunity per group, as € and as % of that group's revenue."""
    out = (
        cp.groupby(col, as_index=False, observed=True)
        .agg(opportunity_eur=("opportunity_eur", "sum"), revenue_eur=("revenue_eur", "sum"))
    )
    out["opportunity_%_of_revenue"] = out["opportunity_eur"] / out["revenue_eur"] * 100
    return out.sort_values("opportunity_eur", ascending=False)
