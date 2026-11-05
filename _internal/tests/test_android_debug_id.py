"""A debug-signed Android build must never be able to take the real app's place - 2026-11-05.

The owner's phone ended up with com.ngdtuanh.abook signed by the Android DEBUG key; GitHub releases carry the release key, so Android refused
every in-app update. Two guards: the debug buildType installs under its own id (applicationIdSuffix), and no script installs the debug APK
while naming the bare real id (it would `adb install -r` over, or `uninstall`, the real app).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GRADLE = ROOT / "mobile/android/app/build.gradle"
REAL_ID = re.compile(r"com\.ngdtuanh\.abook(?![\w.])")
INSTALLS_DEBUG_APK = re.compile(r"\binstall\S*\s.*app-debug(?:-androidTest)?\.apk")
SKIP_DIRS = {"node_modules", "build", ".git", "runtime", ".gradle", "__pycache__", ".venv"}
SCRIPT_SUFFIXES = {".sh", ".py", ".ps1", ".bat", ".cmd"}


def _block(text: str, name: str, start: int = 0) -> str | None:
    """Body of the first `name { ... }` at or after `start` (brace matched); None when absent."""
    found = re.compile(r"\b" + re.escape(name) + r"\s*\{").search(text, start)
    if not found:
        return None
    depth, index = 1, found.end()
    while index < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        index += 1
    return text[found.end():index - 1]


def debug_build_type(gradle: str) -> str | None:
    build_types = _block(gradle, "buildTypes")
    return None if build_types is None else _block(build_types, "debug")


def has_applicationid_suffix(gradle: str) -> bool:
    debug = debug_build_type(gradle)
    if debug is None:
        return False
    debug = re.sub(r"//[^\n]*", "", debug)
    return re.search(r"\bapplicationIdSuffix\s*=?\s*[\"']", debug) is not None


def code_lines(text: str) -> list[str]:
    """Lines with whole-line and trailing `#` comments removed (a `#` inside quotes is not a comment in these scripts)."""
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        out.append(re.sub(r"\s+#\s.*$", "", line))
    return out


def installs_debug_under_real_id(script: str) -> bool:
    """Installs app-debug.apk and also uses the bare real id on a line that is not a refusing guard (`... exit`)."""
    lines = code_lines(script)
    if not any(INSTALLS_DEBUG_APK.search(line) for line in lines):
        return False
    return any(REAL_ID.search(line) and "exit" not in line for line in lines)


def repo_scripts() -> list[Path]:
    found = []
    for path in ROOT.rglob("*"):
        if path.suffix in SCRIPT_SUFFIXES and path.is_file() and not SKIP_DIRS.intersection(path.relative_to(ROOT).parts):
            found.append(path)
    return sorted(found)


def test_debug_build_type_has_its_own_application_id_suffix():
    assert has_applicationid_suffix(GRADLE.read_text(encoding="utf-8")), \
        "app/build.gradle: buildTypes.debug needs applicationIdSuffix so a debug APK cannot replace the release-signed app"


def test_the_detector_sees_a_missing_suffix():
    bare = "android { buildTypes { debug { versionNameSuffix '-dev' } release { minifyEnabled true } } }"
    suffixed = "android { buildTypes { release { minifyEnabled true } debug { if (x) { applicationIdSuffix '.dev' } } } }"
    other = "android { buildTypes { release { applicationIdSuffix '.x' } debug { } } }"
    assert not has_applicationid_suffix(bare)
    assert not has_applicationid_suffix(other)
    assert not has_applicationid_suffix("android { }")
    assert has_applicationid_suffix(suffixed)


def test_debug_apk_is_never_installed_under_the_real_id():
    bad = [str(path.relative_to(ROOT)) for path in repo_scripts() if path != Path(__file__).resolve()
           and installs_debug_under_real_id(path.read_text(encoding="utf-8", errors="replace"))]
    assert bad == [], f"these scripts install app-debug.apk while naming com.ngdtuanh.abook (use the .dev id): {bad}"


@pytest.mark.parametrize("script, expected", [
    ('PKG=com.ngdtuanh.abook\nadb install -r -t "$D/app-debug.apk"\n', True),
    ('PKG=com.ngdtuanh.abook.dev\nadb install -r -t "$D/app-debug.apk"\n', False),
    ('# never com.ngdtuanh.abook\nadb install -r app-debug.apk # com.ngdtuanh.abook\n', False),
    ('[ "$ID" = com.ngdtuanh.abook ] && { echo no; exit 2; }\nadb install -r app-debug.apk\n', False),
    ('adb shell pm clear com.ngdtuanh.abook\n', False),
])
def test_script_rule(script, expected):
    assert installs_debug_under_real_id(script) is expected
