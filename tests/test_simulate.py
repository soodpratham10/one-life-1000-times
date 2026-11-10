"""
Checks on engine/simulate.py: whole lives, one and many.

Two kinds of check:
  * every simulated life obeys the rules (one death, no events after it,
    no divorce before marriage, at most one first cancer, ...);
  * across many lives, the averages match what the rates imply when worked
    out exactly: mean age at death = age + life expectancy, the cause mix,
    expected crash injuries, the chance of a first cancer. Tolerance is four
    standard errors of the simulation, so a correct engine fails about once
    in 15,000 runs; the seeds are fixed, so results do not change run to run.

Run from the project folder:
    pytest tests/test_simulate.py -v
"""

import numpy as np
import pytest

from engine.causes import CAUSES
from engine.events import State, event_probabilities
from engine.mortality import life_expectancy
from engine.risk import Person
from engine.simulate import build_schedule, live, probabilities, simulate, story, summary

PERSON = Person("F", 40, smoking="current", activity_minutes=100, height_cm=165, weight_kg=80,
                drinks_per_week=7, fruit_veg_per_day=3)
N = 4000


@pytest.fixture(scope="module")
def sch():
    return build_schedule(PERSON, improve=False)


@pytest.fixture(scope="module")
def lives(sch):
    rng = np.random.default_rng(2026)
    return [live(sch, rng) for _ in range(N)]


def survival_to_start(q: np.ndarray) -> np.ndarray:
    """Chance of being alive at the start of each year."""
    return np.concatenate([[1.0], np.cumprod(1 - q[:-1])])


# ---------------------------------------------------------------- reproducible

def test_same_seed_same_lives():
    a = simulate(PERSON, n=50, seed=7, improve=False)
    b = simulate(PERSON, n=50, seed=7, improve=False)
    c = simulate(PERSON, n=50, seed=8, improve=False)
    key = lambda lives: [(lf.events, lf.death_age, lf.cause) for lf in lives]
    assert key(a) == key(b)
    assert key(a) != key(c)


# ---------------------------------------------------------------- the rules, on every life

def test_every_life_obeys_the_rules(lives):
    once = {"cancer_lung", "cancer_other", "heart_attack", "stroke", "first_marriage", "first_child"}
    for lf in lives:
        assert PERSON.age <= lf.death_age < 111 and lf.cause in CAUSES
        ages = [a for a, _, _ in lf.events]
        assert ages == sorted(ages) and all(PERSON.age <= a <= lf.death_age for a in ages)
        names = [e for _, _, e in lf.events]
        assert sum(n in ("cancer_lung", "cancer_other") for n in names) <= 1
        for e in once:
            assert names.count(e) <= 1
        assert sum(n in ("retire", "disability_to_retirement") for n in names) <= 1
        marital = [n for n in names if n in ("first_marriage", "divorce", "remarriage")]
        expected_next = "first_marriage"
        for n in marital:                      # never -> married -> divorced -> married -> ...
            assert n == expected_next
            expected_next = "divorce" if n in ("first_marriage", "remarriage") else "remarriage"
        disabled, retired = False, False
        for n in names:
            if n == "disability_start":
                assert not disabled and not retired
                disabled = True
            elif n == "disability_end":
                assert disabled
                disabled = False
            elif n == "disability_to_retirement":
                assert disabled
                disabled, retired = False, True
            elif n == "retire":
                assert not disabled
                retired = True


@pytest.mark.parametrize("state", [
    State(), State(marital="married", has_child=True), State(marital="divorced", retired=True),
    State(disabled=True, disability_onset_age=45, disability_years=3),
    State(had_cancer=True, had_heart_attack=True, had_stroke=True, crashes=2),
])
def test_fast_probabilities_match_events_module(sch, state):
    """The simulation's precomputed chances equal engine.events at every age and in every state."""
    for i in range(0, len(sch.ages), 7):
        age, year = int(sch.ages[i]), int(sch.years[i])
        fast = probabilities(sch, state, i)
        slow = event_probabilities(PERSON, state, age, year)
        assert fast.keys() == slow.keys(), age
        for k in fast:
            assert fast[k] == pytest.approx(slow[k], rel=1e-12), (age, k)


# ---------------------------------------------------------------- averages vs exact values

def test_mean_age_at_death_matches_life_expectancy(sch, lives):
    ages = np.array([lf.death_age for lf in lives])
    expected = PERSON.age + life_expectancy(sch.q)
    assert abs(ages.mean() - expected) < 4 * ages.std() / np.sqrt(N)


def test_cause_mix_matches_exact_expectation(sch, lives):
    s = survival_to_start(sch.q)
    p_die = s * sch.q                                   # chance of dying in each year
    expected = p_die @ sch.causes
    observed = np.array([np.mean([lf.cause == c for lf in lives]) for c in CAUSES])
    se = np.sqrt(expected * (1 - expected) / N)
    assert (np.abs(observed - expected) < 4 * se + 1e-9).all()


def test_crash_injuries_match_exact_expectation(sch, lives):
    """Expected injuries = sum over years of (alive at start) x (chance of an injury that year)."""
    expected = float(survival_to_start(sch.q) @ sch.fixed["crash_injury"])
    counts = np.array([sum(e == "crash_injury" for _, _, e in lf.events) for lf in lives])
    assert abs(counts.mean() - expected) < 4 * counts.std() / np.sqrt(N)


def test_first_cancer_matches_exact_expectation(sch, lives):
    """P(cancer) = sum of (alive) x (no cancer yet) x (chance this year)."""
    p = 1 - (1 - sch.fixed["cancer_lung"]) * (1 - sch.fixed["cancer_other"])
    no_cancer_yet = np.concatenate([[1.0], np.cumprod(1 - p[:-1])])
    expected = float(np.sum(survival_to_start(sch.q) * no_cancer_yet * p))
    observed = np.mean([any(e.startswith("cancer") for _, _, e in lf.events) for lf in lives])
    assert abs(observed - expected) < 4 * np.sqrt(expected * (1 - expected) / N)


# ---------------------------------------------------------------- outputs

def test_story_and_summary(lives):
    lines = story(lives[0])
    assert len(lines) == len(lives[0].events) + 1
    assert lines[-1].startswith("You die at")
    s = summary(lives[:1000])
    assert s["lives"] == 1000
    assert sum(s["cause_of_death"].values()) == pytest.approx(1.0)
    assert all(0 <= v <= 1 for v in s["ever"].values())
    low, high = s["death_age_10th_90th"]
    assert low < s["median_death_age"] < high
    assert 0 <= s["reach_90"] <= s["reach_80"] <= 1


def test_quitting_smoking_moves_the_lives():
    """Same seed, one answer changed: never smoked lives longer and dies less of lung cancer."""
    smoker = summary(simulate(PERSON, n=1000, seed=3, improve=False))
    never = summary(simulate(Person("F", 40, activity_minutes=100, height_cm=165, weight_kg=80,
                                    drinks_per_week=7, fruit_veg_per_day=3), n=1000, seed=3, improve=False))
    assert never["median_death_age"] > smoker["median_death_age"]
    assert never["cause_of_death"]["lung_cancer"] < smoker["cause_of_death"]["lung_cancer"]
