"""
Mortality basis: base death rates projected forward with mortality improvement.

    base table   Statistics Canada complete life table, by province and sex (A04);
                 PEI from the derived single-age table (A10). Default period
                 2017-2019, the last before COVID-19 (A09). A three-year table
                 describes its middle year, so 2017-2019 is treated as the rates
                 for calendar year 2018.
    improvement  q(x, t) = q(x, t-1) * (1 - MI(x, t)), from one of two scales:
                 "cpp" (the default, A28): the Chief Actuary's assumed rates from
                   the 32nd CPP actuarial report (Table 41), public, by age band;
                   2019-2025 scaled so the report's own 2025 life expectancies
                   are reproduced (the report replaced those years with actual
                   deaths, which it does not publish by age);
                 "cia" (A05): CIA MI-2024, on a computer with the CIA file.
                   Ages 18-19 use the age-20 rate; years after 2119 keep the
                   2119 rate.
                 Age 110 is never improved (q = 1 there, A02).

A person aged x in calendar year t is aged x + k in year t + k, so their own
rates run along the diagonal of the (age, year) grid: cohort_qx() returns them.
"""

from functools import lru_cache

import numpy as np

import pandas as pd

from engine.data import MI_FILE, ROOT, load

BASE_PERIOD = 2017            # default base table: 2017-2019 (A09)
MAX_AGE = 110                 # open age group, q = 1 (A02)
MIN_AGE = 18                  # youngest person simulated (A01)
MI_MIN_AGE = 20               # youngest age in MI-2024
DEFAULT_BASIS = "cpp"         # improvement scale used unless another is asked for (A28)
BASES = ("cpp", "cia")
CPP_FILE = ROOT / "data" / "assumptions" / "cpp32_improvement.csv"
CPP_LE_FILE = ROOT / "data" / "assumptions" / "cpp32_life_expectancy.csv"
CPP_FIT_YEAR = 2025           # the report's life expectancies the 2019-2025 scale is fitted to
CPP_SPLIT_AGE = 65            # one scale below this age, one at and above it

REGIONS = ("CA", "NL", "PE", "NS", "NB", "QC", "ON", "MB", "SK", "AB", "BC")
SEXES = ("M", "F")


def _check(region: str, sex: str) -> None:
    if region not in REGIONS:
        raise ValueError(f"region must be one of {REGIONS}, got {region!r}")
    if sex not in SEXES:
        raise ValueError(f"sex must be 'M' or 'F', got {sex!r}")


def base_year(period: int) -> int:
    """The calendar year a three-year table describes: its middle year."""
    return period + 1


def base_qx(region: str, sex: str, period: int = BASE_PERIOD) -> np.ndarray:
    """qx at ages 0..110 from the life table starting in `period` (index = age)."""
    _check(region, sex)
    table = load("life_tables_pei.csv") if region == "PE" else load("life_tables.csv")
    rows = table[
        (table["period_start"] == period)
        & (table["region"] == region)
        & (table["sex"] == sex)
    ].sort_values("age")
    q = rows["qx"].to_numpy(dtype=float)
    if len(q) != MAX_AGE + 1 or q[MAX_AGE] != 1.0:
        raise ValueError(f"no complete life table for {region} {sex} starting {period}")
    return q


@lru_cache(maxsize=None)
def _mi_grid(sex: str, first_year: int) -> np.ndarray:
    """MI-2024 as mi[age, year - first_year] for ages 0..110 and years first_year..2119."""
    mi = load(MI_FILE)
    mi = mi[(mi["sex"] == sex) & (mi["year"] >= first_year) & (mi["age"] <= MAX_AGE)]
    wide = mi.pivot(index="age", columns="year", values="mi").sort_index()
    grid = np.zeros((MAX_AGE + 1, wide.shape[1]))
    grid[MI_MIN_AGE:] = wide.loc[MI_MIN_AGE:MAX_AGE].to_numpy()
    grid[:MI_MIN_AGE] = grid[MI_MIN_AGE]          # ages under 20 use the age-20 rate
    grid[MAX_AGE] = 0.0                            # q = 1 at 110 is never improved
    return grid


def _cia_factor(sex: str, age: int, year: int, period: int) -> float:
    """CIA MI-2024: product of (1 - MI(age, s)) for s = base year + 1 .. year."""
    start = base_year(period)
    grid = _mi_grid(sex, start + 1)
    n_years = grid.shape[1]                        # base year + 1 .. 2119
    k = year - start                               # number of years of improvement
    rates = grid[age, : min(k, n_years)]
    extra = max(0, k - n_years)                    # years after 2119 keep the 2119 rate
    return float(np.prod(1 - rates) * (1 - grid[age, -1]) ** extra)


@lru_cache(maxsize=None)
def cpp_rates(sex: str) -> np.ndarray:
    """CPP Table 41 by single age 0..110 as decimals: columns 2025, 2026-2038, 2039+ (age 110: 0)."""
    t = pd.read_csv(CPP_FILE)
    t = t[t["sex"] == sex]
    out = np.zeros((MAX_AGE + 1, 3))
    for r in t.itertuples():
        out[r.age_lo:r.age_hi + 1] = np.array([r.mi_2025, r.mi_2026_2038, r.mi_2039_plus]) / 100
    out[MAX_AGE] = 0.0
    if (out[:MAX_AGE] <= 0).any():
        raise ValueError(f"CPP improvement table incomplete for {sex}")
    return out


def _cpp_years(start: int, year: int) -> tuple[int, int, int]:
    """Years of improvement in each CPP span (to 2025, 2026-2038, 2039+) from start + 1 to year."""
    def count(lo, hi):
        return max(0, min(year, hi) - max(start + 1, lo) + 1)
    return count(-10**6, 2025), count(2026, 2038), count(2039, 10**6)


def _cpp_factor_raw(sex: str, age: int, year: int, period: int, scale: tuple[float, float]) -> float:
    start = base_year(period)
    n1, n2, n3 = _cpp_years(start, year)
    m = cpp_rates(sex)[age]
    k = scale[0] if age < CPP_SPLIT_AGE else scale[1]
    return float((1 - k * m[0]) ** n1 * (1 - m[1]) ** n2 * (1 - m[2]) ** n3)


def _period_e(sex: str, year: int, age: int, scale: tuple[float, float]) -> float:
    """Canada period life expectancy at `age` in `year` on the CPP basis with this 2019-2025 scale."""
    q = base_qx("CA", sex).copy()
    q[:MAX_AGE] *= [_cpp_factor_raw(sex, a, year, BASE_PERIOD, scale) for a in range(MAX_AGE)]
    return life_expectancy(q[age:])


def _solve(f, lo: float = -3.0, hi: float = 3.0) -> float:
    """Root of an increasing function by bisection."""
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


@lru_cache(maxsize=None)
def cpp_scale(sex: str) -> tuple[float, float]:
    """
    Scale on the 2025 rates for the years 2019-2025, below 65 and from 65 (A28): solved so
    the period life expectancy in 2025 at 65, then at 0, equals the report's Table 43.
    """
    t = pd.read_csv(CPP_LE_FILE)
    target = t[(t["sex"] == sex) & (t["basis"] == "period") & (t["year"] == CPP_FIT_YEAR)]
    e = dict(zip(target["age"], target["e"]))
    old = _solve(lambda k: _period_e(sex, CPP_FIT_YEAR, CPP_SPLIT_AGE, (1.0, k)) - e[CPP_SPLIT_AGE])
    young = _solve(lambda k: _period_e(sex, CPP_FIT_YEAR, 0, (k, old)) - e[0])
    return young, old


def improvement_factor(sex: str, age: int, year: int, period: int = BASE_PERIOD,
                       basis: str = DEFAULT_BASIS) -> float:
    """
    How much the base table's death rate at this age falls by this calendar year:
    1 for years up to the table's middle year, then the product of (1 - MI) each year.
    """
    if basis not in BASES:
        raise ValueError(f"improvement basis must be one of {BASES}, got {basis!r}")
    if year <= base_year(period) or age >= MAX_AGE:
        return 1.0
    if basis == "cia":
        return _cia_factor(sex, age, year, period)
    return _cpp_factor_raw(sex, age, year, period, cpp_scale(sex))


def resolve_basis(improve: bool | str) -> str | None:
    """improve=True means the default scale, False none, or name a scale ("cpp", "cia")."""
    if improve is True:
        return DEFAULT_BASIS
    if improve is False or improve is None:
        return None
    if improve not in BASES:
        raise ValueError(f"improve must be True, False or one of {BASES}, got {improve!r}")
    return improve


def cohort_qx(
    region: str, sex: str, age: int, year: int, improve: bool | str = True, period: int = BASE_PERIOD
) -> np.ndarray:
    """
    The death rates one person will face: element k is q at age (age + k) in
    calendar year (year + k), for k = 0 .. 110 - age. The last element is 1.
    improve: True (the default scale, CPP), False (none), or "cpp" / "cia".
    """
    if not MIN_AGE <= age <= MAX_AGE:
        raise ValueError(f"age must be {MIN_AGE}-{MAX_AGE}, got {age}")
    q = base_qx(region, sex, period)[age:].copy()
    basis = resolve_basis(improve)
    if basis:
        q *= np.array(
            [improvement_factor(sex, age + k, year + k, period, basis) for k in range(len(q))]
        )
    return np.clip(q, 0.0, 1.0)


def life_expectancy(q: np.ndarray) -> float:
    """
    Complete life expectancy from a run of yearly death rates ending in q = 1,
    with deaths spread evenly within each year (UDD): sum of k p_x plus 1/2.
    """
    survival = np.cumprod(1 - q)                   # 1p, 2p, ... (last is 0)
    return float(survival.sum() + 0.5)
