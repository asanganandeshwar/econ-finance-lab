"""Leveraged buyout engine.

Annual model with sources & uses, tranche-level debt schedule (mandatory amortization,
cash sweep, PIK, revolver), average-balance interest solved by fixed-point iteration,
exit waterfall, exact value-creation bridge, sensitivity grids, Monte Carlo and a
max-entry-price solver.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd


@dataclass
class Tranche:
    name: str
    multiple: float          # x entry EBITDA
    rate: float              # cash interest rate
    amort: float = 0.0       # mandatory annual amortization, % of original principal
    sweep: bool = False      # receives excess cash flow sweep
    pik: float = 0.0         # PIK interest rate (accrues to principal)


@dataclass
class Deal:
    name: str = "Target Co."
    ltm_revenue: float = 250.0           # $m
    entry_margin: float = 0.20
    exit_margin: float = 0.23            # margin reached by exit year (linear path)
    growth: tuple = (0.08, 0.08, 0.07, 0.06, 0.05)
    entry_multiple: float = 10.0
    exit_multiple: float = 10.0
    da_pct: float = 0.03                 # D&A % revenue
    capex_pct: float = 0.035             # capex % revenue
    nwc_pct: float = 0.10                # NWC % of incremental revenue
    tax_rate: float = 0.25
    txn_fee_pct: float = 0.02            # % of EV
    fin_fee_pct: float = 0.025           # % of funded debt, amortized over hold
    min_cash: float = 10.0
    sweep_pct: float = 0.75              # share of excess cash used for prepayment
    revolver_size: float = 40.0
    revolver_rate: float = 0.075
    mgmt_pool: float = 0.08              # share of equity value gain to management
    avg_interest: bool = True
    tranches: list = field(default_factory=lambda: [
        Tranche("Term Loan B", 4.0, 0.085, amort=0.01, sweep=True),
        Tranche("Senior Notes", 1.5, 0.095),
    ])

    @property
    def years(self):
        return len(self.growth)


@dataclass
class Result:
    deal: Deal
    su: pd.DataFrame          # sources & uses
    pnl: pd.DataFrame         # operating model + cash flow
    debt: pd.DataFrame        # balances by tranche, end of year
    credit: pd.DataFrame      # credit statistics
    entry_equity: float
    exit_ev: float
    exit_net_debt: float
    exit_equity: float
    sponsor_proceeds: float
    moic: float
    irr: float
    bridge: pd.Series


def run(d: Deal, max_iter: int = 50) -> Result:
    e0 = d.ltm_revenue * d.entry_margin
    ev0 = d.entry_multiple * e0
    debt0 = {t.name: t.multiple * e0 for t in d.tranches}
    total_debt = sum(debt0.values())
    txn, fin = d.txn_fee_pct * ev0, d.fin_fee_pct * total_debt
    uses = {"Purchase enterprise value": ev0, "Transaction fees": txn, "Financing fees": fin,
            "Cash to balance sheet": d.min_cash}
    equity0 = sum(uses.values()) - total_debt
    if equity0 <= 0:
        raise ValueError("Debt exceeds total uses; reduce leverage.")
    sources = {**debt0, "Sponsor equity": equity0}
    su = pd.DataFrame({"Sources": pd.Series(sources), "Uses": pd.Series(uses)})

    N = d.years
    bal = dict(debt0)
    rev_prev, cash, rcf = d.ltm_revenue, d.min_cash, 0.0
    rows, debt_rows = [], []
    for y in range(1, N + 1):
        rev = rev_prev * (1 + d.growth[y - 1])
        margin = d.entry_margin + (d.exit_margin - d.entry_margin) * y / N
        ebitda = rev * margin
        da, capex = d.da_pct * rev, d.capex_pct * rev
        dnwc = d.nwc_pct * (rev - rev_prev)
        fee_amort = fin / N
        beg = dict(bal)
        beg_rcf = rcf

        # fixed point: interest depends on ending balances, which depend on interest
        end, end_rcf, cash_int = dict(beg), beg_rcf, None
        for _ in range(max_iter):
            def avg(a, b):
                return (a + b) / 2 if d.avg_interest else a
            ci = sum(t.rate * avg(beg[t.name], end[t.name]) for t in d.tranches) + \
                d.revolver_rate * avg(beg_rcf, end_rcf)
            pik = {t.name: t.pik * beg[t.name] for t in d.tranches}
            ebt = ebitda - da - ci - sum(pik.values()) - fee_amort
            tax = max(0.0, ebt) * d.tax_rate
            fcf = ebitda - capex - dnwc - tax - ci          # levered FCF before principal
            new = {t.name: beg[t.name] + pik[t.name] for t in d.tranches}
            mand = {t.name: min(new[t.name], t.amort * debt0[t.name]) for t in d.tranches}
            for k in new:
                new[k] -= mand[k]
            avail = cash - d.min_cash + fcf - sum(mand.values())
            r = beg_rcf
            if avail < 0:                                   # draw revolver
                draw = min(-avail, d.revolver_size - r)
                r += draw
                avail += draw
            else:                                           # repay revolver first
                rep = min(avail, r)
                r -= rep
                avail -= rep
            sweep_cash = max(0.0, avail) * d.sweep_pct
            swept = 0.0
            for t in d.tranches:
                if t.sweep and sweep_cash > 0:
                    pay = min(sweep_cash, new[t.name])
                    new[t.name] -= pay
                    sweep_cash -= pay
                    swept += pay
            new_cash = d.min_cash + avail - swept
            converged = cash_int is not None and abs(ci - cash_int) < 1e-9
            end, end_rcf, cash_int = new, r, ci
            if converged:
                break
        bal, rcf, cash = end, end_rcf, new_cash
        debt_total = sum(bal.values()) + rcf
        rows.append(dict(year=y, revenue=rev, growth=d.growth[y - 1], ebitda=ebitda, margin=margin, da=da,
                         ebit=ebitda - da, cash_interest=ci, pik_interest=sum(pik.values()),
                         taxes=tax, capex=capex, change_nwc=dnwc, levered_fcf=fcf,
                         mandatory_amort=sum(mand.values()), sweep=swept, revolver=rcf, cash=cash))
        debt_rows.append(dict(year=y, **bal, Revolver=rcf, Cash=cash, total_debt=debt_total,
                              net_debt=debt_total - cash))
        rev_prev = rev

    pnl = pd.DataFrame(rows).set_index("year")
    debt = pd.DataFrame(debt_rows).set_index("year")
    debt.loc[0] = {**debt0, "Revolver": 0.0, "Cash": d.min_cash, "total_debt": total_debt,
                   "net_debt": total_debt - d.min_cash}
    debt = debt.sort_index()

    credit = pd.DataFrame({
        "Total leverage (x)": debt.total_debt.iloc[1:] / pnl.ebitda,
        "Net leverage (x)": debt.net_debt.iloc[1:] / pnl.ebitda,
        "Interest coverage (x)": pnl.ebitda / pnl.cash_interest.replace(0, np.nan),
        "FCF / debt": pnl.levered_fcf / debt.total_debt.iloc[1:].replace(0, np.nan),
        "Cumulative paydown (%)": 1 - debt.total_debt.iloc[1:] / total_debt,
    })
    credit.loc[0, "Total leverage (x)"] = total_debt / e0
    credit.loc[0, "Net leverage (x)"] = (total_debt - d.min_cash) / e0
    credit = credit.sort_index()

    eN = pnl.ebitda.iloc[-1]
    exit_ev = d.exit_multiple * eN
    nd0, ndN = total_debt - d.min_cash, debt.net_debt.iloc[-1]
    exit_eq = exit_ev - ndN
    pool = d.mgmt_pool * max(0.0, exit_eq - equity0)
    proceeds = exit_eq - pool
    moic = proceeds / equity0
    irr = np.sign(moic) * abs(moic) ** (1 / N) - 1 if moic > 0 else -1.0

    bridge = pd.Series({
        "Entry equity": equity0,
        "EBITDA growth": (eN - e0) * d.entry_multiple,
        "Multiple expansion": (d.exit_multiple - d.entry_multiple) * eN,
        "Debt paydown & cash build": nd0 - ndN,
        "Fees": -(txn + fin),
        "Management promote": -pool,
    })
    bridge["Exit equity"] = bridge.sum()
    return Result(d, su, pnl, debt, credit, equity0, exit_ev, ndN, exit_eq, proceeds, moic, irr, bridge)


# ------------------------------------------------------------------ analytics

def with_leverage(d: Deal, total_x: float) -> Deal:
    """Scale every tranche so total leverage equals total_x, keeping the mix."""
    cur = sum(t.multiple for t in d.tranches)
    return replace(d, tranches=[replace(t, multiple=t.multiple * total_x / cur) for t in d.tranches])


def grid(d: Deal, row: str, rows, col: str, cols, metric: str = "irr") -> pd.DataFrame:
    out = pd.DataFrame(index=rows, columns=cols, dtype=float)
    for r in rows:
        for c in cols:
            dd = d
            for k, v in [(row, r), (col, c)]:
                if k == "leverage":
                    dd = with_leverage(dd, v)
                elif k == "growth_shift":
                    dd = replace(dd, growth=tuple(g + v for g in d.growth))
                else:
                    dd = replace(dd, **{k: v})
            try:
                out.loc[r, c] = getattr(run(dd), metric)
            except ValueError:
                out.loc[r, c] = np.nan
    out.index.name, out.columns.name = row, col
    return out


def max_entry_multiple(d: Deal, target_irr: float, lo: float = 4.0, hi: float = 25.0) -> float | None:
    """Highest entry multiple that still earns target_irr (exit multiple held fixed).
    Leverage is capped at 65% of purchase EV, as lenders would at low prices."""
    lev = sum(t.multiple for t in d.tranches)

    def f(m):
        try:
            dd = with_leverage(replace(d, entry_multiple=m), min(lev, 0.65 * m))
            return run(dd).irr - target_irr
        except ValueError:
            return -1.0
    if f(lo) < 0:
        return None
    if f(hi) > 0:
        return hi
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) > 0 else (lo, mid)
    return (lo + hi) / 2


def monte_carlo(d: Deal, n: int = 1000, exit_sd: float = 1.5, growth_sd: float = 0.03,
                margin_sd: float = 0.02, seed: int = 7) -> pd.DataFrame:
    """Draw exit multiple, a persistent growth shock and an exit-margin shock."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        g_shock = rng.normal(0, growth_sd)
        dd = replace(d,
                     exit_multiple=max(3.0, rng.normal(d.exit_multiple, exit_sd)),
                     growth=tuple(g + g_shock + rng.normal(0, growth_sd / 2) for g in d.growth),
                     exit_margin=max(0.02, d.exit_margin + rng.normal(0, margin_sd)))
        r = run(dd)
        out.append(dict(irr=r.irr, moic=r.moic, exit_multiple=dd.exit_multiple,
                        avg_growth=np.mean(dd.growth), exit_margin=dd.exit_margin,
                        exit_leverage=r.credit["Total leverage (x)"].iloc[-1]))
    return pd.DataFrame(out)


# ------------------------------------------------------------------ CIM Analyzer import

def _money(s: str) -> float | None:
    m = re.search(r"\$\s*([\d,.]+)\s*([kKmMbB])?", s or "")
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "m").lower()
    return v * {"k": 0.001, "m": 1.0, "b": 1000.0}[unit]


def _pct(s: str) -> float | None:
    m = re.search(r"(-?[\d.]+)\s*%", s or "")
    return float(m.group(1)) / 100 if m else None


def from_cim(memo: dict, base: Deal | None = None) -> tuple[Deal, list[str]]:
    """Prefill a Deal from CIM Analyzer JSON ('financial_highlights', 'sector_benchmark')."""
    d = base or Deal()
    notes, kw = [], {}
    fh, sb = memo.get("financial_highlights", {}), memo.get("sector_benchmark", {})
    rev, ebitda_s = _money(fh.get("revenue", "")), fh.get("ebitda", "")
    ebitda, margin = _money(ebitda_s), _pct(ebitda_s)
    if rev:
        kw["ltm_revenue"] = rev
        notes.append(f"Revenue ${rev:,.1f}m from CIM")
    if margin is None and ebitda and rev:
        margin = ebitda / rev
    if margin:
        kw["entry_margin"] = margin
        kw["exit_margin"] = margin + 0.02
        notes.append(f"EBITDA margin {margin:.1%} from CIM (exit margin assumed +2pp)")
    g = _pct(fh.get("revenue_growth", ""))
    if g is not None:
        kw["growth"] = tuple(np.linspace(g, max(g * 0.5, 0.02), d.years).round(4))
        notes.append(f"Growth fades from {g:.0%} to {max(g * 0.5, 0.02):.0%}")
    rng = re.findall(r"([\d.]+)\s*[x×]?", sb.get("ev_ebitda", "").replace("–", "-"))
    nums = [float(x) for x in rng if x not in ("", ".")][:2]
    if nums:
        mid = sum(nums) / len(nums)
        kw["entry_multiple"] = kw["exit_multiple"] = mid
        notes.append(f"Entry and exit at {mid:.1f}x, midpoint of sector range {sb.get('ev_ebitda')}")
    if memo.get("company_name") or memo.get("company"):
        kw["name"] = memo.get("company_name") or memo.get("company")
    return replace(d, **kw), notes
