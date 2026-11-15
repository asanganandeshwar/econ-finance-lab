# Rockets & Feathers

An industrial organization tool that tests whether US gasoline prices **rise like rockets and fall like
feathers**, and finds the stage of the supply chain where the asymmetry comes from.

## Headline results (EIA weekly data, 2010–2026, Brent crude)

| United States | Increase | Decrease |
| --- | --- | --- |
| Crude → retail, same-week pass-through | 63% | 23% |
| Wholesale → retail, same-week pass-through | 62% | 21% |
| Crude → wholesale, symmetry test (Wald p) | 0.79 | |
| Wholesale → retail, symmetry test (Wald p) | < 0.001 | |

Gas stations pass about 60% of a cost increase to the pump within a week, but only about 20% of a decrease, and
decreases take about 5 weeks to catch up. The asymmetry sits at the **retail** stage: refiners pass crude price
changes through roughly symmetrically. That pattern is consistent with consumer search-cost and focal-price
explanations rather than refinery capacity. Nationally, the slow decline costs consumers roughly **$220 million
per 10-cent drop in costs**.

## What the tool does

- Asymmetric error-correction model (Borenstein, Cameron and Gilbert 1997) with Newey–West standard errors
- Wald tests of symmetry, lag by lag and cumulatively; Engle–Granger cointegration diagnostics
- Simulated cumulative response curves for a permanent ±10¢ cost change
- **Supply-chain decomposition**: crude → wholesale (refiners), wholesale → retail (stations), and the full chain
- **Margin analysis**: retail spreads when costs are rising vs falling
- **Regional comparison** across the US, California, and the five PADD regions
- Consumer-cost estimate in dollars, based on regional gallon volumes

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r ../requirements.txt
python fetch_eia.py        # downloads 12 weekly EIA price series (no API key needed)
streamlit run app.py
```

## Files

- `fetch_eia.py`: downloads crude, wholesale and retail gasoline prices from EIA
- `rf.py`: model estimation, Wald tests, impulse-response simulation, margin analysis
- `app.py`: Streamlit interface

## Limitations

Retail prices include taxes, which change in discrete steps. The long-run equation is in nominal levels, and
California's retail–wholesale spread shifts structurally (cap-and-trade, LCFS, the 2015 Torrance refinery
outage), so cointegration is weak there and long-horizon responses should be read with care.
