"""Shared visual style: typography, palette, Plotly template and small layout helpers."""
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

NAVY = "#051C2C"
BLUE = "#2251FF"
CYAN = "#00A9F4"
SKY = "#99C4E7"
GREY = "#A2AAAD"
DARK_GREY = "#5A6872"
LIGHT = "#E6E8EA"
RED = "#C0504D"
GREEN = "#2E7D5B"

SERIF = "'Source Serif 4', Georgia, 'Times New Roman', serif"
SANS = "Inter, 'Helvetica Neue', Arial, sans-serif"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Inter:wght@400;500;600&display=swap');
html, body, .stApp {{ font-family: {SANS}; color: #1F2A33; }}
.block-container {{ padding-top: 2.2rem; max-width: 1180px; }}
h1, h2, h3, h4 {{ font-family: {SERIF} !important; color: {NAVY} !important; font-weight: 600 !important;
                  letter-spacing: -0.01em; }}
h1 {{ font-size: 2.15rem !important; padding-bottom: 0.35rem !important; }}
.eyebrow {{ font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: {DARK_GREY};
            margin-bottom: -0.6rem; }}
.dek {{ font-size: 1.02rem; color: #3A4650; max-width: 860px; margin: 0.2rem 0 1.1rem; line-height: 1.5; }}
.rule {{ border: none; border-top: 1px solid {NAVY}; margin: 0.4rem 0 1.4rem; }}
.finding {{ border-left: 3px solid {BLUE}; padding: 0.35rem 0 0.35rem 1rem; margin: 1rem 0 1.4rem;
            font-size: 1.0rem; line-height: 1.55; color: {NAVY}; max-width: 980px; }}
.source {{ font-size: 0.76rem; color: {DARK_GREY}; margin-top: -0.4rem; margin-bottom: 1.6rem; }}
[data-testid="stMetricValue"] {{ font-family: {SERIF}; color: {NAVY}; font-weight: 600; }}
[data-testid="stMetricLabel"] p {{ text-transform: uppercase; letter-spacing: 0.07em; font-size: 0.7rem !important;
                                  color: {DARK_GREY}; }}
[data-testid="stMetric"] {{ border-top: 1px solid {LIGHT}; padding-top: 0.6rem; }}
.stTabs [data-baseweb="tab"] {{ font-weight: 500; }}
.stTabs [aria-selected="true"] {{ color: {NAVY} !important; }}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ font-size: 0.78rem !important; letter-spacing: 0.1em;
    text-transform: uppercase; font-family: {SANS} !important; color: {DARK_GREY} !important; }}
.card {{ border-top: 3px solid {NAVY}; padding-top: 0.8rem; }}
.card .num {{ font-family: {SERIF}; font-size: 2rem; color: {NAVY}; line-height: 1.1; }}
.card .lbl {{ font-size: 0.82rem; color: {DARK_GREY}; margin-bottom: 0.6rem; }}
</style>
"""

pio.templates["consult"] = go.layout.Template(layout=dict(
    font=dict(family=SANS, size=13, color="#1F2A33"),
    title=dict(font=dict(family=SERIF, size=18, color=NAVY), x=0, xanchor="left", y=0.97),
    colorway=[NAVY, BLUE, CYAN, GREY, SKY, DARK_GREY],
    paper_bgcolor="white", plot_bgcolor="white",
    xaxis=dict(showgrid=False, linecolor=GREY, ticks="outside", tickcolor=GREY, zeroline=False,
               title=dict(font=dict(size=12, color=DARK_GREY))),
    yaxis=dict(showgrid=True, gridcolor=LIGHT, linecolor=GREY, zeroline=False, ticks="",
               title=dict(font=dict(size=12, color=DARK_GREY))),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, font=dict(size=12),
                bgcolor="rgba(0,0,0,0)"),
    margin=dict(l=60, r=30, t=90, b=50),
    hoverlabel=dict(font=dict(family=SANS)),
))
pio.templates.default = "consult"
TEMPLATE = "consult"


def style():
    st.markdown(_CSS, unsafe_allow_html=True)


def header(eyebrow: str, title: str, dek: str):
    style()
    st.markdown(f'<div class="eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<hr class="rule"><div class="dek">{dek}</div>', unsafe_allow_html=True)


def finding(text: str):
    st.markdown(f'<div class="finding">{text}</div>', unsafe_allow_html=True)


def source(text: str):
    st.markdown(f'<div class="source">{text}</div>', unsafe_allow_html=True)


def exhibit(n: int, title: str) -> str:
    """Plotly title with a small exhibit label above an action title."""
    return (f"<span style='font-family:{SANS};font-size:11px;letter-spacing:1.5px;color:{DARK_GREY}'>"
            f"EXHIBIT {n}</span><br>{title}")
