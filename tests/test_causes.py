"""
Checks on engine/causes.py: splitting a death between causes (A06, A20).

Run from the project folder:
    pytest tests/test_causes.py -v
"""

import numpy as np
import pytest

from engine.causes import (
    CAUSES,
    _calibration,
    _ratios,
    base_shares,
    cause_probabilities,
    smoking_cause_ratio,
)
from engine.data import load
from engine.risk import Person, age_group, hazard_ratio, population_mix, taper

AGES = [18, 25, 40, 55, 62, 70, 85, 95, 109]


def test_cause_list_matches_the_data():
    """The 11 groups in the data, without COVID-19 (no deaths in 2017-2019)."""
    data_causes = set(load("causes_of_death.csv")["cause"]) - {"covid"}
    assert set(CAUSES) == data_causes
    assert len(CAUSES) == 11


@pytest.mark.parametrize("sex", ["M", "F"])
def test_shares_add_to_one_at_every_age(sex):
    for age in range(18, 111):
        s = base_shares(sex, age)
        assert s.sum() == pytest.approx(1.0)
        assert (s >= 0).all()


def test_share_by_hand():
    """Men 60-64, 2017-2019: 3,463 lung cancer deaths out of 32,108 = 10.79%."""
    assert base_shares("M", 62)[CAUSES.index("lung_cancer")] == pytest.approx(3463 / 32108)
    assert (base_shares("M", 60) == base_shares("M", 64)).all()      # same 5-year group


def test_cause_ratios():
    """Thun 2013 current-smoker ratios; former smokers keep the all-cause share of the excess."""
    assert smoking_cause_ratio("lung_cancer", "current", "M") == 24.97
    assert smoking_cause_ratio("copd", "current", "F") == 22.35
    assert smoking_cause_ratio("diabetes", "current", "M") == 2.0          # 'other' ratio
    assert smoking_cause_ratio("lung_cancer", "never", "F") == 1.0
    # quit at 35-44 keeps (1.20 - 1) / (2.8 - 1) = 1/9 of the excess: 1 + 23.97 / 9 = 3.663
    assert smoking_cause_ratio("lung_cancer", "quit_35_44", "M") == pytest.approx(1 + 23.97 / 9)


@pytest.mark.parametrize("sex", ["M", "F"])
@pytest.mark.parametrize("age", AGES)
def test_population_reproduces_official_cause_shares(sex, age):
    """
    Across the population's smoking mix, each group weighted by its all-cause
    hazard, the deaths split by cause exactly as in the 2017-2019 data.
    """
    shares = base_shares(sex, age)
    mix = population_mix(sex, age_group(age))["smoking"]
    w = taper(age)
    a = _calibration(sex, age)
    expected = np.zeros(len(CAUSES))
    total = 0.0
    for level, p in mix.items():
        h = hazard_ratio("smoking", level, sex) ** w
        split = shares * _ratios(level, sex, age) / a
        expected += p * h * split / split.sum()
        total += p * h
    assert expected / total == pytest.approx(shares, rel=1e-9, abs=1e-15)


@pytest.mark.parametrize("smoking, quit_age", [("never", None), ("former", 40), ("current", None)])
def test_probabilities_add_to_one(smoking, quit_age):
    p = Person("F", 70, smoking=smoking, quit_age=quit_age)
    for age in AGES[3:]:
        cp = cause_probabilities(p, age)
        assert cp.sum() == pytest.approx(1.0)
        assert (cp >= 0).all()


@pytest.mark.parametrize("sex", ["M", "F"])
def test_smokers_die_more_of_lung_disease(sex):
    """Smoker > population > never smoker for lung cancer and COPD; the reverse for dementia."""
    lung, copd, dementia = (CAUSES.index(c) for c in ("lung_cancer", "copd", "dementia"))
    for age in (55, 62, 70):
        pop = base_shares(sex, age)
        smoker = cause_probabilities(Person(sex, 50, smoking="current"), age)
        never = cause_probabilities(Person(sex, 50), age)
        for c in (lung, copd):
            assert smoker[c] > pop[c] > never[c]
        assert smoker[dementia] < pop[dementia] < never[dementia]


def test_taper_brings_smokers_back_to_never_smokers():
    """At 109 the ratios have almost faded (taper 1/31), so the two mixes are close."""
    smoker = cause_probabilities(Person("M", 50, smoking="current"), 109)
    never = cause_probabilities(Person("M", 50), 109)
    assert np.abs(smoker - never).max() < 0.02
