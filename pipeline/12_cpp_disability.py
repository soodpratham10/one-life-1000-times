"""
Step 12 of the data pipeline: CPP disability assumptions from the Office of the Chief
Actuary's 32nd Actuarial Report on the Canada Pension Plan (as at 31 December 2024,
revised version). Numbers are read straight from the PDF, not typed by hand.

Tables used
  Table 85  Ultimate disability incidence rates (2029+), per 1,000 ELIGIBLE, by age and sex
            (disability pension; ages 25, 30, ..., 55, and 60-64)
  Table 88  Disability termination rates (recovery, death or reaching 65), per 1,000 people,
            by age, sex and duration of disability, 2025 and 2035 (ultimate)
  Table 73  Share of people aged 20-64 eligible for the CPP disability benefit, by year and sex

Single ages 18-64 are filled in from Table 85 by log-linear interpolation between the
published ages; ages 18-24 are held at the age-25 rate (the report gives no younger ages).

Event definition: becoming entitled to a CPP disability pension, i.e. a "severe and
prolonged" disability under the CPP. CPP covers Canada outside Quebec (Quebec has the QPP).

Input : data/raw/oca/cpp32-rev-ed-en.pdf   (download by hand from osfi-bsif.gc.ca; see README)
Output: data/clean/cpp_disability_incidence.csv     published ages and filled-in single ages
        data/clean/cpp_disability_termination.csv
        data/clean/cpp_disability_eligibility.csv

Run from the project folder:
    python pipeline/12_cpp_disability.py
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data" / "raw" / "oca" / "cpp32-rev-ed-en.pdf"
OUT = ROOT / "data" / "clean"

NUM = r"(\d+(?:\.\d+)?)"


def find_page(pages: list[str], *anchors: str) -> str:
    """Text of the single page that contains every anchor phrase
    (line breaks in the PDF text are ignored when matching)."""
    flat = [" ".join(t.split()) for t in pages]
    hits = [t for t, f in zip(pages, flat) if all(a in f for a in anchors)]
    if len(hits) != 1:
        raise ValueError(f"Expected 1 page with {anchors}, found {len(hits)}")
    return hits[0]


def table_85(page: str) -> pd.DataFrame:
    """Rows like '25 0.3 0.4 N/A N/A' and '61 9.6 10.1 12.4 13.1'."""
    rows = []
    for m in re.finditer(rf"^(\d{{2}}) {NUM} {NUM} (?:N/A|{NUM}) (?:N/A|{NUM})\s*$", page, re.M):
        age = int(m.group(1))
        rows += [{"sex": "M", "age": age, "per_1000": float(m.group(2))},
                 {"sex": "F", "age": age, "per_1000": float(m.group(3))}]
    df = pd.DataFrame(rows)
    expected = [25, 30, 35, 40, 45, 50, 55, 60, 61, 62, 63, 64]
    if sorted(df["age"].unique()) != expected:
        raise ValueError(f"Table 85: expected ages {expected}, found {sorted(df['age'].unique())}")
    totals = re.search(rf"All ages {NUM} {NUM}", page)
    df.attrs["all_ages"] = {"M": float(totals.group(1)), "F": float(totals.group(2))}
    return df


def table_88(page: str) -> pd.DataFrame:
    """Two blocks (2025, then 2035), rows like '30 39 65 58 52 52 37 35 50 60 47 45 35'."""
    rows = []
    lines = re.findall(r"^(\d{2})((?: +\d+){12})\s*$", page, re.M)
    if len(lines) != 8:
        raise ValueError(f"Table 88: expected 8 rows (4 ages x 2 years), found {len(lines)}")
    for i, (age, values) in enumerate(lines):
        year = 2025 if i < 4 else 2035
        v = [int(x) for x in values.split()]
        for j, rate in enumerate(v):
            rows.append({"year": year, "sex": "M" if j < 6 else "F", "age": int(age),
                         "duration": j % 6 + 1, "per_1000": rate})
    return pd.DataFrame(rows)


def table_73(page: str) -> pd.DataFrame:
    """Rows like '2025 101.1 98.2 97.7 79.1 77.9 70.0 71.7 65.7 51.5 45.8'; columns 7-8 =
    disability benefit eligibility at ages 20-64 (males, females)."""
    rows = []
    for m in re.finditer(rf"^(20\d\d)((?: +{NUM}){{10}})\s*$", page, re.M):
        v = [float(x) for x in m.group(2).split()]
        rows += [{"year": int(m.group(1)), "sex": "M", "eligible_pct": v[6]},
                 {"year": int(m.group(1)), "sex": "F", "eligible_pct": v[7]}]
    df = pd.DataFrame(rows)
    if df.empty or 2025 not in set(df["year"]):
        raise ValueError("Table 73: could not read the eligibility rows")
    return df


def single_ages(t85: pd.DataFrame) -> pd.DataFrame:
    """Ages 18-64: published ages as given; between them log-linear; 18-24 = age 25."""
    out = []
    for sex, g in t85.groupby("sex"):
        known = g.set_index("age")["per_1000"]
        ages = np.arange(18, 65)
        logs = np.interp(ages, known.index, np.log(known.to_numpy()))
        for a, lv in zip(ages, logs):
            method = "published" if a in known.index else ("held at age 25" if a < 25 else "interpolated")
            out.append({"sex": sex, "age": int(a), "per_1000": float(np.exp(lv)), "method": method})
    return pd.DataFrame(out)


if __name__ == "__main__":
    if not PDF.exists():
        raise SystemExit(f"Missing {PDF.relative_to(ROOT)}: download the 32nd CPP Actuarial Report (see README)")
    pages = [p.extract_text() or "" for p in PdfReader(PDF).pages]

    t85 = table_85(find_page(pages, "Table 85 Ultimate disability incidence rates (2029+) (1)", "All ages"))
    t88 = table_88(find_page(pages, "Males - 2025", "Males - 2035", "6 Year"))
    t73 = table_73(find_page(pages, "Table 73 Benefit eligibility rates by type of benefit", "Disability benefit eligibility rate at ages 20-64 (1)"))

    filled = single_ages(t85)
    print("Table 85 'All ages' (per 1,000 eligible):", t85.attrs["all_ages"])
    print("\nDisability incidence per 1,000 eligible (selected ages):")
    print(filled[filled["age"].isin([18, 25, 30, 40, 50, 55, 60, 64])]
          .pivot(index="age", columns="sex", values="per_1000").round(2).to_string())
    print(f"\nTermination rates read: {len(t88)} values; eligibility years: {t73['year'].min()}-{t73['year'].max()}")

    filled.to_csv(OUT / "cpp_disability_incidence.csv", index=False, float_format="%.6g")
    t88.to_csv(OUT / "cpp_disability_termination.csv", index=False)
    t73.to_csv(OUT / "cpp_disability_eligibility.csv", index=False)
    print("\nSaved cpp_disability_incidence.csv, cpp_disability_termination.csv, cpp_disability_eligibility.csv")
