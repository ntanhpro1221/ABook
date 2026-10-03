# Đọc tên và từ nước ngoài: quy ước của ABook, có dẫn nguồn

Tài liệu này là quy ước để làm **đáp án** cho model phiên âm từ riêng (`TEXT_NORMALIZATION.md`, tầng 4b) và cho bộ thử chuẩn hoá chữ.

Yêu cầu của chủ sách (04-10):
- Đáp án do Claude làm, theo "luật nọ, quy tắc kia, thông tin thực tế từ các nguồn uy tín".
- "Dữ liệu, quy tắc cũ hiện tại của studio cũng không đáng tin lắm": quy ước cũ `ENGLISH_TO_VIETNAMESE.md` và 1.945 tên Studio đã
  khoá chỉ là một hệ để so, không phải đáp án.

Đầu vào là MỘT từ (tên hay từ mượn) kèm gợi ý gốc theo cuốn (Nhật / Hàn / Anh). Đầu ra là cách đọc gồm các âm tiết tiếng Việt.

Mức độ của từng quy tắc:
- **[Có nguồn]:** dạng đã thấy trong nguồn chính thức hay sách giáo khoa.
- **[Chọn]:** các nguồn vênh nhau; app chọn một và ghi lý do.
- **[App]:** không có nguồn nào đủ tin; quyết định riêng của app, kiểm bằng âm thanh (thu thử → ASR / máy nghe).
- **[Chủ sách]:** chủ sách đã chốt bằng tai; đứng trên mọi nguồn.

## 0. Điều nền: không có chuẩn đọc chính thức

- Văn bản Nhà nước chỉ quy định cách **viết** tên nước ngoài, không quy định cách đọc:
  - QĐ 240/1984 ưu tiên giữ dạng Latinh;
  - QĐ 07/2003/QĐ-BGDĐT cho phiên âm trực tiếp, viết hoa từng bộ phận, nối âm tiết bằng gạch ngang (Mát-xcơ-va, I-ta-li-a);
  - QĐ 1989/QĐ-BGDĐT 2018 bắt phiên âm gạch nối ở tiểu học (Tô-mát Ê-đi-xơn, Pa-ri, Tô-ky-ô).
- TTXVN (hội thảo 2013) thừa nhận cả nhóm làm tin truyền hình "không biết phát âm thế nào cho chuẩn".
- Nguồn tốt nhất cho tên Nhật và Hàn: **Bộ Ngoại giao** ghi tên Latinh kèm phiên âm trong ngoặc.
- Nguồn tốt nhất cho địa danh: **sách giáo khoa Địa lí / Lịch sử 11** (Kết nối tri thức, Chân trời sáng tạo, Cánh Diều) và Tiếng
  Việt 4–5. Các bộ sách vênh nhau ở s/x, ku/cư, f/ph, tsu.
- Nền bằng chứng đầy đủ (hơn 200 dạng có nguồn, mỗi dạng một URL) nằm ở repo riêng tư:
  `Corpus/research/tn/reading_evidence.md`.

Hệ quả: ABook phải tự chọn một quy ước, neo vào nguồn chính thống nhất có được, và giữ **nhất quán**. Cùng một từ thì luôn một cách
đọc trong cả cuốn, và trong cả app.

## 1. Luật chung (mọi gốc)

1. **Âm tiết.** Mỗi âm tiết của đầu ra phải là âm tiết tiếng Việt hợp lệ. Nối các âm tiết của một bộ phận tên bằng gạch ngang; các bộ
   phận cách nhau bằng dấu cách. [Có nguồn: QĐ 07/2003, QĐ 2018]
   - Ràng buộc riêng của app: giọng đọc chỉ đọc đúng âm tiết Việt, nên cụm phụ âm luôn được tách bằng "ơ" ("Mát-xơ-cơ-va", không
     viết "Mát-xcơ-va"). [Chọn: SGK có cả hai kiểu, Xtrây-li-a / Mát-xcơ-va]
2. **Thanh.**
   - Mặc định thanh ngang: 85–97% âm tiết trong 173 tên có nguồn mang thanh ngang. [Có nguồn: thống kê trên dạng đã chứng thực]
   - Âm tiết khép bằng p / t / c / ch mang thanh sắc (Mát-, Bét-tô-ven, Hốc-cai-đô, Xáp-pô-rô). Không tên riêng nào trong mẫu mang
     nặng, hỏi, ngã. [Có nguồn]
   - Ghi chú: danh từ chung đã Việt hoá thì khác. "Cạc" (card) mang thanh nặng, nhưng đó là từ đã vào từ điển, đọc theo từ điển
     (mục 6), không theo luật này.
3. **Phụ âm cuối:** chỉ p, t, c, ch, m, n, ng, nh.
   - r cuối bỏ (Poóc-len, Niu Oóc, Véc-xai). [Có nguồn]
   - l cuối thành n (Bun-kuc ~ Bul-kuc). [Chọn: nguồn có cả hai; "l" cuối không phải âm cuối tiếng Việt]
4. **s / x.** Tiếng Nhật: x cho âm /s/ (Ô-xa-ca, Na-ga-xa-ki, Ma-xa-ca-du); s cho âm "sh" (Hi-rô-si-ma, Ki-si-đa, Tô-si-mi-chu).
   Tiếng Hàn: s (Su-uân, Han Sưng Su, Bu-san). [Chọn: Bộ Ngoại giao và SGK lẫn cả hai. Đã quét theo bằng chứng: Nhật x khớp 27 dạng SGK
   (s: 24), sh -> s khớp hơn sh -> x; Hàn s khớp 17 dạng Bộ Ngoại giao (x: 14). Giọng miền Nam phân biệt được s / x.]
5. **c / k / q, g / gh, ng / ngh:** theo chính tả tiếng Việt (c trước a, o, ô, ơ, u, ư; k trước i, e, ê, y; gh, ngh trước i, e, ê).
   [Có nguồn: SGK Ca-oa-xa-ki, Cô-bê, Ki-si-đa]
6. **Hán-Việt:** chỉ khi chính bản dịch đã viết bằng Hán-Việt (Minh Trị, Bình Nhưỡng, Kim Nhật Thành). App không tự chuyển tên
   Latinh sang Hán-Việt. [Có nguồn: QĐ 07/2003, NĐ 30/2020]

## 2. Tiếng Nhật (romaji Hepburn)

| romaji | đọc | mức | bằng chứng |
|---|---|---|---|
| a, i, o | a, i, ô | Có nguồn | Ô-xa-ca, Tô-ky-ô, Hi-rô-si-ma |
| e | ê | Có nguồn | Sa-na-ê, Mô-tê-gi, Cô-bê (đa số) |
| u | **u** ở mọi chỗ (fu → phu, ku → cu, ru → ru) | **Chủ sách** | Chủ sách 04-10: "Fukushima => phu-cu-si-ma", "haruto-kun => ha-ru-tô-cun". Khớp SGK (Phu-cu-ô-ca, Mu-rô-ran, Cu-si-rô, Chu-bu); bỏ kiểu "ư" của Bộ Ngoại giao (Phư-mi-ô, Ê-xư-kê) |
| yu, kyu, ryu, shu, chu, ju | iu / u sau âm vòm | Có nguồn | Kiu-xiu, Riu-kiu, Chu-bu |
| nguyên âm dài ō, ou, oo / ū, uu | ô / ư (không kéo dài) | Có nguồn | Tô-ky-ô, Hô-cai-đô, Kiu-xiu |
| ei | ay | Chọn | Quét: ay hơn ê / ây đúng một dạng (SGK cũ May-gi); Bộ Ngoại giao viết Ê-xư-kê (ê), SGK cũ Kô-mây (ây). Kém chắc nhất trong các điểm đã quét |
| ai | ai (tách "a-i" khi hai âm tiết: Ta-ca-i-chi) | Có nguồn | Sai-ta-ma, Ta-ca-i-chi |
| k | c / k theo luật 1.5 | Có nguồn | Ca-oa-xa-ki, Ki-si-đa |
| g | g; trước i đọc "gi", trước e đọc "ghê" | Chọn | Bộ Ngoại giao viết "Mô-tê-gi" (quét: gi hơn ghi một dạng). Hệ quả: gi trùng với ji ("Gin" và "Jin" cùng đọc "Gin"), "gi" tiếng Việt đọc /z/ |
| s | x | Chọn (luật 1.4) | Ô-xa-ca, Na-ga-xa-ki |
| shi, sha, sho, shu | si, sa, sô, xiu | Có nguồn | Hi-rô-si-ma, Sô-gun, Kiu-xiu |
| z, j | d / gi (zu → dư, ji → gi) | Có nguồn | Ma-xa-ca-dư, Sin-dô |
| t, d | t, đ | Có nguồn | Ta-ca-i-chi, Hô-cai-đô, E-đô |
| chi | chi | Có nguồn | Cô-chi, Ta-ca-i-chi |
| tsu | chu | Chọn | theo quyết định u → u của chủ sách (Bộ Ngoại giao Tô-si-mi-chư → chu); SGK cũ Mát-xu-ya-ma |
| h, b, p, m, n, r | h, b, p, m, n, r | Có nguồn | Ha-kô-ne, Mô-ri |
| fu | phu | Chủ sách | "Fukushima => phu-cu-si-ma"; SGK Phu-cu-ô-ca |
| w (wa) | oa | Có nguồn | Ca-oa-xa-ki, Bi-oa, Tô-ku-ga-oa |
| ya, yo (đầu từ) | **mở**; mặc định ya / i-ô | App | SGK: Ya-ma-tô, I-ô-cô-ha-ma / Y-ô-cô-ha-ma; mặc định là hai dạng ấy ghép lại (quét); "ya" không phải âm tiết Việt; chọn bằng âm thanh |
| kyo, ryo, nyo… | ki-ô, ri-ô, ni-ô | Có nguồn | Ki-ô-tô (CTST) |
| n âm tiết | n khép âm tiết trước | Có nguồn | Hôn-su, Can-tô, Sin-dô |
| phụ âm đôi kk, pp, tt, ss | khép âm tiết trước bằng c / p / t + thanh sắc | Có nguồn | Hốc-cai-đô, Xáp-pô-rô |
| "u" vô thanh (desu, Matsu…) | vẫn đọc ư / u | Có nguồn | dạng viết không bỏ âm nào |

**Hậu tố gọi** (-san, -kun, -chan, -sama, senpai, sensei): không có nguồn đọc tiếng Việt. Đọc theo bảng trên: xan, cun, chan, xa-ma,
xen-pai, xen-xay (ei -> ay). Hậu tố nối vào tên bằng GẠCH NỐI thành một chuỗi: "Haruto-kun" → "Ha-ru-tô-cun". [Chủ sách 04-10 cho -kun; các hậu
tố khác áp cùng cách]

## 3. Tiếng Hàn (phiên âm Latinh RR / McCune, như bản dịch viết)

Nguồn chính: Bộ Ngoại giao (Pắc Cưn Hê, Kim Te Chung, Li Miêng Bắc, Chơng Hông Uân, Xơ-un, Chê-chu, Su-uân, Hoa-sơng, Chang-đớc,
Kiơng-chu).

| RR | đọc | mức | bằng chứng |
|---|---|---|---|
| eo (ㅓ) | ơ | Có nguồn | Xơ-un, Chơng |
| yeo (ㅕ) | iê | Chọn | Miêng, Hiêng, Yêng (Bộ Ngoại giao) hơn Kiơng-chu; "iơ" không là vần tiếng Việt, bộ kiểm âm tiết từ chối |
| eu (ㅡ) | ư | Có nguồn | Cưn, Sưng |
| ae (ㅐ) | e | Có nguồn | Te, He-in |
| e (ㅔ) | ê | Có nguồn | Chê-chu, Hê |
| o, u, i | ô, u, i | Có nguồn | Hông, Bu-san |
| wa, wo, oe, wi, ui | oa, uơ, uê, uy, ưi | Chọn | Hoa-sơng; các nguyên âm còn lại theo âm, chưa có ví dụ |
| g, d, b đầu từ | c / k, t, p | Có nguồn | Cưn, Te, Pắc (âm tắc nhẹ đầu từ của tiếng Hàn là âm vô thanh) |
| g, d, b giữa hai âm hữu thanh | g, đ, b | Có nguồn | Chang-đớc |
| k, t, p (bật hơi) | kh, th, ph | Chọn | chưa có ví dụ tên; theo âm |
| j, ch | ch | Có nguồn | Chê-chu, Chung, Châng |
| s, ss | s | Chọn (luật 1.4) | Su-uân, Sưng Su, Bu-san (quét: s 17 dạng Bộ Ngoại giao, x 14); Xơ-un là dạng hiếm hơn |
| h, m, n, ng | h, m, n, ng | Có nguồn | Hê, Nam-san |
| r / l | r giữa từ, l đầu từ; l cuối → n | Chọn | Han-la, Li |
| âm cuối k, t, p | c, t, p + thanh sắc | Có nguồn | Pắc, Bắc, Sớc |

Tên người Hàn: mỗi âm tiết RR một âm tiết, không gạch nối (Pắc Cưn Hê). [Có nguồn: Bộ Ngoại giao]

## 4. Tên tiếng Anh và phương Tây

- Đi qua âm vị (từ điển phát âm CMU / IPA), không đi theo chữ viết.
- Áp luật chung mục 1 và các dạng đã có trong sách giáo khoa / báo chính thống (Oa-sinh-tơn, Niu Oóc, Ê-đi-xơn, Sếch-xơ-pia,
  Bét-tô-ven, Gioóc-giơ, Ru-dơ-ven).
- Nền bằng chứng ở repo riêng tư có hơn 90 dạng; dùng làm bộ kiểm cho luật.

| âm | đọc | bằng chứng |
|---|---|---|
| /w/ đầu | oa / u / o | Oa-sinh-tơn, Uy-li-am |
| /dʒ/ | gi | Gioóc-giơ, Gia-cô-banh |
| schwa | ơ | Ê-đi-xơn, Oa-sinh-tơn |
| r cuối, sau nguyên âm | bỏ | Poóc-len, Niu Oóc |
| /θ/, /ð/ | x / đ | [Chọn] |

Các luật cụ thể của `ENGLISH_TO_VIETNAMESE.md` chỉ được giữ khi chúng cho ra đúng dạng đã có nguồn. Phần đối chiếu từng luật làm khi
dựng đáp án.

## 5. Chữ viết tắt

- Không có chuẩn bắt buộc. Năm 2010, VTV đọc "gờ bảy", "vê tê vê", "giê em"; HTV đọc "giê bảy"; VTC đọc "ai xi ti" (Tuổi Trẻ
  21/4/2010).
- ABook chọn **hệ a-bê-xê** (tên chữ cái chính thức, SGV Tiếng Việt 1, NXB GD 2002) cho mọi chữ viết tắt, đúng đề xuất của chính bài
  báo ấy. [Chọn]
- Dạng nói gọn khi đọc liền: e-lờ, em, en, e-rờ, ét, ích (theo "giê em" của VTV). F = ép, J = gi, W = vê kép, Z = dét.
- Ví dụ: HP "hát pê", MP "em pê", NPC "en pê xê", VTV "vê tê vê", EXP "e ích pê".
- Chữ viết tắt đã thành từ thì đọc như từ: OK "ô kê", TV "ti vi". [Có nguồn: từ điển]
- Mọi chữ viết tắt trong một cuốn dùng cùng một hệ. Người nghe sửa được từng mục (bảng cách đọc của cuốn).

## 6. Từ mượn và thuật ngữ game

- Từ đã vào từ điển tiếng Việt đọc như từ Việt: cà phê, ô tô, ra-đi-ô, xích lô, sơ mi, cạc, gôn. [Có nguồn: từ điển]
- Thuật ngữ game / LN chưa vào từ điển (level, skill, mana, buff, guild, boss…): không có nguồn nào ghi cách đọc thành tiếng (chỉ có
  giải nghĩa). Đọc theo mục 4 (đường âm vị tiếng Anh), nhất quán, người nghe sửa được. [App]

## 7. Còn mở, quyết bằng âm thanh

- "ya", "yo" đầu từ (Yamato, Yokohama): "Ya-ma-tô" hay "Gia-ma-tô" / "I-a-ma-tô". Chọn dạng mà giọng đọc phát ra gần âm gốc nhất
  (thu thử → nghe lại).
- Giọng miền Bắc đọc s và x như nhau. Luật 1.4 chỉ có tác dụng với giọng miền Nam; kiểm lại khi đã có số đo.
- Các nguyên âm Hàn chưa có ví dụ chính thức (wo, oe, wi, ui) và các âm bật hơi.

## Nguồn

Toàn bộ URL kèm loại và mức kiểm ở `Corpus/research/tn/reading_evidence.md` (repo riêng tư). Các nguồn chính:

- QĐ 07/2003/QĐ-BGDĐT: https://hoatieu.vn/phap-luat/quyet-dinh-so-07-2003-qd-bgddt-67490
- QĐ 1989/QĐ-BGDĐT 2018: https://hoatieu.vn/phap-luat/quyet-dinh-1989-qd-bgddt-2018-quy-dinh-chinh-ta-chuong-trinh-sach-giao-khoa-giao-duc-pho-thong-214530
- TTXVN 2013: https://dhtn.ttxvn.org.vn/tintuc/chuan-hoa-cach-su-dung-ten-rieng-tieng-nuocngoai-2575
- Bộ Ngoại giao, Nhật Bản: https://mofa.gov.vn/tin-chi-tiet/chi-tiet/thong-tin-co-ban-ve-nhat-ban-va-quan-he-voi-viet-nam-59199-652.html
- Bộ Ngoại giao, Hàn Quốc: https://mofa.gov.vn/tin-chi-tiet/chi-tiet/tai-lieu-co-ban-ve-dai-han-dan-quoc-va-quan-he-viet-nam-han-quoc-589.html
- SGK Địa lí 11 (KNTT, CTST, Cánh Diều): xem nền bằng chứng.
- Tuổi Trẻ 21/4/2010, "Những chữ cái nhảy múa": https://tuoitre.vn/nhung-chu-cai-nhay-mua-374522.htm
- Nguyễn Thiện Giáp, "Chuẩn hoá các tên riêng": https://ngonngu.net/chuanhoa_ntg_05/186
- Kang (2011), "Loanword phonology": https://www.yoonjungkang.com/uploads/1/1/6/2/11625099/tbc_100.kang.pdf
