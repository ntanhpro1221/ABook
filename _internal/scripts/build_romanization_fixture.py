"""Sinh bộ ví dụ DÙNG CHUNG cho luật đọc romaji Nhật / RR Hàn: `tests/fixtures/romanization/cases.json`.

Bản Python (`abook/romanization.py`) và bản Kotlin (`readaloud/Romanization.kt`) cùng đọc file này (test_romanization.py,
RomanizationTest.kt) và phải ra đúng cách đọc + đúng cờ. Ba nhóm ca:
  sourced   mọi dạng Nhật / Hàn có nguồn (kể cả ca của chủ sách) trong `tests/romanization_evidence.py` (kèm dạng nguồn và khớp hay không)
  edge      ca tự dựng cho từng dòng luật: hậu tố, phụ âm đôi, n âm tiết, nguyên âm dài, g / d / b hữu thanh, chữ không nhận
  names     tên thật trong `names.json` (tên nhân vật thường gặp nhất trong kho truyện thử; chỉ tên)

Sinh lại (chỉ khi cố ý đổi luật):  runtime/.venv/Scripts/python.exe scripts/build_romanization_fixture.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abook.romanization import romanized_reading_flags  # noqa: E402
from tests import romanization_evidence  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "romanization"

# (token, origin): mỗi ca một dòng luật; ca nào luật không nhận thì reading là null.
EDGE: list[tuple[str, str | None]] = [
    # hậu tố gọi (mục 2): đọc theo chính bảng romaji
    ("Koutarou-san", "ja"), ("Subaru-kun", "ja"), ("Yuki-chan", "ja"), ("Sakura-sama", "ja"), ("Tanaka-senpai", "ja"), ("Sato-sensei", "ja"), ("Onee-san", "ja"), ("Okaa-san", "ja"), ("Ojii-san", "ja"), ("Jin-dono", "ja"), ("Yuki-tan", "ja"), ("Kou-nii", "ja"), ("Sora-nee", "ja"),
    ("senpai", "ja"), ("sensei", "ja"), ("Charlotte-san", "ja"),
    # u -> u, e -> e (chủ sách), iu / u sau âm vòm, s -> x, sh -> s, tsu, fu, z / j, k / g theo chính tả
    ("Kuro", "ja"), ("Yuzuru", "ja"), ("Ryuu", "ja"), ("Shuuichi", "ja"), ("Chuuya", "ja"), ("Jun", "ja"), ("Tsubasa", "ja"),
    ("Fuji", "ja"), ("Zenzo", "ja"), ("Kenji", "ja"), ("Gin", "ja"), ("Kei", "ja"), ("Kiyoshi", "ja"), ("Sakura", "ja"),
    # nguyên âm dài, ei -> ây (chủ sách), ai tách khi khép
    ("Koutarou", "ja"), ("Ōsaka", "ja"), ("Osaka", "ja"), ("Tokyo", "ja"), ("Reiji", "ja"), ("Rei", "ja"), ("Kain", "ja"), ("Kaito", "ja"), ("Maaya", "ja"),
    ("Shiina", "ja"),
    # phụ âm đôi khép âm tiết trước, n âm tiết, nn, n' , m trước b / p
    ("Hokkaido", "ja"), ("Nippon", "ja"), ("Matcha", "ja"), ("Isshiki", "ja"), ("Otto", "ja"), ("Kanna", "ja"), ("Shin'ichi", "ja"),
    ("Shinichi", "ja"), ("Shimbun", "ja"), ("Hyakkimaru", "ja"),
    # y + nguyên âm -> gi (chủ sách), kya / kyo, wa
    ("Yamato", "ja"), ("Ayaka", "ja"), ("Kyoko", "ja"), ("Ryoma", "ja"), ("Hyouka", "ja"), ("Wakana", "ja"), ("Yuki", "ja"),
    ("Yokohama", "ja"), ("Mayu", "ja"), ("Yoshida", "ja"), ("Megumi", "ja"), ("Keita", "ja"), ("Seiya", "ja"), ("Kyouko", "ja"), ("Ryouma", "ja"),
    ("Kouki", "ja"), ("Satou", "ja"), ("Shouta", "ja"), ("Chouji", "ja"), ("Jouji", "ja"), ("Ouji", "ja"), ("Kyōto", "ja"), ("Kyôto", "ja"), ("Ōno", "ja"),
    ("Kaoru", "ja"), ("Tooru", "ja"), ("Hokkaidō", "ja"), ("Nōto", "ja"),
    # chủ sách lần 4: ee / ii / aa gộp, g + i -> ghi, tsu -> xu, yu tách, shu -> su, o không phụ âm đầu -> o, ao cuối gộp / giữa từ tách, từ quen onigiri
    ("Hiiragi", "ja"), ("Inoue", "ja"), ("Jouichi", "ja"), ("Kouhai", "ja"), ("Senpai", "ja"), ("Tsubasa", "ja"), ("Matsuyama", "ja"), ("Natsuki", "ja"),
    ("Ryuu", "ja"), ("Kyuuji", "ja"), ("Nyuu", "ja"), ("Shuuichi", "ja"), ("Kyūshū", "ja"), ("Osaka", "ja"), ("Ōsaka", "ja"), ("Aoi", "ja"), ("Kaori", "ja"),
    ("Nao", "ja"), ("Naoki", "ja"), ("Ao", "ja"), ("Onigiri", "ja"), ("Onigiri-kun", "ja"), ("Tomoe", "ja"), ("Sora", "ja"), ("Konoha", "ja"), ("Ozu", "ja"),
    ("Maaya", "ja"), ("Gin", "ja"), ("Ginko", "ja"), ("Jin", "ja"),
    # lần 5: o sau i / u -> ô, sau a / e hay đầu từ -> o; ya cuối từ sau nguyên âm -> may-a; Kouya-kiểu có cờ mở; Hàn yu / yeo sau phụ âm
    ("Fumio", "ja"), ("Fukuoka", "ja"), ("Suneo", "ja"), ("Maaya", "ja"), ("Seiya", "ja"), ("Kouya", "ja"), ("Maya", "ja"), ("Kaya", "ja"), ("Mayu", "ja"), ("Sayo", "ja"), ("Raiya", "ja"), ("Kyung", "ko"), ("Byung", "ko"), ("Gyeong", "ko"), ("Pyeong", "ko"), ("Kyeong", "ko"), ("Ayaka", "ja"), ("Akio", "ja"), ("Mio", "ja"),
    ("Taeko", "ja"), ("Reo", "ja"), ("Kouichi", "ja"),
    # Hàn lần 5: b đầu từ -> b, gye -> ghi, eo + u -> e-un, Myung -> mung, tên nối gạch thành một chuỗi
    ("Bak", "ko"), ("Daebak", "ko"), ("Myung", "ko"), ("Hyun", "ko"), ("Cheonggyecheon", "ko"), ("Kim Jong-un", "ko"), ("Lee Myung-bak", "ko"), ("Park", "ko"),
    ("Geun-hye", "ko"), ("Gye", "ko"), ("Seou", "ko"), ("Jeou", "ko"), ("Bulguksa", "ko"),
    # Hàn lần 4: bật hơi như thường, s -> x, j -> gi, y + nguyên âm -> gi, eo, yu / yeo tách i-, wo -> uô, w đầu từ -> gu (giữa từ: analogy), oi
    ("Kang", "ko"), ("Taehyun", "ko"), ("Choi", "ko"), ("Yoon", "ko"), ("Hyung", "ko"), ("Seojun", "ko"), ("Jeong", "ko"), ("Won", "ko"), ("Suwon", "ko"),
    ("Busan", "ko"), ("Jin", "ko"), ("Kim Jong-un", "ko"), ("Yeji", "ko"), ("Yeo", "ko"), ("Ye", "ko"), ("Hyeon", "ko"), ("Gyeongju", "ko"), ("Seoul", "ko"),
    ("Hoe", "ko"), ("Jeju", "ko"), ("Seok", "ko"),
    # Hepburn không có: ti, tu, hu, si, dài hoặc chữ không phải romaji
    ("Tuka", "ja"), ("Hiro", "ja"), ("Cale", "ja"), ("Lily", "ja"), ("Ah", "ja"), ("IZUMO", "ja"), ("iPhone", "ja"), ("Ko1", "ja"),
    ("kk", "ja"), ("'ka", "ja"), ("Ka-", "ja"), ("", "ja"), ("Kaz", "ja"), ("Sō", "ja"),
    # Hàn: tên người không gạch nối, g / d / b đầu từ vô thanh và giữa hai âm hữu thanh, l cuối, ll, r đầu từ
    ("Park Geun-hye", "ko"), ("Kim Dae-jung", "ko"), ("Lee Myung-bak", "ko"), ("Seo-yeon", "ko"), ("Min-jun", "ko"), ("Minjun", "ko"),
    ("Jang", "ko"), ("Daon", "ko"), ("Eun", "ko"), ("Ryu", "ko"), ("Ryung", "ko"), ("Han", "ko"), ("Hanbit", "ko"), ("Hallasan", "ko"),
    ("Bulguk", "ko"), ("Daegu", "ko"), ("Gwangju", "ko"), ("Incheon", "ko"), ("Cheonggye", "ko"), ("Sejun", "ko"), ("Taehyung", "ko"),
    ("Yuna", "ko"), ("Yeonha", "ko"), ("Gwi", "ko"), ("Kwon", "ko"), ("Wonbin", "ko"), ("Sangchul", "ko"),
    # Hàn: cách viết quen (Yoo, Kim), không nhận (nguyên âm đôi lặp, ambiguous ng / n + g, chữ lạ)
    ("Kim", "ko"), ("Yoo", "ko"), ("Lee", "ko"), ("Shin", "ko"), ("Jiwoo", "ko"), ("Hangang", "ko"), ("Yongin", "ko"), ("Cale", "ko"),
    ("Hmm", "ko"), ("PARK", "ko"), ("park", "ko"),
    # không biết gốc thì không đoán
    ("Hajime", None), ("Seoul", None),
    # tiền xử lý (token tên của bộ đo luật): TOÀN HOA casefold, hoa lạ, CamelCase (hai nửa một âm tiết nối gạch), đoạn thường / hậu tố / chữ Việt / chữ Anh / viết tắt sau gạch
    ("KANATA", "ja"), ("REI", "ja"), ("NEE-SAN", "ja"), ("KAEDE", "ja"), ("IZUMO", "ja"), ("PARK", "ko"), ("OSAKA", "ja"), ("HImeno", "ja"), ("oSAKA", "ja"),
    ("OkabeRintarou", "ja"), ("DereDere", "ja"), ("ChuChu", "ja"), ("YuNa", "ja"), ("KouIchi", "ja"), ("NhạcJoJo", "ja"), ("iPhone", "ja"), ("YouTube", "ja"),
    ("Tenshi-chwan", "ja"), ("Rin-chwan", "ja"), ("Waseda-Keio", "ja"), ("Waseda-Keio-Sophia", "ja"), ("Ikemen-style", "ja"), ("Nagaya-Stable", "ja"), ("Mary-san", "ja"),
    ("Mary-Ann", "ja"), ("Spider-Man", "ja"), ("Clan-sama", "ja"), ("Gấu-san", "ja"), ("Vương-sama", "ja"), ("Thủ-chan", "ja"), ("thơm-sensei", "ja"), ("Kanata-cả", "ja"),
    ("à-degozaru", "ja"), ("xám-onechan", "ja"), ("Khoan-san", "ja"), ("Nhạc", "ja"), ("PD", "ja"),
    ("Seol-Ah", "ko"), ("Ahn-Seon", "ko"), ("Ahn", "ko"), ("Ahri", "ko"), ("Ahrin", "ko"), ("Min-ah", "ko"), ("Ah-ryeon", "ko"), ("Bi-Ah", "ko"), ("Hanah", "ko"),
    ("Shi", "ko"), ("Shinhyun", "ko"), ("Shincheol", "ko"), ("shinkal", "ko"), ("Joo", "ko"), ("Jooseon", "ko"), ("Joo-chul", "ko"), ("Ji-woo", "ko"), ("Jiwoo", "ko"),
    ("Soohyuk", "ko"), ("Jaemoon", "ko"), ("Jahoon", "ko"), ("Tae-hoon", "ko"), ("Ryoon", "ko"), ("Jinyoon", "ko"), ("Jiyoon", "ko"), ("Noona", "ko"), ("Weol-hyun", "ko"),
    ("PD-nim", "ko"), ("Hoẵng-nim", "ko"), ("Gyeong-nim", "ko"), ("Spider-Man", "ko"), ("Takeshi", "ko"),
    # chủ sách lần 8: oh -> ô dài, jy -> j, gh -> g, tên cố định (Gesunoh, Theia, Fina, Tio); Hàn kk -> k (tie-break), Gangwon
    ("Ohto", "ja"), ("Ohka", "ja"), ("Poh-chan", "ja"), ("Sanjyo", "ja"), ("Kanjyaka", "ja"), ("Hiiraghi", "ja"), ("Gesunoh", "ja"), ("Gesu", "ja"), ("Theia", "ja"),
    ("Fina", "ja"), ("Tio", "ja"), ("Tio-san", "ja"), ("Ohayou", "ja"), ("Johan", "ja"), ("Ōsaka", "ja"), ("tokki", "ko"), ("Hakkyo", "ko"), ("Gangwon", "ko"), ("Oppa", "ko"),
]


def _names() -> list[tuple[str, str]]:
    data = json.loads((FIXTURES / "names.json").read_text(encoding="utf-8"))
    return [(entry["token"], entry["origin"]) for entry in data["names"]]


def cases() -> dict:
    out = []
    for token, origin, sources, kind in romanization_evidence.SOURCED:
        found = romanized_reading_flags(token, origin)
        reading = None if found is None else found[0]
        matched = reading is not None and reading.casefold() in {source.casefold() for source in sources}
        entry = {"group": "sourced", "token": token, "origin": origin, "reading": reading,
                 "flags": [] if found is None else list(found[1]), "sources": list(sources), "kind": kind, "matches": matched}
        if not matched:
            entry["because"] = romanization_evidence.EXPLAINED[token][1]
        out.append(entry)
    for group, items in (("edge", EDGE), ("names", _names())):
        for token, origin in items:
            found = romanized_reading_flags(token, origin)
            out.append({"group": group, "token": token, "origin": origin, "reading": None if found is None else found[0],
                        "flags": [] if found is None else list(found[1])})
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
    data = cases()["cases"]
    print(f"{len(data)} ca -> {FIXTURES / 'cases.json'}")


if __name__ == "__main__":
    main()
