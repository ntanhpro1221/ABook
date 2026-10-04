"""Quét biến thể cho từng điểm [Chọn] / để ngỏ / analogy của luật đọc romaji Nhật và RR Hàn (abook/romanization.py `CHOICES`).

Với mỗi điểm thử mọi biến thể hợp lý, đếm số dạng có nguồn (tests/romanization_evidence.py) mà cách đọc trùng một dạng nguồn. Trọng số: ca của chủ sách
x100, Bộ Ngoại giao x2, sách giáo khoa x1, cộng đồng x0. Các điểm ràng buộc nhau nên quét VÉT CẠN chung theo nhóm (nhóm Nhật và nhóm Hàn, hai nhóm không
dùng chung giá trị nào). Hoà điểm thì lấy tổ hợp mà các biến thể đứng đầu danh sách VALUES nhiều nhất (xếp theo lý do ngữ âm). Biến thể làm bộ kiểm âm
tiết (`vietnamese_syllable.valid_spoken_form`) từ chối thêm tên so với biến thể ít bị từ chối nhất của cùng điểm (kể cả tên ngoài nguồn: ca edge và tên thật) thì
không bao giờ được chọn, chỉ đếm để biết.

Không quét (chủ sách 04-10 đã chốt, cố định): u Nhật -> u ở mọi chỗ, e Nhật -> e, ei -> ây, ou viết ra -> âu, y + nguyên âm -> gi, tsu -> xu, fu -> phu, g + i -> ghi, ee / ii / aa -> e / i / a, o không phụ âm đầu -> o, bật hơi Hàn -> thường, s Hàn -> x, j Hàn -> gi, eo, wo, hậu tố nối
gạch. Cuối bảng kiểm các luật ấy còn đứng. (ya / yo của tiếng Hàn dùng CHOICES["y"] nhưng không có ca nguồn nào, nên cũng không quét.)

    runtime/.venv/Scripts/python.exe scripts/sweep_romanization_variants.py

In bảng cho từng điểm (các điểm khác để ở giá trị đã chọn) và bộ giá trị tốt nhất; KHÔNG sửa file nào.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abook import romanization  # noqa: E402
from tests import romanization_evidence as evidence  # noqa: E402

WEIGHT = {"owner": 100, "official": 2, "textbook": 1, "community": 0}

# Danh sách giá trị: cái đứng trước thắng khi hoà điểm (lý do ngữ âm: x cho /s/, i-a cho ya, gh cho g trước i...).
VALUES: dict[str, list] = {
    "s": ["x", "s"],
    "sh": ["s", "x"],
    "k": ["orth", "k_o", "k_all"],
    "kya": ["ki_a", "kia"],
    "ss": ["t", "c"],
    "ko_g": ["k", "g"],
    "ko_d": ["t", "đ"],
    "ko_b": ["p", "b"],
    "ko_s": ["x", "s"],
    "ko_ye": ["ê", "iê"],
    "ko_tense": ["plain", "aspirated"],
    "ko_a_short": [True, False],
}
GROUPS = [
    ["s", "sh", "k", "kya", "ss"],
    ["ko_g", "ko_d", "ko_b", "ko_s", "ko_ye", "ko_tense", "ko_a_short"],
]
# Luật cố định của chủ sách (không quét): (chữ, gốc, cách đọc phải ra). Kiểm ở cuối để biết kết quả quét không phá chúng.
OWNER_RULES = [
    ("Haruto-kun", "ja", "Ha-ru-tô-cun"), ("Fukushima", "ja", "Phu-cu-si-ma"), ("Suzu", "ja", "Xu-du"), ("Gugu", "ja", "Gu-gu"),
    ("Tsuru", "ja", "Chu-ru"), ("Kuro", "ja", "Cu-rô"),
    ("Yamato", "ja", "Gia-ma-tô"), ("Ayaka", "ja", "A-gia-ca"), ("Rei", "ja", "Rây"), ("sensei", "ja", "xen-xây"), ("Hajime", "ja", "Ha-gi-me"),
    ("Kenji", "ja", "Ken-gi"), ("Yuki", "ja", "Giu-ki"), ("Kyoko", "ja", "Ki-ô-cô"), ("Kyouko", "ja", "Ki-âu-cô"), ("Ryouma", "ja", "Ri-âu-ma"),
    # lần 4 (04-10)
    ("Onee-san", "ja", "O-ne-xan"), ("Onii-chan", "ja", "O-ni-chan"), ("Hiiragi", "ja", "Hi-ra-ghi"), ("Inoue", "ja", "I-nâu-e"), ("Tsubasa", "ja", "Xu-ba-xa"),
    ("Ryuu", "ja", "Ri-u"), ("Osaka", "ja", "O-xa-ca"), ("Aoi", "ja", "A-o-i"), ("Nao", "ja", "Nao"), ("Onigiri", "ja", "O-ni-gi-ri"),
    ("Kang", "ko", "Cang"), ("Taehyun", "ko", "Te-hi-un"), ("Choi", "ko", "Choi"), ("Yoon", "ko", "Giun"), ("Hyung", "ko", "Hi-ung"),
    ("Seojun", "ko", "Xeo-giun"), ("Park", "ko", "Pắc"), ("Jeong", "ko", "Gie-ong"), ("Won", "ko", "Guôn"),
]


def _edge_and_names() -> list[tuple[str, str | None]]:
    spec = importlib.util.spec_from_file_location("build_romanization_fixture", ROOT / "scripts" / "build_romanization_fixture.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.EDGE) + module._names()


EXTRA = _edge_and_names()


def _apply(choices: dict, validate: bool) -> None:
    romanization.CHOICES.update(choices)
    romanization._CHECK_SYLLABLES = validate


def score(choices: dict) -> tuple[int, int, int, int]:
    """(điểm có trọng số, số dạng khớp của Bộ Ngoại giao, của SGK, của chủ sách)."""
    _apply(choices, True)
    counts = {"owner": 0, "official": 0, "textbook": 0}
    for token, origin, sources, kind in evidence.SOURCED:
        reading = romanization.romanized_reading(token, origin)
        if kind in counts and reading is not None and reading.casefold() in {source.casefold() for source in sources}:
            counts[kind] += 1
    weighted = sum(WEIGHT[kind] * count for kind, count in counts.items())
    return weighted, counts["official"], counts["textbook"], counts["owner"]


def rejected(choices: dict) -> int:
    """Số tên (nguồn + edge + tên thật) mà luật tách được nhưng bộ kiểm âm tiết từ chối."""
    tokens = [(token, origin) for token, origin, _sources, _kind in evidence.SOURCED] + EXTRA
    total = 0
    for token, origin in tokens:
        _apply(choices, False)
        raw = romanization.romanized_reading(token, origin)
        _apply(choices, True)
        if raw is not None and romanization.romanized_reading(token, origin) is None:
            total += 1
    return total


def selectable(base: dict) -> dict[str, set]:
    """Với mỗi điểm, các giá trị mà bộ kiểm âm tiết không từ chối nhiều hơn giá trị ít bị từ chối nhất."""
    out = {}
    for key, values in VALUES.items():
        counts = {value: rejected({**base, key: value}) for value in values}
        out[key] = {value for value, count in counts.items() if count == min(counts.values())}
    return out


def best_for_group(base: dict, group: list[str], allowed: dict[str, set]) -> dict:
    best, best_key = dict(base), None
    pools = [[value for value in VALUES[key] if value in allowed[key]] for key in group]
    for combo in itertools.product(*pools):
        trial = {**base, **dict(zip(group, combo))}
        weighted = score(trial)[0]
        preference = sum(VALUES[key].index(value) for key, value in zip(group, combo))
        key_tuple = (-weighted, preference)
        if best_key is None or key_tuple < best_key:
            best, best_key = trial, key_tuple
    return best


def sweep(start: dict) -> dict:
    current = dict(start)
    allowed = selectable(current)
    for group in GROUPS:
        current = best_for_group(current, group, allowed)
    return current


def table(final: dict, allowed: dict[str, set]) -> None:
    print(f"{'điểm':12} {'biến thể':10} {'BNG':>4} {'SGK':>4} {'owner':>5} {'điểm':>6} {'bị kiểm từ chối':>16}")
    for key, values in VALUES.items():
        for value in values:
            trial = {**final, key: value}
            weighted, official, textbook, owner = score(trial)
            mark = " <== chọn" if final[key] == value else ""
            note = "" if value in allowed[key] else "  (chỉ đếm: bộ kiểm âm tiết từ chối thêm tên)"
            print(f"{key:12} {str(value):10} {official:4d} {textbook:4d} {owner:5d} {weighted:6d} {rejected(trial):16d}{mark}{note}")
        print()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    start = dict(romanization.CHOICES)
    allowed = selectable(start)
    final = sweep(start)
    print("bộ giá trị đã chọn:", final)
    total = score(final)
    sourced = len(evidence.SOURCED)
    print(f"khớp: Bộ Ngoại giao {total[1]}, SGK {total[2]}, chủ sách {total[3]}, cộng {total[1] + total[2] + total[3]} / {sourced} dạng; điểm {total[0]}\n")
    table(final, allowed)
    _apply(final, True)
    for token, origin, want in OWNER_RULES:
        got = romanization.romanized_reading(token, origin)
        print(f"luật chủ sách {token} -> {got}  {'đúng' if got == want else 'SAI, phải là ' + want}")


if __name__ == "__main__":
    main()
