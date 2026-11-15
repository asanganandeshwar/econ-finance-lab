from pathlib import Path

import streamlit as st

st.title("Econ & Finance Lab")
st.markdown(
    "Interactive tools in applied microeconomics, industrial organization and private equity, built on "
    "public data. Each tool runs the analysis live, so every chart and estimate updates as you change "
    "the assumptions.  \n*Asanga Nandeshwar · UC Davis, Managerial Economics and Statistics (ML)*"
)
st.divider()

has_lbo = (Path(__file__).parent / "lbo-engine" / "app.py").exists()
cols = st.columns(3 if has_lbo else 2)
i = 0
if has_lbo:
    with cols[i]:
        st.subheader("LBO Engine")
        st.caption("Private equity · deal modeling")
        st.markdown("A leveraged buyout model with a tranche-by-tranche debt schedule and cash sweep, "
                    "IRR and MOIC, a value-creation bridge, sensitivity grids, and Monte Carlo exit risk. "
                    "It imports deal inputs from my CIM Analyzer.")
        st.page_link("lbo-engine/app.py", label="Open the LBO Engine →")
    i += 1
with cols[i]:
    st.subheader("Minimum Wage Evaluator")
    st.caption("Labor economics · causal inference")
    st.markdown("Did California's $20 fast-food wage cost jobs? Difference-in-differences, event study, "
                "synthetic control and triple difference on BLS QCEW data, with permutation inference.")
    st.page_link("min-wage-did/app.py", label="Open the evaluator →")
with cols[i + 1]:
    st.subheader("Rockets & Feathers")
    st.caption("Industrial organization · time series")
    st.markdown("Do gas prices rise faster than they fall? An asymmetric error-correction model on EIA data "
                "that locates the asymmetry in the supply chain and puts a dollar cost on it.")
    st.page_link("rockets-feathers/app.py", label="Open the analyzer →")

st.divider()
st.caption("Source code and methodology: see the README in each project folder on GitHub.")
