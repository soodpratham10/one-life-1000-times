"""
Checks on data/clean/cia_mi2024.csv (built by pipeline/03_clean_mi2024.py).

The CIA file is not in the public repo, so these tests are skipped (not failed)
on a machine that has not downloaded it.

Run from the project folder:
    pytest
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
CLEAN_CSV = ROOT / "data" / "clean" / "cia_mi2024.csv"
RAW_XLSX = ROOT / "data" / "raw" / "cia_mi2024" / "224043te.xlsx"

pytestmark = pytest.mark.skipif(
    not CLEAN_CSV.exists(),
    reason="CIA MI-2024 not downloaded (copyrighted; see README)",
)


@pytest.fixture(scope="module")
def mi() -> pd.DataFrame:
    return pd.read_csv(CLEAN_CSV)


def test_grid_is_complete(mi):
    """2 sexes x ages 20-120 x years 1981-2119, once each, no gaps."""
    assert set(mi["sex"]) == {"F", "M"}
    assert set(mi["age"]) == set(range(20, 121))
    assert set(mi["year"]) == set(range(1981, 2120))
    assert len(mi) == 2 * 101 * 139
    assert not mi.duplicated(subset=["sex", "age", "year"]).any()
    assert mi["mi"].notna().all()


def test_rates_are_plausible(mi):
    """Annual improvement between -15% and +15% in every cell."""
    assert mi["mi"].between(-0.15, 0.15).all()


def test_long_term_rate_about_1_3_percent(mi):
    """Published long-term assumption: about 1.3% a year for ages 40-90."""
    ult = mi.query("year == 2100 and 40 <= age <= 90")["mi"]
    assert ult.between(0.0120, 0.0135).all()


def test_rates_constant_after_2060(mi):
    """The scale has reached its long-term level by 2060."""
    late = mi.query("year >= 2060")
    spread = late.groupby(["sex", "age"])["mi"].agg(lambda s: s.max() - s.min())
    assert spread.max() < 1e-9


def test_no_improvement_at_extreme_ages(mi):
    """Rates grade to zero at the very oldest ages."""
    assert (mi.query("age >= 115")["mi"] == 0).all()


@pytest.mark.skipif(not RAW_XLSX.exists(), reason="raw workbook not present")
def test_reshape_matches_workbook_cells(mi):
    """Spot cells read straight from the workbook match the tidy table."""
    for sheet, sex in [("female", "F"), ("male", "M")]:
        raw = pd.read_excel(RAW_XLSX, sheet_name=sheet, header=None)
        years = raw.iloc[6, 1:].astype(int).to_list()
        for row, col in [(7, 1), (27, 39), (52, 45), (72, 80), (107, 139)]:
            age, year, value = int(raw.iloc[row, 0]), years[col - 1], float(raw.iloc[row, col])
            got = mi.query("sex == @sex and age == @age and year == @year")["mi"].item()
            assert got == pytest.approx(value, abs=1e-12), (sex, age, year)
