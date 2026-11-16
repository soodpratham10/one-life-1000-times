"""
Checks on web/data/engine-data.json, the data the browser engine runs on
(web/build_data.py, Phase 5): it must match what the Python engine gives today,
and its layout must mean what the browser engine assumes. If the first test
fails after a change to the engine or the data, rebuild the file:
    python web/build_data.py
"""

import importlib.util
import json
import math
from pathlib import Path

import pytest

from engine import disability as D
from engine import events as E
from engine import mortality as MO
from engine.risk import Person, levels, population_mix

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "web" / "data" / "engine-data.json"


@pytest.fixture(scope="module")
def data():
    return json.loads(FILE.read_text())


def _module():
    spec = importlib.util.spec_from_file_location("build_data", ROOT / "web" / "build_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _close(a, b, path=""):
    """Same structure, numbers equal to a relative 1e-9 (iteratively solved tables differ slightly by computer)."""
    if isinstance(a, dict):
        assert set(a) == set(b), f"{path}: keys differ"
        for k in a:
            _close(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, list):
        assert len(a) == len(b), f"{path}: lengths differ"
        for i, (x, y) in enumerate(zip(a, b)):
            _close(x, y, f"{path}[{i}]")
    elif isinstance(a, float) or isinstance(b, float):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-15), f"{path}: {a} vs {b}"
    else:
        assert a == b, f"{path}: {a} vs {b}"


def test_file_matches_the_engine(data):
    fresh = json.loads(json.dumps(_module().build()))
    _close(data, fresh)


@pytest.mark.parametrize("sex", ["M", "F"])
def test_layout_spot_checks(data, sex):
    d = data[sex]
    assert len(d["base_q"]["MB"]) == MO.MAX_AGE + 1 and d["base_q"]["MB"][MO.MAX_AGE] == 1.0
    assert d["base_q"]["PE"][60] == pytest.approx(MO.base_qx("PE", sex)[60])
    assert d["cpp_scale"] == pytest.approx(list(MO.cpp_scale(sex)))
    assert d["mix"]["50"]["smoking"] == pytest.approx(population_mix(sex, (50, 64))["smoking"])
    assert sum(d["cause_shares"][70]) == pytest.approx(1.0)
    # disability start = incidence per eligible person x share eligible, as in the engine
    assert d["disability_incidence"][45] * d["eligible_share"]["2040"] == pytest.approx(
        E.disability_start_probability(sex, 45, 2040), rel=1e-12)
    assert d["disability_incidence"][70] == 0.0
    # recovery[band][years - 1][year - 2025][age - 18]
    assert d["recovery"][D.BANDS.index(40)][2][5][47 - 18] == pytest.approx(
        D.recovery_probability(sex, 40, 3, 2030, 47), rel=1e-12)
    assert d["first_child"][30] == pytest.approx(E.first_child_probability(sex, 30))


def test_hazard_ratios_resolve_like_the_engine(data):
    hr = data["hazard_ratios"]
    assert hr["smoking"]["current"]["M"] == 2.8 and hr["smoking"]["current"]["F"] == 3.0
    assert hr["bmi"]["40_plus"]["B"] == 2.76
    for factor, level in levels(Person("F", 40, smoking="current")).items():
        assert level in hr[factor]


def test_no_cia_data(data):
    text = FILE.read_text().lower()
    assert "mi2024" not in text and "cia_" not in text
