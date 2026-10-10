r"""Đưa một GGUF vào Ollama với ĐÚNG khuôn chat + tham số của một model có sẵn (vd LoRA 8B -> giống `qwen3:8b`).

    python scripts/model_eval/ollama_like.py --gguf D:/.../model.Q4_K_M.gguf --name qwen3-8b-lora28 --like qwen3:8b

Vì sao không để Ollama tự đoán khuôn từ GGUF (như serve_lora.py với nền 4B không nghĩ): Qwen3-8B có chế độ nghĩ, và
dây chuyền gửi think=false; khuôn phải là khuôn của `qwen3:8b` thì khối think rỗng mới y hệt lúc huấn luyện
(train_lora_unsloth.py dựng chữ với enable_thinking=False). Tên bắt đầu bằng "qwen3" để eval_models gửi think=false.
Máy chủ Ollama phải đang chạy. Tạo model qua HTTP (/api/blobs + /api/create), KHÔNG qua CLI `ollama`: CLI gọi lúc máy chủ
tắt sẽ tự mở app khay, mà app khay mang bộ tự cập nhật (0.40.x đổi runner -> đổi digest -> hỏng seed theo digest).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

OLLAMA = "http://127.0.0.1:11434"


def _call(method: str, path: str, body: Any = None, data: bytes | None = None, timeout: float = 3600) -> Any:
    payload = data if data is not None else (json.dumps(body).encode() if body is not None else None)
    request = urllib.request.Request(f"{OLLAMA}{path}", data=payload, method=method,
                                     headers={"Content-Type": "application/json"} if data is None else {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        if method == "HEAD":
            raise
        raise RuntimeError(f"{method} {path} -> {error.code}: {error.read().decode('utf-8', 'replace')[:500]}") from error
    return json.loads(text) if text.strip() else None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 24), b""):
            digest.update(block)
    return digest.hexdigest()


def push_blob(path: Path) -> str:
    """Đẩy file lên kho blob của máy chủ (bỏ qua nếu đã có); trả "sha256:<hex>"."""
    digest = f"sha256:{_file_sha256(path)}"
    try:
        _call("HEAD", f"/api/blobs/{digest}", timeout=60)
        return digest
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    size = path.stat().st_size
    with path.open("rb") as handle:
        request = urllib.request.Request(f"{OLLAMA}/api/blobs/{digest}", data=handle, method="POST",
                                         headers={"Content-Length": str(size)})
        with urllib.request.urlopen(request, timeout=3600) as response:
            response.read()
    return digest


def _parameters(text: str) -> dict[str, Any]:
    """`parameters` dạng chữ của /api/show -> đối tượng của /api/create (stop luôn là danh sách)."""
    out: dict[str, Any] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        key, _, raw = line.strip().partition(" ")
        raw = raw.strip()
        value: Any = raw[1:-1] if len(raw) >= 2 and raw[0] == raw[-1] == '"' else raw
        if value is raw:
            for cast in (int, float):
                try:
                    value = cast(raw)
                    break
                except ValueError:
                    pass
        if key == "stop":
            out.setdefault("stop", []).append(value)
        else:
            out[key] = value
    return out


def create_model(name: str, gguf: Path, like: str = "", quantize: str = "") -> None:
    """= `ollama create <name>` với Modelfile `FROM <gguf>` (+ khuôn/tham số/system của `like`), qua HTTP."""
    # Ollama từ chối (400) tên file không đuôi .gguf trong `files`.
    key = gguf.name if gguf.suffix.lower() == ".gguf" else f"{gguf.name}.gguf"
    body: dict[str, Any] = {"model": name, "files": {key: push_blob(gguf)}, "stream": False}
    if like:
        shown = _call("POST", "/api/show", {"model": like}, timeout=60)
        if shown.get("template"):
            body["template"] = shown["template"]
        if shown.get("system"):
            body["system"] = shown["system"]
        if shown.get("parameters"):
            body["parameters"] = _parameters(shown["parameters"])
    if quantize:
        body["quantize"] = quantize
    result = _call("POST", "/api/create", body)
    if not result or result.get("status") != "success":
        raise RuntimeError(f"/api/create {name}: {result}")


def modelfile_like(like: str, gguf: Path) -> str:
    """Modelfile của model `like` (khuôn chat, tham số, stop) với FROM trỏ sang `gguf`."""
    request = urllib.request.Request(f"{OLLAMA}/api/show", data=json.dumps({"model": like}).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        modelfile = json.loads(response.read().decode("utf-8"))["modelfile"]
    lines = [line for line in modelfile.splitlines() if not line.startswith("#")]
    return "\n".join(f"FROM {gguf.as_posix()}" if re.match(r"FROM\s", line) else line for line in lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gguf", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--like", default="qwen3:8b")
    parser.add_argument("--quantize", default="", help="nén lúc tạo, vd q4_K_M (GGUF vào phải là f16/bf16)")
    args = parser.parse_args(argv)
    # Modelfile vẫn ghi cạnh GGUF để người đọc biết model dựng thế nào (không dùng để tạo).
    args.gguf.with_suffix(".Modelfile").write_text(modelfile_like(args.like, args.gguf), encoding="utf-8")
    try:
        create_model(args.name, args.gguf, like=args.like, quantize=args.quantize)
    except (OSError, RuntimeError, urllib.error.URLError) as error:
        sys.stdout.write(f"tạo model thất bại: {error}\n")
        return 1
    sys.stdout.write(f"xong: {args.name}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
