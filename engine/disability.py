"""
Disability and mortality (A25): people receiving a CPP disability pension die
at several times the population rate, and the CPP termination rates (A15)
count both recoveries and deaths.

    * while disabled (to 64), a person's death rate is their own rate x the
      disabled-to-population ratio for their sex and age (Office of the Chief
      Actuary, Actuarial Study No. 16, Table 40, 2011; ages under 20 use 20);
    * recovery = CPP termination rate - the death rate of a disabled person of
      that age (the same ratio on the 2017-2019 base table), never below 0;
    * everyone not disabled has their death rate scaled by gamma(age) <= 1 for
      ages 18-64, solved on a synthetic cohort (CPP incidence, recovery and
      retirement as in the engine, 2025 rates) so the population as a whole
      still has the official death rates. The cohort's disabled share is
      checked against the number of CPP disability beneficiaries (tested).

After 64 a disability pension becomes a retirement pension (A21) and the
extra mortality stops: the study covers ages 20-64 only.
"""

from functools import lru_cache

import numpy as np
import pandas as pd

from engine.data import load
from engine.events import (
    DISABILITY_MAX_AGE,
    disability_end_probability,
    disability_start_probability,
    onset_band,
    retire_probability,
)
from engine.mortality import MIN_AGE, base_qx
from engine.risk import ASSUMPTIONS

COHORT_YEAR = 2025          # incidence, eligibility and termination as published for 2025
BANDS = (30, 40, 50, 60)    # published onset ages of the termination table


@lru_cache(maxsize=None)
def _table() -> pd.DataFrame:
    return pd.read_csv(ASSUMPTIONS / "disabled_mortality.csv")


@lru_cache(maxsize=None)
def mortality_ratio(sex: str, age: int) -> float:
    """Disabled-to-population death rate ratio (1 after 64)."""
    if age > DISABILITY_MAX_AGE:
        return 1.0
    t = _table()
    return float(t.loc[(t["sex"] == sex) & (t["age"] == max(age, 20)), "ratio"].iloc[0])


@lru_cache(maxsize=None)
def disabled_q(sex: str, age: int) -> float:
    """Yearly death probability of a disabled person on the 2017-2019 base table."""
    q = base_qx("CA", sex)[age]
    return float(1 - (1 - q) ** mortality_ratio(sex, age))


@lru_cache(maxsize=None)
def recovery_probability(sex: str, onset_age: int, completed_years: int, year: int, age: int) -> float:
    """Chance a spell ends in recovery this year: termination minus deaths, never below 0."""
    return max(disability_end_probability(sex, onset_age, completed_years, year) - disabled_q(sex, age), 0.0)


def _work_states() -> int:
    """0 not disabled and not retired; 1..24 disabled (band, completed years 1..6); 25 retired."""
    return 26


def state_index(band: int, years: int) -> int:
    return 1 + BANDS.index(band) * 6 + (min(max(years, 1), 6) - 1)


@lru_cache(maxsize=None)
def _recovery_block(sex: str, age: int, year: int) -> np.ndarray:
    """Transition rows for the 24 disabled states (independent of the person)."""
    n = _work_states()
    t = np.zeros((24, n))
    for b in BANDS:
        for y in range(1, 7):
            k = state_index(b, y)
            if age > DISABILITY_MAX_AGE:
                t[k - 1, 25] = 1.0
                continue
            rec = recovery_probability(sex, b, y, year, age)
            t[k - 1, 0] = rec
            t[k - 1, state_index(b, y + 1)] += 1 - rec
    return t


def work_transition(sex: str, age: int, year: int, p_start: float, p_retire: float) -> np.ndarray:
    """
    Matrix T[from, to] of moves between work states over one year, for people who
    survive it, in the engine's order: a new disability or retirement from state 0
    (retirement wins a tie), recovery or one more year for the disabled, and at 65
    a disability pension becomes a retirement pension.
    """
    n = _work_states()
    t = np.zeros((n, n))
    new = state_index(onset_band(age), 1)
    t[0, 25] = p_retire
    t[0, new] = p_start * (1 - p_retire)
    t[0, 0] = 1 - t[0, 25] - t[0, new]
    t[1:25] = _recovery_block(sex, age, min(max(year, 2025), 2035))
    t[25, 25] = 1.0
    return t


@lru_cache(maxsize=None)
def calibration(sex: str) -> dict[str, np.ndarray]:
    """
    By age (index = age): gamma, the scale on the death rate of people who are not
    disabled, and share_disabled, the cohort's disabled share at the start of the year.
    """
    q = base_qx("CA", sex)
    gamma = np.ones(len(q))
    share = np.zeros(len(q))
    p = np.zeros(_work_states())
    p[0] = 1.0
    for age in range(MIN_AGE, DISABILITY_MAX_AGE + 1):
        mass = p.sum()
        disabled = p[1:25].sum()
        share[age] = disabled / mass
        q_d = disabled_q(sex, age)
        target = mass * q[age]
        lo, hi = 0.0, 1.0
        for _ in range(100):
            g = (lo + hi) / 2
            deaths = (mass - disabled) * (1 - (1 - q[age]) ** g) + disabled * q_d
            lo, hi = (g, hi) if deaths < target else (lo, g)
        gamma[age] = (lo + hi) / 2
        q_state = np.full(len(p), 1 - (1 - q[age]) ** gamma[age])
        q_state[1:25] = q_d
        survivors = p * (1 - q_state)
        t = work_transition(sex, age, COHORT_YEAR, disability_start_probability(sex, age, COHORT_YEAR),
                            retire_probability(sex, age))
        p = survivors @ t
    return {"gamma": gamma, "share_disabled": share}


def death_multipliers(sex: str, age: int) -> tuple[float, float]:
    """(not disabled, disabled) multipliers on a person's force of mortality at this age."""
    if age > DISABILITY_MAX_AGE:
        return 1.0, 1.0
    return float(calibration(sex)["gamma"][age]), mortality_ratio(sex, age)
