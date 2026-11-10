"""
Checks on data/clean/cancer_incidence.csv (09_clean_cancer_incidence.py)
and data/clean/cancer_rates.csv (10_cancer_rates.py).

Run from the project folder:
    pytest
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
INCIDENCE_CSV = ROOT / "data" / "clean" / "cancer_incidence.csv"
RATES_CSV = ROOT / "data" / "clean" / "cancer_rates.csv"
CAUSES_CSV = ROOT / "data" / "clean" / "causes_of_death.csv"


def load(path: Path) -> pd.DataFrame:
    if not path.exists():
        pytest.fail(f"{path.relative_to(ROOT)} missing: run the pipeline scripts 09 and 10")
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def inc() -> pd.DataFrame:
    return load(INCIDENCE_CSV)


@pytest.fixture(scope="module")
def rates() -> pd.DataFrame:
    return load(RATES_CSV)


def test_canada_equals_rest_of_canada_plus_quebec(inc):
    """Canada = Canada excluding Quebec + Quebec, within StatCan's rounding of counts to 5."""
    allc = inc[(inc["cancer"] == "all") & (inc["year"] == 2019)]
    w = allc.pivot_table(index=["sex", "age_lo"], columns="geo", values="cases")
    gap = (w["CA"] - w["CA_exQC"] - w["QC"]).abs()
    assert gap.max() <= 10, gap.max()


def test_rates_grid_complete(rates):
    """Both sexes, 19 age groups (0-4 ... 85-89, 90+), no blanks."""
    assert set(rates["sex"]) == {"M", "F"}
    assert rates["age_lo"].nunique() == 19
    assert len(rates) == 2 * 19
    assert rates.notna().all().all()


def test_suppression_only_for_rare_young_lung_cancer(rates):
    """StatCan's privacy suppression should only affect lung cancer under age 30."""
    assert (rates.loc[rates["lung_suppressed"].astype(bool), "age_hi"] < 30).all()


def test_probabilities_valid(rates):
    assert rates["p_any_cancer"].between(0, 1).all()
    assert (rates["p_lung"] >= 0).all()
    assert (rates["p_lung"] <= rates["p_any_cancer"]).all()
    assert (rates["p_other_cancer"] >= 0).all()


def test_matches_statcan_published_rates(rates):
    """Our rate (cases / our population) agrees with StatCan's own published rate within 2%
    for every group with at least 100 cases (small groups are affected by rounding)."""
    big = rates[rates["cases_all"] >= 100]
    rel = (big["p_any_cancer"] / big["statcan_p_any"] - 1).abs()
    assert rel.max() <= 0.02, rel.max()


def test_risk_rises_with_age(rates):
    """Cancer is mostly a disease of older age: 70-74 has a far higher rate than 30-34."""
    for sex in ["M", "F"]:
        r = rates[rates["sex"] == sex].set_index("age_lo")["p_any_cancer"]
        assert r[70] > 10 * r[30]


def test_deaths_are_a_plausible_share_of_new_cases(rates):
    """Cancer deaths in 2019 (death certificates) are roughly 30-50% of new cases that year,
    the usual mortality-to-incidence ratio for a high-income country."""
    causes = load(CAUSES_CSV)
    deaths = causes.query("year == 2019 and sex == 'B' and cause in ['lung_cancer', 'other_cancer']")["deaths"].sum()
    cases = rates["cases_all"].sum()
    assert 0.30 <= deaths / cases <= 0.50, deaths / cases
