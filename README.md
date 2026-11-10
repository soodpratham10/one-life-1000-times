# One Life, 1,000 Times

> Nobody can tell you how your life will go. Here are 1,000 ways it could.

**Status: in development (Phase 0 — foundation).** Nothing below is built or verified yet. This README will be updated as each phase is finished.

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

All inputs will come from official or peer-reviewed public sources (Statistics Canada, the Canadian Institute of Actuaries, Transport Canada, Canadian Cancer Statistics, published research). Each source will be listed here with its table number and access date once it is checked.

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
