"""
Checks on the CPP improvement basis (A28): the Chief Actuary's assumed mortality
improvement rates from the 32nd CPP actuarial report, the project's default.

  * the typed-in tables match the report (spot values) and are complete;
  * the arithmetic is right (one factor worked by hand; the spans; age 110);
  * the 2019-2025 scale reproduces the report's 2025 life expectancies (fitted);
  * out of sample: the report's period life expectancies in 2050 and 2075 and
    its cohort life expectancies from 2025 and 2050 (not fitted).

Run from the project folder:
    pytest tests/test_cpp_improvement.py -v
"""

import numpy as np
import pandas as pd
import pytest

from engine.mortality import (
    CPP_FILE,
    CPP_LE_FILE,
    MAX_AGE,
    _period_e,
    base_qx,
    cohort_qx,
    cpp_rates,
    cpp_scale,
    improvement_factor,
    life_expectancy,
)

TABLE = pd.read_csv(CPP_FILE)
LE = pd.read_csv(CPP_LE_FILE)


def report_e(sex, basis, year, age):
    row = LE[(LE["sex"] == sex) & (LE["basis"] == basis) & (LE["year"] == year) & (LE["age"] == age)]
    return float(row["e"].iloc[0])


# ---------------------------------------------------------------- the tables

def test_table_41_spot_values():
    """Typed in from Table 41 (percent): men 20-49 in 2025 1.6, 2026-2038 2.4; women 95+ ultimate 0.2."""
    def cell(sex, lo, col):
        return float(TABLE[(TABLE["sex"] == sex) & (TABLE["age_lo"] == lo)][col].iloc[0])
    assert cell("M", 20, "mi_2025") == 1.6 and cell("M", 20, "mi_2026_2038") == 2.4
    assert cell("F", 20, "mi_2026_2038") == 2.7
    assert cell("M", 85, "mi_2025") == 2.6
    assert cell("F", 95, "mi_2039_plus") == 0.2


@pytest.mark.parametrize("sex", ["M", "F"])
def test_table_41_covers_every_age_once_and_ultimate_rates(sex):
    """Bands run 0-110 with no gaps; ultimate 1.0% under 90, 0.6% at 90-94, 0.2% at 95+ (report text)."""
    t = TABLE[TABLE["sex"] == sex].sort_values("age_lo")
    assert t["age_lo"].iloc[0] == 0 and t["age_hi"].iloc[-1] == MAX_AGE
    assert (t["age_lo"].iloc[1:].to_numpy() == t["age_hi"].iloc[:-1].to_numpy() + 1).all()
    ult = cpp_rates(sex)[:, 2]
    assert np.allclose(ult[:90], 0.010) and np.allclose(ult[90:95], 0.006) and np.allclose(ult[95:110], 0.002)
    assert ult[MAX_AGE] == 0


def test_life_expectancy_table_complete_and_ordered():
    """Tables 43 and 44: both sexes, 2025/2050/2075, ages 0-100; falls with age; cohort >= period; women > men."""
    assert len(LE) == 2 * 2 * 3 * 14
    for (sex, basis, year), g in LE.groupby(["sex", "basis", "year"]):
        e = g.sort_values("age")["e"].to_numpy()
        assert (np.diff(e) < 0).all()
    for sex in ("M", "F"):
        for year in (2025, 2050, 2075):
            for age in (0, 65):
                assert report_e(sex, "cohort", year, age) >= report_e(sex, "period", year, age)
    assert report_e("F", "period", 2025, 0) > report_e("M", "period", 2025, 0)


# ---------------------------------------------------------------- arithmetic

def test_factor_by_hand():
    """Man aged 40 in 2030: 7 years 2019-2025 at k x 1.6%, then 5 years 2026-2030 at 2.4%."""
    k_young, _ = cpp_scale("M")
    expected = (1 - k_young * 0.016) ** 7 * (1 - 0.024) ** 5
    assert improvement_factor("M", 40, 2030) == pytest.approx(expected, rel=1e-12)


def test_factor_after_2038_uses_ultimate_rate():
    """Woman aged 70: 2045 vs 2040 is five more years at the 1.0% ultimate rate."""
    ratio = improvement_factor("F", 70, 2045) / improvement_factor("F", 70, 2040)
    assert ratio == pytest.approx(0.99 ** 5, rel=1e-12)


def test_no_improvement_up_to_base_year_or_at_110():
    assert improvement_factor("M", 50, 2018) == 1.0
    assert improvement_factor("F", MAX_AGE, 2080) == 1.0
    assert cohort_qx("CA", "F", 100, 2026)[-1] == 1.0


def test_default_is_cpp():
    assert np.array_equal(cohort_qx("CA", "M", 40, 2026), cohort_qx("CA", "M", 40, 2026, improve="cpp"))
    with pytest.raises(ValueError):
        cohort_qx("CA", "M", 40, 2026, improve="soa")


# ---------------------------------------------------------------- fit and out-of-sample checks

@pytest.mark.parametrize("sex", ["M", "F"])
def test_scale_reproduces_the_2025_life_expectancies(sex):
    """Fitted: period e(65) and e(0) in 2025 equal Table 43 exactly."""
    scale = cpp_scale(sex)
    assert _period_e(sex, 2025, 65, scale) == pytest.approx(report_e(sex, "period", 2025, 65), abs=1e-9)
    assert _period_e(sex, 2025, 0, scale) == pytest.approx(report_e(sex, "period", 2025, 0), abs=1e-9)
    assert 0 < scale[0] < 1 and 0 < scale[1] < 1     # 2019-2025 improved less than the 2025 rate


@pytest.mark.parametrize("sex", ["M", "F"])
@pytest.mark.parametrize("year", [2050, 2075])
@pytest.mark.parametrize("age", [0, 20, 40, 65, 80])
def test_period_life_expectancy_out_of_sample(sex, year, age):
    """Not fitted: Table 43 in 2050 and 2075. Engine: within 0.25 years at every age tested (values 0.1 apart)."""
    assert _period_e(sex, year, age, cpp_scale(sex)) == pytest.approx(report_e(sex, "period", year, age), abs=0.25)


@pytest.mark.parametrize("sex", ["M", "F"])
@pytest.mark.parametrize("year", [2025, 2050])
@pytest.mark.parametrize("age", [20, 40, 65, 80])
def test_cohort_life_expectancy_out_of_sample(sex, year, age):
    """Not fitted: Table 44, life expectancy with improvement after the year shown. Engine: within 0.5 years."""
    q = cohort_qx("CA", sex, age, year)
    assert life_expectancy(q) == pytest.approx(report_e(sex, "cohort", year, age), abs=0.5)


@pytest.mark.parametrize("sex", ["M", "F"])
def test_cpp_basis_adds_years(sex):
    """An 18-year-old in 2026 lives longer with improvement than on 2018 rates, by a plausible 3-10 years."""
    plain = life_expectancy(cohort_qx("CA", sex, 18, 2026, improve=False))
    assert 3 < life_expectancy(cohort_qx("CA", sex, 18, 2026)) - plain < 10


def test_period_e_without_improvement_is_the_base_table():
    q = base_qx("CA", "M")
    assert _period_e("M", 2018, 65, (1.0, 1.0)) == pytest.approx(life_expectancy(q[65:]))
