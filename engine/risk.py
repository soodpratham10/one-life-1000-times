"""
Personal risk multipliers: turning survey answers into personal death rates.

How it works (A07, A08, A18 in docs/assumptions.md):

1. Each answer falls into a level, and each level has a hazard ratio from a
   published study (data/assumptions/hazard_ratios.csv), relative to a
   reference level (never smoked, no activity, BMI 18.5-25, under 25 g of
   alcohol a day, 2 servings of fruit and vegetables a day).
2. Base death rates are averages over everyone, so they already include the
   population's mix of smokers, inactive people and so on. Applying a hazard
   ratio directly would double-count. The population's average multiplier at
   each age, built from how common each level is (CCHS, A18; former smokers
   from Health Canada's CTNS), is divided out first:
        relative multiplier = person's multiplier / population average
3. The relative multiplier scales the force of mortality, as a hazard ratio
   does:  mu_person = mu_base * r,  so  q_person = 1 - (1 - q_base) ** r.
4. Taper: the studies cover ages up to about 80, and risk ratios narrow at very
   old ages, so each log hazard ratio is applied in full to age 79 and then
   shrinks in a straight line to zero at 110.
5. Cap: r is kept between CAP_LOW and CAP_HIGH, because multiplying ratios from
   separate studies overstates risk for people with many factors (A08).

Factors are treated as independent, so the population average is the product
of each factor's average. Answers are held for life (a smoker stays a smoker).
"""

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

from engine.data import ROOT, load
from engine.mortality import MAX_AGE, MIN_AGE, REGIONS, SEXES, cohort_qx

ASSUMPTIONS = ROOT / "data" / "assumptions"

CAP_LOW = 0.35        # A08: lowest relative multiplier
CAP_HIGH = 5.0        # A08: highest relative multiplier
TAPER_START = 79      # full effect up to this age (Jha et al. cover ages 25-79)
GRAMS_PER_DRINK = 13.45   # one Canadian standard drink, grams of alcohol

FACTORS = ("smoking", "activity", "bmi", "alcohol", "fruit_veg")
AGE_GROUPS = ((18, 34), (35, 49), (50, 64), (65, 110))   # CCHS adult groups

# How the yes/no groups the surveys publish split into the model's levels.
# These are judgements where no Canadian split is published (A18).
ACTIVITY_UNDER_150 = {"none": 0.5, "under_150": 0.5}
ACTIVITY_150_PLUS = {"150_299": 0.5, "300_449": 0.25, "450_plus": 0.25}
OVERWEIGHT_SPLIT = {"25_27.5": 0.5, "27.5_30": 0.5}
# Obesity classes I, II, III among obese adults: measured 2004 CCHS
# (15.2%, 5.1% and 2.7% of adults; Statistics Canada 82-620-MWE2005001)
OBESE_SPLIT = {"30_35": 15.2 / 23.0, "35_40": 5.1 / 23.0, "40_plus": 2.7 / 23.0}
# Former smokers by the age they quit (no Canadian split published): most quit young
FORMER_QUIT_SPLIT_UNDER_50 = {"quit_before_35": 0.75, "quit_35_44": 0.25}
FORMER_QUIT_SPLIT_50_PLUS = {"quit_before_35": 0.4, "quit_35_44": 0.3,
                             "quit_45_54": 0.2, "quit_55_plus": 0.1}


# ---------------------------------------------------------------- inputs

@dataclass(frozen=True)
class Person:
    """Survey answers. Units: minutes a week, cm, kg, drinks a week, servings a day."""
    sex: str
    age: int
    region: str = "CA"
    smoking: str = "never"            # never, former or current
    quit_age: int | None = None       # former smokers only
    activity_minutes: float = 0.0     # moderate-to-vigorous leisure activity
    height_cm: float = 170.0
    weight_kg: float = 70.0
    drinks_per_week: float = 0.0
    fruit_veg_per_day: float = 2.0

    def __post_init__(self):
        if self.sex not in SEXES:
            raise ValueError("sex must be 'M' or 'F'")
        if not MIN_AGE <= self.age < MAX_AGE:
            raise ValueError(f"age must be {MIN_AGE}-{MAX_AGE - 1}")
        if self.region not in REGIONS:
            raise ValueError(f"region must be one of {REGIONS}")
        if self.smoking not in ("never", "former", "current"):
            raise ValueError("smoking must be never, former or current")
        if self.smoking == "former":
            if self.quit_age is None or not 10 <= self.quit_age <= self.age:
                raise ValueError("former smokers need a quit age between 10 and their age")
        elif self.quit_age is not None:
            raise ValueError("quit age is only for former smokers")
        if not 0 <= self.activity_minutes <= 3000:
            raise ValueError("activity must be 0-3000 minutes a week")
        if not 120 <= self.height_cm <= 230 or not 30 <= self.weight_kg <= 300:
            raise ValueError("height must be 120-230 cm and weight 30-300 kg")
        if not 12 <= self.bmi <= 80:
            raise ValueError("height and weight give an implausible BMI")
        if not 0 <= self.drinks_per_week <= 150:
            raise ValueError("drinks must be 0-150 a week")
        if not 0 <= self.fruit_veg_per_day <= 20:
            raise ValueError("fruit and vegetables must be 0-20 servings a day")

    @property
    def bmi(self) -> float:
        return self.weight_kg / (self.height_cm / 100) ** 2

    @property
    def alcohol_g_per_day(self) -> float:
        return self.drinks_per_week * GRAMS_PER_DRINK / 7


def levels(p: Person) -> dict[str, str]:
    """The level of each factor for this person."""
    if p.smoking == "former":
        q = p.quit_age
        smoking = ("quit_before_35" if q < 35 else "quit_35_44" if q < 45
                   else "quit_45_54" if q < 55 else "quit_55_plus")
    else:
        smoking = p.smoking
    m = p.activity_minutes
    activity = ("none" if m == 0 else "under_150" if m < 150 else "150_299" if m < 300
                else "300_449" if m < 450 else "450_plus")
    b = p.bmi
    bmi = ("under_18.5" if b < 18.5 else "18.5_25" if b < 25 else "25_27.5" if b < 27.5
           else "27.5_30" if b < 30 else "30_35" if b < 35 else "35_40" if b < 40 else "40_plus")
    g = p.alcohol_g_per_day
    alcohol = "under_25g" if g < 25 else "25_44g" if g < 45 else "45_64g" if g < 65 else "65g_plus"
    f = p.fruit_veg_per_day
    fruit_veg = "0_2" if f < 3 else "3" if f < 4 else "4" if f < 5 else "5_plus"
    return {"smoking": smoking, "activity": activity, "bmi": bmi,
            "alcohol": alcohol, "fruit_veg": fruit_veg}


# ---------------------------------------------------------------- hazard ratios

@lru_cache(maxsize=None)
def _hr_table() -> dict[tuple[str, str, str], float]:
    t = pd.read_csv(ASSUMPTIONS / "hazard_ratios.csv")
    return {(r.factor, r.level, r.sex): float(r.hr) for r in t.itertuples()}


def hazard_ratio(factor: str, level: str, sex: str) -> float:
    """Hazard ratio for a level, sex-specific where the study gives one."""
    table = _hr_table()
    for key in ((factor, level, sex), (factor, level, "B")):
        if key in table:
            return table[key]
    raise KeyError(f"no hazard ratio for {factor} {level} {sex}")


def taper(age: int) -> float:
    """Share of each log hazard ratio applied at this age: 1 up to 79, falling to 0 at 110."""
    if age <= TAPER_START:
        return 1.0
    return max(0.0, (MAX_AGE - age) / (MAX_AGE - TAPER_START))


# ---------------------------------------------------------------- population mix

def age_group(age: int) -> tuple[int, int]:
    for lo, hi in AGE_GROUPS:
        if lo <= age <= hi:
            return lo, hi
    raise ValueError(f"no CCHS age group for age {age}")


@lru_cache(maxsize=None)
def population_mix(sex: str, group: tuple[int, int]) -> dict[str, dict[str, float]]:
    """Share of Canadians of this sex and age group at each level of each factor."""
    prev = load("risk_prevalence.csv")
    rows = prev[prev["base"] & (prev["region"] == "CA") & (prev["sex"] == sex)
                & (prev["age_lo"] == group[0]) & (prev["age_hi"] == group[1])]
    pct = dict(zip(rows["indicator"], rows["pct"] / 100))

    former_t = pd.read_csv(ASSUMPTIONS / "former_smokers.csv")
    former = float(former_t.loc[(former_t["sex"] == sex) & (former_t["age_lo"] == group[0]), "pct"].iloc[0]) / 100
    current = pct["current_smoker"]
    quit_split = FORMER_QUIT_SPLIT_UNDER_50 if group[1] < 50 else FORMER_QUIT_SPLIT_50_PLUS
    smoking = {"never": 1 - current - former, "current": current}
    for level, share in quit_split.items():
        smoking[level] = former * share

    active = pct["active_150"]
    activity = {k: (1 - active) * v for k, v in ACTIVITY_UNDER_150.items()}
    activity |= {k: active * v for k, v in ACTIVITY_150_PLUS.items()}

    over, obese = pct["overweight"], pct["obese"]
    bmi = {"18.5_25": 1 - over - obese}           # underweight (a few %) counted as normal
    bmi |= {k: over * v for k, v in OVERWEIGHT_SPLIT.items()}
    bmi |= {k: obese * v for k, v in OBESE_SPLIT.items()}

    five = pct["fruit_veg_5"]
    fruit_veg = {"0_2": 1 - five, "5_plus": five}  # below 5 counted at the 2-serving level

    alcohol = {"under_25g": 1.0}                   # no Canadian figures on volume: not normalised

    mix = {"smoking": smoking, "activity": activity, "bmi": bmi,
           "alcohol": alcohol, "fruit_veg": fruit_veg}
    for factor, shares in mix.items():
        if min(shares.values()) < 0 or abs(sum(shares.values()) - 1) > 1e-9:
            raise ValueError(f"population mix for {factor} {sex} {group} does not add to 1: {shares}")
    return mix


def average_multiplier(sex: str, age: int) -> float:
    """Population average of the combined multiplier at this age (product over factors)."""
    w = taper(age)
    total = 1.0
    for factor, shares in population_mix(sex, age_group(age)).items():
        total *= sum(share * hazard_ratio(factor, level, sex) ** w for level, share in shares.items())
    return total


def person_multiplier(p: Person, age: int) -> float:
    """This person's combined multiplier at a given age, before dividing out the average."""
    w = taper(age)
    return float(np.prod([hazard_ratio(f, lvl, p.sex) ** w for f, lvl in levels(p).items()]))


def relative_multiplier(p: Person, age: int) -> float:
    """Person / population average, capped (A08). Multiplies the force of mortality."""
    if age >= MAX_AGE:
        return 1.0
    r = person_multiplier(p, age) / average_multiplier(p.sex, age)
    return float(min(max(r, CAP_LOW), CAP_HIGH))


# ---------------------------------------------------------------- personal rates

def personal_qx(p: Person, year: int, improve: bool = True) -> np.ndarray:
    """
    This person's yearly death probabilities from their age now to 110:
    element k is the chance of dying at age (p.age + k) in year (year + k).
    """
    q = cohort_qx(p.region, p.sex, p.age, year, improve=improve)
    r = np.array([relative_multiplier(p, p.age + k) for k in range(len(q))])
    out = 1 - (1 - q) ** r
    out[-1] = 1.0                                 # everyone dies in the open age group
    return out
