"""
Step 15 of the data pipeline: how common each survey risk factor is in the
population, by sex and age group (Canadian Community Health Survey, CCHS).

Why the model needs this: base death rates are averages over everyone, smokers
and non-smokers together. To apply a smoker's hazard ratio we first need the
population's average multiplier, and that depends on how many people smoke,
are inactive, are obese, and so on (A18 in docs/assumptions.md).

Input : data/raw/statcan_13100096/13100096.csv   (python pipeline/download_statcan.py 13100096)
Output: data/clean/risk_prevalence.csv
        columns: year, region, sex, age_lo, age_hi, indicator, pct, pct_low, pct_high, quality, base

        indicator     CCHS indicator
        current_smoker  Current smoker, daily or occasional
        daily_smoker    Current smoker, daily
        heavy_drinking  Heavy drinking (men 5+ / women 4+ drinks on one occasion, monthly or more)
        active_150      Self-reported physical activity, 150 minutes per week (adults)
        overweight      BMI 25 to <30, adjusted self-reported (adults)
        obese           BMI 30 or more, adjusted self-reported (adults)
        fruit_veg_5     Fruit and vegetable consumption, 5 times or more per day

        quality: blank = fine; E = use with caution; F = too unreliable to publish
        (pct blank); x = suppressed; .. = not available that year.

        base: True on the rows of the year the engine uses for that indicator.
        The CCHS does not ask every question every year (physical activity and
        fruit and vegetables were not collected in 2019), so for each indicator
        the engine uses the latest year up to 2019 with complete Canadian data
        for both sexes and all four adult age groups; if there is none, the
        earliest year after 2019 (A18).

Run from the project folder:
    python pipeline/15_risk_prevalence.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "raw" / "statcan_13100096" / "13100096.csv"
OUT_CSV = ROOT / "data" / "clean" / "risk_prevalence.csv"

TARGET_YEAR = 2019   # A09: last full year before COVID-19

REGIONS = {
    "Canada (excluding territories)": "CA", "Newfoundland and Labrador": "NL",
    "Prince Edward Island": "PE", "Nova Scotia": "NS", "New Brunswick": "NB",
    "Quebec": "QC", "Ontario": "ON", "Manitoba": "MB", "Saskatchewan": "SK",
    "Alberta": "AB", "British Columbia": "BC",
}
SEXES = {"Males": "M", "Females": "F", "Both sexes": "B"}
AGES = {   # 12+ is kept for the check against StatCan's fact sheet; StatCan
           # publishes the 18+ total only in recent years (2022 in this file)
    "Total, 12 years and over": (12, 110),
    "Total, 18 years and over": (18, 110),
    "18 to 34 years": (18, 34),
    "35 to 49 years": (35, 49),
    "50 to 64 years": (50, 64),
    "65 years and over": (65, 110),
}
INDICATORS = {
    "Current smoker, daily or occasional": "current_smoker",
    "Current smoker, daily": "daily_smoker",
    "Heavy drinking": "heavy_drinking",
    "Self-reported physical activity, 150 minutes per week, adult (18 years and over)": "active_150",
    "Body mass index, adjusted self-reported, adult (18 years and over), overweight": "overweight",
    "Body mass index, adjusted self-reported, adult (18 years and over), obese": "obese",
    "Fruit and vegetable consumption, 5 times or more per day": "fruit_veg_5",
}
MEASURES = {
    "Percent": "pct",
    "Low 95% confidence interval, percent": "pct_low",
    "High 95% confidence interval, percent": "pct_high",
}
# Factors the engine uses; each needs one complete year of Canadian data
ENGINE_INDICATORS = ["current_smoker", "active_150", "overweight", "obese", "fruit_veg_5"]
ADULT_GROUPS = [(18, 34), (35, 49), (50, 64), (65, 110)]


def complete_years(out: pd.DataFrame, indicator: str) -> list[int]:
    """Years with a published Canada figure for M and F in all four adult age groups."""
    rows = out[(out["indicator"] == indicator) & (out["region"] == "CA") & out["sex"].isin(["M", "F"])
               & pd.Series(list(zip(out["age_lo"], out["age_hi"])), index=out.index).isin(ADULT_GROUPS)]
    counts = rows.dropna(subset=["pct"]).groupby("year").size()
    return sorted(int(y) for y in counts[counts == 2 * len(ADULT_GROUPS)].index)


def choose_base_year(years: list[int]) -> int:
    """Latest complete year up to 2019; otherwise the earliest after it."""
    before = [y for y in years if y <= TARGET_YEAR]
    if before:
        return max(before)
    after = [y for y in years if y > TARGET_YEAR]
    if after:
        return min(after)
    raise ValueError("no complete year")


def clean() -> pd.DataFrame:
    raw = pd.read_csv(
        RAW_CSV,
        usecols=["REF_DATE", "GEO", "Age group", "Sex", "Indicators", "Characteristics", "VALUE", "STATUS"],
    )
    missing = set(INDICATORS) - set(raw["Indicators"])
    if missing:
        raise ValueError(f"Indicators not found in the file (StatCan may have renamed them): {missing}")

    raw = raw[
        raw["GEO"].isin(REGIONS)
        & raw["Age group"].isin(AGES)
        & raw["Sex"].isin(SEXES)
        & raw["Indicators"].isin(INDICATORS)
        & raw["Characteristics"].isin(MEASURES)
    ].copy()

    keys = ["REF_DATE", "GEO", "Age group", "Sex", "Indicators"]
    if raw.duplicated(subset=keys + ["Characteristics"]).any():
        raise ValueError("The raw file has more than one value for the same cell")
    values = raw.set_index(keys + ["Characteristics"])["VALUE"].unstack("Characteristics")
    for col in MEASURES:
        if col not in values:
            values[col] = float("nan")
    # The quality flag of the estimate itself sits on the "Percent" row
    quality = (raw[raw["Characteristics"] == "Percent"]
               .set_index(keys)["STATUS"].fillna("").rename("quality"))
    table = values.join(quality, how="outer").reset_index()

    age = table["Age group"].map(AGES)
    out = pd.DataFrame({
        "year": table["REF_DATE"].astype(int),
        "region": table["GEO"].map(REGIONS),
        "sex": table["Sex"].map(SEXES),
        "age_lo": age.str[0].astype(int),
        "age_hi": age.str[1].astype(int),
        "indicator": table["Indicators"].map(INDICATORS),
        "pct": table["Percent"],
        "pct_low": table["Low 95% confidence interval, percent"],
        "pct_high": table["High 95% confidence interval, percent"],
        "quality": table["quality"].fillna(""),
    })
    out = out.sort_values(["indicator", "year", "region", "sex", "age_lo", "age_hi"]).reset_index(drop=True)

    if out.duplicated(subset=["year", "region", "sex", "age_lo", "age_hi", "indicator"]).any():
        raise ValueError("Duplicate rows after cleaning")
    out["base"] = False
    for ind in ENGINE_INDICATORS:
        years = complete_years(out, ind)
        if not years:
            raise ValueError(f"No year has complete Canada data for {ind}")
        out.loc[(out["indicator"] == ind) & (out["year"] == choose_base_year(years)), "base"] = True
    return out


def main() -> None:
    if not RAW_CSV.exists():
        raise SystemExit(f"Missing {RAW_CSV.relative_to(ROOT)}: run python pipeline/download_statcan.py 13100096")
    out = clean()
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV.relative_to(ROOT)}: {len(out):,} rows, years {out['year'].min()}-{out['year'].max()}")

    # Which years each question was asked (complete for Canada, M and F, four adult groups)
    print("\nYears with complete Canadian data (both sexes, all four adult age groups):")
    for ind in sorted(out["indicator"].unique()):
        print(f"  {ind:15s} {complete_years(out, ind)}")

    base = out[out["base"] & (out["region"] == "CA") & (out["sex"] != "B")]
    print("\nYear the engine uses for each factor:")
    print(base.groupby("indicator")["year"].first().to_string())

    show = base.assign(age=base["age_lo"].astype(str) + "-" + base["age_hi"].astype(str))
    number = show["pct"].map(lambda v: "-" if pd.isna(v) else f"{v:.1f}")
    show = show.assign(cell=number + show["quality"])
    print("\nEngine values, Canada, percent (E = use with caution):")
    print(show.pivot_table(index=["indicator", "sex"], columns="age", values="cell", aggfunc="first")
          [["18-34", "35-49", "50-64", "65-110"]].to_string())


if __name__ == "__main__":
    main()
