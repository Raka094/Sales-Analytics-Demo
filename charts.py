"""Plotly charts, styled to match the app palette."""

import plotly.graph_objects as go

from styles import AMBER, BLUE, CLASS_COLORS, LIGHT, NAVY, TEAL

FONT = dict(family="Segoe UI, Helvetica, Arial, sans-serif", color=NAVY, size=12)


def pareto_chart(seg, a_cut: float, b_cut: float, level: str) -> go.Figure:
    """Pareto curve: % of customers (x) against % of revenue (y).

    Each class is a shaded zone under the curve. The steeper the start,
    the more revenue is concentrated in a few customers.
    """
    n = len(seg)
    x = seg["rank"] / n * 100          # cumulative % of customers
    y = seg["cum_share"] * 100         # cumulative % of revenue

    fig = go.Figure()

    # One filled zone per class. Each zone starts at the last point of the
    # previous one, so the shaded areas join without gaps.
    start = 0
    for cls, color in CLASS_COLORS.items():
        idx = seg.index[seg["abc_class"] == cls]
        if len(idx) == 0:
            continue
        lo, hi = max(idx.min() - 1, 0), idx.max()
        xs = ([0] if start == 0 else []) + list(x.loc[lo:hi])
        ys = ([0] if start == 0 else []) + list(y.loc[lo:hi])
        fig.add_scatter(
            x=xs, y=ys, mode="lines", fill="tozeroy", name=f"Class {cls}",
            line=dict(color=color, width=0), fillcolor=color, opacity=0.85,
            hoverinfo="skip",
        )
        start = 1

    # The curve itself, on top, carries the hover.
    fig.add_scatter(
        x=[0, *x], y=[0, *y], mode="lines", name="Cumulative revenue",
        line=dict(color=NAVY, width=2.5),
        customdata=[0, *seg["rank"]],
        hovertemplate="Top %{customdata} (%{x:.0f}% of " + level.lower()
                      + ") → %{y:.1f}% of revenue<extra></extra>",
    )

    # Mark where class A ends: the single number a manager remembers.
    a_end = seg[seg["abc_class"] == "A"]
    if len(a_end):
        ax, ay = x.loc[a_end.index.max()], y.loc[a_end.index.max()]
        fig.add_scatter(x=[ax], y=[ay], mode="markers", showlegend=False,
                        marker=dict(color="white", size=10, line=dict(color=NAVY, width=2.5)),
                        hoverinfo="skip")
        fig.add_annotation(
            x=ax, y=ay, ax=40, ay=40, showarrow=True, arrowcolor=NAVY, arrowwidth=1.2,
            text=f"<b>{ax:.0f}% of {level.lower()}</b><br>= {ay:.0f}% of revenue",
            font=dict(color=NAVY, size=12), bgcolor="white", bordercolor=NAVY,
            borderwidth=1, borderpad=4,
        )

    fig.update_layout(
        font=FONT, height=420, plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(title_text=f"% of {level.lower()} (highest revenue first)",
                     range=[0, 100], ticksuffix="%", gridcolor=LIGHT, zeroline=False)
    fig.update_yaxes(title_text="% of revenue", range=[0, 102], ticksuffix="%",
                     tickvals=[0, 20, 40, 60, 80, 100], gridcolor=LIGHT, zeroline=False)
    return fig


def margin_by_class_chart(summary) -> go.Figure:
    """Gross margin per class: shows the discount effect at a glance."""
    fig = go.Figure(go.Bar(
        x=summary["abc_class"], y=summary["margin_%"],
        marker_color=[CLASS_COLORS[c] for c in summary["abc_class"]],
        text=[f"{v:.1f}%" for v in summary["margin_%"]], textposition="outside",
        hovertemplate="Class %{x}: %{y:.1f}% margin<extra></extra>",
    ))
    top = summary["margin_%"].max()
    fig.update_layout(
        font=FONT, height=420, plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=10, r=10, t=30, b=10), showlegend=False,
        title=dict(text="Gross margin by class", font=dict(size=14, color=NAVY)),
    )
    fig.update_xaxes(title_text="Class", showgrid=False)
    fig.update_yaxes(title_text="Gross margin (%)", range=[0, top * 1.2], gridcolor=LIGHT)
    return fig


BAND_COLORS = {"Small": AMBER, "Medium": TEAL, "Large": BLUE}


def opportunity_bar(opp, col: str, title: str, colors=None) -> go.Figure:
    """Horizontal bars: pricing opportunity in €M per group, largest on top."""
    opp = opp.sort_values("opportunity_eur")
    color = [colors.get(str(v), BLUE) for v in opp[col]] if colors else BLUE
    fig = go.Figure(go.Bar(
        y=opp[col].astype(str), x=opp["opportunity_eur"] / 1e6, orientation="h",
        marker_color=color,
        text=[f"€{v / 1e6:.1f}M · {p:.1f}% of rev."
              for v, p in zip(opp["opportunity_eur"], opp["opportunity_%_of_revenue"])],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: €%{x:.2f}M<extra></extra>",
    ))
    fig.update_layout(
        font=FONT, height=320, plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=10, r=110, t=40, b=10), showlegend=False,
        title=dict(text=title, font=dict(size=14, color=NAVY)),
    )
    fig.update_xaxes(title_text="Opportunity (€M)", gridcolor=LIGHT, zeroline=False)
    fig.update_yaxes(showgrid=False)
    return fig


def price_scatter(cp_product, product_id: str) -> go.Figure:
    """One product: each dot is a customer. Dashed line = target price per size band.

    Dots below their band's line are paying less than comparable peers.
    """
    fig = go.Figure()
    for band, color in BAND_COLORS.items():
        part = cp_product[cp_product["size_band"] == band]
        if part.empty:
            continue
        fig.add_scatter(
            x=part["volume_kg"] / 1000, y=part["net_price"], mode="markers", name=band,
            marker=dict(color=color, size=10, opacity=0.85, line=dict(color="white", width=1)),
            customdata=part[["customer_id", "gap_pct", "opportunity_eur"]],
            hovertemplate=("%{customdata[0]}<br>Volume %{x:.0f} t · €%{y:.2f}/kg"
                           "<br>vs target %{customdata[1]:.1f}%"
                           "<br>Opportunity €%{customdata[2]:,.0f}<extra>" + band + "</extra>"),
        )
        target = part["target_price"].dropna()
        if not target.empty:
            fig.add_scatter(
                x=[part["volume_kg"].min() / 1000, part["volume_kg"].max() / 1000],
                y=[target.iloc[0]] * 2, mode="lines", showlegend=False,
                line=dict(color=color, dash="dash", width=2), hoverinfo="skip",
            )
    fig.update_layout(
        font=FONT, height=380, plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text="Customer size: "),
        title=dict(text=f"{product_id}: net price vs yearly volume (dashed = target price)",
                   font=dict(size=14, color=NAVY), x=1, xanchor="right"),
    )
    fig.update_xaxes(title_text="Yearly volume (tonnes, log scale)", type="log", gridcolor=LIGHT)
    fig.update_yaxes(title_text="Net price (€/kg)", gridcolor=LIGHT)
    return fig
