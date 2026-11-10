"""
Checks on engine/events.py: yearly chances of life events (A11, A13-A17, A21).

Expected values are read by hand from the cleaned tables in data/clean/.

Run from the project folder:
    pytest tests/test_events.py -v
"""

import pytest

from engine.data import load
from engine.events import (
    State,
    _childless_schedule,
    cancer_probabilities,
    crash_probability,
    disability_end_probability,
    disability_start_probability,
    eligible_share,
    event_probabilities,
    family_probability,
    first_child_probability,
    heart_stroke_probabilities,
    retire_probability,
    smoking_incidence_multiplier,
)
from engine.risk import Person, age_group, population_mix

ALWAYS = {"crash_injury"}


# ---------------------------------------------------------------- single lookups, by hand

def test_crash():
    """crash_rates.csv, 2019, men 25: 0.005478; ages 99+ share the age-99 rate."""
    assert crash_probability("M", 25) == pytest.approx(0.005478, abs=5e-7)
    assert crash_probability("F", 105) == crash_probability("F", 99)


def test_cancer_and_heart_stroke_groups():
    """Same 5-year group, same rate; heart attack and stroke at 18-19 use 20-24."""
    assert cancer_probabilities("M", 75) == cancer_probabilities("M", 79)
    assert cancer_probabilities("M", 77)[0] == pytest.approx(0.004681, abs=5e-7)
    assert heart_stroke_probabilities("F", 18) == heart_stroke_probabilities("F", 22)


def test_disability_start_by_hand():
    """Rate per 1,000 eligible x share eligible: men 40 in 2025."""
    inc = load("cpp_disability_incidence.csv")
    rate = float(inc.loc[(inc["sex"] == "M") & (inc["age"] == 40), "per_1000"].iloc[0])
    assert disability_start_probability("M", 40, 2025) == pytest.approx(rate / 1000 * 0.717)
    assert disability_start_probability("M", 65, 2025) == 0.0
    assert eligible_share("F", 2010) == eligible_share("F", 2025) == pytest.approx(0.657)
    assert eligible_share("M", 2150) == eligible_share("M", 2100) == pytest.approx(0.806)


def test_disability_end_by_hand():
    """
    Men, onset 40, in the 2nd year (1 year completed): 59 per 1,000 in 2025.
    Onset 43 uses the nearest published age (40); 2030 is halfway to the 2035 value.
    """
    t = load("cpp_disability_termination.csv")
    v2035 = float(t.loc[(t["year"] == 2035) & (t["sex"] == "M") & (t["age"] == 40) & (t["duration"] == 2), "per_1000"].iloc[0])
    assert disability_end_probability("M", 40, 1, 2025) == pytest.approx(0.059)
    assert disability_end_probability("M", 43, 1, 2025) == pytest.approx(0.059)
    assert disability_end_probability("M", 40, 1, 2030) == pytest.approx((59 + v2035) / 2 / 1000)
    assert disability_end_probability("M", 40, 9, 2025) == disability_end_probability("M", 40, 5, 2025)  # 6+


def test_retirement():
    """cpp_retirement.csv: men 65, 0.561404 given not started; 70 is certain; none before 60."""
    assert retire_probability("M", 65) == pytest.approx(0.561404, abs=1e-6)
    assert retire_probability("F", 70) == 1.0
    assert retire_probability("M", 59) == 0.0
    assert retire_probability("M", 71) == 0.0


def test_family_rates_by_hand():
    """family_events.csv: women 30-34 first marriage 47.3247 per 1,000; men 40-44 divorce 12.0."""
    assert family_probability("first_marriage", "F", 32) == pytest.approx(0.0473247, abs=1e-7)
    assert family_probability("divorce", "M", 41) == pytest.approx(0.012)


# ---------------------------------------------------------------- first child

def test_first_child_hazard_by_hand():
    """
    Synthetic cohort: share childless at 15 = 1 - 5 x 0.063198/1000 = 0.999684.
    Hazard at 15 = 5.35467/1000 / 0.999684.
    """
    h = _childless_schedule()
    childless_15 = 1 - 5 * 0.063198 / 1000
    assert h[15] == pytest.approx(5.35467 / 1000 / childless_15, rel=1e-5)
    assert all(0 <= v < 1 for v in h.values())


def test_childless_at_50_matches_the_birth_table():
    """Following the hazard from 15 leaves 1 - (all first births per woman) childless, about 37%."""
    h = _childless_schedule()
    t = load("family_events.csv")
    b = t[t["event"] == "first_child"]
    total_births = sum(5 * r / 1000 for r in b["rate_per_1000"])
    childless = 1 - 5 * 0.063198 / 1000
    for age in range(15, 50):
        childless *= 1 - h[age]
    assert childless == pytest.approx(1 - total_births, rel=1e-8)
    assert 0.3 < childless < 0.45


def test_men_follow_womens_schedule_three_years_later():
    assert first_child_probability("M", 33) == first_child_probability("F", 30)
    assert first_child_probability("M", 17) == 0.0 and first_child_probability("F", 50) == 0.0


# ---------------------------------------------------------------- smoking adjustment

@pytest.mark.parametrize("cause", ["lung_cancer", "heart", "stroke"])
@pytest.mark.parametrize("sex", ["M", "F"])
@pytest.mark.parametrize("age", [30, 60, 85])
def test_smoking_adjustment_averages_to_one(cause, sex, age):
    """Across the population's smoking mix the multiplier averages to 1, keeping official rates."""
    mix = population_mix(sex, age_group(age))["smoking"]
    examples = {"never": Person(sex, 25), "current": Person(sex, 25, smoking="current"),
                "quit_before_35": Person(sex, 25, smoking="former", quit_age=20),
                "quit_35_44": Person(sex, 50, smoking="former", quit_age=40),
                "quit_45_54": Person(sex, 60, smoking="former", quit_age=50),
                "quit_55_plus": Person(sex, 60, smoking="former", quit_age=58)}
    avg = sum(share * smoking_incidence_multiplier(examples[lvl], cause, age) for lvl, share in mix.items())
    assert avg == pytest.approx(1.0, rel=1e-12)


def test_smokers_get_more_lung_cancer():
    smoker = event_probabilities(Person("M", 60, smoking="current"), State(), 60, 2026)
    never = event_probabilities(Person("M", 60), State(), 60, 2026)
    pop_lung = cancer_probabilities("M", 60)[0]
    assert smoker["cancer_lung"] > pop_lung > never["cancer_lung"]
    assert smoker["cancer_other"] == never["cancer_other"]        # other sites not personalised


# ---------------------------------------------------------------- which events are possible

def test_events_depend_on_state():
    p = Person("F", 30)
    fresh = set(event_probabilities(p, State(), 30, 2026))
    assert {"first_marriage", "first_child", "cancer_lung", "disability_start"} <= fresh
    assert not {"divorce", "remarriage", "retire", "disability_end"} & fresh

    married = set(event_probabilities(p, State(marital="married", has_child=True), 30, 2026))
    assert "divorce" in married and "first_marriage" not in married and "first_child" not in married

    divorced = set(event_probabilities(p, State(marital="divorced"), 30, 2026))
    assert "remarriage" in divorced and "divorce" not in divorced

    done = State(had_cancer=True, had_heart_attack=True, had_stroke=True)
    assert not {"cancer_lung", "cancer_other", "heart_attack", "stroke"} & set(event_probabilities(p, done, 30, 2026))


def test_disability_and_retirement_rules():
    p = Person("M", 50)
    disabled = State(disabled=True, disability_onset_age=50, disability_years=2)
    at_60 = event_probabilities(p, disabled, 60, 2030)
    assert "disability_end" in at_60 and "retire" not in at_60 and "disability_start" not in at_60
    at_65 = event_probabilities(p, disabled, 65, 2035)
    assert at_65["retire"] == 1.0 and "disability_end" not in at_65       # converts at 65
    retired = event_probabilities(p, State(retired=True), 62, 2030)
    assert "disability_start" not in retired and "retire" not in retired


@pytest.mark.parametrize("age", [18, 30, 45, 64, 65, 70, 90, 109])
def test_all_probabilities_valid(age):
    for state in (State(), State(marital="married"), State(marital="divorced", retired=True)):
        probs = event_probabilities(Person("F", 18, smoking="current"), state, age, 2026)
        assert ALWAYS <= set(probs)
        assert all(0 < v <= 1 for v in probs.values())
