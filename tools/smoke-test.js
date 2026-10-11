#!/usr/bin/env node
/*
 * smoke-test.js — اجرای واقعی بازی در Node با شبیه‌سازی canvas/DOM.
 *
 * هدف: گرفتن خطاهای runtime (تابع تعریف‌نشده، متغیر اشتباه، مسیر رندر شکسته)
 * بدون نیاز به مرورگر. چند صد فریم در منو، همه‌ی فصل‌ها و همه‌ی صفحه‌ها
 * اجرا می‌شود و هر استثنا با استک گزارش می‌شود.
 *
 * اجرا:  node tools/smoke-test.js [game/index.html] [--frames=120]
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const file = process.argv[2] && !process.argv[2].startsWith("--")
    ? process.argv[2]
    : path.join(__dirname, "..", "game", "index.html");
const framesArg = process.argv.find((a) => a.startsWith("--frames="));
const FRAMES = framesArg ? parseInt(framesArg.split("=")[1], 10) : 120;

const html = fs.readFileSync(file, "utf8");
const script = html.match(/<script[^>]*>([\s\S]*?)<\/script>/);
if (!script) { console.error("no <script> found"); process.exit(1); }
const code = script[1] + `
// ---- پل تست: دسترسی به متغیرهای اسکوپِ اسکریپت از بیرون ----
globalThis.__game = {
  get keys() { return keys; },
  get player() { return player; },
  get gameState() { return gameState; }, set gameState(v) { gameState = v; },
  get neonFX() { return neonFX; },
  get currentSeason() { return currentSeason; }, set currentSeason(v) { currentSeason = v; },
  get SEASON_COUNT() { return SEASON_COUNT; },
  get neonBufA() { return neonBufA; },
  get neonBufB() { return neonBufB; },
  get particleCount() { return particles.length; },
  initLevel, doJump, setNeon, setGfxQuality, neonOn, resizeGame, gameLoop,
  startEndlessFloor: (typeof startEndlessFloor === "function") ? startEndlessFloor : null
};`;

// ---------------------------------------------------------------- DOM mocks
const noop = () => { };

// --- ماک صوتی با مقادیر عددی واقعی (Web Audio + Audio) ---
function makeAudioMock() {
    const node = () => ({
        connect: (x) => x, disconnect: () => { }, start: () => { }, stop: () => { },
        gain: { value: 1, setValueAtTime: () => { }, linearRampToValueAtTime: () => { }, exponentialRampToValueAtTime: () => { }, cancelScheduledValues: () => { } },
        frequency: { value: 440, setValueAtTime: () => { }, linearRampToValueAtTime: () => { }, exponentialRampToValueAtTime: () => { } },
        Q: { value: 1 }, detune: { value: 0 }, pan: { value: 0 }, playbackRate: { value: 1 },
        type: "sine", buffer: null, loop: false, curve: null, oversample: "none",
        threshold: { value: -24 }, knee: { value: 30 }, ratio: { value: 12 }, attack: { value: 0.003 }, release: { value: 0.25 },
        onended: null
    });
    return {
        sampleRate: 44100, currentTime: 0, state: "running",
        destination: node(), listener: {},
        createGain: node, createOscillator: node, createBufferSource: node, createBiquadFilter: node,
        createDynamicsCompressor: node, createStereoPanner: node, createWaveShaper: node,
        createDelay: node, createConvolver: node, createAnalyser: node, createPanner: node, createChannelMerger: node,
        createBuffer: (ch, len, rate) => ({
            length: len, numberOfChannels: ch, sampleRate: rate, duration: len / (rate || 44100),
            getChannelData: () => new Float32Array(len), copyToChannel: () => { }
        }),
        resume: () => Promise.resolve(), close: () => Promise.resolve(), suspend: () => Promise.resolve()
    };
}
function makeAudioElementMock() {
    return {
        src: "", volume: 1, loop: false, currentTime: 0, paused: true, muted: false,
        play: () => Promise.resolve(), pause: () => { }, load: () => { },
        addEventListener: () => { }, removeEventListener: () => { }, cloneNode() { return makeAudioElementMock(); }
    };
}


function makeCtx() {
    const store = {
        fillStyle: "#000", strokeStyle: "#000", lineWidth: 1, lineCap: "butt", lineJoin: "miter",
        globalAlpha: 1, globalCompositeOperation: "source-over", font: "10px sans-serif",
        textAlign: "start", textBaseline: "alphabetic", direction: "ltr", filter: "none",
        imageSmoothingEnabled: true, shadowColor: "transparent", shadowBlur: 0,
        shadowOffsetX: 0, shadowOffsetY: 0, miterLimit: 10, lineDashOffset: 0
    };
    const grad = { addColorStop: noop };
    const handler = {
        get(t, k) {
            if (k in store) return store[k];
            if (k === "measureText") return () => ({ width: 24 });
            if (k === "createLinearGradient" || k === "createRadialGradient" || k === "createConicGradient") return () => grad;
            if (k === "createPattern") return () => ({ setTransform: noop });
            if (k === "getImageData") return () => ({ data: new Uint8ClampedArray(4), width: 1, height: 1 });
            if (k === "canvas") return t.__canvas;
            if (typeof k === "symbol") return undefined;
            return noop;
        },
        set(t, k, v) { store[k] = v; return true; }
    };
    return new Proxy({}, handler);
}

const listeners = { window: {}, canvas: {} };
function makeCanvas(w, h) {
    const c = {
        width: w || 800, height: h || 450, style: {},
        classList: { add: noop, remove: noop, contains: () => false },
        addEventListener: (t, fn) => { (listeners.canvas[t] = listeners.canvas[t] || []).push(fn); },
        removeEventListener: noop,
        getBoundingClientRect: () => ({ left: 0, top: 0, right: 800, bottom: 450, width: 800, height: 450 }),
        focus: noop, requestFullscreen: noop
    };
    const ctx = makeCtx();
    ctx.__canvas = c;
    c.getContext = () => ctx;
    return c;
}

const mainCanvas = makeCanvas(800, 450);
const documentMock = {
    getElementById: (id) => (id === "gameCanvas" || id === "canvas" ? mainCanvas : { style: {}, appendChild: noop, textContent: "" }),
    createElement: (tag) => (tag === "canvas" ? makeCanvas(1, 1) : { style: {}, appendChild: noop }),
    addEventListener: (t, fn) => { (listeners.document = listeners.document || {})[t] = (listeners.document?.[t] || []).concat(fn); },
    removeEventListener: noop,
    documentElement: { requestFullscreen: noop, webkitRequestFullscreen: noop, style: {} },
    fullscreenElement: null,
    hidden: false,
    body: { appendChild: noop, style: {} },
    querySelector: () => null,
    visibilityState: "visible"
};

const storeMap = new Map();
const localStorageMock = {
    getItem: (k) => (storeMap.has(k) ? storeMap.get(k) : null),
    setItem: (k, v) => storeMap.set(k, String(v)),
    removeItem: (k) => storeMap.delete(k),
    clear: () => storeMap.clear()
};

function deepStub() {
    const fn = function () { return deepStub(); };
    return new Proxy(fn, {
        get(t, k) {
            if (k === "value") return 0;
            if (k === "currentTime") return 0;
            if (k === Symbol.toPrimitive) return () => 0;
            if (typeof k === "symbol") return undefined;
            return deepStub();
        },
        set: () => true,
        apply: () => deepStub(),
        construct: () => deepStub()
    });
}

const rafQueue = [];
const sandbox = {
    console,
    Math, Date, JSON, Object, Array, String, Number, Boolean, Error, RegExp, Map, Set, Promise, Symbol,
    Intl, isNaN, isFinite, parseInt, parseFloat, Uint8ClampedArray, Uint8Array, Float32Array, ArrayBuffer, TextEncoder,
    setTimeout: (fn) => { try { fn(); } catch (e) { throw e; } return 0; },
    clearTimeout: noop, setInterval: () => 0, clearInterval: noop,
    requestAnimationFrame: (fn) => { rafQueue.push(fn); return rafQueue.length; },
    cancelAnimationFrame: noop,
    performance: { now: () => Date.now() },
    document: documentMock,
    localStorage: localStorageMock,
    navigator: { userAgent: "node-smoke-test", serviceWorker: undefined, standalone: false, vibrate: noop },
    screen: { orientation: { lock: () => Promise.resolve(), unlock: noop, type: "landscape-primary" }, width: 900, height: 450 },
    Audio: function Audio() { return makeAudioElementMock(); },
    AudioContext: function AudioContext() { return makeAudioMock(); },
    webkitAudioContext: function webkitAudioContext() { return makeAudioMock(); },
    fetch: () => Promise.resolve({ json: () => Promise.resolve([]), text: () => Promise.resolve("") }),
    matchMedia: () => ({ matches: false, addEventListener: noop, addListener: noop }),
    location: { href: "http://localhost/", reload: noop },
    alert: noop, prompt: () => null, confirm: () => false
};
sandbox.window = sandbox;
sandbox.self = sandbox;
sandbox.globalThis = sandbox;
sandbox.window.innerWidth = 900;
sandbox.window.innerHeight = 450;
sandbox.window.devicePixelRatio = 1;
sandbox.window.addEventListener = (t, fn) => { (listeners.window[t] = listeners.window[t] || []).push(fn); };
sandbox.window.removeEventListener = noop;
sandbox.window.matchMedia = sandbox.matchMedia;
sandbox.window.screen = sandbox.screen;
sandbox.window.navigator = sandbox.navigator;

// ------------------------------------------------------------------ run
const ctx = vm.createContext(sandbox);
let errors = 0;
function step(label) {
    let q = rafQueue.splice(0, rafQueue.length);
    if (!q.length) {
        // حلقه‌ی rAF مثل مرورگر باید خودش را ادامه بدهد
        const gl = sandbox.__game && sandbox.__game.gameLoop;
        if (gl) { q = [gl]; } else { console.log(`  ⚠ no rAF callback queued at ${label}`); return; }
    }
    for (const fn of q) {
        try { fn(Date.now()); }
        catch (e) { errors++; console.log(`  ✗ ${label}: ${e && e.message}\n${(e && e.stack || "").split("\n").slice(1, 4).join("\n")}`); }
    }
}

try {
    vm.runInContext(code, ctx, { filename: "game.js" });
    console.log("• script evaluated");
} catch (e) {
    console.error("✗ evaluation failed:", e.message);
    console.error((e.stack || "").split("\n").slice(0, 6).join("\n"));
    process.exit(1);
}

const g = sandbox.__game;
const run = (state, n, prep) => {
    try { if (prep) prep(); } catch (e) { errors++; console.log(`  ✗ prep for ${state}: ${e.message}`); }
    g.gameState = state;
    for (let i = 0; i < n; i++) step(`${state}#${i}`);
};

console.log("• menu:", FRAMES, "frames");
run("menu", FRAMES);

for (const s of ["modeSelect", "levels", "shop", "settings", "audioSettings", "gfxSettings", "wheel", "daily", "endlessTower", "paused", "win", "lose", "tutorial"]) {
    run(s, 4);
}

// همه‌ی فصل‌ها: منو + گیم‌پلی واقعی روی هر مرحله
for (let season = 1; season <= (g.SEASON_COUNT || 6); season++) {
    g.currentSeason = season;
    run("menu", 6);
    run("playing", 40, () => { g.initLevel(1); g.gameState = "playing"; });
    run("playing", 40, () => { g.keys.right = true; });
    run("playing", 30, () => { g.keys.right = false; g.keys.left = true; g.doJump(); });
    g.keys.left = false;
}

// نئون خاموش: مسیر بدون بلوم هم باید سالم باشد
run("playing", 20, () => { if (g.setNeon) g.setNeon(false); });
run("menu", 10);
run("playing", 20, () => { if (g.setNeon) g.setNeon(true); });

// کیفیت پایین/متوسط: مسیرهای qMul
for (const q of ["low", "medium", "high"]) {
    run("playing", 20, () => g.setGfxQuality(q));
}

// سفر بین همه‌ی مراحل هر فصل برای اطمینان از سالم بودن سطح‌ها
try {
    g.currentSeason = 4;
    for (let lv = 1; lv <= 25; lv++) { g.initLevel(lv); g.gameState = "playing"; step("lv" + lv); }
    g.currentSeason = 5;
    for (let lv = 1; lv <= 25; lv++) { g.initLevel(lv); g.gameState = "playing"; step("space lv" + lv); }
    g.currentSeason = 6;
    for (let lv = 1; lv <= 25; lv++) { g.initLevel(lv); g.gameState = "playing"; step("venus lv" + lv); }
} catch (e) { errors++; console.log("  ✗ level sweep:", e.message); }

// دانجن (طبقه‌ی بی‌نهایت)
try { if (g.startEndlessFloor) { g.startEndlessFloor(1); step("endless"); } } catch (e) { errors++; console.log("  ✗ endless:", e.message); }

// بررسی سلامت بافرهای بلوم
try {
    const A = g.neonBufA, B = g.neonBufB;
    if (g.neonOn()) {
        if (!A || !A.width || !B || !B.width) { errors++; console.log("  ✗ bloom buffers not sized"); }
        else if (A.width !== Math.max(64, Math.round(mainCanvas.width / 4))) { errors++; console.log("  ✗ bloom buffer scale wrong:", A.width); }
        else console.log(`• bloom buffers ok: ${A.width}x${A.height} (canvas ${mainCanvas.width}x${mainCanvas.height})`);
    }
    console.log("• neonFX =", g.neonFX, "| neonOn() =", g.neonOn());
} catch (e) { errors++; console.log("  ✗ bloom check:", e.message); }

console.log(errors === 0 ? "\n=== SMOKE TEST PASSED ===" : `\n=== SMOKE TEST FAILED (${errors} errors) ===`);
process.exit(errors === 0 ? 0 : 1);
