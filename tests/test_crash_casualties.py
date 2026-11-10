"""
Checks on data/clean/crash_casualties.csv (built by pipeline/06_clean_ncdb.py).

Run from the project folder:
    pytest
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
CLEAN_CSV = ROOT / "data" / "clean" / "crash_casualties.csv"

# Person counts in the NCDB files (P_ISEV = 2 injured, 3 killed), all ages, all road users
SOURCE_TOTALS = {2019: {"injured": 140_801, "killed": 1_762},
                 2020: {"injured": 104_265, "killed": 1_746}}


@pytest.fixture(scope="module")
def crash() -> pd.DataFrame:
    if not CLEAN_CSV.exists():
        pytest.fail("data/clean/crash_casualties.csv missing: run pipeline/06_clean_ncdb.py")
    return pd.read_csv(CLEAN_CSV)


def test_grid_is_complete(crash):
    """Each year has both sexes and every age 1-99, once each."""
    assert set(crash["year"]) == {2019, 2020}
    assert set(crash["sex"]) == {"M", "F"}
    assert set(crash["age"]) == set(range(1, 100))
    assert len(crash) == 2 * 2 * 99
    assert not crash.duplicated(subset=["year", "sex", "age"]).any()


def test_no_negative_counts(crash):
    assert (crash[["injured", "killed"]] >= 0).all().all()


def test_totals_match_source_files(crash):
    """Spreading unknown age/sex keeps each year's totals exactly equal to the source."""
    for year, totals in SOURCE_TOTALS.items():
        got = crash[crash["year"] == year][["injured", "killed"]].sum()
        assert got["injured"] == pytest.approx(totals["injured"], abs=0.5)
        assert got["killed"] == pytest.approx(totals["killed"], abs=0.5)


def test_covid_year_has_fewer_injuries(crash):
    """2020 lockdowns cut driving: injuries fell well below 2019."""
    by_year = crash.groupby("year")["injured"].sum()
    assert by_year[2020] < 0.85 * by_year[2019]


def test_2020_deaths_match_transport_canada_report(crash):
    """2020 deaths equal Transport Canada's published figure (1,746), from its report
    "Canadian Motor Vehicle Traffic Collision Statistics: 2021" (an outside source)."""
    year_2020 = crash[crash["year"] == 2020]
    assert year_2020["killed"].sum() == pytest.approx(1746, abs=0.5)
