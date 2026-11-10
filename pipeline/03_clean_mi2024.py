"""
Step 3 of the data pipeline: reshape the CIA MI-2024 mortality improvement scale
into a long, tidy table.

The CIA workbook has one sheet per sex ('female', 'male'). On each sheet:
  - row 6 holds calendar years 1981..2119 (columns B onward)
  - column A holds ages 20..120 (rows 7 onward)
  - each cell is the improvement rate MI(x, t): q(x, t) = q(x, t-1) * (1 - MI(x, t))

Input : data/raw/cia_mi2024/224043te.xlsx  (download by hand from cia-ica.ca, see README)
Output: data/clean/cia_mi2024.csv           (columns: sex, age, year, mi)

The input and output are NOT committed: the scale is the CIA's copyrighted material.

Run from the project folder:
    python pipeline/03_clean_mi2024.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_XLSX = ROOT / "data" / "raw" / "cia_mi2024" / "224043te.xlsx"
OUT_CSV = ROOT / "data" / "clean" / "cia_mi2024.csv"

SHEETS = {"female": "F", "male": "M"}
YEAR_ROW = 6        # 0-based row index holding the calendar years
FIRST_AGE_ROW = 7   # 0-based row index of the first age (20)


def read_sheet(sheet: str) -> pd.DataFrame:
    raw = pd.read_excel(RAW_XLSX, sheet_name=sheet, header=None)

    title = str(raw.iloc[YEAR_ROW - 1, 0]).strip()
    if title != "Mortality Improvement Rates":
        raise ValueError(f"Sheet {sheet!r}: unexpected layout (title cell reads {title!r})")

    years = raw.iloc[YEAR_ROW, 1:].astype(int).to_list()
    block = raw.iloc[FIRST_AGE_ROW:, : len(years) + 1].dropna(how="all")
    block.columns = ["age"] + years
    block["age"] = block["age"].astype(int)

    long = block.melt(id_vars="age", var_name="year", value_name="mi")
    long["year"] = long["year"].astype(int)
    long["mi"] = long["mi"].astype(float)
    long.insert(0, "sex", SHEETS[sheet])
    return long


def clean() -> pd.DataFrame:
    out = pd.concat([read_sheet(s) for s in SHEETS], ignore_index=True)
    return out.sort_values(["sex", "age", "year"]).reset_index(drop=True)


def report(df: pd.DataFrame) -> None:
    print(f"Tidy table: {len(df):,} rows")
    print(f"Ages {df['age'].min()}-{df['age'].max()}, years {df['year'].min()}-{df['year'].max()}")
    print(f"Missing values: {df['mi'].isna().sum()}")
    print("\nLong-term rate in 2060 (improvement per year):")
    pick = df.query("year == 2060 and age in [20, 40, 65, 85, 100]")
    print(pick.pivot(index="age", columns="sex", values="mi").round(4).to_string())


if __name__ == "__main__":
    if not RAW_XLSX.exists():
        raise SystemExit(f"Missing {RAW_XLSX.relative_to(ROOT)}: download it from the CIA (see README)")
    tidy = clean()
    report(tidy)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    tidy.to_csv(OUT_CSV, index=False)
    print(f"\nSaved {OUT_CSV.relative_to(ROOT)}")
