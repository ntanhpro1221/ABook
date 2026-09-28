"""QLoRA trên nền 8B bằng Unsloth - chạy TRONG WSL2 (archlinux, môi trường ~/unsloth), 28-09.

    wsl.exe -d archlinux -- bash -lc ". ~/unsloth/bin/activate && python \
        '/mnt/d/Novels/ABook/_internal/scripts/model_eval/train_lora_unsloth.py' \
        --data /mnt/d/Novels/LLM_Train/data_v3 --out /mnt/d/Novels/LLM_Train/runs/qwen3-8b-lora-28-09 --smoke 8"

Vì sao: `train_lora.py` (PyTorch trên Windows) vừa khít nền 4B trên card 8 GB (đỉnh 4,7-5,0 GiB); nền 8B cần ~8,5-9 GB
theo cùng cách - hai bảng từ vựng 16-bit ~2,5 GB + các lớp 4-bit ~3,5 GB + kích hoạt của prompt 3-4 nghìn token. Unsloth
đẩy kích hoạt của gradient checkpointing sang RAM và tính cross-entropy theo khúc, nên có thể nhét được. Chủ sách hỏi
"sao không huấn luyện trên nền qwen3:8b?" - đây là phép thử.

Cùng siêu tham số với `train_lora.py` để so công bằng: r=16, alpha=32, bảy phép chiếu, lr 1e-4 cosine, batch 1 x accum
8, adamw_8bit, 1 epoch, max_length 4352, loss CHỈ trên câu trả lời. Nền Qwen3-8B có chế độ nghĩ: dựng chữ bằng khuôn
chat với `enable_thinking=False` (khối think rỗng trước JSON - đúng thứ Ollama gửi cho qwen3:8b khi think=false).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

# 28-09 10:27: 8B 4-bit (5,7 GB) nạp được nhưng bước đầu hết VRAM ở loss ("No or negligible GPU memory available for fused
# cross entropy") - chia loss thành khúc cố định thay vì để Unsloth dò VRAM trống (đã gần 0). unsloth_zoo đọc biến này lúc
# import, nên phải đặt TRƯỚC dòng import unsloth.
os.environ.setdefault("UNSLOTH_CE_LOSS_N_CHUNKS", "32")

from unsloth import FastLanguageModel  # noqa: I001 - Unsloth phải được nạp trước transformers/trl
from unsloth.chat_templates import train_on_responses_only

import torch
from datasets import Dataset
from trl import SFTConfig, SFTTrainer

TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="unsloth/Qwen3-8B-unsloth-bnb-4bit")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--max-length", type=int, default=4352)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--r", type=int, default=16)
    parser.add_argument("--alpha", type=int, default=32)
    parser.add_argument("--accum", type=int, default=8)
    parser.add_argument("--smoke", type=int, default=0, help="chỉ N mẫu dài nhất và 3 bước - đo VRAM, không huấn luyện")
    parser.add_argument("--smoke-at", choices=("longest", "median"), default="longest",
                        help="median: N mẫu quanh độ dài TRUNG VỊ - đo tốc độ một bước điển hình thay vì đỉnh VRAM (28-09: "
                             "8B trên card 8 GB tràn VRAM ở mẫu dài nhất, câu hỏi là mẫu thường có tràn không)")
    parser.add_argument("--smoke-steps", type=int, default=3)
    parser.add_argument("--render-only", action="store_true", help="in đuôi một mẫu đã dựng khuôn rồi thoát")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--export-gguf", default="",
                        help="không huấn luyện: gộp <out>/adapter vào nền 16-bit, xuất GGUF theo kiểu nén này (vd q4_k_m)")
    parser.add_argument("--save-steps", type=int, default=50,
                        help="lưu checkpoint mỗi N bước; 8B trên card 8 GB ~3 phút/bước nên 10 (~30 phút) - máy khởi "
                             "động lại chỉ mất chừng ấy")
    parser.add_argument("--offload-embedding", action="store_true",
                        help="nạp bằng FastModel và đẩy bảng embedding sang RAM (~1,2 GB với Qwen3-8B) - nhánh tối ưu "
                             "FastLanguageModel của Qwen3 lặng lẽ bỏ qua tuỳ chọn này")
    args = parser.parse_args()
    loader = FastLanguageModel
    if args.offload_embedding:
        from unsloth import FastModel

        loader = FastModel

    if args.export_gguf:
        # Q4_K_M như qwen3:8b đang chạy: bản q8_0 của 8B nặng 8,7 GB, không vừa card 8 GB lúc suy luận.
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=str(args.out / "adapter"), max_seq_length=args.max_length, load_in_4bit=True, dtype=None
        )
        model.save_pretrained_gguf(str(args.out / "gguf"), tokenizer, quantization_method=args.export_gguf)
        print("đã xuất", sorted(str(path) for path in (args.out / "gguf").rglob("*.gguf")))
        return 0

    extra = {"offload_embedding": True} if args.offload_embedding else {}
    model, tokenizer = loader.from_pretrained(
        model_name=args.base, max_seq_length=args.max_length, load_in_4bit=True, dtype=None, **extra
    )
    rows = [json.loads(line) for line in (args.data / "train.jsonl").open(encoding="utf-8")]
    texts = [tokenizer.apply_chat_template(row["messages"], tokenize=False, enable_thinking=False) for row in rows]
    if args.render_only:
        print(texts[0][-600:])
        return 0
    lengths = [len(tokenizer(text).input_ids) for text in texts]
    print(f"{len(texts)} mẫu, token trung vị {sorted(lengths)[len(lengths) // 2]}, dài nhất {max(lengths)}")
    if max(lengths) > args.max_length:
        raise SystemExit(f"mẫu dài {max(lengths)} > max_length {args.max_length}: cắt là mất câu trả lời")
    if args.smoke:
        ranked = sorted(range(len(texts)), key=lambda index: -lengths[index])
        if args.smoke_at == "median":
            ranked = ranked[max(0, len(ranked) // 2 - args.smoke // 2):]
        order = ranked[: args.smoke]
        print(f"thử trên {len(order)} mẫu, {min(lengths[i] for i in order)}-{max(lengths[i] for i in order)} token")
        texts = [texts[index] for index in order]  # mặc định mẫu DÀI NHẤT: đo đúng đỉnh VRAM

    model = loader.get_peft_model(
        model, r=args.r, lora_alpha=args.alpha, lora_dropout=0, target_modules=TARGETS, bias="none",
        use_gradient_checkpointing="unsloth", random_state=3407,
    )
    steps = max(1, int(len(texts) * args.epochs / args.accum))
    config = SFTConfig(
        output_dir=str(args.out), dataset_text_field="text", max_length=args.max_length, packing=False,
        per_device_train_batch_size=1, gradient_accumulation_steps=1 if args.smoke else args.accum,
        learning_rate=args.lr, lr_scheduler_type="cosine", warmup_steps=max(5, int(0.03 * steps)),
        num_train_epochs=args.epochs, max_steps=args.smoke_steps if args.smoke else -1, optim="adamw_8bit",
        # T4 (Kaggle/Colab miễn phí) không có bf16: tự rơi về fp16, như sổ tay của Unsloth.
        bf16=torch.cuda.is_bf16_supported(), fp16=not torch.cuda.is_bf16_supported(),
        logging_steps=1 if args.smoke else 5, save_steps=args.save_steps, save_total_limit=3, report_to="none", seed=3407,
    )
    trainer = SFTTrainer(model=model, processing_class=tokenizer, train_dataset=Dataset.from_dict({"text": texts}),
                         args=config)
    trainer = train_on_responses_only(trainer, instruction_part="<|im_start|>user\n",
                                      response_part="<|im_start|>assistant\n")
    torch.cuda.reset_peak_memory_stats()
    started = time.time()
    resumable = args.resume and any(args.out.glob("checkpoint-*"))
    trainer.train(resume_from_checkpoint=True if resumable else None)
    peak = torch.cuda.max_memory_reserved() / 2**30
    print(f"xong {time.time() - started:.0f} s, đỉnh VRAM (đã giữ) {peak:.2f} GiB")
    if not args.smoke:
        model.save_pretrained(str(args.out / "adapter"))
        tokenizer.save_pretrained(str(args.out / "adapter"))
        print("đã lưu adapter", args.out / "adapter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
