"""Đo bộ nhớ GPU của MỘT mẫu huấn luyện (lan xuôi + lan ngược), từng biến thể, KHÔNG để tràn sang RAM.

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/profile_train_memory.py [--cap 0.95] [--pick max]

Vì sao (27-09): `train_lora.py` giữ model 4-bit ở 2,56 GiB nhưng đỉnh mỗi mẫu lên 9,65-10,57 GiB trên card 8 GB,
PyTorch giữ tới 17,66 GiB - driver Windows lặng lẽ cho mượn ~11,6 GB RAM (sysmem fallback), nên một mẫu mất 1-4
phút thay vì vài giây. 7 GB tăng thêm ấy nằm ở đâu thì đo, đừng đoán (giả thuyết "logits" đã sai một lần).

Mỗi biến thể chạy trên CÙNG một mẫu, sau `reset_peak_memory_stats`, và `set_per_process_memory_fraction(--cap)` chặn
PyTorch ở dưới VRAM thật: vượt thì là OOM (ghi lại, chạy biến thể kế) chứ không tràn - vừa an toàn cho máy, vừa
cho con số sạch. KHÔNG có optimizer: bước tối ưu không nằm trong đỉnh này (trạng thái LoRA chỉ vài chục MB).
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from train_lora import DEFAULT_BASE, DEFAULT_DATA  # noqa: E402

GIB = 2**30
TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
# (tên, gradient checkpointing, logits, lora_dropout, attention)
# attention "default" = để PyTorch tự chọn; "cudnn" = chỉ cho kernel cuDNN (tắt math) - xem pin_attention_kernel().
VARIANTS = [
    ("như train_lora (gc, logits đáp án, dropout 0,05)", True, "answer", 0.05, "default"),
    ("TẮT gradient checkpointing", False, "answer", 0.05, "default"),
    ("logits CẢ chuỗi", True, "all", 0.05, "default"),
    ("dropout 0", True, "answer", 0.0, "default"),
    ("attention cuDNN (gc, logits đáp án)", True, "answer", 0.05, "cudnn"),
    ("attention cuDNN + logits CẢ chuỗi", True, "all", 0.05, "cudnn"),
    ("attention cuDNN, TẮT gc", False, "answer", 0.05, "cudnn"),
]


def set_attention(torch, kernel: str) -> None:
    cudnn_only = kernel == "cudnn"
    torch.backends.cuda.enable_cudnn_sdp(True)
    torch.backends.cuda.enable_math_sdp(not cudnn_only)
    torch.backends.cuda.enable_mem_efficient_sdp(not cudnn_only)
    torch.backends.cuda.enable_flash_sdp(not cudnn_only)


def _ids(encoded) -> list[int]:
    """transformers 5 trả BatchEncoding (giống dict nhưng KHÔNG phải dict) từ apply_chat_template(tokenize=True)."""
    ids = encoded["input_ids"] if hasattr(encoded, "keys") else encoded
    ids = list(ids)
    return list(ids[0]) if ids and isinstance(ids[0], list) else ids


def pick_sample(rows: list[dict], tokenizer, how: str) -> tuple[list[int], list[int]]:
    """input_ids và nhãn (-100 cho đề bài) của mẫu dài nhất hay trung vị - đáp án là lượt cuối của mẫu."""
    measured = []
    for row in rows:
        messages = row["messages"]
        prompt = tokenizer.apply_chat_template(messages[:-1], add_generation_prompt=True, tokenize=True)
        full = tokenizer.apply_chat_template(messages, tokenize=True)
        prompt, full = _ids(prompt), _ids(full)
        measured.append((len(full), full, [-100] * len(prompt) + full[len(prompt):]))
    measured.sort(key=lambda item: item[0])
    chosen = measured[-1] if how == "max" else measured[len(measured) // 2]
    return chosen[1], chosen[2]


def run_variant(model, torch, ids, labels, checkpointing: bool, logits: str, dropout: float) -> dict:
    import torch.nn.functional as F  # noqa: PLC0415

    if checkpointing:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    else:
        model.gradient_checkpointing_disable()
    for module in model.modules():
        if hasattr(module, "lora_dropout") and "default" in module.lora_dropout:
            module.lora_dropout["default"] = torch.nn.Dropout(dropout) if dropout else torch.nn.Identity()
    model.train()
    input_ids = torch.tensor([ids], device="cuda")
    target = torch.tensor([labels], device="cuda")
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    base = torch.cuda.memory_allocated() / GIB
    result: dict = {"trước": round(base, 2)}
    started = time.perf_counter()
    try:
        if logits == "answer":
            first = int((target[0] != -100).nonzero()[0])
            keep = target.shape[1] - first + 1
            out = model(input_ids=input_ids, use_cache=False, logits_to_keep=keep)
            sliced = target[:, -keep:]
        else:
            out = model(input_ids=input_ids, use_cache=False)
            sliced = target
        shift = out.logits[:, :-1, :].float()
        loss = F.cross_entropy(shift.reshape(-1, shift.shape[-1]), sliced[:, 1:].reshape(-1), ignore_index=-100)
        torch.cuda.synchronize()
        result["đỉnh lan xuôi"] = round(torch.cuda.max_memory_allocated() / GIB, 2)
        loss.backward()
        torch.cuda.synchronize()
        result["đỉnh cả mẫu"] = round(torch.cuda.max_memory_allocated() / GIB, 2)
        result["giây"] = round(time.perf_counter() - started, 1)
        result["loss"] = round(float(loss), 4)
    except torch.OutOfMemoryError:
        result["OOM"] = f"vượt trần sau {time.perf_counter() - started:.1f} s"
        result["đỉnh trước OOM"] = round(torch.cuda.max_memory_allocated() / GIB, 2)
    finally:
        model.zero_grad(set_to_none=True)
        del input_ids, target
        out = loss = shift = None  # noqa: F841
        gc.collect()
        torch.cuda.empty_cache()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--pick", choices=("max", "median"), default="median")
    parser.add_argument("--cap", type=float, default=0.95, help="phần VRAM thật PyTorch được dùng; vượt là OOM")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    import torch  # noqa: PLC0415
    from peft import LoraConfig, get_peft_model  # noqa: PLC0415
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig  # noqa: PLC0415

    torch.cuda.set_per_process_memory_fraction(args.cap)
    total = torch.cuda.get_device_properties(0).total_memory / GIB
    tokenizer = AutoTokenizer.from_pretrained(args.base)
    rows = [json.loads(line) for line in (args.data / "train.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    ids, labels = pick_sample(rows, tokenizer, args.pick)
    answer = sum(label != -100 for label in labels)
    print(f"mẫu {args.pick}: {len(ids)} token, đáp án {answer} | trần PyTorch {args.cap:.0%} của {total:.2f} GiB", flush=True)

    model = AutoModelForCausalLM.from_pretrained(
        args.base,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        ),
        dtype=torch.bfloat16,
        device_map={"": 0},
    )
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
                                             task_type="CAUSAL_LM", target_modules=TARGETS))
    print(f"model nạp xong: {torch.cuda.memory_allocated() / GIB:.2f} GiB | attention = "
          f"{getattr(model.config, '_attn_implementation', '?')}", flush=True)
    report = []
    # Cùng một đề, loss lan xuôi (không gradient) qua hai đường attention phải khớp - cuDNN không được đổi phép tính.
    with torch.no_grad():
        losses = {}
        keep = len(labels) - next(i for i, label in enumerate(labels) if label != -100) + 1
        for kernel in ("default", "cudnn"):
            set_attention(torch, kernel)
            model.eval()
            try:
                out = model(input_ids=torch.tensor([ids], device="cuda"), use_cache=False, logits_to_keep=keep)
                shift = out.logits[:, :-1, :].float()
                target = torch.tensor([labels[-keep:]], device="cuda")[:, 1:]
                losses[kernel] = float(torch.nn.functional.cross_entropy(
                    shift.reshape(-1, shift.shape[-1]), target.reshape(-1), ignore_index=-100))
                del out, shift, target
            except torch.OutOfMemoryError:
                losses[kernel] = float("nan")  # đường math không chứa nổi mẫu dài - chính là điều đang đo
            torch.cuda.empty_cache()
        print(f"loss lan xuôi: mặc định {losses['default']:.5f} | cuDNN {losses['cudnn']:.5f}", flush=True)
    for name, checkpointing, logits, dropout, kernel in VARIANTS:
        set_attention(torch, kernel)
        result = run_variant(model, torch, ids, labels, checkpointing, logits, dropout)
        report.append({"biến thể": name, **result})
        print(f"  {name:48} {json.dumps(result, ensure_ascii=False)}", flush=True)
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
