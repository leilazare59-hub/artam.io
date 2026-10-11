#!/usr/bin/env node
/*
 * render.js — رندر آفلاین فریم‌های واقعی بازی با Skia (@napi-rs/canvas)
 * برای بازرسی بصری بدون مرورگر. خروجی: PNG در پوشه‌ی shots/
 *
 * اجرا:  node render.js <مسیر index.html> <پوشه خروجی>
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { createCanvas } = require("@napi-rs/canvas");

const ROOT = path.join(__dirname, "..");
const htmlFile = process.argv[2] && !process.argv[2].startsWith("--")
    ? process.argv[2] : path.join(ROOT, "game", "index.html");
const outDir = process.argv[3] && !process.argv[3].startsWith("--")
    ? process.argv[3] : path.join(ROOT, "docs", "neon-preview");
fs.mkdirSync(outDir, { recursive: true });

const html = fs.readFileSync(htmlFile, "utf8");
const code = html.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1] + `
globalThis.__game = {
  get keys() { return keys; }, get player() { return player; },
  get gameState() { return gameState; }, set gameState(v) { gameState = v; },
  get currentSeason() { return currentSeason; }, set currentSeason(v) { currentSeason = v; },
  get neonFX() { return typeof neonFX === "undefined" ? false : neonFX; },
  get coins() { return coins; },
  initLevel, doJump, setGfxQuality, gameLoop,
  setNeon: (typeof setNeon === "function") ? setNeon : null
};`;

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


function makeGame() {
    const main = createCanvas(800, 450);
    const listeners = { window: {}, canvas: {}, document: {} };
    // بوم واقعی Skia + رفتار DOM روی همان شیء (مثل مرورگر: بوم همان المان است)
    const canvasEl = main;
    canvasEl.addEventListener = (t, fn) => { (listeners.canvas[t] = listeners.canvas[t] || []).push(fn); };
    canvasEl.removeEventListener = noop;
    canvasEl.getBoundingClientRect = () => ({ left: 0, top: 0, right: 800, bottom: 450, width: 800, height: 450 });
    canvasEl.focus = noop; canvasEl.requestFullscreen = noop;
    canvasEl.style = {}; canvasEl.classList = { add: noop, remove: noop, contains: () => false };
    const storeMap = new Map();
    const deepStub = () => new Proxy(function () { return deepStub(); }, {
        get(t, k) { if (k === "value" || k === "currentTime") return 0; if (typeof k === "symbol") return undefined; return deepStub(); },
        set: () => true, apply: () => deepStub(), construct: () => deepStub()
    });
    const rafQueue = [];
    const sandbox = {
        console, Math, Date, JSON, Object, Array, String, Number, Boolean, Error, RegExp, Map, Set, Promise, Symbol,
        Intl, isNaN, isFinite, parseInt, parseFloat, Uint8ClampedArray, Uint8Array, Float32Array, ArrayBuffer, TextEncoder,
        setTimeout: (fn) => { fn(); return 0; }, clearTimeout: noop, setInterval: () => 0, clearInterval: noop,
        requestAnimationFrame: (fn) => rafQueue.push(fn),
        cancelAnimationFrame: noop,
        performance: { now: () => Date.now() },
        localStorage: {
            getItem: (k) => (storeMap.has(k) ? storeMap.get(k) : null),
            setItem: (k, v) => storeMap.set(k, String(v)),
            removeItem: (k) => storeMap.delete(k), clear: () => storeMap.clear()
        },
        navigator: { userAgent: "node", serviceWorker: undefined, standalone: false, vibrate: noop },
        screen: { orientation: { lock: () => Promise.resolve(), type: "landscape-primary" }, width: 1280, height: 720 },
        Audio: function () { return makeAudioElementMock(); },
        AudioContext: function () { return makeAudioMock(); },
        webkitAudioContext: function () { return makeAudioMock(); },
        fetch: () => Promise.resolve({ json: () => Promise.resolve([]) }),
        matchMedia: () => ({ matches: false, addEventListener: noop, addListener: noop }),
        location: { href: "http://localhost/" },
        alert: noop, prompt: () => null, confirm: () => false,
        document: {
            getElementById: () => canvasEl,
            createElement: (tag) => (tag === "canvas" ? createCanvas(1, 1) : { style: {}, appendChild: noop }),
            addEventListener: (t, fn) => { (listeners.document[t] = listeners.document[t] || []).push(fn); },
            removeEventListener: noop,
            documentElement: { requestFullscreen: noop, webkitRequestFullscreen: noop, style: {} },
            fullscreenElement: null, hidden: false, visibilityState: "visible",
            body: { appendChild: noop, style: {} }, querySelector: () => null
        }
    };
    sandbox.window = sandbox; sandbox.self = sandbox; sandbox.globalThis = sandbox;
    if (SEED !== null) {                     // Math.random قطعی برای مقایسه‌ی پیکسل‌به‌پیکسل
        const M = Object.create(Math);
        M.random = mulberry32(SEED);
        sandbox.Math = M;
    }
    sandbox.innerWidth = 1280; sandbox.innerHeight = 720; sandbox.devicePixelRatio = 1;
    sandbox.addEventListener = (t, fn) => { (listeners.window[t] = listeners.window[t] || []).push(fn); };
    sandbox.removeEventListener = noop;
    sandbox.matchMedia = sandbox.matchMedia;
    const ctx = vm.createContext(sandbox);
    vm.runInContext(code, ctx, { filename: "game.js" });

    const pump = () => {
        const q = rafQueue.splice(0, rafQueue.length);
        if (!q.length) { if (sandbox.__game.gameLoop) q.push(sandbox.__game.gameLoop); }
        for (const fn of q) fn(Date.now());
    };
    return { sandbox, main, canvasEl, pump, g: sandbox.__game };
}

function save(canvas, name) {
    const p = path.join(outDir, name + ".png");
    fs.writeFileSync(p, canvas.toBuffer("image/png"));
    console.log("  →", path.basename(p));
}

// --seed=N : تصادفیِ قطعی (برای تست دقیق رگرسیون گرافیک)
const seedArg = process.argv.find((a) => a.startsWith("--seed="));
const SEED = seedArg ? parseInt(seedArg.split("=")[1], 10) : null;
function mulberry32(a) {
    return function () {
        a |= 0; a = (a + 0x6D2B79F5) | 0;
        let t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

const scenes = [
    { name: "01-menu-neon", setup: (g) => { }, frames: 70 },
    { name: "02-menu-classic", setup: (g) => { if (g.setNeon) g.setNeon(false); }, frames: 70 },
    { name: "03-levels-neon", setup: (g) => { g.gameState = "levels"; }, frames: 20 },
    { name: "04-shop-neon", setup: (g) => { g.gameState = "shop"; }, frames: 20 },
    { name: "05-gfxsettings-neon", setup: (g) => { g.gameState = "gfxSettings"; }, frames: 12 },
    { name: "10-spring-neon", season: 1, play: true, frames: 90 },
    { name: "11-spring-classic", season: 1, play: true, classic: true, frames: 90 },
    { name: "12-summer-neon", season: 2, play: true, frames: 90 },
    { name: "13-autumn-neon", season: 3, play: true, frames: 90 },
    { name: "14-winter-neon", season: 4, play: true, frames: 90 },
    { name: "15-space-neon", season: 5, play: true, frames: 90 },
    { name: "16-venus-neon", season: 6, play: true, frames: 90 },
    { name: "17-winter-classic", season: 4, play: true, classic: true, frames: 90 },
    { name: "18-space-classic", season: 5, play: true, classic: true, frames: 90 }
];

for (const sc of scenes) {
    const { main, pump, g } = makeGame();
    if (sc.classic && g.setNeon) g.setNeon(false);   // نسخه‌ی پایه اصلاً نئون ندارد
    if (sc.setup) sc.setup(g);
    if (sc.play) {
        g.currentSeason = sc.season;
        g.initLevel(1);
        g.gameState = "playing";
        for (let i = 0; i < 25; i++) pump();
        g.keys.right = true;
        for (let i = 0; i < sc.frames; i++) pump();
        g.keys.right = false;
        for (let i = 0; i < 8; i++) pump();     // بایستد تا انیمیشن حالت عادی بگیرد
    } else {
        for (let i = 0; i < sc.frames; i++) pump();
    }
    console.log(sc.name);
    save(main, sc.name);
}
console.log("done");
