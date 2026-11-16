"""
Build the Excel workbook for the VBA cross-check (Phase 4).

Run from the project folder:
    python crosscheck/excel/build_workbook.py

Writes crosscheck/excel/one_life_crosscheck.xlsx with:
    ReadMe       how to add the macro and run it
    HandCheck    one year for one person worked as visible Excel formulas
    Results      filled by the macro: one person, age by age, against Python
    Summary      filled by the macro: all 12 reference people and the population
    Data_q       2017-2019 death probabilities by region and sex (StatCan)
    Data_hr      hazard ratios (data/assumptions/hazard_ratios.csv)
    Data_prev    CCHS prevalence used by the engine (base years, Canada)
    Data_former  former-smoker shares (CTNS 2019)
    Reference    the Python engine's answers (crosscheck/reference/risk_reference.csv)

The data sheets are the raw inputs, copied as they are; the macro
(crosscheck/vba/OneLifeCheck.bas) builds everything else from them itself.
No CIA data goes in the workbook, so it can be committed.
"""

import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.mortality import MAX_AGE, REGIONS, base_qx  # noqa: E402

OUT = ROOT / "crosscheck" / "excel" / "one_life_crosscheck.xlsx"
REF = ROOT / "crosscheck" / "reference" / "risk_reference.csv"
HAND_CASE, HAND_AGE = "former_35_44_F62", 62

BOLD = Font(bold=True)
TITLE = Font(bold=True, size=14)
INPUT = PatternFill("solid", fgColor="FFF2CC")       # values typed in from data
CALC = PatternFill("solid", fgColor="E2EFDA")        # formulas
NOTE = Font(italic=True, color="666666")


def widths(ws, cols):
    for i, w in enumerate(cols, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def table(ws, df: pd.DataFrame) -> None:
    ws.append(list(df.columns))
    for c in ws[1]:
        c.font = BOLD
    for row in df.itertuples(index=False):
        ws.append([None if (isinstance(v, float) and pd.isna(v)) else v for v in row])
    ws.freeze_panes = "A2"


def readme(ws) -> None:
    lines = [
        ("One Life, 1,000 Times: Excel VBA cross-check", TITLE),
        ("An independent rebuild of the risk engine in VBA, checked against the Python engine.", None),
        ("", None),
        ("Add the macro (once):", BOLD),
        ("1. Show the Developer tab: Excel > Settings > Ribbon & Toolbar > tick Developer.", None),
        ("2. Developer > Visual Basic. In the editor: File > Import File > crosscheck/vba/OneLifeCheck.bas.", None),
        ("3. Close the editor. File > Save As > Excel Macro-Enabled Workbook (.xlsm), same folder.", None),
        ("", None),
        ("Run it:", BOLD),
        ("CheckAllCases: Developer > Macros > CheckAllCases > Run. Fills Summary: every reference value, PASS or FAIL.", None),
        ("RunCase: type a case name in Results!B1 (list in Summary after CheckAllCases), then run RunCase.", None),
        ("", None),
        ("HandCheck: one year for one person as plain formulas (no macro), so it can be followed by hand.", None),
        ("Covers: base rates, population mix, hazard ratios, taper, habits that change with age (A26),", None),
        ("quitting smoking (A27), the cap, death rates and life expectancy, on 2017-2019 rates with no improvement.", None),
        ("Yellow cells are values copied from the data; green cells are formulas.", NOTE),
    ]
    for text, font in lines:
        ws.append([text])
        if font:
            ws.cell(ws.max_row, 1).font = font
    ws.column_dimensions["A"].width = 120


def hand_check(ws, ref: pd.DataFrame, prev: pd.DataFrame, former: pd.DataFrame, hr: pd.DataFrame) -> None:
    case = ref[ref["case"] == HAND_CASE].iloc[0]
    sex, region = case["sex"], case["region"]

    def h(factor, level):
        rows = hr[(hr["factor"] == factor) & (hr["level"] == level)]
        own = rows[rows["sex"] == sex]
        return float((own if len(own) else rows[rows["sex"] == "B"])["hr"].iloc[0])

    def pct(indicator):
        r = prev[(prev["sex"] == sex) & (prev["age_lo"] == 50) & (prev["indicator"] == indicator)]
        return float(r["pct"].iloc[0]) / 100

    widths(ws, [34, 16, 12, 16, 60])
    ws.append([f"One year by hand: {HAND_CASE}, age {HAND_AGE}"])
    ws["A1"].font = TITLE
    ws.append(["Woman, 62, Nova Scotia, quit smoking at 40, 150 minutes of activity a week, 160 cm, 72 kg "
               "(BMI 28.1), 7 drinks a week, 5 servings of fruit and vegetables a day."])
    ws.append(["At 62 she is in the same CCHS age group as when she answered (50-64), so her activity and BMI "
               "have not drifted (A26), she is not a current smoker (A27), and the taper is 1 (A08)."])
    ws.append([])
    ws.append(["Population mix, women 50-64", "share", "", "", "source"])
    ws.cell(ws.max_row, 1).font = BOLD
    inputs = {}
    for label, value, src in (
        ("current smokers", pct("current_smoker"), "CCHS 13-10-0096-01, base year (Data_prev)"),
        ("former smokers", float(former[(former["sex"] == sex) & (former["age_lo"] == 50)]["pct"].iloc[0]) / 100,
         "CTNS 2019 (Data_former)"),
        ("active 150+ minutes a week", pct("active_150"), "CCHS (Data_prev)"),
        ("overweight (BMI 25-30)", pct("overweight"), "CCHS (Data_prev)"),
        ("obese (BMI 30+)", pct("obese"), "CCHS (Data_prev)"),
        ("fruit and vegetables 5+ a day", pct("fruit_veg_5"), "CCHS (Data_prev)"),
    ):
        ws.append([label, value, "", "", src])
        ws.cell(ws.max_row, 2).fill = INPUT
        inputs[label] = f"B{ws.max_row}"
    cur, frm = inputs["current smokers"], inputs["former smokers"]
    act, ovr, obs, five = (inputs["active 150+ minutes a week"], inputs["overweight (BMI 25-30)"],
                           inputs["obese (BMI 30+)"], inputs["fruit and vegetables 5+ a day"])
    ws.append([])
    ws.append(["Level", "share", "hazard ratio", "share x ratio", "how the share is made (A18, A19)"])
    for c in ws[ws.max_row]:
        c.font = BOLD

    blocks = {
        "smoking": [("never", f"=1-{cur}-{frm}", "1 - current - former"), ("current", f"={cur}", "CCHS"),
                    ("quit_before_35", f"={frm}*0.4", "former x 40% (50+ split)"),
                    ("quit_35_44", f"={frm}*0.3", "former x 30%"), ("quit_45_54", f"={frm}*0.2", "former x 20%"),
                    ("quit_55_plus", f"={frm}*0.1", "former x 10%")],
        "activity": [("none", f"=(1-{act})*0.5", "half of those under 150"),
                     ("under_150", f"=(1-{act})*0.5", "half of those under 150"),
                     ("150_299", f"={act}*0.5", "half of those 150+"), ("300_449", f"={act}*0.25", "a quarter"),
                     ("450_plus", f"={act}*0.25", "a quarter")],
        "bmi": [("18.5_25", f"=1-{ovr}-{obs}", "1 - overweight - obese"),
                ("25_27.5", f"={ovr}*0.5", "half of overweight"), ("27.5_30", f"={ovr}*0.5", "half of overweight"),
                ("30_35", f"={obs}*15.2/23", "obese x 15.2/23 (2004 measured)"),
                ("35_40", f"={obs}*5.1/23", "obese x 5.1/23"), ("40_plus", f"={obs}*2.7/23", "obese x 2.7/23")],
        "alcohol": [("under_25g", "=1", "no Canadian volume figures: not normalised")],
        "fruit_veg": [("0_2", f"=1-{five}", "below 5 counted at 2"), ("5_plus", f"={five}", "CCHS")],
    }
    person_level = {"smoking": "quit_35_44", "activity": "150_299", "bmi": "27.5_30",
                    "alcohol": "under_25g", "fruit_veg": "5_plus"}
    averages, own = [], []
    for factor, rows in blocks.items():
        ws.append([factor])
        ws.cell(ws.max_row, 1).font = BOLD
        first = ws.max_row + 1
        for level, formula, how in rows:
            ws.append([level, formula, h(factor, level), None, how])
            r = ws.max_row
            ws[f"B{r}"].fill = CALC
            ws[f"C{r}"].fill = INPUT
            ws[f"D{r}"] = f"=B{r}*C{r}"
            ws[f"D{r}"].fill = CALC
            if level == person_level[factor]:
                own.append(f"C{r}")
                ws[f"A{r}"].font = BOLD
        last = ws.max_row
        ws.append([f"average {factor} ratio", f"=SUM(B{first}:B{last})", "", f"=SUM(D{first}:D{last})",
                   "shares add to 1; the average is the share-weighted ratio"])
        ws[f"D{ws.max_row}"].fill = CALC
        averages.append(f"D{ws.max_row}")
    ws.append([])
    base = float(base_qx(region, sex)[HAND_AGE])
    python_q = float(ref[(ref["case"] == HAND_CASE) & (ref["measure"] == "personal_q")
                         & (ref["at_age"] == HAND_AGE)]["value"].iloc[0])
    python_r = float(ref[(ref["case"] == HAND_CASE) & (ref["measure"] == "relative_multiplier")
                         & (ref["at_age"] == HAND_AGE)]["value"].iloc[0])
    steps = [
        ("population average multiplier", "=" + "*".join(averages), "product over the five factors (A08)"),
        ("her multiplier", "=" + "*".join(own), "product of her own ratios (bold rows)"),
        ("relative multiplier r", None, "her multiplier / average, kept between 0.35 and 5 (A08)"),
        ("2017-2019 death probability, NS women at 62", base, "StatCan life table (Data_q)"),
        ("her death probability this year", None, "1 - (1 - q) ^ r: the ratio scales the force of mortality"),
        ("Python engine: relative multiplier", python_r, "crosscheck/reference/risk_reference.csv"),
        ("Python engine: her death probability", python_q, "crosscheck/reference/risk_reference.csv"),
        ("difference in r (formula - Python)", None, ""),
        ("difference in q (formula - Python)", None, ""),
    ]
    rows = {}
    for label, value, how in steps:
        ws.append([label, value, "", "", how])
        rows[label] = ws.max_row
        ws[f"B{ws.max_row}"].fill = INPUT if isinstance(value, float) else CALC
    ws[f"B{rows['relative multiplier r']}"] = (
        f"=MIN(MAX(B{rows['her multiplier']}/B{rows['population average multiplier']},0.35),5)")
    ws[f"B{rows['her death probability this year']}"] = (
        f"=1-(1-B{rows['2017-2019 death probability, NS women at 62']})^B{rows['relative multiplier r']}")
    ws[f"B{rows['difference in r (formula - Python)']}"] = (
        f"=B{rows['relative multiplier r']}-B{rows['Python engine: relative multiplier']}")
    ws[f"B{rows['difference in q (formula - Python)']}"] = (
        f"=B{rows['her death probability this year']}-B{rows['Python engine: her death probability']}")
    for r in rows.values():
        ws[f"B{r}"].number_format = "0.000000000000"
    for row in ws.iter_rows(min_row=5):
        for c in row:
            c.alignment = Alignment(vertical="top")


def main() -> None:
    ref = pd.read_csv(REF)
    hr = pd.read_csv(ROOT / "data" / "assumptions" / "hazard_ratios.csv")[["factor", "level", "sex", "hr"]]
    prev = pd.read_csv(ROOT / "data" / "clean" / "risk_prevalence.csv")
    prev = prev[prev["base"] & (prev["region"] == "CA") & prev["sex"].isin(["M", "F"])
                & prev["age_lo"].isin([18, 35, 50, 65])]
    prev = prev[["sex", "age_lo", "age_hi", "indicator", "pct", "year"]].sort_values(["sex", "age_lo", "indicator"])
    former = pd.read_csv(ROOT / "data" / "assumptions" / "former_smokers.csv")[["sex", "age_lo", "age_hi", "pct"]]

    q = pd.DataFrame({"age": range(MAX_AGE + 1)})
    for region in REGIONS:
        for sex in ("M", "F"):
            q[f"{region}_{sex}"] = base_qx(region, sex)

    wb = Workbook()
    readme(wb.active)
    wb.active.title = "ReadMe"
    hand_check(wb.create_sheet("HandCheck"), ref, prev, former, hr)
    res = wb.create_sheet("Results")
    res["A1"], res["B1"] = "Case:", "never_typical_M25"
    res["A1"].font = BOLD
    res["B1"].fill = INPUT
    res["A2"] = "Type a case name in B1, then run the RunCase macro."
    res["A2"].font = NOTE
    summ = wb.create_sheet("Summary")
    summ["A1"] = "Run the CheckAllCases macro to fill this sheet."
    summ["A1"].font = NOTE
    for name, df in (("Data_q", q), ("Data_hr", hr), ("Data_prev", prev), ("Data_former", former), ("Reference", ref)):
        table(wb.create_sheet(name), df)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
