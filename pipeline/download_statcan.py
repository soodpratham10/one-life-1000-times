"""
Reusable helper: download any Statistics Canada table and print a summary of it.

Usage, from the project folder (table number without dashes, first 8 digits):
    python pipeline/download_statcan.py 13100392

Saves to data/raw/statcan_<table>/ (not committed: re-downloadable).
Statistics Canada data: Open Government Licence - Canada.
"""

import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MAX_LISTED = 80  # list every value of a column with up to this many distinct values


def download(table_id: str) -> Path:
    raw_dir = ROOT / "data" / "raw" / f"statcan_{table_id}"
    csv_path = raw_dir / f"{table_id}.csv"
    if csv_path.exists():
        print(f"Already downloaded: {csv_path.relative_to(ROOT)}")
        return csv_path

    raw_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www150.statcan.gc.ca/n1/tbl/csv/{table_id}-eng.zip"
    zip_path = raw_dir / f"{table_id}-eng.zip"
    print(f"Downloading {url} ...")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request) as response, open(zip_path, "wb") as out:
        out.write(response.read())
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(raw_dir)
    zip_path.unlink()
    print(f"Extracted to {raw_dir.relative_to(ROOT)}")
    return csv_path


def summarise(csv_path: Path) -> None:
    df = pd.read_csv(csv_path, low_memory=False)
    print(f"\n=== SIZE ===\n{len(df):,} rows x {len(df.columns)} columns "
          f"({csv_path.stat().st_size / 1e6:.1f} MB)")
    print(f"\n=== COLUMNS ===\n{list(df.columns)}")
    print(f"\n=== FIRST 5 ROWS ===\n{df.head().to_string()}")
    print("\n=== VALUES IN EACH COLUMN ===")
    for col in df.columns:
        values = df[col].dropna().unique()
        if len(values) <= MAX_LISTED:
            print(f"\n{col} ({len(values)} values):")
            for v in values:
                print(f"   {v}")
        else:
            print(f"\n{col}: {len(values)} distinct values, e.g. {list(values[:3])}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].isdigit() or len(sys.argv[1]) != 8:
        sys.exit("Usage: python pipeline/download_statcan.py 13100392")
    summarise(download(sys.argv[1]))
