"""Quét biến thể cho từng điểm [Chọn] của luật Việt hoá từ tiếng Anh (abook/english_vi.py `CHOICES`).

Với mỗi điểm thử mọi biến thể, đếm số dạng có nguồn (tests/english_vi_evidence.py) mà cách đọc của LUẬT (bảng ghi đè tắt đi) trùng một dạng
nguồn, đủ thanh. Trọng số: chủ sách x100, văn bản nhà nước x2, SGK / báo x1, cộng đồng x0. Các điểm ràng buộc nhau nên quét VÉT CẠN chung
theo nhóm (nguyên âm, phụ âm). Hoà điểm thì lấy tổ hợp mà các biến thể đứng đầu danh sách VALUES nhiều nhất (xếp theo lý do ngữ âm / theo
quy ước). Biến thể làm bộ kiểm âm tiết (`vietnamese_syllable.valid_spoken_form`) từ chối thêm từ so với biến thể ít bị từ chối nhất của cùng điểm
(trên dạng nguồn và ~300 từ chạy thử) thì không được chọn, chỉ đếm để biết.

    runtime/.venv/Scripts/python.exe scripts/sweep_english_vi_variants.py

In bảng cho từng điểm (các điểm khác để ở giá trị đã chọn) và bộ giá trị tốt nhất; KHÔNG sửa file nào.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abook import english_vi
from tests import english_vi_evidence as evidence

WEIGHT = {"owner": 100, "official": 2, "textbook": 1, "press": 1, "community": 0}
KINDS = ("owner", "official", "textbook", "press")

# Danh sách giá trị: cái đứng trước thắng khi hoà điểm.
VALUES: dict[str, list] = {
    "schwa": ["ơ", "letter"],
    "ae": ["a", "e"],
    "aa_o": ["ô", "o"],
    "eh": ["e", "ê"],
    "ih": ["i", "ê"],
    "ey_p": ["ê", "e", "a"],
    "ey_k": ["ê", "e", "a"],
    "ey_t": ["ê", "e", "a"],
    "ey_nasal": ["ê", "e", "a"],
    "ay_m": ["ai", "am"],
    "geminate": ["none", "short", "primary", "stressed"],
    "short_silent_e": ["phonemes", "face"],
    "epenthesis": ["ơ", "ờ"],
    "epenthesis_medial": ["ơ", "ờ"],
    "l_coda": ["n", "drop"],
    "il_final": ["coda", "u"],
    "s_coda": ["t", "syllable"],
    "fric_final": ["stop", "syllable"],
    "voiced_final": ["devoice", "syllable"],
    "final_cluster": ["drop", "syllable"],
    "glide_coda": ["drop", "syllable"],
    "th": ["th", "x"],
    "dh": ["d", "đ"],
    "tr": ["tr", "split"],
}
GROUPS = [
    ["schwa", "ae", "aa_o", "eh", "ih", "geminate", "short_silent_e"],
    ["ey_p", "ey_k", "ey_t", "ey_nasal", "ay_m"],
    ["epenthesis", "epenthesis_medial", "l_coda", "il_final", "s_coda", "fric_final", "voiced_final", "final_cluster", "glide_coda", "th",
     "dh", "tr"],
]
TRIAL = json.loads((ROOT / "tests" / "fixtures" / "english_vi" / "trial.json").read_text(encoding="utf-8"))["tokens"]


def _apply(choices: dict, validate: bool) -> None:
    english_vi.CHOICES.update(choices)
    english_vi._CHECK_SYLLABLES = validate


def matches(token: str, sources: tuple[str, ...]) -> bool:
    reading = english_vi.vietnamized_english(token, overrides=False)  # đo LUẬT, không đo bảng ghi đè
    return reading is not None and reading.casefold() in {source.casefold() for source in sources}


def score(choices: dict) -> tuple[int, dict[str, int]]:
    """(điểm có trọng số, số dạng khớp theo loại)."""
    _apply(choices, True)
    counts = {kind: 0 for kind in WEIGHT}
    for token, sources, kind in evidence.SOURCED:
        counts[kind] += matches(token, sources)
    return sum(WEIGHT[kind] * count for kind, count in counts.items()), counts


def rejected(choices: dict) -> int:
    """Số từ (nguồn + chạy thử) mà luật đọc được khi tắt bộ kiểm âm tiết nhưng bộ kiểm từ chối."""
    total = 0
    for token in [token for token, _sources, _kind in evidence.SOURCED] + TRIAL:
        _apply(choices, False)
        raw = english_vi.vietnamized_english(token, overrides=False)
        _apply(choices, True)
        if raw is not None and english_vi.vietnamized_english(token, overrides=False) is None:
            total += 1
    return total


def selectable(base: dict) -> dict[str, set]:
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
    for _round in range(2):  # hai vòng: nhóm sau có thể đổi điểm tốt nhất của nhóm trước
        for group in GROUPS:
            current = best_for_group(current, group, allowed)
    return current


def table(final: dict, allowed: dict[str, set]) -> None:
    print(f"{'điểm':15} {'biến thể':10} {'owner':>5} {'NN':>3} {'SGK':>4} {'báo':>4} {'điểm':>6} {'bị kiểm từ chối':>16}")
    for key, values in VALUES.items():
        for value in values:
            trial = {**final, key: value}
            weighted, counts = score(trial)
            mark = " <== chọn" if final[key] == value else ""
            note = "" if value in allowed[key] else "  (chỉ đếm: bộ kiểm âm tiết từ chối thêm từ)"
            print(f"{key:15} {value!s:10} {counts['owner']:5d} {counts['official']:3d} {counts['textbook']:4d} {counts['press']:4d} "
                  f"{weighted:6d} {rejected(trial):16d}{mark}{note}")
        print()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    start = dict(english_vi.CHOICES)
    allowed = selectable(start)
    final = sweep(start)
    print("bộ giá trị đã chọn:", {key: final[key] for key in VALUES})
    print("khác giá trị đang cài:", {key: (start[key], final[key]) for key in VALUES if start[key] != final[key]} or "không")
    weighted, counts = score(final)
    total = {kind: sum(1 for _t, _s, k in evidence.SOURCED if k == kind) for kind in WEIGHT}
    print("khớp (đủ thanh):", ", ".join(f"{kind} {counts[kind]}/{total[kind]}" for kind in WEIGHT), f"; điểm {weighted}\n")
    table(final, allowed)
    _apply(final, True)
    for token, sources, kind in evidence.SOURCED:
        if kind == "owner":
            got = english_vi.vietnamized_english(token, overrides=False)
            print(f"luật (không ghi đè) {token} -> {got}  {'đúng' if matches(token, sources) else 'khác ' + ' / '.join(sources)}")
    _apply(start, True)


if __name__ == "__main__":
    main()
