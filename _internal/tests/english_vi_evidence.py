"""Dạng Việt hoá CÓ NGUỒN của tên / từ tiếng Anh, lấy từ `Corpus/research/tn/reading_evidence.md` mục 2.3 và 2.4 (repo riêng tư), làm ca thử
cho `abook/english_vi.py`. Chỉ chép dạng tên / từ, không chép đoạn văn.

Mỗi ca: (chữ tiếng Anh, các dạng Việt có trong nguồn, loại nguồn). Một ca KHỚP khi cách đọc của LUẬT (không qua bảng ghi đè) trùng MỘT dạng
nguồn, đủ cả thanh. Ca không khớp phải có lý do trong `EXPLAINED`.

Loại: owner (chủ sách 04-10, đứng trên mọi nguồn), official (văn bản / cơ quan nhà nước), textbook (SGK), press (báo chính thống),
community (Wikipedia, bản nháp BKTT - chỉ để xem, không là chuẩn).

Chỉ lấy tên GỐC ANH (đọc theo âm Anh, có trong từ điển CMU). Bỏ: tên Pháp / Nga / Đức / Ý / Tây Ban Nha / La-tinh đọc theo tiếng gốc (Ăng-ghen,
Lê-nin, Mát-xcơ-va, Pa-ri, Bét-tô-ven, Mô-da, Tôn-xtôi, Cô-péc-ních, Ga-li-lê, Huy-gô, Vích-to, Na-pô-lê-ông, Lu-i, Rô-be-spi-e, Mê-hi-cô,
Bra-xin, An-đét, Xa-ha-ra, Bu-ê-nôt Ai-ret, Xao Pao-lô, Mát-téc-lích, Đê-mô-crit); tên Indonesia / Singapore (Giô-cô Uy-đô-đô, Rét-nô
Ma-xu-đi, Xing-ga-po); Tếchdát (bản tin tự ghi hai kiểu); Tô-ky-ô. Tên nhiều chữ tách theo chữ khi nguồn tách được (Niu-Oóc -> New, York).
Từ mượn trong bảng ghi đè (`LOANWORDS`: đô-la...) không đưa vào đây: chúng luôn khớp, không đo được gì.
"""
from __future__ import annotations

# (chữ, dạng nguồn, loại)
SOURCED: list[tuple[str, tuple[str, ...], str]] = [
    # --- chủ sách (04-10): mục 4, cố định; Kate là ca cố định (đọc theo mặt chữ), luật âm vị không nhắm tới nó ---
    ("game", ("ghêm",), "owner"),
    ("level", ("le-vồ", "le-vờ"), "owner"),
    ("maple", ("máp-pồ",), "owner"),
    ("Michael", ("Mai-cồ",), "owner"),
    ("Kate", ("Ca-tê",), "owner"),
    # lần 2: tên ngắn tắc + e câm theo mặt chữ (Pete pi-tờ là ca riêng), -ill -> iu, s + phụ âm đầu -> xờ, slime -> xờ-lam là ca riêng
    ("Mike", ("Mi-ke",), "owner"),
    ("Jake", ("Gia-ke",), "owner"),
    ("Luke", ("Lu-ke",), "owner"),
    ("Pete", ("Pi-tờ",), "owner"),
    ("skill", ("xờ-kiu",), "owner"),
    ("boss", ("bót",), "owner"),
    ("slime", ("xờ-lam",), "owner"),
    ("quest", ("quét",), "owner"),
    # lần 3: thay dạng nguồn cùng chữ (Tô-mát của văn bản nhà nước, Bốt-tơn / Rốc-ki của SGK); guild, time, Thomas là ca riêng
    ("guild", ("gui",), "owner"),
    ("Thomas", ("Tho-mát",), "owner"),
    ("Boston", ("Bót-tơn",), "owner"),
    ("Rocky", ("Róc-ki",), "owner"),
    ("time", ("tham",), "owner"),
    ("night", ("nai",), "owner"),
    ("Blake", ("Bờ-lếch",), "owner"),
    ("Master", ("Mát-tơ",), "owner"),
    ("Zeke", ("De-ke",), "owner"),
    ("gold", ("gôn",), "owner"),
    # lần 4: t đầu từ giữ t; /iː/ -> i; /æŋk/ -> anh; l sau ai / oi -> "ồ" không phụ âm đầu
    ("Tom", ("Tom", "Tôm"), "owner"),
    ("Tony", ("To-ni", "Tô-ni"), "owner"),
    ("team", ("tim",), "owner"),
    ("tank", ("tanh",), "owner"),
    ("Tina", ("Ti-na",), "owner"),
    ("Lyle", ("Lai-ồ",), "owner"),
    ("Kyle", ("Kai-ồ", "Cai-ồ"), "owner"),  # chủ sách viết kai; chính tả 1.5 viết c trước a, cùng âm
    ("Doyle", ("Đoi-ồ",), "owner"),
    # --- văn bản nhà nước / Bộ Ngoại giao ---
    ("Edison", ("Ê-đi-xơn",), "official"),
    ("Melbourne", ("Men-bơn",), "official"),
    ("Gillian", ("Ghi-li-ừn",), "official"),
    ("Bird", ("Bớt",), "official"),
    # --- sách giáo khoa (Địa lí, Lịch sử, Ngữ văn, Tiếng Việt, KHTN) ---
    ("Washington", ("Oa-sinh-tơn",), "textbook"),
    ("George", ("Gioóc-giơ",), "textbook"),
    ("Virginia", ("Viếc-gi-ni-a",), "textbook"),
    ("Scotland", ("Xcốt-len",), "textbook"),
    ("Ireland", ("Ai-len",), "textbook"),
    ("Charles", ("Sác-lơ",), "textbook"),
    ("New", ("Niu",), "textbook"),
    ("York", ("Oóc", "I-oóc"), "textbook"),
    ("Yorktown", ("I-oóc-tao",), "textbook"),
    ("Philadelphia", ("Phi-la-đen-phi-a",), "textbook"),
    ("Dallas", ("Đa-lát",), "textbook"),
    ("San", ("Xan",), "textbook"),
    ("Francisco", ("Phran-xít-cô",), "textbook"),
    ("Los", ("Lốt",), "textbook"),
    ("Angeles", ("An-giơ-lét",), "textbook"),
    ("Chicago", ("Chi-ca-gô",), "textbook"),
    ("Detroit", ("Đi-troi",), "textbook"),
    ("Colorado", ("Cô-lô-ra-đô",), "textbook"),
    ("Portland", ("Poóc-len",), "textbook"),
    ("Seattle", ("Xit-tơn",), "textbook"),
    ("Mississippi", ("Mi-xi-xi-pi",), "textbook"),
    ("Appalachian", ("A-pa-lat",), "textbook"),
    ("Hawaii", ("Ha-oai",), "textbook"),
    ("Alaska", ("A-la-xca",), "textbook"),
    ("Canada", ("Ca-na-da",), "textbook"),
    ("Australia", ("Ô-xtrây-li-a", "Xtrây-li-a"), "textbook"),
    ("Saratoga", ("Xa-ra-tô-ga",), "textbook"),
    ("Shakespeare", ("Sếch-xơ-pia", "Sếch-xư-pia"), "textbook"),
    ("Ernest", ("Ơ-ni-xơ-tơ",), "textbook"),
    ("Hemingway", ("Hê-minh-uây",), "textbook"),
    ("Dalton", ("Đan-tơn",), "textbook"),
    ("Rutherford", ("Rơ-dơ-pho",), "textbook"),
    ("Matthew", ("Mét-thiu",), "textbook"),
    ("Roosevelt", ("Ru-dơ-ven", "Rô-sơ-ven"), "textbook"),
    ("Romeo", ("Rô-mê-ô",), "textbook"),
    ("Amazon", ("A-ma-dôn",), "textbook"),
    ("Cromwell", ("Crôm-oen",), "textbook"),
    # --- báo (Phạm Quỳnh 1918 qua Tuổi Trẻ 2007) ---
    ("Manchester", ("Mang-xet-te",), "press"),
    ("Edinburgh", ("E-đinh-bua",), "press"),
    # --- cộng đồng: bản nháp BKTT, Wikipedia "Từ mượn" (bảng Anh, trang tự ghi không nguồn) - chỉ để xem ---
    ("London", ("Lân-đân",), "community"),
    ("Wayne", ("Uây-nơ",), "community"),
    ("Rooney", ("Ru-ni",), "community"),
    ("Marilyn", ("Ma-ri-lin",), "community"),
    ("Monroe", ("Mon-rô",), "community"),
    ("Mark", ("Mac",), "community"),
    ("Twain", ("Tơ-uên",), "community"),
    ("camera", ("ca-mê-ra",), "community"),
    ("clip", ("cờ-líp",), "community"),
    ("font", ("phông",), "community"),
    ("internet", ("in-tơ-nét",), "community"),
    ("laptop", ("láp-tóp",), "community"),
    ("sandwich", ("xăng-guých",), "community"),
    ("robot", ("rô-bốt",), "community"),
    ("rock", ("rốc",), "community"),
    ("show", ("sô",), "community"),
    ("smartphone", ("sờ-mát-phôn",), "community"),
    ("tablet", ("táp-lét",), "community"),
    ("shorts", ("soóc",), "community"),
]

# Ca không khớp, và vì sao. Khoá: chữ. Giá trị: (cách đọc luật đưa ra, lý do). Lý do là một phán quyết chủ sách, một điểm đã quét theo bằng
# chứng (scripts/sweep_english_vi_variants.py), một quy ước của app (luật 1.1: cụm phụ âm luôn tách bằng ơ) hay chỗ nguồn đọc theo chữ / theo
# tiếng khác.
_OWNER_FIXED = "ca riêng của chủ sách 04-10 (bảng ghi đè OWNER), luật không suy rộng"
_AA_O = "/ɑ/ viết o -> o (chủ sách 04-10: boss -> bót; quét: ô khớp thêm 3 dạng nguồn nhưng thua ca chủ sách)"
_EH = "/ɛ/ -> e (chủ sách 04-10: level -> le-vồ); nguồn viết ê"
_CLUSTER = "cụm phụ âm luôn tách bằng ơ, ở đầu từ thanh huyền (mục 1.1; chủ sách 04-10: xờ-kiu, bờ-lếch); nguồn giữ cụm"
_GEM = "p t k sau nguyên âm nhấn chính vừa khép vừa mở âm tiết (chủ sách 04-10: máp-pồ); nguồn không nhân đôi"
_EL = "-əl cuối -> ồ (chủ sách 04-10: máp-pồ, mai-cồ); nguồn viết -tơn"
_FRENCH = "nguồn đọc kiểu Pháp / theo chữ, không theo âm Anh"
_COMMUNITY = "dạng cộng đồng, không phải chuẩn"
EXPLAINED: dict[str, tuple[str, str]] = {
    "Kate": ("Ca-te", _OWNER_FIXED),
    "Pete": ("Pe-te", _OWNER_FIXED + "; tên ngắn khác cùng dạng đọc theo mặt chữ (Zeke -> de-ke)"),
    "guild": ("ghiu", _OWNER_FIXED + "; l cuối sau i -> u (skill -> xờ-kiu) vẫn là luật"),
    "time": ("tam", _OWNER_FIXED + ": t đầu từ giữ t (Tom -> tom, Tina -> ti-na); /aɪ/ + m -> am là luật"),
    "Thomas": ("To-mát", _OWNER_FIXED + ": t đầu từ giữ t (Tom -> tom), th ở đây chỉ của tên này"),
    "Edison": ("E-đi-xơn", _EH),
    "Gillian": ("Gi-li-an", "CMU đọc g mềm /dʒ/ (gi), schwa theo chữ a; Bộ Ngoại giao ghi Ghi- và -ừn (âm tiết khép mang huyền, khác luật 1.2)"),
    "George": ("Giót", _FRENCH + "; r sau nguyên âm bỏ, /dʒ/ cuối -> t (quét: fric_final)"),
    "Virginia": ("Vơ-gi-ni-a", "CMU /ɚ/ -> ơ; nguồn đọc theo chữ (Viếc-)"),
    "Scotland": ("Xờ-cót-lan", _CLUSTER + "; " + _AA_O + "; schwa theo chữ a (-lan), nguồn -len"),
    "Ireland": ("Ai-ơ-lan", "CMU tách /aɪ.ɚ/ thành ai-ơ; nguồn gộp Ai-len"),
    "Charles": ("Chan", _FRENCH + " (ch -> s, r -> c); luật theo âm Anh: ch, r bỏ, l -> n"),
    "New": ("Nu", "CMU (Mỹ) /nuː/ -> nu; nguồn theo âm Anh-Anh /njuː/"),
    "Francisco": ("Phờ-ran-xít-cô", _CLUSTER),
    "Angeles": ("An-gie-lít", "schwa theo chữ e, /ɪ/ -> i (quét); nguồn giơ, lét"),
    "Chicago": ("Si-ca-gô", "/ʃ/ -> s (sh -> s, như Oa-sinh-tơn); nguồn đọc theo chữ ch"),
    "Colorado": ("Co-lơ-ra-đô", _AA_O + "; CMU /ɚ/ -> ơ, nguồn theo chữ lô"),
    "Portland": ("Pót-lan", _FRENCH + " (r -> c: Poóc); luật bỏ r sau nguyên âm (luật 1.3), t khép"),
    "Seattle": ("Xi-át-tồ", _EL),
    "Mississippi": ("Mi-xi-xíp-pi", _GEM),
    "Appalachian": ("A-pa-lây-chan", "nguồn rút gọn (A-pa-lat, bỏ -chian)"),
    "Hawaii": ("Hơ-oai-i", "CMU có schwa đầu từ (hơ) và i cuối; nguồn theo chữ Ha-oai"),
    "Alaska": ("A-lát-ca", "s trước phụ âm khép âm tiết -> t (quét: s_coda); nguồn giữ cụm xc"),
    "Canada": ("Ca-na-đa", "/d/ -> đ; nguồn viết da"),
    "Australia": ("Át-trây-li-a", _CLUSTER + "; au -> a theo chữ, s khép -> t"),
    "Saratoga": ("Xe-ra-tô-ga", "CMU /ɛ/ -> e; nguồn theo chữ Xa-"),
    "Shakespeare": ("Sếch-xơ-pi", "r cuối bỏ (luật 1.3), /ɪɚ/ -> i; nguồn -pia"),
    "Ernest": ("Ơ-nét", "cụm phụ âm cuối giữ một phụ âm (quét: final_cluster); nguồn tách từng phụ âm"),
    "Hemingway": ("He-minh-uây", _EH),
    "Rutherford": ("Ra-thơ-phớt", "/ʌ/ -> a, /θ/ -> th (quét); nguồn Rơ-dơ-pho theo chữ / kiểu Pháp"),
    "Matthew": ("Ma-thiu", "/æ/ -> a (quét: a khớp nhiều hơn e); th không nhân đôi; nguồn Mét-"),
    "Roosevelt": ("Rô-de-ven", "CMU /oʊ/ -> ô, schwa theo chữ e; nguồn Ru-dơ / Rô-sơ"),
    "Romeo": ("Rô-mi-ô", "CMU /iː/ -> i; nguồn theo chữ mê"),
    "Amazon": ("A-ma-don", _AA_O),
    "Cromwell": ("Cờ-ro-mu-ồ", _CLUSTER + "; -wəl cuối -> u-ồ (chủ sách: -əl -> ồ)"),
    "Manchester": ("Man-chét-tơ", "nguồn 1918 (Phạm Quỳnh) đọc kiểu Pháp"),
    "Edinburgh": ("E-đơn-bơ-rô", "nguồn 1918 (Phạm Quỳnh) đọc theo chữ"),
    "London": ("Lăn-đơn", _COMMUNITY),
    "Wayne": ("Uên", _COMMUNITY),
    "Marilyn": ("Me-ri-lin", _COMMUNITY),
    "Monroe": ("Mơn-rô", _COMMUNITY),
    "Mark": ("Mác", _COMMUNITY),
    "Twain": ("Tuên", _COMMUNITY),
    "camera": ("ca-mơ-ra", _COMMUNITY),
    "font": ("phon", _COMMUNITY),
    "sandwich": ("xan-đuýt", _COMMUNITY),
    "robot": ("rô-bót", _COMMUNITY),
    "rock": ("róc", _COMMUNITY),
    "smartphone": ("xờ-mát-phôn", _COMMUNITY),
    "shorts": ("sót", _COMMUNITY),
}
