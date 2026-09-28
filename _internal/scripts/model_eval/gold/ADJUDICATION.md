# Sổ phân xử đáp án chuẩn

Mỗi tranh chấp giữa hai người gán nhãn (A = Claude, B = agent review) và kết luận. Quy tắc: `docs/GOLD_GUIDE.md`.

## Vòng 1 - làm mù (20-09 00:0x): B gán độc lập 378 (cuốn 2) và 248 (cuốn 1)

Độ khớp trước phân xử, trên 94 câu có người nói: người nói ưu tiên trùng 97,9%, tập đủ-điểm giao nhau 100%; loại đoạn
100% (248/248); giới tính 100% (81/81); cảm xúc ưu tiên trùng 89,1%, tập giao nhau 100%.

| câu | A | B | kết luận | lý do |
|---|---|---|---|---|
| 378:1, 48, 87, 91, 93, 95 | chỉ tên | tên + `NPC*~` | theo B | lúc nói, người ấy chỉ được gọi "đại trưởng lão"/ẩn danh; tên ở ngay đoạn kề - quy tắc 5 |
| 378:4, 33, 116, 117 | `NPC*,UNKNOWN` + ... | bỏ `UNKNOWN` | ~~giữ A~~ **bị vòng 2 thay**: `UNKNOWN~` | (cũ) câu cả đám: `UNKNOWN` đủ điểm |
| 378:61 | `NPC*,UNKNOWN` | + 4 người có tên đủ điểm | nửa đường | "Tất cả người lùn... hét lớn": không ai dẫn đầu, người có tên chỉ nửa điểm - quy tắc 6 |
| 378:79 "Aaaaah!" | `NPC*,UNKNOWN` | + `NARRATOR~` | theo B | tiếng thét là của nhân vật; người kể đọc thì chấp nhận được nhưng kém |
| 378:113 | thiếu Myrna, Quinns | có | theo B | câu 112 nêu tên họ đang cầu nguyện |
| 248:13 | `SAMAEL` | + `JULIANA~` | giữ A | câu 14 "Ngay cả Juliana cũng lộ vẻ bối rối" - câu 13 chưa phải của cô; cả B cũng chọn Samael |
| 248:32, 57, 72 | `NARRATOR` | + nhân vật `~` | giữ A | loại bị khoá lời kể; host ép NARRATOR nên nửa điểm nhân vật không bao giờ xảy ra |
| 248:48 "À, ra là..." | `N` | `N,T` + SAMAEL | theo B | câu tự nhủ trực tiếp - quy tắc 4 |
| 248:129 | `N,T` + SAMAEL | `N` | giữ A | cùng quy tắc 4 |
| 248:27..65 Ray/Vince | tên + tên đầy đủ | chỉ tên | giữ A | bí danh cùng người - quy tắc 10 |
| 248:77 "Samael, nằm xuống!" | âm lượng normal trước | loud | theo B | tiếng hét |
| 248:79, 101 "Rầm—!!" | surprised,neutral | excited | nới A | thêm excited |
| 248:81 "Á hự!" | sad trước | không có sad | nới A | surprised lên đầu; sad giữ ở cuối (đau) |
| 248:92 | nhịp normal trước | fast | giữ A | cả hai hợp lý, tập A đã có fast |

## Vòng 2 - soát đối kháng (20-09 00:1x): B đọc đáp án của A cho 351, 363, 381 và tìm lỗi

B không tìm ra người nói CHÍNH sai ở câu nào; ~28 câu tranh chấp về điểm của lựa chọn phụ, thứ tự loại, cảm xúc.

| câu | B đề nghị | kết luận | lý do |
|---|---|---|---|
| mọi câu có manh mối (41 dòng, mọi chương) | `UNKNOWN` -> `UNKNOWN~` | theo B | prompt dự án: UNKNOWN chỉ khi không có dấu hiệu gì |
| 381:13 | thêm MYRNA đủ điểm | theo B | câu 12: "dẫn dắt **Myrna** và những người lùn khác đáp lại" |
| 381:9, 378:4 | HAROLD (và MYRNA ở 378:4) đủ điểm | theo B | được nêu tên trong lời dẫn của câu cả đám |
| 381:17, 21, 31 | thêm MYRNA~, QUINNS~ | theo B | có mặt, không được nêu trong lời dẫn |
| 351:67 "mỉm cười" | bỏ MORRIS | theo B | từ trong ngoặc là mô tả, không phải lời |
| 351:13, 15, 17 | người gốc của từ -> nửa điểm | theo B | đổi giọng giữa một câu kể là sai |
| 381:79 khế ước | tác giả (thần = LUCIEN) đủ điểm, bỏ Augustus/Harold | theo B | tác giả văn bản; người ký không đọc to |
| 381:38 tựa sách | NARRATOR đủ điểm | theo B | văn bản trích |
| 363:69-78, 80 | `T,N` -> `N,T` | theo B | loại thật đứng trước; chính chú thích của A nói đây là lời kể |
| 363:68 | NARRATOR đủ điểm | theo B | đoạn nửa nghĩ nửa kể, loại N được chấp nhận |
| 363:42-43 | thêm neutral, happy; cường độ 1-2 | theo B | câu 40-41: hắn vừa "dằn được cảm xúc xuống" |
| 363:23 | thêm afraid | theo B | câu nói về nỗi sợ cơn giận của Fernando |
| 381:63 | `N,T` + NPC*~ | theo B (điểm yếu) | tiếng lòng chung của đám người lùn, như 363:48 |
| 381:11, 15, 19, 28 giọng "thần" | `NPC*` -> `NPC*~` | **giữ A** | thần chỉ xuất hiện trong arc này; một giọng NPC riêng, nhất quán trong chương là cách đọc đúng, không kém gán tên |

A tự áp cùng quy ước cho chương B chưa soát: 344:68, 93 (tựa luận án Chloe chỉ nhìn thấy) và 344:72, 95, 345:27, 38 (câu
trích luận án: tác giả Lucien đủ, người đọc ~); 050:61-62 (lời nhạc chuông: NPC*~).

## Vòng 3 (20-09 00:2x): B làm mù 344, 345; soát đối kháng 346, 347, 199, 020, 050

Làm mù 344/345 (74 câu có người nói): người nói ưu tiên trùng 98,6%, tập chấp nhận 100%; cảm xúc ưu tiên 94,8%, giao 100%.
Soát 5 chương: không có người nói chính sai; 28 câu tranh chấp.

| câu | kết luận | lý do |
|---|---|---|
| 381:11, 15, 19, 28 giọng thần | **A thua**: `NPC*` -> `NPC*~` | B dẫn chứng: thần nói lại ở chương 460 (585, 793 lộ là Lucien); nhãn NPC chỉ sống trong một chương (`_scope_local_speaker`, hai lượt gộp chỉ cùng chương) nên mỗi chương một giọng |
| 344:44, 345:15 | người đọc to + NARRATOR đủ, tác giả `~` | văn bản đọc to bằng giọng người đọc - quy tắc 7 mới |
| 344:68, 93 | + LUCIEN đủ | tiêu đề chỉ được nhìn thấy: tác giả đủ điểm |
| 344:75, 76 | + LUCIEN~ | câu của Lucien vang lại trong đầu Chloe |
| 344:82, "Aaaaah!" | + NARRATOR~ | như 378:79 |
| 344:4 | `N,T` + ERIC | tiếng lòng của Eric ("Tốc độ khiếp luôn!") |
| 345:84-85 kết luận hội đồng | `NPC*~` | người viết không tên - quy tắc 7 |
| 347:20 | NARRATOR đủ, người thì thầm `~` | **A sai**: cụm trích nằm giữa câu kể - quy tắc 8 |
| 346:78 Lauren, 347:27 Larry, 050:64/67/70 người gọi điện | + `NPC*~` | quy tắc 5 áp đều cho người chưa xác định lúc nói |
| 346:46 | + LAZAR~, HEIDI~, SPRINT~ | có mặt, không được nêu trong lời dẫn - quy tắc 6 |
| 347:48-51 thư Douglas | + DERRICK DOUGLAS (bí danh), HELLEN~ (người đọc) | quy tắc 7, 11 |
| 050:32 | bỏ CHÚ LƯU ĐẠT | prompt dự án cấm tiền tố vai vế |
| 346:38, 199:88, 103, 104, 020:41-43 | `N,T` + người nghĩ | câu tự nhủ trực tiếp - quy tắc 4 |
| 346:39 | **giữ A** (`N`) | câu giải thích của người kể, không phải tiếng lòng |
| 020:19 | **giữ A** (`N`) | có lời dẫn "Chu Mặc tán thưởng" - là lời kể |
| 346:5, 14, 199:86 | cường độ 1-3 -> 1-2 | văn bản nói rõ không phải cao trào ("có chút phấn khích") |
| 199:111, 137, 050:26, 29 | + whispering | lẩm bẩm |
| văn bản viết có người viết đứng đầu (345, 347, 351:73, 344:75-76) | giới tính của người viết | quy ước giới tính mới |

## Vòng 4 (20-09 00:3x): CẢ HAI làm mù hai truyện mới - hdst 060, nise 030

A (Claude) và B (agent review) gán độc lập, không xem bản của nhau. Hai truyện đều ngôi thứ nhất, bản dịch nghiệp dư
có lỗi (đại từ đảo, tên viết nhầm). Hợp nhất bằng `merge_gold.py merge` (hợp các tập chấp nhận, ưu tiên theo A) rồi phân
xử từng câu lệch dưới đây. 86 câu có người nói: người nói ưu tiên trùng 87,2%, tập chấp nhận tương thích 100%; loại trùng
hệt 234/238; cảm xúc ưu tiên 95,0%, giao 100%. Mọi câu lệch ưu tiên đều là `N` với `N,T` - không câu nào hai bên chọn
hai người khác nhau. gold_replay: 49 lượt generator + 49 critic, không LỆCH LUẬT; điểm replay 100.

| câu | kết luận | lý do |
|---|---|---|
| nise 12, 23, 25, 45 | **A thua**: `N` -> `N,T` + MAGALI đủ | A tự mâu thuẫn: đã cho `N,T` các câu cùng kiểu 7 ("Tại sao tôi phải giả vờ...? Vì thích? Không"), 18, 42. Trong lời kể ngôi thứ nhất ở hiện tại, phản ứng tức thời của người kể (câu hỏi tu từ, "Thôi chết.", nói thầm với người trước mặt "tôi muốn anh làm tường thịt") là tiếng lòng - quy tắc 4 |
| nise 13 ("Rõ ràng là lợi bất cập hại mà"), 11 ("mọi người hiểu mà đúng không?") | giữ `N` (hai bên cùng) | giải thích/nói với người đọc, không phải tiếng lòng tức thời |
| nise 5, 21, 41, 44, 49, 68, 75, 79 | bỏ THÁNH NỮ~ | **A sai**: danh hiệu trơn - prompt dự án cấm danh xưng trong nhãn, và nhãn danh hiệu tách thành một giọng thứ hai của cùng người. Quy tắc 11 mở rộng |
| hdst 151 | bỏ GIÁO SƯ GLAST~ | **A sai**: quy tắc 11 đã cấm tiền tố vai vế từ vòng 3 (CHÚ LƯU ĐẠT) |
| hdst 56, 60 | + `NPC*~` | B: Lucy chỉ được gọi tên ở 62 - quy tắc 5 |
| hdst 2, 36 "Hộc... hộc..." | + NARRATOR~ | B: tiếng thở của người là của người ấy - quy tắc 8 |
| hdst 20 "KÉTTTT!" (tiếng hét sắc lẻm, không rõ của ai) | NARRATOR, `NPC*` đủ; `UNKNOWN~` | B: có người/vật phát ra - quy tắc 8 |
| nise 16 | + ERIS~ | B: câu 17 dẫn câu này bằng "Eris" (lỗi dịch) - model đọc theo chữ vẫn đúng người |
| nise 48, 49 | + MAGALI~ / ERIA~ | B: bản dịch đảo đại từ ("em muốn ngài" là lời Eria); mạch truyện quyết định (50 "Đó là nói dối" = Magali nói 49), cách đọc theo đại từ nửa điểm |
| nise 83 "Tôi là Silk" | + `NPC*~` | B: thí sinh một lần - NPC chấp nhận được nửa điểm, dù cô tự xưng tên ngay trong câu |
| nise 58, 63 | + `UNKNOWN~` | A: có manh mối (kỵ sĩ hộ tống) - quy tắc 5 |
| cảm xúc, nhịp, âm lượng, cường độ | hợp hai tập | lệch nhỏ, không câu nào mâu thuẫn (giao 100%) |

## Vòng 5 (20-09 00:5x): cả hai làm mù TMA 407 (cuốn 2, chương 408) và Nageki 20 (truyện mới)

110 câu có người nói: người nói ưu tiên trùng **100%**, tương thích 100%; loại trùng hệt 285/285; cảm xúc ưu tiên 92,9% /
96,5%, giao 100%. gold_replay: Nageki 41 + 41 lượt, điểm replay 100; TMA 407 19 + 19 lượt, điểm replay 92,3 - 6 câu nội
tâm bị host ép NARRATOR (đã có `patch_a_thought_keeps_its_thinker.py` trong hàng chờ) và **407:78 bị luật host
`_explicit_speaker_attribution` đổi BEYER thành Lucien** (tên đầu câu kể sau: "Lucien còn chưa kịp làm gì khác, một giọng
nói... vọng đến") - lỗi sản xuất mới, xem `docs/LLM_EVAL.md`.

| câu | kết luận | lý do |
|---|---|---|
| 407:3-16 ghi chép rời | **A sai**: + THANOS đủ | B: 406 "ghi chép không hoàn chỉnh do Thanos để lại", 22 "ghi chép của Vua Mặt Trời Thanos" - A đọc sót chương trước |
| 407:78, 83 | + RUDOLF II~ | B: người trong xác Beyer là Hoàng đế Rudolf II (lộ ở chương 409); tên chương này gọi đủ điểm - quy tắc 13 mới |
| 407:80 "Beyer?" | + SOPHIA~ | B: Lucien là người nhìn, nhưng Sophia có mặt - chấp nhận nửa điểm |
| 407:63, 69 | **giữ A**: SOPHIA~ (B cho đủ) | đoạn kể NGÔI BA dài ("Nghe vậy, Sophia chợt... Cô nặng nề ngã xuống đất") chỉ có một câu tự nhủ ở đầu/cuối: đọc cả đoạn bằng giọng Sophia là sai giọng cho phần kể về chính cô. Quy tắc 4 bổ sung |
| Nageki 178 "Kill…" | + NARRATOR~ | B: tiếng rống của sinh vật là của nó - quy tắc 8 |
| Nageki 163 "nguyên liệu" | + SITRI SMART~ | bí danh |
| Nageki 102 | giữ SITRI~ của A | vô hại: host luôn đưa narration về NARRATOR |

Góp ý luật của B (đều nhận): quy tắc 4 bỏ chữ "ở hiện tại" (Nageki kể ở quá khứ mà các câu kêu thầm vẫn là tiếng lòng);
quy tắc 9 nói rõ nội tâm bị khoá D -> `T,D`, người nghĩ đủ điểm; quy tắc 7 nói rõ tác giả được gọi tên ở chương khác
hay trích dẫn thoáng qua; quy tắc 13 mới cho nhập xác/cải trang.

## Vòng 6 (20-09 01:0x): cả hai làm mù TMA 419 (chương 420) và Yamiyo no Hotaru 155 (truyện ngoặc 「」)

Yamiyo làm trên bộ tách đoạn SAU `patch_a_corner_bracket_is_a_quote.py` (54/107 đoạn là thoại; trước bản vá là 0). 113 câu
có người nói: người nói ưu tiên trùng **100%**, tương thích 100%; loại trùng hệt 215/215; cảm xúc ưu tiên 93,6% / 84,0%,
giao 100%. Mọi chỗ lệch là bí danh (HOTOYA TAMAKI, AKOU/AKO MURASAKI do B đếm trong kho) và nửa điểm:

| câu | kết luận | lý do |
|---|---|---|
| 419:47 | **A thua**: BAREK~ -> đủ | B: lời dẫn nêu cả hai ("Công tước James và pháp sư bậc bảy Barek... nhỏ giọng thở dài"); quy tắc 6 bổ sung |
| 419:69-70 danh sách "cách chết ngu ngốc nhất" | + BAREK~ | B: Barek vừa nói về pháp sư chết vì điện (67) - có thể đọc như ông trích |
| Yamiyo 80 "Ừ. … Đi thôi." | giữ IRUKA~ của A | Tamaki tự nhủ khi đứng dậy (81) nhưng câu "Ừ" cũng hợp lời Iruka |
| bí danh | hợp hai bên | quy tắc 11 |

replay TMA 419 (host hiện hành): 98,2 - **419:24, 26 ("dây chuyền lắp ráp", "tiêu chuẩn hoá", thuật ngữ trích giữa câu kể)
bị host đổi NARRATOR thành Arthur**, người nói của đoạn văn. Lượt kiểm toàn bộ (mọi chương đáp án phát lại) đang chạy.
Góp ý luật của B (nhận cả ba): quy tắc 6 cho lời dẫn nêu hai người, ví dụ Yamiyo 43 ở quy tắc 10, tiêu đề lặp ở đoạn 1.

## Vòng 7 (20-09 01:2x): B gán một mình, A soát đối kháng - TMA 396, Năng lực bá đạo 0135, Love Unseen 09

B làm nhanh hơn A nhiều (một chương ~3 phút), nên ba chương này B gán và A đọc lại từng câu với nguồn thay vì làm mù.
B tự liệt kê các câu kém chắc chắn nhất; A soát toàn bộ. B chắc tay: A chỉ đổi 6 dòng người nói trên 476 đoạn.

| câu | kết luận | lý do |
|---|---|---|
| TMA 396:16 "Ác quỷ…" | + ANDRIS~ | câu thì thầm có dấu lửng, khớp cách Andris đang quỳ nhìn Lucien ("con quỷ đáng sợ nhất thế giới", câu 1) hơn tiếng la của đám bỏ chạy |
| Năng lực 0135:31-114 (Trịnh Vĩnh Mong) | bỏ `NPC*~` | **B sai**: quy tắc 5 chỉ cho `NPC*~` câu nói TRƯỚC khi được gọi tên (9-16); từ câu 17 anh ta có tên. Trịnh lão giữ `NPC*~` (không có tên riêng, nói lại ở nhiều chương - lô-gic giọng thần vòng 3) |
| Love Unseen 09:28 | HAYASE đủ -> ~ | câu kể nêu hai người ở đoạn văn KHÁC và chỉ tả họ vẫy tay - không phải lời dẫn; Narumi là người châm pháo (30) |
| Love Unseen 09:42, 43, 50 | người thứ hai đủ -> ~ | hai câu liên tiếp sau "Hayase và Narumi gọi Fuyutsuki" là mỗi câu một người (42 gọi "Koharu" = lối Hayase), không phải một câu hai người cùng nói; quy tắc 6 bổ sung |

Góp ý luật của B (nhận): họ + kính xưng là tên khi nhân vật không có tên riêng (quy tắc 11); tên cải trang nửa điểm trên
câu nói, không điểm trên câu nghĩ (quy tắc 13).

## Vòng 8 (20-09 01:3x): TMA 418 cả hai làm mù; TMA 385, Two Childhood Friends 013 B gán - A soát

TMA 418 (làm mù): người nói ưu tiên trùng 97,0% (33 câu), loại 89/89, cảm xúc ưu tiên 98,9%.

| câu | kết luận | lý do |
|---|---|---|
| 418:32 "Chẹp. Thật là một thanh niên có tinh thần văn nghệ, à không, ông già mới đúng. Lucien cười thầm trong lòng." | **A thua**: LUCIEN~ -> đủ | B: phần lớn đoạn là tiếng lòng trực tiếp, lời dẫn ngắn. Khác 419:32, nơi phần kể gọi Lucien là "cậu" |
| 418:41 hai học trò cùng chào, gọi tên ở 44 | **A thua**: NPC* đủ -> `NPC*~` | quy tắc 5: người được gọi tên sau trong chương; LILLIAN, ISAAC đủ |
| 385:20, 95, 109 (Sana, Aska, Inke) | **B sai**: bỏ `NPC*~` | tên có ngay ở lời dẫn liền sau câu ("Nhân sư cái Sana nhìn Lucien và nhỏ giọng nói:") - lời dẫn thường, như 419:5 Lillian mà cả hai bên đều không cho NPC. 35 Helges giữ `NPC*~`: lời dẫn không nêu tên |
| 385:123 Lucien trong hình Aska | LUCIEN, ASKA đều đủ | quy tắc 13: chương gọi "Aska", nhưng đã lộ ngầm trước câu (Aska thật bất tỉnh ở 119) |
| Two Childhood 013 | không đổi | soát từng câu với nguồn |
| 385:123 (bổ sung) | ASKA đủ -> ~ | B tự đề xuất: lời dẫn dùng tên giả "Aska" nhưng danh tính thật đã lộ trước câu; tên giả nửa điểm như Beaulac - quy tắc 13 bổ sung |
| Yamiyo 189 | không đổi | B xác minh "sư phụ" = Kaede Tomoe (corpus 168); 29 câu của kẻ nhập xác Yuusei trong 『…』 bị khoá lời kể -> NARRATOR (quy tắc 10) |

Phát hiện sản phẩm từ vòng này (chưa vá): ngoặc 『…』 NGUYÊN DÒNG là một giọng nói ở ba truyện - kẻ nhập xác (Yamiyo, 6.185
dòng), loa/điện thoại (Two Childhood, 691), bảng hệ thống game (Năng lực bá đạo, 5.048) - nhưng bộ tách đoạn khoá lời kể.
Bản vá 「」 cố ý không đụng 『』 (thuật ngữ trong câu, ngoặc lồng). Cần đo riêng trước khi vá; không vào ranh giới 9.

## Vòng 9 (20-09 01:4x): TMA 436 cả hai làm mù; TMA 426, hdst 090 B gán - A soát

Hai chương TMA chọn vì có lời dẫn "X quay sang/nhìn Y nói:" mà host cũ khoá cho người NGHE; chúng thuộc lô 10, sẽ chạy
với host đã vá - đáp án để đo bản vá có ăn trong sản xuất thật. TMA 436 (làm mù): người nói ưu tiên trùng **100%** (39
câu), loại 83/85, cảm xúc ưu tiên 88,2%.

| câu | kết luận | lý do |
|---|---|---|
| 436:7, 16, 25, 64 | hợp hai bên (thêm `~`) | B: Heidi/Lazar có mặt ở 7, 25; Florencia/Raventi ~ ở 64 |
| 436:72 | giữ A: LUCIEN đủ | phần lớn đoạn là câu hỏi thầm của Lucien, chỉ mở bằng "Lucien khẽ cau mày." - như 418:32 |
| 426:1 "Tự Nhiên?" | + `NPC*~` | có thể cả phòng hỏi lại (4: "thắc mắc chung của tất cả mọi người") |
| 426:36, 436:77-78 | LEVSKI; ANNONIS | cả hai bên cùng đúng: chủ ngữ của "quay sang/nhìn ... nói", không phải người nghe |
| hdst 090 | không đổi | |

## Vòng 10 (20-09 02:0x): TMA 399, 400, 415, 420 (lô 9, vừa thu) - B gán, A soát

Chọn trong lô 9 để chấm đầu ra THẬT của `qwen3:8b` trên nhiều chương hơn. A đọc lại mọi câu có người nói với nguồn: không
đổi dòng nào. Điểm đáng ghi: 400 - "Andris" bị một thứ khác nhập (xưng "ta", mặt biến dạng) nhưng không chương nào đến 407
nêu danh tính ấy -> ANDRIS đủ (quy tắc 13); 415:39 đuôi câu Fernando bị ngoặc lồng cắt, khoá N -> NARRATOR (quy tắc 10);
399:22, 54, 61 và 400:73, 415:88 là lời dẫn nêu người NGHE - không cho điểm người nghe.

## Vòng 11 (20-09 02:1x): cuốn 1 - YM 134, 188; Nise 111 - B gán, A soát

A soát mọi câu có người nói kèm câu kể liền trước/sau: không đổi người nói nào; thêm bí danh đầy đủ có trong truyện
(MICHAEL GODSWILL 34 lần, JULIANA VOX 28 lần - quy tắc 11). B sửa lại đề bài của A: Nise 111 là chương NGÔI BA (Marla,
Alistar), không phải Magali kể. Cả ba chương dày câu gọi tên người nghe ("Samael, ...", "..., Michael", "Marla-san") - đúng
kiểu lỗi lớn nhất của `qwen3:8b` ở lô 9.

## Vòng 12 (20-09 02:2x): Đã bảo 143, Nageki 73, Two Childhood 082 - B gán, A soát

A soát mọi câu có người nói kèm câu kể liền trước/sau: không đổi dòng nào. Đáng ghi: Nageki 73 là một cái BẪY cho model -
nhóm giả mạo có tên na ná nhóm thật (Krahi Andrihee / Krai Andrey, Kutri Smyat / Sitri Smart); tên nhóm thật không được điểm
(quy tắc 12). B tự kiểm cả bốn cách viết trong kho.

## Vòng 13 (20-09 03:3x): TMA 429, 446, 449 (lô 10) - B gán, A soát

Cùng 426, 436: năm chương lô 10 để so độ chính xác sản xuất trước (lô 9) và sau tám bản vá host. A giữ mọi nhãn của B trừ
449:93 (giấy tờ trên bàn Lucien, chỉ được NHÌN thấy, không câu nào nói Lucien viết) -> LUCIEN~ thay vì đủ. "Sơn Ca" là bí
danh phát thanh của Samantha, chính chương nối hai tên (65-66) -> cả hai đủ (quy tắc 11). LOUISE~ cho Dạ Oanh ở 446: danh tính
chỉ lộ ở chương sau (quy tắc 13).

## Vòng 14 (20-09 08:4x): phân xử PHIẾU CHẤM lô 9 - thí sinh có đúng hơn đáp án chỗ nào không?

Chủ sách hỏi: nếu bài làm của thí sinh đúng hơn đáp án thì có nhận và sửa đáp án không. Có - đã xảy ra bốn lần với người
soát (347:20, nise x8, hdst 151, TMA 407). Nay kiểm cả phía model: `score_models.py --dispute-out` in 134 chỗ lệch của
`qwen3:8b` ở lô 9 (điểm 79,7 - người nói 68,4%), làm mù tên model, phân xử bằng văn bản gốc (`dump_segments.py`).

Phân loại 133 chỗ lệch người nói:

| kiểu | số chỗ | trạng thái |
|---|---|---|
| hai nhân vật có tên, nhầm người (phần lớn gán người ĐƯỢC GỌI) | 40 | lỗi model thật |
| nội tâm bị đẩy về NGƯỜI KỂ | 27 | khoá host, đã vá ở ranh giới 9 |
| NPC vô danh bị gán tên một nhân vật có tên | 23 | lỗi model thật |
| lời kể gán cho nhân vật | 19 | lỗi model thật |
| cụm trích ngắn giữa câu kể bị tách thành giọng | 17 | khoá host, đã vá ở ranh giới 9 |
| thoại bị đẩy về NGƯỜI KỂ | 6 | lỗi model thật |
| nhân vật có tên bị gán NPC | 1 | lỗi model thật |

Phân xử kỹ sáu chỗ model nghe có lý nhất - **đáp án đúng cả sáu, không sửa dòng nào**:

| chỗ | đáp án | bài làm | bằng chứng trong truyện | phán xử |
|---|---|---|---|---|
| 399:40, 399:41 | NPC*/ARTHEN/RELPH/UNKNOWN | Claire | 42 "Những tiếng kêu kinh ngạc của đám quý tộc trẻ rào rào vang lên" - đây là tiếng phản ứng VỚI câu 39 của Claire | TS_SAI |
| 399:44 | ARTHEN | Claire | 43 "Arthen nghiêm nghị hỏi:"; Claire là người ĐƯỢC GỌI | TS_SAI |
| 399:51 | SOPHIA | Claire | 52 "Trên khuôn mặt bình tĩnh của Sophia hiện lên niềm vui mãnh liệt"; tên Claire chỉ được NHẮC trong câu | TS_SAI |
| 385:4 | NPC*/UNKNOWN | ASKA | 3 "nhân sư vừa ra lệnh kia" - không câu nào nối nó với Aska (Aska vào truyện ở p72, cảnh khác) | TS_SAI |
| 385:109 | INKE | ASKA | 110 "Inke, cộng sự của Aska, lặng lẽ chỉ vào..."; câu 109 GỌI "Chờ đã, Aska" | TS_SAI |
| 385:122 | INKE | ASKA | 121 "Inke thấy Aska mặt tươi roi rói bước ra, bèn tò mò hỏi:" | TS_SAI |

Một chỗ đáng ghi riêng: 385:123 model gán ASKA và chỉ được NỬA điểm - đúng quy tắc 13, vì đây là Lucien đội lốt Aska sau
khi hạ nó (118-119 Lucien đấm, 121 "Aska" tươi roi rói bước ra). Đáp án LUCIEN đủ, ASKA~ nửa: đáp án khắt khe đúng chỗ.

Hai chỗ model gần đúng mà vẫn 0 điểm, giữ 0 có chủ ý: 396:70 `JOCLEYN` (viết sai tên JOCELYN) và 399:98 `HOÀNG TỬ BEYER`
(thêm tiền tố vai vế). Cả hai trong sản xuất sinh ra một nhân vật MỚI, tức một giọng thứ hai cho cùng người - đó là lỗi
thật, không phải chuyện chính tả. Quy trình phân xử: `docs/GOLD_GUIDE.md`, mục "Khi thí sinh trả lời ĐÚNG HƠN đáp án".

**Bổ sung 09:1x - một lần ĐÁP_ÁN_SAI thật, do bản vá phát hiện chứ không do thí sinh:** `two_childhood_friends 082:94`
là dòng `『Một trong hai người nhượng bộ đi chứ...』`. Đáp án cũ ghi `N NARRATOR` theo quy tắc 10 (bộ tách đoạn khoá
lời kể). Bản vá 『』 khoá nó thành THOẠI, và bản vá đúng: câu 98 nói rõ "có cả Kakushigi và Grey ở đây", nên câu ấy là
một người đứng cạnh NÓI RA MIỆNG - để NGƯỜI KỂ đọc là sai. Sửa thành `D NPC*,UNKNOWN,KAKUSHIGI,GREY` (văn bản không
chỉ rõ ai trong hai người). Phát lại chương: 100%. Đây đúng là ô `ĐÁP_ÁN_SAI` của quy trình, chỉ khác nguồn phát hiện.

## Vòng 15 (20-09 10:1x): phân xử PHIẾU CHẤM lô 10 - lô sản xuất đầu tiên có 8 bản vá host

Chương 426 và 429 (hai chương có đáp án đã phân tích xong khi lô còn đang bay; `score_models.py --chapters`).
Điểm 79,6 - người nói 71,7%. 26 chỗ lệch, phân xử mù bằng phiếu. **Không sửa dòng đáp án nào.**

| kiểu | số chỗ | phán xử |
|---|---|---|
| ARTIL viết thành `ARTEL` / `ARTELI` | 8 | TS_SAI - nguồn có "Artil" 88 lần, "Artel" 0, "Arteli" 0. Mỗi cách viết sai thành một nhân vật riêng có giọng riêng -> `patch_a_name_two_letters_off_still_belongs_to_its_owner.py` |
| cụm trích giữa câu kể gán cho nhân vật (426:6, 9, 11) | 3 | TS_SAI - người kể đang gọi tên hai tập san giữa câu của chính mình -> `patch_a_term_quoted_mid_sentence_is_the_narrators_own_line.py` |
| host tự sửa thành `người gọi EVANS` (429:77, 78) | 2 | không phải lỗi đáp án: luật "người được gọi" thay người nói bằng một NPC vô danh, nên 0 điểm dù host đã nhận ra model sai. Đúng như đo trước đó ở `docs/LLM_EVAL.md` - nới luật ấy không được điểm nào |
| model lấy tên được NHẮC hoặc được GỌI trong câu làm người nói | 13 | TS_SAI |

Ba chỗ phân xử kỹ bằng văn bản gốc:

| chỗ | đáp án | bài làm | bằng chứng | phán xử |
|---|---|---|---|---|
| 426:3 | NEESHKA | LEVSKI | nguồn: `“Tự Nhiên?” Neeshka đằng hắng rồi nói: “Ủy viên Evans, lời giải thích của cậu...”` | TS_SAI |
| 426:79 | NEESHKA | LEVSKI | Samantha hỏi "Thưa thầy, hôm nay thầy thua ạ?" -> người đáp là THẦY của cô, tức Neeshka (xem ghi chú 72 của đáp án). Tên Levski chỉ được NHẮC trong câu ("Hình học mới của Levski đã đúng") | TS_SAI |
| 429:20, 32-34, 42, 67, 74 | ARTIL | ARTEL/ARTELI | "Artil" 88 lần trong nguồn, hai cách kia 0 lần | TS_SAI |

Đáng ghi: `426:3` sẽ được host tự sửa từ ranh giới 10, vì "Neeshka **đằng hắng rồi** nói:" là đúng mẫu mà
`patch_a_modifier_between_a_name_and_said_still_names_the_speaker.py` mở ra (đã thử trên cây đã vá: trả về "Neeshka").
Tổng cộng **11 trên 26** chỗ lệch của lô 10 nằm trong tầm ba bản vá đang ghim ở hàng đợi ranh giới 10.

## Vòng 16 - lượt so ba model 21-09, 10 chương, phiếu giấu tên 324 chỗ

Nguồn: `score_models.py --dispute-out D:/Novels/Audiobooks/_model_eval_gold/dispute_21_09.tsv` trên câu trả
lời TƯƠI của `qwen3:8b`, `qwen3:4b`, `gemma4:e2b-it-qat` (4 chương tập test) và hai model đầu (6 chương
385/396/399/400/407/415). **324 chỗ lệch, 323 ở trục người nói, 1 ở loại đoạn.**

Lọc theo mức NGỜ thay vì đọc cả 324: chỗ đáng sợ nhất cho đáp án là nơi **nhiều thí sinh đồng thuận một
câu trả lời khác đáp án**. Đúng **2 chỗ** có >=3 thí sinh đồng thuận, và cả hai đều phân xử được bằng câu
trong truyện:

| chỗ | đáp án | bài làm (3/3 thí sinh) | bằng chứng trong truyện | phán xử |
|---|---|---|---|---|
| 351:57 | DOUGLAS | LUCIEN | 351:53 `Một lúc sau, Douglas tiên phong vỗ tay:` -> :54-55 là lời Douglas -> :56 `Ông lấy ngón tay chỉ vào đầu mình.` -> :57 -> :58 `Xem ra ông là người rất thích triết học.` Hai câu kể kẹp hai bên đều gọi "ông" = Douglas; và nội dung là người lớn tuổi nói với **"cậu"** về việc vào hội đồng, trong khi Lucien chính là người được kết nạp | **TS_SAI** |
| 363:80 | NARRATOR | LUCIEN | `Giống như Bellak trước đây, Lucien đặt tay phải lên ngực trái và khẽ cúi đầu**:**` - câu kể mô tả động tác, dấu hai chấm dẫn vào 363:81 `“Cảm ơn về chiếc bình, Bellak.”` Thí sinh lấy CHỦ NGỮ của câu kể làm người nói | **TS_SAI** |

**Đáp án đúng 2/2 chỗ ngờ nhất** - cùng kết quả với vòng 14 (6/6). Không sửa một dòng đáp án nào ở vòng này.

### Sản phẩm phụ đáng giá hơn phiếu - và nó thành một kết quả ÂM

`351:57` để lộ rằng **chính sản xuất cũng sai ở đó** (`speaker=LUCIEN`), theo mẫu "lời thoại nối lại SAU
một câu kể chen giữa nói về cùng người ấy". Trông rất giống một luật host. Đo trước khi viết:

| | |
|---|---|
| mẫu `thoại -> câu kể mở bằng đại từ ngôi ba -> thoại` trong 11 lô | **189 chỗ** |
| có đáp án chuẩn ở CẢ HAI đầu | 7 |
| đáp án nói **CÙNG** người | **4** |
| đáp án nói **KHÁC** người | **3** |
| trong nhóm "cùng người", sản xuất gán sai | 2 (`351:57`, `378:95`) |

4 trên 7 là gần như tung đồng xu: luật ấy sẽ sửa 2 câu và **phá 3 câu**. **LOẠI.** Ghi lại vì đây đúng
loại bẫy dễ mắc - một ví dụ sống động (`351:57` đọc lên là thấy ngay ai nói) không phải một luật, và chỉ
phép đếm mới phân biệt được hai thứ đó. Mẫu quá lỏng vì câu kể chen giữa có thể đổi hẳn người: đại từ
ngôi ba ở đầu câu không hứa rằng nó chỉ người vừa nói.

## Tam quốc diễn nghĩa (Phan Kế Bính) Hồi 50-52 - truyện chưa thấy, cổng đổi model (27-09)

A: Claude (vòng chính). B: agent soát đối kháng (xem A). **B không thấy câu nào sai người nói chính.** Đã áp:
- 32 câu lời kể có từ gợi cảm xúc mà luật host cấm neutral ("quát", "khóc", "mừng lắm", "hoảng quá"...): thêm cảm xúc của
  cảnh vào tập, giữ neutral (đúng GOLD_GUIDE "lời kể trong cảnh căng"); thêm afraid cho "rụng rời hồn vía", "ba hồn bảy vía".
- Câu cả toán quân hô ("một toán quân... gọi to lên rằng"): NPC* đủ điểm cả khi câu tự xưng tên tướng (050:26, 28), tướng
  tự xưng mà lúc nói chưa được nêu tên: NPC*~ (050:5, 32; 051:183; 052:75, 81, 83). Câu "các tướng hỏi": người có mặt được
  nêu tên gần đó thêm `~` (050:40, 58, 74, 78, 132; 052:15). 051:136: thêm UNKNOWN~.
- Danh xưng: "Dự-châu" là chức (quy tắc 11: danh hiệu trơn khi đã biết tên) - bỏ; "Quan-công" (họ + tôn xưng) nửa điểm.
  Thêm biến thể không gạch nối còn thiếu (LỖ TỬ KÍNH, ĐỨC MƯU, MÃ QUÝ THƯỜNG, LĂNG CÔNG TỤC...) - `speaker_key` không bỏ gạch.
- 050:169 chú thích cuối hồi của người dịch: NARRATOR đủ điểm (cùng Dữu-công). 052:21 "Túc khen thầm": `T,D` (quy tắc 9).
- Giữ, ghi **host sai**: 050:88 "Sống chết có số, việc gì mà phải khóc? Hễ đứa nào khóc nữa thì chém!" - host cho sad vì chữ
  "khóc" nằm trong phạm vi CẤM (AGENTS.md đòi tôn trọng phủ định/ngăn cấm); gold giữ angry. 050:132 "việc gì phải khóc?" -
  tiếng khóc là của Tào Tháo, không phải của các mưu sĩ đang hỏi; gold giữ surprised/neutral.


## Tắt đèn (Ngô Tất Tố) chương XX, XXI, XXIV - truyện Việt chưa thấy, cổng thứ hai (28-09)

A gán ba chương (245 đoạn, 112 câu thoại), B (agent Sonnet) soát đối kháng: lần lại độc lập mọi câu thoại, kể cả các
cặp hỏi - đáp không lời dẫn (020:20, 31, 49; 021:21-22, 43-45, 60-61, 76; 024:18-22, 28-30, 38-39, 59-60) - không lệch
người nói nào; loại đoạn khớp bộ tách khoá 100%; nhân vật "nói ở nhiều chương" kiểm bằng grep cả 27 chương. Phát lại
đáp án (`gold_replay.py`): không LỆCH LUẬT; người nói 90,2% vì khoá thoại nối tiếp của host đè 11 câu gạch đầu dòng -
host sai, đã sửa (7ca7ef7), sau sửa 100%.

| câu | kết luận | lý do |
|---|---|---|
| 024:9, 13 (ông huyện Minh Hảo) | **B thua**: giữ `NPC*~` | B: chỉ nói ở chương này, như biện lệ (NPC* đủ). Nhưng "Minh Hảo" là tên riêng (tên huyện dùng làm danh xưng, "quan Minh Hảo sang chơi"), gọi ra ở 7-8 TRƯỚC câu nói; prompt bắt nhân vật có tên dùng tên, và quy tắc 5 chỉ cho `NPC*~` cả khi tên đến sau câu nói. Biện lệ không có tên riêng nào - chức danh là tất cả những gì truyện gọi hắn |

Quy ước mới cho truyện Việt (ghi ở đầu 020.txt): chức danh trọn cuốn là tên (QUAN PHỦ, LÝ TRƯỞNG - như "Trịnh lão");
người gọi theo tên chồng: "CHỊ DẬU" đủ, "DẬU" trơn không điểm (là chồng chị); tiền tố xưng hô trên tên thật ("ANH DẬU",
"THẰNG DẦN") nửa điểm - khác "CHÚ LƯU ĐẠT" (quy tắc 11, không điểm) ở chỗ lời kể của sách không bao giờ viết tên trơn.

## Bộ đo LN 28-09 - 5 chương LN Nhật/Hàn CHƯA học (thứ chủ sách đọc)

A = Claude gán, B = agent soát đối kháng (không sửa file, trả bằng chứng file:dòng). Mục đích và cách chọn chương:
`docs/ANALYSIS_RESEARCH.md` "BỘ ĐO LN 28-09".

**Two Childhood Friends 042** - B soát, A chấp nhận hết:

| chỗ | A ghi | kết luận | bằng chứng |
|---|---|---|---|
| 64 | GREY đủ, NARRATOR~ | **ĐÁP_ÁN_SAI** -> `KÝ SINH TRÙNG,CON KÝ SINH TRÙNG` đủ, NPC*~, UNKNOWN~, NARRATOR~, `m` | Dòng 『』 giữa cảnh là "con ký sinh trùng" - giọng NAM trong não Yoshihito, cả cuốn gọi thế (102 lần/49 chương); 072:191-193 "Giọng nói của con ký sinh trùng trong não, chẳng ai nghe thấy"; 001:55-63 giọng một gã đàn ông; hay hỏi "hai người/các cậu" để lời kể trả lời (050:103, 040:157-163, 041:127-131 - đúng khuôn 64 -> 65-67). Grey chỉ nói 『』 khi đã hoá đàn dơi (043:119-141); ở 042 cả 7 câu của cô trong "". |
| 73, 74 | cả hai đủ ở cả hai câu | **ĐÁP_ÁN_SAI** (nhẹ): 73 Yoshihito đủ, Kirako~; 74 Kirako đủ, Yoshihito~ | Grey luôn tiếp cận và bị Yoshihito từ chối riêng (035:91-145, 038:255-261, 040:195-227, 041:141); 73 "đã nói rồi" là cậu; 74 mở bằng "Đúng vậy" là người kia. Tiền lệ quy tắc 6 vòng 7. |
| 2-35 | NARRATOR,NPC*~ | thêm UNKNOWN~ | tiền lệ văn bản viết của người vô danh (345:84-85, 050:61-62). |
| 76, 77 | hai người ~ | cả hai đủ | trọn câu quyết tâm chung, không có phần kể về họ (013:119, 123). |

**Nise Seiken 132** - B không thấy người nói chính nào sai. 30: `N,T NARRATOR,NPC*~` -> NPC* đủ (câu 31 "ông ta" xác định
người nghĩ là ông chú nói 32-70).

**Sửa ngược gold cũ Two Childhood Friends 082:94** (train, không phải test): `NPC*,UNKNOWN,KAKUSHIGI,GREY` -> `KÝ SINH
TRÙNG,CON KÝ SINH TRÙNG,NPC*~,UNKNOWN~,NARRATOR~ ... m`. Nguồn phát hiện: B khi soát 042. Dòng 082:195 "『Một trong hai người
nhượng bộ đi chứ...』" cùng khuôn châm chọc "hai người" của ký sinh trùng (077:165, 081:189); câu 082:203 nhắc Kakushigi,
Grey chỉ giải thích vì sao Yoshihito không quát Kirako; hai người ấy đều nói trong "" (082:107, 261). Dữ liệu LoRA v3 dựng
trước khi sửa (câu ấy dạy NPC* - lựa chọn đầu cũ).

Bài học chung cho LN: **giọng trong đầu nhân vật** (ký sinh trùng ở TCF, Yêu Mẫu ở Yamiyo) nói bằng dòng 『』 ở hàng chục
chương. Nhãn NPC sống một chương -> mỗi chương một giọng; sổ nhân vật cần một tên cố định (tên cả cuốn gọi nó).

**Yamiyo no Hotaru 141** - B soát (27 chương kho), A chấp nhận hết:

| chỗ | A ghi | kết luận | bằng chứng |
|---|---|---|---|
| 41 dòng 『』 "thiếp" | YÊU MẪU, NPC* đủ | **ĐÁP_ÁN_SAI** -> `TỌA PHU ĐỒNG TỬ,TOẠ PHU ĐỒNG TỬ,ZASHIKI-WARASHI` đủ, NPC*~, UNKNOWN~ | 096:477-479 "nàng, Tọa Phu Đồng Tử, cất lên lời nguyền" sau một câu 『』 cùng giọng (096:411-449 tả đúng giọng ở 141: luôn dõi theo, nắm tay, ghen với người Onizuki); giọng ấy nói cả khi Tomobe vắng (137:159, 237) - không thể nằm trong máu cậu; Yêu Mẫu là nhân vật khác (107:63-155, tóc xanh, nói 「」, xưng "mẹ"). A lấy "yếu tố yêu mẫu" (136) làm bằng chứng - sai, đó là thứ trong máu Tomobe mà thuốc ức chế. Quy tắc 12. |
| 173, 175 | NPC*, UNKNOWN~ | `NHỆN TRẮNG,CON NHỆN TRẮNG` đủ, NPC*~ (173 thêm NARRATOR~) | 177 gọi người nói là con nhện trắng; cả cuốn không tên riêng ("nhện trắng" 47 file); nói ở 099, 102, 143, 150. |
| 23 dòng nội tâm Hina | `N,T NARRATOR,HINA` | `T,N HINA,ONIZUKI HINA,NARRATOR ... f` | quy tắc 9 (loại THẬT trước, tiền lệ 385:56); lựa chọn đầu là thứ dạy model; nội tâm đọc bằng giọng người nghĩ (chủ sách 20-09). Điểm không đổi. |
| 26, 100, 149 | TOMOBE, NARRATOR~ | TOMOBE | 189:117, 155:10-12: dòng T thật không cho NARRATOR điểm. |
| 18, 22 | TOMOBE | TOMOBE, NARRATOR~ | tiếng kêu (quy tắc 8; 189:13, 25, 35). |
| 28, 177 | N | N,T NARRATOR,TOMOBE | tự nhủ tức thời như 25. 39: thêm NPC*~ như 38. |
| cảm xúc lời kể | neutral | thêm cảm xúc của cảnh (9, 11, 16, 58, 65, 72, 157, 161, 179 - host cấm neutral; 8, 15, 17, 20, 31, 105 theo GOLD_GUIDE); 83, 158 thêm happy | "host sai" (giữ đáp án): 23, 59, 64, 67 - chữ "đau đớn"/"khóc" nằm trong câu trêu hay kỷ niệm vui. |

**Hướng dẫn sinh tồn 062** - B không thấy câu nào sai người nói chính. 3: bỏ Lucy~ ("Hừm~" là tật nói của Lortel -
028:39-41, 100:265-267). 37, 98, 119: N,T với ED (như 26; 060:127). Lời kể cảnh Glast hấp hối thêm sad (tender ở 128,
141-143); 6, 48, 117 thêm afraid (host cấm neutral). 56: host đòi angry vì chữ "tan nát" - host sai, đáp án neutral,sad.

Hai lỗi nặng A mắc ở bộ này là CÙNG MỘT KIỂU: gán giọng 『』 trong đầu cho một cái tên gần tay mà không lần hết cuốn (Grey ở
TCF 042:64, Yêu Mẫu ở Yamiyo) - đúng lỗi quy tắc 12 cảnh báo ở model. Soát B lần đủ kho mới bắt được.

**Quy ước mới 28-09 11:xx (GOLD_GUIDE 7b):** TCF 042:2-35 (bài đăng mạng xã hội) từ `NARRATOR,NPC*~,UNKNOWN~` -> `NARRATOR,NPC*,UNKNOWN~`.
Lý do: mỗi bài là một người vô danh khác - với người nghe, đọc chuỗi bình luận bằng nhiều giọng NPC đúng như câu "cả đám"
(quy tắc 6), không kém gì người kể đọc. Cái SAI thật là giọng một nhân vật có tên chỉ được NHẮC trong bài: qwen3:8b gán 8/34
bài cho "Kuchinashi" (042:20-27, 35). Phát hiện khi mổ lượt đo mốc qwen3:8b; sửa trước khi chấm bất kỳ model nào khác.

**Nageki no Bourei 65** - B soát (đọc trọn 60-65, grep toàn kho), không người nói chính nào sai hẳn:

| chỗ | A ghi | kết luận | bằng chứng |
|---|---|---|---|
| 41 "Kill, kill" | KILLIGAN đủ, KILLIAM~ | **ĐÁP_ÁN_SAI** -> `KILLIAM,KILLIAM SMART` đủ và đứng đầu, KILLIGAN~, NARRATOR~, `m` | danh tính lộ ở chương TRƯỚC: 60:141-143 Killiam chui ra khỏi giáp Killigan; 47 "Sitri đã bảo tôi trước rồi"; túi giấy hai lỗ mắt (40) là dấu hiệu Killiam (20:337); quy tắc 13, tiền lệ 385:123; gold 20:178 cho "Kill" là KILLIAM. |
| FRANZ ARGMEN | đủ | ~ | "Argman" 7 lần trong kho, "Argmen" 1 lần ở lời kể 143 - lỗi gõ (quy tắc 11). |
| 130 | Murina ~ | đủ | trọn đoạn là tiếng lòng trực tiếp (418:32, 436:72). |
| 187 | Franz | Franz đủ, Murina~ | 182-186 là lập luận của Murina chảy vào câu; nhập nhằng. |
| 295 | Eva, Krai~ | Eva | 296 "Nghe tuyệt đấy" đáp nó; 294 là tiếng lòng không ngoặc. |
| cảm xúc | neutral | 89, 123, 157, 175, 208, 228 thêm cảm xúc host bắt; 132, 150, 161, 164, 170, 194, 203 thêm cảm xúc cảnh; 160 intensity 2-3; 195 pace fast,normal | analysis.py `_direct_cue_allowed_emotions`; GOLD_GUIDE. |

Phát lại cả 5 chương sau mọi sửa (project `gold:ln3`, lọc TOÀN BỘ đầu ra): 0 dòng LỆCH; chấm lại project phát lại = 100% mọi
trục, trừ giới tính Yamiyo 81%: 23 dòng nội tâm Hina bị host giữ khoá lời kể (NARRATOR, giới u) -> đưa về `N,T NARRATOR,HINA
... u` (điều kiện B tự nêu khi đề xuất T,N). Việc cho bộ tách câu: "(…)" cùng đoạn ngay sau lời thoại là nội tâm người vừa nói.

**Love Unseen 07 (28-09 13:xx) - chương đo LN thứ 6.** A = Claude gán, B = agent soát đối kháng (đọc trọn 01-13, không sửa
file). B không thấy câu nào sai người nói chính, giới tính hay loại đoạn; phát lại qua host lệch đúng MỘT dòng (90). A chấp
nhận hết:

| chỗ | A ghi | kết luận | bằng chứng |
|---|---|---|---|
| 80, 83, 89, 92, 94, 97, 99 | KOTOMUGI | thêm `YUICHI KOTOMUGI` đủ | 01:895 "Tôi là Yuichi Kotomugi, hội trưởng..."; quy tắc 11 |
| 41, 171 | N | `N,T NARRATOR,KAKERU...` | tiếng lòng tức thời (quy tắc 4): 41 phản ứng khi bị trêu, 171 tự trả lời câu hỏi tu từ 170; tiền lệ 09:95, 09:142 |
| 103, 138 | neutral | thêm happy (103 thêm tender) | "nhẹ nhõm" là cue happy; host giờ chỉ ghi lại cue của một câu lẻ nên gold_replay không báo - GOLD_GUIDE đã sửa |
| 73 | neutral,angry,tired | thêm afraid | "Lo lắng cho Fuyutsuki" - như 57, 188, 247 |
| 198, 200, 204 | pace normal | thêm slow (198, 204 thêm soft) | 193 "giọng cô chậm chạp như đang chịu đau đớn" |
| 49, 50, 54 | cường độ 1-2 | 0-2 | tập đã nhận neutral thì phải nhận cường độ 0 |
| 13 "Uhh…" | KAKERU... | thêm NARRATOR~ | tiếng rên (quy tắc 8) |
| 54, 58, 100, 117 | NARRATOR,<người nói>~ | NARRATOR trơn | khoá N: host ép NARRATOR, `score_models` không xét danh sách người nói; tiền lệ 09:152 |
| 90 | NARRATOR | thêm KAKERU~ | lời kể của "tôi" bị khoá D - như quy tắc 10 với T khoá mà thực chất là lời kể |

**Lỗi host (90):** 89 quên đóng ngoặc nên bộ tách khoá 90 ("Tôi nhìn những người bên trong...") là thoại, rồi khoá thoại
nối tiếp gán nó cho Kotomugi. Chưa có cách phân biệt bằng dấu câu - đoạn giữa một bài nói dài ở TMA (351:30-45) cũng không có
ngoặc nào; một manh mối có thể: chuỗi ấy không bao giờ đóng ngoặc trước khi đoạn sau mở ngoặc mới.

**Sửa ngược 09:6 (train):** mẹ Fuyutsuki nói ở 4 chương (02:671, 06:43/57/111, 08:225, 09:13) -> `MẸ FUYUTSUKI` đủ, NPC*~,
UNKNOWN~ (quy tắc 5: nhãn NPC sống một chương; quy tắc 11: tên theo con như "chị Dậu"). `voice_identity --gold-check`:
love_unseen 8 người, không nhập ai. Mẹ Kakeru ở 07 giữ NPC* đủ - bà chỉ nói ở chương này (B kiểm 01-13).

**Love Unseen 03 (28-09 15:0x) - đáp án HUẤN LUYỆN** (Love Unseen mới có một chương train; chương này nhiều đối đáp ba người
không lời dẫn). A = Claude gán, B = agent soát đối kháng. Phát lại qua host 100%. B không thấy câu nào sai người nói chắc chắn;
A chấp nhận:

| chỗ | A ghi | kết luận | bằng chứng |
|---|---|---|---|
| 354 "Ừ, thật luôn." | KAKERU, NARUMI~ | NARUMI đầu, KAKERU đủ | người ngoài xác nhận lời Hayase (352); Narumi hay mở câu đáp bằng "Ừ," (252, 370); 355 ghép "ánh mắt Narumi và Hayase" |
| 343 "Mày... Tội cho Koharu" | NARUMI, HAYASE~ | cả hai đủ, NARUMI đầu | "mày" chỉ Kakeru-Narumi dùng; "Koharu" là cách gọi của Hayase (04:625) - bản dịch có thể đặt đại từ |
| 66, 339 | X, Y~ | cả hai đủ | không dấu xưng hô; lựa chọn đầu giữ theo mạch |
| 49 "Nâng ly!" | HAYASE, NARUMI | thêm KAKERU~ | cả nhóm cụng ly (quy tắc 6) |
| 102, 157, 236 | N | N,T | câu hỏi tu từ / phản ứng tức thời (quy tắc 4), như 23, 43, 137, 147 |
| 191, 357, 7 | neutral | thêm happy / sad / afraid,happy | cue "nhẹ nhõm", "khóc", "mừng"+"bồn chồn" |
| cảnh hôn 224-226, 233; tiếng cười 104, 276, 282, 286, 380 | neutral | thêm cảm xúc của cảnh | nhất quán với 73, 77, 153 |

Host sai (giữ đáp án): 350 - `HAPPY_EVIDENCE_PATTERN` bắt "mừng" trong "bữa tiệc chào mừng".

**Two Childhood Friends 107 (28-09 20:xx) - đáp án HUẤN LUYỆN, vòng dữ liệu v5** (dòng 『』 và người nghĩ là hai chỗ model sai
nhiều nhất trên bộ LN). A = Claude gán, B = agent soát đối kháng (`scratchpad/review_tcf107.md`). Phát lại qua host: không
LỆCH LUẬT. B không thấy câu nào sai hẳn người nói; A chấp nhận cả năm điểm:

| chỗ | A ghi | kết luận | bằng chứng |
|---|---|---|---|
| 18 dòng 『』 | AIDA, AIDA MASAMICHI, KÝ SINH TRÙNG | KÝ SINH TRÙNG đầu, thêm CON KÝ SINH TRÙNG, NPC*~ | cả cuốn gọi nó "ký sinh trùng" (102 lần/49 file, cả sau khi lộ tên), 042:64 và 082:94 để tên ấy đầu - lựa chọn đầu là cụm đáp án của B-cubed, một thực thể hai tên đầu thành HAI người; quy tắc 7c |
| 35, 48-50 | hai người nửa điểm | cả hai đủ | lời kể 36 "Họ thực sự nghĩ như vậy", 51 "Yoshihito và Kirako thực tâm nghĩ vậy"; lặp đúng lỗi đã sửa ở 042:76-77 |
| 83 "Hừm. Không xuất hiện à." | cả hai đủ (trái đầu file) | YOSHIHITO đủ, KIRAKO~ | "Hừm" mở câu là tật của Yoshihito (034:147, 049:203, 060:135; Kirako một lần 081:135) |
| 89, 91 | sad, neutral | thêm sarcastic | 90 "Với giọng điệu tự giễu, Aida nói" nằm giữa hai câu |

Host sai (giữ đáp án): 35 - cue "đau lòng" trong câu hỏi tu từ BÁC BỎ việc đau lòng ("Tại sao phải đau lòng vì người khác
chứ?"). `voice_identity --gold-check`: two_childhood_friends 9 người, không nhập ai.

**Yamiyo no Hotaru 009 (28-09 22:xx) - đáp án HUẤN LUYỆN, vòng dữ liệu v5** (truyện ngắn Giao thừa: đối đáp Tomobe - Hina
không lời dẫn, 『』 của Tọa Phu Đồng Tử chen giữa lời Magoroku/Mari, "ả" = Hina không gọi tên). A = Claude, B = agent soát
(`scratchpad/review_yamiyo009.md`). B không thấy câu nào sai người nói chính; A nhận hết đề xuất:

| chỗ | A ghi | kết luận | bằng chứng |
|---|---|---|---|
| 7, 129, 144 | tên đủ | thêm NPC*~ | nói trước khi lời kể gọi tên (10, 132, 153) - quy tắc 5, tiền lệ 141:38, 155:2-3 |
| 13, 16, 17, 20, 28, 36-38, 48, 52, 75, 110, 120, 169, 176 | N | N,T NARRATOR,TOMOBE | tự nhủ / câu hỏi tu từ của người kể (quy tắc 4); 13 "thời Showa ư?" được Hina đáp ở 14 |
| 186, 196, 197, 199, 202 / 200 | N | N,T HINA~ / HINA đủ | tiếng lòng xưng "ta" trong lời kể ngôi ba; 200 trọn là lời trong đầu |
| 93, 135, 150, 152, 182, 192, 194, 204 | người nói | thêm NARRATOR~ | tiếng không lời (quy tắc 8, 141:173) |
| 159 | MARI | thêm MAGOROKU~ | "anh em tôi thấy thật ái ngại" đáp câu "cảm ơn anh trai cô ấy" |
| 8, 86, 122, 161, 188, 199, 200 | neutral | thêm surprised / afraid / happy / angry | "kinh ngạc", "bất an", "lo âu", "e sợ", "đê mê", "thống khoái" |
| 84, 99 / 127 / 54, 85 | normal | soft + whispering / loud / 0-2 | "lẩm bẩm" / "gào" / "!!" |

Host sai (giữ đáp án): 40 "vui vẻ" là CỐ TỎ RA vui; 128 "gào lên" là Hina đùa. "Ả" = Hina: "đứa em gái" = Aoi (079:299), "tảng
mỡ thừa" = Uemon (079:207). `voice_identity --gold-check`: yamiyo 15 người, không nhập ai. Phát lại: 43 + 43 lượt, không
LỆCH LUẬT.

**Nageki no Bourei 53 (28-09 22:xx) - đáp án HUẤN LUYỆN, vòng dữ liệu v5** (truyện ngắn ngôi thứ nhất, bảy người đối đáp,
nhiều câu chỉ suy từ mạch). A = Claude, B = agent soát (`scratchpad/review_nageki053.md`). B không thấy câu nào sai người
nói chính; A nhận:

| chỗ | A ghi | kết luận | bằng chứng |
|---|---|---|---|
| 66 "chắc em sẽ thử nín thở" | NARRATOR, SITRI~ | thêm KRAI đủ | cụm trích nằm trong câu tu từ của Krai (65, 67 N,T); quy tắc 8 chỉ hạ người gốc lời |
| 29, 30, 106 | N | N,T KRAI | phản ứng tức thời của người kể (tiền lệ 65:294), như 22 |
| 75 "Kill, kill" | KILLIAM | thêm NARRATOR~, NPC*~, excited | tiền lệ 20:178, 65:41; lời dẫn chỉ nói "con quái vật" |
| mọi dòng | tên thật | thêm SIDDY, ANSSY, LIZZY, LUCY | biệt danh trong chương (70, 91) và lời kể cuốn 5 (46:1375, 52:371), quy tắc 11 |
| 103 "Hay đó!!" | ... LUCIA~ | bỏ LUCIA~ | Lucia là người đề xuất cả đám đáp lại |
| 16, 51 / 37, 102 / 26, 42, 72 | neutral / ... | happy,tender / afraid / sarcastic / loud / NARRATOR~ | "vui", "hoảng hốt"; giọng mỉa; hét |

A giữ: 33 "HẢ?!" Lucia (49:1353 người làm thác cho Luke; 49:725-730 cùng khuôn), 95 "Ừm." Ansem (49:1673...), 41 "Đội
trưởng" = Lucia (49:823). Host sai: 6 "Khóc" trong tên nhóm "Vong Linh Than Khóc". Dấu ~ ở 4 dòng khoá N (45, 74, 90, 101)
giữ lại dù score_models bỏ qua: segment_diff.py dùng nó khi bộ tách mới (dev/comma-dialogue) tách các câu ấy thành thoại.
`voice_identity --gold-check`: nageki 20 người, không nhập ai. Phát lại: 22 + 22 lượt, không LỆCH LUẬT.

**Yamiyo no Hotaru 225 (29-09 00:xx) - bộ đo LN MỞ RỘNG** (chương chưa học, "Chap 169 (2)": ngôi thứ nhất Tomobe, Azuma -
Gensei - Shiro đối đáp, tên Gensei chỉ lộ ở 72, cô con gái út nhà Ako không gọi tên). A = Claude, B = agent soát đối kháng
(chỉ đọc). B đồng ý người nói ưu tiên 92/92 dòng D/T, trọn tập 91/92; kiểm lại mọi khẳng định trong đầu file (18/19 một câu
của Azuma, các cặp lượt 44/45, 54/56, 67/68, 71, 135 là Tomobe, Ako = Akou Murasaki qua 026:5, 038:149, 226:477-499). A nhận:

| chỗ | A ghi | kết luận | bằng chứng |
|---|---|---|---|
| 135 "Ha, haha…" | TOMOBE, GENSEI~, happy đầu | TOMOBE, `neutral,afraid,happy` | 133 "Bị lộ rồi" - cười gượng của người bị lộ; 136 Gensei nhìn nghi hoặc, không có chứng cứ y cười |
| 116 "Đây là…" | N | N,T NARRATOR,TOMOBE | phản ứng bỏ lửng ngay trước câu hỏi 117, cùng khuôn 99/110/138 |
| 4, 5 / 72 / 84 | neutral | thêm surprised,angry / afraid / afraid | "bối rối và khó chịu"; "run rẩy" (cùng cue đã dùng ở 51); "e ngại" + 86 "nghi ngờ, cảnh giác" |
| 47 "Thủ lĩnh-sama...?" | TOMOBE | thêm SHIRO~ | cùng khuôn 44 |

A giữ: 143 "Ừ. Nhờ cậu." = Azuma (lời người đi nhờ ở 140; Gensei xưng hô trang trọng, không gọi "cậu") dù 144 là lời dẫn
của Gensei; KIRISOU (phiên âm khác ở 112) không thêm vì 225 không dùng. Host sai (giữ đáp án): 33, 45, 125 (ghi trong đầu
file). `voice_identity --gold-check`: yamiyo 18 người, không nhập ai. Phát lại: 100/100, không LỆCH LUẬT.

**Nageki no Bourei 62 (29-09 01:xx) - bộ đo LN MỞ RỘNG** (ngoại truyện "May Rủi và Vận Xui": ngôi thứ nhất Krai, Lucia, một
bà thầy bói vô danh nói dài; nguồn hỏng dấu nháy ở 53-55). A = Claude, B = agent soát đối kháng (chỉ đọc, tự đưa lựa chọn
đầu qua `_validate` của host - cả chương một lô và chia lô 4-8 mọi độ lệch - không dòng nào mất điểm người nói). B đồng ý
người nói ưu tiên 81/81 dòng D/N,T; trọn tập 55/81 trước khi sửa. A nhận:

| chỗ | A ghi | kết luận | bằng chứng |
|---|---|---|---|
| 25 dòng bà thầy bói | NPC* | thêm UNKNOWN~ | quy tắc 5: có manh mối thì UNKNOWN chỉ nửa điểm; tiền lệ LU 07:104-111, Nageki 73:2, 53:107 |
| 56 “Mọi loại vận xui” / 57 | NARRATOR, NPC*~ / N | thêm KRAI đủ / N,T | cụm trích mở câu nghĩ của Krai ("nghe hơi cường điệu", cùng khuôn 33, 72, 77, 91); tiền lệ 53:67 |
| dòng Lucia | LUCIA, LUCIA ROGIER | thêm LUCY | biệt danh cả cuốn (52.txt 34 lần), như gold 53 |
| 136 | N | N,T | lời bác tức thời, song song 135, 137 |
| 26, 71, 141 / 14 / 111 / 10, 42, 46 / 23, 62 / 75 | neutral | thêm angry / surprised / happy / afraid, angry, sad / excited, afraid / angry + cường độ 0-2 | "quát", "cực kỳ khó chịu"; "Lucia ngạc nhiên"; "giọng vui vẻ"; "đầy cảnh giác", "sủa lại", "giọng thương xót"; "Ô hô" như 3, "nuốt nước bọt"; tập có neutral thì cường độ phải chạm 0 |

Sửa đầu file (B chỉ ra): 54-55 là host NỐI LỜI (`_repair_continued_dialogue_speakers`) chép người nói của 53, không phải
`_repair_explicit_attribution` (hàm ấy chỉ xét lời kể cùng đoạn); "101-105" là dòng nguồn (= seq 53-55); bằng chứng mạnh hơn
cho 62 "Hả?!" = Lucia (bà thầy bói lờ đi tiếng chen ngang như với Lucia ở 27, 44, còn câu nào Krai nói bà đều đáp); bà
thầy bói có thể chính là "Con Mắt Thần" của Astral Divinarium được nhắc ở 65:443, 66:1303 nhưng không nói ở đó, và danh
hiệu ấy dùng chung cho nhiều nhà chiêm tinh (66:1311) -> NPC* đủ vẫn đứng, CON MẮT CỦA THẦN không điểm. B cũng bắt lỗ hổng
quy trình: chương đo chưa vào `SPLIT["test"]` thì lần dựng dữ liệu sau sẽ lọt vào train - đã thêm. `voice_identity
--gold-check`: nageki 20 người, không nhập ai. Phát lại: 62 không lệch (hai chỗ lệch còn lại của cuốn là 73, có từ trước).

**Two Childhood Friends 060 (29-09 02:xx) - bộ đo LN MỞ RỘNG** (ngôi ba rồi ngôi thứ nhất trong một chương; sát thủ Linlin
"Ngộ... yo/ne/aru"; 11 dòng 『』 của ký sinh trùng). A = Claude, B = agent soát đối kháng (chỉ đọc; tự dò cue host và lint
nhãn). B đồng ý người nói ưu tiên 113/113 (52 D/T/T,D + 61 N,T); trọn tập 99/113. A nhận:

| chỗ | A ghi | kết luận | bằng chứng |
|---|---|---|---|
| 11 dòng 『』 | KÝ SINH TRÙNG, CON KÝ SINH TRÙNG, NPC*~ | thêm UNKNOWN~, NARRATOR~ | cho khớp 042:64, 082:94 - hai chương test cùng truyện chấm như nhau |
| 16, 57 "Hự!?", 110 "Tou!", 67 "Hừm?" | người nói | thêm NARRATOR~ | tiếng kêu/hô, quy tắc 8; tiền lệ 082:79, Yamiyo 141:18, LU 07:13 |
| 96 / 69 | N | N,T (Yoshihito đủ) / N,T (Yoshihito ~) | giữa chuỗi lập luận tức thời 94-97; 69 nửa tiếng lòng nửa lời kể |
| 54, 8, 17, 27, 63, 25 / 40, 179 / 41 | neutral | thêm afraid / surprised / angry / afraid | host bắt "hoảng loạn" ở 54; "chết lặng", "giật mình", "bối rối", "ngơ ngác", "hoang mang"; "phẫn nộ", "điên tiết"; "nhát gan, sợ" |
| 6 "Tiếp theo là mày đó yo." | neutral,happy,excited | bỏ happy | câu đe doạ - GOLD_GUIDE lấy chính "happy cho câu đe doạ" làm ví dụ đọc sai |
| 132, 123, 71, 75, 87, 149 | ... | thêm whispering / surprised / happy / sarcastic / tired / sarcastic | "lẩm bẩm"; câu bỏ lửng; "đắc thắng"; "cười khẩy"; "ngán ngẩm"; "cười nhạo" |

A giữ: 13 "Vậy thì, tại sao?" Kirako chỉ ~ (người kể tự hỏi về Kirako - 10 "...Mà không hẳn." là người kể tự sửa lời); 152
"Vừa phải thôi." (khoá N) Yoshihito vặc lại trong đầu (cùng cụm ở 056:151). Chưa thêm AIDA MASAMICHI~ (tên thật lộ ở 107) cho
cả cuốn: chấm từng chương, model không thể biết. Đầu file sửa khoảng cách chương, góc ngôi ba, chữ "tiếng lòng". B chỉ ra chương
đo phải vào SPLIT["test"] - đã thêm. `voice_identity --gold-check`: two_childhood_friends 10 người, không nhập ai. Phát lại:
100/100.

**Nise Seiken 086 (29-09 02:xx) - bộ đo LN MỞ RỘNG** (ngôi ba; "đấu khẩu thầm lặng" Alistar - Magali bằng "(...)", Rubon và
Elizabeth Stream, lính Toà án dị giáo, thanh kiếm nói bằng "[...]"). A = Claude, B = agent soát đối kháng (chỉ đọc; grep 158
file, dò cue host). B đồng ý người nói ưu tiên 60/60 (41 D + 19 T); trọn tập 49/60. A nhận:

| chỗ | A ghi | kết luận | bằng chứng |
|---|---|---|---|
| 57, 76, 102, 104 "[...]" | NARRATOR, THÁNH KIẾM~ | thêm NGUYỀN KIẾM~ | "Nguyền Kiếm" 533 lần/104 file (tên Alistar đặt, 009:243-245, 010:127-129; 085 chỉ dùng tên này) > "Thánh Kiếm" 429 lần; tên thật bị giấu (008:299) |
| 66 (lời kể bị khoá D) | NARRATOR, NPC*~ | chỉ NARRATOR | NPC là lỗi host nối lời; tiền lệ LU 07:90 - người bị gán nhầm không được điểm |
| 10 tiếng kêu (51-53, 68, 69, 83, 105, 108, 109, 111) | người kêu | thêm NARRATOR~ | quy tắc 8; tiền lệ Yamiyo 141, LU 07, TMA 378:79 |
| 83 "Ugh!" | ELIZABETH, ALISTAR~ | cả hai đủ, Elizabeth trước | 84 "cơ thể cô bé run rẩy" / 85 Alistar "giật nảy mình"; "Ugh!?" là tiếng của Alistar ở 071:167 |
| 111 "Ehh…" | ALISTAR, MAGALI~ | bỏ MAGALI~ | 112 "Alistar hồn xiêu phách lạc"; Magali "nôn nhẹ" (113); "Eehhhh.." là tật của Alistar (085:119) |
| 5 / 60 | N | N,T, người nghĩ ~ | "Im lặng chính là thừa nhận. Rubon nghĩa vậy" (lời dẫn liền sau); "...cơ chứ" (tiền lệ 132:30) |
| 64, 73, 106, 48, 77, 70, 11, 13, 23, 50, 89, 90 / tiếng kêu / Rubon 24, 26, 30 / 91 | neutral | thêm theo cue | "ghét cay ghét đắng", "sự bất ngờ", "khẽ hét", "nhăn nhó", "ác cảm", "tàn ác", lời kể mỉa; kêu đau cho sad/angry; Rubon giả nhân nghĩa (25 vặn lại); "Cha!!" |

Host sai (giữ đáp án): 66-67 - dấu nháy mở ở 65 không đóng, host nối lời gán lời kể 66 và tiếng thét trong đầu Alistar 67
cho người lính; nhánh dev/curse-noun (82ed7a7) sửa 67 ("(" mở lượt mới). B xác nhận các khẳng định còn lại (RUBON STREAM 077:39,
ELIZABETH STREAM 071:213..., Herge Hubner 002:241, "tớ/cậu" giữa Alistar - Magali 005:69...). `voice_identity --gold-check`:
nise_seiken 9 người, không nhập ai. Phát lại: chỉ 66, 67 lệch (host).
