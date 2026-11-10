"""
Checks on data/clean/risk_prevalence.csv (built by pipeline/15_risk_prevalence.py):
how common each survey risk factor is, by sex and age group (CCHS, A18).

The last test compares the table with a figure StatCan published separately
(Health Fact Sheet "Smoking, 2019", catalogue 82-625-X).

Run from the project folder:
    pytest tests/test_risk_prevalence.py -v
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
CLEAN_CSV = ROOT / "data" / "clean" / "risk_prevalence.csv"
KEYS = ["year", "region", "sex", "age_lo", "age_hi", "indicator"]
INDICATORS = {"current_smoker", "daily_smoker", "heavy_drinking", "active_150",
              "overweight", "obese", "fruit_veg_5"}
ADULT_GROUPS = [(18, 34), (35, 49), (50, 64), (65, 110)]
ENGINE_INDICATORS = ["current_smoker", "active_150", "overweight", "obese", "fruit_veg_5"]
TARGET_YEAR = 2019


@pytest.fixture(scope="module")
def prev() -> pd.DataFrame:
    if not CLEAN_CSV.exists():
        pytest.fail("data/clean/risk_prevalence.csv missing: run pipeline/15_risk_prevalence.py")
    return pd.read_csv(CLEAN_CSV, keep_default_na=False, na_values=[""])


def base_year(prev, indicator) -> int:
    years = prev.loc[prev["base"] & (prev["indicator"] == indicator), "year"].unique()
    assert len(years) == 1, f"{indicator}: base rows in {sorted(years)}"
    return int(years[0])


def cell(prev, indicator, sex, age_lo, age_hi, year=None, region="CA") -> float:
    """One published percent; by default from the year the engine uses for that indicator."""
    year = base_year(prev, indicator) if year is None else year
    row = prev[(prev["year"] == year) & (prev["region"] == region) & (prev["sex"] == sex)
               & (prev["age_lo"] == age_lo) & (prev["age_hi"] == age_hi)
               & (prev["indicator"] == indicator)]
    assert len(row) == 1
    return float(row["pct"].iloc[0])


def test_grid_is_complete(prev):
    """
    Every year x 11 regions x 3 sexes x 7 indicators has the 12+ total and the four
    adult groups, once each. StatCan publishes the 18+ total only in some years
    (2022 in the 2026 download), so it is checked separately.
    """
    assert set(prev["indicator"]) == INDICATORS
    assert prev["region"].nunique() == 11
    assert set(prev["sex"]) == {"M", "F", "B"}
    groups = set(zip(prev["age_lo"], prev["age_hi"]))
    assert groups == {(12, 110), (18, 110), *ADULT_GROUPS}
    assert not prev.duplicated(subset=KEYS).any()
    regular = prev[~((prev["age_lo"] == 18) & (prev["age_hi"] == 110))]
    assert len(regular) == prev["year"].nunique() * 11 * 3 * 5 * 7
    adult_total = prev[(prev["age_lo"] == 18) & (prev["age_hi"] == 110)]
    per_year = adult_total.groupby("year").size()
    assert (per_year == 11 * 3 * 7).all()          # where it exists, it is complete
    assert TARGET_YEAR in set(prev["year"])


def test_percent_in_range_and_inside_its_interval(prev):
    p = prev.dropna(subset=["pct"])
    assert p["pct"].between(0, 100).all()
    both = p.dropna(subset=["pct_low", "pct_high"])
    assert (both["pct_low"] <= both["pct"] + 1e-9).all()
    assert (both["pct"] <= both["pct_high"] + 1e-9).all()


def test_suppressed_estimates_are_blank(prev):
    """Where StatCan publishes F (too unreliable) or x (suppressed), there is no number."""
    hidden = prev[prev["quality"].isin(["F", "x"])]
    assert hidden["pct"].isna().all()


def test_engine_year_complete(prev):
    """Each factor the engine uses has one base year with a Canada figure for M and F, all adult groups."""
    for ind in ENGINE_INDICATORS:
        for sex in ["M", "F"]:
            for lo, hi in ADULT_GROUPS:
                assert 0 < cell(prev, ind, sex, lo, hi) < 100, (ind, sex, lo, hi)
    unused = prev[prev["base"] & ~prev["indicator"].isin(ENGINE_INDICATORS)]
    assert unused.empty


def test_engine_year_is_latest_complete_year_up_to_2019(prev):
    """The rule in A18: latest complete year up to 2019, otherwise the earliest after it."""
    for ind in ENGINE_INDICATORS:
        rows = prev[(prev["indicator"] == ind) & (prev["region"] == "CA") & prev["sex"].isin(["M", "F"])
                    & (prev["age_lo"] >= 18) & (prev["age_hi"] - prev["age_lo"] < 60)]
        counts = rows.dropna(subset=["pct"]).groupby("year").size()
        complete = sorted(counts[counts == 8].index)
        before = [y for y in complete if y <= TARGET_YEAR]
        expected = max(before) if before else min(complete)
        assert base_year(prev, ind) == expected, ind


def test_daily_smokers_are_a_subset_of_current_smokers(prev):
    wide = prev.pivot_table(index=KEYS[:-1], columns="indicator", values="pct").dropna(
        subset=["current_smoker", "daily_smoker"])
    assert (wide["daily_smoker"] <= wide["current_smoker"] + 0.1).all()


def test_overweight_and_obese_at_most_100(prev):
    wide = prev.pivot_table(index=KEYS[:-1], columns="indicator", values="pct").dropna(
        subset=["overweight", "obese"])
    assert (wide["overweight"] + wide["obese"] <= 100).all()


@pytest.mark.parametrize("sex", ["M", "F"])
def test_well_known_age_patterns(prev, sex):
    """Obesity is lower at 18-34 than at 50-64; activity is higher at 18-34 than at 65+."""
    assert cell(prev, "obese", sex, 18, 34) < cell(prev, "obese", sex, 50, 64)
    assert cell(prev, "active_150", sex, 18, 34) > cell(prev, "active_150", sex, 65, 110)


@pytest.mark.parametrize("sex, published", [("M", 17.3), ("F", 12.3)])
def test_smoking_matches_statcan_fact_sheet(prev, sex, published):
    """StatCan, Health Fact Sheet 'Smoking, 2019': daily or occasional smokers aged 12+, Canada."""
    assert cell(prev, "current_smoker", sex, 12, 110, year=2019) == pytest.approx(published, abs=0.05)
