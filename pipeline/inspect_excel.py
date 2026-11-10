"""
Reusable helper: show what is inside an Excel workbook before writing a cleaner.

Prints every sheet's name, size and its first rows exactly as stored, so the
cleaning script can be written against the real layout.

Run from the project folder:
    python pipeline/inspect_excel.py "data/raw/cia_mi2024/<file name>.xlsx"
Optional: number of rows to show per sheet (default 25)
    python pipeline/inspect_excel.py "data/raw/cia_mi2024/<file name>.xlsx" 40
"""

import sys
from pathlib import Path

import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_colwidth", 40)


def inspect(path: Path, n_rows: int) -> None:
    sheets = pd.read_excel(path, sheet_name=None, header=None)
    print(f"File: {path.name}")
    print(f"Sheets ({len(sheets)}): {list(sheets)}")

    for name, df in sheets.items():
        df = df.dropna(how="all").dropna(axis=1, how="all")
        print("\n" + "=" * 100)
        print(f"SHEET: {name!r}   ({df.shape[0]} non-empty rows x {df.shape[1]} non-empty columns)")
        print("=" * 100)
        print(df.head(n_rows).to_string())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('Usage: python pipeline/inspect_excel.py "path/to/file.xlsx" [rows]')
    file_path = Path(sys.argv[1])
    if not file_path.exists():
        sys.exit(f"Not found: {file_path}")
    rows = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    inspect(file_path, rows)
