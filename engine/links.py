"""
Links between events, Phase 3 (A22): cancer deaths follow a cancer diagnosis.

Without this link, a simulated person could die of lung cancer never having
been diagnosed with it. With it, cancer deaths happen only to people who
have been diagnosed, at a rate that depends on the time since diagnosis.

How the rates are set, for each sex (a synthetic cohort on 2017-2019 rates):
  * start 100,000 cancer-free 18-year-olds; each year some are diagnosed with
    lung or other-site cancer (A13) and everyone faces the death rates (A04);
  * people diagnosed in the last 5 years carry an excess cancer death rate
    s(age); after 5 years it falls to W_LATE x s(age) (Canadian Cancer
    Statistics 2023: lung cancer 5-year net survival 22%, 10-year 15%, which
    puts the later yearly rate at about a quarter of the early one);
  * at each age, s for lung and for other sites, and a small scale on all
    other causes, are solved so the cohort reproduces the official 2017-2019
    deaths that year exactly: total, lung cancer and other cancer.
  * where too few people have been diagnosed to produce the official cancer
    deaths (very young or very old ages), s is capped at S_MAX and the rest
    is carried by undiagnosed people (a cancer found only at death).

Survival is not an input: the cancer survival that comes out (e.g. about 22%
of men alive 5 years after a lung diagnosis at 50-65) is a check (tested).

For a person, the non-cancer part of their own death rate (engine/risk.py and
engine/causes.py) is kept. Their chance of a cancer diagnosis is the
population's times their own cancer death ratio (cancer_incidence), and after
diagnosis they face the population's death rate (state_tables; the scale k
there is 1 whenever the diagnosis rate was not capped at 1).
"""

from functools import lru_cache

import numpy as np

from engine.causes import CAUSES, base_shares
from engine.events import cancer_probabilities
from engine.mortality import MAX_AGE, MIN_AGE, base_qx

W = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 0.25])   # weight by years since diagnosis 0..4, 5+
W_LATE = W[-1]
S_MAX = 3.0                                      # cap on the yearly excess force (q about 95%)
LUNG, OTHER = CAUSES.index("lung_cancer"), CAUSES.index("other_cancer")
NON_CANCER = [i for i in range(len(CAUSES)) if i not in (LUNG, OTHER)]


def shift(diag: np.ndarray, new: float) -> np.ndarray:
    """One year on: years since diagnosis +1 (5+ stays 5+), new diagnoses enter at 0."""
    return np.concatenate([[new], diag[:4], [diag[4] + diag[5]]])


def _year(pu, pl, po, h_nc, s_l, s_o, r_l, r_o):
    """Deaths by cause group (non-cancer, lung, other) and each state's death probability."""
    def split(mass, forces):
        total = forces.sum(axis=0)
        q = 1 - np.exp(-total)
        return (mass * q * forces / np.where(total > 0, total, 1)).sum(axis=-1), q
    d_u, q_u = split(np.array([pu]), np.array([[h_nc], [r_l], [r_o]]))
    d_l, q_l = split(pl, np.array([np.full(6, h_nc), s_l * W, np.zeros(6)]))
    d_o, q_o = split(po, np.array([np.full(6, h_nc), np.zeros(6), s_o * W]))
    return d_u + d_l + d_o, q_u[0], q_l, q_o


@lru_cache(maxsize=None)
def calibration(sex: str) -> dict[str, np.ndarray]:
    """
    Arrays by age (index = age) of: s_lung, s_other (excess force after diagnosis),
    r_lung, r_other (force on undiagnosed people, usually 0) and eta (scale on
    the non-cancer force), solved year by year on the synthetic cohort.
    """
    q = base_qx("CA", sex)
    out = {k: np.zeros(MAX_AGE + 1) for k in ("s_lung", "s_other", "r_lung", "r_other", "eta")}
    out["eta"][:] = 1.0
    pu, pl, po = 1.0, np.zeros(6), np.zeros(6)
    for age in range(MIN_AGE, MAX_AGE):
        lung, other = cancer_probabilities(sex, age)
        pl, po = shift(pl, pu * lung), shift(po, pu * (1 - lung) * other)
        pu *= (1 - lung) * (1 - other)
        mass = pu + pl.sum() + po.sum()
        shares = base_shares(sex, age)
        mu = -np.log(1 - q[age])
        target = mass * q[age] * np.array([1 - shares[LUNG] - shares[OTHER], shares[LUNG], shares[OTHER]])
        h_nc = mu * (1 - shares[LUNG] - shares[OTHER])
        diagnosed = np.array([(pl * W).sum(), (po * W).sum()])
        need = mu * np.array([shares[LUNG], shares[OTHER]])        # force needed if spread on everyone
        s, r = np.zeros(2), np.zeros(2)
        for j in (0, 1):
            if need[j] == 0:
                continue
            if diagnosed[j] == 0:
                r[j] = need[j]                                     # nobody diagnosed yet
            else:
                s[j] = min(need[j] * mass / diagnosed[j], S_MAX)
        for _ in range(1000):
            deaths, q_u, q_l, q_o = _year(pu, pl, po, h_nc, s[0], s[1], r[0], r[1])
            if np.allclose(deaths, target, rtol=1e-12, atol=1e-300):
                break
            h_nc *= target[0] / deaths[0]
            for j in (0, 1):
                if need[j] == 0:
                    continue
                ratio = target[j + 1] / deaths[j + 1]
                if r[j] > 0:
                    r[j] *= ratio
                elif s[j] * ratio > S_MAX:
                    s[j] = S_MAX
                    r[j] = need[j] * 1e-3
                else:
                    s[j] *= ratio
        else:
            raise RuntimeError(f"cancer link calibration did not converge: {sex} {age}")
        out["s_lung"][age], out["s_other"][age] = s
        out["r_lung"][age], out["r_other"][age] = r
        out["eta"][age] = h_nc / (mu * (1 - shares[LUNG] - shares[OTHER]))
        pu *= 1 - q_u
        pl, po = pl * (1 - q_l), po * (1 - q_o)
    for k in out:                       # age 110: everyone dies; keep 109's values for the cause split
        out[k][MAX_AGE] = out[k][MAX_AGE - 1]
    return out


def death_ratios(q_person: np.ndarray, causes_person: np.ndarray, sex: str, first_age: int) -> np.ndarray:
    """
    Person's death rate from lung and from other-site cancer divided by the
    population's 2017-2019 rate, at each age (columns: lung, other).
    """
    q_pop = base_qx("CA", sex)
    out = np.ones((len(q_person), 2))
    for i in range(len(q_person)):
        age = first_age + i
        if q_person[i] >= 1:
            continue
        mu, mu_pop = -np.log(1 - q_person[i]), -np.log(1 - q_pop[age])
        shares = base_shares(sex, age)
        for j, site in enumerate((LUNG, OTHER)):
            if shares[site] > 0:
                out[i, j] = mu * causes_person[i][site] / (mu_pop * shares[site])
    return out


def cancer_incidence(q_person: np.ndarray, causes_person: np.ndarray, sex: str, first_age: int):
    """
    The person's yearly chance of a first lung and of a first other-site cancer
    diagnosis: the 2019 population rate (A13) x the person's death ratio for that
    cancer (death_ratios). So whatever raises or lowers a person's cancer deaths
    in their own model (smoking above all, and the other habits and mortality
    improvement through the all-cause multiplier) raises or lowers their chance
    of diagnosis by the same factor, and the population's survival after
    diagnosis then gives them, in expectation, their own model's cancer deaths.
    """
    ratios = death_ratios(q_person, causes_person, sex, first_age)
    lung, other = np.zeros(len(q_person)), np.zeros(len(q_person))
    for i in range(len(q_person)):
        pop_lung, pop_other = cancer_probabilities(sex, min(first_age + i, MAX_AGE))
        lung[i] = min(1.0, pop_lung * ratios[i, 0])
        other[i] = min(1.0, pop_other * ratios[i, 1])
    return lung, other


def state_tables(q_person: np.ndarray, causes_person: np.ndarray, sex: str, first_age: int,
                 incidence_person: tuple[np.ndarray, np.ndarray]):
    """
    For a person (their own death probability, cause mix and cancer incidence by
    age), the death probability and cause mix in each cancer state, at each age.

    The population's death rate after diagnosis is scaled for the person, site
    by site, by k = (person's cancer death rate / population's) divided by
    (person's chance of diagnosis / population's). So a person whose own model
    gives fewer cancer deaths (healthier habits, later years with mortality
    improvement) keeps that advantage, and a smoker's extra lung cancer deaths
    come mostly through extra diagnoses (k close to 1).

        q_u[i], c_u[i]              never diagnosed
        q_l[i, d], c_l[i, d]        lung cancer, d = years since diagnosis (0..4, 5+)
        q_o[i, d], c_o[i, d]        other-site cancer
    """
    cal = calibration(sex)
    ratios = death_ratios(q_person, causes_person, sex, first_age)
    n, k = len(q_person), len(CAUSES)
    q_u, q_l, q_o = np.ones(n), np.ones((n, 6)), np.ones((n, 6))
    c_u, c_l, c_o = np.zeros((n, k)), np.zeros((n, 6, k)), np.zeros((n, 6, k))
    for i in range(n):
        age = first_age + i
        nc = causes_person[i].copy()
        nc[[LUNG, OTHER]] = 0
        if nc.sum() > 0:
            nc /= nc.sum()
        if q_person[i] >= 1:                                     # age 110: everyone dies
            c_u[i] = nc
            c_l[i] = c_o[i] = causes_person[i]
            continue
        mu = -np.log(1 - q_person[i])
        h_nc = mu * (1 - causes_person[i][LUNG] - causes_person[i][OTHER]) * cal["eta"][age]
        lung_pop, other_pop = cancer_probabilities(sex, age)
        d_site = ratios[i]
        k_site = []
        for j, (inc_pop, inc_p) in enumerate(((lung_pop, incidence_person[0][i]),
                                              (other_pop, incidence_person[1][i]))):
            inc_ratio = inc_p / inc_pop if inc_pop > 0 else d_site[j]
            k_site.append(d_site[j] / inc_ratio if inc_ratio > 0 else 1.0)
        k_l, k_o = k_site
        forces_u = h_nc * nc                     # undiagnosed cancer deaths scale with the death ratio only
        forces_u[LUNG] += cal["r_lung"][age] * d_site[0]
        forces_u[OTHER] += cal["r_other"][age] * d_site[1]
        q_u[i] = 1 - np.exp(-forces_u.sum())
        c_u[i] = forces_u / forces_u.sum()
        for d in range(6):
            fl = h_nc * nc
            fl[LUNG] += cal["s_lung"][age] * k_l * W[d]
            q_l[i, d] = 1 - np.exp(-fl.sum())
            c_l[i, d] = fl / fl.sum()
            fo = h_nc * nc
            fo[OTHER] += cal["s_other"][age] * k_o * W[d]
            q_o[i, d] = 1 - np.exp(-fo.sum())
            c_o[i, d] = fo / fo.sum()
    return q_u, q_l, q_o, c_u, c_l, c_o


def five_year_survival(sex: str, site: str, age: int) -> float:
    """Chance of surviving cancer itself for 5 years after a diagnosis at this age (net survival)."""
    s = calibration(sex)["s_lung" if site == "lung" else "s_other"]
    return float(np.exp(-s[age:age + 5].sum()))
