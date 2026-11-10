"""
Checks on data/clean/causes_of_death.csv (built by pipeline/04_clean_causes_of_death.py).

Run from the project folder:
    pytest
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
CLEAN_CSV = ROOT / "data" / "clean" / "causes_of_death.csv"

CAUSES = [
    "lung_cancer", "other_cancer", "heart", "stroke", "copd", "diabetes",
    "dementia", "motor_vehicle", "other_accidents", "other_injury", "covid", "other",
]
CELL = ["year", "sex", "age_lo"]   # one cell = one year x sex x age group


@pytest.fixture(scope="module")
def cod() -> pd.DataFrame:
    if not CLEAN_CSV.exists():
        pytest.fail("data/clean/causes_of_death.csv missing: run pipeline/04_clean_causes_of_death.py")
    return pd.read_csv(CLEAN_CSV)


def test_grid_is_complete(cod):
    """Every year x sex x age group has all 12 cause groups, once each."""
    assert set(cod["sex"]) == {"B", "M", "F"}
    assert set(cod["cause"]) == set(CAUSES)
    assert cod["age_lo"].nunique() == 20          # under 1, 1-4, 5-9, ..., 85-89, 90+
    expected = cod["year"].nunique() * 3 * 20 * 12
    assert len(cod) == expected
    assert not cod.duplicated(subset=CELL + ["cause"]).any()


def test_age_groups_cover_0_to_110(cod):
    """Age groups run from 0 to 110 with no gaps or overlaps."""
    groups = cod[["age_lo", "age_hi"]].drop_duplicates().sort_values("age_lo")
    assert groups["age_lo"].iloc[0] == 0 and groups["age_hi"].iloc[-1] == 110
    assert (groups["age_lo"].iloc[1:].to_numpy() == groups["age_hi"].iloc[:-1].to_numpy() + 1).all()


def test_groups_add_up_to_total(cod):
    """In every cell, the cause groups sum exactly to StatCan's total deaths."""
    sums = cod.groupby(CELL).agg(deaths=("deaths", "sum"), total=("total_deaths", "first"))
    assert (sums["deaths"] == sums["total"]).all()


def test_males_plus_females_equals_both(cod):
    """Deaths for males + females equal 'both sexes', cause by cause."""
    w = cod.pivot_table(index=["year", "age_lo", "cause"], columns="sex", values="deaths")
    assert (w["M"] + w["F"] == w["B"]).all()


def test_no_cause_groups_overlap(cod):
    """'Other' (the remainder) is never negative, so no deaths are counted twice."""
    other = cod[cod["cause"] == "other"]
    assert (other["deaths"] >= 0).all()
