// Tests for the browser engine (web/engine/engine.js), run with Node's own test runner:
//     node --test web/tests/
// It must reproduce the Python engine on the same reference files as the R and
// Excel VBA rebuilds (crosscheck/reference/), and its simulated lives must
// average to its own exact results.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createEngine } from "../engine/engine.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const data = JSON.parse(readFileSync(join(ROOT, "web", "data", "engine-data.json"), "utf8"));
const engine = createEngine(data);

// ------------------------------------------------------------ reading the reference files

function readCsv(name) {
  const text = readFileSync(join(ROOT, "crosscheck", "reference", name), "utf8").trim();
  const lines = text.split(/\r?\n/);
  const header = splitLine(lines[0]);
  return lines.slice(1).map((line) => {
    const cells = splitLine(line);
    return Object.fromEntries(header.map((h, i) => [h, cells[i]]));
  });
}

function splitLine(line) {
  const out = [];
  let cur = "", quoted = false;
  for (const ch of line) {
    if (ch === '"') quoted = !quoted;
    else if (ch === "," && !quoted) { out.push(cur); cur = ""; }
    else cur += ch;
  }
  out.push(cur);
  return out;
}

const num = (x) => (x === "" || x === undefined ? null : Number(x));

function personFrom(row) {
  return {
    sex: row.sex, age: num(row.age), region: row.region, smoking: row.smoking,
    quit_age: num(row.quit_age), keeps_smoking: row.keeps_smoking === "True",
    activity_minutes: num(row.activity_minutes), height_cm: num(row.height_cm), weight_kg: num(row.weight_kg),
    drinks_per_week: num(row.drinks_per_week), fruit_veg_per_day: num(row.fruit_veg_per_day),
  };
}

const RISK = readCsv("risk_reference.csv");
const PEOPLE = {};
for (const r of RISK) if (!r.case.startsWith("population") && !PEOPLE[r.case]) PEOPLE[r.case] = personFrom(r);

function close(actual, expected, rel, abs, label) {
  const tol = Math.max(abs, rel * Math.abs(expected));
  assert.ok(Math.abs(actual - expected) <= tol, `${label}: ${actual} vs ${expected} (tolerance ${tol})`);
}

// ------------------------------------------------------------ risk engine (A07, A08, A18, A19, A26, A27)

test("risk engine matches the Python reference on every value (no improvement)", () => {
  let n = 0;
  const qByCase = {};
  for (const r of RISK) {
    const v = Number(r.value), a = num(r.at_age);
    if (r.measure === "average_multiplier") {
      close(engine.averageMultiplier(r.sex, a), v, 1e-12, 0, `average ${r.sex} ${a}`);
    } else {
      const p = engine.person(PEOPLE[r.case]);
      qByCase[r.case] ??= engine.personalQ(p, 2026, false);
      if (r.measure === "relative_multiplier") close(engine.relativeMultiplier(p, a), v, 1e-12, 0, `${r.case} r ${a}`);
      if (r.measure === "personal_q") close(qByCase[r.case][a - p.age], v, 1e-10, 1e-15, `${r.case} q ${a}`);
      if (r.measure === "life_expectancy") close(engine.lifeExpectancy(qByCase[r.case]), v, 1e-11, 0, `${r.case} e`);
    }
    n++;
  }
  assert.equal(n, 1632);
});

// ------------------------------------------------------------ CPP improvement (A28)

test("CPP improvement matches the Python reference", () => {
  const rows = readCsv("cpp_reference.csv");
  const qByCase = {};
  for (const r of rows) {
    const v = Number(r.value), a = num(r.at_age), y = num(r.year);
    if (r.measure === "scale_under_65") close(data[r.sex].cpp_scale[0], v, 1e-9, 0, "scale");
    if (r.measure === "improvement_factor") close(engine.improvementFactor(r.sex, a, y), v, 1e-12, 0, `factor ${r.sex} ${a} ${y}`);
    if (r.measure === "personal_q_improved" || r.measure === "life_expectancy_improved") {
      const p = engine.person(PEOPLE[r.case]);
      qByCase[r.case] ??= engine.personalQ(p, 2026);
      if (r.measure === "personal_q_improved") close(qByCase[r.case][a - p.age], v, 1e-10, 1e-15, `${r.case} q ${a}`);
      else close(engine.lifeExpectancy(qByCase[r.case]), v, 1e-11, 0, `${r.case} e`);
    }
  }
});

// ------------------------------------------------------------ whole lives (A20-A25)

const LIFE = readCsv("life_reference.csv");

test("cause mix and the person's own first-event rates match at every age", () => {
  const sch = {};
  let n = 0;
  for (const r of LIFE) {
    if (r.measure !== "cause_probability" && r.measure !== "incidence") continue;
    sch[r.case] ??= engine.buildSchedule(PEOPLE[r.case]);
    const s = sch[r.case], k = num(r.at_age) - s.person.age;
    const v = Number(r.value);
    if (r.measure === "cause_probability") {
      close(s.causes[k][data.constants.CAUSES.indexOf(r.index)], v, 1e-10, 1e-15, `${r.case} cause ${r.index} ${r.at_age}`);
    } else {
      close(s.fixed[r.index][k], v, 1e-9, 1e-15, `${r.case} ${r.index} ${r.at_age}`);
    }
    n++;
  }
  assert.ok(n > 9000);
});

test("exact year-by-year results match: chance of dying at each age, causes, first events", () => {
  const results = {};
  for (const r of LIFE) {
    if (r.measure === "cause_probability" || r.measure === "incidence") continue;
    const key = `${r.case}|${r.start_marital}`;
    if (!results[key]) {
      const sch = engine.buildSchedule(PEOPLE[r.case], 2026, true, r.start_marital);
      results[key] = { sch, e: engine.exact(sch) };
    }
    const { sch, e } = results[key];
    const v = Number(r.value);
    if (r.measure === "die") close(e.die[num(r.at_age) - sch.person.age], v, 1e-8, 1e-14, `${key} die ${r.at_age}`);
    else if (r.measure === "cause") close(e.cause[data.constants.CAUSES.indexOf(r.index)], v, 1e-8, 1e-14, `${key} cause ${r.index}`);
    else close(e[r.measure], v, 1e-9, 1e-12, `${key} ${r.measure}`);
  }
  assert.equal(Object.keys(results).length, 14);
});

// ------------------------------------------------------------ simulated lives

test("simulated lives average to the exact results (within four standard errors)", () => {
  const answers = PEOPLE.smoker_may_quit_M25;
  const { schedule, lives } = engine.simulate(answers, 4000, 7);
  const e = engine.exact(schedule);
  const ages = lives.map((l) => l.death_age);
  const mean = ages.reduce((a, b) => a + b, 0) / ages.length;
  const sd = Math.sqrt(ages.reduce((a, b) => a + (b - mean) ** 2, 0) / (ages.length - 1));
  assert.ok(Math.abs(mean - e.mean_death_age) < 4 * sd / Math.sqrt(ages.length), `mean ${mean} vs ${e.mean_death_age}`);
  const share = lives.filter((l) => l.events.some(([, , ev]) => ev.startsWith("cancer_"))).length / lives.length;
  const se = Math.sqrt((e.ever_cancer * (1 - e.ever_cancer)) / lives.length);
  assert.ok(Math.abs(share - e.ever_cancer) < 4 * se, `cancer ${share} vs ${e.ever_cancer}`);
  const lung = lives.filter((l) => l.cause === "lung_cancer").length / lives.length;
  const pl = e.cause[data.constants.CAUSES.indexOf("lung_cancer")];
  assert.ok(Math.abs(lung - pl) < 4 * Math.sqrt((pl * (1 - pl)) / lives.length), `lung ${lung} vs ${pl}`);
});

test("lives obey the rules: one death by 110, events in order, at most one of each first event", () => {
  const { lives } = engine.simulate(PEOPLE.former_before35_M47, 500, 3);
  for (const l of lives) {
    assert.ok(l.death_age >= 47 && l.death_age < 111);
    let last = 0;
    for (const [age, , ev] of l.events) { assert.ok(age >= last && age <= l.death_age); last = age; }
    for (const once of ["first_marriage", "heart_attack", "stroke", "first_child"]) {
      assert.ok(l.events.filter(([, , ev]) => ev === once).length <= 1, once);
    }
    assert.ok(l.events.filter(([, , ev]) => ev.startsWith("cancer_")).length <= 1);
    assert.ok(data.constants.CAUSES.includes(l.cause));
  }
});

test("the same seed gives the same lives; a different seed different ones", () => {
  const a = engine.simulate(PEOPLE.never_typical_M25, 50, 11).lives.map((l) => l.death_age);
  const b = engine.simulate(PEOPLE.never_typical_M25, 50, 11).lives.map((l) => l.death_age);
  const c = engine.simulate(PEOPLE.never_typical_M25, 50, 12).lives.map((l) => l.death_age);
  assert.deepEqual(a, b);
  assert.notDeepEqual(a, c);
});

test("impossible answers are refused", () => {
  assert.throws(() => engine.person({ sex: "M", age: 17 }));
  assert.throws(() => engine.person({ sex: "M", age: 30, smoking: "former" }));
  assert.throws(() => engine.person({ sex: "F", age: 30, keeps_smoking: true }));
  assert.throws(() => engine.person({ sex: "F", age: 30, height_cm: 170, weight_kg: 300 }));
});
