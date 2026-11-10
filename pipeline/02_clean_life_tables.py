"""
Step 2 of the data pipeline: turn the raw StatCan life table (long format, one
row per element) into a tidy table with one row per period x region x sex x age
and one column per life-table element.

Input : data/raw/statcan_13100114/13100114.csv   (from 01_download_life_tables.py)
Output: data/clean/life_tables.csv

Run from the project folder:
    python pipeline/02_clean_life_tables.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "raw" / "statcan_13100114" / "13100114.csv"
OUT_CSV = ROOT / "data" / "clean" / "life_tables.csv"

# StatCan element names -> short column names (standard actuarial notation)
ELEMENTS = {
    "Number of survivors at age x (lx)": "lx",
    "Number of deaths between age x and x+1 (dx)": "dx",
    "Death probability between age x and x+1 (qx)": "qx",
    "Margin of error of the death probability (m.e.(qx))": "qx_moe",
    "Probability of survival between age x and x+1 (px)": "px",
    "Number of life years lived between age x and x+1 (Lx)": "Lx",
    "Cumulative number of life years lived beyond age x (Tx)": "Tx",
    "Life expectancy (in years) at age x (ex)": "ex",
    "Margin of error of the life expectancy (m.e.(ex))": "ex_moe",
}

REGIONS = {
    "Canada": "CA",
    "Newfoundland and Labrador": "NL",
    "Nova Scotia": "NS",
    "New Brunswick": "NB",
    "Quebec": "QC",
    "Ontario": "ON",
    "Manitoba": "MB",
    "Saskatchewan": "SK",
    "Alberta": "AB",
    "British Columbia": "BC",
}

SEXES = {"Both sexes": "B", "Males": "M", "Females": "F"}

COLUMN_ORDER = [
    "period_start", "period_end", "region", "sex", "age",
    "qx", "qx_moe", "px", "lx", "dx", "Lx", "Tx", "ex", "ex_moe",
]


def parse_age(label: str) -> int:
    """'0 years' -> 0, '1 year' -> 1, '110 years and over' -> 110."""
    return int(label.split()[0])


def clean() -> pd.DataFrame:
    raw = pd.read_csv(
        RAW_CSV,
        usecols=["REF_DATE", "GEO", "Age group", "Sex", "Element", "VALUE"],
        low_memory=False,
    )
    print(f"Read {len(raw):,} raw rows")

    # Fail loudly if StatCan ever changes a label we rely on
    for col, mapping in [("Element", ELEMENTS), ("GEO", REGIONS), ("Sex", SEXES)]:
        unknown = set(raw[col].unique()) - set(mapping)
        if unknown:
            raise ValueError(f"Unexpected {col} values: {unknown}")

    df = pd.DataFrame({
        "period_start": raw["REF_DATE"].str[:4].astype(int),
        "period_end": raw["REF_DATE"].str[-4:].astype(int),
        "region": raw["GEO"].map(REGIONS),
        "sex": raw["Sex"].map(SEXES),
        "age": raw["Age group"].map(parse_age),
        "element": raw["Element"].map(ELEMENTS),
        "value": raw["VALUE"],
    })

    # Each (period, region, sex, age, element) must appear exactly once in the raw data
    dupes = df.duplicated(subset=["period_start", "region", "sex", "age", "element"]).sum()
    if dupes:
        raise ValueError(f"{dupes} duplicate raw cells")

    # Strict reshape: one row per period x region x sex x age, one column per element.
    # (pivot keeps missing values as NaN and never invents rows.)
    tidy = df.pivot(
        index=["period_start", "period_end", "region", "sex", "age"],
        columns="element",
        values="value",
    ).reset_index()
    tidy.columns.name = None

    return tidy[COLUMN_ORDER].sort_values(
        ["period_start", "region", "sex", "age"]
    ).reset_index(drop=True)


def report(tidy: pd.DataFrame) -> None:
    print(f"Tidy table: {len(tidy):,} rows x {len(tidy.columns)} columns")
    print(f"Periods: {tidy['period_start'].min()}-{tidy['period_end'].min()} "
          f"to {tidy['period_start'].max()}-{tidy['period_end'].max()}")
    print("\nMissing values per column (StatCan '..' = not available):")
    missing = tidy.isna().sum()
    print(missing[missing > 0].to_string() if missing.any() else "   none")

    latest = tidy["period_start"].max()
    e0 = tidy.query("period_start == @latest and region == 'CA' and age == 0")
    print(f"\nLife expectancy at birth, Canada, {latest}-{latest + 2}:")
    for _, row in e0.iterrows():
        print(f"   {row['sex']}: {row['ex']:.2f} years")


if __name__ == "__main__":
    tidy = clean()
    report(tidy)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    tidy.to_csv(OUT_CSV, index=False)
    print(f"\nSaved {OUT_CSV.relative_to(ROOT)} "
          f"({OUT_CSV.stat().st_size / 1e6:.1f} MB)")
