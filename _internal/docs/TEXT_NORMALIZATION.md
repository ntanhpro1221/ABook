# Chuẩn hoá chữ cho giọng đọc (text normalization)

Chủ sách 04-10: "nghiên cứu thêm về text normalization của studio. hiện tại nó đã ngon chưa? có sẵn bộ text normalization nào
trên mạng không? ... nhất là từ tiếng anh sang cụm để máy tiếng việt đọc, chính là cách mà người việt đọc tiếng anh, đọc số,
đọc các cụm từ ... tổng hợp thành một quy trình text normalization ngon lành, nghiêm túc".

Tài liệu này gồm bốn phần:
- trả lời "đã ngon chưa" bằng số đo;
- những gì thế giới đã có;
- quy trình đề xuất;
- cách đo và lộ trình.

Chuẩn hoá chữ là **biến đổi để đọc**: chữ hiện cho người đọc không bao giờ đổi, và app không tự bỏ chữ nào của truyện (chỉ đề
xuất, người nghe đồng ý mới áp).

## 1. Hiện trạng: chưa ngon, nhưng hỏng đúng ở chỗ truyện dùng nhiều nhất

### Chữ đi qua những gì (04-10, đọc code + chạy thật)

**Studio** (`tts.py` → `vieneu 3.8.1`):
1. `text_processing.normalize_text`: Unicode, khoảng trắng, 「」 thành “”.
2. `spoken_symbols_to_words`: + = × ÷ → thành chữ; ngoặc thành dấu phẩy; dãy ký hiệu chửi thề thành "…".
3. Bảng cách đọc tên (`pronunciations`). Tên viết hoa không phải âm tiết Việt được đọc theo:
   - từ điển CMU (luật trong `ENGLISH_TO_VIETNAMESE.md`), không có thì
   - LLM đề xuất (kiểm âm tiết Việt), không được thì
   - đánh vần;
   - kết quả được khoá; người nghe sửa được.
4. Chuẩn hoá thán từ ([cười] → "Ha ha...").
5. Bên trong vieneu: **sea-g2p 0.9.1** chuẩn hoá HAI lần (theo câu, rồi cả khúc), hạ chữ thường, rồi G2P. Từ nào có trong từ
   điển tiếng Anh thì đọc bằng âm vị tiếng Anh; từ lạ thì cắt mảnh hay đánh vần.

**Nghe ngay**:
- VieNeu: chỉ có luật số La Mã của app (`readaloud/vieneu.spoken_tokens`), rồi sea-g2p. KHÔNG có bảng tên.
- Supertonic: sea-g2p normalize rồi làm sạch ký hiệu.
- Edge: nhận CHÍNH chữ mà giọng trên máy nhận (`readaloud/spoken.py` -> `vieneu.spoken_tokens`, `speaks_english` True; điện thoại `SpokenText.kt`). Đo a39 (Whisper, 74 câu bịa x 2 giọng): âm tiết sai 29% (thô) -> 12%; tên Nhật + kính ngữ 33% -> 2%, tiếng kêu, "1,500", "+50" "x2" "3-5" "100/250", viết tắt thắng lớn; xấu hơn ở 5 ca nhỏ (mức nhiễu của ASR).
- Giọng dùng khoá (Azure, Google, FPT, Viettel): chữ thô; nhà cung cấp tự chuẩn hoá (chưa đo).

### sea-g2p chạy thật trên câu kiểu truyện

| vào | ra | |
|---|---|---|
| mở level mới, dùng skill | giữ "level", "skill" (âm Anh) | người Việt đọc "lê-vồ", "xờ-kiu" |
| HP và MP | `<en>h p</en>` và "mờ phê" | hai hệ chữ cái trong một câu |
| 1,500 vàng | "một phẩy năm vàng" | sai: dấu phẩy ngăn nghìn kiểu Anh |
| Tempest XIV / cấp XL | "ích i vê" / "ích lờ" | Studio chưa có luật La Mã |
| Hmm~ để xem | "hmm khoảng" | "~" là kéo dài, không phải "khoảng" |
| Lv.5 | "lv. năm" | |
| Ừm... vâng | "ừm. vâng" | mất chỗ ngập ngừng |
| Facebook, Google | âm Anh | người Việt: "phây-búc", "gu-gồ" |
| 1.500, 15/8, 7h30, 25%, 1m65, 48kg, 3-5 người, tầng 4, lần thứ 3, OK, hạng S, -san | đúng | |

Số, ngày giờ, đơn vị, phần trăm: tốt. Chỗ hỏng là từ mượn, viết tắt, ký hiệu cảm xúc, nghìn kiểu Anh, và Nghe ngay không có
bảng tên.

### Truyện thật dùng gì (161 cuốn trong Corpus/_full, 29.115 chương, 87,3 triệu chữ)

Tính trên 10.000 chữ, xếp theo tần suất:

| loại | /10k chữ | ghi chú |
|---|---|---|
| Tên riêng nước ngoài (romaji, Hàn, Anh) | **283** | có ở cả 161 cuốn; 52.000 tên khác nhau, 2.000 tên đầu chỉ phủ 76% → đuôi rất dài, phải tự động |
| Dấu "…" | **94** | 96% số chương; là ngập ngừng, không phải dấu chấm |
| Từ mượn viết thường (game, mana, skill, goblin) | 31,5 | 2.000 từ đầu phủ 84% → làm từ điển được |
| Từ nước ngoài viết hoa không phải tên (Skill, Elf, Clan, Master) | 24,6 | 2.000 từ đầu phủ 93% |
| Kính ngữ Nhật, romaji nối gạch (-san, -kun, senpai) | 27 (48 ở truyện Nhật) | 107 cuốn |
| Ngoặc 「」『』 | 24 | 82 cuốn |
| Số các loại | 23 | phần lớn là số 1-3 chữ số; "cấp/tầng/số/khoảng/thứ" đứng trước |
| Gạch nối dài, !?, ~ | 19 / 12 / 5,7 | |
| Ngoặc vuông / tròn / 【】 | 14 / 9 / 1,5 | thường là bảng trạng thái, kỹ năng |
| Thán từ kéo dài (Aaaa, Hmmm) | 8 | |
| Dấu * | 7,9 | |
| Chữ cái đơn hoa / viết tắt | 4,9 / 4,9 | 100 viết tắt đầu phủ 74%: TN, MP, HP, TV, NPC, DP, MAX, PK, SP, SSR, OK, VIP, AGI, STR, EXP... |
| Chữ Hán, Hàn còn sót | 3,3 | |
| Emoji / kaomoji | 1,7 | |

Kết luận ưu tiên:
1. tên riêng;
2. "…" và dấu ngắt;
3. từ mượn;
4. kính ngữ;
5. ngoặc;
6. viết tắt;
7. số (đã tốt, chỉ vá chỗ hỏng).

## 2. Thế giới đã có gì

| công cụ | cách làm | số/ngày/đơn vị | viết tắt | chữ nước ngoài | giấy phép | tình trạng |
|---|---|---|---|---|---|---|
| sea-g2p (VieNeu) | 17 tầng luật, Rust | có | bảng nhỏ | âm vị Anh, thẻ `<en>` | Apache-2.0 | đang phát triển |
| VietNormalizer | regex + từ điển CSV + phiên âm theo luật | có, cả số thứ tự, khoảng | từ điển (NASA → na-sa) | từ điển + luật | MIT | 2026, chưa có số đo |
| donglao-g2p | luật + bộ định tuyến Việt/Anh + CMUdict | có, phân biệt "." và "," | có | âm vị Anh theo từng từ | Apache-2.0 | mới (08-2026) |
| Vinorm | từ điển + regex | cơ bản | từ điển | từ điển | phi thương mại | bỏ từ 2020 |
| NeMo text-processing | WFST | **không có TN tiếng Việt** (chỉ ITN) | | | Apache-2.0 | |
| Dang et al. 2022 | BERT gắn nhãn 19 lớp + luật | có | từ điển + đánh vần | từ điển | chỉ có bài báo | |

Nguồn:
- https://github.com/pnnbao97/sea-g2p
- https://arxiv.org/html/2603.04145v1 (VietNormalizer, https://github.com/nghimestudio/vietnormalizer)
- https://github.com/DongLaoAI/donglao-g2p
- https://github.com/v-nhandt21/Vinorm
- https://docs.nvidia.com/nemo-framework/user-guide/25.09/nemotoolkit/nlp/text_normalization/wfst/wfst_text_normalization.html
- https://arxiv.org/pdf/2209.02971

Các phát hiện chính:
- **Phân loại chữ không chuẩn:** Sproat và cộng sự 2001 là khung gốc
  (https://www.clsp.jhu.edu/workshops/99-workshop/normalization-of-non-standard-words). Dang 2022 thu về 19 lớp cho tiếng Việt.
  Lỗi câu của bộ gắn nhãn 6,67%; lớp "dãy chữ số hay con số" yếu nhất (F1 0,77).
- **Chữ nước ngoài là điểm yếu chung:**
  - VLSP 2020: câu nhiều từ mượn chỉ nghe hiểu 68–89%, kể cả người thật đọc (https://aclanthology.org/2020.vlsp-1.7.pdf).
  - Có đội huấn luyện seq2seq phiên âm tên Anh sang âm tiết Việt ("Anderson" → "an đơ sơn").
  - Không có từ điển phiên âm Anh–Việt mở nào đủ lớn.
- **Viết tắt không có một cách đúng:** ngay đài truyền hình cũng trộn "vê tê vê" (tên chữ cái Việt) với "ai xi ti" (tên chữ cái
  Anh) (https://tuoitre.vn/nhung-chu-cai-nhay-mua-374522.htm). Phải quyết từng mục bằng từ điển, và giữ nhất quán trong một cuốn.
- **Đọc số:** quy tắc đã rõ: mốt, lăm, tư, linh (Bắc) / lẻ (Nam), nghìn / ngàn, dấu phẩy thập phân
  (https://en.wikipedia.org/wiki/Vietnamese_numerals).
- **LLM làm chuẩn hoá:**
  - GPT-4 hơn hệ luật sản xuất ~40% với tiếng Anh (https://arxiv.org/html/2309.13426v2).
  - PolyNorm dùng cho 8 ngôn ngữ, không có tiếng Việt (https://arxiv.org/html/2511.03080v1).
  - Mạng nơ-ron thuần có lỗi nguy hiểm, kiểu "3 cm" → "ba ki-lô-mét".
- **Bộ thử:** chưa có bộ thử chuẩn hoá tiếng Việt công khai; phải tự dựng.

## 3. Quy trình đề xuất

Một mô-đun **chung cho mọi giọng** (VieNeu, Supertonic, ZeroTTS, và các lớp từ điển cho cả Edge), chạy TRƯỚC engine.
- **Đầu ra:** âm tiết tiếng Việt và dấu câu ngắt. Đầu ra chỉ còn âm tiết Việt nên lần chuẩn hoá thứ hai bên trong sea-g2p không
  còn gì để làm sai (hết chuyện hạ chữ thường làm hỏng luật phụ thuộc chữ hoa, hết chuyện tên đã phiên âm bị đọc lại kiểu Anh).
- **Hai nền tảng:** máy tính (Python) và điện thoại (Kotlin) dùng cùng luật và cùng fixture, như `units`.

**Tầng 0 – làm sạch.** Đã có (`normalize_text`). Thêm vào:
- 「」『』 thành ngoặc kép;
- 【】 và [ ] của bảng trạng thái thành dấu ngắt;
- bỏ chữ Hán/Hàn sót, emoji, kaomoji, nhưng giữ một chỗ ngắt nghỉ.

**Tầng 1 – gắn nhãn.** Tách token, gắn lớp theo khung Sproat/Dang:
- số đếm, số thứ tự, thập phân, khoảng, tỉ số, phân số, phần trăm;
- ngày, giờ, tiền, đơn vị;
- La Mã;
- viết tắt, chữ cái đơn;
- từ mượn, tên riêng, kính ngữ;
- thán từ, ký hiệu.

Luật trước, mơ hồ thì ghi lại để đo.

**Tầng 2 – lớp xác định (luật, không LLM).** Số, ngày, giờ, đơn vị, tiền dùng lại sea-g2p (đã tốt), vá thêm:
- nghìn kiểu Anh: "1,500" + danh từ đếm (vàng, xu, người, yên…) → một nghìn năm trăm; mơ hồ thì ghi lại;
- "x2" → "nhân hai"; "3/5" + danh từ → "ba phần năm";
- La Mã: luật của Nghe ngay (8403c1e7) dùng chung cho Studio;
- "Lv.5" / "Level 5" → "cấp năm" hay "lê-vồ năm" (một lựa chọn, ghi trong từ điển);
- "~" sau thán từ → kéo dài âm cuối, KHÔNG phải "khoảng";
- "…" giữ thành chỗ ngập ngừng (không thành dấu chấm).

**Tầng 3 – từ điển dùng chung** (có phiên bản, đi kèm app; máy đề xuất, máy kiểm):
- *Viết tắt và thuật ngữ game* (100 mục đầu phủ 74%). Mỗi mục một cách đọc cố định:
  - HP, MP, NPC, EXP, AGI, STR, SSR, PK, MAX…;
  - "TN" (ghi chú người dịch) là trường hợp riêng: đề xuất bỏ đọc, người nghe đồng ý mới áp;
  - mặc định game/tiếng Anh đọc tên chữ cái Anh theo cách Việt ("ếch pi"); từ Việt hoá rồi thì đọc như từ ("ti vi", "vi-ai-pi"
    hay "víp" chọn một);
  - **nhất quán trong một cuốn** là luật cứng.
- *Từ mượn* (2.000 từ đầu phủ 84–93%): game, skill, mana, level, guild, Elf, Clan, Master, Facebook, Google… Mỗi mục được:
  - LLM đề xuất cách đọc kiểu Việt ("lê-vồ", "xờ-kiu", "ma-na", "phây-búc");
  - kiểm âm tiết Việt hợp lệ (`_valid_vietnamese_spoken_form`);
  - kiểm vòng ASR (thu thử → nghe lại → so);
  - rồi mới vào bảng.
  Từ đã Việt hoá phổ biến (ô tô, ti vi, ok) đọc như từ Việt.
- *Kính ngữ Nhật:* -san, -kun, -chan, -sama, senpai, sensei: cách đọc cố định ("xan", "cun", "chan", "xa-ma", "xen-pai").

**Tầng 4 – tên riêng (đuôi dài, phải tự động, theo từng cuốn).**
- *Studio:* giữ đường hiện có (CMU → LLM → khoá → người nghe sửa). Mở rộng để bắt cả tên viết thường lặp lại; tầng 3 lo từ mượn.
- *Phiên âm theo luật* (chạy được trên điện thoại, không cần LLM):
  - romaji Nhật (Hepburn → âm tiết Việt: Kou-ta-rou → "Cô-ta-rô");
  - phiên âm Hàn chuẩn RR (Chae-yeon → "Che-dơn");
  - hai hệ này đều có luật rõ, đáng làm thành luật xác định có test.
- *Tên tiếng Anh:* [Đo 04-10] GIỮ NGUYÊN chữ Anh cho máy nói được âm vị Anh (VieNeu qua sea-g2p, ZeroTTS, Edge: Whisper nghe lại đúng
  Rose / Mike / Facebook / Fireball; Việt hoá "Rô-dơ / Mai-cơ" lại bị nghe thành Roger / Michael). Việt hoá qua CMU chỉ cho máy chỉ đọc
  được âm tiết Việt; tên tác giả tự đặt cần LLM hay luật đọc theo chính tả.
- *Nghe ngay:* hiện không có tầng tên. Dùng phiên âm theo luật (romaji, Hàn) + từ điển dùng chung + điều ước của người nghe
  (`book_wishes` đã lưu nhưng chưa áp).

**Tầng 4b – model phiên âm từ riêng** (chủ sách 04-10: "tách ra một lớp train khác ... llm này sẽ chỉ làm việc theo kiểu nhận
word và cho ra dạng normalized của word").
- **Vì sao tách khỏi model phân tích:** mỗi model một mục đích, đo riêng, phát hành riêng. Tên không có quy tắc và từ điển không
  bao giờ đủ, nên phần đuôi dài cần một model học cách phiên âm kiểu Việt.
- **Vào / ra:**
  - Vào: một token nước ngoài, kèm gợi ý lớp (tên / từ / viết tắt) và gợi ý gốc (Nhật / Hàn / Anh / không rõ) nếu tầng 1 biết.
  - Ra: âm tiết Việt nối gạch theo quy ước của app (`ENGLISH_TO_VIETNAMESE.md`), qua cửa kiểm âm tiết Việt hợp lệ.
  - Không ngữ cảnh câu: cùng từ thì cùng cách đọc, lưu đệm theo cuốn.
  - Chủ sách 04-10: "bài toán này cực kỳ cụ thể đầu vào là một từ tiếng anh, nhật, hàn, từ trong tên,... và đầu ra là normalized
    của nó để máy đọc".
    - Gợi ý gốc lấy theo CUỐN (light novel Nhật / truyện Hàn), không theo câu.
    - Từ nối gạch tách trước ("Tanaka-san" → "Tanaka" + "san").
  - Cụm từ KHÔNG giao cho model, mà là luật tầng 2:
    - số La Mã sau danh từ;
    - số đi với chữ ("Lv.5", "x2", "1,500 vàng", "3/5 chai");
    - ký hiệu dính từ ("Hmm~").
  - Ràng buộc cấp cuốn duy nhất: viết tắt cùng loại (HP / MP / SP) đọc cùng một hệ chữ cái.
- **Cỡ:** nhỏ để chạy cả trên điện thoại (ONNX, cỡ vài MB). So hai phương án bằng số đo:
  - transformer ký tự tự huấn luyện;
  - LLM nhỏ tinh chỉnh.
- **Dữ liệu:**
  - token thật từ Corpus/_full (52k tên + từ mượn), chia train / dev / test THEO CUỐN;
  - đáp án do LLM lớn đề xuất + luật CMU sẵn có + luật romaji / Hàn;
  - lọc qua kiểm âm tiết và vòng ASR.
- **Điện thoại yếu** (chủ sách hỏi 04-10). Ba lớp, máy nào cũng có lớp dưới cùng:
  1. *Bảng cách đọc đóng trong file `.abook`:* sách làm hay nhập trên máy tính mang sẵn cách đọc mọi từ nước ngoài; điện thoại
     chỉ tra bảng.
  2. *Model phiên âm (tải thêm, không đóng vào APK):*
     - chạy MỘT lần cho mỗi từ khác nhau của cuốn, lúc thêm sách hay chạy nền, rồi lưu đệm;
     - cỡ một cuốn: vài trăm đến nghìn từ × vài chục ms trên máy yếu = vài chục giây;
     - Chạy bằng ONNX Runtime dùng chung. Điện thoại đã tải ORT 1.30.0 theo yêu cầu (`OrtRuntime.kt`, ~12 MB nén) cho Gói nhạc và
       VieNeu; VieNeu dùng lại bản của Gói nhạc.
     - Khi thêm module thứ ba, gom ORT thành một thành phần dùng chung thật: tải một lần, đếm module đang cần, gỡ khi không còn ai
       cần. Thay cho cách VieNeu "ngó" thư mục Gói nhạc như hiện nay.
  3. *Luật thuần* (không tải gì, chạy mọi máy, cũng là lưới an toàn khi model ra dạng không hợp lệ):
     - romaji / Hàn theo quy ước đã nghiên cứu;
     - từ điển từ mượn và viết tắt;
     - đánh vần làm đường lùi cuối.
- **Thay thế:** Studio dùng nó thay bước LLM đề xuất cách đọc tên (bảng khoá và người nghe sửa vẫn giữ). Nghe ngay dùng nó cho mọi
  token nước ngoài chưa có trong từ điển.

**Tầng 4b – kết quả đo (phiên Model, 04-10) và vì sao HẠ ƯU TIÊN.**
- **Nhãn:** 7.000 token của 161 cuốn, do agent Claude làm theo `READING_FOREIGN_NAMES.md` + ca chủ sách (Sonnet viết, Opus
  phân xử TOÀN BỘ tập test). 5.000 token hay gặp nhất (train, 25 lô) + 2.000 token bốc phân tầng của 24 cuốn test (10 lô).
  - 5.093 nhãn chắc, 1.907 còn treo chờ chủ sách; nhóm treo lớn nhất: schwa, yu/yo Nhật, tên bịa âm vị hay mặt chữ.
  - Bộ nhãn + script chấm luật ở Corpus `research/tn/translit_bench/` (073aef12 → 62865d5e).
- **Model A:** transformer ký tự 4M tham số, đầu vào = token + gốc cuốn + loại + GỢI Ý của luật (romanization / english_vi);
  nhãn vẫn là của Claude. Ra không phải âm tiết Việt hợp lệ thì lùi về `_local_name_fallback` (M0). ONNX int8 4,9 MB,
  khoảng 5 ms/từ trên 1 luồng CPU x86.
- **Số (3 hạt, accept = khớp đáp án hay một cách đọc chấp nhận được, không phân biệt hoa/thường):**

  | hệ | dev (323) | test ok (749) | test đủ, gồm mục treo (1.314) |
  |---|---|---|---|
  | M0 `_local_name_fallback` | 38,7 % | 25,6 % | 24,7 % |
  | A chỉ token (1 hạt, lô 1-15) | 69,1 % | 44,0 % | 37,1 % |
  | A + gợi ý luật + lưới M0 | 85,8-87,0 % | 69,6-70,8 % | 63,0-65,4 % |
  | luật trước, model chỉ khi luật trả None | 87,9 % | 72,0-72,7 % | - |

- **Ranh giới luật / model (test ok):** khi luật ra cách đọc không cờ, luật đúng 90,6 % (model 82,7-85,6 %) - giữ luật. Khi
  luật trả None (356 token), model đúng 57-59 % - nhưng 289 trong số đó là token tiếng Anh, mà ở máy nói được tiếng Anh thì
  giữ nguyên chữ, không qua model. Phần model thật sự gánh - tên Nhật / Hàn luật trả None - chỉ có 45 token, model đúng
  22-24 %.
- **Vì sao hạ ưu tiên:** 45 token ấy gần hết là lỗi TIỀN XỬ LÝ của luật (chữ in hoa toàn bộ "KANATA", gạch nối / hậu tố
  "Seol-Ah", "PD-nim", viết dính "OkabeRintarou", luật Hàn từ chối "sh"), model làm tệ đúng ở đó ("KANATA" → "A"). Sửa luật
  rẻ và chắc hơn (Lead giao). Model chỉ còn giá trị khi có máy KHÔNG nói được tiếng Anh cần đích "vi" (04-10: chưa có).
  Giữ hạ tầng (nhãn, khung huấn luyện, ONNX); KHÔNG đo phương án B (Qwen3-0.6B) và M1 cho tới khi có máy cần "vi" hay luật
  None Nhật / Hàn còn nhiều sau khi sửa luật.
- **Số của chính các luật** trên bộ nhãn (luật main 04-10): Nhật 95,3 % (không cờ 99,3 %), Hàn 82,1 % (không cờ 98,9 %),
  Anh 87,8 %. Thiên lệch cần biết: agent làm nhãn có nhìn gợi ý của luật, nên số "không cờ" có thể được nâng nhẹ.

**Tầng 5 – nhịp và ngắt.** Đưa thành dấu câu ngắt mà engine hiểu:
- "…", "—" (gạch nối dài), "!?";
- thán từ kéo dài (Aaaa → "A… a", đã có ở Studio, chuyển sang dùng chung);
- dấu *.

## 4. Đo và lộ trình

**Bộ thử:**
- khoảng 600 câu bốc phân tầng theo lớp từ Corpus/_full; chữ truyện nằm ở repo riêng tư;
- đáp án cách đọc do agent Claude viết (chủ sách không chấm), hai agent độc lập rồi đối chiếu.

**Thước đo:**
- độ đúng theo câu và theo lớp (khung của Sproat; https://github.com/rwsproat/text-normalization-data);
- vòng ASR trên âm thanh thu thật cho tầng 3–4 (tên và từ mượn chỉ đo được bằng tai máy);
- test hồi quy trong CI.

**Lộ trình** (xếp theo lợi / công):
1. Bộ thử + đo đường cơ sở hiện tại (sea-g2p) theo lớp.
2. Tầng 5 (… — ~ !?) và tầng 2 vá (nghìn kiểu Anh, x2, Lv, La Mã cho Studio): nhỏ, chắc thắng.
   **Xong (05-11, dev/tn-tier25).** Phần lớn đã có sẵn trong `readaloud/vieneu.spoken_tokens` từ trước (bảng mục 1 là số
   04-10): nghìn kiểu Anh, "x2", "Lv.5", "?!", gạch dài dính chữ, khung 【】/[ ], La Mã I..XXXIX; Studio dùng chung qua
   `studio_tn`. Lượt này thêm (Python + Kotlin, bộ ví dụ chung `tests/fixtures/readaloud/spoken/reading_forms.json`, 100 ca,
   39 ca bảo vệ cách đọc cũ / không đoán thêm, trong đó 25 ca giữ nguyên cả chuỗi; pytest, vitest gọi backend Python thật và JVM cùng dùng file):
   - "…" / "..." cuối chữ mà câu nói tiếp bằng chữ thường, hay dính giữa hai chữ ("Ừm…vâng") → dấu phẩy: sea-g2p đọc mọi "…"
     là dấu chấm (giọng xuống, chữ sau như câu mới). Câu của Nghe ngay / Supertonic không cắt ở chỗ ấy nữa (`_groups`).
     Theo sau là chữ hoa hay hết đoạn: giữ.
   - "…" mở đầu đoạn hay ngay sau ngoặc mở ("...Không", "“…Vâng") → bỏ (sea-g2p để lại một dấu chấm trơ).
   - "~" sau chữ mà còn chữ nói tiếp ("Hmm~ để xem", "Hự ~ đau") → dấu phẩy (trước đây bỏ, dính liền).
     Cụm kéo giọng từng chữ ("Không~ chịu~ đâu~") chỉ ngắt ở cuối cụm, không chen dấu phẩy giữa từng chữ.
   - Nghìn kiểu Anh chỉ bỏ dấu phẩy khi có danh từ đếm / nhãn chỉ số, nhiều nhóm nghìn, hay hậu tố tiền / điểm G, pt.
     "1,500 kg", mã "A1,500B" và số trơ thiếu ngữ cảnh giữ nguyên; không đoán thập phân thành số nguyên.
   - La Mã 40..399 (có L / C, hai chữ trở lên) chỉ ngay sau danh từ đánh số ("Chương XLV", "tầng LX"); "size XL",
     "hạng C", "Louis XL" giữ.
   - "x1.5" → "nhân 1,5" (sea-g2p đọc "một chấm năm").

   Tăng phiên bản cache đọc từ 4 lên 5 ở cả hai nền để clip cũ / đã ghim được làm lại theo luật mới.

   Đo trên 349 chương / 186 cuốn bốc phân tầng (truyen 70 cuốn / 131 chương, ai-dich 70/139, sang-tac 40/67, khac 6/12;
   hạt 20261105; mỗi cuốn tối đa hai chương; 61.678 đoạn, 1.423.904 chữ, Unicode NFC từng dòng). Đoạn có cách đọc khác chữ gốc:
   trước 6.138, sau 9.756; so trực tiếp trước/sau có 4.175 đoạn đổi (6,77 %).
   Trên 105.700 khoảng câu theo bộ cắt TRƯỚC vá (kể cả "…" chốt khoảng), 4.458 khoảng đổi: "…" giữa câu 2.714,
   "…" mở đầu 1.674, "~" / "～" 104, nghìn mơ hồ giữ lại 1 (các lớp có giao nhau). Theo đoạn tương ứng: 2.479 / 1.672 / 102 / 1.
   Gạch dài, !?, khung trạng thái, x2, Lv, viết tắt và La Mã nhỏ giữ luật cũ; La Mã từ 40 và "x1.5" không gặp lần đổi nào (chỉ có fixture).
   Đọc tay 40 đoạn đổi phân tầng (22 giữa câu, 10 mở đầu, 7 kéo giọng, 1 số mơ hồ): 40/40 đúng theo luật, kể cả quyết định giữ số khi thiếu ngữ cảnh.
   Chưa đo bằng tai: dấu phẩy ngừng ngắn hơn chỗ ngập ngừng tác giả muốn; cần lượt nghe thử VieNeu trước khi phát hành.

   **tnbig (06-11, dev/tn-bigint; chưa tích hợp):** thêm nhóm dấu chấm cho số nguyên liền từ 7 chữ số,
   không có số 0 đầu, khi có danh từ đếm hoặc từ gợi lượng; Python và Kotlin cùng fixture. Cache đọc 5 → 6.
   Kiểm lại bản lưu riêng của đúng mẫu tn-tier25: 349 chương / 186 cuốn / 61.678 đoạn, **0** số liền từ 7 chữ số
   (lượng / mã / khoảng năm / khác đều 0; đổi 0, giữ 0). Không dùng mẫu này để suy rộng danh sách từ gợi lượng.
   Đối chiếu từ gợi lượng trước số liền 1–6 chữ số trong cùng mẫu: có 42, khoảng 34, hơn 26, gần 11,
   tổng cộng 5, lên tới 3, tổng 1 (đếm lượt xuất hiện, chưa phải độ chính xác trên số dài).
   Kiểm trực tiếp hai bộ nguồn Sugaru: 11 + 12 chương, 3.016 + 2.592 dòng nội dung không rỗng (bỏ dòng tên chương);
   23/23 file khớp SHA-256 trong SQLite. Số nguyên liền từ 7 chữ số trong toàn bộ file nguồn (kể cả tên chương): **0 + 0**;
   lượng / mã / khoảng năm / khác đều 0. Có **1** số lượng 9 chữ số do luật bỏ phẩy tạo ra ở cuốn thứ nhất, cuốn thứ hai 0.
   Sửa ngay luật nghìn kiểu Anh: kết quả từ 7 chữ số giữ nhóm bằng dấu chấm, 4–6 chữ số giữ cách đọc cũ.
   Sau sửa: số dài liền sinh ra **1 → 0**, đổi **1 + 0** dòng; đọc kiểm riêng **1/1** dòng đổi và sea-g2p 0.9.1 đọc đúng hàng triệu.
   Dấu ~ sinh khoảng số dài cũng giữ nhóm; dấu cách / dấu chấm không bị nối thành số liền, khoảng gạch nối chỉ nhận tối đa 4 chữ số mỗi vế.
   Fixture chung 146 ca: thêm 46 câu bịa, đổi duy nhất ca cũ `thousands-2`; kiểm thứ / hạng với cả 5 và 6 chữ số đọc đúng, giữ nguyên.
   Chưa tổng hợp hay chấm audio; phép kiểm này xác nhận văn bản đọc và Normalizer trên CPU.

   **tnnext (06-11, dev/tnnext; chưa phát hành):** nhãn `Chap`/`Chap.` và `Vol`/`Vol.` ngay trước số Ả Rập,
   hoặc dính số (`Chap.12`, `Vol.5`), đọc thành “chương” / “tập”. Không đoán số phức hợp, mã chữ-số, URL,
   từ đứng riêng hay token ngay sau nhãn mã/id/serial. Python và Kotlin cùng áp trước bước đọc từ; Studio và Edge
   dùng đường chung. Cách đọc riêng của cuốn vẫn thắng, số chữ hiện và mốc sáng chữ giữ nguyên. Cache đọc 6 → 7.
   Fixture chung 190 ca: giữ nguyên 146 ca cũ, thêm 44 câu tự viết (20 đổi, 24 bảo vệ cách đọc hiện hành).
   Đo chỉ đọc 637 file của 30 LN Nhật trong các thư mục curated của Corpus: 174.217 dòng không rỗng, 3.722.710 chữ
   tách theo khoảng trắng, gồm cả tiêu đề. `Chap`+số: 547 lượt / 5 cuốn; `Vol`+số: 19 / 2 cuốn; 566 dòng đổi cách đọc.
   Đây là mẫu cố định, không ngẫu nhiên: riêng một cuốn chiếm 542/547 lượt Chap. Không suy rộng mức lợi cho mọi LN.
   Chỉ kiểm văn bản/Normalizer CPU; chưa tổng hợp hay chấm audio.

   **tnnext2 (07-11, cùng dev/tnnext; chưa phát hành):** thêm hai khoảng trống tầng 3 có luật nhỏ, xác định:
   - `v.v.` / `v.v` (kể cả chữ V đầu câu) → `vân vân`, giữ dấu chấm cuối nếu có. Không mở `V.V.`, `v.v.v.`,
     chữ cái đầu có chấm khác, URL/mã hay nhãn mã/id/serial. Các đường đều nhận cùng chữ đọc trước engine,
     thay vì phụ thuộc từ điển riêng của sea-g2p trên máy tính.
   - Gạch U+2010/U+2011/U+2012/U+2013 dính với hậu tố Nhật san/kun/chan/sama/senpai/sensei/dono dùng lại
     cách đọc gạch ASCII đã có, kể cả sau dấu ngập ngừng dính chữ. Chỉ khi cả lõi hợp lệ theo luật kính ngữ cũ;
     không đặt thêm cách đọc tên/từ mượn. Em dash, gạch rời, mã dính số và hậu tố chưa nhận giữ luật cũ.
   Sửa kiểm Chap/Vol trước khi tách dấu: `Chap.12..5`, `Vol.1...2` không còn bị nhận nhầm thành nhãn + số nguyên.
   Python/Kotlin cùng thứ tự; Edge/Nghe ngay và Studio dùng đường chung. Cách đọc riêng vẫn thắng, chữ nguồn và
   mốc chữ giữ nguyên. Cache 7 → 8; fixture chung 190 → 227 ca tự viết, giữ nguyên 190 ca trước.

   Đo thêm Hako `_full`, không cộng lặp mẫu curated: hạt 20261107, chọn ngẫu nhiên 200 cuốn truyen, 70 ai-dich,
   6 khac (tất cả khac có TXT), tối đa 2 chương/cuốn: **534 file / 276 cuốn / 89.197 dòng / 1.881.652 chữ**.
   NFC từng dòng, tính cả tiêu đề; nhóm nguồn không đồng nghĩa quốc tịch. `v.v.` 7 lượt/7 cuốn;
   gạch Unicode kính ngữ 5 lượt/1 cuốn. Số thập phân dấu chấm 49 lượt/24 cuốn nhưng nhiều số chương,
   nên hoãn luật rộng; số+k có 2 lượt, cả hai là độ phân giải 4K. Viết tắt có chấm 14 lượt, trong đó 7 là v.v.;
   7 lượt còn lại (V.L., B.F.) và 4 lượt vs chưa tự quyết cách đọc. Hai luật được chọn vì công nhỏ và tái dùng
   cách đọc đã biết; không khẳng định lợi ích audio cao hay phổ biến trên mọi LN. Chỉ đếm xuất hiện và đổi văn bản;
   chưa tổng hợp/chấm audio.

3. Tầng 3 từ điển viết tắt + từ mượn + kính ngữ: dựng bằng LLM ngoại tuyến, kiểm âm tiết + ASR, vào cả Studio lẫn Nghe ngay.
4. Tầng 4 phiên âm romaji / Hàn theo luật cho Nghe ngay (máy tính + điện thoại), và tầng 4b model phiên âm từ riêng (Model
   train, sau cân bằng giọng; kế hoạch 1 trang trước khi train).
5. So các bộ VietNormalizer / donglao-g2p trên cùng bộ thử; lớp nào chúng thắng thì mượn luật (MIT / Apache-2.0).

Ràng buộc:
- Studio đụng file khoá (`tts.py`, `text_processing.py`) nên làm ở nhánh dev, kèm sự kiện phiên bản.
- Nghe ngay cũng có file khoá (`readaloud/symbols.py`, `readaloud/vieneu.py`...): đọc `QUALITY_IMPLEMENTATION_FILES` từ code,
  đo `quality_implementation_hash()` trước/sau; thay đổi hash chỉ nằm ở nhánh dev và chờ hết run trước khi tích hợp.
