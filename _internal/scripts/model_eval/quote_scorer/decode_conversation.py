"""N3 - giải mã CẢ HỘI THOẠI: điểm từng câu của bộ chấm + luật lượt lời, thay vì chọn từng câu một mình.

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/decode_conversation.py \
        --runs D:/Novels/LLM_Train/runs/scorer_vi_base [D:/.../scorer_vi_base_s7 ...]

Bộ chấm chấm mỗi câu thoại độc lập (dù cửa sổ có thấy các câu quanh nó). Hội thoại có cấu trúc: câu cùng paragraph gần
như luôn cùng người; hai dòng thoại liền nhau khác paragraph thường là hai người thay phiên (A-B-A). Đo trên gold train
27-09: cùng paragraph -> 89% cùng người câu trước; xuống dòng liền -> 30% cùng người câu trước, 68% cùng người câu t-2.
(Truyện dịch tách lời một người thành nhiều dòng nhiều hơn tiểu thuyết Anh - luật yếu hơn, nên phải ĐO chứ không áp.)

Mô hình: chuỗi bậc hai trên các câu thoại (D) của một chương. Mỗi câu có nhãn = một thực thể trong xác suất biên của
bộ chấm hoặc "không ai". Điểm một chuỗi nhãn = Σ log p_bộ chấm(nhãn) + λ Σ log P(mẫu | quan hệ), trong đó quan hệ giữa
câu t-1 và t ∈ {cùng paragraph, xuống dòng liền, có lời kể xen giữa} và mẫu ∈ {cùng người câu t-1, cùng người câu t-2
(khác t-1), người khác}; P(mẫu | quan hệ) đếm trên GOLD TRAIN (không dùng dự đoán). "Không ai" không bao giờ "cùng
người" (hai NPC khác nhau). λ chọn trên dev, rồi báo test với McNemar so với chọn độc lập.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from build_vi import GOLD_ROOT, entity_of, gold_quotes, split_of  # noqa: E402
from compare_predictions import ensemble, load_rows, mcnemar  # noqa: E402

REPLAY = Path("D:/Novels/Audiobooks/_model_eval_gold/replay_21_09_base")
RELATIONS = ("cùng paragraph", "xuống dòng liền", "lời kể xen giữa")
PATTERNS = ("như t-1", "như t-2", "người khác")


def chapter_structure() -> dict[tuple[str, str], list[tuple[int, str, int]]]:
    """(truyện, chương) -> [(seq, kind, paragraph)] của mọi chương có gold."""
    out = {}
    for database in sorted(REPLAY.rglob("project.sqlite3")):
        book = database.relative_to(REPLAY).parts[0]
        connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        for chapter_id, title in connection.execute("SELECT id, title FROM chapters"):
            if (GOLD_ROOT / book / f"{title}.txt").is_file():
                out[(book, str(title))] = [(int(s), str(k), int(p)) for s, k, p in connection.execute(
                    "SELECT seq, kind, paragraph_index FROM segments WHERE chapter_id = ? ORDER BY seq", (chapter_id,))]
    return out


def dialogue_chain(segments: list[tuple[int, str, int]], quote_seqs: set[int]) -> list[tuple[int, str | None]]:
    """[(seq, quan hệ với câu thoại trước)] theo thứ tự; quan hệ None ở câu đầu chương."""
    chain, previous, narration = [], None, False
    for seq, kind, paragraph in segments:
        if seq in quote_seqs:
            if previous is None:
                relation = None
            elif paragraph == previous[1]:
                relation = RELATIONS[0]
            else:
                relation = RELATIONS[2] if narration else RELATIONS[1]
            chain.append((seq, relation))
            previous, narration = (seq, paragraph), False
        elif kind != "dialogue":
            narration = True
    return chain


def pattern(label, previous, before) -> str:
    if label is not None and label == previous:
        return PATTERNS[0]
    if label is not None and label == before:
        return PATTERNS[1]
    return PATTERNS[2]


def transition_table(structure: dict) -> dict[str, dict[str, float]]:
    counts: dict[str, Counter] = defaultdict(Counter)
    for (book, chapter), segments in structure.items():
        if split_of(book, chapter) != "train":
            continue
        gold = {seq: entity_of(label) for seq, (kind, label) in gold_quotes(GOLD_ROOT / book / f"{chapter}.txt").items()
                if kind == "D"}
        chain = dialogue_chain(segments, set(gold))
        for index, (seq, relation) in enumerate(chain):
            if relation is None:
                continue
            previous = gold[chain[index - 1][0]]
            before = gold[chain[index - 2][0]] if index >= 2 else None
            counts[relation][pattern(gold[seq], previous, before)] += 1
    return {relation: {p: (counts[relation][p] + 1) / (sum(counts[relation].values()) + len(PATTERNS))
                       for p in PATTERNS} for relation in RELATIONS}


def fit_temperature(rows: dict) -> float:
    """Nhiệt độ T làm log-likelihood của đáp án trên DEV lớn nhất: bộ chấm học tới loss ~0,03 nên xác suất ra gần
    0/1 (0,99999996) - điểm chuyển tiếp log 0,26 = -1,3 không bao giờ thắng được log 1e-8 = -18. p^(1/T) chuẩn hoá lại."""
    def nll(temperature: float) -> float:
        total = 0.0
        for row in rows.values():
            if row.get("p_null") is None:
                continue
            options = {**row["probs"], None: row["p_null"]}
            if row["gold"] not in options:
                continue
            scaled = {k: math.log(max(1e-12, v)) / temperature for k, v in options.items()}
            top = max(scaled.values())
            total -= scaled[row["gold"]] - top - math.log(sum(math.exp(v - top) for v in scaled.values()))
        return total
    return min((1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32), key=nll)


def decode(chain: list[tuple[int, str | None]], rows: dict[int, dict], table: dict, weight: float,
           temperature: float = 1.0) -> dict[int, object]:
    """Viterbi bậc hai: trạng thái = (nhãn câu t-1, nhãn câu t)."""
    options = []
    for seq, _ in chain:
        row = rows[seq]
        choices = {name: p for name, p in row["probs"].items()}
        choices[None] = row["p_null"]
        options.append({label: math.log(max(1e-12, p)) / temperature for label, p in choices.items()})
    if not options:
        return {}
    # best[(a, b)] = (điểm, đường đi) với a = nhãn câu t-1, b = nhãn câu t
    best = {("<s>", label): (score, [label]) for label, score in options[0].items()}
    for index in range(1, len(chain)):
        relation = chain[index][1]
        new: dict = {}
        for (before, previous), (score, path) in best.items():
            for label, emission in options[index].items():
                transition = math.log(table[relation][pattern(label, previous, None if before == "<s>" else before)])
                candidate = score + emission + weight * transition
                key = (previous, label)
                if key not in new or candidate > new[key][0]:
                    new[key] = (candidate, path + [label])
        best = new
    path = max(best.values(), key=lambda value: value[0])[1]
    return {seq: label for (seq, _), label in zip(chain, path)}


def run(rows: dict, structure: dict, table: dict, weight: float, temperature: float = 1.0) -> dict:
    """Dự đoán mới cho mọi câu: câu D theo chuỗi, câu còn lại (T, câu thiếu xác suất) giữ nguyên."""
    out = {}
    by_chapter: dict = defaultdict(dict)
    for key, row in rows.items():
        if row.get("p_null") is not None and row["kind"] == "D":
            by_chapter[(key[0], key[1])][key[2]] = row
    for (book, chapter), chapter_rows in by_chapter.items():
        chain = dialogue_chain(structure[(book, chapter)], set(chapter_rows))
        for seq, label in decode(chain, chapter_rows, table, weight, temperature).items():
            gold = chapter_rows[seq]["gold"]
            out[(book, chapter, seq)] = {**chapter_rows[seq], "correct": (label is None) if gold is None else label == gold}
    return {key: out.get(key, row) for key, row in rows.items()}


def accuracy(rows: dict) -> float:
    return sum(row["correct"] for row in rows.values()) / max(1, len(rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=Path, nargs="+", required=True, help="thư mục lần chạy (nhiều seed -> ensemble)")
    parser.add_argument("--weights", type=float, nargs="*", default=[0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0])
    args = parser.parse_args()

    structure = chapter_structure()
    table = transition_table(structure)
    print("P(mẫu | quan hệ) trên gold train:")
    for relation in RELATIONS:
        print(f"  {relation:18s} " + "  ".join(f"{p} {table[relation][p]:.2f}" for p in PATTERNS))
    splits = {}
    for split in ("dev", "test"):
        runs = [load_rows(path, split) for path in args.runs]
        splits[split] = ensemble(runs) if len(runs) > 1 else runs[0]
    temperature = fit_temperature(splits["dev"])
    print(f"\nnhiệt độ khớp trên dev (NLL nhỏ nhất): T = {temperature}")
    independent = {split: run(rows, structure, table, 0.0) for split, rows in splits.items()}
    print(f"\nđộc lập (λ=0): dev {accuracy(independent['dev']):.1%}  test {accuracy(independent['test']):.1%}")
    scores = {}
    for weight in args.weights:
        dev = run(splits["dev"], structure, table, weight, temperature)
        scores[weight] = accuracy(dev)
        print(f"  λ={weight:<5} dev {scores[weight]:.1%}")
    chosen = max(sorted(scores), key=lambda w: (scores[w], -w))  # hoà thì chọn λ nhỏ hơn
    test = run(splits["test"], structure, table, chosen, temperature)
    base = independent["test"]
    only_base = sum(base[k]["correct"] and not test[k]["correct"] for k in base)
    only_new = sum(test[k]["correct"] and not base[k]["correct"] for k in base)
    print(f"\nλ chọn trên dev = {chosen}: test {accuracy(test):.1%} vs độc lập {accuracy(base):.1%} "
          f"(chỉ độc lập đúng {only_base}, chỉ N3 đúng {only_new}, p McNemar {mcnemar(only_base, only_new):.3f})")
    for weight in args.weights:
        print(f"  (tham khảo, không dùng để chọn) λ={weight:<5} test "
              f"{accuracy(run(splits['test'], structure, table, weight, temperature)):.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
