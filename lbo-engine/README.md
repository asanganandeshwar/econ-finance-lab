# LBO Engine

A five-year leveraged buyout model in Python. It reproduces the mechanics of a standard LBO spreadsheet,
including the circular interest calculation, and adds analysis that is slow to build in Excel: an exact
value-creation bridge, a maximum-price solver, two-way sensitivities and Monte Carlo exit risk. Deal inputs can be
loaded from a CIM Analyzer memo.

## Base case

$250M revenue, EBITDA margin expanding from 20% to 23%, 9.5x entry and exit, 5.5x leverage (4.0x term loan B,
1.5x senior notes).

| Metric | Value |
| --- | --- |
| IRR / MOIC | 20.7% / 2.56x |
| Leverage, entry → exit | 5.5x → 2.0x |
| Maximum entry multiple for a 20% IRR | 9.6x |
| Share of equity gain from EBITDA growth | 77% |

No multiple expansion is assumed; returns come from operating growth and debt paydown.

## Model

- **Sources and uses:** purchase price, transaction and financing fees, minimum cash; sponsor equity balances
- **Debt schedule:** any number of tranches with cash and PIK interest, scheduled amortization, a cash sweep
  applied in priority order, and a revolver that funds shortfalls and is repaid first
- **Interest on average balances,** solved each year by fixed-point iteration
- **Returns:** IRR and MOIC after a management promote on the equity gain
- **Value-creation bridge:** EBITDA growth, multiple expansion, deleveraging, fees and promote, reconciling exactly
  to exit equity
- **Maximum-price solver:** highest entry multiple that clears a target IRR
- **Sensitivities:** IRR by entry × exit multiple and by leverage × revenue growth; leverage covenant test
- **Monte Carlo:** exit multiple, growth and margin shocks; probability of clearing the hurdle and of losing capital
- **Excel export** of every schedule

## Files

- `lbo.py`: model, analytics and CIM import
- `app.py`: Streamlit interface
- `test_lbo.py`: 10 tests (sources equal uses, bridge reconciles, IRR/MOIC consistency, net-debt change equals
  levered free cash flow, solver accuracy, revolver behavior under stress, CIM parsing)
