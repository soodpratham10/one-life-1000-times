"""
The cross-check reference files (crosscheck/reference/risk_reference.csv and
cancer_reference.csv) must match what the engine gives today, or the R and Excel VBA checks would be
checking an old engine. If this fails after a change to the engine, rebuild it:
    python crosscheck/make_reference.py
"""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "crosscheck" / "reference" / "risk_reference.csv"
CANCER_REF = ROOT / "crosscheck" / "reference" / "cancer_reference.csv"


def _module():
    spec = importlib.util.spec_from_file_location("make_reference", ROOT / "crosscheck" / "make_reference.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reference_file_matches_the_engine(tmp_path, monkeypatch):
    mod = _module()
    fresh = tmp_path / "risk_reference.csv"
    fresh_cancer = tmp_path / "cancer_reference.csv"
    monkeypatch.setattr(mod, "OUT", fresh)
    monkeypatch.setattr(mod, "CANCER_OUT", fresh_cancer)
    monkeypatch.setattr(mod, "CIA_OUT", tmp_path / "cia_reference.csv")
    monkeypatch.setattr(mod, "ROOT", tmp_path)       # only used to print the path
    mod.main()
    # The cancer link is solved by iteration to a relative accuracy of 1e-12, so a
    # Mac and a Linux computer can differ in about the 12th digit: allow 1e-9 there.
    for committed, rebuilt, key, rel in ((REF, fresh, "case", 1e-12), (CANCER_REF, fresh_cancer, "sex", 1e-9)):
        old, new = pd.read_csv(committed), pd.read_csv(rebuilt)
        assert len(old) == len(new)
        assert (old[key] == new[key]).all() and (old["measure"] == new["measure"]).all()
        assert old["value"].to_numpy() == pytest.approx(new["value"].to_numpy(), rel=rel, abs=1e-15)


def test_reference_covers_every_level():
    mod = _module()
    from engine.risk import levels
    seen = {}
    for p in mod.CASES.values():
        for factor, level in levels(p).items():
            seen.setdefault(factor, set()).add(level)
    assert seen["smoking"] == {"never", "current", "quit_before_35", "quit_35_44", "quit_45_54", "quit_55_plus"}
    assert seen["activity"] == {"none", "under_150", "150_299", "300_449", "450_plus"}
    assert seen["bmi"] == {"under_18.5", "18.5_25", "25_27.5", "27.5_30", "30_35", "35_40", "40_plus"}
    assert seen["alcohol"] == {"under_25g", "25_44g", "45_64g", "65g_plus"}
    assert seen["fruit_veg"] == {"0_2", "3", "4", "5_plus"}
