from dataclasses import replace

import numpy as np
import pytest

import lbo


@pytest.fixture
def res():
    return lbo.run(lbo.Deal())


def test_sources_equal_uses(res):
    assert res.su.Sources.sum() == pytest.approx(res.su.Uses.sum())


def test_bridge_ties_to_exit_equity(res):
    assert res.bridge["Exit equity"] == pytest.approx(res.sponsor_proceeds)


def test_moic_and_irr_consistent(res):
    assert res.moic == pytest.approx(res.sponsor_proceeds / res.entry_equity)
    assert (1 + res.irr) ** res.deal.years == pytest.approx(res.moic)


def test_balances_never_negative(res):
    assert (res.debt.drop(columns=["Cash"]) >= -1e-9).all().all()
    assert (res.debt.Cash >= res.deal.min_cash - 1e-9).all()


def test_cash_flow_identity(res):
    p = res.pnl
    # change in net debt each year equals -(levered FCF) when there is no PIK
    nd = res.debt.net_debt
    assert np.allclose(-(nd.diff().iloc[1:]).values, p.levered_fcf.values, atol=1e-6)


def test_more_leverage_raises_irr_when_returns_beat_cost():
    lo = lbo.run(lbo.with_leverage(lbo.Deal(), 3.0)).irr
    hi = lbo.run(lbo.with_leverage(lbo.Deal(), 6.0)).irr
    assert hi > lo


def test_multiple_expansion_component():
    d = lbo.Deal()
    r = lbo.run(replace(d, exit_multiple=d.entry_multiple + 2))
    assert r.bridge["Multiple expansion"] == pytest.approx(2 * r.pnl.ebitda.iloc[-1])


def test_revolver_draws_under_stress():
    d = replace(lbo.Deal(), growth=(-0.25, -0.1, 0.0, 0.0, 0.0), exit_margin=0.08)
    r = lbo.run(d)
    assert r.pnl.revolver.max() > 0


def test_max_entry_multiple_hits_target():
    d = lbo.Deal()
    m = lbo.max_entry_multiple(d, 0.20)
    assert m is not None and 8 < m < 12
    lev = min(5.5, 0.65 * m)
    r = lbo.run(lbo.with_leverage(replace(d, entry_multiple=m), lev))
    assert r.irr == pytest.approx(0.20, abs=1e-4)


def test_cim_import():
    memo = {"financial_highlights": {"revenue": "$45M · p.12", "ebitda": "$12M / 27% · p.14",
                                     "revenue_growth": "18% YoY · p.12"},
            "sector_benchmark": {"ev_ebitda": "8–12x"}}
    d, notes = lbo.from_cim(memo)
    assert d.ltm_revenue == 45 and d.entry_margin == pytest.approx(0.27)
    assert d.entry_multiple == 10 and d.growth[0] == pytest.approx(0.18)
    assert len(notes) == 4
