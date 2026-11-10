"""
Checks on engine/mortality.py: base death rates and mortality improvement.

Expected values are worked out by hand from the published tables, not taken
from the engine. Tests that need the CIA MI-2024 scale skip when it has not
been built on this computer (it is never committed: CIA copyright).

Run from the project folder:
    pytest tests/test_mortality.py -v
"""

import numpy as np
import pytest

from engine.data import has_improvement_scale
from engine.mortality import (
    MAX_AGE,
    REGIONS,
    base_qx,
    cohort_qx,
    improvement_factor,
    life_expectancy,
)

needs_mi = pytest.mark.skipif(
    not has_improvement_scale(),
    reason="CIA MI-2024 not built (copyrighted; see README)",
)


# ---------- life expectancy formula ----------

def test_life_expectancy_by_hand():
    """q = (0.5, 1): half die in year 1 (average 0.5 years lived), half in year 2 (1.5): e = 1.0."""
    assert life_expectancy(np.array([0.5, 1.0])) == pytest.approx(1.0)
    assert life_expectancy(np.array([1.0])) == pytest.approx(0.5)
    # q = (0.2, 0.5, 1): 0.2 x 0.5 + 0.4 x 1.5 + 0.4 x 2.5 = 1.7
    assert life_expectancy(np.array([0.2, 0.5, 1.0])) == pytest.approx(1.7)


# ---------- base table (no improvement) ----------

@pytest.mark.parametrize("region", REGIONS)
@pytest.mark.parametrize("sex", ["M", "F"])
def test_base_table_shape(region, sex):
    """Every region and sex: ages 0..110, rates between 0 and 1, q = 1 at 110."""
    q = base_qx(region, sex)
    assert len(q) == MAX_AGE + 1
    assert ((q >= 0) & (q <= 1)).all()
    assert q[MAX_AGE] == 1.0


def test_base_rate_matches_statcan():
    """StatCan 13-10-0114-01, Canada, males, 2017-2019, age 65: qx = 0.01108."""
    assert base_qx("CA", "M")[65] == pytest.approx(0.01108)


@pytest.mark.parametrize(
    "region, sex, published_e18",
    [
        ("CA", "M", 62.44),   # StatCan 13-10-0114-01, 2017-2019
        ("CA", "F", 66.59),
        ("MB", "M", 60.71),
        ("PE", "M", 61.36),   # derived PEI table (A10)
        ("PE", "F", 66.20),
    ],
)
def test_unimproved_life_expectancy_matches_table(region, sex, published_e18):
    """With no improvement, the engine's e(18) reproduces the life table's e(18)."""
    q = cohort_qx(region, sex, 18, 2018, improve=False)
    assert life_expectancy(q) == pytest.approx(published_e18, abs=0.01)


def test_cohort_rates_run_to_age_110():
    q = cohort_qx("ON", "F", 40, 2026, improve=False)
    assert len(q) == MAX_AGE - 40 + 1
    assert q[-1] == 1.0


def test_bad_inputs_rejected():
    with pytest.raises(ValueError):
        base_qx("YT", "M")              # territories not modelled
    with pytest.raises(ValueError):
        base_qx("CA", "B")              # a person is M or F
    with pytest.raises(ValueError):
        cohort_qx("CA", "M", 17, 2026)  # adults only (A01)


# ---------- mortality improvement (needs MI-2024) ----------

@needs_mi
def test_improvement_by_hand():
    """
    Canada, male, 65, in 2020: two years of improvement from the 2018 base.
    MI-2024 male age 65: 2019 = 0.0159330335604066, 2020 = 0.011221342142326.
    q = 0.01108 x (1 - 0.0159330...) x (1 - 0.0112213...) = 0.0107811105...
    """
    expected = 0.01108 * (1 - 0.0159330335604066) * (1 - 0.011221342142326)
    assert cohort_qx("CA", "M", 65, 2020)[0] == pytest.approx(expected, rel=1e-12)


@needs_mi
def test_no_improvement_up_to_base_year():
    assert improvement_factor("M", 50, 2018) == 1.0
    assert improvement_factor("M", 50, 2000) == 1.0


@needs_mi
def test_ages_18_19_use_age_20_rate():
    for year in (2019, 2030, 2060):
        f20 = improvement_factor("F", 20, year)
        assert improvement_factor("F", 18, year) == f20
        assert improvement_factor("F", 19, year) == f20


@needs_mi
def test_years_after_2119_keep_2119_rate():
    """Two years past 2119 = two more years at the 2119 rate (male 90: 0.0123993753097154)."""
    ratio = improvement_factor("M", 90, 2121) / improvement_factor("M", 90, 2119)
    assert ratio == pytest.approx((1 - 0.0123993753097154) ** 2, rel=1e-12)


@needs_mi
def test_age_110_never_improved():
    assert cohort_qx("CA", "F", 100, 2026)[-1] == 1.0
    assert improvement_factor("F", 110, 2080) == 1.0


@needs_mi
@pytest.mark.parametrize("sex", ["M", "F"])
def test_improvement_adds_years(sex):
    """An 18-year-old in 2026 lives longer with improvement than on 2018 rates, by a plausible 3-12 years."""
    plain = life_expectancy(cohort_qx("CA", sex, 18, 2026, improve=False))
    improved = life_expectancy(cohort_qx("CA", sex, 18, 2026))
    assert 3 < improved - plain < 12


@needs_mi
def test_other_base_period():
    """The 2022-2024 table works as a base; it starts from 2023, so 2023 rates are unimproved."""
    q = cohort_qx("CA", "M", 65, 2023, period=2022)
    assert q[0] == pytest.approx(base_qx("CA", "M", period=2022)[65])
