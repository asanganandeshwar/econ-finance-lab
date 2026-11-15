"""Rockets and Feathers: asymmetric pass-through of crude oil costs to gasoline prices.

Run:  streamlit run streamlit_app.py  (from the repository root)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).parent
for p in (HERE, HERE.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import rf  # noqa: E402
import ui  # noqa: E402
from ui import BLUE, GREY, NAVY, SKY  # noqa: E402

UP, DOWN = NAVY, BLUE


@st.cache_data
def load():
    return rf.load()


@st.cache_data(show_spinner=False, max_entries=256)
def run(region, stage, crude, start, k, horizon):
    return rf.fit(rf.series_for(load().loc[str(start):], region, stage, crude), k=k, horizon=horizon)


df = load()

# ---------------------------------------------------------------- sidebar
st.sidebar.header("Market")
region = st.sidebar.selectbox("Region", list(rf.REGIONS))
stage = st.sidebar.radio("Supply-chain link", list(rf.STAGES))
crude_lbl = st.sidebar.radio("Crude benchmark", ["Brent", "WTI"], horizontal=True)
crude = "brent_gal" if crude_lbl == "Brent" else "wti_gal"
st.sidebar.header("Model")
start = st.sidebar.slider("Sample start year", 2004, 2022, 2010)
k = st.sidebar.slider("Lags (weeks)", 1, 8, 4)
horizon = st.sidebar.slider("Response horizon (weeks)", 6, 20, 8)
st.sidebar.header("Consumer cost")
gallons_bn = st.sidebar.number_input("Weekly gallons sold (billions)", 0.05, 5.0,
                                     2.6 if region == "United States" else 0.25, 0.05,
                                     help="United States ≈ 2.6 billion gallons per week; California ≈ 0.25 billion.")

ui.header("Industrial organization", "Rockets and Feathers",
          "Do gasoline prices rise faster than they fall? This model measures how quickly cost increases and "
          "decreases reach the pump, identifies where in the supply chain the asymmetry arises, and estimates "
          "what it costs consumers.")

f = run(region, stage, crude, start, k, horizon)
up, dn = f.resp_up, f.resp_down
weeks = np.arange(len(up))
link = stage.split(" (")[0]


def half_life(path):
    hit = np.where(path >= 0.5)[0]
    return int(hit[0]) if len(hit) else None


extra = (up - dn).clip(min=0).sum() * 0.10 * gallons_bn * 1e9

c = st.columns(4)
c[0].metric("Same-week pass-through, increases", f"{up[0]:.0%}")
c[1].metric("Same-week pass-through, decreases", f"{dn[0]:.0%}")
c[2].metric("Symmetry test, p-value", f"{f.wald_all_p:.3f}",
            help="Wald test that every lag responds equally to increases and decreases; HAC standard errors.")
c[3].metric("Consumer cost per 10¢ decline", f"${extra / 1e6:,.0f}M",
            help="Area between the two response curves × $0.10 × weekly gallons.")

h_up, h_dn = half_life(up), half_life(dn)
def fmt(h):
    if h is None:
        return f"takes more than {horizon} weeks"
    if h == 0:
        return "occurs within the first week"
    return f"takes {h} week{'s' if h != 1 else ''}"


ui.finding(
    f"{region}, {link.lower()}: {up[0]:.0%} of a cost increase is passed through in the same week, against "
    f"{dn[0]:.0%} of a decrease. Half of the long-run adjustment {fmt(h_up)} for increases and "
    f"{fmt(h_dn)} for decreases. "
    + ("Symmetry is rejected at the 5% level." if f.wald_all_p < 0.05 else
       "Symmetry is not rejected at the 5% level.")
)

tabs = st.tabs(["Response curves", "Supply chain", "Retail margins", "Regions", "Prices", "Model output",
                "Methodology"])
SRC = (f"Source: U.S. Energy Information Administration, weekly prices, "
       f"{f.data.index.min():%b %Y}–{f.data.index.max():%b %Y} ({len(f.data):,} weeks).")

# ---------------------------------------------------------------- responses
with tabs[0]:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=np.r_[weeks, weeks[::-1]], y=np.r_[up, np.minimum(up, dn)[::-1]], fill="toself",
                             fillcolor="rgba(153,196,231,0.35)", line=dict(width=0), hoverinfo="skip",
                             name="Overpayment while decreases lag"))
    fig.add_trace(go.Scatter(x=weeks, y=up, name="Cost increase", mode="lines+markers",
                             line=dict(color=UP, width=3), marker=dict(size=6)))
    fig.add_trace(go.Scatter(x=weeks, y=dn, name="Cost decrease", mode="lines+markers",
                             line=dict(color=DOWN, width=3), marker=dict(size=6)))
    fig.add_hline(y=1, line_dash="dot", line_color=GREY, annotation_text="Full long-run pass-through",
                  annotation_position="bottom left", annotation_font=dict(size=11, color="#5A6872"))
    gap0 = (up[0] - dn[0]) * 100
    fig.update_layout(title=ui.exhibit(1, f"Increases reach the pump {gap0:.0f} points faster than decreases "
                                          f"in the first week" if gap0 > 0 else
                                          "Cumulative pass-through of a permanent 10¢ cost change"),
                      xaxis_title="Weeks after the cost change", yaxis_title="Share of long-run pass-through",
                      yaxis_tickformat=".0%", height=470)
    st.plotly_chart(fig, width="stretch")
    ui.source("Simulated from the estimated asymmetric error-correction model for a permanent ±10¢ change in "
              "upstream cost. " + SRC)

# ---------------------------------------------------------------- decomposition
with tabs[1]:
    rows = []
    for st_name in rf.STAGES:
        g = run(region, st_name, crude, start, k, horizon)
        rows.append({"Link": st_name, "Long-run pass-through": g.b, "Same-week, increases": g.resp_up[0],
                     "Same-week, decreases": g.resp_down[0],
                     "Gap, weeks 0–4 (pp-weeks)": 100 * (g.resp_up[:5] - g.resp_down[:5]).sum(),
                     "Symmetry p (all lags)": g.wald_all_p, "Symmetry p (sum)": g.wald_sum_p,
                     "Error correction θ": g.theta})
    t = pd.DataFrame(rows).set_index("Link")
    fig = go.Figure(go.Bar(
        x=t.index, y=t["Gap, weeks 0–4 (pp-weeks)"],
        marker_color=[NAVY if p < 0.05 else SKY for p in t["Symmetry p (all lags)"]],
        text=[f"{v:.0f}" for v in t["Gap, weeks 0–4 (pp-weeks)"]], textposition="outside"))
    short = {s_: s_.split("(")[-1].rstrip(")") for s_ in t.index}
    sig = [short[s_] for s_ in t.index if t.loc[s_, "Symmetry p (all lags)"] < 0.05]
    nonsig = [short[s_] for s_ in t.index if t.loc[s_, "Symmetry p (all lags)"] >= 0.05]
    if sig and nonsig:
        title2 = f"Symmetry is rejected for {' and '.join(sig)}, but not for {' and '.join(nonsig)}"
    elif sig:
        title2 = "Symmetry is rejected at every link of the supply chain"
    else:
        title2 = "Symmetry is not rejected at any link of the supply chain"
    fig.update_layout(title=ui.exhibit(2, title2),
                      yaxis_title="Increase minus decrease, cumulative pp-weeks", height=400, showlegend=False)
    st.plotly_chart(fig, width="stretch")
    ui.source("Dark bars reject symmetry at the 5% level; light bars do not, so their gaps are not statistically "
              "meaningful. Asymmetry at stations alongside symmetric refinery pricing is consistent with consumer "
              "search costs and focal-point pricing rather than refinery constraints.")
    st.dataframe(t.style.format({
        "Long-run pass-through": "{:.2f}", "Same-week, increases": "{:.0%}", "Same-week, decreases": "{:.0%}",
        "Gap, weeks 0–4 (pp-weeks)": "{:+.0f}", "Symmetry p (all lags)": "{:.3f}", "Symmetry p (sum)": "{:.3f}",
        "Error correction θ": "{:.3f}"}), width="stretch")

# ---------------------------------------------------------------- margins
with tabs[2]:
    s = rf.series_for(df.loc[str(start):], region, "Wholesale → retail (stations)")
    m = rf.margin_asymmetry(s)
    by = m.groupby("regime").margin.mean() * 100
    diff = by.get("Costs falling", np.nan) - by.get("Costs rising", np.nan)
    fig = go.Figure()
    for reg_name, col in [("Costs rising", UP), ("Costs falling", DOWN)]:
        d = m[m.regime == reg_name]
        fig.add_trace(go.Scatter(x=d.cost_change * 100, y=d.margin * 100, mode="markers", name=reg_name,
                                 marker=dict(color=col, size=5, opacity=0.45)))
    fig.update_layout(title=ui.exhibit(3, f"Retail spreads average {diff:.0f}¢ wider when wholesale costs are "
                                          f"falling"),
                      xaxis_title="Change in wholesale price over prior 4 weeks (¢/gal)",
                      yaxis_title="Retail minus wholesale (¢/gal, incl. taxes)", height=460)
    st.plotly_chart(fig, width="stretch")
    ui.source(f"Average spread: {by.get('Costs falling', np.nan):.1f}¢ when costs are falling, "
              f"{by.get('Costs rising', np.nan):.1f}¢ when rising. " + SRC)
    fig2 = go.Figure(go.Scatter(x=s.index, y=(s.P - s.C) * 100, line=dict(color=NAVY, width=1.5)))
    fig2.update_layout(title=ui.exhibit(4, "Retail–wholesale spread over time"), yaxis_title="¢/gal", height=330)
    st.plotly_chart(fig2, width="stretch")

# ---------------------------------------------------------------- regions
with tabs[3]:
    rows = []
    for r_ in rf.REGIONS:
        g = run(r_, stage, crude, start, k, horizon)
        rows.append({"Region": r_, "Same-week, increases": g.resp_up[0], "Same-week, decreases": g.resp_down[0],
                     "Half-life of decreases (weeks)": half_life(g.resp_down) if half_life(g.resp_down) is not None
                     else np.nan, "Symmetry p": g.wald_all_p})
    rt = pd.DataFrame(rows).set_index("Region")
    rt["gap"] = rt["Same-week, increases"] - rt["Same-week, decreases"]
    rt = rt.sort_values("gap")
    fig = go.Figure()
    fig.add_trace(go.Bar(y=rt.index, x=rt["Same-week, increases"], name="Increases", orientation="h",
                         marker_color=UP))
    fig.add_trace(go.Bar(y=rt.index, x=rt["Same-week, decreases"], name="Decreases", orientation="h",
                         marker_color=DOWN))
    fig.update_layout(barmode="group", title=ui.exhibit(5, f"Same-week pass-through is asymmetric in "
                                                           f"{int((rt['Symmetry p'] < 0.05).sum())} of "
                                                           f"{len(rt)} regions"),
                      xaxis_tickformat=".0%", height=440)
    st.plotly_chart(fig, width="stretch")
    ui.source(f"Link: {stage}. " + SRC)
    st.dataframe(rt.drop(columns="gap").style.format({
        "Same-week, increases": "{:.0%}", "Same-week, decreases": "{:.0%}",
        "Half-life of decreases (weeks)": "{:.0f}", "Symmetry p": "{:.3f}"}), width="stretch")

# ---------------------------------------------------------------- prices
with tabs[4]:
    s = rf.series_for(df.loc[str(start):], region, stage, crude)
    labels = {"crude": f"{crude_lbl} crude ($/gal)", "spot": "Wholesale gasoline", "retail": "Retail gasoline"}
    up_lbl, dn_lbl = (labels[x] for x in rf.STAGES[stage])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s.C, name=up_lbl, line=dict(color=GREY, width=1.5)))
    fig.add_trace(go.Scatter(x=s.index, y=s.P, name=dn_lbl, line=dict(color=NAVY, width=1.5)))
    fig.update_layout(title=ui.exhibit(6, f"{region}: {dn_lbl.lower()} vs. {up_lbl.split(' (')[0].lower()}"),
                      yaxis_title="$ per gallon", height=440)
    st.plotly_chart(fig, width="stretch")
    ui.source(SRC)

# ---------------------------------------------------------------- model output
with tabs[5]:
    a, b = st.columns(2, gap="large")
    a.table(pd.DataFrame({"Value": {
        "Long-run pass-through (b)": f"{f.b:.3f}",
        "Long-run intercept (a)": f"{f.a:.3f}",
        "Error correction (θ)": f"{f.theta:.3f}",
        "Engle–Granger cointegration p": f"{f.coint_p:.3f}",
        "ADF on long-run residual p": f"{f.adf_resid_p:.3f}",
        "Symmetry, all lags (Wald p)": f"{f.wald_all_p:.4f}",
        "Symmetry, cumulative (Wald p)": f"{f.wald_sum_p:.4f}",
        "Observations": f"{int(f.model.nobs):,}",
        "R²": f"{f.model.rsquared:.3f}",
    }}))
    if f.coint_p > 0.10:
        a.caption("Cointegration is weak in this sample, so long-horizon responses are less reliable than the "
                  "first few weeks. Moving the sample start can help.")
    coef = pd.DataFrame({"Coefficient": f.model.params, "HAC s.e.": f.model.bse, "p-value": f.model.pvalues})
    b.dataframe(coef.style.format("{:.4f}"), width="stretch", height=560)

# ---------------------------------------------------------------- methodology
with tabs[6]:
    st.markdown(r"""
**Data.** EIA weekly series: Brent and WTI spot prices (converted to $/gallon), spot conventional gasoline at New
York Harbor and the Gulf Coast, Los Angeles RBOB, and retail regular gasoline for the United States, the five PADD
regions and California. Spot prices (Friday week-ending) are aligned to the following Monday's retail survey.

**Model.** Asymmetric error-correction model (Borenstein, Cameron and Gilbert 1997):

$$P_t = a + bC_t + u_t$$
$$\Delta P_t = \sum_{i=0}^{k}\left(\beta_i^+\Delta C^+_{t-i} + \beta_i^-\Delta C^-_{t-i}\right)
+ \sum_{j=1}^{k}\left(\gamma_j^+\Delta P^+_{t-j} + \gamma_j^-\Delta P^-_{t-j}\right) + \theta u_{t-1} + \varepsilon_t$$

Newey–West standard errors. Symmetry is tested with Wald tests of $\beta_i^+ = \beta_i^-$ for all $i$ and of
$\sum\beta^+ = \sum\beta^-$. Response curves simulate the full system after a permanent ±10¢ cost change.

**Interpretation.** Leading explanations are consumer search costs (Lewis 2011), tacit coordination around the
previous price, and inventory adjustment costs. Estimating each link of the supply chain separately helps
distinguish them, because search-cost and focal-point explanations predict asymmetry at the retail level.

**Limitations.** Retail prices include taxes, which change in discrete steps. The long-run relationship is
estimated in nominal levels. California's retail–wholesale spread shifts with cap-and-trade, the Low Carbon Fuel
Standard and refinery outages, which weakens cointegration there.
""")
