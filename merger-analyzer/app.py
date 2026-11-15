"""Merger Analyzer: acquirer EPS accretion/dilution and competitive effects.

Run:  streamlit run streamlit_app.py  (from the repository root)
"""
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).parent
for p in (HERE, HERE.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import merger as mg  # noqa: E402
import ui  # noqa: E402
from ui import BLUE, GREY, LIGHT, NAVY, RED, SKY  # noqa: E402

ss = st.session_state
PRESETS = {
    "Stock-and-cash strategic deal": dict(
        a=dict(price=80.0, shares=500.0, ni=2400.0, ebitda=4800.0, nd=6000.0, book=15000.0, g=5.0),
        t=dict(price=40.0, shares=250.0, ni=700.0, ebitda=1500.0, nd=2000.0, book=4000.0, g=5.0),
        premium=30.0, stock=50, cash=0.0, syn=150.0),
    "All-cash, debt-funded acquisition": dict(
        a=dict(price=120.0, shares=800.0, ni=4000.0, ebitda=7000.0, nd=5000.0, book=20000.0, g=4.0),
        t=dict(price=30.0, shares=200.0, ni=480.0, ebitda=1000.0, nd=1200.0, book=2500.0, g=6.0),
        premium=35.0, stock=0, cash=1500.0, syn=120.0),
}


def apply_preset():
    pr = PRESETS[ss.mg_preset]
    for side in ("a", "t"):
        for k, v in pr[side].items():
            ss[f"mg_{side}_{k}"] = v
    ss.mg_premium, ss.mg_stock, ss.mg_cash, ss.mg_syn = pr["premium"], pr["stock"], pr["cash"], pr["syn"]


if "mg_a_price" not in ss:
    ss.mg_preset = list(PRESETS)[0]
    apply_preset()

# ---------------------------------------------------------------- sidebar
sb = st.sidebar
sb.header("Case")
sb.selectbox("Illustrative case", list(PRESETS), key="mg_preset", on_change=apply_preset)
for side, label in (("a", "Acquirer"), ("t", "Target")):
    sb.header(label)
    c = sb.columns(2)
    c[0].number_input("Share price ($)", 0.5, 5000.0, key=f"mg_{side}_price", step=1.0)
    c[1].number_input("Diluted shares (M)", 1.0, 50000.0, key=f"mg_{side}_shares", step=10.0)
    c = sb.columns(2)
    c[0].number_input("Net income, NTM ($M)", 1.0, 1e6, key=f"mg_{side}_ni", step=50.0)
    c[1].number_input("EBITDA, NTM ($M)", 1.0, 1e6, key=f"mg_{side}_ebitda", step=50.0)
    c = sb.columns(3)
    c[0].number_input("Net debt", -1e6, 1e6, key=f"mg_{side}_nd", step=100.0)
    c[1].number_input("Book equity", 0.0, 1e6, key=f"mg_{side}_book", step=100.0)
    c[2].number_input("Growth %", -20.0, 50.0, key=f"mg_{side}_g", step=0.5)
sb.header("Terms")
c = sb.columns(2)
c[0].number_input("Premium %", 0.0, 150.0, key="mg_premium", step=5.0)
c[1].slider("Stock consideration %", 0, 100, key="mg_stock", step=5)
c = sb.columns(2)
c[0].number_input("Run-rate synergies ($M)", 0.0, 1e5, key="mg_syn", step=10.0, help="Pre-tax; 50% in year 1")
c[1].number_input("Cash on hand used ($M)", 0.0, 1e6, key="mg_cash", step=100.0)
c = sb.columns(2)
debt_rate = c[0].number_input("Cost of new debt %", 0.0, 20.0, 6.5, 0.25)
tax = c[1].number_input("Tax rate %", 0.0, 50.0, 25.0, 1.0)
c = sb.columns(2)
intang = c[0].number_input("Intangibles % of excess", 0.0, 100.0, 30.0, 5.0,
                           help="Share of the purchase price above book value allocated to amortizable intangibles")
life = c[1].number_input("Amortization life (yrs)", 1, 40, 10)
incl_integ = sb.checkbox("Include integration costs in EPS", False,
                         help="Adjusted EPS conventionally excludes one-time costs ($150M in year 1, $75M in year 2).")


def company(side, name):
    g = lambda k: ss[f"mg_{side}_{k}"]  # noqa: E731
    return mg.Company(name, g("price"), g("shares"), g("ni"), g("ebitda"), g("nd"), g("book"), g("g") / 100)


deal = mg.Deal(company("a", "Acquirer"), company("t", "Target"), premium=ss.mg_premium / 100,
               pct_stock=ss.mg_stock / 100, balance_sheet_cash=ss.mg_cash, debt_rate=debt_rate / 100,
               tax_rate=tax / 100, synergies=ss.mg_syn, include_integration=incl_integ,
               intangible_pct=intang / 100, intangible_life=int(life))
r = mg.analyze(deal)
yrs = r.years

ui.header("Mergers and acquisitions", "Merger Analyzer",
          "Two views of the same transaction: whether it adds to the acquirer's earnings per share, and whether "
          "it reduces competition. The deal model covers financing, purchase-price amortization and synergies; "
          "the competition model applies the 2023 Merger Guidelines screens and simulates post-merger prices. "
          "Cases are illustrative; all inputs are editable. Figures in $ millions unless noted.")

deal_tab, comp_tab = st.tabs(["Deal economics", "Competitive effects"])

# =============================================================== deal economics
with deal_tab:
    acc2 = yrs.loc[2, "accretion"]
    be2 = r.breakeven_synergies.loc[2]
    k = st.columns(5)
    k[0].metric("EPS impact, year 2", f"{acc2:+.1%}")
    k[1].metric("Breakeven synergies", f"${be2:,.0f}M", help="Run-rate pre-tax synergies for zero dilution in year 2")
    k[2].metric("Target holders' ownership", f"{r.target_ownership:.1%}")
    k[3].metric("Pro forma net debt / EBITDA", f"{r.leverage:.1f}x")
    k[4].metric("EV / EBITDA paid", f"{r.multiples['EV / EBITDA']:.1f}x")

    word = "accretive" if acc2 > 0 else "dilutive"
    gap = ss.mg_syn - be2
    ui.finding(
        f"The deal is {abs(acc2):.1%} {word} to earnings per share in year 2. It needs ${be2:,.0f}M of run-rate "
        f"synergies to break even, {'below' if gap >= 0 else 'above'} the ${ss.mg_syn:,.0f}M assumed. "
        f"At a {deal.premium:.0%} premium, the acquirer pays ${-r.value_created['Premium paid']:,.0f}M over market "
        f"value; capitalized synergies are worth ${r.value_created['Capitalized synergies']:,.0f}M.")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        x = [f"Year {y}" for y in yrs.index]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=x, y=yrs.standalone_eps, name="Acquirer standalone", marker_color=GREY))
        fig.add_trace(go.Bar(x=x, y=yrs.pro_forma_eps, name="Pro forma", marker_color=NAVY,
                             text=[f"{a:+.1%}" for a in yrs.accretion], textposition="outside"))
        fig.update_layout(barmode="group", title=ui.exhibit(1, f"Pro forma EPS is {word} in year 2 "
                                                               f"({acc2:+.1%})"),
                          yaxis_title="EPS ($)", height=420)
        st.plotly_chart(fig, width="stretch")
    with c2:
        y2 = yrs.loc[2]
        items = ["acquirer_ni", "target_ni", "Synergies", "Interest on new debt", "Forgone interest on cash",
                 "Financing fee amortization", "Intangible amortization", "Integration costs"]
        labels = ["Acquirer", "Target", "Synergies", "New debt interest", "Forgone interest", "Fee amortization",
                  "Intangible amortization", "Integration costs"]
        keep = [(lab, y2[i]) for lab, i in zip(labels, items) if abs(y2[i]) > 1e-9]
        fig = go.Figure(go.Waterfall(
            x=[k_ for k_, _ in keep] + ["Pro forma"], y=[v for _, v in keep] + [y2.pro_forma_ni],
            measure=["relative"] * len(keep) + ["total"],
            text=[f"–{-v:,.0f}" if v < 0 else f"{v:,.0f}" for _, v in keep] + [f"{y2.pro_forma_ni:,.0f}"],
            textposition="outside", increasing=dict(marker=dict(color=NAVY)),
            decreasing=dict(marker=dict(color=RED)), totals=dict(marker=dict(color=GREY)),
            connector=dict(line=dict(color=GREY, width=1))))
        costs = -(y2["Interest on new debt"] + y2["Forgone interest on cash"] + y2["Financing fee amortization"]
                  + y2["Intangible amortization"] + y2["Integration costs"])
        t2 = (f"Financing and amortization costs (${costs:,.0f}M) exceed synergies (${y2['Synergies']:,.0f}M)"
              if costs > y2["Synergies"] else
              f"Synergies (${y2['Synergies']:,.0f}M) exceed financing and amortization costs (${costs:,.0f}M)")
        fig.update_layout(title=ui.exhibit(2, t2), yaxis_title="$M, after tax", height=420, showlegend=False)
        st.plotly_chart(fig, width="stretch")
    ui.source(f"Pro forma shares: {deal.acquirer.shares:,.0f}M existing + {r.new_shares:,.0f}M issued at "
              f"${deal.acquirer.price:,.2f}. Synergies phase in at 50% in year 1. Adjusted EPS "
              f"{'includes' if incl_integ else 'excludes'} one-time integration costs.")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**Transaction summary**")
        summ = pd.DataFrame({"Value": {
            "Offer price per share": f"${deal.offer_price:,.2f}",
            "Offer equity value": f"${deal.equity_value:,.0f}M",
            "Enterprise value": f"${deal.enterprise_value:,.0f}M",
            "EV / EBITDA": f"{r.multiples['EV / EBITDA']:.1f}x",
            "Offer P/E vs. acquirer P/E": f"{r.multiples['Offer P/E']:.1f}x vs. {deal.acquirer.pe:.1f}x",
            "Stock issued": f"${r.funding['Acquirer stock issued']:,.0f}M ({r.new_shares:,.0f}M shares)",
            "New debt": f"${r.new_debt:,.0f}M",
            "Cash on hand used": f"${r.funding['Balance-sheet cash']:,.0f}M",
            "Pro forma net debt / EBITDA": f"{r.leverage:.1f}x",
        }})
        st.table(summ)
    with c2:
        vc = r.value_created
        fig = go.Figure(go.Waterfall(
            x=list(vc.index), y=list(vc.values), measure=["relative"] * 3 + ["total"],
            text=[f"–{-v:,.0f}" if v < 0 else f"{v:,.0f}" for v in vc.values], textposition="outside",
            increasing=dict(marker=dict(color=NAVY)), decreasing=dict(marker=dict(color=RED)),
            totals=dict(marker=dict(color=NAVY if vc.iloc[-1] >= 0 else RED)),
            connector=dict(line=dict(color=GREY, width=1))))
        fig.update_layout(title=ui.exhibit(3, f"Net value to acquirer shareholders: "
                                              f"{'+' if vc.iloc[-1] >= 0 else '–'}${abs(vc.iloc[-1]):,.0f}M"),
                          yaxis_title="$M", height=400, showlegend=False)
        st.plotly_chart(fig, width="stretch")
        ui.source("Synergies capitalized at the acquirer's P/E after tax. One-time costs include integration, "
                  "advisory and financing fees.")

    def heat(g, title, fx, fy, xt, yt):
        z = g.values.astype(float) * 100
        fig = go.Figure(go.Heatmap(z=z, x=[fx(v) for v in g.columns], y=[fy(v) for v in g.index],
                                   text=[[f"{v:+.1f}%" for v in row] for row in z], texttemplate="%{text}",
                                   colorscale=[[0, "#F2D7D5"], [0.5, "#FFFFFF"], [1, "#B9C9F5"]], zmid=0,
                                   showscale=False, xgap=2, ygap=2))
        fig.update_layout(title=title, height=380, xaxis_title=xt, yaxis_title=yt,
                          xaxis=dict(type="category"), yaxis=dict(showgrid=False, type="category"))
        return fig

    c1, c2 = st.columns(2, gap="large")
    prem = tuple(np.round(np.arange(0.10, 0.51, 0.10), 2))
    stock = (0.0, 0.25, 0.5, 0.75, 1.0)
    g1 = mg.accretion_grid(deal, "premium", prem, "pct_stock", stock)
    c1.plotly_chart(heat(g1, ui.exhibit(4, "Year-2 EPS impact by premium and stock mix"),
                         lambda v: f"{v:.0%}", lambda v: f"{v:.0%}", "Stock consideration", "Premium"),
                    width="stretch")
    base_syn = max(ss.mg_syn, 50.0)
    syn = tuple(np.round(np.linspace(0, 2 * base_syn, 5), 0))
    g2 = mg.accretion_grid(deal, "premium", prem, "synergies", syn)
    c2.plotly_chart(heat(g2, ui.exhibit(5, "Year-2 EPS impact by premium and synergies"),
                         lambda v: f"${v:,.0f}M", lambda v: f"{v:.0%}", "Run-rate synergies", "Premium"),
                    width="stretch")
    ui.source("Blue cells are accretive, red cells dilutive. In an all-stock deal without synergies, the deal is "
              "accretive only if the acquirer's P/E exceeds the P/E paid for the target.")

# =============================================================== competition
with comp_tab:
    st.markdown("**Market.** Enter each firm's share of the relevant market and its average price. Shares are "
                "rescaled to 100%.")
    ss.setdefault("mg_market", pd.DataFrame({
        "Firm": ["Firm A", "Firm B", "Firm C", "Firm D", "Firm E"],
        "Share %": [30.0, 22.0, 20.0, 16.0, 12.0],
        "Price ($)": [4.00, 3.90, 3.70, 3.60, 3.40],
    }))
    mk = st.data_editor(ss.mg_market, num_rows="dynamic", hide_index=True, width="stretch", key="mg_mk_editor")
    mk = mk.dropna().query("`Share %` > 0 and `Price ($)` > 0").reset_index(drop=True)
    if len(mk) < 3 or mk.Firm.duplicated().any():
        st.warning("Enter at least three firms with unique names, positive shares and positive prices.")
        st.stop()
    firms = list(mk.Firm)
    c = st.columns(5)
    fa = c[0].selectbox("Merging firm 1", firms, index=0)
    fb = c[1].selectbox("Merging firm 2", [f_ for f_ in firms if f_ != fa], index=0)
    margin = c[2].number_input(f"{fa} gross margin %", 5.0, 90.0, 35.0, 1.0,
                               help="Price-cost margin used to calibrate how price-sensitive consumers are") / 100
    outside = c[3].number_input("Outside-option share %", 1.0, 80.0, 20.0, 1.0,
                                help="Share of consumers who buy none of these products") / 100
    rev = c[4].number_input("Market revenue ($M)", 10.0, 1e6, 10000.0, 500.0)
    eff = st.slider("Marginal-cost savings at merging firms %", 0.0, 40.0, 0.0, 1.0) / 100

    ia, ib = firms.index(fa), firms.index(fb)
    shares = pd.Series(mk["Share %"].values, index=firms)
    conc = mg.concentration(shares, fa, fb)
    try:
        lm = mg.LogitMarket(firms, mk["Share %"].values, mk["Price ($)"].values, margin_firm=ia, margin=margin,
                            outside=outside, market_revenue=rev)
    except ValueError as e:
        st.error(str(e))
        st.stop()
    sim = lm.simulate(ia, ib, eff)
    margins = 1 - lm.cost / lm.prices
    d_ab, d_ba = lm.s[ib] / (1 - lm.s[ia]), lm.s[ia] / (1 - lm.s[ib])
    g_a = mg.guppi(d_ab, margins[ib], lm.prices[ib], lm.prices[ia])
    g_b = mg.guppi(d_ba, margins[ia], lm.prices[ia], lm.prices[ib])
    cm = mg.cmcr(margins[ia], margins[ib], d_ab, d_ba, lm.prices[ia], lm.prices[ib])
    offset = lm.offsetting_efficiency(ia, ib)
    dp_merged = (sim["prices"][[ia, ib]] * sim["shares_post"][[ia, ib]]).sum() / \
        (lm.prices[[ia, ib]] * sim["shares_post"][[ia, ib]]).sum() - 1

    k = st.columns(5)
    k[0].metric("HHI, post-merger", f"{conc['post']:,.0f}")
    k[1].metric("Change in HHI", f"+{conc['delta']:,.0f}")
    k[2].metric("GUPPI, higher of two", f"{max(g_a, g_b):.1%}",
                help=f"Gross upward pricing pressure: {fa} {g_a:.1%}, {fb} {g_b:.1%}. Values above about 5% "
                     f"typically warrant closer review.")
    k[3].metric("Price change, merging firms", f"{dp_merged:+.1%}")
    k[4].metric("Consumer surplus change", f"{'+' if sim['delta_cs'] >= 0 else '–'}${abs(sim['delta_cs']):,.0f}M")

    pres = ("is presumed to substantially lessen competition under the 2023 Merger Guidelines "
            f"({conc['reason']})") if conc["presumption"] else "falls below the structural presumption of the 2023 Merger Guidelines"
    ui.finding(
        f"A {fa}–{fb} merger {pres}. The simulation predicts a {dp_merged:+.1%} price change at the merging firms "
        f"and a ${abs(sim['delta_cs']):,.0f}M {'loss' if sim['delta_cs'] < 0 else 'gain'} in consumer surplus "
        f"{'with no cost savings' if eff == 0 else f'with {eff:.0%} cost savings'}. Marginal-cost savings of "
        f"{offset:.0%} would be needed to leave consumers no worse off.")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        xs = np.linspace(0, max(800, conc["delta"] * 1.4), 50)
        fig = go.Figure()
        fig.add_shape(type="rect", x0=100, x1=xs.max(), y0=1800, y1=max(10000, conc["post"] * 1.1),
                      fillcolor="rgba(192,80,77,0.10)", line_width=0, layer="below")
        fig.add_annotation(x=xs.max(), y=max(10000, conc["post"] * 1.1), text="Presumed anticompetitive",
                           showarrow=False, xanchor="right", yanchor="top", font=dict(size=11, color=RED))
        fig.add_hline(y=1800, line_color=GREY, line_dash="dot")
        fig.add_vline(x=100, line_color=GREY, line_dash="dot")
        fig.add_trace(go.Scatter(x=[conc["delta"]], y=[conc["post"]], mode="markers+text",
                                 marker=dict(size=14, color=NAVY), text=[f"{fa} + {fb}"],
                                 textposition="top center", showlegend=False))
        fig.update_layout(title=ui.exhibit(6, f"Post-merger HHI of {conc['post']:,.0f}, up {conc['delta']:,.0f}"),
                          xaxis_title="Change in HHI", yaxis_title="Post-merger HHI", height=420,
                          yaxis=dict(range=[0, max(10000, conc["post"] * 1.1)]))
        st.plotly_chart(fig, width="stretch")
    with c2:
        pc = pd.Series(sim["price_change"], index=firms)
        fig = go.Figure(go.Bar(x=pc.index, y=pc.values * 100,
                               marker_color=[NAVY if f_ in (fa, fb) else SKY for f_ in pc.index],
                               text=[f"{v:+.1%}" for v in pc.values], textposition="outside"))
        fig.add_hline(y=0, line_color=GREY, line_width=1)
        top_ = max(pc.max() * 100, 0.5)
        fig.update_layout(title=ui.exhibit(7, f"Merging firms raise prices {pc[[fa, fb]].min():.0%}–"
                                              f"{pc[[fa, fb]].max():.0%}; rivals follow by under "
                                              f"{max(pc.drop([fa, fb]).max(), 0.001):.1%}"),
                          yaxis_title="Price change (%)", height=420, showlegend=False,
                          yaxis=dict(range=[min(pc.min() * 100 * 1.25, 0), top_ * 1.22]))
        st.plotly_chart(fig, width="stretch")
    ui.source("Logit demand calibrated to observed shares, prices and one margin; Bertrand price competition before "
              "and after the merger. Rivals raise prices less than the merging firms (strategic complements).")

    effs = np.linspace(0, 0.4, 21)
    dcs = [lm.simulate(ia, ib, e_)["delta_cs"] for e_ in effs]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=effs * 100, y=dcs, mode="lines", line=dict(color=NAVY, width=3), showlegend=False))
    fig.add_hline(y=0, line_color=GREY, line_width=1)
    fig.add_vline(x=offset * 100, line_color=BLUE, line_dash="dash",
                  annotation_text=f"Break-even savings: {offset:.0%}", annotation_position="bottom right")
    fig.update_layout(title=ui.exhibit(8, f"Consumers are harmed unless merging-firm costs fall at least "
                                          f"{offset:.0%}"),
                      xaxis_title="Marginal-cost savings at merging firms (%)",
                      yaxis_title="Change in consumer surplus ($M)", height=380)
    st.plotly_chart(fig, width="stretch")

    tbl = pd.DataFrame({
        "Diversion to partner": [d_ab, d_ba],
        "Implied margin": [margins[ia], margins[ib]],
        "GUPPI": [g_a, g_b],
        "Compensating cost reduction": list(cm),
        "Simulated price change": [sim["price_change"][ia], sim["price_change"][ib]],
    }, index=[fa, fb])
    st.dataframe(tbl.style.format("{:.1%}"), width="stretch")
    ui.source("Diversion ratios follow from logit substitution (proportional to shares). Compensating marginal "
              "cost reductions follow Werden (1996): the cost savings that would keep pre-merger prices unchanged.")

    with st.expander("Methodology"):
        st.markdown(r"""
**Concentration.** HHI is the sum of squared market shares (in percent). Under the 2023 Merger Guidelines, a merger
is presumed to substantially lessen competition if the post-merger HHI exceeds 1,800 and rises by more than 100, or
if the merged firm's share exceeds 30% and the HHI rises by more than 100.

**Upward pricing pressure.** For merging products 1 and 2 with diversion ratio $D_{12}$, margin $m_2$ and prices
$p_1, p_2$: $\text{GUPPI}_1 = D_{12}\, m_2\, p_2/p_1$.

**Merger simulation.** Logit demand $s_j = e^{\delta_j - \alpha p_j}/(1 + \sum_k e^{\delta_k - \alpha p_k})$.
The price coefficient $\alpha$ is calibrated from one firm's margin through its pricing condition
$p_j - c_j = 1/[\alpha(1 - s_j)]$; marginal costs and quality terms $\delta_j$ then follow from observed prices and
shares. After the merger, each product of the merged firm carries markup $1/[\alpha(1 - S_F)]$, where $S_F$ is the
firm's combined share, and the new equilibrium is solved numerically. Consumer surplus is
$\frac{N}{\alpha}\ln\left(1 + \sum_j e^{\delta_j - \alpha p_j}\right)$.

**Deal model.** Pro forma net income adds the target's earnings, after-tax synergies, and after-tax interest,
fee amortization and amortization of acquired intangibles. Pro forma shares add the stock issued at the
acquirer's price. Breakeven synergies solve for zero EPS dilution.
""")
