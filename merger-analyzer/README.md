# Merger Analyzer

Two views of the same transaction. The deal model asks whether an acquisition adds to the acquirer's earnings per
share. The competition model asks whether it would reduce competition, using the screens antitrust agencies
apply and a structural simulation of post-merger prices. The cases are illustrative, and every input is editable.

## Deal economics

- Offer value, enterprise value and multiples paid
- Funding mix of stock, new debt and cash on hand; new debt also funds its own financing fees
- Purchase-price allocation: amortization of acquired intangibles on the excess over book value
- Synergy phase-in and optional integration costs
- Pro forma EPS for three years, breakeven synergies, ownership split and pro forma leverage
- Value created for acquirer shareholders: capitalized synergies against the premium paid
- Sensitivity of EPS impact to premium, stock mix and synergies

**Default case:** a 30% premium, half stock and half debt, with $150M of run-rate synergies. The deal is 3.7%
dilutive in year 2 and needs $295M of synergies to break even.

## Competitive effects

- HHI and change in HHI against the 2023 U.S. Merger Guidelines structural presumption
- Diversion ratios and gross upward pricing pressure (GUPPI)
- Compensating marginal cost reductions (Werden 1996)
- Logit Bertrand merger simulation calibrated to shares, prices and one observed margin: price effects for merging
  firms and rivals, consumer surplus and merging-firm profits
- Cost savings needed to leave consumers no worse off

**Default case:** in a five-firm market, a merger of the 30% and 22% firms raises HHI by 1,320 to 3,504, which is
presumptively anticompetitive. Simulated prices rise 6–9% at the merging firms and under 1% at rivals, consumer
surplus falls $396M, and marginal-cost savings of 18% would be needed to offset the harm.

## Validation

`test_merger.py` (11 tests) checks, among other things, that:

- an all-stock deal at equal P/E with no synergies is EPS-neutral
- breakeven synergies give exactly zero dilution
- the calibrated logit model reproduces observed pre-merger prices and shares
- Werden's closed-form compensating cost reductions match those implied by the simulation, and holding prices
  fixed when applied

## Files

- `merger.py`: deal model, concentration screens, GUPPI, CMCR and logit merger simulation
- `app.py`: Streamlit interface
