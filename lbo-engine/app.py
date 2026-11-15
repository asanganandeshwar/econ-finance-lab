"""LBO Engine: five-year leveraged buyout model.

Run:  streamlit run streamlit_app.py  (from the repository root)
"""
import io
import json
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
import lbo  # noqa: E402
import ui  # noqa: E402
from ui import BLUE, CYAN, GREEN, GREY, NAVY, RED, SKY  # noqa: E402

ss = st.session_state
DEFAULTS = dict(name="Target Co.", rev=250.0, m0=20.0, m1=23.0, g1=8.0, g5=5.0, entry=9.5, exit=9.5,
                da=3.0, capex=3.5, nwc=10.0, tax=25.0, txn=2.0, finfee=2.5, cash=10.0, sweep=75,
                rcf=40.0, pool=8.0, target=20.0)
for key, val in DEFAULTS.items():
    ss.setdefault(f"lbo_{key}", val)
ss.setdefault("lbo_tranches", pd.DataFrame([
    {"Tranche": "Term Loan B", "x EBITDA": 4.0, "Rate %": 8.5, "Amort %": 1.0, "Sweep": True, "PIK %": 0.0},
    {"Tranche": "Senior Notes", "x EBITDA": 1.5, "Rate %": 9.5, "Amort %": 0.0, "Sweep": False, "PIK %": 0.0},
]))

# ---------------------------------------------------------------- sidebar
sb = st.sidebar
sb.header("Transaction")
sb.text_input("Company", key="lbo_name")
sb.number_input("LTM revenue ($M)", 1.0, 100000.0, key="lbo_rev", step=10.0)
c = sb.columns(2)
c[0].number_input("Entry EV/EBITDA", 2.0, 40.0, key="lbo_entry", step=0.5)
c[1].number_input("Exit EV/EBITDA", 2.0, 40.0, key="lbo_exit", step=0.5)
sb.header("Operations")
c = sb.columns(2)
c[0].number_input("Entry margin %", 1.0, 80.0, key="lbo_m0", step=0.5)
c[1].number_input("Exit margin %", 1.0, 80.0, key="lbo_m1", step=0.5)
c = sb.columns(2)
c[0].number_input("Growth, year 1 %", -50.0, 100.0, key="lbo_g1", step=0.5)
c[1].number_input("Growth, year 5 %", -50.0, 100.0, key="lbo_g5", step=0.5)
c = sb.columns(3)
c[0].number_input("D&A %", 0.0, 30.0, key="lbo_da", step=0.5, help="% of revenue")
c[1].number_input("Capex %", 0.0, 40.0, key="lbo_capex", step=0.5, help="% of revenue")
c[2].number_input("NWC %", 0.0, 60.0, key="lbo_nwc", step=1.0, help="% of incremental revenue")
sb.header("Financing")
c = sb.columns(2)
c[0].number_input("Tax rate %", 0.0, 50.0, key="lbo_tax", step=1.0)
c[1].number_input("Minimum cash ($M)", 0.0, 10000.0, key="lbo_cash", step=1.0)
c = sb.columns(2)
c[0].number_input("Deal fees % EV", 0.0, 10.0, key="lbo_txn", step=0.25)
c[1].number_input("Financing fees %", 0.0, 10.0, key="lbo_finfee", step=0.25, help="% of funded debt")
c = sb.columns(2)
c[0].number_input("Revolver ($M)", 0.0, 10000.0, key="lbo_rcf", step=5.0)
c[1].slider("Cash sweep %", 0, 100, key="lbo_sweep")
c = sb.columns(2)
c[0].number_input("Mgmt. promote %", 0.0, 30.0, key="lbo_pool", step=1.0, help="Share of the equity gain")
c[1].number_input("Target IRR %", 5.0, 50.0, key="lbo_target", step=1.0)

ui.header("Private equity", "LBO Engine",
          "A five-year leveraged buyout model: sources and uses, a tranche-level debt schedule with cash sweep, "
          "returns, an exact value-creation bridge, sensitivities and Monte Carlo exit risk. "
          "All figures in $ millions.")

with st.expander("Load inputs from a CIM Analyzer memo"):
    st.caption("Upload or paste the JSON output of the CIM Analyzer. Revenue, EBITDA margin, growth and the "
               "sector EV/EBITDA range populate the model; every input can be adjusted afterward.")
    st.file_uploader("CIM Analyzer JSON", type="json", label_visibility="collapsed", key="lbo_cim_file")
    st.text_area("JSON", height=100, label_visibility="collapsed", key="lbo_cim_txt",
                 placeholder='{"financial_highlights": {"revenue": "$45M", "ebitda": "$12M / 27%"}, ...}')

    def load_cim():
        """Runs as a callback, before widgets are drawn, so their values can be updated."""
        ss.lbo_cim_error = None
        try:
            f = ss.get("lbo_cim_file")
            memo = json.load(f) if f else json.loads(ss.get("lbo_cim_txt") or "")
            d, notes = lbo.from_cim(memo)
        except Exception as e:  # noqa: BLE001
            ss.lbo_cim_error = f"Could not read the memo: {e}"
            return
        ss.lbo_name, ss.lbo_rev = d.name, float(d.ltm_revenue)
        ss.lbo_m0, ss.lbo_m1 = round(d.entry_margin * 100, 1), round(d.exit_margin * 100, 1)
        ss.lbo_g1, ss.lbo_g5 = round(d.growth[0] * 100, 1), round(d.growth[-1] * 100, 1)
        ss.lbo_entry = ss.lbo_exit = round(d.entry_multiple, 1)
        ss.lbo_cash = round(max(2.0, 0.04 * d.ltm_revenue), 1)
        ss.lbo_rcf = round(max(5.0, 0.15 * d.ltm_revenue), 1)
        ss.lbo_notes = notes

    st.button("Load inputs", on_click=load_cim)
    if ss.get("lbo_cim_error"):
        st.error(ss.lbo_cim_error)
    for n_ in ss.get("lbo_notes", []):
        st.markdown(f"- {n_}")

st.markdown("**Capital structure.** Edit, add or remove tranches. The cash sweep repays eligible tranches in order.")
tr = st.data_editor(ss.lbo_tranches, num_rows="dynamic", width="stretch", key="lbo_tr_editor", hide_index=True,
                    column_config={"Sweep": st.column_config.CheckboxColumn()})
tr = tr.dropna(subset=["Tranche"]).fillna({"x EBITDA": 0.0, "Rate %": 0.0, "Amort %": 0.0, "Sweep": False,
                                           "PIK %": 0.0})
tranches = [lbo.Tranche(row["Tranche"], float(row["x EBITDA"]), float(row["Rate %"]) / 100,
                        float(row["Amort %"]) / 100, bool(row["Sweep"]), float(row["PIK %"]) / 100)
            for _, row in tr.iterrows() if float(row["x EBITDA"]) > 0]
if not tranches:
    st.warning("Add at least one debt tranche.")
    st.stop()

deal = lbo.Deal(
    name=ss.lbo_name, ltm_revenue=ss.lbo_rev, entry_margin=ss.lbo_m0 / 100, exit_margin=ss.lbo_m1 / 100,
    growth=tuple(np.linspace(ss.lbo_g1, ss.lbo_g5, 5) / 100), entry_multiple=ss.lbo_entry,
    exit_multiple=ss.lbo_exit, da_pct=ss.lbo_da / 100, capex_pct=ss.lbo_capex / 100, nwc_pct=ss.lbo_nwc / 100,
    tax_rate=ss.lbo_tax / 100, txn_fee_pct=ss.lbo_txn / 100, fin_fee_pct=ss.lbo_finfee / 100,
    min_cash=ss.lbo_cash, sweep_pct=ss.lbo_sweep / 100, revolver_size=ss.lbo_rcf, mgmt_pool=ss.lbo_pool / 100,
    tranches=tranches)

try:
    r = lbo.run(deal)
except ValueError as e:
    st.error(str(e))
    st.stop()

target = ss.lbo_target / 100
KEY = repr(deal)


@st.cache_data(show_spinner=False, max_entries=128)
def cached_max(key, _deal, target):
    return lbo.max_entry_multiple(_deal, target)


@st.cache_data(show_spinner=False, max_entries=128)
def cached_grid(key, _deal, row, rows, col, cols):
    return lbo.grid(_deal, row, list(rows), col, list(cols))


@st.cache_data(show_spinner="Simulating", max_entries=32)
def cached_mc(key, _deal, n, xsd, gsd, msd):
    return lbo.monte_carlo(_deal, n, xsd, gsd, msd)


max_m = cached_max(KEY, deal, target)
lev0 = sum(t.multiple for t in tranches)
e0 = deal.ltm_revenue * deal.entry_margin

# ---------------------------------------------------------------- headline
k = st.columns(5)
k[0].metric("IRR", f"{r.irr:.1%}")
k[1].metric("MOIC", f"{r.moic:.2f}x")
k[2].metric("Sponsor equity", f"${r.entry_equity:,.0f}M")
k[3].metric("Leverage, entry → exit", f"{lev0:.1f}x → {r.credit['Total leverage (x)'].iloc[-1]:.1f}x")
k[4].metric(f"Max. entry for {target:.0%} IRR", f"{max_m:.1f}x" if max_m else "n/a",
            help="Highest entry EV/EBITDA that still earns the target IRR at the same exit multiple. "
                 "Leverage is capped at 65% of enterprise value.")

b = r.bridge
drivers = b.drop(["Entry equity", "Exit equity"])
gain = b["Exit equity"] - b["Entry equity"]
top = drivers.idxmax()
price_line = (f"At {deal.entry_multiple:.1f}x the deal clears the {target:.0%} hurdle; the maximum price is "
              f"{max_m:.1f}x." if max_m and max_m >= deal.entry_multiple else
              f"The deal misses the {target:.0%} hurdle; the maximum price for that return is {max_m:.1f}x."
              if max_m else f"No tested entry price reaches a {target:.0%} IRR.")
ui.finding(f"{deal.name} generates {r.moic:.2f}x and a {r.irr:.1%} IRR over five years. "
           f"{top} accounts for {drivers[top] / gain:.0%} of the ${gain:,.0f}M equity gain. {price_line}")

tabs = st.tabs(["Value creation", "Sources and uses", "Operating model", "Debt schedule", "Sensitivities",
                "Monte Carlo", "Methodology"])

# ---------------------------------------------------------------- bridge
with tabs[0]:
    fig = go.Figure(go.Waterfall(
        x=list(b.index), y=list(b.values), measure=["absolute"] + ["relative"] * len(drivers) + ["total"],
        text=[f"–${-v:,.0f}" if v < 0 else f"${v:,.0f}" for v in b.values], textposition="outside",
        increasing=dict(marker=dict(color=NAVY)), decreasing=dict(marker=dict(color=RED)),
        totals=dict(marker=dict(color=GREY)), connector=dict(line=dict(color=GREY, width=1))))
    fig.update_layout(title=ui.exhibit(1, f"{top} drives most of the {r.moic:.1f}x return"),
                      yaxis_title="$M", height=470, showlegend=False)
    st.plotly_chart(fig, width="stretch")
    ui.source("EBITDA growth is valued at the entry multiple, multiple expansion at exit EBITDA, and deleveraging "
              "is the reduction in net debt. Components sum exactly to exit equity.")

# ---------------------------------------------------------------- S&U
with tabs[1]:
    a, c2 = st.columns(2, gap="large")
    src, use = r.su.Sources.dropna(), r.su.Uses.dropna()
    order = [t.name for t in tranches] + ["Sponsor equity"]
    src = src.reindex([x for x in order if x in src.index])
    use = use.reindex(["Purchase enterprise value", "Transaction fees", "Financing fees", "Cash to balance sheet"])
    a.markdown("**Sources**")
    a.dataframe(pd.DataFrame({"$M": src, "% of total": src / src.sum(), "x EBITDA": src / e0})
                .style.format({"$M": "{:,.1f}", "% of total": "{:.1%}", "x EBITDA": "{:.2f}x"}), width="stretch")
    c2.markdown("**Uses**")
    c2.dataframe(pd.DataFrame({"$M": use, "% of total": use / use.sum()})
                 .style.format({"$M": "{:,.1f}", "% of total": "{:.1%}"}), width="stretch")
    ui.source(f"Purchase enterprise value = LTM EBITDA of ${e0:,.1f}M × {deal.entry_multiple:.1f}x, on a "
              f"cash-free, debt-free basis. Sponsor equity is {r.entry_equity / use.sum():.0%} of total uses.")

# ---------------------------------------------------------------- operating model
with tabs[2]:
    p = r.pnl
    show = pd.DataFrame({
        "Revenue": p.revenue, "Growth (%)": p.growth * 100, "EBITDA": p.ebitda, "EBITDA margin (%)": p.margin * 100,
        "D&A": -p.da, "EBIT": p.ebit, "Cash interest": -p.cash_interest, "PIK interest": -p.pik_interest,
        "Taxes": -p.taxes, "Capital expenditures": -p.capex, "Change in NWC": -p.change_nwc,
        "Levered free cash flow": p.levered_fcf, "Mandatory amortization": -p.mandatory_amort,
        "Cash sweep": -p.sweep,
    }).T
    show.columns = [f"Year {y}" for y in show.columns]
    st.dataframe(show.style.format("{:,.1f}"), width="stretch", height=530)

# ---------------------------------------------------------------- debt
with tabs[3]:
    dbt = r.debt
    lev = r.credit["Total leverage (x)"]
    fig = go.Figure()
    shades = [NAVY, BLUE, CYAN, SKY, GREY]
    for i, n_ in enumerate([t.name for t in tranches] + ["Revolver"]):
        if dbt[n_].abs().sum() > 0:
            fig.add_trace(go.Bar(x=[f"Year {y}" for y in dbt.index], y=dbt[n_], name=n_,
                                 marker_color=shades[i % len(shades)]))
    fig.add_trace(go.Scatter(x=[f"Year {y}" for y in lev.index], y=lev, name="Total leverage (x)", yaxis="y2",
                             mode="lines+markers+text", text=[f"{v:.1f}x" for v in lev], textposition="top center",
                             line=dict(color=RED, width=2)))
    paid = 1 - dbt.total_debt.iloc[-1] / dbt.total_debt.iloc[0]
    fig.update_layout(barmode="stack", title=ui.exhibit(2, f"{paid:.0%} of acquisition debt is repaid by exit; "
                                                           f"leverage falls to {lev.iloc[-1]:.1f}x"),
                      yaxis_title="$M", height=460,
                      yaxis2=dict(overlaying="y", side="right", title="x EBITDA", rangemode="tozero", showgrid=False))
    st.plotly_chart(fig, width="stretch")
    cov = st.number_input("Maximum total leverage covenant (x)", 1.0, 15.0, max(6.0, round(lev0 + 0.75, 1)), 0.25)
    cr = r.credit.copy()
    cr["Covenant headroom"] = 1 - cr["Total leverage (x)"] / cov
    cr.index = [f"Year {y}" for y in cr.index]
    st.dataframe(cr.T.style.format("{:.2f}"), width="stretch")
    if (cr["Covenant headroom"] < 0).any():
        st.error(f"Covenant breached in {', '.join(cr.index[cr['Covenant headroom'] < 0])}.")

# ---------------------------------------------------------------- sensitivities
with tabs[4]:
    def heat(g, title, fmt_r, fmt_c, ytitle, xtitle):
        z = g.values.astype(float)
        fig = go.Figure(go.Heatmap(
            z=z * 100, x=[fmt_c(v) for v in g.columns], y=[fmt_r(v) for v in g.index],
            text=[[f"{v:.1%}" if np.isfinite(v) else "" for v in row] for row in z], texttemplate="%{text}",
            colorscale=[[0, "#F2D7D5"], [0.5, "#FFFFFF"], [1, "#B9C9F5"]], zmid=target * 100, showscale=False,
            xgap=2, ygap=2))
        fig.update_layout(title=title, height=400, xaxis_title=xtitle, yaxis_title=ytitle,
                          yaxis=dict(showgrid=False))
        return fig

    em = tuple(np.round(np.arange(deal.entry_multiple - 2, deal.entry_multiple + 2.01, 1.0), 1))
    xm = tuple(np.round(np.arange(deal.exit_multiple - 2, deal.exit_multiple + 2.01, 1.0), 1))
    g1 = cached_grid(KEY, deal, "entry_multiple", em, "exit_multiple", xm)
    st.plotly_chart(heat(g1, ui.exhibit(3, f"IRR by entry and exit multiple (shading relative to {target:.0%})"),
                         lambda v: f"{v:.1f}x", lambda v: f"{v:.1f}x", "Entry EV/EBITDA", "Exit EV/EBITDA"),
                    width="stretch")
    lv = tuple(np.round(np.arange(max(1.0, lev0 - 2), lev0 + 1.51, 0.5), 1))
    gs = (-0.04, -0.02, 0.0, 0.02, 0.04)
    g2 = cached_grid(KEY, deal, "leverage", lv, "growth_shift", gs)
    st.plotly_chart(heat(g2, ui.exhibit(4, "IRR by total leverage and revenue growth"),
                         lambda v: f"{v:.1f}x", lambda v: f"{v * 100:+.0f} pp", "Total leverage (x EBITDA)",
                         "Change in annual revenue growth"), width="stretch")
    ui.source("Blue cells exceed the target IRR; red cells fall short.")

# ---------------------------------------------------------------- monte carlo
with tabs[5]:
    c = st.columns(4)
    n = c[0].select_slider("Simulations", [250, 500, 1000], 500)
    xsd = c[1].number_input("Exit multiple σ (x)", 0.0, 5.0, 1.5, 0.25)
    gsd = c[2].number_input("Growth σ (pp)", 0.0, 10.0, 3.0, 0.5) / 100
    msd = c[3].number_input("Exit margin σ (pp)", 0.0, 10.0, 2.0, 0.5) / 100
    mc_key = (KEY, n, xsd, gsd, msd)
    if st.button("Run simulation", type="primary"):
        ss.lbo_mc = (mc_key, cached_mc(KEY, deal, n, xsd, gsd, msd))
    if "lbo_mc" not in ss or ss.lbo_mc[0] != mc_key:
        st.caption("Run the simulation to see the distribution of returns under these assumptions.")
    else:
        sims = ss.lbo_mc[1]
        p_hurdle = (sims.irr >= target).mean()
        k2 = st.columns(4)
        k2[0].metric("Median IRR", f"{sims.irr.median():.1%}")
        k2[1].metric(f"Probability IRR ≥ {target:.0%}", f"{p_hurdle:.0%}")
        k2[2].metric("Probability of capital loss", f"{(sims.moic < 1).mean():.1%}")
        k2[3].metric("5th-percentile IRR", f"{sims.irr.quantile(0.05):.1%}")
        fig = go.Figure(go.Histogram(x=sims.irr * 100, nbinsx=50, marker_color=SKY,
                                     marker_line=dict(color="white", width=0.5)))
        fig.add_vline(x=target * 100, line_color=NAVY, line_dash="dash", annotation_text=f"Target {target:.0%}")
        fig.add_vline(x=r.irr * 100, line_color=RED, annotation_text="Base case", annotation_position="top left")
        fig.update_layout(title=ui.exhibit(5, f"The deal clears the {target:.0%} hurdle in {p_hurdle:.0%} of "
                                              f"{n:,} simulated outcomes"),
                          xaxis_title="IRR (%)", yaxis_title="Simulations", height=420, showlegend=False)
        st.plotly_chart(fig, width="stretch")
        corr = sims[["exit_multiple", "avg_growth", "exit_margin"]].corrwith(sims.irr).rename(
            {"exit_multiple": "exit multiple", "avg_growth": "revenue growth", "exit_margin": "exit margin"})
        ui.source("Correlation with IRR: " +
                  ", ".join(f"{k_} {v:.2f}" for k_, v in corr.sort_values(ascending=False).items()) + ".")

# ---------------------------------------------------------------- methodology
with tabs[6]:
    st.markdown(r"""
**Structure.** Purchase enterprise value equals the entry multiple times LTM EBITDA (cash-free, debt-free). Uses add
transaction fees, financing fees and minimum cash. Debt tranches are sized as multiples of EBITDA; sponsor equity is
the balancing item.

**Projection.** Revenue growth moves linearly from the year-1 to the year-5 rate, and margin moves linearly to the
exit margin. Levered free cash flow = EBITDA − cash interest − taxes − capex − change in NWC. Financing fees are
amortized for tax purposes.

**Debt schedule.** Each year the model accrues PIK interest, pays scheduled amortization, draws the revolver to
cover any shortfall, repays the revolver first, then applies the cash sweep to eligible tranches in order. Interest
is charged on average balances. Because interest and the sweep depend on each other, each year is solved by
fixed-point iteration.

**Returns.** Exit equity = exit multiple × year-5 EBITDA − net debt, less the management promote. With no interim
distributions, IRR = MOIC^(1/5) − 1.

**Value-creation bridge.**
$$\Delta E = (\text{EBITDA}_5 - \text{EBITDA}_0)\,m_0 + (m_5 - m_0)\,\text{EBITDA}_5 + (ND_0 - ND_5)
- \text{fees} - \text{promote}$$

**Monte Carlo.** Each draw shocks the exit multiple, applies a persistent and a year-specific growth shock, and
shocks the exit margin.

**Validation.** Unit tests confirm that sources equal uses, the bridge reconciles to exit equity, IRR and MOIC
agree, the annual change in net debt equals levered free cash flow, and the price solver hits its target.
""")

# ---------------------------------------------------------------- export
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    r.su.to_excel(xw, sheet_name="Sources and uses")
    r.pnl.T.to_excel(xw, sheet_name="Operating model")
    r.debt.T.to_excel(xw, sheet_name="Debt schedule")
    r.credit.T.to_excel(xw, sheet_name="Credit statistics")
    r.bridge.to_frame("$M").to_excel(xw, sheet_name="Returns bridge")
st.download_button("Download model (.xlsx)", buf.getvalue(), f"{deal.name.replace(' ', '_')}_LBO.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
