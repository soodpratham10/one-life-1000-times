"""
Mortality basis: base death rates projected forward with mortality improvement.

    base table   Statistics Canada complete life table, by province and sex (A04);
                 PEI from the derived single-age table (A10). Default period
                 2017-2019, the last before COVID-19 (A09). A three-year table
                 describes its middle year, so 2017-2019 is treated as the rates
                 for calendar year 2018.
    improvement  CIA MI-2024 (A05): q(x, t) = q(x, t-1) * (1 - MI(x, t)).
                 Ages 18-19 use the age-20 rate; years after 2119 keep the 2119
                 rate; age 110 is never improved (q = 1 there, A02).

A person aged x in calendar year t is aged x + k in year t + k, so their own
rates run along the diagonal of the (age, year) grid: cohort_qx() returns them.
"""

from functools import lru_cache

import numpy as np

from engine.data import MI_FILE, load

BASE_PERIOD = 2017            # default base table: 2017-2019 (A09)
MAX_AGE = 110                 # open age group, q = 1 (A02)
MIN_AGE = 18                  # youngest person simulated (A01)
MI_MIN_AGE = 20               # youngest age in MI-2024

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


def improvement_factor(sex: str, age: int, year: int, period: int = BASE_PERIOD) -> float:
    """
    Product of (1 - MI(age, s)) for s = base year + 1 .. year, where the base
    year is the middle of the life table; 1 for years up to the base year.
    """
    start = base_year(period)
    if year <= start:
        return 1.0
    grid = _mi_grid(sex, start + 1)
    n_years = grid.shape[1]                        # base year + 1 .. 2119
    k = year - start                               # number of years of improvement
    rates = grid[age, : min(k, n_years)]
    extra = max(0, k - n_years)                    # years after 2119 keep the 2119 rate
    return float(np.prod(1 - rates) * (1 - grid[age, -1]) ** extra)


def cohort_qx(
    region: str, sex: str, age: int, year: int, improve: bool = True, period: int = BASE_PERIOD
) -> np.ndarray:
    """
    The death rates one person will face: element k is q at age (age + k) in
    calendar year (year + k), for k = 0 .. 110 - age. The last element is 1.
    """
    if not MIN_AGE <= age <= MAX_AGE:
        raise ValueError(f"age must be {MIN_AGE}-{MAX_AGE}, got {age}")
    q = base_qx(region, sex, period)[age:].copy()
    if improve:
        q *= np.array(
            [improvement_factor(sex, age + k, year + k, period) for k in range(len(q))]
        )
    return np.clip(q, 0.0, 1.0)


def life_expectancy(q: np.ndarray) -> float:
    """
    Complete life expectancy from a run of yearly death rates ending in q = 1,
    with deaths spread evenly within each year (UDD): sum of k p_x plus 1/2.
    """
    survival = np.cumprod(1 - q)                   # 1p, 2p, ... (last is 0)
    return float(survival.sum() + 0.5)
