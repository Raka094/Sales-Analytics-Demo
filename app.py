"""
Sales Analytics Demo: ABC segmentation, pricing opportunity and AI summary
on synthetic chemical sales data.

Run with:  streamlit run app.py
"""

import pandas as pd
import streamlit as st

import ai_summary
from analysis import abc_segmentation, abc_summary, opportunity_by, price_gap_analysis
from charts import (BAND_COLORS, margin_by_class_chart, opportunity_bar,
                    pareto_chart, price_scatter)
from styles import (AMBER, BLUE, CLASS_COLORS, NAVY, TEAL, apply_style, badge,
                    header, insight, kpi, section)

st.set_page_config(page_title="Sales Analytics Demo", page_icon="📊", layout="wide")
apply_style()

REQUIRED_COLUMNS = {
    "month", "customer_id", "region", "industry", "product_id",
    "product_family", "volume_kg", "net_price_eur_per_kg",
    "revenue_eur", "cost_eur",
}

# Cached versions of the analysis functions. Same inputs -> stored result,
# so moving a slider only recalculates what actually changed.
cached_abc = st.cache_data(abc_segmentation)
cached_prices = st.cache_data(price_gap_analysis)


@st.cache_data
def load_data(file) -> pd.DataFrame:
    """Read the CSV once and cache it (Streamlit reruns the script on every click)."""
    return pd.read_csv(file, parse_dates=["month"])


@st.cache_data(show_spinner="Writing summary...")
def cached_llm(facts_json: str, api_key: str) -> str:
    """Cache per set of facts: the same numbers never cost a second API call."""
    return ai_summary.llm_summary(facts_json, api_key)


def fmt_m(x: float) -> str:
    return f"€{x / 1e6:,.1f}M"


# =========================================================================
# Sidebar: data and filters
# =========================================================================
st.sidebar.header("Data")
# Rule: an uploaded file always wins. Without an upload, the sample data is used.
# (An earlier version had a "use sample" checkbox that stayed ticked after an
# upload, so uploaded files were silently ignored.)
uploaded = st.sidebar.file_uploader(
    "Upload sales CSV", type="csv",
    help="Remove the file (×) to go back to the sample data.")

with open("sales_data.csv", "rb") as f:
    st.sidebar.download_button(
        "Download sample CSV", f, file_name="sales_data_sample.csv",
        mime="text/csv", help="Use it as a template: your own file needs the same column names.")

source = uploaded.name if uploaded is not None else "sample data"
header("Sales Analytics Demo",
       "Customer segmentation and pricing analysis · "
       + (f"uploaded file: {source}" if uploaded is not None
          else "synthetic chemical sales data, FY2025"))

try:
    raw = load_data(uploaded if uploaded is not None else "sales_data.csv")
except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as e:
    # e.g. no 'month' column, not a real CSV, or an Excel file renamed to .csv
    st.error("Could not read the file. Please upload a comma-separated CSV saved as UTF-8 "
             "(in Excel: Save As → 'CSV UTF-8'). You can download the sample CSV in the "
             f"sidebar as a template. Details: {type(e).__name__}")
    st.stop()

st.sidebar.caption(f"Using: **{source}** ({len(raw):,} rows)")

missing = REQUIRED_COLUMNS - set(raw.columns)
if missing:
    st.error(f"The file is missing these columns: {', '.join(sorted(missing))}")
    st.stop()

# Basic sanity check: prices need positive volumes.
bad = (raw["volume_kg"] <= 0) | (raw["revenue_eur"] < 0)
if bad.any():
    st.warning(f"Removed {bad.sum():,} rows with zero/negative volume or negative revenue.")
    raw = raw[~bad]

st.sidebar.header("Filters")
st.sidebar.caption("Type or pick values. Leave a filter empty to include everything.")

# column -> (label, placeholder). Explicit plurals: "industries", not "industrys".
FILTERS = {
    "region": ("Region", "All regions"),
    "industry": ("Industry", "All industries"),
    "product_family": ("Product family", "All product families"),
}


def reset_filters() -> None:
    """Callback: runs before the rerun, so the boxes are empty when the page redraws."""
    for col in FILTERS:
        st.session_state[f"f_{col}"] = []


selected = {}
for col, (label, placeholder) in FILTERS.items():
    selected[col] = st.sidebar.multiselect(
        label,
        options=sorted(raw[col].unique()),
        placeholder=placeholder,          # starts empty = no filter = all values
        key=f"f_{col}",                   # key lets the reset button clear it
    )

st.sidebar.button("Reset filters", on_click=reset_filters,
                  disabled=not any(selected.values()))

# Empty selection means "all": only filter on columns where something is picked.
mask = pd.Series(True, index=raw.index)
for col, values in selected.items():
    if values:
        mask &= raw[col].isin(values)
df = raw[mask]

if df.empty:
    st.warning("No data for this filter combination. Try removing a filter.")
    st.stop()

filters = {col: values or "all" for col, values in selected.items()}
is_filtered = any(selected.values())

# =========================================================================
# Headline numbers
# =========================================================================
revenue = df["revenue_eur"].sum()
margin_pct = (1 - df["cost_eur"].sum() / revenue) * 100

c1, c2, c3, c4 = st.columns(4)
kpi(c1, "Revenue" + (" (filtered)" if is_filtered else ""), fmt_m(revenue), NAVY)
kpi(c2, "Gross margin", f"{margin_pct:.1f}%", BLUE)
kpi(c3, "Customers", f"{df['customer_id'].nunique():,}", TEAL)
kpi(c4, "Products", f"{df['product_id'].nunique():,}", AMBER)
if is_filtered:
    st.caption(f"Showing {revenue / raw['revenue_eur'].sum():.0%} of total revenue "
               "based on the sidebar filters.")

tab_seg, tab_price, tab_ai, tab_data = st.tabs(
    ["ABC segmentation", "Pricing opportunity", "AI summary", "Data"])

# =========================================================================
# Tab 1: ABC segmentation
# =========================================================================
with tab_seg:
    s1, s2, s3 = st.columns([1.2, 1, 1])
    level = s1.radio("Segment by", ["Customers", "Products"], horizontal=True)
    a_cut = s2.slider("Class A: top share of revenue", 0.50, 0.90, 0.80, 0.05)
    b_cut = s3.slider("Class A + B: top share of revenue", a_cut + 0.05, 0.99,
                      max(0.95, a_cut + 0.05), 0.01)
    key = "customer_id" if level == "Customers" else "product_id"

    seg = cached_abc(df, key=key, a_cut=a_cut, b_cut=b_cut)
    summary = abc_summary(seg)
    by_class = summary.set_index("abc_class")

    section(f"ABC segmentation of {level.lower()}")
    a, c = by_class.loc["A"], by_class.loc["C"]
    if pd.notna(c["margin_%"]) and a["margin_%"] < c["margin_%"]:
        insight(
            f"{badge('A')} <b>{a['count_share_%']:.0f}% of {level.lower()}</b> bring "
            f"<b>{a['revenue_share_%']:.0f}% of revenue</b>, but at the lowest gross margin "
            f"(<b>{a['margin_%']:.1f}%</b> vs {c['margin_%']:.1f}% in class C). "
            "Check whether their discounts are justified by volume: see <b>Pricing opportunity</b>.")
    else:
        insight(
            f"{badge('A')} <b>{a['count_share_%']:.0f}% of {level.lower()}</b> bring "
            f"<b>{a['revenue_share_%']:.0f}% of revenue</b> at a gross margin of "
            f"<b>{a['margin_%']:.1f}%</b>.")

    left, right = st.columns([3, 1])
    left.plotly_chart(pareto_chart(seg, a_cut, b_cut, level), width="stretch")
    right.plotly_chart(margin_by_class_chart(summary.dropna()), width="stretch")

    st.dataframe(
        summary, hide_index=True, width="stretch",
        column_config={
            "abc_class": "Class",
            "count": st.column_config.NumberColumn(level),
            "revenue_eur": st.column_config.NumberColumn("Revenue (€)", format="%,.0f"),
            "count_share_%": st.column_config.ProgressColumn(
                f"% of {level.lower()}", format="%.1f%%", min_value=0, max_value=100),
            "revenue_share_%": st.column_config.ProgressColumn(
                "% of revenue", format="%.1f%%", min_value=0, max_value=100),
            "margin_%": st.column_config.NumberColumn("Gross margin", format="%.1f%%"),
        },
    )

    with st.expander(f"All {level.lower()} with their class"):
        st.dataframe(
            seg[["rank", key, "abc_class", "revenue_eur", "revenue_share", "cum_share", "margin_pct"]],
            hide_index=True, width="stretch",
            column_config={
                "rank": "Rank", key: level[:-1], "abc_class": "Class",
                "revenue_eur": st.column_config.NumberColumn("Revenue (€)", format="%,.0f"),
                "revenue_share": st.column_config.NumberColumn("Share", format="percent"),
                "cum_share": st.column_config.NumberColumn("Cumulative", format="percent"),
                "margin_pct": st.column_config.NumberColumn("Margin", format="%.1f%%"),
            },
        )
        st.download_button("Download as CSV", seg.to_csv(index=False),
                           file_name=f"abc_{level.lower()}.csv", mime="text/csv")

# Pricing is always analysed per customer, so it needs the customer ABC class
# (independent of the Customers/Products toggle above).
cust_seg = cached_abc(df, key="customer_id", a_cut=a_cut, b_cut=b_cut)
cust_summary = abc_summary(cust_seg)

# =========================================================================
# Tab 2: Pricing opportunity
# =========================================================================
with tab_price:
    p1, p2 = st.columns(2)
    target_pct = p1.slider("Target price = this percentile of the peer group",
                           0.50, 0.90, 0.75, 0.05,
                           help="0.75 means: a quarter of comparable customers already pay this or more.")
    min_gap = p2.slider("Count only gaps larger than (% below target)", 0, 20, 5, 1,
                        help="Small gaps are normal price noise and not worth a negotiation.")

    cp = cached_prices(df, target_pct=target_pct, min_gap_pct=float(min_gap))
    cp = cp.merge(cust_seg[["customer_id", "abc_class"]], on="customer_id", how="left")

    total_opp = cp["opportunity_eur"].sum()
    hits = cp[cp["opportunity_eur"] > 0]
    opp_class = opportunity_by(cp, "abc_class")
    opp_region = opportunity_by(cp, "region")
    a_share = (opp_class.set_index("abc_class")["opportunity_eur"].get("A", 0)
               / total_opp * 100) if total_opp else 0

    section("Pricing opportunity")
    k1, k2, k3 = st.columns(3)
    kpi(k1, "Opportunity (upper bound)", fmt_m(total_opp), BLUE)
    kpi(k2, "Share of revenue", f"{total_opp / cp['revenue_eur'].sum() * 100:.1f}%", TEAL)
    kpi(k3, "Customers below target", f"{hits['customer_id'].nunique():,}", AMBER)

    insight(
        f"If customers priced more than {min_gap}% below their peers moved to the "
        f"{target_pct * 100:.0f}th percentile, revenue would rise by up to <b>{fmt_m(total_opp)}</b>. "
        f"{badge('A')} <b>{a_share:.0f}%</b> of this sits with class A customers: "
        "a few negotiations, not hundreds."
        if total_opp else
        "No customer is priced meaningfully below the target with these settings."
    )

    b1, b2 = st.columns(2)
    b1.plotly_chart(opportunity_bar(opp_class, "abc_class", "Opportunity by ABC class",
                                    CLASS_COLORS), width="stretch")
    b2.plotly_chart(opportunity_bar(opp_region, "region", "Opportunity by region"),
                    width="stretch")

    st.markdown("**Drill down: one product**")
    top_products = (cp.groupby("product_id")["opportunity_eur"].sum()
                    .sort_values(ascending=False).index.tolist())
    product = st.selectbox("Product (sorted by opportunity)", top_products)
    st.plotly_chart(price_scatter(cp[cp["product_id"] == product], product), width="stretch")
    st.caption("Peer groups: same product and similar yearly volume (Small / Medium / Large). "
               "Groups with fewer than 3 customers get no target.")

    st.markdown("**Largest individual gaps**")
    st.dataframe(
        hits.head(25)[["customer_id", "abc_class", "region", "product_id", "size_band",
                       "net_price", "target_price", "gap_pct", "opportunity_eur"]],
        hide_index=True, width="stretch",
        column_config={
            "customer_id": "Customer", "abc_class": "Class", "region": "Region",
            "product_id": "Product", "size_band": "Size",
            "net_price": st.column_config.NumberColumn("Net price (€/kg)", format="%.2f"),
            "target_price": st.column_config.NumberColumn("Target (€/kg)", format="%.2f"),
            "gap_pct": st.column_config.NumberColumn("Gap", format="%.1f%%"),
            "opportunity_eur": st.column_config.NumberColumn("Opportunity (€)", format="%,.0f"),
        },
    )
    st.download_button("Download all gaps as CSV", hits.to_csv(index=False),
                       file_name="pricing_gaps.csv", mime="text/csv")

    with st.expander("Limitations of this analysis"):
        st.markdown(
            "- **Upper bound, not a forecast.** Some customers will push back or reduce volume.\n"
            "- **Contracts and strategic deals** are not in the data. Some low prices are deliberate.\n"
            "- **Peer groups** use product and volume only. Region, contract length or service "
            "level could also justify price differences.")

# =========================================================================
# Tab 3: AI summary
# =========================================================================
with tab_ai:
    section("Summary for a manager")
    facts = ai_summary.build_facts(
        filters, cust_summary, cp, opp_class, opp_region,
        settings={"abc_cutoffs": [a_cut, b_cut], "target_percentile": target_pct,
                  "min_gap_pct": min_gap},
    )
    facts_json = ai_summary.to_json(facts)
    api_key = ai_summary.get_api_key()

    st.markdown(
        "Python calculates every number. The language model only turns the aggregated "
        "figures below into readable text. **No customer-level data is sent.**")

    if api_key:
        if st.button("Generate AI summary", type="primary"):
            try:
                st.session_state["ai_text"] = cached_llm(facts_json, api_key)
                st.session_state["ai_facts"] = facts_json
            except Exception as e:  # network, quota, wrong key...
                st.error(f"The AI call failed ({type(e).__name__}). Showing the template summary instead.")
                st.session_state.pop("ai_text", None)

        if "ai_text" in st.session_state:
            if st.session_state.get("ai_facts") != facts_json:
                st.info("Filters or settings changed since this summary. Generate it again.")
            with st.container(border=True):
                st.markdown(st.session_state["ai_text"])  # model writes markdown
            st.caption(f"Generated by {ai_summary.get_model()} via Groq. Check figures against the facts below.")
        else:
            st.markdown(ai_summary.template_summary(facts))
    else:
        st.info("No API key found, so this is a template summary. "
                "Add GROQ_API_KEY to .streamlit/secrets.toml to enable the AI version.")
        st.markdown(ai_summary.template_summary(facts))

    with st.expander("Facts sent to the model"):
        st.code(facts_json, language="json")

# =========================================================================
# Tab 4: Data
# =========================================================================
with tab_data:
    st.write(f"{len(df):,} rows, {df['month'].min():%b %Y} to {df['month'].max():%b %Y}")
    st.dataframe(df.head(500), width="stretch", hide_index=True,
                 column_config={"month": st.column_config.DateColumn("month", format="MMM YYYY")})
