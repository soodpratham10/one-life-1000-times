"""
Step 1 of the data pipeline: download Statistics Canada Table 13-10-0114-01
(complete life tables, three-year estimates, Canada and provinces except PEI)
and print a summary of its structure so we can write the cleaning step.

Run from the project folder:
    python pipeline/01_download_life_tables.py

Source: Statistics Canada, Table 13-10-0114-01. Open Government Licence - Canada.
"""

from pathlib import Path
import urllib.request
import zipfile

import pandas as pd

TABLE_ID = "13100114"
URL = f"https://www150.statcan.gc.ca/n1/tbl/csv/{TABLE_ID}-eng.zip"

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / f"statcan_{TABLE_ID}"
ZIP_PATH = RAW_DIR / f"{TABLE_ID}-eng.zip"
CSV_PATH = RAW_DIR / f"{TABLE_ID}.csv"


def download() -> None:
    """Download and unzip the full table, unless it is already here."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if CSV_PATH.exists():
        print(f"Already downloaded: {CSV_PATH.relative_to(ROOT)}")
        return

    print(f"Downloading {URL} ...")
    request = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request) as response, open(ZIP_PATH, "wb") as out:
        out.write(response.read())
    print(f"Saved zip: {ZIP_PATH.stat().st_size / 1e6:.1f} MB")

    with zipfile.ZipFile(ZIP_PATH) as z:
        print("Zip contains:", z.namelist())
        z.extractall(RAW_DIR)

    ZIP_PATH.unlink()  # keep only the extracted files
    print(f"Extracted to {RAW_DIR.relative_to(ROOT)}")


def summarise() -> None:
    """Print what is in the table, so the cleaning step is written against reality."""
    df = pd.read_csv(CSV_PATH, low_memory=False)

    print("\n=== SIZE ===")
    print(f"{len(df):,} rows x {len(df.columns)} columns")
    print(f"File size: {CSV_PATH.stat().st_size / 1e6:.1f} MB")

    print("\n=== COLUMNS ===")
    print(list(df.columns))

    print("\n=== FIRST 5 ROWS ===")
    print(df.head().to_string())

    print("\n=== VALUES IN EACH SMALL COLUMN ===")
    for col in df.columns:
        values = df[col].dropna().unique()
        if len(values) <= 40:
            print(f"\n{col} ({len(values)} values):")
            for v in values:
                print(f"   {v}")
        else:
            print(f"\n{col}: {len(values)} distinct values, e.g. {list(values[:3])} ... {list(values[-3:])}")


if __name__ == "__main__":
    download()
    summarise()
