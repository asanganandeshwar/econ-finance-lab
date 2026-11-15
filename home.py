import streamlit as st

import ui

ui.header(
    "Applied economics portfolio",
    "Asanga Nandeshwar",
    "Managerial Economics and Statistics, UC Davis. Four analytical tools in private equity, M&A, labor "
    "economics and industrial organization, built in Python. Source code and methodology are on "
    "<a href='https://github.com/asanganandeshwar/econ-finance-lab'>GitHub</a>.",
)

cards = [
    ("lbo-engine/app.py", "Private equity", "LBO Engine", "20.7%",
     "Base-case IRR at 9.5x entry and exit, 5.5x leverage",
     "Five-year buyout model with a tranche-level debt schedule and cash sweep, an exact value-creation "
     "bridge, a maximum-price solver, sensitivity grids and Monte Carlo exit risk."),
    ("merger-analyzer/app.py", "Mergers and acquisitions", "Merger Analyzer", "18%",
     "Cost savings needed to offset consumer harm from a #1–#2 merger",
     "EPS accretion and dilution with financing, purchase-price amortization and breakeven synergies, plus "
     "HHI screens, upward pricing pressure and a logit merger simulation."),
    ("min-wage-did/app.py", "Labor economics", "$20 Fast-Food Wage", "−2.9%",
     "Fast-food employment vs. other states; not significant (p = 0.16)",
     "Difference-in-differences, event study, synthetic control and triple difference on BLS QCEW data, "
     "with permutation inference for a single treated state."),
    ("rockets-feathers/app.py", "Industrial organization", "Rockets and Feathers", "63% vs. 23%",
     "Same-week pass-through of gasoline cost increases vs. decreases",
     "Asymmetric error-correction model on weekly EIA prices that locates the asymmetry in the supply "
     "chain and estimates its cost to consumers."),
]
for i, (page, field, title, num, lbl, desc) in enumerate(cards):
    if i % 2 == 0:
        cols = st.columns(2, gap="large")
    with cols[i % 2]:
        st.markdown(f'<div class="card"><div class="eyebrow">{field}</div></div>', unsafe_allow_html=True)
        st.subheader(title)
        st.markdown(f'<div class="card" style="border:none;padding:0"><div class="num">{num}</div>'
                    f'<div class="lbl">{lbl}</div></div>', unsafe_allow_html=True)
        st.write(desc)
        st.page_link(page, label="Open →")
