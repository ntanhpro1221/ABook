# Lý thuyết chọn nhạc nền cho đoạn truyện - "sợi dây" giữa chữ và nhạc

Tổng hợp của phiên Lead, 02-10. Bốn báo cáo gốc có trích nguồn đầy đủ nằm ở `docs/music_theory/`:

| File | Nội dung |
|---|---|
| `A_music_emotion.md` | tâm lý học cảm xúc âm nhạc, các bộ dữ liệu chuẩn hoá |
| `B_narrative_crossmodal.md` | cảm xúc trong văn bản và truyện, lý thuyết nhạc phim/game, ghép chữ-nhạc |
| `C_descriptor_axes.md` | các trục ngoài cảm xúc, thư viện nhạc chuyên nghiệp, nhạc dưới giọng nói |
| `D_ai_methods.md` | AI đã làm được gì ở hai phía và ở cầu nối, cách huấn luyện, thí nghiệm nên làm |

Mỗi nhận định dưới đây ghi mức chắc: **[CM]** đã chứng minh trong tài liệu; **[GT]** chứng minh ở bài toán gần (phim, game, truyện cổ tích), mang sang; **[SL]** suy luận của ta, phải đo.
`docs/MUSIC_RESEARCH.md` (phiên Music) là nhật ký đo đạc; file này là nền lý thuyết mà code phải theo.

## 1. Bài toán, nói chính xác

Với mỗi đoạn truyện (scene), chọn một đoạn nhạc trong danh mục cố định (hoặc im lặng) sao cho người nghe sách thấy nhạc
**hợp** với đoạn đó, nằm **dưới** giọng đọc mà không lấn, và **liền mạch** qua cả cuốn.

Ba sự thật định hình lời giải:

1. **Không có dữ liệu cặp (đoạn văn xuôi, bài nhạc) có người chấm, ở bất kỳ ngôn ngữ nào [CM - D §5.8, B §5.4].** Mọi hệ
   thống đang chạy đều nối hai phía qua một **không gian chung mô tả bằng tay**, hoặc nhờ LLM viết mô tả nhạc. Điểm số chủ
   sách chấm sẽ là dữ liệu gốc đầu tiên cho thể loại này.
2. **Ghép theo nhãn trùng tên thì thất bại** khi bộ nhãn phía chữ và phía nhạc khác nhau: P@5 = 0 (Won et al., ISMIR 2021)
   [CM]. Phải có một **hợp đồng** chung hai phía cùng hiểu. Đó là "sợi dây".
3. **Nút thắt là đoán không khí của đoạn, không phải cách biểu diễn.** Đo trên bộ cảnh 4:
   - hai người chấm khớp nhau r 0,83-0,91; máy chỉ 0,29-0,45;
   - với đầu vào của người, ba trục và tỉ lệ cảm xúc cho kết quả ngang nhau (0,692 / 0,691); gộp hai cách được 0,669.

   Vậy hợp đồng phải đủ giàu để không mất thông tin, nhưng phần lớn công sức phải dồn vào **đoán phía chữ cho đúng**.

## 2. Hợp đồng chung: hai phía mô tả bằng cùng một bộ trục

Nguyên tắc chung cho mọi trục:

- **Cảm xúc nhạc THỂ HIỆN, không phải cảm xúc người nghe THẤY** [CM - A §2.5]. Cảm xúc người nghe thấy bị lệch theo việc
  họ có thích bài không, theo tâm trạng lúc nghe và theo kỷ niệm riêng, và thường ghi thiếu cảm xúc tiêu cực. Nhạc phim
  tác động lên cách hiểu cảnh qua cái nó thể hiện.
- **Phía truyện ghi không khí NGƯỜI ĐỌC cảm nhận, không phải cảm xúc nhân vật** [CM - B §5.2]. Nhãn theo góc người đọc
  đáng tin hơn (EmoBank). Cảm xúc nhân vật (app đã có cho giọng đọc) là đặc trưng đầu vào, không phải đích.
- **Mỗi điểm số đi kèm độ không chắc và nguồn** (người / model / nhãn có sẵn). Không bao giờ trộn lặng lẽ dữ liệu từ các
  thang đo khác nhau [CM - A §3.2].
- **Không ép cộng bằng 1.** Mỗi cảm xúc là một cường độ độc lập 0..1 [CM - A §4.3: Emotify cho chọn tới 3/9 cảm xúc; ép
  phân phối làm mất cảm xúc pha trộn]. Bản chuẩn hoá `p = s/Σs` chỉ là dạng suy ra khi cần so phân phối.

### Lớp 1 - ba trục cảm xúc liên tục (cả đoạn lẫn bài)

| Trục | Khoảng | Mốc | Độ tin cậy | Nguồn |
|---|---|---|---|---|
| `valence` (vui-buồn) | −1..+1 | −1 u tối, 0 trung tính / mập mờ, +1 tươi sáng | nhạc: kém nhất (người r ≈ 0,65; máy R² 0,52-0,63). Chữ: tốt nhất | Russell 1980; A §4.1; D §1.3, §2.2 |
| `energy` (năng lượng) | −1..+1 | −1 rất êm, thưa, chậm; +1 rất mạnh, dày, nhanh | nhạc: tốt nhất (người 0,75; máy R² 0,72-0,79). Chữ: kém (LLM 8B r ≈ 0,2) | Thayer; Schimmack & Grob 2000 |
| `tension` (căng thẳng) | −1..+1 | −1 thả lỏng, đã giải quyết; +1 rất căng, hồi hộp | thang đo người ổn định (α 0,98); máy chưa có chuẩn đo [khoảng trống] | Schimmack & Grob 2000; Lehne & Koelsch 2015; IsoVAT |

- Mỗi trục lưu `mean`, `sd`, và `n` hoặc `confidence`.
- `tension` tách khỏi `energy`: hồi hộp lặng lẽ là energy thấp, tension cao [CM - S&G 2000; B §5.4].
- Với đoạn dài, `tension` có thể là chuỗi theo thời gian (dồn lên / nhả ra) [GT].
- Bỏ trục `dominance` của PAD: phía nhạc hầu như không dùng [B §5.4].
- Đổi thang từ các bộ dữ liệu theo A §5.2: Likert 9 điểm → `(x−5)/4`; DEAM → `x/10`; PMEmo → `2x−1`. Chuẩn hoá z theo từng
  nguồn trước khi gộp.

### Lớp 2 - 13 cảm xúc nhạc, cường độ độc lập 0..1 (cả đoạn lẫn bài)

GEMS-9 (Zentner et al. 2008) làm xương sống. Gộp `wonder` với `transcendence`, vì tách ra thì chúng là hai thang kém tin cậy
nhất. Thêm bốn lớp mà nhạc nền truyện cần nhưng GEMS thiếu [CM - A §5.2]. Mỗi lớp định nghĩa bằng 2-3 từ mô tả và ví dụ
mẫu, không bằng một từ: từ chỉ cảm xúc dịch qua ngôn ngữ khác hay lệch nghĩa (Celen et al. 2025).

| # | Mã | Tiếng Việt (hiển thị) | Mô tả |
|---|---|---|---|
| 1 | `peacefulness` | bình yên | thanh thản, êm, vỗ về |
| 2 | `tenderness` | dịu dàng | ấm áp, trìu mến, lãng mạn |
| 3 | `nostalgia` | hoài niệm | bâng khuâng, buồn mà ngọt |
| 4 | `sadness` | buồn | sầu, đau, tang tóc |
| 5 | `joy` | vui tươi | hân hoan, nảy nhịp |
| 6 | `playful` | tinh nghịch / hài | buồn cười, lém lỉnh, ngộ nghĩnh |
| 7 | `power` | hào hùng | mạnh mẽ, chiến thắng, sử thi |
| 8 | `wonder` | kỳ vĩ | choáng ngợp, uy nghi, siêu thoát |
| 9 | `tension` | căng thẳng | bồn chồn, chờ đợi, hồi hộp |
| 10 | `fear` | sợ / rùng rợn | đáng sợ, điềm gở, kỳ quái |
| 11 | `anger` | giận dữ / hung bạo | dữ dội, hung hăng, sục sôi |
| 12 | `mystery` | bí ẩn / mơ màng | huyền bí, mộng, mờ ảo |
| 13 | `moved` (tuỳ chọn) | xúc động | lay động, thấm thía; chỉ giữ nếu người chấm tách được khỏi 2+4+8 |

Thêm trường `intensity` 0..1 (độ mạnh cảm xúc chung, khác với năng lượng). Chen et al. 2022 cho thấy chỗ hụt chính của máy
là **cường độ**, không phải chọn sai loại [CM - B tóm tắt].

### Lớp 3 - chức năng của đoạn trong truyện (cả đoạn lẫn bài)

Không có bảng phân loại chuẩn; bộ duy nhất làm cho truyện mạng là Chen et al. 2022 (12 lớp, macro-F1 0,53) [CM]. Bảng dưới
gộp bộ của Chen, Bardo và các mục "use case" của thư viện nhạc (B §5.1, C §5.1 #13). Đây là **từ vựng của ta [SL]**.
Lưu thành phân phối, không lấy một nhãn duy nhất.

`daily_calm`, `warm_tender`, `comedy`, `romance`, `awkward_misunderstanding`, `mystery_eerie`, `suspense_threat`,
`battle_action`, `climax_triumph` (爽点), `sorrow_loss`, `despair_injury`, `conflict_argument`, `solemn_ceremony`,
`training_cultivation`, `travel_explore`, `town_tavern`, `night_rest`, `horror`, `neutral_background`.

Kèm `salience` ∈ {`background`, `normal`, `climax`}: mức nổi bật của nhạc. "Nền tích cực / tiêu cực" của Chen nghĩa là
"đoạn dẫn truyện ít điểm nhấn, đặt nền nhỏ" [GT - Gorbman: nhạc phim không được nghe thấy].

### Lớp 4 - bối cảnh và văn hoá

- `idiom` (đoạn và bài): xác suất trên 12 giá trị (C §4.2): `cn_traditional`, `cn_cinematic`, `jp_traditional`,
  `kr_traditional`, `west_medieval_fantasy`, `west_orchestral_cinematic`, `jrpg_game`, `contemporary_acoustic_pop`,
  `electronic_scifi`, `ambient_neutral`, `horror_textural`, `comedic_light`.
  - **Lọc cứng ở cấp CUỐN**: chỉ dùng các idiom trong bảng phong cách của cuốn, cộng `ambient_neutral`.
  - **Chấm mềm ở cấp đoạn**: ví dụ một đoạn hồi tưởng thế giới hiện đại trong truyện isekai.
- `era` ∈ {ancient, medieval, early_modern, modern, futuristic}: phụ, ưu tiên thấp.
- Phía đoạn: bảng phong cách cấp cuốn do LLM đọc tóm tắt / mấy chương đầu + thẻ thể loại của truyện (hako) + nhạc của bản
  chuyển thể anime nếu có (E_signal_sources.md §2); người dùng sửa được nếu muốn.

### Lớp 5 - tính hợp làm nền dưới giọng đọc (chỉ phía bài)

Từ C §3 và §5.1. Phần lớn đo được thẳng từ âm thanh.

| Trục | Kiểu | Vai trò | Căn cứ |
|---|---|---|---|
| `vocal_kind` | none / wordless / lead_foreign / lead_vi + `p_voice` | **lọc cứng**: loại lời hát; giọng không lời chỉ khi đoạn cho phép | mạnh (lời cùng ngôn ngữ hại nhất) |
| `melodic_salience` | 0..1 | phạt × mật độ thoại của đoạn | trung bình (bản "underscore" của APM) |
| `masking_index`, `required_ld_lu` | 0..1; LU | phạt + đặt mức trộn (nhạc thấp hơn giọng ≥ 10 LU, Torcoli 2019) | mạnh về nguyên lý; ngưỡng là lựa chọn kỹ thuật |
| `busyness` | số onset/giây + phần trăm vị trí | phạt lệch khỏi dải đích theo loại đoạn | trung bình |
| `tempo_bpm` | số thực + độ tin | phạt lệch | trung bình |
| `peak_excursion_lu`, `lra_lu` | LU | **lọc cứng** cú vọt âm lượng > ~8 LU; mềm với LRA | trung bình |
| `tonality` | p_tonal, mode, độ nghịch tai | mềm | trung bình |
| `structure` | độ dài, intro/outro, kiểu kết, điểm lặp, chất lượng lặp, phiên bản | lọc cho chỗ chuyển; mềm cho độ dài | thực hành ngành |
| `quality`, `license` | | **lọc cứng** (license theo `source-strictness`: CC0 / BY / BY-SA / BY-NC dùng được, ND không) | |

Phía đoạn cần thêm: `dialogue_density` (số câu thoại mỗi phút), `duration_s`, `allow_wordless`.

### Lớp 6 - nhúng ngữ nghĩa (phụ, để phá thế hoà)

Một vector nhúng mô tả phong cách / bối cảnh ("quán rượu trung cổ", "lễ hội trường học"). Lấy từ tháp chữ đa ngôn ngữ của
CLaMP 3 hoặc câu LLM viết lại bằng tiếng Anh, so với tháp âm thanh có giấy phép tự do. Chỉ dùng phá thế hoà và cho gợi ý
bối cảnh mở [GT - B §5.3 cách D]. Tháp chữ của các model hai tháp là mắt xích yếu: mô tả dài không giúp gì [CM - D §1.5].

## 3. Phân tích phía nhạc (danh mục cố định, làm một lần)

Rà soát đầy đủ mọi nguồn tín hiệu hai phía, cái nào đang dùng, cái nào thiếu, và hai đường ghép mới (chỉ thị nhạc bằng
lời, LLM xếp lại top-K): **music_theory/E_signal_sources.md**.

**Nguồn tín hiệu phía bài (02-10, chủ sách):** bài nhạc không phân tích từ số 0. Có ba nguồn, gộp lại và đo đóng góp từng
nguồn bằng ablation (MUSIC_RESEARCH.md "GỘP BA NGUỒN"):
- **Âm thanh qua model:** CLAP / đầu dò, model nghe.
- **Âm học đo trực tiếp:** nhịp, trưởng / thứ, âm vực, độ nghịch tai, articulation, độ to và đường bao, âm sắc, mật độ.
- **Văn bản và ngữ cảnh:** tên bài, mô tả và ghi chú tác giả, tag, nhạc cụ, bình luận, bài viết cho game / phim nào, lời.
  Một LLM đọc phần chữ này, cho 13 cường độ + V/E/T + độ tin cậy.

1. **Cắt mỗi bài thành các đoạn đồng nhất**, chấm từng đoạn: cửa sổ 10 giây không thấy được cung của cả bài [CM - D §1.5].
   Ranh giới đoạn nhạc là chỗ được phép chuyển bài.
2. **Model dùng được (giấy phép tự do, chạy máy nhà):** LAION-CLAP music (Apache-2.0), MS-CLAP (MIT), PANNs CNN14 (MIT;
   cho sẵn 7 lớp cảm xúc của AudioSet), MusicFM-FMA (MIT), MusiCNN (ISC).
   - MERT, MuQ, TTMR++ (CC-BY-NC) mạnh hơn - DÙNG ĐƯỢC (chủ sách 02-10: mã nguồn công khai, không thu tiền, model NC ổn).
   - Essentia: model ĐÃ HỌC sẵn V/A (DEAM, emoMusic, MuSe) và tâm trạng/chủ đề (MTG-Jamendo), CC BY-NC-SA - dùng được,
     đưa vào ablation phía bài. openSMILE chỉ để đối chiếu khi phát triển.
3. **Đừng tin CLAP đoán cảm xúc khi chưa huấn luyện.** Trên GlobalMood: r = 0,08; tinh chỉnh trên 1.180 bài lên 0,31 [CM].
   CLAP nhận **nhạc cụ** Đông Á tốt (phiên Music đo AUC 0,994), nhưng nhận nhạc cụ khác đoán cảm xúc. Cách đúng là đầu dò
   nhỏ (MLP) trên vector nhúng đóng băng, huấn luyện cho V/E/T và 13 cảm xúc [CM - D §4.2].
   - Dữ liệu: DEAM, PMEmo, EmoMusic, Soundtracks, Emotify (kiểm giấy phép từng bộ trước).
   - Rồi **neo lại trên chính danh mục của ta** bằng phép so sánh (BWS / cặp) do MÁY chấm (Claude chấm mù, model nghe chấm
     từng clip) - chủ sách không chấm gì.
4. **Lớp 5** đo bằng tín hiệu: độ to, onset, phổ trong dải 1-4 kHz, tách giọng.
5. **IncompeBench (Clavié et al. 2026)** dựng trên chính Incompetech: 1.574 đoạn, 500 truy vấn, nhãn kiểm với người ở mức
   κ 0,94 [CM]. Dùng làm bài kiểm phía tìm nhạc.

## 4. Phân tích phía truyện

1. **Cắt cảnh** theo đơn vị tình tiết, không theo từng câu: cảm xúc nhân vật đổi từng câu, nhạc đổi theo cảnh [CM - Chen
   2022: cảm xúc theo đoạn văn quá nhiễu; Gorbman: nhạc liền mạch]. Hiện app đã có `music_scenes`.
2. **LLM nội bộ (Qwen 9B LoRA)** cho mỗi cảnh:
   - Lớp 2 và 3 dạng cường độ / phân phối;
   - **V/E/T theo cách SO SÁNH** giữa các cảnh trong cùng chương (từng cặp, hoặc chọn nhất / kém nhất trong nhóm 4), rồi
     đổi ra điểm bằng Bradley-Terry hoặc đếm BWS. Lý do: LLM 8B chấm thẳng năng lượng chỉ r ≈ 0,2, và chấm hẹp thang (độ
     trải bằng nửa người). So sánh đáng tin hơn với cả người lẫn LLM [CM - Kiritchenko 2017; Bagdon 2024; EmoPair 2026];
   - bảng phong cách (cấp cuốn) và `salience`.
3. **Hiệu chỉnh** bằng hồi quy đơn điệu (isotonic) về thang chung, và nới lại độ trải bị nén [CM - Inoshita 2026: tốt nhất
   trong các cách hiệu chỉnh sau].
4. **Kiểm chéo rẻ:** PhoBERT / ViSoBERT tinh chỉnh trên UIT-VSMEC. Lưu ý đó là dữ liệu mạng xã hội, không phải văn chương,
   nên lệch miền.
5. **Văn dịch Việt từ JP/KR/CN chưa có nghiên cứu nào** [khoảng trống] - phải đo trên sách của ta.

## 5. Sợi dây: hiệu chỉnh hai phía về một thang, rồi chấm độ hợp

1. **Bộ neo chung:** khoảng 40-60 cảnh neo và 40-60 đoạn nhạc neo trải đều không gian. Chủ sách (có thể thêm 2-3 người
   chấm) xếp chúng bằng BWS trên từng trục. Bộ neo định nghĩa thang chung, như các từ neo của NRC-VAD [GT - D §5.3].
2. **Ánh xạ đơn điệu** từ điểm thô của mỗi phía về thang neo. Đừng khớp phân vị giữa sách và danh mục: sách u tối không bị
   ép dùng nhạc tươi [SL - D §5.3].
3. **Chấm độ hợp** của đoạn `s` với bài `m` [GT/SL - D §5.4]:

   ```
   Score(s, m) = − Σ_d w_d · (μ_s,d − μ_m,d)² / (σ_s,d² + σ_m,d² + τ_d²)     # Lớp 1, trừ theo độ không chắc
                 + λ · sim(cường độ 13 cảm xúc)                               # Lớp 2: cosine, KHÔNG phạt pha trộn
                 + φ · khớp(chức năng)  + ι · khớp(idiom)                     # Lớp 3, 4
                 + γ · cos(nhúng ngữ nghĩa)                                   # Lớp 6
                 − phạt Lớp 5 (salience × mật độ thoại, che lời, busyness, tempo, vừa dùng)
                 + κ · [m nối tiếp bài đang phát]
   ```

   Trọng số khởi đầu: **energy > tension > valence** (1,0 / 0,8 / 0,6 - theo độ tin cậy đo được) [CM về thứ tự, SL về con
   số]. Rồi **học các trọng số bằng Bradley-Terry trên phán quyết cặp mù của máy chấm** (chủ sách không chấm): vài trăm phán quyết là đủ, vì chỉ
   có vài tham số [GT - D §4.2 bước 4].
4. **Lọc cứng trước khi chấm:** giấy phép, chất lượng, có lời hát, idiom ngoài bảng phong cách của cuốn, cú vọt âm lượng.
5. **Ổn định:** chỉ đổi bài khi bài mới hơn bài đang phát một khoảng ≥ biên, liên tục ≥ N đơn vị chữ (trễ kiểu Bardo), ưu
   tiên đổi ở ranh giới cảnh [CM trong miền RPG - Bardo n = 61].
6. **Không chắc thì êm, hoặc im:** nếu `P(hợp) = sigmoid(điểm đã hiệu chỉnh)` < θ, hoặc phía chữ quá không chắc (σ lớn,
   phân phối dàn đều), thì đặt nền trung tính (năng lượng thấp, vui-buồn ở giữa), hoặc im lặng. Nhạc sai làm người nghe
   hiểu sai và nhớ sai cảnh (Boltz 2001) [CM]. θ chọn sao cho tỉ lệ "không hợp" dưới một ngưỡng ghi trước. Im lặng tốt hơn
   nhạc khi nào thì chưa ai nghiên cứu [khoảng trống - E5].
7. **Cảm xúc pha trộn:** đoạn buồn-mà-ấm khớp với bài có cả `sadness` lẫn `tenderness` cao. Phân phối hai đỉnh (hài + buồn)
   thì ưu tiên bài có hồ sơ rộng, hoặc theo cảm xúc còn kéo sang cảnh sau [SL].
8. **Mặc định là tương hợp, không đối nghịch:** không bao giờ "sáng tạo" bằng nhạc ngược không khí; không chắc thì lùi về
   nền [B §3.2, §5.4].

Chỉ khi có ≥ 1-2 nghìn bộ ba (cảnh, bài, phán quyết) đã kiểm mới thử **không gian chung học được** (metric learning 3 nhánh
của Won, hoặc SupCon với positive mềm `exp(−d_VAT)`). Chỉ giữ nếu nó thắng bước 3 trên các cuốn để riêng.

## 6. Lưu trữ

- **Bài:** bảng `music_descriptor`, mỗi dòng là một bộ (bài, trục, nguồn) (C §5.3).
  - `value_num` hoặc `value_json` (xác suất, không có/không);
  - `confidence`, `source` (`human:owner` | `model:<tên>@<bản>` | `meta:<kho>`), `vocab_version`;
  - ưu tiên nguồn: người > nhãn có sẵn đã duyệt > model;
  - lưu vector nhúng để thêm nhãn mới mà không giải mã lại âm thanh.
- **Đoạn:** cùng bộ từ vựng (Lớp 1-4), kèm `dialogue_density`, `duration_s`, `salience`, độ không chắc.
- **Tương thích EmotionML:** EmotionML là chuẩn W3C 2014 và cho phép bộ từ vựng riêng; bộ từ vựng chính thức không có
  GEMS hay bộ nào cho âm nhạc [CM]. Nên lưu JSON tương thích EmotionML với URI riêng (`abook:vet`, `abook:music-emotion-13`,
  `abook:scene-function`).
- **Cần xin phép:** danh sách từ đầy đủ GEMS-45 cần tác giả cho phép; tên 9 thang GEMS thì dùng tự do [CM - Moscati 2024].
- **Không tương thích dữ liệu cũ:** app chưa phát hành.

## 7. Thí nghiệm theo thứ tự giá trị (D §5.7)

| # | Thí nghiệm | Vì sao trước |
|---|---|---|
| E1 | **Bộ đáp án + trần người**: 150-300 cảnh LN/KR/CN × 6-8 bài ứng viên; máy chấm cặp mù (Claude mù x2 + model nghe chấm từng clip; chủ sách không chấm); độ tin cậy chia đôi | mọi số đo sau cần nó; cho biết "tốt" tốt tới đâu |
| E2 | **Cảm xúc nhạc trên danh mục của ta**: PANNs-mood vs CLAP zero-shot vs đầu dò trên CLAP/MusicFM, so với BWS ~200 đoạn | phía nhạc cố định, sai ở đây hỏng mọi cuốn |
| E3 | **Cảm xúc phía chữ**: LLM chấm thẳng vs so sánh trong chương vs PhoBERT; hiệu chỉnh isotonic; so với E1 | quyết định cách làm phía chữ |
| E4 | **Bóc từng lớp của sợi dây**: VA → +T → +13 cảm xúc → +chức năng → +nhúng → trọng số học Bradley-Terry | biết lớp nào mang tín hiệu |
| E5 | **Khi nào im lặng**: nhạc hợp nhất vs nền trung tính vs im, ở nhiều mức điểm | chưa ai nghiên cứu; quyết định trải nghiệm |
| E6 | **Chính sách đổi bài**: biên trễ, thời gian tối thiểu | Bardo: ổn định làm tăng chất lượng |
| E7 | **Không gian học được** | chỉ khi đủ dữ liệu E1-E4 |
| E8 | **LLM làm người chấm**: model nội bộ có tái tạo phán quyết E1 không (alt-test) | để chấm hàng loạt rẻ |

Đang chạy (02-10, phiên Music): segllm 03-10 so cách đoán phía đoạn (VET, phân phối, 9 cường độ độc lập) với hai người
chấm mù - là một phần của E3.

## 8. Những chỗ khác với code hiện tại

- `music_select` dùng một điểm V/A + T, trọng số tay (`TENSION_WEIGHT` 0,6, `MAX_DISTANCE` 0,75, `CALM_TARGET`).
  → Thêm σ, Lớp 2-5; trọng số energy > tension > valence; học trọng số từ E1.
- Phân phối GEMS-9 phía bài hiện là **softmax** (cộng 1) → đổi sang **sigmoid độc lập** trên 13 lớp. Phân phối chỉ là dạng
  suy ra.
- 14 phong cách hiện có → ánh xạ sang 12 `idiom`; lọc cứng cấp cuốn như hiện nay.
- Nhánh `dev/music-gems` (phiên Music): giữ ý "phân phối + ba trục gộp", nhưng làm lại theo Lớp 2 (13 cường độ độc lập) và
  điểm có σ. **Chưa gộp main.**

## 9. Bất đồng trong tài liệu (để không tin quá mức)

- **Nhóm cảm xúc hay trục là cơ bản hơn?**
  - Nghiêng về nhóm: Cowen 2020; Eerola & Saari 2025.
  - Nghiêng về trục: Russell, Barrett.
  - Dạng lai của ta đứng giữa hai phía.
- **Hai hay ba trục?** Với nhạc, `tension` phần lớn rút về hai trục được (E&V 2011); với cảm xúc nói chung thì không
  (S&G 2000).
- **Cấu trúc GEMS:** 9 nhân tố (Zentner 2008) so với khoảng 3 chiều hiệu dụng trong dữ liệu đám đông (Aljanaki 2014).
- **Tính phổ quát:** có một lõi chung (Fritz 2009); nhưng vui-buồn và nghĩa của từ thay đổi theo văn hoá (Cowen 2020,
  Celen 2025). Chưa có thang cảm xúc nhạc nào được kiểm định cho tiếng Việt, Nhật, Hàn hay Trung.
- **Tương hợp hay đối nghịch** (nhạc ngược không khí có chủ ý trong phim). Ta mặc định tương hợp.
