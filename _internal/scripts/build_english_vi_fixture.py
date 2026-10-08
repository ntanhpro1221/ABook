"""Sinh bộ ví dụ DÙNG CHUNG cho luật Việt hoá từ tiếng Anh: `tests/fixtures/english_vi/cases.json`.

Bản Python (`abook/english_vi.py`) và bản Kotlin (`readaloud/EnglishVi.kt`) cùng đọc file này (test_english_vi.py, EnglishViTest.kt) và
phải ra đúng cách đọc + đúng cờ, cả khi có từ điển phát âm (`assets/english_phones.txt.gz`) lẫn khi không (`*_nodict`: chỉ đường chính
tả). Bốn nhóm ca:
  sourced   mọi dạng có nguồn trong `tests/english_vi_evidence.py` (kèm dạng nguồn, cách đọc của LUẬT khi tắt bảng ghi đè, khớp hay không)
  override  mọi mục của bảng ghi đè (chủ sách, từ mượn, chữ viết tắt thành từ)
  edge      ca tự dựng cho từng dòng luật
  trial     ~300 từ tiếng Anh thật trong kho truyện thử (`trial.json`; chỉ từ / tên)

Sinh lại (chỉ khi cố ý đổi luật):  runtime/.venv/Scripts/python.exe scripts/build_english_vi_fixture.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abook.english_vi import ACRONYMS, OVERRIDES, vietnamized_english_flags
from tests import english_vi_evidence

FIXTURES = ROOT / "tests" / "fixtures" / "english_vi"

# Mỗi ca một dòng luật; ca nào luật không nhận thì reading là null.
EDGE: list[str] = [
    # -əl cuối -> ồ; l sau ai / ao / oi -> "ồ" không phụ âm đầu; l cuối sau i -> u; l khép khác -> n
    "table", "little", "Daniel", "Lyle", "mile", "owl", "oil", "bill", "feel", "guild", "Melbourne", "Dalton",
    # cụm phụ âm đầu -> Cờ- thanh huyền; giữa từ ơ ngang; t + r giữ tr; t đầu từ giữ t
    "spell", "star", "smile", "Blake", "Brian", "Grace", "trust", "strong", "Francis", "Excalibur", "Tom", "Tyler", "Tony",
    # phụ âm tắc nhân đôi sau nguyên âm nhấn chính; không nhân đôi sau nhấn phụ
    "happy", "Rocky", "copper", "cookie", "ticket", "Appalachian",
    # /eɪ/ mở ây, khép p a, khép c êch, khép t ê (analogy), khép mũi ê; ai + m -> am; ai / ao / oi + phụ âm khác bỏ; /æŋk/ -> anh
    "day", "name", "make", "late", "Grey", "time", "crime", "night", "five", "town", "Lloyd", "tank", "rank", "Frankie", "sang",
    # w, y bán âm; qu; ng không mở âm tiết; /ɚ/ trước nguyên âm mở r
    "William", "Wendy", "queen", "quick", "you", "music", "Hemingway", "singer", "camera", "Colorado",
    # phụ âm cuối hữu thanh / xát -> tắc; cụm cuối giữ một
    "bad", "dog", "love", "bath", "judge", "Ruth", "first", "world", "Edward",
    # tên ngắn một phụ âm đầu + tắc + e câm theo mặt chữ; cụm phụ âm đầu đi đường âm vị
    "Coke", "Duke", "Zeke", "Nate", "Pike", "Shake", "Blake", "Gate", "gate", "Rose", "rose", "Lace", "Page", "Jane", "Cale", "Dave",
    # /eɪ/ + t -> êt, + s cuối -> ây; /aɪər/ -> ai; /ɔːl/ -> ôn; từ ghép đọc từng phần
    "late", "great", "Grace", "days", "fire", "higher", "fireball", "ball", "Paul", "sandworm", "Brightwater", "Shalltear",
    # âm mũi theo âm vị, g + e cứng, c + e mềm; tắc + l / r giữa từ -> Cờ huyền; w đầu từ -> gu
    "Dane", "Jane", "Luce", "Cage", "Laplace", "tablet", "Andrew", "goblin", "Walt", "Walter", "water", "Will", "Weiss", "Washington", "Wolf",
    "Walker", "Wood", "Wendy",
    # đường chính tả (tên tự chế / không có trong từ điển)
    "Encrid", "Lancel", "Calian", "Theia", "Arna", "Rudeus", "Sylphy", "Kraken", "Wyvern", "Ainz", "Thorne", "Phoebus", "Knightley",
    "Brightwater", "Xylo", "Quinzel", "Shalltear", "Lucretia", "Ashford", "Whitlock",
    # nối gạch, viết hoa, chữ lạ, chữ viết tắt
    "Jean-Paul", "Mary-Ann", "MARY", "iPhone", "McDonald", "O'Brien", "Ko1", "", "VIP", "ID", "id", "Vip",
    # vòng 10 (bộ đo translit_bench): o mở âm tiết tên bịa, -ton / -xon, -oa cuối, ch cuối, a + x / g cuối, e + c, r bỏ + -y, -er / -ur huyền hay ngang,
    # e câm cuối khi gắn chữ, ey, từ thường cùng dáng tên ngắn + e câm, từ mượn có dấu, OK / TV, hậu tố gọi Nhật sau gạch
    "Docora", "Symphonia", "Dystopia", "Heliona", "Novem", "Jaxon", "Anton", "Astroa", "Ranoa", "Lich", "Mitch", "March", "Axel", "Flag", "magma",
    "Rebecca", "Extra", "text", "next", "Party", "harpy", "Arthur", "Silver", "Elixir", "Beatrice", "Greyrat", "Fire", "Note", "Code", "White",
    "video", "Video", "café", "OK", "TV", "ok", "Lyle-kun", "Mary-dono", "Eleanora-san", "Persona-kun",
    # vòng 11: -well, -ore, tắc + l / r (d g, nguyên âm dài, cụm ng + g), ir không nhấn, -ar cuối, -re cuối, -ayer, ou + nguyên âm, chr, oh cuối,
    # w nuốt vào u ở nửa sau từ ghép, chữ viết hoa lạ (TOÀN HOA, kết bằng một chữ hoa), từ mượn thêm
    "Cromwell", "Roxwell", "Maxwell", "Manticore", "Pellinore", "Algore", "Libra", "Daydream", "Integra", "deadline", "England", "Templar", "Miranda",
    "Oscar", "Altar", "Maria", "Ogre", "Louina", "Chrono", "Uzoh", "Loyar", "cosplayer", "Lilywood", "LYLE", "TYPE", "YGGDRASIL", "DreadlorD",
    "NPC", "MARY", "beta", "Beta", "motor", "pharaoh", "protein", "coca", "piranha",
]


def _trial() -> list[str]:
    return json.loads((FIXTURES / "trial.json").read_text(encoding="utf-8"))["tokens"]


def _read(token: str, **options) -> dict:
    found = vietnamized_english_flags(token, **options)
    return {"reading": None if found is None else found[0], "flags": [] if found is None else list(found[1])}


def _case(group: str, token: str) -> dict:
    with_dict = _read(token)
    without = _read(token, dictionary={})
    return {"group": group, "token": token, **with_dict, "reading_nodict": without["reading"], "flags_nodict": without["flags"]}


def cases() -> dict:
    out = []
    for token, sources, kind in english_vi_evidence.SOURCED:
        rule = _read(token, overrides=False)
        matched = rule["reading"] is not None and rule["reading"].casefold() in {source.casefold() for source in sources}
        entry = {**_case("sourced", token), "rule": rule["reading"], "rule_flags": rule["flags"], "sources": list(sources), "kind": kind,
                 "matches": matched}
        if not matched:
            entry["because"] = english_vi_evidence.EXPLAINED[token][1]
        out.append(entry)
    for token in list(OVERRIDES) + list(ACRONYMS):
        out.append(_case("override", token))
    for group, items in (("edge", EDGE), ("trial", _trial())):
        for token in items:
            out.append(_case(group, token))
    return {"cases": out}


def cases_bytes() -> bytes:
    lines = ['{', ' "cases": [']
    body = [json.dumps(case, ensure_ascii=False) for case in cases()["cases"]]
    for index, line in enumerate(body):
        lines.append("  " + line + ("," if index < len(body) - 1 else ""))
    lines += [" ]", "}", ""]
    return "\n".join(lines).encode("utf-8")


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "cases.json").write_bytes(cases_bytes())  # write_bytes: LF, không CRLF của Windows
    print(f"{len(cases()['cases'])} ca -> {FIXTURES / 'cases.json'}")


if __name__ == "__main__":
    main()
