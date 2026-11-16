"""
Living a life forward, year by year, and doing it 1,000 times (Phase 2, step 4).

Each simulated year, from the person's age now to 110 (A01-A03):
  1. every possible non-fatal event is drawn with its chance for this year
     (engine/events.py), and the person's state is updated;
  2. after a first heart attack or stroke this year, its acute fatality is
     drawn (engine/links.py, A23);
  3. death is drawn with this year's death probability for the person's state
     at the start of the year: cancer state (A22), whether they survived an
     earlier heart attack or stroke (A23), marital state (A24) and whether
     they are disabled (A25), built on engine/risk.py and engine/causes.py. If it happens, the cause is drawn and the life ends.
     Exact age at death = age + a uniform fraction of the year (A03).

Events within a year are not ordered (A03). If the same year draws both lung
and other-site cancer, it is recorded as lung; if it draws both retirement and
a new disability, retirement wins (the CPP pays one or the other).

All randomness comes from one seeded generator, so a seed always gives the
same lives. Everything that does not depend on the draws is worked out once
per person (Schedule), which keeps 1,000 lives fast.
"""

from dataclasses import dataclass, field, replace

import numpy as np

from engine.causes import CAUSE_LABELS, CAUSES, cause_probabilities
from engine.disability import recovery_probability, work_transition
from engine.events import (
    DISABILITY_MAX_AGE,
    State,
    crash_probability,
    disability_start_probability,
    family_probability,
    first_child_probability,
    retire_probability,
)
from engine.links import MARITAL_STATES, N_CANCER, death_tables, person_incidence
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
    q: np.ndarray                    # personal death probability at each age (engine/risk.py)
    causes: np.ndarray               # personal cause probabilities, one row per age
    fixed: dict[str, np.ndarray]     # state-independent event chances by age
    start_marital: str = "never"     # marital state at the start (A24)
    q_state: np.ndarray = None       # death probability [age, cancer, heart attack survivor, stroke survivor, marital, disabled]
    c_state: np.ndarray = None       # cause mix [age, cancer, heart attack survivor, stroke survivor, cause]
    acute_heart: np.ndarray = None   # acute fatality of a first heart attack, by age
    acute_stroke: np.ndarray = None

    @staticmethod
    def cancer_state(s: State) -> int:
        if s.cancer_site is None:
            return 0
        d = min(s.cancer_years, 5)
        return 1 + d if s.cancer_site == "lung" else 7 + d

    def death(self, i: int, s: State, heart_survivor: bool, stroke_survivor: bool, marital: str, disabled: bool):
        """This year's death probability and cause mix (states as at the start of the year)."""
        key = (i, self.cancer_state(s), int(heart_survivor), int(stroke_survivor))
        return self.q_state[key + (MARITAL_STATES.index(marital), int(disabled))], self.c_state[key]


def build_schedule(p: Person, start_year: int = START_YEAR, improve: bool = True,
                   start_marital: str = "never") -> Schedule:
    ages = np.arange(p.age, MAX_AGE + 1)
    years = start_year + (ages - p.age)
    fixed = {k: np.zeros(len(ages)) for k in
             ("crash_injury", "cancer_lung", "cancer_other", "heart_attack", "stroke",
              "disability_start", "retire", "first_marriage", "divorce", "remarriage", "first_child")}
    for i, (a, y) in enumerate(zip(ages, years)):
        a, y = int(a), int(y)
        fixed["crash_injury"][i] = crash_probability(p.sex, a)
        fixed["disability_start"][i] = disability_start_probability(p.sex, a, y)
        fixed["retire"][i] = retire_probability(p.sex, a)
        for event in ("first_marriage", "divorce", "remarriage"):
            fixed[event][i] = family_probability(event, p.sex, a)
        fixed["first_child"][i] = first_child_probability(p.sex, a)
    causes = np.array([cause_probabilities(p, int(a)) for a in ages])
    q = personal_qx(p, start_year, improve=improve)
    fixed.update(person_incidence(q, causes, p.sex, p.age))
    q_state, c_state, acute_h, acute_s = death_tables(q, causes, p.sex, p.age)
    return Schedule(p, start_year, ages, years, q, causes, fixed, start_marital, q_state, c_state, acute_h, acute_s)


def probabilities(sch: Schedule, s: State, i: int) -> dict[str, float]:
    """
    This year's event chances in state s; mirrors engine.events.event_probabilities
    given the person's cancer diagnosis rates from engine.links (tested).
    """
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
        out["disability_end"] = recovery_probability(sex, s.disability_onset_age, s.disability_years, year, age)
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


def starting_state(sch: "Schedule") -> State:
    """Default state today until the survey asks (Phase 5): anyone over 70 has retired."""
    return State(retired=sch.person.age > 70, marital=sch.start_marital)


def live(sch: Schedule, rng: np.random.Generator, start: State | None = None) -> Life:
    s = replace(start) if start is not None else starting_state(sch)
    life = Life()
    for i, age in enumerate(sch.ages):
        age, year = int(age), int(sch.years[i])
        heart_survivor, stroke_survivor = s.had_heart_attack, s.had_stroke   # as at the start of the year
        marital_now, disabled_now = s.marital, s.disabled
        probs = probabilities(sch, s, i)
        happened = {k for k, v in probs.items() if rng.random() < v}

        if "crash_injury" in happened:
            s.crashes += 1
            life.events.append((age, year, "crash_injury"))
        if happened & {"cancer_lung", "cancer_other"}:
            s.had_cancer, s.cancer_years = True, 0
            s.cancer_site = "lung" if "cancer_lung" in happened else "other"
            life.events.append((age, year, "cancer_" + s.cancer_site))
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

        for e, attr, acute, cause in (("heart_attack", "had_heart_attack", sch.acute_heart, "heart"),
                                      ("stroke", "had_stroke", sch.acute_stroke, "stroke")):
            if e in happened:
                setattr(s, attr, True)
                life.events.append((age, year, e))
                if rng.random() < acute[i]:             # dies of it within the year (A23)
                    life.death_age, life.death_year, life.cause = age + rng.random(), year, cause
                    life.final = s
                    return life

        q, cause_mix = sch.death(i, s, heart_survivor, stroke_survivor, marital_now, disabled_now)
        if rng.random() < q:
            life.death_age = age + rng.random()
            life.death_year = year
            life.cause = CAUSES[rng.choice(len(CAUSES), p=cause_mix)]
            life.final = s
            return life
        if s.disabled:
            s.disability_years += 1
        if s.cancer_site is not None:
            s.cancer_years += 1
    raise RuntimeError("a life reached past age 110")      # q = 1 at 110, so never happens


def exact(sch: Schedule) -> dict:
    """
    What the simulation should average to, worked out exactly by following the
    share of lives in every state (cancer x heart attack survivor x stroke
    survivor) year by year, in the same order as live(). Returns the chance of
    dying in each year, the expected age at death, the cause mix, the chance of
    a first cancer, heart attack and stroke, and the expected crash injuries.
    """
    # work state (0 working age, 1-24 disabled, 25 retired), cancer, heart attack survivor,
    # stroke survivor, marital
    p = np.zeros((26, N_CANCER, 2, 2, 3))
    p[25 if sch.person.age > 70 else 0, 0, 0, 0, MARITAL_STATES.index(sch.start_marital)] = 1.0
    n = len(sch.ages)
    die, cause = np.zeros(n), np.zeros(len(CAUSES))
    ever = {"cancer": 0.0, "heart_attack": 0.0, "stroke": 0.0, "disability": 0.0}
    crashes = 0.0
    lung_idx, other_idx = slice(1, 7), slice(7, 13)
    heart, stroke = CAUSES.index("heart"), CAUSES.index("stroke")
    for i in range(n):
        f = sch.fixed
        crashes += p.sum() * f["crash_injury"][i]
        working_at_start = p[0].sum()          # new disabilities are drawn before deaths, as in live()
        # cancer: first diagnoses, then everyone diagnosed moves one year on
        lung, other = f["cancer_lung"][i], f["cancer_other"][i]
        new_l, new_o = p[:, 0] * lung, p[:, 0] * (1 - lung) * other
        ever["cancer"] += new_l.sum() + new_o.sum()
        nxt = np.zeros_like(p)
        nxt[:, 0] = p[:, 0] - new_l - new_o
        for block, new in ((lung_idx, new_l), (other_idx, new_o)):
            old = p[:, block]
            nxt[:, block.start] = new
            nxt[:, block.start + 1:block.start + 5] = old[:, :4]
            nxt[:, block.start + 5] = old[:, 4] + old[:, 5]
        p = nxt
        # heart attack, then stroke: first events and acute deaths
        new_a = p[:, :, 0, :, :] * f["heart_attack"][i]
        acute_a = new_a * sch.acute_heart[i]
        ever["heart_attack"] += new_a.sum()
        p[:, :, 0, :, :] -= acute_a
        move_a = np.divide(new_a - acute_a, p[:, :, 0, :, :], out=np.zeros_like(new_a), where=p[:, :, 0, :, :] > 0)
        new_s = p[:, :, :, 0, :] * f["stroke"][i]
        acute_s = new_s * sch.acute_stroke[i]
        ever["stroke"] += new_s.sum()
        p[:, :, :, 0, :] -= acute_s
        move_s = np.divide(new_s - acute_s, p[:, :, :, 0, :], out=np.zeros_like(new_s), where=p[:, :, :, 0, :] > 0)
        cause[heart] += acute_a.sum()
        cause[stroke] += acute_s.sum()
        # regular deaths in the state held at the start of the year (disabled: work states 1-24)
        disabled = np.zeros(26, dtype=int)
        disabled[1:25] = 1
        q_now = sch.q_state[i][..., disabled]                    # cancer, a, s, marital, work
        q_now = np.moveaxis(q_now, -1, 0)                         # work, cancer, a, s, marital
        d = p * q_now
        cause += np.einsum("wkasm,kasc->c", d, sch.c_state[i])
        die[i] = acute_a.sum() + acute_s.sum() + d.sum()
        alive = p - d
        # survivors of this year's events move state: heart attack, stroke, marital status, work
        p = np.zeros_like(alive)
        for a in (0, 1):
            for s_ in (0, 1):
                pa = move_a[:, :, s_, :] if a == 0 else 0.0
                ps = move_s[:, :, a, :] if s_ == 0 else 0.0
                for da, wa in ((0, 1 - pa), (1, pa)):
                    for ds, ws in ((0, 1 - ps), (1, ps)):
                        p[:, :, min(a + da, 1), min(s_ + ds, 1), :] += alive[:, :, a, s_, :] * wa * ws
        marry, divorce, remarry = f["first_marriage"][i], f["divorce"][i], f["remarriage"][i]
        never, married, divorced = p[..., 0].copy(), p[..., 1].copy(), p[..., 2].copy()
        p[..., 0] = never * (1 - marry)
        p[..., 1] = married * (1 - divorce) + never * marry + divorced * remarry
        p[..., 2] = divorced * (1 - remarry) + married * divorce
        age, year = int(sch.ages[i]), int(sch.years[i])
        t = work_transition(sch.person.sex, age, year, f["disability_start"][i], f["retire"][i])
        ever["disability"] += working_at_start * t[0, 1:25].sum()
        p = np.tensordot(t.T, p, axes=1)
    return {"die": die, "mean_death_age": float(die @ (sch.ages + 0.5)), "cause": cause,
            "ever_cancer": ever["cancer"], "ever_heart_attack": ever["heart_attack"],
            "ever_stroke": ever["stroke"], "ever_disability": ever["disability"], "crashes": crashes}


def simulate(p: Person, n: int = 1000, seed: int = 0, start_year: int = START_YEAR,
             start: State | None = None, improve: bool = True) -> list[Life]:
    """n lives for this person, reproducible from the seed."""
    sch = build_schedule(p, start_year, improve, start_marital=start.marital if start else "never")
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
