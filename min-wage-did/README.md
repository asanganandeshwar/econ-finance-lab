# The $20 Fast-Food Wage

California's AB 1228 raised the minimum wage at fast-food chains with 60 or more locations from $16 to $20 an hour
on April 1, 2024. This project estimates its effect on employment and wages with BLS Quarterly Census of
Employment and Wages data for all 50 states and DC.

## Results (2022Q1–2026Q1, California vs. all other states)

| Outcome | Effect | Permutation p |
| --- | --- | --- |
| Fast-food average weekly wage | +5.5% | 0.06 |
| Fast-food employment, difference-in-differences | −2.9% | 0.16 |
| Fast-food employment, synthetic control | −4.0% | 0.31 |
| Full-service restaurant employment (not covered by the law) | −3.2% | 0.18 |
| Triple difference: fast food minus full service | +0.3% | 0.92 |

The law raised fast-food pay. Fast-food employment fell about 3% relative to other states, but full-service
restaurants in California, which the law does not cover, fell by a similar amount. Netting out that statewide
restaurant trend leaves no detectable employment effect. 29 of 36 robustness specifications are negative, and one
is significant at the 10% level.

A conventional clustered standard error gives p < 0.001 for the same −2.9% estimate. With a single treated state,
clustered errors understate uncertainty (Conley and Taber 2011), so inference here relies on permutation tests.

## Methods

- Seasonality removed with state × quarter-of-year effects estimated on the pre-period only
- Quarters between signing (September 2023) and the effective date excluded
- Event study with a placebo band built by assigning the policy to every control state
- Synthetic control with ridge-penalized weights; with more donor states than pre-period quarters, unpenalized
  weights are not unique
- Triple difference using full-service restaurants in the same state
- Specification curve across control groups, sectors, sample windows and state trends
- Any state and policy date can be analyzed

## Files

- `fetch_qcew.py`: downloads QCEW data for NAICS 722513 and 722511
- `did.py`: estimators and inference
- `app.py`: Streamlit interface

## Limitations

QCEW includes limited-service restaurants exempt from the law, which biases estimates toward zero. State-level
data do not separate hours from headcount.
