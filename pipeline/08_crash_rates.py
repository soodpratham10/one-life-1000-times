"""
Step 8 of the data pipeline: yearly probability of being injured (or killed) in a
police-reported motor vehicle collision, by sex and single age, Canada.

    rate(sex, age) = people injured in the year / population on July 1 of that year

The NCDB's top age is "99 or older", so population ages 99 and 100+ are combined.

Input : data/clean/crash_casualties.csv   (06_clean_ncdb.py)
        data/clean/population.csv         (07_clean_population.py)
Output: data/clean/crash_rates.csv
        columns: year, sex, age, injured, killed, population, p_injured, p_killed

Run from the project folder:
    python pipeline/08_crash_rates.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CRASH_CSV = ROOT / "data" / "clean" / "crash_casualties.csv"
POP_CSV = ROOT / "data" / "clean" / "population.csv"
OUT_CSV = ROOT / "data" / "clean" / "crash_rates.csv"


def build() -> pd.DataFrame:
    crash = pd.read_csv(CRASH_CSV)
    pop = pd.read_csv(POP_CSV)
    pop = pop[(pop["region"] == "CA") & pop["sex"].isin(["M", "F"]) & pop["year"].isin(crash["year"])].copy()
    pop["age"] = pop["age"].clip(upper=99)                     # 99 and 100+ -> 99+
    pop = pop.groupby(["year", "sex", "age"], as_index=False)["population"].sum()

    rates = crash.merge(pop, on=["year", "sex", "age"], how="left", validate="one_to_one")
    if rates["population"].isna().any():
        raise ValueError("Population missing for some year/sex/age")
    rates["p_injured"] = rates["injured"] / rates["population"]
    rates["p_killed"] = rates["killed"] / rates["population"]
    return rates


def report(rates: pd.DataFrame) -> None:
    r = rates[rates["year"] == 2019]
    bands = pd.cut(r["age"], [17, 24, 34, 44, 54, 64, 74, 99],
                   labels=["18-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+"])
    grouped = r.groupby([bands, "sex"], observed=True)[["injured", "population"]].sum()
    per_1000 = (grouped["injured"] / grouped["population"] * 1000).unstack().round(2)
    print("Chance of being injured in a crash in 2019, per 1,000 people:")
    print(per_1000.to_string())


if __name__ == "__main__":
    table = build()
    report(table)
    table.to_csv(OUT_CSV, index=False, float_format="%.6g")
    print(f"\nSaved {OUT_CSV.relative_to(ROOT)}")
