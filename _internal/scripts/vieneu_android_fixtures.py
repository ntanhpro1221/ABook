"""Shared fixtures for the phone's VieNeu voice (tests/fixtures/vieneu/android/, read by the JVM tests in app/src/test/.../vieneu and by
VieneuOnDeviceTest): what the DESKTOP path (abook/readaloud/vieneu.py + vieneu_engine.py) gives for the same input, so the Kotlin port can be
checked piece by piece - text -> phonemes (sea-g2p), paragraph -> units, phonemes -> Turbo token ids, frame caps, the numpy random streams,
the edge trimming / joining of audio, the WAV bytes, and two whole paragraph clips (Nano bit-exact, Turbo length + loudness).

Runs on the dev machine (runtime venv with sea-g2p + the VieNeu models in the Hugging Face cache; vieneu 3.8.3 only for its voice files):

    runtime/.venv/Scripts/python.exe scripts/vieneu_android_fixtures.py            # rewrite everything
    runtime/.venv/Scripts/python.exe scripts/vieneu_android_fixtures.py --no-clips # skip the two clips (no models needed)

tests/test_vieneu_android.py recomputes the text parts and fails when a fixture is stale.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

from abook.readaloud import names, vieneu
from abook.readaloud import vieneu_engine as ve

OUT = ROOT / "tests" / "fixtures" / "vieneu" / "android"
HF = next((hub for hub in (Path(os.environ.get("HF_HOME", "-")) / "hub", Path.home() / ".cache" / "huggingface" / "hub")
           if (hub / "models--pnnbao-ump--VieNeu-TTS-v3-Turbo").is_dir()), Path.home() / ".cache" / "huggingface" / "hub")
TURBO = HF / "models--pnnbao-ump--VieNeu-TTS-v3-Turbo" / "snapshots" / "61b85e3d937fbbacb387714180e8182823512523" / "onnx_int8"
CODEC = HF / "models--OpenMOSS-Team--MOSS-Audio-Tokenizer-Nano-ONNX" / "snapshots" / "ceff0d0749bfb3fa2d61149794ec6feef0d1e1ae"
NANO = HF / "models--pnnbao-ump--VieNeu-TTS-v3-Nano" / "snapshots" / "aba295eb96a6fa6003ebe417cc1f2802a7adc1dc"

# Written for these fixtures (no book text). Numbers, dates, times, money, units, abbreviations, Roman numerals, foreign words and names,
# addresses, URLs, e-mails, phone numbers, maths, and every kind of punctuation a translated novel uses.
SENTENCES = [
    "Trời hôm nay đẹp quá.",
    "Cô gái đứng bên cửa sổ, lặng lẽ nhìn mưa rơi.",
    "Chiếc thuyền nhỏ trôi chậm giữa dòng sông, mang theo những mùa hè đã xa.",
    "Anh ấy mở cuốn sổ cũ, đọc lại từng dòng chữ mà mẹ đã viết cho mình từ nhiều năm trước.",
    "Ừ.",
    "Hả?",
    "Không!",
    "Thật sao...?",
    "“Cậu định đi đâu vậy?” - cô hỏi.",
    "\"Tớ không biết,\" cậu đáp, \"nhưng tớ sẽ quay lại.\"",
    "Cậu ta - người mà ai cũng sợ - lại đang mỉm cười.",
    "Ầm! Cánh cửa bật tung.",
    "Hừm... để tôi nghĩ đã.",
    "Ba ngày sau (đúng như lời hẹn), họ gặp lại nhau.",
    "Có ba thứ cô cần: nước, lửa và một tấm bản đồ.",
    "Hắn gào lên: \"Chạy đi!!!\"",
    "Cái gì?! Sao lại thế được?",
    "— Em đã ăn cơm chưa?",
    "— Rồi ạ.",
    "Năm 2024, dân số thành phố đạt 9.389.700 người.",
    "Giá vàng hôm nay là 82,5 triệu đồng một lượng.",
    "Cô ấy sinh ngày 12/3/1998 tại Hà Nội.",
    "Cuộc họp bắt đầu lúc 7h30 sáng thứ Hai.",
    "Chuyến bay cất cánh lúc 19:45 ngày 01-10-2026.",
    "Lãi suất tăng 0,5% so với tháng trước.",
    "Nhiệt độ ngoài trời xuống tới -5°C.",
    "Quãng đường dài 12,7 km, đi mất khoảng 45 phút.",
    "Căn phòng rộng 25m2, giá thuê 4.500.000đ/tháng.",
    "Gói hàng nặng 2,3kg và có giá $19.99.",
    "Vé vào cửa là 50.000 VND cho người lớn và 20.000 VND cho trẻ em.",
    "Đội tuyển thắng 3-1 trong trận chung kết.",
    "Trận đấu diễn ra từ ngày 5 đến ngày 9 tháng 7.",
    "Học kỳ II kéo dài từ tháng 1 đến tháng 5.",
    "Thế kỷ XIX là thời kỳ nhiều biến động.",
    "Chương IV bắt đầu ở trang 132.",
    "Vua Louis XIV trị vì nước Pháp rất lâu.",
    "Ông là PGS.TS ngành Vật lý tại ĐH Bách khoa.",
    "UBND TP.HCM vừa ban hành quy định mới.",
    "Văn phòng ở số 15 đường Lê Lợi, Q.1, TP.HCM.",
    "Bạn mang theo bút, thước, compa, v.v. nhé.",
    "CLB bóng đá của trường có 30 thành viên.",
    "Liên hệ qua số 0912 345 678 hoặc 028.3822.1234.",
    "Gửi thư tới hotro@abook.vn trước 17h.",
    "Xem thêm tại https://example.com/tin-tuc/2024.",
    "Tôi vừa mua một chiếc iPhone 15 Pro Max.",
    "Cô ấy rất thích đọc Harry Potter và xem Netflix.",
    "Họ đặt phòng qua Booking.com rồi bay sang Tokyo.",
    "Kirito rút kiếm, còn Asuna thì lùi lại một bước.",
    "Tanaka-san cúi đầu chào mọi người.",
    "Kim Min-jun là học sinh mới chuyển đến.",
    "Tháp Eiffel ở Paris cao khoảng 330 mét.",
    "Anh ấy làm kỹ sư phần mềm cho Google ở Singapore.",
    "Cô dùng Facebook, Zalo và TikTok mỗi ngày.",
    "Bài toán: 3 + 5 = 8, còn 12 x 4 = 48.",
    "Tỷ lệ là 1/3, tức khoảng 33,3%.",
    "Căn bậc hai của 16 là 4.",
    "Phiên bản 2.0.1 sửa nhiều lỗi nhỏ.",
    "Mã đơn hàng là A12-B345.",
    "Lớp 10A1 có 45 học sinh.",
    "Xe buýt số 32 chạy từ bến xe Mỹ Đình.",
    "Quốc lộ 1A dài hơn 2.300 km.",
    "Anh ấy chạy 100m hết 10,5 giây.",
    "Chiếc máy bay Boeing 787 chở được khoảng 250 hành khách.",
    "Công ty có doanh thu 1,2 tỷ USD năm ngoái.",
    "Tốc độ tối đa là 120 km/h.",
    "Dung lượng ổ cứng là 512GB.",
    "Màn hình 6,7 inch, pin 5000mAh.",
    "Tầng 3, phòng 305, nhà B.",
    "Ngày 30/4/1975 là một mốc lịch sử.",
    "Hẹn gặp lại vào 8 giờ tối mai nhé!",
    "Năm học 2025-2026 sắp bắt đầu.",
    "Trong khoảng 10-15 phút nữa tàu sẽ tới.",
    "Bà cụ đã 102 tuổi mà vẫn còn minh mẫn.",
    "Một nghìn lẻ một đêm là câu chuyện nổi tiếng.",
    "Cô đếm: một, hai, ba, bốn, năm.",
    "OK, chúng ta bắt đầu thôi.",
    "Wow, thật không thể tin được!",
    "Hôm nay là thứ 6, ngày 13.",
    "Tôi ở lại Đà Lạt 3 ngày 2 đêm.",
    "Anh trai tôi cao 1m75 và nặng 68kg.",
    "Cửa hàng mở cửa từ 8:00 đến 22:00.",
    "Mẹ dặn: \"Nhớ mang áo mưa.\"",
    "Tiếng chuông vang lên... một lần... hai lần...",
    "Gió thổi vù vù, lá rơi lả tả.",
    "Bầu trời xanh ngắt, không một gợn mây.",
    "Họ im lặng hồi lâu; không ai nói gì.",
    "Cậu bé hỏi: “Tại sao bầu trời lại màu xanh?”",
    "“Vì ánh sáng bị tán xạ,” thầy giáo trả lời.",
    "Ông già ngồi bên hiên, tay cầm điếu thuốc lào.",
    "Con mèo nhảy lên bàn, làm đổ cốc nước.",
    "Ngoài kia, tiếng ve kêu inh ỏi.",
    "Đêm ấy trăng sáng vằng vặc.",
    "Nàng khẽ thở dài, rồi quay mặt đi.",
    "Hắn cười khẩy: \"Ngươi nghĩ ngươi là ai?\"",
    "Thiếu gia, xin người hãy bình tĩnh!",
    "Sư phụ, đệ tử đã hiểu rồi.",
    "Bệ hạ vạn tuế, vạn tuế, vạn vạn tuế!",
    "Kiếm khí tung hoành, cả ngọn núi rung chuyển.",
    "Cấp độ của cô ấy đã lên tới Lv.99.",
    "HP còn 15%, MP chỉ còn 3%.",
    "Hệ thống thông báo: [Nhiệm vụ hoàn thành].",
    "Ma pháp sư hạng S hiếm như lá mùa thu.",
    "Nhật ký ngày 3 tháng 9.",
    "Tập 1: Khởi đầu.",
    "Phần 2 - Chương 15: Cuộc gặp gỡ định mệnh.",
    "P/S: Nhớ trả lời tin nhắn nhé.",
    "Tác giả: Nguyễn Văn A.",
    "Ghi chú (*): số liệu chưa kiểm chứng.",
    "Cô ấy nói tiếng Anh rất giỏi, kiểu \"native speaker\" ấy.",
    "Đây là một deadline cực kỳ quan trọng.",
    "Team mình họp online qua Zoom lúc 9h.",
    "Anh ta là CEO của một startup công nghệ.",
    "Cuốn sách bán được hơn 1 triệu bản.",
    "Từ năm 1945 đến năm 1954.",
    "Khoảng 70-80% số người được hỏi đồng ý.",
    "Mức lương khởi điểm 15 triệu/tháng.",
    "Cân nặng giảm từ 80kg xuống 72kg.",
    "Đã 3 giờ 15 phút sáng mà cô vẫn chưa ngủ.",
    "Giải nhất trị giá 100.000.000 đồng.",
    "Tàu SE1 khởi hành từ ga Hà Nội.",
    "Cô ấy đạt điểm 9,75 môn Toán.",
    "Bài viết có 2.345 lượt thích và 678 bình luận.",
    "Thời hạn nộp hồ sơ là 15/11.",
    "Tháng 12 năm ngoái trời rét đậm.",
    "Cây cầu dài 1.535 mét bắc qua sông Hồng.",
    "Sáng mai, 6 giờ, tập trung ở cổng trường.",
    "Ừm, cũng được.",
    "À, ra là vậy.",
    "Ơ kìa!",
    "Chậc chậc, đáng tiếc thật.",
    "Hì hì, cảm ơn cậu.",
    "Ha ha ha!",
    "Ê, đợi tớ với!",
    "Vâng ạ.",
    "Dạ, con biết rồi.",
    "Thôi được rồi, đi thôi.",
    "Thật là... chẳng biết nói sao nữa.",
    "Anh... anh xin lỗi.",
    "Không, không, không phải thế!",
    "Hãy nhớ: đừng bao giờ bỏ cuộc.",
    "Câu trả lời là... không.",
    "Lần thứ nhất, lần thứ hai, rồi lần thứ ba.",
    "Cô đứng thứ 2 trong lớp.",
    "Anh về đích thứ 3.",
    "Họ sống ở tầng 21 của tòa nhà.",
    "Mùa đông năm 2010 lạnh nhất trong 30 năm.",
    "Tỉ số 2:1 nghiêng về đội khách.",
    "Đây là lần thứ 1000 tôi nói điều này.",
    "Pin còn 5%, cần sạc ngay.",
    "Tốc độ mạng 100Mbps.",
    "Nhà sách mở cửa 24/7.",
    "Hôm qua là ngày 29/02/2024.",
    "Cô ấy cao 1,62m.",
    "Bản đồ tỉ lệ 1:50.000.",
    "Thành phố có 12 quận và 5 huyện.",
    "Anh ấy nói: \"Tôi sẽ đến lúc 5 giờ.\" Rồi đi mất.",
    "Ngôi nhà số 7, ngõ 42, phố Huế.",
    "Thư viện có hơn 50.000 đầu sách.",
    "Giảm giá 30% cho đơn từ 500k.",
    "Hôm nay mình đi cafe nhé.",
    "Trà sữa trân châu size L giá 45k.",
    "Bạn đã xem phim Avengers: Endgame chưa?",
    "Bài hát \"Happy Birthday\" vang lên.",
    "Họ đi du lịch New York vào mùa thu.",
    "Ông ấy là giáo sư ở Đại học Harvard.",
    "Cô bé tên là Alice, đến từ London.",
    "Ryuu no Kiseki là tên một trò chơi cũ.",
    "Yamada Taro luôn đến lớp sớm nhất.",
    "Seo-yeon và Ji-ho là đôi bạn thân.",
    "Thành phố Seoul về đêm rất đẹp.",
    "Tôi học tiếng Nhật được 2 năm rồi.",
    "Một chiếc xe Honda SH đỗ trước cửa.",
    "Anh ấy lái chiếc Toyota Camry màu đen.",
    "Mã PIN gồm 4 chữ số.",
    "Hãy nhập mật khẩu và nhấn Enter.",
    "Lỗi 404: không tìm thấy trang.",
    "File báo cáo dạng PDF nặng 3,5MB.",
    "Ảnh chụp bằng máy Canon EOS R5.",
    "Bóng đèn LED 9W tiết kiệm điện.",
    "Vitamin C rất tốt cho sức khỏe.",
    "Nước sôi ở 100°C.",
    "Công thức nước là H2O.",
    "Tốc độ ánh sáng khoảng 300.000 km/s.",
    "Trái Đất cách Mặt Trời khoảng 150 triệu km.",
    "Năm 2050, dân số có thể vượt 10 tỷ người.",
    "Khoảng cách giữa hai cây là 2-3m.",
    "Quyển 3, trang 45-47.",
    "Điều 5, khoản 2 của luật quy định rõ.",
    "Theo Nghị định 100/2019/NĐ-CP.",
    "Số hiệu chuyến bay là VN254.",
    "Cô ấy đeo kính cận 2,5 độ.",
    "Đôi giày size 39 vừa khít.",
    "Áo cỡ XL hơi rộng.",
    "Từ 1/1/2025, quy định mới có hiệu lực.",
    "Kỳ nghỉ Tết kéo dài 9 ngày.",
    "Lúc 0h ngày 1/1, pháo hoa rực sáng.",
    "Còn 3 ngày nữa là Giáng sinh.",
    "Ngày mai, 14/2, là lễ Tình nhân.",
    "Ông nội tôi sinh năm 1930.",
    "Em gái tôi học lớp 5.",
    "Cả lớp có 40 bạn, trong đó 22 nữ.",
    "Anh ấy được 8/10 điểm.",
    "Trận đấu kết thúc với tỉ số 0-0.",
    "Giải đấu có 32 đội tham gia.",
    "Cô về nhì trong cuộc thi hát.",
    "Bức tranh được bán với giá 2,5 triệu USD.",
    "Những năm 90 của thế kỷ trước.",
    "Thập niên 1980 là thời của băng cát-xét.",
    "Anh sinh vào khoảng giữa những năm 70.",
]

# Paragraphs for the unit packing (several sentences; long ones are cut at commas, then at spaces).
PARAGRAPHS = [
    "Trời hôm nay đẹp quá. Cô gái đứng bên cửa sổ, lặng lẽ nhìn mưa rơi. Anh ấy về nhà rất muộn hôm ấy.",
    "Ừ. Cô gái đứng bên cửa sổ, lặng lẽ nhìn mưa rơi suốt cả buổi chiều hôm ấy.",
    ("Khi ánh đèn trong phòng vụt tắt, cả ngôi nhà chìm vào bóng tối, chỉ còn tiếng đồng hồ gõ nhịp đều đặn như một nhịp tim đang chờ đợi. "
     "Cô ngồi im, không dám thở mạnh, vì sợ rằng chỉ một tiếng động nhỏ thôi cũng đủ để phá vỡ sự yên lặng mong manh ấy. Rồi trời sáng."),
    "“Cậu định đi đâu vậy?” - cô hỏi. “Đi thật xa,” cậu đáp, “xa đến mức không ai tìm thấy.” Cô không nói gì nữa.",
    "Năm 2024, dân số thành phố đạt 9.389.700 người; diện tích 2.095 km2; mật độ khoảng 4.481 người/km2. Con số này tăng 2,3% so với năm trước.",
    ("Một hai ba bốn năm, sáu bảy tám chín mười, mười một mười hai mười ba mười bốn mười lăm mười sáu mười bảy mười tám mười chín hai mươi "
     "hai mốt hai hai hai ba hai bốn hai lăm hai sáu hai bảy hai tám hai chín ba mươi ba mốt ba hai ba ba ba bốn ba lăm ba sáu ba bảy ba tám ba chín."),
    "Ầm! Rầm! Cánh cửa bật tung. Hắn bước vào.",
    "Hừm... Để xem nào... À, đây rồi! Tìm thấy rồi!",
    ("Sư phụ nói: \"Kiếm pháp không nằm ở tay, mà nằm ở tâm.\" Đệ tử cúi đầu, im lặng suy ngẫm hồi lâu, rồi mới chậm rãi đáp: "
     "\"Đệ tử đã hiểu.\""),
    "Cô ấy sinh ngày 12/3/1998 tại Hà Nội, tốt nghiệp ĐH Bách khoa năm 2020, rồi làm kỹ sư cho một công ty ở TP.HCM.",
    "A.",
    "Một câu rất ngắn. Hai.",
    # Roman numerals after a common noun are read as numbers (vieneu.spoken_tokens); "I am", abbreviations and sentence-initial "I" stay.
    "Trường Phổ thông I, Trường Phổ thông II và Thế chiến II. Benedict III lên ngôi ở chương XIV.",
    "I. Mở đầu",
    "Chương I, thế kỷ X và Phần V; ông X, nhân vật X, tia X, điểm V, loại I. Vua Louis X lên ngôi, Hoàng đế Napoleon I thì không.",
    "I am here. Xong. I am đây. Anh ấy là MC của CV VIP.",
    # Marks sea-g2p reads as words (vieneu.reading_marks): "~" , English thousands, <angle brackets>, a lone slash between two words.
    "Hmm~ Har~kun, ưm~~~ được rồi~! Ô ~, vậy sao. Từ 10,000 ~ 15,000 đồng, khoảng 3~5 người, ~50 người nữa, *Kà-ran*~ ừ.",
    "Cô có 500,000 đồng và 100,000 yen. Trên bảng ghi 1,419 / 3,419 rồi 1,5 và 3,25 và 1,500 và 1.234,567 và 12,3456.",
    "Mặt dây này tên là <Angel Wings> đó. Dùng <khiên> đi, phần IV <Hạ> thôi. Cô thấy 3 < 5 và <3 và >:) và <50/50>. Kỹ năng 《Xiềng Xích》 và 〈Ánh Sao〉.",
    "Bị 【Đóng băng / yếu】 rồi. HP: 5813 / 5813, tỉ lệ 3/5 và 15/8, còn mở/đóng thì để nguyên.",
    # TN lượt 3 (04-10): số (phân số bé, khoảng, số liền, x2, đô la), mặt cười, dấu *, gạch ngang dính chữ, khung hệ thống, dấu câu CJK, ngoặc nhọn dài / số / không đóng.
    "Lớp 1-1 và 1-3-1, dài 3-4000 từ, nặng 3/5 chai, thanh 180/300, sự kiện x2, giá ($1 USD) hay $5, cả 9-5, 01-10-2026, 090-123-4567, 3-1.",
    "*từ* (*) đ* b*** orz :3 nào >:)! <3 vl -_- ;) xong.",
    "Babi—người đã. Nên— Cảm ơn. Làm—” rồi nha-- ừ. Tên là【Song Kiếm Thuật】!” Bất lợi  【Đóng băng】. Của 【Kho】rất gọn. Tiến hóa: [Bậc 1] xong [1] và kỹ năng [Hỏa] nữa.",
    "Đi，nhà ta. 734：Chúng ta nên làm gì？ Xong！ Thế。",
    "Tên <game> <50/50>. Nghĩ <mình vẫn ổn mà, chỉ hơi mệt sau một ngày dài…thôi kệ> hết. < Thật Tuyệt vời. Còn x < y.",
    "Ý tôi chỉ có vậy.”(GM) xong. “Ahhhh…Em hiểu rồi…Senpai.” Thế chiến II—thời kỳ. Bất lợi III】, DP?”…Tốn 20 DP.",
]

# Paragraphs read with a book origin (abook/readaloud/names.py): Japanese / Korean names read by the romanization rules, English names and Vietnamese
# words left to sea-g2p, shouts and capitals untouched. Names are written for these fixtures (no book text).
NAME_PARAGRAPHS = [
    ("Haruto-kun, Kyouko-san đã đến. “Yamato!” Kate hỏi Mike, còn Rose và Hana thì cười. Anne, Emma và Rika cũng ở đó.", "ja"),
    ("Hoa nói: Tôi là AI. Level 5, Dungeon. Aaaa! Fukushima và Tōkyō, Kôbe, Shin'ichi, Hajime~ rồi (Sakura).", "ja"),
    ("Seo-yeon và Ji-ho là đôi bạn. Kim Min-jun đến Seoul cùng Park, Geun-hye và Chang-dok.", "ko"),
    ("Haruto-kun, Kyouko-san đã đến. Kate hỏi Mike, còn Rose và Hana thì cười.", "ko"),
    ("Haruto-kun, Kyouko-san đã đến. Kate hỏi Mike, còn Rose và Hana thì cười.", None),
]
# Paragraphs for the reading-only sounds (abbreviations.py letter names, shouts.py stretched sounds and Latin interjections, names.honorific_reading suffixes): read with
# and without a book origin. Written for these fixtures (no book text).
SOUND_PARAGRAPHS = [
    ("Chỉ số HP và MP của cô còn 15%. NPC đứng cạnh SSR, VIP, ID, OK, TV, GOTY. LINE, MAX, YES, TIP, BAKA, HAHA. 10KG, LV5, A12-B, TP.HCM, PGS.TS.", None),
    ("CÚT ĐI, AI ĐÓ! ONII-CHAN LO LẮNG CHO CON KÌA. Hạng AAA và AAA+++, rồi SSS. Chương III, XXX. Ôi, XXX! IIII.", None),
    ("Aaaa, Haaa… Uuu! Viiiiii, rồiiiii, tớơơơơ, chứứứứ, quẹooo, đâuuuu. Khônggg, Emmmm, Hầyyy, rấtttt, Oáppp~", None),
    ("Hmmm, Ummm…Ý bạn; Haaa…..cuối; màaaa—nếu; Oáppp~....Hầy; -EH....nhìn. Xoạttt- *Viiiii*- ‘nhaaa’ (Hmmm)", None),
    ("Kyaaa! Uwaaa! Yaaa! Aー, Haー, EMMMMMMM, AAAA, Weisss, Onii-channnn, zzz, Cccchhhhàaaaaaoooo.", "ja"),
    ("Umm, Ugh, Boom, Oh, Hmm, Ahhhh, Oooh, Hm, UGH.", "ko"),
    ("Ariel-sama, Mary-san, Zeros-sensei, Goblin Slayer-san, Sora-sama, Hinata-sama, Haruto-kun, Tanaka-senpai, Kate-san, sĩ-sama, thần-chan.", None),
    ("Ariel-sama, Mary-san, Zeros-sensei, Sora-sama, Haruto-kun, onee-chan, ojou-sama, Tsukinoki-senpai.", "ja"),
    ("Oppa, unnie! hyung noona. Hyung-nim, Soleum-ssi, Minho-oppa, Seo-yeon-ssi, Mary-san.", "ko"),
    ("Oppa, unnie! hyung noona. Hyung-nim, Soleum-ssi, Minho-oppa, san, sama, tan, nee, nii.", None),
    # TN lượt 3: nói lắp, tiếng cười, thán từ mới, kéo nhiều chỗ, Lv, từ mượn quen, đơn vị tiền, tên có chữ O đầu
    ("T-tôi không biết. C-Chuyện đó... Ng-ngài có chắc. [Kh- Không phải thế. “T-Tsukinoki-senpai cho tôi quá giang. E-em muốn. Hà-Hà đến. “……T-, tức là sao???", None),
    ("T-Tsukinoki-senpai và A-anime. K-Kenji, Đ-Điều này.", "ja"),
    ("Haha, Hahaha, Hehe, Fufu~, Hihi, Hm, Huh, Hic, Ooh, Urgh. HAHA. Cccchhhhàaaaaaoooo sssssáaaannnngggg BAAAAAMMMMM.", None),
    ("Lv 5, Lv.15] Lvl.1 LV5, Lv ơi, LVL. Level 7, lv 40.", None),
    ("Sofa, anime, Ninja, manga, Samurai (bento) kimono sake miso dango takoyaki okonomiyaki senpai Ara ara, Umu eroge tsukkomi. Video, logic, piano, violin, sandal, vali, robot, gorilla.", None),
    ("Sofa, anime, Ninja, manga. 3 triệu won, 100 yen, 5 kwan, won rồi.", "ko"),
    ("Otsuki-san, Okayama, Onii-sama, Ojou-sama, Otaku-kun.", "ja"),
    # TN lượt 4: gọi viết hoa cả, danh xưng viết tắt, mũi tên chữ
    ("ONII-CHAN, ONII-CHAN LO LẮNG! “NEE-SAN!” và OPPA, ARIEL-SAMA. Kiểm tra SAN và SENPAI.", None),
    ("ONII-CHAN, ONII-CHAN LO LẮNG! “NEE-SAN!” và OPPA, ARIEL-SAMA.", "ja"),
    ("Mr. Lyle đến, Mrs. Smith, Ms. Lee và Dr. Stone. Mục tiêu của mr.lyle thôi, “Mr.Lyle” và (dr.Stone). St. Louis và Dr Stone. Main St. dài, Dr. nào.", None),
    ("HP: 1780 --> 1940. A -> B, C => D, E → F. 1780->1940 và A-->B. A <- B và C ← D, E<-F. -> Bước tiếp. A <-> B, x <= 5, a -> b <- c.", None),
    # TN lượt 5: mũi tên "thành" (đổi giá trị) hay "đến" (hướng đi / khoảng / trình tự) tuỳ ngữ cảnh
    ("Lv 5 -> Lv 6. Giá 100 -> 200. Cấp D => C. Nghề: Tân Thủ -> Pháp Sư. Cân lực : 22000 ⇒ 66000. Họ bay Tokyo → Osaka lúc 8h -> 10h. Bước 1 -> Bước 2, trang 3 -> 5. HP 10%->20%.", None),
]
JA_NAMES = "Haruto Yuki Sakura Kyouko Takeshi Hiroshi Akira Kenji Yamato Naoki Satoshi Ayaka Reiji Tsubasa Shinji Kaori".split()
KO_NAMES = "Si-eun So-hye Hwi-min Seo-ram Deok-gu Kang-ho Ha-jin Joo-seon Min-jun Seo-yeon Ji-ho Geun-hye".split()
WEST_NAMES = "Alberu Eruhaben Henituse Harol Witira Cale Mirabelle Ruel Alon Gideon Damien Aurora Nora Stella".split()


def _name_text(names: list[str], rounds: int) -> str:
    return " ".join(f"{name} nói với {names[(i + 1) % len(names)]}." for _ in range(rounds) for i, name in enumerate(names))


# Cases for `names.book_origin`: (list of chapter texts, sample or None = the default of twelve chapters). Only the first chapters count; a book of Vietnamese words or too few names says nothing.
ORIGIN_CASES = [
    ([_name_text(JA_NAMES, 4)], None),
    ([_name_text(JA_NAMES, 4)] * 3, None),
    ([_name_text(KO_NAMES, 6)], None),
    ([_name_text(WEST_NAMES, 5)], None),
    ([_name_text(JA_NAMES[:4], 3)], None),
    ([_name_text(JA_NAMES[:12], 1)], None),
    ([_name_text(WEST_NAMES, 2) + " " + _name_text(JA_NAMES[:6], 2)], None),
    (["Hoa và Nam đi chợ. Mai nói với Ba rằng Tôi không đi. " * 60], None),
    ([_name_text(WEST_NAMES, 1)] * 40 + [_name_text(JA_NAMES, 40)] * 5, None),
    ([_name_text(WEST_NAMES, 1)] * 40 + [_name_text(JA_NAMES, 40)] * 5, 45),
    # honorifics beside romaji names lower the share needed: a Japanese book with many Western-style names
    ([_name_text(WEST_NAMES * 2 + JA_NAMES, 4) + " " + (" ".join(f"{name}-san nói." for name in JA_NAMES[:4]) + " ") * 8], None),
    ([_name_text(WEST_NAMES * 2 + JA_NAMES, 4) + " " + (" ".join(f"{name}-san nói." for name in WEST_NAMES[:4]) + " ") * 8], None),
    ([_name_text(WEST_NAMES * 2 + JA_NAMES, 4) + " " + (" ".join(f"{name}-dono nói." for name in JA_NAMES[:2]) + " ") * 8], None),
]

# Clips made on the desktop for VieneuOnDeviceTest: a paragraph of two sentences that is two units for Nano (140 chars) and one for Turbo.
CLIP_TEXT = ("Chiếc thuyền nhỏ trôi chậm giữa dòng sông, mang theo những mùa hè đã xa. "
             "Anh ấy mở cuốn sổ cũ, đọc lại từng dòng chữ mà mẹ đã viết cho mình từ nhiều năm trước.")


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_bytes((json.dumps(data, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def _sha(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _b64_i16(array: np.ndarray) -> str:
    return base64.b64encode(np.asarray(array, dtype="<i2").tobytes()).decode()


def text_fixture() -> dict:
    """Phonemes (sea-g2p via vieneu_engine.phonemize), units, frame caps, syllables and seeds - pure text, no models."""
    from sea_g2p import punc_norm

    normalizer = ve._sea().normalizer
    g2p = [{"sentences": [text], "phonemes": ve.phonemize([text])} for text in SENTENCES]
    normalize = [{"text": text, "plain": normalizer.normalize(text, punc_norm=False), "punc": normalizer.normalize(text, punc_norm=True),
                  "puncNorm": punc_norm(text)} for text in SENTENCES]
    units = []
    for text, origin in [(text, None) for text in PARAGRAPHS + [CLIP_TEXT]] + NAME_PARAGRAPHS + SOUND_PARAGRAPHS:
        for limit in (256, 140, 40):
            toks, parts = vieneu.units(text, limit, origin)
            rows = [{"first": unit.first, "last": unit.last, "pieces": unit.pieces, "phonemes": ve.phonemize(unit.pieces)} for unit in parts]
            units.append({"text": text, "max": limit, "tokens": len(toks), "units": rows, **({"origin": origin} if origin else {})})
            g2p += [{"sentences": row["pieces"], "phonemes": row["phonemes"]} for row in rows if len(row["pieces"]) > 1]
    phonemes = sorted({case["phonemes"] for case in g2p if case["phonemes"]})
    frames = [{"phonemes": ph, "syllables": ve.phoneme_syllables(ph), "cap": ve.max_expected_frames(ph)} for ph in phonemes]
    frames += [{"phonemes": ph, "syllables": ve.phoneme_syllables(ph), "cap": ve.max_expected_frames(ph)}
               for ph in ["", "a", "ʔa1 ʔa1.", "<|emotion_3|>", "<|emotion_3|> ʔa1.", "<en>ˈhɛloʊ</en> ʔa1."]]
    seeds = [{"parts": parts, "seed": vieneu.seed_of(*parts)} for parts in
             [["turbo", "Ngọc Huyền", "Trời hôm nay đẹp quá."], ["nano", "Adam", "Ừ."], ["nano", "Đức Trí", CLIP_TEXT], ["turbo", "", ""]]]
    origins = []
    for texts, sample in ORIGIN_CASES:
        shares = names.origin_shares(*names.scan_names(texts[:sample or names.SAMPLE_CHAPTERS]))
        origins.append({"texts": texts, **({"sample": sample} if sample else {}), "origin": names.book_origin(texts, **({"sample": sample} if sample else {})),
                        **{key: shares[key] for key in ("total", "names", "ja_names", "ko_names", "honorific", "honorific_names")}})
    return {"sea_g2p": "0.9.1", "sentences": len(SENTENCES), "g2p": g2p, "normalize": normalize, "units": units, "frames": frames, "seeds": seeds,
            "origins": origins}


def tokenizer_fixture(text: dict) -> dict:
    """Turbo token ids of every phoneme string of the text fixture (ByteBPE of tokenizer.json, checked against `tokenizers` by the desktop tests)."""
    shutil.copyfile(TURBO / "tokenizer.json", OUT / "turbo_tokenizer.json")
    bpe = ve.ByteBPE(TURBO / "tokenizer.json")
    extra = ["Hello world", "naïve café", "  spaces  and\ttabs\n", "123 4567 89", "<|emotion_3|> ʔa1", "don't you'll we've", "ﬁ ①"]
    return {"cases": [{"text": ph, "ids": bpe.encode(ph)} for ph in [row["phonemes"] for row in text["frames"]] + extra]}


def rng_fixture() -> dict:
    """numpy streams the voices draw from: RandomState(seed).random_sample (Turbo sampling) and default_rng(seed).standard_normal (Nano noise)."""
    mt = [{"seed": seed, "values": np.random.RandomState(seed).random_sample(12).tolist()} for seed in (0, 1, 1000, 2**31 + 7, 4294967295)]
    pcg = []
    for seed in (0, 1, 2000, 123456789, 4294967295, 2**40 + 3):
        draws = np.random.default_rng(seed).standard_normal((1, 144, 300))
        pcg.append({"seed": seed, "first": draws.reshape(-1)[:8].tolist(), "count": int(draws.size),
                    "float32Sha256": _sha(draws.astype(np.float32).astype("<f4"))})
    uniform = [{"seed": seed, "values": np.random.default_rng(seed).random(6).tolist()} for seed in (0, 77)]
    return {"randomState": mt, "standardNormal": pcg, "uniform": uniform}


def audio_fixture() -> dict:
    """Edge silence, trim + fade, joins, speech bursts, babble check and WAV bytes on small synthetic signals (int16 / 32768 exactly)."""
    rng = np.random.default_rng(5)
    rate = 24_000

    def burst(seconds: float, level: float) -> np.ndarray:
        n = int(seconds * rate)
        tone = np.sin(2 * np.pi * 220 * np.arange(n) / rate) * level + rng.standard_normal(n) * level * 0.1
        return tone

    def quiet(seconds: float) -> np.ndarray:
        return rng.standard_normal(int(seconds * rate)) * 0.0004

    signals = {
        "speech": np.concatenate([quiet(0.12), burst(0.25, 0.3), quiet(0.05), burst(0.2, 0.2), quiet(0.2)]),
        "two": np.concatenate([quiet(0.03), burst(0.15, 0.25), quiet(0.3)]),
        "three": np.concatenate([quiet(0.01), burst(0.1, 0.1), quiet(0.12), burst(0.1, 0.12), quiet(0.12), burst(0.1, 0.1), quiet(0.02)]),
        "silent": quiet(0.2),
        "loud": np.clip(burst(0.1, 1.4), -1.2, 1.2),
    }
    cases = {}
    for name, signal in signals.items():
        quantised = np.clip(np.round(signal * 32768), -32768, 32767).astype(np.int16)
        wav = (quantised.astype(np.float32) / np.float32(32768))
        lead, tail = ve.edge_silence(wav, rate)
        trimmed = ve.trim_and_fade(wav, rate)
        cases[name] = {"pcm": _b64_i16(quantised), "edge": [lead, tail], "trimmedLength": int(trimmed.size), "trimmedSha256": _sha(trimmed.astype("<f4")),
                       "bursts": ve.count_speech_bursts(wav, rate), "wavSha256": hashlib.sha256(vieneu.wav_bytes(wav, rate)).hexdigest()}
    joins = []
    for names, pauses in ((["speech", "two", "three"], [0.5, 0.3]), (["silent", "two"], [0.5]), (["two"], []), (["three", "speech"], [0.7])):
        chunks = [np.clip(np.round(signals[n] * 32768), -32768, 32767).astype(np.int16).astype(np.float32) / np.float32(32768) for n in names]
        joined, spans = ve.join(chunks, rate, pauses)
        joins.append({"chunks": names, "pauses": pauses, "length": int(joined.size), "spans": [list(span) for span in spans], "sha256": _sha(joined.astype("<f4"))})
    babble = []
    for name, phonemes, cap, frames in (("two", "ʔa1.", 13, 5), ("three", "ʔa1.", 13, 5), ("three", "ʔa1 ʔa1 ʔa1 ʔa1.", 40, 30),
                                        ("speech", "ʔa1 ʔa1.", 18, 17), ("silent", "<|emotion_3|>", 13, 12)):
        wav = np.clip(np.round(signals[name] * 32768), -32768, 32767).astype(np.int16).astype(np.float32) / np.float32(32768)
        bad, syl, bursts, length = ve.babble_suspect(wav, rate, phonemes, cap, frames)
        babble.append({"signal": name, "phonemes": phonemes, "cap": cap, "frames": frames, "result": [bool(bad), int(syl), int(bursts), int(length)]})
    return {"rate": rate, "signals": cases, "joins": joins, "babble": babble, "gaps": ve.GAP_SECONDS}


def clip_fixture() -> dict:
    """The desktop's clip of CLIP_TEXT for one voice of each tier (vieneu.VieneuProvider, default sampling)."""
    import vieneu as package

    voices = Path(package.__file__).parent / "assets"
    installed = vieneu.Installed(voices=voices, turbo=(TURBO, CODEC), nano=NANO, aligner=False)
    provider = vieneu.VieneuProvider(lambda: installed)
    out = {"text": CLIP_TEXT, "clips": []}
    for tier in ("nano", "turbo"):
        presets = provider.presets(tier, installed)
        name = next(iter(presets))
        audio, rate, _toks, parts, spans = provider._speak(tier, name, installed, presets[name], CLIP_TEXT)
        made = provider.synthesize(CLIP_TEXT, f"{tier}/{name}")
        units = []
        for unit, (start, stop) in zip(parts, spans):
            piece = audio[start:stop]
            units.append({"pieces": unit.pieces, "phonemes": ve.phonemize(unit.pieces), "seed": vieneu.seed_of(tier, name, " ".join(unit.pieces)),
                          "span": [start, stop], "rms": float(np.sqrt(np.mean(np.square(piece, dtype=np.float64)))) if stop > start else 0.0})
        out["clips"].append({"voice": f"vieneu:{tier}/{name}", "tier": tier, "rate": rate, "samples": int(audio.size), "durationMs": made.duration_ms,
                             "float32Sha256": _sha(audio.astype("<f4")), "wavSha256": hashlib.sha256(made.audio).hexdigest(),
                             "voiceOrder": list(presets), "units": units})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-clips", action="store_true", help="skip the two desktop clips (needs the VieNeu models + vieneu 3.8.3)")
    args = parser.parse_args()
    text = text_fixture()
    _write("text.json", text)
    _write("tokens.json", tokenizer_fixture(text))
    _write("rng.json", rng_fixture())
    _write("audio.json", audio_fixture())
    small = OUT / "small.npz"  # np.savez stamps the zip with the time: written once, so the fixture does not change on every run
    if not small.exists():
        np.savez(small, table=np.arange(12, dtype=np.float32).reshape(3, 4) / np.float32(8), eps=np.float32(1e-5),
                 wide=np.arange(5, dtype=np.float64))
    if not args.no_clips:
        _write("clips.json", clip_fixture())
    print(f"{len(SENTENCES)} sentences, {len(text['g2p'])} phoneme cases, {len(text['units'])} unit cases -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
