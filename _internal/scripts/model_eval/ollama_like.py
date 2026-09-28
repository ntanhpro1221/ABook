r"""Đưa một GGUF vào Ollama với ĐÚNG khuôn chat + tham số của một model có sẵn (vd LoRA 8B -> giống `qwen3:8b`).

    python scripts/model_eval/ollama_like.py --gguf D:/.../model.Q4_K_M.gguf --name qwen3-8b-lora28 --like qwen3:8b

Vì sao không để Ollama tự đoán khuôn từ GGUF (như serve_lora.py với nền 4B không nghĩ): Qwen3-8B có chế độ nghĩ, và
dây chuyền gửi think=false; khuôn phải là khuôn của `qwen3:8b` thì khối think rỗng mới y hệt lúc huấn luyện
(train_lora_unsloth.py dựng chữ với enable_thinking=False). Tên bắt đầu bằng "qwen3" để eval_models gửi think=false.
Máy chủ Ollama phải đang chạy (gọi CLI khi máy chủ tắt thì nó tự mở app khay - docs/AGENTS).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

OLLAMA = "http://127.0.0.1:11434"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gguf", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--like", default="qwen3:8b")
    args = parser.parse_args(argv)
    request = urllib.request.Request(f"{OLLAMA}/api/show", data=json.dumps({"model": args.like}).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        modelfile = json.loads(response.read().decode("utf-8"))["modelfile"]
    lines = [line for line in modelfile.splitlines() if not line.startswith("#")]
    lines = [f"FROM {args.gguf.as_posix()}" if re.match(r"FROM\s", line) else line for line in lines]
    target = args.gguf.with_suffix(".Modelfile")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    create = subprocess.run(["ollama", "create", args.name, "-f", str(target)], text=True, capture_output=True,
                            encoding="utf-8", errors="replace")
    sys.stdout.write(create.stdout[-1500:] + create.stderr[-1500:])
    return create.returncode


if __name__ == "__main__":
    raise SystemExit(main())
