"""
Checks on data/clean/crash_rates.csv (built by pipeline/08_crash_rates.py).

Run from the project folder:
    pytest
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
RATES_CSV = ROOT / "data" / "clean" / "crash_rates.csv"
CAUSES_CSV = ROOT / "data" / "clean" / "causes_of_death.csv"


@pytest.fixture(scope="module")
def rates() -> pd.DataFrame:
    if not RATES_CSV.exists():
        pytest.fail("data/clean/crash_rates.csv missing: run pipeline/08_crash_rates.py")
    return pd.read_csv(RATES_CSV)


def test_probabilities_valid(rates):
    adults = rates[rates["age"] >= 18]
    assert adults[["p_injured", "p_killed"]].notna().all().all()
    assert adults["p_injured"].between(0, 1).all()
    assert adults["p_killed"].between(0, 1).all()
    assert (adults["p_killed"] < adults["p_injured"]).all()


def test_rates_times_population_give_back_counts(rates):
    """rate x population = count: the division was done on matching rows."""
    assert (rates["p_injured"] * rates["population"] - rates["injured"]).abs().max() < 0.01


def test_young_adults_most_at_risk(rates):
    """Known pattern: adults 18-24 are injured more often than adults 55-64."""
    r = rates[rates["year"] == 2019]
    def band(lo, hi):
        b = r[r["age"].between(lo, hi)]
        return b["injured"].sum() / b["population"].sum()
    assert band(18, 24) > band(55, 64)


def test_crash_deaths_agree_with_death_certificates():
    """
    Two independent sources: police-reported crash deaths (Transport Canada) vs
    motor vehicle deaths on death certificates (StatCan). StatCan's count is
    somewhat higher (it includes crashes off public roads and deaths after 30 days),
    so the police count should be 80-100% of it.
    """
    if not CAUSES_CSV.exists():
        pytest.fail("data/clean/causes_of_death.csv missing: run pipeline/04_clean_causes_of_death.py")
    crash = pd.read_csv(RATES_CSV)
    causes = pd.read_csv(CAUSES_CSV)
    for year in [2019, 2020]:
        police = crash.loc[crash["year"] == year, "killed"].sum()
        certificates = causes.query("year == @year and sex == 'B' and cause == 'motor_vehicle'")["deaths"].sum()
        assert 0.80 <= police / certificates <= 1.00, (year, police, certificates)
