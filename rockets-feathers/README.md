# Rockets and Feathers

Do gasoline prices rise faster than they fall? This project estimates how quickly crude oil and wholesale cost
changes reach retail prices, tests whether increases and decreases pass through at different speeds, and
identifies the stage of the supply chain where any asymmetry arises.

## Results (United States, weekly EIA data, 2010–2026, Brent crude)

| Link | Same-week pass-through, increases | Same-week, decreases | Symmetry test p |
| --- | --- | --- | --- |
| Crude → retail (full chain) | 63% | 23% | 0.003 |
| Wholesale → retail (stations) | 62% | 21% | < 0.001 |
| Crude → wholesale (refiners) | 96% | 79% | 0.79 |

Stations pass about 60% of a cost increase to the pump within a week but only about 20% of a decrease. Refiner
pricing is statistically symmetric, so the asymmetry arises at retail, which is consistent with consumer search
costs and focal-point pricing. Retail spreads average 96¢ per gallon when wholesale costs are falling and 85¢ when
they are rising. The slower pass-through of decreases costs U.S. consumers about $220 million for each 10-cent fall
in costs.

## Methods

- Asymmetric error-correction model (Borenstein, Cameron and Gilbert 1997) with Newey–West standard errors
- Wald tests of symmetry, lag by lag and cumulatively; Engle–Granger cointegration diagnostics
- Simulated cumulative response to a permanent ±10¢ cost change
- Estimates for each link of the supply chain and for the United States, California and the five PADD regions

## Files

- `fetch_eia.py`: downloads 12 weekly EIA price series
- `rf.py`: estimation, tests and response simulation
- `app.py`: Streamlit interface

## Limitations

Retail prices include taxes, which change in discrete steps. The long-run relationship is estimated in nominal
levels. California's retail–wholesale spread shifts with state fuel policy and refinery outages, which weakens
cointegration there.
