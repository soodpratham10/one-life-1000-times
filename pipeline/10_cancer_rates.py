"""
Step 10 of the data pipeline: yearly probability of a new cancer diagnosis,
by sex and 5-year age group, Canada, 2019.

    p(any cancer) = new primary cancers in 2019 / population on July 1, 2019
    p(lung)       = same, lung and bronchus only;   p(other) = p(any) - p(lung)

2019 is the latest year with complete national data in the table and the last
year before COVID-19 disrupted cancer screening and diagnosis.

Our own population (07_clean_population.py) is used as the denominator, and the
result is checked against StatCan's published incidence rate for each group.

Input : data/clean/cancer_incidence.csv   (09_clean_cancer_incidence.py)
        data/clean/population.csv         (07_clean_population.py)
Output: data/clean/cancer_rates.csv

Run from the project folder:
    python pipeline/10_cancer_rates.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INCIDENCE_CSV = ROOT / "data" / "clean" / "cancer_incidence.csv"
POP_CSV = ROOT / "data" / "clean" / "population.csv"
OUT_CSV = ROOT / "data" / "clean" / "cancer_rates.csv"
BASE_YEAR = 2019


def population_by_group(groups: pd.DataFrame) -> pd.DataFrame:
    """Sum single-age population into the incidence table's age groups (90+ = 90-100+)."""
    pop = pd.read_csv(POP_CSV)
    pop = pop[(pop["year"] == BASE_YEAR) & (pop["region"] == "CA") & pop["sex"].isin(["M", "F"])]
    rows = []
    for _, g in groups.iterrows():
        n = pop[(pop["sex"] == g["sex"]) & pop["age"].between(g["age_lo"], min(g["age_hi"], 100))]["population"].sum()
        rows.append({"sex": g["sex"], "age_lo": g["age_lo"], "population": n})
    return pd.DataFrame(rows)


def build() -> pd.DataFrame:
    inc = pd.read_csv(INCIDENCE_CSV)
    inc = inc[(inc["year"] == BASE_YEAR) & (inc["geo"] == "CA") & inc["sex"].isin(["M", "F"])]
    # StatCan suppresses very small counts ('x') for privacy. Lung cancer under age 30 is
    # rare enough that those cells are suppressed; they are set to 0 and flagged (even 4 cases
    # would be a chance below 1 in a million). A blank anywhere else stops the pipeline.
    blank = inc["cases"].isna()
    allowed = (inc["cancer"] == "lung") & (inc["age_hi"] < 30)
    if (blank & ~allowed).any():
        raise ValueError(f"Unexpected blank case counts for Canada {BASE_YEAR}:\n"
                         f"{inc[blank & ~allowed].head()}")
    inc = inc.assign(suppressed=blank)
    inc["cases"] = inc["cases"].fillna(0)
    inc["rate_per_100k"] = inc["rate_per_100k"].fillna(0)
    print(f"{blank.sum()} suppressed lung cancer counts under age 30 set to 0 (flagged)")

    wide = inc.pivot(index=["sex", "age_lo", "age_hi"], columns="cancer",
                     values=["cases", "rate_per_100k", "suppressed"])
    wide.columns = [f"{m}_{c}" for m, c in wide.columns]
    wide = wide.reset_index().rename(columns={"suppressed_lung": "lung_suppressed"})

    wide = wide.merge(population_by_group(wide[["sex", "age_lo", "age_hi"]]), on=["sex", "age_lo"])
    wide["p_any_cancer"] = wide["cases_all"] / wide["population"]
    wide["p_lung"] = wide["cases_lung"] / wide["population"]
    wide["p_other_cancer"] = wide["p_any_cancer"] - wide["p_lung"]
    wide["statcan_p_any"] = wide["rate_per_100k_all"] / 100_000
    wide.insert(0, "year", BASE_YEAR)
    return wide[["year", "sex", "age_lo", "age_hi", "cases_all", "cases_lung", "population",
                 "p_any_cancer", "p_lung", "p_other_cancer", "statcan_p_any", "lung_suppressed"]]


def report(df: pd.DataFrame) -> None:
    show = df[df["age_lo"] >= 20].copy()
    show["any per 1,000"] = (show["p_any_cancer"] * 1000).round(2)
    show["lung per 1,000"] = (show["p_lung"] * 1000).round(2)
    show["StatCan per 1,000"] = (show["statcan_p_any"] * 1000).round(2)
    print(f"Chance of a new cancer diagnosis in {BASE_YEAR}, Canada, per 1,000 people:\n")
    for sex in ["F", "M"]:
        print("Women" if sex == "F" else "Men")
        print(show[show["sex"] == sex][["age_lo", "age_hi", "any per 1,000", "StatCan per 1,000",
                                        "lung per 1,000"]].to_string(index=False))
        print()


if __name__ == "__main__":
    table = build()
    report(table)
    table.to_csv(OUT_CSV, index=False, float_format="%.6g")
    print(f"Saved {OUT_CSV.relative_to(ROOT)}")
