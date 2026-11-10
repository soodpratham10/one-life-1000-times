"""
Checks on data/clean/cpp_retirement.csv (built by pipeline/13_cpp_retirement.py from
Table 76 of the 32nd Actuarial Report on the Canada Pension Plan).

Run from the project folder:
    pytest
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
CLEAN_CSV = ROOT / "data" / "clean" / "cpp_retirement.csv"


@pytest.fixture(scope="module")
def ret() -> pd.DataFrame:
    if not CLEAN_CSV.exists():
        pytest.fail("data/clean/cpp_retirement.csv missing: run pipeline/13_cpp_retirement.py")
    return pd.read_csv(CLEAN_CSV)


def test_grid_complete(ret):
    assert set(ret["sex"]) == {"M", "F"}
    assert set(ret["age"]) == set(range(60, 71))
    assert len(ret) == 22


def test_shares_add_to_100(ret):
    assert (ret.groupby("sex")["share_pct"].sum() == 100).all()


def test_average_age_matches_report(ret):
    """The report: these rates give an average take-up age of 64.3 for both sexes."""
    for sex, g in ret.groupby("sex"):
        mean_age = (g["age"] * g["share_pct"]).sum() / 100
        assert mean_age == pytest.approx(64.3, abs=0.05), (sex, mean_age)


def test_published_values_read_correctly(ret):
    """Spot values quoted in the report's text: 21% (men) and 22% (women) at 60,
    32% at 65 and 10% at 70 for both sexes."""
    s = ret.set_index(["sex", "age"])["share_pct"]
    assert s[("M", 60)] == 21 and s[("F", 60)] == 22
    assert s[("M", 65)] == 32 and s[("F", 65)] == 32
    assert s[("M", 70)] == 10 and s[("F", 70)] == 10


def test_yearly_chances_rebuild_the_shares(ret):
    """Running the yearly chances forward from age 60 gives back the published shares,
    and everyone has started by 70."""
    for sex, g in ret.sort_values("age").groupby("sex"):
        not_started = 1.0
        for _, row in g.iterrows():
            started_now = not_started * row["p_start_given_not_started"]
            assert started_now * 100 == pytest.approx(row["share_pct"], abs=1e-9)
            not_started -= started_now
        assert not_started == pytest.approx(0, abs=1e-12)
