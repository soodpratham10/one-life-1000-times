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
| A06 | Cause-of-death split | 12 non-overlapping groups: lung cancer, other cancers, heart, stroke, chronic lung disease, diabetes, dementia, motor vehicle, other accidents, other injury, COVID-19, all other (remainder). Deaths by year 2000–2024, sex, 20 age groups. Same cause mix assumed for every province | Statistics Canada, Table 13-10-0392-01 (deaths by selected grouped causes) | 2026-11-10 | Groups match what the survey can change (smoking, activity, driving) | Canada only, not by province; 5-year age groups; cause coding and reporting lags (StatCan notes younger deaths are reported later) | Loaded (years to use: A09) |
| A07 | Lifestyle hazard ratios | To set | Published peer-reviewed studies | — | Measured effects of smoking, alcohol, activity, diet | Self-reported answers; studies overlap | To set (Phase 2) |
| A08 | Cap on combined multipliers | To set | Design decision, tested | — | Stops stacked risks compounding | Cap level is a judgement | To set (Phase 2) |
| A09 | Base data period | To set | Design decision | — | Choice of whether COVID-era years are included | Any choice shifts the base rates | To set (Phase 1) |
| A10 | PEI single-age mortality | Derived: within each PEI age group, the single-age force of mortality is the NS–NB average scaled by one factor; ages 0–89 match PEI's published group survival exactly; ages 90–109 match PEI's published e(90+); q = 1 at 110+ | Statistics Canada, Table 13-10-0140-01 (abridged life tables, PEI and territories), with NS and NB from 13-10-0114-01 | 2026-11-10 | StatCan publishes only 5-year groups for PEI; borrowing the shape of similar Atlantic provinces keeps PEI's own level | The within-group shape is assumed, not observed; territories excluded from v1 (tiny populations, recent Yukon tables not published) | Loaded (derived) |

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

## Data checks on A06

`tests/test_causes_of_death.py` (5 tests, all passing on 2026-11-10):

- complete grid: every year x sex x age group has all 12 groups, once each
- age groups run 0–110 with no gaps or overlaps
- groups sum exactly to StatCan's total deaths in every cell
- males + females = both sexes, cause by cause
- "all other" (the remainder) is never negative, so no deaths are counted twice (written by Pratham)
- external check: 2024 shares (heart 17.7%, stroke 4.2%, chronic lung disease 4.0%, diabetes 2.1%, accidents 6.3%) match StatCan's published 2024 leading causes
- only missing counts in the source: COVID-19 before 2020 (cause did not exist), set to 0; any other gap stops the pipeline

## Data checks on A10

`tests/test_pei.py` (5 tests, all passing on 2026-11-10):

- complete grid: every period x sex x ages 0–110, no duplicates
- 0 ≤ qx < 1 below 110; qx = 1 at 110+
- survival over every PEI age group below 90 equals the published group survival (within 1e-6)
- e(90) equals PEI's published e(90+) within rounding
- e(0) within 0.1 years of PEI's published e(0)
- method check on test data: with PEI set to exactly 1.15 x the reference force, the build recovered 1.148–1.154 at every age (differences from 5-decimal rounding)

## Change log

| Date | ID | Change |
| --- | --- | --- |
| 2026-11-10 | A10 | PEI single-age table derived and tested |
| 2026-11-10 | A06 | Cause-of-death groups loaded and tested |
| 2026-11-10 | A04 | Noted preliminary status of latest periods and StatCan release date; added external e(0) check |
| 2026-11-10 | A05 | MI-2024 loaded and tested |
| 2026-11-10 | A04 | Life tables loaded and tested (StatCan 13-10-0114-01) |
| 2026-11-10 | A01–A09 | Register created |
