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

For a person (person_incidence and death_tables, at the end of this file):
their chance of a cancer diagnosis is the population's times their own cancer
death ratio, and after diagnosis they face the population's excess rate; all
their other causes keep their own model's rates.
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


def five_year_survival(sex: str, site: str, age: int) -> float:
    """Chance of surviving cancer itself for 5 years after a diagnosis at this age (net survival)."""
    s = calibration(sex)["s_lung" if site == "lung" else "s_other"]
    return float(np.exp(-s[age:age + 5].sum()))


# ================================================================ heart attack and stroke (A23)
#
# After a first heart attack or stroke:
#   * acute phase: an extra chance of dying of it in the year it happens. The
#     chance rises with age along FATALITY_AGE_SHAPE, is scaled so that over
#     all Canadian cases (both sexes, CCDSS 2018-19) it averages the published
#     30-day fatality, and never makes acute deaths more than ACUTE_CAP of the
#     deaths Canada records from that cause at that age;
#   * afterwards: survivors' all-cause death rate is SURVIVOR_RR times their
#     own, the extra deaths counted as that cause;
#   * everyone without the event: background heart (stroke) death rate scaled
#     by b(age), solved on a synthetic cohort so the official 2017-2019 total,
#     heart and stroke deaths are reproduced exactly at every age. If acute
#     and survivor deaths alone would exceed the official figure, b is 0 and
#     the survivor excess is lowered at that age.

from engine.data import load  # noqa: E402
from engine.events import heart_stroke_probabilities  # noqa: E402

HEART, STROKE = CAUSES.index("heart"), CAUSES.index("stroke")
FATALITY_AGE_SHAPE = (50, 0.021, 88, 0.263)    # Quebec AMI registry: 2.1% under 55, 26.3% at 85+
FATALITY_LEVEL = {"heart": 0.065, "stroke": 0.132}
ACUTE_CAP = 0.75
SURVIVOR_RR = 1.5
CARDIO = {"heart": (HEART, 0, "cases_heart_attack"), "stroke": (STROKE, 1, "cases_stroke")}


def _shape(age: float) -> float:
    a0, f0, a1, f1 = FATALITY_AGE_SHAPE
    return f0 * (f1 / f0) ** ((age - a0) / (a1 - a0))


@lru_cache(maxsize=None)
def _fatality_scale(event: str) -> float:
    """Scale so the case-weighted average of the age shape equals the published fatality (both sexes)."""
    t = load("heart_stroke_rates.csv")
    col = CARDIO[event][2]
    mid = (t["age_lo"] + t["age_hi"].clip(upper=95)) / 2
    weighted = (t[col] * mid.map(_shape)).sum() / t[col].sum()
    return FATALITY_LEVEL[event] / weighted


@lru_cache(maxsize=None)
def acute_fatality(sex: str, event: str) -> np.ndarray:
    """Chance of dying of a first heart attack / stroke in the year it happens, by age (index = age)."""
    idx, col, _ = CARDIO[event]
    q = base_qx("CA", sex)
    f = np.zeros(MAX_AGE + 1)
    for a in range(MIN_AGE, MAX_AGE + 1):
        f[a] = min(_shape(a) * _fatality_scale(event), 0.95)
        inc = heart_stroke_probabilities(sex, a)[col]
        if a < MAX_AGE and inc > 0:
            f[a] = min(f[a], ACUTE_CAP * q[a] * base_shares(sex, a)[idx] / inc)
    return f


def _cardio_year(p, ia, ist, fa, fs):
    """
    One year for a grid p[i, j] of people alive at the start (i: heart attack survivor,
    j: stroke survivor). First heart attacks, then acute deaths, then first strokes
    among those still alive, then acute deaths. Returns the grid still alive in its
    old state (r), the acute deaths by cause, and the share of each cell that moves.
    """
    new_a = p[0, :] * ia
    acute_a = new_a * fa
    r = p.copy()
    r[0, :] -= acute_a
    move_a = np.divide(new_a - acute_a, r[0, :], out=np.zeros(2), where=r[0, :] > 0)
    new_s = r[:, 0] * ist
    acute_s = new_s * fs
    r[:, 0] -= acute_s
    move_s = np.divide(new_s - acute_s, r[:, 0], out=np.zeros(2), where=r[:, 0] > 0)
    return r, acute_a.sum(), acute_s.sum(), move_a, move_s


def _next_grid(s, move_a, move_s):
    """Survivors move to their new state at the end of the year."""
    out = np.zeros((2, 2))
    for i in (0, 1):
        for j in (0, 1):
            pa = move_a[j] if i == 0 else 0.0
            ps = move_s[i] if j == 0 else 0.0
            for di, wa in ((0, 1 - pa), (1, pa)):
                for dj, ws in ((0, 1 - ps), (1, ps)):
                    out[min(i + di, 1), min(j + dj, 1)] += s[i, j] * wa * ws
    return out


@lru_cache(maxsize=None)
def cardio_calibration(sex: str) -> dict[str, np.ndarray]:
    """By age: b_heart, b_stroke, rr_heart, rr_stroke and eta (scale on all other causes)."""
    q = base_qx("CA", sex)
    fa, fs = acute_fatality(sex, "heart"), acute_fatality(sex, "stroke")
    out = {k: np.ones(MAX_AGE + 1) for k in ("b_heart", "b_stroke", "eta")}
    out["rr_heart"] = np.full(MAX_AGE + 1, SURVIVOR_RR)
    out["rr_stroke"] = np.full(MAX_AGE + 1, SURVIVOR_RR)
    p = np.array([[1.0, 0.0], [0.0, 0.0]])
    for age in range(MIN_AGE, MAX_AGE):
        ia, ist = heart_stroke_probabilities(sex, age)
        shares = base_shares(sex, age)
        mu = -np.log(1 - q[age])
        mass = p.sum()
        target = mass * q[age] * np.array([1 - shares[HEART] - shares[STROKE], shares[HEART], shares[STROKE]])
        r, acute_h, acute_s, move_a, move_s = _cardio_year(p, ia, ist, fa[age], fs[age])
        acute = np.array([0.0, acute_h, acute_s])
        h_nc = mu * (1 - shares[HEART] - shares[STROKE])
        cause_mu = mu * np.array([shares[HEART], shares[STROKE]])

        def regular(h_nc, b, rr):
            d, qg = np.zeros(3), np.zeros((2, 2))
            for i in (0, 1):
                for j in (0, 1):
                    f = np.array([h_nc, b[0] * cause_mu[0] + (rr[0] - 1) * mu * i,
                                  b[1] * cause_mu[1] + (rr[1] - 1) * mu * j])
                    qg[i, j] = 1 - np.exp(-f.sum())
                    if f.sum() > 0:
                        d += r[i, j] * qg[i, j] * f / f.sum()
            return d, qg

        def bisect(fn, lo, hi):
            """Root of an increasing function on [lo, hi]."""
            for _ in range(200):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if fn(mid) < 0 else (lo, mid)
            return (lo + hi) / 2

        b, rr = np.ones(2), np.full(2, SURVIVOR_RR)
        for _ in range(200):
            for k in (0, 1):
                need = target[k + 1] - acute[k + 1]
                def gap_b(x, k=k):
                    bb = b.copy(); bb[k] = x
                    return regular(h_nc, bb, rr)[0][k + 1] - need
                def gap_rr(x, k=k):
                    bb = b.copy(); bb[k] = 0.0
                    rrr = rr.copy(); rrr[k] = x
                    return regular(h_nc, bb, rrr)[0][k + 1] - need
                rr[k] = SURVIVOR_RR
                if need <= 0:
                    b[k], rr[k] = 0.0, 1.0
                elif gap_b(0.0) >= 0:                    # survivors alone are too many: lower their excess
                    b[k] = 0.0
                    rr[k] = bisect(gap_rr, 1.0, SURVIVOR_RR)
                else:
                    hi = 1.0
                    while gap_b(hi) < 0:
                        hi *= 2
                    b[k] = bisect(gap_b, 0.0, hi)
            d, qg = regular(h_nc, b, rr)
            if np.allclose(d + acute, target, rtol=1e-10, atol=1e-300):
                break
            h_nc *= target[0] / d[0]
        else:
            raise RuntimeError(f"heart/stroke calibration did not converge: {sex} {age}")
        out["b_heart"][age], out["b_stroke"][age] = b
        out["rr_heart"][age], out["rr_stroke"][age] = rr
        out["eta"][age] = h_nc / (mu * (1 - shares[HEART] - shares[STROKE]))
        p = _next_grid(r * (1 - qg), move_a, move_s)
    for k in out:
        out[k][MAX_AGE] = out[k][MAX_AGE - 1]
    return out


# ================================================================ a person's death rates in every state

N_CANCER = 13          # 0 never diagnosed; 1-6 lung, years since 0..5+; 7-12 other site
CAUSE_RATIO_SITES = (LUNG, OTHER, HEART, STROKE)


def person_ratios(q_person: np.ndarray, causes_person: np.ndarray, sex: str, first_age: int) -> np.ndarray:
    """Person's death rate from lung cancer, other cancer, heart disease and stroke ÷ the population's (2017-2019)."""
    q_pop = base_qx("CA", sex)
    out = np.ones((len(q_person), 4))
    for i in range(len(q_person)):
        age = first_age + i
        if q_person[i] >= 1:
            continue
        mu, mu_pop = -np.log(1 - q_person[i]), -np.log(1 - q_pop[age])
        shares = base_shares(sex, age)
        for j, site in enumerate(CAUSE_RATIO_SITES):
            if shares[site] > 0:
                out[i, j] = mu * causes_person[i][site] / (mu_pop * shares[site])
    return out


def person_incidence(q_person, causes_person, sex: str, first_age: int) -> dict[str, np.ndarray]:
    """
    A person's yearly chance of a first lung cancer, other cancer, heart attack and
    stroke: population rate x the person's own death ratio for that cause (A22, A23).
    """
    ratios = person_ratios(q_person, causes_person, sex, first_age)
    out = {k: np.zeros(len(q_person)) for k in ("cancer_lung", "cancer_other", "heart_attack", "stroke")}
    for i in range(len(q_person)):
        age = min(first_age + i, MAX_AGE)
        lung, other = cancer_probabilities(sex, age)
        ha, st = heart_stroke_probabilities(sex, age)
        for j, (key, pop) in enumerate(zip(out, (lung, other, ha, st))):
            out[key][i] = min(1.0, pop * ratios[i, j])
    return out


def death_tables(q_person: np.ndarray, causes_person: np.ndarray, sex: str, first_age: int):
    """
    For each age: death probability q[i, cancer_state, heart_attack_survivor, stroke_survivor]
    and cause mix c[i, cancer_state, a, s, cause]; plus the acute fatality of a first heart
    attack and of a first stroke at each age.
    """
    cal, cc = calibration(sex), cardio_calibration(sex)
    n, k = len(q_person), len(CAUSES)
    q = np.ones((n, N_CANCER, 2, 2))
    c = np.zeros((n, N_CANCER, 2, 2, k))
    acute_h = np.array([acute_fatality(sex, "heart")[min(first_age + i, MAX_AGE)] for i in range(n)])
    acute_s = np.array([acute_fatality(sex, "stroke")[min(first_age + i, MAX_AGE)] for i in range(n)])
    other_causes = [x for x in range(k) if x not in CAUSE_RATIO_SITES]
    all_ratios = person_ratios(q_person, causes_person, sex, first_age)
    for i in range(n):
        age = first_age + i
        cp = causes_person[i]
        if q_person[i] >= 1:                                   # age 110: everyone dies
            mix_u = cp.copy()
            mix_u[[LUNG, OTHER]] = 0
            mix_u /= mix_u.sum()
            c[i, 0] = mix_u
            c[i, 1:] = cp
            continue
        mu = -np.log(1 - q_person[i])
        base = np.zeros(k)
        base[other_causes] = mu * cp[other_causes] * cal["eta"][age] * cc["eta"][age]
        heart_bg, stroke_bg = mu * cp[HEART] * cc["b_heart"][age], mu * cp[STROKE] * cc["b_stroke"][age]
        extra_h, extra_s = (cc["rr_heart"][age] - 1) * mu, (cc["rr_stroke"][age] - 1) * mu
        ratios = all_ratios[i]
        cancer = np.zeros((N_CANCER, 2))                       # forces: lung, other site
        cancer[0] = [cal["r_lung"][age] * ratios[0], cal["r_other"][age] * ratios[1]]
        for d in range(6):
            cancer[1 + d] = [cal["s_lung"][age] * W[d], 0.0]
            cancer[7 + d] = [0.0, cal["s_other"][age] * W[d]]
        for cs in range(N_CANCER):
            for a in (0, 1):
                for s_ in (0, 1):
                    f = base.copy()
                    f[LUNG], f[OTHER] = cancer[cs]
                    f[HEART] = heart_bg + extra_h * a
                    f[STROKE] = stroke_bg + extra_s * s_
                    q[i, cs, a, s_] = 1 - np.exp(-f.sum())
                    c[i, cs, a, s_] = f / f.sum()
    return q, c, acute_h, acute_s
