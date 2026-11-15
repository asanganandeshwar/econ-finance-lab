"""Minimum Wage Policy Evaluator: interactive DiD / event study / synthetic control.

Run:  streamlit run app.py
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import did  # noqa: E402

st.set_page_config(page_title="Minimum Wage Policy Evaluator", layout="wide")

ACCENT, GREY, LIGHT = "#1f5fbf", "#8a8f98", "rgba(138,143,152,0.18)"


@st.cache_data
def load():
    return did.load()


df = load()
states = sorted(df.state.unique())
quarters = [did.lab(t) for t in sorted(df.t.unique())]

# ---------------------------------------------------------------- sidebar
st.sidebar.header("Policy")
treated = st.sidebar.selectbox("Treated state", states, index=states.index("CA"))
pre_end = st.sidebar.selectbox("Last pre-period quarter", quarters, index=quarters.index("2023Q3"),
                               help="CA signed AB 1228 on Sep 28, 2023. Quarters between this and the "
                                    "policy start are shown as an anticipation window and excluded from the estimate.")
post_start = st.sidebar.selectbox("First treated quarter", quarters, index=quarters.index("2024Q2"),
                                  help="The $20 fast-food wage took effect Apr 1, 2024.")

st.sidebar.header("Specification")
sector_name = st.sidebar.radio("Sector", list(did.SECTORS))
outcome_name = st.sidebar.radio("Outcome", list(did.OUTCOMES))
sets = did.control_sets(treated, states)
ctrl_name = st.sidebar.selectbox("Control group", list(sets) + ["Custom"])
if ctrl_name == "Custom":
    controls = st.sidebar.multiselect("Control states", [s for s in states if s != treated],
                                      default=sets["Federal-minimum-wage states"])
else:
    controls = sets[ctrl_name]
sample_start = st.sidebar.selectbox("Sample start", quarters, index=quarters.index("2022Q1"),
                                    help="2022Q1 avoids the uneven post-COVID restaurant rebound.")
trend = st.sidebar.checkbox("State-specific linear trends", value=False)

if len(controls) < 2:
    st.warning("Pick at least two control states.")
    st.stop()

spec = did.Spec(treated, tuple(controls), did.OUTCOMES[outcome_name], did.SECTORS[sector_name],
                sample_start, pre_end, post_start, trend)
res = did.run_did(df, spec)
syn = did.run_synth(res)
pct = lambda x: 100 * (np.exp(x) - 1)
xl = [did.lab(t) for t in res.gap.index]

# ---------------------------------------------------------------- header
st.title("Minimum Wage Policy Evaluator")
st.caption(f"{treated} vs {ctrl_name.lower()} · {sector_name} · {outcome_name.lower()} · "
           f"BLS QCEW, private ownership, state level, {sample_start} to {xl[-1]}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("DiD estimate", f"{pct(res.est):+.2f}%", help="Average post-period gap minus pre-period gap, in percent.")
c2.metric("Permutation p-value", f"{res.p_perm:.3f}",
          help=f"Share of {len(res.placebo_est)} placebo states with an effect at least as large.")
c3.metric("Synthetic control", f"{pct(syn['est']):+.2f}%", help=f"Permutation p = {syn['p']:.3f} (RMSPE ratio).")
if spec.outcome == "emp" and spec.sector != "ddd":
    c4.metric("Implied jobs", f"{(np.exp(res.est) - 1) * res.base_level:+,.0f}",
              help=f"Applied to {treated}'s pre-period average of {res.base_level:,.0f} workers.")
else:
    c4.metric("Control states", len(res.placebo_est))

# auto-written read of the result
sig = res.p_perm < 0.10
direction = "lower" if res.est < 0 else "higher"
st.info(
    f"**Reading.** After the policy, {treated}'s {sector_name.split(' (')[0].lower()} "
    f"{outcome_name.lower()} ran {abs(pct(res.est)):.1f}% {direction} than the control-group "
    f"({ctrl_name.lower()}) benchmark, relative to the pre-period. "
    + (f"Only {res.p_perm:.0%} of placebo states show a gap this large, so the effect is distinguishable from noise."
       if sig else
       f"{res.p_perm:.0%} of placebo states show a gap at least this large, so the estimate is **not** "
       f"distinguishable from ordinary state-to-state variation.")
)

tabs = st.tabs(["Trends", "Event study", "Placebo test", "Synthetic control",
                "Specification curve", "Regression table", "Method"])

# ---------------------------------------------------------------- trends
with tabs[0]:
    ctrl_mean = res.R[[c for c in res.R.columns if c != treated]].mean(axis=1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xl, y=100 * ctrl_mean, name="Control average", line=dict(color=GREY, width=2)))
    fig.add_trace(go.Scatter(x=xl, y=100 * res.R[treated], name=treated, line=dict(color=ACCENT, width=3)))
    fig.add_vline(x=xl.index(pre_end), line_dash="dot", line_color=GREY)
    fig.add_vline(x=xl.index(post_start), line_dash="dash", line_color=ACCENT)
    fig.add_annotation(x=xl.index(post_start), y=1, yref="paper", text="Policy start", showarrow=False,
                       xanchor="left", font=dict(color=ACCENT))
    fig.update_layout(title="Seasonally adjusted log outcome, % deviation from own pre-period mean",
                      yaxis_title="% vs pre-period", height=440, template="simple_white")
    st.plotly_chart(fig, width="stretch")
    st.caption("Each state's quarter-of-year pattern is removed using pre-period data only, so the post-period "
               "never shapes the baseline.")

# ---------------------------------------------------------------- event study
with tabs[1]:
    P = res.placebo_gaps
    lo, hi = 100 * P.quantile(0.05, axis=1), 100 * P.quantile(0.95, axis=1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xl + xl[::-1], y=list(hi) + list(lo[::-1]), fill="toself", fillcolor=LIGHT,
                             line=dict(width=0), name="90% placebo band", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=xl, y=100 * res.gap, mode="lines+markers", name=f"{treated} gap",
                             line=dict(color=ACCENT, width=3)))
    fig.add_hline(y=0, line_color="black", line_width=1)
    fig.add_vrect(x0=xl.index(pre_end), x1=xl.index(post_start), fillcolor="rgba(31,95,191,0.07)",
                  line_width=0, annotation_text="anticipation", annotation_position="top left")
    fig.update_layout(title=f"Event study: {treated} minus control average (%), with placebo-state band",
                      yaxis_title="Gap, %", height=460, template="simple_white")
    st.plotly_chart(fig, width="stretch")
    st.caption("The band holds 90% of the gaps produced by pretending each control state was treated. "
               "A flat pre-period supports parallel trends; a post-period line outside the band is a real effect.")

# ---------------------------------------------------------------- placebo
with tabs[2]:
    pe = pct(res.placebo_est).sort_values()
    colors = [GREY] * len(pe)
    fig = go.Figure(go.Bar(x=pe.index, y=pe.values, marker_color=colors, name="Placebo states"))
    fig.add_trace(go.Bar(x=[treated], y=[pct(res.est)], marker_color=ACCENT, name=treated))
    fig.update_layout(title=f"DiD estimate for {treated} vs every placebo state (p = {res.p_perm:.3f})",
                      yaxis_title="Estimated effect, %", height=440, template="simple_white",
                      xaxis=dict(categoryorder="total ascending"))
    st.plotly_chart(fig, width="stretch")
    st.caption("Randomization inference (Abadie, Diamond and Hainmueller 2010; Conley and Taber 2011). "
               "With one treated state, this ranking is the honest test.")

# ---------------------------------------------------------------- synth
with tabs[3]:
    a, b = st.columns([2, 1])
    with a:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=xl, y=100 * syn["synthetic"], name=f"Synthetic {treated}",
                                 line=dict(color=GREY, width=2, dash="dash")))
        fig.add_trace(go.Scatter(x=xl, y=100 * res.R[treated], name=treated, line=dict(color=ACCENT, width=3)))
        fig.add_vline(x=xl.index(post_start), line_dash="dash", line_color=ACCENT)
        fig.update_layout(title=f"{treated} vs synthetic {treated} (p = {syn['p']:.3f})",
                          yaxis_title="% vs pre-period", height=420, template="simple_white")
        st.plotly_chart(fig, width="stretch")
    with b:
        w = syn["weights"][syn["weights"] > 0.01]
        st.markdown("**Donor weights**")
        st.dataframe(w.rename("weight").to_frame().style.format("{:.1%}"), width="stretch")
        st.caption(f"Post/pre RMSPE ratio: {syn['ratio']:.2f}, ranked against {len(syn['ratios'])} placebo runs.")

# ---------------------------------------------------------------- spec curve
with tabs[4]:
    sc = did.spec_curve(df, spec)
    sc["label"] = sc.controls + " · " + sc.sector.str.split(" \\(").str[0] + " · " + sc.sample_start + \
        np.where(sc.state_trends, " · trends", "")
    fig = go.Figure(go.Scatter(
        x=list(range(len(sc))), y=sc.est_pct, mode="markers",
        marker=dict(size=10, color=np.where(sc.p_perm < 0.10, ACCENT, GREY)),
        text=sc.label + "<br>p = " + sc.p_perm.round(3).astype(str), hoverinfo="text+y"))
    fig.add_hline(y=0, line_color="black", line_width=1)
    fig.update_layout(title=f"Specification curve: {len(sc)} estimates for {outcome_name.lower()} "
                            f"(blue = permutation p < 0.10)",
                      xaxis_title="Specifications, sorted by estimate", yaxis_title="Effect, %",
                      height=440, template="simple_white")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(sc.drop(columns="label").style.format({"est_pct": "{:+.2f}", "p_perm": "{:.3f}"}),
                 width="stretch", height=300)

# ---------------------------------------------------------------- regression
with tabs[5]:
    m = did.twfe_regression(df, spec)
    b_, se = m.params["treat_post"], m.std_errors["treat_post"]
    tbl = pd.DataFrame({
        "": ["Coefficient (log points)", "Effect (%)", "Clustered SE", "Clustered p-value",
             "Permutation p-value", "Observations", "Fixed effects"],
        "TWFE DiD": [f"{b_:.4f}", f"{pct(b_):+.2f}", f"{se:.4f}", f"{m.pvalues['treat_post']:.4f}",
                     f"{res.p_perm:.3f}", f"{int(m.nobs):,}",
                     "state × quarter-of-year, quarter" + (", state trends" if trend else "")],
    })
    st.table(tbl.set_index(""))
    st.warning("Clustered standard errors assume many treated clusters. With a single treated state they "
               "understate uncertainty, which is why the clustered p-value looks far stronger than the "
               "permutation p-value (Conley and Taber 2011). Trust the permutation test.")

# ---------------------------------------------------------------- method
with tabs[6]:
    st.markdown(r"""
**Question.** Did California's AB 1228 ($16 → $20 for fast-food chains, April 1, 2024) reduce employment?

**Data.** BLS Quarterly Census of Employment and Wages, private ownership, state level.
NAICS 722513 (limited-service restaurants) is the treated sector; NAICS 722511 (full-service) is the
within-state comparison for the triple difference. Employment is the average of the three monthly counts.

**Estimator.** For log outcome $y_{st}$, remove each state's quarter-of-year mean (and optionally a linear
trend) using pre-period data only, giving $\tilde y_{st}$. The gap is

$$g_t = \tilde y_{CA,t} - \frac{1}{N}\sum_{c} \tilde y_{c,t}, \qquad
\hat\delta = \bar g_{\text{post}} - \bar g_{\text{pre}}.$$

The anticipation window (signing to start date) is excluded from both averages.

**Triple difference.** The outcome becomes $\ln(\text{limited}) - \ln(\text{full})$ within each state, which nets
out shocks that hit all California restaurants, such as local demand, costs, or a statewide slowdown.

**Inference.** Each control state is treated as a placebo, and $\hat\delta$ is ranked against the placebo
distribution. Synthetic control (Abadie et al. 2010) builds a weighted donor pool fitted on the pre-period and
is tested with the post/pre RMSPE ratio.

**Limitations.** QCEW covers all limited-service restaurants, including chains under 60 locations that the law
exempts, which biases estimates toward zero. State-level data cannot separate hours from headcount. Other
California shocks after April 2024 (for example, the 2024 health-care minimum wage) are not separated out.
""")
