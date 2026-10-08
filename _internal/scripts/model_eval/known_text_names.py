"""Bộ trích TÊN RIÊNG không dùng gold cho thí nghiệm "known-list + tên trong chữ" (b15b16/PLAN.md 08-10 20:0x, hướng (1)).

Từ chữ các đoạn của một lô (text + previous_text + next_text như prompt), lấy chuỗi từ viết hoa chữ đầu (1-4 từ, từ thứ hai trở đi
cũng viết hoa) KHÔNG đứng đầu câu, bỏ đại từ / chức danh / từ chung viết hoa (STOP). Tên đứng đầu câu chỉ nhận khi ngay sau là
động từ nói ("X nói", "X đáp"...) hoặc là lời gọi ("X ạ", "X ơi"). Không biết gì về gold.

    D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe -X utf8 extract.py eval   # đo trên 573 lô cổng B9 (CPU)
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata

STOP = {w.casefold() for w in """
Tôi Ta Mình Tớ Anh Em Chị Cô Cậu Ông Bà Bác Chú Dì Thím Cháu Con Mẹ Bố Cha Ba Má Ngài Nàng Chàng Hắn Họ Nó Bọn Chúng Các Những Mọi
Này Kia Đó Ấy Vậy Thế Nhưng Và Hoặc Nếu Khi Lúc Rồi Thì Là Có Không Chưa Đã Đang Sẽ Vì Bởi Nên Cho Với Của Trong Ngoài Trên Dưới
Sau Trước Giữa Một Hai Ba Bốn Năm Sáu Bảy Tám Chín Mười Ừ Ờ Ồ À Á Ơ Ê Này Hả Hử Hừ Hmm Ừm Vâng Dạ Ừa Ôi Trời Chết Thôi Đúng Sai
Được Phải Thật Quả Chắc Có_lẽ Tuy Dù Mặc Ngay Cả Chỉ Đến Từ Tại Theo Về Ra Vào Lên Xuống Đi Lại Hãy Đừng Chớ Xin Mời Cảm Ơn Chào
Giáo Sư Thầy Tiểu Thư Công Chúa Hoàng Tử Bệ Hạ Điện Hạ Đại Nhân Tiểu Thư Sư Phụ Sư Huynh Sư Tỷ Tiền Bối Hậu Bối Senpai Sensei
Chủ Nhân Quý Ngài Thưa Đức Vua Nữ Hoàng Hoàng Đế Đại Tư Tế Ma Vương Dũng Giả Hiệp Sĩ Kỵ Sĩ Pháp Sư
Chương Phần Hồi Tập Quyển Ngày Tháng Năm Giờ Phút Thứ Chủ Nhật OK Ok
""".split()}
SPEECH = r"(nói|đáp|hỏi|hét|gọi|thì thầm|lên tiếng|cười|kêu|quát|bảo|trả lời|thở dài|lẩm bẩm|gắt|reo|xen vào|tiếp lời)"
UP = r"[A-ZÀ-ỸĐ][\w'’-]*"
NAME = re.compile(rf"(?<![\w'’-])({UP}(?:\s+{UP}){{0,3}})(?![\w'’-])")
SENT_END = re.compile(r"(^|[.!?…:;\"“”«»\-—–(\[]\s*)$")


def is_upper_word(w: str) -> bool:
    return bool(w) and w[0].isupper()


def names_in(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text or "")
    out = []
    for m in NAME.finditer(text):
        words = []
        for w in m.group(1).split():  # dải À-Ỹ của regex lẫn chữ thường -> cắt ở từ đầu tiên không viết hoa
            if not w[0].isupper():
                break
            words.append(w)
        if not words:
            continue
        end = m.start() + m.group(1).index(words[-1]) + len(words[-1])
        while words and words[0].casefold() in STOP:  # bỏ chức danh/đại từ đầu cụm ("Giáo sư Fernando" -> "Fernando")
            words = words[1:]
        while words and words[-1].casefold() in STOP:
            words = words[:-1]
        if not words or len(words[0]) < 2:
            continue
        name = " ".join(words)
        start = m.start() + m.group(1).index(words[0])
        before = text[:start]
        after = text[end:end + 25]
        sentence_start = SENT_END.search(before) is not None
        vocative = re.match(r"\s*(ạ|ơi|à|này|nhé|hả)\b", after) is not None or re.search(r",\s*$", before) is not None
        speaks = re.match(rf"\s*{SPEECH}\b", after) is not None
        if sentence_start and not (vocative or speaks):
            continue
        out.append(name)
    return out


def batch_names(rows: list[dict]) -> list[str]:
    seen, order = set(), []
    for r in rows:
        for field in ("previous_text", "text", "next_text"):
            for n in names_in(str(r.get(field) or "")):
                k = n.casefold()
                if k not in seen:
                    seen.add(k)
                    order.append(n)
    return order


def cmd_eval() -> int:
    """Trên cổng B9: (a) nhân vật gold nói trong lô nhưng VẮNG known-list - bộ trích bắt được bao nhiêu (theo root gold);
    (b) số tên thêm mỗi lô, bao nhiêu không khớp nhân vật gold nào của truyện (rác: địa danh, vật...)."""
    import collections
    import contextlib
    import io
    sys.path.insert(0, "D:/Novels/LLM_Train/rerank")
    with contextlib.redirect_stdout(io.StringIO()):
        import oracle as O
        import build_step1 as B
    chs = O.load_chapters()
    byp = B.load_prompts()
    projects = B.chapter_projects()
    tot = collections.Counter()
    per_story = collections.defaultdict(collections.Counter)
    for ch in chs:
        root = lambda lab: ch.roots.get(O.speaker_key(lab), O.speaker_key(lab))  # noqa: E731
        gold_roots = {root(o) for e in ch.gold.values() for o, _c in e.speakers if o and not O.is_special(o)}
        tok_root = {}
        for e in ch.gold.values():
            for o, _c in e.speakers:
                if o and not O.is_special(o):
                    for t in re.findall(r"\w{3,}", O.strip_marks(o).casefold()):
                        tok_root.setdefault(t, root(o))
        for rec in byp[B.norm(projects[ch.name])]:
            p = rec["prompt"]
            known = re.findall(r"\n- ([^;\n]+); số lần đã gặp", p)
            known_roots = {root(k) for k in known}
            rows, _ = json.JSONDecoder().raw_decode(p[p.index("Các đoạn liên tiếp:") + len("Các đoạn liên tiếp:"):].lstrip())
            names = batch_names(rows)
            hit_roots = set()
            junk = 0
            for n in names:
                rs = {tok_root[t] for t in re.findall(r"\w{3,}", O.strip_marks(n).casefold()) if t in tok_root}
                if rs:
                    hit_roots |= rs
                else:
                    junk += 1
            spoken = set()
            for seq in rec["seqs"]:
                e = ch.gold.get((ch.chapter, int(seq)))
                if e is not None and e.spoken and e.speakers and not O.is_special(e.speakers[0][0]):
                    spoken.add(root(e.speakers[0][0]))
            missing = spoken - known_roots
            tot["lô"] += 1
            tot["tên thêm"] += len(names)
            tot["tên rác"] += junk
            tot["người nói vắng known"] += len(missing)
            tot["  bắt được"] += len(missing & hit_roots)
            per_story[ch.story]["vắng"] += len(missing)
            per_story[ch.story]["bắt"] += len(missing & hit_roots)
            per_story[ch.story]["rác"] += junk
            per_story[ch.story]["lô"] += 1
    print(dict(tot))
    print(f"recall người nói vắng known: {tot['  bắt được']}/{tot['người nói vắng known']}; tên thêm TB/lô {tot['tên thêm'] / tot['lô']:.1f}, "
          f"rác TB/lô {tot['tên rác'] / tot['lô']:.1f}")
    for s, c in sorted(per_story.items()):
        print(f"  {s}: bắt {c['bắt']}/{c['vắng']}, rác/lô {c['rác'] / c['lô']:.1f}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["eval"]:
        raise SystemExit(cmd_eval())
    print(batch_names([{"text": " ".join(sys.argv[1:])}]))
