"""
Step 11 of the data pipeline: yearly probability of a heart attack (acute myocardial
infarction) and of a stroke, by sex and 5-year age group, Canada, fiscal year 2018-19.

Source: Public Health Agency of Canada, Canadian Chronic Disease Surveillance System
        (CCDSS), Health Infobase data tool, "Age Distribution" view, crude incidence
        rate (newly identified cases), Download Detailed Table.
        Built from provincial health-insurance records (hospital and physician claims).

    p(event) = newly identified cases / CCDSS population, both from the CCDSS file,
               so the top and bottom of the fraction come from the same registry.

2018-19 (April 2018 - March 2019) is the last full fiscal year before COVID-19
(PHAC treats 2020-21 to 2022-23 as the pandemic period; 2019-20 ends in March 2020).

Input : data/raw/ccdss/ccdss_ami_by_age.csv, data/raw/ccdss/ccdss_stroke_by_age.csv
        (downloaded by hand from health-infobase.canada.ca/ccdss/data-tool; see README)
Output: data/clean/heart_stroke_incidence.csv   all geographies and years, tidy
        data/clean/heart_stroke_rates.csv       Canada 2018-19 probabilities

Run from the project folder:
    python pipeline/11_heart_stroke.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = {"heart_attack": ROOT / "data" / "raw" / "ccdss" / "ccdss_ami_by_age.csv",
       "stroke": ROOT / "data" / "raw" / "ccdss" / "ccdss_stroke_by_age.csv"}
INCIDENCE_CSV = ROOT / "data" / "clean" / "heart_stroke_incidence.csv"
RATES_CSV = ROOT / "data" / "clean" / "heart_stroke_rates.csv"
BASE_YEAR = 2018           # fiscal year 2018-19
SEXES = {"Both sexes": "B", "Males": "M", "Females": "F"}
REGIONS = {
    "Canada": "CA", "Newfoundland and Labrador": "NL", "Prince Edward Island": "PE",
    "Nova Scotia": "NS", "New Brunswick": "NB", "Quebec": "QC", "Ontario": "ON",
    "Manitoba": "MB", "Saskatchewan": "SK", "Alberta": "AB", "British Columbia": "BC",
    "Yukon": "YT", "Northwest Territories": "NT", "Nunavut": "NU",
}


def parse_age_group(label: str):
    """'20–24' -> (20, 24); '90+' -> (90, 110); '20+' -> (20, 110). (– is an en dash.)"""
    label = label.replace("–", "-")
    if label.endswith("+"):
        return int(label[:-1]), 110
    lo, hi = label.split("-")
    return int(lo), int(hi)


def to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.str.replace(",", ""), errors="coerce")


def read_one(condition: str, path: Path) -> pd.DataFrame:
    # The file is in Windows encoding, has a title line, and ends with rows of notes
    raw = pd.read_csv(path, skiprows=2, encoding="cp1252", dtype=str)
    raw = raw[raw["Sex"].notna()]
    rate_col = [c for c in raw.columns if c.startswith("Rate (per")][0]

    raw = raw[raw["Age group type"].isin(["5 Year", "Total"])]
    unknown = set(raw["Geography"]) - set(REGIONS)
    if unknown:
        raise ValueError(f"{path.name}: unexpected geographies {unknown}")

    ages = raw["Age group"].map(parse_age_group)
    return pd.DataFrame({
        "condition": condition,
        "fiscal_year": raw["Fiscal year"].str[:4].astype(int),
        "region": raw["Geography"].map(REGIONS),
        "sex": raw["Sex"].map(SEXES),
        "age_group_type": raw["Age group type"].map({"5 Year": "5yr", "Total": "total"}),
        "age_lo": ages.str[0],
        "age_hi": ages.str[1],
        "cases": to_number(raw["Case counts"]),
        "population": to_number(raw["Population"]),
        "rate_per_100k": to_number(raw[rate_col]),
    })


def build_rates(inc: pd.DataFrame) -> pd.DataFrame:
    base = inc[(inc["fiscal_year"] == BASE_YEAR) & (inc["region"] == "CA")
               & (inc["age_group_type"] == "5yr") & inc["sex"].isin(["M", "F"])]
    if base[["cases", "population"]].isna().any().any():
        raise ValueError(f"Blank counts for Canada {BASE_YEAR}-{BASE_YEAR + 1}")
    rates = base.pivot_table(index=["sex", "age_lo", "age_hi"], columns="condition",
                             values=["cases", "population", "rate_per_100k"])
    rates.columns = [f"{m}_{c}" for m, c in rates.columns]
    rates = rates.reset_index()
    for c in ["heart_attack", "stroke"]:
        rates[f"p_{c}"] = rates[f"cases_{c}"] / rates[f"population_{c}"]
    rates.insert(0, "fiscal_year", f"{BASE_YEAR}-{BASE_YEAR + 1 - 2000:02d}")
    return rates


def report(rates: pd.DataFrame) -> None:
    show = rates.copy()
    show["heart attack /1,000"] = (show["p_heart_attack"] * 1000).round(2)
    show["stroke /1,000"] = (show["p_stroke"] * 1000).round(2)
    print(f"Chance of a heart attack or stroke in fiscal {BASE_YEAR}-{BASE_YEAR + 1}, Canada, per 1,000:\n")
    w = show.pivot(index=["age_lo", "age_hi"], columns="sex",
                   values=["heart attack /1,000", "stroke /1,000"])
    print(w.to_string())


if __name__ == "__main__":
    incidence = pd.concat([read_one(c, p) for c, p in RAW.items()], ignore_index=True)
    incidence = incidence.sort_values(["condition", "region", "fiscal_year", "sex", "age_lo"])
    rates = build_rates(incidence)
    report(rates)
    incidence.to_csv(INCIDENCE_CSV, index=False)
    rates.to_csv(RATES_CSV, index=False, float_format="%.6g")
    print(f"\nSaved {INCIDENCE_CSV.relative_to(ROOT)} and {RATES_CSV.relative_to(ROOT)}")
