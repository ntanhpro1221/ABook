"""Ca thử cho phần TIỀN XỬ LÝ của `abook/romanization.py` (viết hoa toàn bộ, gạch nối / hậu tố, CamelCase, cách viết quen của tên Hàn): token tên + cách đọc, lấy từ bộ đo
luật phiên âm tên riêng (`Corpus/research/tn/translit_bench`, nhãn của agent Claude theo `docs/READING_FOREIGN_NAMES.md`; chỉ chép TOKEN TÊN và đáp án, không chép câu truyện).

BENCH_JA / BENCH_KO: mỗi ca luật trả None hay sai trước khi có tiền xử lý, nay khớp nhãn (không phân biệt hoa / thường, gạch = cách).
KEPT: tên có phần chữ Anh / viết tắt GIỮ NGUYÊN (nhãn của bộ đo là dạng đã Việt hoá, việc của `english_vi` và luật chữ viết tắt): luật đọc phần romaji / RR, chừa phần kia.
STILL_NONE: cố ý để None (quy ước không quyết, hay là tên Tây).
Các ca trong bộ đo mà luật vẫn None / sai vì lý do KHÁC tiền xử lý (Theia, Fina, Tio: ti / fi không phải Hepburn; Kasuya: uya cuối từ; Pimpon: m trước p; Gyu; Oppa: o-pa / op-pa;
Gangwon ...) không có ở đây.
"""
from __future__ import annotations

BENCH_JA: list[tuple[str, str, str]] = [
    ("IZUMO", "ja", "I-du-mô"), ("Gấu-san", "ja", "Gấu-xan"), ("Vương-sama", "ja", "Vương-xa-ma"), ("vương-sama", "ja", "vương-xa-ma"),
    ("hùng-sama", "ja", "hùng-xa-ma"), ("Thư-sama", "ja", "Thư-xa-ma"), ("thần-sama", "ja", "thần-xa-ma"), ("Thủy-sama", "ja", "Thủy-xa-ma"),
    ("sĩ-sama", "ja", "sĩ-xa-ma"), ("chính-sama", "ja", "chính-xa-ma"), ("tước-sama", "ja", "tước-xa-ma"), ("Giả-sama", "ja", "Giả-xa-ma"),
    ("giả-sama", "ja", "giả-xa-ma"), ("ChuChu", "ja", "Chu-chu"), ("chúa-sama", "ja", "chúa-xa-ma"), ("Thú-sama", "ja", "Thú-xa-ma"),
    ("Thần-sama", "ja", "Thần-xa-ma"), ("Thủ-chan", "ja", "Thủ-chan"), ("KANATA", "ja", "Ca-na-ta"), ("OkabeRintarou", "ja", "O-ca-be Rin-ta-râu"),
    ("Tenshi-chwan", "ja", "Ten-si-choan"), ("HImeno", "ja", "Hi-me-nô"), ("REI", "ja", "Rây"), ("KOU", "ja", "Câu"), ("KAEDE", "ja", "Ca-e-đe"),
    ("TAKIOTO", "ja", "Ta-ki-ô-tô"), ("NEE-SAN", "ja", "Ne-xan"), ("Eruza-người", "ja", "E-ru-da-người"), ("Kanata-cả", "ja", "Ca-na-ta-cả"),
    ("Kanata-vẫn", "ja", "Ca-na-ta-vẫn"), ("đại-sama", "ja", "đại-xa-ma"), ("thơm-sensei", "ja", "thơm-xen-xây"),
    ("xám-onechan", "ja", "xám-o-ne-chan"), ("tải-kun", "ja", "tải-cun"), ("à-degozaru", "ja", "à-đe-gô-da-ru"), ("NhạcJoJo", "ja", "Nhạc Giô-giô"),
    ("DereDere", "ja", "Đe-re Đe-re"), ("Trắng-chan", "ja", "Trắng-chan"),
]

BENCH_KO: list[tuple[str, str, str]] = [
    ("Ahrin", "ko", "A-rin"), ("Ahri", "ko", "A-ri"), ("Joo", "ko", "Giu"), ("Seol-Ah", "ko", "Xe-on-a"), ("Tae-hoon", "ko", "Te-hun"),
    ("Shi", "ko", "Xi"), ("Hi-ah", "ko", "Hi-a"), ("Ahn", "ko", "An"), ("Jooseon", "ko", "Giu-xe-on"), ("Seung-Ah", "ko", "Xưng-a"),
    ("Ji-woo", "ko", "Gi-u"), ("Noona", "ko", "Nu-na"), ("Joo-seon", "ko", "Giu-xe-on"), ("Min-ah", "ko", "Min-a"), ("Ah-ryeon", "ko", "A-re-on"),
    ("noona", "ko", "nu-na"), ("Shinhyun", "ko", "Xin-hi-un"), ("Soohyuk", "ko", "Xu-hi-úc"), ("Jiyoon", "ko", "Gi-giun"),
    ("Joochul", "ko", "Giu-chun"), ("Joo-chul", "ko", "Giu-chun"), ("Bi-Ah", "ko", "Bi-a"), ("Shincheol", "ko", "Xin-che-on"),
    ("Ryoon", "ko", "Li-un"), ("Jaemoon", "ko", "Gie-mun"), ("Seokjoo", "ko", "Xe-óc-giu"), ("shinkal", "ko", "xin-can"),
    ("Ahn-Seon", "ko", "An-xe-on"), ("Weol-hyun", "ko", "Guôn-hi-un"), ("Hoẵng-nim", "ko", "Hoẵng-nim"), ("Jahoon", "ko", "Gia-hun"),
]

# (token, gốc, cách đọc, cờ phải có)
KEPT: list[tuple[str, str, str, str]] = [
    ("PD-nim", "ko", "PD-nim", "keep:abbr"),
    ("Ikemen-style", "ja", "I-ke-men-style", "keep:english"),
    ("Nagaya-Stable", "ja", "Na-gay-a Stable", "keep:english"),
    ("Clan-sama", "ja", "Clan-xa-ma", "keep:english"),
    ("Mary-san", "ja", "Mary-xan", "keep:english"),
]

STILL_NONE: list[tuple[str, str]] = [
    ("Jinyoon", "ko"),       # Jin-yun hay Ji-nyun: RR viết giống nhau
    ("Spider-Man", "ja"),    # chữ Anh cạnh một đoạn cũng là chữ Anh: tên Tây
    ("Mary-Ann", "ja"), ("YouTube", "ja"), ("iPhone", "ja"),   # không có đoạn nào đọc theo luật / CamelCase chữ Anh
    ("PD", "ko"), ("PD-NPC", "ko"), ("Nhạc", "ja"), ("Nhạc-Gấu", "ja"),   # chỉ có phần giữ nguyên
    ("Waseda-Keio-Sophia", "ja"),   # Sophia đọc được theo RR của Hàn: không chắc là chữ Anh
    ("Khoan-san", "ja"),     # âm tiết Việt không dấu không được giữ (Si-eun, Seo-ram cũng là âm tiết Việt)
]
