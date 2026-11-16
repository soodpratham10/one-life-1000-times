"""
Write the Python engine's answers for a fixed set of people, for the R and
Excel VBA cross-checks to reproduce independently.

Run from the project folder:
    python crosscheck/make_reference.py

Writes crosscheck/reference/risk_reference.csv in long format:
    case, sex, age, region, smoking, quit_age, keeps_smoking, activity_minutes,
    height_cm, weight_kg, drinks_per_week, fruit_veg_per_day, measure, at_age, value

Measures:
    average_multiplier   population average multiplier at at_age (case "population_M"/"_F")
    relative_multiplier  the person's capped relative multiplier at at_age
    personal_q           the person's death probability at at_age (2017-2019 rates, no improvement)
    life_expectancy      complete life expectancy from the person's age (no improvement)

Everything above uses the 2017-2019 base table with no future improvement, so
it runs without the CIA file.

Also writes:
    crosscheck/reference/cancer_reference.csv
        the cancer link calibration (A22) by sex and age: s_lung, s_other,
        r_lung, r_other, eta, and 5-year survival after a diagnosis
    crosscheck/reference/cia_reference.csv   (only if the CIA file is on this computer)
        improvement factors by sex, age and year, and each person's death rates and
        life expectancy with improvement. Derived from the CIA's scale, so it is
        not committed (.gitignore), like the scale itself.
"""

import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.data import has_improvement_scale  # noqa: E402
from engine.links import calibration, five_year_survival  # noqa: E402
from engine.mortality import MAX_AGE, MIN_AGE, improvement_factor, life_expectancy  # noqa: E402
from engine.risk import Person, average_multiplier, personal_qx, relative_multiplier  # noqa: E402

OUT = ROOT / "crosscheck" / "reference" / "risk_reference.csv"
CANCER_OUT = ROOT / "crosscheck" / "reference" / "cancer_reference.csv"
CIA_OUT = ROOT / "crosscheck" / "reference" / "cia_reference.csv"
START_YEAR = 2026
IMPROVEMENT_YEARS = (2018, 2019, 2026, 2040, 2075, 2119, 2120, 2150)

# Chosen to reach every level of every factor, both sexes, every CCHS age group,
# quitting and keep-smoking smokers, the cap, and the PEI table.
CASES = {
    "never_typical_M25": Person("M", 25, "MB", activity_minutes=200, height_cm=178, weight_kg=80,
                                drinks_per_week=3, fruit_veg_per_day=3),
    "smoker_may_quit_M25": Person("M", 25, "MB", smoking="current", activity_minutes=60, height_cm=178,
                                  weight_kg=88, drinks_per_week=10, fruit_veg_per_day=2),
    "smoker_keeps_F33": Person("F", 33, "ON", smoking="current", keeps_smoking=True, activity_minutes=0,
                               height_cm=163, weight_kg=95, drinks_per_week=20, fruit_veg_per_day=1),
    "smoker_may_quit_F18": Person("F", 18, "QC", smoking="current", activity_minutes=500, height_cm=165,
                                  weight_kg=52, fruit_veg_per_day=6),
    "former_before35_M47": Person("M", 47, "BC", smoking="former", quit_age=30, activity_minutes=320,
                                  height_cm=180, weight_kg=97, drinks_per_week=25, fruit_veg_per_day=4),
    "former_35_44_F62": Person("F", 62, "NS", smoking="former", quit_age=40, activity_minutes=150,
                               height_cm=160, weight_kg=72, drinks_per_week=7, fruit_veg_per_day=5),
    "former_45_54_M70": Person("M", 70, "AB", smoking="former", quit_age=50, activity_minutes=460,
                               height_cm=175, weight_kg=110, drinks_per_week=40, fruit_veg_per_day=3),
    "former_55_plus_F85": Person("F", 85, "SK", smoking="former", quit_age=60, activity_minutes=30,
                                 height_cm=158, weight_kg=40, drinks_per_week=0, fruit_veg_per_day=2),
    "capped_M40": Person("M", 40, "CA", smoking="current", keeps_smoking=True, height_cm=170, weight_kg=130,
                         drinks_per_week=50, fruit_veg_per_day=0),
    "healthy_F50_PEI": Person("F", 50, "PE", activity_minutes=600, height_cm=170, weight_kg=63,
                              fruit_veg_per_day=7),
    "smoker_may_quit_M60": Person("M", 60, "NL", smoking="current", activity_minutes=100, height_cm=172,
                                  weight_kg=100, drinks_per_week=15, fruit_veg_per_day=2),
    "never_F100": Person("F", 100, "CA"),
}


def main() -> None:
    rows = []
    for sex in ("M", "F"):
        for a in range(MIN_AGE, MAX_AGE + 1):
            rows.append({"case": f"population_{sex}", "sex": sex, "measure": "average_multiplier",
                         "at_age": a, "value": average_multiplier(sex, a)})
    for name, p in CASES.items():
        answers = asdict(p)
        q = personal_qx(p, 2026, improve=False)
        for k, a in enumerate(range(p.age, MAX_AGE + 1)):
            rows.append({"case": name, **answers, "measure": "relative_multiplier", "at_age": a,
                         "value": relative_multiplier(p, a)})
            rows.append({"case": name, **answers, "measure": "personal_q", "at_age": a, "value": q[k]})
        rows.append({"case": name, **answers, "measure": "life_expectancy", "at_age": p.age,
                     "value": life_expectancy(q)})
    df = pd.DataFrame(rows)
    cols = ["case", "sex", "age", "region", "smoking", "quit_age", "keeps_smoking", "activity_minutes",
            "height_cm", "weight_kg", "drinks_per_week", "fruit_veg_per_day", "measure", "at_age", "value"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df[cols].to_csv(OUT, index=False, float_format="%.15g")
    print(f"Wrote {len(df):,} values for {len(CASES)} people to {OUT.relative_to(ROOT)}")
    for name in CASES:
        e = df[(df["case"] == name) & (df["measure"] == "life_expectancy")]["value"].iloc[0]
        print(f"  {name:<22} life expectancy {e:6.2f}")
    cancer_reference()
    if has_improvement_scale():
        cia_reference()
    else:
        print("CIA MI-2024 file not found: cia_reference.csv not written (the R check skips that part)")


def cancer_reference() -> None:
    rows = []
    for sex in ("M", "F"):
        cal = calibration(sex)
        for a in range(MIN_AGE, MAX_AGE):
            for key in ("s_lung", "s_other", "r_lung", "r_other", "eta"):
                rows.append({"sex": sex, "measure": key, "at_age": a, "value": float(cal[key][a])})
        for a in range(MIN_AGE, MAX_AGE - 4):
            for site in ("lung", "other"):
                rows.append({"sex": sex, "measure": f"five_year_survival_{site}", "at_age": a,
                             "value": five_year_survival(sex, site, a)})
    pd.DataFrame(rows).to_csv(CANCER_OUT, index=False, float_format="%.15g")
    print(f"Wrote {len(rows):,} cancer link values to {CANCER_OUT.relative_to(ROOT)}")


def cia_reference() -> None:
    rows = []
    for sex in ("M", "F"):
        for a in range(MIN_AGE, MAX_AGE + 1):
            for y in IMPROVEMENT_YEARS:
                rows.append({"case": f"improvement_{sex}", "sex": sex, "measure": "improvement_factor",
                             "at_age": a, "year": y, "value": improvement_factor(sex, a, y)})
    for name, p in CASES.items():
        q = personal_qx(p, START_YEAR, improve=True)
        for k, a in enumerate(range(p.age, MAX_AGE + 1)):
            rows.append({"case": name, "sex": p.sex, "measure": "personal_q_improved", "at_age": a,
                         "year": START_YEAR + k, "value": q[k]})
        rows.append({"case": name, "sex": p.sex, "measure": "life_expectancy_improved", "at_age": p.age,
                     "year": START_YEAR, "value": life_expectancy(q)})
    pd.DataFrame(rows).to_csv(CIA_OUT, index=False, float_format="%.15g")
    print(f"Wrote {len(rows):,} improvement values to {CIA_OUT.relative_to(ROOT)} (not committed)")


if __name__ == "__main__":
    main()
