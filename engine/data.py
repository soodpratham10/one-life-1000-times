"""
Where the engine gets its data.

Every engine module reads the cleaned tables in data/clean/ through load(), so
the engine never touches raw source files. Each table is read once and cached.
"""

from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"

# Built locally from the CIA's own workbook; never committed (CIA copyright).
MI_FILE = "cia_mi2024.csv"


@lru_cache(maxsize=None)
def load(name: str) -> pd.DataFrame:
    """Read data/clean/<name>, with a clear message if it has not been built."""
    path = CLEAN / name
    if not path.exists():
        hint = (
            "download the CIA file and run pipeline/03_clean_mi2024.py (see README)"
            if name == MI_FILE
            else "run python pipeline/run_all.py"
        )
        raise FileNotFoundError(f"data/clean/{name} is missing: {hint}")
    return pd.read_csv(path)


def has_improvement_scale() -> bool:
    """True if the CIA MI-2024 scale has been built on this computer."""
    return (CLEAN / MI_FILE).exists()
