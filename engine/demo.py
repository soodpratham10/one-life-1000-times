"""
Try the engine: one example person, one life story, then 1,000 lives.

Run from the project folder:
    python -m engine.demo
Change the answers below to see how the lives move.
"""

from engine.causes import CAUSE_LABELS
from engine.data import has_improvement_scale
from engine.risk import Person
from engine.simulate import simulate, story, summary

ME = Person(
    sex="M", age=25, region="MB",
    smoking="current",              # never, former (then give quit_age) or current
    activity_minutes=60,            # moderate or vigorous activity a week
    height_cm=178, weight_kg=88,
    drinks_per_week=10,
    fruit_veg_per_day=2,
)


def main() -> None:
    improve = has_improvement_scale()
    if not improve:
        print("Note: the CIA MI-2024 scale is not on this computer (see README), so these lives use\n"
              "2017-2019 death rates with no future improvement; lifetimes come out several years shorter.\n")
    lives = simulate(ME, n=1000, seed=1, improve=improve)
    print("One of your lives:")
    for line in story(lives[0]):
        print("  " + line)

    s = summary(lives)
    low, high = s["death_age_10th_90th"]
    print(f"\nAcross {s['lives']:,} lives:")
    print(f"  median age at death {s['median_death_age']:.1f} (1 in 10 die before {low:.0f}, 1 in 10 live past {high:.0f})")
    print(f"  reached 80 in {s['reach_80']:.0%} of lives, 90 in {s['reach_90']:.0%}")
    print("  most common causes of death: " + ", ".join(
        f"{CAUSE_LABELS[c]} {v:.0%}" for c, v in list(s["cause_of_death"].items())[:4]))
    print("  at least once: " + ", ".join(f"{k.replace('_', ' ')} {v:.0%}" for k, v in s["ever"].items()))


if __name__ == "__main__":
    main()
