"""
Marriage and mortality (A24): married people die at lower rates than people who
never married, divorced or were widowed.

A person's marital state (never, married, divorced: engine/events.py) changes
during their life, so the ratio is applied year by year in their current
state: relative ratio = HR(state) / population average at that age, where the
average uses the 2019 legal marital mix of Canadians of that sex and age
(single, married, separated, widowed, divorced; data/clean/marital_status.csv)
and the ratios in data/assumptions/hazard_ratios.csv. So Canadians as a whole
keep the official death rates. The same taper as A08 shrinks the log ratio
after 79. People living common law are legally single, as in the events.
"""

from functools import lru_cache

from engine.data import load
from engine.risk import hazard_ratio, taper

BASE_YEAR = 2019
STATE_LEVEL = {"never": "single", "married": "married", "divorced": "divorced"}
LEVELS = ("single", "married", "separated", "widowed", "divorced")


@lru_cache(maxsize=None)
def marital_mix(sex: str, age: int) -> dict[str, float]:
    """Share of Canadians of this sex and single age (100 = 100+) in each legal marital status, 2019."""
    t = load("marital_status.csv")
    a = min(max(age, 15), 100)
    rows = t[(t["year"] == BASE_YEAR) & (t["region"] == "CA") & (t["sex"] == sex) & (t["age"] == a)]
    mix = dict(zip(rows["status"], rows["share"]))
    if set(mix) != set(LEVELS) or abs(sum(mix.values()) - 1) > 1e-6:
        raise ValueError(f"incomplete marital mix for {sex} {age}: {mix}")
    return mix


@lru_cache(maxsize=None)
def average_ratio(sex: str, age: int) -> float:
    w = taper(age)
    return sum(share * hazard_ratio("marital", level, sex) ** w for level, share in marital_mix(sex, age).items())


def marital_ratio(state: str, sex: str, age: int) -> float:
    """Multiplier on the person's force of mortality while in this marital state."""
    return hazard_ratio("marital", STATE_LEVEL[state], sex) ** taper(age) / average_ratio(sex, age)
