"""Danh sách file của bộ cài Qt, sinh từ dist/ để bước cài và bước gỡ đọc cùng một danh sách.

$INSTDIR của ABook là %LOCALAPPDATA%\\ABook, cũng là cha của dữ liệu người dùng (Studio, preferences.json, chỗ đang nghe), nên
bộ gỡ không bao giờ `RMDir /r "$INSTDIR"`: nó xoá đúng từng file đã cài, rồi gỡ thư mục rỗng từ sâu lên nông.
`resources\\` toàn của app (Python nhúng + mã app) nên được xoá cả cây, sau khi kiểm nó không phải junction.

files.py <dist> <out_dir> -> out_dir/install_files.nsh, uninstall_files.nsh, estimated_size.nsh
"""
import sys
from pathlib import Path

# Exe của bản dựng là ABookDesk.exe; bản cài mang tên của bản Tauri để lối tắt, liên kết file và khoá gỡ cài cũ vẫn trỏ đúng.
RENAME = {"ABookDesk.exe": "ABook.exe"}
OWNED_TREE = "resources"


def collect(dist: Path) -> tuple[list[Path], list[Path]]:
    """(file ngoài resources\\, thư mục ngoài resources\\), đường tương đối, theo thứ tự ổn định."""
    files, dirs = [], []
    for path in sorted(dist.rglob("*")):
        rel = path.relative_to(dist)
        if rel.parts[0] == OWNED_TREE:
            continue
        if path.is_symlink():
            raise SystemExit(f"FILES_FAIL liên kết trong dist: {rel}")
        (dirs if path.is_dir() else files).append(rel)
    if Path("ABookDesk.exe") not in files:
        raise SystemExit(f"FILES_FAIL thiếu ABookDesk.exe trong {dist}")
    return files, dirs


def win(rel: Path) -> str:
    return str(rel).replace("/", "\\")


def installed(rel: Path) -> Path:
    return rel.with_name(RENAME.get(rel.name, rel.name)) if rel.parent == Path(".") else rel


def main() -> int:
    dist, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    if not (dist / OWNED_TREE / "python" / "pythonw.exe").is_file():
        raise SystemExit(f"FILES_FAIL {dist} chưa có resources (build.bat package)")
    files, dirs = collect(dist)
    out.mkdir(parents=True, exist_ok=True)
    install = ["; Sinh bởi desktop_qt/installer/files.py - đừng sửa tay."]
    current = None
    for rel in files:
        if rel.parent != current:
            current = rel.parent
            install.append(f'SetOutPath "$INSTDIR{"" if current == Path(".") else chr(92) + win(current)}"')
        target = installed(rel)
        rename = f'"/oname={target.name}" ' if target != rel else ""
        install.append(f'File {rename}"${{ABOOK_DIST}}\\{win(rel)}"')
    install += ['SetOutPath "$INSTDIR\\resources"', f'File /r "${{ABOOK_DIST}}\\{OWNED_TREE}\\*.*"', 'SetOutPath "$INSTDIR"']
    uninstall = ["; Sinh bởi desktop_qt/installer/files.py - đừng sửa tay."]
    uninstall += [f'Delete "$INSTDIR\\{win(installed(rel))}"' for rel in files]
    # Sâu trước: RMDir không /r chỉ gỡ thư mục đã rỗng, nên file lạ của người dùng (nếu có) làm thư mục ấy ở lại.
    uninstall += [f'RMDir "$INSTDIR\\{win(rel)}"' for rel in sorted(dirs, key=lambda d: (-len(d.parts), str(d)))]
    size_kb = sum(p.stat().st_size for p in dist.rglob("*") if p.is_file()) // 1024
    for name, lines in (("install_files.nsh", install), ("uninstall_files.nsh", uninstall),
                        ("estimated_size.nsh", [f"!define ABOOK_ESTIMATED_KB {size_kb}"])):
        (out / name).write_text("\n".join(lines) + "\n", encoding="utf-8-sig", newline="\n")
    print(f"FILES_OK {len(files)} file + {len(dirs)} thư mục ngoài resources, {size_kb // 1024} MB -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
