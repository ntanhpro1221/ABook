"""Prepare the ONNX Runtime native libraries the phone downloads on demand (docs/MUSIC_IMPORT.md, "Gói nhạc").

The APK carries ONNX Runtime's Java API only (vendored in app/src/main/java/ai/onnxruntime); the two native libraries per ABI
(`libonnxruntime.so`, `libonnxruntime4j_jni.so`) are fetched by MusicStudentSetup. This script builds the files to host from the
official Maven Central AAR of the SAME version as the vendored sources: it downloads the AAR (SHA-256 pinned below), takes
`jni/<abi>/*.so`, gzips them deterministically (the phone gunzips and verifies the raw file too) and prints the `Part(...)` lines
for OrtRuntime.kt plus a manifest. Upload `<out>/ort/<version>/` to the model repo yourself; this script never uploads.

    python scripts/prepare_ort_runtime.py --out D:/Novels/LLM_Train/ort_build/hosting [--aar path-to-aar]
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

VERSION = "1.30.0"
AAR_URL = f"https://repo1.maven.org/maven2/com/microsoft/onnxruntime/onnxruntime-android/{VERSION}/onnxruntime-android-{VERSION}.aar"
AAR_SHA256 = "e7fb945e402205f6db858d65bb78d2bdb0812317b383976c9e3bceb4862c73f1"
ABIS = ("arm64-v8a", "armeabi-v7a", "x86_64")  # x86 (32-bit) is not offered: no phone sold in a decade is x86
LIBRARIES = ("libonnxruntime.so", "libonnxruntime4j_jni.so")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def gz(data: bytes) -> bytes:
    """Deterministic gzip: no name, mtime 0 - the same input always gives the same bytes (so the pinned hash is reproducible)."""
    out = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=out, compresslevel=9, mtime=0) as handle:
        handle.write(data)
    return out.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--aar", type=Path, help="a local copy of the AAR (otherwise downloaded from Maven Central)")
    args = parser.parse_args()

    blob = args.aar.read_bytes() if args.aar else urllib.request.urlopen(AAR_URL, timeout=120).read()
    if sha256(blob) != AAR_SHA256:
        print(f"AAR SHA-256 mismatch: {sha256(blob)} != {AAR_SHA256}", file=sys.stderr)
        return 1
    manifest: dict[str, dict[str, dict[str, object]]] = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as bundle:
        for abi in ABIS:
            target = args.out / "ort" / VERSION / abi
            target.mkdir(parents=True, exist_ok=True)
            for name in LIBRARIES:
                raw = bundle.read(f"jni/{abi}/{name}")
                packed = gz(raw)
                (target / f"{name}.gz").write_bytes(packed)
                manifest.setdefault(abi, {})[name] = {
                    "size": len(raw), "sha256": sha256(raw), "packedSize": len(packed), "packedSha256": sha256(packed),
                }
    (args.out / "ort" / VERSION / "manifest.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    for abi, entries in manifest.items():
        total = sum(int(entry["packedSize"]) for entry in entries.values())
        print(f"{abi}: download {total / 1e6:.1f} MB")
        for name, entry in entries.items():
            print(f'    Part("{name}", "{entry["sha256"]}", {entry["size"]}, packed = Packed("{entry["packedSha256"]}", {entry["packedSize"]})),')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
