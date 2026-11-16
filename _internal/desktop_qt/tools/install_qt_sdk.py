"""Install checksum-verified Windows desktop archives from Qt's architecture repository."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from qt_sdk import qt_version


def archive_plan(xml: bytes, version: str, addons: list[str]) -> list[dict]:
    stem = "qt.qt6." + version.replace(".", "")
    names = [stem + ".win64_msvc2022_64"]
    names += [stem + ".addons." + addon + ".win64_msvc2022_64" for addon in addons]
    packages = {node.findtext("Name"): node for node in ET.fromstring(xml).findall("PackageUpdate")}
    result = []
    for name in names:
        node = packages[name]
        package_version = node.findtext("Version")
        if not package_version or not package_version.startswith(version + "-"):
            raise ValueError(f"Unexpected package version: {name}: {package_version}")
        for archive in (node.findtext("DownloadableArchives") or "").split(","):
            archive = archive.strip()
            if not re.fullmatch(r"[A-Za-z0-9_.-]+\.7z", archive):
                raise ValueError(f"Invalid archive name: {archive!r}")
            result.append(dict(package=name, version=package_version, archive=archive,
                               relative_url=f"{name}/{package_version}{archive}"))
    return result


def fetch(url: str, path: Path) -> None:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as response, path.open("wb") as stream:
                shutil.copyfileobj(response, stream, 1024 * 1024)
            return
        except (OSError, urllib.error.URLError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def verified_archive(base: str, row: dict, cache: Path) -> Path:
    url = base + row["relative_url"]
    checksum = None
    for algorithm in ("sha256", "sha1"):
        sidecar = cache / (row["archive"] + "." + algorithm)
        try:
            fetch(url + "." + algorithm, sidecar)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                continue
            raise
        checksum = sidecar.read_text(encoding="ascii").split()[0].lower()
        if not re.fullmatch("[0-9a-f]{" + str(hashlib.new(algorithm).digest_size * 2) + "}", checksum):
            raise ValueError(f"Invalid {algorithm} checksum: {sidecar}")
        break
    if checksum is None:
        raise ValueError(f"No repository checksum for {url}")
    archive = cache / row["archive"]
    def digest():
        with archive.open("rb") as stream:
            return hashlib.file_digest(stream, algorithm).hexdigest()
    if not archive.exists() or digest() != checksum:
        part = archive.with_suffix(".7z.part")
        fetch(url, part)
        with part.open("rb") as stream:
            actual = hashlib.file_digest(stream, algorithm).hexdigest()
        if actual != checksum:
            raise ValueError(f"Checksum mismatch: {url}: {actual} != {checksum}")
        part.replace(archive)
    row.update(url=url, algorithm=algorithm, checksum=checksum, bytes=archive.stat().st_size)
    print(f"VERIFIED {row['archive']} {algorithm}={checksum} bytes={row['bytes']}", flush=True)
    return archive


def extract(archive: Path, destination: Path, version: str) -> None:
    import py7zr
    with py7zr.SevenZipFile(archive) as packed:
        names = packed.getnames()
        if archive.name in {"d3dcompiler_47-x64.7z", "opengl32sw-64-mesa_11_2_2-signed_sha256.7z"}:
            expected = "d3dcompiler_47.dll" if archive.name.startswith("d3dcompiler") else "opengl32sw.dll"
            if names != [expected]:
                raise ValueError(f"Unexpected support DLL archive entries: {names}")
            packed.extractall(destination / "bin")
            print(f"EXTRACTED {archive.name}: bin/{expected}", flush=True)
            return
        # Architecture repository archives contain paths relative to the SDK root.
        for name in names:
            path = PurePosixPath(name.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or ":" in name:
                raise ValueError(f"Unsafe archive entry: {name}")
            if not path.parts or (path.parts[0] not in {"bin", "doc", "include", "lib", "libexec", "metatypes", "mkspecs", "modules", "plugins", "qml", "resources", "share", "translations", "phrasebooks", "LICENSES", "licenses", "sbom"}
                                  and not re.fullmatch(r"config_[a-z0-9_]+\.(opt|summary)", name)):
                raise ValueError(f"Unexpected SDK entry: {name}")
        packed.extractall(destination)
    print(f"EXTRACTED {archive.name}: {len(names)} entries", flush=True)


def configure(root: Path) -> dict:
    (root / "bin/qt.conf").write_text("[Paths]\nPrefix=..\n", encoding="ascii", newline="\n")
    config = root / "mkspecs/qconfig.pri"
    text = config.read_text(encoding="utf-8")
    text = re.sub(r"^QT_EDITION =.*$", "QT_EDITION = OpenSource", text, flags=re.M)
    text = re.sub(r"^QT_LICHECK =.*$", "QT_LICHECK =", text, flags=re.M)
    config.write_text(text, encoding="utf-8", newline="\n")
    for pattern in ("lib/**/*.prl", "lib/pkgconfig/*.pc"):
        for path in root.glob(pattern):
            text = path.read_text(encoding="utf-8")
            fixed = text.replace("c:/Users/qt/work/install/lib", "$$[QT_INSTALL_LIBS]" if path.suffix == ".prl" else str(root / "lib"))
            fixed = fixed.replace("c:/Users/qt/work/install", str(root))
            if fixed != text:
                path.write_text(fixed, encoding="utf-8", newline="\n")
    target = root / "bin/target_qt.conf"
    if target.exists():
        raise ValueError(f"Unexpected cross-target configuration: inspect {target}")
    result = {}
    for program in ("qmake", "qtpaths"):
        done = subprocess.run([str(root / f"bin/{program}.exe"), "-query"], check=True,
                              capture_output=True, text=True, encoding="utf-8",
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        result[program] = done.stdout
        values = dict(line.split(":", 1) for line in done.stdout.splitlines() if ":" in line)
        if Path(values["QT_INSTALL_PREFIX"]).resolve() != root.resolve() or values["QT_VERSION"] != qt_version():
            raise ValueError(f"SDK query mismatch: {done.stdout}")
        print(program, done.stdout, flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True, help="SDK parent containing version directories")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--addon", action="append", default=[])
    parser.add_argument("--python-libraries", type=Path, help="Optional existing py7zr site-packages")
    args = parser.parse_args()
    if args.python_libraries:
        sys.path.append(str(args.python_libraries))
    version = qt_version()
    folder = "qt6_" + version.replace(".", "")
    base = f"https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/{folder}/{folder}_msvc2022_64/"
    args.cache.mkdir(parents=True, exist_ok=True)
    metadata = args.cache / "Updates.xml"
    fetch(base + "Updates.xml", metadata)
    plan = archive_plan(metadata.read_bytes(), version, args.addon)
    archives = [verified_archive(base, row, args.cache) for row in plan]
    root = args.destination / version / "msvc2022_64"
    root.mkdir(parents=True, exist_ok=True)
    for archive in archives:
        extract(archive, root, version)
    queries = configure(root)
    (args.cache / "installed.json").write_text(json.dumps(dict(version=version, repository=base, archives=plan, queries=queries), indent=2),
                                               encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
