"""Build sea-g2p (text -> phonemes for VieNeu) for the phone: the JNI library the "Giọng VieNeu" module downloads on tap.

The desktop runs sea-g2p from its PyPI wheel (abook/webui/vieneu_module.py, part "g2p"); the phone cannot run the wheel, so this
script builds the SAME Rust crate as a JNI library (docs/LISTEN_ANYTHING.md, section 3, "VieNeu on the phone"):

1. downloads the pinned sea-g2p sdist from PyPI (SHA-256 below) into mobile/sea_g2p_jni/build/ and strips its PyO3 bindings - the
   only change: the Python module glue (`src/lib.rs`, the `#[pyclass]` / `#[pymethods]` attributes and the one batch method that
   needs a Python thread handle). The normaliser and G2P code are untouched, dependency versions come from the sdist's own Cargo.lock;
2. builds mobile/sea_g2p_jni (the JNI wrapper) with cargo-ndk for arm64-v8a, armeabi-v7a and x86_64 (the emulator), and for the
   host (the JVM parity test, SeaG2pParityTest);
3. gzips each .so deterministically into <out>/sea-g2p/<version>/<abi>/ and prints the `Part(...)` lines for VieneuModule.kt.

The dictionary (`sea_g2p.bin`, 63 MB) is NOT rebuilt: the phone takes it out of the same pinned wheel the desktop downloads.
Upload `<out>/sea-g2p/<version>/` to the model repo yourself (next to `ort/`); this script never uploads.

    runtime/.venv/Scripts/python.exe scripts/prepare_sea_g2p_android.py --out D:/Novels/LLM_Train/sea_g2p_build/hosting
    (needs cargo + cargo-ndk, `rustup target add aarch64-linux-android armv7-linux-androideabi x86_64-linux-android`,
    and an Android NDK - ANDROID_NDK_HOME, or the newest one under the SDK of mobile/android/local.properties)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

VERSION = "0.9.1"
SDIST_URL = ("https://files.pythonhosted.org/packages/4a/b7/e1b8ea81f220a719a57c2e1da439cf0396f36f257bf145ba4502554f0823/"
             f"sea_g2p-{VERSION}.tar.gz")
SDIST_SHA256 = "9ecb286442c34c96b8a2f20bf32196c168271600a8bad1cf23825d0e1b8fb3da"
ABIS = ("arm64-v8a", "armeabi-v7a", "x86_64")
LIBRARY = "libabook_sea_g2p.so"
MIN_SDK = 24  # mobile/android/variables.gradle minSdkVersion

ROOT = Path(__file__).resolve().parents[1]
CRATE = ROOT / "mobile" / "sea_g2p_jni"
SOURCE = CRATE / "build" / f"sea_g2p-{VERSION}"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def gz(data: bytes) -> bytes:
    """Deterministic gzip (no name, mtime 0), as scripts/prepare_ort_runtime.py: the pinned hash is reproducible."""
    out = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=out, compresslevel=9, mtime=0) as handle:
        handle.write(data)
    return out.getvalue()


def _replace(text: str, old: str, new: str, path: str) -> str:
    if old not in text:
        raise SystemExit(f"patch: {path} no longer contains {old!r} - check the new sea-g2p version by hand")
    return text.replace(old, new)


def strip_pyo3(source: Path) -> None:
    """Remove the PyO3 bindings so the crate builds as a plain Rust library (no Python on the phone)."""
    cargo = source / "Cargo.toml"
    text = cargo.read_bytes().decode("utf-8")
    text = _replace(text, 'crate-type = ["cdylib", "rlib"]', 'crate-type = ["rlib"]', "Cargo.toml")
    text = "\n".join(line for line in text.split("\n") if not line.startswith(("pyo3 =", "pyo3-build-config =")))
    text = _replace(text, "[build-dependencies]\n", "", "Cargo.toml")
    cargo.write_bytes(text.encode("utf-8"))

    lib = source / "src" / "lib.rs"
    text = lib.read_bytes().decode("utf-8")
    head = text.split("use pyo3::prelude::*;", 1)[0]
    lib.write_bytes((head + "pub mod core;\npub mod g2p;\npub mod lang;\npub mod punc;\n").encode("utf-8"))

    vi = source / "src" / "lang" / "vi" / "mod.rs"
    text = vi.read_bytes().decode("utf-8")
    text = _replace(text, "use pyo3::prelude::*;\n", "", "vi/mod.rs")
    text = _replace(text, "#[pyclass]\npub struct Normalizer {\n    #[pyo3(get)]\n", "pub struct Normalizer {\n", "vi/mod.rs")
    text = _replace(text, "#[pymethods]\nimpl Normalizer {\n    #[new]\n    #[pyo3(signature = (lang=\"vi\", dict_path=None))]\n",
                    "impl Normalizer {\n", "vi/mod.rs")
    text = _replace(text, "    #[pyo3(signature = (text, punc_norm=false))]\n    pub fn normalize(", "    pub fn normalize(", "vi/mod.rs")
    start = text.index("    #[pyo3(signature = (texts, punc_norm=false))]\n    pub fn normalize_batch(")
    end = text.index("\n    }\n", text.index("py.allow_threads", start)) + len("\n    }\n")
    text = text[:start].rstrip(" \n") + "\n" + text[end:]
    if "pyo3" in text or "Python<" in text:
        raise SystemExit("patch: vi/mod.rs still mentions PyO3")
    vi.write_bytes(text.encode("utf-8"))


def unpack(sdist: bytes) -> None:
    shutil.rmtree(SOURCE, ignore_errors=True)
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(sdist), mode="r:gz") as archive:
        archive.extractall(SOURCE.parent, filter="data")
    strip_pyo3(SOURCE)
    lock = CRATE / "Cargo.lock"
    if not lock.exists():  # first build: start from the sdist's own lock so regex & co. are the versions the wheel was built with
        shutil.copyfile(SOURCE / "Cargo.lock", lock)


def ndk_home() -> str:
    found = os.environ.get("ANDROID_NDK_HOME")
    if found:
        return found
    props = ROOT / "mobile" / "android" / "local.properties"
    for line in props.read_text(encoding="utf-8").splitlines() if props.exists() else []:
        if line.startswith("sdk.dir="):
            ndks = sorted((Path(line.split("=", 1)[1].strip()) / "ndk").glob("*"))
            if ndks:
                return str(ndks[-1])
    raise SystemExit("no Android NDK: set ANDROID_NDK_HOME")


def build(locked: bool) -> dict[str, Path]:
    # Source paths end up in panic messages: strip this machine's folders (user name, checkout) so the library is reproducible and
    # carries nothing personal.
    cargo_home = Path(os.environ.get("CARGO_HOME") or Path.home() / ".cargo")
    remap = [f"--remap-path-prefix={cargo_home}=/cargo", f"--remap-path-prefix={CRATE}=/sea_g2p_jni"]
    env = {**os.environ, "ANDROID_NDK_HOME": ndk_home(), "CARGO_ENCODED_RUSTFLAGS": "\x1f".join(remap)}
    lock = ["--locked"] if locked else []
    targets = [arg for abi in ABIS for arg in ("-t", abi)]
    subprocess.run(["cargo", "ndk", *targets, "--platform", str(MIN_SDK), "build", "--release", *lock], cwd=CRATE, env=env, check=True)
    subprocess.run(["cargo", "build", "--release", *lock], cwd=CRATE, env=env, check=True)  # host library for the JVM test
    triples = {"arm64-v8a": "aarch64-linux-android", "armeabi-v7a": "armv7-linux-androideabi", "x86_64": "x86_64-linux-android"}
    return {abi: CRATE / "target" / triple / "release" / LIBRARY for abi, triple in triples.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--sdist", type=Path, help="a local copy of the sdist (otherwise downloaded from PyPI)")
    parser.add_argument("--unlocked", action="store_true", help="let cargo update Cargo.lock (only when changing a dependency)")
    args = parser.parse_args()

    blob = args.sdist.read_bytes() if args.sdist else urllib.request.urlopen(SDIST_URL, timeout=300).read()
    if sha256(blob) != SDIST_SHA256:
        print(f"sdist SHA-256 mismatch: {sha256(blob)} != {SDIST_SHA256}", file=sys.stderr)
        return 1
    unpack(blob)
    libraries = build(locked=not args.unlocked and (CRATE / "Cargo.lock").exists())
    lines = []
    for abi, path in libraries.items():
        raw = path.read_bytes()
        packed = gz(raw)
        target = args.out / "sea-g2p" / VERSION / abi
        target.mkdir(parents=True, exist_ok=True)
        (target / f"{LIBRARY}.gz").write_bytes(packed)
        lines.append(f'"{abi}" to g2pLib("{abi}", "{sha256(raw)}", {len(raw):_}, "{sha256(packed)}", {len(packed):_}),')
        print(f"{abi}: {len(raw):,} bytes, {len(packed):,} gzipped")
    print("\n".join(lines))
    print(f"upload {args.out / 'sea-g2p'} to the model repo, then pin its commit in VieneuModule.G2P_REVISION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
