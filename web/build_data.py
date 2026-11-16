"""
Phase 5, step 1: export everything the browser engine needs into one file.

Run from the project folder:
    python web/build_data.py

Writes web/data/engine-data.json. Two kinds of content:

  * inputs, copied from the data and assumption tables: base death rates by
    region and sex (2017-2019), CPP improvement rates (A28), hazard ratios,
    smoking ratios by cause, event rates (crashes, cancer, heart attack, stroke,
    disability, retirement, family events);
  * population tables the engine solves once for everyone, so the browser does
    not repeat the work: the habit mix by age group (A18, A19), the cause mix
    and its smoking calibration (A20), the cancer link (A22), the heart attack
    and stroke link (A23), the marriage ratios (A24), the disability multipliers
    and recovery chances (A25), and the fitted 2019-2025 CPP scales.

Everything personal (survey answers -> death rates -> life events -> 1,000
lives) is worked out again in the browser by web/engine/, and checked against
the same reference files as the R and Excel VBA rebuilds. Every value comes
from the Python engine's own functions, so the file cannot drift from it; a
test (tests/test_web_data.py) fails if the file is out of date. No CIA data is
used, so the file can be published.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import causes as C  # noqa: E402
from engine import disability as D  # noqa: E402
from engine import events as E  # noqa: E402
from engine import links as L  # noqa: E402
from engine import marriage as M  # noqa: E402
from engine import mortality as MO  # noqa: E402
from engine import risk as R  # noqa: E402
from engine import simulate as S  # noqa: E402

OUT = ROOT / "web" / "data" / "engine-data.json"
AGES = range(MO.MAX_AGE + 1)                  # arrays are indexed by age 0..110
ADULT = range(MO.MIN_AGE, MO.MAX_AGE + 1)
DIS_AGES = range(MO.MIN_AGE, E.DISABILITY_MAX_AGE + 1)
RECOVERY_YEARS = range(2025, 2036)             # termination rates are interpolated 2025-2035, flat outside
ELIGIBLE_YEARS = range(2025, 2141)             # eligibility published to 2100, flat after


def by_age(f, ages=AGES, fill=0.0):
    """List over ages 0..110 of f(age) for ages in `ages`, `fill` elsewhere."""
    keep = set(ages)
    return [float(f(a)) if a in keep else fill for a in AGES]


def _incidence(sex: str, age: int) -> float:
    """New CPP disabilities per eligible person a year (the table E.disability_start_probability reads)."""
    t = E.load("cpp_disability_incidence.csv")
    return float(t.loc[(t["sex"] == sex) & (t["age"] == age), "per_1000"].iloc[0]) / 1000


def sex_block(sex: str) -> dict:
    cancer = L.calibration(sex)
    cardio = L.cardio_calibration(sex)
    return {
        "base_q": {region: [float(x) for x in MO.base_qx(region, sex)] for region in MO.REGIONS},
        "cpp_rates": [[float(x) for x in row] for row in MO.cpp_rates(sex)],
        "cpp_scale": [float(x) for x in MO.cpp_scale(sex)],
        "mix": {str(lo): R.population_mix(sex, (lo, hi)) for lo, hi in R.AGE_GROUPS},
        "cause_shares": [[float(x) for x in C.base_shares(sex, a)] if a >= MO.MIN_AGE else [0.0] * len(C.CAUSES)
                         for a in AGES],
        "cause_calibration": [[float(x) for x in C._calibration(sex, a)] if a >= MO.MIN_AGE
                              else [1.0] * len(C.CAUSES) for a in AGES],
        "smoking_cause_ratio_current": {c: C.smoking_cause_ratio(c, "current", sex) for c in C.CAUSES},
        "crash": by_age(lambda a: E.crash_probability(sex, a), ADULT),
        "cancer_pop": [list(E.cancer_probabilities(sex, a)) if a >= MO.MIN_AGE else [0.0, 0.0] for a in AGES],
        "cardio_pop": [list(E.heart_stroke_probabilities(sex, a)) if a >= MO.MIN_AGE else [0.0, 0.0] for a in AGES],
        "disability_incidence": by_age(lambda a: _incidence(sex, a), DIS_AGES),
        "eligible_share": {str(y): E.eligible_share(sex, y) for y in ELIGIBLE_YEARS},
        "retire": by_age(lambda a: E.retire_probability(sex, a), ADULT),
        "family": {ev: by_age(lambda a, ev=ev: E.family_probability(ev, sex, a), ADULT)
                   for ev in ("first_marriage", "divorce", "remarriage")},
        "first_child": by_age(lambda a: E.first_child_probability(sex, a), ADULT),
        "cancer_link": {k: [float(x) for x in cancer[k]] for k in ("s_lung", "s_other", "r_lung", "r_other", "eta")},
        "cardio_link": {k: [float(x) for x in cardio[k]] for k in ("b_heart", "b_stroke", "rr_heart", "rr_stroke", "eta")},
        "acute": {ev: [float(x) for x in L.acute_fatality(sex, ev)] for ev in ("heart", "stroke")},
        "marital_ratio": {st: by_age(lambda a, st=st: M.marital_ratio(st, sex, a), ADULT, 1.0)
                          for st in L.MARITAL_STATES},
        "death_multipliers": [list(D.death_multipliers(sex, a)) if a >= MO.MIN_AGE else [1.0, 1.0] for a in AGES],
        # recovery[band][completed years 1..6][year 2025..2035][age 18..64]
        "recovery": [[[[D.recovery_probability(sex, b, y, yr, a) for a in DIS_AGES]
                       for yr in RECOVERY_YEARS] for y in range(1, 7)] for b in D.BANDS],
    }


def build() -> dict:
    hr = {}
    for (factor, level, sex), value in R._hr_table().items():
        hr.setdefault(factor, {}).setdefault(level, {})[sex] = value
    return {
        "about": "One Life, 1,000 Times: data for the browser engine, built by web/build_data.py "
                 "from the Python engine. Sources and assumptions: docs/assumptions.md.",
        "constants": {
            "MIN_AGE": MO.MIN_AGE, "MAX_AGE": MO.MAX_AGE, "BASE_YEAR": MO.base_year(MO.BASE_PERIOD),
            "START_YEAR": S.START_YEAR, "CPP_SPLIT_AGE": MO.CPP_SPLIT_AGE,
            "CAP_LOW": R.CAP_LOW, "CAP_HIGH": R.CAP_HIGH, "TAPER_START": R.TAPER_START,
            "GRAMS_PER_DRINK": R.GRAMS_PER_DRINK, "QUIT_RATE": R.QUIT_RATE, "QUIT_FROM_AGE": R.QUIT_FROM_AGE,
            "AGE_GROUPS": [list(g) for g in R.AGE_GROUPS], "FACTORS": list(R.FACTORS),
            "DRIFTING": {k: list(v) for k, v in R.DRIFTING.items()},
            "CAUSES": list(C.CAUSES), "CAUSE_LABELS": C.CAUSE_LABELS,
            "W": [float(x) for x in L.W], "N_CANCER": L.N_CANCER, "MARITAL_STATES": list(L.MARITAL_STATES),
            "DISABILITY_MAX_AGE": E.DISABILITY_MAX_AGE, "RETIREMENT_AGES": list(E.RETIREMENT_AGES),
            "BANDS": list(D.BANDS), "RECOVERY_YEARS": [RECOVERY_YEARS[0], RECOVERY_YEARS[-1]],
            "ELIGIBLE_YEARS": [ELIGIBLE_YEARS[0], ELIGIBLE_YEARS[-1]],
            "REGIONS": list(MO.REGIONS),
        },
        "hazard_ratios": hr,
        "M": sex_block("M"),
        "F": sex_block("F"),
    }


def main() -> None:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")))
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
