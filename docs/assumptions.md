# Assumptions register

Every assumption the model makes is listed here: what it is, its value, where it comes from and its known weakness. Nothing enters the engine without a row in this file.

**Status key:** Decided = fixed by design · Loaded = source data in the repo and tested · Set = value chosen and tested in the engine · To set = value comes from data in a later phase · Changed = revised (old value kept in the notes)

| ID | Assumption | Value | Source | Accessed | Rationale | Known weakness | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A01 | Minimum age simulated | 18 | Design decision | — | Survey and risk data are for adults | Excludes minors entirely | Decided |
| A02 | Ultimate age | 110 | Design decision | — | Every life must end; StatCan's open age group is 110+, where qx = 1 | Rates above about 100 rest on few deaths | Decided |
| A03 | Time step | 1 year | Design decision | — | Matches annual source tables | Events inside a year are not ordered | Decided |
| A04 | Base mortality by age, sex, province | qx by single age 0–110+, Canada and 9 provinces, 3 sexes, periods 1980–1982 to 2022–2024 | Statistics Canada, Table 13-10-0114-01 (complete life tables, three-year estimates) | 2026-11-10 | Official population rates; three-year tables are more stable than single-year ones | Population, not insured lives; PEI not in this table (built separately: A10); latest data ends 2024; StatCan marks 2021–2023 and 2022–2024 as preliminary, so they may be revised | Loaded (release of 2026-01-13; which period to use: A09) |
| A05 | Mortality improvement scale | CIA MI-2024: two-dimensional rates by sex, age 20–120, calendar year 1981–2119; long-term rate about 1.29% a year at ages 40–80 from 2060, grading to 0 at 115+. Applied as q(x, t) = q(x, t−1)(1 − MI(x, t)). Ages 18–19 use the age-20 rate | Canadian Institute of Actuaries, Mortality Improvements Research – Tables (2024), file 224043te.xlsx | 2026-11-10 | Profession's current scale; proposed for Canadian commuted-value standards from Feb 2027 | Built from data to 2019; future improvement is uncertain; ages under 20 not covered | Loaded (not in public repo: CIA copyright) |
| A06 | Cause-of-death split | 12 non-overlapping groups: lung cancer, other cancers, heart, stroke, chronic lung disease, diabetes, dementia, motor vehicle, other accidents, other injury, COVID-19, all other (remainder). Deaths by year 2000–2024, sex, 20 age groups. Same cause mix assumed for every province | Statistics Canada, Table 13-10-0392-01 (deaths by selected grouped causes) | 2026-11-10 | Groups match what the survey can change (smoking, activity, driving) | Canada only, not by province; 5-year age groups; cause coding and reporting lags (StatCan notes younger deaths are reported later) | Loaded; used by the engine (2017–2019 combined, A09) |
| A07 | Lifestyle hazard ratios | All-cause hazard ratios against a reference level, in `data/assumptions/hazard_ratios.csv`. Smoking: current 2.8 men, 3.0 women; quit before 35: 1.05; 35–44: 1.20; 45–54: two-thirds of the excess removed (1.60 / 1.67); 55+: half removed (1.90 / 2.00, judgement). Activity a week: none 1.00, under 150 min 0.80, 150–299 0.69, 300–449 0.63, 450+ 0.61. BMI: under 18.5 1.51, 18.5–25 1.00, 25–27.5 1.07, 27.5–30 1.20, 30–35 1.45, 35–40 1.94, 40+ 2.76. Alcohol a day: under 25 g 1.00, 25–44 g 1.05, 45–64 g 1.19, 65 g+ 1.35 (one Canadian drink = 13.45 g). Fruit and vegetables a day: 2 or fewer 1.00, 3 0.955, 4 0.911, 5+ 0.87. Applied to the force of mortality; factors multiplied as if independent; answers held for life. Driving changes crash risk only (later step) | Jha et al., NEJM 2013 (smoking, quitting at 45–54); Pirie et al., Lancet 2013 (quitting before 45); Arem et al., JAMA Intern Med 2015 (activity); Global BMI Mortality Collaboration, Lancet 2016 (BMI, never-smokers); Zhao et al., JAMA Netw Open 2023 (alcohol); Wang et al., Circulation 2021 (fruit and vegetables) | 2026-11-10 | Large studies of all-cause mortality; each factor is something the survey can ask and the person can change. Results agree with the studies: best vs worst habits 18.8 years (men) and 17.4 (women) against MPoRT's 17.9 for Canada | Self-reported answers; most studies are American or British; the studies adjust for different things, so multiplying their ratios overlaps somewhat (hence the cap, A08); smokers lose about 9 years in the engine against Jha's "more than 10" (US), mainly because of the taper after 79; quit-at-55+ ratio is a judgement; below 2 servings of fruit and vegetables is not penalised; family history left out (no Canadian population figures to normalise it, and it overlaps with existing conditions, which are out of scope) | Set |
| A08 | Combining, taper and cap | Relative multiplier r = person's multiplier ÷ population average (A18, A19), so the population as a whole keeps the official death rates (tested exactly). Each log hazard ratio applies in full to age 79, then shrinks in a straight line to zero at 110. r is capped between 0.35 and 5.0 | Design decision, tested | 2026-11-10 | Dividing out the population average is how aggregate tables are split into risk classes; the studies cover ages to about 80, and risk ratios narrow at very old ages; the cap stops stacked ratios from separate studies compounding without limit | Taper start and cap levels are judgements: starting the taper at 89 instead of 79 adds about 0.7 years to a smoker's loss; the cap binds only for extreme profiles (e.g. a smoker with BMI 45 who drinks 7 a day: about 8x uncapped) | Set |
| A09 | Base data period | Event rates: calendar 2019 (crashes, cancer) and fiscal 2018–19 (heart attack, stroke), the last full years before COVID-19. Mortality: life table 2017–2019, treated as calendar 2018 (its middle year) and projected forward with MI-2024 (A05). The engine can also use another period (e.g. 2022–2024) for comparison | Design decision | 2026-11-10 | COVID-19 distorted 2020–2022: crash injuries fell 26%, cancer diagnoses fell (Quebec 2020: −8%), PHAC flags 2020–21 to 2022–23. A pre-COVID mortality base matches the event base year and the data MI-2024 was built on, and avoids StatCan's preliminary 2021–2023 and 2022–2024 tables | Optimistic against recent experience: the base projected to 2023 gives Canadian men e(65) = 20.1 and e(18) = 63.1, while the actual 2022–2024 table gives 19.4 and 62.1 (women 22.8 vs 22.2 at 65, 67.3 vs 66.4 at 18). Part of the gap is COVID-19, part is ongoing (e.g. overdose deaths at young ages), so this choice may overstate future lifetimes by about a year | Decided (2017–2019); to revisit in Phase 4 validation |
| A10 | PEI single-age mortality | Derived: within each PEI age group, the single-age force of mortality is the NS–NB average scaled by one factor; ages 0–89 match PEI's published group survival exactly; ages 90–109 match PEI's published e(90+); q = 1 at 110+ | Statistics Canada, Table 13-10-0140-01 (abridged life tables, PEI and territories), with NS and NB from 13-10-0114-01 | 2026-11-10 | StatCan publishes only 5-year groups for PEI; borrowing the shape of similar Atlantic provinces keeps PEI's own level | The within-group shape is assumed, not observed; territories excluded from v1 (tiny populations, recent Yukon tables not published); PEI's small population makes some published rates noisy (e.g. 2022–2024 infant death rate higher for girls than boys), which does not affect the model since it starts at 18 | Loaded (derived) |
| A11 | Car crash event | Event = injured in a police-reported motor vehicle collision (any road user: driver, passenger, pedestrian, cyclist, motorcyclist). Counts by sex and single age; base year 2019. Unknown age or sex (about 2%) spread in proportion. Annual probability = count ÷ Canada's July 1 population of the same sex, age and year (A12); ages 99 and 100+ combined | Transport Canada, National Collision Database open data, 2019 and 2020 files | 2026-11-10 | Only national source of injury counts by age and sex | Open data does not separate minor from serious injuries; police-reported only (some injuries never reported); national only, no province; 2020 distorted by COVID (kept as comparison only) | Loaded (rates by sex and age, 2019 and 2020) |
| A12 | Population (denominator for event rates) | July 1 population by year 2000–2026, Canada and 10 provinces, single age 0–100+. StatCan's gender categories mapped to sex: Men+ → M, Women+ → F | Statistics Canada, Table 17-10-0005-01 (population estimates on July 1, by age and gender) | 2026-11-10 | Official population estimates, same source family as the life tables | Reported by gender, while the life tables are by sex: non-binary people (a very small share) are distributed between Men+ and Women+; territories not used; years before 2000 not used because StatCan does not publish every single age up to 100+ for them (before 1991 the oldest group is 90+; in 1991–1999 ages 90–100 are blank) | Loaded |
| A13 | Cancer diagnosis event | Yearly probability of a new primary cancer = new cases ÷ population, by sex and 5-year age group (90+ = 90–100+), Canada, 2019. Split into lung (lung and bronchus) and other cancers, matching the cause-of-death groups (A06) | Statistics Canada, Table 13-10-0111-01 (new cases of primary cancer, Canadian Cancer Registry), with population from A12 | 2026-11-10 | 2019 is the latest year with complete national data in this table and the last before COVID-19 disrupted screening and diagnosis | Counts primary cancers, not people (a second primary cancer counts again), so the chance of a first diagnosis is slightly overstated; 5-year age groups; national rates used for every province; StatCan rounds counts to the nearest 5; lung cancer counts under age 30 are suppressed for privacy and set to 0 (flagged), a negligible effect since even 4 cases would be a chance below 1 in a million | Loaded |
| A14 | Heart attack and stroke events | Yearly probability = newly identified cases ÷ CCDSS population, by sex and 5-year age group (20–24 … 90+), Canada, fiscal year 2018–19 (April 2018 – March 2019). Ages 18–19 use the 20–24 rate | Public Health Agency of Canada, Canadian Chronic Disease Surveillance System (CCDSS), Health Infobase data tool, crude incidence rate of acute myocardial infarction and of stroke (data as of April 2025) | 2026-11-10 | National data from provincial health-insurance records, covering nearly everyone; 2018–19 is the last full fiscal year before COVID-19 | Case definitions are PHAC's (from hospital and physician claims; whether repeat events are counted is set by those definitions and not checked here); registry population runs about 2–3% above StatCan's estimates; Quebec diagnostic coding may slightly undercount from 2016–17; national rates used for every province | Loaded |
| A15 | Disability event | Event = becoming entitled to a CPP disability pension (a "severe and prolonged" disability). Yearly rate per 1,000 eligible, ultimate (2029+), by sex and age: published at ages 25, 30, …, 55 and 60–64; other ages log-linear interpolation; ages 18–24 held at the age-25 rate. Ends (termination) per 1,000 by sex, age (read as age at onset) and duration 1–6+ years, 2025 and 2035. Share of adults 20–64 eligible kept by year, 2025–2100 (2025: men 71.7%, women 65.7%) | Office of the Chief Actuary (OSFI), 32nd Actuarial Report on the Canada Pension Plan as at 31 December 2024 (revised version): Tables 73, 85 and 88, read from the PDF | 2026-11-10 | The actuarial assumptions used to value the CPP; the report found incidence not significantly affected by COVID-19; termination rates allow a disability to end | Covers only people eligible for CPP disability (enough contributions) and only severe and prolonged disability; CPP excludes Quebec (QPP); termination includes recovery and death, so using it as recovery would double-count deaths the engine models separately (to handle in Phase 3); rates are projections for 2029+, not one observed year; ages under 25 not published | Loaded |
| A16 | Retirement event | Event = starting the CPP retirement pension. Share of a cohort starting at each age 60–70 (ultimate, cohort aged 65 in 2031+); men 21% at 60, 32% at 65, 10% at 70; converted to a yearly chance of starting given not yet started (1 at age 70) | Office of the Chief Actuary (OSFI), 32nd Actuarial Report on the Canada Pension Plan, Table 76, read from the PDF | 2026-11-10 | The CPP's own best-estimate assumption; covers nearly all workers outside Quebec | Starting the pension is not the same as stopping work (people can work while receiving it, and some retire from work earlier or later); people not eligible for CPP are not covered; Quebec has the QPP | Loaded |
| A17 | Family events | Canada, 2019, by sex and 5-year age group: first marriage (per 1,000 never legally married), remarriage (per 1,000 divorced), divorce (per 1,000 married), first child (first live births per 1,000 women of that age; parity not stated spread in proportion). Marriage and divorce tables have no sex split after 2002 and 2017, so: rate(sex) = 2019 rate for both sexes x sex relativity from 2002 (marriage) or 2017 (divorce). Remarriage under 20 uses the 20–24 rate (almost nobody is divorced before 20) | Statistics Canada, Tables 39-10-0057-01 (marriages), 39-10-0053-01 (divorces), 13-10-0421-01 (live births by age and parity of mother); population from A12 | 2026-11-10 | Official vital statistics; 2019 is the last year before COVID-19 disrupted weddings and divorce courts; the relational method keeps the latest level and a real sex pattern | Assumes the male/female gap is the same as in 2002 (marriage) and 2017 (divorce); legal marriage only, so common-law unions (about a fifth of couples) are not covered; first-child rate is per woman, not per childless woman, so it understates the chance for a childless woman; national rates used for every province | Loaded |
| A18 | Risk factor prevalence | Percent of people who smoke (daily or occasional), drink heavily, are active 150+ minutes a week, are overweight (BMI 25 to <30) or obese (BMI 30+), and eat fruit and vegetables 5+ times a day, by sex and age group 18–34, 35–49, 50–64, 65+. Canada and provinces, 2015–2022. The engine uses, for each factor, the latest year up to 2019 with complete Canadian data (the CCHS does not ask every question every year: physical activity and fruit and vegetables were not collected in 2019) | Statistics Canada, Table 13-10-0096-01 (health characteristics, annual estimates, Canadian Community Health Survey) | 2026-11-10 | Needed to turn population death rates into a reference rate before applying a person's hazard ratios (the population average multiplier); official national survey, same base year as the events | Self-reported (BMI is adjusted for self-report bias by StatCan); no former smokers, underweight or drinks per day in this table. Splits inside the published yes/no groups are judgements (in `engine/risk.py`): under 150 minutes = half none, half some; 150+ = 50% 150–299, 25% 300–449, 25% 450+; overweight = half 25–27.5, half 27.5–30; obese = classes I, II, III in the measured 2004 CCHS shares (15.2%, 5.1%, 2.7% of adults); below 5 fruit and vegetables counted at 2 servings; underweight counted as normal; alcohol volume not normalised (no Canadian figures by volume). Moving any one split by 10 points changes the population average by about 1–3%; 4 broad age groups; heavy drinking is a binge measure, not average intake; table is terminated by StatCan (last year 2022); excludes the territories and people living on reserves or in institutions | Loaded; used by the engine |
| A19 | Former smokers | Percent of adults who are former smokers: men 16.9% (18–49), 38.1% (50+); women 17.3% (18–49), 32.2% (50+). Quit-age mix (judgement): under 50, 75% quit before 35 and 25% at 35–44; 50+, 40% before 35, 30% at 35–44, 20% at 45–54, 10% at 55+ | Health Canada, Canadian Tobacco and Nicotine Survey 2019, Table 1 (former smokers by age group and gender), typed into `data/assumptions/former_smokers.csv` | 2026-11-10 | The CCHS table has no former smokers; CTNS is the federal tobacco survey for the same year | Only two adult age groups (25–44 and 45+), so 18–34 uses 25–44 (overstates young former smokers a little) and 65+ uses 45+ (understates older former smokers: StatCan reported about 62% of senior non-smokers were former smokers in 2013); a different survey from the CCHS smoking figures; quit ages not published | Loaded (typed in) |
| A20 | Cause of death | When a person dies, the cause is drawn from the 2017–2019 cause mix for their sex and 5-year age group (11 groups), adjusted for smoking only. Current-smoker ratios by cause: lung cancer 24.97 men / 25.66 women, COPD 25.61 / 22.35, heart disease 2.50 / 2.86, stroke 1.92 / 2.10, every other cause 2.0. Former smokers keep the same share of each cause's excess as of the all-cause excess (A07); same taper as A08. The total chance of dying is unchanged (A07, A08); per-cause scale factors are calibrated so the population's deaths reproduce the official cause mix exactly at every age | Thun et al., NEJM 2013 (contemporary cohorts, 2000–2010); Jha et al., NEJM 2013 (other causes, about 2); Statistics Canada, Table 13-10-0392-01 (A06) | 2026-11-10 | Smoking changes what people die of far more than how much it changes total mortality, and the life story should show that | Heart disease uses the ischemic heart disease ratio for all heart disease; "other causes" ratio of 2 is approximate and covers causes smoking barely affects (e.g. accidents); BMI, activity and diet change only total mortality, not the cause mix; 5-year age steps; US studies | Set |

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

`tests/test_causes_of_death.py` (6 tests, all passing on 2026-11-10):

- complete grid: every year x sex x age group has all 12 groups, once each
- age groups run 0–110 with no gaps or overlaps
- groups sum exactly to StatCan's total deaths in every cell (a guard against code changes: 'all other' is defined as the remainder)
- 2024 total deaths equal StatCan's published 326,779 (outside source)
- males + females = both sexes, cause by cause
- "all other" (the remainder) is never negative, so no deaths are counted twice
- external check: 2024 shares (heart 17.7%, stroke 4.2%, chronic lung disease 4.0%, diabetes 2.1%, accidents 6.3%) match StatCan's published 2024 leading causes
- external check: 2024 total deaths in the cleaned file (326,779) equal StatCan's published 2024 count
- only missing counts in the source: COVID-19 before 2020 (cause did not exist), set to 0; any other gap stops the pipeline

## Data checks on A10

`tests/test_pei.py` (5 tests, all passing on 2026-11-10):

- complete grid: every period x sex x ages 0–110, no duplicates
- 0 ≤ qx < 1 below 110; qx = 1 at 110+
- survival over every PEI age group below 90 equals the published group survival (within 1e-6)
- e(90) equals PEI's published e(90+) within rounding
- e(0) within 0.1 years of PEI's published e(0)
- StatCan's published PEI values are kept in `data/clean/life_tables_pei_abridged.csv`, so these checks run on any copy of the repo
- method check on test data: with PEI set to exactly 1.15 x the reference force, the build recovered 1.148–1.154 at every age (differences from 5-decimal rounding)

## Data checks on A11

`tests/test_crash_casualties.py` (5 tests):

- complete grid: 2 years x 2 sexes x ages 1–99
- no negative counts
- totals after spreading unknowns equal the source files exactly (2019: 140,801 injured, 1,762 killed; 2020: 104,265 injured, 1,746 killed)
- 2020 injuries at least 15% below 2019 (COVID): actual drop 26%
- 2020 deaths equal Transport Canada's published 1,746

## Data checks on A11 rates and A12

`tests/test_population.py` (4 tests) and `tests/test_crash_rates.py` (4 tests):

- population grid complete from 2000 (earlier years lack single ages 90–100, found by these tests); single ages sum exactly to StatCan's "All ages" totals; Men+ + Women+ = total
- the 10 provinces hold 99–100% of Canada's population
- crash probabilities between 0 and 1, deaths below injuries; rate x population gives back the counts
- adults 18–24 are injured more often than adults 55–64: 2019 rates per 1,000 were 7.1 (women) and 6.1 (men) at 18–24, versus 3.4 and 3.3 at 55–64
- cross-source check: police-reported crash deaths (Transport Canada) are 80–100% of motor vehicle deaths on death certificates (StatCan): 2019 1,762 vs 1,926 (91%); 2020 1,746 vs 1,818 (96%). StatCan's count is higher because it includes crashes off public roads and deaths after 30 days

## Data checks on A13

`tests/test_cancer.py` (7 tests):

- Canada = Canada excluding Quebec + Quebec, within rounding (2019 all ages: 219,125 vs 161,785 + 57,345)
- complete grid for Canada 2019: 2 sexes x 19 age groups, no blanks
- probabilities valid; lung never above all cancers
- privacy suppression only affects lung cancer under age 30
- our rate (cases ÷ our population) within 2% of StatCan's published rate in every group with at least 100 cases
- risk at 70–74 more than 10 times risk at 30–34
- 2019 cancer deaths (A06) are 30–50% of 2019 new cases, a typical mortality-to-incidence ratio

What the source showed: national totals in this table run to 2019 only, while Quebec's run to 2023; Quebec's 2020 count fell about 8% below 2019 (screening disruption).

## Data checks on A14

`tests/test_heart_stroke.py` (7 tests, all passing on real data on 2026-11-10):

- complete grid for Canada 2018–19: 2 sexes x 15 age groups, no blanks
- 5-year groups sum to the published 20+ totals within rounding (largest gap 15 cases of 41,560)
- males + females = both sexes
- cases ÷ population reproduce PHAC's published rates
- risk rises steeply with age (90+ more than 20 times 20–24)
- men's heart-attack rate more than twice women's at every age 35–64 (PHAC reports about four times at 25–44); measured 3–4 times at 35–49
- CCDSS registry population within 5% of StatCan's July 1 estimates (29.98M adults vs 28.99M–29.48M)

## Data checks on A15

`tests/test_cpp_disability.py` (8 tests, all passing on the real report on 2026-11-10):

- incidence grid complete: 2 sexes x ages 18–64, all positive
- published values read correctly (spot values agree between the report's web page and PDF)
- filled-in ages lie between the published ages on either side; risk rises with age to 61
- women's rates at least men's at every age (the report: consistently higher since 1996)
- termination table complete (96 values); onset at 60 has no 6th year (benefits stop at 65)
- eligibility table complete, 2025–2035 and every 5 years to 2100; first and last rows read correctly (2025: 71.7% men, 65.7% women; 2100: 80.6%, 76.1%)
- rebuild check: rates x eligible population (Canada less Quebec, 2026) give about 20,300 new male and 23,300 new female beneficiaries, within 15% of the report's 2029 projection (19,000 and 21,900); one eligibility rate is used for all ages, which overstates the young

## Data checks on A16

`tests/test_cpp_retirement.py` (5 tests, all passing on the real report on 2026-11-10):

- grid complete: 2 sexes x ages 60–70; shares add to 100% for each sex
- average take-up age equals the report's 64.3 (measured 64.33 men, 64.27 women)
- values quoted in the report's text read correctly (21%/22% at 60, 32% at 65, 10% at 70)
- running the yearly chances forward from 60 gives back the published shares exactly, and everyone has started by 70

## Data checks on A17

`tests/test_family_events.py` (11 tests, all passing on the real tables on 2026-11-10):

- grid complete: 28 first-marriage, 28 remarriage, 22 divorce and 8 first-child rows; every rate filled in
- rates between 0 and 1,000; counts not negative
- men's and women's rates sit either side of the 2019 both-sexes rate in every group (relational method)
- persons divorced in 2019 (113,871) within 0.5% of twice StatCan's published 56,937 divorces
- overall divorce rate 7.5 per 1,000 married persons, as published
- first marriage peaks at 25–34 (2019: 30–34 for both sexes); women's first-marriage rate at 20–24 above men's (17.0 vs 9.4)
- divorce rate at 65+ below the rate at 30–34
- first-child rate peaks at 25–34; first births are 40–44% of all births (42%); mean age at first birth between 28 and 32 (29.85)

What the source showed: the marriage table is split by gender only up to 2002 and the divorce table by sex only up to 2017; from then on only totals are published.

## Data checks on A18

`tests/test_risk_prevalence.py` (11 tests):

- complete grid: years x 11 regions x 3 sexes x 6 age groups x 7 indicators, no duplicates
- every percent between 0 and 100 and inside its own 95% confidence interval; suppressed estimates (F, x) are blank
- every factor the engine uses has exactly one base year, complete for Canada, both sexes and all four adult age groups, chosen by the rule above
- daily smokers never exceed current smokers; overweight plus obese never exceeds 100%
- known age patterns: obesity lower at 18–34 than 50–64, activity higher at 18–34 than 65+
- outside check: 2019 smokers aged 12+ match StatCan's separately published fact sheet (men 17.3%, women 12.3%)

## Engine checks: mortality basis (A04, A05, A09)

`tests/test_mortality.py` (39 tests; the 8 that need MI-2024 skip where the CIA file is absent), checking `engine/mortality.py`:

- life expectancy formula checked on small hand-worked cases (e.g. q = 0.2, 0.5, 1 gives 1.7 years)
- base table for all 11 regions and both sexes: ages 0–110, rates in [0, 1], q = 1 at 110
- with no improvement, the engine's e(18) reproduces the published table (Canada, Manitoba, PEI) within 0.01 years
- one cell of improvement worked by hand: Canada, male, 65, 2020 = 0.01108 × (1 − MI 2019) × (1 − MI 2020)
- ages 18–19 use the age-20 rate; years after 2119 keep the 2119 rate; age 110 never improved; nothing improved before 2018
- improvement adds 3–12 years to e(18) for someone aged 18 in 2026 (engine: men 62.4 → 70.8, women 66.6 → 74.3)

## Engine checks: risk multipliers (A07, A08, A18, A19)

`tests/test_risk.py` (75 tests; one needs MI-2024), checking `engine/risk.py`:

- hazard ratio table: every level present for both sexes, references equal 1, derived ratios match their formulas, ratios move the right way (U shape for BMI)
- answers to levels at every boundary, worked by hand (e.g. 180 cm and 81 kg is BMI 25.0; 14 drinks a week is 26.9 g a day); impossible answers rejected
- population mix adds to 1 for every sex and age group; average multiplier for men aged 40 worked by hand (1.2774)
- exact rule: averaged over the whole population mix, person ÷ average equals 1, so the population keeps the official death rates (ages 25–85, both sexes)
- taper (1 at 79, 0 at 110), cap (extreme profile held at 5), one personal rate worked by hand
- agreement with the studies: best vs worst habits 18.8 / 17.4 years (MPoRT 17.9); smokers lose 9.2 / 8.8 years (Jha: more than 10, US); quitting earlier always gains more (quit at 30: 8.6 years; Jha: about 10)

## Engine checks: cause of death (A06, A20)

`tests/test_causes.py` (29 tests), checking `engine/causes.py`:

- the 11 cause groups match the data; shares add to 1 at every age 18–110; one share worked by hand (men 60–64: 3,463 lung cancer deaths of 32,108)
- cause ratios match Thun 2013, and the former-smoker rule worked by hand (quit at 35–44: lung cancer 1 + 23.97 / 9 = 3.66)
- exact rule: across the population's smoking mix, deaths split by cause exactly as in the 2017–2019 data, at ages 18–109, both sexes
- smokers die more often of lung cancer and COPD, and less often of dementia, than the population, and never smokers the reverse; the difference fades by 109

## Open items for later phases

| Item | Why it matters | Plan |
| --- | --- | --- |
| Split CPP disability termination (A15) into recovery and death | Termination includes deaths; the engine models deaths separately, so using termination as recovery would count some deaths twice | Phase 3: the 32nd CPP report does not publish disabled-beneficiary mortality; candidate source is the Office of the Chief Actuary's beneficiary mortality study (Actuarial Study No. 16, 2015), to be checked |
| Driving distance and crash risk (A07, A11) | Crash risk should rise with distance driven | Phase 2, crash step: needs Canadian distance-driven figures by age and sex |
| Cause-specific effects of BMI, activity and diet (A20) | These change only total mortality; their effects differ by cause (e.g. BMI on heart disease) | Later version: cause-specific ratios from the same studies |
| Disability rates are per eligible person (A15) | Applying them to everyone overstates disability | Engine: survey asks about work history; apply eligibility |
| First-child rate is per woman, not per childless woman (A17) | Understates the chance for a childless woman | Engine: convert using the share of women still childless by age |

## Change log

| Date | ID | Change |
| --- | --- | --- |
| 2026-11-10 | A06, A20 | Cause of death: 2017–2019 mix, smoking-specific ratios by cause, calibrated to official shares |
| 2026-11-10 | A07, A08, A19 | Hazard ratios, combining rule, taper and cap set; former smokers typed in from CTNS 2019; A18 now used by the engine |
| 2026-11-10 | A18 | Risk factor prevalence (CCHS) loaded and tested |
| 2026-11-10 | A07 | Survey factors and studies chosen; family history left out |
| 2026-11-10 | A09 | Mortality base period set to 2017–2019 (base year 2018); gap against the 2022–2024 table recorded |
| 2026-11-10 | A15 | Eligibility table now read to 2100 (year pattern fixed); open items listed |
| 2026-11-10 | A17 | Marriage, remarriage, divorce and first child loaded and tested |
| 2026-11-10 | A16 | CPP retirement take-up loaded and tested |
| 2026-11-10 | A15 | CPP disability incidence, termination and eligibility loaded and tested |
| 2026-11-10 | A09 | Event base years recorded; mortality base period left open |
| 2026-11-10 | A14 | Heart attack and stroke incidence loaded and tested |
| 2026-11-10 | A13 | Cancer incidence loaded; diagnosis probabilities built and tested |
| 2026-11-10 | A11, A12 | Population loaded; crash probabilities built and tested |
| 2026-11-10 | A11 | Crash injury and death counts loaded and tested |
| 2026-11-10 | A04, A06, A10 | Review fixes: PEI checks run without raw file; outdated A04 note; PEI noise note; external death-count check |
| 2026-11-10 | A10 | PEI single-age table derived and tested |
| 2026-11-10 | A06 | Cause-of-death groups loaded and tested |
| 2026-11-10 | A04 | Noted preliminary status of latest periods and StatCan release date; added external e(0) check |
| 2026-11-10 | A05 | MI-2024 loaded and tested |
| 2026-11-10 | A04 | Life tables loaded and tested (StatCan 13-10-0114-01) |
| 2026-11-10 | A01–A09 | Register created |
