"""Estimation engine: difference-in-differences, event study, synthetic control,
triple difference, and permutation inference for a single treated state.

All outcomes are in logs. Seasonality is removed with state-by-quarter-of-year
fixed effects estimated on the pre-period only, so post-period data never
leaks into the counterfactual.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from linearmodels.iv.absorbing import AbsorbingLS
from scipy.optimize import minimize

DATA = Path(__file__).parent / "data" / "qcew_state_restaurants.csv"

FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
    "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY",
}
# States bound by the $7.25 federal minimum throughout 2022-2026 (no state-level increases).
FED_MIN_STATES = ["AL", "GA", "ID", "IN", "IA", "KS", "KY", "LA", "MS", "NH", "NC",
                  "ND", "OK", "PA", "SC", "TN", "TX", "UT", "WI", "WY"]
NEIGHBORS = {"CA": ["AZ", "NV", "OR", "WA"]}

OUTCOMES = {"Employment": "emp", "Average weekly wage": "wage", "Establishments": "estabs"}
SECTORS = {
    "Limited-service (fast food)": "limited",
    "Full-service restaurants": "full",
    "Triple difference (limited minus full)": "ddd",
}


def tq(label: str) -> int:
    y, q = label.upper().split("Q")
    return int(y) * 4 + int(q) - 1


def lab(t: int) -> str:
    return f"{t // 4}Q{t % 4 + 1}"


def load(path: Path = DATA) -> pd.DataFrame:
    d = pd.read_csv(path, dtype={"area_fips": str})
    d["state"] = d.area_fips.str[:2].map(FIPS)
    d = d.dropna(subset=["state"])
    d["emp"] = d[["month1_emplvl", "month2_emplvl", "month3_emplvl"]].mean(axis=1)
    d["wage"] = d.avg_wkly_wage
    d["estabs"] = d.qtrly_estabs
    d["t"] = d.year * 4 + d.qtr - 1
    return d[["state", "sector", "t", "year", "qtr", "emp", "wage", "estabs"]]


def outcome_matrix(df: pd.DataFrame, outcome: str, sector: str) -> pd.DataFrame:
    """Wide log-outcome matrix: rows = quarter index t, columns = state."""
    def wide(sec):
        w = df[df.sector == sec].pivot_table(index="t", columns="state", values=outcome)
        return np.log(w.where(w > 0))
    if sector == "ddd":
        return wide("limited") - wide("full")
    return wide(sector)


def residualize(Y: pd.DataFrame, pre: np.ndarray, trend: bool = False) -> pd.DataFrame:
    """Remove state x season means (and optionally a state linear trend), fit on pre-period only."""
    t = Y.index.values.astype(float)
    season = Y.index.values % 4
    cols = [(season == k).astype(float) for k in range(4)]
    if trend:
        cols.append(t - t[pre].mean())
    X = np.column_stack(cols)
    out = {}
    for s in Y.columns:
        y = Y[s].values
        beta = np.linalg.lstsq(X[pre], y[pre], rcond=None)[0]
        out[s] = y - X @ beta
    return pd.DataFrame(out, index=Y.index)


@dataclass
class Spec:
    treated: str = "CA"
    controls: tuple = ()
    outcome: str = "emp"
    sector: str = "limited"
    sample_start: str = "2022Q1"
    pre_end: str = "2023Q3"       # last quarter before the law was signed (Sep 28, 2023)
    post_start: str = "2024Q2"    # first quarter with the $20 wage (Apr 1, 2024)
    trend: bool = False


@dataclass
class Result:
    spec: Spec
    R: pd.DataFrame               # residualized log outcomes
    gap: pd.Series                # treated minus control mean, by quarter
    placebo_gaps: pd.DataFrame    # same gap with each control state as fake treated
    est: float                    # DiD in log points
    placebo_est: pd.Series
    p_perm: float
    pre_mask: np.ndarray
    post_mask: np.ndarray
    base_level: float             # treated pre-period mean level (for implied jobs)


def prepare(df: pd.DataFrame, spec: Spec):
    Y = outcome_matrix(df, spec.outcome, spec.sector)
    Y = Y.loc[tq(spec.sample_start):]
    states = [spec.treated] + [c for c in spec.controls if c != spec.treated]
    Y = Y[[s for s in states if s in Y.columns]].dropna(axis=1)
    pre = Y.index.values <= tq(spec.pre_end)
    post = Y.index.values >= tq(spec.post_start)
    return Y, pre, post


def run_did(df: pd.DataFrame, spec: Spec) -> Result:
    Y, pre, post = prepare(df, spec)
    controls = [c for c in Y.columns if c != spec.treated]
    R = residualize(Y, pre, spec.trend)
    gap = R[spec.treated] - R[controls].mean(axis=1)
    est = gap[post].mean() - gap[pre].mean()

    plac = {c: R[c] - R[[x for x in controls if x != c]].mean(axis=1) for c in controls}
    P = pd.DataFrame(plac)
    pest = P[post].mean() - P[pre].mean()
    p = (1 + (pest.abs() >= abs(est)).sum()) / (1 + len(pest))

    sec = "limited" if spec.sector == "ddd" else spec.sector
    lvl = df[(df.state == spec.treated) & (df.sector == sec)].set_index("t")[spec.outcome]
    base = lvl.loc[Y.index[pre]].mean()
    return Result(spec, R, gap, P, est, pest, p, pre, post, base)


def twfe_regression(df: pd.DataFrame, spec: Spec):
    """Conventional TWFE DiD with state-clustered SEs, for comparison only.
    With one treated cluster these SEs are not reliable (Conley and Taber, 2011)."""
    Y, pre, post = prepare(df, spec)
    long = Y.stack().rename("y").reset_index()
    long.columns = ["t", "state", "y"]
    keep = set(Y.index[pre]) | set(Y.index[post])
    long = long[long.t.isin(keep)].copy()
    long["season"] = long.t % 4
    long["treat_post"] = ((long.state == spec.treated) & (long.t >= tq(spec.post_start))).astype(int)
    long["state_season"] = (long.state + "_" + long.season.astype(str)).astype("category")
    long["tcat"] = long.t.astype("category")
    exog = long[["treat_post"]].astype(float)
    if spec.trend:
        for s in long.state.unique():
            exog[f"trend_{s}"] = np.where(long.state == s, long.t - long.t.mean(), 0.0)
    clusters = long.state.astype("category").cat.codes.to_frame("state")
    m = AbsorbingLS(long.y, exog, absorb=long[["state_season", "tcat"]], drop_absorbed=True).fit(
        cov_type="clustered", clusters=clusters)
    return m


def synth(R: pd.DataFrame, treated: str, donors: list[str], pre: np.ndarray):
    X0 = R.loc[pre, donors].values
    x1 = R.loc[pre, treated].values
    n = len(donors)
    res = minimize(lambda w: ((x1 - X0 @ w) ** 2).sum(), np.full(n, 1 / n), method="SLSQP",
                   bounds=[(0, 1)] * n, constraints={"type": "eq", "fun": lambda w: w.sum() - 1},
                   options={"maxiter": 500, "ftol": 1e-12})
    w = pd.Series(res.x, index=donors).clip(lower=0)
    w /= w.sum()
    synthetic = R[donors] @ w
    return w, synthetic


def run_synth(res: Result):
    R, pre, post, tr = res.R, res.pre_mask, res.post_mask, res.spec.treated
    donors = [c for c in R.columns if c != tr]
    w, s = synth(R, tr, donors, pre)
    gap = R[tr] - s

    def ratio(g):
        return np.sqrt((g[post] ** 2).mean()) / max(np.sqrt((g[pre] ** 2).mean()), 1e-9)

    ratios, plac = {}, {}
    for c in donors:
        _, sc = synth(R, c, [d for d in donors if d != c], pre)
        g = R[c] - sc
        plac[c] = g
        ratios[c] = ratio(g)
    r_t = ratio(gap)
    ratios = pd.Series(ratios)
    p = (1 + (ratios >= r_t).sum()) / (1 + len(ratios))
    est = gap[post].mean() - gap[pre].mean()
    return dict(weights=w.sort_values(ascending=False), synthetic=s, gap=gap,
                placebo=pd.DataFrame(plac), ratio=r_t, ratios=ratios, p=p, est=est)


def control_sets(treated: str, all_states: list[str]) -> dict[str, list[str]]:
    others = [s for s in all_states if s != treated]
    sets = {"All other states": others,
            "Federal-minimum-wage states": [s for s in FED_MIN_STATES if s != treated]}
    if treated in NEIGHBORS:
        sets["Neighboring states"] = NEIGHBORS[treated]
    return sets


def spec_curve(df: pd.DataFrame, base: Spec) -> pd.DataFrame:
    """Re-estimate across control groups, sectors, sample starts and trend choices."""
    states = sorted(df.state.unique())
    rows = []
    for cname, ctrls in control_sets(base.treated, states).items():
        for sec_name, sec in SECTORS.items():
            for start in ["2019Q1", "2022Q1"]:
                for trend in [False, True]:
                    s = Spec(base.treated, tuple(ctrls), base.outcome, sec, start,
                             base.pre_end, base.post_start, trend)
                    try:
                        r = run_did(df, s)
                    except Exception:
                        continue
                    rows.append(dict(controls=cname, sector=sec_name, sample_start=start,
                                     state_trends=trend, est_pct=100 * (np.exp(r.est) - 1),
                                     p_perm=r.p_perm, n_controls=len(r.placebo_est)))
    return pd.DataFrame(rows).sort_values("est_pct").reset_index(drop=True)
