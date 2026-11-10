"""
Step 5 of the data pipeline: build single-age life tables for Prince Edward Island.

StatCan publishes PEI only as an ABRIDGED table (age groups 0, 1-4, 5-9, ..., 85-89, 90+).
We turn it into single ages by borrowing the within-group SHAPE of mortality from
Nova Scotia and New Brunswick, and scaling it to PEI's own LEVEL:

    mu_PEI(x) = k_g * mu_ref(x)        for every age x in group g
    mu_ref(x) = average of -ln(1 - q(x)) for NS and NB (same period and sex)

  - Ages 0-89: k_g makes survival over the group equal PEI's published p_g exactly.
  - Ages 90-109: one k makes life expectancy at 90 equal PEI's published e(90+).
  - Age 110+: q = 1 (everyone dies in the open group), as in the complete tables.

Input : data/raw/statcan_13100140/13100140.csv   (python pipeline/download_statcan.py 13100140)
        data/clean/life_tables.csv                (from 02_clean_life_tables.py)
Output: data/clean/life_tables_pei.csv            (same columns as life_tables.csv, region 'PE')

Run from the project folder:
    python pipeline/05_build_pei_life_table.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "raw" / "statcan_13100140" / "13100140.csv"
COMPLETE_CSV = ROOT / "data" / "clean" / "life_tables.csv"
OUT_CSV = ROOT / "data" / "clean" / "life_tables_pei.csv"

REFERENCE = ["NS", "NB"]
SEXES = {"Both sexes": "B", "Males": "M", "Females": "F"}
ELEMENTS = {
    "Probability of survival in age interval i (pi)": "p_group",
    "Life expectancy (in years) from age interval i (ei)": "e_group",
}
MAX_AGE = 110


def parse_interval(label: str):
    """'0 years' -> (0, 0); '1 to 4 years' -> (1, 4); '90 years and over' -> (90, 110)."""
    if label == "90 years and over":
        return 90, MAX_AGE
    parts = label.split()
    if parts[1] == "to":
        return int(parts[0]), int(parts[2])
    return int(parts[0]), int(parts[0])


def read_pei() -> pd.DataFrame:
    raw = pd.read_csv(RAW_CSV, usecols=["REF_DATE", "GEO", "Age interval", "Sex", "Element", "VALUE"])
    raw = raw[(raw["GEO"] == "Prince Edward Island") & raw["Element"].isin(ELEMENTS)]
    if raw["VALUE"].isna().any():
        raise ValueError("PEI has missing values in p or e; check the source")
    ages = raw["Age interval"].map(parse_interval)
    df = pd.DataFrame({
        "period_start": raw["REF_DATE"].str[:4].astype(int),
        "period_end": raw["REF_DATE"].str[-4:].astype(int),
        "sex": raw["Sex"].map(SEXES),
        "age_lo": ages.str[0],
        "age_hi": ages.str[1],
        "element": raw["Element"].map(ELEMENTS),
        "value": raw["VALUE"],
    })
    return df.pivot(index=["period_start", "period_end", "sex", "age_lo", "age_hi"],
                    columns="element", values="value").reset_index()


def reference_force(complete: pd.DataFrame) -> pd.DataFrame:
    """Average force of mortality of the reference provinces, ages 0-109."""
    ref = complete[complete["region"].isin(REFERENCE) & (complete["age"] < MAX_AGE)].copy()
    ref["mu"] = -np.log(1 - ref["qx"])
    return ref.groupby(["period_start", "sex", "age"], as_index=False)["mu"].mean()


def life_expectancy(qx: np.ndarray, e_open: float) -> np.ndarray:
    """e(x) from single-age qx (deaths spread evenly within each year; open group uses e_open)."""
    lx = np.concatenate([[1.0], np.cumprod(1 - qx[:-1])])
    Lx = np.empty_like(lx)
    Lx[:-1] = (lx[:-1] + lx[1:]) / 2
    Lx[-1] = lx[-1] * e_open
    return np.cumsum(Lx[::-1])[::-1] / lx


def build_one(groups: pd.DataFrame, mu_ref: np.ndarray, e_open_ref: float) -> np.ndarray:
    """Single-age qx (ages 0-110) for one PEI period and sex."""
    mu = np.empty(MAX_AGE)  # ages 0-109

    # Ages 0-89: match each group's published survival exactly
    for _, g in groups[groups["age_lo"] < 90].iterrows():
        ages = slice(int(g["age_lo"]), int(g["age_hi"]) + 1)
        k = -np.log(g["p_group"]) / mu_ref[ages].sum()
        mu[ages] = k * mu_ref[ages]

    # Ages 90-109: find k so that e(90) equals PEI's published e(90+)
    target = groups.loc[groups["age_lo"] == 90, "e_group"].item()

    def e90(k: float) -> float:
        q_old = np.append(1 - np.exp(-k * mu_ref[90:]), 1.0)
        return life_expectancy(q_old, e_open_ref)[0]

    lo, hi = 0.05, 20.0                     # e90 falls as k rises
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if e90(mid) > target else (lo, mid)
    mu[90:] = (lo + hi) / 2 * mu_ref[90:]

    return np.append(1 - np.exp(-mu), 1.0)  # q(110+) = 1


def build() -> pd.DataFrame:
    complete = pd.read_csv(COMPLETE_CSV)
    pei = read_pei()
    ref = reference_force(complete)
    e_open = (complete[complete["region"].isin(REFERENCE) & (complete["age"] == MAX_AGE)]
              .groupby(["period_start", "sex"])["ex"].mean())

    rows = []
    for (start, end, sex), groups in pei.groupby(["period_start", "period_end", "sex"]):
        mu_ref = ref.query("period_start == @start and sex == @sex").sort_values("age")["mu"].to_numpy()
        qx = build_one(groups, mu_ref, e_open[(start, sex)])
        lx = 100_000 * np.concatenate([[1.0], np.cumprod(1 - qx[:-1])])
        ex = life_expectancy(qx, e_open[(start, sex)])
        rows.append(pd.DataFrame({
            "period_start": start, "period_end": end, "region": "PE", "sex": sex,
            "age": np.arange(MAX_AGE + 1), "qx": qx, "px": 1 - qx, "lx": lx, "ex": ex,
        }))
    return pd.concat(rows, ignore_index=True)


def report(df: pd.DataFrame, pei: pd.DataFrame) -> None:
    latest = df["period_start"].max()
    print(f"PEI single-age table: {len(df):,} rows, periods {df['period_start'].min()} to {latest}")
    print(f"\nLife expectancy at birth, PEI {latest}-{latest + 2}: rebuilt vs StatCan's abridged table")
    for sex in ["B", "F", "M"]:
        mine = df.query("period_start == @latest and sex == @sex and age == 0")["ex"].item()
        theirs = pei.query("period_start == @latest and sex == @sex and age_lo == 0")["e_group"].item()
        print(f"   {sex}: {mine:.2f} vs {theirs:.2f}")


if __name__ == "__main__":
    table = build()
    report(table, read_pei())
    table.to_csv(OUT_CSV, index=False)
    print(f"\nSaved {OUT_CSV.relative_to(ROOT)} ({OUT_CSV.stat().st_size / 1e6:.1f} MB)")
