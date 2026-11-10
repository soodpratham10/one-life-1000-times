"""
Checks on engine/risk.py: survey answers -> personal death rates (A07, A08, A18).

Three kinds of check:
  * the hazard ratio table matches its sources and its stated formulas;
  * the arithmetic is right (worked by hand, and the exact rule that the
    population as a whole reproduces the base rates);
  * the results agree with the published studies the ratios come from.

Run from the project folder:
    pytest tests/test_risk.py -v
"""

import itertools

import numpy as np
import pytest

from engine.data import has_improvement_scale
from engine.mortality import cohort_qx, life_expectancy
from engine.risk import (
    CAP_HIGH,
    FACTORS,
    Person,
    age_group,
    average_multiplier,
    hazard_ratio,
    levels,
    person_multiplier,
    personal_qx,
    population_mix,
    relative_multiplier,
    taper,
)

LEVELS = {
    "smoking": ["never", "quit_before_35", "quit_35_44", "quit_45_54", "quit_55_plus", "current"],
    "activity": ["none", "under_150", "150_299", "300_449", "450_plus"],
    "bmi": ["under_18.5", "18.5_25", "25_27.5", "27.5_30", "30_35", "35_40", "40_plus"],
    "alcohol": ["under_25g", "25_44g", "45_64g", "65g_plus"],
    "fruit_veg": ["0_2", "3", "4", "5_plus"],
}
needs_mi = pytest.mark.skipif(not has_improvement_scale(), reason="CIA MI-2024 not built (copyrighted; see README)")
TYPICAL = dict(activity_minutes=200, height_cm=175, weight_kg=79, drinks_per_week=3, fruit_veg_per_day=3)


def e_unimproved(p: Person) -> float:
    """Life expectancy on 2017-2019 rates with no improvement, to compare with studies."""
    return life_expectancy(personal_qx(p, 2018, improve=False))


# ---------------------------------------------------------------- the hazard ratio table

@pytest.mark.parametrize("sex", ["M", "F"])
def test_every_level_has_a_positive_ratio(sex):
    for factor, lv in LEVELS.items():
        for level in lv:
            assert hazard_ratio(factor, level, sex) > 0


@pytest.mark.parametrize("sex", ["M", "F"])
def test_reference_levels_are_one(sex):
    for factor, level in [("smoking", "never"), ("activity", "none"), ("bmi", "18.5_25"),
                          ("alcohol", "under_25g"), ("fruit_veg", "0_2")]:
        assert hazard_ratio(factor, level, sex) == 1.0


@pytest.mark.parametrize("sex, current", [("M", 2.8), ("F", 3.0)])
def test_former_smoker_ratios_follow_their_formulas(sex, current):
    """Jha 2013: quitting at 45-54 removes two-thirds of the excess; judgement: half for 55+."""
    assert hazard_ratio("smoking", "current", sex) == current
    assert hazard_ratio("smoking", "quit_45_54", sex) == pytest.approx(1 + (current - 1) / 3, abs=0.005)
    assert hazard_ratio("smoking", "quit_55_plus", sex) == pytest.approx(1 + (current - 1) / 2, abs=0.005)


def test_fruit_veg_interpolation():
    """Log-linear between 2 servings (1.00) and 5 (0.87)."""
    assert hazard_ratio("fruit_veg", "3", "M") == pytest.approx(0.87 ** (1 / 3), abs=0.0005)
    assert hazard_ratio("fruit_veg", "4", "M") == pytest.approx(0.87 ** (2 / 3), abs=0.0005)


@pytest.mark.parametrize("sex", ["M", "F"])
def test_ratios_move_the_right_way(sex):
    hr = {f: [hazard_ratio(f, lvl, sex) for lvl in lv] for f, lv in LEVELS.items()}
    assert hr["smoking"] == sorted(hr["smoking"])                     # rises with exposure
    assert hr["activity"] == sorted(hr["activity"], reverse=True)     # falls with activity
    assert hr["alcohol"] == sorted(hr["alcohol"])
    assert hr["fruit_veg"] == sorted(hr["fruit_veg"], reverse=True)
    assert min(hr["bmi"]) == hazard_ratio("bmi", "18.5_25", sex)       # U shape
    assert hr["bmi"][1:] == sorted(hr["bmi"][1:])


# ---------------------------------------------------------------- answers -> levels

@pytest.mark.parametrize("weight, level", [(80.9, "18.5_25"), (81.0, "25_27.5"), (59.9, "under_18.5")])
def test_bmi_boundaries(weight, level):
    """180 cm: 81 kg is BMI 25.0 exactly; 80.9 kg is 24.97; 59.9 kg is 18.49."""
    assert levels(Person("M", 40, height_cm=180, weight_kg=weight))["bmi"] == level


@pytest.mark.parametrize("drinks, level", [(13, "under_25g"), (14, "25_44g"), (24, "45_64g"), (34, "65g_plus")])
def test_alcohol_boundaries(drinks, level):
    """Drinks a week x 13.45 g / 7: 13 -> 24.98 g, 14 -> 26.9 g, 24 -> 46.1 g, 34 -> 65.3 g a day."""
    assert levels(Person("F", 40, drinks_per_week=drinks))["alcohol"] == level


@pytest.mark.parametrize("minutes, level", [(0, "none"), (149, "under_150"), (150, "150_299"),
                                            (300, "300_449"), (450, "450_plus")])
def test_activity_boundaries(minutes, level):
    assert levels(Person("M", 30, activity_minutes=minutes))["activity"] == level


@pytest.mark.parametrize("quit_age, level", [(20, "quit_before_35"), (34, "quit_before_35"), (35, "quit_35_44"),
                                             (44, "quit_35_44"), (45, "quit_45_54"), (55, "quit_55_plus")])
def test_quit_age_boundaries(quit_age, level):
    assert levels(Person("M", 70, smoking="former", quit_age=quit_age))["smoking"] == level


@pytest.mark.parametrize("servings, level", [(0, "0_2"), (2.9, "0_2"), (3, "3"), (4.5, "4"), (5, "5_plus")])
def test_fruit_veg_boundaries(servings, level):
    assert levels(Person("F", 30, fruit_veg_per_day=servings))["fruit_veg"] == level


@pytest.mark.parametrize("bad", [
    dict(age=17), dict(age=110), dict(region="YT"), dict(smoking="sometimes"),
    dict(smoking="former"), dict(smoking="former", quit_age=60), dict(quit_age=30),
    dict(activity_minutes=-1), dict(height_cm=100), dict(weight_kg=20),
    dict(height_cm=200, weight_kg=35), dict(drinks_per_week=200), dict(fruit_veg_per_day=25),
])
def test_impossible_answers_rejected(bad):
    answers = dict(sex="M", age=40) | bad
    with pytest.raises(ValueError):
        Person(**answers)


# ---------------------------------------------------------------- arithmetic

@pytest.mark.parametrize("sex", ["M", "F"])
@pytest.mark.parametrize("group", [(18, 34), (35, 49), (50, 64), (65, 110)])
def test_population_mix_adds_to_one(sex, group):
    for factor, shares in population_mix(sex, group).items():
        assert sum(shares.values()) == pytest.approx(1.0)
        assert min(shares.values()) >= 0
        assert set(shares) <= set(LEVELS[factor])


def test_average_multiplier_by_hand():
    """
    Men 35-49 at age 40 (no taper). Prevalence: smokers 20.2%, former 16.9% (CTNS 25-44),
    active 62.4% (2018), overweight 43.7%, obese 30.9%, fruit and vegetables 5+ 23.3% (2017).
      smoking   0.629 + 0.169 x (0.75 x 1.05 + 0.25 x 1.20) + 0.202 x 2.8          = 1.378388
      activity  0.376 x (0.5 x 1 + 0.5 x 0.8) + 0.624 x (0.5 x 0.69 + 0.25 x 0.63 + 0.25 x 0.61)
      bmi       0.254 + 0.437 x 1.135 + 0.309 x (15.2 x 1.45 + 5.1 x 1.94 + 2.7 x 2.76) / 23
      fruit_veg 0.767 + 0.233 x 0.87
    """
    smoking = 0.629 + 0.169 * (0.75 * 1.05 + 0.25 * 1.20) + 0.202 * 2.8
    activity = 0.376 * 0.9 + 0.624 * (0.5 * 0.69 + 0.25 * 0.63 + 0.25 * 0.61)
    bmi = 0.254 + 0.437 * 1.135 + 0.309 * (15.2 * 1.45 + 5.1 * 1.94 + 2.7 * 2.76) / 23
    fruit_veg = 0.767 + 0.233 * 0.87
    assert average_multiplier("M", 40) == pytest.approx(smoking * activity * bmi * fruit_veg, rel=1e-9)
    assert smoking * activity * bmi * fruit_veg == pytest.approx(1.2774, abs=1e-4)


@pytest.mark.parametrize("sex", ["M", "F"])
@pytest.mark.parametrize("age", [25, 40, 57, 70, 85])
def test_population_reproduces_base_rates(sex, age):
    """
    The exact rule behind the method: averaging everyone's multiplier over the
    population mix gives the population average, so person / average averages
    to 1 and the population as a whole keeps the official death rates.
    """
    mix = population_mix(sex, age_group(age))
    w = taper(age)
    avg = average_multiplier(sex, age)
    total = 0.0
    for combo in itertools.product(*[mix[f].items() for f in FACTORS]):
        share = np.prod([s for _, s in combo])
        m = np.prod([hazard_ratio(f, lvl, sex) ** w for f, (lvl, _) in zip(FACTORS, combo)])
        total += share * m / avg
    assert total == pytest.approx(1.0, rel=1e-12)


def test_taper():
    assert taper(79) == 1.0
    assert taper(80) == pytest.approx(30 / 31)
    assert taper(110) == 0.0
    smoker = Person("M", 40, smoking="current")
    assert relative_multiplier(smoker, 110) == 1.0


def test_cap_applies_to_extreme_profiles():
    """Smoker, BMI 45, 50 drinks a week, no activity, no fruit: uncapped about 8x the average."""
    p = Person("M", 40, smoking="current", height_cm=170, weight_kg=130, drinks_per_week=50, fruit_veg_per_day=0)
    assert person_multiplier(p, 40) / average_multiplier("M", 40) > CAP_HIGH
    assert relative_multiplier(p, 40) == CAP_HIGH


def test_personal_rate_by_hand():
    """q_person = 1 - (1 - q_base) ** r for one cell."""
    p = Person("F", 50, smoking="current", **TYPICAL)
    q_base = cohort_qx("CA", "F", 50, 2026, improve=False)[0]
    r = relative_multiplier(p, 50)
    assert personal_qx(p, 2026, improve=False)[0] == pytest.approx(1 - (1 - q_base) ** r, rel=1e-12)


def test_personal_rates_shape():
    p = Person("M", 30, smoking="current", **TYPICAL)
    q = personal_qx(p, 2026, improve=False)
    assert len(q) == 110 - 30 + 1
    assert ((q >= 0) & (q <= 1)).all()
    assert q[-1] == 1.0
    never = personal_qx(Person("M", 30, **TYPICAL), 2026, improve=False)
    assert (never[:-1] < q[:-1]).all()


@needs_mi
def test_personal_rates_with_improvement():
    """With MI-2024 the same person's rates are lower in later years, and the rule is unchanged."""
    p = Person("F", 50, smoking="current", **TYPICAL)
    q_base = cohort_qx("CA", "F", 50, 2026)[0]
    assert personal_qx(p, 2026)[0] == pytest.approx(1 - (1 - q_base) ** relative_multiplier(p, 50), rel=1e-12)
    assert life_expectancy(personal_qx(p, 2026)) > life_expectancy(personal_qx(p, 2026, improve=False))


# ---------------------------------------------------------------- agreement with the studies

@pytest.mark.parametrize("sex", ["M", "F"])
def test_best_vs_worst_habits_gap_close_to_mport(sex):
    """
    Manuel et al., PLOS Med 2016 (MPoRT, Canada): life expectancy 17.9 years higher
    for the most favourable than the least favourable smoking, alcohol, activity and
    diet profile. Engine (same four factors, normal BMI): men 18.8, women 17.4.
    """
    best = Person(sex, 18, activity_minutes=500, height_cm=175, weight_kg=70, fruit_veg_per_day=5)
    worst = Person(sex, 18, smoking="current", height_cm=175, weight_kg=70,
                   drinks_per_week=40, fruit_veg_per_day=1)
    assert 13.9 < e_unimproved(best) - e_unimproved(worst) < 21.9


@pytest.mark.parametrize("sex", ["M", "F"])
def test_smokers_lose_about_a_decade(sex):
    """
    Jha et al. 2013: current smokers lose more than 10 years against never smokers
    (US rates). Engine: about 9 years at 25 (men 9.2, women 8.8); the smaller loss
    comes mostly from tapering the ratio after age 79.
    """
    gap = e_unimproved(Person(sex, 25, **TYPICAL)) - e_unimproved(Person(sex, 25, smoking="current", **TYPICAL))
    assert 8 < gap < 12


@pytest.mark.parametrize("sex", ["M", "F"])
def test_quitting_earlier_gains_more(sex):
    """Jha et al. 2013: quitting at 25-34, 35-44, 45-54 gains about 10, 9 and 6 years. Engine: 8.6, 7.2, 4.5."""
    gains = []
    for age in (30, 40, 50, 60):
        quit = Person(sex, age, smoking="former", quit_age=age, **TYPICAL)
        still = Person(sex, age, smoking="current", **TYPICAL)
        gains.append(e_unimproved(quit) - e_unimproved(still))
    assert gains == sorted(gains, reverse=True)
    assert gains[0] > 7
