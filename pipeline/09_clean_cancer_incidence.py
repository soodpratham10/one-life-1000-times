"""
Step 9 of the data pipeline: new cancer cases by year, geography, sex and age group.

The source table is very large (about 1.8 GB), so it is read in chunks and only
what the model needs is kept:
  - geographies: Canada, Canada (excluding Quebec), Quebec
    (Quebec has not sent recent years to the national registry, so recent
     national figures may exist only without Quebec)
  - cancer types: all primary sites, and lung and bronchus (tied to smoking)
  - measures: number of new cases, and StatCan's incidence rate per 100,000

Note: the registry counts primary CANCERS, not people; someone diagnosed with two
separate primary cancers counts twice. See A13 in docs/assumptions.md.

Input : data/raw/statcan_13100111/13100111.csv   (python pipeline/download_statcan.py 13100111)
Output: data/clean/cancer_incidence.csv
        columns: year, geo, sex, age_lo, age_hi, cancer, cases, rate_per_100k

Run from the project folder:
    python pipeline/09_clean_cancer_incidence.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "raw" / "statcan_13100111" / "13100111.csv"
OUT_CSV = ROOT / "data" / "clean" / "cancer_incidence.csv"

GEOS = {"Canada": "CA", "Canada (excluding Quebec)": "CA_exQC", "Quebec": "QC"}
CANCERS = {
    "Total, all primary sites of cancer [C00.0-C80.9]": "all",
    "Lung and bronchus [C34.0-C34.9]": "lung",
}
MEASURES = {"Number of new cancer cases": "cases", "Cancer incidence rate": "rate_per_100k"}
SEXES = {"Both sexes": "B", "Males": "M", "Females": "F"}
COLS = ["REF_DATE", "GEO", "Age group", "Sex", "Primary types of cancer (ICD-O-3)",
        "Characteristics", "VALUE"]


def parse_age_group(label: str):
    """'20 to 24 years' -> (20, 24); '90 years and over' -> (90, 110); others -> (None, None)."""
    if label == "90 years and over":
        return 90, 110
    parts = label.split()
    if len(parts) == 4 and parts[1] == "to":
        return int(parts[0]), int(parts[2])
    return None, None


def read_filtered() -> pd.DataFrame:
    pieces = []
    for i, chunk in enumerate(pd.read_csv(RAW_CSV, usecols=COLS, chunksize=500_000, low_memory=False)):
        keep = (chunk["GEO"].isin(GEOS)
                & chunk["Primary types of cancer (ICD-O-3)"].isin(CANCERS)
                & chunk["Characteristics"].isin(MEASURES))
        pieces.append(chunk[keep])
        print(f"   read {(i + 1) * 500_000:>10,} rows", end="\r")
    print()
    return pd.concat(pieces, ignore_index=True)


def clean() -> pd.DataFrame:
    raw = read_filtered()
    missing = set(CANCERS) - set(raw["Primary types of cancer (ICD-O-3)"])
    if missing:
        raise ValueError(f"Cancer labels not found: {missing}")

    raw = raw[~raw["Age group"].isin(["Total, all ages", "Age group, not stated"])]
    ages = raw["Age group"].map(parse_age_group)
    df = pd.DataFrame({
        "year": raw["REF_DATE"].astype(int),
        "geo": raw["GEO"].map(GEOS),
        "sex": raw["Sex"].map(SEXES),
        "age_lo": ages.str[0],
        "age_hi": ages.str[1],
        "cancer": raw["Primary types of cancer (ICD-O-3)"].map(CANCERS),
        "measure": raw["Characteristics"].map(MEASURES),
        "value": raw["VALUE"],
    })
    if df["age_lo"].isna().any():
        raise ValueError(f"Unexpected age labels: {set(raw['Age group'][df['age_lo'].isna()])}")

    tidy = df.pivot(index=["year", "geo", "sex", "age_lo", "age_hi", "cancer"],
                    columns="measure", values="value").reset_index()
    tidy.columns.name = None
    tidy[["age_lo", "age_hi"]] = tidy[["age_lo", "age_hi"]].astype(int)
    return tidy.sort_values(["geo", "year", "cancer", "sex", "age_lo"]).reset_index(drop=True)


def report(df: pd.DataFrame) -> None:
    print(f"Tidy table: {len(df):,} rows")
    print("\nYears with ALL-cancer case counts available (both sexes, every age group):")
    allc = df[(df["cancer"] == "all") & (df["sex"] == "B")]
    complete = allc.groupby(["geo", "year"])["cases"].apply(lambda s: s.notna().all())
    for geo, years in complete.groupby(level="geo"):
        have = [y for (_, y), ok in years.items() if ok]
        print(f"   {geo:8s}: {min(have)}-{max(have)} ({len(have)} years)" if have else f"   {geo}: none")
    blank = df["cases"].isna().sum()
    print(f"\nBlank case counts (suppressed 'x' or not available '..'): {blank:,} of {len(df):,}")
    print("\nNew cancer cases, both sexes, all ages, by geography (last 6 years):")
    tot = allc.groupby(["year", "geo"])["cases"].sum(min_count=1).unstack()
    print(tot.tail(6).to_string())


if __name__ == "__main__":
    table = clean()
    report(table)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_CSV, index=False)
    print(f"\nSaved {OUT_CSV.relative_to(ROOT)} ({OUT_CSV.stat().st_size / 1e6:.1f} MB)")
