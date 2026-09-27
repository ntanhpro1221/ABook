"""Huấn luyện QLoRA cho khâu phân tích, từ bộ train/dev do `build_training_set.py` dựng.

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/train_lora.py --smoke 8
    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/train_lora.py --epochs 1

**Chạy bằng venv RIÊNG** `D:/Novels/LLM_Train/.venv` (torch 2.11+cu128, transformers 5.17, peft 0.21, trl 1.13,
bitsandbytes 0.50.2) - KHÔNG phải `runtime/.venv` của dây chuyền: nâng gói trong runtime là đổi hash chính sách
chất lượng, và cái đó chỉ được làm ở ranh giới.

Model nền: `Qwen/Qwen3-4B-Instruct-2507`. Cùng họ với model sản xuất (`qwen3:8b`) nên prompt không phải viết lại,
nhỏ đủ để QLoRA 4-bit vừa 8 GB VRAM, và bản `-Instruct-2507` KHÔNG có chế độ nghĩ - chế độ ấy chính là thứ làm
`qwen3.5:9b` trả về "0/5 IDs" trong lượt đo đêm 19-09.

Số đo để chọn tham số (tokenizer Qwen3, 20-09): mỗi mẫu trung vị **3.213** token, p99 4.069, tối đa **4.276**; riêng
câu trả lời trung vị 369, tối đa 784. Nên `--max-length 4352` giữ TRỌN mọi mẫu - cắt ngắn ở đây là cắt mất câu trả
lời, tức huấn luyện trên một đề bài không có đáp án. Một epoch = 1.727 mẫu = **5,29M token**.

`assistant_only_loss=True`: chỉ tính loss trên câu trả lời. Không có nó thì model học cả việc sinh lại đề bài -
mà đề bài là prompt sản xuất, thứ nó sẽ luôn được cho sẵn.

Bộ canh GPU: script TỪ CHỐI chạy khi có lượt sản xuất đang bay (dùng lại `_runs_in_flight` của `apply_all.py` chứ
không viết bộ canh thứ hai - docstring của hàm ấy ghi hai lần bộ canh tự viết đã sai). Máy chỉ có 8 GB VRAM:
huấn luyện chen vào giữa một lượt thu là ném cả lượt ấy vào OOM.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_BASE = "Qwen/Qwen3-4B-Instruct-2507"
DEFAULT_DATA = Path(r"D:/Novels/LLM_Train/data")
DEFAULT_OUT = Path(r"D:/Novels/LLM_Train/runs")
# Trên mọi mẫu đã đo, mẫu dài nhất là 4.276 token; để trần cao hơn nó một nhịp.
DEFAULT_MAX_LENGTH = 4352
# Hai lần tái hiện y hệt (27-09 01:41 và 07:37): hết bước 3, Trainer lưu checkpoint, `optimizer.pt` đứng ở 12 MB rồi
# 29 MB (đủ là ~66 MB), driver ghi `nvlddmkm` 14 "\Device\UVMLiteProcess1 | GPU recovery action changed from 0x0 (None)
# to 0x2 (Node Reboot Required)", rồi máy BSOD 0x1E (c0000005, đọc 0x28) ở cùng một chỗ trong mã cả hai lần. UVM là bộ
# nhớ CUDA dùng chung (managed memory) - thứ duy nhất trong script dùng nó là trạng thái của optimizer `paged_*` của
# bitsandbytes, và lúc lưu là lúc CPU đọc vùng ấy ra.
# Bức tường VRAM 21-09 ("38 token/s ở VRAM 95%, ~40 giờ một epoch") đo lại 27-09 bằng profile_train_memory.py:
# PyTorch cho Windows KHÔNG có flash attention, kernel memory-efficient từ chối GQA (Qwen3: 32 đầu query, 8 đầu k/v),
# cuDNN bị tắt mặc định - nên SDPA rơi về đường MATH, dựng cả ma trận chú ý: +5,2 GB cho MỘT lớp (xuôi + ngược) so
# với +0,24 GB của cuDNN. Một mẫu 3.213 token: đỉnh 4,73 GiB và 6,1 s với cuDNN, so với OOM ở trần 7,56 GiB (và
# 65-233 s khi để driver tràn sang RAM). Loss lan xuôi khớp: 0,24411 (math) / 0,24364 (cuDNN).
ATTENTION_NOTE = "attention ghim vào cuDNN (xem pin_attention_kernel)"


def pin_attention_kernel(torch) -> None:
    """Chỉ cho SDPA dùng cuDNN: đường math không được lặng lẽ quay lại - thiếu kernel thì phải báo lỗi."""
    torch.backends.cuda.enable_cudnn_sdp(True)
    torch.backends.cuda.enable_math_sdp(False)
    torch.backends.cuda.enable_mem_efficient_sdp(False)
    torch.backends.cuda.enable_flash_sdp(False)


PAGED_OPTIMIZER_CRASH = (
    "từ chối: optimizer `paged_*` (bộ nhớ CUDA UVM) làm máy này BSOD khi lưu checkpoint - hai lần 27-09, driver 592.47, "
    "RTX 5060 Laptop (xem docs/LLM_EVAL.md). Dùng --optim adamw_8bit."
)


def load_rows(path: Path, only: str) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if only != "both":
        rows = [row for row in rows if row.get("type") == only]
    return [{"messages": row["messages"]} for row in rows]


def answer_logits_trainer(base: type) -> type:
    """`SFTTrainer` chỉ dựng logits cho phần ĐÁP ÁN, không cho cả chuỗi.

    Giả thuyết cho bức tường VRAM (26-09): với từ vựng 151.936 của Qwen3, một mẫu 3,2k token dựng ma trận logits
    ~0,5 tỉ phần tử - ~1 GB bf16, ~2 GB khi hàm loss nâng lên fp32, cộng gradient cùng cỡ. Trên 8 GB, cộng model
    4-bit (~2,8 GB) là tràn, và driver Windows lặng lẽ đẩy phần tràn sang RAM chứ không báo OOM - khớp với
    "38 token/s ở VRAM 95%" đã đo 21-09. Mà `assistant_only_loss` chỉ cần logits ở ~360-600 vị trí cuối (đáp án
    luôn là lượt cuối của mẫu), nên `logits_to_keep` cắt ma trận ấy 5-9 lần mà không đổi một giá trị loss nào.
    """
    import torch.nn.functional as F  # noqa: PLC0415

    class AnswerLogitsTrainer(base):
        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            labels = inputs.pop("labels")
            if labels.shape[0] != 1:
                raise ValueError("--logits answer cần đúng 1 mẫu mỗi bước (per_device_train_batch_size=1)")
            answer = (labels[0] != -100).nonzero()
            first = int(answer[0]) if len(answer) else labels.shape[1] - 1
            keep = labels.shape[1] - first + 1  # +1: logit ở ngay TRƯỚC token đáp án đầu tiên dự đoán token ấy
            inputs["use_cache"] = False
            outputs = model(**inputs, logits_to_keep=keep)
            logits = outputs.logits[:, :-1, :].float()
            target = labels[:, -keep:][:, 1:]
            loss = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), target.reshape(-1),
                                   ignore_index=-100, reduction="sum")
            loss = loss / (num_items_in_batch if num_items_in_batch is not None else (target != -100).sum())
            return (loss, outputs) if return_outputs else loss

    return AnswerLogitsTrainer


def trace_callback(path: Path):
    """Nhật ký từng pha của vòng huấn luyện, fsync mỗi dòng - để một lần SẬP MÁY vẫn để lại dấu vết.

    27-09 01:41 phép đo `--smoke 8 --accum 2 --logits answer` làm máy BSOD (0x1E, nvlddmkm.sys) và không để lại gì:
    stdout đi qua `tail`, còn log của Trainer chỉ in mỗi 5 bước. Dòng cuối cùng trong file này cho biết máy chết
    ở pha nào (nạp model, lan xuôi/ngược một mẫu, bước tối ưu) và VRAM PyTorch đang giữ bao nhiêu lúc ấy.
    """
    import os  # noqa: PLC0415
    import time  # noqa: PLC0415

    import torch  # noqa: PLC0415
    from transformers import TrainerCallback  # noqa: PLC0415

    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a", encoding="utf-8")
    start = time.monotonic()

    def write(event: str) -> None:
        memory = ""
        if torch.cuda.is_available():
            memory = (f" | cấp phát {torch.cuda.memory_allocated() / 2**30:.2f} GiB, giữ "
                      f"{torch.cuda.memory_reserved() / 2**30:.2f} GiB, đỉnh {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB")
        handle.write(f"{time.strftime('%H:%M:%S')} +{time.monotonic() - start:7.1f}s {event}{memory}\n")
        handle.flush()
        os.fsync(handle.fileno())

    class Trace(TrainerCallback):
        def on_train_begin(self, args, state, control, **kwargs):
            write("bắt đầu huấn luyện")

        def on_step_begin(self, args, state, control, **kwargs):
            write(f"bước {state.global_step + 1} bắt đầu")

        def on_substep_end(self, args, state, control, **kwargs):
            write("xong lan ngược một mẫu")

        def on_pre_optimizer_step(self, args, state, control, **kwargs):
            write("lan ngược mẫu cuối xong, trước bước tối ưu")

        def on_optimizer_step(self, args, state, control, **kwargs):
            write("sau bước tối ưu")

        def on_step_end(self, args, state, control, **kwargs):
            write(f"bước {state.global_step} xong")

        def on_train_end(self, args, state, control, **kwargs):
            write("kết thúc huấn luyện")

    return Trace(), write


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=None, help="mặc định runs/<tên model>-<only>-r<r>")
    parser.add_argument("--only", choices=("both", "generator", "critic"), default="both")
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--max-length", type=int, default=DEFAULT_MAX_LENGTH)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--r", type=int, default=16)
    parser.add_argument("--alpha", type=int, default=32)
    parser.add_argument("--accum", type=int, default=8, help="batch hiệu dụng = accum (batch mỗi bước luôn là 1)")
    parser.add_argument("--smoke", type=int, default=0, help="chỉ N mẫu và 3 bước - kiểm đường ống, không huấn luyện")
    parser.add_argument("--force", action="store_true", help="chạy dù có lượt sản xuất đang bay (sẽ tranh VRAM)")
    parser.add_argument("--optim", default="adamw_8bit",
                        help="adamw_8bit (mặc định). Bản `paged_*` bị CHẶN trên Windows - xem PAGED_OPTIMIZER_CRASH")
    parser.add_argument("--logits", choices=("all", "answer"), default="answer",
                        help="answer = chỉ dựng logits cho phần đáp án (xem answer_logits_trainer); all = như TRL mặc định")
    parser.add_argument("--vram-cap", type=float, default=0.95,
                        help="phần VRAM thật PyTorch được giữ; vượt là OOM thay vì để driver Windows tràn sang RAM "
                             "(chậm 17-80 lần, và là nền của lần BSOD 27-09)")
    parser.add_argument("--attention", choices=("cudnn", "auto"), default="cudnn",
                        help="cudnn = ghim kernel cuDNN (mặc định); auto = để PyTorch tự chọn (rơi về math trên máy này)")
    parser.add_argument("--save-steps", type=int, default=50,
                        help="lưu checkpoint mỗi N bước (50 bước x accum 8 = 400 mẫu, ~35 phút): máy khởi động lại chỉ mất chừng ấy")
    parser.add_argument("--resume", action="store_true",
                        help="chạy tiếp từ checkpoint mới nhất trong --out nếu có (không có thì bắt đầu từ đầu)")
    parser.add_argument("--trace", type=Path, default=None,
                        help="ghi từng pha của vòng huấn luyện vào file này, fsync mỗi dòng (xem trace_callback)")
    args = parser.parse_args(argv)
    if os.name == "nt" and args.optim.startswith("paged_"):
        raise SystemExit(PAGED_OPTIMIZER_CRASH)

    from scripts.pending_patches.apply_all import _runs_in_flight  # noqa: PLC0415  (dùng lại bộ canh đã đo)

    flying = _runs_in_flight()
    if flying and not args.force:
        for project, reason in flying:
            print(f"  đang bay: {project.name} ({reason})")
        raise SystemExit("từ chối: máy chỉ có 8 GB VRAM, huấn luyện lúc này là ném lượt sản xuất vào OOM")

    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    torch.cuda.set_per_process_memory_fraction(args.vram_cap)
    if args.attention == "cudnn":
        pin_attention_kernel(torch)
    train_rows = load_rows(args.data / "train.jsonl", args.only)
    dev_rows = load_rows(args.data / "dev.jsonl", args.only)
    if args.smoke:
        train_rows = train_rows[: args.smoke]
        dev_rows = dev_rows[: max(2, args.smoke // 4)]
    out = args.out or (DEFAULT_OUT / f"{args.base.split('/')[-1]}-{args.only}-r{args.r}")
    print(f"  model nền {args.base} | train {len(train_rows)} mẫu, dev {len(dev_rows)} | ra {out}")

    tokenizer = AutoTokenizer.from_pretrained(args.base)
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    config = SFTConfig(
        output_dir=str(out),
        num_train_epochs=args.epochs if not args.smoke else 1.0,
        max_steps=3 if args.smoke else -1,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=args.accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        # TRL 1.13 ở venv này KHÔNG có `warmup_ratio` (chỉ `warmup_steps`) - đã thử và nó ném TypeError.
        warmup_steps=max(5, int(0.03 * len(train_rows) / max(1, args.accum))),
        logging_steps=5,
        save_steps=args.save_steps,
        save_total_limit=2,
        eval_strategy="steps" if dev_rows else "no",
        eval_steps=100,
        per_device_eval_batch_size=1,
        bf16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim=args.optim,
        max_length=args.max_length,
        packing=False,          # mỗi mẫu là một lượt hỏi trọn vẹn; ghép chúng lại là trộn hai đề bài
        assistant_only_loss=True,
        model_init_kwargs={"quantization_config": quantization, "dtype": torch.bfloat16},
        report_to=[],
        seed=1234,
        # Chế độ `answer` trả logits ngắn hơn nhãn: chỉ giữ loss khi eval, đừng gom logits.
        prediction_loss_only=args.logits == "answer",
    )
    trainer_class = answer_logits_trainer(SFTTrainer) if args.logits == "answer" else SFTTrainer
    trace, note = trace_callback(args.trace) if args.trace else (None, lambda _event: None)
    note(f"nạp model {args.base} (logits={args.logits}, optim={args.optim}, attention={args.attention}, "
         f"trần VRAM={args.vram_cap:.0%}, accum={args.accum}, smoke={args.smoke})")
    trainer = trainer_class(
        model=args.base,
        args=config,
        train_dataset=Dataset.from_list(train_rows),
        eval_dataset=Dataset.from_list(dev_rows) if dev_rows else None,
        processing_class=tokenizer,
        peft_config=LoraConfig(
            r=args.r,
            lora_alpha=args.alpha,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        ),
        callbacks=[trace] if trace else None,
    )
    note("model đã nạp, trainer sẵn sàng")
    torch.cuda.reset_peak_memory_stats()
    checkpoints = sorted(out.glob("checkpoint-*"), key=lambda path: int(path.name.split("-")[-1])) if args.resume else []
    note(f"chạy tiếp từ {checkpoints[-1].name}" if checkpoints else "bắt đầu từ đầu")
    result = trainer.train(resume_from_checkpoint=str(checkpoints[-1]) if checkpoints else None)
    metrics = result.metrics
    total = torch.cuda.get_device_properties(0).total_memory / 2**30
    print(f"  logits={args.logits} | {metrics.get('train_runtime', 0):.0f} s cho {config.max_steps if args.smoke else '?'} bước "
          f"x accum {args.accum} | {metrics.get('train_samples_per_second', 0):.3f} mẫu/s | VRAM đỉnh: cấp phát "
          f"{torch.cuda.max_memory_allocated() / 2**30:.2f} GiB, giữ {torch.cuda.max_memory_reserved() / 2**30:.2f} GiB "
          f"trên {total:.2f} GiB")
    trainer.save_model(str(out))
    tokenizer.save_pretrained(str(out))
    print(f"  đã lưu adapter vào {out}")
    print("  bước tiếp: gộp adapter rồi `ollama create` để chấm bằng scripts/model_eval/eval_models.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
