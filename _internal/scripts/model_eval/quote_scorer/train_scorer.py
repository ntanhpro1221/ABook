"""Huấn luyện + chấm BỘ CHẤM ỨNG VIÊN người nói (ANALYSIS_RESEARCH.md, E3).

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/train_scorer.py \
        --data D:/Novels/LLM_Train/data/quote_vi --out D:/Novels/LLM_Train/runs/scorer_vi [--epochs 6]

Theo "Fast and Accurate Quotation Attribution in Literary Texts" (arXiv 2608.02359), rút gọn:

- bộ mã hoá (mặc định mmBERT-base, đa ngữ có tiếng Việt, kiến trúc ModernBERT) đọc MỘT cửa sổ một lần;
- câu thoại q và chỗ nhắc m biểu diễn bằng hai đầu mút: h = [H[đầu]; H[cuối]] (span endpoints như đồng tham chiếu
  span-based, Lee và cs. 2017);
- điểm s(q, m) = MLP([h_q; h_m; h_q * h_m; khoảng cách]) với khoảng cách (số token, có dấu, chia xô) là một
  embedding học được; thêm lựa chọn "không ai" s(q, ∅) = MLP∅(h_q) cho người kể / NPC không tên;
- loss = -log Σ_{m đúng người} e^s + log Σ_{m ∪ ∅} e^s (log-likelihood biên trên các chỗ nhắc đúng người, như huấn
  luyện đồng tham chiếu); câu có người nói không nằm trong ứng viên thì bỏ khỏi loss (không có đáp án để học).

Chấm: độ đúng người nói trên MỌI câu thoại/nội tâm của tập (đúng = chọn chỗ nhắc thuộc đúng người, hoặc chọn ∅ khi
gold là người kể/NPC), tách: có tên / không tên / người nói nằm ngoài ứng viên (chắc chắn sai - giới hạn của cách
lấy ứng viên chỉ bằng bí danh).

KHÔNG dùng optimizer `paged_*` (BSOD 27-09); attention để PyTorch chọn - cửa sổ 1.024 token, 12 đầu, không GQA: kernel
memory-efficient dùng được, đường math cũng chỉ ~25 MB mỗi lớp.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

DISTANCE_BUCKETS = [-1024, -256, -128, -64, -32, -16, -8, -1, 0, 8, 16, 32, 64, 128, 256, 1024]


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def bucket(distance: int) -> int:
    for index, edge in enumerate(DISTANCE_BUCKETS):
        if distance <= edge:
            return index
    return len(DISTANCE_BUCKETS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--encoder", default="jhu-clsp/mmBERT-base")
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--lr", type=float, default=3e-5, help="bộ mã hoá")
    parser.add_argument("--head-lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--vram-cap", type=float, default=0.9)
    parser.add_argument("--predict-only", action="store_true",
                        help="không huấn luyện: nạp mô hình đã lưu trong --out, chấm test, ghi test_predictions.jsonl")
    parser.add_argument("--pretrain", type=Path, nargs="*", default=[],
                        help="giai đoạn 1 (curriculum): học trước trên dữ liệu này (vd che dấu hiệu N1 - chỉ có câu CÓ TÊN, "
                             "trộn thẳng vào thì lựa chọn 'không ai' bị bỏ đói: dev người kể/NPC 0%% ở 27-09), rồi mới tới gold")
    parser.add_argument("--pretrain-epochs", type=int, default=2)
    parser.add_argument("--fold", type=int, default=None,
                        help="kiểm chứng chéo (make_folds.py): test = fold<k>.jsonl, train = các fold còn lại; dev chỉ để "
                             "theo dõi (= chính fold ấy) - so cấu hình bằng epoch cuối (epochs/), không chọn theo dev")
    parser.add_argument("--fold-prefix", default="fold",
                        help="fold (theo chương) hoặc bookfold (theo truyện: chấm một truyện chưa từng thấy) - make_folds.py")
    parser.add_argument("--save-last", action="store_true", help="kiểm chứng chéo: vẫn lưu mô hình epoch cuối")
    parser.add_argument("--predict-file", type=Path, default=None,
                        help="không huấn luyện: nạp --init, chấm tệp cửa sổ này, ghi <out>/predictions.jsonl có xác suất")
    parser.add_argument("--init", type=Path, default=None,
                        help="nạp encoder/ + head.pt của một lần chạy trước (vd lần chỉ học trước PDNC) rồi mới huấn luyện")
    parser.add_argument("--extra-train", type=Path, nargs="*", default=[],
                        help="thêm cửa sổ huấn luyện (vd dữ liệu che dấu hiệu N1: data/quote_vi_cue/train.jsonl)")
    args = parser.parse_args()

    import torch  # noqa: PLC0415
    import torch.nn as nn  # noqa: PLC0415
    from transformers import AutoModel, AutoTokenizer  # noqa: PLC0415

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        torch.cuda.set_per_process_memory_fraction(args.vram_cap)
    tokenizer = AutoTokenizer.from_pretrained(args.encoder)
    # Trọng số gốc fp32 (AdamW trên bf16 làm tròn mất các bước nhỏ), lan xuôi bf16 qua autocast: ~5,5 GB với mmBERT-base.
    encoder = AutoModel.from_pretrained(args.encoder, dtype=torch.float32).to(device)
    size = encoder.config.hidden_size
    # mmBERT: ~197 triệu / 307 triệu tham số là bảng embedding từ vựng 256 nghìn (tokenizer Gemma 2) - fp32 + Adam riêng
    # nó ~3 GB, cả bộ hết 8 GB (OOM 27-09). Bài toán không cần học lại nghĩa từ: đóng băng embedding.
    encoder.get_input_embeddings().weight.requires_grad_(False)
    trainable = [parameter for parameter in encoder.parameters() if parameter.requires_grad]

    if args.fold is None:
        train, dev, test = (load(args.data / f"{name}.jsonl") for name in ("train", "dev", "test"))
    else:
        folds = sorted(args.data.glob(f"{args.fold_prefix}*.jsonl"))
        held_out = f"{args.fold_prefix}{args.fold}.jsonl"
        test = load(args.data / held_out)
        train = [window for path in folds if path.name != held_out for window in load(path)]
        dev = test
        print(f"kiểm chứng chéo: {held_out} ({len(folds)} phần) làm test (dev = chính nó, chỉ để theo dõi)", flush=True)
    for extra in args.extra_train:
        train += load(extra)
    pretrain = [window for path in args.pretrain for window in load(path)]
    # N9: chỗ nhắc trong danh sách nhân vật đầu cửa sổ không có khoảng cách thật tới câu - một xô riêng. Chỉ thêm xô
    # khi dữ liệu có cast, để các lần chạy không cast khởi tạo y hệt trước (cùng seed -> cùng số ngẫu nhiên).
    has_cast = any(mention.get("cast") for window in train + dev + test for mention in window["mentions"])
    cast_bucket = len(DISTANCE_BUCKETS) + 1

    class Head(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.distance = nn.Embedding(len(DISTANCE_BUCKETS) + 1 + has_cast, 32)
            self.pair = nn.Sequential(nn.Linear(6 * size + 32, 2 * size), nn.GELU(), nn.Linear(2 * size, 1))
            self.null = nn.Sequential(nn.Linear(2 * size, size), nn.GELU(), nn.Linear(size, 1))

        def forward(self, quote: torch.Tensor, mentions: torch.Tensor, distances: torch.Tensor) -> torch.Tensor:
            count = mentions.shape[0]
            q = quote.unsqueeze(0).expand(count, -1)
            pair = torch.cat([q, mentions, q * mentions, self.distance(distances)], dim=-1)
            scores = self.pair(pair).squeeze(-1)
            return torch.cat([scores, self.null(quote)], dim=0)  # phần tử cuối = "không ai"

    head = Head().to(device)
    if args.init:
        encoder.load_state_dict(AutoModel.from_pretrained(args.init / "encoder", dtype=torch.float32).state_dict())
        head.load_state_dict(torch.load(args.init / "head.pt")["head"])
        print(f"nạp mô hình khởi đầu từ {args.init}", flush=True)

    def encode(window: dict):
        batch = tokenizer(window["text"], return_offsets_mapping=True, return_tensors="pt", truncation=True,
                          max_length=2048)
        offsets = batch.pop("offset_mapping")[0].tolist()
        with torch.autocast(device_type=device, dtype=torch.bfloat16, enabled=device == "cuda"):
            hidden = encoder(**{k: v.to(device) for k, v in batch.items()}).last_hidden_state[0].float()

        def token_span(start: int, end: int) -> tuple[int, int] | None:
            inside = [i for i, (a, b) in enumerate(offsets) if b > a and a < end and b > start]
            return (inside[0], inside[-1]) if inside else None

        return hidden, token_span

    def score_window(window: dict):
        """(điểm từng câu, danh sách thực thể của từng chỗ nhắc) cho một cửa sổ."""
        hidden, token_span = encode(window)
        spans, entities, cast = [], [], []
        for mention in window["mentions"]:
            span = token_span(mention["start"], mention["end"])
            if span:
                spans.append(span)
                entities.append(mention["entities"])
                cast.append(bool(mention.get("cast")))
        if spans:
            m_repr = torch.stack([torch.cat([hidden[a], hidden[b]]) for a, b in spans])
        else:
            m_repr = torch.zeros(0, 2 * size, device=device)
        results = []
        for quote in window["quotes"]:
            span = token_span(quote["start"], quote["end"])
            if span is None:
                results.append(None)
                continue
            q_repr = torch.cat([hidden[span[0]], hidden[span[1]]])
            distances = torch.tensor([cast_bucket if is_cast else bucket(a - span[0])
                                      for (a, _), is_cast in zip(spans, cast)], device=device, dtype=torch.long)
            results.append(head(q_repr, m_repr, distances))
        return results, entities

    print(f"train {len(train)} cửa sổ, dev {len(dev)}, test {len(test)}", flush=True)
    optimizer = torch.optim.AdamW([
        {"params": trainable, "lr": args.lr},
        {"params": head.parameters(), "lr": args.head_lr},
    ], weight_decay=0.01)
    total_steps = args.epochs * len(train) + args.pretrain_epochs * len(pretrain)
    schedule = torch.optim.lr_scheduler.LambdaLR(
        optimizer, lambda step: min(1.0, (step + 1) / max(1, total_steps // 20)) * max(0.0, 1 - step / total_steps))

    def evaluate(windows: list[dict], dump: list | None = None) -> dict:
        encoder.eval()
        head.eval()
        tally = {"all": [0, 0], "named": [0, 0], "null": [0, 0], "uncovered": 0}
        with torch.no_grad():
            for window in windows:
                results, entities = score_window(window)
                for quote, scores in zip(window["quotes"], results):
                    gold = quote["speaker"]
                    if scores is None:
                        predicted = None
                    else:
                        best = int(scores.argmax())
                        predicted = None if best == len(entities) else entities[best]
                    correct = (predicted is None) if gold is None else (predicted is not None and gold in predicted)
                    if dump is not None:
                        # Xác suất biên từng thực thể = tổng softmax các chỗ nhắc trỏ tới nó (cùng dạng với loss),
                        # để N3 (giải mã cả hội thoại), N5 (bỏ phiếu trắng) và N6 (xếp chồng với LLM) dùng lại.
                        probs: dict[str, float] = {}
                        p_null = None
                        if scores is not None:
                            softmax = torch.softmax(scores, 0).tolist()
                            p_null = softmax[-1]
                            for index, names in enumerate(entities):
                                for name in names:
                                    probs[name] = probs.get(name, 0.0) + softmax[index]
                        dump.append({key: quote[key] for key in ("book", "chapter", "seq", "kind")}
                                    | {"gold": gold, "predicted": predicted, "correct": bool(correct),
                                       "p_null": p_null, "probs": dict(sorted(probs.items(), key=lambda kv: -kv[1])[:8])})
                    key = "null" if gold is None else "named"
                    tally["all"][0] += correct
                    tally["all"][1] += 1
                    tally[key][0] += correct
                    tally[key][1] += 1
                    if gold is not None and not any(gold in e for e in entities):
                        tally["uncovered"] += 1
        return {name: (value[0] / value[1] if isinstance(value, list) and value[1] else value)
                for name, value in tally.items()} | {"n": tally["all"][1]}

    args.out.mkdir(parents=True, exist_ok=True)
    if args.predict_file:
        rows: list = []
        evaluate(load(args.predict_file), rows)
        with (args.out / "predictions.jsonl").open("w", encoding="utf-8") as handle:
            handle.writelines(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        print(f"đã chấm {len(rows)} câu của {args.predict_file} -> {args.out / 'predictions.jsonl'}", flush=True)
        (args.out / "test.json").write_text(json.dumps({"predicted": len(rows)}), encoding="utf-8")
        return 0
    log = (args.out / "train.log").open("a", encoding="utf-8")
    best = -1.0
    phases = [] if args.predict_only else (
        [("học trước", pretrain)] * (args.pretrain_epochs if pretrain else 0) + [("gold", train)] * args.epochs)
    for epoch, (phase, windows) in enumerate(phases):
        encoder.train()
        head.train()
        windows = list(windows)
        random.shuffle(windows)
        started, losses = time.time(), []
        for window in windows:
            results, entities = score_window(window)
            terms = []
            for quote, scores in zip(window["quotes"], results):
                if scores is None:
                    continue
                gold = quote["speaker"]
                if gold is None:
                    positive = torch.tensor([len(entities)], device=device)
                else:
                    positive = torch.tensor([i for i, e in enumerate(entities) if gold in e], device=device,
                                            dtype=torch.long)
                    if positive.numel() == 0:
                        continue  # người nói không nằm trong ứng viên: không có gì để học
                terms.append(torch.logsumexp(scores, 0) - torch.logsumexp(scores[positive], 0))
            if not terms:
                continue
            loss = torch.stack(terms).mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable + list(head.parameters()), 1.0)
            optimizer.step()
            schedule.step()
            losses.append(float(loss))
        # Ghi dự đoán dev + test MỖI epoch (27-09): dev 68 câu không có truyện ngôi thứ nhất, nên chọn checkpoint theo dev
        # từng chọn epoch 3 chưa học "tôi = người kể" (YMP 92,9% -> 59,5%) - so cấu hình phải bằng một quy tắc định
        # trước (epoch cuối), chọn sau trên các tệp này, không theo dev.
        dumps: dict[str, list] = {"dev": [], "test": []}
        scores_dev = evaluate(dev, dumps["dev"])
        if test is dev:  # kiểm chứng chéo: cùng một tập, chấm một lần
            scores_test, dumps["test"] = scores_dev, dumps["dev"]
        else:
            scores_test = evaluate(test, dumps["test"])
        (args.out / "epochs").mkdir(parents=True, exist_ok=True)
        for name, rows in dumps.items():
            with (args.out / "epochs" / f"{epoch + 1}_{name}_predictions.jsonl").open("w", encoding="utf-8") as handle:
                handle.writelines(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        line = (f"epoch {epoch + 1}: loss {sum(losses) / max(1, len(losses)):.4f} | dev {json.dumps(scores_dev)} | "
                f"{time.time() - started:.0f}s | {phase} | test {scores_test['all']:.3f}")
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()
        if args.fold is None and scores_dev["all"] > best:
            best = scores_dev["all"]
            torch.save({"head": head.state_dict()}, args.out / "head.pt")
            encoder.save_pretrained(args.out / "encoder")
    if args.fold is not None:
        # Kiểm chứng chéo: dev chính là test, nên "tốt nhất trên dev" là nhìn trộm - không lưu checkpoint (1,2 GB mỗi lần),
        # kết quả là epoch cuối (epochs/<cuối>_test_predictions.jsonl).
        line = f"TEST (epoch cuối, fold {args.fold}): {json.dumps(scores_test)}"
        print(line, flush=True)
        log.write(line + "\n")
        if args.save_last:  # mô hình để chấm tiếp (vd tự học theo cuốn: chấm các chương không nhãn của truyện bị giữ lại)
            torch.save({"head": head.state_dict()}, args.out / "head.pt")
            encoder.save_pretrained(args.out / "encoder")
        (args.out / "test.json").write_text(json.dumps(scores_test, indent=2), encoding="utf-8")
        return 0
    head.load_state_dict(torch.load(args.out / "head.pt")["head"])
    encoder.load_state_dict(AutoModel.from_pretrained(args.out / "encoder", dtype=torch.float32).state_dict())
    for name, windows in (("dev", dev), ("test", test)):
        predictions: list = []
        result = evaluate(windows, predictions)
        with (args.out / f"{name}_predictions.jsonl").open("w", encoding="utf-8") as handle:
            for row in predictions:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    line = f"TEST (mô hình tốt nhất trên dev): {json.dumps(result)}"
    print(line, flush=True)
    log.write(line + "\n")
    (args.out / "test.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
