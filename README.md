# One Life, 1,000 Times

[![tests](https://github.com/soodpratham10/one-life-1000-times/actions/workflows/tests.yml/badge.svg)](https://github.com/soodpratham10/one-life-1000-times/actions/workflows/tests.yml)
[![release](https://img.shields.io/github/v/release/soodpratham10/one-life-1000-times)](https://github.com/soodpratham10/one-life-1000-times/releases)
[![licence: MIT](https://img.shields.io/badge/licence-MIT-blue)](LICENSE)

> Nobody can tell you how your life will go. Here are 1,000 ways it could.

**Status: in development. Phase 1 of 6 (data) is complete and released as [v0.1.0](https://github.com/soodpratham10/one-life-1000-times/releases/tag/v0.1.0); Phase 2 (engine) is in progress.** Personal death rates (base table, mortality improvement and survey risk multipliers) are built and tested; the year-by-year simulation of events is not built yet. This README is updated as each step is finished.

## What this is

A life simulator built on real Canadian data. You answer a short survey; the model lives your life forward year by year (health, accidents, family, work, and how it ends), then does it again, 1,000 times, so you can see the realistic range of how things could go and which of your choices move the odds.

**Aim (draft):** show someone the realistic range of how their life could unfold, using the data and methods actuaries use, and show which of their choices actually change the odds.

### What this is not

- Not a prediction of when or how you will die. No model can do that for one person; this shows probabilities.
- Not medical, financial or insurance advice.
- Not an insurance price. There are no premiums or reserves in this project.

## Planned events (version 1)

| Event | Notes |
| --- | --- |
| Death, by cause | 11 cause groups plus "all other causes" (see A06) |
| Disability | CPP-style severe and prolonged disability; can end |
| Injured in a car crash | Police-reported injury of any severity; can happen more than once |
| Cancer diagnosis | Raises later mortality |
| Heart attack or stroke | Raises later mortality |
| Marriage | Legal marriage; affects later mortality |
| Divorce | Only after a marriage |
| Remarriage | Only after a divorce |
| First child | |
| Retirement | Starting the CPP retirement pension, ages 60–70 |

Widowhood, job loss and home purchase are planned for version 2.

## Survey questions (version 1)

Each answer moves your death rates by a hazard ratio from a large published study. All ratios, with their sources, are in [`data/assumptions/hazard_ratios.csv`](data/assumptions/hazard_ratios.csv).

| Question | Study |
| --- | --- |
| Smoking: never, former (and the age you quit), current | Jha et al., *NEJM* 2013; Pirie et al., *Lancet* 2013 |
| Minutes of moderate or vigorous activity a week | Arem et al., *JAMA Internal Medicine* 2015 |
| Height and weight (BMI) | Global BMI Mortality Collaboration, *Lancet* 2016 |
| Drinks a week | Zhao et al., *JAMA Network Open* 2023 |
| Servings of fruit and vegetables a day | Wang et al., *Circulation* 2021 |

Official death rates already include everyone, smokers and non-smokers alike, so the model first divides out the Canadian population's average mix of these habits (from the Canadian Community Health Survey) and then applies yours. Smoking also changes what people die of (lung cancer and COPD far more than other causes), using cause-specific ratios from Thun et al., *NEJM* 2013. A check: with these ratios, the gap between the healthiest and least healthy habits comes out at about 18 years of life expectancy, close to the 17.9 years found for Canada by the MPoRT study (Manuel et al., *PLOS Medicine* 2016).

## Method (planned)

The structure follows how life insurers underwrite: a base mortality table, personal risk multipliers, future mortality improvement, competing risks between events, and an actual-to-expected check against official data. Published data is used where insurers use proprietary underwriting manuals. Every assumption, its source and its weakness is listed in [`docs/assumptions.md`](docs/assumptions.md).

## Roadmap

| Phase | What it covers | Status |
| --- | --- | --- |
| 0. Setup | Environment, repository, licence | Done |
| 1. Data | Pipeline, cleaned tables, assumptions register, data dictionary, tests | Done (v0.1.0) |
| 2. Engine | Mortality projection, survey risk multipliers, competing risks, 1,000 simulated lives | In progress (2 of 4 steps done) |
| 3. Links between events | Disability recovery vs death, higher mortality after cancer or a heart attack, marriage effects | Planned |
| 4. Validation | Actual-to-expected checks against official figures; independent R and Excel cross-checks | Planned |
| 5. Website | Survey and interactive visuals | Planned |
| 6. Launch | Write-up and release | Planned |

## Data

All inputs come from official public sources. Every cleaned file and column is described in [`docs/data_dictionary.md`](docs/data_dictionary.md).

| Source | Used for |
| --- | --- |
| Statistics Canada life tables (13-10-0114-01; PEI abridged 13-10-0140-01) | Base death rates by age, sex and province |
| Canadian Institute of Actuaries, MI-2024 | Future mortality improvement (not committed; see below) |
| Statistics Canada causes of death (13-10-0392-01) | Splitting deaths into 12 cause groups |
| Transport Canada, National Collision Database | Car crash injuries |
| Statistics Canada cancer incidence (13-10-0111-01) | Cancer diagnoses |
| Public Health Agency of Canada, CCDSS | Heart attacks and strokes |
| Office of the Chief Actuary, 32nd CPP Actuarial Report | Disability and retirement |
| Statistics Canada marriages, divorces, births (39-10-0057-01, 39-10-0053-01, 13-10-0421-01) | Marriage, divorce, remarriage, first child |
| Statistics Canada population (17-10-0005-01) | Denominators for event rates |
| Statistics Canada, Canadian Community Health Survey (13-10-0096-01) | How common smoking, inactivity, obesity and low fruit and vegetable intake are, by age and sex |
| Health Canada, Canadian Tobacco and Nicotine Survey 2019 | How common former smokers are, by age and sex |

<details>
<summary><b>Full source details, and how to get the hand-downloaded files</b></summary>

| Source | What it gives | In this repo? |
| --- | --- | --- |
| Statistics Canada, Table 13-10-0114-01 (complete life tables, three-year estimates) | Death probabilities by single age 0–110+, sex, Canada and 9 provinces, 1980–1982 to 2022–2024 | Cleaned copy yes (`data/clean/life_tables.csv`); raw file is re-downloaded by `pipeline/01_download_life_tables.py` |
| Statistics Canada, Table 13-10-0140-01 (abridged life tables, PEI) | PEI death probabilities by age group; turned into single ages by borrowing the within-group shape of NS and NB (see A10 in `docs/assumptions.md`) | Derived single-age table yes (`data/clean/life_tables_pei.csv`); raw file via `python pipeline/download_statcan.py 13100140` |
| Statistics Canada, Table 13-10-0392-01 (deaths by selected grouped causes) | Deaths by 12 cause groups, sex and 5-year age group, Canada, 2000–2024 | Cleaned copy yes (`data/clean/causes_of_death.csv`); raw file via `python pipeline/download_statcan.py 13100392` |
| Transport Canada, National Collision Database (open data, 2019 and 2020) | People injured and killed in police-reported collisions, by sex and age | Cleaned counts yes (`data/clean/crash_casualties.csv`); raw files downloaded by `pipeline/06_clean_ncdb.py` |
| Statistics Canada, Table 17-10-0005-01 (population on July 1, by age and gender) | Population by province, sex and single age, 2000–2026: the denominator for event rates | Cleaned copy yes (`data/clean/population.csv`); raw file via `python pipeline/download_statcan.py 17100005` |
| Statistics Canada, Table 13-10-0111-01 (new cases of primary cancer) | New cancer cases (all, and lung) by sex and 5-year age group, Canada, Quebec and Canada excluding Quebec, 1992–2023 | Cleaned extract yes (`data/clean/cancer_incidence.csv`); raw file (about 1.8 GB) via `python pipeline/download_statcan.py 13100111` |
| Public Health Agency of Canada, Canadian Chronic Disease Surveillance System (Health Infobase data tool) | Newly identified heart attacks and strokes by sex and 5-year age group, Canada and provinces, 2000–01 to 2023–24 | Cleaned copy yes (`data/clean/heart_stroke_incidence.csv`); raw files downloaded by hand (below) |
| Office of the Chief Actuary (OSFI), 32nd Actuarial Report on the Canada Pension Plan (Tables 73, 76, 85, 88) | CPP disability: chance per year of a severe and prolonged disability by age and sex, how long it lasts, and the share of adults eligible. Retirement: share starting the CPP pension at each age 60–70 | Extracted tables yes (`data/clean/cpp_disability_*.csv`, `data/clean/cpp_retirement.csv`); report PDF downloaded by hand (below) |
| Statistics Canada, Table 13-10-0096-01 (health characteristics, Canadian Community Health Survey) | Percent of people who smoke, drink heavily, are active 150+ minutes a week, are overweight or obese, or eat fruit and vegetables 5+ times a day, by sex and age group (18–34, 35–49, 50–64, 65+), Canada and provinces, 2015–2022 | Cleaned copy yes (`data/clean/risk_prevalence.csv`); raw file via `python pipeline/download_statcan.py 13100096` |
| Statistics Canada, Tables 39-10-0057-01, 39-10-0053-01 and 13-10-0421-01 (marriages, divorces, births by parity) | First marriage, remarriage, divorce and first-child rates by sex and age group, Canada, 2019 | Rates yes (`data/clean/family_events.csv`); raw files via `python pipeline/download_statcan.py 39100057` (and `39100053`, `13100421`) |
| Health Canada, Canadian Tobacco and Nicotine Survey 2019, Table 1 | Percent of former smokers by sex and age group (25–44, 45+) | Typed in (`data/assumptions/former_smokers.csv`) |
| Canadian Institute of Actuaries, MI-2024 mortality improvement scale ("Mortality Improvements Research – Tables", 2024) | Annual improvement rates by sex, age 20–120 and calendar year 1981–2119 | **No.** The scale is the CIA's copyrighted material. Download it yourself (below) |

### Getting the CIA MI-2024 file

1. Download "Mortality Improvements Research – Tables" from the CIA website (cia-ica.ca, publication 224043).
2. Save it as `data/raw/cia_mi2024/224043te.xlsx`.
3. Run `python pipeline/03_clean_mi2024.py`.

Without it, the MI-2024 tests are skipped rather than failed.

### Getting the CCDSS heart attack and stroke files

1. Open the CCDSS data tool on health-infobase.canada.ca and choose the **Age Distribution** view.
2. Condition **Acute myocardial infarction**, measure **Crude incidence rate**; click **Download Detailed Table**. Save as `data/raw/ccdss/ccdss_ami_by_age.csv`.
3. Repeat for **Stroke**; save as `data/raw/ccdss/ccdss_stroke_by_age.csv`.
4. Run `python pipeline/11_heart_stroke.py`.

The download contains every year, whatever year the tool shows on screen.

### Getting the CPP actuarial report

1. Download the 32nd Actuarial Report on the Canada Pension Plan (revised version) PDF, `cpp32-rev-ed-en.pdf`, from osfi-bsif.gc.ca (Office of the Chief Actuary).
2. Save it as `data/raw/oca/cpp32-rev-ed-en.pdf`.
3. Run `python pipeline/12_cpp_disability.py` and `python pipeline/13_cpp_retirement.py` (they read the tables straight from the PDF).

</details>

## Run it locally

Requires [Anaconda or Miniconda](https://docs.conda.io/).

```bash
conda env create -f environment.yml
conda activate onelife
pytest                          # checks the cleaned data already in data/clean/
```

To rebuild every cleaned file from the original sources (downloads several tables; the hand-downloaded files described above must be in place first):

```bash
python pipeline/run_all.py --plan    # show what will run and what is missing
python pipeline/run_all.py           # rebuild
pytest
```

## Repository layout

```
.github/workflows/   automatic test run on every push
data/raw/            source files as published (not committed; rebuilt by the pipeline)
data/clean/          cleaned tables used by the model (see docs/data_dictionary.md)
data/assumptions/    small tables typed in from published studies (hazard ratios, former smokers)
pipeline/            numbered scripts 01–15 that build data/clean, run in order by run_all.py
  download_statcan.py   helper: download and summarise any Statistics Canada table
  inspect_excel.py      helper: show what is inside an Excel workbook
tests/               pytest suite: one file per data source, plus the data dictionary check
docs/                assumptions.md (every assumption and its weakness), data_dictionary.md
engine/              simulation engine (Phases 2–3, in progress: mortality.py, risk.py, causes.py done)
crosscheck/          independent R and Excel checks (Phase 4, not built yet)
web/                 survey and visuals (Phase 5, not built yet)
```

## Known limits

Each assumption's weaknesses are listed in [`docs/assumptions.md`](docs/assumptions.md). The main ones so far:

- Adults 18+ only; people with an existing serious diagnosis are out of scope.
- Official tables are by sex; the population table is by gender (a very small difference, see A12).
- Causes of death, crashes, cancer, heart attack and stroke use national rates for every province.
- Crash data cannot separate minor from serious injuries; cancer counts are counts of cancers, not people.
- Disability means CPP disability (severe and prolonged, people with enough CPP contributions; outside Quebec).
- Retirement means starting the CPP retirement pension, which is not always the same as stopping work.
- Marriage means legal marriage; common-law unions are not covered by the marriage and divorce tables.
- Territories are not modelled.

## Licence

- **Code:** MIT (see [`LICENSE`](LICENSE)).
- **Data:** contains information licensed under the [Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada) (Statistics Canada, Transport Canada, Public Health Agency of Canada). The CPP disability and retirement tables are taken from the Office of the Chief Actuary's 32nd Actuarial Report on the Canada Pension Plan (Office of the Superintendent of Financial Institutions), reproduced for non-commercial use with attribution. The CIA MI-2024 scale is not included and remains the Canadian Institute of Actuaries' copyright.

## Author

Pratham Sood, Actuarial Mathematics & Statistics, University of Manitoba.
