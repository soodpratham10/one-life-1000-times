"""
Checks on engine/links.py: cancer deaths follow a cancer diagnosis (A22), and
deaths after a heart attack or stroke (A23).

Run from the project folder:
    pytest tests/test_links.py -v
"""

import numpy as np
import pytest

from engine.causes import base_shares
from engine.events import cancer_probabilities
from engine.links import LUNG, OTHER, S_MAX, W, calibration, five_year_survival, shift
from engine.mortality import base_qx
from engine.risk import Person


def test_shift_by_hand():
    d = np.array([1.0, 2, 3, 4, 5, 6])
    assert list(shift(d, 9.0)) == [9, 1, 2, 3, 4, 11]      # 5 and 6 merge into 5+


@pytest.mark.parametrize("sex", ["M", "F"])
def test_calibration_reproduces_official_deaths(sex):
    """
    Re-run the synthetic cohort with the solved rates: at every age 18-109 the
    total, lung cancer and other cancer deaths equal the 2017-2019 figures.
    """
    cal = calibration(sex)
    q = base_qx("CA", sex)
    pu, pl, po = 1.0, np.zeros(6), np.zeros(6)
    for age in range(18, 110):
        lung, other = cancer_probabilities(sex, age)
        pl, po = shift(pl, pu * lung), shift(po, pu * (1 - lung) * other)
        pu *= (1 - lung) * (1 - other)
        mass = pu + pl.sum() + po.sum()
        shares = base_shares(sex, age)
        mu = -np.log(1 - q[age])
        h_nc = mu * (1 - shares[LUNG] - shares[OTHER]) * cal["eta"][age]

        def deaths(mass_s, f_nc, f_l, f_o):
            total = f_nc + f_l + f_o
            qq = 1 - np.exp(-total)
            return mass_s * qq, mass_s * qq * f_l / total, mass_s * qq * f_o / total

        du = deaths(pu, h_nc, cal["r_lung"][age], cal["r_other"][age])
        dl = deaths(pl, h_nc, cal["s_lung"][age] * W, 0.0)
        do = deaths(po, h_nc, 0.0, cal["s_other"][age] * W)
        total = du[0] + dl[0].sum() + do[0].sum()
        assert total == pytest.approx(mass * q[age], rel=1e-9)
        assert du[1] + dl[1].sum() == pytest.approx(mass * q[age] * shares[LUNG], rel=1e-9, abs=1e-15)
        assert du[2] + do[2].sum() == pytest.approx(mass * q[age] * shares[OTHER], rel=1e-9, abs=1e-15)
        pu -= du[0]
        pl, po = pl - dl[0], po - do[0]


@pytest.mark.parametrize("sex", ["M", "F"])
def test_rates_are_sensible(sex):
    cal = calibration(sex)
    ages = slice(18, 110)
    assert (cal["s_lung"][ages] >= 0).all() and (cal["s_lung"][ages] <= S_MAX).all()
    assert (cal["s_other"][ages] >= 0).all() and (cal["s_other"][ages] <= S_MAX).all()
    assert np.abs(cal["eta"][ages] - 1).max() < 0.02           # other causes barely rescaled
    # undiagnosed cancer deaths only where too few people have been diagnosed: under 30 or over 85
    for key in ("r_lung", "r_other"):
        where = [a for a in range(18, 110) if cal[key][a] > 0]
        assert all(a < 30 or a > 85 for a in where), (key, where)


@pytest.mark.parametrize("sex, low, high", [("M", 0.12, 0.35), ("F", 0.15, 0.50)])
def test_lung_cancer_survival_close_to_published(sex, low, high):
    """
    Not an input, an outcome. Canadian Cancer Statistics 2023: 5-year net survival
    for lung cancer 19% (men) and 26% (women). Engine, diagnosis at 50-70: men
    about 22-26%, women about 35-45% (the engine is optimistic for women).
    """
    for age in (50, 55, 60, 65, 70):
        assert low < five_year_survival(sex, "lung", age) < high


@pytest.mark.parametrize("sex", ["M", "F"])
def test_other_cancer_survival_close_to_published(sex):
    """All cancers combined (including lung, which lowers it): 64% (Statistics Canada). Other sites: 65-90%."""
    for age in (45, 55, 65, 75):
        assert 0.6 < five_year_survival(sex, "other", age) < 0.92


# ================================================================ heart attack and stroke (A23)

from engine.links import (  # noqa: E402
    ACUTE_CAP, FATALITY_LEVEL, HEART, STROKE, SURVIVOR_RR, _cardio_year, _fatality_scale, _next_grid,
    _shape, acute_fatality, cardio_calibration, death_tables, person_incidence,
)
from engine.data import load  # noqa: E402
from engine.events import heart_stroke_probabilities  # noqa: E402


@pytest.mark.parametrize("event", ["heart", "stroke"])
def test_fatality_level_matches_published_average(event):
    """Before the cap, the age curve averages over all Canadian cases to 6.5% (heart attack) and 13.2% (stroke)."""
    t = load("heart_stroke_rates.csv")
    col = "cases_heart_attack" if event == "heart" else "cases_stroke"
    mid = (t["age_lo"] + t["age_hi"].clip(upper=95)) / 2
    avg = (t[col] * mid.map(_shape)).sum() / t[col].sum() * _fatality_scale(event)
    assert avg == pytest.approx(FATALITY_LEVEL[event])


def test_fatality_age_shape_by_hand():
    """Log-linear through 2.1% at 50 and 26.3% at 88 (Quebec registry)."""
    assert _shape(50) == pytest.approx(0.021)
    assert _shape(88) == pytest.approx(0.263)
    assert _shape(69) == pytest.approx((0.021 * 0.263) ** 0.5)       # halfway: geometric mean


@pytest.mark.parametrize("sex", ["M", "F"])
@pytest.mark.parametrize("event", ["heart", "stroke"])
def test_acute_deaths_never_exceed_the_cap(sex, event):
    f = acute_fatality(sex, event)
    q = base_qx("CA", sex)
    idx, col = (HEART, 0) if event == "heart" else (STROKE, 1)
    for age in range(18, 110):
        inc = heart_stroke_probabilities(sex, age)[col]
        assert inc * f[age] <= ACUTE_CAP * q[age] * base_shares(sex, age)[idx] * (1 + 1e-12)
        assert 0 <= f[age] < 1


@pytest.mark.parametrize("sex", ["M", "F"])
def test_cardio_calibration_reproduces_official_deaths(sex):
    """Re-run the cohort with the solved rates: total, heart and stroke deaths match 2017-2019 at every age."""
    cc = cardio_calibration(sex)
    q = base_qx("CA", sex)
    fa, fs = acute_fatality(sex, "heart"), acute_fatality(sex, "stroke")
    p = np.array([[1.0, 0.0], [0.0, 0.0]])
    for age in range(18, 110):
        ia, ist = heart_stroke_probabilities(sex, age)
        shares = base_shares(sex, age)
        mu = -np.log(1 - q[age])
        mass = p.sum()
        r, acute_h, acute_s, move_a, move_s = _cardio_year(p, ia, ist, fa[age], fs[age])
        deaths = np.array([0.0, acute_h, acute_s])
        qg = np.zeros((2, 2))
        for i in (0, 1):
            for j in (0, 1):
                f = np.array([mu * (1 - shares[HEART] - shares[STROKE]) * cc["eta"][age],
                              cc["b_heart"][age] * mu * shares[HEART] + (cc["rr_heart"][age] - 1) * mu * i,
                              cc["b_stroke"][age] * mu * shares[STROKE] + (cc["rr_stroke"][age] - 1) * mu * j])
                qg[i, j] = 1 - np.exp(-f.sum())
                deaths += r[i, j] * qg[i, j] * f / f.sum()
        target = mass * q[age] * np.array([1 - shares[HEART] - shares[STROKE], shares[HEART], shares[STROKE]])
        assert deaths == pytest.approx(target, rel=1e-8)
        p = _next_grid(r * (1 - qg), move_a, move_s)


@pytest.mark.parametrize("sex", ["M", "F"])
def test_cardio_rates_are_sensible(sex):
    cc = cardio_calibration(sex)
    ages = slice(18, 110)
    for k in ("b_heart", "b_stroke"):
        assert (cc[k][ages] >= 0).all() and (cc[k][ages] <= 1.05).all()
    for k in ("rr_heart", "rr_stroke"):
        assert (cc[k][ages] >= 1).all() and (cc[k][ages] <= SURVIVOR_RR + 1e-9).all()
    assert np.abs(cc["eta"][ages] - 1).max() < 0.02
    assert (cc["rr_heart"][18:100] == SURVIVOR_RR).all()            # heart: the full 1.5 fits at every age to 99


def test_person_tables():
    """Probabilities valid; survivors die more than others; a lung cancer diagnosis raises the death rate."""
    from engine.causes import cause_probabilities
    from engine.risk import personal_qx
    p = Person("F", 45, smoking="current")
    q = personal_qx(p, 2026, improve=False)
    causes = np.array([cause_probabilities(p, a) for a in range(45, 111)])
    qs, cs, ah, ast = death_tables(q, causes, "F", 45)
    assert ((qs >= 0) & (qs <= 1)).all() and np.allclose(cs.sum(axis=-1), 1)
    assert (qs[:-1, 0, 1, 0] > qs[:-1, 0, 0, 0]).all()               # heart attack survivor
    assert (qs[:-1, 1, 0, 0] > qs[:-1, 0, 0, 0]).all()               # lung cancer, first year
    inc = person_incidence(q, causes, "F", 45)
    assert all(((v >= 0) & (v <= 1)).all() for v in inc.values())
    assert ((ah >= 0) & (ah < 1)).all() and ((ast >= 0) & (ast < 1)).all()
