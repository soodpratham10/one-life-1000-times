# Data dictionary

Every cleaned file in `data/clean/`, and every hand-entered assumption table in `data/assumptions/`: what one row is, what each column means, where it comes from, which script builds it and which tests check it. `tests/test_data_dictionary.py` fails if a file or column here does not match the real files.

Codes used throughout: **sex** `M` men, `F` women, `B` both · **region** `CA` Canada, `NL` `PE` `NS` `NB` `QC` `ON` `MB` `SK` `AB` `BC` provinces (`YT` `NT` `NU` territories, where present) · **age_lo / age_hi** first and last age of a group (`110` = open top group) · probabilities are per year unless stated.

---

### `life_tables.csv`
One row per period x region x sex x single age 0–110. Source: Statistics Canada, Table 13-10-0114-01. Built by `pipeline/01_download_life_tables.py` and `pipeline/02_clean_life_tables.py`. Tests: `tests/test_life_tables.py`. Assumption A04.

| Column | Meaning |
| --- | --- |
| `period_start` | First year of the three-year period (e.g. 2022 for 2022–2024) |
| `period_end` | Last year of the period |
| `region` | Canada or province (PEI is in `life_tables_pei.csv`) |
| `sex` | M, F or B |
| `age` | Age x, 0–110 (110 = 110 and over) |
| `qx` | Probability of dying between age x and x+1 |
| `qx_moe` | Margin of error of qx |
| `px` | Probability of surviving from x to x+1 (1 − qx) |
| `lx` | Survivors at age x out of 100,000 born |
| `dx` | Deaths between x and x+1 out of 100,000 born |
| `Lx` | Person-years lived between x and x+1 |
| `Tx` | Person-years lived beyond age x |
| `ex` | Life expectancy at age x (years) |
| `ex_moe` | Margin of error of ex (blank for 110+) |

### `life_tables_pei.csv`
Prince Edward Island, single ages, derived from its abridged table (see A10). Built by `pipeline/05_build_pei_life_table.py`. Tests: `tests/test_pei.py`.

| Column | Meaning |
| --- | --- |
| `period_start` | First year of the three-year period |
| `period_end` | Last year of the period |
| `region` | Always PE |
| `sex` | M, F or B |
| `age` | Age x, 0–110 |
| `qx` | Probability of dying between x and x+1 (derived) |
| `px` | 1 − qx |
| `lx` | Survivors at age x out of 100,000 born |
| `ex` | Life expectancy at age x (years) |

### `life_tables_pei_abridged.csv`
Statistics Canada's published PEI values by age group, kept so the PEI checks run without the raw file. Source: Table 13-10-0140-01. Built by `pipeline/05_build_pei_life_table.py`.

| Column | Meaning |
| --- | --- |
| `period_start` | First year of the three-year period |
| `period_end` | Last year of the period |
| `sex` | M, F or B |
| `age_lo` | First age of the group (0, 1, 5, 10, …, 90) |
| `age_hi` | Last age of the group (110 for 90+) |
| `e_group` | Life expectancy at the start of the group (years) |
| `p_group` | Probability of surviving the whole group (0 for 90+) |

### `causes_of_death.csv`
Deaths by cause group, one row per year x sex x age group x cause. Source: Statistics Canada, Table 13-10-0392-01. Built by `pipeline/04_clean_causes_of_death.py`. Tests: `tests/test_causes_of_death.py`. Assumption A06.

| Column | Meaning |
| --- | --- |
| `year` | Calendar year, 2000–2024 |
| `sex` | M, F or B |
| `age_lo` | First age of the group (0 = under 1) |
| `age_hi` | Last age of the group (110 for 90+) |
| `cause` | One of 12 groups: lung_cancer, other_cancer, heart, stroke, copd, diabetes, dementia, motor_vehicle, other_accidents, other_injury, covid, other |
| `deaths` | Deaths from that cause |
| `total_deaths` | Deaths from all causes in the same year, sex and age group |

### `population.csv`
July 1 population. Source: Statistics Canada, Table 17-10-0005-01 (by gender: Men+ → M, Women+ → F). Built by `pipeline/07_clean_population.py`. Tests: `tests/test_population.py`. Assumption A12.

| Column | Meaning |
| --- | --- |
| `year` | 2000–2026 |
| `region` | Canada or province |
| `sex` | M, F or B |
| `age` | Single age 0–100 (100 = 100 and over) |
| `population` | People on July 1 |
| `all_ages_published` | StatCan's own all-ages total for the year, region and sex (for checking) |

### `crash_casualties.csv`
People injured or killed in police-reported motor vehicle collisions. Source: Transport Canada, National Collision Database. Built by `pipeline/06_clean_ncdb.py`. Tests: `tests/test_crash_casualties.py`. Assumption A11.

| Column | Meaning |
| --- | --- |
| `year` | 2019 or 2020 |
| `sex` | M or F (unknown sex spread in proportion) |
| `age` | 1–99 (99 = 99 and over; unknown age spread in proportion) |
| `injured` | People injured |
| `killed` | People killed (within 30 days) |

### `crash_rates.csv`
Yearly chance of being injured or killed in a crash. Built by `pipeline/08_crash_rates.py`. Tests: `tests/test_crash_rates.py`.

| Column | Meaning |
| --- | --- |
| `year` | 2019 or 2020 |
| `sex` | M or F |
| `age` | 1–99 |
| `injured` | People injured |
| `killed` | People killed |
| `population` | Canada's July 1 population, same year, sex and age |
| `p_injured` | injured ÷ population |
| `p_killed` | killed ÷ population |

### `cancer_incidence.csv`
New primary cancers. Source: Statistics Canada, Table 13-10-0111-01. Built by `pipeline/09_clean_cancer_incidence.py`. Tests: `tests/test_cancer.py`. Assumption A13.

| Column | Meaning |
| --- | --- |
| `year` | 1992–2023 |
| `geo` | CA (Canada), CA_exQC (Canada excluding Quebec) or QC |
| `sex` | M, F or B |
| `age_lo` | First age of the group |
| `age_hi` | Last age of the group (110 for 90+) |
| `cancer` | all (all primary sites) or lung |
| `cases` | New cases (rounded to 5 by StatCan; blank if suppressed) |
| `rate_per_100k` | StatCan's published rate per 100,000 |

### `cancer_rates.csv`
Yearly chance of a new cancer diagnosis, Canada 2019. Built by `pipeline/10_cancer_rates.py`. Tests: `tests/test_cancer.py`.

| Column | Meaning |
| --- | --- |
| `year` | 2019 |
| `sex` | M or F |
| `age_lo` | First age of the group |
| `age_hi` | Last age of the group |
| `cases_all` | New cancers, all sites |
| `cases_lung` | New lung cancers (0 where suppressed) |
| `population` | July 1 population of the group |
| `p_any_cancer` | cases_all ÷ population |
| `p_lung` | cases_lung ÷ population |
| `p_other_cancer` | p_any_cancer − p_lung |
| `statcan_p_any` | StatCan's published rate ÷ 100,000 (for checking) |
| `lung_suppressed` | True where StatCan suppressed the lung count (under 30 only) |

### `heart_stroke_incidence.csv`
Newly identified heart attacks and strokes, all regions and years. Source: Public Health Agency of Canada, CCDSS. Built by `pipeline/11_heart_stroke.py`. Tests: `tests/test_heart_stroke.py`. Assumption A14.

| Column | Meaning |
| --- | --- |
| `condition` | heart_attack (acute myocardial infarction) or stroke |
| `fiscal_year` | First year of the fiscal year (2018 = April 2018 – March 2019) |
| `region` | Canada, province or territory |
| `sex` | M, F or B |
| `age_group_type` | 5yr (5-year group) or total (all adults 20+) |
| `age_lo` | First age of the group |
| `age_hi` | Last age of the group (110 for 90+ and 20+) |
| `cases` | Newly identified cases (rounded to 5) |
| `population` | CCDSS registry population |
| `rate_per_100k` | PHAC's published crude rate per 100,000 |

### `heart_stroke_rates.csv`
Yearly chance of a heart attack or stroke, Canada 2018–19. Built by `pipeline/11_heart_stroke.py`.

| Column | Meaning |
| --- | --- |
| `fiscal_year` | 2018-19 |
| `sex` | M or F |
| `age_lo` | First age of the group (20, 25, …, 90) |
| `age_hi` | Last age of the group (110 for 90+) |
| `cases_heart_attack` | Newly identified heart attacks |
| `cases_stroke` | Newly identified strokes |
| `population_heart_attack` | CCDSS population for the heart attack data |
| `population_stroke` | CCDSS population for the stroke data |
| `rate_per_100k_heart_attack` | PHAC's published rate |
| `rate_per_100k_stroke` | PHAC's published rate |
| `p_heart_attack` | cases ÷ population |
| `p_stroke` | cases ÷ population |

### `cpp_disability_incidence.csv`
Yearly chance of starting a CPP disability pension, per 1,000 eligible. Source: 32nd CPP Actuarial Report, Table 85. Built by `pipeline/12_cpp_disability.py`. Tests: `tests/test_cpp_disability.py`. Assumption A15.

| Column | Meaning |
| --- | --- |
| `sex` | M or F |
| `age` | 18–64 |
| `per_1000` | New disability pensions per 1,000 eligible people |
| `method` | published, interpolated (log-linear between published ages) or held at age 25 |

### `cpp_disability_termination.csv`
How often a CPP disability ends (recovery, death or reaching 65). Source: Table 88. Built by `pipeline/12_cpp_disability.py`.

| Column | Meaning |
| --- | --- |
| `year` | 2025 or 2035 (ultimate) |
| `sex` | M or F |
| `age` | 30, 40, 50 or 60 (read as age at onset) |
| `duration` | Year of disability, 1–6 (6 = sixth year and later) |
| `per_1000` | Terminations per 1,000 people on disability |

### `cpp_disability_eligibility.csv`
Share of people aged 20–64 eligible for a CPP disability pension. Source: Table 73. Built by `pipeline/12_cpp_disability.py`.

| Column | Meaning |
| --- | --- |
| `year` | 2025–2035, then every 5 years to 2100 |
| `sex` | M or F |
| `eligible_pct` | Percent of the population aged 20–64 who are eligible |

### `cpp_retirement.csv`
Age at starting the CPP retirement pension. Source: Table 76. Built by `pipeline/13_cpp_retirement.py`. Tests: `tests/test_cpp_retirement.py`. Assumption A16.

| Column | Meaning |
| --- | --- |
| `sex` | M or F |
| `age` | 60–70 |
| `share_pct` | Percent of a cohort starting the pension at this age (adds to 100) |
| `p_start_given_not_started` | Yearly chance of starting, given not started yet (1 at 70) |

### `family_events.csv`
First marriage, remarriage, divorce and first child, Canada 2019. Sources: Statistics Canada, Tables 39-10-0057-01, 39-10-0053-01, 13-10-0421-01. Built by `pipeline/14_family_events.py`. Tests: `tests/test_family_events.py`. Assumption A17.

| Column | Meaning |
| --- | --- |
| `event` | first_marriage, remarriage, divorce or first_child |
| `sex` | M or F (first_child: F only) |
| `age_lo` | First age of the group |
| `age_hi` | Last age of the group (110 for the open top group) |
| `rate_per_1000` | Rate used by the model, per 1,000 people at risk |
| `rate_both_2019` | StatCan's 2019 rate for both sexes (marriage, divorce) |
| `sex_relativity` | Sex rate ÷ both-sexes rate in the reference year |
| `ref_year` | Year the sex relativity comes from (2002 marriage, 2017 divorce) |
| `count_2019` | Events in 2019 (both sexes for marriage and divorce; women for first child) |
| `at_risk_2019` | People at risk in 2019 (implied from StatCan's rate, or our population) |
| `counts_cover` | Whether count_2019 and at_risk_2019 cover both sexes or women |
| `at_risk_group` | Who the rate applies to (never legally married, divorced, married, all women) |

---

### `risk_prevalence.csv`
One row per year x region x sex x age group x risk factor: the share of people with that factor. Canadian Community Health Survey, 2015–2022 (the engine uses one year per factor, marked in `base`). Source: Statistics Canada, Table 13-10-0096-01. Built by `pipeline/15_risk_prevalence.py`. Tests: `tests/test_risk_prevalence.py`. Assumption A18.

| Column | Meaning |
| --- | --- |
| `year` | Survey year |
| `region` | `CA` is Canada excluding the territories |
| `sex` | M, F or B |
| `age_lo` | First age of the group: 18, 35, 50 or 65 (12 and 18 for the two totals) |
| `age_hi` | Last age of the group (110 for 65+ and for the totals) |
| `indicator` | current_smoker, daily_smoker, heavy_drinking, active_150 (150+ minutes of activity a week), overweight (BMI 25 to under 30), obese (BMI 30+), fruit_veg_5 (fruit and vegetables 5+ times a day) |
| `pct` | Percent of people in the group with the factor (blank if StatCan did not publish it) |
| `pct_low` | Lower end of StatCan's 95% confidence interval |
| `pct_high` | Upper end of StatCan's 95% confidence interval |
| `quality` | Blank = fine; E = use with caution; F = too unreliable to publish; x = suppressed; .. = not collected that year |
| `base` | True on the rows of the year the engine uses for that factor: the latest year up to 2019 with complete Canadian data (A18) |

---

## Assumption tables (`data/assumptions/`)

Small tables typed in from published studies, used by the engine. Each row carries its source.

### `assumptions/hazard_ratios.csv`
One row per risk factor x level (x sex where the study gives one). Read by `engine/risk.py`. Tests: `tests/test_risk.py`. Assumption A07.

| Column | Meaning |
| --- | --- |
| `factor` | smoking, activity, bmi, alcohol or fruit_veg |
| `level` | The answer group, e.g. quit_35_44, 150_299 (minutes a week), 25_27.5 (BMI), 25_44g (grams of alcohol a day), 5_plus (servings a day) |
| `sex` | M, F, or B where the same ratio is used for both |
| `hr` | Hazard ratio against the factor's reference level (which has 1.00) |
| `source` | Study and table the number comes from, or how it was derived |

### `assumptions/former_smokers.csv`
Share of adults who are former smokers, by sex and CCHS age group, mapped from the survey's own age groups. Read by `engine/risk.py`. Assumption A19.

| Column | Meaning |
| --- | --- |
| `sex` | M or F |
| `age_lo` | First age of the CCHS group (18, 35, 50, 65) |
| `age_hi` | Last age of the group (110 for 65+) |
| `pct` | Percent of all adults in the group who are former smokers |
| `ctns_group` | The survey age group the figure is taken from (25-44 or 45+) |
| `source` | Health Canada, Canadian Tobacco and Nicotine Survey 2019, Table 1 |

---

### Not in the public repo

`cia_mi2024.csv`: the CIA MI-2024 mortality improvement scale (columns `sex`, `age`, `year`, `mi`), built locally by `pipeline/03_clean_mi2024.py` from the CIA's own file. It is the CIA's copyrighted material, so it is listed in `.gitignore`; see the README for how to get it.
