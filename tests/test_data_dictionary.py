"""
Keeps docs/data_dictionary.md honest: every cleaned file in data/clean/ must have a
section there, and the columns listed must be exactly the file's columns.

Run from the project folder:
    pytest
"""

import re
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DICTIONARY = ROOT / "docs" / "data_dictionary.md"
CLEAN = ROOT / "data" / "clean"
LOCAL_ONLY = {"cia_mi2024.csv"}     # copyrighted, never committed; documented separately


def documented() -> dict[str, set[str]]:
    """{file name: set of column names} as written in the data dictionary."""
    text = DICTIONARY.read_text(encoding="utf-8")
    sections = re.split(r"^### `([^`]+\.csv)`\s*$", text, flags=re.M)
    out = {}
    for name, body in zip(sections[1::2], sections[2::2]):
        out[name] = set(re.findall(r"^\| `([^`]+)` \|", body, flags=re.M))
    return out


def committed_files() -> list[Path]:
    return sorted(p for p in CLEAN.glob("*.csv") if p.name not in LOCAL_ONLY)


def test_every_clean_file_is_documented():
    missing = [p.name for p in committed_files() if p.name not in documented()]
    assert not missing, f"Add these to docs/data_dictionary.md: {missing}"


def test_no_documented_file_is_missing():
    exists = {p.name for p in committed_files()}
    stale = [name for name in documented() if name not in exists]
    assert not stale, f"Documented but not in data/clean/: {stale}"


@pytest.mark.parametrize("path", committed_files(), ids=lambda p: p.name)
def test_documented_columns_match_file(path):
    actual = set(pd.read_csv(path, nrows=0).columns)
    listed = documented().get(path.name, set())
    assert listed == actual, f"{path.name}: missing from docs {actual - listed}, not in file {listed - actual}"
