"""Ký `remote-config/remote-config.json` (webui/remote_config.py) bằng khoá Ed25519 của ABook (repo riêng tư ABook-Private,
keys/remote_config_ed25519.pem): đặt `issued` = bây giờ (UTC), ghi lại file chuẩn hoá, rồi ghi chữ ký base64 vào `.sig`.
App chỉ nhận cấu hình có chữ ký đúng và `issued` mới hơn bản nó đang giữ - nên mỗi lần sửa đều phải ký lại.

    python scripts/sign_remote_config.py [--key D:/Novels/ABook/Corpus/keys/remote_config_ed25519.pem]
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "remote-config" / "remote-config.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", type=Path, default=Path("D:/Novels/ABook/Corpus/keys/remote_config_ed25519.pem"))
    args = parser.parse_args()
    from cryptography.hazmat.primitives import serialization

    sys.path.insert(0, str(ROOT / "_internal"))
    from ebook_reader.webui.ed25519_verify import verify
    from ebook_reader.webui.remote_config import PUBLIC_KEY

    key = serialization.load_pem_private_key(args.key.read_bytes(), password=None)
    value = json.loads(CONFIG.read_text(encoding="utf-8"))
    value["issued"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = (json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    signature = key.sign(raw)
    if not verify(PUBLIC_KEY, raw, signature):
        print("Khoá này không khớp khoá công khai trong app - không ký.", file=sys.stderr)
        return 1
    CONFIG.write_bytes(raw)
    CONFIG.with_name(CONFIG.name + ".sig").write_bytes(base64.b64encode(signature) + b"\n")
    print(f"đã ký {CONFIG} (issued {value['issued']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
