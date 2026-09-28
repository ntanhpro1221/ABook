"""Gộp adapter LoRA vào model nền, chuyển GGUF, rồi nạp vào Ollama - để chấm bằng ĐÚNG bộ phân tích sản xuất.

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/serve_lora.py \
        --adapter D:/Novels/LLM_Train/runs/Qwen3-4B-Instruct-2507-both-r16 --name qwen3-4b-phanvai

Vì sao phải qua GGUF (đo ngày 20-09, không phải phỏng đoán): **Ollama 0.33.2 KHÔNG nhập được safetensors Qwen3** -
`ollama create` từ thư mục safetensors trả `Error: unsupported architecture "Qwen3ForCausalLM"`. Đường đi được là
GGUF, và đã thử trọn mắt xích bằng `Qwen/Qwen3-0.6B`:

    safetensors -> convert_hf_to_gguf.py -> 1,5 GB f16 -> ollama create -> POST /api/generate có `format` (lược đồ
    JSON) -> trả JSON hợp lệ, `done=True`, `eval_count=61`, 6,4s khi nạp nguội.

Đó đúng là hợp đồng mà `OllamaBookAnalyzer` dùng (`/api/tags` + `/api/generate` dạng NDJSON, đọc `response`, `done`,
`done_reason`, `eval_count`), nên model tự huấn luyện được chấm trong CÙNG điều kiện với `qwen3:8b`: cùng prompt,
cùng lược đồ bắt buộc, cùng `num_ctx`. Không có bước này thì "model chuyên đúng hơn" chỉ là một con số không so
được với mốc.

Công cụ chuyển nằm ở `D:/Novels/LLM_Train/llama.cpp` (sparse clone: chỉ `conversion/` + `gguf-py`, 3,5 MB - bản
`convert_hf_to_gguf.py` mới KHÔNG còn tự chứa, nó import package `conversion`, nên tải một file là không đủ).

Gộp chạy trên CPU và cần ~8 GB RAM cho model 4B ở bf16 (máy có 31 GB, lượt sản xuất dùng ~8 GB) - không cần GPU,
nên chạy được giữa lúc lô đang thu. Chỉ `--outtype q8_0` mới hợp với 8 GB VRAM nếu sau này muốn model 8B.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

LLAMA_CPP = Path(r"D:/Novels/LLM_Train/llama.cpp")
GGUF_DIR = Path(r"D:/Novels/LLM_Train/runs")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--adapter", type=Path, default=None, help="thư mục adapter do train_lora.py lưu")
    parser.add_argument("--base-only", action="store_true",
                        help="chuyển model nền KHÔNG adapter - đối chứng cùng đường GGUF/lượng tử hoá với bản LoRA, để "
                             "chênh lệch đo được là của LoRA chứ không phải của q8_0 hay mẫu chat")
    parser.add_argument("--base", default=None, help="mặc định đọc từ adapter_config.json")
    parser.add_argument("--name", required=True, help="tên model trong Ollama")
    parser.add_argument("--outtype", default="q8_0", choices=("f16", "bf16", "q8_0"))
    parser.add_argument("--keep-merged", action="store_true", help="giữ thư mục safetensors đã gộp (nặng)")
    parser.add_argument("--like", default="",
                        help="chép Modelfile (khuôn chat, tham số) của model Ollama này, vd qwen3:8b - nền có chế độ "
                             "nghĩ cần đúng khuôn của qwen3:8b để khối think rỗng y như lúc huấn luyện")
    parser.add_argument("--quantize", default="",
                        help="nén lúc `ollama create`, vd q4_K_M (dùng với --outtype f16): 8B ở q8_0 nặng 8,7 GB, "
                             "không vừa card 8 GB")
    args = parser.parse_args(argv)
    if not args.base_only and args.adapter is None:
        parser.error("cần --adapter (hoặc --base-only với --base)")
    if args.base_only and not args.base:
        parser.error("--base-only cần --base")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from peft import PeftConfig

    base = args.base or PeftConfig.from_pretrained(str(args.adapter)).base_model_name_or_path
    merged = GGUF_DIR / f"{args.name}-merged"
    gguf = GGUF_DIR / f"{args.name}.gguf"
    if args.base_only:
        from huggingface_hub import snapshot_download  # noqa: PLC0415

        # Chuyển thẳng bản tải sẵn trong bộ nhớ đệm HF: không gộp gì, không ghi lại 8 GB.
        merged = Path(snapshot_download(base, local_files_only=True,
                                        allow_patterns=["*.json", "*.safetensors", "*.txt", "*.jinja"]))
        print(f"  nền {base} (KHÔNG adapter) -> {gguf.name} ({args.outtype})")
    else:
        print(f"  nền {base} + adapter {args.adapter.name} -> {gguf.name} ({args.outtype})")
        print("  gộp trên CPU (bf16)...")
        model = AutoModelForCausalLM.from_pretrained(base, dtype=torch.bfloat16, device_map="cpu")
        model = PeftModel.from_pretrained(model, str(args.adapter))
        model = model.merge_and_unload()
        model.save_pretrained(str(merged), safe_serialization=True)
        AutoTokenizer.from_pretrained(str(args.adapter) if (args.adapter / "tokenizer.json").is_file() else base
                                      ).save_pretrained(str(merged))
        del model

    print("  chuyển GGUF...")
    convert = subprocess.run(
        [sys.executable, str(LLAMA_CPP / "convert_hf_to_gguf.py"), str(merged),
         "--outfile", str(gguf), "--outtype", args.outtype],
        cwd=str(LLAMA_CPP), text=True, capture_output=True, encoding="utf-8", errors="replace",
    )
    if convert.returncode != 0:
        print(convert.stdout[-2000:], convert.stderr[-2000:])
        raise SystemExit("chuyển GGUF thất bại")

    modelfile = GGUF_DIR / f"{args.name}.Modelfile"
    if args.like:
        from ollama_like import modelfile_like  # cùng thư mục scripts/model_eval (sys.path[0])

        modelfile.write_text(modelfile_like(args.like, gguf), encoding="utf-8")
    else:
        modelfile.write_text(f"FROM {gguf}\n", encoding="utf-8")
    command = ["ollama", "create", args.name, "-f", str(modelfile)]
    if args.quantize:
        command += ["--quantize", args.quantize]
    create = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if create.returncode != 0:
        print(create.stdout[-2000:], create.stderr[-2000:])
        raise SystemExit("ollama create thất bại")
    if not args.keep_merged and not args.base_only:
        shutil.rmtree(merged, ignore_errors=True)
    print(f"  xong: ollama model `{args.name}`")
    print(f"  chấm: runtime/.venv/Scripts/python.exe scripts/model_eval/eval_models.py --models {args.name} ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
