"""California's $20 fast-food wage: difference-in-differences, event study, synthetic control.

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
import did  # noqa: E402
import ui  # noqa: E402
from ui import GREY, LIGHT, NAVY, SKY  # noqa: E402


@st.cache_data
def load():
    return did.load()


df = load()


@st.cache_data(show_spinner=False, max_entries=64)
def cached_did(spec):
    return did.run_did(df, spec)


@st.cache_data(show_spinner="Fitting synthetic control", max_entries=64)
def cached_synth(spec):
    return did.run_synth(cached_did(spec))


@st.cache_data(show_spinner="Estimating specifications", max_entries=32)
def cached_curve(spec):
    return did.spec_curve(df, spec)


@st.cache_data(show_spinner=False, max_entries=64)
def cached_twfe(spec):
    m = did.twfe_regression(df, spec)
    return dict(b=m.params["treat_post"], se=m.std_errors["treat_post"], p=m.pvalues["treat_post"], n=m.nobs)


states = sorted(df.state.unique())
quarters = [did.lab(t) for t in sorted(df.t.unique())]

# ---------------------------------------------------------------- sidebar
st.sidebar.header("Policy")
treated = st.sidebar.selectbox("Treated state", states, index=states.index("CA"))
pre_end = st.sidebar.selectbox("Last pre-period quarter", quarters, index=quarters.index("2023Q3"),
                               help="AB 1228 was signed on Sep 28, 2023. Quarters between signing and the "
                                    "effective date are excluded from the estimate.")
post_start = st.sidebar.selectbox("First treated quarter", quarters, index=quarters.index("2024Q2"),
                                  help="The $20 wage took effect on Apr 1, 2024.")
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
                                    help="2022Q1 avoids the uneven post-pandemic restaurant recovery.")
trend = st.sidebar.checkbox("State-specific linear trends")

ui.header("Labor economics", "California's $20 Fast-Food Minimum Wage",
          "Did AB 1228, which raised pay at chains with 60+ locations from $16 to $20 an hour in April 2024, "
          "reduce fast-food employment? Estimates compare California with other states before and after the "
          "law, using BLS Quarterly Census of Employment and Wages data.")

if len(controls) < 2:
    st.warning("Select at least two control states.")
    st.stop()
if did.tq(post_start) <= did.tq(pre_end) or did.tq(pre_end) < did.tq(sample_start) + 3:
    st.warning("The pre-period needs at least four quarters and must end before the first treated quarter.")
    st.stop()

spec = did.Spec(treated, tuple(controls), did.OUTCOMES[outcome_name], did.SECTORS[sector_name],
                sample_start, pre_end, post_start, trend)
res = cached_did(spec)
syn = cached_synth(spec)
pct = lambda x: 100 * (np.exp(x) - 1)  # noqa: E731
xl = [did.lab(t) for t in res.gap.index]
sector_short = sector_name.split(" (")[0].lower()
outcome_lc = outcome_name.lower()

# ---------------------------------------------------------------- headline
c = st.columns(4)
c[0].metric("Difference-in-differences", f"{pct(res.est):+.1f}%")
c[1].metric("Permutation p-value", f"{res.p_perm:.2f}",
            help=f"Share of {len(res.placebo_est)} placebo states with an effect at least as large.")
c[2].metric("Synthetic control", f"{pct(syn['est']):+.1f}%", help=f"Permutation p = {syn['p']:.2f}")
if spec.outcome == "emp" and spec.sector != "ddd":
    c[3].metric("Implied jobs", f"{(np.exp(res.est) - 1) * res.base_level:+,.0f}",
                help=f"Applied to the pre-period average of {res.base_level:,.0f} workers.")
else:
    c[3].metric("Control states", len(res.placebo_est))

sig = res.p_perm < 0.10
ui.finding(
    f"{treated} {sector_short} {outcome_lc} was {abs(pct(res.est)):.1f}% "
    f"{'lower' if res.est < 0 else 'higher'} than the control group after the policy, relative to the "
    f"pre-period. "
    + (f"Only {res.p_perm:.0%} of placebo states show an effect this large, so the result is statistically "
       f"distinguishable from normal variation across states." if sig else
       f"{res.p_perm:.0%} of placebo states show an effect at least this large, so the result is not "
       f"statistically distinguishable from normal variation across states.")
)

tabs = st.tabs(["Trends", "Event study", "Placebo test", "Synthetic control", "Robustness", "Regression",
                "Methodology"])
SRC = (f"Source: BLS QCEW, private ownership, state level, {sample_start}–{xl[-1]}. "
       f"Seasonality removed with state × quarter-of-year effects estimated on the pre-period.")


def policy_lines(fig):
    fig.add_vrect(x0=xl.index(pre_end), x1=xl.index(post_start), fillcolor=LIGHT, opacity=0.6, line_width=0, layer="below",
                  annotation_text="Signed → effective", annotation_position="top left",
                  annotation_font=dict(size=11, color="#5A6872"))
    return fig


# ---------------------------------------------------------------- trends
with tabs[0]:
    ctrl_mean = res.R[[x for x in res.R.columns if x != treated]].mean(axis=1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xl, y=100 * ctrl_mean, name="Control-group average", line=dict(color=GREY, width=2)))
    fig.add_trace(go.Scatter(x=xl, y=100 * res.R[treated], name=treated, line=dict(color=NAVY, width=3)))
    policy_lines(fig)
    fig.update_layout(title=ui.exhibit(1, f"{treated} {sector_short} {outcome_lc} {'fell' if res.est < 0 else 'rose'} "
                                          f"{abs(pct(res.est)):.1f}% relative to the control group after the policy"),
                      yaxis_title="% deviation from pre-period mean", height=460)
    st.plotly_chart(fig, width="stretch")
    ui.source(SRC)

# ---------------------------------------------------------------- event study
with tabs[1]:
    P = res.placebo_gaps
    lo, hi = 100 * P.quantile(0.05, axis=1), 100 * P.quantile(0.95, axis=1)
    outside = int(((100 * res.gap < lo) | (100 * res.gap > hi))[res.post_mask].sum())
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xl + xl[::-1], y=list(hi) + list(lo[::-1]), fill="toself",
                             fillcolor="rgba(153,196,231,0.35)", line=dict(width=0),
                             name="90% range of placebo states", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=xl, y=100 * res.gap, mode="lines+markers", name=f"{treated} minus controls",
                             line=dict(color=NAVY, width=3), marker=dict(size=6)))
    fig.add_hline(y=0, line_color=GREY, line_width=1)
    policy_lines(fig)
    fig.update_layout(title=ui.exhibit(2, f"{outside} of {int(res.post_mask.sum())} post-policy quarters fall "
                                          f"outside the placebo range"),
                      yaxis_title="Gap vs. control group, %", height=460)
    st.plotly_chart(fig, width="stretch")
    ui.source("The shaded band contains 90% of the gaps obtained by assigning the policy to each control state "
              "in turn. A flat pre-period supports the parallel-trends assumption.")

# ---------------------------------------------------------------- placebo
with tabs[2]:
    pe = pct(res.placebo_est)
    allv = pd.concat([pe, pd.Series({treated: pct(res.est)})]).sort_values()
    rank = list(allv.index).index(treated) + 1
    fig = go.Figure(go.Bar(x=allv.index, y=allv.values,
                           marker_color=[NAVY if s == treated else SKY for s in allv.index]))
    fig.add_hline(y=0, line_color=GREY, line_width=1)
    fig.update_layout(title=ui.exhibit(3, f"{treated} ranks {rank} of {len(allv)} when each state is assigned "
                                          f"the policy (p = {res.p_perm:.2f})"),
                      yaxis_title="Estimated effect, %", height=440, showlegend=False)
    st.plotly_chart(fig, width="stretch")
    ui.source("Randomization inference (Abadie, Diamond and Hainmueller 2010; Conley and Taber 2011). "
              "With one treated state, this ranking is the appropriate significance test.")

# ---------------------------------------------------------------- synth
with tabs[3]:
    a, b = st.columns([2.2, 1], gap="large")
    with a:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=xl, y=100 * syn["synthetic"], name=f"Synthetic {treated}",
                                 line=dict(color=GREY, width=2, dash="dash")))
        fig.add_trace(go.Scatter(x=xl, y=100 * res.R[treated], name=treated, line=dict(color=NAVY, width=3)))
        policy_lines(fig)
        fig.update_layout(title=ui.exhibit(4, f"Synthetic control estimate: {pct(syn['est']):+.1f}% "
                                              f"(p = {syn['p']:.2f})"),
                          yaxis_title="% deviation from pre-period mean", height=440)
        st.plotly_chart(fig, width="stretch")
    with b:
        w = syn["weights"][syn["weights"] > 0.01].head(12)
        st.markdown("**Largest donor weights**")
        st.dataframe(w.rename("Weight").to_frame().style.format("{:.1%}"), width="stretch", height=380)
    ui.source("Weights are ridge-penalized (cf. Abadie and L'Hour 2021). With more donor states than pre-period "
              "quarters, unpenalized weights are not unique. Inference uses the post/pre RMSPE ratio across "
              f"{len(syn['ratios'])} placebo runs.")

# ---------------------------------------------------------------- robustness
with tabs[4]:
    sc = cached_curve(spec)
    sc["label"] = (sc.controls + " · " + sc.sector.str.split(" \\(").str[0] + " · from " + sc.sample_start +
                   np.where(sc.state_trends, " · trends", ""))
    neg = (sc.est_pct < 0).mean()
    nsig = int((sc.p_perm < 0.10).sum())
    fig = go.Figure(go.Scatter(
        x=list(range(1, len(sc) + 1)), y=sc.est_pct, mode="markers",
        marker=dict(size=9, color=np.where(sc.p_perm < 0.10, NAVY, SKY), line=dict(width=0)),
        text=sc.label + "<br>p = " + sc.p_perm.round(2).astype(str), hoverinfo="text+y"))
    fig.add_hline(y=0, line_color=GREY, line_width=1)
    fig.update_layout(title=ui.exhibit(5, f"{neg:.0%} of {len(sc)} specifications are negative; "
                                          f"{nsig} are significant at the 10% level"),
                      xaxis_title="Specification, sorted by estimate", yaxis_title="Effect, %", height=440)
    st.plotly_chart(fig, width="stretch")
    ui.source("Dark points: permutation p < 0.10. Specifications vary the control group, sector, sample start and "
              f"state trends, holding the outcome ({outcome_lc}) fixed.")
    st.dataframe(sc.drop(columns="label").rename(columns={
        "controls": "Control group", "sector": "Sector", "sample_start": "Sample start",
        "state_trends": "State trends", "est_pct": "Effect, %", "p_perm": "p-value", "n_controls": "Controls"})
        .style.format({"Effect, %": "{:+.2f}", "p-value": "{:.2f}"}), width="stretch", height=300)

# ---------------------------------------------------------------- regression
with tabs[5]:
    m = cached_twfe(spec)
    tbl = pd.DataFrame({"Two-way fixed effects": {
        "Treated × post (log points)": f"{m['b']:.4f}",
        "Effect (%)": f"{pct(m['b']):+.2f}",
        "Clustered standard error": f"{m['se']:.4f}",
        "Clustered p-value": f"{m['p']:.3f}",
        "Permutation p-value": f"{res.p_perm:.3f}",
        "Observations": f"{int(m['n']):,}",
        "Fixed effects": "State × quarter-of-year, quarter" + (", state trends" if trend else ""),
    }})
    st.table(tbl)
    st.markdown("Clustered standard errors assume many treated clusters. With one treated state they understate "
                "uncertainty (Conley and Taber 2011), which is why the clustered p-value is far smaller than the "
                "permutation p-value. Inference here is based on the permutation test.")

# ---------------------------------------------------------------- methodology
with tabs[6]:
    st.markdown(r"""
**Data.** BLS Quarterly Census of Employment and Wages, private ownership, state level. Treated sector: NAICS 722513
(limited-service restaurants). Within-state comparison: NAICS 722511 (full-service restaurants). Employment is the
mean of the three monthly counts in each quarter.

**Estimator.** For log outcome $y_{st}$, each state's quarter-of-year means (and optionally a linear trend) are
estimated on the pre-period only and removed, giving $\tilde y_{st}$. The gap and the estimate are

$$g_t = \tilde y_{\text{treated},t} - \frac{1}{N}\sum_{c} \tilde y_{c,t}, \qquad
\hat\delta = \bar g_{\text{post}} - \bar g_{\text{pre}}.$$

Quarters between signing and the effective date are excluded.

**Triple difference.** The outcome becomes $\ln(\text{limited-service}) - \ln(\text{full-service})$ within each
state, which removes shocks common to all restaurants in a state.

**Inference.** Each control state is assigned the policy in turn, and $\hat\delta$ is ranked against that
placebo distribution.

**Limitations.** QCEW includes limited-service restaurants exempt from AB 1228 (chains with fewer than 60
locations), which biases estimates toward zero. State-level data do not separate hours from headcount.
""")
