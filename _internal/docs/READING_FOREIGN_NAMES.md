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
   Tiếng Hàn: s (Su-uân, Han Sưng Su, Bu-san). [Chọn: Bộ Ngoại giao và SGK lẫn cả hai. Đã quét theo bằng chứng: Nhật x khớp 24 dạng SGK
   (s: 21), sh -> s khớp hơn sh -> x; Hàn s khớp 17 dạng Bộ Ngoại giao (x: 14). Giọng miền Nam phân biệt được s / x.]
5. **c / k / q, g / gh, ng / ngh:** theo chính tả tiếng Việt (c trước a, o, ô, ơ, u, ư; k trước i, e, ê, y; gh, ngh trước i, e, ê).
   [Có nguồn: SGK Ca-oa-xa-ki, Cô-chi, Ki-si-đa]
6. **Hán-Việt:** chỉ khi chính bản dịch đã viết bằng Hán-Việt (Minh Trị, Bình Nhưỡng, Kim Nhật Thành). App không tự chuyển tên
   Latinh sang Hán-Việt. [Có nguồn: QĐ 07/2003, NĐ 30/2020]

## 2. Tiếng Nhật (romaji Hepburn)

| romaji | đọc | mức | bằng chứng |
|---|---|---|---|
| a, i, o | a, i, ô khi có phụ âm đầu; **o đứng một mình (không phụ âm đầu) → o, trừ sau i / u thì → ô** | Có nguồn; o một mình: **Chủ sách** | Tô-ky-ô, Hi-rô-si-ma; chủ sách 04-10 (lần 4): "Osaka => o-xa-ca (alt ô-xa-ca)", "Aoi => a-o-i", "Okaa-san => o-ca-xan", "Onigiri => o-ni-gi-ri". Âm tiết "ô" tách từ kyo / ryo vẫn là ô (ki-ô, ri-ô). Lần 5: "Fukuoka => phu-cu-ô-ca", "Fumio => phu-mi-ô" (o sau i / u là ô), "Naoki => na-o-ki" (o sau a / e và đầu từ là o) |
| **ee, ii, aa viết lặp** | **e, i, a** (gộp một, như oo → ô, uu → u) | **Chủ sách** | Chủ sách 04-10 (lần 4): "Onee-san => o-ne-xan", "Onii-chan => o-ni-chan", "Hiiragi => hi-ra-ghi", "Okaa-san => o-ca-xan", "Ojii-san => o-gi-xan" |
| **ao** | cuối từ: một âm tiết **ao** (Nao); giữa từ: tách **a-o** (Aoi, Kaori; Naoki theo analogy, cờ `analogy:ao_split`) | **Chủ sách** | Chủ sách 04-10 (lần 4): "Nao => nao", "Aoi => a-o-i", "Kaori => ca-o-ri" |
| e | **e** ở mọi chỗ (Xa-na-e, Cô-be, E-đô; ge → ghe, ke → ke) | **Chủ sách** | Chủ sách 04-10 (lần 2): "Hajime => Ha-gi-me", "Kenji => Ken-gi". Bỏ kiểu "ê" của SGK / Bộ Ngoại giao (Cô-bê, Sa-na-ê, Mô-tê-gi, Ha-kô-ne) |
| u | **u** ở mọi chỗ (fu → phu, ku → cu, ru → ru) | **Chủ sách** | Chủ sách 04-10: "Fukushima => phu-cu-si-ma", "haruto-kun => ha-ru-tô-cun". Khớp SGK (Phu-cu-ô-ca, Mu-rô-ran, Cu-si-rô, Chu-bu); bỏ kiểu "ư" của Bộ Ngoại giao (Phư-mi-ô, Ê-xư-kê) |
| kyu, gyu, nyu, hyu, byu, pyu, myu, ryu | **tách ki-u, ri-u** (như kyo → ki-ô; không "kiu") | **Chủ sách** | Chủ sách 04-10 (lần 4): "Ryuu => ri-u". Thay Kiu-xiu, Riu-kiu của SGK |
| shu, chu, ju | **su**, chu, giu (phụ âm + u) | **Chủ sách** (shu) | Chủ sách 04-10 (lần 4): shu giữ s + u (không xiu). Chu-bu (SGK) giữ |
| nguyên âm dài viết bằng dấu ō (ô) / oo / ū, uu | ô / u (không kéo dài) | Có nguồn | Tô-ky-ô, Hô-cai-đô, Kiu-xiu |
| **ou viết ra hai chữ** (o + u) | **âu** ở mọi chỗ (Câu-ta-râu, Câu-ki, Xa-tâu); sau y âm vòm tách i-âu (kyou → ki-âu, ryou → ri-âu); shou → sâu, chou → châu, jou → giâu | **Chủ sách** | Chủ sách 04-10 (lần 3): "Kyouko => Ki-âu-cô", "Ryouma => Ri-âu-ma"; shou / chou / jou theo analogy (cờ `analogy:ou_vom`). ō vẫn là ô (Tô-ky-ô giữ) |
| ei | **ây** | **Chủ sách** | Chủ sách 04-10 (lần 2): "Rei => Rây", "sensei => xen-xây". Khớp SGK cũ Kô-mây; bỏ ê (Bộ Ngoại giao Ê-xư-kê) và ay |
| ai | ai (tách "a-i" khi hai âm tiết: Ta-ca-i-chi) | Có nguồn | Sai-ta-ma, Ta-ca-i-chi |
| k | c / k theo luật 1.5 | Có nguồn | Ca-oa-xa-ki, Ki-si-đa |
| g | g; trước i đọc **"ghi"**, trước e đọc "ghe" (ji vẫn → gi) | **Chủ sách** | Chủ sách 04-10 (lần 4): "Hiiragi => hi-ra-ghi". "Gin" → Ghin, "Jin" → Gin. Từ quen onigiri là ca ghi đè cố định (o-ni-gi-ri), không đổi luật |
| s | x | Chọn (luật 1.4) | Ô-xa-ca, Na-ga-xa-ki |
| shi, sha, sho, shu | si, sa, sô, su | Có nguồn (shu: **Chủ sách**) | Hi-rô-si-ma, Sô-gun; shu → su theo chủ sách 04-10 (lần 4) |
| z, j | d / gi (zu → du, ji → gi) | Có nguồn (ji: **Chủ sách** 04-10, Ha-gi-me, Ken-gi) | Ma-xa-ca-du, Sin-dô |
| t, d | t, đ | Có nguồn | Ta-ca-i-chi, Hô-cai-đô, E-đô |
| chi | chi | Có nguồn | Cô-chi, Ta-ca-i-chi |
| tsu | **xu** ở mọi chỗ | **Chủ sách** | Chủ sách 04-10 (lần 4): "Tsubasa => xu-ba-xa" (thay chu); Matsuyama → Ma-xu-gia-ma (SGK cũ Mát-xu-ya-ma) |
| h, b, p, m, n, r | h, b, p, m, n, r | Có nguồn | Ha-kô-ne, Mô-ri |
| fu | phu | Chủ sách | "Fukushima => phu-cu-si-ma"; SGK Phu-cu-ô-ca |
| w (wa) | oa | Có nguồn | Ca-oa-xa-ki, Bi-oa, Tô-ku-ga-oa |
| ya, yu, yo (đầu từ và giữa từ) | **gia, giu, giô**; **ya cuối từ sau nguyên âm**: y thành bán âm cuối của âm tiết trước + a riêng (**may-a, cay-a, xây-a**); yu / yo cuối từ cùng cách (May-u, Xay-ô: analogy `analogy:y_final`) | **Chủ sách** | Chủ sách 04-10 (lần 2): "Yamato => Gia-ma-tô", "Ayaka => A-gia-ca". yu, yo theo ya (cờ `analogy:y_gi`). Thay dạng SGK Ya-ma-tô, I-ô-cô-ha-ma. Lần 5: "Maaya => may-a", "Maya => may-a", "Kaya => cay-a", "Seiya => xây-a (alt xay-a)"; Ayaka, Yamato vẫn gia. Hai nguyên âm rồi ya mà vần không thành (Kouya, Raiya) còn mở: cờ `open:y_after_vowel_pair` |
| kyo, ryo, nyo… | ki-ô, ri-ô, ni-ô (kyou, ryou → ki-âu, ri-âu: xem dòng ou) | Có nguồn | Ki-ô-tô (CTST) |
| n âm tiết | n khép âm tiết trước | Có nguồn | Hôn-su, Can-tô, Sin-dô |
| phụ âm đôi kk, pp, tt, ss | khép âm tiết trước bằng c / p / t + thanh sắc | Có nguồn | Hốc-cai-đô, Xáp-pô-rô |
| "u" vô thanh (desu, Matsu…) | vẫn đọc ư / u | Có nguồn | dạng viết không bỏ âm nào |

**Hậu tố gọi** (-san, -kun, -chan, -sama, senpai, sensei, -dono, -tan, -nee, -nii): không có nguồn đọc tiếng Việt. Đọc theo bảng trên: xan, cun, chan, xa-ma,
xen-pai, xen-xây (ei -> ây). Hậu tố nối vào tên bằng GẠCH NỐI thành một chuỗi: "Haruto-kun" → "Ha-ru-tô-cun". [Chủ sách 04-10 cho -kun; các hậu
tố khác áp cùng cách]

**Phán quyết của chủ sách (04-10)** — đứng trên mọi nguồn, cố định, không quét; mỗi cái là một ca kind `owner` trong
`tests/romanization_evidence.py` và test phải khớp:
- Lần 1: Fukushima → Phu-cu-si-ma; Haruto-kun → Ha-ru-tô-cun (u → u ở mọi chỗ, fu → phu, tsu → chu, hậu tố nối gạch).
- Lần 2: Yamato → Gia-ma-tô, Ayaka → A-gia-ca (y + nguyên âm → gi: ya gia, yu giu, yo giô); Rei → Rây, sensei → xen-xây (ei → ây);
  Hajime → Ha-gi-me, Kenji → Ken-gi (e → e, không ê; ge → ghe, ke → ke). Giữ: s → x, sh → s, ji → gi, u → u, tsu → chu, -kun → cun nối gạch.
  Âm vòm kya / kyo / ryo… giữ như cũ (Ki-ô-cô, Ri-ô-ma).
- Lần 4 (Nhật): Onee-san → o-ne-xan, Onii-chan → o-ni-chan, Okaa-san → o-ca-xan (alt ô-), Ojii-san → o-gi-xan (alt ô-), Osaka → o-xa-ca (alt ô-xa-ca) (o không phụ âm đầu → o,
  ee / ii / aa gộp); Hiiragi → hi-ra-ghi (g + i → ghi, ji vẫn gi); Inoue → i-nâu-e; Shouta → sâu-ta; Jouichi → giâu-i-chi; Kouhai → câu-hai; Senpai → xen-pai;
  Tsubasa → xu-ba-xa (tsu → xu); Ryuu → ri-u (yu sau phụ âm tách); Aoi → a-o-i, Kaori → ca-o-ri, Nao → nao (ao cuối gộp, giữa từ tách); Tomoe → tô-mô-e; Sora → xô-ra
  (alt xo-ra); Konoha → cô-nô-ha; Onigiri → o-ni-gi-ri (từ quen, ghi đè cố định `_JA_FIXED`, không đổi luật g + i).
- Lần 4 (Hàn): Kang → cang (bật hơi k / t / p đọc như âm thường, chính tả Việt c / k); Taehyun → te-hi-un; Choi → choi (oi → oi); Yoon → giun (alt dun); Hyung → hi-ung;
  Seojun → xeo-giun; Park → pắc; Jeong → gie-ong (alt de-ong); Won → guôn (wo → uô, w đầu từ → gu; giữa từ như Suwon → Su-guôn theo analogy, cờ `analogy:ko_w_gu`).
  Luật: s → x; j → gi; y + nguyên âm → gi (như Nhật); eo → eo khi âm tiết mở, tách e-o + coda khi có phụ âm cuối; yu / yeo sau phụ âm tách i- (hyun → hi-un).
- Lần 5 (Nhật): Fukuoka → phu-cu-ô-ca; Fumio → phu-mi-ô; Naoki → na-o-ki (o đầu từ và sau a / e → o, sau i / u → ô); Maaya → may-a, Maya → may-a, Kaya → cay-a,
  Seiya → xây-a (alt xay-a): ya cuối từ sau nguyên âm thì y là bán âm cuối của âm tiết trước và a đứng riêng.
- Lần 5 (Hàn): Seoul → xe-un (alt xeo-un; eo mở trước âm tiết u gộp thành e, `analogy:ko_eo_u`); Busan → bu-xan (b đầu từ → b); Suwon → xu-guôn; Kim Jong-un → kim giông-un
  (tên nối gạch: mỗi bộ phận viết thường, nối bằng gạch); Lee Myung-bak → li mung-bắc (Myung → mung là ca cố định, hyun / hyung vẫn hi-un / hi-ung; a + k → ắ);
  Cheonggyecheon → che-ong-ghi-che-on (gye → ghi); Kyung → ki-ung, Byung → bi-ung (yu sau phụ âm tách i-u); Gyeong → ghe-ong, Pyeong → pe-ong (yeo sau phụ âm: y mất,
  eo tách e-ong; g + y đọc ghe).
- Lần 3: Kyouko → Ki-âu-cô, Ryouma → Ri-âu-ma ("ou" viết ra hai chữ → âu; Koutarou → Câu-ta-râu, Satou → Xa-tâu). Nguyên âm dài viết bằng
  dấu (ō) vẫn → ô (Tô-ky-ô); "oo" giữ.
- Ca sách giáo khoa / Bộ Ngoại giao vênh các phán quyết này (Ya-ma-tô, Cô-bê, Ê-xư-kê…) được ghi lý do ở `EXPLAINED`, không phải lỗi luật.

## 3. Tiếng Hàn (phiên âm Latinh RR / McCune, như bản dịch viết)

Nguồn chính: Bộ Ngoại giao (Pắc Cưn Hê, Kim Te Chung, Li Miêng Bắc, Chơng Hông Uân, Xơ-un, Chê-chu, Su-uân, Hoa-sơng, Chang-đớc,
Kiơng-chu).

| RR | đọc | mức | bằng chứng |
|---|---|---|---|
| eo (ㅓ) | **eo** khi âm tiết mở (Seo → xeo); có phụ âm cuối thì tách **e-o** + coda (Jeong → gie-ong, Seoul → xeo-un) | **Chủ sách** | Chủ sách 04-10 (lần 4): "Seojun => xeo-giun", "Jeong => gie-ong". Thay ơ của Bộ Ngoại giao (Xơ-un, Chơng) |
| yeo (ㅕ) | đầu từ: gi + eo (gieo, gie-ong); sau phụ âm **y mất**, eo như thường (gyeong → ghe-ong, pyeong → pe-ong; myung → mung cố định) | **Chủ sách** (suy từ eo, y) | Chủ sách 04-10 (lần 4, 5); cờ `analogy:ko_yeo`. Thay iê của Bộ Ngoại giao (Miêng, Hiêng) |
| eu (ㅡ) | ư | Có nguồn | Cưn, Sưng |
| ae (ㅐ) | e | Có nguồn | Te, He-in |
| e (ㅔ) | ê | Có nguồn | Chê-chu, Hê |
| o, u, i | ô, u, i | Có nguồn | Hông, Bu-san |
| wa, oe, wi, ui | oa, uê, uy, ưi | Chọn | Hoa-sơng; các nguyên âm còn lại theo âm, chưa có ví dụ |
| wo, oi | **uô** (w đầu từ → **gu**: won → guôn); **oi** | **Chủ sách** | Chủ sách 04-10 (lần 4): "Won => guôn", "Choi => choi". Giữa từ (Suwon → Su-guôn) theo analogy |
| y + nguyên âm (ya, yo, yu) | **gi** + nguyên âm (như Nhật); sau phụ âm tách i- (hyung → hi-ung, kyung → ki-ung, byung → bi-ung) | **Chủ sách** | Chủ sách 04-10 (lần 4): "Yoon => giun (alt dun)", "Hyung => hi-ung" |
| g, d đầu từ; b đầu từ | c / k, t; **b** | Có nguồn; b: **Chủ sách** | Cưn, Te (âm tắc nhẹ đầu từ của tiếng Hàn là âm vô thanh). Lần 5: "Busan => bu-xan", "Park Geun-hye" vẫn Pắc (p thật của park giữ p) |
| g, d, b giữa hai âm hữu thanh | g, đ, b | Có nguồn | Chang-đớc |
| k, t, p (bật hơi) | **như âm thường**: c / k theo chính tả Việt, t, p | **Chủ sách** | Chủ sách 04-10 (lần 4): "Kang => cang", "Taehyun => te-hi-un" (không kh, th, ph) |
| j | **gi** | **Chủ sách** | Chủ sách 04-10 (lần 4): "Seojun => xeo-giun", "Jeong => gie-ong" (thay ch) |
| ch | ch | Có nguồn | Chê-chu, Chung, Châng |
| s, ss | **x** | **Chủ sách** | Chủ sách 04-10 (lần 4): "Seojun => xeo-giun" (thay s của Bộ Ngoại giao: Su-uân, Sưng Su) |
| h, m, n, ng | h, m, n, ng | Có nguồn | Hê, Nam-san |
| r / l | r giữa từ, l đầu từ; l cuối → n | Chọn | Han-la, Li |
| âm cuối k, t, p | c, t, p + thanh sắc | Có nguồn | Pắc, Bắc, Sớc |

Tên người Hàn: mỗi âm tiết RR một âm tiết, không gạch nối (Pắc Cưn Hê). [Có nguồn: Bộ Ngoại giao]

## 4. Tên tiếng Anh và phương Tây

**Mặc định: GIỮ NGUYÊN chữ Anh** cho máy đọc nói được âm vị tiếng Anh. [Đo 04-10] Whisper nghe lại: VieNeu Turbo / Nano (sea-g2p cho
âm vị Anh), ZeroTTS và Edge đọc "Rose", "Mike", "laptop", "Facebook", "Jennifer", "Fireball", "level", "Boss" để nguyên ra tiếng Anh
nhận được; viết Việt hoá "Rô-dơ", "Mai-cơ" lại bị nghe thành "Roger", "Michael". Phần dưới đây (Việt hoá qua âm vị) chỉ dành cho máy
đọc CHỈ nói được âm tiết tiếng Việt.

**Phán quyết của chủ sách (04-10) cho dạng Việt hoá** — đứng trên các nguồn viết bên dưới, cố định:
game → gêm (viết ghêm), level → le-vờ / le-vồ, maple → máp-pồ, Michael → mai-cồ, Kate → ca-tê.
- Chủ sách xác nhận dạng sách báo Oa-sinh-tơn, Ê-đi-xơn là ĐÚNG: schwa + phụ âm cuối hợp lệ (n, m, ng) giữ phụ âm cuối, thanh ngang
  (tơn, xơn; game → gêm).
- Thanh HUYỀN chỉ ở âm tiết schwa MỞ sinh ra vì phụ âm cuối không đứng được cuối âm tiết Việt: -əl (l tối) → "ồ", l bỏ (máp-pồ,
  mai-cồ, le-vồ; le-vờ cũng được); phụ âm khác → "ờ" (analogy, chưa có ca chủ sách).
- Âm tiết khép trước đó giữ sắc theo luật 1 (máp).
- Kate → ca-tê: chủ sách "dễ nghe hơn là 'kết'" - tránh âm tiết khép tắc mang sắc nghe gắt ở tên ngắn, đọc mở theo mặt chữ.

**Lần 2 (04-10):** Mike → mi-ke, Jake → gia-ke, Luke → lu-ke, Pete → pi-tờ, skill → xờ-kiu, boss → bót, slime → xờ-lam, quest → quét;
chữ viết tắt đã thành từ: VIP → víp, ID → ai-đi.

**Lần 3 (04-10):** guild → gui, Thomas → tho-mát, Boston → bót-tơn, Rocky → róc-ki, time → tham, night → nai, Blake → bờ-lếch,
Master → mát-tơ, Zeke → de-ke, gold → gôn.

**Lần 4 (04-10):** Tom → tom / tôm, Tony → to-ni / tô-ni, team → tim, tank → tanh, Tina → ti-na, Lyle → lai-ồ, Kyle → kai-ồ (viết
cai-ồ theo luật 1.5, cùng âm), Doyle → đoi-ồ.

**Lần 5 (04-10):** fireball → phai-bôn, Rose → ro-xe, great → gờ-rít, late → lết, Grace → gờ-rây, Gate → gết (viết ghết như ghêm),
Nate → na-te / nết.

Luật rút ra (chung các lần):
- Tên ngắn MỘT phụ âm đầu + nguyên âm + MỘT phụ âm (mọi phụ âm, trừ h w x y) + e câm đọc theo MẶT CHỮ, e cuối đọc **e** (mi-ke,
  gia-ke, de-ke, ro-xe, na-te; o → o, s → x, z → d; c / g trước e mềm: la-xe). Cụm phụ âm đầu thì đi đường âm vị (Blake → bờ-lếch,
  Grace → gờ-rây). Chỉ áp cho chữ viết hoa: từ thường (make, late) đi đường âm vị.
- Ca riêng, không suy rộng: Kate → ca-tê, Pete → pi-tờ, guild → gui, time → tham, Thomas → tho-mát, great → gờ-rít (ea không thành i),
  Gate → gết (từ thường viết hoa: luật theo mặt chữ không phân được tên với từ thường). t đầu từ vẫn là **t** (Tom, Tony,
  Tina, team): tham / tho-mát không phải luật bật hơi.
- Cụm phụ âm ĐẦU từ → "Cờ-" thanh HUYỀN (xờ-kiu, xờ-lam, bờ-lếch). Phụ âm thừa giữa từ vẫn "ơ" ngang như sách báo (Sếch-xơ-pia).
- l cuối sau i thành **u** (skill → xờ-kiu). l cuối sau nguyên âm đôi ai / ao / oi thành âm tiết **"ồ" không phụ âm đầu**, l bỏ
  (lai-ồ, kai-ồ, đoi-ồ); sau phụ âm vẫn như cũ (mai-cồ, máp-pồ). l khép sau nguyên âm khác thành n (Men-bơn, Đan-tơn).
- /ɑ/ viết o đọc **o** (bót, bót-tơn, róc-ki, tom); Tô-mát, Bốt-tơn, Rốc-ki của nguồn thua. Khép tắc mang sắc.
- /eɪ/ khép bằng p → a (máp), khép bằng c → êch (lếch), khép bằng t → êt (lết, gết), khép bằng m n ng → ê (gêm); /eɪ/ + s cuối →
  ây, s bỏ (gờ-rây).
- /aɪər/ (fire) → ai, r bỏ (phai). /ɔːl/ → ôn (bôn, như gôn): l sau nguyên âm đầy đủ thành n, chỉ sau schwa / nguyên âm đôi mới thành ồ.
- Từ ghép không có trong từ điển phát âm mà hai nửa có (sandworm) đọc từng phần.
- /aɪ/ + m → **am** (xờ-lam, tham); /aɪ/ + phụ âm khác bỏ phụ âm (nai, phai).
- /æŋk/ → **anh** (tanh; rank → ranh, thank → thanh theo đó, cờ `analogy:ank`). /iː/ → i (tim).
- -er cuối → ơ thanh NGANG (mát-tơ).

Cài đặt: `abook/english_vi.py` (bản Kotlin `readaloud/EnglishVi.kt`), ca có nguồn ở `tests/english_vi_evidence.py`, các điểm [Chọn] quét
bằng `scripts/sweep_english_vi_variants.py` (chủ sách x100, nhà nước x2, SGK / báo x1, cộng đồng x0).

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

- Giọng miền Bắc đọc s và x như nhau. Luật 1.4 chỉ có tác dụng với giọng miền Nam; kiểm lại khi đã có số đo.
- Các nguyên âm Hàn chưa có ví dụ chính thức (oe, wi, ui, we, wae).
- Hai nguyên âm rồi ya / yu / yo cuối từ mà vần không thành (Kouya, Raiya): hiện y → gi (Câu-gia); chưa có phán quyết.
- Chữ "o" đầu từ của Nhật: chủ sách viết "o" cho Osaka / Onee / Okaa (alt "ô"); luật hiện tại o không phụ âm đầu → o. Kyo / ryo tách vẫn ki-ô / ri-ô.

## 8. Nối vào "Nghe ngay" (04-10)

Giọng VieNeu của "Nghe ngay" (máy tính `abook/readaloud/names.py` + `vieneu.spoken_tokens`; điện thoại `readaloud/Names.kt` + `VieneuUnits.kt`) đọc tên Nhật / Hàn theo mục 2-3 khi cuốn có gốc ấy; chữ hiện trên màn hình không đổi.

- **Token được đổi**: viết hoa chữ đầu (không toàn HOA), chữ Latin, luật tách được hết thành âm tiết, và KHÔNG phải (a) từ tiếng Anh thật hay tên Anh / Âu (`abook/readaloud/english_words.txt`: từ vựng bert-base-uncased id <= 10000 giao CMUdict, cộng ~900 tên gọi và họ Anh / Âu tự viết, trừ 55 tên vốn là tên Nhật như Hana, Rika, Mina, Kana, Nana, Sakura - tên trùng hai bên thì gốc của cuốn quyết; sinh bằng `scripts/build_english_words.py`, 7277 từ, 55 KB, có cả ở Kotlin), (b) âm tiết tiếng Việt viết sẵn (Hoa, Nam, Mai), (c) tiếng reo (chữ lặp ba lần: Aaaa). Kate, Mike, Rose, Anne, Emma, Nina, Sara, Mario giữ nguyên cho sea-g2p (đo 04-10: VieNeu / ZeroTTS / Edge đọc tên Anh đúng).
- **Gốc của cuốn** tự đoán (`names.book_origin`): trong 40 chương đầu, tỉ lệ LẦN XUẤT HIỆN của tên đọc được bằng romaji >= 0,75 (và >= 10 tên khác nhau, >= 60 lần) thì "ja"; có hậu tố gọi (-san, -kun, -sama...) đi cùng tên romaji (>= 20 lần, >= 3 tên) thì chỉ cần >= 0,3; "ko" đòi RR >= 0,85 và >= 0,5 là tên chỉ RR đọc được (luật RR dễ tính: Mirabelle, Ruel, Alon của truyện Hàn cũng tách được, nên ngưỡng cao và "ko" ít khi bật). Không chắc thì không đổi gì. Người dùng ghi đè được (máy tính `BookOrigins.override`, điện thoại `ReadAloud.setOrigin`); giao diện cho chọn là việc sau.
- **Khoá bộ đệm clip** thêm "|gốc" chỉ cho đoạn mà gốc làm nghe khác, nên clip cũ của đoạn không có tên vẫn dùng được.
- **Theo năng lực của máy đọc** (`speaks_english` của provider; `names.spoken_names(toks, origin, speaks_english)` dùng chung): giọng nói được âm Anh (VieNeu, Edge, Azure, Google) giữ chữ Anh như trên; giọng chỉ nói được âm tiết Việt (Supertonic nuốt "Rose", "Haruto"; FPT / Viettel / giọng Windows chưa đo nên khai False, chưa nối) thì từ / tên Anh được Việt hoá bằng `english_vi.vietnamized_english` (bỏ qua chữ TOÀN HOA, âm tiết Việt viết sẵn, chữ dính số). Tên Nhật / Hàn theo gốc cuốn áp cho mọi giọng nối. Khoá clip thêm "en<số>" (`names.ENGLISH_READING`) cho đoạn có từ Anh được đổi, nối với "ja" / "ko" bằng "+".
- **Đo** trên kho truyện thử (161 cuốn, 40 chương đầu): 66 cuốn "ja" (47 / 68 cuốn Nhật đã dán nhãn, 19 cuốn chưa nhãn mà tên là romaji), 2 "ko"; không cuốn dán nhãn Hàn / Trung nào ra "ja". Chi tiết trong CHANGELOG và báo cáo.

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
