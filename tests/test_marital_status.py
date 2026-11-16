"""
Checks on data/clean/marital_status.csv (built by pipeline/16_marital_status.py):
Canadians by legal marital status, sex and single age (A24).

Run from the project folder:
    pytest tests/test_marital_status.py -v
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
CLEAN_CSV = ROOT / "data" / "clean" / "marital_status.csv"
STATUSES = {"single", "married", "separated", "widowed", "divorced"}
KEYS = ["year", "region", "sex", "age", "status"]


@pytest.fixture(scope="module")
def ms() -> pd.DataFrame:
    if not CLEAN_CSV.exists():
        pytest.fail("data/clean/marital_status.csv missing: run pipeline/16_marital_status.py")
    return pd.read_csv(CLEAN_CSV)


def test_grid_is_complete(ms):
    """Every year x 11 regions x 3 sexes x ages 15-100 x 5 statuses, once each; 2019 present."""
    assert set(ms["status"]) == STATUSES
    assert ms["region"].nunique() == 11
    assert set(ms["sex"]) == {"M", "F", "B"}
    assert set(ms["age"]) == set(range(15, 101))
    assert len(ms) == ms["year"].nunique() * 11 * 3 * 86 * 5
    assert not ms.duplicated(subset=KEYS).any()
    assert 2019 in set(ms["year"])


def test_shares_add_to_one(ms):
    sums = ms.groupby(["year", "region", "sex", "age"])["share"].sum()
    assert (sums - 1).abs().max() < 1e-9
    assert (ms["population"] >= 0).all()


def test_sexes_add_to_both(ms):
    """Men + women = both sexes, for every year, region, age and status."""
    wide = ms.pivot_table(index=["year", "region", "age", "status"], columns="sex", values="population")
    assert ((wide["M"] + wide["F"] - wide["B"]).abs() <= 2).all()


@pytest.mark.parametrize("sex", ["M", "F"])
def test_life_course_patterns(ms, sex):
    """2019, Canada: fewer single people with age (to 70), more widowed with age (from 50), married peaks mid-life."""
    t = ms[(ms["year"] == 2019) & (ms["region"] == "CA") & (ms["sex"] == sex)].set_index(["age", "status"])["share"]
    single = [t[(a, "single")] for a in range(20, 71, 10)]
    widowed = [t[(a, "widowed")] for a in range(50, 101, 10)]
    assert single == sorted(single, reverse=True)
    assert widowed == sorted(widowed)
    married = {a: t[(a, "married")] for a in range(20, 101, 10)}
    assert married[20] < married[50] and married[100] < married[50]
