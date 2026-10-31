"""Kiểm chữ ký cập nhật (.sig minisign của `tauri signer sign`) của một file, bằng khoá công khai trong tauri.conf.json.
Định dạng và phép kiểm: abook/webui/minisign_verify.py (bộ cập nhật của app dùng chung).

minisign_verify.py <file> [--sig <file>.sig] [--pubkey <base64>] [--version <ver>]  -> SIG_OK / SIG_FAIL, mã 0 / 1
"""
import argparse
import json
import sys
from pathlib import Path

INTERNAL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(INTERNAL))
from abook.webui.minisign_verify import file_ok  # noqa: E402

TAURI_CONF = INTERNAL / "shell" / "src-tauri" / "tauri.conf.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--sig", type=Path)
    ap.add_argument("--pubkey")
    ap.add_argument("--version", help="đòi trusted comment ghi version:<bản này>")
    args = ap.parse_args()
    key = args.pubkey or json.loads(TAURI_CONF.read_text(encoding="utf-8"))["plugins"]["updater"]["pubkey"]
    sig = (args.sig or args.file.with_name(args.file.name + ".sig")).read_text(encoding="utf-8")
    ok = file_ok(args.file, sig, key, args.version)
    print(("SIG_OK " if ok else "SIG_FAIL ") + str(args.file))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
