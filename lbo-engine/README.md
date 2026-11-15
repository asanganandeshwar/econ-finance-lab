# LBO Engine

An interactive leveraged buyout model in Python. It replicates a banker-style LBO spreadsheet, including the
circular interest calculation, and adds analytics a spreadsheet makes painful: an exact value-creation bridge,
a max-price solver, sensitivity grids and Monte Carlo exit risk. It imports deal inputs straight from my
**CIM Analyzer** JSON memos.

## Features

- **Sources & uses** with transaction and financing fees, minimum cash, and sponsor equity as the plug
- **Tranche-level debt schedule**: any number of tranches with cash and PIK interest, mandatory amortization,
  an excess-cash sweep in priority order, and a revolver that draws on shortfalls and is repaid first
- **Average-balance interest**, solved by fixed-point iteration (the spreadsheet circular reference)
- **Returns**: IRR, MOIC, and a management promote on the equity gain
- **Value-creation bridge**, exact to the dollar: EBITDA growth, multiple expansion, deleveraging, fees, promote
- **Max entry price solver**: the highest EV/EBITDA that still clears a target IRR
- **Sensitivities**: IRR heatmaps for entry × exit multiple and leverage × revenue growth
- **Credit stats** with a leverage covenant test
- **Monte Carlo**: shocks to the exit multiple, growth and margin; P(hitting the hurdle), P(loss), tail IRR
- **Excel export** of every schedule

## Base case

$250m revenue, 20% → 23% margin, 10.0x in and out, 5.5x leverage (4.0x TLB + 1.5x notes):
**2.45x MOIC / 19.6% IRR**. EBITDA growth drives about 80% of value creation. The sponsor can pay up to
**9.9x** for a 20% IRR.

## Run and test

```bash
pip install -r ../requirements.txt
streamlit run app.py
python -m pytest test_lbo.py      # 10 tests: S&U balance, bridge tie-out, IRR/MOIC, cash-flow identity, solver
```
