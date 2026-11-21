// One Life, 1,000 Times: the website.
// The sky -> the consultation -> the casting -> the five cards -> the reading in words -> the life chart
// -> four other lives -> change your fate -> the actuary's table -> the share card.
// Every number comes from the engine in worker.js; nothing here is invented for effect.

const $ = (s) => document.querySelector(s);
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const C = { night: "#0c1626", star: "#dde7f0", dim: "#8fa2b7", ochre: "#d9a648", rule: "#2a3b55" };
const wait = (ms) => new Promise((r) => setTimeout(r, reduceMotion ? 0 : ms));

// ------------------------------------------------------------ the engine

const worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
let nextId = 1;
const pending = new Map();
worker.onmessage = ({ data }) => {
  const p = pending.get(data.id);
  if (!p) return;
  pending.delete(data.id);
  data.error ? p.reject(new Error(data.error)) : p.resolve(data.result);
};
const ask = (m) => new Promise((resolve, reject) => { const id = nextId++; pending.set(id, { resolve, reject }); worker.postMessage({ id, ...m }); });

const PROVINCES = [["NL", "Newfoundland and Labrador"], ["PE", "Prince Edward Island"], ["NS", "Nova Scotia"], ["NB", "New Brunswick"],
  ["QC", "Quebec"], ["ON", "Ontario"], ["MB", "Manitoba"], ["SK", "Saskatchewan"], ["AB", "Alberta"], ["BC", "British Columbia"]];
const placeName = (code) => (code === "CA" ? "Canada" : PROVINCES.find(([c]) => c === code)[1]);
const EXAMPLE = { sex: "F", age: 40, region: "ON", smoking: "never", activity_minutes: 150, height_cm: 163, weight_kg: 66, drinks_per_week: 3, fruit_veg_per_day: 3 };
const SAMPLES = {
  smoker: { answers: { sex: "M", age: 45, region: "MB", smoking: "current", keeps_smoking: false, activity_minutes: 60, height_cm: 178, weight_kg: 92, drinks_per_week: 8, fruit_veg_per_day: 2 }, marital: "married" },
  young: { answers: { sex: "F", age: 22, region: "BC", smoking: "never", activity_minutes: 300, height_cm: 165, weight_kg: 60, drinks_per_week: 2, fruit_veg_per_day: 5 }, marital: "never" },
  retired: { answers: { sex: "M", age: 67, region: "QC", smoking: "former", quit_age: 50, activity_minutes: 90, height_cm: 175, weight_kg: 84, drinks_per_week: 10, fruit_veg_per_day: 3 }, marital: "married" },
};
function who(a) {
  const smoke = a.smoking === "never" ? "who has never smoked" : a.smoking === "former" ? `who quit smoking at ${a.quit_age}`
    : a.keeps_smoking ? "who smokes and expects to keep smoking" : "who smokes";
  return `a ${a.age}-year-old ${a.sex === "F" ? "woman" : "man"} in ${placeName(a.region)} ${smoke}`;
}

// ------------------------------------------------------------ small helpers

function fitCanvas(canvas) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = canvas.clientWidth, h = canvas.clientHeight;
  canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h };
}
function seeded(seed) {
  let s = seed >>> 0;
  return () => { s = (s + 0x6d2b79f5) >>> 0; let t = Math.imul(s ^ (s >>> 15), s | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
function survival(ex) {                                  // S at the start of each year of age
  const S = []; let left = 1;
  for (const d of ex.die) { S.push(left); left -= d; }
  return S;
}
function quantile(ex, q) {
  let total = 0;
  for (let i = 0; i < ex.ages.length; i++) {
    if (total + ex.die[i] >= q) return ex.ages[i] + (q - total) / ex.die[i];
    total += ex.die[i];
  }
  return ex.ages[ex.ages.length - 1] + 1;
}
function sampleMedian(ages) {                            // median of draws and its 95% interval from order statistics
  const s = [...ages].sort((a, b) => a - b), n = s.length, at = (k) => s[Math.min(Math.max(Math.round(k), 0), n - 1)];
  return { m: at(n / 2), lo: at(n / 2 - 0.98 * Math.sqrt(n)), hi: at(n / 2 + 0.98 * Math.sqrt(n)) };
}
const whole = Math.floor;
const pct = (x) => (x > 0 && x < 0.005 ? "under 1%" : `${Math.round(x * 100)}%`);
const fmt = (n) => n.toLocaleString("en-CA");
const capital = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"];
function star(ctx, x, y, r, alpha, colour) { ctx.globalAlpha = alpha; ctx.fillStyle = colour; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); }
function glint(ctx, x, y, len, alpha, colour) {
  ctx.globalAlpha = alpha; ctx.strokeStyle = colour; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(x - len, y); ctx.lineTo(x + len, y); ctx.moveTo(x, y - len); ctx.lineTo(x, y + len); ctx.stroke();
}
function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v; else if (k === "html") n.innerHTML = v;
    else if (v === true) n.setAttribute(k, ""); else if (v !== false && v != null) n.setAttribute(k, v);
  }
  for (const c of kids) if (c != null) n.append(c);
  return n;
}
async function swap(from, to) {                           // one act leaves, the next arrives
  if (from && !from.hidden) { from.classList.add("leaving"); await wait(220); from.hidden = true; from.classList.remove("leaving"); }
  to.hidden = false; to.classList.remove("entering"); void to.offsetWidth; to.classList.add("entering");
}

// ------------------------------------------------------------ 1. the sky that never stops

const sky = { canvas: $("#sky-canvas"), lives: [], queue: [], deaths: [], seed: 101, paused: false, startAge: EXAMPLE.age, asking: false };
const YEAR_MS = 55;

function topUp() {
  if (sky.asking || sky.queue.length > 400) return;
  sky.asking = true;
  ask({ type: "batch", answers: EXAMPLE, n: 600, seed: sky.seed++ }).then((r) => { sky.queue.push(...r.lives); sky.startAge = r.startAge; sky.asking = false; })
    .catch(() => { sky.asking = false; });
}
function avoidBox() {
  const c = $(".stagebox").getBoundingClientRect(), s = sky.canvas.getBoundingClientRect();
  return { x0: c.left - s.left - 20, x1: Math.min(c.left - s.left + 760, c.right - s.left) + 20, y0: c.top - s.top - 20, y1: c.bottom - s.top + 10 };
}
function spawn(now, w, h, box, random) {
  const life = sky.queue.shift();
  if (!life) return;
  let x, y, tries = 0;
  do { x = random() * w; y = 60 + random() * (h - 130); tries++; } while (tries < 6 && x > box.x0 && x < box.x1 && y > box.y0 && y < box.y1);
  sky.lives.push({ x, y, born: now, span: Math.max(life.age - sky.startAge, 0.3) * YEAR_MS,
    events: life.events.map((a) => now + (a - sky.startAge) * YEAR_MS), r: 0.8 + random() * 1.1, phase: random() * 6.28 });
  if (sky.deaths.length < 200000) sky.deaths.push(life.age);
}
function tallyText() {
  const n = sky.deaths.length;
  if (n < 30) return "Drawing the first lives…";
  const { m, lo, hi } = sampleMedian(sky.deaths);
  return `Lives read so far: <strong>${fmt(n)}</strong>. Half of them last past <strong>${m.toFixed(1)}</strong>, give or take ${((hi - lo) / 2).toFixed(1)}. The more lives, the steadier that number.`;
}
function runSky() {
  let { ctx, w, h } = fitCanvas(sky.canvas);
  let box = avoidBox();
  const random = seeded(7);
  addEventListener("resize", () => { ({ ctx, w, h } = fitCanvas(sky.canvas)); box = avoidBox(); });
  sky.rebox = () => { box = avoidBox(); };
  let last = performance.now(), carry = 0, lastTally = 0;
  const target = () => Math.min(320, Math.round((w * h) / 4200));
  function frame(now) {
    const dt = Math.min(now - last, 100); last = now;
    if (!sky.paused && !document.hidden) {
      topUp();
      carry += (dt * target()) / (52 * YEAR_MS);
      if (sky.lives.length < target() * 0.6) carry += 3;
      while (carry >= 1) { spawn(now, w, h, box, random); carry -= 1; }
      ctx.globalAlpha = 1; ctx.fillStyle = C.night; ctx.fillRect(0, 0, w, h);
      sky.lives = sky.lives.filter((s) => now < s.born + s.span + 900);
      for (const s of sky.lives) {
        const age = now - s.born;
        let a = Math.min(age / 300, 1) * (0.55 + 0.3 * Math.sin(now / 700 + s.phase)), r = s.r;
        if (age > s.span) { const f = (age - s.span) / 900; a *= 1 - f; r *= 1 - 0.5 * f; }
        star(ctx, s.x, s.y, r, a, C.star);
        for (const t of s.events) {
          const since = now - t;
          if (since > 0 && since < 520) { const f = 1 - since / 520; star(ctx, s.x, s.y, r * 2.2, 0.9 * f, C.star); glint(ctx, s.x, s.y, 7 * f + 2, 0.7 * f, C.star); }
        }
      }
      ctx.globalAlpha = 1;
      if (now - lastTally > 300) { $("#tally-text").innerHTML = tallyText(); lastTally = now; }
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}
async function stillSky() {
  const { ctx, w, h } = fitCanvas(sky.canvas);
  const random = seeded(7);
  for (let k = 0; k < 8; k++) { const r = await ask({ type: "batch", answers: EXAMPLE, n: 600, seed: sky.seed++ }); sky.deaths.push(...r.lives.map((l) => l.age)); }
  ctx.fillStyle = C.night; ctx.fillRect(0, 0, w, h);
  for (let i = 0; i < 260; i++) star(ctx, random() * w, 60 + random() * (h - 130), 0.8 + random() * 1.1, 0.4 + random() * 0.4, C.star);
  $("#tally-text").innerHTML = tallyText();
  $("#sky-pause").hidden = true;
}
$("#sky-pause").addEventListener("click", (e) => {
  sky.paused = !sky.paused;
  e.currentTarget.setAttribute("aria-pressed", String(sky.paused));
  e.currentTarget.textContent = sky.paused ? "Play" : "Pause";
});

// ------------------------------------------------------------ 2. the consultation

const ans = { units: "metric" };
const SURVEY = ans;
const placed = new Array(9).fill(null);                 // where each answer puts its star (0 top, 1 bottom)
let qStep = 0, lastPlaced = -1;

function starValue(k, src = null) {
  const ans = src || SURVEY;                             // the survey's answers, or a sample person's
  const bmi = ans.weight_kg && ans.height_cm ? ans.weight_kg / (ans.height_cm / 100) ** 2 : 25;
  const v = [
    ans.sex === "F" ? 0.3 : 0.7,
    (ans.age - 18) / 91,
    ans.region === "CA" ? 0.5 : (PROVINCES.findIndex(([c]) => c === ans.region) + 0.5) / 10,
    { never: 0.2, former: 0.5, current: 0.85 }[ans.smoking],
    1 - Math.min(ans.activity_minutes, 600) / 600,
    (bmi - 15) / 25,
    Math.min(ans.drinks_per_week, 30) / 30,
    1 - Math.min(ans.fruit_veg_per_day, 8) / 8,
    { never: 0.3, married: 0.6, divorced: 0.85 }[ans.marital],
  ][k];
  return Math.min(Math.max(v ?? 0.5, 0.04), 0.96);
}
function drawConstellation() {
  const svg = $("#constellation");
  const x = (k) => 50 + k * 100, y = (v) => 14 + v * 92;
  let html = "";
  for (let k = 0; k < 9; k++) if (placed[k] === null) html += `<circle class="c-slot" cx="${x(k)}" cy="60" r="4"/>`;
  for (let k = 1; k < 9; k++) if (placed[k] !== null && placed[k - 1] !== null)
    html += `<line class="c-line${k === lastPlaced ? " new" : ""}" x1="${x(k - 1)}" y1="${y(placed[k - 1])}" x2="${x(k)}" y2="${y(placed[k])}"/>`;
  for (let k = 0; k < 9; k++) if (placed[k] !== null) {
    const cx = x(k), cy = y(placed[k]), r = 5;
    html += `<path class="c-star${k === lastPlaced ? " new" : ""}" d="M${cx} ${cy - r * 2}L${cx + r * 0.45} ${cy - r * 0.45}L${cx + r * 2} ${cy}L${cx + r * 0.45} ${cy + r * 0.45}L${cx} ${cy + r * 2}L${cx - r * 0.45} ${cy + r * 0.45}L${cx - r * 2} ${cy}L${cx - r * 0.45} ${cy - r * 0.45}Z"/>`;
  }
  svg.innerHTML = html;
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
function numberField({ id, label, unit, value, min, max, step = 1, check, onInput }) {
  const input = el("input", { type: "number", id, inputmode: step < 1 ? "decimal" : "numeric", min, max, step, value: value ?? "" });
  const msg = el("p", { class: "msg", id: `${id}-msg`, "aria-live": "polite" });
  input.setAttribute("aria-describedby", `${id}-msg`);
  const field = el("div", { class: "field" }, el("label", { for: id }, label), el("div", { class: "input-wrap" }, input, unit ? el("span", { class: "unit" }, unit) : null), msg);
  const run = (show) => {
    const raw = input.value.trim(), v = raw === "" ? null : Number(raw);
    const problem = v === null ? "Enter a number." : check(v);
    field.classList.toggle("valid", show && !problem);
    field.classList.toggle("invalid", show && !!problem);
    msg.textContent = show ? (problem || "") : "";
    onInput(problem ? null : v);
  };
  input.addEventListener("input", () => run(true));
  field.validate = () => run(true);
  field.quiet = () => run(false);
  field.input = input;
  return field;
}

const QUESTIONS = [
  { title: "Which life table should we read you from?", help: "Canada’s life tables are kept for men and women separately; this chooses your starting death rates.",
    render(body, done) { body.append(choice("sex", [["F", "Female"], ["M", "Male"]], ans.sex, (v) => { ans.sex = v; done(true); }, true)); done(!!ans.sex); } },
  { title: "How old are you?", help: "In whole years. The tables begin at 18.",
    render(body, done) {
      const f = numberField({ id: "age", label: "Age", unit: "years", value: ans.age, min: 18, max: 109,
        check: (v) => (!Number.isInteger(v) ? "Use whole years." : v < 18 ? "The tables begin at 18." : v > 109 ? "The tables run to 109." : null),
        onInput: (v) => { ans.age = v; done(v !== null); } });
      body.append(f); ans.age != null ? f.validate() : f.quiet();
    } },
  { title: "Where do you live?", help: "Death rates differ by province. The territories are not in the data yet; choose Canada as a whole if you live there.",
    render(body, done) {
      const sel = el("select", { id: "region" }, el("option", { value: "" }, "Choose a province"), el("option", { value: "CA" }, "Canada as a whole"),
        ...PROVINCES.map(([c, n]) => el("option", { value: c }, n)));
      sel.value = ans.region || "";
      sel.addEventListener("change", () => { ans.region = sel.value || null; done(!!sel.value); });
      body.append(el("div", { class: "field" }, el("label", { for: "region" }, "Province"), sel)); done(!!ans.region);
    } },
  { title: "Do you smoke?", help: "Cigarettes, daily or now and then.",
    render(body, done) {
      const follow = el("div");
      const update = () => {
        follow.replaceChildren();
        if (ans.smoking === "former") {
          const f = numberField({ id: "quit", label: "How old were you when you quit?", unit: "years", value: ans.quit_age, min: 10, max: ans.age,
            check: (v) => (!Number.isInteger(v) ? "Use whole years." : v < 10 ? "Enter an age of 10 or more." : v > ans.age ? `That is older than you are now (${ans.age}).` : null),
            onInput: (v) => { ans.quit_age = v; done(v !== null); } });
          follow.append(el("div", { class: "follow" }, f)); ans.quit_age != null ? f.validate() : (f.quiet(), done(false));
        } else if (ans.smoking === "current") {
          follow.append(el("div", { class: "follow" }, el("p", { class: "q-help" }, "Most Canadian smokers quit at some point. Should your lives allow for that?"),
            choice("keeps", [["false", "Yes, I may well quit", "About 5 in 100 smokers quit for good each year from 25."], ["true", "No, assume I keep smoking", "Shows what smoking for life does."]],
              ans.keeps_smoking == null ? null : String(ans.keeps_smoking), (v) => { ans.keeps_smoking = v === "true"; done(true); })));
          done(ans.keeps_smoking != null);
        } else done(ans.smoking === "never");
      };
      body.append(choice("smoking", [["never", "I have never smoked"], ["former", "I used to smoke"], ["current", "I smoke now"]], ans.smoking,
        (v) => { ans.smoking = v; if (v !== "former") ans.quit_age = null; if (v !== "current") ans.keeps_smoking = null; update(); }), follow);
      update();
    } },
  { title: "How active are you in a usual week?", help: "Minutes of spare-time activity that leaves you breathing harder: brisk walking, cycling, swimming, sport.",
    render(body, done) {
      const f = numberField({ id: "activity", label: "Minutes a week", unit: "minutes", value: ans.activity_minutes, min: 0, max: 3000, step: 5,
        check: (v) => (v < 0 ? "Minutes cannot be negative." : v > 3000 ? "Enter up to 3,000." : null),
        onInput: (v) => { ans.activity_minutes = v; done(v !== null); } });
      const chips = el("div", { class: "chips", role: "group", "aria-label": "Common answers" },
        ...[[0, "None"], [60, "An hour"], [150, "2½ hours"], [300, "5 hours"]].map(([m, label]) => {
          const b = el("button", { type: "button", class: "chip", "aria-pressed": String(ans.activity_minutes === m) }, label);
          b.addEventListener("click", () => { f.input.value = m; f.validate(); chips.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", String(c === b))); });
          return b;
        }));
      body.append(f, chips); ans.activity_minutes != null ? f.validate() : f.quiet();
    } },
  { title: "How tall are you, and how much do you weigh?", help: "For your body-mass index.",
    render(body, done) {
      const holder = el("div");
      const draw = () => {
        holder.replaceChildren();
        const metric = ans.units === "metric", st = { h: null, w: null };
        const check = () => {
          const msg = holder.querySelector(".bmi");
          if (st.h == null || st.w == null) { msg.textContent = ""; return done(false); }
          const bmi = st.w / (st.h / 100) ** 2;
          if (bmi < 12 || bmi > 80) { msg.textContent = "Together these are outside what the studies cover; check them."; msg.style.color = "var(--bad)"; return done(false); }
          msg.textContent = `Body-mass index ${bmi.toFixed(1)}.`; msg.style.color = "var(--good)";
          ans.height_cm = st.h; ans.weight_kg = st.w; done(true);
        };
        let fields;
        if (metric) fields = [
          numberField({ id: "h", label: "Height", unit: "cm", value: ans.height_cm != null ? Math.round(ans.height_cm) : null, min: 120, max: 230,
            check: (v) => (v < 120 || v > 230 ? "Enter 120 to 230 cm." : null), onInput: (v) => { st.h = v; check(); } }),
          numberField({ id: "w", label: "Weight", unit: "kg", value: ans.weight_kg != null ? Math.round(ans.weight_kg) : null, min: 30, max: 300,
            check: (v) => (v < 30 || v > 300 ? "Enter 30 to 300 kg." : null), onInput: (v) => { st.w = v; check(); } })];
        else {
          const inches = ans.height_cm != null ? ans.height_cm / 2.54 : null;
          const imp = { ft: inches != null ? Math.floor(inches / 12) : null, inch: inches != null ? Math.round(inches % 12) : null };
          const setH = () => { st.h = imp.ft != null && imp.inch != null ? (imp.ft * 12 + imp.inch) * 2.54 : null; if (st.h != null && (st.h < 120 || st.h > 230)) st.h = null; check(); };
          fields = [
            numberField({ id: "ft", label: "Feet", unit: "ft", value: imp.ft, min: 3, max: 7, check: (v) => (!Number.isInteger(v) || v < 3 || v > 7 ? "3 to 7." : null), onInput: (v) => { imp.ft = v; setH(); } }),
            numberField({ id: "in", label: "Inches", unit: "in", value: imp.inch, min: 0, max: 11, check: (v) => (v < 0 || v >= 12 ? "0 to 11." : null), onInput: (v) => { imp.inch = v; setH(); } }),
            numberField({ id: "lb", label: "Weight", unit: "lb", value: ans.weight_kg != null ? Math.round(ans.weight_kg / 0.45359237) : null, min: 66, max: 660,
              check: (v) => (v < 66 || v > 660 ? "66 to 660 lb." : null), onInput: (v) => { st.w = v == null ? null : v * 0.45359237; check(); } })];
        }
        holder.append(el("div", { class: "pair" }, ...fields), el("p", { class: "msg bmi", "aria-live": "polite" }));
        fields.forEach((f) => (f.input.value ? f.validate() : f.quiet()));
      };
      const units = el("div", { class: "chips", role: "group", "aria-label": "Units" },
        ...[["metric", "Centimetres and kilograms"], ["imperial", "Feet, inches and pounds"]].map(([u, label]) => {
          const b = el("button", { type: "button", class: "chip", "aria-pressed": String(ans.units === u) }, label);
          b.addEventListener("click", () => { ans.units = u; units.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", String(c === b))); draw(); });
          return b;
        }));
      units.style.marginBottom = "1rem";
      body.append(units, holder); draw();
    } },
  { title: "How many drinks do you have in a usual week?", help: "One drink is a 341 ml bottle of 5% beer, a 142 ml glass of 12% wine, or a 43 ml shot of 40% spirits.",
    render(body, done) {
      const f = numberField({ id: "drinks", label: "Drinks a week", unit: "drinks", value: ans.drinks_per_week, min: 0, max: 150, step: 0.5,
        check: (v) => (v < 0 ? "Drinks cannot be negative." : v > 150 ? "Enter up to 150." : null), onInput: (v) => { ans.drinks_per_week = v; done(v !== null); } });
      body.append(f); ans.drinks_per_week != null ? f.validate() : f.quiet();
    } },
  { title: "How many servings of fruit and vegetables do you eat a day?", help: "A serving is about one medium fruit or half a cup of vegetables.",
    render(body, done) {
      const f = numberField({ id: "fv", label: "Servings a day", unit: "servings", value: ans.fruit_veg_per_day, min: 0, max: 20, step: 0.5,
        check: (v) => (v < 0 ? "Servings cannot be negative." : v > 20 ? "Enter up to 20." : null), onInput: (v) => { ans.fruit_veg_per_day = v; done(v !== null); } });
      body.append(f); ans.fruit_veg_per_day != null ? f.validate() : f.quiet();
    } },
  { title: "Are you married?", help: "The data cover legal marriage, so living common-law counts as not married.",
    render(body, done) {
      body.append(choice("marital", [["never", "I have never been married"], ["married", "I am married"], ["divorced", "I am divorced, separated or widowed"]], ans.marital,
        (v) => { ans.marital = v; done(true); }));
      done(!!ans.marital);
    } },
];

function showQuestion(entering = true) {
  const q = QUESTIONS[qStep], body = $("#q-body"), next = $("#q-next");
  const fs = el("fieldset", {}, el("legend", { class: "q-title", id: "q-title" }, q.title), el("p", { class: "q-help" }, q.help));
  body.replaceChildren(fs);
  q.render(fs, (ok) => { next.disabled = !ok; });
  $("#q-count").innerHTML = `Question <i>${ROMAN[qStep]}</i> of IX`;
  $("#q-back").style.visibility = qStep === 0 ? "hidden" : "visible";
  next.querySelector(".label").textContent = qStep === 8 ? "Cast my 1,000 lives" : "Continue";
  if (entering) { body.classList.remove("leaving", "entering"); void body.offsetWidth; body.classList.add("entering"); }
  const first = fs.querySelector("input:not([type=radio]), select") || fs.querySelector("input:checked") || fs.querySelector("input");
  if (first) first.focus({ preventScroll: true });
  drawConstellation();
}
async function moveQuestion(delta) {
  const body = $("#q-body");
  body.classList.remove("entering"); body.classList.add("leaving");
  await wait(180);
  body.classList.remove("leaving");
  qStep += delta; showQuestion();
}
function engineAnswers() {
  return { sex: ans.sex, age: ans.age, region: ans.region, smoking: ans.smoking,
    quit_age: ans.smoking === "former" ? ans.quit_age : null, keeps_smoking: ans.smoking === "current" ? !!ans.keeps_smoking : false,
    activity_minutes: ans.activity_minutes, height_cm: ans.height_cm, weight_kg: ans.weight_kg,
    drinks_per_week: ans.drinks_per_week, fruit_veg_per_day: ans.fruit_veg_per_day };
}

$("#begin").addEventListener("click", async () => { qStep = 0; await swap($("#intro"), $("#consult")); showQuestion(false); sky.rebox && sky.rebox(); });
$("#q-back").addEventListener("click", () => { if (qStep > 0) moveQuestion(-1); });
$("#q-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if ($("#q-next").disabled) return;
  placed[qStep] = starValue(qStep); lastPlaced = qStep;
  if (qStep < 8) { drawConstellation(); moveQuestion(1); return; }
  drawConstellation();
  await cast({ answers: engineAnswers(), marital: ans.marital }, $("#q-next"));
});
document.querySelectorAll("[data-sample]").forEach((b) => b.addEventListener("click", () => cast(SAMPLES[b.dataset.sample], b)));

// ------------------------------------------------------------ 3. the casting

const EVENT_WORDS = {
  first_child: "a child is born", first_marriage: "you marry", divorce: "you divorce", remarriage: "you marry again",
  retire: "you start your CPP pension", disability_to_retirement: "your disability pension becomes a retirement pension",
  cancer_lung: "you are told you have lung cancer", cancer_other: "you are told you have cancer",
  heart_attack: "you have a heart attack", stroke: "you have a stroke", crash_injury: "you are hurt in a car crash",
  disability_start: "illness or injury stops you working", disability_end: "you recover and leave disability",
};
const castState = { canvas: $("#cast-canvas"), paused: false, done: false, t: 0, raf: 0 };
let current = null;

async function cast(person, button) {
  const label = button.querySelector?.(".label");
  const before = label ? label.textContent : button.textContent;
  button.setAttribute("aria-busy", "true"); button.disabled = true;
  if (label) label.textContent = "Casting";
  try {
    const r = await ask({ type: "reading", answers: person.answers, startMarital: person.marital, n: 1000, seed: Math.floor(Math.random() * 2 ** 31) });
    person = { ...person, who: who(person.answers),
      stars: Array.from({ length: 9 }, (_, k) => starValue(k, { ...person.answers, marital: person.marital })) };
    current = { person, r };
    $("#reading").hidden = true;
    startCasting(person, r);
  } catch (err) {
    if (label) label.textContent = `Could not cast: ${err.message}`;
    return;
  } finally {
    button.removeAttribute("aria-busy"); button.disabled = false;
  }
  if (label) label.textContent = before;
}

function startCasting(person, result) {
  const section = $("#casting");
  section.hidden = false;
  $("#casting-who").textContent = `For ${person.who}. Each light is one of your lives; when a life ends, it falls into place below.`;
  $("#to-cards").hidden = true;
  section.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
  cancelAnimationFrame(castState.raf);
  const cs = castState;
  const lives = result.lives, startAge = person.answers.age, startYear = result.exact.startYear;
  const span = 111 - startAge, TOTAL_MS = 16000;
  let geo = null;

  function layout() {
    const { ctx, w, h } = fitCanvas(cs.canvas);
    const L = Math.max(20, w * 0.05), R = w - L;
    const skyTop = 8, skyBot = h * 0.56, chartTop = h * 0.64, chartBot = h - 28;
    const cols = Math.round(Math.sqrt((1000 * (R - L)) / (skyBot - skyTop))), rows = Math.ceil(1000 / cols);
    const cw = (R - L) / cols, rh = (skyBot - skyTop) / rows, jitter = seeded(5);
    const pos = lives.map((_, i) => ({ x: L + ((i % cols) + 0.2 + jitter() * 0.6) * cw, y: skyTop + (Math.floor(i / cols) + 0.2 + jitter() * 0.6) * rh }));
    const colW = (R - L) / span, counts = new Map(), slot = new Array(lives.length);
    for (const [age, i] of lives.map((l, i) => [l.age, i]).sort((a, b) => a[0] - b[0])) {
      const c = Math.min(Math.floor(age), 110), k = counts.get(c) || 0; counts.set(c, k + 1); slot[i] = [c, k];
    }
    const step = Math.min(colW, (chartBot - chartTop) / Math.max(...counts.values()));
    geo = { ctx, w, h, L, R, chartTop, chartBot, colW, pos, dot: Math.max(1.1, step * 0.42),
      land: slot.map(([c, k]) => ({ x: L + (c - startAge + 0.5) * colW, y: chartBot - (k + 0.5) * step })) };
  }
  layout();
  if (cs.onResize) removeEventListener("resize", cs.onResize);
  cs.onResize = () => { layout(); if (cs.done) draw(performance.now()); };
  addEventListener("resize", cs.onResize);

  const byYear = new Map();
  lives.forEach((l) => l.events.forEach(([age, , e]) => { const m = byYear.get(age) || {}; m[e] = (m[e] || 0) + 1; byYear.set(age, m); }));
  const tick = (age) => {
    const m = byYear.get(age); if (!m) return "";
    const [e, n] = Object.entries(m).sort((a, b) => b[1] - a[1])[0];
    return n < 3 ? "" : `This year, in ${n} of your lives, ${EVENT_WORDS[e] || e}.`;
  };
  const median = quantile(result.exact, 0.5);
  cs.t = startAge; cs.done = false; cs.paused = false; cs.instant = false;
  $("#cast-pause").textContent = "Pause"; $("#cast-pause").setAttribute("aria-pressed", "false"); $("#cast-pause").hidden = false; $("#cast-skip").hidden = false;
  let last = performance.now(), shownYear = -1, doneStamp = null;

  function draw(now) {
    const { ctx, w, h, L, R, chartBot, colW, pos, land, dot } = geo;
    ctx.globalAlpha = 1; ctx.fillStyle = C.night; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = C.rule; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(L, chartBot + 0.5); ctx.lineTo(R, chartBot + 0.5); ctx.stroke();
    ctx.fillStyle = C.dim; ctx.font = `${w < 640 ? 11 : 13}px Lora, Georgia, serif`; ctx.textAlign = "center";
    for (let a = Math.ceil((startAge + 5) / 10) * 10; a <= 110; a += w < 640 ? 20 : 10) ctx.fillText(String(a), L + (a - startAge + 0.5) * colW, chartBot + 18);
    ctx.textAlign = "left"; ctx.fillText(`age ${startAge}`, L, chartBot + 18);
    const t = cs.t, yearsPerMs = span / TOTAL_MS, flare = (0.6 * span) / 16;
    lives.forEach((life, i) => {
      const p = pos[i];
      if (t < life.age) {
        let a = 0.55 + 0.25 * Math.sin(now / 650 + i);
        for (const [age] of life.events) {
          const since = t - age;
          if (since >= 0 && since < flare) { const f = 1 - since / flare; star(ctx, p.x, p.y, 3, f, C.ochre); glint(ctx, p.x, p.y, 6 * f + 2, 0.8 * f, C.ochre); a = Math.max(a, f); }
        }
        star(ctx, p.x, p.y, 1.25, a, C.star);
      } else {
        const since = (t - life.age) / (yearsPerMs * 700), dst = land[i];
        if (since < 1 && !cs.instant) {
          const e = since < 0.5 ? 2 * since * since : 1 - (-2 * since + 2) ** 2 / 2;
          star(ctx, p.x + (dst.x - p.x) * e, p.y + (dst.y - p.y) * e, 1.4, 0.9, C.star);
        } else {
          const fresh = since < 2.2 && !cs.instant;
          star(ctx, dst.x, dst.y, dot, fresh ? 1 : 0.82, fresh ? C.ochre : C.star);
        }
      }
    });
    if (cs.done) {
      const x = L + (median - startAge) * colW, right = x > w - 160;
      ctx.globalAlpha = 1; ctx.strokeStyle = C.ochre; ctx.setLineDash([3, 4]);
      ctx.beginPath(); ctx.moveTo(x, geo.chartTop - 8); ctx.lineTo(x, chartBot); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = C.ochre; ctx.textAlign = right ? "right" : "left";
      ctx.fillText(`half last past ${whole(median)}`, x + (right ? -8 : 8), geo.chartTop - 10);
    }
    ctx.globalAlpha = 1;
  }
  function updateText() {
    const age = Math.min(Math.floor(cs.t), 110);
    if (age === shownYear) return;
    shownYear = age;
    if (cs.done) {
      $("#clock").innerHTML = `All 1,000 lives are cast. Half of them last past <strong>${whole(median)}</strong>.`;
      $("#ticker").textContent = "The cards are ready.";
    } else {
      $("#clock").innerHTML = `${startYear + age - startAge}. Age ${age}. <strong>${fmt(lives.filter((l) => l.age > cs.t).length)}</strong> of your lives still going.`;
      const line = tick(age); if (line) $("#ticker").textContent = line;
    }
  }
  function finish() {
    cs.done = true; cs.t = 111;
    $("#cast-pause").hidden = true; $("#cast-skip").hidden = true; $("#to-cards").hidden = false;
    shownYear = -1; updateText();
  }
  function frame(now) {
    const dt = Math.min(now - last, 80); last = now;
    if (!cs.paused && !cs.done) { cs.t += (dt / TOTAL_MS) * span; if (cs.t >= 111 + span * 0.05) finish(); }
    draw(now); updateText();
    if (cs.done && doneStamp === null) doneStamp = now;
    if (!cs.done || now - doneStamp < 3000) cs.raf = requestAnimationFrame(frame);
  }
  cs.skip = () => { cs.instant = true; finish(); draw(performance.now()); };
  if (reduceMotion) cs.skip(); else cs.raf = requestAnimationFrame(frame);
}
$("#cast-pause").addEventListener("click", (e) => {
  castState.paused = !castState.paused;
  e.currentTarget.setAttribute("aria-pressed", String(castState.paused));
  e.currentTarget.textContent = castState.paused ? "Play" : "Pause";
});
$("#cast-skip").addEventListener("click", () => castState.skip && castState.skip());

// ------------------------------------------------------------ 4. the five cards

const GROUPS = [
  { label: "cancer", causes: ["lung_cancer", "other_cancer"] },
  { label: "heart disease or stroke", causes: ["heart", "stroke"] },
  { label: "an accident or injury", causes: ["motor_vehicle", "other_accidents", "other_injury"] },
  { label: "dementia", causes: ["dementia"] },
  { label: "lung disease (COPD)", causes: ["copd"] },
  { label: "diabetes", causes: ["diabetes"] },
];
const OLD_AGE = ["dementia", "other", "stroke", "heart"];
const EMBLEMS = {
  road: `<svg viewBox="0 0 100 70" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M4 66 L46 22 M96 66 L54 22 M2 22 H98"/><path d="M50 66 V60 M50 52 V47 M50 40 V36 M50 31 V28" stroke-width="1.8"/><path d="M50 4 L52 10 L58 12 L52 14 L50 20 L48 14 L42 12 L48 10 Z" fill="currentColor" stroke="none"/></svg>`,
  hourglass: `<svg viewBox="0 0 100 70" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M34 4 H66 M34 66 H66 M38 4 C38 24 62 26 62 35 C62 44 38 46 38 66 M62 4 C62 24 38 26 38 35 C38 44 62 46 62 66"/><path d="M44 60 Q50 52 56 60 Z" fill="currentColor"/><path d="M50 37 V54" stroke-dasharray="1.5 3"/></svg>`,
  rings: `<svg viewBox="0 0 100 70" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="40" cy="38" r="20"/><circle cx="60" cy="38" r="20"/><circle cx="40" cy="38" r="16" stroke-width="0.7"/><circle cx="60" cy="38" r="16" stroke-width="0.7"/><path d="M50 6 L51.3 10 L55 11 L51.3 12 L50 16 L48.7 12 L45 11 L48.7 10 Z" fill="currentColor" stroke="none"/></svg>`,
  eclipse: `<svg viewBox="0 0 100 70" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="50" cy="36" r="24"/><circle cx="58" cy="32" r="22" fill="currentColor" fill-opacity="0.85" stroke="none"/><path d="M50 4 V9 M50 63 V68 M18 36 H23 M77 36 H82 M27 13 L31 17 M69 55 L73 59 M27 59 L31 55" stroke-width="1"/></svg>`,
  lever: `<svg viewBox="0 0 100 70" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M8 50 L92 26"/><path d="M50 38 L40 62 H60 Z"/><path d="M30 64 H70"/><circle cx="16" cy="40" r="6"/><path d="M84 12 L85.3 16 L89 17 L85.3 18 L84 22 L82.7 18 L79 17 L82.7 16 Z" fill="currentColor" stroke="none"/></svg>`,
};
const BACK = (seed) => {
  const r = seeded(seed); let dots = "";
  for (let i = 0; i < 46; i++) dots += `<circle cx="${(r() * 100).toFixed(1)}" cy="${(r() * 166).toFixed(1)}" r="${(0.35 + r() * 0.8).toFixed(2)}" fill="#dde7f0" fill-opacity="${(0.35 + r() * 0.5).toFixed(2)}"/>`;
  return `<svg viewBox="0 0 100 166" preserveAspectRatio="none" aria-hidden="true"><rect x="4" y="4" width="92" height="158" rx="3" fill="none" stroke="#2a3b55"/><rect x="7" y="7" width="86" height="152" rx="2" fill="none" stroke="#2a3b55" stroke-width="0.5"/><circle cx="50" cy="83" r="26" fill="none" stroke="#2a3b55" stroke-width="0.6"/><circle cx="50" cy="83" r="34" fill="none" stroke="#2a3b55" stroke-width="0.4" stroke-dasharray="1 2"/>${dots}</svg>`;
};
const tp = (t, x) => `<sub>${t}</sub><i>p</i><sub>${x}</sub>`;
const qx = (x) => `<i>q</i><sub>${x}</sub>`;

function cardsFor(person, r) {
  const a = person.answers, ex = r.exact, x = a.age;
  const q10 = quantile(ex, 0.1), q50 = quantile(ex, 0.5), q90 = quantile(ex, 0.9);
  const sexWord = a.sex === "M" ? "man" : "woman", place = placeName(a.region), idx = (c) => r.causes.indexOf(c);
  const groups = GROUPS.map((g) => ({ ...g, share: g.causes.reduce((s, c) => s + ex.cause[idx(c)], 0) })).sort((p, q) => q.share - p.share);
  const count = (names) => r.lives.filter((l) => l.events.some(([, , e]) => names.includes(e))).length;
  const se = (k) => (100 * Math.sqrt((k / 1000) * (1 - k / 1000) / 1000)).toFixed(1);

  let companion;
  const kids = count(["first_child"]);
  if (person.marital === "never") { const k = count(["first_marriage"]);
    companion = { figure: pct(k / 1000), says: "of your lives include a marriage.", fine: kids >= 100 ? `A first child is born in ${pct(kids / 1000)} of them.` : "Counted from today onwards.", k }; }
  else if (person.marital === "married") { const k = 1000 - count(["divorce"]);
    companion = { figure: pct(k / 1000), says: "of your lives never see a divorce.", fine: kids >= 100 ? `A first child is born in ${pct(kids / 1000)} of them.` : "The model follows divorce, not widowhood, so this is not the chance of growing old together.", k }; }
  else { const k = count(["remarriage"]); companion = { figure: pct(k / 1000), says: "of your lives include a new marriage.", fine: "Counted from today onwards.", k }; }
  companion.working = `<p>Counted, not computed: <b>${fmt(companion.k)}</b> of your 1,000 lives.</p><p class="eq">s.e. = √(<i>p</i>(1 − <i>p</i>) / 1,000) = ${se(companion.k)} points</p><p>Marriage, divorce, remarriage and a first child follow Statistics Canada rates by age and sex; being married lowers the death rate while it lasts.</p>`;

  const sh = r.ratios.filter((z) => z.person >= 0.02).sort((p, q) => q.ratio - p.ratio)[0];
  const shadow = sh.ratio >= 1.25
    ? { figure: `${sh.ratio.toFixed(1)}×`, says: `${capital(sh.label)} ends ${sh.ratio.toFixed(1)} times as many of your lives as it does for the average ${sexWord} your age in ${place}.`,
        fine: `Yours: ${pct(sh.person)} of lives. The average: ${pct(sh.pop)}.` }
    : { figure: "None", says: "No cause stands out against the average for you.",
        fine: `The largest rise is ${sh.label}, ${sh.ratio.toFixed(1)} times the average${OLD_AGE.includes(sh.cause) && r.median > r.popMedian ? ", mostly because more of your lives reach old age" : ""}.` };
  shadow.working = `<p class="eq">ratio = <i>P</i>(die of <i>c</i> | you) ÷ <i>P</i>(die of <i>c</i> | table)</p><p>${capital(sh.label)}: ${(100 * sh.person).toFixed(1)}% ÷ ${(100 * sh.pop).toFixed(1)}% = <b>${sh.ratio.toFixed(2)}</b>.</p><p>The table: Statistics Canada 2017–2019 rates for ${place} on the same CPP improvement, split by Canada’s cause shares. Causes under 2% of your deaths are left out.</p>`;

  const [top, next] = r.levers;
  let lever;
  if (top && top.gain >= 0.25) lever = { figure: `+${top.gain.toFixed(1)}`, says: `years if you ${top.label}: half of your lives would last past ${whole(top.median)} instead of ${whole(q50)}.`,
    fine: next && next.gain >= 0.25 ? `Next best: ${next.label}, +${next.gain.toFixed(1)} years.` : "None of the other changes tried moves you as much." };
  else if (!top) lever = { figure: "Hold", says: "You already meet every target the model tests.", fine: "No smoking, 5 hours of activity a week, a BMI of 18.5 to 25, under 25 g of alcohol a day, and 5 servings a day." };
  else lever = { figure: "Hold", says: `None of the changes tried moves you by more than a few months. The best is to ${top.label}, +${Math.round(top.gain * 12)} months.`, fine: "Your habits are already doing most of the work." };
  lever.working = `<p>Your mortality multiplier at ${x}: <b>${r.multiplier.toFixed(2)}</b> × the population average${top ? `; if you ${top.label}, <b>${top.multiplier.toFixed(2)}</b>` : ""}.</p><p>Each change is one answer moved to the next level the studies reward, with everything else held, and the median recomputed exactly. ${r.levers.length ? `Tried: ${r.levers.map((l) => `${l.label} (+${l.gain.toFixed(2)})`).join("; ")}.` : "Nothing was left to try."}</p>`;

  const t90 = q90 - x;
  return [
    { num: "I", title: "The Long Road", emblem: "road", figure: String(whole(q90)), says: `1 in 10 of your lives pass ${whole(q90)}.`, fine: `Half pass ${whole(q50)}. 1 in 10 end before ${whole(q10)}.`,
      working: `<p class="eq">${tp("t", x)} = ∏<sub>k&lt;t</sub> (1 − ${qx(`${x}+k`)})</p><p>The Long Road is where ${tp("t", x)} falls to 0.10: <i>t</i> = ${t90.toFixed(1)}, age ${q90.toFixed(1)}. Half your lives are gone where it falls to 0.50, at age ${q50.toFixed(1)}. Deaths are spread evenly within each year of age.</p><p>Complete expectation of life: e̊<sub>${x}</sub> = ${(ex.mean - x).toFixed(1)} years.</p>` },
    { num: "II", title: "The Turning", emblem: "hourglass", figure: pct(groups[0].share), says: `of your lives end with ${groups[0].label}, more than any other cause.`, fine: `Next: ${groups[1].label}, ${pct(groups[1].share)}.`,
      working: `<p class="eq">Σ<sub>t</sub> ${tp("t", x)} · ${qx(`${x}+t`)} · <i>s</i><sup>c</sup><sub>${x}+t</sub></p><p><i>s</i><sup>c</sup> is your share of deaths from cause <i>c</i> at each age, after smoking and the links between events: cancer survival, and the extra risk after a heart attack or stroke. Worked out exactly, state by state, not counted from the draws.</p>` },
    { num: "III", title: "The Companion", emblem: "rings", ...companion },
    { num: "IV", title: "The Shadow", emblem: "eclipse", ...shadow },
    { num: "V", title: "The Lever", emblem: "lever", ...lever },
  ];
}

async function showReading(person, r) {
  const reading = $("#reading");
  $("#reading-title").textContent = `The reading of ${person.who.replace(/-/g, "‑")}`;
  $("#reading-lede").innerHTML = `Half of your lives last past <strong>${whole(quantile(r.exact, 0.5))}</strong>. Each card holds one finding from your 1,000 lives.`;
  const spread = $("#spread");
  spread.replaceChildren(...cardsFor(person, r).map((c, i) => {
    const front = el("div", { class: "face front", html:
      `<div class="top"><h3>${c.title}</h3><span class="num">${c.num}</span></div>
       <div class="emblem" aria-hidden="true">${EMBLEMS[c.emblem]}</div>
       <p class="figure">${c.figure}</p><p class="says">${c.says}</p><p class="fine">${c.fine}</p>
       <div class="working">${c.working}</div>` });
    const toggle = el("button", { type: "button", class: "work-toggle", "aria-expanded": "false" }, "The working");
    toggle.addEventListener("click", () => {
      const open = front.classList.toggle("show-work");
      toggle.textContent = open ? "Back to the card" : "The working";
      toggle.setAttribute("aria-expanded", String(open));
    });
    front.append(toggle);
    const back = el("div", { class: "face back", "aria-hidden": "true", html: BACK(40 + i) + `<span class="numeral">${c.num}</span>` });
    return el("li", { class: "card" }, el("div", { class: "flip" }, back, front));
  }));
  renderTable(person, r);
  renderWords(person, r);
  renderWheel(person, r);
  renderOthers(person, r);
  renderFate(person, r);
  renderShare(person, r);

  reading.hidden = false;
  if (!reduceMotion) { reading.classList.remove("revealed"); reading.classList.add("revealing"); }
  reading.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
  await wait(380);
  reading.classList.remove("revealing"); void reading.offsetWidth; reading.classList.add("revealed");
  const cards = [...spread.children];
  if (reduceMotion) cards.forEach((c) => c.classList.add("turned"));
  else cards.forEach((c, i) => setTimeout(() => c.classList.add("turned"), 700 + i * 420));
  observeRises();
}

// ------------------------------------------------------------ 5. the actuary's table

function renderTable(person, r) {
  const ex = r.exact, x0 = person.answers.age, S = survival(ex);
  const qYou = ex.die.map((d, i) => (S[i] > 0 ? d / S[i] : 1));
  const ages = [x0];
  for (let a = Math.ceil((x0 + 1) / 5) * 5; a <= 105; a += 5) ages.push(a);
  const rows = ages.filter((a) => a === x0 || S[a - x0] * 1000 >= 0.5).map((a) => {
    const i = a - x0, drawn = r.lives.filter((l) => l.age >= a).length;
    return `<tr><td>${a}</td><td>${(1000 * S[i]).toFixed(1)}</td><td>${fmt(drawn)}</td><td class="you">${qYou[i].toFixed(5)}</td><td>${r.qPop[i].toFixed(5)}</td><td>${Math.round((100 * qYou[i]) / r.qPop[i])}%</td></tr>`;
  });
  $("#life-table tbody").innerHTML = rows.join("");
  drawQChart(x0, qYou, r.qPop);

  const startRatio = qYou[0] / r.qPop[0];
  const { m, lo, hi } = sampleMedian(r.lives.map((l) => l.age));
  const exactMedian = quantile(ex, 0.5);
  $("#actuary-notes").innerHTML = `
    <div><h4>Select, then ultimate</h4><p>Your risk multiplier today is <strong>${r.multiplier.toFixed(2)}</strong> × the population average; your actual death rate at ${x0} is <strong>${startRatio.toFixed(2)}</strong> × the table. You start ${person.marital === "married" ? "married and " : ""}free of cancer, heart attack and stroke; the multiplier averages over everyone of your type, including those already ill. The gap narrows with age, much as select mortality runs into ultimate.</p></div>
    <div><h4>Monte Carlo error</h4><p>Your 1,000 draws give a median of <strong>${m.toFixed(1)}</strong>; the exact answer is <strong>${exactMedian.toFixed(1)}</strong>. With 1,000 lives the drawn median is good to about ±${((hi - lo) / 2).toFixed(1)} years (95%). Every card except The Companion uses the exact figures.</p></div>
    <div><h4>Basis</h4><p>Statistics Canada 2017–2019 life tables by province; improvement from the 32nd CPP Actuarial Report; risk factors as proportional hazards on the force of mortality, capped at 0.35 to 5 and tapering after 79; cause shares from Statistics Canada deaths. Every assumption has a number and a source in the repository.</p></div>`;
}

function drawQChart(x0, qYou, qPop) {
  const W = 560, H = 360, L = 74, R = 540, T = 16, B = 320;
  const xs = (a) => L + ((a - x0) / (110 - x0)) * (R - L);
  const lo = -4, hi = 0;                                  // log10 from 1 in 10,000 to 1
  const ys = (q) => B - ((Math.log10(Math.max(q, 1e-4)) - lo) / (hi - lo)) * (B - T);
  const path = (arr) => arr.map((q, i) => `${i ? "L" : "M"}${xs(x0 + i).toFixed(1)} ${ys(Math.min(q, 1)).toFixed(1)}`).join("");
  let g = "";
  [[1e-4, "1 in 10,000"], [1e-3, "1 in 1,000"], [1e-2, "1 in 100"], [1e-1, "1 in 10"], [1, "certain"]].forEach(([q, label]) => {
    g += `<line x1="${L}" x2="${R}" y1="${ys(q)}" y2="${ys(q)}" stroke="#d8ccb3" stroke-dasharray="${q === 1e-4 ? "" : "2 4"}"/><text x="${L - 8}" y="${ys(q) + 4}" text-anchor="end">${label}</text>`;
  });
  for (let a = Math.ceil((x0 + 5) / 10) * 10; a <= 110; a += 10) g += `<text x="${xs(a)}" y="${B + 22}" text-anchor="middle">${a}</text>`;
  g += `<text x="${L}" y="${B + 22}" text-anchor="start">${x0}</text>`;
  g += `<path d="${path(qPop.slice(0, -1))}" fill="none" stroke="#4f5665" stroke-width="1.5" stroke-dasharray="5 4"/>`;
  g += `<path d="${path(qYou.slice(0, -1))}" fill="none" stroke="#8b4d1c" stroke-width="2.2"/>`;
  // label both lines where they are furthest apart, each on its own side
  let iL = 0, gap = 0;
  for (let i = 0; i < Math.min(qYou.length - 1, 95 - x0); i++) { const d = Math.abs(Math.log(qYou[i] / qPop[i])); if (d > gap) { gap = d; iL = i; } }
  const youAbove = qYou[iL] > qPop[iL], lx = Math.min(xs(x0 + iL) + 4, R - 60);
  g += `<text x="${lx}" y="${ys(qYou[iL]) + (youAbove ? -12 : 22)}" style="fill:#8b4d1c;font-weight:600">yours</text>`;
  g += `<text x="${lx}" y="${ys(qPop[iL]) + (youAbove ? 22 : -12)}" style="fill:#4f5665">table</text>`;
  g += `<line id="q-cross" x1="0" x2="0" y1="${T}" y2="${B}" stroke="#1f2531" stroke-width="1" visibility="hidden"/><text id="q-read" x="${R}" y="${T + 4}" text-anchor="end" style="fill:#1f2531"></text>`;
  g += `<rect id="q-hit" x="${L}" y="${T}" width="${R - L}" height="${B - T}" fill="transparent"/>`;
  const box = $("#q-chart");
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Your yearly death rate against the population table, by age, on a log scale">${g}</svg>`;
  const svg = box.querySelector("svg"), cross = svg.querySelector("#q-cross"), read = svg.querySelector("#q-read");
  svg.querySelector("#q-hit").addEventListener("pointermove", (e) => {
    const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    const i = Math.min(Math.max(Math.round(((p.x - L) / (R - L)) * (110 - x0)), 0), qYou.length - 2);
    cross.setAttribute("x1", xs(x0 + i)); cross.setAttribute("x2", xs(x0 + i)); cross.setAttribute("visibility", "visible");
    read.textContent = `age ${x0 + i}: yours ${qYou[i].toFixed(4)}, table ${qPop[i].toFixed(4)}`;
  });
  svg.querySelector("#q-hit").addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); read.textContent = ""; });
}

function observeRises() {
  const targets = document.querySelectorAll(".rise:not(.seen)");
  if (reduceMotion || !("IntersectionObserver" in window)) { targets.forEach((t) => t.classList.add("seen")); return; }
  const io = new IntersectionObserver((entries) => entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("seen"); io.unobserve(en.target); } }), { threshold: 0.12 });
  targets.forEach((t) => io.observe(t));
}

// ------------------------------------------------------------ wiring

$("#to-cards").addEventListener("click", () => current && showReading(current.person, current.r));
$("#again").addEventListener("click", async () => {
  $("#sky").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
  qStep = 0; await swap($("#intro"), $("#consult")); showQuestion(false);
});
ask({ type: "batch", answers: EXAMPLE, n: 600, seed: sky.seed++ }).then((r) => {
  sky.queue.push(...r.lives); sky.startAge = r.startAge;
  $("#begin").disabled = false; $("#begin").querySelector(".label").textContent = "Begin your reading";
  reduceMotion ? stillSky() : runSky();
}).catch((err) => { $("#tally-text").textContent = `The tables could not be loaded (${err.message}). Reload to try again.`; });

// ================================================================ the rest of the reading

function cdf(ex, x) {                                    // share of lives ended by exact age x
  let total = 0;
  for (let i = 0; i < ex.ages.length; i++) {
    const a = ex.ages[i];
    if (x >= a + 1) total += ex.die[i]; else if (x > a) total += ex.die[i] * (x - a);
  }
  return total;
}
const firstEvent = (life, names) => { const e = life.events.find(([, , n]) => names.includes(n)); return e ? e[0] : null; };
const shareWith = (r, names) => r.lives.filter((l) => firstEvent(l, names) !== null).length / r.lives.length;

// ------------------------------------------------------------ the reading, in words (calibrated likelihood words)

function likelihood(p) {
  return p >= 0.9 ? "almost certain" : p >= 0.66 ? "likely" : p >= 0.33 ? "about as likely as not" : p >= 0.1 ? "unlikely" : "rare";
}
const w = (p) => `<span class="w">${likelihood(p)}</span> (${pct(p)})`;

function renderWords(person, r) {
  const a = person.answers, ex = r.exact, x = a.age;
  const M = x < 75 ? 80 : x < 85 ? 90 : Math.ceil((x + 5) / 5) * 5;
  const reach = 1 - cdf(ex, M);
  const idx = (c) => r.causes.indexOf(c);
  const groups = GROUPS.map((g) => ({ ...g, share: g.causes.reduce((s, c) => s + ex.cause[idx(c)], 0) })).sort((p, q) => q.share - p.share);
  const paras = [];
  paras.push(`Reaching ${M} is <span class="w">${likelihood(reach)}</span>: ${pct(reach)} of your lives get there. Half of them last past ${whole(quantile(ex, 0.5))}, and 1 in 10 pass ${whole(quantile(ex, 0.9))}.`);
  let health = `Along the way, a cancer diagnosis is ${w(ex.ever.cancer)}. A heart attack is ${w(ex.ever.heart_attack)}, and a stroke ${w(ex.ever.stroke)}.`;
  if (x < 65) health += ` Being kept from work by serious illness or injury, on CPP disability, is ${w(ex.ever.disability)}.`;
  paras.push(health);
  let life = "";
  if (person.marital === "never") {
    const kids = shareWith(r, ["first_child"]);
    life = `Marriage is ${w(shareWith(r, ["first_marriage"]))}${kids >= 0.1 ? `, and a first child ${w(kids)}` : ""}.`;
  } else if (person.marital === "married") life = `Divorce is ${w(shareWith(r, ["divorce"]))}.`;
  else life = `Marrying again is ${w(shareWith(r, ["remarriage"]))}.`;
  if (x < 60) life += ` Drawing a CPP retirement pension is ${w(shareWith(r, ["retire", "disability_to_retirement"]))}.`;
  paras.push(life);
  const top = r.levers[0];
  const lever = top && top.gain >= 0.25
    ? `Of the habits the model tests, the one that moves you most is to ${top.label}: about ${top.gain.toFixed(1)} more years at the middle.`
    : "None of the habits the model tests would move you by much.";
  paras.push(`When your lives end, it is most often with ${groups[0].label} (${pct(groups[0].share)}). ${lever}`);
  $("#words-text").innerHTML = paras.map((p) => `<p>${p}</p>`).join("");
}

// ------------------------------------------------------------ the life chart

const PLANETS = [
  { key: "marriage", label: "First marriage", names: ["first_marriage"] },
  { key: "child", label: "A first child", names: ["first_child"] },
  { key: "remarriage", label: "Marrying again", names: ["remarriage"] },
  { key: "divorce", label: "Divorce", names: ["divorce"] },
  { key: "crash", label: "Hurt in a car crash", names: ["crash_injury"] },
  { key: "disability", label: "Illness or injury stops work", names: ["disability_start"], exact: "disability" },
  { key: "cancer", label: "A cancer diagnosis", names: ["cancer_lung", "cancer_other"], exact: "cancer" },
  { key: "heart", label: "A heart attack", names: ["heart_attack"], exact: "heart_attack" },
  { key: "stroke", label: "A stroke", names: ["stroke"], exact: "stroke" },
  { key: "retire", label: "A CPP retirement pension", names: ["retire", "disability_to_retirement"] },
];

function renderWheel(person, r) {
  const x0 = person.answers.age, ex = r.exact;
  const S = 640, cx = 320, cy = 320, R = 268;
  const span = 110 - x0;
  const th = (a) => -Math.PI / 2 + 2 * Math.PI * 0.94 * Math.min(Math.max(a - x0, 0), span) / span;
  const pt = (a, rad) => [cx + rad * Math.cos(th(a)), cy + rad * Math.sin(th(a))];
  const arc = (a1, a2, rad) => {
    const [x1, y1] = pt(a1, rad), [x2, y2] = pt(a2, rad);
    const large = th(a2) - th(a1) > Math.PI ? 1 : 0;
    return `M${x1.toFixed(1)} ${y1.toFixed(1)}A${rad} ${rad} 0 ${large} 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`;
  };
  let g = "";
  // the busiest decade of deaths, shaded on the rim
  let best = 0, from = x0;
  for (let a = x0; a + 10 <= 111; a++) { const d = cdf(ex, a + 10) - cdf(ex, a); if (d > best) { best = d; from = a; } }
  g += `<path d="${arc(from, Math.min(from + 10, 110), R - 8)}" fill="none" stroke="#8b4d1c" stroke-opacity="0.16" stroke-width="16"/>`;
  // the 1,000 lives: one dot each, at the angle of the age it ends, scattered across the ring like stars
  for (let a = Math.ceil((x0 + 3) / 10) * 10; a <= 110; a += 10) {
    const [x1, y1] = pt(a, 64), [x2, y2] = pt(a, R - 18);
    g += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#d8ccb3" stroke-dasharray="1 4"/>`;
  }
  const jitter = seeded(110);
  let dots = "";
  r.lives.forEach((l) => {
    const [px, py] = pt(Math.min(l.age, 110.4), 70 + jitter() * 168);
    dots += `<circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="1.7"/>`;
  });
  g += `<g fill="#1f2531" fill-opacity="0.55">${dots}</g>`;
  // the rim and its ages
  g += `<path d="${arc(x0, 110, R)}" fill="none" stroke="#1f2531" stroke-width="1"/>`;
  for (let a = Math.ceil((x0 + 3) / 10) * 10; a <= 110; a += 10) {
    const [x1, y1] = pt(a, R - 4), [x2, y2] = pt(a, R + 4), [tx, ty] = pt(a, R + 22);
    g += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#1f2531"/><text x="${tx}" y="${ty + 4}" text-anchor="middle">${a}</text>`;
  }
  { const [tx, ty] = pt(x0, R + 22); g += `<text x="${tx}" y="${ty + 4}" text-anchor="middle" style="font-style:italic">${x0}, today</text>`; }
  // the middle: half your lives have ended here
  const med = quantile(ex, 0.5);
  { const [x1, y1] = pt(med, 58), [x2, y2] = pt(med, R); g += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#8b4d1c" stroke-width="1.4" stroke-dasharray="3 4"/>`; }
  // the planets: moments your lives share, at the age each is most likely
  const planets = PLANETS.map((p) => {
    const ages = r.lives.map((l) => firstEvent(l, p.names)).filter((a) => a !== null);
    if (ages.length < 50) return null;                  // under 5% of lives: left off the chart
    const counts = new Map(); ages.forEach((a) => counts.set(a, (counts.get(a) || 0) + 1));
    const mode = [...counts.entries()].sort((p1, p2) => p2[1] - p1[1] || p1[0] - p2[0])[0][0];
    return { ...p, share: p.exact ? ex.ever[p.exact] : ages.length / r.lives.length, mode };
  }).filter(Boolean).sort((p, q) => p.mode - q.mode);
  let lastAge = -99, ring = 0;
  planets.forEach((p, i) => {
    ring = p.mode - lastAge < 5 ? (ring + 1) % 3 : 0; lastAge = p.mode;
    p.n = i + 1;
    const [px, py] = pt(p.mode + 0.5, R + 0 - ring * 22);
    g += `<g class="planet" data-n="${p.n}" tabindex="0" role="button" aria-label="${p.label}, most often at ${p.mode}, in ${pct(p.share)} of your lives">
      <circle class="halo" cx="${px}" cy="${py}" r="15" fill="#8b4d1c" opacity="0"/>
      <circle cx="${px}" cy="${py}" r="9.5" fill="#f8f4ea" stroke="#8b4d1c" stroke-width="1.4"/>
      <text x="${px}" y="${py + 4.2}" text-anchor="middle" style="fill:#8b4d1c;font-size:11.5px;font-style:italic">${p.n}</text></g>`;
  });
  const [mx, my] = pt(med, R);
  g += `<circle cx="${mx}" cy="${my}" r="6" fill="#1f2531"/>`;
  g += `<text x="${cx}" y="${cy - 8}" text-anchor="middle" style="font-size:15px;fill:#1f2531;font-style:italic;paint-order:stroke;stroke:#f2ecdf;stroke-width:6px">1,000 lives</text>`;
  g += `<text x="${cx}" y="${cy + 14}" text-anchor="middle" style="font-size:13px;paint-order:stroke;stroke:#f2ecdf;stroke-width:6px">half end by ${whole(med)}</text>`;
  $("#wheel").innerHTML = `<svg viewBox="-30 -30 ${S + 60} ${S + 60}" role="img" aria-label="A circular chart of your 1,000 lives from age ${x0} to 110, with the moments they share marked on the rim.">${g}</svg>`;

  const list = planets.map((p) => `<li data-n="${p.n}"><span class="glyph">${p.n}</span><span class="what">${p.label}<small>most often at ${p.mode}</small></span><span class="share">${pct(p.share)}</span></li>`);
  list.push(`<li><span class="glyph" style="color:#1f2531">●</span><span class="what">Half of your lives have ended<small>the dark dot, at ${whole(med)}</small></span><span class="share">50%</span></li>`);
  list.push(`<li><span class="glyph" style="color:#c9a27c">▬</span><span class="what">The busiest decade<small>${from} to ${from + 10}, the shaded band</small></span><span class="share">${pct(best)}</span></li>`);
  $("#planets").innerHTML = list.join("");
  const link = (n, on) => document.querySelectorAll(`[data-n="${n}"]`).forEach((e) => e.classList.toggle("on", on));
  document.querySelectorAll("#wheel .planet, #planets li[data-n]").forEach((e) => {
    e.addEventListener("pointerenter", () => link(e.dataset.n, true));
    e.addEventListener("pointerleave", () => link(e.dataset.n, false));
    e.addEventListener("focus", () => link(e.dataset.n, true));
    e.addEventListener("blur", () => link(e.dataset.n, false));
  });
}

// ------------------------------------------------------------ four other lives

const DEATH_WORDS = {
  lung_cancer: "lung cancer", other_cancer: "cancer", heart: "heart disease", stroke: "a stroke", copd: "chronic lung disease",
  diabetes: "diabetes", dementia: "dementia", motor_vehicle: "injuries from a car crash", other_accidents: "an accident",
  other_injury: "an injury", other: "other causes",
};
const ILLNESS = ["cancer_lung", "cancer_other", "heart_attack", "stroke", "disability_start", "crash_injury"];

function lifeCard(title, life) {
  const items = life.events.map(([age, year, e]) => `<li><span>${age}, in ${year}</span>${capital(EVENT_WORDS[e] || e)}.</li>`);
  items.push(`<li class="end"><span>${whole(life.age)}, in ${life.year}</span>You die of ${DEATH_WORDS[life.cause] || life.cause}.</li>`);
  return `<li class="life"><h4>${title}</h4><p class="span">To ${whole(life.age)}${life.events.length ? "" : ", with none of the events the model follows"}</p><ol>${items.join("")}</ol></li>`;
}
function renderOthers(person, r) {
  const L = r.lives, med = quantile(r.exact, 0.5);
  const longest = L.reduce((p, q) => (q.age > p.age ? q : p));
  const shortest = L.reduce((p, q) => (q.age < p.age ? q : p));
  const ordinary = L.reduce((p, q) => (Math.abs(q.age - med) < Math.abs(p.age - med) ? q : p));
  const calm = L.filter((l) => !l.events.some(([, , e]) => ILLNESS.includes(e))).sort((p, q) => p.age - q.age);
  const cards = [lifeCard("The longest", longest), lifeCard("The shortest", shortest), lifeCard("The most ordinary", ordinary)];
  cards.push(calm.length ? lifeCard("No serious illness", calm[Math.floor(calm.length / 2)])
    : `<li class="life"><h4>No serious illness</h4><p class="span">None of your 1,000 lives escaped every illness and injury the model follows.</p></li>`);
  $("#others").innerHTML = cards.join("");
  $("#drawn").innerHTML = "";
}
$("#another").addEventListener("click", () => {
  if (!current) return;
  const life = current.r.lives[Math.floor(Math.random() * current.r.lives.length)];
  $("#drawn").innerHTML = `<ol class="others" style="grid-template-columns:1fr">${lifeCard("Another of your lives", life)}</ol>`;
});

// ------------------------------------------------------------ change your fate

let fateTimer = null, fateToken = 0;
function renderFate(person, r) {
  const a = person.answers, form = $("#controls");
  const smokingNow = a.smoking === "never" ? "never" : a.smoking === "former" ? "former" : a.keeps_smoking ? "keeps" : "current";
  const opts = [["never", "Never smoked"]];
  if (a.smoking === "former") opts.push(["former", `Quit at ${a.quit_age}, as you said`]);
  opts.push(["quit_now", `Quit now, at ${a.age}`], ["current", "Smoke, and may quit later"], ["keeps", "Smoke, and keep smoking"]);
  const sel = el("select", { id: "c-smoking" }, ...opts.map(([v, label]) => el("option", { value: v, selected: v === smokingNow }, label)));
  const range = (id, label, min, max, step, value, show) => {
    const out = el("output", { for: id }, show(value));
    const input = el("input", { type: "range", id, min, max, step, value });
    input.addEventListener("input", () => { out.textContent = show(Number(input.value)); schedule(); });
    return [el("div", { class: "control" }, el("label", { for: id }, label, out), input), input];
  };
  const bmi = (kg) => kg / (a.height_cm / 100) ** 2;
  const [c1, act] = range("c-activity", "Activity", 0, Math.max(600, a.activity_minutes), 15, a.activity_minutes, (v) => `${v} min a week`);
  const [c2, wt] = range("c-weight", "Weight", Math.max(30, Math.round(a.weight_kg - 40)), Math.min(300, Math.round(a.weight_kg + 40)), 1, Math.round(a.weight_kg), (v) => `${v} kg, BMI ${bmi(v).toFixed(1)}`);
  const [c3, dr] = range("c-drinks", "Drinks", 0, Math.max(40, a.drinks_per_week), 1, Math.round(a.drinks_per_week), (v) => `${v} a week`);
  const [c4, fv] = range("c-fv", "Fruit and vegetables", 0, Math.max(10, a.fruit_veg_per_day), 0.5, a.fruit_veg_per_day, (v) => `${v} a day`);
  const reset = el("button", { type: "button", class: "quiet" }, "Back to my answers");
  reset.addEventListener("click", () => renderFate(person, r));
  sel.addEventListener("change", schedule);
  form.replaceChildren(el("div", { class: "control" }, el("label", { for: "c-smoking" }, "Smoking"), sel), c1, c2, c3, c4, el("div", {}, reset));

  const read = () => {
    const s = sel.value;
    return { ...a, smoking: s === "quit_now" ? "former" : s === "keeps" ? "current" : s,
      quit_age: s === "quit_now" ? a.age : s === "former" ? a.quit_age : null, keeps_smoking: s === "keeps",
      activity_minutes: Number(act.value), weight_kg: Number(wt.value), drinks_per_week: Number(dr.value), fruit_veg_per_day: Number(fv.value) };
  };
  function schedule() {
    clearTimeout(fateTimer);
    $("#odds-chart").classList.add("busy");
    fateTimer = setTimeout(async () => {
      const token = ++fateToken;
      try {
        const changed = await ask({ type: "exact", answers: read(), startMarital: person.marital });
        if (token !== fateToken) return;
        showCompare(r.exact, changed, a.age); drawOdds(r.exact, changed);
      } catch (err) {
        $("#compare").innerHTML = `<div><dt>That change could not be worked out</dt><dd>${err.message}</dd></div>`;
      } finally { if (token === fateToken) $("#odds-chart").classList.remove("busy"); }
    }, 200);
  }
  showCompare(r.exact, r.exact, a.age); drawOdds(r.exact, r.exact);
}
function showCompare(before, after, x) {
  const M = x < 85 ? 90 : Math.ceil((x + 5) / 5) * 5;
  const rows = [
    ["Half last past", quantile(before, 0.5), quantile(after, 0.5), (v) => v.toFixed(1), 1],
    ["1 in 10 pass", quantile(before, 0.9), quantile(after, 0.9), (v) => v.toFixed(1), 1],
    [`Reach ${M}`, 1 - cdf(before, M), 1 - cdf(after, M), (v) => `${(100 * v).toFixed(1)}%`, 100],
    ["Expected age at death", before.mean, after.mean, (v) => v.toFixed(1), 1],
  ];
  $("#compare").innerHTML = rows.map(([label, b, c, show, scale]) => {
    const diff = (c - b) * scale, same = Math.abs(diff) < 0.05;
    const tag = same ? "" : `<span class="${diff > 0 ? "up" : "down"}"> ${diff > 0 ? "+" : "−"}${Math.abs(diff).toFixed(1)}${scale === 100 ? " pts" : ""}</span>`;
    return `<div><dt>${label}</dt><dd>${same ? show(c) : `<span class="from">${show(b)} →</span> ${show(c)}${tag}`}</dd></div>`;
  }).join("");
}
function drawOdds(base, changed) {
  const box = $("#odds-chart"), W = 760, H = 320, L = 4, R = 756, T = 10, B = H - 34;
  const start = base.ages[0], width = 2, bins = [];
  for (let a = start; a <= 110; a += width) bins.push(a);
  const binned = (ex) => bins.map((b) => ex.ages.reduce((s, a, i) => (a >= b && a < b + width ? s + ex.die[i] : s), 0));
  const b0 = binned(base), b1 = binned(changed), peak = Math.max(...b0, ...b1) || 1;
  const xs = (a) => L + ((a - start) / (112 - start)) * (R - L), bw = xs(start + width) - xs(start), h = (v) => (v / peak) * (B - T - 16);
  let g = "";
  for (let a = Math.ceil((start + 3) / 10) * 10; a <= 110; a += 10) g += `<line x1="${xs(a)}" x2="${xs(a)}" y1="${T}" y2="${B}" stroke="#d8ccb3" stroke-dasharray="2 5"/><text x="${xs(a)}" y="${B + 22}" text-anchor="middle">${a}</text>`;
  g += `<line x1="${L}" x2="${R}" y1="${B + 0.5}" y2="${B + 0.5}" stroke="#1f2531"/>`;
  bins.forEach((b, i) => { if (b1[i] > 0) g += `<rect x="${xs(b) + 1}" y="${B - h(b1[i])}" width="${Math.max(bw - 2, 1)}" height="${h(b1[i])}" rx="1.5" fill="#8b4d1c" fill-opacity="0.72"/>`; });
  g += `<path d="${bins.map((b, i) => `M${(xs(b) + 1).toFixed(1)} ${B}V${(B - h(b0[i])).toFixed(1)}H${(xs(b) + bw - 1).toFixed(1)}V${B}`).join("")}" fill="none" stroke="#1f2531" stroke-width="1.4"/>`;
  const same = base === changed;
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" aria-hidden="true">${g}</svg><ul class="odds-key"><li><i class="k-outline"></i>Your answers</li>${same ? "" : `<li><i class="k-fill"></i>With the change</li>`}<li>Ages at death, in two-year bands</li></ul>`;
}

// ------------------------------------------------------------ the share card

async function renderShare(person, r) {
  const c = $("#share-canvas"), ctx = c.getContext("2d"), W = 1080, H = 1350;
  try { await document.fonts.load("60px Lora"); await document.fonts.load("italic 60px Lora"); } catch { /* fall back to Georgia */ }
  ctx.fillStyle = C.night; ctx.fillRect(0, 0, W, H);
  const random = seeded(1693);
  for (let i = 0; i < 220; i++) star(ctx, random() * W, random() * H, 0.6 + random() * 1.6, 0.25 + random() * 0.5, C.star);
  ctx.globalAlpha = 1;
  ctx.strokeStyle = C.rule; ctx.lineWidth = 2; ctx.strokeRect(36, 36, W - 72, H - 72);
  ctx.lineWidth = 1; ctx.strokeRect(48, 48, W - 96, H - 96);
  ctx.fillStyle = C.dim; ctx.font = "34px Lora, Georgia, serif"; ctx.textAlign = "center";
  ctx.fillText("One Life, 1,000 Times", W / 2, 140);
  // the constellation
  const stars = person.stars, X = (k) => 150 + k * 97.5, Y = (v) => 230 + v * 280;
  ctx.strokeStyle = C.ochre; ctx.globalAlpha = 0.6; ctx.lineWidth = 2; ctx.beginPath();
  stars.forEach((v, k) => (k ? ctx.lineTo(X(k), Y(v)) : ctx.moveTo(X(k), Y(v)))); ctx.stroke();
  ctx.globalAlpha = 1; ctx.fillStyle = C.ochre;
  stars.forEach((v, k) => {
    const x = X(k), y = Y(v), s = 11;
    ctx.beginPath(); ctx.moveTo(x, y - s * 2); ctx.lineTo(x + s * 0.45, y - s * 0.45); ctx.lineTo(x + s * 2, y); ctx.lineTo(x + s * 0.45, y + s * 0.45);
    ctx.lineTo(x, y + s * 2); ctx.lineTo(x - s * 0.45, y + s * 0.45); ctx.lineTo(x - s * 2, y); ctx.lineTo(x - s * 0.45, y - s * 0.45); ctx.closePath(); ctx.fill();
  });
  const med = whole(quantile(r.exact, 0.5)), q90 = whole(quantile(r.exact, 0.9));
  ctx.fillStyle = C.star; ctx.font = "italic 50px Lora, Georgia, serif";
  ctx.fillText("Half of my lives last past", W / 2, 640);
  ctx.fillStyle = C.ochre; ctx.font = "500 230px Lora, Georgia, serif";
  ctx.fillText(String(med), W / 2, 860);
  ctx.fillStyle = C.star; ctx.font = "40px Lora, Georgia, serif";
  ctx.fillText(`and 1 in 10 pass ${q90}.`, W / 2, 940);
  const top = r.levers[0];
  ctx.fillStyle = C.dim; ctx.font = "34px Lora, Georgia, serif";
  const lever = top && top.gain >= 0.25 ? `My lever: ${top.label}, +${top.gain.toFixed(1)} years.` : "My lever: hold steady. My habits already do the work.";
  wrapText(ctx, lever, W / 2, 1060, W - 220, 46);
  ctx.fillStyle = C.dim; ctx.font = "28px Lora, Georgia, serif";
  ctx.fillText("A model built on Canadian data, not a prediction.", W / 2, 1210);
  ctx.fillStyle = C.star; ctx.fillText("soodpratham10.github.io/one-life-1000-times", W / 2, 1255);
}
function wrapText(ctx, text, x, y, maxW, lh) {
  const words = text.split(" "); let line = "";
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxW && line) { ctx.fillText(line, x, y); line = word; y += lh; } else line = test;
  }
  if (line) ctx.fillText(line, x, y);
}
$("#download").addEventListener("click", () => {
  const b = $("#download");
  b.setAttribute("aria-busy", "true");
  $("#share-canvas").toBlob((blob) => {
    const a = el("a", { href: URL.createObjectURL(blob), download: "my-reading.png" });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    b.removeAttribute("aria-busy");
  }, "image/png");
});

// ------------------------------------------------------------ the one floating control

const toTop = $("#to-top");
addEventListener("scroll", () => { toTop.hidden = scrollY < innerHeight * 1.5; }, { passive: true });
toTop.addEventListener("click", () => scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" }));
