# Assumptions register

Every assumption the model makes is listed here: what it is, its value, where it comes from and its known weakness. Nothing enters the engine without a row in this file.

**Status key:** Decided = fixed by design · Loaded = source data in the repo and tested · To set = value comes from data in a later phase · Changed = revised (old value kept in the notes)

| ID | Assumption | Value | Source | Accessed | Rationale | Known weakness | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A01 | Minimum age simulated | 18 | Design decision | — | Survey and risk data are for adults | Excludes minors entirely | Decided |
| A02 | Ultimate age | 110 | Design decision | — | Every life must end; StatCan's open age group is 110+, where qx = 1 | Rates above about 100 rest on few deaths | Decided |
| A03 | Time step | 1 year | Design decision | — | Matches annual source tables | Events inside a year are not ordered | Decided |
| A04 | Base mortality by age, sex, province | qx by single age 0–110+, Canada and 9 provinces, 3 sexes, periods 1980–1982 to 2022–2024 | Statistics Canada, Table 13-10-0114-01 (complete life tables, three-year estimates) | 2026-11-10 | Official population rates; three-year tables are more stable than single-year ones | Population, not insured lives; PEI not included (needs Table 13-10-0140); latest data ends 2024; StatCan marks 2021–2023 and 2022–2024 as preliminary, so they may be revised | Loaded (release of 2026-01-13; which period to use: A09) |
| A05 | Mortality improvement scale | CIA MI-2024: two-dimensional rates by sex, age 20–120, calendar year 1981–2119; long-term rate about 1.29% a year at ages 40–80 from 2060, grading to 0 at 115+. Applied as q(x, t) = q(x, t−1)(1 − MI(x, t)). Ages 18–19 use the age-20 rate | Canadian Institute of Actuaries, Mortality Improvements Research – Tables (2024), file 224043te.xlsx | 2026-11-10 | Profession's current scale; proposed for Canadian commuted-value standards from Feb 2027 | Built from data to 2019; future improvement is uncertain; ages under 20 not covered | Loaded (not in public repo: CIA copyright) |
| A06 | Cause-of-death split | To set | Statistics Canada cause-of-death tables | — | Official cause shares by age and sex | Cause coding changes over time | To set (Phase 1) |
| A07 | Lifestyle hazard ratios | To set | Published peer-reviewed studies | — | Measured effects of smoking, alcohol, activity, diet | Self-reported answers; studies overlap | To set (Phase 2) |
| A08 | Cap on combined multipliers | To set | Design decision, tested | — | Stops stacked risks compounding | Cap level is a judgement | To set (Phase 2) |
| A09 | Base data period | To set | Design decision | — | Choice of whether COVID-era years are included | Any choice shifts the base rates | To set (Phase 1) |

## Data checks on A04

`tests/test_life_tables.py` (8 tests, all passing on 2026-11-10):

- complete grid: 43 periods x 10 regions x 3 sexes x ages 0–110, no duplicates
- no missing qx; 0 ≤ qx ≤ 1; qx = 1 at 110+
- px = 1 − qx; l(0) = 100,000; l(x+1) = l(x)(1 − q(x)) within rounding
- life expectancy rebuilt independently from qx matches StatCan's ex within 0.05 years at ages 1–100
- external check: cleaned e(0) for Canada 2022–2024 is 81.65; StatCan's single-year figures (about 81.3 in 2022, 81.68 in 2023, 82.16 in 2024) average about 81.7, consistent with it

Only gap in the source: margin of error of e(x) not published for one cell per period x region x sex (1,290 cells); not used by the model.

## Data checks on A05

`tests/test_mi2024.py` (6 tests, all passing on 2026-11-10; skipped where the CIA file is absent):

- complete grid: 2 sexes x ages 20–120 x years 1981–2119, no gaps or duplicates
- every rate between −15% and +15%
- long-term rate 1.20%–1.35% at ages 40–90 (published assumption: about 1.3%)
- rates constant from 2060; zero at ages 115+
- spot cells read straight from the workbook match the tidy table

## Change log

| Date | ID | Change |
| --- | --- | --- |
| 2026-11-10 | A04 | Noted preliminary status of latest periods and StatCan release date; added external e(0) check |
| 2026-11-10 | A05 | MI-2024 loaded and tested |
| 2026-11-10 | A04 | Life tables loaded and tested (StatCan 13-10-0114-01) |
| 2026-11-10 | A01–A09 | Register created |
