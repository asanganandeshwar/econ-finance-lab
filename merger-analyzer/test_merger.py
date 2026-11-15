from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

import merger as mg


def base():
    a = mg.Company("Acquirer", price=80, shares=500, net_income=2400, ebitda=4800, net_debt=6000,
                   book_equity=15000)
    t = mg.Company("Target", price=40, shares=250, net_income=700, ebitda=1500, net_debt=2000,
                   book_equity=4000)
    return mg.Deal(a, t)


def test_all_stock_no_synergies_follows_relative_pe():
    d = replace(base(), pct_stock=1.0, synergies=0, intangible_pct=0, advisory_fee_pct=0)
    r = mg.analyze(d)
    # acquirer P/E (16.7x) above offer P/E (18.6x)? -> dilutive when offer P/E is higher
    offer_pe = d.offer_price / d.target.eps
    assert (r.years.loc[1, "accretion"] < 0) == (offer_pe > d.acquirer.pe)


def test_equal_pe_all_stock_is_neutral():
    a = mg.Company("A", 50, 100, 250, 500, 0)
    t = mg.Company("T", 25, 100, 125, 250, 0)            # same P/E of 20x
    d = mg.Deal(a, t, premium=0.0, pct_stock=1.0, synergies=0, intangible_pct=0, advisory_fee_pct=0,
                integration_costs=(0, 0, 0))
    assert mg.analyze(d).years.accretion.abs().max() < 1e-12


def test_breakeven_synergies_zero_accretion():
    d = base()
    r = mg.analyze(d)
    be = r.breakeven_synergies.loc[2]
    r2 = mg.analyze(replace(d, synergies=be))
    assert r2.years.loc[2, "accretion"] == pytest.approx(0, abs=1e-10)


def test_funding_sums_to_uses():
    r = mg.analyze(replace(base(), balance_sheet_cash=1000))
    assert r.funding.sum() == pytest.approx(r.multiples["Total uses"])


def test_hhi_delta_identity():
    s = pd.Series({"A": 30, "B": 25, "C": 20, "D": 15, "E": 10})
    c = mg.concentration(s, "A", "B")
    assert c["pre"] == pytest.approx(2250)
    assert c["delta"] == pytest.approx(2 * 30 * 25)
    assert c["presumption"]


def test_small_merger_not_presumed():
    s = pd.Series({f"F{i}": 5 for i in range(20)})
    assert not mg.concentration(s, "F0", "F1")["presumption"]


def market():
    return mg.LogitMarket(["A", "B", "C", "D"], [0.35, 0.25, 0.25, 0.15], [4.0, 3.8, 3.6, 3.5],
                          margin_firm=0, margin=0.35, outside=0.2)


def test_calibration_reproduces_pre_merger_equilibrium():
    m = market()
    p = m.equilibrium(np.arange(4), m.cost)
    assert np.allclose(p, m.prices, atol=1e-8)
    assert np.allclose(m.demand(m.prices), m.s)


def test_merger_raises_prices_and_lowers_surplus():
    r = market().simulate(0, 1)
    assert (r["price_change"][[0, 1]] > 0).all()
    assert (r["price_change"][[2, 3]] > 0).all()       # rivals respond with smaller increases
    assert r["delta_cs"] < 0 and r["delta_profit_merged"] > 0


def test_werden_cmcr_matches_logit_exact():
    m = market()
    marg = 1 - m.cost / m.prices
    d01 = m.s[1] / (1 - m.s[0])
    d10 = m.s[0] / (1 - m.s[1])
    c = mg.cmcr(marg[0], marg[1], d01, d10, m.prices[0], m.prices[1])
    assert np.allclose(c, m.exact_cmcr(0, 1), atol=1e-10)


def test_cmcr_cost_cuts_hold_prices_fixed():
    m = market()
    owners = np.array([0, 0, 2, 3])
    cost = m.cost.copy()
    cost[[0, 1]] *= 1 - m.exact_cmcr(0, 1)
    assert np.allclose(m.equilibrium(owners, cost), m.prices, atol=1e-8)


def test_offsetting_efficiency_neutralizes_surplus():
    m = market()
    e = m.offsetting_efficiency(0, 1)
    assert abs(m.simulate(0, 1, e)["delta_cs"]) < 1e-3 * m.market_revenue
