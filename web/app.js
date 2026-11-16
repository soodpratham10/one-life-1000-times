// One Life, 1,000 Times: the website. Survey -> 1,000 lives -> how they end -> one life -> what moves the odds.
// All the arithmetic happens in worker.js (the engine, off the main thread); this file draws and listens.

const NS = "http://www.w3.org/2000/svg";
const $ = (sel) => document.querySelector(sel);
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// ------------------------------------------------------------ the engine, in a worker

const worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
let nextId = 1;
const pending = new Map();
worker.onmessage = ({ data }) => {
  const p = pending.get(data.id);
  if (!p) return;
  pending.delete(data.id);
  data.error ? p.reject(new Error(data.error)) : p.resolve(data.result);
};
worker.onerror = (e) => { for (const p of pending.values()) p.reject(new Error(e.message || "the engine stopped")); pending.clear(); };
function ask(message) {
  const id = nextId++;
  return new Promise((resolve, reject) => { pending.set(id, { resolve, reject }); worker.postMessage({ id, ...message }); });
}

// ------------------------------------------------------------ numbers from an exact result

function cdf(ex, x) {                    // share of lives ended by exact age x (deaths spread evenly in each year)
  let total = 0;
  for (let i = 0; i < ex.ages.length; i++) {
    const a = ex.ages[i];
    if (x >= a + 1) total += ex.die[i];
    else if (x > a) total += ex.die[i] * (x - a);
  }
  return total;
}
function quantile(ex, q) {
  let total = 0;
  for (let i = 0; i < ex.ages.length; i++) {
    if (total + ex.die[i] >= q) return ex.ages[i] + (q - total) / ex.die[i];
    total += ex.die[i];
  }
  return ex.ages[ex.ages.length - 1] + 1;
}
const pct = (x) => (x < 0.005 && x > 0 ? "under 1%" : `${Math.round(x * 100)}%`);
const whole = (x) => Math.floor(x);

const GROUPS = [
  { key: "cancer", label: "Cancer", causes: ["lung_cancer", "other_cancer"], colour: "var(--cancer)" },
  { key: "heart", label: "Heart disease and stroke", causes: ["heart", "stroke"], colour: "var(--heart)" },
  { key: "injury", label: "Accidents and injuries", causes: ["motor_vehicle", "other_accidents", "other_injury"], colour: "var(--injury)" },
  { key: "other", label: "Everything else", causes: null, colour: "var(--other)" },
];
const groupOf = (cause) => GROUPS.findIndex((g) => !g.causes || g.causes.includes(cause));

const CAUSE_NAMES = {
  lung_cancer: "Lung cancer", other_cancer: "Other cancers", heart: "Heart disease", stroke: "Stroke",
  copd: "Chronic lung disease (COPD)", diabetes: "Diabetes", dementia: "Dementia", motor_vehicle: "Car crashes",
  other_accidents: "Other accidents", other_injury: "Other injuries", other: "All other causes",
};

const SENTENCES = {
  crash_injury: "you are injured in a car crash",
  cancer_lung: "you are diagnosed with lung cancer",
  cancer_other: "you are diagnosed with cancer",
  heart_attack: "you have a heart attack",
  stroke: "you have a stroke",
  disability_start: "a serious illness or injury stops you working, and you go on CPP disability",
  disability_end: "you recover enough to leave disability",
  disability_to_retirement: "your disability pension becomes a retirement pension",
  retire: "you start your CPP retirement pension",
  first_marriage: "you get married",
  divorce: "you divorce",
  remarriage: "you marry again",
  first_child: "a child is born",
};
const DEATH_WORDS = {
  lung_cancer: "lung cancer", other_cancer: "cancer", heart: "heart disease", stroke: "a stroke",
  copd: "chronic lung disease", diabetes: "diabetes", dementia: "dementia", motor_vehicle: "injuries from a car crash",
  other_accidents: "an accident", other_injury: "an injury", other: "other causes",
};

// ------------------------------------------------------------ the 1,000 lines

function svgEl(name, attrs = {}, parent) {
  const el = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (parent) parent.appendChild(el);
  return el;
}

function drawLives(container, lives, startAge, { colour = "ink", exact = null, compact = false, animate = true } = {}) {
  // one dot per life, stacked in a column at the age that life ends (a quantile dot plot)
  const narrow = container.clientWidth > 0 && container.clientWidth < 620;
  const W = 960, H = narrow ? 900 : compact ? 560 : 540;
  const L = 8, R = 948, TOP = narrow ? 80 : compact ? 64 : 58, BOT = H - (narrow ? 70 : 44);
  const span = 111 - startAge;
  const x = (age) => L + ((age - startAge) / span) * (R - L);
  const colW = (R - L) / span;
  const columns = new Map();
  for (const life of lives) {
    const a = Math.min(Math.floor(life.age), 110);
    if (!columns.has(a)) columns.set(a, []);
    columns.get(a).push(life);
  }
  const peak = Math.max(...[...columns.values()].map((c) => c.length));
  const step = Math.min(colW, (BOT - TOP) / peak);
  const r = Math.max(1.6, step * 0.42);
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, "aria-hidden": "true",
    style: narrow ? "--tick:36px;--mark:38px" : compact ? "--tick:22px;--mark:24px" : "--tick:17px;--mark:19px" });
  const id = `clip-${Math.random().toString(36).slice(2)}`;
  const clip = svgEl("clipPath", { id }, svgEl("defs", {}, svg));
  svgEl("rect", { class: "reveal", x: 0, y: 0, width: W, height: H }, clip);

  const tick = (a, label, anchor = "middle") => {
    const t = svgEl("text", { x: x(a), y: BOT + (narrow ? 52 : compact ? 36 : 32), "text-anchor": anchor }, svg);
    t.textContent = label;
  };
  tick(startAge, narrow ? `${startAge}` : `age ${startAge}`, "start");
  for (let a = Math.ceil((startAge + (narrow ? 8 : 4)) / 10) * 10; a <= 110; a += narrow ? 20 : 10) tick(a + 0.5, a);
  svgEl("line", { class: "axis", x1: L, x2: R, y1: BOT + 0.5, y2: BOT + 0.5 }, svg);

  const g = svgEl("g", { "clip-path": `url(#${id})` }, svg);
  const order = (life) => (colour === "cause" ? groupOf(life.cause) : 0);
  for (const [a, col] of columns) {
    col.sort((p, q) => order(p) - order(q));
    col.forEach((life, k) => {
      svgEl("circle", {
        cx: (x(a) + colW / 2).toFixed(1), cy: (BOT - step * (k + 0.5)).toFixed(1), r: r.toFixed(2),
        fill: colour === "cause" ? GROUPS[groupOf(life.cause)].colour : "var(--ink)",
        "fill-opacity": colour === "cause" ? 0.95 : 0.82,
      }, g);
    });
  }

  if (exact) {
    const marks = [[0.1, (a) => `1 in 10 end before ${whole(a)}`], [0.5, (a) => `half last past ${whole(a)}`], [0.9, (a) => `1 in 10 last past ${whole(a)}`]];
    const rows = narrow ? [TOP - 24, TOP - 24, TOP - 24] : [TOP - (compact ? 40 : 34), TOP - (compact ? 10 : 8), TOP - (compact ? 40 : 34)];
    marks.forEach(([q, label], i) => {
      const a = quantile(exact, q);
      const cx = x(a);
      svgEl("line", { x1: cx, x2: cx, y1: rows[i] + 8, y2: BOT, stroke: "var(--accent)", "stroke-width": 1.5, "stroke-dasharray": "3 4" }, svg);
      const anchor = i === 0 ? "end" : i === 2 ? "start" : "middle";
      const t = svgEl("text", { class: "marker-label", x: cx + (i === 0 ? -6 : i === 2 ? 6 : 0), y: rows[i], "text-anchor": anchor }, svg);
      t.textContent = narrow ? `${whole(a)}` : label(a);
    });
  }
  container.replaceChildren(svg);
  // keep marker labels inside the frame
  svg.querySelectorAll(".marker-label").forEach((t) => {
    const box = t.getBBox();
    if (box.x + box.width > W - 2) t.setAttribute("x", Number(t.getAttribute("x")) - (box.x + box.width - W + 2));
    if (box.x < 2) t.setAttribute("x", Number(t.getAttribute("x")) + (2 - box.x));
  });
  container.classList.remove("drawn");
  if (animate && !reduceMotion) {
    requestAnimationFrame(() => requestAnimationFrame(() => container.classList.add("drawn")));
  } else {
    container.classList.add("drawn");
  }
}

let lastOdds = null;
function drawOdds(container, base, changed) {
  lastOdds = [base, changed];
  const narrow = container.clientWidth > 0 && container.clientWidth < 620;
  const W = 760, H = narrow ? 520 : 330, L = 4, R = 756, TOP = 10, BOT = H - (narrow ? 56 : 36);
  const start = base.ages[0];
  const width = 2;
  const bins = [];
  for (let a = start; a <= 110; a += width) bins.push(a);
  const binned = (ex) => bins.map((b) => ex.ages.reduce((s, a, i) => (a >= b && a < b + width ? s + ex.die[i] : s), 0));
  const b0 = binned(base), b1 = binned(changed);
  const peak = Math.max(...b0, ...b1) || 1;
  const x = (age) => L + ((age - start) / (112 - start)) * (R - L);
  const bw = x(start + width) - x(start);
  const h = (v) => (v / peak) * (BOT - TOP - 24);
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, "aria-hidden": "true", style: narrow ? "--tick:30px" : "" });
  for (let a = Math.ceil((start + 3) / 10) * 10; a <= 110; a += narrow ? 20 : 10) {
    svgEl("line", { class: "axis", x1: x(a), x2: x(a), y1: TOP, y2: BOT, "stroke-dasharray": "2 5" }, svg);
    const t = svgEl("text", { x: x(a), y: BOT + (narrow ? 40 : 24), "text-anchor": "middle" }, svg);
    t.textContent = a;
  }
  svgEl("line", { class: "axis", x1: L, x2: R, y1: BOT + 0.5, y2: BOT + 0.5 }, svg);
  bins.forEach((b, i) => {
    if (b1[i] > 0) svgEl("rect", { x: x(b) + 1, y: BOT - h(b1[i]), width: Math.max(bw - 2, 1), height: h(b1[i]), rx: 1.5, fill: "var(--accent)", "fill-opacity": 0.82 }, svg);
  });
  const outline = bins.map((b, i) => `M${(x(b) + 1).toFixed(1)} ${BOT}V${(BOT - h(b0[i])).toFixed(1)}H${(x(b) + bw - 1).toFixed(1)}V${BOT}`).join("");
  svgEl("path", { d: outline, fill: "none", stroke: "var(--ink)", "stroke-width": 1.5 }, svg);
  const same = base === changed;
  const lines = same ? [[base, "var(--ink)", 0, "your answers"]] : [[base, "var(--ink)", 0, "your answers"], [changed, "var(--accent)", 20, "with the change"]];
  for (const [ex, colour] of lines) {
    const m = quantile(ex, 0.5);
    svgEl("line", { x1: x(m), x2: x(m), y1: TOP + 14, y2: BOT, stroke: colour, "stroke-width": 2, "stroke-dasharray": colour === "var(--ink)" ? "4 3" : "" }, svg);
  }
  const key = el("ul", { class: "odds-key" },
    el("li", {}, el("i", { class: "k-outline" }), "Your answers"),
    same ? null : el("li", {}, el("i", { class: "k-fill" }), "With the change"),
    el("li", {}, el("i", { class: "k-line" }), "The middle: half your lives end before it"));
  container.replaceChildren(svg, key);
}

// ------------------------------------------------------------ the survey

const PROVINCES = [
  ["NL", "Newfoundland and Labrador"], ["PE", "Prince Edward Island"], ["NS", "Nova Scotia"], ["NB", "New Brunswick"],
  ["QC", "Quebec"], ["ON", "Ontario"], ["MB", "Manitoba"], ["SK", "Saskatchewan"], ["AB", "Alberta"], ["BC", "British Columbia"],
];
const answers = { units: "metric", startMarital: "never" };

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (v === true) node.setAttribute(k, "");
    else if (v !== false && v != null) node.setAttribute(k, v);
  }
  for (const c of children) if (c != null) node.append(c);
  return node;
}

function choice(name, options, current, onChange, two = false) {
  const wrap = el("div", { class: two ? "options two" : "options" });
  options.forEach(([value, label, sub], i) => {
    const id = `${name}-${i}`;
    const input = el("input", { type: "radio", name, id, value, checked: current === value });
    input.addEventListener("change", () => onChange(value));
    wrap.append(el("div", { class: "option" }, input, el("label", { for: id }, label, sub ? el("small", {}, sub) : null)));
  });
  return wrap;
}

function numberField({ id, label, hint, unit, value, min, max, step = 1, check, onInput }) {
  const input = el("input", { type: "number", id, inputmode: step < 1 ? "decimal" : "numeric", min, max, step, value: value ?? "" });
  const msg = el("p", { class: "msg", id: `${id}-msg`, "aria-live": "polite" });
  input.setAttribute("aria-describedby", `${id}-msg`);
  const field = el("div", { class: "field" }, el("label", { for: id }, label), hint ? el("span", { class: "hint" }, hint) : null,
    el("div", { class: "input-wrap" }, input, unit ? el("span", { class: "unit" }, unit) : null), msg);
  const run = (show) => {
    const raw = input.value.trim();
    const v = raw === "" ? null : Number(raw);
    const problem = v === null ? "Enter a number." : check(v);
    field.classList.toggle("valid", show && !problem);
    field.classList.toggle("invalid", show && !!problem);
    msg.textContent = show ? (problem || "Looks good.") : "";
    onInput(problem ? null : v);
    return !problem;
  };
  input.addEventListener("input", () => run(true));
  field.validate = () => run(true);
  field.quiet = () => run(false);
  return field;
}

const QUESTIONS = [
  {
    title: "Which life table should you start from?",
    help: "Canada's life tables are published for men and women separately, so this picks your starting death rates.",
    render(body, done) {
      body.append(choice("sex", [["F", "Female"], ["M", "Male"]], answers.sex, (v) => { answers.sex = v; done(true); }, true));
      done(!!answers.sex);
    },
  },
  {
    title: "How old are you?",
    help: "In whole years. The model covers adults from 18.",
    render(body, done) {
      const f = numberField({ id: "age", label: "Age", unit: "years", value: answers.age, min: 18, max: 109,
        check: (v) => (!Number.isInteger(v) ? "Use whole years." : v < 18 ? "The model starts at 18." : v > 109 ? "The model runs to 109." : null),
        onInput: (v) => { answers.age = v; done(v !== null); } });
      body.append(f);
      answers.age != null ? f.validate() : f.quiet();
    },
  },
  {
    title: "Where do you live?",
    help: "Death rates differ by province. The territories are not covered by the data yet, so choose Canada as a whole if you live there.",
    render(body, done) {
      const sel = el("select", { id: "region" }, el("option", { value: "" }, "Choose a province"),
        el("option", { value: "CA" }, "Canada as a whole"), ...PROVINCES.map(([code, name]) => el("option", { value: code }, name)));
      sel.value = answers.region || "";
      sel.addEventListener("change", () => { answers.region = sel.value || null; done(!!sel.value); });
      body.append(el("div", { class: "field" }, el("label", { for: "region" }, "Province"), sel));
      done(!!answers.region);
    },
  },
  {
    title: "Do you smoke?",
    help: "Cigarettes, daily or now and then.",
    render(body, done) {
      const follow = el("div");
      const update = () => {
        follow.replaceChildren();
        if (answers.smoking === "former") {
          const f = numberField({ id: "quit", label: "How old were you when you quit?", unit: "years", value: answers.quit_age, min: 10, max: answers.age,
            check: (v) => (!Number.isInteger(v) ? "Use whole years." : v < 10 ? "Enter an age of 10 or more." : v > answers.age ? `That is older than you are now (${answers.age}).` : null),
            onInput: (v) => { answers.quit_age = v; done(v !== null); } });
          follow.append(el("div", { class: "follow" }, f));
          answers.quit_age != null ? f.validate() : (f.quiet(), done(false));
        } else if (answers.smoking === "current") {
          follow.append(el("div", { class: "follow" },
            el("p", { class: "q-help" }, "Most Canadian smokers quit at some point. Should your lives allow for that?"),
            choice("keeps", [["false", "Yes, I may well quit", "About 5 in 100 smokers quit for good each year from 25."], ["true", "No, assume I keep smoking", "Shows what smoking for life does."]],
              answers.keeps_smoking == null ? null : String(answers.keeps_smoking), (v) => { answers.keeps_smoking = v === "true"; done(true); })));
          done(answers.keeps_smoking != null);
        } else {
          done(answers.smoking === "never");
        }
      };
      body.append(choice("smoking", [["never", "I have never smoked"], ["former", "I used to smoke"], ["current", "I smoke now"]], answers.smoking,
        (v) => { answers.smoking = v; if (v !== "former") answers.quit_age = null; if (v !== "current") answers.keeps_smoking = null; update(); }), follow);
      update();
    },
  },
  {
    title: "How active are you in a usual week?",
    help: "Minutes of activity in your spare time that gets you breathing harder: brisk walking, cycling, swimming, sport.",
    render(body, done) {
      const f = numberField({ id: "activity", label: "Minutes a week", unit: "minutes", value: answers.activity_minutes, min: 0, max: 3000, step: 5,
        check: (v) => (v < 0 ? "Minutes cannot be negative." : v > 3000 ? "That is more than 50 hours; enter up to 3,000." : null),
        onInput: (v) => { answers.activity_minutes = v; done(v !== null); } });
      const chips = el("div", { class: "toggle", role: "group", "aria-label": "Common answers" },
        ...[[0, "None"], [60, "About an hour"], [150, "2½ hours"], [300, "5 hours"], [450, "7½ hours"]].map(([m, label]) => {
          const b = el("button", { type: "button", class: "chip", "aria-pressed": "false" }, label);
          b.addEventListener("click", () => { f.querySelector("input").value = m; f.validate(); });
          return b;
        }));
      body.append(f, chips);
      answers.activity_minutes != null ? f.validate() : f.quiet();
    },
  },
  {
    title: "How tall are you, and how much do you weigh?",
    help: "Used for your body-mass index.",
    render(body, done) {
      const holder = el("div");
      const draw = () => {
        holder.replaceChildren();
        const metric = answers.units === "metric";
        const state = { h: null, w: null };
        const check = () => {
          const ok = state.h != null && state.w != null;
          if (!ok) return done(false);
          const bmi = state.w / (state.h / 100) ** 2;
          const msg = holder.querySelector(".bmi");
          if (bmi < 12 || bmi > 80) { msg.textContent = "Those two together are outside the range the studies cover; check the numbers."; msg.style.color = "var(--bad)"; return done(false); }
          msg.textContent = `Body-mass index ${bmi.toFixed(1)}.`;
          msg.style.color = "var(--good)";
          answers.height_cm = state.h; answers.weight_kg = state.w;
          done(true);
        };
        const fields = metric ? [
          numberField({ id: "h", label: "Height", unit: "cm", value: answers.height_cm != null ? Math.round(answers.height_cm) : null, min: 120, max: 230,
            check: (v) => (v < 120 || v > 230 ? "Enter 120 to 230 cm." : null), onInput: (v) => { state.h = v; check(); } }),
          numberField({ id: "w", label: "Weight", unit: "kg", value: answers.weight_kg != null ? Math.round(answers.weight_kg) : null, min: 30, max: 300,
            check: (v) => (v < 30 || v > 300 ? "Enter 30 to 300 kg." : null), onInput: (v) => { state.w = v; check(); } }),
        ] : (() => {
          const inches = answers.height_cm != null ? answers.height_cm / 2.54 : null;
          const imp = { ft: inches != null ? Math.floor(inches / 12) : null, inch: inches != null ? Math.round(inches % 12) : null };
          const setH = () => { state.h = imp.ft != null && imp.inch != null ? (imp.ft * 12 + imp.inch) * 2.54 : null; if (state.h != null && (state.h < 120 || state.h > 230)) state.h = null; check(); };
          return [
            numberField({ id: "ft", label: "Height, feet", unit: "ft", value: imp.ft, min: 3, max: 7,
              check: (v) => (!Number.isInteger(v) || v < 3 || v > 7 ? "Enter 3 to 7 feet." : null), onInput: (v) => { imp.ft = v; setH(); } }),
            numberField({ id: "in", label: "and inches", unit: "in", value: imp.inch, min: 0, max: 11,
              check: (v) => (v < 0 || v >= 12 ? "Enter 0 to 11 inches." : null), onInput: (v) => { imp.inch = v; setH(); } }),
            numberField({ id: "lb", label: "Weight", unit: "lb", value: answers.weight_kg != null ? Math.round(answers.weight_kg / 0.45359237) : null, min: 66, max: 660,
              check: (v) => (v < 66 || v > 660 ? "Enter 66 to 660 lb." : null), onInput: (v) => { state.w = v == null ? null : v * 0.45359237; check(); } }),
          ];
        })();
        holder.append(el("div", { class: "pair" }, ...fields), el("p", { class: "msg bmi", "aria-live": "polite" }));
        fields.forEach((f) => (f.querySelector("input").value ? f.validate() : f.quiet()));
      };
      const units = el("div", { class: "toggle units-toggle", role: "group", "aria-label": "Units" },
        ...[["metric", "Centimetres and kilograms"], ["imperial", "Feet, inches and pounds"]].map(([u, label]) => {
          const b = el("button", { type: "button", class: "chip", "aria-pressed": String(answers.units === u) }, label);
          b.addEventListener("click", () => {
            answers.units = u;
            units.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", String(c === b)));
            draw();
          });
          return b;
        }));
      body.append(units, holder);
      draw();
    },
  },
  {
    title: "How many drinks do you have in a usual week?",
    help: "One drink is a 341 ml bottle of 5% beer, a 142 ml glass of 12% wine, or a 43 ml shot of 40% spirits.",
    render(body, done) {
      const f = numberField({ id: "drinks", label: "Drinks a week", unit: "drinks", value: answers.drinks_per_week, min: 0, max: 150, step: 0.5,
        check: (v) => (v < 0 ? "Drinks cannot be negative." : v > 150 ? "Enter up to 150." : null),
        onInput: (v) => { answers.drinks_per_week = v; done(v !== null); } });
      body.append(f);
      answers.drinks_per_week != null ? f.validate() : f.quiet();
    },
  },
  {
    title: "How many servings of fruit and vegetables do you eat a day?",
    help: "A serving is about one medium fruit or half a cup of vegetables. Potatoes and juice count once at most.",
    render(body, done) {
      const f = numberField({ id: "fv", label: "Servings a day", unit: "servings", value: answers.fruit_veg_per_day, min: 0, max: 20, step: 0.5,
        check: (v) => (v < 0 ? "Servings cannot be negative." : v > 20 ? "Enter up to 20." : null),
        onInput: (v) => { answers.fruit_veg_per_day = v; done(v !== null); } });
      body.append(f);
      answers.fruit_veg_per_day != null ? f.validate() : f.quiet();
    },
  },
  {
    title: "Are you married?",
    help: "The data cover legal marriage, so living common-law counts as not married. Married people have lower death rates on average.",
    render(body, done) {
      body.append(choice("marital", [["never", "I have never been married"], ["married", "I am married"], ["divorced", "I am divorced, separated or widowed"]],
        answers.marital, (v) => { answers.marital = v; done(true); }));
      done(!!answers.marital);
    },
  },
];

let step = 0;
function showQuestion() {
  const q = QUESTIONS[step];
  const body = $("#question-body");
  body.replaceChildren(el("fieldset", {}, el("legend", { class: "q-title", id: "q-title" }, q.title), el("p", { class: "q-help" }, q.help)));
  const fs = body.querySelector("fieldset");
  const next = $("#next");
  const done = (ok) => { next.disabled = !ok; };
  q.render(fs, done);
  $("#progress-text").textContent = `Question ${step + 1} of ${QUESTIONS.length}`;
  $("#progress-bar").style.width = `${(step / QUESTIONS.length) * 100}%`;
  $("#back").style.visibility = step === 0 ? "hidden" : "visible";
  next.querySelector(".button-label").textContent = step === QUESTIONS.length - 1 ? "See my 1,000 lives" : "Next";
  const form = $("#question");
  form.classList.remove("leaving");
  form.style.animation = "none";
  void form.offsetWidth;
  form.style.animation = "";
  const top = $("#survey").getBoundingClientRect().top;
  if (step > 0 && (top < -40 || top > innerHeight * 0.5)) $("#survey").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  const first = fs.querySelector("input, select");
  if (first && step > 0) first.focus({ preventScroll: true });
}

function leaveQuestion(then) {
  const form = $("#question");
  if (reduceMotion) return then();
  form.classList.add("leaving");
  setTimeout(then, 160);
}

function engineAnswers() {
  return {
    sex: answers.sex, age: answers.age, region: answers.region, smoking: answers.smoking,
    quit_age: answers.smoking === "former" ? answers.quit_age : null, keeps_smoking: answers.smoking === "current" ? !!answers.keeps_smoking : false,
    activity_minutes: answers.activity_minutes, height_cm: answers.height_cm, weight_kg: answers.weight_kg,
    drinks_per_week: answers.drinks_per_week, fruit_veg_per_day: answers.fruit_veg_per_day,
  };
}

// ------------------------------------------------------------ results

let result = null;
let storyIndex = 0;

function describe(a) {
  const sex = a.sex === "F" ? "woman" : "man";
  const place = a.region === "CA" ? "in Canada" : `in ${PROVINCES.find(([c]) => c === a.region)[1]}`;
  const smoke = a.smoking === "never" ? "who has never smoked" : a.smoking === "former" ? `who quit smoking at ${a.quit_age}`
    : a.keeps_smoking ? "who smokes and keeps smoking" : "who smokes now";
  return `A ${a.age}-year-old ${sex} ${place} ${smoke}, from ${result.exact.startYear}. Future death rates fall the way the Chief Actuary of Canada assumes.`;
}

function renderResults(a) {
  const ex = result.exact;
  $("#results-who").textContent = describe(a);
  drawLives($("#lives-chart"), result.lives, a.age, { colour: currentColour, exact: ex });
  $("#lives-chart").setAttribute("aria-label", `1,000 simulated lives from age ${a.age}. Half last past ${whole(quantile(ex, 0.5))}.`);

  const stats = [
    ["Half of your lives last past", `${whole(quantile(ex, 0.5))}`, "years"],
    ["1 in 10 end before", `${whole(quantile(ex, 0.1))}`, ""],
    ["1 in 10 last past", `${whole(quantile(ex, 0.9))}`, ""],
    ["Reach 80", pct(1 - cdf(ex, 80)), "of your lives"],
    ["Reach 90", pct(1 - cdf(ex, 90)), "of your lives"],
  ].filter(([label]) => !(label.startsWith("Reach 80") && a.age >= 80) && !(label.startsWith("Reach 90") && a.age >= 90));
  $("#lives-summary").replaceChildren(...stats.map(([dt, dd, small]) => el("div", {}, el("dt", {}, dt), el("dd", {}, dd, small ? el("small", {}, ` ${small}`) : null))));

  // how they end: exact cause shares
  const total = ex.cause.reduce((s, v) => s + v, 0);
  const rows = result.causes.map((c, i) => [c, ex.cause[i] / total]).sort((p, q) => q[1] - p[1]);
  const top = rows[0][1];
  $("#causes").replaceChildren(...rows.map(([c, share]) => el("li", {},
    el("span", {}, CAUSE_NAMES[c]),
    el("span", { class: "track" }, el("span", { class: "fill", style: `width:${(share / top) * 100}%` })),
    el("span", { class: "value" }, pct(share)))));

  // along the way, from the 1,000 lives
  const ever = (names) => result.lives.filter((l) => l.events.some(([, , e]) => names.includes(e))).length / result.lives.length;
  const items = [];
  if (a.marital === "never") items.push(["Get married", ever(["first_marriage"])]);
  if (a.marital === "married") items.push(["Divorce", ever(["divorce"])]);
  items.push(["Are diagnosed with cancer", ever(["cancer_lung", "cancer_other"])],
    ["Have a heart attack", ever(["heart_attack"])], ["Have a stroke", ever(["stroke"])],
    ["Are injured in a car crash", ever(["crash_injury"])]);
  if (a.age < 65) items.push(["Go on CPP disability", ever(["disability_start"])]);
  if (a.age < 60) items.push(["Start a CPP retirement pension", ever(["retire", "disability_to_retirement"])]);
  $("#chances").replaceChildren(...items.map(([label, v]) => el("li", {}, el("span", {}, label), el("strong", {}, pct(v)))));

  storyIndex = Math.floor(Math.random() * result.lives.length);
  renderStory();
  renderControls(a);
}

function renderStory() {
  const life = result.lives[storyIndex];
  const items = life.events.map(([age, year, e]) => el("li", {}, el("span", { class: "when" }, `At ${age}, in ${year}`), capital(SENTENCES[e]) + "."));
  items.push(el("li", { class: "end" }, el("span", { class: "when" }, `At ${whole(life.age)}, in ${life.year}`), `You die of ${DEATH_WORDS[life.cause]}.`));
  if (!life.events.length) items.unshift(el("li", {}, el("span", { class: "when" }, "Along the way"), "None of the events the model follows happen in this life."));
  items.forEach((li, i) => { li.style.animationDelay = reduceMotion ? "0ms" : `${Math.min(i * 40, 400)}ms`; });
  $("#timeline").replaceChildren(...items);
}
const capital = (s) => s.charAt(0).toUpperCase() + s.slice(1);

let currentColour = "ink";
document.querySelectorAll(".lives-figure .chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    currentColour = chip.dataset.colour;
    document.querySelectorAll(".lives-figure .chip").forEach((c) => c.setAttribute("aria-pressed", String(c === chip)));
    drawLives($("#lives-chart"), result.lives, answers.age, { colour: currentColour, exact: result.exact, animate: false });
    const legend = $("#lives-legend");
    legend.hidden = currentColour !== "cause";
    if (!legend.hidden) {
      const share = GROUPS.map((g, k) => result.lives.filter((l) => groupOf(l.cause) === k).length / result.lives.length);
      legend.replaceChildren(...GROUPS.map((g, k) => el("li", {}, el("i", { style: `background:${g.colour}` }), `${g.label} ${pct(share[k])}`)));
    }
  });
});

// ------------------------------------------------------------ what moves the odds

let oddsTimer = null, oddsToken = 0;
function renderControls(a) {
  const form = $("#controls");
  const change = { ...engineAnswers() };
  const smokingOptions = [["never", "Never smoked"]];
  if (a.smoking === "former") smokingOptions.push(["former", `Quit at ${a.quit_age}, as you said`]);
  smokingOptions.push(["quit_now", `Quit now, at ${a.age}`], ["current", "Smoke, and may quit later"], ["keeps", "Smoke, and keep smoking"]);
  const smokingNow = a.smoking === "never" ? "never" : a.smoking === "former" ? "former" : a.keeps_smoking ? "keeps" : "current";
  const sel = el("select", { id: "c-smoking" }, ...smokingOptions.map(([v, label]) => el("option", { value: v, selected: v === smokingNow }, label)));
  const range = (id, label, min, max, stepv, value, fmt) => {
    const out = el("output", { for: id }, fmt(value));
    const input = el("input", { type: "range", id, min, max, step: stepv, value });
    input.addEventListener("input", () => { out.textContent = fmt(Number(input.value)); schedule(); });
    return [el("div", { class: "control" }, el("label", { for: id }, label, out), input), input];
  };
  const bmiOf = (w) => w / (a.height_cm / 100) ** 2;
  const [activityC, activity] = range("c-activity", "Activity", 0, Math.max(600, a.activity_minutes), 15, a.activity_minutes, (v) => `${v} min a week`);
  const [weightC, weight] = range("c-weight", "Weight", Math.max(30, Math.round(a.weight_kg - 40)), Math.min(300, Math.round(a.weight_kg + 40)), 1, Math.round(a.weight_kg),
    (v) => `${v} kg, BMI ${bmiOf(v).toFixed(1)}`);
  const [drinksC, drinks] = range("c-drinks", "Drinks", 0, Math.max(40, a.drinks_per_week), 1, Math.round(a.drinks_per_week), (v) => `${v} a week`);
  const [fvC, fv] = range("c-fv", "Fruit and vegetables", 0, Math.max(10, a.fruit_veg_per_day), 0.5, a.fruit_veg_per_day, (v) => `${v} a day`);
  const reset = el("button", { type: "button", class: "button quiet" }, "Back to my answers");
  reset.addEventListener("click", () => renderControls(a));
  sel.addEventListener("change", schedule);
  form.replaceChildren(el("div", { class: "control" }, el("label", { for: "c-smoking" }, "Smoking"), sel), activityC, weightC, drinksC, fvC, el("div", {}, reset));

  function read() {
    const s = sel.value;
    return {
      ...change,
      smoking: s === "quit_now" ? "former" : s === "keeps" ? "current" : s,
      quit_age: s === "quit_now" ? a.age : s === "former" ? a.quit_age : null,
      keeps_smoking: s === "keeps",
      activity_minutes: Number(activity.value), weight_kg: Number(weight.value),
      drinks_per_week: Number(drinks.value), fruit_veg_per_day: Number(fv.value),
    };
  }
  function schedule() {
    clearTimeout(oddsTimer);
    $("#odds-chart").classList.add("busy");
    oddsTimer = setTimeout(async () => {
      const token = ++oddsToken;
      try {
        const changed = await ask({ type: "exact", answers: read(), startMarital: a.marital });
        if (token !== oddsToken) return;
        const before = quantile(result.exact, 0.5), after = quantile(changed, 0.5);
        const diff = after - before;
        const words = Math.abs(diff) < 0.05 ? "no change"
          : `${Math.abs(diff).toFixed(1)} years ${diff > 0 ? "more" : "less"}`;
        $("#odds-result").innerHTML = `Half of your lives would last past <strong>${whole(after)}</strong> instead of ${whole(before)}: ${words} at the middle.`;
        drawOdds($("#odds-chart"), result.exact, changed);
      } catch (err) {
        $("#odds-result").textContent = `That change could not be worked out: ${err.message}.`;
      } finally {
        if (token === oddsToken) $("#odds-chart").classList.remove("busy");
      }
    }, 200);
  }
  $("#odds-result").textContent = "Move a slider or pick another smoking answer to compare.";
  drawOdds($("#odds-chart"), result.exact, result.exact);
}

// ------------------------------------------------------------ page wiring

async function runSurvey() {
  const next = $("#next");
  next.setAttribute("aria-busy", "true");
  next.disabled = true;
  next.querySelector(".button-label").textContent = "Working out your lives";
  const a = { ...engineAnswers(), marital: answers.marital };
  try {
    result = await ask({ type: "lives", answers: engineAnswers(), startMarital: answers.marital, n: 1000, seed: Math.floor(Math.random() * 2 ** 31) });
    $("#survey").hidden = true;
    $("#results").hidden = false;
    renderResults(a);
    observeRises();
    $("#results").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    $("#results-title").focus({ preventScroll: true });
  } catch (err) {
    next.querySelector(".button-label").textContent = "Try again";
    $("#progress-text").textContent = `Your lives could not be worked out: ${err.message}. Check your answers and try again.`;
  } finally {
    next.removeAttribute("aria-busy");
    next.disabled = false;
  }
}

$("#question").addEventListener("submit", (e) => {
  e.preventDefault();
  if ($("#next").disabled) return;
  if (step < QUESTIONS.length - 1) leaveQuestion(() => { step++; showQuestion(); });
  else runSurvey();
});
$("#back").addEventListener("click", () => { if (step > 0) leaveQuestion(() => { step--; showQuestion(); }); });
$("#start").addEventListener("click", () => {
  $("#survey").hidden = false;
  step = 0;
  showQuestion();
  $("#survey").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  $("#survey-title").focus({ preventScroll: true });
});
$("#another").addEventListener("click", () => { storyIndex = (storyIndex + 1 + Math.floor(Math.random() * 997)) % result.lives.length; renderStory(); });
$("#restart").addEventListener("click", () => {
  $("#results").hidden = true;
  $("#survey").hidden = false;
  step = 0;
  showQuestion();
  $("#survey").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
});

// back-to-top: the one floating control
const toTop = $("#to-top");
addEventListener("scroll", () => { toTop.hidden = scrollY < innerHeight * 1.5; }, { passive: true });
toTop.addEventListener("click", () => scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" }));

// gentle scroll reveal, once each
function observeRises() {
  const targets = document.querySelectorAll(".band .block, .story, .odds");
  if (reduceMotion || !("IntersectionObserver" in window)) return;
  const io = new IntersectionObserver((entries) => {
    for (const en of entries) if (en.isIntersecting) { en.target.classList.add("seen"); io.unobserve(en.target); }
  }, { threshold: 0.12 });
  targets.forEach((t) => { if (!t.classList.contains("seen")) { t.classList.add("rise"); io.observe(t); } });
}

// redraw the charts when the window crosses the phone width, so the text stays readable
let introResult = null, wasNarrow = innerWidth < 700, resizeTimer = null;
addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    const narrow = innerWidth < 700;
    if (narrow === wasNarrow) return;
    wasNarrow = narrow;
    if (introResult) drawLives($("#intro-chart"), introResult.lives, EXAMPLE.age, { exact: introResult.exact, compact: true, animate: false });
    if (result && !$("#results").hidden) {
      drawLives($("#lives-chart"), result.lives, answers.age, { colour: currentColour, exact: result.exact, animate: false });
      if (lastOdds) drawOdds($("#odds-chart"), ...lastOdds);
    }
  }, 200);
});

// the example on the first screen
const EXAMPLE = { sex: "F", age: 40, region: "ON", smoking: "never", activity_minutes: 150, height_cm: 163, weight_kg: 66,
  drinks_per_week: 3, fruit_veg_per_day: 3 };
ask({ type: "lives", answers: EXAMPLE, n: 1000, seed: 20261116 })
  .then((r) => {
    introResult = r;
    drawLives($("#intro-chart"), r.lives, EXAMPLE.age, { exact: r.exact, compact: true });
    $("#start").disabled = false;
    $("#load-status").textContent = "";
  })
  .catch((err) => {
    const s = $("#load-status");
    s.textContent = `The data could not be loaded (${err.message}). Reload the page to try again.`;
    s.classList.add("error");
  });
