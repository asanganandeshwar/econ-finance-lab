# Applied Economics Portfolio

**Live site:** [asanga-econ-lab.streamlit.app](https://asanga-econ-lab.streamlit.app)

Four analytical tools in private equity, M&A, labor economics and industrial organization, built in Python.
Each lives in its own folder with its own README; all four deploy as one Streamlit site.

| Project | Field | Question | Headline result |
| --- | --- | --- | --- |
| [LBO Engine](lbo-engine/) | Private equity | What return does a leveraged buyout earn, and what drives it? | 20.7% IRR / 2.56x in the base case; maximum price 9.6x for a 20% IRR |
| [Merger Analyzer](merger-analyzer/) | M&A / antitrust | Does a deal add to EPS, and does it harm competition? | Illustrative #1–#2 merger: +1,320 HHI, 6–9% price increases, 18% cost savings needed to offset consumer harm |
| [The $20 Fast-Food Wage](min-wage-did/) | Labor economics | Did California's AB 1228 reduce fast-food employment? | −2.9% vs. other states, not significant (p = 0.16); ≈0 once statewide restaurant trends are netted out |
| [Rockets and Feathers](rockets-feathers/) | Industrial organization | Do gasoline prices rise faster than they fall? | 63% of cost increases reach the pump in a week vs. 23% of decreases; the asymmetry is at the station level |

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
pytest                      # 63 unit and app tests
```

Data snapshots are included. To refresh them: `python min-wage-did/fetch_qcew.py` and
`python rockets-feathers/fetch_eia.py`.

## Structure

```
streamlit_app.py     site entry point and navigation
home.py              landing page
ui.py                shared typography, palette and chart template
lbo-engine/          lbo.py (model), app.py (interface), test_lbo.py
merger-analyzer/     merger.py (deal and competition models), app.py, test_merger.py
min-wage-did/        did.py (estimators), app.py, fetch_qcew.py, data/
rockets-feathers/    rf.py (model), app.py, fetch_eia.py, data/
tests/               app smoke tests across input combinations
```
