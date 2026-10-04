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
| ya, yu, yo (đầu từ và giữa từ) | **gia, giu, giô**; **sau i thì y rơi** (Shinomiya → si-nô-mi-a, Miyuki → mi-u-ki, Kiyoshi → ki-ô-si); **sau n** (nya) → ni-a (Renya → re-ni-a); **ya cuối từ sau một nguyên âm đơn**: y thành bán âm cuối của âm tiết trước + a riêng (**may-a, cay-a, xây-a**); yu / yo cuối từ vẫn gi (Futayo → phu-ta-giô) | **Chủ sách** | Lần 2: "Yamato => Gia-ma-tô", "Ayaka => A-gia-ca". Lần 5: "Maaya => may-a", "Kaya => cay-a", "Seiya => xây-a (alt xay-a)". Lần 9: "Yurika => giu-ri-ca", "Yume => giu-me", "Yue => giu-e", "Sakuya => xa-ku-gia", "Kasuya => ka-xu-gia", "Kouya => câu-gia", "Raiya => rai-gia", "Alunaya => a-lu-na-gia", "Futayo => phu-ta-giô", "Shinomiya => si-nô-mi-a", "Renya => re-ni-a", "Kiyoshi => ki-ô-si", "Miyuki => mi-u-ki", "Kiyomasa => ki-ô-ma-xa" (cờ `analogy:y_after_i` cho các tên chưa có ca). Thay dạng SGK Ya-ma-tô, I-ô-cô-ha-ma |
| **oi sau phụ âm** | **một âm tiết oi** (Koizumi → coi-du-mi, Izayoi → i-da-gioi); không phụ âm đầu thì tách (Aoi → a-o-i). Koichi → co-i-chi là tên ghép Kou + ichi: cố định `_JA_FIXED` | **Chủ sách** | Lần 9: "Koizumi => coi-du-mi", "Izayoi => i-da-doi" (d = gi giọng Bắc), "Koichi => co-i-chi" |
| kyo, ryo, nyo… | ki-ô, ri-ô, ni-ô (kyou, ryou → ki-âu, ri-âu: xem dòng ou) | Có nguồn | Ki-ô-tô (CTST) |
| n âm tiết | n khép âm tiết trước | Có nguồn | Hôn-su, Can-tô, Sin-dô |
| phụ âm đôi kk, pp, tt, ss, tch | khép âm tiết trước bằng c / p / t + thanh sắc; cch → t + chi (ecchi → ét-chi, alt e-chi); ff → một f (Haffu → ha-phu) | Có nguồn + **Chủ sách** | Hốc-cai-đô, Xáp-pô-rô. Lần 9: "Sapporo => xáp-pô-rô", "Hokkaido => hốc-cai-đô", "Nissan => nít-xan", "Matcha => mát-cha", "ecchi => e-chi / ét-chi", "Haffu => ha-phu". Hatta → ha-ta là ngoại lệ cố định (`_JA_FIXED`), không mở luật gộp |
| m trước s, b, p | khép m (ん): Hamsuke → ham-xu-ke | **Chủ sách** | Lần 9: "Hamsuke => ham-xu-ke (alt ham-xu-kê)" |
| di | đi (tên phương Tây trong truyện Nhật) | **Chủ sách** | Lần 9: "Reidi => rây-đi", "Direkuresu => đi-re-ku-re-xu" |
| fi | **phi** (tên kiểu Âu trong truyện Nhật; fu vẫn phu); Fii → phi (ii gộp), Fina → phi-na (luật, không còn trong bảng cố định) | **Chủ sách** | Lần 9: "Fii => phi", "Fina => phi-na" |
| ー cuối từ | bỏ (Taruー → ta-ru) | **Chủ sách** | Lần 9: "Taruー => ta-ru" |
| "u" vô thanh (desu, Matsu…) | vẫn đọc ư / u | Có nguồn | dạng viết không bỏ âm nào |

**Hậu tố gọi** (-san, -kun, -chan, -sama, senpai, sensei, -dono, -tan, -nee, -nii): không có nguồn đọc tiếng Việt. Đọc theo bảng trên: xan, cun, chan, xa-ma,
xen-pai, xen-xây (ei -> ây). Hậu tố nối vào tên bằng GẠCH NỐI thành một chuỗi: "Haruto-kun" → "Ha-ru-tô-cun". [Chủ sách 04-10 cho -kun; các hậu
tố khác áp cùng cách]

**Phán quyết của chủ sách (04-10)** — đứng trên mọi nguồn, cố định, không quét; mỗi cái là một ca kind `owner` trong
`tests/romanization_evidence.py` và test phải khớp:
- Lần 1: Fukushima → Phu-cu-si-ma; Haruto-kun → Ha-ru-tô-cun (u → u ở mọi chỗ, fu → phu, tsu → chu, hậu tố nối gạch).
- Lần 2: Yamato → Gia-ma-tô, Ayaka → A-gia-ca (y + nguyên âm → gi: ya gia; yu giu, yo giô là suy theo ya, chưa có ca chủ sách); Rei → Rây, sensei → xen-xây (ei → ây);
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
- Lần 8 (Nhật): Ohto → ô-tô, Ohka → ô-ca ("oh" trước phụ âm / cuối từ là o dài → ô, KỂ CẢ đầu từ; ō đầu từ vẫn o); Sanjyo → xan-giô (jy → j); Hiiraghi → hi-ra-ghi (gh → g);
  Gesunoh → ghét-xu-nô (tên cố định, KHÔNG suy rộng ge → ghét); Theia → thi-a, Tio → ti-ô (tên kiểu Âu trong truyện Nhật, Hepburn không có ti: cố định trong
  `_JA_FIXED`, chỉ đúng các tên này, không mở ti cho mọi tên; Fina → phi-na sau đó thành luật fi → phi).
- Lần 8 (Hàn): tokki → tô-ki (alt to-ki; kk là phụ âm đầu căng nên to-kki thắng tok-ki khi RR không phân; chỉ kk, Oppa vẫn không đoán); Gangwon → kang-guôn (cố định gang-won, viết cang
  theo chính tả vì bộ kiểm âm tiết không nhận kang; w giữa từ → gu theo analogy `ko_w_gu`).
- Lần 9 (Nhật, 04-10 trưa): xem các dòng ya / yu / yo, oi, phụ âm đôi, m, di ở bảng trên; thêm Yukinoshita → giu-ki-nô-si-ta, Poh-chan → pô-chan.
  Agent từng suy rộng Hatta thành "gộp mọi phụ âm đôi"; chủ sách bác bằng Sapporo / Hokkaido / Nissan / Matcha - nên một ca lạ là ngoại lệ, đừng suy luật từ nó.
- Lần 9 (Hàn): oppa → óp-pa, unnie → un-ni (ie cuối → i), noona → nu-na, Ahn → an, Yeeun → de-ưn (= gie-ưn), Yejin → de-din, Yerin → de-rin (**ye đầu từ → gie**,
  e mở), Muyoung → mu-giong, Young → giong, Chaeyeon → che-gion, Seoyeon → xeo-gion (**yeo + phụ âm cuối → gi + o + coda**; "young" viết = yeong), Namgung → nam-gung,
  Hye → hê, Jeongeun → châng-gưn, Luda → lu-đa, won (tiền) → guôn. Cố định `_KO_FIXED_*`: Jeongeun, Luda (l đầu từ chỉ mở cho tên này), Oppa. Trả lời nhỏ sau đó: Hyunn → hi-un
  (nn cuối gộp n), Gyu → ghiu (yu mở = một âm tiết); Nhật Taruー → ta-ru (ー cuối bỏ), Fii → phi (fi → phi thành luật, Fina hết cố định); Tiếng Anh well → goeo (luật `w` đầu từ đã ra đúng).
- Lần 3: Kyouko → Ki-âu-cô, Ryouma → Ri-âu-ma ("ou" viết ra hai chữ → âu; Koutarou → Câu-ta-râu, Satou → Xa-tâu). Nguyên âm dài viết bằng
  dấu (ō) vẫn → ô (Tô-ky-ô); "oo" giữ.
- Ca sách giáo khoa / Bộ Ngoại giao vênh các phán quyết này (Ya-ma-tô, Cô-bê, Ê-xư-kê…) được ghi lý do ở `EXPLAINED`, không phải lỗi luật.

## 3. Tiếng Hàn (phiên âm Latinh RR / McCune, như bản dịch viết)

Nguồn chính: Bộ Ngoại giao (Pắc Cưn Hê, Kim Te Chung, Li Miêng Bắc, Chơng Hông Uân, Xơ-un, Chê-chu, Su-uân, Hoa-sơng, Chang-đớc,
Kiơng-chu).

| RR | đọc | mức | bằng chứng |
|---|---|---|---|
| eo (ㅓ) | **eo** khi âm tiết mở (Seo → xeo); có phụ âm cuối thì tách **e-o** + coda (Jeong → gie-ong, Seoul → xeo-un) | **Chủ sách** | Chủ sách 04-10 (lần 4): "Seojun => xeo-giun", "Jeong => gie-ong". Thay ơ của Bộ Ngoại giao (Xơ-un, Chơng) |
| yeo (ㅕ) | không phụ âm đầu, âm tiết mở: gi + eo; **có phụ âm cuối: gi + o + coda** (yeon → gion, young / yeong → giong: Chaeyeon → che-gion, Seoyeon → xeo-gion); sau phụ âm **y mất**, eo như thường (gyeong → ghe-ong, pyeong → pe-ong; myung → mung cố định) | **Chủ sách** | Lần 4, 5, 9; cờ `analogy:ko_yeo`. Thay iê của Bộ Ngoại giao (Miêng, Hiêng) |
| yu (ㅠ) mở sau phụ âm | **MỘT âm tiết**: Gyu → ghiu (g trước i viết gh); có phụ âm cuối thì tách i- (Hyun → hi-un, Kyung → ki-ung, Hyung → hi-ung) | **Chủ sách** | Lần 9: "Gyu => ghiu"; Hyun / Kyung / Hyung giữ. Analogy: Hyu → hiu, Ryu → liu |
| nn cuối từ | gộp n (Hyunn → hi-un); nn giữa từ vẫn n + n (unnie → un-ni) | **Chủ sách** | Lần 9: "Hyunn => hi-un" |
| ye (ㅖ) đầu từ | **gie** (e mở): Yejin → gie-gin, Yerin → gie-rin, Yeeun → gie-ưn | **Chủ sách** | Lần 9: "Yejin => de-din", "Yerin => de-rin", "Yeeun => de-ưn" (d = gi giọng Bắc). Hye → hê (sau phụ âm) giữ |
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

### 3b. Cách viết lạ: tiền xử lý token (05-10, bộ đo luật `translit_bench`)

Token đi qua bước tiền xử lý trước khi áp bảng mục 2-3 (`romanization._read`). Các bước này là [App]: quy ước không nói, mỗi cờ ghi dấu lúc nào chúng áp.

| kiểu | cách đọc | cờ |
|---|---|---|
| TOÀN HOA (KANATA, REI, NEE-SAN) | casefold rồi đọc, viết hoa chữ đầu như thường (Ca-na-ta, Rây, Ne-xan) | không |
| CamelCase (OkabeRintarou) | tách ở chữ hoa giữa từ, mỗi nửa một bộ phận cách nhau dấu cách (O-ca-be Rin-ta-râu); hai nửa đều MỘT âm tiết (JoJo, ChuChu) là một tên lặp, nối gạch (Giô-giô); mỗi nửa phải dài từ hai chữ | `analogy:camel_split` |
| hoa lạ không tách được (HImeno) | đọc như viết hoa chữ đầu của chính token (Hi-me-nô) | `analogy:case_fold` |
| gạch nối + hậu tố (Tenshi-chwan, Haruto-kun, PD-nim) | mỗi đoạn một bộ phận; hậu tố gọi và đoạn thường sau gạch nối gạch vào tên thành một chuỗi, đoạn viết hoa là từ mới (Waseda-Keio). `chwan` là cách viết nũng của `chan` (ch + oa + n: choan) | không |
| đoạn là chữ Việt có dấu (Vương-sama, Kanata-cả) | GIỮ NGUYÊN chữ ấy, phần còn lại đọc | `keep:viet` |
| đoạn là viết tắt TOÀN HOA 2-4 chữ (PD-nim) hay chữ Anh từ 4 chữ trở lên (Ikemen-style, Mary-san) | GIỮ NGUYÊN; đọc đoạn ấy là việc của luật chữ viết tắt / `english_vi`. Chữ Anh mà hệ kia (RR khi gốc Nhật, romaji khi gốc Hàn) đọc được thì KHÔNG giữ (Ji-Young, Sophia: là tên Hàn); chữ Anh cạnh một đoạn cũng là chữ Anh (Spider-Man) là tên Tây | `keep:abbr`, `keep:english` |
| Hàn: sh, oo, woo, yoo | sh -> s (Shinhyun -> Xin-hi-un), oo -> u (Joo -> Giu, Hoon -> hun), woo -> u (Ji-woo -> Gi-u) | không |
| Hàn: weo | -> wo (Weol -> Guôn) | `analogy:ko_weo` |
| Hàn: ah khi h không đứng trước nguyên âm | -> a, h câm của tiếng gọi (Seol-Ah, Ahn, Ahri, Min-ah) | `analogy:ko_ah` |

Giữ nguyên cần ít nhất một đoạn còn lại đọc theo luật; không thì None. Chữ Việt không dấu (Khoan, Seo) không được giữ vì nhiều tên romaji / RR cũng là âm tiết Việt.
Cố ý để None: Jinyoon (Jin-yun hay Ji-nyun), Spider-Man, iPhone, YouTube, PD đứng riêng.
Chưa quyết (liệt kê để chủ sách phán; oh, jy, gh, tokki, Gangwon chốt ở lần 8; ff, uya, m, di, Jeongeun, Oppa, Luda, Taruー, Fii, Hyunn, Gyu chốt ở lần 9): ti của tên
phương Tây ngoài Tio / Theia (Hepburn không có ti; fi đã thành luật phi).

## 4. Tên tiếng Anh và phương Tây

**Mặc định: GIỮ NGUYÊN chữ Anh** cho máy đọc nói được âm vị tiếng Anh. [Đo 04-10] Whisper nghe lại: VieNeu Turbo / Nano (sea-g2p cho
âm vị Anh), ZeroTTS và Edge đọc "Rose", "Mike", "laptop", "Facebook", "Jennifer", "Fireball", "level", "Boss" để nguyên ra tiếng Anh
nhận được; viết Việt hoá "Rô-dơ", "Mai-cơ" lại bị nghe thành "Roger", "Michael". Phần dưới đây (Việt hoá qua âm vị) chỉ dành cho máy
đọc CHỈ nói được âm tiết tiếng Việt.

**Phán quyết của chủ sách (04-10) cho dạng Việt hoá** — đứng trên các nguồn viết bên dưới, cố định:
game → gêm (viết ghêm), level → le-vờ / le-vồ, maple → máp-pồ, Michael → mai-cồ, Kate → ca-tê.
- Chủ sách xác nhận dạng sách báo Ê-đi-xơn và Oa-xinh-tơn (lần 9 sửa: s → x như mọi s khác) là ĐÚNG: schwa + phụ âm cuối hợp lệ (n, m, ng) giữ phụ âm cuối, thanh ngang
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

**Lần 6 (04-10):** Paul → pau, higher → hai-gờ, Laplace → la-pờ-lết, Jane → giên / dên, Cage → ca-ghe, Cale → ca-le, Walt → guốt,
Dalton → đan-tơn, days → đay, Luce → lu-xe.

**Lần 7-8 (04-10):** Washington → oa-sinh-tơn (lần 9 sửa oa-xinh-tơn), Edison → ê-đi-xơn, Gangwon, Theia, Fina, Tio (xem mục 2).

**Lần 9 (04-10 trưa, 89 từ + 41 từ chủ sách đưa ngày 02-09 tìm lại trong phiên cũ):** Lancel lan-xồ, Lucas lu-cát, Golem gô-lem, Damien đa-men,
Garfiel ga-phi-eo, Karen ca-ren, Darius đa-ri-ớt, Violet vai-ô-lét, Hunter hăn-tờ / hăn-tơ, Claudia cờ-lau-đi-a, Ragna rác-na, Audin au-đin,
Forthorthe pho-tho-thơ, Hyrkan hi-can, Sylphy xin-phi, Ainz ên, Eve e-ve, Ruth rút, Elf eo, Cliff cờ-líp, Ash át, Judge dắc-dồ, Max mắc,
Mix mích, King kinh, Starling xờ-ta-linh, Maria ma-ri-a, Dante đan-tê, Mikhail mi-kha-in, España ét-pa-nha, Blanche bờ-lan-che, Ciel xi-eo,
Reine ren, Novem nô-vem, Will guyu (alt guyn), William guy-li-am, Wolf gốp, Weiss guây, Wendy guen-đi, Walker goắc-cơ, Wood guốt, goblin góp-lin,
tablet táp-lét, Andrew an-riu, Scotland xờ-cót-lừn, Patrick pa-trích, Jud dút, Undead ăn-đét, Dusk đắc, Shakespeare xếch-xơ-pia, Pierce pia,
Hilde hiu-đơ, Gilbert ghiu-bớt, Franklin phờ-ranh-lin, Kirk cấc (alt cớt), Burke bấc (alt bớt), Hamburg ham-bơ, George gióc; bell beo,
spell xờ-peo, cobra cốp-ra, April ây-rồ, father pha-dờ, mother ma-dờ, Anne an-ne, Claire cờ-le, Louise lui, Richard ri-chát, Roland rô-lừn,
Austin ô-tin. Từ 02-09: light lai, house hau, sound sao, point poi, mouse mau, oldest ôn-đít, box bóc, text tếch, next nếch, card cạc,
water guốt-tờ, west goét, wind guyn, world gua, jack dách, doctor đóc-tờ, monster mon-tơ, star xờ-ta, stone xờ-tôn, sky xờ-kai, school xờ-cun,
space xờ-pây, month măn, brother bờ-ro-dờ, mary ma-ri, charlie chác-li, nation nây-sừn, station xờ-tây-sừn, action ách-sừn, vision vi-sừn,
cable cây-bồ, table tây-bồ, lake lếch, elena e-le-na, carmen ca-men. Từ mượn từ điển: taxi → tắc-xi.
Cách viết vần lạ (gióch, cớc, bớc) được thử bằng 5 giọng: máy đọc lệch, chủ sách chọn dạng đúng chính tả (gióc, cấc, bấc).

Luật rút ra (chung các lần):
- Tên ngắn MỘT phụ âm đầu + nguyên âm + MỘT phụ âm + e câm đọc theo MẶT CHỮ, e cuối đọc **e** (mi-ke, gia-ke, de-ke, ro-xe, na-te,
  ca-le; o → o, s → x, z → d; c + e mềm: lu-xe; g + e cứng: ca-ghe). Phụ âm mũi (m, n) thì đi đường âm vị (Jane → giên, game → ghêm),
  cụm phụ âm đầu cũng vậy (Blake → bờ-lếch, Grace → gờ-rây). Chỉ áp cho chữ viết hoa: từ thường (make, late) đi đường âm vị.
- Ca riêng, không suy rộng: Kate → ca-tê, Pete → pi-tờ, guild → gui, time → tham, Thomas → tho-mát, great → gờ-rít (ea không thành i),
  Paul → pau, higher → hai-gờ, Dalton → đan-tơn, days → đay, Laplace → (la-pờ-)lết, Walt → guốt (l bỏ trước t),
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
- Phụ âm tắc + l / r GIỮA từ: sau nguyên âm NHẤN, tắc đứng một mình thì KHÉP âm tiết trước (tablet → táp-lét, goblin → góp-lin,
  Scotland → xờ-cót-lừn, cobra → cốp-ra); sau âm không nhấn tách "Cờ" huyền, âm tiết trước mở (Laplace → la-pờ-lết). t + r vẫn "tr"
  (Patrick → pa-trích, Đi-troi); d + r trước u → r (Andrew → an-riu). nk + l: k rơi (Franklin → phờ-ranh-lin).
- w đầu từ → **g + âm đệm** trước mọi nguyên âm (lần 9; lần 7 giới hạn "chỉ trước âm o" là SAI): wi → guy (Will → guyu, William → guy-li-am,
  wind → guyn, well → goeo), we → goe (Wendy → goen-đi, west → goét), wei → guây (Weiss), wa / wo + phụ âm cuối → guô (water, Wood → guốt, Walt),
  wa + c → goắc (Walker), wol → gốp (Wolf), world → gua. Ngoại lệ dạng sách báo: Washington → oa-xinh-tơn. Bộ kiểm âm tiết nhận "guy…" như vần
  của i (chủ sách nghe "guyu" đọc được, 04-10). Nửa sau của từ ghép không áp (sandworm → xan-u-ơm).
- l cuối: sau i → **iu** (Will guyu, Hilde hiu, Gilbert ghiu, skill xờ-kiu); sau e → **eo** (Elf, bell beo, spell xờ-peo; -iel → i-eo:
  Ciel, Garfiel; trước t / d giữ n: Roosevelt); sau schwa → ồ (Lancel lan-xồ, cable cây-bồ).
- Phụ âm cuối: s → t sắc (Lucas cát, Darius ớt); sh → t (Ash át); th → t (Ruth rút); x → c, sau i → ch (Max mắc, Mix mích); ck / c sau i, a
  → ch (Patrick trích, Jack dách); f → p (Cliff líp); sk → c (Dusk đắc); /dʒ/ cuối → âm tiết dồ (Judge dắc-dồ); o + ch cuối → óc (George gióc).
  Sau nguyên âm ĐÔI phụ âm cuối rơi (light lai, sound sao, point poi, house hau).
- Nguyên âm: /ʌ/ → ă (Hunter, Undead, Dusk, Judge); /ɜːr/ → ơ, + tắc cuối → âc (Kirk cấc, Burke bấc; vần ơc không có); /ɪə/ → ia (Pierce pia);
  /ɔː/ + st → ô, s rơi (Austin ô-tin); ŋ sau i → nh (King kinh); ŋk sau a → nh (Franklin ranh).
- -er cuối → "-tờ" huyền (water, doctor, Hunter; sau st giữ ngang: Master, monster mon-tơ); -tion / -sion / -land → "-ừn" huyền
  (nây-sừn, xờ-tây-sừn, vi-sừn, xờ-cót-lừn, rô-lừn); -ton / -son tên người giữ ngang (oa-xinh-tơn, ê-đi-xơn). dh → d (pha-dờ, bờ-ro-dờ).
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
| /θ/, /ð/ | th / đ (code quét chọn th: Arthur a-thơ; sửa 04-10 từ "x", doc cũ vênh code) | [Chọn] |

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
- **Studio** (`abook/studio_names.py`, gọi từ pha đọc tên `analysis.reconcile_name_pronunciations`): gốc cuốn đoán bằng chính `names.book_origin` trên chữ các chương của dự án
  (chưa có ghi đè). Trước CMU / LLM, mỗi tên chưa khoá: (a) cuốn "ja" / "ko" và luật đọc được mọi chữ (`names.name_reading`, cả hậu tố gọi) -> khoá cách đọc ấy, nguồn
  `rule_romanization`, qua bộ kiểm chặt `vietnamese_syllable.valid_spoken_form`; (b) mọi chữ là từ / tên Anh của `english_words.txt` -> khoá đúng mặt chữ, nguồn `keep_english`
  (mọi máy đọc của Studio nói được tiếng Anh; thử 04-10: VieNeu của Studio đi qua cùng sea-g2p, Whisper nghe "Kate", "Michael", "Washington" để nguyên ra "Kết", "Michael",
  "Washington"); tên nhiều chữ quyết từng chữ (âm tiết Việt viết sẵn giữ nguyên), một chữ không quyết được thì cả tên đi đường cũ. Còn lại như trước: CMU, rồi LLM (prompt có
  thêm gốc cuốn và vài cách đọc chủ sách đúng gốc, do luật tính), rồi bộ dự phòng - hai đường này vẫn kiểm lỏng như cũ. Tên đầy đủ đi LLM mà có chữ đã quyết bằng luật
  ("Michael Godswill" khi "Michael" giữ tiếng Anh) được sửa lại cho chữ ấy đọc như khi đứng riêng. Tên đã khoá (cả cách đọc người nghe chọn) không đổi.
  Khâu so ASR (`asr.transcript_metrics`) so mềm chữ Anh để nguyên: Whisper viết lại theo âm nó nghe ("Kate" -> "Kết" / "Kat", "Shadow" -> "Sado", "Portal" -> "Porto"),
  câu ngắn vì thế từng trượt (WER 0,33); chữ nghe được có cùng khung phụ âm (lệch một khi khung >= 3) được tính là khớp (`studio_names.heard_as_english`), chỉ thêm cơ hội
  khớp như phép nở số dính đơn vị. Cờ nói tiếng Anh theo máy đọc ở `studio_names.ENGINE_SPEAKS_ENGLISH` (Supertonic = False); Studio nhánh này chỉ đúc bằng VieNeu.
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
