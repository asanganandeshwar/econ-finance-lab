"""Merger analysis: acquirer EPS accretion/dilution and competitive effects.

Part 1 (deal economics): offer value, funding mix, purchase-price amortization, synergy phase-in, pro forma EPS,
breakeven synergies, ownership, leverage and value created for acquirer shareholders.

Part 2 (competition): HHI screens under the 2023 U.S. Merger Guidelines, diversion ratios, GUPPI, compensating
marginal cost reductions (Werden 1996) and a logit Bertrand merger simulation (cf. Werden and Froeb 1994).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd


# =============================================================== deal economics

@dataclass
class Company:
    name: str
    price: float            # $ per share
    shares: float           # diluted shares, millions
    net_income: float       # next-year net income, $M
    ebitda: float           # next-year EBITDA, $M
    net_debt: float         # $M
    book_equity: float = 0.0
    growth: float = 0.05    # annual net income / EBITDA growth

    @property
    def market_cap(self):
        return self.price * self.shares

    @property
    def eps(self):
        return self.net_income / self.shares

    @property
    def pe(self):
        return self.price / self.eps


@dataclass
class Deal:
    acquirer: Company
    target: Company
    premium: float = 0.30
    pct_stock: float = 0.50
    balance_sheet_cash: float = 0.0       # acquirer cash used, $M
    debt_rate: float = 0.065
    cash_yield: float = 0.04              # interest forgone on cash used
    tax_rate: float = 0.25
    synergies: float = 150.0              # run-rate pre-tax cost synergies, $M
    phase_in: tuple = (0.5, 1.0, 1.0)
    integration_costs: tuple = (150.0, 75.0, 0.0)
    include_integration: bool = False     # adjusted EPS excludes one-time costs by convention
    advisory_fee_pct: float = 0.01        # % of offer equity value, expensed at close
    financing_fee_pct: float = 0.02       # % of new debt, amortized
    financing_fee_years: int = 7
    intangible_pct: float = 0.30          # share of excess purchase price allocated to amortizable intangibles
    intangible_life: int = 10

    @property
    def offer_price(self):
        return self.target.price * (1 + self.premium)

    @property
    def equity_value(self):
        return self.offer_price * self.target.shares

    @property
    def enterprise_value(self):
        return self.equity_value + self.target.net_debt


@dataclass
class DealResult:
    deal: Deal
    funding: pd.Series
    years: pd.DataFrame
    new_shares: float
    new_debt: float
    target_ownership: float
    breakeven_synergies: pd.Series
    leverage: float
    value_created: pd.Series
    multiples: pd.Series


def analyze(d: Deal) -> DealResult:
    a, t = d.acquirer, d.target
    stock = d.equity_value * d.pct_stock
    cash_need = d.equity_value * (1 - d.pct_stock) + d.advisory_fee_pct * d.equity_value
    bs_cash = min(d.balance_sheet_cash, cash_need)
    gross_debt = max(0.0, cash_need - bs_cash)
    new_debt = gross_debt / (1 - d.financing_fee_pct) if gross_debt > 0 else 0.0  # debt also funds its own fees
    fin_fees = new_debt - gross_debt
    new_shares = stock / a.price
    pf_shares = a.shares + new_shares

    excess = max(0.0, d.equity_value - t.book_equity)
    intangibles = d.intangible_pct * excess
    amort = intangibles / d.intangible_life
    fee_amort = fin_fees / d.financing_fee_years

    rows = []
    for y, ph in enumerate(d.phase_in, start=1):
        g_a, g_t = (1 + a.growth) ** (y - 1), (1 + t.growth) ** (y - 1)
        ni_a, ni_t = a.net_income * g_a, t.net_income * g_t
        syn = d.synergies * ph
        integ = d.integration_costs[y - 1] if d.include_integration and y - 1 < len(d.integration_costs) else 0.0
        adj_pre_tax = {
            "Synergies": syn,
            "Interest on new debt": -d.debt_rate * new_debt,
            "Forgone interest on cash": -d.cash_yield * bs_cash,
            "Financing fee amortization": -fee_amort,
            "Intangible amortization": -amort,
            "Integration costs": -integ,
        }
        after_tax = {k: v * (1 - d.tax_rate) for k, v in adj_pre_tax.items()}
        ni_pf = ni_a + ni_t + sum(after_tax.values())
        eps_a = ni_a / a.shares
        eps_pf = ni_pf / pf_shares
        ex_syn = ni_pf - after_tax["Synergies"]
        breakeven = max(0.0, (eps_a * pf_shares - ex_syn) / (1 - d.tax_rate)) if ph > 0 else np.nan
        rows.append(dict(year=y, acquirer_ni=ni_a, target_ni=ni_t, **{k: v for k, v in after_tax.items()},
                         pro_forma_ni=ni_pf, standalone_eps=eps_a, pro_forma_eps=eps_pf,
                         accretion=eps_pf / eps_a - 1, breakeven_run_rate=breakeven / ph if ph else np.nan))
    years = pd.DataFrame(rows).set_index("year")

    pf_net_debt = a.net_debt + t.net_debt + new_debt + bs_cash
    pf_ebitda = a.ebitda + t.ebitda + d.synergies * d.phase_in[0]
    funding = pd.Series({"Acquirer stock issued": stock, "New debt": new_debt, "Balance-sheet cash": bs_cash})
    uses = d.equity_value + d.advisory_fee_pct * d.equity_value + fin_fees

    premium_paid = d.equity_value - t.market_cap
    cap_syn = d.synergies * (1 - d.tax_rate) * a.pe
    one_time = sum(d.integration_costs) * (1 - d.tax_rate) + d.advisory_fee_pct * d.equity_value + fin_fees
    value_created = pd.Series({
        "Capitalized synergies": cap_syn,
        "Premium paid": -premium_paid,
        "One-time costs": -one_time,
    })
    value_created["Net value to acquirer"] = value_created.sum()

    multiples = pd.Series({
        "Offer price per share": d.offer_price,
        "Offer equity value": d.equity_value,
        "Enterprise value": d.enterprise_value,
        "EV / EBITDA": d.enterprise_value / t.ebitda,
        "Offer P/E": d.offer_price / t.eps,
        "Acquirer P/E": a.pe,
        "Total uses": uses,
    })
    return DealResult(d, funding, years, new_shares, new_debt, new_shares / pf_shares,
                      years.breakeven_run_rate, pf_net_debt / pf_ebitda, value_created, multiples)


def accretion_grid(d: Deal, row: str, rows, col: str, cols, year: int = 2) -> pd.DataFrame:
    out = pd.DataFrame(index=list(rows), columns=list(cols), dtype=float)
    for r in rows:
        for c in cols:
            out.loc[r, c] = analyze(replace(d, **{row: r, col: c})).years.loc[year, "accretion"]
    return out


# =============================================================== competition

def hhi(shares) -> float:
    s = np.asarray(shares, dtype=float)
    s = s / s.sum() * 100
    return float((s ** 2).sum())


def concentration(shares: pd.Series, a: str, b: str) -> dict:
    s = shares / shares.sum() * 100
    pre = hhi(s)
    post_s = s.drop([a, b])
    post_s[f"{a} + {b}"] = s[a] + s[b]
    post = hhi(post_s)
    delta = post - pre                               # = 2 * s_a * s_b
    combined = s[a] + s[b]
    presumption = (post > 1800 and delta > 100) or (combined > 30 and delta > 100)
    reason = []
    if post > 1800 and delta > 100:
        reason.append("post-merger HHI above 1,800 with an increase above 100")
    if combined > 30 and delta > 100:
        reason.append("combined share above 30% with an HHI increase above 100")
    return dict(pre=pre, post=post, delta=delta, combined_share=combined, presumption=presumption,
                reason="; ".join(reason))


def diversion(shares: pd.Series, a: str, b: str, outside: float = 0.0) -> float:
    """Diversion from a to b under proportional (logit) substitution; `outside` = outside-good share of total."""
    s = shares / shares.sum() * (1 - outside)
    return float(s[b] / (1 - s[a]))


def guppi(d_ab: float, m_b: float, p_b: float, p_a: float) -> float:
    return d_ab * m_b * p_b / p_a


def cmcr(m1, m2, d12, d21, p1, p2) -> tuple[float, float]:
    """Compensating marginal cost reductions (Werden 1996), as shares of pre-merger marginal cost."""
    den = 1 - d12 * d21
    c1 = (m1 * d12 * d21 + m2 * d12 * p2 / p1) / ((1 - m1) * den)
    c2 = (m2 * d21 * d12 + m1 * d21 * p1 / p2) / ((1 - m2) * den)
    return c1, c2


@dataclass
class LogitMarket:
    firms: list
    shares: np.ndarray       # inside-market shares (sum to 1)
    prices: np.ndarray
    margin_firm: int = 0     # index of the firm whose margin calibrates price sensitivity
    margin: float = 0.35     # (p - c) / p for that firm
    outside: float = 0.20    # outside-good share of all consumers
    market_revenue: float = 10000.0   # inside-market revenue, $M
    owners: list = field(default_factory=list)

    def __post_init__(self):
        self.shares = np.asarray(self.shares, float) / np.sum(self.shares)
        self.prices = np.asarray(self.prices, float)
        self.s = self.shares * (1 - self.outside)                    # shares of all consumers
        j = self.margin_firm
        self.alpha = 1 / (self.margin * self.prices[j] * (1 - self.s[j]))
        self.cost = self.prices - 1 / (self.alpha * (1 - self.s))     # single-product Bertrand FOCs
        if np.any(self.cost <= 0):
            raise ValueError("Calibration implies non-positive marginal cost; lower the margin or check prices.")
        self.delta = np.log(self.s / self.outside) + self.alpha * self.prices
        self.N = self.market_revenue / float((self.prices * self.s).sum())
        if not self.owners:
            self.owners = list(range(len(self.firms)))

    def demand(self, p):
        e = np.exp(self.delta - self.alpha * p)
        return e / (1 + e.sum())

    def equilibrium(self, owners, cost, tol=1e-12, iters=10000):
        """Multi-product Bertrand–Nash with logit demand: every product of firm F has markup 1/(α(1 − S_F))."""
        p = self.prices.copy()
        owners = np.asarray(owners)
        for _ in range(iters):
            s = self.demand(p)
            S_F = np.array([s[owners == o].sum() for o in owners])
            p_new = cost + 1 / (self.alpha * (1 - S_F))
            if np.max(np.abs(p_new - p)) < tol:
                return p_new
            p = 0.5 * p + 0.5 * p_new
        raise RuntimeError("Equilibrium did not converge.")

    def consumer_surplus(self, p):
        return self.N / self.alpha * np.log1p(np.exp(self.delta - self.alpha * p).sum())

    def simulate(self, a: int, b: int, efficiency: float = 0.0) -> dict:
        owners = np.array(self.owners)
        owners = np.where(owners == owners[b], owners[a], owners)
        cost = self.cost.copy()
        cost[[a, b]] *= (1 - efficiency)
        p1 = self.equilibrium(owners, cost)
        s0, s1 = self.s, self.demand(p1)
        cs0, cs1 = self.consumer_surplus(self.prices), self.consumer_surplus(p1)
        prof = lambda p, c, s: (p - c) * s * self.N  # noqa: E731
        return dict(prices=p1, price_change=p1 / self.prices - 1, shares_pre=s0, shares_post=s1,
                    delta_cs=cs1 - cs0, delta_profit_merged=(prof(p1, cost, s1)[[a, b]].sum()
                                                             - prof(self.prices, self.cost, s0)[[a, b]].sum()),
                    delta_profit_rivals=(np.delete(prof(p1, cost, s1), [a, b]).sum()
                                         - np.delete(prof(self.prices, self.cost, s0), [a, b]).sum()))

    def exact_cmcr(self, a: int, b: int) -> np.ndarray:
        """Cost cuts that leave pre-merger prices an equilibrium after the merger."""
        S = self.s[a] + self.s[b]
        new_c = self.prices[[a, b]] - 1 / (self.alpha * (1 - S))
        return 1 - new_c / self.cost[[a, b]]

    def offsetting_efficiency(self, a: int, b: int) -> float:
        """Uniform marginal-cost reduction at the merging firms that leaves consumer surplus unchanged."""
        lo, hi = 0.0, 0.9
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if self.simulate(a, b, mid)["delta_cs"] < 0 else (lo, mid)
        return (lo + hi) / 2
