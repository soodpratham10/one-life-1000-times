"""
Phase 4, check 1: does a population of simulated Canadians die like real Canadians?

Run from the project folder:
    python -m validation.population            # all checks (a few minutes)
    python -m validation.population --quick    # men aged 65 only, to try it

What it does
------------
Take everyone of one sex at one starting age (25, 45 or 65). Split them into
every combination of the survey levels (smoking x activity x BMI x fruit and
vegetables) and every starting marital status, weighted by how common each is
in Canada: the same population mix the engine divides out (A18, A19, A24).
For each combination, the engine's exact() gives the chance of dying at each
later age and of each cause. Weighting them together gives the population's
expected deaths with no simulation noise.

These are compared with the Statistics Canada 2017-2019 life table for Canada
and the 2017-2019 cause-of-death mix, the data the engine was built from. The
runs use no future improvement (improve=False), so both sides describe the
same period.

What should match, and what should not
--------------------------------------
The habit mix is divided out age by age, so a population whose mix matched
Canada's at every age would reproduce the life table closely. This check holds
each person's habits for life instead (as the engine does): the cohort keeps
its starting mix while real Canadians' mix changes with age (fewer smokers at
older ages, partly because smokers die first). Everyone also starts cancer-free,
with no heart attack or stroke and not disabled. So small differences are
expected, mostly at older ages; this script measures them, it does not hide
them. Results are written to validation/results/population_check.csv.
"""

import argparse
import itertools
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from engine.causes import CAUSES, base_shares
from engine.marriage import marital_mix
from engine.mortality import MAX_AGE, base_qx, life_expectancy
from engine.risk import Person, age_group, levels, population_mix
from engine.simulate import build_schedule, exact

OUT = Path(__file__).resolve().parent / "results"
START_AGES = (25, 45, 65)
HEIGHT_CM = 170.0

# A representative answer inside each level (only the level matters to the engine).
ACTIVITY = {"none": 0, "under_150": 75, "150_299": 200, "300_449": 375, "450_plus": 600}
BMI = {"18.5_25": 22.0, "25_27.5": 26.25, "27.5_30": 28.75, "30_35": 32.5, "35_40": 37.5, "40_plus": 42.5}
FRUIT_VEG = {"0_2": 2, "3": 3, "4": 4, "5_plus": 5}
DRINKS = {"under_25g": 3}
QUIT_AGE = {"quit_before_35": 30, "quit_35_44": 40, "quit_45_54": 50, "quit_55_plus": 60}
QUIT_ORDER = ("quit_before_35", "quit_35_44", "quit_45_54", "quit_55_plus")

# The model's three marital states; separated counts as divorced, and widowed (not yet
# modelled, version 2) also starts as divorced, the nearest state the model has.
MARITAL_START = {"single": "never", "married": "married", "separated": "divorced",
                 "widowed": "divorced", "divorced": "divorced"}

GROUPS = {   # cause groups for the report
    "cancer": ("lung_cancer", "other_cancer"),
    "heart_and_stroke": ("heart", "stroke"),
    "copd": ("copd",),
    "dementia": ("dementia",),
    "diabetes": ("diabetes",),
    "accidents_and_injury": ("motor_vehicle", "other_accidents", "other_injury"),
    "other": ("other",),
}


# ---------------------------------------------------------------- the population

def smoking_mix(sex: str, age: int) -> dict[str, float]:
    """Smoking levels at this age; quit bands that start after this age fold into the latest possible one."""
    raw = population_mix(sex, age_group(age))["smoking"]
    out = {"never": raw["never"], "current": raw["current"]}
    possible = [lvl for lvl in QUIT_ORDER if QUIT_AGE[lvl] <= age or lvl == "quit_before_35"]
    for lvl in QUIT_ORDER:
        if lvl in raw:
            target = lvl if lvl in possible else possible[-1]
            out[target] = out.get(target, 0.0) + raw[lvl]
    return out


def person_for(sex: str, age: int, smoking: str, activity: str, bmi: str, fruit_veg: str) -> Person:
    quit = None
    if smoking.startswith("quit"):
        quit = min(QUIT_AGE[smoking], age)
    return Person(sex=sex, age=age, region="CA",
                  smoking="former" if quit is not None else smoking, quit_age=quit,
                  activity_minutes=ACTIVITY[activity], height_cm=HEIGHT_CM,
                  weight_kg=BMI[bmi] * (HEIGHT_CM / 100) ** 2,
                  drinks_per_week=DRINKS["under_25g"], fruit_veg_per_day=FRUIT_VEG[fruit_veg])


def combinations(sex: str, age: int) -> list[tuple[Person, float]]:
    """Every habit combination at this age with its population weight (factors independent, as in the engine)."""
    mix = population_mix(sex, age_group(age))
    factors = [smoking_mix(sex, age), mix["activity"], mix["bmi"], mix["fruit_veg"]]
    out = []
    for combo in itertools.product(*(f.items() for f in factors)):
        names = [k for k, _ in combo]
        weight = float(np.prod([w for _, w in combo]))
        if weight > 0:
            out.append((person_for(sex, age, *names), weight))
    return out


def marital_start(sex: str, age: int) -> dict[str, float]:
    out = {"never": 0.0, "married": 0.0, "divorced": 0.0}
    for status, share in marital_mix(sex, age).items():
        out[MARITAL_START[status]] += share
    return out


# ---------------------------------------------------------------- the model's expectation

def _one(args):
    """Expected deaths for one habit combination, averaged over starting marital status."""
    person, marital = args
    sch = build_schedule(person, improve=False)
    die = np.zeros(len(sch.ages))
    cause = np.zeros(len(CAUSES))
    ever = np.zeros(3)
    for state, share in marital.items():
        if share > 0:
            e = exact(replace(sch, start_marital=state))
            die += share * e["die"]
            cause += share * e["cause"]
            ever += share * np.array([e["ever_cancer"], e["ever_heart_attack"], e["ever_stroke"]])
    return die, cause, ever


def model_population(sex: str, age: int, workers: int | None = None) -> dict:
    combos = combinations(sex, age)
    marital = marital_start(sex, age)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_one, [(p, marital) for p, _ in combos], chunksize=4))
    w = np.array([wt for _, wt in combos])
    die = sum(wi * r[0] for wi, r in zip(w, results))
    cause = sum(wi * r[1] for wi, r in zip(w, results))
    ever = sum(wi * r[2] for wi, r in zip(w, results))
    return {"die": die, "cause": cause, "ever": ever, "combinations": len(combos)}


# ---------------------------------------------------------------- the official figures

def official(sex: str, age: int) -> dict:
    """Statistics Canada 2017-2019, Canada: deaths at each age from `age` and their cause mix."""
    q = base_qx("CA", sex)[age:]
    alive = np.concatenate([[1.0], np.cumprod(1 - q)[:-1]])
    die = alive * q
    cause = sum(d * base_shares(sex, a) for d, a in zip(die, range(age, MAX_AGE + 1)))
    return {"die": die, "cause": cause, "e": life_expectancy(q)}


# ---------------------------------------------------------------- comparison

def compare(sex: str, age: int, workers: int | None = None) -> pd.DataFrame:
    m = model_population(sex, age, workers)
    o = official(sex, age)
    k = np.arange(len(o["die"]))
    rows = [("life_expectancy", "years", float(m["die"] @ (k + 0.5)), o["e"])]
    for lo in range(age, 105, 10):
        band = (k + age >= lo) & (k + age < lo + 10)
        rows.append((f"deaths_{lo}_{lo + 9}", "share of cohort", float(m["die"][band].sum()),
                     float(o["die"][band].sum())))
    rows.append((f"deaths_{lo + 10}_plus", "share of cohort", float(m["die"][k + age >= lo + 10].sum()),
                 float(o["die"][k + age >= lo + 10].sum())))
    for name, causes in GROUPS.items():
        idx = [CAUSES.index(c) for c in causes]
        rows.append((f"cause_{name}", "share of deaths", float(m["cause"][idx].sum() / m["cause"].sum()),
                     float(o["cause"][idx].sum() / o["cause"].sum())))
    for name, v in zip(("cancer", "heart_attack", "stroke"), m["ever"]):
        rows.append((f"ever_{name}", "chance, no benchmark yet", float(v), np.nan))
    df = pd.DataFrame(rows, columns=["measure", "unit", "model", "official"])
    df.insert(0, "start_age", age)
    df.insert(0, "sex", sex)
    df["model_over_official"] = df["model"] / df["official"]
    df["combinations"] = m["combinations"]
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="men aged 65 only")
    ap.add_argument("--workers", type=int, default=None, help="processes to use (default: all cores)")
    args = ap.parse_args()
    cases = [("M", 65)] if args.quick else [(s, a) for s in ("M", "F") for a in START_AGES]
    frames = []
    for sex, age in cases:
        df = compare(sex, age, args.workers)
        frames.append(df)
        e = df.iloc[0]
        print(f"\n{sex} from age {age} ({int(e['combinations'])} habit combinations): "
              f"life expectancy {e['model']:.2f} vs StatCan {e['official']:.2f} "
              f"(difference {e['model'] - e['official']:+.2f} years)")
        for r in df.iloc[1:].itertuples():
            if np.isnan(r.official):
                print(f"  {r.measure:<26} {r.model:7.3f}")
            else:
                print(f"  {r.measure:<26} {r.model:7.3f} vs {r.official:7.3f}   A/E {r.model_over_official:5.2f}")
    if not args.quick:
        OUT.mkdir(exist_ok=True)
        pd.concat(frames).to_csv(OUT / "population_check.csv", index=False)
        print(f"\nWrote {OUT / 'population_check.csv'}")


if __name__ == "__main__":
    main()
