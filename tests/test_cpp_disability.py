"""
Checks on the CPP disability tables (built by pipeline/12_cpp_disability.py from the
32nd Actuarial Report on the Canada Pension Plan).

Run from the project folder:
    pytest
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"


def load(name: str) -> pd.DataFrame:
    path = CLEAN / name
    if not path.exists():
        pytest.fail(f"data/clean/{name} missing: run pipeline/12_cpp_disability.py")
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def inc() -> pd.DataFrame:
    return load("cpp_disability_incidence.csv")


@pytest.fixture(scope="module")
def term() -> pd.DataFrame:
    return load("cpp_disability_termination.csv")


@pytest.fixture(scope="module")
def elig() -> pd.DataFrame:
    return load("cpp_disability_eligibility.csv")


def test_incidence_grid_complete(inc):
    """Both sexes, every age 18-64, positive rates."""
    assert set(inc["sex"]) == {"M", "F"}
    assert set(inc["age"]) == set(range(18, 65))
    assert len(inc) == 2 * 47
    assert (inc["per_1000"] > 0).all()


def test_published_values_read_correctly(inc):
    """Spot values from Table 85, the same in the report's web page and its PDF."""
    r = inc.set_index(["sex", "age"])["per_1000"]
    assert r[("M", 25)] == pytest.approx(0.3) and r[("F", 25)] == pytest.approx(0.4)
    assert r[("M", 50)] == pytest.approx(3.3) and r[("F", 50)] == pytest.approx(4.5)
    assert r[("M", 60)] == pytest.approx(9.4) and r[("F", 60)] == pytest.approx(10.1)
    assert r[("M", 64)] == pytest.approx(9.6) and r[("F", 64)] == pytest.approx(10.0)


def test_filled_ages_lie_between_published_neighbours(inc):
    """Interpolated ages stay between the published ages on either side."""
    for sex, g in inc.groupby("sex"):
        pub = g[g["method"] == "published"].set_index("age")["per_1000"]
        for _, row in g[g["method"] == "interpolated"].iterrows():
            lo = pub[pub.index < row["age"]].iloc[-1]
            hi = pub[pub.index > row["age"]].iloc[0]
            assert min(lo, hi) <= row["per_1000"] <= max(lo, hi)


def test_risk_rises_with_age_to_61(inc):
    for sex, g in inc.groupby("sex"):
        r = g.sort_values("age").set_index("age")["per_1000"].loc[18:61]
        assert r.is_monotonic_increasing


def test_women_higher_than_men(inc):
    """The report: since 1996 women have consistently had higher incidence than men."""
    w = inc.pivot(index="age", columns="sex", values="per_1000")
    assert (w["F"] >= w["M"]).all()


def test_termination_table(term):
    """96 values (2 years x 2 sexes x 4 ages x 6 durations), per 1,000 between 0 and 1,000;
    onset at 60 has no 6th year (benefits stop at 65)."""
    assert len(term) == 96
    assert term["per_1000"].between(0, 1000).all()
    assert (term.query("age == 60 and duration == 6")["per_1000"] == 0).all()
    assert (term.query("age < 60")["per_1000"] > 0).all()


def test_eligibility_2025(elig):
    """Table 73: 71.7% of men and 65.7% of women aged 20-64 eligible in 2025."""
    e = elig[elig["year"] == 2025].set_index("sex")["eligible_pct"]
    assert e["M"] == pytest.approx(71.7) and e["F"] == pytest.approx(65.7)


def test_rates_rebuild_report_projection(inc, elig):
    """Rates x eligible population (Canada less Quebec, ages 20-64, 2026 population) come
    within 15% of the report's projected new beneficiaries for 2029 (Table 86:
    19,000 men, 21,900 women). One eligibility rate is used for every age, a simplification."""
    pop_path = CLEAN / "population.csv"
    if not pop_path.exists():
        pytest.fail("data/clean/population.csv missing: run pipeline/07_clean_population.py")
    pop = pd.read_csv(pop_path)
    p = pop[(pop["year"] == 2026) & pop["sex"].isin(["M", "F"]) & pop["age"].between(20, 64)]
    cpp_area = (p[p["region"] == "CA"].set_index(["sex", "age"])["population"]
                - p[p["region"] == "QC"].set_index(["sex", "age"])["population"])
    report = {"M": 19_000, "F": 21_900}
    for sex, expected in report.items():
        share = elig.query("year == 2029 and sex == @sex")["eligible_pct"].item() / 100
        rate = inc[inc["sex"] == sex].set_index("age")["per_1000"].loc[20:64] / 1000
        estimate = (cpp_area.loc[sex] * share * rate).sum()
        assert abs(estimate / expected - 1) <= 0.15, (sex, estimate, expected)
