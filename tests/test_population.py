"""
Checks on data/clean/population.csv (built by pipeline/07_clean_population.py).

Run from the project folder:
    pytest
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
CLEAN_CSV = ROOT / "data" / "clean" / "population.csv"
PROVINCES = ["NL", "PE", "NS", "NB", "QC", "ON", "MB", "SK", "AB", "BC"]


@pytest.fixture(scope="module")
def pop() -> pd.DataFrame:
    if not CLEAN_CSV.exists():
        pytest.fail("data/clean/population.csv missing: run pipeline/07_clean_population.py")
    return pd.read_csv(CLEAN_CSV)


def test_grid_is_complete(pop):
    """Every year x region (Canada + 10 provinces) x sex has ages 0-100, once each."""
    assert set(pop["region"]) == set(PROVINCES) | {"CA"}
    assert set(pop["sex"]) == {"M", "F", "B"}
    assert set(pop["age"]) == set(range(101))
    assert len(pop) == pop["year"].nunique() * 11 * 3 * 101
    assert not pop.duplicated(subset=["year", "region", "sex", "age"]).any()


def test_single_ages_add_up_to_published_total(pop):
    """Single ages 0-100+ sum exactly to StatCan's own 'All ages' figure."""
    sums = pop.groupby(["year", "region", "sex"]).agg(
        total=("population", "sum"), published=("all_ages_published", "first"))
    assert (sums["total"] == sums["published"]).all()


def test_men_plus_women_equals_total(pop):
    w = pop.pivot_table(index=["year", "region", "age"], columns="sex", values="population")
    assert (w["M"] + w["F"] == w["B"]).all()


def test_provinces_are_almost_all_of_canada(pop):
    """The 10 provinces hold 99-100% of Canada's population (the rest live in the territories)."""
    b = pop[(pop["sex"] == "B")]
    prov = b[b["region"].isin(PROVINCES)].groupby("year")["population"].sum()
    canada = b[b["region"] == "CA"].groupby("year")["population"].sum()
    share = prov / canada
    assert share.between(0.99, 1.0).all(), share.describe()
