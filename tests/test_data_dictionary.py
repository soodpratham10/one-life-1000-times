"""
Keeps docs/data_dictionary.md honest: every cleaned file in data/clean/, every
assumption table in data/assumptions/ and every committed validation output must
have a section there (assumption tables are written as `assumptions/<name>.csv`,
validation outputs by their path from the project folder), and the columns listed
must be exactly the file's columns.

Run from the project folder:
    pytest
"""

import re
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DICTIONARY = ROOT / "docs" / "data_dictionary.md"
DATA = ROOT / "data"
CLEAN = DATA / "clean"
ASSUMPTIONS = DATA / "assumptions"
LOCAL_ONLY = {"cia_mi2024.csv"}     # copyrighted, never committed; documented separately
OUTPUTS = [ROOT / "validation" / "results", ROOT / "crosscheck" / "reference", ROOT / "crosscheck" / "results"]


def documented() -> dict[str, set[str]]:
    """{file name: set of column names} as written in the data dictionary."""
    text = DICTIONARY.read_text(encoding="utf-8")
    sections = re.split(r"^### `([^`]+\.csv)`\s*$", text, flags=re.M)
    out = {}
    for name, body in zip(sections[1::2], sections[2::2]):
        out[name] = set(re.findall(r"^\| `([^`]+)` \|", body, flags=re.M))
    return out


def key(path: Path) -> str:
    """Name used in the dictionary: 'life_tables.csv', 'assumptions/hazard_ratios.csv',
    or a validation output's path such as 'validation/results/population_check.csv'."""
    if path.parent == CLEAN:
        return path.name
    if path.parent == ASSUMPTIONS:
        return f"assumptions/{path.name}"
    return path.relative_to(ROOT).as_posix()


def committed_files() -> list[Path]:
    clean = [p for p in CLEAN.glob("*.csv") if p.name not in LOCAL_ONLY]
    outputs = [p for d in OUTPUTS for p in d.glob("*.csv") if not p.name.startswith("cia_")]
    return sorted(clean) + sorted(ASSUMPTIONS.glob("*.csv")) + sorted(outputs)


def test_every_file_is_documented():
    missing = [key(p) for p in committed_files() if key(p) not in documented()]
    assert not missing, f"Add these to docs/data_dictionary.md: {missing}"


def test_no_documented_file_is_missing():
    exists = {key(p) for p in committed_files()}
    stale = [name for name in documented() if name not in exists]
    assert not stale, f"Documented but not in the repo: {stale}"


@pytest.mark.parametrize("path", committed_files(), ids=key)
def test_documented_columns_match_file(path):
    actual = set(pd.read_csv(path, nrows=0).columns)
    listed = documented().get(key(path), set())
    assert listed == actual, f"{key(path)}: missing from docs {actual - listed}, not in file {listed - actual}"
