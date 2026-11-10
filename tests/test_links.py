"""
Checks on engine/links.py: cancer deaths follow a cancer diagnosis (A22).

Run from the project folder:
    pytest tests/test_links.py -v
"""

import numpy as np
import pytest

from engine.causes import CAUSES, base_shares
from engine.events import cancer_probabilities
from engine.links import LUNG, OTHER, S_MAX, W, calibration, five_year_survival, shift, state_tables
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


def test_state_tables():
    """Probabilities valid; cause mixes add to 1; diagnosed people die more than undiagnosed; no cancer deaths in U at 40-80."""
    from engine.causes import cause_probabilities
    from engine.links import cancer_incidence
    from engine.risk import personal_qx
    p = Person("M", 40, smoking="current")
    q = personal_qx(p, 2026, improve=False)
    causes = np.array([cause_probabilities(p, a) for a in range(40, 111)])
    q_u, q_l, q_o, c_u, c_l, c_o = state_tables(q, causes, "M", 40, cancer_incidence(q, causes, "M", 40))
    assert ((q_u >= 0) & (q_u <= 1)).all() and ((q_l >= 0) & (q_l <= 1)).all()
    for c in (c_u, c_l, c_o):
        assert np.allclose(c.sum(axis=-1), 1)
    assert (q_l[:-1, 0] > q_u[:-1]).all() and (q_o[:-1, 0] > q_u[:-1]).all()
    assert (q_l[:-1, 5] < q_l[:-1, 0]).all()                 # 5+ years after diagnosis: lower
    assert (c_u[:41, LUNG] == 0).all() and (c_u[:41, OTHER] == 0).all()   # ages 40-80
