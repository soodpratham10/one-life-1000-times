"""
Checks on data/clean/life_tables_pei.csv (built by pipeline/05_build_pei_life_table.py).

The derived single-age table must reproduce what StatCan publishes for PEI
in its abridged table (13-10-0140-01), saved as data/clean/life_tables_pei_abridged.csv.

Run from the project folder:
    pytest
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PEI_CSV = ROOT / "data" / "clean" / "life_tables_pei.csv"
ABRIDGED_CSV = ROOT / "data" / "clean" / "life_tables_pei_abridged.csv"


@pytest.fixture(scope="module")
def pei() -> pd.DataFrame:
    if not PEI_CSV.exists():
        pytest.fail("data/clean/life_tables_pei.csv missing: run pipeline/05_build_pei_life_table.py")
    return pd.read_csv(PEI_CSV)


@pytest.fixture(scope="module")
def published() -> pd.DataFrame:
    """PEI's abridged table as StatCan publishes it: p and e by age group."""
    if not ABRIDGED_CSV.exists():
        pytest.fail("data/clean/life_tables_pei_abridged.csv missing: run pipeline/05_build_pei_life_table.py")
    return pd.read_csv(ABRIDGED_CSV)


def test_grid_is_complete(pei):
    assert set(pei["sex"]) == {"B", "M", "F"}
    assert set(pei["age"]) == set(range(111))
    assert len(pei) == pei["period_start"].nunique() * 3 * 111
    assert not pei.duplicated(subset=["period_start", "sex", "age"]).any()


def test_qx_valid(pei):
    assert pei["qx"].between(0, 1).all()
    assert (pei.loc[pei["age"] == 110, "qx"] == 1).all()
    assert (pei.loc[pei["age"] < 110, "qx"] < 1).all()


def test_group_survival_matches_published(pei, published):
    """Over every age group below 90, single-age survival multiplies to PEI's published p."""
    worst = 0.0
    for _, g in published[published["age_lo"] < 90].iterrows():
        ages = pei.query("period_start == @g.period_start and sex == @g.sex "
                         "and @g.age_lo <= age <= @g.age_hi")
        worst = max(worst, abs(np.prod(1 - ages["qx"]) - g["p_group"]))
    assert worst <= 1e-6, f"largest gap {worst:.2e}"


def test_e90_matches_published(pei, published):
    """Life expectancy at 90 equals PEI's published e(90+), within its 2-decimal rounding."""
    mine = pei[pei["age"] == 90].set_index(["period_start", "sex"])["ex"]
    theirs = published[published["age_lo"] == 90].set_index(["period_start", "sex"])["e_group"]
    assert (mine - theirs).abs().max() <= 0.005


def test_e0_close_to_published(pei, published):
    """Life expectancy at birth within 0.1 years of StatCan's (methods differ slightly in year 0)."""
    mine = pei[pei["age"] == 0].set_index(["period_start", "sex"])["ex"]
    theirs = published[published["age_lo"] == 0].set_index(["period_start", "sex"])["e_group"]
    assert (mine - theirs).abs().max() <= 0.1
