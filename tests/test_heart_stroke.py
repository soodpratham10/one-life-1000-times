"""
Checks on data/clean/heart_stroke_incidence.csv and data/clean/heart_stroke_rates.csv
(built by pipeline/11_heart_stroke.py).

Run from the project folder:
    pytest
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
INCIDENCE_CSV = ROOT / "data" / "clean" / "heart_stroke_incidence.csv"
RATES_CSV = ROOT / "data" / "clean" / "heart_stroke_rates.csv"
POP_CSV = ROOT / "data" / "clean" / "population.csv"
CONDITIONS = ["heart_attack", "stroke"]


def load(path: Path) -> pd.DataFrame:
    if not path.exists():
        pytest.fail(f"{path.relative_to(ROOT)} missing: run pipeline/11_heart_stroke.py")
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def inc() -> pd.DataFrame:
    return load(INCIDENCE_CSV)


@pytest.fixture(scope="module")
def rates() -> pd.DataFrame:
    return load(RATES_CSV)


def base(inc: pd.DataFrame) -> pd.DataFrame:
    return inc[(inc["fiscal_year"] == 2018) & (inc["region"] == "CA")]


def test_rates_grid_complete(rates):
    """Both sexes x 15 age groups (20-24 ... 85-89, 90+), no blanks."""
    assert set(rates["sex"]) == {"M", "F"}
    assert rates["age_lo"].tolist().count(20) == 2
    assert len(rates) == 2 * 15
    assert rates.notna().all().all()


def test_age_groups_add_up_to_total(inc):
    """5-year groups sum to the published 20+ total, within rounding of each count to 5."""
    b = base(inc)
    for (cond, sex), g in b.groupby(["condition", "sex"]):
        total = g.loc[g["age_group_type"] == "total", "cases"].item()
        five = g.loc[g["age_group_type"] == "5yr", "cases"].sum()
        assert abs(five - total) <= 5 * 15, (cond, sex, five, total)


def test_males_plus_females_equal_both(inc):
    b = base(inc)
    w = b.pivot_table(index=["condition", "age_group_type", "age_lo"], columns="sex", values="cases")
    assert (w["M"] + w["F"] - w["B"]).abs().max() <= 10


def test_matches_published_rates(rates):
    """Our cases / population reproduce PHAC's published rate (rounded to whole numbers)."""
    for c in CONDITIONS:
        ours = rates[f"p_{c}"] * 100_000
        assert (ours - rates[f"rate_per_100k_{c}"]).abs().max() <= 0.6


def test_risk_rises_with_age(rates):
    for c in CONDITIONS:
        for sex in ["M", "F"]:
            r = rates[rates["sex"] == sex].sort_values("age_lo")[f"p_{c}"]
            assert r.iloc[-1] > 20 * r.iloc[0], (c, sex)


def test_men_have_more_heart_attacks_in_midlife(rates):
    """PHAC: men's heart-attack rates are several times women's before old age."""
    mid = rates[rates["age_lo"].between(35, 64)].pivot(index="age_lo", columns="sex", values="p_heart_attack")
    assert (mid["M"] > 2 * mid["F"]).all()


def test_registry_population_close_to_statcan(inc):
    """CCDSS's health-registry population for adults 20+ is within 5% of StatCan's July 1
    estimates (registries run slightly high: people who leave are not always removed)."""
    if not POP_CSV.exists():
        pytest.fail("data/clean/population.csv missing: run pipeline/07_clean_population.py")
    pop = pd.read_csv(POP_CSV)
    statcan = pop.query("year in [2018, 2019] and region == 'CA' and sex == 'B' and age >= 20") \
                 .groupby("year")["population"].sum().mean()
    b = base(inc)
    for c in CONDITIONS:
        registry = b.query("condition == @c and sex == 'B' and age_group_type == 'total'")["population"].item()
        assert abs(registry / statcan - 1) <= 0.05, (c, registry, statcan)
