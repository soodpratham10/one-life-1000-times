"""
Step 4 of the data pipeline: group StatCan deaths by cause into the model's
cause groups, by year, sex and age group.

StatCan's cause list is nested (e.g. "Malignant neoplasms" contains lung cancer),
so groups are built from labels that do not overlap; "other" is the remainder.

Input : data/raw/statcan_13100392/13100392.csv
        (python pipeline/download_statcan.py 13100392)
Output: data/clean/causes_of_death.csv
        columns: year, sex, age_lo, age_hi, cause, deaths

Run from the project folder:
    python pipeline/04_clean_causes_of_death.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "raw" / "statcan_13100392" / "13100392.csv"
OUT_CSV = ROOT / "data" / "clean" / "causes_of_death.csv"

# Short names for the StatCan labels we use (exact text from the table)
L = {
    "total": "Total, all causes of death [A00-Y89]",
    "cancer_all": "Malignant neoplasms [C00-C97]",
    "lung": "Malignant neoplasms of trachea, bronchus and lung [C33-C34]",
    "heart": "Diseases of heart [I00-I09, I11, I13, I20-I51]",
    "stroke": "Cerebrovascular diseases [I60-I69]",
    "copd": "Chronic lower respiratory diseases [J40-J47]",
    "diabetes": "Diabetes mellitus [E10-E14]",
    "alzheimers": "Alzheimer's disease [G30]",
    "dementia_other": "Dementia [F010-F019, F03]",
    "accidents_all": "Accidents (unintentional injuries) [V01-X59, Y85-Y86]",
    "motor_vehicle": "Motor vehicle accidents",
    "suicide": "Intentional self-harm (suicide) [X60-X84, Y87.0]",
    "homicide": "Assault (homicide) [X85-Y09, Y87.1]",
    "undetermined": "Events of undetermined intent [Y10-Y34, Y87.2, Y89.9]",
    "legal": "Legal intervention [Y35, Y89.0]",
    "war": "Operations of war and their sequelae [Y36, Y89.1]",
    "covid": "COVID-19 [U07.1, U07.2, U10.9]",
}

# The model's cause groups, in display order ("other" is added as the remainder)
CAUSES = [
    "lung_cancer", "other_cancer", "heart", "stroke", "copd", "diabetes",
    "dementia", "motor_vehicle", "other_accidents", "other_injury", "covid", "other",
]

SEXES = {"Both sexes": "B", "Males": "M", "Females": "F"}


def parse_age_group(label: str):
    """'Age at time of death, 20 to 24 years' -> (20, 24); under 1 -> (0, 0); 90+ -> (90, 110)."""
    text = label.replace("Age at time of death, ", "")
    if text == "under 1 year":
        return 0, 0
    if text == "90 years and over":
        return 90, 110
    lo, _, hi, _ = text.split()          # e.g. "20 to 24 years"
    return int(lo), int(hi)


def clean() -> pd.DataFrame:
    raw = pd.read_csv(
        RAW_CSV,
        usecols=["REF_DATE", "Age at time of death", "Sex", "Cause of death (ICD-10)",
                 "Characteristics", "VALUE"],
        low_memory=False,
    )
    raw = raw[raw["Characteristics"] == "Number of deaths"]

    # Drop the all-ages total and the few deaths with age not stated
    age = raw["Age at time of death"]
    raw = raw[~age.isin(["Age at time of death, all ages", "Age at time of death, not stated"])]

    missing = set(L.values()) - set(raw["Cause of death (ICD-10)"])
    if missing:
        raise ValueError(f"Cause labels not found (StatCan may have renamed them): {missing}")

    raw = raw[raw["Cause of death (ICD-10)"].isin(L.values())]

    # Missing counts ('..') are only acceptable for COVID-19 before 2020, when the
    # cause did not exist; those are true zeros. Anything else is a real gap: stop.
    missing_rows = raw[raw["VALUE"].isna()]
    expected_gap = (missing_rows["Cause of death (ICD-10)"] == L["covid"]) & (missing_rows["REF_DATE"] < 2020)
    if not expected_gap.all():
        bad = missing_rows[~expected_gap]
        raise ValueError(
            f"{len(bad)} unexpected missing death counts, e.g.\n"
            f"{bad[['REF_DATE', 'Sex', 'Age at time of death', 'Cause of death (ICD-10)']].head()}"
        )
    print(f"{len(missing_rows)} COVID-19 counts before 2020 not available; set to 0 (cause did not exist)")

    wide = raw.pivot(
        index=["REF_DATE", "Sex", "Age at time of death"],
        columns="Cause of death (ICD-10)",
        values="VALUE",
    ).fillna(0)
    wide = wide.rename(columns={v: k for k, v in L.items()})

    g = pd.DataFrame(index=wide.index)
    g["lung_cancer"] = wide["lung"]
    g["other_cancer"] = wide["cancer_all"] - wide["lung"]
    g["heart"] = wide["heart"]
    g["stroke"] = wide["stroke"]
    g["copd"] = wide["copd"]
    g["diabetes"] = wide["diabetes"]
    g["dementia"] = wide["alzheimers"] + wide["dementia_other"]
    g["motor_vehicle"] = wide["motor_vehicle"]
    g["other_accidents"] = wide["accidents_all"] - wide["motor_vehicle"]
    g["other_injury"] = wide[["suicide", "homicide", "undetermined", "legal", "war"]].sum(axis=1)
    g["covid"] = wide["covid"]
    g["other"] = wide["total"] - g.sum(axis=1)   # remainder: never negative if groups don't overlap
    g["total"] = wide["total"]

    long = g.reset_index().melt(
        id_vars=["REF_DATE", "Sex", "Age at time of death", "total"],
        var_name="cause", value_name="deaths",
    )
    ages = long["Age at time of death"].map(parse_age_group)
    out = pd.DataFrame({
        "year": long["REF_DATE"].astype(int),
        "sex": long["Sex"].map(SEXES),
        "age_lo": ages.str[0],
        "age_hi": ages.str[1],
        "cause": long["cause"],
        "deaths": long["deaths"].astype(int),
        "total_deaths": long["total"].astype(int),
    })
    out["cause"] = pd.Categorical(out["cause"], categories=CAUSES, ordered=True)
    return out.sort_values(["year", "sex", "age_lo", "cause"]).reset_index(drop=True)


def report(df: pd.DataFrame) -> None:
    print(f"Tidy table: {len(df):,} rows; years {df['year'].min()}-{df['year'].max()}")
    latest = df["year"].max()
    share = (
        df.query("year == @latest and sex == 'B'")
        .groupby("cause", observed=True)["deaths"].sum()
    )
    print(f"\nShare of all deaths by cause, Canada {latest}, both sexes:")
    print((share / share.sum() * 100).round(1).astype(str).add("%").to_string())


if __name__ == "__main__":
    tidy = clean()
    report(tidy)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    tidy.to_csv(OUT_CSV, index=False)
    print(f"\nSaved {OUT_CSV.relative_to(ROOT)} ({OUT_CSV.stat().st_size / 1e6:.1f} MB)")
