"""So các model với một mốc THEO CẶP từng chương - phép so đúng theo docs/LLM_EVAL.md.

    python scripts/model_eval/paired.py --base qwen3:8b D:/Novels/Audiobooks/_model_eval_v2/21-09 \
        D:/Novels/Audiobooks/_model_eval_v2/21-09b D:/Novels/Audiobooks/_model_eval_v2/27-09

Vì sao theo cặp (21-09): cùng một model, độ đúng người nói theo chương chạy 51,5-84,6%, nên chọn chương chi phối
mạnh hơn chọn model và hai trung bình trên hai tập chương khác nhau không nói được gì. Công cụ này đọc mọi
`eval_models.json` dưới các thư mục cho vào (đệ quy), chấm LẠI từng chương đã chạy trọn bằng đáp án chuẩn HIỆN
HÀNH (đáp án có thể đã được sửa sau lượt đo), rồi với mỗi model khác mốc, trên đúng những chương CẢ HAI cùng chạy
trọn: thắng / thua / hoà theo điểm tổng, hiệu trung bình và sai số chuẩn của hiệu (điểm tổng và người nói), và
tổng giây. Một chương đo hai lần (hai thư mục) thì lấy lần mới nhất.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from score_models import GOLD_ROOT, aligned_gold, exit_on_gold_mismatch, read_project, score_rows  # noqa: E402


def collect(roots: list[Path]) -> dict[str, dict[str, dict]]:
    """model -> chương -> lần chạy (lần mới nhất theo thời điểm sửa file project)."""
    found: dict[str, dict[str, dict]] = {}
    for root in roots:
        for summary in sorted(root.rglob("eval_models.json")):
            for entry in json.loads(summary.read_text(encoding="utf-8")):
                if entry.get("known_list", "baseline") != "baseline":
                    continue  # biến thể prompt là một phép thử khác, không phải model khác
                for run in entry.get("runs", []):
                    if not run.get("ok"):
                        continue
                    project = Path(run["project"])
                    database = project / "project.sqlite3"
                    if not database.is_file():
                        continue
                    run = {**run, "mtime": database.stat().st_mtime}
                    chapter = str(run["chapter"])
                    old = found.setdefault(entry["model"], {}).get(chapter)
                    if old is None or run["mtime"] > old["mtime"]:
                        found[entry["model"]][chapter] = run
    return found


def chapter_scores(found: dict[str, dict[str, dict]], gold_dir: Path) -> dict[str, dict[str, dict]]:
    scores: dict[str, dict[str, dict]] = {}
    for model, runs in found.items():
        for chapter, run in runs.items():
            # Gióng đáp án theo chữ của chính project lượt đo này (parser có thể đã tách chương khác lúc đo).
            chapter_gold = aligned_gold(gold_dir, Path(run["project"]), {chapter})
            if not chapter_gold:
                continue
            rows, _meta = read_project(Path(run["project"]), {chapter})
            if not rows:
                continue
            scored = score_rows(chapter_gold, rows)
            scores.setdefault(model, {})[chapter] = {
                "score": scored["score"], "speaker": scored["rates"]["speaker"], "seconds": run.get("seconds", 0.0),
            }
    return scores


def mean_and_error(values: list[float]) -> tuple[float, float]:
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, float("nan")
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return mean, math.sqrt(variance / len(values))


@exit_on_gold_mismatch
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--base", default="qwen3:8b")
    parser.add_argument("--gold", default="throne_of_magical_arcana")
    parser.add_argument("--tie", type=float, default=0.5, help="chênh điểm tổng nhỏ hơn mức này là hoà")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    scores = chapter_scores(collect(args.roots), GOLD_ROOT / args.gold)
    if args.base not in scores:
        raise SystemExit(f"không có lượt đo nào của mốc {args.base} dưới các thư mục đã cho")
    base = scores[args.base]
    report = []
    print(f"mốc {args.base}: {len(base)} chương | hoà khi chênh < {args.tie} điểm")
    print(f"{'model':26} {'chung':>5} {'thắng':>5} {'thua':>4} {'hoà':>3} {'Δđiểm':>7} {'±':>5} {'Δngười nói':>10} {'±':>5} "
          f"{'giây/mốc':>8}")
    for model in sorted(scores, key=lambda name: name != args.base):
        if model == args.base:
            continue
        shared = sorted(set(scores[model]) & set(base))
        if not shared:
            print(f"{model[:26]:26} {0:>5}  (không có chương chung với mốc)")
            continue
        score_diffs = [scores[model][c]["score"] - base[c]["score"] for c in shared]
        speaker_diffs = [scores[model][c]["speaker"] - base[c]["speaker"] for c in shared]
        wins = sum(diff >= args.tie for diff in score_diffs)
        losses = sum(diff <= -args.tie for diff in score_diffs)
        score_mean, score_error = mean_and_error(score_diffs)
        speaker_mean, speaker_error = mean_and_error(speaker_diffs)
        seconds = sum(scores[model][c]["seconds"] for c in shared)
        base_seconds = sum(base[c]["seconds"] for c in shared)
        ratio = seconds / base_seconds if base_seconds else float("nan")
        print(f"{model[:26]:26} {len(shared):>5} {wins:>5} {losses:>4} {len(shared) - wins - losses:>3} "
              f"{score_mean:+7.2f} {score_error:5.2f} {speaker_mean:+10.2f} {speaker_error:5.2f} {ratio:8.2f}")
        report.append({
            "model": model, "base": args.base, "chapters": shared, "wins": wins, "losses": losses,
            "score_diff": score_mean, "score_error": score_error,
            "speaker_diff": speaker_mean, "speaker_error": speaker_error, "seconds_ratio": ratio,
            "per_chapter": {c: {"model": scores[model][c], "base": base[c]} for c in shared},
        })
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
