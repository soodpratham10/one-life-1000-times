"""
Cause of death: when a simulated person dies, what they die of (A06, A20).

Base cause mix: Statistics Canada deaths by cause, sex and 5-year age group,
2017-2019 combined (the same years as the base life table, A09), 11 groups
(COVID-19 had no deaths in those years).

Personalised for smoking only: a smoker's death is far more likely to be lung
cancer or COPD than a never smoker's. Each cause has its own smoking ratio
(data/assumptions/smoking_cause_ratios.csv, from Thun et al. 2013); former
smokers keep the same share of each cause's excess as they keep of the
all-cause excess (A07), and the same taper as A08 applies.

The total chance of dying still comes from engine/risk.py (A07, A08): this
module only splits a death between causes. The split is calibrated so that,
across the population's smoking mix, deaths by cause reproduce the official
2017-2019 cause shares exactly at every age (tested).
"""

from functools import lru_cache

import numpy as np
import pandas as pd

from engine.data import load
from engine.risk import ASSUMPTIONS, Person, age_group, hazard_ratio, levels, population_mix, taper

BASE_YEARS = (2017, 2018, 2019)
CAUSES = ("lung_cancer", "other_cancer", "heart", "stroke", "copd", "diabetes", "dementia",
          "motor_vehicle", "other_accidents", "other_injury", "other")
CAUSE_LABELS = {
    "lung_cancer": "lung cancer", "other_cancer": "cancer (other than lung)", "heart": "heart disease",
    "stroke": "stroke", "copd": "chronic lung disease (COPD)", "diabetes": "diabetes",
    "dementia": "dementia", "motor_vehicle": "a motor vehicle crash", "other_accidents": "an accident",
    "other_injury": "another injury", "other": "other causes",
}


@lru_cache(maxsize=None)
def base_shares(sex: str, age: int) -> np.ndarray:
    """Share of deaths from each cause (order of CAUSES) at this age, 2017-2019."""
    deaths = load("causes_of_death.csv")
    rows = deaths[deaths["year"].isin(BASE_YEARS) & (deaths["sex"] == sex)
                  & (deaths["age_lo"] <= age) & (deaths["age_hi"] >= age)]
    by_cause = rows.groupby("cause")["deaths"].sum()
    if by_cause.get("covid", 0) != 0:
        raise ValueError("COVID-19 deaths found in the base years")
    counts = np.array([by_cause.get(c, 0.0) for c in CAUSES], dtype=float)
    if counts.sum() <= 0:
        raise ValueError(f"no deaths for {sex} age {age}")
    return counts / counts.sum()


@lru_cache(maxsize=None)
def _cause_ratio_table() -> dict[tuple[str, str], float]:
    t = pd.read_csv(ASSUMPTIONS / "smoking_cause_ratios.csv")
    return {(r.cause, r.sex): float(r.hr_current) for r in t.itertuples()}


def smoking_cause_ratio(cause: str, level: str, sex: str) -> float:
    """Ratio for one cause and smoking level, before the taper."""
    table = _cause_ratio_table()
    current = table.get((cause, sex), table[("other", "B")])
    if level == "never":
        return 1.0
    kept = (hazard_ratio("smoking", level, sex) - 1) / (hazard_ratio("smoking", "current", sex) - 1)
    return 1 + kept * (current - 1)


def _ratios(level: str, sex: str, age: int) -> np.ndarray:
    w = taper(age)
    return np.array([smoking_cause_ratio(c, level, sex) ** w for c in CAUSES])


@lru_cache(maxsize=None)
def _calibration(sex: str, age: int) -> np.ndarray:
    """
    Per-cause scale factors a, found by iteration, so that across the smoking mix,
    weighted by each group's all-cause hazard, the cause split reproduces base_shares.
    """
    shares = base_shares(sex, age)
    mix = population_mix(sex, age_group(age))["smoking"]
    w = taper(age)
    groups = [(p, hazard_ratio("smoking", lvl, sex) ** w, _ratios(lvl, sex, age)) for lvl, p in mix.items()]
    total = sum(p * h for p, h, _ in groups)
    a = np.ones(len(CAUSES))
    for _ in range(500):
        expected = np.zeros(len(CAUSES))
        for p, h, k in groups:
            split = shares * k / a
            expected += p * h * split / split.sum()
        expected /= total
        nonzero = shares > 0
        if np.allclose(expected[nonzero], shares[nonzero], rtol=1e-12, atol=0):
            return a
        a[nonzero] *= expected[nonzero] / shares[nonzero]
    raise RuntimeError(f"cause calibration did not converge for {sex} {age}")


def cause_probabilities(p: Person, age: int) -> np.ndarray:
    """Given that this person dies at this age, the chance of each cause (order of CAUSES)."""
    shares = base_shares(p.sex, age)
    split = shares * _ratios(levels(p)["smoking"], p.sex, age) / _calibration(p.sex, age)
    return split / split.sum()
