"""Download weekly price series from EIA (no API key needed; history XLS files).

Source: U.S. Energy Information Administration, https://www.eia.gov/petroleum/
"""
from pathlib import Path

import pandas as pd
import requests

DATA = Path(__file__).parent / "data"
DATA.mkdir(exist_ok=True)
BASE = "https://www.eia.gov/dnav/pet/hist_xls/{code}w.xls"

SERIES = {
    # crude oil spot, $/barrel
    "wti": "RWTC",
    "brent": "RBRTE",
    # wholesale (spot) gasoline, $/gallon
    "spot_nyh": "EER_EPMRU_PF4_Y35NY_DPG",   # NY Harbor conventional regular
    "spot_gulf": "EER_EPMRU_PF4_RGC_DPG",    # US Gulf Coast conventional regular
    "spot_la": "EER_EPMRR_PF4_Y05LA_DPG",    # Los Angeles RBOB regular
    # retail regular gasoline, $/gallon
    "retail_us": "EMM_EPMR_PTE_NUS_DPG",
    "retail_east": "EMM_EPMR_PTE_R10_DPG",
    "retail_midwest": "EMM_EPMR_PTE_R20_DPG",
    "retail_gulf": "EMM_EPMR_PTE_R30_DPG",
    "retail_rocky": "EMM_EPMR_PTE_R40_DPG",
    "retail_west": "EMM_EPMR_PTE_R50_DPG",
    "retail_ca": "EMM_EPMR_PTE_SCA_DPG",
}


def fetch(code):
    r = requests.get(BASE.format(code=code), headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    path = DATA / f"{code}.xls"
    path.write_bytes(r.content)
    df = pd.read_excel(path, sheet_name="Data 1", skiprows=2)
    df.columns = ["date", "value"]
    return df.dropna()


frames = []
for name, code in SERIES.items():
    s = fetch(code)
    s["series"] = name
    frames.append(s)
    print(f"{name:15s} {s.date.min():%Y-%m-%d} -> {s.date.max():%Y-%m-%d}  n={len(s)}")

long = pd.concat(frames)
wide = long.pivot_table(index="date", columns="series", values="value")
wide.to_csv(DATA / "eia_weekly_prices.csv")
print("saved", wide.shape)
