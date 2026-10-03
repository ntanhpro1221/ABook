"""Stage the phone's "Giọng VieNeu" module on the desktop for VieneuOnDeviceTest (mobile/android/app/src/androidTest/.../VieneuOnDeviceTest.kt).

Lays the files out exactly as VieneuModule.kt downloads them (`ort/`, `g2p/`, `voices/`, `nano/`, `turbo/`), from what this machine already
has: the VieNeu models in the Hugging Face cache (the pinned commits of abook/webui/vieneu_module.py, SHA-256 checked), sea-g2p's dictionary
from the runtime venv, the JNI library built by scripts/prepare_sea_g2p_android.py, and - fetched once over HTTPS - the pinned vieneu 3.8.1
wheel and the pinned ONNX Runtime libraries of "Gói nhạc". The phone checks every file against its own pins again before using it.

    runtime/.venv/Scripts/python.exe scripts/vieneu_phone_module_stage.py --abi arm64-v8a --out D:/tmp/vieneu_module [--tiers nano,turbo]
    adb push D:/tmp/vieneu_module/. /data/local/tmp/vieneu
    adb shell am instrument -w -e class vn.abook.player.VieneuOnDeviceTest com.ngdtuanh.abook.test/androidx.test.runner.AndroidJUnitRunner
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import shutil
import sys
import urllib.request
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abook.webui import music_student, vieneu_module

TRIPLES = {"arm64-v8a": "aarch64-linux-android", "armeabi-v7a": "armv7-linux-androideabi", "x86_64": "x86_64-linux-android"}
ORT_VERSION = "1.30.0"  # OrtRuntime.VERSION
ORT_LIBRARIES = ("libonnxruntime.so", "libonnxruntime4j_jni.so")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def hf_file(url: str) -> Path:
    """The Hugging Face cache path of a pinned `.../resolve/<commit>/<path>` URL."""
    repo, _, rest = url.removeprefix("https://huggingface.co/").partition("/resolve/")
    commit, _, path = rest.partition("/")
    hub = next((hub for hub in (Path(os.environ.get("HF_HOME", "-")) / "hub", Path.home() / ".cache" / "huggingface" / "hub")
                if (hub / f"models--{repo.replace('/', '--')}").is_dir()), Path.home() / ".cache" / "huggingface" / "hub")
    return hub / f"models--{repo.replace('/', '--')}" / "snapshots" / commit / path


def place(source: Path, target: Path, expected: str | None = None) -> None:
    if expected is not None and sha256(source) != expected:
        raise SystemExit(f"{source} does not match its pin")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--abi", required=True, choices=sorted(TRIPLES))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--tiers", default="nano,turbo")
    args = parser.parse_args()
    out: Path = args.out
    shutil.rmtree(out, ignore_errors=True)

    for name in ORT_LIBRARIES:
        url = f"https://huggingface.co/{music_student.REPO_ID}/resolve/{music_student.REVISION}/ort/{ORT_VERSION}/{args.abi}/{name}.gz"
        (out / "ort").mkdir(parents=True, exist_ok=True)
        (out / "ort" / name).write_bytes(gzip.decompress(urllib.request.urlopen(url, timeout=300).read()))
    library = ROOT / "mobile" / "sea_g2p_jni" / "target" / TRIPLES[args.abi] / "release" / "libabook_sea_g2p.so"
    if not library.is_file():
        raise SystemExit(f"{library} missing: run scripts/prepare_sea_g2p_android.py first")
    place(library, out / "g2p" / "libabook_sea_g2p.so")
    import sea_g2p

    place(Path(sea_g2p.__file__).parent / "sea_g2p.bin", out / "g2p" / "sea_g2p.bin")
    wheel = out / "voices" / "vieneu-3.8.1-py3-none-any.whl"
    wheel.parent.mkdir(parents=True, exist_ok=True)
    wheel.write_bytes(urllib.request.urlopen(vieneu_module.VOICES.url, timeout=300).read())
    if sha256(wheel) != vieneu_module.VOICES.sha256:
        raise SystemExit("the vieneu wheel does not match its pin")
    files = {"turbo": vieneu_module.TURBO_FILES, "nano": vieneu_module.NANO_FILES}
    for tier in [t.strip() for t in args.tiers.split(",") if t.strip()]:
        for item in files[tier]:
            place(hf_file(item.url), out / tier / item.name, item.sha256)
    total = sum(path.stat().st_size for path in out.rglob("*") if path.is_file())
    print(f"staged {total / 1e6:.1f} MB in {out}\n  adb push {out}/. /data/local/tmp/vieneu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
