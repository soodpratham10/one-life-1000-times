"""
Rebuild every cleaned data file, in order, from the original sources.

    python pipeline/run_all.py            run every step
    python pipeline/run_all.py --plan     only show what would run and what is missing

Statistics Canada and Transport Canada files are downloaded automatically (internet needed;
the cancer table is about 1.8 GB). Three sources must be downloaded by hand first
(see README): the CIA MI-2024 workbook, the two CCDSS files, and the CPP actuarial report.
A step whose hand-downloaded input is missing is skipped with a message; the cleaned file
already in data/clean/ is kept (except the CIA file, which is never committed).

When it finishes, run the tests:   pytest
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PY = sys.executable

# (script, StatCan tables it needs downloaded first, hand-downloaded files it needs)
STEPS = [
    ("01_download_life_tables.py", [], []),
    ("02_clean_life_tables.py", [], []),
    ("03_clean_mi2024.py", [], [RAW / "cia_mi2024" / "224043te.xlsx"]),
    ("04_clean_causes_of_death.py", ["13100392"], []),
    ("05_build_pei_life_table.py", ["13100140"], []),
    ("06_clean_ncdb.py", [], []),                       # downloads its own files
    ("07_clean_population.py", ["17100005"], []),
    ("08_crash_rates.py", [], []),
    ("09_clean_cancer_incidence.py", ["13100111"], []),
    ("10_cancer_rates.py", [], []),
    ("11_heart_stroke.py", [], [RAW / "ccdss" / "ccdss_ami_by_age.csv",
                               RAW / "ccdss" / "ccdss_stroke_by_age.csv"]),
    ("12_cpp_disability.py", [], [RAW / "oca" / "cpp32-rev-ed-en.pdf"]),
    ("13_cpp_retirement.py", [], [RAW / "oca" / "cpp32-rev-ed-en.pdf"]),
    ("14_family_events.py", ["39100057", "39100053", "13100421"], []),
]


def statcan_missing(tables: list[str]) -> list[str]:
    return [t for t in tables if not (RAW / f"statcan_{t}" / f"{t}.csv").exists()]


def run(cmd: list[str]) -> None:
    print("   $", " ".join(Path(c).name if c.endswith(".py") else c for c in cmd[1:]))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main(plan_only: bool) -> None:
    skipped = []
    for script, tables, manual in STEPS:
        missing_manual = [p for p in manual if not p.exists()]
        to_download = statcan_missing(tables)
        status = ("SKIP (hand download missing: " + ", ".join(p.name for p in missing_manual) + ")"
                  if missing_manual else "run" + (f" (download {', '.join(to_download)} first)" if to_download else ""))
        print(f"{script:32s} {status}")
        if plan_only:
            continue
        if missing_manual:
            skipped.append(script)
            continue
        for t in to_download:
            run([PY, str(ROOT / "pipeline" / "download_statcan.py"), t])
        run([PY, str(ROOT / "pipeline" / script)])

    if not plan_only:
        print("\nDone." + (f" Skipped (inputs missing): {', '.join(skipped)}" if skipped else " Every step ran."))
        print("Now run:  pytest")


if __name__ == "__main__":
    main(plan_only="--plan" in sys.argv)
