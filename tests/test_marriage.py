"""
Checks on engine/marriage.py: marital-status death ratios (A24).

Run from the project folder:
    pytest tests/test_marriage.py -v
"""

import pytest

from engine.marriage import LEVELS, average_ratio, marital_mix, marital_ratio
from engine.risk import hazard_ratio, taper


@pytest.mark.parametrize("sex", ["M", "F"])
def test_ratios_from_the_meta_analyses(sex):
    assert hazard_ratio("marital", "married", sex) == 1.0
    assert hazard_ratio("marital", "single", sex) == 1.24                          # Roelfs 2011
    assert hazard_ratio("marital", "divorced", sex) == (1.37 if sex == "M" else 1.22)   # Shor 2012
    assert hazard_ratio("marital", "widowed", sex) == (1.27 if sex == "M" else 1.15)    # Shor 2012


@pytest.mark.parametrize("sex", ["M", "F"])
@pytest.mark.parametrize("age", [18, 30, 50, 70, 90, 105])
def test_population_keeps_official_rates(sex, age):
    """Averaged over Canada's 2019 marital mix, the ratio is exactly 1."""
    w = taper(age)
    mix = marital_mix(sex, age)
    avg = sum(share * hazard_ratio("marital", lvl, sex) ** w for lvl, share in mix.items())
    assert avg == pytest.approx(average_ratio(sex, age))
    total = sum(share * hazard_ratio("marital", lvl, sex) ** w / avg for lvl, share in mix.items())
    assert total == pytest.approx(1.0, rel=1e-12)
    assert set(mix) == set(LEVELS)


def test_ratio_by_hand():
    """Married man at 45: 1 / (population average); never married: 1.24 / average."""
    avg = average_ratio("M", 45)
    assert marital_ratio("married", "M", 45) == pytest.approx(1 / avg)
    assert marital_ratio("never", "M", 45) == pytest.approx(1.24 / avg)


@pytest.mark.parametrize("sex", ["M", "F"])
def test_married_lowest(sex):
    for age in (25, 45, 65, 85):
        assert marital_ratio("married", sex, age) < marital_ratio("never", sex, age)
        assert marital_ratio("married", sex, age) < marital_ratio("divorced", sex, age)
        assert marital_ratio("married", sex, age) < 1 < marital_ratio("never", sex, age)


def test_taper_at_110():
    assert marital_ratio("never", "F", 110) == pytest.approx(1.0)
