'use strict';
// The disc builder. Click a cover (or drop the files on the window) to choose that
// disc; when both are checked, COMBINE builds our disc. The covers charge up while
// it's built, a mechanical counter ticking through the real steps, then they slam
// together and shatter, and the Ultimate cover comes out of the flash, with where
// the disc was written and a button to open that folder.
//
// Outside the app (a plain browser) a stand-in pretends to check and build.
// ?at=<seconds> draws the one frame that far into building (silent, same every
// time), for screenshots; ?empty shows the covers not yet chosen.

const stage = document.getElementById('stage');
const ctx = stage.getContext('2d');
const goBtn = document.getElementById('go');
const statusEl = document.getElementById('status');
const header = document.querySelector('header');

const params = new URLSearchParams(location.search);
const FREEZE = params.has('at') ? parseFloat(params.get('at')) : null;
if (FREEZE !== null) {
  window.addEventListener('error', e => { statusEl.textContent = `${e.message} (line ${e.lineno})`; });
  window.addEventListener('unhandledrejection', e => { statusEl.textContent = String(e.reason && e.reason.stack || e.reason); });
}

// timeline, seconds from COMBINE; the charge holds at T.arcs until the disc is built
const T = {
  arcs: 1.6,      // edge sparks give way to bolts between the covers
  impact: 3.0,    // the covers meet: flash, boom
  burst: 3.06,    // they shatter; the new cover starts to grow
  glint: 4.6,     // a glint across the new cover
  done: 5.6,      // the result is shown
};

// ---------------------------------------------------------------- helpers

let seed = FREEZE !== null ? 41 : (Date.now() & 0xffffffff);
function R() {                               // mulberry32
  seed = (seed + 0x6D2B79F5) | 0;
  let t = seed;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
const rand = (a, b) => a + R() * (b - a);
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const seg = (t, a, b) => clamp((t - a) / (b - a), 0, 1);
const pad = n => String(n).padStart(2, '0');
const ease = {
  inCubic: t => t * t * t,
  outCubic: t => 1 - Math.pow(1 - t, 3),
  inOut: t => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2),
  outBack: t => 1 + 2.4 * Math.pow(t - 1, 3) + 1.4 * Math.pow(t - 1, 2),
};
function mix(a, b, t) {
  return `rgb(${a.map((v, i) => Math.round(lerp(v, b[i], t))).join(',')})`;
}

// ---------------------------------------------------------------- art

const art = {};
function load(name, src) {
  return new Promise((resolve, reject) => {
    const im = new Image();
    im.onload = () => { art[name] = im; resolve(); };
    im.onerror = reject;
    im.src = src;
  });
}

// a cover not yet chosen: grey and dim
function greyCopy(im) {
  const c = document.createElement('canvas');
  c.width = im.width;
  c.height = im.height;
  const g = c.getContext('2d');
  g.filter = 'grayscale(1) brightness(0.42) contrast(0.9)';
  g.drawImage(im, 0, 0);
  return c;
}

// ---------------------------------------------------------------- sound

let actx = null, master = null, noise = null, humNodes = null;
let muted = FREEZE !== null;

function audio() {
  if (!actx) {
    actx = new AudioContext();
    const glue = actx.createDynamicsCompressor();
    glue.threshold.value = -10;
    glue.knee.value = 6;
    glue.ratio.value = 6;
    glue.attack.value = 0.003;
    glue.release.value = 0.25;
    glue.connect(actx.destination);
    master = actx.createGain();
    master.gain.value = 0.55;
    master.connect(glue);
    noise = actx.createBuffer(1, actx.sampleRate * 2, actx.sampleRate);
    const d = noise.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  }
  return actx;
}

// stock sound effects from sfx/; the synth stands in for any that didn't load
const sfx = {};
async function loadSound(name, src) {
  try {
    const data = await (await fetch(src)).arrayBuffer();
    sfx[name] = await audio().decodeAudioData(data);
  } catch (e) {
    console.warn(`no sound ${src}: ${e}`);
  }
}

// offset skips a clip's lead-in; dur cuts it short with a fade
function playSound(name, { vol = 1, rate = 1, offset = 0, dur = 0 } = {}) {
  if (muted || !sfx[name]) return false;
  const a = audio(), now = a.currentTime;
  const s = a.createBufferSource();
  s.buffer = sfx[name];
  s.playbackRate.value = rate;
  const g = a.createGain();
  g.gain.setValueAtTime(vol, now);
  s.connect(g).connect(master);
  if (dur) {
    g.gain.setValueAtTime(vol, now + dur - 0.3);
    g.gain.linearRampToValueAtTime(0, now + dur);
    s.start(now, offset, dur);
  } else {
    s.start(now, offset);
  }
  return true;
}

function crackle(vol) {
  if (muted) return;
  const a = audio(), now = a.currentTime, dur = 0.04 + Math.random() * 0.1;
  const s = a.createBufferSource();
  s.buffer = noise;
  s.playbackRate.value = 0.6 + Math.random() * 0.9;
  const hp = a.createBiquadFilter();
  hp.type = 'highpass';
  hp.frequency.value = 1200 + Math.random() * 3000;
  const g = a.createGain();
  g.gain.setValueAtTime(vol, now);
  g.gain.exponentialRampToValueAtTime(0.001, now + dur);
  s.connect(hp).connect(g).connect(master);
  s.start(now, Math.random() * 1.5, dur + 0.02);
}

// the charge's hum and electric buzz; humTo sets how charged (0..1) over secs
function humStart() {
  if (muted || humNodes) return;
  const a = audio(), now = a.currentTime;
  const lp = a.createBiquadFilter();
  lp.type = 'lowpass';
  lp.frequency.setValueAtTime(260, now);
  const g = a.createGain();
  g.gain.setValueAtTime(0.0001, now);
  const oscs = [0, 7].map(cents => {
    const o = a.createOscillator();
    o.type = 'sawtooth';
    o.frequency.setValueAtTime(42, now);
    o.detune.value = cents;
    o.connect(lp);
    o.start(now);
    return o;
  });
  lp.connect(g).connect(master);
  humNodes = { oscs, lp, g };
  if (sfx.buzz_loop) {
    const s = a.createBufferSource();
    s.buffer = sfx.buzz_loop;
    s.loop = true;
    s.playbackRate.setValueAtTime(0.75, now);
    const bg = a.createGain();
    bg.gain.setValueAtTime(0.03, now);
    s.connect(bg).connect(master);
    s.start(now);
    Object.assign(humNodes, { buzz: s, bg });
  }
}

function humTo(level, secs) {
  if (!humNodes) return;
  const now = actx.currentTime, end = now + secs;
  const ramp = (param, v) => {
    param.cancelScheduledValues(now);
    param.setValueAtTime(param.value, now);
    param.exponentialRampToValueAtTime(v, end);
  };
  humNodes.oscs.forEach(o => ramp(o.frequency, 42 * Math.pow(150 / 42, level)));
  ramp(humNodes.lp.frequency, 260 * Math.pow(3200 / 260, level));
  ramp(humNodes.g.gain, Math.max(0.0001, 0.22 * level * level));
  if (humNodes.buzz) {
    ramp(humNodes.buzz.playbackRate, 0.75 + 0.6 * level);
    ramp(humNodes.bg.gain, 0.03 * Math.pow(0.4 / 0.03, level));
  }
}

function humStop() {
  if (!humNodes) return;
  const now = actx.currentTime;
  for (const g of [humNodes.g, humNodes.bg].filter(Boolean)) {
    g.gain.cancelScheduledValues(now);
    g.gain.setValueAtTime(g.gain.value, now);
    g.gain.exponentialRampToValueAtTime(0.0001, now + 0.05);
  }
  humNodes.oscs.forEach(o => o.stop(now + 0.1));
  if (humNodes.buzz) humNodes.buzz.stop(now + 0.1);
  humNodes = null;
}

function boom() {
  if (muted) return;
  const a = audio(), now = a.currentTime;
  const s = a.createBufferSource();
  s.buffer = noise;
  const lp = a.createBiquadFilter();
  lp.type = 'lowpass';
  lp.frequency.setValueAtTime(2400, now);
  lp.frequency.exponentialRampToValueAtTime(70, now + 1.6);
  const g = a.createGain();
  g.gain.setValueAtTime(1.0, now);
  g.gain.exponentialRampToValueAtTime(0.001, now + 2.2);
  s.connect(lp).connect(g).connect(master);
  s.start(now);
  const o = a.createOscillator();
  o.frequency.setValueAtTime(120, now);
  o.frequency.exponentialRampToValueAtTime(26, now + 1.0);
  const og = a.createGain();
  og.gain.setValueAtTime(0.9, now);
  og.gain.exponentialRampToValueAtTime(0.001, now + 1.3);
  o.connect(og).connect(master);
  o.start(now);
  o.stop(now + 1.4);
}

const thunderclap = () => playSound('thunder_snap', { offset: 0.17, dur: 3.3 }) || boom();

// a V8 roaring as the new cover comes out
const roar = () => playSound('roar') || chime();

function chime() {
  if (muted) return;
  const a = audio(), now = a.currentTime;
  [523.25, 659.25, 783.99, 1046.5, 1318.5].forEach((f, i) => {
    const t = now + i * 0.085;
    for (const type of ['sine', 'triangle']) {
      const o = a.createOscillator();
      o.type = type;
      o.frequency.value = f;
      const g = a.createGain();
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(type === 'sine' ? 0.16 : 0.05, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 1.8);
      o.connect(g).connect(master);
      o.start(t);
      o.stop(t + 1.9);
    }
  });
}

// a relay's click: the counter's segments, a disc checking in
function click(pitch = 1, vol = 1) {
  if (muted) return;
  const a = audio(), now = a.currentTime;
  const s = a.createBufferSource();
  s.buffer = noise;
  const bp = a.createBiquadFilter();
  bp.type = 'bandpass';
  bp.frequency.value = 2600 * pitch;
  bp.Q.value = 3;
  const g = a.createGain();
  g.gain.setValueAtTime(0.35 * vol, now);
  g.gain.exponentialRampToValueAtTime(0.001, now + 0.03);
  s.connect(bp).connect(g).connect(master);
  s.start(now, Math.random() * 1.5, 0.04);
  const o = a.createOscillator();
  o.frequency.setValueAtTime(190 * pitch, now);
  o.frequency.exponentialRampToValueAtTime(90 * pitch, now + 0.04);
  const og = a.createGain();
  og.gain.setValueAtTime(0.18 * vol, now);
  og.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
  o.connect(og).connect(master);
  o.start(now);
  o.stop(now + 0.06);
}

// ---------------------------------------------------------------- the app's side

const TAURI = window.__TAURI__;

// outside the app: a stand-in that checks any choice and builds in a couple of seconds,
// with steps like the real ones; its build is driven by the animation's clock
const DEMO_STEPS = (() => {
  const steps = [];
  let f = 0;
  const add = (stage, detail, df, log) => {
    f = Math.min(1, f + df);
    steps.push({ stage, detail, fraction: f, log });
  };
  add('Checking Circuit Edition', 'track 01 · 29.4 MB', 0, null);
  add('Checking Circuit Edition', 'track 01', 0.038, 'CCE track 01 · SHA-1 f450f510 ✓');
  add('Checking Daytona USA', 'track 01 · 9.6 MB', 0, null);
  add('Checking Daytona USA', 'track 01', 0.012, 'DUSA track 01 · SHA-1 6078e96e ✓');
  add('Unpacking the patch', '6.4 MB', 0.044, 'Patch unpacked · 6.4 MB of data for 3127 sectors');
  add('Rebuilding track 01', 'sector 14327 of 14328 · EDC/ECC', 0.043, 'Track 01 · 3127 sectors rebuilt, EDC/ECC written');
  add('Writing track 01', '', 0.044, 'Track 01 · SHA-1 2b6c2c45 ✓ matches');
  for (let n = 2; n <= 33; n++) {
    const src = n <= 31 ? `CCE ${pad(n)}` : `DUSA ${pad(35 - n)}`;
    add(`Copying track ${pad(n)}`, '', 0.818 / 32, `Track ${pad(n)} ← ${src} · SHA-1 ✓`);
  }
  add('Done', '', 1, 'Daytona USA Ultimate.cue written');
  return steps.map((s, i) => ({ ...s, at: 0.15 + i * 0.045 }));
})();

const backend = TAURI ? {
  pick: () => TAURI.core.invoke('pick'),
  inspect: path => TAURI.core.invoke('inspect', { path }),
  outDir: () => TAURI.core.invoke('out_dir'),
  pickOutDir: () => TAURI.core.invoke('pick_out_dir'),
  build(cce, dusa, out, onProgress) {
    let unlisten = null;
    return TAURI.event.listen('build-progress', e => onProgress(e.payload))
      .then(u => { unlisten = u; return TAURI.core.invoke('build', { cce, dusa, out }); })
      .finally(() => unlisten && unlisten());
  },
  reveal: path => TAURI.core.invoke('reveal', { path }),
} : {
  pick: key => Promise.resolve(`demo:${key}`),
  inspect: path => new Promise(res => setTimeout(() => res({
    game: path.endsWith('cce') ? 'cce' : 'dusa', name: path, path,
  }), 600)),
  outDir: () => Promise.resolve('Daytona USA Ultimate'),
  pickOutDir: () => Promise.resolve('Daytona USA Ultimate'),
  build: () => new Promise((res, rej) => { work.demo = { at: 0, i: 0, res, rej }; }),
  reveal: () => Promise.resolve(),
};

// where the disc will be written: beside the app, or wherever the player chooses
let outDir = null;

// ---------------------------------------------------------------- the two discs

const shown = FREEZE !== null && !params.has('empty');
const slots = {
  dusa: { title: 'DAYTONA USA', want: 'Daytona USA disc', state: shown ? 'ok' : 'empty', path: shown ? 'demo:dusa' : '', lit: shown ? 1 : 0, flash: 0 },
  cce: { title: 'DAYTONA USA CIRCUIT EDITION', want: 'Japan disc', state: shown ? 'ok' : 'empty', path: shown ? 'demo:cce' : '', lit: shown ? 1 : 0, flash: 0 },
};
const ready = () => slots.dusa.state === 'ok' && slots.cce.state === 'ok';
let picking = false, hover = null;

// the status line, and under it a path (with a link to change it), if given
function setStatus(text, kind = '', path = null, change = null) {
  statusEl.className = kind;
  statusEl.textContent = text;
  if (path === null) return;
  const where = document.createElement('span');
  where.className = 'path';
  where.textContent = path;
  if (change) {
    const a = document.createElement('a');
    a.className = 'change';
    a.href = '#';
    a.textContent = 'change';
    a.addEventListener('click', e => { e.preventDefault(); change(); });
    where.append(' ', a);
  }
  statusEl.appendChild(where);
}

function refresh() {
  goBtn.disabled = !ready();
  if (mode !== 'idle') return;
  if (ready()) {
    if (outDir) setStatus('Both discs checked. The disc will be written to:', 'good', outDir, chooseOutDir);
    else setStatus('Both discs checked. COMBINE will ask where to write the disc.', 'good');
  } else if (!statusEl.classList.contains('bad')) {
    setStatus('Click a cover to choose that disc (its .cue sheet, or a .zip of it), or drop the files here.');
  }
}

async function chooseOutDir() {
  if (picking) return false;
  picking = true;
  try {
    const d = await backend.pickOutDir();
    if (d) outDir = d;
    return !!d;
  } finally {
    picking = false;
    refresh();
  }
}

// COMBINE: once it's known where the disc goes
async function combine() {
  if (mode !== 'idle' || !ready() || picking) return;
  if (!outDir && !(await chooseOutDir())) return;
  play();
}

async function choose(key) {
  if (mode !== 'idle' || picking) return;
  picking = true;
  let path = null;
  try {
    path = await backend.pick(key);
  } finally {
    picking = false;
  }
  if (path) check(path, key);
}

// check the disc at path; it goes on its own cover whichever was clicked
async function check(path, key) {
  const slot = key && slots[key];
  const before = slot && { ...slot };
  if (slot) slot.state = 'checking';
  setStatus(`Checking ${path.split(/[\\/]/).pop()}…`);
  try {
    const r = await backend.inspect(path);
    const target = slots[r.game];
    if (slot && target !== slot) Object.assign(slot, before);
    Object.assign(target, { state: 'ok', path: r.path, flash: 1 });
    click(0.7, 1.4);
    statusEl.className = '';
    refresh();
    if (slot && target !== slot && !ready()) {
      setStatus(`That's ${r.name}, so it went on its own cover. Now choose the ${slot.want}.`);
    }
  } catch (e) {
    if (slot) Object.assign(slot, before, { state: 'bad' });
    setStatus(String(e), 'bad');
    goBtn.disabled = !ready();
  }
}

// ---------------------------------------------------------------- stage

let W = 0, H = 0, DPR = 1;
function resize() {
  DPR = window.devicePixelRatio || 1;
  W = window.innerWidth;
  H = window.innerHeight;
  stage.width = Math.round(W * DPR);
  stage.height = Math.round(H * DPR);
  stage.style.width = W + 'px';
  stage.style.height = H + 'px';
}
// a resize clears the canvas: the frozen frame is drawn again
let frozen = false;
window.addEventListener('resize', () => { resize(); if (frozen) draw(); });
resize();

let mode = 'idle';            // idle, playing (building), done
let clock = 0;                // seconds since COMBINE, held at T.arcs until the disc is built
let wall = 0;                 // seconds since the page opened
let playWall = 0;             // wall at COMBINE
let slow = false;
let released = false;         // the disc is built and its steps all shown: on to the slam
let bolts = [], shards = [], sparks = [], rings = [];
let flash = 0, shake = 0, crawlAcc = 0, arcAcc = 0, strikeAt = 0, humAt = 0;
const fired = new Set();

// the build as the counter shows it: never faster than a mechanism would turn
const SEGS = 40;
const work = {
  real: 0, shown: 0, events: [], queue: [], lines: [], lit: 0, litAt: [],
  done: false, result: null, demo: null,
};

const coverH = () => Math.min(H * 0.5, W * 0.32);
const centreY = () => H * 0.47;

// The two covers' places: apart and turned toward each other, drawn in
// together while they charge, closer as the disc is built, then turned
// face-on and slammed edge to edge in the middle. Each sits half its own
// width (as turned) plus its share of the gap from the middle. The US
// longbox stands taller than the Japanese case, on the same floor.
const TALL = { dusa: 1.2, cce: 1 };

function poses(t) {
  const h = coverH();
  const half = (name, yaw, scale) =>
    (h * TALL[name] * scale * art[name].width / art[name].height / 2) * Math.cos(yaw) * 2.2 / (2.2 + 0.5 * Math.sin(yaw));
  const idleYaw = 0.38;
  const still = mode === 'idle';
  const pc = still ? 0 : seg(t, 0, T.arcs), pa = still ? 0 : seg(t, T.arcs, T.impact);
  const squeeze = still ? 0 : work.shown;
  const yaw = lerp(lerp(idleYaw, 0.62, ease.inOut(pc)), 0, ease.inCubic(pa));
  const scale = 1 + 0.07 * ease.inCubic(pa);
  const off = name => {
    const idleGap = W * 0.23 - half(name, idleYaw, 1);
    const gap = lerp(lerp(idleGap, idleGap * 0.45, ease.inOut(pc)) * (1 - 0.45 * squeeze), 0, ease.inCubic(pa));
    return half(name, yaw, scale) + gap;
  };
  const jitter = still ? 0 : 1.5 + 5 * pc + 4 * squeeze + 9 * pa;
  const bob = still ? Math.sin(wall * 1.4) * 5 : 0;
  const j = () => (R() - 0.5) * 2 * jitter;
  const place = (name, side, lift) => {
    const ch = h * TALL[name] * scale;
    return {
      key: name,
      img: art[name],
      grey: art[name + 'Grey'],
      lit: slots[name].lit,
      x: W / 2 + side * off(name) + j(),
      y: centreY() + (h * scale - ch) / 2 + lift + j(),
      h: ch,
      yaw: -side * yaw,
    };
  };
  return { dusa: place('dusa', -1, bob), cce: place('cce', 1, -bob) };
}

// A cover turned yaw radians about its upright middle, seen in perspective:
// drawn in thin upright strips, each as tall as its depth makes it.
function project(p, x) {
  const w = p.h * p.img.width / p.img.height;
  const f = w * 2.2;
  const k = f / (f + x * Math.sin(p.yaw));
  return { x: p.x + x * Math.cos(p.yaw) * k, k };
}

// The strips overlap a little so no seam shows between them, which only works
// drawn opaque: a see-through cover is drawn opaque into a layer, then faded.
function drawStrips(c, p, img) {
  const w = p.h * p.img.width / p.img.height, N = 56, sw = img.width / N;
  for (let i = 0; i < N; i++) {
    const a = project(p, -w / 2 + (w * i) / N), b = project(p, -w / 2 + (w * (i + 1)) / N);
    const k = (a.k + b.k) / 2;
    const x0 = Math.min(a.x, b.x), x1 = Math.max(a.x, b.x);
    c.drawImage(img, i * sw, 0, sw, img.height, x0, p.y - (p.h * k) / 2, x1 - x0 + 0.7, p.h * k);
  }
}

// a chosen cover in colour, one not yet chosen grey, lit between them; a flash as it's checked
const mixed = {};
function coverLook(p) {
  const lit = p.lit ?? 1, fl = p.key ? slots[p.key].flash : 0;
  if (fl <= 0 && lit >= 0.999) return p.img;
  if (fl <= 0 && lit <= 0.001 && p.grey) return p.grey;
  const c = mixed[p.key] ||= Object.assign(document.createElement('canvas'), { width: p.img.width, height: p.img.height });
  const g = c.getContext('2d');
  g.globalCompositeOperation = 'source-over';
  g.globalAlpha = 1;
  g.drawImage(p.grey, 0, 0);
  g.globalAlpha = lit;
  g.drawImage(p.img, 0, 0);
  if (fl > 0) {
    g.globalCompositeOperation = 'lighter';
    g.globalAlpha = fl * 0.6;
    g.drawImage(p.img, 0, 0);
  }
  return c;
}

const layer = document.createElement('canvas');
function drawCover(p, alpha = 1) {
  const look = coverLook(p);
  if (alpha >= 1) {
    drawStrips(ctx, p, look);
    return;
  }
  if (layer.width !== stage.width || layer.height !== stage.height) {
    layer.width = stage.width;
    layer.height = stage.height;
  }
  const l = layer.getContext('2d');
  l.setTransform(1, 0, 0, 1, 0, 0);
  l.clearRect(0, 0, layer.width, layer.height);
  l.setTransform(ctx.getTransform());
  drawStrips(l, p, look);
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = alpha;
  ctx.drawImage(layer, 0, 0);
  ctx.restore();
}

// the edge of a cover nearer the other cover: x, top, bottom
function innerEdge(p, side) {
  const w = p.h * p.img.width / p.img.height;
  const e = project(p, side * w / 2);
  return { x: e.x, top: p.y - (p.h * e.k) / 2, bottom: p.y + (p.h * e.k) / 2 };
}

function floorY(p) { return p.y + p.h / 2 + 10; }

function drawReflection(p, alpha) {
  const fy = floorY(p);
  ctx.save();
  ctx.translate(0, 2 * fy);
  ctx.scale(1, -1);
  drawCover({ ...p, y: p.y + 10 }, alpha);
  ctx.restore();
}

// where a cover and its label take clicks
function coverBox(p) {
  const w = p.h * p.img.width / p.img.height * Math.cos(p.yaw);
  return { x0: p.x - w / 2, x1: p.x + w / 2, y0: p.y - p.h / 2, y1: floorY(p) + 62 };
}

// ---------------------------------------------------------------- lightning

function boltPath(ax, ay, bx, by, rough, depth) {
  let pts = [[ax, ay], [bx, by]];
  let disp = Math.hypot(bx - ax, by - ay) * rough;
  for (let d = 0; d < depth; d++) {
    const next = [pts[0]];
    for (let i = 0; i < pts.length - 1; i++) {
      const [x0, y0] = pts[i], [x1, y1] = pts[i + 1];
      const L = Math.hypot(x1 - x0, y1 - y0) || 1;
      const o = (R() * 2 - 1) * disp;
      next.push([(x0 + x1) / 2 - ((y1 - y0) / L) * o, (y0 + y1) / 2 + ((x1 - x0) / L) * o], pts[i + 1]);
    }
    pts = next;
    disp *= 0.55;
  }
  return pts;
}

function makeBolt(ax, ay, bx, by, o = {}) {
  const main = boltPath(ax, ay, bx, by, o.rough ?? 0.22, o.depth ?? 6);
  const branches = [];
  const len = Math.hypot(bx - ax, by - ay), dir = Math.atan2(by - ay, bx - ax);
  for (let i = 0; i < (o.branches ?? 2); i++) {
    const [px, py] = main[1 + Math.floor(R() * (main.length - 2))];
    const ang = dir + (R() - 0.5) * 1.8;
    const l = len * rand(0.12, 0.4);
    branches.push(boltPath(px, py, px + Math.cos(ang) * l, py + Math.sin(ang) * l, 0.3, 4));
  }
  return { main, branches, age: 0, life: o.life ?? rand(0.06, 0.14), width: o.width ?? 1 };
}

function stroke(pts) {
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  ctx.stroke();
}

function drawBolt(b) {
  const a = (1 - b.age / b.life) * (0.65 + 0.35 * R());
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  for (const [w, col, al] of [[18, '110,80,255', 0.16], [7, '140,185,255', 0.45], [2.2, '255,255,255', 1]]) {
    ctx.strokeStyle = `rgba(${col},${al * a})`;
    ctx.lineWidth = w * b.width;
    stroke(b.main);
    ctx.lineWidth = w * b.width * 0.5;
    b.branches.forEach(stroke);
  }
  ctx.restore();
}

// ---------------------------------------------------------------- shatter

function shatter(p, impact) {
  const img = p.img, h = p.h, w = h * img.width / img.height;
  const cols = 8, rows = 7, P = [];
  for (let j = 0; j <= rows; j++) {
    P.push([]);
    for (let i = 0; i <= cols; i++) {
      let x = -w / 2 + (w * i) / cols, y = -h / 2 + (h * j) / rows;
      if (i > 0 && i < cols) x += (R() - 0.5) * (w / cols) * 0.75;
      if (j > 0 && j < rows) y += (R() - 0.5) * (h / rows) * 0.75;
      P[j].push([x, y]);
    }
  }
  const tris = [];
  for (let j = 0; j < rows; j++) {
    for (let i = 0; i < cols; i++) {
      const a = P[j][i], b = P[j][i + 1], c = P[j + 1][i + 1], d = P[j + 1][i];
      if (R() < 0.5) tris.push([a, b, c], [a, c, d]);
      else tris.push([a, b, d], [b, c, d]);
    }
  }
  const reach = Math.hypot(w, h);
  for (const tri of tris) {
    const lx = (tri[0][0] + tri[1][0] + tri[2][0]) / 3, ly = (tri[0][1] + tri[1][1] + tri[2][1]) / 3;
    const x = p.x + lx, y = p.y + ly;
    const dx = x - impact.x, dy = y - impact.y, d = Math.hypot(dx, dy) || 1;
    const speed = rand(260, 820) * (1.3 - 0.5 * Math.min(1, d / reach));
    shards.push({
      img, w, h, lx, ly, x, y,
      poly: tri.map(([px, py]) => [px - lx, py - ly]),
      vx: (dx / d) * speed + rand(-90, 90),
      vy: (dy / d) * speed - rand(60, 260),
      rot: 0, vr: rand(-7, 7), s: 1, vs: rand(-0.15, 0.9),
      age: 0, life: rand(1.0, 1.7),
    });
  }
}

function burst(impact) {
  for (let i = 0; i < 280; i++) {
    const ang = R() * Math.PI * 2, sp = rand(150, 1150);
    sparks.push({ x: impact.x, y: impact.y, vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp - 120, age: 0, life: rand(0.4, 1.3) });
  }
  const far = Math.hypot(W, H) * 0.7;
  rings.push({ age: 0, life: 0.75, max: far, w: 46 }, { age: -0.08, life: 0.9, max: far * 0.8, w: 18 });
}

// ---------------------------------------------------------------- the build, as shown

function onProgress(p) {
  work.real = Math.max(work.real, p.fraction);
  work.events.push(p);
  if (p.log) work.queue.push({ text: p.log, at: p.fraction });
}

// the stand-in build: its steps when the animation's clock reaches them
function demoStep(dt) {
  const d = work.demo;
  d.at += dt;
  while (d.i < DEMO_STEPS.length && DEMO_STEPS[d.i].at <= d.at) onProgress(DEMO_STEPS[d.i++]);
  if (d.i === DEMO_STEPS.length && !work.done) {
    // done here and now, not when the promise's callbacks get round to it (?at= runs the clock in one go)
    work.demo = null;
    work.done = true;
    work.result = { cue: 'Documents\\Daytona USA Ultimate\\Daytona USA Ultimate.cue', dir: 'Documents\\Daytona USA Ultimate' };
    d.res(work.result);
  }
}

// the counter follows the build no faster than 1/4 of the way a second; each
// segment clicks in as it's reached, each finished step joins the log as passed
// (one a frame, so a run of short steps ripples in)
function pace(dt) {
  work.shown = Math.min(work.real, work.shown + dt * 0.25);
  const lit = Math.floor(work.shown * SEGS + 1e-9);
  while (work.lit < lit) {
    work.litAt[work.lit++] = wall;
    click(1 + 0.15 * (work.lit % 2));
  }
  if (work.queue.length && work.queue[0].at <= work.shown + 1e-9) work.lines.push(work.queue.shift().text);
}

function currentEvent() {
  let ev = null;
  for (const e of work.events) if (e.fraction <= work.shown + 1e-9) ev = e;
  return ev;
}

// ---------------------------------------------------------------- the timeline

function once(name, t, fn) {
  if (clock >= t && !fired.has(name)) { fired.add(name); fn(); }
}

function update(dt) {
  wall += dt;
  for (const s of Object.values(slots)) {
    const want = s.state === 'ok' ? 1 : (hover && slots[hover] === s && mode === 'idle') ? 0.22 : 0;
    s.lit += (want - s.lit) * Math.min(1, dt * 7);
    s.flash = Math.max(0, s.flash - dt * 2);
  }
  if (mode === 'playing') {
    if (work.demo) demoStep(dt);
    if (!released) pace(dt);
    clock = released ? clock + dt : Math.min(T.arcs, clock + dt);
    const t = clock, ps = poses(t);
    once('hum', 0, () => { humStart(); humTo(0.45, T.arcs); });
    if (!released && t >= T.arcs && wall - humAt > 0.5) {
      humAt = wall;
      humTo(0.45 + 0.3 * work.shown, 0.5);
    }
    if (!released && work.done && work.shown >= 1 && !work.queue.length && t >= T.arcs) {
      released = true;
      humTo(1, T.impact - T.arcs);
    }
    // how hot the charge runs: a little while the disc is built, flat out at the slam
    const heat = t < T.arcs ? 0 : released ? lerp(0.35, 1, seg(t, T.arcs, T.impact)) : 0.35 * work.shown;
    if (t < T.arcs) {
      // sparks crawling along the covers' facing edges
      crawlAcc += lerp(3, 16, seg(t, 0, T.arcs)) * dt;
      while (crawlAcc >= 1) {
        crawlAcc -= 1;
        const [p, side] = R() < 0.5 ? [ps.dusa, 1] : [ps.cce, -1];
        const e = innerEdge(p, side);
        const y0 = rand(e.top, e.bottom), y1 = clamp(y0 + rand(-130, 130), e.top, e.bottom);
        bolts.push(makeBolt(e.x, y0, e.x + side * rand(4, 26), y1, { width: 0.55, branches: 1, depth: 5, rough: 0.35 }));
        if (R() < 0.5) crackle(0.08);
      }
    } else if (t < T.impact) {
      // bolts leaping between the covers
      arcAcc += lerp(9, 42, heat) * dt;
      while (arcAcc >= 1) {
        arcAcc -= 1;
        const a = innerEdge(ps.dusa, 1), b = innerEdge(ps.cce, -1);
        bolts.push(makeBolt(a.x, rand(a.top, a.bottom), b.x, rand(b.top, b.bottom),
          { width: lerp(0.8, 1.7, heat), branches: 2 + Math.floor(R() * 3) }));
        flash = Math.max(flash, 0.06 + 0.1 * heat);
        shake = Math.max(shake, 2 + 8 * heat);
        if (R() < 0.7) crackle(0.12 + 0.15 * heat);
        if (Math.random() < 0.12) playSound('zap', { vol: 0.25, rate: 0.8 + Math.random() * 0.7 });
      }
    }
    once('arcs', T.arcs, () => playSound('thunder_tiny', { offset: 0.18, vol: 0.55 }));
    // the strike: a bolt from the sky onto the meeting covers, struck afresh every few frames
    if (t >= T.impact - 0.06 && t < T.burst + 0.4 && t >= strikeAt) {
      strikeAt = t + 0.05;
      bolts.push(makeBolt(W / 2 + rand(-120, 120), -20, W / 2 + rand(-10, 10), centreY(),
        { width: 3.2, branches: 7, life: 0.07, rough: 0.18 }));
    }
    once('impact', T.impact, () => { humStop(); thunderclap(); flash = 1; shake = 30; });
    once('burst', T.burst, () => {
      const ps2 = poses(T.burst), impact = { x: W / 2, y: centreY() };
      shatter(ps2.dusa, impact);
      shatter(ps2.cce, impact);
      burst(impact);
      playSound('glass', { vol: 0.7 });
    });
    once('roar', T.burst + 0.25, roar);
    once('done', T.done, finish);
  } else if (mode === 'done') {
    clock += dt;
  }
  for (const b of bolts) b.age += dt;
  bolts = bolts.filter(b => b.age < b.life);
  for (const s of shards) {
    s.age += dt;
    s.vy += 760 * dt;
    s.x += s.vx * dt;
    s.y += s.vy * dt;
    s.rot += s.vr * dt;
    s.s = Math.max(0.2, s.s + s.vs * dt);
  }
  shards = shards.filter(s => s.age < s.life);
  for (const p of sparks) {
    p.age += dt;
    p.vx *= 1 - 1.4 * dt;
    p.vy = p.vy * (1 - 1.4 * dt) + 520 * dt;
    p.x += p.vx * dt;
    p.y += p.vy * dt;
  }
  sparks = sparks.filter(p => p.age < p.life);
  for (const r of rings) r.age += dt;
  rings = rings.filter(r => r.age < r.life);
  flash = Math.max(0, flash - dt * 2.2);
  shake = Math.max(0, shake - dt * 40);
}

// ---------------------------------------------------------------- drawing

function drawBackground(t) {
  // DUSA's daylight blue on the left, CCE's sunset on the right; one dusk once they're one
  const r = mode === 'idle' ? 0 : seg(t, T.burst, T.burst + 1.4);
  const g = ctx.createLinearGradient(0, 0, W, 0);
  g.addColorStop(0, mix([14, 48, 104], [40, 22, 84], r));
  g.addColorStop(0.5, mix([10, 8, 24], [26, 14, 48], r));
  g.addColorStop(1, mix([92, 30, 50], [84, 34, 52], r));
  ctx.fillStyle = g;
  ctx.fillRect(-50, -50, W + 100, H + 100);
  const v = ctx.createRadialGradient(W / 2, H * 0.45, H * 0.15, W / 2, H * 0.5, Math.max(W, H) * 0.75);
  v.addColorStop(0, 'rgba(0,0,0,0)');
  v.addColorStop(1, 'rgba(0,0,0,0.8)');
  ctx.fillStyle = v;
  ctx.fillRect(-50, -50, W + 100, H + 100);
  // the charge darkens the room
  const dark = mode === 'idle' ? 0 : 0.5 * seg(t, 0, T.arcs) * (1 - seg(t, T.burst, T.burst + 0.8));
  if (dark > 0) {
    ctx.fillStyle = `rgba(0,0,0,${dark})`;
    ctx.fillRect(-50, -50, W + 100, H + 100);
  }
}

function drawFloor(y) {
  const g = ctx.createLinearGradient(0, y, 0, H);
  g.addColorStop(0, 'rgba(5,4,12,0.55)');
  g.addColorStop(0.35, 'rgba(5,4,12,0.92)');
  g.addColorStop(1, 'rgba(5,4,12,1)');
  ctx.fillStyle = g;
  ctx.fillRect(-50, y, W + 100, H - y + 50);
}

function drawLabel(p, slot, alpha) {
  if (alpha <= 0) return;
  const sub = {
    empty: [`${slot.want} · click to choose`, '#bdb8d6'],
    checking: [`checking${'.'.repeat(1 + Math.floor(wall * 3) % 3)}`, '#f2c14e'],
    ok: [`${slot.want} ✓ checked`, '#46d17a'],
    bad: [`not the right disc · click to choose again`, '#ff5a5f'],
  }[slot.state];
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.textAlign = 'center';
  ctx.fillStyle = '#f3f1ff';
  ctx.font = 'italic 900 17px "Arial Black", "Segoe UI Black", sans-serif';
  ctx.fillText(slot.title, p.x, floorY(p) + 34);
  ctx.fillStyle = sub[1];
  ctx.font = '600 13px "Segoe UI", sans-serif';
  ctx.fillText(sub[0], p.x, floorY(p) + 54);
  ctx.restore();
}

function drawRays(cx, cy, a, spin) {
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  ctx.translate(cx, cy);
  ctx.rotate(spin);
  const len = Math.hypot(W, H);
  for (let i = 0; i < 18; i++) {
    ctx.rotate((Math.PI * 2) / 18);
    const col = i % 2 ? '255,170,90' : '120,170,255';     // CCE's sunset, DUSA's sky
    const g = ctx.createLinearGradient(0, 0, len, 0);
    g.addColorStop(0, `rgba(${col},${0.3 * a})`);
    g.addColorStop(0.6, `rgba(${col},${0.05 * a})`);
    g.addColorStop(1, `rgba(${col},0)`);
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(len, -len * 0.07);
    ctx.lineTo(len, len * 0.07);
    ctx.closePath();
    ctx.fill();
  }
  ctx.restore();
}

function newCover(t) {
  const grow = seg(t, T.burst, T.burst + 0.9);
  const settle = Math.max(0, t - (T.burst + 0.9));
  const h = coverH() * 1.2 * lerp(0.25, 1, ease.outBack(grow));
  return { img: art.ultimate, x: W / 2, y: centreY() + Math.sin(settle * 1.4) * 5 * seg(settle, 0, 0.6), h, yaw: 0 };
}

function drawNew(t) {
  const p = newCover(t), a = seg(t, T.burst, T.burst + 0.12);
  const w = p.h * p.img.width / p.img.height;
  drawRays(p.x, p.y, a * lerp(1, 0.55, seg(t, T.burst + 1, T.done + 1)), t * 0.18);
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  const halo = ctx.createRadialGradient(p.x, p.y, p.h * 0.2, p.x, p.y, p.h * 1.1);
  halo.addColorStop(0, `rgba(170,150,255,${0.35 * a})`);
  halo.addColorStop(1, 'rgba(170,150,255,0)');
  ctx.fillStyle = halo;
  ctx.fillRect(p.x - p.h * 1.2, p.y - p.h * 1.2, p.h * 2.4, p.h * 2.4);
  ctx.restore();
  drawReflection(p, 0.2 * a);
  drawFloor(floorY(p));
  ctx.save();
  ctx.globalAlpha = a;
  ctx.shadowColor = 'rgba(0,0,0,0.7)';
  ctx.shadowBlur = 40;
  ctx.shadowOffsetY = 16;
  ctx.drawImage(p.img, p.x - w / 2, p.y - p.h / 2, w, p.h);
  ctx.restore();
  // a glint sweeping across it
  const gl = seg(t, T.glint, T.glint + 0.8);
  if (gl > 0 && gl < 1) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(p.x - w / 2, p.y - p.h / 2, w, p.h);
    ctx.clip();
    ctx.globalCompositeOperation = 'lighter';
    const gx = p.x - w * 0.9 + gl * w * 1.8;
    const g = ctx.createLinearGradient(gx - 90, 0, gx + 90, 0);
    g.addColorStop(0, 'rgba(255,255,255,0)');
    g.addColorStop(0.5, 'rgba(255,255,255,0.45)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.transform(1, 0, -0.35, 1, 0, 0);
    ctx.fillRect(gx - 90 + p.y * 0.35 - p.h, p.y - p.h / 2, 180 + p.h, p.h);
    ctx.restore();
  }
}

function drawShard(s) {
  const fade = clamp(1 - (s.age - s.life * 0.45) / (s.life * 0.55), 0, 1);
  ctx.save();
  ctx.globalAlpha = fade;
  ctx.translate(s.x, s.y);
  ctx.rotate(s.rot);
  ctx.scale(s.s, s.s);
  ctx.beginPath();
  ctx.moveTo(s.poly[0][0], s.poly[0][1]);
  ctx.lineTo(s.poly[1][0], s.poly[1][1]);
  ctx.lineTo(s.poly[2][0], s.poly[2][1]);
  ctx.closePath();
  ctx.save();
  ctx.clip();
  ctx.drawImage(s.img, -s.w / 2 - s.lx, -s.h / 2 - s.ly, s.w, s.h);
  ctx.restore();
  const hot = clamp(1 - s.age / 0.4, 0, 1);
  if (hot > 0) {
    ctx.globalCompositeOperation = 'lighter';
    ctx.strokeStyle = `rgba(190,215,255,${hot})`;
    ctx.lineWidth = 2.5 / s.s;
    ctx.stroke();
  }
  ctx.restore();
}

function drawSparks() {
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  ctx.lineCap = 'round';
  for (const p of sparks) {
    const k = p.age / p.life;
    const [r, g, b] = k < 0.25 ? [255, 255, 255] : k < 0.6 ? [255, 214, 120] : [255, 120, 40];
    ctx.strokeStyle = `rgba(${r},${g},${b},${1 - k})`;
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
    ctx.lineTo(p.x - p.vx * 0.035, p.y - p.vy * 0.035);
    ctx.stroke();
  }
  for (const r of rings) {
    if (r.age < 0) continue;
    const k = r.age / r.life;
    ctx.strokeStyle = `rgba(175,195,255,${0.8 * (1 - k)})`;
    ctx.lineWidth = r.w * (1 - k) + 1;
    ctx.beginPath();
    ctx.arc(W / 2, centreY(), ease.outCubic(k) * r.max, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
}

// ---- the counter: a riveted plate, the step under way, a three-drum odometer,
// a bar of segments that click in, and the last few finished steps

function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

// v from 0 to 100; the ones drum turns with v, each drum above turns as the ones pass 9
function drawOdometer(v, right, top) {
  const dw = 17, dh = 28, n = 3;
  const x0 = right - n * dw - 22;
  ctx.save();
  roundRect(x0 - 5, top, n * dw + 10, dh, 4);
  ctx.fillStyle = '#050409';
  ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.18)';
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.clip();
  ctx.font = '700 21px Consolas, "Cascadia Mono", monospace';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const whole = Math.floor(v), frac = v - whole;
  for (let k = 0; k < n; k++) {
    const place = Math.pow(10, k);
    const digit = Math.floor(v / place) % 10;
    const turning = k === 0 ? frac : (whole % place === place - 1 ? frac : 0);
    const cx = x0 + (n - 1 - k) * dw + dw / 2;
    for (const [d, dy] of [[digit, -turning * dh], [(digit + 1) % 10, (1 - turning) * dh]]) {
      ctx.fillStyle = '#f3f1ff';
      ctx.fillText(String(d), cx, top + dh / 2 + 1 + dy);
    }
  }
  // the drums' curve: dark at their top and bottom
  const g = ctx.createLinearGradient(0, top, 0, top + dh);
  g.addColorStop(0, 'rgba(0,0,0,0.75)');
  g.addColorStop(0.3, 'rgba(0,0,0,0)');
  g.addColorStop(0.7, 'rgba(0,0,0,0)');
  g.addColorStop(1, 'rgba(0,0,0,0.75)');
  ctx.fillStyle = g;
  ctx.fillRect(x0 - 5, top, n * dw + 10, dh);
  ctx.restore();
  ctx.save();
  ctx.fillStyle = '#8f8aa8';
  ctx.font = '700 15px Consolas, "Cascadia Mono", monospace';
  ctx.textBaseline = 'middle';
  ctx.fillText('%', right - 14, top + dh / 2 + 1);
  ctx.restore();
}

function drawPanel(a) {
  if (a <= 0) return;
  const w = Math.min(760, W - 80), h = 150, x = (W - w) / 2, y = H - h - 26 + (1 - a) * 30;
  ctx.save();
  ctx.globalAlpha = a;
  roundRect(x, y, w, h, 10);
  ctx.fillStyle = 'rgba(9,8,18,0.9)';
  ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.14)';
  ctx.lineWidth = 1;
  ctx.stroke();
  for (const [rx, ry] of [[x + 9, y + 9], [x + w - 9, y + 9], [x + 9, y + h - 9], [x + w - 9, y + h - 9]]) {
    ctx.beginPath();
    ctx.arc(rx, ry, 2.6, 0, Math.PI * 2);
    ctx.fillStyle = '#3d3a4c';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(rx - 0.7, ry - 0.7, 1, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.35)';
    ctx.fill();
  }

  // the step under way
  const ev = currentEvent();
  ctx.textBaseline = 'middle';
  ctx.letterSpacing = '2px';
  ctx.font = '800 13px "Segoe UI", sans-serif';
  ctx.fillStyle = '#f3f1ff';
  const stageText = (ev ? ev.stage : 'Starting').toUpperCase();
  ctx.fillText(stageText, x + 24, y + 30);
  if (ev && ev.detail) {
    const sw = ctx.measureText(stageText).width;
    ctx.letterSpacing = '0.5px';
    ctx.font = '500 13px "Segoe UI", sans-serif';
    ctx.fillStyle = '#8f8aa8';
    ctx.fillText(ev.detail, x + 24 + sw + 14, y + 30);
  }
  ctx.letterSpacing = '0px';
  drawOdometer(work.shown * 100, x + w - 18, y + 16);

  // the segments: DUSA's blue through white to CCE's orange, each flashing as it clicks in
  const bx = x + 24, bw = w - 48, by = y + 56, bh = 22, gap = 3;
  const sw = (bw - gap * (SEGS - 1)) / SEGS;
  for (let i = 0; i < SEGS; i++) {
    const sx = bx + i * (sw + gap);
    if (i < work.lit) {
      const age = wall - (work.litAt[i] ?? -9);
      const f = i / (SEGS - 1);
      const col = f < 0.5 ? mix([90, 150, 255], [235, 235, 255], f * 2) : mix([235, 235, 255], [255, 140, 50], f * 2 - 1);
      const drop = age < 0.09 ? (1 - age / 0.09) * 5 : 0;
      ctx.fillStyle = age < 0.12 ? '#ffffff' : col;
      ctx.shadowColor = col;
      ctx.shadowBlur = 8;
      ctx.fillRect(sx, by - drop, sw, bh);
      ctx.shadowBlur = 0;
      ctx.fillStyle = 'rgba(255,255,255,0.25)';
      ctx.fillRect(sx, by - drop, sw, 3);
    } else {
      ctx.fillStyle = 'rgba(255,255,255,0.07)';
      ctx.fillRect(sx, by, sw, bh);
    }
  }

  // the last steps done, the newest brightest
  ctx.font = '500 12.5px Consolas, "Cascadia Mono", monospace';
  const lines = work.lines.slice(-3);
  lines.forEach((l, i) => {
    const k = lines.length - 1 - i;
    ctx.fillStyle = `rgba(200,196,230,${[0.95, 0.55, 0.3][k]})`;
    ctx.fillText(`› ${l}`, x + 24, y + 98 + i * 17);
  });
  ctx.restore();
}

function draw() {
  const t = clock;
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  const sx = (R() - 0.5) * 2 * shake, sy = (R() - 0.5) * 2 * shake;
  ctx.translate(sx, sy);
  drawBackground(t);
  const exploded = mode !== 'idle' && t >= T.burst;
  if (exploded) drawNew(t);
  else {
    const ps = poses(t);
    drawReflection(ps.dusa, 0.22);
    drawReflection(ps.cce, 0.22);
    drawFloor(floorY(ps.cce));
    const labels = mode === 'idle' ? 1 : 1 - seg(t, 0, 0.4);
    drawLabel(ps.dusa, slots.dusa, labels);
    drawLabel(ps.cce, slots.cce, labels);
    drawCover(ps.dusa);
    drawCover(ps.cce);
  }
  shards.forEach(drawShard);
  bolts.forEach(drawBolt);
  drawSparks();
  if (mode === 'playing') {
    drawPanel(seg(wall - playWall, 0.15, 0.55) * (1 - seg(t, T.impact - 0.25, T.impact + 0.1)));
  }
  if (flash > 0) {
    ctx.fillStyle = `rgba(255,255,255,${flash})`;
    ctx.fillRect(-60, -60, W + 120, H + 120);
  }
}

// ---------------------------------------------------------------- controls

function clearStage() {
  bolts = []; shards = []; sparks = []; rings = [];
  flash = shake = crawlAcc = arcAcc = strikeAt = humAt = 0;
  fired.clear();
  released = false;
  Object.assign(work, {
    real: 0, shown: 0, events: [], queue: [], lines: [], lit: 0, litAt: [],
    done: false, result: null, demo: null,
  });
}

function play() {
  if (mode !== 'idle' || !ready()) return;
  clearStage();
  mode = 'playing';
  clock = 0;
  playWall = wall;
  goBtn.classList.add('hidden');
  header.style.opacity = '0';
  setStatus('');
  if (!muted) audio().resume();
  backend.build(slots.cce.path, slots.dusa.path, outDir, onProgress)
    .then(res => { work.done = true; work.result = res; })
    .catch(fail);
}

function finish() {
  mode = 'done';
  setStatus('Daytona USA Ultimate is built. Its cue sheet and tracks are in:', 'good', work.result ? work.result.dir : '');
  goBtn.textContent = 'OPEN';
  goBtn.disabled = false;
  goBtn.classList.remove('hidden');
  header.style.opacity = '1';
}

// the build failed: the charge dies away and the covers stand apart again
function fail(err) {
  humStop();
  clearStage();
  mode = 'idle';
  clock = 0;
  goBtn.textContent = 'COMBINE';
  goBtn.classList.remove('hidden');
  header.style.opacity = '1';
  setStatus(String(err), 'bad');
  goBtn.disabled = !ready();
}

function reset() {
  if (mode === 'playing') return;
  humStop();
  clearStage();
  mode = 'idle';
  clock = 0;
  goBtn.textContent = 'COMBINE';
  goBtn.classList.remove('hidden');
  header.style.opacity = '1';
  statusEl.className = '';
  refresh();
}

goBtn.addEventListener('click', () => {
  if (mode === 'done') backend.reveal(work.result.cue).catch(e => setStatus(String(e), 'bad'));
  else combine();
});

function slotAt(mx, my) {
  if (mode !== 'idle') return null;
  const ps = poses(clock);
  for (const key of ['dusa', 'cce']) {
    const b = coverBox(ps[key]);
    if (mx >= b.x0 && mx <= b.x1 && my >= b.y0 && my <= b.y1) return key;
  }
  return null;
}

stage.addEventListener('mousemove', e => {
  hover = slotAt(e.clientX, e.clientY);
  stage.classList.toggle('pointing', !!hover && !picking && slots[hover].state !== 'checking');
});
stage.addEventListener('mouseleave', () => { hover = null; stage.classList.remove('pointing'); });
stage.addEventListener('click', e => {
  const key = slotAt(e.clientX, e.clientY);
  if (key && slots[key].state !== 'checking') choose(key);
});

window.addEventListener('keydown', e => {
  if (e.code === 'Space') { e.preventDefault(); combine(); }
  else if (e.code === 'KeyR') reset();
  else if (e.code === 'KeyS') slow = !slow;
  else if (e.code === 'KeyM') setMuted(!muted);
});

// the speaker in the corner; the choice is remembered for next time
const muteBtn = document.getElementById('mute');
function setMuted(m) {
  muted = m;
  if (m) humStop();
  muteBtn.classList.toggle('muted', m);
  muteBtn.title = m ? 'Sound off (M)' : 'Sound on (M)';
  muteBtn.setAttribute('aria-label', m ? 'Turn sound on' : 'Mute sound');
  if (FREEZE === null) {
    try { localStorage.setItem('muted', m ? '1' : '0'); } catch (e) { /* not remembered */ }
  }
}
muteBtn.addEventListener('click', () => {
  setMuted(!muted);
  muteBtn.blur();                            // Space is COMBINE, not this button again
  if (!muted) audio().resume();
});
try { if (FREEZE === null && localStorage.getItem('muted') === '1') setMuted(true); } catch (e) { /* sound on */ }

// files dropped on the window: each checked and put on its own cover
if (TAURI && TAURI.webview) {
  TAURI.webview.getCurrentWebview().onDragDropEvent(e => {
    if (e.payload.type === 'drop' && mode === 'idle') e.payload.paths.forEach(p => check(p, null));
  });
}

// ---------------------------------------------------------------- start

let last = 0;
function frame(now) {
  if (window.innerWidth !== W || window.innerHeight !== H) resize();
  const dt = Math.min(0.05, (now - last) / 1000 || 0) * (slow ? 0.25 : 1);
  last = now;
  update(dt);
  draw();
  requestAnimationFrame(frame);
}

Promise.all([load('dusa', 'art/dusa.jpg'), load('cce', 'art/cce.jpg'), load('ultimate', 'art/ultimate.jpg')]).then(() => {
  art.dusaGrey = greyCopy(art.dusa);
  art.cceGrey = greyCopy(art.cce);
  if (FREEZE !== null) {
    resize();
    if (FREEZE > 0) {
      play();
      for (let i = 0; i * (1 / 60) < FREEZE; i++) update(1 / 60);
    } else {
      refresh();
    }
    frozen = true;
    draw();
    return;
  }
  refresh();
  backend.outDir().then(d => { outDir = d; refresh(); });
  for (const name of ['thunder_snap', 'thunder_tiny', 'buzz_loop', 'zap', 'glass', 'roar']) loadSound(name, `sfx/${name}.mp3`);
  requestAnimationFrame(frame);
});
