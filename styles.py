"""
Visual style: one palette and a small amount of CSS, kept in one place.

Why a separate file: if the look needs to change (for example, to match
a client's brand), only this file changes, not the analysis code.
"""

import streamlit as st

# Corporate palette: a deep blue base with three clear, distinct accents.
NAVY = "#0B2545"
BLUE = "#1F5AA6"
TEAL = "#0E9AA7"
AMBER = "#E8A33D"
GREY = "#6B7A8C"
LIGHT = "#E6ECF2"

# One colour per ABC class, used everywhere (tables, chart, text),
# so the reader learns the colour once.
CLASS_COLORS = {"A": BLUE, "B": TEAL, "C": AMBER}

CSS = f"""
<style>
/* Header band */
.app-header {{
    background: linear-gradient(90deg, {NAVY} 0%, {BLUE} 100%);
    color: white;
    padding: 1.4rem 1.8rem;
    border-radius: 12px;
    margin-bottom: 1.4rem;
}}
.app-header h1 {{ color: white; font-size: 1.9rem; margin: 0; padding: 0; }}
.app-header p  {{ color: #C9D6E6; margin: 0.3rem 0 0 0; font-size: 0.95rem; }}

/* KPI cards */
.kpi {{
    background: white;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    border-left: 5px solid var(--accent);
    box-shadow: 0 1px 3px rgba(11, 37, 69, 0.08);
}}
.kpi .label {{ color: {GREY}; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; }}
.kpi .value {{ color: {NAVY}; font-size: 1.7rem; font-weight: 700; margin-top: 0.2rem; }}

/* Section titles with a short coloured underline */
.section {{
    color: {NAVY};
    font-size: 1.25rem;
    font-weight: 700;
    margin: 1.6rem 0 0.6rem 0;
    padding-bottom: 0.3rem;
    border-bottom: 3px solid {TEAL};
    display: inline-block;
}}

/* Insight box: the "so what" sentence */
.insight {{
    background: #EAF3FB;
    border-left: 5px solid {BLUE};
    border-radius: 8px;
    padding: 0.9rem 1.1rem;
    color: {NAVY};
    margin: 0.8rem 0 1rem 0;
}}

/* Class badges (A / B / C) */
.badge {{
    display: inline-block; color: white; font-weight: 700;
    border-radius: 6px; padding: 0.05rem 0.5rem; margin-right: 0.3rem;
}}

/* Tabs: larger labels and a coloured active tab */
button[data-baseweb="tab"] p {{ font-size: 1.02rem; font-weight: 600; }}
button[data-baseweb="tab"][aria-selected="true"] p {{ color: {BLUE}; }}

/* Sidebar: navy background, light text */
section[data-testid="stSidebar"] {{ background-color: {NAVY}; }}
/* Light text ONLY for text elements (headings, labels, captions).
   Input boxes are left alone, so text typed into them stays dark on white. */
section[data-testid="stSidebar"] :is(h1, h2, h3),
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] *,
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] *,
section[data-testid="stSidebar"] [data-testid="stCheckbox"] p,
section[data-testid="stSidebar"] .stButton button p {{ color: #E6ECF2; }}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {{ color: #A9BBD1; }}
/* Reset button: outlined, readable on navy */
section[data-testid="stSidebar"] .stButton button {{
    background: transparent; border: 1px solid #8FA6C1;
}}
</style>
"""


def apply_style() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def header(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="app-header"><h1>{title}</h1><p>{subtitle}</p></div>',
                unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(f'<div class="section">{title}</div>', unsafe_allow_html=True)


def kpi(col, label: str, value: str, accent: str = BLUE) -> None:
    col.markdown(
        f'<div class="kpi" style="--accent:{accent}">'
        f'<div class="label">{label}</div><div class="value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def badge(cls: str) -> str:
    return f'<span class="badge" style="background:{CLASS_COLORS[cls]}">{cls}</span>'


def insight(html: str) -> None:
    st.markdown(f'<div class="insight">{html}</div>', unsafe_allow_html=True)
