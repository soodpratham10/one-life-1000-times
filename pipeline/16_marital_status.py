"""
Step 16 of the data pipeline: how Canadians are split by legal marital status,
by year, region, sex and single age (A24).

Why the model needs this: married people die at lower rates than never-married,
divorced or widowed people. Official death rates mix everyone, so to apply a
person's marital-status ratio the engine first divides out the population's
average, which depends on this mix.

Legal marital status is used (not "marital status"), because the marriage and
divorce events (A17) are legal ones: people living common law are counted as
single, separated people as still married.

Input : data/raw/statcan_17100060/17100060.csv   (python pipeline/download_statcan.py 17100060)
Output: data/clean/marital_status.csv
        columns: year, region, sex, age, status, population, share
        status: single, married, separated, widowed, divorced
        age: 15-100 (100 = 100 and over); share = population / all statuses at that age

Run from the project folder:
    python pipeline/16_marital_status.py
"""

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "raw" / "statcan_17100060" / "17100060.csv"
OUT_CSV = ROOT / "data" / "clean" / "marital_status.csv"

FIRST_YEAR = 2015
REGIONS = {
    "Canada": "CA", "Newfoundland and Labrador": "NL", "Prince Edward Island": "PE",
    "Nova Scotia": "NS", "New Brunswick": "NB", "Quebec": "QC", "Ontario": "ON",
    "Manitoba": "MB", "Saskatchewan": "SK", "Alberta": "AB", "British Columbia": "BC",
}
SEXES = {"Males": "M", "Females": "F", "Both sexes": "B"}
STATUSES = {
    "Legal marital status, single (including living common law)": "single",
    "Legal marital status, married (and not separated)": "married",
    "Legal marital status, separated (including living common law)": "separated",
    "Legal marital status, widowed (including living common law)": "widowed",
    "Legal marital status, divorced (including living common law)": "divorced",
}
TOTAL = "Total legal marital status"
SINGLE_AGE = re.compile(r"^(\d+) years?$")
OPEN_AGE = re.compile(r"^100 years and (over|older)$")


def parse_age(label: str):
    if OPEN_AGE.match(label):
        return 100
    m = SINGLE_AGE.match(label)
    return int(m.group(1)) if m else None


def clean() -> pd.DataFrame:
    raw = pd.read_csv(RAW_CSV, usecols=["REF_DATE", "GEO", "Marital status", "Sex", "Age group", "VALUE"])
    raw = raw[(raw["REF_DATE"] >= FIRST_YEAR) & raw["GEO"].isin(REGIONS) & raw["Sex"].isin(SEXES)
              & raw["Marital status"].isin(set(STATUSES) | {TOTAL})].copy()
    missing = set(STATUSES) - set(raw["Marital status"])
    if missing:
        raise ValueError(f"Marital status labels not found (StatCan may have renamed them): {missing}")
    raw["age"] = raw["Age group"].map(parse_age)
    raw = raw[raw["age"].notna() & (raw["age"] >= 15)]
    ages = sorted(int(a) for a in raw["age"].unique())
    if ages != list(range(15, 101)):
        labels = sorted(l for l in raw["Age group"].unique() if "99" in l or "100" in l)
        raise ValueError(f"Expected single ages 15-100, found {ages[:3]}...{ages[-3:]}; labels near 100: {labels}")
    if raw["VALUE"].isna().any():
        raise ValueError(f"{raw['VALUE'].isna().sum()} blank counts from {FIRST_YEAR} on")

    keys = ["REF_DATE", "GEO", "Sex", "age"]
    total = raw[raw["Marital status"] == TOTAL].set_index(keys)["VALUE"].rename("total")
    parts = raw[raw["Marital status"] != TOTAL].copy()
    sums = parts.groupby(keys)["VALUE"].sum()
    gap = (sums - total).abs() / total.clip(lower=1)
    if gap.max() > 0.001:
        raise ValueError(f"Statuses do not add up to the total (worst gap {gap.max():.2%})")
    parts = parts.join(total, on=keys)
    out = pd.DataFrame({
        "year": parts["REF_DATE"].astype(int),
        "region": parts["GEO"].map(REGIONS),
        "sex": parts["Sex"].map(SEXES),
        "age": parts["age"].astype(int),
        "status": parts["Marital status"].map(STATUSES),
        "population": parts["VALUE"].astype(int),
        "share": parts["VALUE"] / parts["total"],
    })
    out = out.sort_values(["year", "region", "sex", "age", "status"]).reset_index(drop=True)
    if out.duplicated(subset=["year", "region", "sex", "age", "status"]).any():
        raise ValueError("Duplicate rows after cleaning")
    return out


def main() -> None:
    if not RAW_CSV.exists():
        raise SystemExit(f"Missing {RAW_CSV.relative_to(ROOT)}: run python pipeline/download_statcan.py 17100060")
    out = clean()
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV.relative_to(ROOT)}: {len(out):,} rows, years {out['year'].min()}-{out['year'].max()}")
    show = out[(out["year"] == 2019) & (out["region"] == "CA") & (out["sex"] != "B") & out["age"].isin([25, 35, 45, 55, 65, 75, 85, 95])]
    print("\n2019, Canada, share of each age by legal marital status (%):")
    print((show.pivot_table(index=["sex", "age"], columns="status", values="share") * 100).round(1)
          [["single", "married", "separated", "divorced", "widowed"]].to_string())


if __name__ == "__main__":
    main()
