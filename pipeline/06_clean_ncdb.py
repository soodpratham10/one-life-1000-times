"""
Step 6 of the data pipeline: count people injured and killed in police-reported
motor vehicle collisions, by year, sex and single year of age.

Source: Transport Canada, National Collision Database (NCDB), open data
        (Open Government Licence - Canada). One row per person involved.
Years : 2019 (last year before COVID; used by the model) and 2020 (COVID comparison).

Codes used (NCDB data dictionary):
    P_ISEV  person's injury: 1 = no injury, 2 = injury, 3 = fatality,
            N = not applicable (e.g. parked vehicle record), U = unknown
    P_SEX   M, F, U = unknown, N = not applicable
    P_AGE   01..99 (99 = 99 or older); UU = unknown

People with unknown age or sex are spread over the known ones in proportion,
so yearly totals stay exactly equal to the source.

Input : data/raw/ncdb/<file>.csv     (downloaded automatically if missing)
Output: data/clean/crash_casualties.csv
        columns: year, sex, age, injured, killed

Run from the project folder:
    python pipeline/06_clean_ncdb.py
"""

import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "ncdb"
OUT_CSV = ROOT / "data" / "clean" / "crash_casualties.csv"

BASE = "https://open.canada.ca/data/dataset/1eb9eba7-71d1-4b30-9fb1-30cbdab7e63a/resource"
FILES = {
    2019: ("2019_dataset_en.csv", f"{BASE}/1e2a6aa0-c35f-4736-984a-71f2eac1c1dc/download/2019_dataset_en.csv"),
    2020: ("y_2020.csv", f"{BASE}/2164b2a7-a580-4708-bdac-8ab0c1304bc2/download/y_2020.csv"),
}
OUTCOMES = {"2": "injured", "3": "killed"}
AGES = range(1, 100)


def get_file(year: int) -> Path:
    name, url = FILES[year]
    path = RAW_DIR / name
    if not path.exists():
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Downloading NCDB {year} ...")
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request) as response, open(path, "wb") as out:
            out.write(response.read())
    return path


def allocate_unknowns(counts: pd.DataFrame) -> pd.DataFrame:
    """
    counts: one row per (sex, age) with sex in {M, F, U} and age a number or NaN (unknown).
    Spread unknown-age people over ages within their sex, then unknown-sex people
    over sexes within each age, both in proportion to the known counts.
    """
    known_age = counts[counts["age"].notna()]
    out = []
    for sex in ["M", "F", "U"]:
        by_age = (known_age[known_age["sex"] == sex].set_index("age")["n"]
                  .reindex(AGES, fill_value=0).astype(float))
        unknown = counts[(counts["sex"] == sex) & counts["age"].isna()]["n"].sum()
        if by_age.sum() > 0:
            by_age += unknown * by_age / by_age.sum()
        out.append(by_age.rename(sex))
    table = pd.concat(out, axis=1)                       # rows = age, columns = M, F, U

    known_sex = table["M"] + table["F"]
    share_m = np.where(known_sex > 0, table["M"] / known_sex.where(known_sex > 0, 1), 0.5)
    table["M"] += table["U"] * share_m
    table["F"] += table["U"] * (1 - share_m)
    return table[["M", "F"]]


def clean_year(year: int) -> pd.DataFrame:
    df = pd.read_csv(get_file(year), dtype=str, usecols=["C_YEAR", "P_ISEV", "P_SEX", "P_AGE"])
    if set(df["C_YEAR"]) != {str(year)}:
        raise ValueError(f"{year} file contains other years: {set(df['C_YEAR'])}")

    df = df[df["P_ISEV"].isin(OUTCOMES) & df["P_SEX"].isin(["M", "F", "U"])].copy()
    df["age"] = pd.to_numeric(df["P_AGE"], errors="coerce")
    if not df["age"].dropna().between(1, 99).all():
        raise ValueError("Unexpected ages outside 1-99")

    pieces = []
    for code, name in OUTCOMES.items():
        counts = (df[df["P_ISEV"] == code]
                  .groupby(["P_SEX", "age"], dropna=False).size()
                  .rename("n").reset_index().rename(columns={"P_SEX": "sex"}))
        table = allocate_unknowns(counts)
        long = table.reset_index(names="age").melt(id_vars="age", var_name="sex", value_name=name)
        pieces.append(long.set_index(["sex", "age"]))
    out = pd.concat(pieces, axis=1).reset_index()
    out.insert(0, "year", year)
    return out


def report(df: pd.DataFrame) -> None:
    print("\nTotals (after spreading unknown age/sex):")
    print(df.groupby("year")[["injured", "killed"]].sum().round(0).astype(int).to_string())
    adults = df[df["age"] >= 18].groupby(["year", "sex"])["injured"].sum().unstack().round(0)
    print("\nAdults (18+) injured, by sex:")
    print(adults.astype(int).to_string())


if __name__ == "__main__":
    table = pd.concat([clean_year(y) for y in FILES], ignore_index=True)
    table = table[["year", "sex", "age", "injured", "killed"]].sort_values(["year", "sex", "age"])
    report(table)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_CSV, index=False, float_format="%.4f")
    print(f"\nSaved {OUT_CSV.relative_to(ROOT)}")
