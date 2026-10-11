#!/usr/bin/env node
/*
 * make-keystore.js — ساخت کلید و گواهی امضای اپلیکیشن (یک‌بار برای همیشه).
 *
 * خروجی‌ها در پوشه‌ی keystore/ :
 *   artam-release.key.pem   کلید خصوصی (RSA 2048) — این فایل را گم نکن
 *   artam-release.cert.pem  گواهی خودامضا (۲۵ سال اعتبار)
 *   artam-release.p12       بستهٔ PKCS#12 برای وارد کردن در Android Studio
 *   artam-release.info.txt  اثر انگشت‌ها و گذرواژه‌ی پیش‌فرض p12
 *
 * اگر فایل‌ها از قبل باشند، دوباره ساخته نمی‌شوند (مگر با --force).
 *
 * اجرا:  node tools/make-keystore.js [--force]
 */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const forge = require("node-forge");

const OUT = path.join(__dirname, "..", "keystore");
const KEY_PEM = path.join(OUT, "artam-release.key.pem");
const CERT_PEM = path.join(OUT, "artam-release.cert.pem");
const P12 = path.join(OUT, "artam-release.p12");
const INFO = path.join(OUT, "artam-release.info.txt");

const P12_PASS = "artam-adventure";
const force = process.argv.includes("--force");

if (fs.existsSync(KEY_PEM) && !force) {
    console.log("• کلید از قبل موجود است:", path.relative(process.cwd(), KEY_PEM));
    console.log("  (برای ساخت مجدد: --force)");
    process.exit(0);
}

fs.mkdirSync(OUT, { recursive: true });

console.log("• ساخت کلید RSA 2048…");
const keys = forge.pki.rsa.generateKeyPair({ bits: 2048, e: 0x10001 });

console.log("• ساخت گواهی خودامضا (۲۵ سال)…");
const cert = forge.pki.createCertificate();
cert.publicKey = keys.publicKey;
cert.serialNumber = "0a" + Date.now().toString(16);
cert.validity.notBefore = new Date();
cert.validity.notAfter = new Date();
cert.validity.notAfter.setFullYear(cert.validity.notBefore.getFullYear() + 25);
const attrs = [
    { name: "commonName", value: "Artam Adventure World" },
    { name: "organizationName", value: "Artam" },
    { name: "organizationalUnitName", value: "Games" },
    { name: "countryName", value: "IR" }
];
cert.setSubject(attrs);
cert.setIssuer(attrs);
cert.setExtensions([
    { name: "basicConstraints", cA: true },
    { name: "keyUsage", digitalSignature: true, keyEncipherment: true, dataEncipherment: true },
    { name: "extKeyUsage", serverAuth: true, clientAuth: true, codeSigning: true, emailProtection: true, timeStamping: true },
    { name: "subjectAltName", altNames: [{ type: 6, value: "https://leilazare59-hub.github.io/artam.io/" }] }
]);
cert.sign(keys.privateKey, forge.md.sha256.create());

// کتابخانه‌ی امضا کلید را در قالب PKCS#8 (#8 «BEGIN PRIVATE KEY») می‌خواهد؛
// node-forge قالب PKCS#1 می‌دهد، پس با خود Node تبدیل می‌کنیم.
const keyPem = crypto.createPrivateKey(forge.pki.privateKeyToPem(keys.privateKey))
    .export({ type: "pkcs8", format: "pem" });
const certPem = forge.pki.certificateToPem(cert);
fs.writeFileSync(KEY_PEM, keyPem);
console.log("  قالب کلید: PKCS#8");
fs.writeFileSync(CERT_PEM, certPem);

console.log("• ساخت بستهٔ PKCS#12…");
const p12Asn1 = forge.pkcs12.toPkcs12Asn1(keys.privateKey, [cert], P12_PASS, { algorithm: "3des" });
fs.writeFileSync(P12, forge.util.decode64(forge.util.encode64(forge.asn1.toDer(p12Asn1).getBytes())), "binary");

// اثر انگشت گواهی (SHA-256 و SHA-1) برای مقایسه با خروجی apksigner
const der = forge.asn1.toDer(forge.pki.certificateToAsn1(cert)).getBytes();
const md256 = forge.md.sha256.create(); md256.update(der);
const md1 = forge.md.sha1.create(); md1.update(der);
const hex = (s) => s.match(/../g).join(":").toUpperCase();

fs.writeFileSync(INFO, [
    "کلید امضای بازی «دنیای ماجراجویی» — آرتام",
    "",
    "کلید خصوصی : artam-release.key.pem",
    "گواهی       : artam-release.cert.pem",
    "بسته PKCS12 : artam-release.p12   (گذرواژه: " + P12_PASS + ")",
    "اعتبار گواهی: ۲۵ سال از تاریخ ساخت",
    "",
    "SHA-256 اثر انگشت گواهی:",
    "  " + hex(md256.digest().toHex()),
    "SHA-1 اثر انگشت گواهی:",
    "  " + hex(md1.digest().toHex()),
    "",
    "مهم:",
    "  • برای انتشار نسخه‌های بعدی همیشه با همین کلید امضا کن، وگرنه کاربر باید",
    "    نسخه‌ی قبلی را حذف کند تا نسخه‌ی جدید نصب شود.",
    "  • ورود به Android Studio: Build > Generate Signed Bundle / APK > PKCS12",
    "    و انتخاب فایل .p12 با گذرواژه‌ی بالا.",
    ""
].join("\n"), "utf8");

console.log("✓ ساخته شد:");
for (const f of [KEY_PEM, CERT_PEM, P12, INFO]) console.log("  -", path.relative(path.join(__dirname, ".."), f));
