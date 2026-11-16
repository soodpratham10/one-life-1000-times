"""
Checks on engine/disability.py: deaths and recovery of CPP disability beneficiaries (A25).

Run from the project folder:
    pytest tests/test_disability.py -v
"""

import numpy as np
import pandas as pd
import pytest

from engine.data import load
from engine.disability import (
    COHORT_YEAR,
    _table,
    calibration,
    death_multipliers,
    disabled_q,
    mortality_ratio,
    recovery_probability,
    work_transition,
)
from engine.events import disability_end_probability, disability_start_probability, retire_probability
from engine.mortality import base_qx


@pytest.mark.parametrize("sex, age, rate, ratio", [
    ("M", 50, 28.9, 9.5), ("M", 64, 40.0, 3.7), ("F", 50, 20.7, 9.9), ("F", 64, 22.7, 3.3), ("M", 20, 39.4, 56.3),
])
def test_table_typed_in_correctly(sex, age, rate, ratio):
    """Spot values from Actuarial Study No. 16, Table 40 (2011)."""
    t = _table()
    row = t[(t["sex"] == sex) & (t["age"] == age)]
    assert float(row["disabled_per_1000"].iloc[0]) == rate
    assert float(row["ratio"].iloc[0]) == ratio


def test_table_complete():
    t = _table()
    assert len(t) == 90 and set(t["age"]) == set(range(20, 65)) and set(t["sex"]) == {"M", "F"}
    assert (t["ratio"] > 1).all()


@pytest.mark.parametrize("sex", ["M", "F"])
def test_ratio_falls_with_age_after_45(sex):
    r = [mortality_ratio(sex, a) for a in range(45, 65)]
    assert r == sorted(r, reverse=True)
    assert mortality_ratio(sex, 18) == mortality_ratio(sex, 20)
    assert mortality_ratio(sex, 65) == 1.0


def test_recovery_by_hand():
    """Men, onset 50, second year, at 52 in 2025: termination 66 per 1,000 minus a disabled 52-year-old's death rate."""
    q = base_qx("CA", "M")[52]
    expected = 0.066 - (1 - (1 - q) ** mortality_ratio("M", 52))
    assert recovery_probability("M", 50, 2, 2025, 52) == pytest.approx(expected)
    assert disabled_q("M", 52) == pytest.approx(1 - (1 - q) ** mortality_ratio("M", 52))


@pytest.mark.parametrize("sex", ["M", "F"])
def test_recovery_never_negative_and_below_termination(sex):
    for onset in (30, 40, 50, 60):
        for years in range(1, 7):
            age = min(onset + years, 64)
            rec = recovery_probability(sex, onset, years, 2030, age)
            assert 0 <= rec <= disability_end_probability(sex, onset, years, 2030)


@pytest.mark.parametrize("sex", ["M", "F"])
def test_calibration_reproduces_population_deaths(sex):
    """Re-run the cohort: disabled at their own rate, everyone else at gamma, total = official deaths each age."""
    cal = calibration(sex)
    q = base_qx("CA", sex)
    p = np.zeros(26)
    p[0] = 1.0
    for age in range(18, 65):
        mass, disabled = p.sum(), p[1:25].sum()
        assert disabled / mass == pytest.approx(cal["share_disabled"][age])
        q_state = np.full(26, 1 - (1 - q[age]) ** cal["gamma"][age])
        q_state[1:25] = disabled_q(sex, age)
        assert (p * q_state).sum() == pytest.approx(mass * q[age], rel=1e-9)
        t = work_transition(sex, age, COHORT_YEAR, disability_start_probability(sex, age, COHORT_YEAR),
                            retire_probability(sex, age))
        p = (p * (1 - q_state)) @ t


@pytest.mark.parametrize("sex", ["M", "F"])
def test_multipliers(sex):
    cal = calibration(sex)
    for age in range(18, 65):
        g, r = death_multipliers(sex, age)
        assert 0.5 < g <= 1 and r > 1
        assert g == cal["gamma"][age]
    assert death_multipliers(sex, 65) == (1.0, 1.0)


def test_transition_rows_add_to_one():
    for age in (30, 55, 64, 65, 68):
        t = work_transition("F", age, 2030, 0.004, retire_probability("F", age))
        assert np.allclose(t.sum(axis=1), 1)
        assert (t >= 0).all()


@pytest.mark.parametrize("sex, beneficiaries_55_59, beneficiaries_60_64", [
    ("M", 44212, 53685), ("F", 49445, 55950),
])
def test_disabled_share_against_cpp_beneficiaries(sex, beneficiaries_55_59, beneficiaries_60_64):
    """
    Actual-to-expected: CPP disability beneficiaries on 1 July 2011 (Actuarial Study No. 16,
    Table 34) over Canada-minus-Quebec population (CPP excludes Quebec), against the cohort's
    disabled share. The cohort uses the lower 2029+ incidence rates, so it is expected to sit
    below 2011: A/E men about 1.3-1.4, women about 1.1-1.3.
    """
    pop = load("population.csv")
    cal = calibration(sex)
    for (lo, hi), ben in (((55, 59), beneficiaries_55_59), ((60, 64), beneficiaries_60_64)):
        t = pop[(pop["year"] == 2011) & pop["age"].between(lo, hi) & (pop["sex"] == sex)]
        outside_quebec = t.loc[t["region"] == "CA", "population"].sum() - t.loc[t["region"] == "QC", "population"].sum()
        actual = ben / outside_quebec
        model = cal["share_disabled"][lo:hi + 1].mean()
        assert 0.9 < actual / model < 1.6, (lo, hi, actual / model)
