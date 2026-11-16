"""
Draw the README figures from the engine's own simulated lives.

Run from the project folder:
    python docs/figures/make_figures.py

Writes a light and a dark version of each figure into docs/figures/:
    lives-light.svg, lives-dark.svg       1,000 lives of one person, stacked
    choices-light.svg, choices-dark.svg   the same person with three sets of habits
    how-light.svg, how-dark.svg           how one life is lived (a diagram, no data)

The SVG is written by hand (no plotting library needed). Every number on the
figures comes from engine.simulate; nothing is typed in. Run it with the CIA
MI-2024 file in place (see README) so the lives include future mortality
improvement; without it the figures say so in their subtitle.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # the project folder, for engine/
from engine.data import has_improvement_scale
from engine.risk import Person
from engine.simulate import simulate

OUT = Path(__file__).resolve().parent
N, SEED = 1000, 1
AGE_LO, AGE_HI = 25, 110

# The example person in engine/demo.py, and two other sets of habits for the same person.
BASE = dict(sex="M", age=25, region="MB", activity_minutes=60, height_cm=178, weight_kg=88,
            drinks_per_week=10, fruit_veg_per_day=2)
PROFILES = [
    ("Keeps smoking, little exercise, 10 drinks a week",
     Person(smoking="current", keeps_smoking=True, **BASE)),
    ("Same habits, but quits smoking today",
     Person(smoking="former", quit_age=25, **BASE)),
    ("Never smoked, active, healthy weight, 3 drinks, 5 fruit and veg",
     Person(**{**BASE, "smoking": "never", "activity_minutes": 300, "weight_kg": 72,
               "drinks_per_week": 3, "fruit_veg_per_day": 5})),
]

# Cause groups for colour. Three hues plus a neutral, checked for colour-blind
# separation (all pairs) in both themes; GitHub's light and dark page colours.
GROUPS = [
    ("Cancer", {"lung_cancer", "other_cancer"}),
    ("Heart disease and stroke", {"heart", "stroke"}),
    ("Accidents and injuries", {"motor_vehicle", "other_accidents", "other_injury"}),
    ("Everything else", None),
]
THEMES = {
    "light": dict(bg="#ffffff", ink="#1f2328", ink2="#59636e", muted="#818b98", grid="#d1d9e0",
                  series=["#2a78d6", "#eb6834", "#1baf7a", "#c4c9cf"]),
    "dark": dict(bg="#0d1117", ink="#f0f6fc", ink2="#9198a1", muted="#656c76", grid="#30363d",
                 series=["#3987e5", "#d95926", "#199e70", "#3d444d"]),
}
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"


def group_of(cause: str) -> int:
    for k, (_, causes) in enumerate(GROUPS):
        if causes is None or cause in causes:
            return k
    raise ValueError(cause)


def halo(bg):
    """Text attributes that paint a thin page-coloured outline behind the letters."""
    return f'stroke="{bg}" stroke-width="4" stroke-linejoin="round" paint-order="stroke"'


def text(x, y, s, size, fill, weight=400, anchor="start", extra=""):
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" {extra}>{s}</text>')


def svg(width, height, bg, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" font-family="{FONT}" role="img">\n'
            f'<title>{title}</title>\n'
            f'<rect width="{width}" height="{height}" rx="12" fill="{bg}"/>\n'
            + "\n".join(body) + "\n</svg>\n")


def age_axis(x_of, y, top, t, body):
    for a in range(30, AGE_HI + 1, 10):
        x = x_of(a)
        body.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{y}" stroke="{t["grid"]}" '
                    f'stroke-width="1" stroke-dasharray="2 4"/>')
        body.append(text(x, y + 18, str(a), 12, t["muted"], anchor="middle"))
    body.append(text(x_of(AGE_LO), y + 18, "Age", 12, t["muted"], anchor="start"))


def lives_figure(lives, improve, t):
    W, H = 960, 560
    L, R, TOP, BOT = 48, 912, 128, 500
    x_of = lambda a: L + (a - AGE_LO) / (AGE_HI - AGE_LO) * (R - L)
    ages = np.array([lf.death_age for lf in lives])
    order = np.argsort(ages)
    row = (BOT - TOP) / len(lives)
    body = [text(L, 54, "One Life, 1,000 Times", 30, t["ink"], 700),
            text(L, 82, "One 25-year-old man in Manitoba, lived 1,000 times by the model. "
                 "Each line is one life, from today to the age it ends,", 14, t["ink2"]),
            text(L, 102, "coloured by what it ends with. Sorted by length, the lives draw "
                 "the survival curve." + ("" if improve else " (No future mortality improvement.)"),
                 14, t["ink2"])]
    age_axis(x_of, BOT, TOP, t, body)
    paths = {k: [] for k in range(len(GROUPS))}
    for r, i in enumerate(order):
        y = TOP + (r + 0.5) * row
        paths[group_of(lives[i].cause)].append(f"M{x_of(AGE_LO):.1f} {y:.2f}H{x_of(ages[i]):.1f}")
    for k in (3, 0, 1, 2):
        body.append(f'<path d="{"".join(paths[k])}" stroke="{t["series"][k]}" '
                    f'stroke-width="{row * 1.02:.2f}" fill="none"/>')
    # median and the 10th / 90th percentiles, as ticks on the curve's edge
    for p, label in ((10, "1 in 10 die before {a:.0f}"), (50, "half live past {a:.0f}"),
                     (90, "1 in 10 live past {a:.0f}")):
        a = np.percentile(ages, p)
        y = TOP + p / 100 * (BOT - TOP)
        x = x_of(a)
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{t["ink"]}" '
                    f'stroke="{t["bg"]}" stroke-width="2"/>')
        body.append(text(x + 10, y + 4, label.format(a=a), 13, t["ink"], 600, extra=halo(t["bg"])))
    # legend, with the share of lives ending in each group
    share = [np.mean([group_of(lf.cause) == k for lf in lives]) for k in range(len(GROUPS))]
    x = L
    for k, (name, _) in enumerate(GROUPS):
        body.append(f'<rect x="{x}" y="{H - 30}" width="12" height="12" rx="3" fill="{t["series"][k]}"/>')
        label = f"{name} {share[k]:.0%}"
        body.append(text(x + 18, H - 20, label, 13, t["ink2"]))
        x += 18 + 7.2 * len(label) + 28
    return svg(W, H, t["bg"], body, "1,000 simulated lives of one person, sorted by length")


def choices_figure(results, improve, t):
    W, ROW = 960, 120
    L, R, TOP = 48, 912, 112
    H = TOP + ROW * len(results) + 44
    x_of = lambda a: L + (a - AGE_LO) / (AGE_HI - AGE_LO) * (R - L)
    body = [text(L, 46, "Which choices move the odds", 26, t["ink"], 700),
            text(L, 74, "The same man, three sets of habits, 1,000 lives each: how many of "
                 "the lives end at each age." + ("" if improve else " (No future mortality improvement.)"),
                 14, t["ink2"])]
    bottom = TOP + ROW * len(results)
    age_axis(x_of, bottom, TOP - 8, t, body)
    bins = np.arange(AGE_LO, AGE_HI + 2, 2)          # two-year bars
    first = None
    peak = max(np.histogram([lf.death_age for lf in lives], bins)[0].max() for _, lives in results)
    for r, (name, lives) in enumerate(results):
        base = TOP + ROW * (r + 1) - 14
        ages = np.array([lf.death_age for lf in lives])
        counts = np.histogram(ages, bins)[0]
        bw = 2 * (R - L) / (AGE_HI - AGE_LO)
        bars = []
        for b, c in enumerate(counts):
            if c:
                h = c / peak * (ROW - 60)
                bars.append(f'<rect x="{x_of(bins[b]) + 0.5:.1f}" y="{base - h:.1f}" '
                            f'width="{min(bw, R - x_of(bins[b])) - 1:.1f}" height="{h:.1f}" rx="1.5"/>')
        body.append(f'<g fill="{t["series"][0]}">' + "".join(bars) + "</g>")
        body.append(f'<line x1="{L}" y1="{base + 0.5}" x2="{R}" y2="{base + 0.5}" '
                    f'stroke="{t["grid"]}" stroke-width="1"/>')
        med = float(np.median(ages))
        first = med if first is None else first
        gain = "" if r == 0 else f"  ({med - first:+.0f} years)"
        body.append(text(L, base - ROW + 44, name, 14, t["ink"], 600))
        body.append(f'<line x1="{x_of(med):.1f}" y1="{base - ROW + 58}" x2="{x_of(med):.1f}" '
                    f'y2="{base}" stroke="{t["ink"]}" stroke-width="2"/>')
        body.append(text(R, base - ROW + 44, f"half live past {med:.0f}{gain}", 14, t["ink"], 600,
                         anchor="end"))
    return svg(W, H, t["bg"], body, "Age at death for one person with three sets of habits")


HOW_CARDS = [
    ("1", "Your answers", ["smoking, activity,", "height and weight,", "drinks, fruit and veg"]),
    ("2", "Your death rates", ["StatCan life table", "\u00d7 your habits, improved", "with CIA MI-2024"]),
    ("3", "Live one year", ["crash, cancer, heart attack,", "stroke, disability, marriage,", "child, retirement"]),
    ("4", "Death this year?", ["the chance depends on", "everything that has", "happened so far"]),
    ("5", "1,000 lives", ["repeat from today,", "1,000 times: the range", "of ages and causes"]),
]
HOW_COLOURS = {
    "light": dict(card="#f6f8fa", edge="#d1d9e0", accent="#2a78d6"),
    "dark": dict(card="#161b22", edge="#30363d", accent="#3987e5"),
}


def how_figure(t, c):
    """The five-step diagram of one life (no data)."""
    W, H = 960, 250
    CW, CH, GAP, TOP = 160, 128, 30, 66
    left = (W - (5 * CW + 4 * GAP)) / 2
    xs = [left + i * (CW + GAP) for i in range(5)]
    body = [f'<defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{t["ink2"]}"/></marker></defs>',
            text(left, 40, "How one life is lived", 22, t["ink"], 700)]
    for i, (num, head, lines) in enumerate(HOW_CARDS):
        x = xs[i]
        loop = i in (2, 3)
        body.append(f'<rect x="{x:.1f}" y="{TOP}" width="{CW}" height="{CH}" rx="10" fill="{c["card"]}" '
                    f'stroke="{c["accent"] if loop else c["edge"]}" stroke-width="{2 if loop else 1}"/>')
        body.append(f'<circle cx="{x + 22:.1f}" cy="{TOP + 24}" r="11" fill="{c["accent"]}"/>')
        body.append(text(x + 22, TOP + 28.5, num, 12, "#ffffff", 700, "middle"))
        body.append(text(x + 40, TOP + 29, head, 14.5, t["ink"], 700))
        for k, line in enumerate(lines):
            body.append(text(x + CW / 2, TOP + 62 + 19 * k, line, 12, t["ink2"], anchor="middle"))
        if i < 4:
            body.append(f'<line x1="{x + CW + 3:.1f}" y1="{TOP + CH / 2}" x2="{x + CW + GAP - 3:.1f}" '
                        f'y2="{TOP + CH / 2}" stroke="{t["ink2"]}" stroke-width="1.5" marker-end="url(#a)"/>')
    x3, x4, y = xs[2] + CW / 2, xs[3] + CW / 2, TOP + CH
    body.append(f'<path d="M{x4:.1f} {y + 2}V{y + 26}H{x3:.1f}V{y + 6}" fill="none" stroke="{c["accent"]}" '
                f'stroke-width="2" marker-end="url(#a)"/>')
    body.append(text((x3 + x4) / 2, y + 44, "survives: next year", 12.5, c["accent"], 600, "middle"))
    body.append(text(xs[3] + CW + GAP / 2, TOP + CH / 2 - 10, "dies", 11.5, t["ink2"], 600, "middle"))
    return svg(W, H, t["bg"], body, "How one life is lived: answers, death rates, then each year events "
               "and a death check, repeated 1,000 times")


def main() -> None:
    improve = has_improvement_scale()
    if not improve:
        print("Note: CIA MI-2024 file not found, so these lives have no future mortality improvement.")
    results = [(name, simulate(p, n=N, seed=SEED, improve=improve)) for name, p in PROFILES]
    for theme, t in THEMES.items():
        (OUT / f"lives-{theme}.svg").write_text(lives_figure(results[0][1], improve, t))
        (OUT / f"choices-{theme}.svg").write_text(choices_figure(results, improve, t))
        (OUT / f"how-{theme}.svg").write_text(how_figure(t, HOW_COLOURS[theme]))
    for name, lives in results:
        ages = np.array([lf.death_age for lf in lives])
        print(f"{name}: median {np.median(ages):.1f}, 10th {np.percentile(ages, 10):.1f}, "
              f"90th {np.percentile(ages, 90):.1f}")
    print(f"Wrote 6 figures to {OUT}")


if __name__ == "__main__":
    main()
