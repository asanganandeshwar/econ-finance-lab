# Econ & Finance Lab

Interactive tools in applied microeconomics, industrial organization and private equity, built on public data.

| Tool | Field | What it does |
| --- | --- | --- |
| [LBO Engine](lbo-engine/) | Private equity | Leveraged buyout model with debt schedule, cash sweep, returns attribution, sensitivities and Monte Carlo exit risk |
| [Minimum Wage Evaluator](min-wage-did/) | Labor / causal inference | DiD, event study, synthetic control and triple difference on California's $20 fast-food wage |
| [Rockets & Feathers](rockets-feathers/) | Industrial organization | Asymmetric pass-through from crude oil to gasoline prices, by supply-chain stage and region |

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

The data snapshots are committed. To refresh them, run `python min-wage-did/fetch_qcew.py` and `python rockets-feathers/fetch_eia.py`.
