"""
Step 14 of the data pipeline: family events, Canada, 2019 (the last year before COVID-19
disrupted weddings and divorce courts).

  First marriage  StatCan 39-10-0057-01: marriage rate per 1,000 persons of the same
                  marital status; "Never legally married"
  Remarriage      same table; "Divorced"
  Divorce         StatCan 39-10-0053-01: divorce rate per 1,000 married persons
  First child     StatCan 13-10-0421-01: live births by age and parity of mother; first
                  births / women of the same age (population from 07_clean_population.py).
                  Births with parity not stated are spread over parities in proportion.

Sex split. The marriage table has no split by gender after 2002, and the divorce table
none after 2017. For those events the 2019 rate for both sexes is kept as the level and the
male/female difference is borrowed from the last year with a split (relational method):

    rate(sex, age, 2019) = rate(both, age, 2019) x rate(sex, age, ref) / rate(both, age, ref)

with ref = 2002 for marriage and 2017 for divorce. See A17 in docs/assumptions.md.

Marriage here means LEGAL marriage; common-law unions are not in these tables.

Input : data/raw/statcan_39100057/39100057.csv, data/raw/statcan_39100053/39100053.csv,
        data/raw/statcan_13100421/13100421.csv   (python pipeline/download_statcan.py <table>)
        data/clean/population.csv
Output: data/clean/family_events.csv
        columns: event, sex, age_lo, age_hi, rate_per_1000, rate_both_2019, sex_relativity,
                 ref_year, count_2019, at_risk_2019, counts_cover, at_risk_group

Run from the project folder:
    python pipeline/14_family_events.py
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MARRIAGE_CSV = RAW / "statcan_39100057" / "39100057.csv"
DIVORCE_CSV = RAW / "statcan_39100053" / "39100053.csv"
BIRTHS_CSV = RAW / "statcan_13100421" / "13100421.csv"
POP_CSV = ROOT / "data" / "clean" / "population.csv"
OUT_CSV = ROOT / "data" / "clean" / "family_events.csv"
YEAR = 2019
REF_YEAR = {"marriage": 2002, "divorce": 2017}


def parse_age(label: str):
    """Age-group labels in these tables -> (lo, hi). Returns None for totals / not stated."""
    text = label.replace("Age of mother, ", "")
    if re.search(r"all ages|Total|not stated", text, re.I):
        return None
    m = re.match(r"[Uu]nder (\d+) years", text)       # under 20 -> 15-19, under 15 -> 10-14
    if m:
        return (int(m.group(1)) - 5, int(m.group(1)) - 1)
    m = re.match(r"(\d+) years and over", text)
    if m:
        return (int(m.group(1)), 110)
    m = re.match(r"(\d+) to (\d+) years", text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    raise ValueError(f"Unexpected age label: {label!r}")


def relational(df, sex_col, both, male, female, age_col, rate_name, count_name, ref_year):
    """2019 both-sexes level x sex relativity from ref_year, for one event."""
    df = df[df[age_col].map(parse_age).notna()]
    rate = df[df["Indicator"] == rate_name]
    count = df[df["Indicator"] == count_name]

    level = rate[(rate["REF_DATE"] == YEAR) & (rate[sex_col] == both)].set_index(age_col)["VALUE"]
    n2019 = count[(count["REF_DATE"] == YEAR) & (count[sex_col] == both)].set_index(age_col)["VALUE"]
    ref = rate[rate["REF_DATE"] == ref_year].pivot_table(index=age_col, columns=sex_col, values="VALUE")
    for needed in (male, female, both):
        if needed not in ref:
            raise ValueError(f"No {needed!r} rates in {ref_year}")
    if level.isna().any() or len(level) == 0:
        raise ValueError(f"Missing {YEAR} both-sexes rates")

    rows = []
    for label, lvl in level.items():
        lo, hi = parse_age(label)
        for sex, col in (("M", male), ("F", female)):
            base = ref.loc[label, both]
            rel = ref.loc[label, col] / base if base > 0 else 1.0
            rows.append({"sex": sex, "age_lo": lo, "age_hi": hi,
                         "rate_per_1000": lvl * rel, "rate_both_2019": lvl,
                         "sex_relativity": rel, "ref_year": ref_year,
                         "count_2019": n2019[label],
                         "at_risk_2019": n2019[label] / lvl * 1000 if lvl > 0 else np.nan,
                         "counts_cover": "both sexes"})
    return pd.DataFrame(rows)


def marriage() -> pd.DataFrame:
    raw = pd.read_csv(MARRIAGE_CSV, low_memory=False)
    raw = raw[raw["GEO"] == "Canada"]
    out = []
    for status, event, group in [("Never legally married", "first_marriage", "never legally married"),
                                 ("Divorced", "remarriage", "divorced")]:
        part = relational(raw[raw["Legal marital status prior to marriage"] == status],
                          "Gender", "Total – Gender", "Men+", "Women+", "Age at marriage",
                          "Marriage rate", "Number of persons who married", REF_YEAR["marriage"])
        part = part.assign(event=event, at_risk_group=group)
        if event == "remarriage":
            # Almost nobody is divorced before 20, so that group's rate is noise (or blank).
            # Use the 20-24 rate instead, flagged in sex_relativity's note column.
            for sex in ("M", "F"):
                young = (part["sex"] == sex) & (part["age_lo"] == 15)
                adult = (part["sex"] == sex) & (part["age_lo"] == 20)
                part.loc[young, "rate_per_1000"] = part.loc[adult, "rate_per_1000"].item()
                part.loc[young, "at_risk_group"] = "divorced (under 20: 20-24 rate used)"
        out.append(part)
    return pd.concat(out, ignore_index=True)


def divorce() -> pd.DataFrame:
    raw = pd.read_csv(DIVORCE_CSV, low_memory=False)
    raw = raw[raw["GEO"] == "Canada"]
    part = relational(raw, "Sex or gender", "Both sexes", "Males", "Females", "Age at divorce",
                      "Divorce rate", "Number of divorces", REF_YEAR["divorce"])
    return part.assign(event="divorce", at_risk_group="married")


def first_birth() -> pd.DataFrame:
    raw = pd.read_csv(BIRTHS_CSV, low_memory=False)
    raw = raw[(raw["REF_DATE"] == YEAR) & (raw["Characteristics"] == "Number of live births")]
    raw = raw[raw["Age of mother"].map(parse_age).notna()]
    w = raw.pivot_table(index="Age of mother", columns="Parity of mother", values="VALUE")
    known = w["Total, parity of mother"] - w["Parity of mother, not stated"]
    first = w["Parity of mother, first live birth"] * w["Total, parity of mother"] / known

    pop = pd.read_csv(POP_CSV)
    pop = pop[(pop["year"] == YEAR) & (pop["region"] == "CA") & (pop["sex"] == "F")]
    rows = []
    for label, n in first.items():
        lo, hi = parse_age(label)
        women = pop[pop["age"].between(lo, hi)]["population"].sum()
        rows.append({"event": "first_child", "sex": "F", "age_lo": lo, "age_hi": hi,
                     "rate_per_1000": n / women * 1000, "rate_both_2019": np.nan,
                     "sex_relativity": np.nan, "ref_year": np.nan,
                     "count_2019": n, "at_risk_2019": women, "counts_cover": "women",
                     "at_risk_group": "all women of that age"})
    return pd.DataFrame(rows)


COLUMNS = ["event", "sex", "age_lo", "age_hi", "rate_per_1000", "rate_both_2019", "sex_relativity",
           "ref_year", "count_2019", "at_risk_2019", "counts_cover", "at_risk_group"]

if __name__ == "__main__":
    table = pd.concat([marriage(), divorce(), first_birth()], ignore_index=True)[COLUMNS]
    table[["age_lo", "age_hi"]] = table[["age_lo", "age_hi"]].astype(int)
    table = table.sort_values(["event", "sex", "age_lo"]).reset_index(drop=True)

    for event, g in table.groupby("event", sort=False):
        print(f"\n{event}: rate per 1,000 ({g['at_risk_group'].iloc[0]}), {YEAR}")
        print(g.pivot_table(index=["age_lo", "age_hi"], columns="sex", values="rate_per_1000")
              .round(1).to_string())

    table.to_csv(OUT_CSV, index=False, float_format="%.6g")
    print(f"\nSaved {OUT_CSV.relative_to(ROOT)}")
