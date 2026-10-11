#!/usr/bin/env node
/*
 * compare-classic.js — تست رگرسیون گرافیک.
 *
 * نسخه‌ی پایه (بدون لایه‌ی نئون) و نسخه‌ی نئون را در حالت «نئون خاموش» با
 * تصادفیِ قطعی (یک seed) رندر می‌کند و پیکسل‌به‌پیکسل مقایسه می‌کند.
 * انتظار: تفاوت صفر — یعنی وقتی نئون خاموش است، بازی دقیقاً همان ظاهر قبلی است.
 *
 * اجرا:  node tools/compare-classic.js
 */
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");
const { createCanvas, loadImage } = require("@napi-rs/canvas");

const ROOT = path.join(__dirname, "..");
const tmpA = fs.mkdtempSync(path.join(os.tmpdir(), "base-"));
const tmpB = fs.mkdtempSync(path.join(os.tmpdir(), "neon-"));
const SEED = "20251011";

console.log("• رندر نسخه‌ی پایه…");
execFileSync(process.execPath, [path.join(__dirname, "render-frames.js"), path.join(ROOT, "game/src/adventure-world.base.html"), tmpA, "--seed=" + SEED], { stdio: "ignore" });
console.log("• رندر نسخه‌ی نئون (حالت خاموش)…");
execFileSync(process.execPath, [path.join(__dirname, "render-frames.js"), path.join(ROOT, "game/index.html"), tmpB, "--seed=" + SEED], { stdio: "ignore" });

(async () => {
    const files = fs.readdirSync(tmpA).filter((f) => f.includes("classic")).sort();
    let failed = 0;
    for (const f of files) {
        const [a, b] = await Promise.all([loadImage(path.join(tmpA, f)), loadImage(path.join(tmpB, f))]);
        const ca = createCanvas(a.width, a.height);
        const cb = createCanvas(b.width, b.height);
        ca.getContext("2d").drawImage(a, 0, 0);
        cb.getContext("2d").drawImage(b, 0, 0);
        const da = ca.getContext("2d").getImageData(0, 0, a.width, a.height).data;
        const db = cb.getContext("2d").getImageData(0, 0, b.width, b.height).data;
        let diff = 0;
        for (let i = 0; i < da.length; i += 4) {
            if (da[i] !== db[i] || da[i + 1] !== db[i + 1] || da[i + 2] !== db[i + 2] || da[i + 3] !== db[i + 3]) diff++;
        }
        console.log(`  ${diff === 0 ? "✓" : "✗"} ${f}: ${diff} پیکسل متفاوت`);
        if (diff !== 0) failed++;
    }
    console.log(failed === 0
        ? "=== قبول: با نئونِ خاموش، گرافیک عیناً همان نسخه‌ی قبلی است ==="
        : `=== رد: ${failed} تصویر تفاوت دارد ===`);
    fs.rmSync(tmpA, { recursive: true, force: true });
    fs.rmSync(tmpB, { recursive: true, force: true });
    process.exit(failed === 0 ? 0 : 1);
})();
