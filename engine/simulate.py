"""
Living a life forward, year by year, and doing it 1,000 times (Phase 2, step 4).

Each simulated year, from the person's age now to 110 (A01-A03):
  1. every possible non-fatal event is drawn with its chance for this year
     (engine/events.py), and the person's state is updated;
  2. death is drawn with this year's personal death probability
     (engine/risk.py); if it happens, the cause is drawn (engine/causes.py)
     and the life ends. Exact age at death = age + a uniform fraction of the
     year (A03), matching the life expectancy formula.

Events within a year are not ordered (A03). If the same year draws both lung
and other-site cancer, it is recorded as lung; if it draws both retirement and
a new disability, retirement wins (the CPP pays one or the other).

All randomness comes from one seeded generator, so a seed always gives the
same lives. Everything that does not depend on the draws is worked out once
per person (Schedule), which keeps 1,000 lives fast.
"""

from dataclasses import dataclass, field, replace
from functools import lru_cache

import numpy as np

from engine.causes import CAUSE_LABELS, CAUSES, cause_probabilities
from engine.events import (
    DISABILITY_MAX_AGE,
    State,
    cancer_probabilities,
    crash_probability,
    disability_end_probability,
    disability_start_probability,
    family_probability,
    first_child_probability,
    heart_stroke_probabilities,
    retire_probability,
    smoking_incidence_multiplier,
)
from engine.mortality import MAX_AGE
from engine.risk import Person, personal_qx

START_YEAR = 2026


# ---------------------------------------------------------------- per-person schedule

@dataclass
class Schedule:
    """Everything about a person's future that does not depend on chance."""
    person: Person
    start_year: int
    ages: np.ndarray
    years: np.ndarray
    q: np.ndarray                    # death probability at each age
    causes: np.ndarray               # cause probabilities, one row per age
    fixed: dict[str, np.ndarray]     # state-independent event chances by age


def build_schedule(p: Person, start_year: int = START_YEAR, improve: bool = True) -> Schedule:
    ages = np.arange(p.age, MAX_AGE + 1)
    years = start_year + (ages - p.age)
    fixed = {k: np.zeros(len(ages)) for k in
             ("crash_injury", "cancer_lung", "cancer_other", "heart_attack", "stroke",
              "disability_start", "retire", "first_marriage", "divorce", "remarriage", "first_child")}
    for i, (a, y) in enumerate(zip(ages, years)):
        a, y = int(a), int(y)
        fixed["crash_injury"][i] = crash_probability(p.sex, a)
        lung, other = cancer_probabilities(p.sex, a)
        fixed["cancer_lung"][i] = min(1.0, lung * smoking_incidence_multiplier(p, "lung_cancer", a))
        fixed["cancer_other"][i] = other
        ha, st = heart_stroke_probabilities(p.sex, a)
        fixed["heart_attack"][i] = min(1.0, ha * smoking_incidence_multiplier(p, "heart", a))
        fixed["stroke"][i] = min(1.0, st * smoking_incidence_multiplier(p, "stroke", a))
        fixed["disability_start"][i] = disability_start_probability(p.sex, a, y)
        fixed["retire"][i] = retire_probability(p.sex, a)
        for event in ("first_marriage", "divorce", "remarriage"):
            fixed[event][i] = family_probability(event, p.sex, a)
        fixed["first_child"][i] = first_child_probability(p.sex, a)
    causes = np.array([cause_probabilities(p, int(a)) for a in ages])
    return Schedule(p, start_year, ages, years, personal_qx(p, start_year, improve=improve), causes, fixed)


@lru_cache(maxsize=None)
def _disability_end(sex: str, onset: int, duration: int, year: int) -> float:
    return disability_end_probability(sex, onset, duration, year)


def probabilities(sch: Schedule, s: State, i: int) -> dict[str, float]:
    """This year's event chances in state s; mirrors engine.events.event_probabilities (tested)."""
    f = sch.fixed
    age, year, sex = int(sch.ages[i]), int(sch.years[i]), sch.person.sex
    out = {"crash_injury": f["crash_injury"][i]}
    if not s.had_cancer:
        out["cancer_lung"] = f["cancer_lung"][i]
        out["cancer_other"] = f["cancer_other"][i]
    if not s.had_heart_attack:
        out["heart_attack"] = f["heart_attack"][i]
    if not s.had_stroke:
        out["stroke"] = f["stroke"][i]
    if s.disabled and age <= DISABILITY_MAX_AGE:
        out["disability_end"] = _disability_end(sex, s.disability_onset_age, s.disability_years, year)
    elif not s.disabled and not s.retired:
        out["disability_start"] = f["disability_start"][i]
    if not s.retired:
        out["retire"] = (1.0 if age > DISABILITY_MAX_AGE else 0.0) if s.disabled else f["retire"][i]
    key = {"never": "first_marriage", "married": "divorce", "divorced": "remarriage"}[s.marital]
    out[key] = f[key][i]
    if not s.has_child:
        out["first_child"] = f["first_child"][i]
    return {k: float(v) for k, v in out.items() if v > 0}


# ---------------------------------------------------------------- one life

@dataclass
class Life:
    events: list[tuple[int, int, str]] = field(default_factory=list)   # (age, year, event)
    death_age: float = 0.0           # exact age at death
    death_year: int = 0
    cause: str = ""
    final: State = field(default_factory=State)


def starting_state(p: Person) -> State:
    """Default state today until the survey asks (Phase 5): anyone over 70 has retired."""
    return State(retired=p.age > 70)


def live(sch: Schedule, rng: np.random.Generator, start: State | None = None) -> Life:
    s = replace(start) if start is not None else starting_state(sch.person)
    life = Life()
    for i, age in enumerate(sch.ages):
        age, year = int(age), int(sch.years[i])
        probs = probabilities(sch, s, i)
        happened = {k for k, v in probs.items() if rng.random() < v}

        if "crash_injury" in happened:
            s.crashes += 1
            life.events.append((age, year, "crash_injury"))
        if happened & {"cancer_lung", "cancer_other"}:
            s.had_cancer = True
            life.events.append((age, year, "cancer_lung" if "cancer_lung" in happened else "cancer_other"))
        for e, attr in (("heart_attack", "had_heart_attack"), ("stroke", "had_stroke")):
            if e in happened:
                setattr(s, attr, True)
                life.events.append((age, year, e))
        if "retire" in happened:
            if s.disabled:
                life.events.append((age, year, "disability_to_retirement"))
            else:
                life.events.append((age, year, "retire"))
            s.retired, s.disabled = True, False
        elif "disability_start" in happened:
            s.disabled, s.disability_onset_age, s.disability_years = True, age, 0
            life.events.append((age, year, "disability_start"))
        elif "disability_end" in happened:
            s.disabled = False
            life.events.append((age, year, "disability_end"))
        for e, new in (("first_marriage", "married"), ("divorce", "divorced"), ("remarriage", "married")):
            if e in happened:
                s.marital = new
                life.events.append((age, year, e))
        if "first_child" in happened:
            s.has_child = True
            life.events.append((age, year, "first_child"))

        if rng.random() < sch.q[i]:
            life.death_age = age + rng.random()
            life.death_year = year
            life.cause = CAUSES[rng.choice(len(CAUSES), p=sch.causes[i])]
            life.final = s
            return life
        if s.disabled:
            s.disability_years += 1
    raise RuntimeError("a life reached past age 110")      # q = 1 at 110, so never happens


def simulate(p: Person, n: int = 1000, seed: int = 0, start_year: int = START_YEAR,
             start: State | None = None, improve: bool = True) -> list[Life]:
    """n lives for this person, reproducible from the seed."""
    sch = build_schedule(p, start_year, improve)
    rng = np.random.default_rng(seed)
    return [live(sch, rng, start) for _ in range(n)]


# ---------------------------------------------------------------- telling it

SENTENCES = {
    "crash_injury": "you are injured in a car crash",
    "cancer_lung": "you are diagnosed with lung cancer",
    "cancer_other": "you are diagnosed with cancer",
    "heart_attack": "you have a heart attack",
    "stroke": "you have a stroke",
    "disability_start": "a serious illness or injury stops you working (CPP disability)",
    "disability_end": "you recover enough to leave disability",
    "disability_to_retirement": "your disability pension becomes a retirement pension",
    "retire": "you start your CPP retirement pension",
    "first_marriage": "you get married",
    "divorce": "you divorce",
    "remarriage": "you marry again",
    "first_child": "your first child is born",
}


def story(life: Life) -> list[str]:
    """One life as plain sentences."""
    lines = [f"At {age} ({year}), {SENTENCES[e]}." for age, year, e in life.events]
    lines.append(f"You die at {int(life.death_age)} ({life.death_year}) of {CAUSE_LABELS[life.cause]}.")
    return lines


def summary(lives: list[Life]) -> dict:
    """The honest picture across all the lives."""
    ages = np.array([lf.death_age for lf in lives])
    ever = lambda names: float(np.mean([any(e in names for _, _, e in lf.events) for lf in lives]))
    causes = {c: float(np.mean([lf.cause == c for lf in lives])) for c in CAUSES}
    return {
        "lives": len(lives),
        "median_death_age": float(np.median(ages)),
        "mean_death_age": float(ages.mean()),
        "death_age_10th_90th": (float(np.percentile(ages, 10)), float(np.percentile(ages, 90))),
        "reach_80": float(np.mean(ages >= 80)),
        "reach_90": float(np.mean(ages >= 90)),
        "cause_of_death": dict(sorted(causes.items(), key=lambda kv: -kv[1])),
        "ever": {
            "crash_injury": ever({"crash_injury"}),
            "cancer": ever({"cancer_lung", "cancer_other"}),
            "heart_attack": ever({"heart_attack"}),
            "stroke": ever({"stroke"}),
            "disability": ever({"disability_start"}),
            "married": ever({"first_marriage"}),
            "divorced": ever({"divorce"}),
            "first_child": ever({"first_child"}),
            "retired": ever({"retire", "disability_to_retirement"}),
        },
    }
