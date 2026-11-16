"""
Checks on the population check itself (validation/population.py): that the
synthetic population is built the way it says. The full comparison takes a few
minutes, so it is run by hand (python -m validation.population), not here.
"""

import numpy as np
import pytest

from engine.mortality import base_qx, life_expectancy
from engine.risk import age_group, levels, population_mix
from validation.population import (QUIT_AGE, START_AGES, combinations, marital_start,
                                   official, smoking_mix)

CASES = [(s, a) for s in ("M", "F") for a in START_AGES]


@pytest.mark.parametrize("sex,age", CASES)
def test_weights_add_to_one(sex, age):
    assert sum(w for _, w in combinations(sex, age)) == pytest.approx(1.0)
    assert sum(marital_start(sex, age).values()) == pytest.approx(1.0)


@pytest.mark.parametrize("sex,age", CASES)
def test_smoking_mix_keeps_every_smoker(sex, age):
    raw = population_mix(sex, age_group(age))["smoking"]
    mix = smoking_mix(sex, age)
    assert sum(mix.values()) == pytest.approx(sum(raw.values()))
    assert mix["never"] == raw["never"] and mix["current"] == raw["current"]
    # nobody quits at an age they have not reached
    for level in mix:
        if level.startswith("quit") and level != "quit_before_35":
            assert QUIT_AGE[level] <= age


def test_at_25_later_quit_bands_fold_into_quit_before_35():
    raw = population_mix("M", age_group(25))["smoking"]
    mix = smoking_mix("M", 25)
    assert set(mix) == {"never", "current", "quit_before_35"}
    assert mix["quit_before_35"] == pytest.approx(raw["quit_before_35"] + raw["quit_35_44"])


@pytest.mark.parametrize("sex,age", CASES)
def test_each_combination_is_in_its_levels_and_weights_match(sex, age):
    mix = population_mix(sex, age_group(age))
    smoke = smoking_mix(sex, age)
    for person, w in combinations(sex, age):
        lv = levels(person)
        expected = smoke[lv["smoking"]] * mix["activity"][lv["activity"]] * mix["bmi"][lv["bmi"]] \
            * mix["fruit_veg"][lv["fruit_veg"]]
        assert w == pytest.approx(expected)
        assert lv["alcohol"] == "under_25g"


@pytest.mark.parametrize("sex,age", CASES)
def test_official_side_is_the_life_table(sex, age):
    o = official(sex, age)
    q = base_qx("CA", sex)[age:]
    assert o["die"].sum() == pytest.approx(1.0)
    k = np.arange(len(q))
    assert o["e"] == pytest.approx(life_expectancy(q))
    assert o["die"] @ (k + 0.5) == pytest.approx(o["e"])      # the same UDD formula as the model side
    assert o["die"][0] == pytest.approx(q[0])
