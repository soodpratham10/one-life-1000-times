// Runs the engine off the main thread, so the page never freezes while a life is worked out.
// Messages in:  { id, type: "lives" | "exact", answers, startMarital, n, seed }
// Messages out: { id, result } or { id, error }

import { createEngine } from "./engine/engine.js";

let enginePromise = null;

function getEngine() {
  enginePromise ??= fetch(new URL("./data/engine-data.json", import.meta.url))
    .then((r) => {
      if (!r.ok) throw new Error(`could not load the data (HTTP ${r.status})`);
      return r.json();
    })
    .then((data) => createEngine(data));
  return enginePromise;
}

function exactResult(engine, answers, startMarital) {
  const sch = engine.buildSchedule(answers, engine.constants.START_YEAR, true, startMarital);
  const e = engine.exact(sch);
  return { ages: sch.ages, die: e.die, mean: e.mean_death_age, cause: e.cause, ever: {
    cancer: e.ever_cancer, heart_attack: e.ever_heart_attack, stroke: e.ever_stroke, disability: e.ever_disability,
  }, crashes: e.crashes, startYear: sch.startYear };
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
    } else {
      throw new Error(`unknown request ${type}`);
    }
  } catch (err) {
    self.postMessage({ id, error: err.message || String(err) });
  }
};
