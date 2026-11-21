// Runs the engine off the main thread, so the page never freezes while a life is worked out.
// Messages in:  { id, type: "lives" | "exact" | "batch" | "reading", answers, startMarital, n, seed }
// Messages out: { id, result } or { id, error }

import { createEngine } from "./engine/engine.js";

let enginePromise = null;
let tables = null;

function getEngine() {
  enginePromise ??= fetch(new URL("./data/engine-data.json", import.meta.url))
    .then((r) => {
      if (!r.ok) throw new Error(`could not load the data (HTTP ${r.status})`);
      return r.json();
    })
    .then((data) => { tables = data; return createEngine(data); });
  return enginePromise;
}

// schedules are the slow part, so keep the last few
const schedules = new Map();
function schedule(engine, answers, startMarital) {
  const key = JSON.stringify([answers, startMarital]);
  if (!schedules.has(key)) {
    if (schedules.size > 12) schedules.delete(schedules.keys().next().value);
    schedules.set(key, engine.buildSchedule(answers, engine.constants.START_YEAR, true, startMarital));
  }
  return schedules.get(key);
}

function exactResult(engine, answers, startMarital) {
  const sch = schedule(engine, answers, startMarital);
  const e = engine.exact(sch);
  return { ages: sch.ages, die: e.die, mean: e.mean_death_age, cause: e.cause, ever: {
    cancer: e.ever_cancer, heart_attack: e.ever_heart_attack, stroke: e.ever_stroke, disability: e.ever_disability,
  }, crashes: e.crashes, startYear: sch.startYear };
}

function median(ex) {                       // deaths spread evenly within each year of age
  let total = 0;
  for (let i = 0; i < ex.ages.length; i++) {
    if (total + ex.die[i] >= 0.5) return ex.ages[i] + (0.5 - total) / ex.die[i];
    total += ex.die[i];
  }
  return ex.ages[ex.ages.length - 1] + 1;
}

// The average Canadian of the same sex, age and province: population death rates (with the same CPP
// improvement) split by the population cause shares, which the model is calibrated to.
function populationCauses(engine, p) {
  const K = engine.constants;
  const q = engine.cohortQ(p.region, p.sex, p.age, K.START_YEAR, true);
  const out = new Array(K.CAUSES.length).fill(0);
  let alive = 1;
  q.forEach((qi, i) => {
    tables[p.sex].cause_shares[p.age + i].forEach((s, j) => { out[j] += alive * qi * s; });
    alive *= 1 - qi;
  });
  const total = out.reduce((x, y) => x + y, 0);
  let left = 1, popMedian = p.age + q.length;
  for (let i = 0; i < q.length; i++) {
    if (left * (1 - q[i]) <= 0.5) { popMedian = p.age + i + (left - 0.5) / (left * q[i]); break; }
    left *= 1 - q[i];
  }
  return { shares: out.map((x) => x / total), median: popMedian };
}

// One realistic change at a time, each to the next level the studies reward.
function leverCandidates(engine, a) {
  const K = engine.constants;
  const out = [];
  if (a.smoking === "current") out.push(["quit smoking now", { smoking: "former", quit_age: a.age, keeps_smoking: false }]);
  if (a.activity_minutes < 150) out.push(["get 2½ hours of activity a week", { activity_minutes: 150 }]);
  else if (a.activity_minutes < 300) out.push(["get 5 hours of activity a week", { activity_minutes: 300 }]);
  const bmi = a.weight_kg / (a.height_cm / 100) ** 2;
  const kgAt = (b) => Math.floor(b * (a.height_cm / 100) ** 2 * 10) / 10;
  if (bmi >= 25) out.push([`weigh ${Math.floor(kgAt(24.9))} kg, a BMI under 25`, { weight_kg: kgAt(24.9) }]);
  else if (bmi < 18.5) out.push([`weigh ${Math.ceil(18.5 * (a.height_cm / 100) ** 2)} kg, a BMI of 18.5`, { weight_kg: Math.ceil(18.5 * (a.height_cm / 100) ** 2) }]);
  const underLimit = Math.floor((25 * 7) / K.GRAMS_PER_DRINK - 1e-9);   // under 25 g of alcohol a day
  if ((a.drinks_per_week * K.GRAMS_PER_DRINK) / 7 >= 25) out.push([`have ${underLimit} drinks a week or fewer`, { drinks_per_week: underLimit }]);
  if (a.fruit_veg_per_day < 5) out.push(["eat 5 servings of fruit and vegetables a day", { fruit_veg_per_day: 5 }]);
  return out;
}

function reading(engine, answers, startMarital, n, seed) {
  const K = engine.constants;
  const exact = exactResult(engine, answers, startMarital);
  const sch = schedule(engine, answers, startMarital);
  const random = engine.rng(seed);
  const lives = [];
  for (let k = 0; k < n; k++) {
    const l = engine.live(sch, random);
    lives.push({ age: l.death_age, year: l.death_year, cause: l.cause, events: l.events });
  }
  const p = engine.person(answers);
  const { shares: pop, median: popMedian } = populationCauses(engine, p);
  const ratios = K.CAUSES.map((c, j) => ({ cause: c, label: K.CAUSE_LABELS[c], person: exact.cause[j], pop: pop[j],
    ratio: pop[j] > 0 ? exact.cause[j] / pop[j] : 0 }));
  const base = median(exact);
  const levers = leverCandidates(engine, p).map(([label, change]) => {
    const m = median(exactResult(engine, { ...answers, ...change }, startMarital));
    return { label, median: m, gain: m - base, multiplier: engine.relativeMultiplier(engine.person({ ...answers, ...change }), p.age) };
  }).sort((x, y) => y.gain - x.gain);
  // for the actuary's table: the population's death rates on the same CPP basis, and your multiplier today
  const qPop = engine.cohortQ(p.region, p.sex, p.age, K.START_YEAR, true);
  return { exact, lives, ratios, levers, median: base, popMedian, qPop, multiplier: engine.relativeMultiplier(p, p.age),
    causes: K.CAUSES, labels: K.CAUSE_LABELS };
}

self.onmessage = async (event) => {
  const { id, type, answers, startMarital = "never", n = 1000, seed = 1 } = event.data;
  try {
    const engine = await getEngine();
    if (type === "exact") {
      self.postMessage({ id, result: exactResult(engine, answers, startMarital) });
    } else if (type === "lives") {
      const exact = exactResult(engine, answers, startMarital);
      const { lives } = engine.simulate(answers, n, seed, engine.constants.START_YEAR, startMarital);
      const compact = lives.map((l) => ({ age: l.death_age, year: l.death_year, cause: l.cause, events: l.events }));
      self.postMessage({ id, result: { exact, lives: compact, summary: engine.summary(lives),
        causes: engine.constants.CAUSES, labels: engine.constants.CAUSE_LABELS } });
    } else if (type === "batch") {
      // a quick batch of lives (ages and event ages only) for the never-ending sky
      const sch = schedule(engine, answers, startMarital);
      const random = engine.rng(seed);
      const lives = [];
      for (let k = 0; k < n; k++) {
        const l = engine.live(sch, random);
        lives.push({ age: l.death_age, events: l.events.map(([age]) => age) });
      }
      self.postMessage({ id, result: { startAge: sch.ages[0], lives } });
    } else if (type === "reading") {
      self.postMessage({ id, result: reading(engine, answers, startMarital, n, seed) });
    } else {
      throw new Error(`unknown request ${type}`);
    }
  } catch (err) {
    self.postMessage({ id, error: err.message || String(err) });
  }
};
