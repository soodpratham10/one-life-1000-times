"""
Life events: the yearly chance of each non-fatal event, given a person's
answers and where their life has got to (A11, A13-A17, A21).

    crash_injury     injured in a police-reported crash; can happen again     (A11)
    cancer_lung      first cancer diagnosis, lung                              (A13)
    cancer_other     first cancer diagnosis, any other site                    (A13)
    heart_attack     first heart attack                                        (A14)
    stroke           first stroke                                              (A14)
    disability_start becomes entitled to a CPP disability pension, ages 18-64  (A15)
    disability_end   recovery from a disability spell (CPP termination minus
                     the death rate of disabled people)                        (A15, A25)
    retire           starts the CPP retirement pension, ages 60-70             (A16)
    first_marriage, divorce, remarriage, first_child                           (A17)

Smoking personalises lung cancer, heart attack and stroke, using the same
cause ratios as deaths (A20), divided by the population average so Canadians
as a whole keep the official rates. Every other event uses population rates
(A21). Death is handled separately (engine/risk.py, engine/causes.py).
"""

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from engine.causes import smoking_cause_ratio
from engine.data import load
from engine.risk import Person, age_group, population_mix, smoking_path, taper

CRASH_YEAR = 2019
DISABILITY_MAX_AGE = 64       # CPP disability ends at 65 (converts to retirement)
RETIREMENT_AGES = (60, 70)
FATHER_AGE_GAP = 3            # A21 judgement: men's first child follows women's schedule 3 years later
FIRST_CHILD_AGES = (15, 49)   # women's ages in the birth table used here


@dataclass
class State:
    """Where a life has got to. Updated by the simulation each year."""
    marital: str = "never"          # never, married or divorced
    has_child: bool = False
    retired: bool = False
    disabled: bool = False
    disability_onset_age: int | None = None
    disability_years: int = 0       # completed years in the current spell
    had_cancer: bool = False
    cancer_site: str | None = None  # lung or other, once diagnosed (A22)
    cancer_years: int = 0           # completed years since the diagnosis
    had_heart_attack: bool = False
    had_stroke: bool = False
    crashes: int = 0


# ---------------------------------------------------------------- lookups

def _group_value(table, sex: str, age: int, column: str, **filters) -> float:
    rows = table[(table["sex"] == sex) & (table["age_lo"] <= age) & (table["age_hi"] >= age)]
    for col, val in filters.items():
        rows = rows[rows[col] == val]
    if len(rows) != 1:
        raise ValueError(f"expected one row for {sex} {age} {filters}, found {len(rows)}")
    return float(rows[column].iloc[0])


def crash_probability(sex: str, age: int) -> float:
    """Chance of being injured in a crash this year (2019); age 99 covers 99 and over."""
    t = load("crash_rates.csv")
    row = t[(t["year"] == CRASH_YEAR) & (t["sex"] == sex) & (t["age"] == min(age, 99))]
    return float(row["p_injured"].iloc[0])


def cancer_probabilities(sex: str, age: int) -> tuple[float, float]:
    """Population chance of a lung and of an other-site cancer diagnosis this year (2019)."""
    t = load("cancer_rates.csv")
    return (_group_value(t, sex, age, "p_lung"), _group_value(t, sex, age, "p_other_cancer"))


def heart_stroke_probabilities(sex: str, age: int) -> tuple[float, float]:
    """Population chance of a first heart attack and of a first stroke (2018-19); 18-19 use 20-24."""
    t = load("heart_stroke_rates.csv")
    a = max(age, 20)
    return (_group_value(t, sex, a, "p_heart_attack"), _group_value(t, sex, a, "p_stroke"))


def eligible_share(sex: str, year: int) -> float:
    """
    Share of adults 20-64 eligible for CPP disability. Published yearly to 2035 and
    every 5 years to 2100: years in between are interpolated; held flat outside 2025-2100.
    """
    t = load("cpp_disability_eligibility.csv")
    rows = t[t["sex"] == sex].sort_values("year")
    return float(np.interp(year, rows["year"], rows["eligible_pct"])) / 100


def disability_start_probability(sex: str, age: int, year: int) -> float:
    """Chance of a new CPP disability: rate per eligible person x share eligible (A15, A21)."""
    if age > DISABILITY_MAX_AGE:
        return 0.0
    t = load("cpp_disability_incidence.csv")
    per_1000 = float(t.loc[(t["sex"] == sex) & (t["age"] == age), "per_1000"].iloc[0])
    return per_1000 / 1000 * eligible_share(sex, year)


@lru_cache(maxsize=None)
def _termination_table() -> tuple[np.ndarray, dict]:
    """Published onset ages, and {(sex, onset, duration): (rate 2025, rate 2035)} per 1,000."""
    t = load("cpp_disability_termination.csv")
    ages = np.array(sorted(t["age"].unique()))
    rates = {}
    for (sex, age, dur), g in t.groupby(["sex", "age", "duration"]):
        by_year = dict(zip(g["year"], g["per_1000"]))
        rates[(sex, int(age), int(dur))] = (float(by_year[2025]), float(by_year[2035]))
    return ages, rates


def onset_band(onset_age: int) -> int:
    """Nearest onset age the termination table publishes (30, 40, 50, 60; ties go to the younger)."""
    ages = _termination_table()[0]
    return int(ages[np.abs(ages - onset_age).argmin()])


def disability_end_probability(sex: str, onset_age: int, completed_years: int, year: int) -> float:
    """
    CPP termination rate (recovery or death) for a spell that began at onset_age and
    has run completed_years full years: the rate for duration 1 applies in the first
    year in which the spell can end (the year after it began), and duration 6 covers 6
    and more. Onset ages use the nearest published age; years between 2025 and 2035
    are interpolated.
    """
    d = min(max(completed_years, 1), 6)
    r2025, r2035 = _termination_table()[1][(sex, onset_band(onset_age), d)]
    y = min(max(year, 2025), 2035)
    return (r2025 + (r2035 - r2025) * (y - 2025) / 10) / 1000


def retire_probability(sex: str, age: int) -> float:
    """Chance of starting the CPP pension this year, given not started (1 at 70)."""
    if not RETIREMENT_AGES[0] <= age <= RETIREMENT_AGES[1]:
        return 0.0
    t = load("cpp_retirement.csv")
    return float(t.loc[(t["sex"] == sex) & (t["age"] == age), "p_start_given_not_started"].iloc[0])


def family_probability(event: str, sex: str, age: int) -> float:
    """First marriage, divorce or remarriage: yearly rate for the people at risk (A17)."""
    t = load("family_events.csv")
    return _group_value(t[t["event"] == event], sex, age, "rate_per_1000") / 1000


@lru_cache(maxsize=None)
def _childless_schedule() -> dict[int, float]:
    """
    Women's chance of a first child at each age 15-49, given still childless.
    The table gives first births per woman (b); in a synthetic cohort the share
    still childless falls by b each year, so the hazard is b / share childless.
    """
    t = load("family_events.csv")
    t = t[t["event"] == "first_child"]
    childless = 1.0
    for age in range(10, 15):
        childless -= _group_value(t, "F", age, "rate_per_1000") / 1000
    hazard = {}
    for age in range(FIRST_CHILD_AGES[0], FIRST_CHILD_AGES[1] + 1):
        b = _group_value(t, "F", age, "rate_per_1000") / 1000
        hazard[age] = b / childless
        childless -= b
    return hazard


def first_child_probability(sex: str, age: int) -> float:
    """Chance of a first child this year for someone childless (men: women's schedule 3 years later)."""
    a = age if sex == "F" else age - FATHER_AGE_GAP
    return _childless_schedule().get(a, 0.0)


# ---------------------------------------------------------------- smoking adjustment

def smoking_incidence_multiplier(p: Person, cause: str, age: int) -> float:
    """Person's smoking ratio for this cause / population average (so the average person gets 1)."""
    w = taper(age)
    mix = population_mix(p.sex, age_group(age))["smoking"]
    average = sum(share * smoking_cause_ratio(cause, lvl, p.sex) ** w for lvl, share in mix.items())
    own = sum(chance * smoking_cause_ratio(cause, lvl, p.sex) ** w for lvl, chance in smoking_path(p, age))
    return own / average


# ---------------------------------------------------------------- one year

def event_probabilities(p: Person, s: State, age: int, year: int,
                        cancer: tuple[float, float] | None = None,
                        cardio: tuple[float, float] | None = None) -> dict[str, float]:
    """
    Chance of each event this year that can happen in this state. The simulation
    passes the person's own chances of a first cancer (lung, other) and of a first
    heart attack and stroke (engine/links.py, A22, A23) as `cancer` and `cardio`;
    without them, lung cancer, heart attack and stroke are the population rates
    scaled for smoking.
    """
    out = {"crash_injury": crash_probability(p.sex, age)}

    if not s.had_cancer:
        if cancer is None:
            lung, other = cancer_probabilities(p.sex, age)
            cancer = (min(1.0, lung * smoking_incidence_multiplier(p, "lung_cancer", age)), other)
        out["cancer_lung"], out["cancer_other"] = cancer
    if cardio is None:
        heart_attack, stroke = heart_stroke_probabilities(p.sex, age)
        cardio = (min(1.0, heart_attack * smoking_incidence_multiplier(p, "heart", age)),
                  min(1.0, stroke * smoking_incidence_multiplier(p, "stroke", age)))
    if not s.had_heart_attack:
        out["heart_attack"] = cardio[0]
    if not s.had_stroke:
        out["stroke"] = cardio[1]

    if s.disabled and age <= DISABILITY_MAX_AGE:
        from engine.disability import recovery_probability
        out["disability_end"] = recovery_probability(p.sex, s.disability_onset_age, s.disability_years, year, age)
    elif not s.disabled and not s.retired:
        out["disability_start"] = disability_start_probability(p.sex, age, year)
    if not s.retired:
        if s.disabled:
            # a CPP disability pension becomes a retirement pension at 65 (ends the spell)
            out["retire"] = 1.0 if age > DISABILITY_MAX_AGE else 0.0
        else:
            out["retire"] = retire_probability(p.sex, age)

    if s.marital == "never":
        out["first_marriage"] = family_probability("first_marriage", p.sex, age)
    elif s.marital == "married":
        out["divorce"] = family_probability("divorce", p.sex, age)
    else:
        out["remarriage"] = family_probability("remarriage", p.sex, age)
    if not s.has_child:
        out["first_child"] = first_child_probability(p.sex, age)

    return {k: v for k, v in out.items() if v > 0}
