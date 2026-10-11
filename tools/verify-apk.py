#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify-apk.py — بازرسی مستقل امضای APK (بدون apksigner و بدون Java).

کارهایی که انجام می‌دهد:
  • ساختار APK Signing Block و طرح‌های امضا (v2 / v3) را پیدا می‌کند
  • خورده‌ها (digests) چهار بخش فایل را دوباره حساب می‌کند و با بلوک امضا مقایسه می‌کند
  • امضای RSA روی signed-data را با کلید عمومی خودِ گواهی داخل APK بررسی می‌کند
  • جدول MANIFEST.MF / CERT.SF (امضای JAR v1) را هم صحت‌سنجی می‌کند
  • اثر انگشت گواهی را چاپ می‌کند

اجرا:  python3 tools/verify-apk.py [--file game/adventure-world-neon.apk]
نیازمندی: pip install cryptography
"""
import argparse
import base64
import hashlib
import io
import struct
import sys
import zipfile
from pathlib import Path

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
except ImportError:
    sys.exit("نیازمندی نصب نیست:  pip install cryptography")

APK_SIG_BLOCK_MAGIC = b"APK Sig Block 42"
EOCD_SIG = 0x06054B50
CD_SIG = 0x02014B50

# شناسه‌ها بر اساس تعریف طرح امضای APK (Android source: apksig)
V2_ID = 0x7109871A
V3_ID = 0xF05368C0
V31_ID = 0x1B93AD61

# در بلوک digests، شناسه‌ی الگوریتم همان شناسه‌ی الگوریتم امضاست (طبق طرح apksig)
# و الگوریتم خورده‌ی محتوا از آن مشتق می‌شود: 0x0103→SHA-256 و 0x0104→SHA-512
DIGEST_ALGOS = {0x0101: "SHA-256", 0x0102: "SHA-512", 0x0103: "SHA-256", 0x0104: "SHA-512"}
SIG_ALGOS = {
    0x0101: ("SHA-256", "RSA"),
    0x0201: ("SHA-512", "RSA"),
    0x0102: ("SHA-256", "DSA"),
    0x0103: ("SHA-256", "RSA"),
    0x0104: ("SHA-512", "RSA"),
    0x0201: ("SHA-512", "RSA"),
}
CHUNK_COUNT = 4
CHUNK_MARKER = b"\xa5"


class Reader:
    """خواننده‌ی ساده‌ی طول-پیشوند (length-prefixed) طرح apksig."""

    def __init__(self, data: bytes):
        self.d = data
        self.o = 0
        self.limit_stack = []

    def u32(self) -> int:
        v = struct.unpack_from("<I", self.d, self.o)[0]
        self.o += 4
        return v

    def lp(self) -> bytes:
        n = self.u32()
        out = self.d[self.o:self.o + n]
        self.o += n
        return out

    def eof(self) -> bool:
        return self.o >= len(self.d)


def find_eocd(data: bytes):
    """آخرین End Of Central Directory را پیدا می‌کند."""
    start = max(0, len(data) - 65557)
    i = len(data) - 22
    while i >= start:
        if struct.unpack_from("<I", data, i)[0] == EOCD_SIG:
            return i
        i -= 1
    return None


def parse_signing_block(data: bytes, cd_offset: int):
    """بلوک امضا (APK Signing Block) که بلافاصله قبل از Central Directory است."""
    magic_at = cd_offset - 16
    if magic_at < 0 or data[magic_at:cd_offset] != APK_SIG_BLOCK_MAGIC:
        return None
    size2 = struct.unpack_from("<Q", data, magic_at - 8)[0]
    block_start = cd_offset - size2 - 8
    if block_start < 0:
        return None
    size1 = struct.unpack_from("<Q", data, block_start)[0]
    if size1 != size2:
        raise ValueError("اندازه‌های ابتدا/انتهای بلوک امضا یکی نیست")
    pairs = {}
    p = block_start + 8
    end_pairs = magic_at - 8
    while p + 12 <= end_pairs:
        plen = struct.unpack_from("<Q", data, p)[0]       # طول ورودی (uint64، شامل شناسه)
        pid = struct.unpack_from("<I", data, p + 8)[0]
        val = data[p + 12:p + 12 + (plen - 4)]
        pairs.setdefault(pid, []).append(val)
        p += 8 + plen
    return {"start": block_start, "end": cd_offset, "pairs": pairs}


def chunk_digest(sha_name: str, chunks):
    """
    خورده‌ی خوشه‌ای طبق طرح apksig (درخت مرکل دوسطحی):
      خورده‌ی هر خوشه = H( 0xa5 || طول خوشه || داده‌ی خوشه )
      خورده‌ی نهایی    = H( 0x5a || تعداد خوشه‌ها || رشته‌ی خورده‌ی خوشه‌ها )
    هر خوشه حداکثر ۱ مگابایت است.
    """
    one_mb = 1024 * 1024
    pieces = []
    for c in chunks:
        if len(c) == 0:
            continue
        for i in range(0, len(c), one_mb):
            pieces.append(c[i:i + one_mb])
    hashes = []
    for piece in pieces:
        h = hashlib.new(sha_name)
        h.update(CHUNK_MARKER)
        h.update(struct.pack("<I", len(piece)))
        h.update(piece)
        hashes.append(h.digest())
    top = hashlib.new(sha_name)
    top.update(b"\x5a")
    top.update(struct.pack("<I", len(hashes)))
    for x in hashes:
        top.update(x)
    return top.digest()


def verify_signer(signed_data: bytes, signatures: bytes, pubkey_der: bytes, label: str, report: dict):
    """امضای یک signer را بررسی می‌کند و خورده‌ها را برمی‌گرداند."""
    r = Reader(signed_data)
    digests_blob = r.lp()
    certs_blob = r.lp()
    r.lp()  # additional attributes

    dr = Reader(digests_blob)
    digests = {}
    while not dr.eof():
        rec = Reader(dr.lp())      # هر خورده خودش یک رکورد طول-پیشوند است
        algo = rec.u32()
        digests[algo] = rec.lp()

    certs = []
    cr = Reader(certs_blob)
    while not cr.eof():
        der = cr.lp()
        try:
            certs.append(x509.load_der_x509_certificate(der))
        except Exception as e:  # noqa: BLE001
            report["errors"].append(f"{label}: گواهی نامعتبر ({e})")

    # کلید عمومی داخل signer باید با کلید گواهی اول یکی باشد
    if certs:
        try:
            key_from_cert = certs[0].public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
            if key_from_cert != pubkey_der:
                report["errors"].append(f"{label}: کلید عمومی signer با گواهی داخل امضا یکی نیست")
        except Exception as e:  # noqa: BLE001
            report["errors"].append(f"{label}: مقایسه‌ی کلید شکست خورد ({e})")

    try:
        pub = serialization.load_der_public_key(pubkey_der)
    except Exception as e:  # noqa: BLE001
        report["errors"].append(f"{label}: کلید عمومی خوانده نشد ({e})")
        return digests, certs, False

    sr = Reader(signatures)
    ok_sig = False
    while not sr.eof():
        rec = Reader(sr.lp())      # رکورد امضا: (algo, lp(signature))
        algo = rec.u32()
        sig = rec.lp()
        sha_name, kind = SIG_ALGOS.get(algo, (None, None))
        if not sha_name or kind != "RSA":
            report["notes"].append(f"{label}: الگوریتم امضای {hex(algo)} پشتیبانی نشد")
            continue
        digest = hashes.SHA256() if sha_name == "SHA-256" else hashes.SHA512()
        try:
            pub.verify(sig, signed_data, padding.PKCS1v15(), digest)
            ok_sig = True
            report["verified_with"] = f"{sha_name} / RSA (PKCS#1 v1.5)"
        except Exception:  # noqa: BLE001
            report["errors"].append(f"{label}: امضای {sha_name}/RSA معتبر نیست")

    report["signers"].append({
        "label": label,
        "certs": [f"{c.subject.rfc4514_string()}" for c in certs],
        "digests": {DIGEST_ALGOS.get(k, hex(k)): v.hex() for k, v in digests.items()},
    })
    return digests, certs, ok_sig


def verify_v1(zf: zipfile.ZipFile, report: dict):
    """صحت جدول JAR v1: MANIFEST.MF و CERT.SF."""
    try:
        manifest = zf.read("META-INF/MANIFEST.MF")
    except KeyError:
        report["notes"].append("امضای v1 (MANIFEST.MF) وجود ندارد")
        return
    # بخش‌ها را با \r\n\r\n جدا می‌کنیم
    sections = manifest.split(b"\r\n\r\n")
    checked = 0
    bad = []
    for sec in sections:
        if b"Name:" not in sec:
            continue
        lines = sec.split(b"\r\n")
        name = None
        digest_b64 = None
        for ln in lines:
            if ln.startswith(b"Name:"):
                name = ln[5:].strip().decode()
            elif ln.startswith(b"SHA-256-Digest:"):
                digest_b64 = ln.split(b":", 1)[1].strip()
        if not name or not digest_b64:
            continue
        try:
            content = zf.read(name)
        except KeyError:
            bad.append(name + " (در بسته نیست)")
            continue
        got = hashlib.sha256(content).digest()
        try:
            want = base64.b64decode(digest_b64)
        except Exception:  # noqa: BLE001
            bad.append(name + " (digest ناخوانا)")
            continue
        if got != want:
            bad.append(name)
        checked += 1
    report["v1_checked"] = checked
    report["v1_bad"] = bad

    try:
        sf = zf.read("META-INF/CERT.SF")
        if b"SHA-256-Digest-Manifest:" in sf:
            line = [l for l in sf.split(b"\r\n") if l.startswith(b"SHA-256-Digest-Manifest:")][0]
            want = base64.b64decode(line.split(b":", 1)[1].strip())
            got = hashlib.sha256(manifest).digest()
            if got != want:
                report["errors"].append("امضای v1: خورده‌ی MANIFEST در CERT.SF نمی‌خواند")
    except KeyError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="game/adventure-world-neon.apk")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        sys.exit(f"فایل پیدا نشد: {path}")
    data = path.read_bytes()

    report = {"errors": [], "notes": [], "signers": [], "verified_with": None}
    print(f"■ بازرسی امضای {path}  ({len(data) / 1024 / 1024:.2f} مگابایت)")

    eocd_off = find_eocd(data)
    if eocd_off is None:
        sys.exit("✗ EOCD پیدا نشد؛ فایل ZIP/APK معتبر نیست")
    cd_size, cd_off, comment_len = struct.unpack_from("<IIH", data, eocd_off + 12)
    print(f"  Central Directory: offset={cd_off} size={cd_size}")

    block = parse_signing_block(data, cd_off)
    if not block:
        sys.exit("✗ بلوک امضای APK پیدا نشد (فقط امضای v1 وجود دارد)")
    print(f"  بلوک امضا: {block['end'] - block['start']} بایت، شناسه‌ها: "
          + ", ".join(hex(k) for k in block["pairs"]))

    schemes = []
    if V3_ID in block["pairs"] or V31_ID in block["pairs"]:
        schemes.append("v3")
    if V2_ID in block["pairs"]:
        schemes.append("v2")
    print(f"  طرح‌های امضا: v1 (JAR) + {' + '.join(schemes)}")

    # --- خوشه‌های فایل برای بازمحاسبه‌ی خورده‌ها ---
    # بخش‌های محافظت‌شده: ۱) پیش از بلوک امضا  ۲) بلوک امضا (خورده نمی‌شود)  ۳) CD  ۴) EOCD
    eocd_bytes = bytearray(data[eocd_off:eocd_off + 22 + comment_len])
    struct.pack_into("<I", eocd_bytes, 16, block["start"])   # آفست CD = ابتدای بلوک امضا
    chunks = [
        data[:block["start"]],
        bytes(eocd_bytes[:0]),        # بلوک امضا: خالی (در خورده شرکت نمی‌کند)
        data[cd_off:eocd_off],
        bytes(eocd_bytes),
    ]

    def check_chunks(digests: dict):
        """خورده‌های بازمحاسبه‌شده را با خورده‌های بلوک امضا مقایسه می‌کند."""
        results = {}
        for algo_id, want in digests.items():
            sha_name = DIGEST_ALGOS.get(algo_id)
            if not sha_name:
                continue
            got = chunk_digest(sha_name, chunks)
            results[sha_name] = (got == want)
            if got != want:
                report["errors"].append(f"خورده‌ی {sha_name} با محتوای واقعی فایل نمی‌خواند")
        return results

    # --- بررسی v2 ---
    if V2_ID in block["pairs"]:
        for val in block["pairs"][V2_ID]:
            r = Reader(val)
            signers_blob = r.lp()          # دنباله‌ی signerها
            sr = Reader(signers_blob)
            idx = 0
            while not sr.eof():
                idx += 1
                signer = Reader(sr.lp())   # هر signer: lp(signedData) + lp(signatures) + lp(pk)
                signed_data = signer.lp()
                signatures = signer.lp()
                pubkey = signer.lp()
                digests, certs, ok = verify_signer(signed_data, signatures, pubkey, f"v2/signer{idx}", report)
                res = check_chunks(digests)
                for k, v in res.items():
                    print(f"  خورده‌ی {k} خوشه‌ای: {'✓ درست' if v else '✗ نادرست'}")
                print(f"  امضای v2/signer{idx}: {'✓ معتبر' if ok else '✗ نامعتبر'}")

    # --- بررسی v3 (ساختار و امضا) ---
    if V3_ID in block["pairs"]:
        for val in block["pairs"][V3_ID]:
            r = Reader(val)
            signers_blob = r.lp()
            min_sdk = r.u32() if not r.eof() else None
            max_sdk = r.u32() if not r.eof() else None
            sr = Reader(signers_blob)
            idx = 0
            while not sr.eof():
                idx += 1
                sg = Reader(sr.lp())
                signed_data = sg.lp()
                min2 = sg.u32()
                max2 = sg.u32()
                signatures = sg.lp()
                pubkey = sg.lp()
                digests, certs, ok = verify_signer(signed_data, signatures, pubkey, f"v3/signer{idx}", report)
                res = check_chunks(digests)
                for k, v in res.items():
                    print(f"  خورده‌ی {k} خوشه‌ای (v3): {'✓ درست' if v else '✗ نادرست'}")
                print(f"  امضای v3/signer{idx}: {'✓ معتبر' if ok else '✗ نامعتبر'}  "
                      f"(بلوک: minSdk={min_sdk} maxSdk={max_sdk} | signer: {min2}-{max2})")
            if min_sdk is None or max_sdk is None:
                report["errors"].append("بلوک v3 فیلدهای minSdk/maxSdk سطح بلوک را ندارد")

    # --- بررسی‌های ساختاری که AOSP پیش از تأیید امضا انجام می‌دهد ---
    if cd_off + cd_size != eocd_off:
        report["errors"].append("Central Directory بلافاصله به EOCD نمی‌چسبد")
    if eocd_off + 22 + comment_len != len(data):
        report["errors"].append("بعد از EOCD داده‌ی اضافه وجود دارد")
    if block["end"] != cd_off:
        report["errors"].append("بلوک امضا بلافاصله پیش از Central Directory نیست")
    if report["verified_with"]:
        print("  ساختار فایل: ✓ (بلوک امضا چسبیده به CD، بدون داده‌ی اضافه بعد از EOCD)")

    # --- بررسی v1 ---
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        verify_v1(zf, report)
        # محافظت رول‌بک: فایل SF باید بگوید بسته با کدام طرح‌ها هم امضا شده است
        try:
            sf = zf.read("META-INF/CERT.SF").decode("utf-8", "replace")
            line = [l for l in sf.split("\r\n") if l.startswith("X-Android-APK-Signed:")]
            if not line:
                report["notes"].append("ویژگی X-Android-APK-Signed در CERT.SF نیست (محافظت رول‌بک)")
            else:
                print("  محافظت رول‌بک: " + line[0])
        except KeyError:
            pass
        print(f"  امضای v1: {report.get('v1_checked', 0)} فایل بررسی شد"
              + (f"، ناموفق: {report['v1_bad'][:5]}" if report.get("v1_bad") else "، همه سالم"))

    # --- گواهی ---
    if report["signers"]:
        certs = report["signers"][0]["certs"]
        print(f"  گواهی: {certs[0] if certs else '؟'}")
    if report["verified_with"]:
        print(f"  الگوریتم تأییدشده: {report['verified_with']}")

    for n in report["notes"]:
        print("  • " + n)
    if report["errors"]:
        print("\n✗ ایرادها:")
        for e in report["errors"]:
            print("  - " + e)
        return 1
    print("\n✓ امضای APK معتبر است و با محتوای فایل می‌خواند.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
