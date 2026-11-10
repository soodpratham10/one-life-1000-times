# Assumptions register

Every assumption the model makes is listed here: what it is, its value, where it comes from and its known weakness. Nothing enters the engine without a row in this file.

**Status key:** Decided = fixed by design · To set = value comes from data in a later phase · Changed = revised (old value kept in the notes)

| ID | Assumption | Value | Source | Accessed | Rationale | Known weakness | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A01 | Minimum age simulated | 18 | Design decision | — | Survey and risk data are for adults | Excludes minors entirely | Decided |
| A02 | Ultimate age | 110 | Design decision | — | Every life must end; very few Canadians pass 110 | Rates above about 100 are thin and must be extended | Decided |
| A03 | Time step | 1 year | Design decision | — | Matches annual source tables | Events inside a year are not ordered | Decided |
| A04 | Base mortality by age, sex, province | To set | Statistics Canada life tables | — | Official population rates | Population, not insured lives; lags a few years | To set (Phase 1) |
| A05 | Mortality improvement scale | To set | Canadian Institute of Actuaries | — | Profession's published scale | Future improvement is uncertain | To set (Phase 1) |
| A06 | Cause-of-death split | To set | Statistics Canada cause-of-death tables | — | Official cause shares by age and sex | Cause coding changes over time | To set (Phase 1) |
| A07 | Lifestyle hazard ratios | To set | Published peer-reviewed studies | — | Measured effects of smoking, alcohol, activity, diet | Self-reported answers; studies overlap | To set (Phase 2) |
| A08 | Cap on combined multipliers | To set | Design decision, tested | — | Stops stacked risks compounding | Cap level is a judgement | To set (Phase 2) |
| A09 | Base data years | To set | Design decision | — | Choice of whether COVID-era years are included | Any choice shifts the base rates | To set (Phase 1) |

## Change log

| Date | ID | Change |
| --- | --- | --- |
| 2026-11-10 | A01–A09 | Register created |
