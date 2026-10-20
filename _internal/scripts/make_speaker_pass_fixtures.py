"""Dựng tests/fixtures/speaker_pass/*.json - MỘT LẦN, từ mã đo của B41 (D:/Novels/LLM_Train/b38; chỉ đọc).

    RUN_PY scripts/make_speaker_pass_fixtures.py

Mã đo (run_block_eval.run_piece nhánh pq + build_block + prompts) là NGUỒN SỰ THẬT của đề gửi model người nói; `abook/speaker_pass.py`
chép nó. Fixture ghi lại đề mã đo sinh ra để test so từng byte:
- `synthetic_*.json`: truyện TỰ VIẾT (bịa, an toàn cho repo công khai). Có cả đề đầy đủ (bộ đếm ký tự/3 - test luôn chạy được)
  lẫn băm (bộ đếm tokenizer thật - test bỏ qua nếu máy không có tokenizer).
- `real_*.json`: chương thật của dự án đo b9lps1234 / nhãn thật của b41s1234. CHỈ cấu trúc + băm sha256 từng đề (không chép chữ
  truyện); test đọc văn bản và nhãn từ dự án ấy lúc chạy và bỏ qua (có lý do) nếu máy không có.

Nhãn model trong lượt đo = nhãn đã ghi trong dự án b41s1234 (`NPC_LOCAL::x` -> `NPC_LOCAL:x` như model viết). Đề của mỗi câu phụ thuộc
nhãn các câu trước, nên mã đo và app phải được cho CÙNG chuỗi nhãn: đó là điều fixture kiểm.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from pathlib import Path

LLM = Path("D:/Novels/LLM_Train")
sys.path.insert(0, str(LLM / "b38"))
import run_pq_modelkind as M  # noqa: E402  (nạp run_block_eval, build_block, prompts, score_bd)

RB, BB = M.RB, M.BB
OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "speaker_pass"
EVAL = Path(RB.EVAL)

# (ngắn, chương) của các chương thật được chọn: truyện khác nhau, có NPC_LOCAL / nội tâm / ngôi thứ nhất / chương dài.
REAL = [("villain", "22"), ("rk", "014"), ("sm", "195"), ("eroge", "003")]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CharCounter:
    """Bộ đếm không cần tokenizer (ký tự / 3): test luôn chạy được. Cùng công thức với fallback của TokenCounter mã đo."""

    kind = "chars/3"

    @staticmethod
    def count(system: str, user: str) -> int:
        return math.ceil(len(BB._template(system, user)) / 3)


class Recorder:
    """Thay `Model` của mã đo: ghi lại từng đề + câu đích, trả nhãn đã cho theo seq của câu đích."""

    def __init__(self, labels: dict[int, str]) -> None:
        self.labels, self.users, self.targets = labels, [], []
        self._target = None
        self._piece = None
        original = BB.window_rows

        def window_rows(piece, start, end, arm, target=None, stage=0):
            if arm == "pq" and target is not None:
                self._target = piece[target].seq
            return original(piece, start, end, arm, target, stage)

        BB.window_rows = window_rows
        self._restore = lambda: setattr(BB, "window_rows", original)

    def ask_pq(self, user: str):
        self.users.append(user)
        self.targets.append(self._target)
        return self.labels[self._target], 0

    def close(self) -> None:
        self._restore()


def run_reference(piece, labels: dict[int, str], counter) -> dict:
    """Chạy run_piece của mã đo trên `piece` (Seg chưa nhãn) với model giả trả `labels`; trả đề + kết quả."""
    recorder = Recorder(labels)
    try:
        info = RB.run_piece(piece, "pq", recorder, counter)
    finally:
        recorder.close()
    return {"users": recorder.users, "targets": recorder.targets, "info": info,
            "final": {s.seq: s.speaker for s in piece if s.spoken}}


# --------------------------------------------------------------------------------------------------------------------
# Truyện tự viết
# --------------------------------------------------------------------------------------------------------------------
TITLE = "Chương 1: Buổi sáng ở bến xe"
NARRATOR = "Minh"
STORY_A = [
    ("narration", "Sáng sớm, bến xe nhỏ ở thị trấn vẫn còn ngái ngủ."),
    ("narration", "Tôi kéo vali qua cổng, tay kia cầm chiếc vé nhàu nát."),
    ("dialogue", "“Chuyến đi Hạ Long mấy giờ thì chạy vậy cô?”", "Minh"),
    ("narration", "Người bán vé ngẩng lên khỏi tờ báo."),
    ("dialogue", "“Bảy giờ mười lăm. Cậu còn hai mươi phút.”", "NPC_LOCAL:người bán vé"),
    ("narration", "Tôi gật đầu rồi ngồi xuống chiếc ghế dài. Linh đã ngồi sẵn ở đó từ lúc nào."),
    ("dialogue", "“Anh đến muộn nữa là em đi trước đấy.”", "Linh"),
    ("dialogue", "“Xin lỗi, tối qua anh thức khuya xếp đồ.”", "Minh"),
    ("narration", "Linh bật cười, đưa cho tôi một chiếc bánh mì còn ấm."),
    ("thought", "‘Cô ấy lúc nào cũng nhớ mình chưa ăn sáng.’", "Minh"),
    ("narration", "Một bà cụ chống gậy bước lại gần, nhìn chúng tôi chăm chú."),
    ("dialogue", "“Hai đứa đi xa hả? Cho bà nhờ gửi bọc này cho thằng cháu ở bến bên kia.”", "NPC_LOCAL:bà cụ"),
    ("dialogue", "“Dạ được ạ, bà ghi tên cháu giúp con.”", "Linh"),
    ("narration", "Bà cụ lúi húi lấy ra một mẩu giấy, run run viết."),
    ("narration", "Tiếng loa phát thanh vang lên, báo xe sắp vào bến."),
    ("narration", "Quân từ phía sau chạy tới, thở không ra hơi."),
    ("dialogue", "“Chờ tôi với! Tôi suýt nữa thì lỡ chuyến.”", "Quân"),
    ("dialogue", "“Cậu cũng đi chuyến này à?”", "Linh"),
    ("dialogue", "“Ừ, công ty đổi lịch đột xuất.”", "Quân"),
    ("narration", "Chiếc xe khách cũ kỹ rú lên rồi từ từ dừng trước mặt chúng tôi."),
    ("narration", "Phụ xe nhảy xuống, mở cốp và bắt đầu xếp hành lý."),
    ("dialogue", "“Ai lên trước thì chọn ghế trước nhé!”", "NPC_LOCAL:phụ xe"),
    ("narration", "Quân là người đầu tiên chen lên."),
    ("thought", "‘Thằng này vẫn y như hồi học chung.’", "Minh"),
    ("dialogue", "“Này, anh đi chậm thôi, kẻo đè lên hành lý của người ta.”", "Linh"),
    ("narration", "Tôi đỡ bà cụ lên bậc thang, gửi bọc đồ cho phụ xe."),
    ("dialogue", "“Cảm ơn con, trời phù hộ con.”", "NPC_LOCAL:bà cụ"),
    ("narration", "Xe lăn bánh ra khỏi bến lúc bảy giờ mười sáu phút."),
    ("narration", "Ngoài cửa sổ, sương còn phủ trắng những ruộng lúa."),
    ("dialogue", "“Anh nghĩ chuyến này mình sẽ gặp được chị ấy không?”", "Linh"),
    ("dialogue", "“Anh không biết. Nhưng mình phải thử.”", "Minh"),
    ("narration", "Linh im lặng một lúc lâu, rồi tựa đầu vào vai tôi."),
    ("thought", "‘Mong là lần này mọi chuyện sẽ khác.’", "UNKNOWN"),
    ("narration", "Phía cuối xe, một ai đó bắt đầu ngân nga một bài hát cũ."),
    ("dialogue", "“Bài này hay quá, ai hát vậy nhỉ?”", "Quân"),
    ("narration", "Không ai trả lời."),
    ("narration", "Bánh xe lăn đều trên mặt đường, và buổi sáng cứ thế trôi đi."),
    ("dialogue", "“Dậy đi, tới bến nghỉ rồi.”", "NPC_LOCAL:phụ xe"),
    ("narration", "Tôi mở mắt, thấy nắng đã lên cao."),
    ("narration", "Chúng tôi xuống xe, vươn vai giữa tiếng rao bán nước mía."),
]


def story_b() -> list[tuple]:
    """Chương bịa để ép MỌI nhánh cắt khối: bớt câu cuối (đ.k. 4), cắt xem_truoc (mức 1), cắt đoạn kể (mức 2), bỏ khối.
    Đoạn dài là {"rep": [đơn vị, số lần]} cho gọn (test bung ra)."""

    def rep(unit: str, n: int) -> dict:
        return {"rep": [unit, n]}

    long_line = "Anh cứ nói mãi một chuyện cũ như thế, em nghe mà không biết nên cười hay nên khóc. "
    long_narr = "Gió thổi qua mái hiên, chiếc đèn lồng đung đưa và bóng người kéo dài trên nền đất ẩm. "
    story: list[tuple] = []
    story += [("narration", "Đêm ấy, quán trà cuối phố vắng khách."),
              ("dialogue", rep(long_line, 60), "Khoa"),
              ("dialogue", rep(long_line, 60), "Lan"),
              ("dialogue", rep(long_line, 60), "Khoa"),
              ("narration", "Ngoài kia mưa bắt đầu rơi."),
              ("dialogue", "“Thôi, để mai nói tiếp.”", "Lan")]
    story += [("narration", rep(long_narr, 40)) for _ in range(2)]
    story += [("dialogue", "“Câu này nằm trước một dải đoạn dài.”", "NPC_LOCAL:chủ quán")]
    story += [("narration", rep(long_narr, 38)) for _ in range(6)]
    story += [("dialogue", "“Đã khuya rồi, anh về đi.”", "Lan")]
    story += [("narration", "Lan thu dọn chén đĩa."),
              ("narration", rep(long_narr, 38)),
              ("dialogue", "“Câu A.”", "Khoa"),
              ("narration", rep(long_narr, 38)),
              ("narration", rep(long_narr, 38)),
              ("dialogue", "“Câu B.”", "Lan"),
              ("narration", rep(long_narr, 38))]
    story += [("dialogue", rep(long_line, 160), "Khoa"),
              ("narration", "Chủ quán thở dài."),
              ("dialogue", "“Câu cuối.”", "Lan"),
              ("narration", "Đèn tắt.")]
    # Đuôi ngắn: khối nhiều câu KHÔNG bị cắt.
    for turn in range(6):
        story += [("dialogue", f"“Lời thứ {turn + 1} của buổi nói chuyện cuối.”", "Khoa" if turn % 2 == 0 else "Lan"),
                  ("narration", "Họ nhìn nhau.")]
    return story


def expand(text) -> str:
    if isinstance(text, dict):
        unit, n = text["rep"]
        return unit * n
    return text


def synthetic_pieces(story, counter_kind: str, narrator: str):
    head = (f"Các chương hiện tại: {TITLE}", BB.narrator_line(narrator))
    piece, labels = [], {}
    for seq, entry in enumerate(story):
        kind, text = entry[0], expand(entry[1])
        spoken = kind in ("dialogue", "thought")
        piece.append(BB.Seg(text=text, paragraph=seq // 2, kind=kind if spoken else "narration", speaker="" if spoken else "NARRATOR",
                            head=head, seq=seq))
        if spoken:
            labels[seq] = entry[2]
    return piece, labels


def build_synthetic(name: str, story, narrator: str, require: set[str]) -> dict:
    fixture: dict = {"name": name, "title": TITLE, "narrator": narrator, "limit_tokens": BB.LIMIT_TOKENS,
                     "story": [{"kind": e[0], "text": e[1], **({"label": e[2]} if len(e) > 2 else {})} for e in story]}
    fixture["system_pq_sha256"] = sha(BB.prompts.SYSTEM_PQ)
    fixture["system_block_sha256"] = sha(BB.prompts.SYSTEM_BLOCK)
    for variant, counter in (("chars3", CharCounter()), ("tokenizer", BB.TokenCounter())):
        if variant == "tokenizer" and not counter.kind.startswith("tokenizers:"):
            raise SystemExit("cần tokenizer thật để dựng fixture")
        piece, labels = synthetic_pieces(story, variant, narrator)
        result = run_reference(piece, labels, counter)
        entry = {"info": result["info"], "targets": result["targets"], "final": {str(k): v for k, v in result["final"].items()},
                 "users_sha256": [sha(user) for user in result["users"]]}
        if variant == "chars3":
            entry["users"] = result["users"]   # đề đầy đủ: truyện bịa nên chép được
        fixture[variant] = entry
        covered = {key for key in ("blocks_trimmed", "blocks_truncated", "blocks_dropped") if result["info"].get(key)}
        missing = require - covered
        if missing:
            raise SystemExit(f"{name}/{variant}: thiếu nhánh {sorted(missing)} (info={result['info']})")
        print(f"{name}/{variant}: {len(result['users'])} đề, info={result['info']}")
    return fixture


# --------------------------------------------------------------------------------------------------------------------
# Chương thật
# --------------------------------------------------------------------------------------------------------------------
def build_real(short: str, ch: str) -> dict:
    row = next(r for r in RB.read_gate() if r.short == short and ch in r.chapters)
    src = RB.find_project(EVAL, row.rootpat, "b9lps1234", ch)
    dst = RB.find_project(EVAL, row.rootpat, "b41s1234", ch)
    assert src is not None and dst is not None and (dst / RB.DONE_NAME).is_file(), (short, ch)
    piece = M.load_piece_modelkind(src / "project.sqlite3", row, ch)
    con = sqlite3.connect(f"file:{(dst / 'project.sqlite3').as_posix()}?mode=ro", uri=True)
    try:
        stored = {int(seq): str(speaker or "") for seq, speaker in con.execute("select seq, speaker from segments")}
    finally:
        con.close()
    labels = {}
    for s in piece:
        if s.spoken:
            label = stored[s.seq]
            labels[s.seq] = "NPC_LOCAL:" + label[len("NPC_LOCAL::"):] if label.startswith("NPC_LOCAL::") else label
    counter = BB.TokenCounter()
    assert counter.kind.startswith("tokenizers:")
    result = run_reference(piece, labels, counter)
    texts = hashlib.sha256("\x00".join(s.text for s in M.load_piece_modelkind(src / "project.sqlite3", row, ch)).encode("utf-8")).hexdigest()
    print(f"{short}/{ch}: {len(result['users'])} đề, info={result['info']}")
    return {"short": short, "chapter": ch, "root_pattern": row.rootpat, "narrator": row.fp, "base_tag": "b9lps1234", "label_tag": "b41s1234",
            "segments": len(piece), "spoken": sum(s.spoken for s in piece), "thoughts": sum(s.kind == "thought" for s in piece),
            "npc_local": sum(label.startswith("NPC_LOCAL:") for label in labels.values()),
            "texts_sha256": texts, "info": result["info"], "targets": result["targets"],
            "users_sha256": [sha(user) for user in result["users"]],
            "final_sha256": sha(json.dumps([[seq, label] for seq, label in sorted(result["final"].items())], ensure_ascii=False))}


def write(name: str, data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_bytes((json.dumps(data, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def main() -> int:
    write("synthetic_a.json", build_synthetic("synthetic_a", STORY_A, NARRATOR, set()))
    write("synthetic_b.json", build_synthetic("synthetic_b", story_b(), "", {"blocks_trimmed", "blocks_truncated", "blocks_dropped"}))
    real = [build_real(short, ch) for short, ch in REAL]
    write("real.json", {"eval_root": str(EVAL), "token_counter": "tokenizers:Qwen/Qwen3-4B-Instruct-2507", "chapters": real,
                        "system_pq_sha256": sha(BB.prompts.SYSTEM_PQ)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
