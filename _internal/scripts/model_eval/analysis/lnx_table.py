"""Bảng so trên bộ LN GỘP (6 chương 28-09 + các chương mở rộng 29-09) và phép so cặp có khoảng tin cậy.

    python lnx_table.py v3=28-09-ln-lora3,29-09-lnx-lora3 v5=28-09-ln-lora5,29-09-lnx-lora5 [--pair v5 v3]

Mỗi đối số: <nhãn>=<tiền tố bộ 28-09>,<tiền tố bộ mở rộng> (bỏ trống một vế được: "v5=,29-09-lnx-lora5"). Thước:
F1 giọng (B-cubed, thước chính - voice_identity), người nói chặt (tín dụng đủ), cảm xúc (trong tập chấp nhận). `--pair A B`:
hiệu A - B trên đúng các câu CẢ HAI có, khoảng tin cậy 95% bằng bootstrap theo CHƯƠNG (câu trong một chương không độc lập -
lấy lại cả chương), và số chương A hơn / thua B.
"""
from __future__ import annotations

import contextlib
import io
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ln_table import EVAL, chapter_points  # noqa: E402
from voice_identity import bcubed  # noqa: E402

BASE = [("tcf", "two_childhood_friends", "042"), ("nise", "nise_seiken", "132"), ("hdst", "huong_dan_sinh_ton", "062"),
        ("yamiyo", "yamiyo_no_hotaru", "141"), ("nageki", "nageki_no_bourei", "65"), ("lu", "love_unseen", "07")]
EXT = [("yamiyo225", "yamiyo_no_hotaru", "225"), ("nageki62", "nageki_no_bourei", "62"),
       ("tcf060", "two_childhood_friends", "060"), ("nise086", "nise_seiken", "086"),
       ("hdst130", "huong_dan_sinh_ton", "130"), ("lu10", "love_unseen", "10")]


def collect(spec: str) -> dict[str, tuple]:
    """nhãn=base,ext -> {chương: (model, points, strict, emotion, lines)} cho các chương đã đo xong."""
    base, _, ext = spec.partition("=")[2].partition(",")
    out = {}
    for prefix, chapters in ((base, BASE), (ext, EXT)):
        if not prefix:
            continue
        for name, gold_dir, chapter in chapters:
            with contextlib.redirect_stdout(io.StringIO()):
                found = chapter_points(EVAL / f"{prefix}-{name}", gold_dir, chapter)
            if found and found[1]:
                out[name] = found
    return out


BY_BOOK = "--by-book" in sys.argv  # gộp theo CUỐN: cùng người ở hai chương một truyện là một người, cùng nhãn là một giọng


def _scope(name: str) -> str:
    """Chương -> phạm vi gộp: tên chương (mặc định, trung bình từng chương) hay tên truyện ("nageki62" -> "nageki")."""
    return name.rstrip("0123456789") if BY_BOOK else name


def totals(data: dict[str, tuple], names: list[str]) -> tuple[float, float, float, int]:
    points, strict, spoken, emotion, lines = [], 0, 0, 0, 0
    for name in names:
        _model, chapter_points_, chapter_strict, chapter_emotion, chapter_lines = data[name]
        points += [((_scope(name), person), (_scope(name), voice)) for person, voice in chapter_points_]
        strict += chapter_strict
        spoken += len(chapter_points_)
        emotion += chapter_emotion
        lines += chapter_lines
    return (bcubed(points)[2] if points else 0.0, strict / spoken if spoken else 0.0,
            emotion / lines if lines else 0.0, spoken)


def main(argv: list[str]) -> int:
    argv = [arg for arg in argv if arg != "--by-book"]
    pair = None
    if "--pair" in argv:
        index = argv.index("--pair")
        pair = argv[index + 1], argv[index + 2]
        argv = argv[:index] + argv[index + 3:]
    runs = {spec.partition("=")[0]: collect(spec) for spec in argv}
    order = [name for name, _, _ in BASE + EXT]
    print("| lượt | " + " | ".join(order) + " | GỘP F1 giọng | người nói chặt | cảm xúc |")
    print("|" + "---|" * (len(order) + 4))
    for label, data in runs.items():
        cells = [f"{bcubed(data[name][1])[2]:.1%}" if name in data else "-" for name in order]
        f1, strict, emotion, spoken = totals(data, [name for name in order if name in data])
        print(f"| {label} | " + " | ".join(cells) + f" | {f1:.1%} ({spoken} câu, {len(data)} chương) | {strict:.1%} | {emotion:.1%} |")
    if pair:
        a, b = runs[pair[0]], runs[pair[1]]
        shared = [name for name in order if name in a and name in b]
        if not shared:
            print("không có chương chung")
            return 1
        rng = random.Random(29092026)
        observed = [x - y for x, y in zip(totals(a, shared)[:3], totals(b, shared)[:3])]
        draws = [[], [], []]
        for _ in range(2000):
            sample = [rng.choice(shared) for _ in shared]
            # nhãn chương trùng khi lấy lại có hoàn lại: đổi tên để B-cubed coi là chương riêng
            renamed_a = {f"{name}#{i}": a[name] for i, name in enumerate(sample)}
            renamed_b = {f"{name}#{i}": b[name] for i, name in enumerate(sample)}
            ta, tb = totals(renamed_a, list(renamed_a)), totals(renamed_b, list(renamed_b))
            for k in range(3):
                draws[k].append(ta[k] - tb[k])
        wins = sum(bcubed(a[name][1])[2] > bcubed(b[name][1])[2] for name in shared)
        losses = sum(bcubed(a[name][1])[2] < bcubed(b[name][1])[2] for name in shared)
        print(f"\n{pair[0]} - {pair[1]} trên {len(shared)} chương chung (bootstrap theo chương, 2000 lần, KTC 95%):")
        for k, title in enumerate(("F1 giọng", "người nói chặt", "cảm xúc")):
            values = sorted(draws[k])
            low, high = values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]
            print(f"  {title}: {observed[k]:+.1%} [{low:+.1%}, {high:+.1%}]")
        print(f"  F1 giọng từng chương: hơn {wins}, thua {losses}, hoà {len(shared) - wins - losses}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
