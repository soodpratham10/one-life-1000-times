# Validation report (Phase 4)

What was checked, how close each check came, and where the model is still off.
Written 16 November 2026, for release v0.4.0. Every number here comes from a
file in this repository; the commands to reproduce them are at the end.

## In short

- **The code does what the assumptions say.** Three independent rebuilds (R,
  Excel VBA and plain Excel formulas) reproduce the Python engine to within
  10⁻¹² or better, on every value tested.
- **The machinery keeps the official death rates.** With everyone given
  average habits, simulated men from 25 live 55.70 years against StatCan's
  55.74, so the cancer, heart attack, stroke, marriage and disability links add
  no bias.
- **The model agrees with the published studies** it was built from, within
  about a year of life expectancy, and with Canada's lifetime cancer risk.
- **Where it is off:** a simulated population with today's habits outlives
  the 2017–2019 life table by about 2 years from age 25 (mostly because
  simulated smokers quit), lung cancer survival comes out too high for women,
  and near-term projected lifetimes are up to a year longer than recent
  experience.
  None of these is a coding error; each is a modelling choice, explained
  below.

## 1. Does the code do what the assumptions say?

The engine's answers for 12 reference people (every level of every survey
answer, both sexes, every survey age group, smokers who may quit and who keep
smoking, the cap and the PEI table) were worked out again from the raw data,
by code written separately from the engine.

| Check | Values | Largest difference | Files |
| --- | --- | --- | --- |
| R rebuild of the risk engine: population mix, hazard ratios, taper, cap, habits changing with age (A26), quitting (A27), death rates, life expectancy | 1,632 | 6×10⁻¹⁴ | [`crosscheck/r/`](../crosscheck/r/), [`crosscheck/results/r_vs_python.csv`](../crosscheck/results/r_vs_python.csv) |
| R run of the cancer link (A22): the synthetic cohort with the engine's solved rates reproduces official total, lung cancer and other-cancer deaths at every age 18–109 | 184 ages | 1×10⁻¹² (relative) | [`crosscheck/results/r_cancer_cohort.csv`](../crosscheck/results/r_cancer_cohort.csv) |
| R rebuild of CIA MI-2024 improvement: factors, improved death rates, life expectancy from 2026 | 2,217 | 6×10⁻¹⁴ | run locally only (CIA copyright) |
| Excel VBA rebuild of the risk engine, from the workbook's data sheets only | 1,632 | 6×10⁻¹⁴ | [`crosscheck/vba/OneLifeCheck.bas`](../crosscheck/vba/OneLifeCheck.bas), [`crosscheck/excel/`](../crosscheck/excel/) |
| One year for one person as visible Excel formulas (woman, 62, quit at 40) | 2 | 5×10⁻¹⁷ | `HandCheck` sheet |

The R code has 115 tests of its own, including hand-worked values. Inside the
Python engine, 443 tests check each table against its source, each formula
against a hand calculation, and each simulation average against an exact
year-by-year calculation (within four standard errors).

These checks show the code matches the assumptions register. They cannot show
the assumptions are right; sections 2 and 3 test that.

## 2. Does the model match Canada?

[`validation/population.py`](../validation/population.py) splits everyone of
one sex at age 25, 45 or 65 into every combination of survey answers and
starting marital status, weighted by how common each is in Canada, and works
out their deaths exactly (no simulation noise). The result is compared with the
2017–2019 StatCan life table and cause-of-death mix, both without future
improvement. Results: [`validation/results/population_check.csv`](../validation/results/population_check.csv).

**Life expectancy**

| Start | StatCan 2017–2019 | Model | Difference |
| --- | --- | --- | --- |
| Men 25 | 55.74 | 57.70 | +1.96 |
| Men 45 | 36.88 | 38.39 | +1.51 |
| Men 65 | 19.41 | 20.69 | +1.28 |
| Women 25 | 59.74 | 61.46 | +1.71 |
| Women 45 | 40.36 | 41.95 | +1.59 |
| Women 65 | 22.15 | 23.41 | +1.26 |

**Why the model lives longer**, measured one cause at a time:

1. *Machinery: no bias.* With every person's habits set to average, men from
   25 come out at 55.70 against 55.74.
2. *Habits held for life would add about 1.8 years.* This was the first
   finding of this phase. Young adults are slimmer and more active than older
   ones, so a cohort that kept its habits at 25 for life would be too
   healthy. Fixed by A26 (activity and BMI keep their rank as people age),
   which brought the gap down to +0.7 (men) and +1.0 (women).
3. *Quitting smoking adds about 1 year back (A27).* Simulated smokers quit at
   Canadian rates (5% a year from 25), so the cohort ends up with far fewer
   smokers than today's older Canadians (about 20% of 50–64-year-olds smoke).
   The life table reflects those older generations, so a cohort that quits
   *should* outlive it. This is a difference between a cohort and a period
   table, not an error, and it is the main reason for the gap above.
4. *Clean start at 65 adds about 0.6 years.* Everyone starts with no cancer,
   heart attack or stroke and not disabled. That is right for a survey user who
   reports none, but not for all 65-year-olds.

**Deaths by age and cause** (from 25): deaths at 25–44 are 87–91% of
StatCan's, at 45–84 77–90%, at 85–94 100–106%, and more lives reach 95–104
(A/E 1.3–1.5). The cause mix is within 10% of StatCan's for heart disease and
stroke, diabetes, accidents and "other"; cancer deaths are lower (A/E
0.82–0.91 across all starts), COPD much lower (0.63 from 25, 0.86–0.87 from 65)
and dementia higher (1.10–1.17). This is the pattern
expected from a cohort with fewer smokers who live longer.

**Lifetime cancer, against published Canadian figures** (no improvement, from
age 25 in the model):

| | Model | Published | Source |
| --- | --- | --- | --- |
| Chance of a cancer diagnosis, men | 43% | 45.1% (2018) | Statistics Canada |
| Chance of a cancer diagnosis, women | 40% | 43.5% (2018) | Statistics Canada |
| Share of deaths from cancer, men | 24.5% | 24.1% chance of dying from cancer (2020) | Statistics Canada |
| Share of deaths from cancer, women | 20.0% | 21.1% (2020) | Statistics Canada |

The model counts a first cancer only, from 25, so slightly lower diagnosis
figures are expected. Source: [Statistics Canada, *Raising cancer awareness
through data* (2024)](https://www.statcan.gc.ca/o1/en/plus/6019-raising-cancer-awareness-through-data).

**Projection against recent experience** (A09): the 2017–2019 base projected
to 2023 gives men e(65) = 20.0 and e(18) = 63.0 on the CPP basis (20.1 and
63.1 with MI-2024), while the actual 2022–2024 table gives 19.4 and 62.1
(women 22.6 vs 22.2 at 65, 67.1 vs 66.4 at 18). Part of that gap is COVID-19
and part is ongoing (e.g. overdose deaths at young ages), so projected
lifetimes may be up to a year too long in the near term.

**Future improvement against the Chief Actuary's own projection** (A28, the
default since this report; see the update at the end): with the CPP report's
improvement rates and one scale on 2019–2025 fitted to its 2025 life
expectancies, the engine reproduces the report's other life expectancies,
which were not fitted:

| Report table | Values | Largest difference | Average difference |
| --- | --- | --- | --- |
| Table 43, period life expectancy 2025, 2050, 2075, ages 0–100 | 84 | 0.20 years | −0.03 |
| Table 44, cohort life expectancy from 2025, 2050, 2075, ages 20–100 | 72 | 0.41 years | −0.13 |

## 3. Does the model agree with the studies?

| Check | Model | Published |
| --- | --- | --- |
| Best vs worst habits, life expectancy gap | 18.8 years (men), 17.4 (women) | 17.9 years, Canada (MPoRT, Manuel et al. 2016) |
| Life lost by someone who keeps smoking, from 25 | 9.5 (men), 9.2 (women) | more than 10 (Jha et al. 2013, US) |
| Gain from quitting at 30 / 40 / 50 (men) | 8.9 / 7.2 / 4.5 | about 10 / 9 / 6 (Jha et al. 2013) |
| Life lost by a smoker who may quit (A27), from 25 | about 3.5 | (no direct published figure) |
| 30-day heart attack / stroke fatality, all Canadian cases | 6.5% / 13.2% | 6.5% (CIHI, Li et al. 2022) / 13.2% (Joundi et al. 2021), set by design |
| 5-year survival after lung cancer, diagnosed at 50–70 | 20–28% (men), 32–39% (women) | 19% men, 26% women (Canadian Cancer Statistics 2023) |
| Disabled share at 55–64, against CPP beneficiaries in 2011 | A/E 1.1–1.4 | 1 |

The smoking figures are slightly smaller than Jha's because the ratios fade
after 79 (the studies end there) and Jha's are US rates; the gap stays within
about a year at every quit age.

## 4. Where the model is off, and what is planned

| Issue | Size | Why | Plan |
| --- | --- | --- | --- |
| Projected lifetimes long in the near term | +0.4 to +0.9 years against 2022–2024 | Pre-COVID base; the CPP scale reproduces the Chief Actuary's projection, which assumes recovery | Shown plainly on the website; the 2022–2024 base can be switched on for comparison |
| Population outlives the period table | +1.7 to +2.0 years from 25 | Simulated smokers quit (A27) | Expected for a cohort; the survey will ask whether a smoker plans to quit |
| Lung cancer survival, women | 32–39% against 26% | Survival is an output of the cancer link, not an input: the post-diagnosis rate is solved to match deaths, and women's 2017–2019 lung cancer deaths are low relative to 2019 diagnoses | Later: fit the post-diagnosis rate to published survival by sex |
| Stroke survivors' extra risk | limited to about 1.1–1.3x from 60 | Acute stroke deaths already use most of the recorded stroke deaths at older ages | Later: Ontario stroke fatality by age (Joundi et al. 2021 supplement) |
| Disabled share at 55–64 | 10–40% below the 2011 CPP count | Uses the lower 2029+ CPP incidence | Accepted: the CPP's own projection |
| Quit rate | one rate for all ages | No published Canadian rate by age | Later: fit to quitter shares by age |
| Habits independent of each other | not measured | No Canadian joint distribution | Accepted; the cap (A08) limits stacked ratios |

## 5. What was not checked

- Event rates (crashes, cancer, heart attack, stroke, disability, marriage,
  births, retirement) are taken from the same official tables they would be
  compared with, so they reproduce them by construction; no independent
  outside data was available for an out-of-sample test.
- The hazard ratios themselves are taken from the studies as published; their
  confidence intervals are not carried through the model.
- Survey answers are self-reported, as in the studies.
- The CIA MI-2024 scale is used as published; it is not re-derived.

## Update, 16 November 2026: default improvement scale (A28)

After v0.4.0 the default improvement scale changed from CIA MI-2024 to the
Chief Actuary's CPP rates, so that every number in the repository and on the
website can be reproduced from public sources (the CIA scale cannot be
redistributed). Sections 1–3 above are unaffected except where they quote
improved lifetimes: sections 2 and 3 use 2017–2019 rates with no improvement,
and the R and VBA rebuilds were run on that basis. On the CPP basis lifetimes
are about 2 years shorter than with MI-2024 for an 18-year-old in 2026 (men
68.7 vs 70.8). MI-2024 remains available with `improve="cia"`.

## Reproduce it

```bash
pytest                                                  # 443 tests (15 skip without the CIA file)
python -m validation.population                         # section 2, a few minutes
python crosscheck/make_reference.py                     # the engine's answers for section 1
Rscript crosscheck/r/run_crosscheck.R                   # R rebuild
Rscript -e 'testthat::test_file("crosscheck/r/tests/test_risk.R")'
```

Excel: open `crosscheck/excel/one_life_crosscheck.xlsm`, enable macros, and
run `CheckAllCases` (Developer → Macros). Every assumption, with its source and
weakness, is in [`assumptions.md`](assumptions.md).
