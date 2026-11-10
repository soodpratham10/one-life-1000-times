"""
Checks on data/clean/life_tables.csv (built by pipeline/02_clean_life_tables.py).

The last test is an independent recomputation: it rebuilds life expectancy
from qx alone and compares it with StatCan's published ex.

Run from the project folder:
    pytest
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
CLEAN_CSV = ROOT / "data" / "clean" / "life_tables.csv"
KEYS = ["period_start", "region", "sex"]


@pytest.fixture(scope="module")
def lt() -> pd.DataFrame:
    if not CLEAN_CSV.exists():
        pytest.fail("data/clean/life_tables.csv missing: run pipeline/02_clean_life_tables.py")
    return pd.read_csv(CLEAN_CSV)


def test_grid_is_complete(lt):
    """Every period x region x sex has all ages 0..110, once each."""
    assert lt["region"].nunique() == 10
    assert set(lt["sex"]) == {"B", "M", "F"}
    assert set(lt["age"]) == set(range(111))
    expected = lt["period_start"].nunique() * 10 * 3 * 111
    assert len(lt) == expected
    assert not lt.duplicated(subset=KEYS + ["age"]).any()


def test_no_missing_qx(lt):
    assert lt["qx"].notna().all()


def test_qx_between_0_and_1(lt):
    assert lt["qx"].between(0, 1).all()


def test_open_age_group_qx_is_one(lt):
    """Everyone alive at 110+ dies in the open age group."""
    assert (lt.loc[lt["age"] == 110, "qx"] == 1).all()


def test_px_complements_qx(lt):
    """px = 1 - qx, up to 5-decimal rounding of both."""
    assert (lt["px"] + lt["qx"] - 1).abs().max() <= 1.5e-5


def test_radix_is_100000(lt):
    assert (lt.loc[lt["age"] == 0, "lx"] == 100_000).all()


def test_lx_recursion(lt):
    """l(x+1) = l(x) * (1 - q(x)), allowing for rounding of lx to whole numbers."""
    lt = lt.sort_values(KEYS + ["age"])
    next_lx = lt.groupby(KEYS)["lx"].shift(-1)
    implied = lt["lx"] * (1 - lt["qx"])
    diff = (next_lx - implied).abs().dropna()
    assert diff.max() <= 2, f"largest gap {diff.max():.2f}"


def recompute_ex(qx: np.ndarray, e_open: float) -> np.ndarray:
    """
    Life expectancy at each age from qx alone.
    Deaths spread evenly within each year of age (L = average of l at both ends);
    the open group 110+ uses StatCan's published e(110).
    """
    lx = np.concatenate([[1.0], np.cumprod(1 - qx[:-1])])
    Lx = np.empty_like(lx)
    Lx[:-1] = (lx[:-1] + lx[1:]) / 2
    Lx[-1] = lx[-1] * e_open
    Tx = np.cumsum(Lx[::-1])[::-1]
    return Tx / lx


def test_ex_matches_independent_recomputation(lt):
    """Rebuilt ex agrees with StatCan's ex within 0.05 years at ages 1-100."""
    worst = 0.0
    for _, g in lt.sort_values(KEYS + ["age"]).groupby(KEYS):
        ex_rebuilt = recompute_ex(g["qx"].to_numpy(), g["ex"].iloc[-1])
        gap = np.abs(ex_rebuilt - g["ex"].to_numpy())[1:101].max()
        worst = max(worst, gap)
    assert worst <= 0.05, f"largest gap {worst:.3f} years"
