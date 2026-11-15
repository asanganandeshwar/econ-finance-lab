"""Applied economics portfolio: entry point for all tools.

Run:  streamlit run streamlit_app.py
"""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
for sub in ["", "min-wage-did", "rockets-feathers", "lbo-engine", "merger-analyzer"]:
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

st.set_page_config(page_title="Asanga Nandeshwar | Applied Economics", layout="wide")

pages = [
    st.Page("home.py", title="Home", default=True),
    st.Page("min-wage-did/app.py", title="Minimum Wage Study", url_path="minimum-wage"),
    st.Page("rockets-feathers/app.py", title="Rockets & Feathers", url_path="rockets-feathers"),
]
pages.insert(1, st.Page("lbo-engine/app.py", title="LBO Engine", url_path="lbo"))
pages.insert(2, st.Page("merger-analyzer/app.py", title="Merger Analyzer", url_path="merger"))

st.navigation(pages).run()
