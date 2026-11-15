import streamlit as st

import ui

ui.header(
    "Applied economics portfolio",
    "Asanga Nandeshwar",
    "Managerial Economics and Statistics, UC Davis. Three analytical tools in private equity, labor economics "
    "and industrial organization, built on public data. Source code and methodology are on "
    "<a href='https://github.com/asanganandeshwar/econ-finance-lab'>GitHub</a>.",
)

cards = [
    ("lbo-engine/app.py", "Private equity", "LBO Engine", "20.7%",
     "Base-case IRR at 9.5x entry and exit, 5.5x leverage",
     "Five-year buyout model with a tranche-level debt schedule and cash sweep, an exact value-creation "
     "bridge, a maximum-price solver, sensitivity grids and Monte Carlo exit risk."),
    ("min-wage-did/app.py", "Labor economics", "The $20 Fast-Food Wage", "−2.9%",
     "Fast-food employment vs. other states; not significant (p = 0.16)",
     "Difference-in-differences, event study, synthetic control and triple difference on BLS QCEW data, "
     "with permutation inference for a single treated state."),
    ("rockets-feathers/app.py", "Industrial organization", "Rockets and Feathers", "63% vs. 23%",
     "Same-week pass-through of gasoline cost increases vs. decreases",
     "Asymmetric error-correction model on weekly EIA prices that locates the asymmetry in the supply "
     "chain and estimates its cost to consumers."),
]
cols = st.columns(3, gap="large")
for col, (page, field, title, num, lbl, desc) in zip(cols, cards):
    with col:
        st.markdown(f'<div class="card"><div class="eyebrow">{field}</div></div>', unsafe_allow_html=True)
        st.subheader(title)
        st.markdown(f'<div class="card" style="border:none;padding:0"><div class="num">{num}</div>'
                    f'<div class="lbl">{lbl}</div></div>', unsafe_allow_html=True)
        st.write(desc)
        st.page_link(page, label="Open →")
