"""Download BLS QCEW quarterly state-level data for restaurant industries.

Source: BLS QCEW Open Data API, https://www.bls.gov/cew/additional-resources/open-data/
Industry slices: 722513 (limited-service restaurants), 722511 (full-service restaurants).
Keeps private ownership (own_code 5), state-level rows (agglvl_code 58 = state, 6-digit NAICS).
"""
import io
import time
from pathlib import Path

import pandas as pd
import requests

DATA = Path(__file__).parent / "data"
DATA.mkdir(exist_ok=True)
INDUSTRIES = {"722513": "limited", "722511": "full"}
YEARS = range(2019, 2027)
URL = "https://data.bls.gov/cew/data/api/{y}/{q}/industry/{ind}.csv"
HEADERS = {"User-Agent": "econ-research-script/1.0"}


def fetch(y, q, ind):
    r = requests.get(URL.format(y=y, q=q, ind=ind), headers=HEADERS, timeout=60)
    if r.status_code != 200 or not r.text.startswith('"area_fips"'):
        return None
    df = pd.read_csv(io.StringIO(r.text), dtype={"area_fips": str})
    df = df[(df.own_code == 5) & (df.agglvl_code == 58)]
    return df


frames = []
for ind, label in INDUSTRIES.items():
    for y in YEARS:
        for q in range(1, 5):
            df = fetch(y, q, ind)
            if df is None or df.empty:
                print(f"  no data {ind} {y}Q{q}")
                continue
            df["sector"] = label
            frames.append(df)
            print(f"ok {ind} {y}Q{q}: {len(df)} states")
            time.sleep(0.3)

raw = pd.concat(frames, ignore_index=True)
keep = ["area_fips", "year", "qtr", "sector", "disclosure_code", "qtrly_estabs",
        "month1_emplvl", "month2_emplvl", "month3_emplvl", "avg_wkly_wage"]
raw[keep].to_csv(DATA / "qcew_state_restaurants.csv", index=False)
print("saved", len(raw), "rows")
