"""Phát hành một phiên bản ABook (docs/RELEASING.md) - một script thay cho bộ script chép tay mỗi lần phát hành.

    python scripts/release.py bump 0.4.12 --commit   # nâng số ở 7 file + commit "Release 0.4.12"
    python scripts/release.py build 0.4.12           # bộ cài Windows + APK ký khoá phát hành, kiểm chữ ký và latest.json
    python scripts/release.py notes 0.4.12           # ghi chú GitHub Release từ CHANGELOG + README
    python scripts/release.py publish 0.4.12 --commit <sha>   # tag, đẩy main, GitHub Release 6 file, kiểm latest.json

Mỗi bước dừng ở chỗ đầu tiên không đúng (assert / mã thoát khác 0). File phát hành nằm NGOÀI repo (thư mục tạm của máy, hay
--out), để không bao giờ lỡ commit file nhị phân. Khoá ký APK và khoá minisign không đi qua script này: bước dựng đọc chúng ở
chỗ các script dựng vẫn đọc (%USERPROFILE%/.abook-keys).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # _internal
REPO = ROOT.parent
GITHUB_REPO = "ntanhpro1221/ABook"
GITHUB_USER = "ntanhpro1221"
# Chứng chỉ khoá phát hành APK (công khai: ai cài APK cũng đọc được) - APK ký khoá khác thì không cài đè được bản cũ.
APK_CERT_SHA256 = "e0aeae7e8407ec636b01f634af915beda289ceb25c9ab038351823aefcd3a226"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
BELOW_NORMAL = 0x00004000  # Windows: dựng ở ưu tiên thấp, không giành máy với hàng GPU


def current_version(root: Path = ROOT) -> str:
    match = re.search(r'^version = "([^"]+)"', (root / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    assert match, "pyproject.toml không có dòng version"
    return match.group(1)


def _edit(path: Path, change) -> None:
    text = path.read_bytes().decode("utf-8")  # đọc/ghi byte: giữ kiểu xuống dòng của từng file
    updated = change(text)
    assert updated != text, f"không đổi gì ở {path}"
    path.write_bytes(updated.encode("utf-8"))


def bump(new: str, root: Path = ROOT, today: datetime.date | None = None) -> list[Path]:
    """Nâng số phiên bản ở đúng 7 file của một commit phát hành; trả về các file đã đổi."""
    assert VERSION.match(new), f"số phiên bản lạ: {new}"
    old = current_version(root)
    assert old != new, f"đã là {new}"

    def json_version(text: str) -> str:
        # Chỉ "version" của CHÍNH gói (đầu package.json; gốc + packages."" trong lock), không đụng phụ thuộc trùng số.
        return re.sub(rf'("version": "){re.escape(old)}(")', rf"\g<1>{new}\g<2>", text, count=2)

    def gradle(text: str) -> str:
        code = int(re.search(r"versionCode (\d+)", text).group(1))
        text = text.replace(f"versionCode {code}", f"versionCode {code + 1}", 1)
        return text.replace(f'versionName "{old}"', f'versionName "{new}"', 1)

    day = (today or datetime.date.today()).isoformat()
    edits = {
        "pyproject.toml": lambda t: t.replace(f'version = "{old}"', f'version = "{new}"', 1),
        "ui/package.json": json_version,
        "ui/package-lock.json": json_version,
        "mobile/package.json": json_version,
        "mobile/package-lock.json": json_version,
        "mobile/android/app/build.gradle": gradle,
        "docs/CHANGELOG.md": lambda t: t.replace("## [Chưa phát hành]\n", f"## [Chưa phát hành]\n\n## [{new}] - {day}\n", 1),
    }
    changed = []
    for relative, change in edits.items():
        _edit(root / relative, change)
        changed.append(root / relative)
    return changed


def release_notes(version: str, repo: Path = REPO) -> str:
    """Ghi chú GitHub Release: mục CHANGELOG của bản ấy + yêu cầu máy (README) + cách cài."""
    changelog = (repo / "_internal/docs/CHANGELOG.md").read_text(encoding="utf-8")
    readme = (repo / "README.md").read_text(encoding="utf-8")
    section = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[)", changelog, re.S | re.M)
    requirements = re.search(r"^## Yêu cầu máy\n(.*?)(?=^## )", readme, re.S | re.M)
    assert section and section.group(1).strip(), f"CHANGELOG không có mục [{version}] (chạy bump trước?)"
    assert requirements, "README không có mục Yêu cầu máy"
    return f"""ABook {version} - app nghe và làm sách nói tiếng Việt: máy tính Windows làm sách (Studio), điện thoại Android và trình
duyệt nghe cùng một thư viện.

## Cài đặt

- **Windows**: tải `ABook_{version}_x64-setup.exe` bên dưới và chạy (khoảng 30 MB, không cần quyền quản trị). Bản đã cài tự
  báo có bản mới trong Cài đặt.
- **Android**: tải file `.apk` bên dưới và cài; ghép với máy tính bằng mã 6 số (Cài đặt → "Ghép thiết bị mới" trên máy tính).
  App điện thoại từ 0.4.11 tự báo khi có bản mới.
- Hướng dẫn đầy đủ (Studio, Bluetooth, trình duyệt, máy tính khác): [README](https://github.com/{GITHUB_REPO}#readme).

## Yêu cầu máy

{requirements.group(1).rstrip()}

## Thay đổi

{section.group(1).rstrip()}
"""


def artifacts(version: str) -> list[str]:
    return [f"ABook_{version}.apk", f"ABook_{version}_x64-setup.exe", f"ABook_{version}_x64-setup.exe.sig", "latest.json",
            "LICENSE", "THIRD_PARTY.md"]


def _run(command: list[str], cwd: Path, env: dict[str, str] | None = None, low: bool = False) -> None:
    print("$", " ".join(command), f"  (ở {cwd})", flush=True)
    flags = BELOW_NORMAL if low and os.name == "nt" else 0
    subprocess.run(command, cwd=cwd, env=env, check=True, creationflags=flags)


def _tool(name: str) -> str:
    found = shutil.which(name)
    assert found, f"không tìm thấy {name} trong PATH"
    return found


def _apk_certificate(apk: Path) -> str:
    sdk = Path(os.environ.get("LOCALAPPDATA", "")) / "Android/Sdk/build-tools"
    tools = sorted(sdk.glob("*/apksigner.bat"), key=lambda path: [int(part) for part in re.findall(r"\d+", path.parent.name)])
    assert tools, f"không có apksigner trong {sdk}"
    output = subprocess.run([str(tools[-1]), "verify", "--print-certs", str(apk)], capture_output=True, text=True, check=True).stdout
    match = re.search(r"SHA-256 digest: ([0-9a-f]{64})", output)
    assert match, "apksigner không in chứng chỉ"
    return match.group(1)


def build(version: str, out: Path) -> None:
    """Bộ cài Windows (NSIS + chữ ký cập nhật + latest.json) và APK ký khoá phát hành, chép vào `out`, kiểm cả hai."""
    assert current_version() == version, f"repo đang là {current_version()}, chưa bump {version}?"
    out.mkdir(parents=True, exist_ok=True)
    _run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/build_windows_app.ps1")], ROOT, low=True)
    nsis = ROOT / "shell/src-tauri/target/release/bundle/nsis"
    for name in (f"ABook_{version}_x64-setup.exe", f"ABook_{version}_x64-setup.exe.sig", "latest.json"):
        assert (nsis / name).is_file(), f"bộ cài thiếu {name}"
        shutil.copy2(nsis / name, out / name)
    manifest = json.loads((out / "latest.json").read_text(encoding="utf-8"))
    assert manifest.get("version") == version, f"latest.json ghi {manifest.get('version')}"

    env = dict(os.environ, JAVA_HOME=os.environ.get("JAVA_HOME") or "C:/Program Files/Android/Android Studio/jbr")
    _run([_tool("npm"), "run", "-s", "build:android"], ROOT / "ui", env, low=True)
    _run([_tool("npx"), "cap", "sync", "android"], ROOT / "mobile", env, low=True)
    _run([str(ROOT / "mobile/android/gradlew.bat"), "--no-daemon", "-q", ":app:assembleRelease"], ROOT / "mobile/android", env,
         low=True)
    apk = ROOT / "mobile/android/app/build/outputs/apk/release/app-release.apk"
    assert apk.is_file(), "gradle không ra APK"
    shutil.copy2(apk, out / f"ABook_{version}.apk")
    certificate = _apk_certificate(out / f"ABook_{version}.apk")
    assert certificate == APK_CERT_SHA256, f"APK ký bằng chứng chỉ lạ {certificate} - điện thoại sẽ không cài đè được"

    shutil.copy2(ROOT / "LICENSE", out / "LICENSE")
    shutil.copy2(ROOT / "docs/THIRD_PARTY.md", out / "THIRD_PARTY.md")
    print(f"đủ {len(artifacts(version))} file ở {out}")


def publish(version: str, commit: str, out: Path) -> None:
    """Tag v<version> ở commit phát hành, tua nhanh main tới đó, GitHub Release 6 file (--latest), rồi kiểm latest.json."""
    missing = [name for name in artifacts(version) if not (out / name).is_file()]
    assert not missing, f"thiếu {missing} ở {out} (chạy build trước)"
    notes = out / "notes.md"
    notes.write_bytes(release_notes(version).encode("utf-8"))
    _run(["git", "fetch", "-q", "origin"], REPO)
    # main chỉ tua nhanh: commit phát hành phải nằm trên origin/main hiện tại.
    _run(["git", "merge-base", "--is-ancestor", "origin/main", commit], REPO)
    _run(["git", "tag", "-a", f"v{version}", commit, "-m", f"ABook {version}"], REPO)
    _run(["git", "push", "-q", "origin", f"{commit}:main"], REPO)
    _run(["git", "push", "-q", "origin", f"v{version}"], REPO)
    token = subprocess.run(["gh", "auth", "token", "--user", GITHUB_USER], capture_output=True, text=True, check=True).stdout.strip()
    env = dict(os.environ, GH_TOKEN=token)  # đúng tài khoản cho từng lệnh, không đổi tài khoản đang dùng của gh
    _run(["gh", "release", "create", f"v{version}", "--repo", GITHUB_REPO, "--title", f"ABook {version}", "--notes-file",
          str(notes), "--latest", *artifacts(version)], out, env)
    for _ in range(6):
        time.sleep(5)
        url = f"https://github.com/{GITHUB_REPO}/releases/latest/download/latest.json"
        try:
            with urllib.request.urlopen(url, timeout=20) as reply:
                served = json.loads(reply.read().decode("utf-8")).get("version")
        except OSError:
            continue
        if served == version:
            print(f"đã phát hành: https://github.com/{GITHUB_REPO}/releases/tag/v{version}")
            return
    raise SystemExit(f"releases/latest chưa trả {version} - kiểm lại trang Release")


def _commit_bump(version: str, files: list[Path]) -> None:
    _run(["git", "add", "--", *[str(path.relative_to(REPO)) for path in files]], REPO)
    message = f"Release {version}\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
    _run(["git", "commit", "-q", "-m", message], REPO)
    print(subprocess.run(["git", "log", "--oneline", "-1"], cwd=REPO, capture_output=True, text=True).stdout.strip())


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # console Windows (cp1252) không in được tiếng Việt
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["bump", "build", "notes", "publish"])
    parser.add_argument("version")
    parser.add_argument("--commit", nargs="?", const="HEAD", help="bump: commit luôn; publish: commit phát hành (mặc định HEAD)")
    parser.add_argument("--out", type=Path, help="thư mục file phát hành (mặc định: thư mục tạm/abook-release/<bản>)")
    args = parser.parse_args(argv)
    assert VERSION.match(args.version), f"số phiên bản lạ: {args.version}"
    out = args.out or Path(tempfile.gettempdir()) / "abook-release" / args.version
    sys.path.insert(0, str(ROOT))
    if args.step == "bump":
        from ebook_reader.quality_policy import quality_implementation_hash

        before = quality_implementation_hash()
        files = bump(args.version)
        # Nâng số không được đổi hash chất lượng (pyproject băm với version thay bằng '*', 0.4.6) - đổi là lỗi.
        assert quality_implementation_hash() == before, "nâng số phiên bản làm đổi hash chất lượng"
        print(f"{current_version()} ở {len(files)} file, hash {before[:8]} không đổi")
        if args.commit:
            _commit_bump(args.version, files)
    elif args.step == "build":
        build(args.version, out)
    elif args.step == "notes":
        out.mkdir(parents=True, exist_ok=True)
        (out / "notes.md").write_bytes(release_notes(args.version).encode("utf-8"))
        print(f"ghi chú -> {out / 'notes.md'}")
    else:
        commit = subprocess.run(["git", "rev-parse", args.commit or "HEAD"], cwd=REPO, capture_output=True, text=True,
                                check=True).stdout.strip()
        publish(args.version, commit, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
