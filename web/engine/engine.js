// One Life, 1,000 Times: the engine in JavaScript, for the website (Phase 5).
//
// Runs in the browser and in Node, with no libraries. It works out everything
// personal from the survey answers, on the data exported by web/build_data.py
// (web/data/engine-data.json): death rates with future improvement (A04, A28),
// habits and how they change (A07, A08, A26, A27), the cause of death (A20),
// the person's own cancer, heart attack and stroke rates and death tables
// (A22-A25), and then the year-by-year exact calculation and simulated lives.
// It follows the Python engine (engine/) step for step and is checked against
// the same reference files (web/tests/engine.test.mjs).
//
// Usage:
//   import { createEngine } from "./engine.js";
//   const engine = createEngine(data);           // data = parsed engine-data.json
//   const person = { sex: "M", age: 25, region: "MB", smoking: "current", ... };
//   const sch = engine.buildSchedule(person);     // everything that does not depend on chance
//   const e = engine.exact(sch);                  // exact expected results
//   const lives = engine.simulate(person, 1000, 1);

export function createEngine(data) {
  const K = data.constants;
  const HR = data.hazard_ratios;
  const CAUSES = K.CAUSES;
  const NC = CAUSES.length;
  const LUNG = CAUSES.indexOf("lung_cancer"), OTHER = CAUSES.indexOf("other_cancer");
  const HEART = CAUSES.indexOf("heart"), STROKE = CAUSES.indexOf("stroke");
  const SITES = [LUNG, OTHER, HEART, STROKE];
  const MAX_AGE = K.MAX_AGE, MIN_AGE = K.MIN_AGE;
  const QUIT_ORDER = ["quit_before_35", "quit_35_44", "quit_45_54", "quit_55_plus"];
  const memo = new Map();
  const cached = (key, f) => {
    if (!memo.has(key)) memo.set(key, f());
    return memo.get(key);
  };

  // ------------------------------------------------------------ answers to levels (A07)

  function validate(p) {
    const fail = (msg) => { throw new Error(msg); };
    if (p.sex !== "M" && p.sex !== "F") fail("sex must be 'M' or 'F'");
    if (!(Number.isInteger(p.age) && p.age >= MIN_AGE && p.age < MAX_AGE)) fail(`age must be ${MIN_AGE}-${MAX_AGE - 1}`);
    if (!K.REGIONS.includes(p.region)) fail(`region must be one of ${K.REGIONS.join(", ")}`);
    if (!["never", "former", "current"].includes(p.smoking)) fail("smoking must be never, former or current");
    if (p.smoking === "former") {
      if (p.quit_age == null || p.quit_age < 10 || p.quit_age > p.age) fail("former smokers need a quit age between 10 and their age");
    } else if (p.quit_age != null) fail("quit age is only for former smokers");
    if (p.keeps_smoking && p.smoking !== "current") fail("keeps_smoking is only for current smokers");
    const bmi = p.weight_kg / (p.height_cm / 100) ** 2;
    if (!(p.activity_minutes >= 0 && p.activity_minutes <= 3000)) fail("activity must be 0-3000 minutes a week");
    if (!(p.height_cm >= 120 && p.height_cm <= 230 && p.weight_kg >= 30 && p.weight_kg <= 300)) fail("height must be 120-230 cm and weight 30-300 kg");
    if (!(bmi >= 12 && bmi <= 80)) fail("height and weight give an implausible BMI");
    if (!(p.drinks_per_week >= 0 && p.drinks_per_week <= 150)) fail("drinks must be 0-150 a week");
    if (!(p.fruit_veg_per_day >= 0 && p.fruit_veg_per_day <= 20)) fail("fruit and vegetables must be 0-20 servings a day");
  }

  function person(answers) {
    const p = {
      region: "CA", smoking: "never", quit_age: null, keeps_smoking: false, activity_minutes: 0,
      height_cm: 170, weight_kg: 70, drinks_per_week: 0, fruit_veg_per_day: 2, ...answers,
    };
    validate(p);
    return p;
  }

  function quitLevel(q) {
    return q < 35 ? "quit_before_35" : q < 45 ? "quit_35_44" : q < 55 ? "quit_45_54" : "quit_55_plus";
  }

  function levels(p) {
    const m = p.activity_minutes;
    const b = p.weight_kg / (p.height_cm / 100) ** 2;
    const g = (p.drinks_per_week * K.GRAMS_PER_DRINK) / 7;
    const f = p.fruit_veg_per_day;
    return {
      smoking: p.smoking === "former" ? quitLevel(p.quit_age) : p.smoking,
      activity: m === 0 ? "none" : m < 150 ? "under_150" : m < 300 ? "150_299" : m < 450 ? "300_449" : "450_plus",
      bmi: b < 18.5 ? "under_18.5" : b < 25 ? "18.5_25" : b < 27.5 ? "25_27.5" : b < 30 ? "27.5_30"
        : b < 35 ? "30_35" : b < 40 ? "35_40" : "40_plus",
      alcohol: g < 25 ? "under_25g" : g < 45 ? "25_44g" : g < 65 ? "45_64g" : "65g_plus",
      fruit_veg: f < 3 ? "0_2" : f < 4 ? "3" : f < 5 ? "4" : "5_plus",
    };
  }

  // ------------------------------------------------------------ ratios, taper, mix (A07, A08, A18)

  function hazard(factor, level, sex) {
    const row = HR[factor] && HR[factor][level];
    if (!row) throw new Error(`no hazard ratio for ${factor} ${level}`);
    const v = row[sex] !== undefined ? row[sex] : row.B;
    if (v === undefined) throw new Error(`no hazard ratio for ${factor} ${level} ${sex}`);
    return v;
  }

  function taper(age) {
    if (age <= K.TAPER_START) return 1;
    return Math.max(0, (MAX_AGE - age) / (MAX_AGE - K.TAPER_START));
  }

  function groupLo(age) {
    for (const [lo, hi] of K.AGE_GROUPS) if (age >= lo && age <= hi) return lo;
    throw new Error(`no age group for ${age}`);
  }

  const mix = (sex, age) => data[sex].mix[String(groupLo(age))];

  function averageMultiplier(sex, age) {
    return cached(`avg|${sex}|${age}`, () => {
      const w = taper(age);
      const m = mix(sex, age);
      let total = 1;
      for (const f of K.FACTORS) {
        let s = 0;
        for (const [lvl, share] of Object.entries(m[f])) s += share * hazard(f, lvl, sex) ** w;
        total *= s;
      }
      return total;
    });
  }

  // habits that change with age (A26): keep your slice of the distribution
  function slices(order, shares) {
    const out = {};
    let lo = 0;
    for (const lvl of order) {
      const s = shares[lvl] || 0;
      out[lvl] = [lo, lo + s];
      lo += s;
    }
    return out;
  }

  function driftRatio(factor, level, sex, answerAge, age) {
    return cached(`drift|${factor}|${level}|${sex}|${answerAge}|${age}`, () => {
      const w = taper(age);
      const order = K.DRIFTING[factor];
      if (!order || !order.includes(level) || groupLo(age) === groupLo(answerAge)) return hazard(factor, level, sex) ** w;
      const [lo, hi] = slices(order, mix(sex, answerAge)[factor])[level];
      if (hi <= lo) return hazard(factor, level, sex) ** w;
      const later = slices(order, mix(sex, age)[factor]);
      let total = 0;
      for (const [lvl, [a, b]] of Object.entries(later)) {
        const overlap = Math.max(0, Math.min(hi, b) - Math.max(lo, a));
        total += overlap * hazard(factor, lvl, sex) ** w;
      }
      return total / (hi - lo);
    });
  }

  // quitting smoking (A27): chance of each smoking level at a later age
  function smokingPath(p, age) {
    const level = levels(p).smoking;
    if (level !== "current" || p.keeps_smoking || age <= p.age) return [[level, 1]];
    const shares = new Map();
    let still = 1;
    for (let y = p.age; y < age; y++) {
      const quit = still * (y >= K.QUIT_FROM_AGE ? K.QUIT_RATE : 0);
      if (quit > 0) {
        const lvl = quitLevel(y);
        shares.set(lvl, (shares.get(lvl) || 0) + quit);
        still -= quit;
      }
    }
    shares.set("current", still);
    return [...shares.entries()];
  }

  function personMultiplier(p, age) {
    const lv = levels(p);
    const w = taper(age);
    let total = 1;
    for (const f of K.FACTORS) {
      if (f === "smoking") {
        let s = 0;
        for (const [lvl, chance] of smokingPath(p, age)) s += chance * hazard("smoking", lvl, p.sex) ** w;
        total *= s;
      } else {
        total *= driftRatio(f, lv[f], p.sex, p.age, age);
      }
    }
    return total;
  }

  function relativeMultiplier(p, age) {
    if (age >= MAX_AGE) return 1;
    const r = personMultiplier(p, age) / averageMultiplier(p.sex, age);
    return Math.min(Math.max(r, K.CAP_LOW), K.CAP_HIGH);
  }

  // ------------------------------------------------------------ death rates with improvement (A04, A28)

  function improvementFactor(sex, age, year) {
    if (year <= K.BASE_YEAR || age >= MAX_AGE) return 1;
    const count = (lo, hi) => Math.max(0, Math.min(year, hi) - Math.max(K.BASE_YEAR + 1, lo) + 1);
    const n1 = count(-1e6, 2025), n2 = count(2026, 2038), n3 = count(2039, 1e6);
    const m = data[sex].cpp_rates[age];
    const scale = data[sex].cpp_scale;
    const k = age < K.CPP_SPLIT_AGE ? scale[0] : scale[1];
    return (1 - k * m[0]) ** n1 * (1 - m[1]) ** n2 * (1 - m[2]) ** n3;
  }

  function cohortQ(region, sex, age, year, improve = true) {
    const base = data[sex].base_q[region];
    const q = [];
    for (let a = age; a <= MAX_AGE; a++) {
      let x = base[a] * (improve ? improvementFactor(sex, a, year + (a - age)) : 1);
      q.push(Math.min(Math.max(x, 0), 1));
    }
    return q;
  }

  function personalQ(p, year, improve = true) {
    const q = cohortQ(p.region, p.sex, p.age, year, improve);
    const out = q.map((x, k) => 1 - (1 - x) ** relativeMultiplier(p, p.age + k));
    out[out.length - 1] = 1;
    return out;
  }

  function lifeExpectancy(q) {
    let alive = 1, total = 0;
    for (const x of q) { alive *= 1 - x; total += alive; }
    return total + 0.5;
  }

  // ------------------------------------------------------------ cause of death (A20)

  function smokingCauseRatio(cause, level, sex) {
    if (level === "never") return 1;
    const current = data[sex].smoking_cause_ratio_current[cause];
    const kept = (hazard("smoking", level, sex) - 1) / (hazard("smoking", "current", sex) - 1);
    return 1 + kept * (current - 1);
  }

  function causeProbabilities(p, age) {
    const shares = data[p.sex].cause_shares[age];
    const a = data[p.sex].cause_calibration[age];
    const w = taper(age);
    const out = new Array(NC).fill(0);
    for (const [level, chance] of smokingPath(p, age)) {
      const split = shares.map((s, j) => (s * smokingCauseRatio(CAUSES[j], level, p.sex) ** w) / a[j]);
      const total = split.reduce((x, y) => x + y, 0);
      const weight = chance * hazard("smoking", level, p.sex) ** w;
      for (let j = 0; j < NC; j++) out[j] += (weight * split[j]) / total;
    }
    const total = out.reduce((x, y) => x + y, 0);
    return out.map((x) => x / total);
  }

  // ------------------------------------------------------------ the person's own rates and death tables (A22-A25)

  function personRatios(q, causes, sex, firstAge) {
    const qPop = data[sex].base_q.CA;
    return q.map((qi, i) => {
      const age = firstAge + i;
      if (qi >= 1) return [1, 1, 1, 1];
      const mu = -Math.log(1 - qi), muPop = -Math.log(1 - qPop[age]);
      const shares = data[sex].cause_shares[age];
      return SITES.map((site) => (shares[site] > 0 ? (mu * causes[i][site]) / (muPop * shares[site]) : 1));
    });
  }

  const N_CANCER = K.N_CANCER;      // 0 never diagnosed; 1-6 lung, years since 0..5+; 7-12 other site
  const W = K.W;

  function deathTables(q, causes, sex, firstAge, ratios) {
    const d = data[sex];
    const n = q.length;
    // qState[i][cs][a][s][m][dis], cState[i][cs][a][s] = cause mix
    const qState = [], cState = [];
    const acuteH = [], acuteS = [];
    const others = [];
    for (let j = 0; j < NC; j++) if (!SITES.includes(j)) others.push(j);
    for (let i = 0; i < n; i++) {
      const age = firstAge + i;
      acuteH.push(d.acute.heart[Math.min(age, MAX_AGE)]);
      acuteS.push(d.acute.stroke[Math.min(age, MAX_AGE)]);
      const cp = causes[i];
      const qi = [], ci = [];
      if (q[i] >= 1) {                                    // age 110: everyone dies
        const mixU = cp.slice();
        mixU[LUNG] = 0; mixU[OTHER] = 0;
        const t = mixU.reduce((x, y) => x + y, 0);
        for (let cs = 0; cs < N_CANCER; cs++) {
          const mixCs = cs === 0 ? mixU.map((x) => x / t) : cp.slice();
          qi.push([[[[1, 1], [1, 1], [1, 1]], [[1, 1], [1, 1], [1, 1]]], [[[1, 1], [1, 1], [1, 1]], [[1, 1], [1, 1], [1, 1]]]]);
          ci.push([[mixCs, mixCs], [mixCs, mixCs]]);
        }
        qState.push(qi); cState.push(ci);
        continue;
      }
      const cal = d.cancer_link, cc = d.cardio_link;
      const mRatio = K.MARITAL_STATES.map((st) => d.marital_ratio[st][age]);
      const dMult = d.death_multipliers[age];
      const mu = -Math.log(1 - q[i]);
      const base = new Array(NC).fill(0);
      for (const j of others) base[j] = mu * cp[j] * cal.eta[age] * cc.eta[age];
      const heartBg = mu * cp[HEART] * cc.b_heart[age], strokeBg = mu * cp[STROKE] * cc.b_stroke[age];
      const extraH = (cc.rr_heart[age] - 1) * mu, extraS = (cc.rr_stroke[age] - 1) * mu;
      const r = ratios[i];
      const cancer = [[cal.r_lung[age] * r[0], cal.r_other[age] * r[1]]];
      for (let k = 0; k < 6; k++) cancer[1 + k] = [cal.s_lung[age] * W[k], 0];
      for (let k = 0; k < 6; k++) cancer[7 + k] = [0, cal.s_other[age] * W[k]];
      for (let cs = 0; cs < N_CANCER; cs++) {
        const qa = [], ca = [];
        for (let a = 0; a < 2; a++) {
          const qs = [], cs2 = [];
          for (let s = 0; s < 2; s++) {
            const f = base.slice();
            f[LUNG] = cancer[cs][0];
            f[OTHER] = cancer[cs][1];
            f[HEART] = heartBg + extraH * a;
            f[STROKE] = strokeBg + extraS * s;
            const total = f.reduce((x, y) => x + y, 0);
            cs2.push(f.map((x) => x / total));
            qs.push(mRatio.map((mr) => [1 - Math.exp(-total * mr * dMult[0]), 1 - Math.exp(-total * mr * dMult[1])]));
          }
          qa.push(qs); ca.push(cs2);
        }
        qi.push(qa); ci.push(ca);
      }
      qState.push(qi); cState.push(ci);
    }
    return { qState, cState, acuteH, acuteS };
  }

  // ------------------------------------------------------------ event chances (A11-A17, A21)

  const eligible = (sex, year) => {
    const [lo, hi] = K.ELIGIBLE_YEARS;
    return data[sex].eligible_share[String(Math.min(Math.max(year, lo), hi))];
  };

  function disabilityStart(sex, age, year) {
    if (age > K.DISABILITY_MAX_AGE) return 0;
    return data[sex].disability_incidence[age] * eligible(sex, year);
  }

  function onsetBand(onsetAge) {
    let best = K.BANDS[0];
    for (const b of K.BANDS) if (Math.abs(b - onsetAge) < Math.abs(best - onsetAge)) best = b;
    return best;
  }

  function recovery(sex, onsetAge, completedYears, year, age) {
    const b = K.BANDS.indexOf(onsetBand(onsetAge));
    const y = Math.min(Math.max(completedYears, 1), 6);
    const [lo, hi] = K.RECOVERY_YEARS;
    const yr = Math.min(Math.max(year, lo), hi);
    return data[sex].recovery[b][y - 1][yr - lo][age - MIN_AGE];
  }

  // ------------------------------------------------------------ the schedule: everything not left to chance

  function buildSchedule(answers, startYear = K.START_YEAR, improve = true, startMarital = "never") {
    const p = person(answers);
    const d = data[p.sex];
    const ages = [], years = [];
    for (let a = p.age; a <= MAX_AGE; a++) { ages.push(a); years.push(startYear + (a - p.age)); }
    const fixed = {
      crash_injury: ages.map((a) => d.crash[a]),
      disability_start: ages.map((a, i) => disabilityStart(p.sex, a, years[i])),
      retire: ages.map((a) => d.retire[a]),
      first_marriage: ages.map((a) => d.family.first_marriage[a]),
      divorce: ages.map((a) => d.family.divorce[a]),
      remarriage: ages.map((a) => d.family.remarriage[a]),
      first_child: ages.map((a) => d.first_child[a]),
    };
    const causes = ages.map((a) => causeProbabilities(p, a));
    const q = personalQ(p, startYear, improve);
    const ratios = personRatios(q, causes, p.sex, p.age);
    const keys = ["cancer_lung", "cancer_other", "heart_attack", "stroke"];
    keys.forEach((key, j) => {
      fixed[key] = ages.map((a, i) => {
        const age = Math.min(a, MAX_AGE);
        const pop = j < 2 ? d.cancer_pop[age][j] : d.cardio_pop[age][j - 2];
        return Math.min(1, pop * ratios[i][j]);
      });
    });
    const tables = deathTables(q, causes, p.sex, p.age, ratios);
    return { person: p, startYear, ages, years, q, causes, fixed, startMarital, ...tables };
  }

  // ------------------------------------------------------------ exact year-by-year results

  // work states: 0 working age, 1-24 disabled (band x completed years 1..6), 25 retired
  const stateIndex = (band, years) => 1 + K.BANDS.indexOf(band) * 6 + (Math.min(Math.max(years, 1), 6) - 1);

  function workTransition(sex, age, year, pStart, pRetire) {
    const n = 26;
    const t = Array.from({ length: n }, () => new Array(n).fill(0));
    const nw = stateIndex(onsetBand(age), 1);
    t[0][25] = pRetire;
    t[0][nw] = pStart * (1 - pRetire);
    t[0][0] = 1 - t[0][25] - t[0][nw];
    const yr = Math.min(Math.max(year, 2025), 2035);
    for (const b of K.BANDS) {
      for (let y = 1; y <= 6; y++) {
        const k = stateIndex(b, y);
        if (age > K.DISABILITY_MAX_AGE) { t[k][25] = 1; continue; }
        const rec = recovery(sex, b, y, yr, age);
        t[k][0] = rec;
        t[k][stateIndex(b, y + 1)] += 1 - rec;
      }
    }
    t[25][25] = 1;
    return t;
  }

  function exact(sch) {
    const W_ = 26, C_ = N_CANCER, M_ = 3;
    const idx = (w, c, a, s, m) => ((((w * C_ + c) * 2 + a) * 2 + s) * M_ + m);
    const size = W_ * C_ * 2 * 2 * M_;
    let p = new Float64Array(size);
    p[idx(sch.person.age > 70 ? 25 : 0, 0, 0, 0, K.MARITAL_STATES.indexOf(sch.startMarital))] = 1;
    const n = sch.ages.length;
    const die = new Array(n).fill(0), cause = new Array(NC).fill(0);
    const ever = { cancer: 0, heart_attack: 0, stroke: 0, disability: 0 };
    let crashes = 0;
    const f = sch.fixed;
    for (let i = 0; i < n; i++) {
      let mass = 0;
      for (let x = 0; x < size; x++) mass += p[x];
      crashes += mass * f.crash_injury[i];
      let workingAtStart = 0;
      for (let c = 0; c < C_; c++) for (let a = 0; a < 2; a++) for (let s = 0; s < 2; s++) for (let m = 0; m < M_; m++) workingAtStart += p[idx(0, c, a, s, m)];

      // cancer: first diagnoses, then everyone diagnosed moves one year on
      const lung = f.cancer_lung[i], other = f.cancer_other[i];
      let nxt = new Float64Array(size);
      for (let w = 0; w < W_; w++) for (let a = 0; a < 2; a++) for (let s = 0; s < 2; s++) for (let m = 0; m < M_; m++) {
        const u = p[idx(w, 0, a, s, m)];
        const nl = u * lung, no = u * (1 - lung) * other;
        ever.cancer += nl + no;
        nxt[idx(w, 0, a, s, m)] = u - nl - no;
        for (const [start, newMass] of [[1, nl], [7, no]]) {
          nxt[idx(w, start, a, s, m)] = newMass;
          for (let k = 1; k < 5; k++) nxt[idx(w, start + k, a, s, m)] = p[idx(w, start + k - 1, a, s, m)];
          nxt[idx(w, start + 5, a, s, m)] = p[idx(w, start + 4, a, s, m)] + p[idx(w, start + 5, a, s, m)];
        }
      }
      p = nxt;

      // heart attack, then stroke: first events and acute deaths
      const moveA = new Float64Array(size), moveS = new Float64Array(size);
      let acuteA = 0, acuteSt = 0;
      for (let w = 0; w < W_; w++) for (let c = 0; c < C_; c++) for (let s = 0; s < 2; s++) for (let m = 0; m < M_; m++) {
        const x = idx(w, c, 0, s, m);
        const newA = p[x] * f.heart_attack[i];
        const ac = newA * sch.acuteH[i];
        ever.heart_attack += newA;
        acuteA += ac;
        p[x] -= ac;
        moveA[x] = p[x] > 0 ? (newA - ac) / p[x] : 0;
      }
      for (let w = 0; w < W_; w++) for (let c = 0; c < C_; c++) for (let a = 0; a < 2; a++) for (let m = 0; m < M_; m++) {
        const x = idx(w, c, a, 0, m);
        const newS = p[x] * f.stroke[i];
        const ac = newS * sch.acuteS[i];
        ever.stroke += newS;
        acuteSt += ac;
        p[x] -= ac;
        moveS[x] = p[x] > 0 ? (newS - ac) / p[x] : 0;
      }
      cause[HEART] += acuteA;
      cause[STROKE] += acuteSt;

      // regular deaths in the state held at the start of the year
      const alive = new Float64Array(size);
      let deaths = 0;
      for (let w = 0; w < W_; w++) {
        const dis = w >= 1 && w <= 24 ? 1 : 0;
        for (let c = 0; c < C_; c++) for (let a = 0; a < 2; a++) for (let s = 0; s < 2; s++) {
          const mixC = sch.cState[i][c][a][s];
          for (let m = 0; m < M_; m++) {
            const x = idx(w, c, a, s, m);
            const dx = p[x] * sch.qState[i][c][a][s][m][dis];
            deaths += dx;
            for (let j = 0; j < NC; j++) cause[j] += dx * mixC[j];
            alive[x] = p[x] - dx;
          }
        }
      }
      die[i] = acuteA + acuteSt + deaths;

      // survivors of this year's events move state: heart attack, stroke, marital status, work
      p = new Float64Array(size);
      for (let w = 0; w < W_; w++) for (let c = 0; c < C_; c++) for (let m = 0; m < M_; m++) {
        for (let a = 0; a < 2; a++) for (let s = 0; s < 2; s++) {
          const x = idx(w, c, a, s, m);
          const pa = a === 0 ? moveA[idx(w, c, 0, s, m)] : 0;
          const ps = s === 0 ? moveS[idx(w, c, a, 0, m)] : 0;
          for (const [da, wa] of [[0, 1 - pa], [1, pa]]) for (const [ds, ws] of [[0, 1 - ps], [1, ps]]) {
            p[idx(w, c, Math.min(a + da, 1), Math.min(s + ds, 1), m)] += alive[x] * wa * ws;
          }
        }
      }
      const marry = f.first_marriage[i], divorce = f.divorce[i], remarry = f.remarriage[i];
      for (let w = 0; w < W_; w++) for (let c = 0; c < C_; c++) for (let a = 0; a < 2; a++) for (let s = 0; s < 2; s++) {
        const nv = p[idx(w, c, a, s, 0)], ma = p[idx(w, c, a, s, 1)], dv = p[idx(w, c, a, s, 2)];
        p[idx(w, c, a, s, 0)] = nv * (1 - marry);
        p[idx(w, c, a, s, 1)] = ma * (1 - divorce) + nv * marry + dv * remarry;
        p[idx(w, c, a, s, 2)] = dv * (1 - remarry) + ma * divorce;
      }
      const t = workTransition(sch.person.sex, sch.ages[i], sch.years[i], f.disability_start[i], f.retire[i]);
      let toDisabled = 0;
      for (let k = 1; k <= 24; k++) toDisabled += t[0][k];
      ever.disability += workingAtStart * toDisabled;
      const moved = new Float64Array(size);
      for (let w = 0; w < W_; w++) for (let w2 = 0; w2 < W_; w2++) {
        const tw = t[w][w2];
        if (tw === 0) continue;
        for (let c = 0; c < C_; c++) for (let a = 0; a < 2; a++) for (let s = 0; s < 2; s++) for (let m = 0; m < M_; m++) {
          moved[idx(w2, c, a, s, m)] += tw * p[idx(w, c, a, s, m)];
        }
      }
      p = moved;
    }
    let mean = 0;
    for (let i = 0; i < n; i++) mean += die[i] * (sch.ages[i] + 0.5);
    return {
      die, mean_death_age: mean, cause,
      ever_cancer: ever.cancer, ever_heart_attack: ever.heart_attack, ever_stroke: ever.stroke,
      ever_disability: ever.disability, crashes,
    };
  }

  // ------------------------------------------------------------ simulated lives (A03)

  // small, fast, seedable generator (mulberry32); the Python engine uses NumPy's,
  // so single lives differ, but averages over many lives match the exact results
  function rng(seed) {
    let s = seed >>> 0;
    return () => {
      s = (s + 0x6d2b79f5) >>> 0;
      let t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const cancerState = (s) => (s.cancer_site == null ? 0 : (s.cancer_site === "lung" ? 1 : 7) + Math.min(s.cancer_years, 5));

  function probabilities(sch, s, i) {
    const f = sch.fixed;
    const age = sch.ages[i], year = sch.years[i], sex = sch.person.sex;
    const out = { crash_injury: f.crash_injury[i] };
    if (!s.had_cancer) { out.cancer_lung = f.cancer_lung[i]; out.cancer_other = f.cancer_other[i]; }
    if (!s.had_heart_attack) out.heart_attack = f.heart_attack[i];
    if (!s.had_stroke) out.stroke = f.stroke[i];
    if (s.disabled && age <= K.DISABILITY_MAX_AGE) {
      out.disability_end = recovery(sex, s.disability_onset_age, s.disability_years, year, age);
    } else if (!s.disabled && !s.retired) out.disability_start = f.disability_start[i];
    if (!s.retired) out.retire = s.disabled ? (age > K.DISABILITY_MAX_AGE ? 1 : 0) : f.retire[i];
    const key = { never: "first_marriage", married: "divorce", divorced: "remarriage" }[s.marital];
    out[key] = f[key][i];
    if (!s.has_child) out.first_child = f.first_child[i];
    for (const k of Object.keys(out)) if (!(out[k] > 0)) delete out[k];
    return out;
  }

  function startingState(sch) {
    return {
      marital: sch.startMarital, has_child: false, retired: sch.person.age > 70, disabled: false,
      disability_onset_age: null, disability_years: 0, had_cancer: false, cancer_site: null,
      cancer_years: 0, had_heart_attack: false, had_stroke: false, crashes: 0,
    };
  }

  function live(sch, random) {
    const s = startingState(sch);
    const life = { events: [], death_age: 0, death_year: 0, cause: "" };
    for (let i = 0; i < sch.ages.length; i++) {
      const age = sch.ages[i], year = sch.years[i];
      const heartSurvivor = s.had_heart_attack, strokeSurvivor = s.had_stroke;
      const maritalNow = s.marital, disabledNow = s.disabled;
      const probs = probabilities(sch, s, i);
      const happened = new Set(Object.keys(probs).filter((k) => random() < probs[k]));
      const add = (e) => life.events.push([age, year, e]);
      if (happened.has("crash_injury")) { s.crashes += 1; add("crash_injury"); }
      if (happened.has("cancer_lung") || happened.has("cancer_other")) {
        s.had_cancer = true; s.cancer_years = 0;
        s.cancer_site = happened.has("cancer_lung") ? "lung" : "other";
        add("cancer_" + s.cancer_site);
      }
      if (happened.has("retire")) {
        add(s.disabled ? "disability_to_retirement" : "retire");
        s.retired = true; s.disabled = false;
      } else if (happened.has("disability_start")) {
        s.disabled = true; s.disability_onset_age = age; s.disability_years = 0; add("disability_start");
      } else if (happened.has("disability_end")) {
        s.disabled = false; add("disability_end");
      }
      for (const [e, nw] of [["first_marriage", "married"], ["divorce", "divorced"], ["remarriage", "married"]]) {
        if (happened.has(e)) { s.marital = nw; add(e); }
      }
      if (happened.has("first_child")) { s.has_child = true; add("first_child"); }
      for (const [e, attr, acute, c] of [["heart_attack", "had_heart_attack", sch.acuteH, "heart"],
                                         ["stroke", "had_stroke", sch.acuteS, "stroke"]]) {
        if (happened.has(e)) {
          s[attr] = true;
          add(e);
          if (random() < acute[i]) {
            life.death_age = age + random(); life.death_year = year; life.cause = c; life.final = s;
            return life;
          }
        }
      }
      const cs = cancerState(s);                          // includes a diagnosis this year, as in the Python engine
      const q = sch.qState[i][cs][+heartSurvivor][+strokeSurvivor][K.MARITAL_STATES.indexOf(maritalNow)][+disabledNow];
      if (random() < q) {
        life.death_age = age + random();
        life.death_year = year;
        const mixC = sch.cState[i][cs][+heartSurvivor][+strokeSurvivor];
        let u = random(), j = 0;
        while (j < NC - 1 && u >= mixC[j]) { u -= mixC[j]; j++; }
        life.cause = CAUSES[j];
        life.final = s;
        return life;
      }
      if (s.disabled) s.disability_years += 1;
      if (s.cancer_site != null) s.cancer_years += 1;
    }
    throw new Error("a life reached past age 110");
  }

  function simulate(answers, n = 1000, seed = 1, startYear = K.START_YEAR, startMarital = "never") {
    const sch = buildSchedule(answers, startYear, true, startMarital);
    const random = rng(seed);
    const lives = [];
    for (let k = 0; k < n; k++) lives.push(live(sch, random));
    return { schedule: sch, lives };
  }

  function summary(lives) {
    const ages = lives.map((l) => l.death_age).sort((a, b) => a - b);
    const pct = (q) => {                                  // linear interpolation, as NumPy's default
      const h = (ages.length - 1) * q, lo = Math.floor(h);
      return ages[lo] + (ages[Math.min(lo + 1, ages.length - 1)] - ages[lo]) * (h - lo);
    };
    const ever = (names) => lives.filter((l) => l.events.some(([, , e]) => names.includes(e))).length / lives.length;
    const causes = {};
    for (const c of CAUSES) causes[c] = lives.filter((l) => l.cause === c).length / lives.length;
    return {
      lives: lives.length,
      median_death_age: pct(0.5),
      mean_death_age: ages.reduce((x, y) => x + y, 0) / ages.length,
      death_age_10th_90th: [pct(0.1), pct(0.9)],
      reach_80: ages.filter((a) => a >= 80).length / ages.length,
      reach_90: ages.filter((a) => a >= 90).length / ages.length,
      cause_of_death: causes,
      ever: {
        crash_injury: ever(["crash_injury"]), cancer: ever(["cancer_lung", "cancer_other"]),
        heart_attack: ever(["heart_attack"]), stroke: ever(["stroke"]), disability: ever(["disability_start"]),
        married: ever(["first_marriage"]), divorced: ever(["divorce"]), first_child: ever(["first_child"]),
        retired: ever(["retire", "disability_to_retirement"]),
      },
    };
  }

  return {
    constants: K, person, levels, taper, hazard, averageMultiplier, driftRatio, smokingPath,
    personMultiplier, relativeMultiplier, improvementFactor, cohortQ, personalQ, lifeExpectancy,
    causeProbabilities, buildSchedule, exact, simulate, live, rng, summary,
  };
}
