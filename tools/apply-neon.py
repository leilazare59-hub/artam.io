#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply-neon.py — لایه‌ی گرافیکی «نئون» را روی بازی «دنیای ماجراجویی» می‌نشاند.

    game/src/adventure-world.base.html   →   game/index.html

سورس اصلی هرگز تغییر نمی‌کند؛ هر بار خروجی از صفر ساخته می‌شود، پس اسکریپت
idempotent است و همیشه می‌توان با حذف game/index.html به حالت اول برگشت.

اجرا:  python3 tools/apply-neon.py
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "game" / "src" / "adventure-world.base.html"
OUT = ROOT / "game" / "index.html"

MARKER = "NEON GFX ENGINE"

# ---------------------------------------------------------------------------
# موتور نئون — این بلوک پیش از gameLoop تزریق می‌شود
# ---------------------------------------------------------------------------
NEON_ENGINE = r"""// ===================== NEON GFX ENGINE =====================
// لایه‌ی گرافیکی نئون: بلوم، وینیت، اسکن‌لاین، شفق، پالت شبانه، دنباله‌ی نورانی و افکت‌های محیطی.
// کاملاً روی همان Canvas 2D و همان منطق بازی سوار شده؛ هیچ تغییری در گیم‌پلی نمی‌دهد.
// با «کیفیت گرافیک = پایین» یا کلید Neon FX در تنظیمات گرافیک خاموش می‌شود.
let neonFX = true;
const NEON_ACCENT = {
    spring: "#5BF7C4", summer: "#FFCE6B", autumn: "#FF8A4C", winter: "#7FE9FF",
    space: "#B98CFF", venus: "#FF6B4A", dungeon: "#63F5E0"
};
// پالت شبانه‌ی هر فصل: زمین/تپه‌ها به‌جای رنگ‌های روز، تیره و اشباع با لبه‌های درخشان
const NEON_THEMES = {
    spring: { ground: "#16453A", groundTop: "#23B58C", groundLine: "#57FFD0", pitWater: "#0D3B4F", dirt: "#0F2B24", hillFar: "#17224E", hillNear: "#1F2D63", grassBlade: "#63FFD8" },
    summer: { ground: "#3A2A12", groundTop: "#C9873A", groundLine: "#FFC46B", pitWater: "#123C52", dirt: "#2A1D0C", hillFar: "#33224E", hillNear: "#43295E", grassBlade: "#FFD08A" },
    autumn: { ground: "#3A1810", groundTop: "#C2612A", groundLine: "#FF8A4C", pitWater: "#163A48", dirt: "#26100A", hillFar: "#3A1B33", hillNear: "#4A2140", grassBlade: "#FF9A5C" },
    winter: { ground: "#16303F", groundTop: "#A8E6FF", groundLine: "#7FE9FF", pitWater: "#0E4A6B", dirt: "#0F2230", hillFar: "#172A4D", hillNear: "#1E3A66", grassBlade: "#CFF3FF" },
    space: { ground: "#26283A", groundTop: "#8E93B8", groundLine: "#B98CFF", pitWater: "#0A0620", dirt: "#161726", hillFar: "#1A1C36", hillNear: "#23264A", grassBlade: "#C0A6FF" },
    venus: { ground: "#331005", groundTop: "#A8431A", groundLine: "#FF6B4A", pitWater: "#FF7043", dirt: "#230A03", hillFar: "#3A1420", hillNear: "#521B26", grassBlade: "#FF8156" },
    dungeon: { ground: "#1B1D26", groundTop: "#4A4F66", groundLine: "#63F5E0", pitWater: "#0A0A12", dirt: "#12131B", hillFar: "#15161F", hillNear: "#1E2029", grassBlade: "#63F5E0" }
};
// انتخاب تم رنگ صحنه: پالت نئون (شب) یا پالت اصلی روز
function TH(s) { return (neonOn() && NEON_THEMES[s]) ? NEON_THEMES[s] : THEMES[s]; }
function neonOn() { return neonFX && gfxQuality !== "low"; }
function neonA(s) { return NEON_ACCENT[s] || NEON_ACCENT.spring; }
function setNeon(on) { neonFX = !!on; saveGame(); }
// "#RRGGBB" + شفافیت → "rgba(...)"
function neonRGBA(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    return "rgba(" + ((n >> 16) & 255) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + a + ")";
}
// گرادیان‌های آسمان: بسته به وضعیت نئون، نسخه‌ی روز یا نسخه‌ی نئونی (کلید کش جداگانه دارد)
function neonSky(key, y0, y1, normal, neon) {
    if (neonOn()) return vGrad(key + "N", y0, y1, neon);
    return vGrad(key, y0, y1, normal);
}
// هاله‌ی درخشان دور اجسام نورانی — سه حلقه‌ی ارزان به‌جای گرادیان گران‌قیمت
function neonHalo(x, y, r, color, a) {
    ctx.save(); ctx.globalCompositeOperation = "lighter";
    ctx.fillStyle = neonRGBA(color, 0.10 * a); ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = neonRGBA(color, 0.15 * a); ctx.beginPath(); ctx.arc(x, y, r * 0.62, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = neonRGBA(color, 0.22 * a); ctx.beginPath(); ctx.arc(x, y, r * 0.32, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
}
// --- بافرهای بلوم در مقیاس ۱/۴ صفحه: فوق‌سریع، حتی روی گوشی‌های متوسط ---
const neonBufA = document.createElement("canvas"), neonBufB = document.createElement("canvas");
const neonCtxA = neonBufA.getContext("2d"), neonCtxB = neonBufB.getContext("2d");
let neonBufW = 0, neonBufH = 0;
function neonSyncBuffers() {
    const w = Math.max(64, Math.round(canvas.width / 4)), h = Math.max(36, Math.round(canvas.height / 4));
    if (w === neonBufW && h === neonBufH) return;
    neonBufW = neonBufA.width = neonBufB.width = w;
    neonBufH = neonBufA.height = neonBufB.height = h;
}
function neonBloom() {
    neonSyncBuffers();
    const w = neonBufW, h = neonBufH;
    // ۱) صحنه‌ی کوچک‌شده
    neonCtxB.globalCompositeOperation = "copy"; neonCtxB.globalAlpha = 1; neonCtxB.filter = "none";
    neonCtxB.drawImage(canvas, 0, 0, w, h);
    // ۲) آستانه‌ی روشنایی: رنگ در خودش ضرب می‌شود تا فقط بخش‌های روشن باقی بمانند
    neonCtxA.globalCompositeOperation = "copy"; neonCtxA.drawImage(neonBufB, 0, 0);
    neonCtxA.globalCompositeOperation = "multiply"; neonCtxA.drawImage(neonBufB, 0, 0);
    // ۳) محو کردن تا نور پخش شود
    neonCtxB.globalCompositeOperation = "copy"; neonCtxB.filter = "blur(3px)";
    neonCtxB.drawImage(neonBufA, 0, 0); neonCtxB.filter = "none";
    // ۴) افزودن درخشش روی تصویر اصلی — دو لایه: تیز + پخش‌شده
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.imageSmoothingEnabled = true;
    ctx.globalAlpha = 0.28; ctx.drawImage(neonBufA, 0, 0, canvas.width, canvas.height);
    ctx.globalAlpha = 0.45; ctx.drawImage(neonBufB, 0, 0, canvas.width, canvas.height);
    ctx.restore();
}
// --- وینیت، اسکن‌لاین و تینت رنگی ---
let neonVigGrad = null, neonVigKey = "", neonScanPattern = null;
function neonOverlay() {
    const W = canvas.width, H = canvas.height;
    const key = W + "x" + H;
    if (neonVigKey !== key) {
        neonVigKey = key;
        const g = ctx.createRadialGradient(W / 2, H * 0.46, Math.min(W, H) * 0.32, W / 2, H * 0.52, Math.max(W, H) * 0.78);
        g.addColorStop(0, "rgba(0,0,0,0)");
        g.addColorStop(0.62, "rgba(9,4,26,0.16)");
        g.addColorStop(1, "rgba(5,2,18,0.62)");
        neonVigGrad = g;
        const t = document.createElement("canvas"); t.width = 4; t.height = 4;
        const tc = t.getContext("2d");
        tc.fillStyle = "rgba(0,0,0,0.09)"; tc.fillRect(0, 0, 4, 1);
        neonScanPattern = ctx.createPattern(t, "repeat");
    }
    ctx.save();
    ctx.fillStyle = neonVigGrad; ctx.fillRect(0, 0, W, H);
    // تینت ملایم در رنگ فصل روی کل صحنه (حس نئون یکپارچه)
    ctx.globalCompositeOperation = "overlay";
    ctx.globalAlpha = 0.055;
    ctx.fillStyle = neonA(getSeason()); ctx.fillRect(0, 0, W, H);
    if (gfxQuality === "high" && neonScanPattern) {
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = 0.55;
        ctx.fillStyle = neonScanPattern; ctx.fillRect(0, 0, W, H);
    }
    ctx.restore();
}
function neonPost() { if (!neonOn()) return; neonBloom(); neonOverlay(); }

// --- آسمان نئونی: ستاره، شفق، درخشش افق، اخگر و سنگ‌نوشته ---
function drawNeonSky() {
    const s = getSeason(), W = canvas.width, H = canvas.height, acc = neonA(s);
    if (s === "venus") {
        // اخگرهای بالارونده در آسمان زهره
        for (let i = 0; i < Math.round(20 * qMul()); i++) {
            const sd = i * 3.9;
            const fx = ((hash01(sd) * W - player.worldX * 0.1) % W + W) % W;
            const fy = H - ((globalFrame * (0.5 + hash01(sd + 1) * 1.3) + hash01(sd + 2) * H) % H);
            ctx.fillStyle = neonRGBA(acc, 0.18 + Math.abs(Math.sin(globalFrame * 0.05 + i)) * 0.30);
            ctx.fillRect(fx, fy, 2.4, 2.4);
        }
        const hgv = ctx.createLinearGradient(0, H * 0.5, 0, H * 0.72);
        hgv.addColorStop(0, neonRGBA(acc, 0));
        hgv.addColorStop(1, neonRGBA(acc, 0.26));
        ctx.fillStyle = hgv; ctx.fillRect(0, H * 0.5, W, H * 0.22);
        return;
    }
    if (s === "dungeon") {
        // سنگ‌نوشته‌های نئونی تپنده روی دیوار سیاه‌چال
        const step = 210, base = Math.floor(player.worldX / step) * step;
        for (let wx = base - step; wx < base + W + step; wx += step) {
            const sx = wx - player.worldX * 0.9;
            if (sx < -50 || sx > W + 50) continue;
            const pulse = 0.45 + Math.abs(Math.sin(globalFrame * 0.03 + wx * 0.01)) * 0.55;
            ctx.save();
            ctx.translate(sx, 120);
            ctx.strokeStyle = neonRGBA(acc, 0.42 * pulse); ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(0, -13); ctx.lineTo(9, 0); ctx.lineTo(0, 13); ctx.lineTo(-9, 0); ctx.closePath();
            ctx.moveTo(0, -13); ctx.lineTo(0, 13);
            ctx.stroke();
            ctx.restore();
            if (pulse > 0.9) burstUI(sx, 120, acc);
        }
        return;
    }
    // ستاره‌های چشمک‌زن نئونی
    const n = Math.round(30 * qMul());
    for (let i = 0; i < n; i++) {
        const sd = i * 7.3, depth = (i % 3) + 1;
        const sx = ((hash01(sd) * W * 2 - player.worldX * 0.02 * depth * 0.5) % W + W) % W;
        const sy = 12 + hash01(sd + 1) * (H * 0.5);
        const tw = 0.3 + Math.abs(Math.sin(globalFrame * 0.035 + i * 1.7)) * 0.7;
        ctx.fillStyle = neonRGBA(depth === 3 ? acc : "#FFFFFF", tw * 0.8);
        const r = depth === 3 ? 2.2 : 1.4;
        ctx.fillRect(sx, sy, r, r);
    }
    // شفق قطبی — نوارهای نرم و موج‌دار
    for (let b = 0; b < 3; b++) {
        const baseY = 30 + b * 30;
        const ag = ctx.createLinearGradient(0, baseY - 26, 0, baseY + 30);
        ag.addColorStop(0, neonRGBA(acc, 0));
        ag.addColorStop(0.5, neonRGBA(acc, Math.max(0, 0.15 - b * 0.03)));
        ag.addColorStop(1, neonRGBA(acc, 0));
        ctx.strokeStyle = ag; ctx.lineWidth = 22 - b * 4;
        ctx.beginPath();
        for (let sx = 0; sx <= W; sx += 24) {
            const y = baseY + Math.sin(sx * 0.006 + globalFrame * 0.012 + b * 1.7) * 12 + Math.sin(sx * 0.017 - globalFrame * 0.02) * 5;
            if (sx === 0) ctx.moveTo(sx, y); else ctx.lineTo(sx, y);
        }
        ctx.stroke();
    }
    // درخشش افق پشت تپه‌ها
    const hg = ctx.createLinearGradient(0, H * 0.48, 0, H * 0.72);
    hg.addColorStop(0, neonRGBA(acc, 0));
    hg.addColorStop(1, neonRGBA(acc, 0.28));
    ctx.fillStyle = hg; ctx.fillRect(0, H * 0.48, W, H * 0.24);
}
function drawSky() { drawSkyBase(); if (neonOn()) drawNeonSky(); }

// --- لبه‌ی نورانی تپه‌های پارالاکس ---
function neonHillRims() {
    const s = getSeason(), W = canvas.width, acc = neonA(s);
    const layers = [[0.25, 330, "f", 0.5], [0.36, 362, "m", 0.65], [0.5, 392, "n", 0.8]];
    for (let i = 0; i < layers.length; i++) {
        const L = layers[i];
        ctx.save();
        ctx.lineJoin = "round";
        ctx.beginPath();
        for (let sx = 0; sx <= W; sx += 26) {
            const y = seasonHillY(sx + player.worldX * L[0], L[1], s, L[2]);
            if (sx === 0) ctx.moveTo(sx, y); else ctx.lineTo(sx, y);
        }
        ctx.strokeStyle = neonRGBA(acc, 0.14 * L[3]); ctx.lineWidth = 3.6; ctx.stroke();
        ctx.strokeStyle = neonRGBA(acc, 0.40 * L[3]); ctx.lineWidth = 1.2; ctx.stroke();
        ctx.restore();
    }
}
// --- نوار نور و تیک‌های شبکه‌ای روی سطح زمین ---
function neonGroundFX(s, cO) {
    const W = canvas.width, acc = neonA(s);
    ctx.save();
    ctx.strokeStyle = neonRGBA(acc, 0.15); ctx.lineWidth = 6;
    ctx.beginPath();
    for (let sx = 0; sx <= W; sx += 14) { const gy = baseGroundHeightAt(sx + cO); if (sx === 0) ctx.moveTo(sx, gy); else ctx.lineTo(sx, gy); }
    ctx.stroke();
    if (gfxQuality !== "low") {
        const step = 120, base = Math.floor(cO / step) * step;
        ctx.strokeStyle = neonRGBA(acc, 0.45); ctx.lineWidth = 1.6;
        ctx.beginPath();
        for (let wx = base; wx < cO + W + step; wx += step) {
            const gy = baseGroundHeightAt(wx), sx = wx - cO;
            ctx.moveTo(sx, gy + 4); ctx.lineTo(sx, gy + 15);
        }
        ctx.stroke();
    }
    ctx.restore();
}
// --- دنباله‌ی نورانی و هاله‌ی زیر پای بازیکن ---
let neonTrail = [];
function neonPlayerFX(feetY) {
    const acc = neonA(getSeason());
    const cx = screenX + player.width / 2;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    const gg = ctx.createRadialGradient(cx, feetY, 2, cx, feetY, 34);
    gg.addColorStop(0, neonRGBA(acc, 0.28)); gg.addColorStop(1, neonRGBA(acc, 0));
    ctx.fillStyle = gg;
    ctx.beginPath(); ctx.ellipse(cx, feetY, 34, 12, 0, 0, Math.PI * 2); ctx.fill();
    const active = keys.left || keys.right || player.isJumping || player.pitFalling;
    if (active && gfxQuality !== "low") {
        neonTrail.push({ x: cx, y: player.y - camY + 26 });
        if (neonTrail.length > 12) neonTrail.shift();
    } else if (neonTrail.length) { neonTrail.shift(); }
    for (let i = 0; i < neonTrail.length; i++) {
        const t = neonTrail[i], k = (i + 1) / neonTrail.length;
        ctx.fillStyle = neonRGBA(acc, 0.11 * k * k);
        ctx.beginPath(); ctx.arc(t.x, t.y, 9 * k + 2, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
}
function neonLandBurst(wx, gy) {
    const acc = neonA(getSeason());
    burst(wx, gy, { n: 10, colors: [acc, "#FFFFFF"], spd: 2.6, size: 3, life: 26, g: 0.05 });
    burst(wx, gy, { n: 6, colors: [acc], spd: 1.1, size: 5, life: 34, g: 0.02 });
}
function neonJumpFX(wx, gy) {
    burst(wx, gy, { n: 6, colors: [neonA(getSeason())], spd: 1.8, size: 2.8, life: 22, g: 0.02 });
}
// --- لبه‌ی نورانی سکوها ---
function neonPlatformEdge(dx, y, w) {
    const acc = neonA(getSeason());
    ctx.save();
    ctx.strokeStyle = neonRGBA(acc, 0.20); ctx.lineWidth = 4;
    ctx.beginPath(); ctx.moveTo(dx - w / 2 - 2, y - 5); ctx.lineTo(dx + w / 2 + 2, y - 5); ctx.stroke();
    ctx.strokeStyle = neonRGBA(acc, 0.75); ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(dx - w / 2 - 2, y - 5); ctx.lineTo(dx + w / 2 + 2, y - 5); ctx.stroke();
    ctx.restore();
}
// --- پس‌زمینه‌ی نئونی منوی اصلی: آسمان شب، خورشید سینت‌ویو و کف شبکه‌ای ---
function neonMenuBackdrop() {
    const W = canvas.width, H = canvas.height;
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, "#0A0620"); g.addColorStop(0.42, "#1A1046"); g.addColorStop(0.72, "#3B1E63"); g.addColorStop(1, "#12082B");
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    for (let i = 0; i < 42; i++) {
        const sx = hash01(i * 3.7) * W, sy = hash01(i * 9.1) * H * 0.55;
        const tw = 0.3 + Math.abs(Math.sin(globalFrame * 0.04 + i)) * 0.7;
        ctx.fillStyle = "rgba(255,255,255," + (tw * 0.8).toFixed(3) + ")";
        ctx.fillRect(sx, sy, 1.6, 1.6);
    }
    for (let b = 0; b < 2; b++) {
        const baseY = 40 + b * 34;
        const ag = ctx.createLinearGradient(0, baseY - 30, 0, baseY + 34);
        ag.addColorStop(0, "rgba(91,247,196,0)"); ag.addColorStop(0.5, "rgba(91,247,196,0.10)"); ag.addColorStop(1, "rgba(91,247,196,0)");
        ctx.strokeStyle = ag; ctx.lineWidth = 26 - b * 8;
        ctx.beginPath();
        for (let sx = 0; sx <= W; sx += 24) { const y = baseY + Math.sin(sx * 0.007 + globalFrame * 0.01 + b) * 12; if (sx === 0) ctx.moveTo(sx, y); else ctx.lineTo(sx, y); }
        ctx.stroke();
    }
    // خورشید سینت‌ویو گوشه‌ی راست
    const sunX = W - 96, sunY = H * 0.26, sunR = 52;
    ctx.save(); ctx.globalCompositeOperation = "lighter";
    const sg = ctx.createRadialGradient(sunX, sunY, 6, sunX, sunY, sunR * 2.4);
    sg.addColorStop(0, "rgba(255,120,200,0.40)"); sg.addColorStop(0.5, "rgba(255,80,160,0.13)"); sg.addColorStop(1, "rgba(255,80,160,0)");
    ctx.fillStyle = sg; ctx.beginPath(); ctx.arc(sunX, sunY, sunR * 2.4, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
    ctx.save();
    ctx.beginPath(); ctx.arc(sunX, sunY, sunR, 0, Math.PI * 2); ctx.clip();
    const dg = ctx.createLinearGradient(0, sunY - sunR, 0, sunY + sunR);
    dg.addColorStop(0, "#FFE066"); dg.addColorStop(0.5, "#FF7AB8"); dg.addColorStop(1, "#8B5CF6");
    ctx.fillStyle = dg; ctx.fillRect(sunX - sunR, sunY - sunR, sunR * 2, sunR * 2);
    ctx.fillStyle = "rgba(10,6,32,0.6)";
    for (let i = 0; i < 7; i++) { const yy = sunY - 4 + i * 8; ctx.fillRect(sunX - sunR, yy, sunR * 2, 2.2 + i * 0.7); }
    ctx.restore();
    // کف شبکه‌ای با پرسپکتیو
    const horizon = H * 0.62;
    ctx.save();
    ctx.strokeStyle = "rgba(91,247,196,0.40)"; ctx.lineWidth = 1.4;
    ctx.beginPath();
    for (let i = 0; i <= 14; i++) {
        const t = i / 14;
        const y = horizon + Math.pow(t, 2.1) * (H - horizon) * 1.15;
        ctx.moveTo(0, y); ctx.lineTo(W, y);
    }
    ctx.stroke();
    ctx.strokeStyle = "rgba(91,247,196,0.26)";
    ctx.beginPath();
    for (let i = -8; i <= 8; i++) {
        ctx.moveTo(W / 2 + i * 36, horizon);
        ctx.lineTo(W / 2 + i * 200, H + 40);
    }
    ctx.stroke();
    ctx.restore();
    const fg = ctx.createLinearGradient(0, horizon - 40, 0, H);
    fg.addColorStop(0, "rgba(139,92,246,0)"); fg.addColorStop(1, "rgba(139,92,246,0.32)");
    ctx.fillStyle = fg; ctx.fillRect(0, horizon - 40, W, H - horizon + 40);
}

"""

# ---------------------------------------------------------------------------
# فهرست پچ‌ها: (تعداد انتظار، متن اصلی، متن جدید)
# ---------------------------------------------------------------------------
PATCHES = [
    # ۱) ذخیره/بازیابی وضعیت نئون
    (1,
     "            musicOn, sfxOn, masterAudioOn, musicVolume, sfxVolume, gfxQuality,",
     "            musicOn, sfxOn, masterAudioOn, musicVolume, sfxVolume, gfxQuality, neonFX,"),
    (1,
     "        if (d.gfxQuality) gfxQuality = d.gfxQuality;",
     "        if (d.gfxQuality) gfxQuality = d.gfxQuality;\n        if (d.neonFX !== undefined) neonFX = d.neonFX;"),

    # ۲) آسمان: تابع اصلی به drawSkyBase تغییر نام می‌دهد و drawSky نئون را رویش می‌کشد
    (1,
     "function drawSky() {\n    const s = getSeason(), W = canvas.width, H = canvas.height;\n    if (s === \"space\") {",
     "function drawSkyBase() {\n    const s = getSeason(), W = canvas.width, H = canvas.height;\n    if (s === \"space\") {"),

    # ۳) پالت نئونی آسمان هر فصل
    (1,
     "ctx.fillStyle = vGrad(\"skyX\", 0, H, [[0, \"#05030F\"], [0.45, \"#0E0A26\"], [0.8, \"#1B1338\"], [1, \"#2A2050\"]]);",
     "ctx.fillStyle = neonSky(\"skyX\", 0, H, [[0, \"#05030F\"], [0.45, \"#0E0A26\"], [0.8, \"#1B1338\"], [1, \"#2A2050\"]], [[0, \"#04020C\"], [0.4, \"#0B0724\"], [0.75, \"#1C0F42\"], [1, \"#301C6B\"]]);"),
    (1,
     "ctx.fillStyle = vGrad(\"skyD\", 0, H, [[0, \"#0C0D10\"], [0.5, \"#1C1E23\"], [1, \"#2E3037\"]]);",
     "ctx.fillStyle = neonSky(\"skyD\", 0, H, [[0, \"#0C0D10\"], [0.5, \"#1C1E23\"], [1, \"#2E3037\"]], [[0, \"#06070B\"], [0.5, \"#12151F\"], [1, \"#231D33\"]]);"),
    (1,
     "ctx.fillStyle = vGrad(\"skyV\", 0, H, [[0, \"#2C0B05\"], [0.35, \"#5C1A0A\"], [0.68, \"#9C3B12\"], [1, \"#D9622B\"]]);",
     "ctx.fillStyle = neonSky(\"skyV\", 0, H, [[0, \"#2C0B05\"], [0.35, \"#5C1A0A\"], [0.68, \"#9C3B12\"], [1, \"#D9622B\"]], [[0, \"#160306\"], [0.35, \"#430B12\"], [0.68, \"#8E2417\"], [1, \"#E0562B\"]]);"),
    (1,
     "ctx.fillStyle = vGrad(\"skyW\", 0, H, [[0, \"#1A2A44\"], [0.3, \"#3E5C7E\"], [0.62, \"#7FA3C4\"], [1, \"#CFE3F2\"]]);",
     "ctx.fillStyle = neonSky(\"skyW\", 0, H, [[0, \"#1A2A44\"], [0.3, \"#3E5C7E\"], [0.62, \"#7FA3C4\"], [1, \"#CFE3F2\"]], [[0, \"#050A16\"], [0.3, \"#102A4A\"], [0.62, \"#2C6B96\"], [1, \"#7FD8F5\"]]);"),
    (1,
     "ctx.fillStyle = vGrad(\"skyS\", 0, H, [[0, \"#FF6B35\"], [0.3, \"#FF8C42\"], [0.6, \"#FFA500\"], [1, \"#FFD98E\"]]);",
     "ctx.fillStyle = neonSky(\"skyS\", 0, H, [[0, \"#FF6B35\"], [0.3, \"#FF8C42\"], [0.6, \"#FFA500\"], [1, \"#FFD98E\"]], [[0, \"#12062A\"], [0.34, \"#3B1155\"], [0.64, \"#8E2A6B\"], [1, \"#FF8A5C\"]]);"),
    (1,
     "ctx.fillStyle = vGrad(\"skyA\", 0, H, [[0, \"#2C1A0E\"], [0.25, \"#6B3A20\"], [0.6, \"#A0522D\"], [1, \"#C8724A\"]]);",
     "ctx.fillStyle = neonSky(\"skyA\", 0, H, [[0, \"#2C1A0E\"], [0.25, \"#6B3A20\"], [0.6, \"#A0522D\"], [1, \"#C8724A\"]], [[0, \"#140722\"], [0.28, \"#3A1233\"], [0.6, \"#7A2B2A\"], [1, \"#E0763A\"]]);"),
    (1,
     "ctx.fillStyle = vGrad(\"skyP\", 0, H, [[0, \"#2980B9\"], [0.4, \"#5DADE2\"], [0.7, \"#A9CCE3\"], [1, \"#D5F5E3\"]]);",
     "ctx.fillStyle = neonSky(\"skyP\", 0, H, [[0, \"#2980B9\"], [0.4, \"#5DADE2\"], [0.7, \"#A9CCE3\"], [1, \"#D5F5E3\"]], [[0, \"#0A0A2E\"], [0.4, \"#221A55\"], [0.72, \"#4B2A7A\"], [1, \"#8B5CF6\"]]);"),

    # ۴) گرادیان زمین: پالت نئون + کلید کش جداگانه
    (1,
     "ctx.fillStyle = vGrad(\"gnd\" + s, 300, H, [[0, th.groundTop], [0.25, th.ground], [1, s === \"spring\" ? \"#1E5C17\" : s === \"summer\" ? \"#8B560E\" : s === \"winter\" ? \"#8FA6B8\" : \"#5E2F0C\"]]);",
     "ctx.fillStyle = vGrad(\"gnd\" + s + (neonOn() ? \"N\" : \"\"), 300, H, [[0, th.groundTop], [0.25, th.ground], [1, neonOn() ? (s === \"spring\" ? \"#06231C\" : s === \"summer\" ? \"#1B1105\" : s === \"winter\" ? \"#0A1A26\" : s === \"autumn\" ? \"#1B0906\" : s === \"space\" ? \"#0D0E18\" : s === \"venus\" ? \"#1A0602\" : \"#0B0C12\") : (s === \"spring\" ? \"#1E5C17\" : s === \"summer\" ? \"#8B560E\" : s === \"winter\" ? \"#8FA6B8\" : \"#5E2F0C\")]]);"),

    # ۵) نوار نور و تیک‌های نئونی روی زمین
    (1,
     "    ctx.strokeStyle = th.groundLine; ctx.lineWidth = 1.5; ctx.stroke();",
     "    ctx.strokeStyle = th.groundLine; ctx.lineWidth = 1.5; ctx.stroke();\n    if (neonOn()) neonGroundFX(s, cO);"),

    # ۶) لبه‌ی نورانی تپه‌ها
    (1,
     "    ctx.fillStyle = th.hillNear; ctx.fill();\n}",
     "    ctx.fillStyle = th.hillNear; ctx.fill();\n    if (neonOn()) neonHillRims();\n}"),

    # ۷) هاله و دنباله‌ی نئونی بازیکن
    (1,
     "    const moving = keys.left || keys.right;\n    const inAir = player.isJumping || player.pitFalling;\n    const legSwing = (moving && !inAir) ? Math.sin(frameCount * 0.28) * 9 : 0;",
     "    const moving = keys.left || keys.right;\n    const inAir = player.isJumping || player.pitFalling;\n    const legSwing = (moving && !inAir) ? Math.sin(frameCount * 0.28) * 9 : 0;\n    if (neonOn()) neonPlayerFX(player.y - camY + player.height);"),

    # ۸) افکت فرود و پرش
    (1,
     "                dust(player.worldX, s2.y, 4, 0); landSquash = 9;\n                return;",
     "                dust(player.worldX, s2.y, 4, 0); landSquash = 9;\n                if (neonOn()) neonLandBurst(player.worldX, s2.y);\n                return;"),
    (1,
     "dust(player.worldX, curG, 4, 0); landSquash = 9; }",
     "dust(player.worldX, curG, 4, 0); landSquash = 9; if (neonOn()) neonLandBurst(player.worldX, curG); }"),
    (2,
     "dust(player.worldX, player.y + player.height, 4, player.facing); sfx(\"jump\"); }",
     "dust(player.worldX, player.y + player.height, 4, player.facing); if (neonOn()) neonJumpFX(player.worldX, player.y + player.height); sfx(\"jump\"); }"),

    # ۹) ذرات: رنگ نئون فصل به هر انفجار و گرد و غبار اضافه می‌شود
    (1,
     ", cols = opt.colors || [\"#FFD700\"], spd = opt.spd || 2.4;",
     ", cols = (opt.colors || [\"#FFD700\"]).concat(neonOn() ? [neonA(getSeason()), \"#FFFFFF\"] : []), spd = opt.spd || 2.4;"),
    (1,
     "color: \"rgba(205,195,175,0.5)\"",
     "color: neonOn() ? neonRGBA(neonA(getSeason()), 0.45) : \"rgba(205,195,175,0.5)\""),

    # ۱۰) هاله‌ی درخشان سکه‌ها و ستاره‌ها
    (1,
     "function drawCoin(x, y, wx) {",
     "function drawCoin(x, y, wx) {\n    if (neonOn()) neonHalo(x, y, 22, \"#FFD700\", 0.75);"),
    (1,
     "function drawGoldCoin(x, y) {",
     "function drawGoldCoin(x, y) {\n    if (neonOn()) neonHalo(x, y, 30, \"#FFD700\", 1);"),
    (1,
     "function drawWorldStar(x, y, wx) {\n    if (wx === undefined) wx = x;",
     "function drawWorldStar(x, y, wx) {\n    if (wx === undefined) wx = x;\n    if (neonOn()) neonHalo(x, y, 40, \"#FFD54F\", 1.1);"),

    # ۱۱) لبه‌ی نورانی سکوها
    (1,
     "    ctx.restore();\n}\n// پروانه",
     "    if (neonOn()) neonPlatformEdge(dx, y, w);\n    ctx.restore();\n}\n// پروانه"),

    # ۱۲) پس‌زمینه‌ی منوی اصلی
    (1,
     "    const g = ctx.createLinearGradient(0, 0, 0, canvas.height); g.addColorStop(0, \"#7ED77F\"); g.addColorStop(0.7, \"#4CB050\"); g.addColorStop(1, \"#2F8F35\"); ctx.fillStyle = g; ctx.fillRect(0, 0, canvas.width, canvas.height);\n    // دشت دور\n    ctx.fillStyle = \"rgba(255,255,255,0.22)\"; ctx.beginPath(); ctx.ellipse(160, canvas.height + 40, 320, 130, 0, 0, Math.PI * 2); ctx.ellipse(620, canvas.height + 60, 340, 150, 0, 0, Math.PI * 2); ctx.fill();",
     "    if (neonOn()) neonMenuBackdrop(); else {\n    const g = ctx.createLinearGradient(0, 0, 0, canvas.height); g.addColorStop(0, \"#7ED77F\"); g.addColorStop(0.7, \"#4CB050\"); g.addColorStop(1, \"#2F8F35\"); ctx.fillStyle = g; ctx.fillRect(0, 0, canvas.width, canvas.height);\n    // دشت دور\n    ctx.fillStyle = \"rgba(255,255,255,0.22)\"; ctx.beginPath(); ctx.ellipse(160, canvas.height + 40, 320, 130, 0, 0, Math.PI * 2); ctx.ellipse(620, canvas.height + 60, 340, 150, 0, 0, Math.PI * 2); ctx.fill();\n    }"),

    # ۱۳) کلید Neon FX در صفحه‌ی کیفیت گرافیک
    (1,
     "        btn.action = () => setGfxQuality(o.key);\n        gfxSettingsButtons.push(btn);\n    });",
     """        btn.action = () => setGfxQuality(o.key);
        gfxSettingsButtons.push(btn);
    });
    // کلید جلوه‌های نئون
    const nY = 324, nSel = neonFX;
    ctx.fillStyle = nSel ? "rgba(0,137,123,0.25)" : "rgba(255,255,255,0.06)"; roundRect(rowX, nY, rowW, 58, 14); ctx.fill();
    if (nSel) { ctx.strokeStyle = "#5BF7C4"; ctx.lineWidth = 2; roundRect(rowX, nY, rowW, 58, 14); ctx.stroke(); }
    ctx.fillStyle = "#ECEFF1"; ctx.font = F(17, 900); ctx.textAlign = "start";
    ctx.fillText(lang === "fa" ? "جلوه‌های نئون" : "Neon FX", rowX + 20, nY + 25);
    ctx.font = F(12, 400); ctx.fillStyle = "rgba(255,255,255,0.65)";
    ctx.fillText(lang === "fa" ? "درخشش، بلوم، شفق و رنگ‌بندی نئونی صحنه" : "Bloom, glow, aurora and neon color grading", rowX + 20, nY + 45);
    const nBtn = rect(rowX + rowW - 106, nY + 9, 88, 40);
    drawButton(Object.assign({}, nBtn, { label: nSel ? (lang === "fa" ? "✓ روشن" : "✓ ON") : (lang === "fa" ? "خاموش" : "OFF"), color: nSel ? "#00897B" : "#546E7A" }));
    nBtn.action = () => setNeon(!neonFX);
    gfxSettingsButtons.push(nBtn);"""),
    (1,
     "    ctx.fillText(lang === \"fa\" ? \"فقط تراکم جلوه‌های تزئینی را تغییر می‌دهد، نه گیم‌پلی.\" : \"Only affects decorative effect density, never gameplay.\", canvas.width / 2, 340);",
     "    ctx.fillText(lang === \"fa\" ? \"فقط تراکم جلوه‌های تزئینی را تغییر می‌دهد، نه گیم‌پلی.\" : \"Only affects decorative effect density, never gameplay.\", canvas.width / 2, 402);\n    if (gfxQuality === \"low\" && neonFX) { ctx.fillStyle = \"rgba(255,196,107,0.8)\"; ctx.fillText(lang === \"fa\" ? \"در کیفیت «پایین» جلوه‌های نئون خودکار خاموش می‌شوند.\" : \"Neon FX is disabled automatically at LOW quality.\", canvas.width / 2, 422); }"),

    # ۱۴) موتور نئون + فراخوانی بلوم در انتهای هر فریم
    (1,
     "function gameLoop() {",
     NEON_ENGINE + "function gameLoop() {"),
    (1,
     "    requestAnimationFrame(gameLoop);\n}",
     "    neonPost();\n    requestAnimationFrame(gameLoop);\n}"),
]


def apply(text: str, old: str, new: str, expect: int, label: str) -> str:
    found = text.count(old)
    if found != expect:
        print(f"  ✗ {label}: انتظار {expect} تطابق، {found} پیدا شد")
        print(f"    → {old[:110]!r}")
        sys.exit(1)
    return text.replace(old, new)


def main() -> None:
    if not SRC.exists():
        sys.exit(f"سورس پیدا نشد: {SRC}")
    src = SRC.read_text(encoding="utf-8")
    if MARKER in src:
        sys.exit("این سورس از قبل پچ شده است.")

    text = src
    print("• تغییر نام دسترسی به تم: THEMES[…] → TH(…)")
    text = apply(text, "THEMES[season]", "TH(season)", 3, "TH(season)")
    text = apply(text, "THEMES[s]", "TH(s)", 2, "TH(s)")

    for i, (expect, old, new) in enumerate(PATCHES, 1):
        text = apply(text, old, new, expect, f"patch #{i}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"✓ ساخته شد: {OUT.relative_to(ROOT)}  ({len(text):,} کاراکتر)")
    print(f"  از {SRC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
