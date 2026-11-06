"""
AI manager summary, using Groq's free API tier.

Design rules (these are your interview answers for Q22-Q25):
1. Python calculates every number. The LLM only writes text around them.
2. Only aggregated figures are sent to the model, never raw customer rows.
3. The prompt tells the model to use only the given facts, and the
   facts are shown on screen so anyone can check the summary.
4. Without an API key the app still works, using a plain template.

Why Groq: a free tier with no payment card, fast responses, and open-weight
models. The provider is isolated in this file: switching to another LLM
(Anthropic, Azure OpenAI, a company-internal endpoint) only changes
get_api_key() and llm_summary().
"""

import json
import os

# Default model on Groq's free tier. Free model lists change, so it can be
# overridden with GROQ_MODEL in secrets without touching the code.
DEFAULT_MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """You are an analyst in an in-house management consulting team.
Write a short summary for a business unit manager.

Rules:
- Use ONLY the numbers in the facts JSON. Never invent or estimate numbers.
- If something is not in the facts, do not mention it.
- Plain business English, no jargon, no hype.
- Format: a one-sentence headline in bold, then 3-4 bullet points,
  then one line starting with "Recommended next step:".
- Mention that the pricing opportunity is an upper bound, not a forecast."""


def build_facts(filters, summary, cp, opp_class, opp_region, settings) -> dict:
    """Collect the aggregated numbers the model is allowed to use."""
    by_class = summary.set_index("abc_class")
    return {
        "scope_filters": filters,
        "settings": settings,
        "abc_segmentation": {
            cls: {
                "share_of_customers_pct": round(float(by_class.loc[cls, "count_share_%"]), 1),
                "share_of_revenue_pct": round(float(by_class.loc[cls, "revenue_share_%"]), 1),
                "gross_margin_pct": round(float(by_class.loc[cls, "margin_%"]), 1),
            }
            for cls in by_class.index if by_class.loc[cls, "count"] > 0
        },
        "pricing_opportunity": {
            "total_eur_m": round(cp["opportunity_eur"].sum() / 1e6, 2),
            "pct_of_revenue": round(cp["opportunity_eur"].sum() / cp["revenue_eur"].sum() * 100, 1),
            "customers_below_target": int(cp.loc[cp["opportunity_eur"] > 0, "customer_id"].nunique()),
            "by_abc_class_eur_m": {
                str(r.abc_class): round(r.opportunity_eur / 1e6, 2) for r in opp_class.itertuples()
            },
            "top_regions_eur_m": {
                str(r.region): round(r.opportunity_eur / 1e6, 2) for r in opp_region.head(3).itertuples()
            },
        },
    }


def _secret(name: str):
    """Read a value from Streamlit secrets first, then environment variables."""
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass  # no secrets file: that is fine
    return os.environ.get(name)


def get_api_key():
    return _secret("GROQ_API_KEY")


def get_model() -> str:
    return _secret("GROQ_MODEL") or DEFAULT_MODEL


def llm_summary(facts_json: str, api_key: str) -> str:
    """Ask the model for a summary. facts_json is a string so it can be cached."""
    from groq import Groq

    model = get_model()
    extra = {}
    if model.startswith("openai/gpt-oss"):
        # gpt-oss "thinks" before answering. Low effort is enough for a
        # short summary, and the thinking text is not returned to us.
        extra = {"reasoning_effort": "low", "include_reasoning": False}

    client = Groq(api_key=api_key, timeout=30)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Facts:\n{facts_json}"},
        ],
        temperature=0.2,              # low = consistent, factual wording
        max_completion_tokens=1500,   # includes the model's thinking tokens
        **extra,
    )
    text = response.choices[0].message.content or ""
    if not text.strip():
        raise ValueError("The model returned an empty answer.")
    return text


def template_summary(facts: dict) -> str:
    """Fallback without an LLM: the same facts in a fixed sentence structure."""
    abc = facts["abc_segmentation"]
    p = facts["pricing_opportunity"]
    a, c = abc.get("A", {}), abc.get("C", {})
    biggest_class = max(p["by_abc_class_eur_m"], key=p["by_abc_class_eur_m"].get)
    top_region = next(iter(p["top_regions_eur_m"]), "n/a")
    return (
        f"**Class A customers ({a.get('share_of_customers_pct')}% of customers) bring "
        f"{a.get('share_of_revenue_pct')}% of revenue at {a.get('gross_margin_pct')}% gross margin.**\n\n"
        + (f"- Class C margin is {c.get('gross_margin_pct')}%, so the largest customers are the least profitable per euro.\n"
           if a and c and a["gross_margin_pct"] < c["gross_margin_pct"]
           else f"- Class C margin is {c.get('gross_margin_pct')}%.\n")
        + 
        f"- Pricing opportunity (upper bound): €{p['total_eur_m']}M, {p['pct_of_revenue']}% of revenue, "
        f"across {p['customers_below_target']} customers.\n"
        f"- Class {biggest_class} holds the largest share of the opportunity; {top_region} is the top region.\n\n"
        "Recommended next step: review discount terms of the largest class A gaps with the sales team."
    )


def to_json(facts: dict) -> str:
    return json.dumps(facts, indent=2, ensure_ascii=False)
