"""Install the Windows desktop Qt SDK from Qt's architecture repository, every archive checked against a SHA-256 pinned in the repo.

The pins live in desktop_qt/qt_sdk_pins.json (package -> repository version -> archive -> sha256 + bytes). The server's own
.sha256/.sha1 files are never trusted for an install: an archive without a pin, or a repository whose package list differs
from the pins, stops the install before anything is downloaded or extracted. `--record-pins` is the only path that reads a
server checksum, to pin a new Qt version: it accepts SHA-256 only (a SHA-1-only archive is refused), writes the pins file and
installs nothing - review the diff, cross-check against a second mirror and commit it before installing.

py7zr is pinned too (desktop_qt/tools/qt_sdk_requirements.txt, with wheel hashes); another version refuses to extract.

  install_qt_sdk.py --destination <parent of version dirs> --cache <dir>                  whole SDK (base + REQUIRED_ADDONS)
  install_qt_sdk.py --destination ... --cache ... --only-addon qtimageformats             one addon into an existing SDK
  install_qt_sdk.py --destination ... --cache ... --record-pins                           pin a new QT_VERSION (no install)
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
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

from qt_sdk import qt_version, validate_qt_root

PINS_FILE = Path(__file__).resolve().parents[1] / "qt_sdk_pins.json"
REQUIREMENTS_FILE = Path(__file__).resolve().parent / "qt_sdk_requirements.txt"
# The app needs these on top of the base package: QtMultimedia (sound), QtTaskTree (Qt6QmlAssetDownloaderPrivate),
# QtImageFormats (qwebp: every voice portrait and character avatar is WebP).
REQUIRED_ADDONS = ("qtmultimedia", "qttasktree", "qtimageformats")
SHA256 = re.compile(r"[0-9a-f]{64}")


def package_names(version: str, addons: list[str] | tuple[str, ...], base: bool = True) -> list[str]:
    stem = "qt.qt6." + version.replace(".", "")
    names = [stem + ".win64_msvc2022_64"] if base else []
    for addon in addons:
        if not re.fullmatch(r"[a-z0-9_]+", addon):
            raise ValueError(f"Invalid addon name: {addon!r}")
        name = stem + ".addons." + addon + ".win64_msvc2022_64"
        if name not in names:
            names.append(name)
    return names


def archive_plan(xml: bytes, version: str, names: list[str]) -> list[dict]:
    packages = {node.findtext("Name"): node for node in ET.fromstring(xml).findall("PackageUpdate")}
    result = []
    for name in names:
        node = packages.get(name)
        if node is None:
            raise ValueError(f"Package not in the repository: {name}")
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


def load_pins(path: Path = PINS_FILE) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    for name, package in data["packages"].items():
        for archive, pin in package["archives"].items():
            if not SHA256.fullmatch(str(pin.get("sha256", ""))) or not isinstance(pin.get("bytes"), int):
                raise ValueError(f"Pin must be a SHA-256 and a size: {name}/{archive}")
    return data


def apply_pins(plan: list[dict], pins: dict) -> list[dict]:
    """Attach the pinned SHA-256 to every row; the repository must list exactly the pinned archives of each package."""
    packages = pins["packages"]
    for name in dict.fromkeys(row["package"] for row in plan):
        rows = [row for row in plan if row["package"] == name]
        pinned = packages.get(name)
        if pinned is None:
            raise ValueError(f"No SHA-256 pins for {name} in {PINS_FILE.name}: run --record-pins and review the diff")
        if rows[0]["version"] != pinned["version"]:
            raise ValueError(f"Repository has {name} {rows[0]['version']}, pins are for {pinned['version']}")
        listed, expected = [row["archive"] for row in rows], list(pinned["archives"])
        if sorted(listed) != sorted(expected):
            raise ValueError(f"Repository archives of {name} differ from the pins: {listed} != {expected}")
        for row in rows:
            pin = pinned["archives"][row["archive"]]
            row.update(algorithm="sha256", checksum=pin["sha256"], expected_bytes=pin["bytes"])
    return plan


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


def sha256_of(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verified_archive(base: str, row: dict, cache: Path) -> Path:
    """Download (or reuse from the cache) one archive whose SHA-256 and size match the pin in `row`."""
    checksum = row.get("checksum")
    if row.get("algorithm") != "sha256" or not SHA256.fullmatch(str(checksum or "")):
        raise ValueError(f"No pinned SHA-256 for {row['archive']}")
    url = base + row["relative_url"]
    archive = cache / row["archive"]
    if not archive.exists() or sha256_of(archive) != checksum:
        part = archive.with_suffix(".7z.part")
        fetch(url, part)
        actual = sha256_of(part)
        if actual != checksum:
            part.unlink()
            raise ValueError(f"Checksum mismatch: {url}: {actual} != pinned {checksum}")
        part.replace(archive)
    size = archive.stat().st_size
    if size != row["expected_bytes"]:
        raise ValueError(f"Size mismatch: {archive}: {size} != pinned {row['expected_bytes']}")
    row.update(url=url, bytes=size)
    print(f"VERIFIED {row['archive']} sha256={checksum} bytes={size}", flush=True)
    return archive


def server_sha256(base: str, row: dict, cache: Path) -> str:
    """Only for --record-pins: the repository's SHA-256 file. A SHA-1-only archive is refused."""
    sidecar = cache / (row["archive"] + ".sha256")
    try:
        fetch(base + row["relative_url"] + ".sha256", sidecar)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise ValueError(f"No SHA-256 published for {row['archive']} (SHA-1 is not accepted)") from error
        raise
    checksum = sidecar.read_text(encoding="ascii").split()[0].lower()
    if not SHA256.fullmatch(checksum):
        raise ValueError(f"Invalid sha256 checksum: {sidecar}")
    return checksum


def record_pins(base: str, plan: list[dict], cache: Path, path: Path = PINS_FILE) -> dict:
    """Download every archive of `plan`, check it against the repository's SHA-256, and write the pins (installs nothing)."""
    pins = load_pins(path) if path.exists() else {"packages": {}}
    for row in plan:
        checksum = server_sha256(base, row, cache)
        archive = cache / row["archive"]
        if not archive.exists() or sha256_of(archive) != checksum:
            part = archive.with_suffix(".7z.part")
            fetch(base + row["relative_url"], part)
            actual = sha256_of(part)
            if actual != checksum:
                part.unlink()
                raise ValueError(f"Checksum mismatch: {row['archive']}: {actual} != {checksum}")
            part.replace(archive)
        package = pins["packages"].setdefault(row["package"], {"version": row["version"], "archives": {}})
        if package["version"] != row["version"]:
            package.update(version=row["version"], archives={})
        package["archives"][row["archive"]] = {"sha256": checksum, "bytes": archive.stat().st_size}
        print(f"PINNED {row['package']} {row['archive']} sha256={checksum}", flush=True)
    path.write_text(json.dumps(pins, indent=2) + "\n", encoding="utf-8", newline="\n")
    return pins


def pinned_py7zr_version(path: Path = REQUIREMENTS_FILE) -> str:
    match = re.search(r"^py7zr==(\S+)", path.read_text(encoding="utf-8"), re.M)
    if match is None:
        raise ValueError(f"py7zr is not pinned in {path}")
    return match[1]


def check_py7zr() -> None:
    try:
        installed = importlib.metadata.version("py7zr")
    except importlib.metadata.PackageNotFoundError:
        installed = None
    wanted = pinned_py7zr_version()
    if installed != wanted:
        raise ValueError(f"py7zr {installed} found, {wanted} required: pip install --require-hashes --only-binary :all: "
                         f"--target <dir> -r {REQUIREMENTS_FILE} and pass --python-libraries <dir>")


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


def relocate_pkgconfig(root: Path) -> None:
    """Point each .pc file at this SDK, using the build prefix the file itself declares.

    .prl files already refer to $$[QT_INSTALL_LIBS], so they need no rewrite.
    """
    for path in root.glob("lib/pkgconfig/*.pc"):
        text = path.read_text(encoding="utf-8")
        declared = re.search(r"^prefix=(.*)$", text, flags=re.M)
        if not declared or not declared.group(1).strip():
            continue
        fixed = text.replace(declared.group(1).strip(), root.as_posix())
        if fixed != text:
            path.write_text(fixed, encoding="utf-8", newline="\n")


def configure(root: Path) -> dict:
    (root / "bin/qt.conf").write_text("[Paths]\nPrefix=..\n", encoding="ascii", newline="\n")
    config = root / "mkspecs/qconfig.pri"
    text = config.read_text(encoding="utf-8")
    text = re.sub(r"^QT_EDITION =.*$", "QT_EDITION = OpenSource", text, flags=re.M)
    text = re.sub(r"^QT_LICHECK =.*$", "QT_LICHECK =", text, flags=re.M)
    config.write_text(text, encoding="utf-8", newline="\n")
    relocate_pkgconfig(root)
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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--destination", type=Path, required=True, help="SDK parent containing version directories")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--addon", action="append", default=[], help="Extra addon on top of REQUIRED_ADDONS")
    parser.add_argument("--only-addon", action="append", default=[],
                        help="Install only this addon into an existing SDK of the same version")
    parser.add_argument("--record-pins", action="store_true", help="Pin base + addons from the repository; install nothing")
    parser.add_argument("--python-libraries", type=Path, help="site-packages holding the pinned py7zr")
    args = parser.parse_args()
    if args.python_libraries:
        sys.path.append(str(args.python_libraries))
        importlib.invalidate_caches()
    version = qt_version()
    folder = "qt6_" + version.replace(".", "")
    base = f"https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/{folder}/{folder}_msvc2022_64/"
    root = args.destination / version / "msvc2022_64"
    if args.only_addon:
        validate_qt_root(root, require_modules=False)
        names = package_names(version, args.only_addon, base=False)
    else:
        names = package_names(version, [*REQUIRED_ADDONS, *args.addon])
    args.cache.mkdir(parents=True, exist_ok=True)
    metadata = args.cache / "Updates.xml"
    fetch(base + "Updates.xml", metadata)
    plan = archive_plan(metadata.read_bytes(), version, names)
    if args.record_pins:
        record_pins(base, plan, args.cache)
        print(f"PINS written to {PINS_FILE}: review, cross-check against a second mirror, commit; then install", flush=True)
        return
    apply_pins(plan, load_pins())
    check_py7zr()
    archives = [verified_archive(base, row, args.cache) for row in plan]
    root.mkdir(parents=True, exist_ok=True)
    for archive in archives:
        extract(archive, root, version)
    queries = configure(root)
    validate_qt_root(root)
    record = args.cache / ("installed-" + "-".join(args.only_addon) + ".json" if args.only_addon else "installed.json")
    record.write_text(json.dumps(dict(version=version, repository=base, archives=plan, queries=queries), indent=2),
                      encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
