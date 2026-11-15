# Minimum Wage Policy Evaluator

An interactive tool for evaluating state minimum wage policies with difference-in-differences, event studies,
synthetic control, and randomization inference. The default case is **California's AB 1228**, which raised
the minimum wage for fast-food chains from $16 to $20 an hour on April 1, 2024.

## Headline results (BLS QCEW, 2022Q1–2026Q1)

| Specification | Effect | Permutation p |
| --- | --- | --- |
| Limited-service employment vs all other states | −2.9% | 0.16 |
| Limited-service employment, synthetic control | −5.0% | 0.10 |
| Limited-service average weekly wage (first stage) | +5.5% | 0.06 |
| Triple difference: limited minus full-service employment | +0.3% | 0.92 |

The law clearly raised fast-food pay. Fast-food employment fell about 3% relative to other states, but
full-service restaurants in California, which the law does not cover, fell by about the same amount. Once that
California-wide restaurant shock is netted out (triple difference), there is no detectable employment effect.
The conventional clustered standard error makes the −2.9% look highly significant (p < 0.001). With a single
treated state, that is misleading (Conley and Taber 2011), and the tool shows both tests side by side.

## What the tool does

- **DiD and event study**, with seasonality removed using state × quarter-of-year effects fit on pre-period data only
- **Anticipation window** between signing (Sep 2023) and the effective date, excluded from the estimate
- **Placebo-state permutation inference** and a 90% placebo band on the event study
- **Synthetic control** with donor weights and RMSPE-ratio inference
- **Triple difference**, using full-service restaurants in the same state as an extra control
- **Specification curve** across control groups, sectors, sample windows, and state trends
- Works for any state and any policy date: change the treated state and quarters in the sidebar

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r ../requirements.txt
python fetch_qcew.py        # downloads ~3,000 state-quarter rows from the BLS QCEW open-data API
streamlit run app.py
```

## Files

- `fetch_qcew.py`: downloads QCEW data for NAICS 722513 (limited-service) and 722511 (full-service)
- `did.py`: estimation engine (DiD, event study, synthetic control, TWFE, permutation tests, specification curve)
- `app.py`: Streamlit interface

## Limitations

QCEW counts all limited-service restaurants, including the small chains AB 1228 exempts, which biases estimates
toward zero. State-level data cannot separate hours from headcount, and other California shocks after April 2024
are not modeled separately.
