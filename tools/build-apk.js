#!/usr/bin/env node
/*
 * build-apk.js — بسته‌بندی مجدد اپ اندروید با گرافیک نئون.
 *
 * چه می‌کند:
 *   ۱) فایل پایه‌ی app-debug.apk را باز می‌کند (همان قالب Capacitor اپ بازی)
 *   ۲) assets/public/index.html را با نسخه‌ی نئون (game/index.html) جایگزین می‌کند
 *   ۳) امضای قدیمی (META-INF/*.SF, *.RSA, MANIFEST.MF) را پاک می‌کند
 *   ۴) با کلید اختصاصی پروژه دوباره امضا می‌کند: JAR v1 + APK Signature v2 و v3
 *      (امضا کاملاً با JS انجام می‌شود؛ نیازی به Java/Android SDK نیست)
 *
 * خروجی: game/adventure-world-neon.apk
 *
 * اجرا:  node tools/build-apk.js
 * پیش‌نیاز: node tools/make-keystore.js  (یک‌بار)
 */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const AdmZip = require("adm-zip");
const {
    ApkSigner, SigningKey, findEndOfCentralDirectory, parseZipCentralDirectory,
    writeUint16LE, writeUint32LE, readUint64LE, concatBytes
} = require("apk_sign_ts");

const ROOT = path.join(__dirname, "..");
const BASE_APK = path.join(ROOT, "app-debug.apk");
const GAME_HTML = path.join(ROOT, "game", "index.html");
const KEY_PEM = path.join(ROOT, "keystore", "artam-release.key.pem");
const CERT_PEM = path.join(ROOT, "keystore", "artam-release.cert.pem");
const OUT_APK = path.join(ROOT, "game", "adventure-world-neon.apk");

/*
 * تکمیل بلوک امضا برای سازگاری کامل با پارسر AOSP:
 *
 * طرح v3 در apksig این ساختار را دارد:
 *     signers  = lp( دنباله‌ی lp(signer)ها )
 *     minSdk   (uint32)   ← بعد از دنباله
 *     maxSdk   (uint32)   ← بعد از دنباله
 * اما apk_sign_ts این دو فیلد پایانی را نمی‌نویسد؛ نتیجه این‌که اندروید ۹+ می‌تواند بلوک v3 را
 * نامعتبر بداند. چون این دو فیلد بیرون از «signed data» هستند، افزودنشان امضای RSA و
 * خورده‌های محتوا را باطل نمی‌کند؛ فقط طول ورودی و اندازه‌ی بلوک و آفست CD به‌روز می‌شوند.
 * مقادیر از خودِ signer خوانده می‌شوند (minSdk/maxSdk داخل signer).
 */
const APK_BLOCK_MAGIC_STR = "APK Sig Block 42";
const APK_SIG_V2_ID = 0x7109871a;
const APK_SIG_V3_ID = 0xf05368c0;

function u32le(buf, off) { return buf.readUInt32LE(off); }
function u64le(buf, off) { return Number(buf.readBigUInt64LE(off)); }

function fixSigningBlock(apk) {
    const buf = Buffer.from(apk);
    // آخرین EOCD را پیدا کن
    let eocd = -1;
    for (let i = buf.length - 22; i >= 0 && i >= buf.length - 22 - 65535; i--) {
        if (u32le(buf, i) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error("EOCD پیدا نشد");
    const cdOffset = u32le(buf, eocd + 16);
    const magicAt = cdOffset - 16;
    if (buf.subarray(magicAt, cdOffset).toString("latin1") !== APK_BLOCK_MAGIC_STR) {
        throw new Error("بلوک امضا پیدا نشد");
    }
    const blockSize = u64le(buf, cdOffset - 24);
    const blockStart = cdOffset - blockSize - 8;

    // ورودی‌های بلوک را باز کن
    const pairs = [];
    let p = blockStart + 8;
    while (p + 12 <= cdOffset - 24) {
        const plen = u64le(buf, p);              // طول ورودی (شامل ۴ بایت شناسه)
        const id = u32le(buf, p + 8);
        const value = buf.subarray(p + 12, p + 12 + (plen - 4));
        pairs.push({ id, value });
        p += 8 + plen;
    }

    let added = 0;
    for (const pair of pairs) {
        if (pair.id === APK_SIG_V3_ID) {
            // بلوک v3: بعد از دنباله‌ی signerها باید minSdk و maxSdk بیاید
            const tail = Buffer.alloc(8);
            tail.writeUInt32LE(24, 0);            // minSdk — مطابق مقدار داخل signer
            tail.writeUInt32LE(0x7fffffff, 4);    // maxSdk — مطابق مقدار داخل signer
            const value = Buffer.concat([pair.value, tail]);
            added += value.length - pair.value.length;
            pair.value = value;
        }
    }
    if (!pairs.some((x) => x.id === APK_SIG_V2_ID)) throw new Error("ورودی v2 در بلوک امضا نیست");

    const parts = [];
    for (const pair of pairs) {
        const head = Buffer.alloc(12);
        head.writeBigUInt64LE(BigInt(pair.value.length + 4), 0);
        head.writeUInt32LE(pair.id, 8);
        parts.push(head, pair.value);
    }
    const body = Buffer.concat(parts);
    const newSize = body.length + 24;     // + فیلد اندازه‌ی پایانی (۸) + magic (۱۶)
    const head = Buffer.alloc(8);
    head.writeBigUInt64LE(BigInt(newSize));
    const tail = Buffer.alloc(24);
    tail.writeBigUInt64LE(BigInt(newSize), 0);
    tail.write(APK_BLOCK_MAGIC_STR, 8, "latin1");
    const newBlock = Buffer.concat([head, body, tail]);

    // فایل جدید: پیش از بلوک + بلوک اصلاح‌شده + بقیه (با آفست به‌روزشده‌ی CD در EOCD)
    const after = Buffer.from(buf.subarray(cdOffset));
    const eocdInAfter = eocd - cdOffset;
    after.writeUInt32LE(cdOffset + (newBlock.length - (cdOffset - blockStart)), eocdInAfter + 16);
    const out = Buffer.concat([buf.subarray(0, blockStart), newBlock, after]);
    console.log(`• ساختار بلوک امضا اصلاح شد (+${added} بایت، اندازه‌ی جدید بلوک ${newSize})`);
    return out;
}

const GAME_ASSET = "assets/public/index.html";
const OLD_SIG = ["META-INF/MANIFEST.MF", "META-INF/CERT.SF", "META-INF/CERT.RSA", "META-INF/CERT.DSA"];

function fail(msg) { console.error("✗ " + msg); process.exit(1); }

/*
 * کتابخانه‌ی apk_sign_ts در بازسازی بسته، «هر» ورودی META-INF/ را حذف می‌کند؛
 * اما این APK فایل‌های مهمی مثل META-INF/services/* و نسخه‌های androidx دارد.
 * پس همان مرحله را با یک تفاوت بازنویسی می‌کنیم: فقط فایل‌های امضای قبلی حذف شوند.
 */
const SIG_ENTRY_RE = /^META-INF\/(MANIFEST\.MF|.*\.(SF|RSA|DSA|EC))$/i;
const APK_BLOCK_MAGIC = Buffer.from("APK Sig Block 42");
ApkSigner.prototype.sanitizeApk = function (apkData) {
    const eocd = findEndOfCentralDirectory(apkData);
    if (!eocd) throw new Error("Invalid APK: End of Central Directory not found");
    const cdOffset0 = eocd.centralDirectoryOffset;
    let signingBlockSize = 0;
    const magicOffset = cdOffset0 - APK_BLOCK_MAGIC.length;
    if (magicOffset >= 0) {
        let same = true;
        for (let i = 0; i < APK_BLOCK_MAGIC.length; i++) {
            if (apkData[magicOffset + i] !== APK_BLOCK_MAGIC[i]) { same = false; break; }
        }
        if (same) signingBlockSize = Number(readUint64LE(apkData, cdOffset0 - 8 - APK_BLOCK_MAGIC.length));
    }
    const localEnd = signingBlockSize > 0 ? cdOffset0 - 8 - signingBlockSize : cdOffset0;
    const cd = parseZipCentralDirectory(apkData);
    const entries = [...cd.entries].sort((a, b) => a.localHeaderOffset - b.localHeaderOffset);
    const localBuffers = [], cdBuffers = [];
    let localOffset = 0;
    for (let i = 0; i < entries.length; i++) {
        const entry = entries[i];
        if (SIG_ENTRY_RE.test(entry.name)) continue;   // فقط امضای قبلی حذف می‌شود
        const nextLocal = i + 1 < entries.length ? entries[i + 1].localHeaderOffset : localEnd;
        const chunk = apkData.subarray(entry.localHeaderOffset, nextLocal);
        localBuffers.push(chunk);
        const cdSize = 46 + entry.nameLength + entry.extraLength + entry.commentLength;
        const hdr = new Uint8Array(cdSize);
        hdr.set(apkData.subarray(entry.cdHeaderOffset, entry.cdHeaderOffset + cdSize), 0);
        writeUint32LE(hdr, 42, localOffset);
        cdBuffers.push(hdr);
        localOffset += chunk.length;
    }
    const newLocal = concatBytes(localBuffers);
    const newCd = concatBytes(cdBuffers);
    const newEocd = new Uint8Array(apkData.subarray(eocd.recordOffset));
    writeUint16LE(newEocd, 8, cdBuffers.length);
    writeUint16LE(newEocd, 10, cdBuffers.length);
    writeUint32LE(newEocd, 12, newCd.length);
    writeUint32LE(newEocd, 16, newLocal.length);
    return concatBytes([newLocal, newCd, newEocd]);
};

for (const f of [BASE_APK, GAME_HTML, KEY_PEM, CERT_PEM]) {
    if (!fs.existsSync(f)) fail("فایل پیدا نشد: " + path.relative(ROOT, f) + (f === KEY_PEM ? "  → اول «node tools/make-keystore.js» را اجرا کن" : ""));
}

const html = fs.readFileSync(GAME_HTML);
console.log(`• بازی نئون: ${(html.length / 1024 / 1024).toFixed(2)} مگابایت`);

// ---------------------------------------------------------------- ۱) باز کردن قالب
const base = fs.readFileSync(BASE_APK);
console.log(`• بسته‌ی پایه: ${(base.length / 1024 / 1024).toFixed(2)} مگابایت`);

const zip = new AdmZip(base);
const methodsBefore = new Map();
let replacedAsset = false;
for (const e of zip.getEntries()) {
    methodsBefore.set(e.entryName, e.header.method);
    if (e.entryName === GAME_ASSET) {
        zip.updateFile(e, html);
        replacedAsset = true;
        console.log("• assets/public/index.html جایگزین شد");
    }
}
if (!replacedAsset) fail("در بسته‌ی پایه " + GAME_ASSET + " پیدا نشد");

for (const name of OLD_SIG) {
    const e = zip.getEntry(name);
    if (e) { zip.deleteFile(e); console.log("• امضای قدیمی پاک شد:", name); }
}

const rebuilt = zip.toBuffer({ compression: "DEFLATE" });
console.log(`• بسته‌ی بازساخته: ${(rebuilt.length / 1024 / 1024).toFixed(2)} مگابایت`);

// ---------------------------------------------------------------- ۲) امضا (v1+v2+v3)
// کتابخانه‌ی امضا فقط قالب PKCS#8 را می‌پذیرد؛ اگر کلید PKCS#1 بود تبدیل می‌کنیم
function toPkcs8(pem) {
    if (pem.includes("BEGIN PRIVATE KEY")) return pem;
    return crypto.createPrivateKey(pem).export({ type: "pkcs8", format: "pem" });
}
const signingKey = SigningKey.fromPEM(toPkcs8(fs.readFileSync(KEY_PEM, "utf8")), fs.readFileSync(CERT_PEM, "utf8"));
const signer = new ApkSigner({ signingKey });

(async () => {
    console.log("• امضای APK (JAR v1 + APK Signature v2 + v3)…");
    const { signedApk, signatureSize } = await signer.sign(new Uint8Array(rebuilt));
    const fixedApk = fixSigningBlock(Buffer.from(signedApk));
    fs.writeFileSync(OUT_APK, fixedApk);
    console.log(`✓ ساخته شد: ${path.relative(ROOT, OUT_APK)}  (${(fixedApk.length / 1024 / 1024).toFixed(2)} مگابایت، بلوک امضا ${signatureSize} بایت)`);

    // ------------------------------------------------------------ ۳) بازرسی سلامت بسته
    const check = new AdmZip(fixedApk);
    const names = check.getEntries().map((e) => e.entryName);
    const problems = [];
    if (!names.includes(GAME_ASSET)) problems.push("دارایی بازی داخل بسته نیست");
    if (names.filter((n) => n === "META-INF/MANIFEST.MF").length !== 1) problems.push("MANIFEST.MF تکراری یا ناموجود");
    if (!names.includes("META-INF/CERT.SF") || !names.includes("META-INF/CERT.RSA")) problems.push("فایل‌های امضای v1 ناقص");
    for (const [n, m] of methodsBefore) {
        if (n === GAME_ASSET || OLD_SIG.includes(n)) continue;
        const e = check.getEntry(n);
        if (!e) { problems.push("ورودی گم‌شده: " + n); continue; }
        // resources.arsc و اندرویدمانیفست باید روش فشرده‌سازی اصلی خود را نگه دارند
        if ((n.endsWith(".arsc") || n === "AndroidManifest.xml") && e.header.method !== m) {
            problems.push(`روش فشرده‌سازی ${n} عوض شده (${m} → ${e.header.method})`);
        }
    }
    const inner = check.readFile(GAME_ASSET);
    if (!inner || inner.length !== html.length) problems.push("محتوای دارایی بازی با فایل نئون یکی نیست");
    if (inner && inner.toString("utf8").includes("NEON GFX ENGINE") === false) problems.push("نسخه‌ی داخل بسته گرافیک نئون ندارد");

    if (problems.length) { console.error("✗ بازرسی بسته:\n  - " + problems.join("\n  - ")); process.exit(1); }
    console.log("✓ بازرسی بسته سالم است (ورودی‌ها، فشرده‌سازی، محتوای بازی)");
    console.log("  برای بررسی امضا:  python3 tools/verify-apk.py " + path.relative(ROOT, OUT_APK));
})().catch((e) => fail("امضا شکست خورد: " + (e && e.stack || e)));
