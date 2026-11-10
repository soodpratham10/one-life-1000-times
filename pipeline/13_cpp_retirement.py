"""
Step 13 of the data pipeline: age at retirement, from CPP retirement pension take-up.

Source: Office of the Chief Actuary, 32nd Actuarial Report on the Canada Pension Plan
        (as at 31 December 2024, revised version), Table 76 "Retirement pension take-up
        rates (cohort aged 65 in 2031+)", read straight from the PDF.

Table 76 gives, for each sex, the share (%) of a cohort that starts its CPP retirement
pension at each age 60 to 70; the shares add to 100%. For a year-by-year simulation the
shares are turned into a yearly chance of starting, given not started yet:

    h(x) = share(x) / (share(x) + share(x+1) + ... + share(70))      so h(70) = 1

Event definition: starting the CPP retirement pension, used as the model's "retirement".
Taking the pension and stopping work are not the same thing (people can work while
receiving it); see A16 in docs/assumptions.md.

Input : data/raw/oca/cpp32-rev-ed-en.pdf
Output: data/clean/cpp_retirement.csv   columns: sex, age, share_pct, p_start_given_not_started

Run from the project folder:
    python pipeline/13_cpp_retirement.py
"""

import re
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data" / "raw" / "oca" / "cpp32-rev-ed-en.pdf"
OUT_CSV = ROOT / "data" / "clean" / "cpp_retirement.csv"


def table_76_page(pages: list[str]) -> str:
    """The page holding Table 76 itself (not the table of contents)."""
    hits = [t for t in pages
            if "Table 76 Retirement pension take-up rates" in " ".join(t.split())
            and "Total 100 100" in " ".join(t.split())]
    if len(hits) != 1:
        raise ValueError(f"Expected 1 page with Table 76, found {len(hits)}")
    return hits[0]


def read_table_76(page: str) -> pd.DataFrame:
    start = page.index("Table 76")
    block = page[start:page.index("Total 100 100", start)]
    rows = []
    for m in re.finditer(r"^(6\d|70) (\d+) (\d+)\s*$", block, re.M):
        rows += [{"sex": "M", "age": int(m.group(1)), "share_pct": int(m.group(2))},
                 {"sex": "F", "age": int(m.group(1)), "share_pct": int(m.group(3))}]
    df = pd.DataFrame(rows)
    if sorted(df["age"].unique()) != list(range(60, 71)):
        raise ValueError(f"Table 76: expected ages 60-70, found {sorted(df['age'].unique())}")
    return df


def add_hazard(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for sex, g in df.groupby("sex"):
        g = g.sort_values("age").copy()
        remaining = g["share_pct"][::-1].cumsum()[::-1]       # share still to start at x or later
        g["p_start_given_not_started"] = g["share_pct"] / remaining
        out.append(g)
    return pd.concat(out, ignore_index=True)


if __name__ == "__main__":
    if not PDF.exists():
        raise SystemExit(f"Missing {PDF.relative_to(ROOT)}: download the 32nd CPP Actuarial Report (see README)")
    pages = [p.extract_text() or "" for p in PdfReader(PDF).pages]
    table = add_hazard(read_table_76(table_76_page(pages)))

    for sex in ["M", "F"]:
        g = table[table["sex"] == sex]
        mean_age = (g["age"] * g["share_pct"]).sum() / g["share_pct"].sum()
        print(f"{'Men' if sex == 'M' else 'Women'}: shares add to {g['share_pct'].sum()}%, "
              f"average take-up age {mean_age:.2f} (report: 64.3)")
    print("\nYearly chance of starting the CPP pension, given not started yet:")
    print(table.pivot(index="age", columns="sex", values="p_start_given_not_started").round(3).to_string())

    table.to_csv(OUT_CSV, index=False)
    print(f"\nSaved {OUT_CSV.relative_to(ROOT)}")
