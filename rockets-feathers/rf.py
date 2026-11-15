"""Asymmetric price pass-through ("rockets and feathers") engine.

Model (Borenstein, Cameron and Gilbert 1997, asymmetric error-correction):

  Long run:   P_t = a + b C_t + u_t
  Short run:  dP_t = sum_{i=0..k} (bp_i dC+_{t-i} + bm_i dC-_{t-i})
                   + sum_{j=1..k} (gp_j dP+_{t-j} + gm_j dP-_{t-j})
                   + theta u_{t-1} + e_t

P is the downstream price and C the upstream cost, both in $/gallon, weekly.
Newey-West (HAC) standard errors. Cumulative response functions are simulated
from the estimated system for a permanent 10-cent cost increase and decrease.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, coint

DATA = Path(__file__).parent / "data" / "eia_weekly_prices.csv"

REGIONS = {
    "United States": ("retail_us", "spot_gulf"),
    "California": ("retail_ca", "spot_la"),
    "West Coast (PADD 5)": ("retail_west", "spot_la"),
    "East Coast (PADD 1)": ("retail_east", "spot_nyh"),
    "Midwest (PADD 2)": ("retail_midwest", "spot_gulf"),
    "Gulf Coast (PADD 3)": ("retail_gulf", "spot_gulf"),
    "Rocky Mountain (PADD 4)": ("retail_rocky", "spot_gulf"),
}
STAGES = {
    "Crude → retail (full chain)": ("crude", "retail"),
    "Crude → wholesale (refiners)": ("crude", "spot"),
    "Wholesale → retail (stations)": ("spot", "retail"),
}


def load(path: Path = DATA) -> pd.DataFrame:
    """Weekly panel aligned to EIA's Monday retail survey dates."""
    raw = pd.read_csv(path, parse_dates=["date"]).set_index("date")
    retail = raw.filter(like="retail_").dropna(how="all")
    upstream = raw[[c for c in raw.columns if not c.startswith("retail_")]].dropna(how="all")
    upstream.index = upstream.index + pd.Timedelta(days=3)  # Friday week-ending -> next Monday
    df = retail.join(upstream, how="inner")
    df["wti_gal"] = df["wti"] / 42.0
    df["brent_gal"] = df["brent"] / 42.0
    return df


def series_for(df: pd.DataFrame, region: str, stage: str, crude: str = "brent_gal"):
    retail, spot = REGIONS[region]
    up, down = STAGES[stage]
    name = {"crude": crude, "spot": spot, "retail": retail}
    out = df[[name[up], name[down]]].dropna()
    out.columns = ["C", "P"]
    return out


@dataclass
class Fit:
    model: object
    a: float
    b: float
    theta: float
    k: int
    params: pd.Series
    wald_sum_p: float      # H0: sum bp = sum bm
    wald_all_p: float      # H0: bp_i = bm_i for all i
    coint_p: float
    adf_resid_p: float
    data: pd.DataFrame
    resp_up: np.ndarray
    resp_down: np.ndarray


def fit(s: pd.DataFrame, k: int = 4, horizon: int = 16) -> Fit:
    s = s.copy()
    lr = sm.OLS(s.P, sm.add_constant(s.C)).fit()
    a, b = lr.params["const"], lr.params["C"]
    s["u"] = s.P - a - b * s.C
    dC, dP = s.C.diff(), s.P.diff()
    X = pd.DataFrame(index=s.index)
    for i in range(k + 1):
        X[f"dCp{i}"] = dC.clip(lower=0).shift(i)
        X[f"dCm{i}"] = dC.clip(upper=0).shift(i)
    for j in range(1, k + 1):
        X[f"dPp{j}"] = dP.clip(lower=0).shift(j)
        X[f"dPm{j}"] = dP.clip(upper=0).shift(j)
    X["ect"] = s.u.shift(1)
    X = sm.add_constant(X)
    d = pd.concat([dP.rename("dP"), X], axis=1).dropna()
    m = sm.OLS(d.dP, d.drop(columns="dP")).fit(cov_type="HAC", cov_kwds={"maxlags": k + 1})

    sum_test = " + ".join(f"dCp{i}" for i in range(k + 1)) + " = " + " + ".join(f"dCm{i}" for i in range(k + 1))
    wald_sum = m.wald_test(sum_test, scalar=True).pvalue
    R = np.zeros((k + 1, len(m.params)))
    names = list(m.params.index)
    for i in range(k + 1):
        R[i, names.index(f"dCp{i}")] = 1
        R[i, names.index(f"dCm{i}")] = -1
    wald_all = m.wald_test(R, scalar=True).pvalue

    coint_p = coint(s.P, s.C)[1]
    adf_p = adfuller(s.u.dropna(), autolag="AIC")[1]
    up = simulate(m.params, k, b, +0.10, horizon)
    down = simulate(m.params, k, b, -0.10, horizon)
    return Fit(m, a, b, m.params["ect"], k, m.params, wald_sum, wald_all, coint_p, adf_p, s, up / b, down / b)


def simulate(p: pd.Series, k: int, b: float, shock: float, horizon: int) -> np.ndarray:
    """Cumulative price response per $1 of a permanent cost change of size `shock` at week 0."""
    dC = np.zeros(horizon + k + 1)
    dC[k] = shock                      # index k = week 0, padding for lags
    dP = np.zeros(horizon + k + 1)
    u = np.zeros(horizon + k + 1)      # deviation from long-run equilibrium
    P = np.zeros(horizon + k + 1)
    Cc = np.zeros(horizon + k + 1)
    for t in range(k, horizon + k + 1):
        Cc[t] = Cc[t - 1] + dC[t]
        val = 0.0
        for i in range(k + 1):
            x = dC[t - i]
            val += p[f"dCp{i}"] * max(x, 0) + p[f"dCm{i}"] * min(x, 0)
        for j in range(1, k + 1):
            y = dP[t - j]
            val += p[f"dPp{j}"] * max(y, 0) + p[f"dPm{j}"] * min(y, 0)
        val += p["ect"] * u[t - 1]
        dP[t] = val
        P[t] = P[t - 1] + dP[t]
        u[t] = P[t] - b * Cc[t]
    return P[k:] / shock


def margin_asymmetry(s: pd.DataFrame, window: int = 4) -> pd.DataFrame:
    """Margin (P - C) against the cost change over the previous `window` weeks."""
    out = pd.DataFrame({
        "margin": s.P - s.C,
        "cost_change": s.C - s.C.shift(window),
    }).dropna()
    out["regime"] = np.where(out.cost_change > 0, "Costs rising", "Costs falling")
    return out
