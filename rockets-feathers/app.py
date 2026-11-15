"""Rockets & Feathers: asymmetric pass-through analyzer for US gasoline markets.

Run:  streamlit run app.py
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import rf  # noqa: E402

st.set_page_config(page_title="Rockets & Feathers", layout="wide")
UP, DOWN, GREY = "#c0392b", "#1f5fbf", "#8a8f98"


@st.cache_data
def load():
    return rf.load()


@st.cache_data
def run(region, stage, crude, start, k, horizon):
    df = load().loc[str(start):]
    f = rf.fit(rf.series_for(df, region, stage, crude), k=k, horizon=horizon)
    return f


df = load()

# ---------------------------------------------------------------- sidebar
st.sidebar.header("Market")
region = st.sidebar.selectbox("Region", list(rf.REGIONS))
stage = st.sidebar.radio("Supply-chain stage", list(rf.STAGES))
crude_lbl = st.sidebar.radio("Crude benchmark", ["Brent", "WTI"], horizontal=True)
crude = "brent_gal" if crude_lbl == "Brent" else "wti_gal"
st.sidebar.header("Model")
start = st.sidebar.slider("Sample start year", 2004, 2024, 2010)
k = st.sidebar.slider("Lags (weeks)", 1, 8, 4)
horizon = st.sidebar.slider("Response horizon (weeks)", 6, 20, 12)
st.sidebar.header("Consumer cost")
gallons_bn = st.sidebar.number_input("Weekly gallons in region (billions)", 0.1, 5.0,
                                     2.6 if region == "United States" else 0.25, 0.05,
                                     help="US ≈ 2.6 bn gal/week (≈ 9 m bbl/day). California ≈ 0.25 bn.")

f = run(region, stage, crude, start, k, horizon)
up, dn = f.resp_up, f.resp_down
weeks = np.arange(len(up))

def weeks_to(path, level=0.5):
    hit = np.where(path >= level)[0]
    return int(hit[0]) if len(hit) else None

extra = (up - dn).clip(min=0).sum() * 0.10 * gallons_bn * 1e9  # $ per 10-cent decline vs symmetric

# ---------------------------------------------------------------- header
st.title("Rockets & Feathers")
st.caption(f"Do {region} gasoline prices rise faster than they fall? · {stage} · weekly EIA data, "
           f"{f.data.index.min():%b %Y} to {f.data.index.max():%b %Y} · {len(f.data):,} weeks")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Same-week pass-through, increase", f"{up[0]:.0%}")
c2.metric("Same-week pass-through, decrease", f"{dn[0]:.0%}", f"{(dn[0] - up[0]) * 100:+.0f} pp", delta_color="off")
c3.metric("Symmetry test (Wald p)", f"{f.wald_all_p:.3f}",
          help="H0: every lag responds equally to cost increases and decreases. HAC standard errors.")
c4.metric("Extra paid per 10¢ cost drop", f"${extra / 1e6:,.0f}m",
          help="Area between the two response curves × 10¢ × weekly gallons: what consumers pay because "
               "decreases arrive slowly, relative to a symmetric market.")

t_up, t_dn = weeks_to(up), weeks_to(dn)
asym = f.wald_all_p < 0.05
st.info(
    f"**Reading.** Along the {stage.split(' (')[0].lower()} link, a cost increase reaches "
    f"{up[0]:.0%} of its long-run pass-through in the same week, while a decrease reaches {dn[0]:.0%}. "
    f"Half of the long-run pass-through arrives after {t_up if t_up is not None else f'>{horizon}'} week(s) for increases and "
    f"{t_dn if t_dn is not None else f'>{horizon}'} for decreases. "
    + ("Symmetry is rejected at 5%: **prices go up like rockets and down like feathers.**" if asym else
       "Symmetry is **not** rejected at 5% for this stage.")
)

tabs = st.tabs(["Response curves", "Supply-chain decomposition", "Margins", "Regional comparison",
                "Prices", "Model output", "Method"])

# ---------------------------------------------------------------- responses
with tabs[0]:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=weeks, y=up, name="Cost increase", mode="lines+markers", line=dict(color=UP, width=3)))
    fig.add_trace(go.Scatter(x=weeks, y=dn, name="Cost decrease", mode="lines+markers", line=dict(color=DOWN, width=3)))
    fig.add_trace(go.Scatter(x=np.r_[weeks, weeks[::-1]], y=np.r_[up, np.minimum(up, dn)[::-1]], fill="toself",
                             fillcolor="rgba(192,57,43,0.08)", line=dict(width=0), hoverinfo="skip",
                             name="Consumer overpayment"))
    fig.add_hline(y=1, line_dash="dot", line_color=GREY, annotation_text="Full long-run pass-through", annotation_position="bottom left")
    fig.update_layout(title="Cumulative pass-through of a permanent 10¢ cost change (share of long run)",
                      xaxis_title="Weeks after the cost change", yaxis_title="Share passed through",
                      yaxis_tickformat=".0%", height=460, template="simple_white")
    st.plotly_chart(fig, width="stretch")
    st.caption("Simulated from the estimated asymmetric error-correction model. The shaded gap is the "
               "money consumers keep paying while decreases work through.")

# ---------------------------------------------------------------- decomposition
with tabs[1]:
    rows = []
    figd = go.Figure()
    for i, st_name in enumerate(rf.STAGES):
        g = run(region, st_name, crude, start, k, horizon)
        rows.append({"Stage": st_name, "Long-run pass-through (b)": g.b,
                     "Week-0 up": g.resp_up[0], "Week-0 down": g.resp_down[0],
                     "Week-2 gap (pp)": 100 * (g.resp_up[2] - g.resp_down[2]),
                     "Symmetry p (all lags)": g.wald_all_p, "Symmetry p (sum)": g.wald_sum_p,
                     "Error correction θ": g.theta})
        figd.add_trace(go.Bar(x=[st_name], y=[100 * (g.resp_up[:5] - g.resp_down[:5]).sum()],
                              marker_color=UP if g.wald_all_p < 0.05 else GREY, showlegend=False))
    figd.update_layout(title="Where does the asymmetry come from? Cumulative up-minus-down gap, weeks 0–4 (pp-weeks)",
                       yaxis_title="pp-weeks", height=380, template="simple_white")
    st.plotly_chart(figd, width="stretch")
    st.dataframe(pd.DataFrame(rows).set_index("Stage").style.format({
        "Long-run pass-through (b)": "{:.2f}", "Week-0 up": "{:.0%}", "Week-0 down": "{:.0%}",
        "Week-2 gap (pp)": "{:+.0f}", "Symmetry p (all lags)": "{:.3f}", "Symmetry p (sum)": "{:.3f}",
        "Error correction θ": "{:.3f}"}), width="stretch")
    st.caption("Red bars reject symmetry at 5%. If the wholesale-to-retail stage carries the gap while "
               "crude-to-wholesale does not, the asymmetry comes from station pricing (search costs, "
               "focal-point pricing) rather than refiners.")

# ---------------------------------------------------------------- margins
with tabs[2]:
    retail, spot = rf.REGIONS[region]
    s = rf.series_for(df.loc[str(start):], region, "Wholesale → retail (stations)")
    m = rf.margin_asymmetry(s)
    fig = go.Figure()
    for reg_name, col in [("Costs rising", UP), ("Costs falling", DOWN)]:
        d = m[m.regime == reg_name]
        fig.add_trace(go.Scatter(x=d.cost_change * 100, y=d.margin * 100, mode="markers", name=reg_name,
                                 marker=dict(color=col, size=5, opacity=0.5)))
    fig.update_layout(title="Retail margin over wholesale vs 4-week wholesale price change",
                      xaxis_title="Wholesale change over prior 4 weeks (¢/gal)",
                      yaxis_title="Retail minus wholesale (¢/gal, incl. taxes)", height=440, template="simple_white")
    st.plotly_chart(fig, width="stretch")
    by = m.groupby("regime").margin.mean() * 100
    st.markdown(f"Average spread when costs are **falling**: **{by.get('Costs falling', np.nan):.1f}¢**, "
                f"when **rising**: **{by.get('Costs rising', np.nan):.1f}¢**. Stations earn fat margins "
                "on the way down and thin ones on the way up, which is the margin-side signature of rockets and feathers.")
    fig2 = go.Figure(go.Scatter(x=s.index, y=(s.P - s.C) * 100, line=dict(color=GREY)))
    fig2.update_layout(title="Retail–wholesale spread over time (¢/gal)", height=320, template="simple_white")
    st.plotly_chart(fig2, width="stretch")

# ---------------------------------------------------------------- regions
with tabs[3]:
    rows = []
    for r in rf.REGIONS:
        g = run(r, stage, crude, start, k, horizon)
        rows.append({"Region": r, "Week-0 up": g.resp_up[0], "Week-0 down": g.resp_down[0],
                     "Half-life, decrease (weeks)": weeks_to(g.resp_down) if weeks_to(g.resp_down) is not None else np.nan,
                     "Symmetry p": g.wald_all_p})
    rt = pd.DataFrame(rows).set_index("Region")
    fig = go.Figure()
    fig.add_trace(go.Bar(y=rt.index, x=rt["Week-0 up"], name="Increase", orientation="h", marker_color=UP))
    fig.add_trace(go.Bar(y=rt.index, x=rt["Week-0 down"], name="Decrease", orientation="h", marker_color=DOWN))
    fig.update_layout(barmode="group", title=f"Same-week pass-through by region · {stage}",
                      xaxis_tickformat=".0%", height=420, template="simple_white")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(rt.style.format({"Week-0 up": "{:.0%}", "Week-0 down": "{:.0%}",
                                  "Half-life, decrease (weeks)": "{:.0f}", "Symmetry p": "{:.3f}"}), width="stretch")

# ---------------------------------------------------------------- prices
with tabs[4]:
    s = rf.series_for(df.loc[str(start):], region, stage, crude)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s.P, name="Downstream price", line=dict(color=UP)))
    fig.add_trace(go.Scatter(x=s.index, y=s.C, name="Upstream cost", line=dict(color=GREY)))
    fig.update_layout(title=f"{region}: {stage} ($/gal)", height=420, template="simple_white")
    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------- model output
with tabs[5]:
    a, b = st.columns(2)
    a.markdown(f"""
**Long run:** P = {f.a:.3f} + **{f.b:.3f}** · C
**Error correction θ:** {f.theta:.3f} (≈ {abs(f.theta):.1%} of a gap closes per week)
**Engle–Granger cointegration p:** {f.coint_p:.3f}
**ADF on residual p:** {f.adf_resid_p:.3f}
**Symmetry, all lags (Wald p):** {f.wald_all_p:.4f}
**Symmetry, cumulative (Wald p):** {f.wald_sum_p:.4f}
**Observations:** {int(f.model.nobs):,} · **R²:** {f.model.rsquared:.3f}
""")
    if f.coint_p > 0.10:
        a.warning("Cointegration is weak for this sample. Long-horizon responses may drift; "
                  "trust the first few weeks, or move the sample start.")
    coef = pd.DataFrame({"coef": f.model.params, "HAC se": f.model.bse, "p": f.model.pvalues})
    b.dataframe(coef.style.format("{:.4f}"), width="stretch", height=520)

# ---------------------------------------------------------------- method
with tabs[6]:
    st.markdown(r"""
**Question.** Do gasoline prices respond faster to cost increases than to cost decreases, and at which stage of
the supply chain does the asymmetry arise?

**Data.** EIA weekly series: Brent and WTI spot ($/bbl ÷ 42), spot conventional gasoline at New York Harbor and the
Gulf Coast, Los Angeles RBOB, and retail regular gasoline for the US, the PADD regions and California. Spot prices
(Friday week-ending) are aligned to the next Monday's retail survey.

**Model.** Asymmetric error-correction model (Borenstein, Cameron and Gilbert 1997):

$$P_t = a + bC_t + u_t$$
$$\Delta P_t = \sum_{i=0}^{k}\left(\beta_i^+\Delta C^+_{t-i} + \beta_i^-\Delta C^-_{t-i}\right)
+ \sum_{j=1}^{k}\left(\gamma_j^+\Delta P^+_{t-j} + \gamma_j^-\Delta P^-_{t-j}\right) + \theta u_{t-1} + \varepsilon_t$$

Newey–West HAC standard errors. Symmetry is tested by Wald tests of $\beta_i^+ = \beta_i^-$ for all $i$ and of
$\sum\beta^+ = \sum\beta^-$. The response curves simulate the full system after a permanent ±10¢ cost change.

**IO interpretation.** Candidate explanations include consumer search costs (Lewis 2011), tacit collusion with
the old price as a focal point (Borenstein et al. 1997), and inventory or production adjustment costs. Splitting
the chain helps separate them: search-cost and focal-point stories predict asymmetry at the retail stage.

**Limitations.** Retail prices include taxes, which change in steps (California's excise is indexed every July).
The long-run equation is in nominal levels, and California's spread to wholesale shifts structurally (cap-and-trade,
LCFS, the 2015 Torrance refinery outage), which weakens cointegration there.
""")
