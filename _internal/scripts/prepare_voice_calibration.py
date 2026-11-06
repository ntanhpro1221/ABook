"""Chuẩn bị model ghim cho bộ đo, chỉ ghi trong thư mục tác vụ."""
import hashlib
import io
import os
from pathlib import Path
import shutil
import sys
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from abook.webui import zerotts_module as z, supertonic_module as s
from abook.webui import vieneu_module as v


def main(folder):
    folder.mkdir(parents=True, exist_ok=True)
    code = urllib.request.urlopen(z.CODE.url, timeout=120).read()
    assert hashlib.sha256(code).hexdigest() == z.CODE.sha256
    lib = folder / "zerotts" / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(code)) as archive:
        for name in archive.namelist():
            assert (lib / name).resolve().is_relative_to(lib.resolve())
        archive.extractall(lib)
    for spec in s.FILES:
        dest = folder / "supertonic" / spec.name
        cached = Path.home() / ".cache/supertonic3" / spec.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest() == spec.sha256:
            continue
        if cached.is_file() and hashlib.sha256(cached.read_bytes()).hexdigest() == spec.sha256:
            shutil.copyfile(cached, dest)
        else:
            data = urllib.request.urlopen(spec.url, timeout=180).read()
            assert hashlib.sha256(data).hexdigest() == spec.sha256, spec.name
            dest.write_bytes(data)
        print("VERIFIED", spec.name, flush=True)


def readaloud(folder):
    for tier, specs in (("turbo", v.TURBO_FILES), ("nano", v.NANO_FILES)):
        for spec in specs:
            dest = folder / "readaloud" / tier / spec.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest() == spec.sha256:
                continue
            cached = None
            if "huggingface.co/" in spec.url and "/resolve/" in spec.url:
                repo, tail = spec.url.split("huggingface.co/", 1)[1].split("/resolve/")
                revision, name = tail.split("/", 1)
                cached = Path.home() / ".cache/huggingface/hub" / ("models--" + repo.replace("/", "--")) / "snapshots" / revision / name
            if cached is not None and cached.is_file() and hashlib.sha256(cached.read_bytes()).hexdigest() == spec.sha256:
                shutil.copyfile(cached, dest)
            else:
                data = urllib.request.urlopen(spec.url, timeout=180).read()
                assert hashlib.sha256(data).hexdigest() == spec.sha256, spec.name
                dest.write_bytes(data)
            print("VERIFIED", tier, spec.name, flush=True)
    code = urllib.request.urlopen(v.VOICES.url, timeout=120).read()
    assert hashlib.sha256(code).hexdigest() == v.VOICES.sha256
    voices = folder / "readaloud" / "voices"
    voices.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(code)) as archive:
        for member, name in v.VOICE_MEMBERS.items():
            (voices / name).write_bytes(archive.read(member))


if __name__ == "__main__":
    if "--readaloud" in sys.argv:
        readaloud(Path(sys.argv[1]))
    else:
        main(Path(sys.argv[1]))
