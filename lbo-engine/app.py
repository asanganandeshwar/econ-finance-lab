"""LBO Engine: interactive leveraged buyout model.

Run:  streamlit run app.py   (or through ../streamlit_app.py)
"""
import io
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
import lbo  # noqa: E402

ACCENT, GREY, GOOD, BAD = "#1f5fbf", "#8a8f98", "#2e8b57", "#c0392b"
ss = st.session_state

DEFAULTS = dict(name="Target Co.", rev=250.0, m0=20.0, m1=23.0, g1=8.0, g5=5.0, entry=10.0, exit=10.0,
                da=3.0, capex=3.5, nwc=10.0, tax=25.0, txn=2.0, finfee=2.5, cash=10.0, sweep=75,
                rcf=40.0, pool=8.0, target=20.0)
for k, v in DEFAULTS.items():
    ss.setdefault(f"lbo_{k}", v)
ss.setdefault("lbo_tranches", pd.DataFrame([
    dict(Tranche="Term Loan B", **{"x EBITDA": 4.0, "Rate %": 8.5, "Amort %": 1.0, "Sweep": True, "PIK %": 0.0}),
    dict(Tranche="Senior Notes", **{"x EBITDA": 1.5, "Rate %": 9.5, "Amort %": 0.0, "Sweep": False, "PIK %": 0.0}),
]))

st.title("LBO Engine")
st.caption("A five-year leveraged buyout model: sources & uses, tranche-level debt schedule with cash sweep, "
           "returns, value-creation bridge, sensitivities and Monte Carlo. All figures in $ millions.")

# ---------------------------------------------------------------- CIM import
with st.expander("Import deal inputs from CIM Analyzer"):
    st.markdown("Paste or upload the JSON memo from the CIM Analyzer. Revenue, EBITDA margin, growth and the "
                "sector EV/EBITDA range prefill the model, and you can adjust everything afterward.")
    up = st.file_uploader("CIM Analyzer JSON", type="json", label_visibility="collapsed")
    txt = st.text_area("…or paste JSON", height=110, placeholder='{"financial_highlights": {"revenue": "$45M", ...}}')
    if st.button("Prefill model"):
        try:
            memo = json.load(up) if up else json.loads(txt)
            d, notes = lbo.from_cim(memo)
            ss.lbo_name, ss.lbo_rev = d.name, float(d.ltm_revenue)
            ss.lbo_m0, ss.lbo_m1 = round(d.entry_margin * 100, 1), round(d.exit_margin * 100, 1)
            ss.lbo_g1, ss.lbo_g5 = round(d.growth[0] * 100, 1), round(d.growth[-1] * 100, 1)
            ss.lbo_entry = ss.lbo_exit = round(d.entry_multiple, 1)
            ss.lbo_cash = round(max(2.0, 0.04 * d.ltm_revenue), 1)
            ss.lbo_rcf = round(max(5.0, 0.15 * d.ltm_revenue), 1)
            ss.lbo_notes = notes
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"Could not read that memo: {e}")
    for n in ss.get("lbo_notes", []):
        st.markdown(f"- {n}")

# ---------------------------------------------------------------- inputs
sb = st.sidebar
sb.header("Deal")
sb.text_input("Company", key="lbo_name")
sb.number_input("LTM revenue ($m)", 1.0, 100000.0, key="lbo_rev", step=10.0)
c = sb.columns(2)
c[0].number_input("Entry EV/EBITDA", 2.0, 40.0, key="lbo_entry", step=0.5)
c[1].number_input("Exit EV/EBITDA", 2.0, 40.0, key="lbo_exit", step=0.5)
sb.header("Operations")
c = sb.columns(2)
c[0].number_input("Entry margin %", 1.0, 80.0, key="lbo_m0", step=0.5)
c[1].number_input("Exit margin %", 1.0, 80.0, key="lbo_m1", step=0.5)
c = sb.columns(2)
c[0].number_input("Growth yr 1 %", -50.0, 100.0, key="lbo_g1", step=0.5)
c[1].number_input("Growth yr 5 %", -50.0, 100.0, key="lbo_g5", step=0.5)
c = sb.columns(3)
c[0].number_input("D&A %", 0.0, 30.0, key="lbo_da", step=0.5)
c[1].number_input("Capex %", 0.0, 40.0, key="lbo_capex", step=0.5)
c[2].number_input("NWC %Δrev", 0.0, 60.0, key="lbo_nwc", step=1.0)
sb.header("Financing")
c = sb.columns(2)
c[0].number_input("Tax rate %", 0.0, 50.0, key="lbo_tax", step=1.0)
c[1].number_input("Min cash ($m)", 0.0, 10000.0, key="lbo_cash", step=1.0)
c = sb.columns(2)
c[0].number_input("Txn fees % EV", 0.0, 10.0, key="lbo_txn", step=0.25)
c[1].number_input("Fin. fees % debt", 0.0, 10.0, key="lbo_finfee", step=0.25)
c = sb.columns(2)
c[0].number_input("Revolver ($m)", 0.0, 10000.0, key="lbo_rcf", step=5.0)
c[1].slider("Cash sweep %", 0, 100, key="lbo_sweep")
sb.number_input("Management promote % of gain", 0.0, 30.0, key="lbo_pool", step=1.0)
sb.number_input("Target IRR %", 5.0, 50.0, key="lbo_target", step=1.0)

st.markdown("**Capital structure** (edit, add or remove tranches; sweep pays down tranches top to bottom)")
tr = st.data_editor(ss.lbo_tranches, num_rows="dynamic", width="stretch", key="lbo_tr_editor",
                    column_config={"Sweep": st.column_config.CheckboxColumn()})
tr = tr.dropna(subset=["Tranche"])
tr = tr.fillna({"x EBITDA": 0.0, "Rate %": 0.0, "Amort %": 0.0, "Sweep": False, "PIK %": 0.0})
tranches = [
    lbo.Tranche(row["Tranche"], float(row["x EBITDA"]), float(row["Rate %"]) / 100, float(row["Amort %"]) / 100,
                bool(row["Sweep"]), float(row["PIK %"]) / 100)
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
max_m = lbo.max_entry_multiple(deal, target)
lev0 = sum(t.multiple for t in tranches)

# ---------------------------------------------------------------- headline
k = st.columns(5)
k[0].metric("IRR", f"{r.irr:.1%}", f"{(r.irr - target) * 100:+.1f} pp vs target")
k[1].metric("MOIC", f"{r.moic:.2f}x")
k[2].metric("Sponsor equity", f"${r.entry_equity:,.0f}m", f"{r.entry_equity / r.su.Uses.sum():.0%} of uses",
            delta_color="off")
k[3].metric("Entry leverage", f"{lev0:.1f}x", f"exit {r.credit['Total leverage (x)'].iloc[-1]:.1f}x",
            delta_color="off")
k[4].metric(f"Max entry for {target:.0%} IRR", f"{max_m:.1f}x" if max_m else "n/a",
            help="Highest entry EV/EBITDA that still earns the target IRR, holding the exit multiple fixed; "
                 "leverage capped at 65% of EV.")

b = r.bridge
drivers = b.drop(["Entry equity", "Exit equity"])
top = drivers.abs().idxmax()
st.info(f"**Reading.** {deal.name} returns **{r.moic:.2f}x / {r.irr:.1%}** over five years. "
        f"The largest value driver is **{top[0].lower() + top[1:] if not top.startswith("EBITDA") else top}** (${drivers[top]:,.0f}m, "
        f"{drivers[top] / (b['Exit equity'] - b['Entry equity']):.0%} of the equity gain). "
        + (f"At {deal.entry_multiple:.1f}x the deal clears the {target:.0%} hurdle with "
           f"{(max_m - deal.entry_multiple):.1f}x of headroom on price." if max_m and max_m >= deal.entry_multiple
           else f"To earn {target:.0%}, the sponsor can pay at most {max_m:.1f}x." if max_m
           else f"The deal cannot reach {target:.0%} at any tested price."))

tabs = st.tabs(["Value creation", "Sources & uses", "Operating model", "Debt schedule", "Sensitivities",
                "Monte Carlo", "Method"])

# ---------------------------------------------------------------- bridge
with tabs[0]:
    measures = ["absolute"] + ["relative"] * len(drivers) + ["total"]
    fig = go.Figure(go.Waterfall(
        x=list(b.index), y=list(b.values), measure=measures,
        text=[f"${v:,.0f}m" for v in b.values], textposition="outside",
        increasing=dict(marker=dict(color=GOOD)), decreasing=dict(marker=dict(color=BAD)),
        totals=dict(marker=dict(color=GREY)), connector=dict(line=dict(color=GREY, width=1))))
    fig.update_layout(title="Equity value bridge, entry to exit ($m): green adds value, red subtracts",
                      height=460, template="simple_white", showlegend=False)
    st.plotly_chart(fig, width="stretch")
    share = (drivers / drivers[drivers > 0].sum()).clip(lower=0)
    st.caption("Exact decomposition: EBITDA growth is valued at the entry multiple, multiple expansion at exit "
               "EBITDA, and deleveraging is the fall in net debt. " +
               " · ".join(f"{k}: {v:.0%}" for k, v in share.items() if v > 0) + " of positive value creation.")

# ---------------------------------------------------------------- S&U
with tabs[1]:
    a, c2 = st.columns(2)
    src = r.su.Sources.dropna()
    use = r.su.Uses.dropna()
    a.markdown("**Sources**")
    a.dataframe(pd.DataFrame({"$m": src, "% total": src / src.sum(), "x EBITDA": src / (deal.ltm_revenue * deal.entry_margin)})
                .style.format({"$m": "{:,.1f}", "% total": "{:.1%}", "x EBITDA": "{:.2f}x"}), width="stretch")
    c2.markdown("**Uses**")
    c2.dataframe(pd.DataFrame({"$m": use, "% total": use / use.sum()})
                 .style.format({"$m": "{:,.1f}", "% total": "{:.1%}"}), width="stretch")
    st.caption(f"Entry EBITDA ${deal.ltm_revenue * deal.entry_margin:,.1f}m × {deal.entry_multiple:.1f}x = "
               f"${use['Purchase enterprise value']:,.1f}m purchase EV (cash-free, debt-free).")

# ---------------------------------------------------------------- operating model
with tabs[2]:
    p = r.pnl.copy()
    show = pd.DataFrame({
        "Revenue": p.revenue, "Growth %": p.growth * 100, "EBITDA": p.ebitda, "Margin %": p.margin * 100,
        "D&A": -p.da, "EBIT": p.ebit, "Cash interest": -p.cash_interest, "PIK interest": -p.pik_interest,
        "Taxes": -p.taxes, "Capex": -p.capex, "Δ NWC": -p.change_nwc, "Levered FCF": p.levered_fcf,
        "Mandatory amortization": -p.mandatory_amort, "Cash sweep": -p.sweep,
    }).T
    show.columns = [f"Year {c}" for c in show.columns]
    st.dataframe(show.style.format("{:,.1f}"), width="stretch", height=530)

# ---------------------------------------------------------------- debt
with tabs[3]:
    dbt = r.debt
    fig = go.Figure()
    names = [t.name for t in tranches] + ["Revolver"]
    shades = [ACCENT, "#5b8bd6", "#9bb8e8", "#c9d9f2", GREY]
    for i, n in enumerate(names):
        if dbt[n].abs().sum() > 0:
            fig.add_trace(go.Bar(x=[f"Y{y}" for y in dbt.index], y=dbt[n], name=n, marker_color=shades[i % 5]))
    lev = r.credit["Total leverage (x)"]
    fig.add_trace(go.Scatter(x=[f"Y{y}" for y in lev.index], y=lev, name="Total leverage (x)", yaxis="y2",
                             mode="lines+markers+text", text=[f"{v:.1f}x" for v in lev], textposition="top center",
                             line=dict(color=BAD, width=2)))
    fig.update_layout(barmode="stack", title="Debt outstanding by tranche ($m) and leverage", height=460,
                      template="simple_white", yaxis2=dict(overlaying="y", side="right", title="x EBITDA",
                                                           rangemode="tozero"))
    st.plotly_chart(fig, width="stretch")
    cov = st.number_input("Maximum leverage covenant (x)", 1.0, 15.0, max(6.0, round(lev0 + 0.75, 1)), 0.25)
    cr = r.credit.copy()
    cr["Covenant headroom"] = 1 - cr["Total leverage (x)"] / cov
    st.dataframe(cr.T.style.format("{:.2f}"), width="stretch")
    if (cr["Covenant headroom"] < 0).any():
        st.error(f"Covenant breach in year(s) {list(cr.index[cr['Covenant headroom'] < 0])}.")

# ---------------------------------------------------------------- sensitivities
with tabs[4]:
    def heat(g, title, fmt_r, fmt_c):
        z = g.values.astype(float)
        fig = go.Figure(go.Heatmap(
            z=z * 100, x=[fmt_c(c) for c in g.columns], y=[fmt_r(i) for i in g.index],
            text=[[f"{v:.1%}" if np.isfinite(v) else "" for v in row] for row in z], texttemplate="%{text}",
            colorscale=[[0, "#c0392b"], [0.5, "#f5f5f5"], [1, "#2e8b57"]], zmid=target * 100,
            colorbar=dict(title="IRR %")))
        fig.update_layout(title=title, height=400, template="simple_white",
                          xaxis_title=g.columns.name, yaxis_title=g.index.name)
        return fig

    em = np.round(np.arange(deal.entry_multiple - 2, deal.entry_multiple + 2.01, 1.0), 1)
    xm = np.round(np.arange(deal.exit_multiple - 2, deal.exit_multiple + 2.01, 1.0), 1)
    g1 = lbo.grid(deal, "entry_multiple", em, "exit_multiple", xm)
    g1.index.name, g1.columns.name = "Entry EV/EBITDA", "Exit EV/EBITDA"
    st.plotly_chart(heat(g1, f"IRR: entry vs exit multiple (white = {target:.0%} target)",
                         lambda v: f"{v:.1f}x", lambda v: f"{v:.1f}x"), width="stretch")
    lv = np.round(np.arange(max(1.0, lev0 - 2), lev0 + 1.51, 0.5), 1)
    gs = np.array([-0.04, -0.02, 0.0, 0.02, 0.04])
    g2 = lbo.grid(deal, "leverage", lv, "growth_shift", gs)
    g2.index.name, g2.columns.name = "Total leverage (x)", "Revenue growth shift"
    st.plotly_chart(heat(g2, "IRR: leverage vs revenue growth", lambda v: f"{v:.1f}x",
                         lambda v: f"{v * 100:+.0f} pp"), width="stretch")

# ---------------------------------------------------------------- monte carlo
with tabs[5]:
    c = st.columns(4)
    n = c[0].select_slider("Simulations", [250, 500, 1000, 2000], 1000)
    xsd = c[1].number_input("Exit multiple σ (x)", 0.0, 5.0, 1.5, 0.25)
    gsd = c[2].number_input("Growth σ (pp)", 0.0, 10.0, 3.0, 0.5) / 100
    msd = c[3].number_input("Exit margin σ (pp)", 0.0, 10.0, 2.0, 0.5) / 100

    @st.cache_data(show_spinner="Simulating exits…")
    def mc(_deal, key, n, xsd, gsd, msd):
        return lbo.monte_carlo(_deal, n, xsd, gsd, msd)

    sims = mc(deal, repr(deal), n, xsd, gsd, msd)
    p_loss, p_hurdle = (sims.moic < 1).mean(), (sims.irr >= target).mean()
    k2 = st.columns(4)
    k2[0].metric("Median IRR", f"{sims.irr.median():.1%}")
    k2[1].metric(f"P(IRR ≥ {target:.0%})", f"{p_hurdle:.0%}")
    k2[2].metric("P(loss of capital)", f"{p_loss:.1%}")
    k2[3].metric("5th percentile IRR", f"{sims.irr.quantile(0.05):.1%}")
    fig = go.Figure(go.Histogram(x=sims.irr * 100, nbinsx=50, marker_color=GREY))
    fig.add_vline(x=target * 100, line_color=ACCENT, line_dash="dash", annotation_text=f"Target {target:.0%}")
    fig.add_vline(x=r.irr * 100, line_color=BAD, annotation_text="Base case", annotation_position="top left")
    fig.update_layout(title=f"Distribution of IRR across {n:,} simulated deals", xaxis_title="IRR %",
                      height=400, template="simple_white")
    st.plotly_chart(fig, width="stretch")
    corr = sims[["exit_multiple", "avg_growth", "exit_margin"]].corrwith(sims.irr).rename(
        {"exit_multiple": "Exit multiple", "avg_growth": "Revenue growth", "exit_margin": "Exit margin"})
    st.markdown("**What drives the spread?** Correlation of each shock with IRR: " +
                " · ".join(f"{k} {v:.2f}" for k, v in corr.sort_values(ascending=False).items()))

# ---------------------------------------------------------------- method
with tabs[6]:
    st.markdown(r"""
**Structure.** Purchase EV = entry multiple × LTM EBITDA (cash-free, debt-free). Uses add transaction fees,
financing fees and minimum cash. Debt tranches are sized as multiples of EBITDA, and sponsor equity is the plug.

**Projection.** Revenue grows on a path that fades linearly from year 1 to year 5. Margin moves linearly to the
exit margin. Levered FCF = EBITDA − cash interest − taxes − capex − ΔNWC. Financing fees are amortized for tax.

**Debt schedule.** Each year: accrue PIK, pay mandatory amortization, draw the revolver if cash falls short, repay
the revolver first, then sweep the chosen share of excess cash into prepayable tranches in order. Interest runs on
average balances, and because interest and the sweep depend on each other, the year is solved by fixed-point
iteration (the circular reference a spreadsheet model handles with iterative calculation).

**Returns.** Exit equity = exit multiple × year-5 EBITDA − net debt, less a management promote on the equity gain.
With no interim dividends, IRR = MOIC^(1/5) − 1.

**Value-creation bridge (exact).**
$$\Delta E = \underbrace{(\text{EBITDA}_5 - \text{EBITDA}_0)\,m_0}_{\text{growth}}
+ \underbrace{(m_5 - m_0)\,\text{EBITDA}_5}_{\text{multiple}}
+ \underbrace{ND_0 - ND_5}_{\text{deleveraging}} - \text{fees} - \text{promote}$$

**Monte Carlo.** Each draw shocks the exit multiple, adds a persistent and an idiosyncratic growth shock, and
shocks the exit margin.

**Tests.** `test_lbo.py` checks that sources equal uses, the bridge ties to exit equity, IRR and MOIC agree, the
yearly change in net debt equals levered FCF, and the price solver hits its target.
""")

# ---------------------------------------------------------------- export
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    r.su.to_excel(xw, sheet_name="Sources & Uses")
    r.pnl.T.to_excel(xw, sheet_name="Operating model")
    r.debt.T.to_excel(xw, sheet_name="Debt schedule")
    r.credit.T.to_excel(xw, sheet_name="Credit stats")
    r.bridge.to_frame("$m").to_excel(xw, sheet_name="Returns bridge")
st.download_button("Download model (Excel)", buf.getvalue(), f"{deal.name.replace(' ', '_')}_LBO.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
