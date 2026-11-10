"""
Checks on data/clean/family_events.csv (built by pipeline/14_family_events.py):
first marriage, remarriage, divorce and first child, Canada, 2019.

Run from the project folder:
    pytest
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
CLEAN_CSV = ROOT / "data" / "clean" / "family_events.csv"


@pytest.fixture(scope="module")
def fam() -> pd.DataFrame:
    if not CLEAN_CSV.exists():
        pytest.fail("data/clean/family_events.csv missing: run pipeline/14_family_events.py")
    return pd.read_csv(CLEAN_CSV)


def rates(fam, event, sex):
    return fam[(fam["event"] == event) & (fam["sex"] == sex)].set_index("age_lo")["rate_per_1000"]


def test_grid_complete(fam):
    """14 marriage age groups x 2 sexes (first and re-marriage), 11 divorce groups x 2 sexes,
    8 age groups of mothers; every rate filled in."""
    n = fam.groupby("event").size()
    assert n["first_marriage"] == 28 and n["remarriage"] == 28
    assert n["divorce"] == 22 and n["first_child"] == 8
    assert fam["rate_per_1000"].notna().all()


def test_rates_valid(fam):
    assert fam["rate_per_1000"].between(0, 1000).all()
    assert (fam["count_2019"] >= 0).all()


def test_sex_rates_bracket_the_both_sexes_rate(fam):
    """With the relational method, men's and women's rates sit either side of (or equal to)
    the 2019 rate for both sexes, in every age group (remarriage under 20 excluded: replaced)."""
    rel = fam[fam["event"].isin(["first_marriage", "remarriage", "divorce"])
              & ~((fam["event"] == "remarriage") & (fam["age_lo"] == 15))]
    w = rel.pivot_table(index=["event", "age_lo"], columns="sex", values="rate_per_1000")
    both = rel.groupby(["event", "age_lo"])["rate_both_2019"].first()
    lo, hi = w.min(axis=1), w.max(axis=1)
    assert ((lo <= both + 1e-9) & (both <= hi + 1e-9)).all()


def test_divorced_persons_match_published_divorces(fam):
    """StatCan's The Daily (9 March 2022): 56,937 divorces in 2019. Each divorce is two
    persons, so persons who divorced should be about 113,874 (within 0.5%)."""
    persons = fam.query("event == 'divorce' and sex == 'M'")["count_2019"].sum()   # counts cover both sexes
    assert abs(persons / (2 * 56_937) - 1) <= 0.005, persons


def test_overall_divorce_rate(fam):
    """Persons divorced / married persons at risk = StatCan's published 7.5 per 1,000 for 2019."""
    d = fam.query("event == 'divorce' and sex == 'M'")
    assert d["count_2019"].sum() / d["at_risk_2019"].sum() * 1000 == pytest.approx(7.5, abs=0.1)


def test_first_marriage_peaks_in_late_20s_or_early_30s(fam):
    for sex in ["M", "F"]:
        assert rates(fam, "first_marriage", sex).idxmax() in (25, 30), sex


def test_women_marry_younger_than_men(fam):
    assert rates(fam, "first_marriage", "F")[20] > rates(fam, "first_marriage", "M")[20]


def test_divorce_less_common_in_old_age(fam):
    for sex in ["M", "F"]:
        r = rates(fam, "divorce", sex)
        assert r[65] < r[30], sex


def test_first_child_peaks_25_to_34(fam):
    assert rates(fam, "first_child", "F").idxmax() in (25, 30)


def test_first_births_share(fam):
    """2019: 157,114 first births out of 373,889 live births (about 42%), from the source."""
    fb = fam.query("event == 'first_child'")["count_2019"].sum()
    assert 0.40 <= fb / 373_889 <= 0.44, fb


def test_mean_age_at_first_birth_plausible(fam):
    """Count-weighted mean age of mothers at first birth (group mid-points) between 28 and 32."""
    fb = fam[fam["event"] == "first_child"]
    mid = (fb["age_lo"] + fb["age_hi"] + 1) / 2
    mean_age = (mid * fb["count_2019"]).sum() / fb["count_2019"].sum()
    assert 28 <= mean_age <= 32, mean_age
