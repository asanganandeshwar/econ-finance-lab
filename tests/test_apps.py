"""Smoke tests: render every page under a range of inputs and assert no exceptions."""
import itertools
import json
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ENTRY = str(ROOT / "streamlit_app.py")
T = 300


def page(path):
    at = AppTest.from_file(ENTRY, default_timeout=T).run()
    at.switch_page(path).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def ok(at):
    assert not at.exception, [e.value for e in at.exception]


def test_home():
    at = AppTest.from_file(ENTRY, default_timeout=T).run()
    ok(at)
    assert at.title[0].value == "Asanga Nandeshwar"


@pytest.mark.parametrize("sector,outcome", itertools.product(
    ["Limited-service (fast food)", "Full-service restaurants", "Triple difference (limited minus full)"],
    ["Employment", "Average weekly wage", "Establishments"]))
def test_min_wage_sector_outcome(sector, outcome):
    at = page("min-wage-did/app.py")
    at.sidebar.radio[0].set_value(sector).run()
    at.sidebar.radio[1].set_value(outcome).run()
    ok(at)


@pytest.mark.parametrize("controls", ["All other states", "Federal-minimum-wage states", "Neighboring states",
                                      "Custom"])
def test_min_wage_controls_and_trends(controls):
    at = page("min-wage-did/app.py")
    sel = [s for s in at.sidebar.selectbox if s.label == "Control group"][0]
    sel.set_value(controls).run()
    at.sidebar.checkbox[0].check().run()
    ok(at)


def test_min_wage_other_state_and_dates():
    at = page("min-wage-did/app.py")
    sb = {s.label: s for s in at.sidebar.selectbox}
    sb["Treated state"].set_value("NY").run()
    sb = {s.label: s for s in at.sidebar.selectbox}
    sb["Sample start"].set_value("2019Q1").run()
    ok(at)
    sb = {s.label: s for s in at.sidebar.selectbox}
    sb["First treated quarter"].set_value("2022Q1").run()   # invalid ordering -> warning, no crash
    ok(at)
    assert at.warning


@pytest.mark.parametrize("region", ["United States", "California", "West Coast (PADD 5)",
                                    "Rocky Mountain (PADD 4)"])
@pytest.mark.parametrize("stage", ["Crude → retail (full chain)", "Crude → wholesale (refiners)",
                                   "Wholesale → retail (stations)"])
def test_rockets_regions_stages(region, stage):
    at = page("rockets-feathers/app.py")
    at.sidebar.selectbox[0].set_value(region).run()
    at.sidebar.radio[0].set_value(stage).run()
    ok(at)


def test_rockets_model_settings():
    at = page("rockets-feathers/app.py")
    at.sidebar.radio[1].set_value("WTI").run()
    for s in at.sidebar.slider:
        if s.label == "Sample start year":
            s.set_value(2016).run()
        elif s.label == "Lags (weeks)":
            s.set_value(8).run()
        elif s.label == "Response horizon (weeks)":
            s.set_value(20).run()
    ok(at)


def test_lbo_default_and_monte_carlo():
    at = page("lbo-engine/app.py")
    assert any(m.label == "IRR" for m in at.metric)
    [b for b in at.button if b.label == "Run simulation"][0].click().run()
    ok(at)
    assert any("Median IRR" == m.label for m in at.metric)


@pytest.mark.parametrize("entry,exit_,g1", [(6.0, 6.0, 0.0), (14.0, 9.0, 3.0), (8.0, 12.0, 25.0),
                                            (10.0, 10.0, -15.0)])
def test_lbo_scenarios(entry, exit_, g1):
    at = page("lbo-engine/app.py")
    ni = {n.label: n for n in at.sidebar.number_input}
    ni["Entry EV/EBITDA"].set_value(entry).run()
    ni = {n.label: n for n in at.sidebar.number_input}
    ni["Exit EV/EBITDA"].set_value(exit_).run()
    ni = {n.label: n for n in at.sidebar.number_input}
    ni["Growth, year 1 %"].set_value(g1).run()
    ok(at)


def test_lbo_cim_import():
    at = page("lbo-engine/app.py")
    memo = {"company_name": "Acme HVAC",
            "financial_highlights": {"revenue": "$45M · p.12", "ebitda": "$12M / 27% · p.14",
                                     "revenue_growth": "18% YoY"},
            "sector_benchmark": {"ev_ebitda": "8–12x"}}
    at.text_area[0].input(json.dumps(memo))
    [b for b in at.button if b.label == "Load inputs"][0].click().run()
    ok(at)
    assert at.session_state["lbo_name"] == "Acme HVAC"


@pytest.mark.parametrize("preset", ["Stock-and-cash strategic deal", "All-cash, debt-funded acquisition"])
def test_merger_presets(preset):
    at = page("merger-analyzer/app.py")
    [s for s in at.sidebar.selectbox if s.label == "Illustrative case"][0].set_value(preset).run()
    ok(at)
    assert any(m.label == "EPS impact, year 2" for m in at.metric)
    assert any(m.label == "HHI, post-merger" for m in at.metric)


@pytest.mark.parametrize("stock,premium,integ", [(0, 0.0, False), (100, 60.0, True), (25, 15.0, False)])
def test_merger_terms(stock, premium, integ):
    at = page("merger-analyzer/app.py")
    [s for s in at.sidebar.slider if s.label == "Stock consideration %"][0].set_value(stock).run()
    [n for n in at.sidebar.number_input if n.label == "Premium %"][0].set_value(premium).run()
    if integ:
        at.sidebar.checkbox[0].check().run()
    ok(at)


@pytest.mark.parametrize("pair,eff", [(("Firm A", "Firm B"), 0.0), (("Firm D", "Firm E"), 10.0),
                                      (("Firm A", "Firm C"), 30.0)])
def test_merger_competition(pair, eff):
    at = page("merger-analyzer/app.py")
    sel = {s.label: s for s in at.selectbox}
    sel["Merging firm 1"].set_value(pair[0]).run()
    sel = {s.label: s for s in at.selectbox}
    sel["Merging firm 2"].set_value(pair[1]).run()
    [s for s in at.slider if s.label.startswith("Marginal-cost savings")][0].set_value(eff).run()
    ok(at)
