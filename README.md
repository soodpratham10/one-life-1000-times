# One Life, 1,000 Times

> Nobody can tell you how your life will go. Here are 1,000 ways it could.

**Status: in development (Phase 1 — data).** Six data sources are loaded and tested; the simulation engine is not built yet. This README is updated as each phase is finished.

## What this is

A life simulator built on real Canadian data. You answer a short survey; the model lives your life forward year by year — health, accidents, family, work, and how it ends — then does it again, 1,000 times, so you can see the realistic range of how things could go and which of your choices move the odds.

**Aim (draft):** show someone the realistic range of how their life could unfold, using the data and methods actuaries use, and show which of their choices actually change the odds.

## What this is not

- Not a prediction of when or how you will die. No model can do that for one person; this shows probabilities.
- Not medical, financial or insurance advice.
- Not an insurance price. There are no premiums or reserves in this project.

## Planned events (version 1)

| Event | Notes |
| --- | --- |
| Death, by cause | About 8 cause groups plus "all other causes" |
| Disability spell | Can recover or become permanent |
| Serious car crash | Can happen more than once |
| Cancer diagnosis | Raises later mortality |
| Heart attack or stroke | Raises later mortality |
| Marriage or common-law union | Affects later mortality |
| First child | |
| Divorce or separation | Only after a union |
| Retirement | |

Widowhood, job loss and home purchase are planned for version 2.

## Method (planned)

The structure follows how life insurers underwrite: a base mortality table, personal risk multipliers, future mortality improvement, competing risks between events, and an actual-to-expected check against official data. Published data is used where insurers use proprietary underwriting manuals. Every assumption is listed in [`docs/assumptions.md`](docs/assumptions.md).

## Data

All inputs come from official or peer-reviewed public sources. Loaded so far:

| Source | What it gives | In this repo? |
| --- | --- | --- |
| Statistics Canada, Table 13-10-0114-01 (complete life tables, three-year estimates) | Death probabilities by single age 0–110+, sex, Canada and 9 provinces, 1980–1982 to 2022–2024 | Cleaned copy yes (`data/clean/life_tables.csv`); raw file is re-downloaded by `pipeline/01_download_life_tables.py` |
| Statistics Canada, Table 13-10-0140-01 (abridged life tables, PEI) | PEI death probabilities by age group; turned into single ages by borrowing the within-group shape of NS and NB (see A10 in `docs/assumptions.md`) | Derived single-age table yes (`data/clean/life_tables_pei.csv`); raw file via `python pipeline/download_statcan.py 13100140` |
| Statistics Canada, Table 13-10-0392-01 (deaths by selected grouped causes) | Deaths by 12 cause groups, sex and 5-year age group, Canada, 2000–2024 | Cleaned copy yes (`data/clean/causes_of_death.csv`); raw file via `python pipeline/download_statcan.py 13100392` |
| Transport Canada, National Collision Database (open data, 2019 and 2020) | People injured and killed in police-reported collisions, by sex and age | Cleaned counts yes (`data/clean/crash_casualties.csv`); raw files downloaded by `pipeline/06_clean_ncdb.py` |
| Statistics Canada, Table 17-10-0005-01 (population on July 1, by age and gender) | Population by province, sex and single age, 2000–2026: the denominator for event rates | Cleaned copy yes (`data/clean/population.csv`); raw file via `python pipeline/download_statcan.py 17100005` |
| Canadian Institute of Actuaries, MI-2024 mortality improvement scale ("Mortality Improvements Research – Tables", 2024) | Annual improvement rates by sex, age 20–120 and calendar year 1981–2119 | **No.** The scale is the CIA's copyrighted material. Download it yourself (below) |

### Getting the CIA MI-2024 file

1. Download "Mortality Improvements Research – Tables" from the CIA website (cia-ica.ca, publication 224043).
2. Save it as `data/raw/cia_mi2024/224043te.xlsx`.
3. Run `python pipeline/03_clean_mi2024.py`.

Without it, the MI-2024 tests are skipped rather than failed.

## Repository layout

```
data/raw/          source tables, as published
data/clean/        tidy tables (database is rebuilt, not committed)
pipeline/          scripts that build data/clean
engine/            Python reference engine
tests/             pytest suite
crosscheck/r/      independent R checks
crosscheck/excel/  hand calculations
web/               survey, browser engine, visuals
docs/              assumptions, methodology, limits
```

## Run it locally

Requires [Anaconda or Miniconda](https://docs.conda.io/).

```bash
conda env create -f environment.yml
conda activate onelife
pytest
```

## Known limits

To be written as the model is built. Planned: adults 18+ only; no existing serious diagnoses; official tables are by sex only; self-reported answers.

## Author

Pratham Sood — Actuarial Mathematics & Statistics, University of Manitoba.
