"""
Step 7 of the data pipeline: population on July 1 by year, province, sex and single age.
Used as the denominator for event rates (crashes, and later marriage, births, etc.).

StatCan reports this table by GENDER ("Men+", "Women+": non-binary people are
distributed between the two). We map Men+ -> M and Women+ -> F; see A12 in
docs/assumptions.md for why that is close enough to sex for this model.

Input : data/raw/statcan_17100005/17100005.csv   (python pipeline/download_statcan.py 17100005)
Output: data/clean/population.csv
        columns: year, region, sex, age (0-100, 100 = 100 and over), population

Run from the project folder:
    python pipeline/07_clean_population.py
"""

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "raw" / "statcan_17100005" / "17100005.csv"
OUT_CSV = ROOT / "data" / "clean" / "population.csv"

REGIONS = {
    "Canada": "CA", "Newfoundland and Labrador": "NL", "Prince Edward Island": "PE",
    "Nova Scotia": "NS", "New Brunswick": "NB", "Quebec": "QC", "Ontario": "ON",
    "Manitoba": "MB", "Saskatchewan": "SK", "Alberta": "AB", "British Columbia": "BC",
}
GENDERS = {"Men+": "M", "Women+": "F", "Total - gender": "B"}
# StatCan only publishes every single age 0-100+ from 2000 on: before 1991 the oldest
# group is "90 and older" (no single ages 90-100), and in 1991-1999 ages 90-100 are blank.
# The model needs 2019 on, so we keep 2000 on and require it to be complete.
FIRST_YEAR = 2000
SINGLE_AGE = re.compile(r"^(\d+) years?$")
OPEN_AGE = re.compile(r"^100 years and (over|older)$")   # StatCan's wording varies


def parse_single_age(label: str):
    """'0 years' -> 0, '1 year' -> 1, '100 years and over/older' -> 100.
    Age groups ('0 to 4 years', '65 years and older', ...) and averages -> None."""
    if OPEN_AGE.match(label):
        return 100
    m = SINGLE_AGE.match(label)
    return int(m.group(1)) if m else None


def clean() -> pd.DataFrame:
    raw = pd.read_csv(RAW_CSV, usecols=["REF_DATE", "GEO", "Gender", "Age group", "UOM", "VALUE"])
    raw = raw[(raw["UOM"] == "Persons") & raw["GEO"].isin(REGIONS) & (raw["REF_DATE"] >= FIRST_YEAR)]

    unknown = set(raw["Gender"]) - set(GENDERS)
    if unknown:
        raise ValueError(f"Unexpected gender labels: {unknown}")

    raw["age"] = raw["Age group"].map(parse_single_age)
    totals = raw[raw["Age group"] == "All ages"]
    single = raw[raw["age"].notna()]

    ages_found = sorted(int(a) for a in single["age"].unique())
    if ages_found != list(range(101)):
        near_100 = sorted(l for l in raw["Age group"].unique() if "100" in l or "99" in l)
        raise ValueError(
            f"Expected single ages 0-100, found {ages_found[:3]}...{ages_found[-3:]}.\n"
            f"Age labels mentioning 99 or 100 in the file: {near_100}"
        )
    # From 2000 on there must be no blanks and every year must have all 101 ages
    if single["VALUE"].isna().any():
        gaps = single[single["VALUE"].isna()]
        raise ValueError(f"{len(gaps)} blank population counts from {FIRST_YEAR} on, e.g.\n"
                         f"{gaps[['REF_DATE', 'GEO', 'Gender', 'Age group']].head()}")
    ages_per_year = single.groupby(["REF_DATE", "GEO", "Gender"])["age"].nunique()
    if (ages_per_year != 101).any():
        short = ages_per_year[ages_per_year != 101]
        raise ValueError(f"Some years do not have all 101 single ages:\n{short.head()}")

    out = pd.DataFrame({
        "year": single["REF_DATE"].astype(int),
        "region": single["GEO"].map(REGIONS),
        "sex": single["Gender"].map(GENDERS),
        "age": single["age"].astype(int),
        "population": single["VALUE"].astype(int),
    }).sort_values(["year", "region", "sex", "age"]).reset_index(drop=True)

    # Keep StatCan's own "All ages" totals alongside, so a test can check the single ages add up
    tot = pd.DataFrame({
        "year": totals["REF_DATE"].astype(int),
        "region": totals["GEO"].map(REGIONS),
        "sex": totals["Gender"].map(GENDERS),
        "all_ages_published": totals["VALUE"].astype(int),
    })
    return out.merge(tot, on=["year", "region", "sex"], how="left")


def report(df: pd.DataFrame) -> None:
    print(f"Population table: {len(df):,} rows, years {df['year'].min()}-{df['year'].max()}")
    latest = df["year"].max()
    ca = df.query("year == @latest and region == 'CA' and sex == 'B'")["population"].sum()
    print(f"Canada, July 1 {latest}: {ca:,} people")


if __name__ == "__main__":
    table = clean()
    report(table)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_CSV, index=False)
    print(f"Saved {OUT_CSV.relative_to(ROOT)} ({OUT_CSV.stat().st_size / 1e6:.1f} MB)")
