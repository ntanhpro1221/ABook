# Cân bằng giọng

Cùng một câu, các giọng khác nhau về tốc độ và độ to vì mỗi giọng thu riêng, không có mốc chung. Cách chữa:
mỗi giọng có MỘT bản ghi hằng số đo trước; lúc thu máy tự áp, không đo-rồi-kéo từng câu.

## Cách áp trong app

### Khoá giọng và bảng

Một giọng là `(engine, phiên bản engine, preset, bậc formant)`, khoá bằng chuỗi ổn định
`vieneu@3.8.1/<preset>/f100` (`voice_balance.voice_key`; `f100` là bậc formant 1,00, `f093` là 0,93).
Bảng nằm ở `abook/assets/voice_balance.json`:

| trường | ý nghĩa |
|---|---|
| `version` | phiên bản định dạng bảng (mã từ chối số khác) |
| `engine_versions` | phiên bản engine mà bảng được đo cho; phải khớp bản ghim ở `runtime_contract` |
| `x` | núm tốc độ chung của cả sách |
| `L_lufs` | mức độ to chung (LUFS) |
| `pace_floor_scale` | hệ số chung nhân vào sàn của cổng nhịp |
| `voices[khoá].r` | hệ số tốc độ riêng của giọng (nhân) |
| `voices[khoá].o_db` | lệch độ to riêng của giọng, dB (cộng), đo ở x = 1 |
| `voices[khoá].ref_lufs` | LUFS trung bình đã đo của bản thô của giọng (sau cao độ và tempo) |
| `voices[khoá].pitch_st` | màu giọng nền, bán cung (cộng); không đo, không đề xuất |

Đổi phiên bản engine thì khoá đổi theo, nên bảng cũ không áp nhầm cho bản mới: giọng thiếu trong bảng là
LỖI (`VoiceBalanceError`) ngay lúc phân vai hoặc lúc thu, không bao giờ lặng lẽ dùng 1,0. Test
`test_voice_balance.py` bảo đảm mọi giọng mà phân vai có thể tạo ra (thang formant + formant theo tuổi, của
mọi preset trong `VIENEU_PRESETS`) có bản ghi. `voice_balance.py` và file json nằm trong
`QUALITY_IMPLEMENTATION_FILES` (và `ANALYSIS_CASTING_IMPLEMENTATION_FILES`, vì `pitch_st` đi vào hồ sơ giọng):
sửa bảng đổi hash chất lượng, nên chỉ sửa ở nhánh dev khi không có lượt sản xuất nào đang chạy.

### Công thức và đơn vị

| đại lượng | thang | cách ghép | công thức |
|---|---|---|---|
| tốc độ | tỉ lệ (có số 0 thật) | NHÂN | `tempo = x · r_v` |
| độ to | dB/LUFS (mốc 0 là quy ước) | CỘNG dB | `gain_dB = L + o_v + offsets(câu) − ref_lufs_v` |
| màu giọng | bán cung (log tần số) | CỘNG | `pitch = pitch_st + độ lệch theo tuổi` |

Không bao giờ nhân giá trị dB hay bán cung với nhau.

- **Tốc độ.** `tempo` áp bằng WSOLA tương quan chuẩn hoá (`tts.apply_speed_change`, từ 04-10; trước đó WORLD), khoảng cho phép
  `SPEED_FACTOR_MIN = 0,70` đến `SPEED_FACTOR_MAX = 1,50` (bảng bị từ chối nếu `x · r` ra ngoài). Mặc định
  `x = 1`.
- **Độ to.** `audio_io.segment_gain_db` cho gain hằng số áp lên bản thô; không đo LUFS của câu.
  `offsets(câu)` = volume (`segment_target_lufs[volume] − segment_target_lufs["normal"]`: soft −3,0 /
  normal 0 / loud +1,2) + cảm xúc (`LOUDNESS_EMOTION_OFFSETS_DB[cảm xúc] · cường độ / 3`, chỉ khi volume
  là normal) + người kể (`segment_narrator_offset_db`). Hai câu cùng giọng, một to một nhỏ, ra cùng
  gain. Trần đỉnh `segment_peak_dbfs` (−2 dBFS) giữ làm chốt: đỉnh vượt thì hạ cho vừa, phần hạ ghi ở
  metric `peak_limited_db`; gain đã áp ghi ở `level_gain_db`. Bản ghép từ các phần đã áp gain
  (`merge_wav_parts_atomic`) chỉ còn trần đỉnh, không áp gain lần hai. Sách khoá từ trước thời LUFS giữ
  chính sách RMS cũ.
- **Cổng nhịp.** Sàn (ký tự và âm tiết) nhân với `pace_floor_scale · x`; cận trên không đổi. Ngân sách
  sinh của bản thô chia thêm cho tempo của giọng, tức là nhân `pace_floor_scale / r_v` (`x` triệt tiêu).
  Cổng chỉ còn bắt lỗi hỏng, không dùng để kéo tốc độ.

### Thứ tự áp

cao độ → tempo → gain. `o_v` phải đo SAU khi áp `r_v` (WORLD làm đổi độ to tới 2 dB tuỳ giọng; WSOLA chuẩn hoá ≤ 0,2 dB, vẫn đo
sau cho chắc). Trong `tts.py`
cao độ và tempo chạy trước `atomic_write_wav`, nơi gain được áp; formant nhân vật áp sau cùng, lúc ghép chương.

### Hai núm chung

- `x`: nhanh/chậm cả sách. 0,85 chậm 15% cho mọi giọng như nhau.
- `L_lufs`: to/nhỏ cả sách, dB. +1 dB làm mọi giọng to lên 1 dB như nhau.

Sửa hai số này trong file json (mọi giọng đi theo), không sửa từng giọng.

### Nhập số đo mới

Số thật do bộ đo sinh ra hai file; thả vào bảng bằng

```
cd _internal
runtime/.venv/Scripts/python.exe scripts/voice_balance_import.py rates.json gains.json [--create] [--dry-run]
```

Định dạng vào ghi ở docstring của script (`rates.json`: `r` hoặc `syll_per_s` cùng `median_syll_per_s`;
`gains.json`: `lufs` và tuỳ chọn `o_db`). Script chỉ đổi `r`, `ref_lufs`, `o_db`; không đụng `pitch_st`. Khoá
chưa có trong bảng là lỗi, trừ khi `--create`. Bảng được kiểm trước khi ghi (số hỏng thì file giữ nguyên) và
ghi lại bằng LF. Sau khi thả: chạy `tests/test_voice_balance.py`, ghi hash chất lượng mới.

## Số đo (phiên Model, 04-10)

Đo trên máy, không phải tai. Mã đo và số thô: Corpus/claude/model_lane/voice_balance (bản sao scratchpad phiên Model).

### Cách đo

- **Câu:** 40 câu trung tính, cố định, chọn tất định.
  - Lô 18 của sách 2: 11 câu kể, 9 câu thoại, 6 câu 1–3 tiếng, 4 câu dài ≥250 ký tự.
  - Thêm 10 câu LN Nhật trong Corpus/_full.
  - Chữ đưa cho giọng = `TTSCoordinator.spoken_text`; tham số lấy mẫu = `vieneu_sampling_for_segment`.
  - Mỗi giọng 2 hạt ở bậc f100, 1 hạt ở các bậc khác.
  - Nửa hiệu chỉnh 22 câu, nửa kiểm 18 câu.
- **Tốc độ:** âm tiết / giây nói. Giây nói = thời lượng trừ lặng mép và mọi quãng lặng ≥150 ms (VAD khung 10 ms).
  - Độ lệch của giọng = trung bình theo câu của log tốc độ, trừ trung bình CÙNG câu qua mốc. Cách này bỏ được hiệu ứng câu.
  - CI 95 % tính theo câu.
- **Độ to:** LUFS tích hợp của app (`integrated_loudness_lufs`), đo trên bản thô SAU cao độ (`pitch_st`) và SAU `r_v`.
  - WORLD kéo tốc độ làm đổi độ to, không đều giữa giọng: Thanh Bình ở tempo 0,76 lệch −3,7 dB so với dự kiến. Bảng hiện tại đo
    với WSOLA chuẩn hoá (mục "Cách kéo tốc độ" dưới).
- **Mốc tốc độ:** trung vị tốc độ GỐC (không hệ số tay) của 19 preset phân vai, bậc f100 = **4.56 âm tiết/giây**.
  - 2 người kể miền Trung và các model khác so với cùng mốc, không kéo mốc đi.
- **Núm x = 1,00** (chủ sách chốt 04-10). Để so: 4 giọng kể chuyện chủ sách chọn tốc độ bằng tai ngày 18-09 đọc ở 3.87 âm tiết/giây.
  - Tương đương x = 0.848.
  - Từ nay 4 giọng ấy đọc nhanh hơn mức đã chọn; muốn chậm cả sách thì vặn x, không sửa r_v.

### Theo preset (bậc f100)

| preset | tốc độ gốc (âm tiết/s) | lệch mốc % ±CI | r_v | log2(r_v) | hệ số tay cũ | ref_lufs (sau cao độ + r_v) | o_v dB ±CI | gain ở L = −25 | gain qua các bậc formant |
|---|---|---|---|---|---|---|---|---|---|
| Trúc Ly | 5.12 | +11.7 ±0.8 | 0.890 | -0.169 | 1 | -19.95 | +0.46 ±0.22 | -5.05 | -5.15 … -4.12 (12 bậc) |
| Thanh Bình | 5.09 | +11.1 ±3.8 | 0.895 | -0.160 | 1 | -19.36 | +1.05 ±0.33 | -5.64 | -5.64 … -4.14 (11 bậc) |
| Xuân Vĩnh | 4.99 | +9.1 ±2.5 | 0.913 | -0.131 | 1 | -21.58 | -1.17 ±0.23 | -3.42 | -3.48 … -2.03 (11 bậc) |
| Minh Quân Pro | 4.97 | +8.6 ±1.2 | 0.917 | -0.124 | 1 | -21.47 | -1.06 ±0.31 | -3.53 | -3.53 … -1.91 (11 bậc) |
| Anh Khôi | 4.77 | +4.5 ±1.3 | 0.956 | -0.065 | 1 | -20.90 | -0.49 ±0.26 | -4.10 | -4.10 … -2.70 (11 bậc) |
| Ngọc Huyền | 4.76 | +4.4 ±3.3 | 0.957 | -0.063 | 1 | -19.63 | +0.78 ±0.19 | -5.37 | -5.46 … -4.59 (12 bậc) |
| Mạnh Dũng | 4.73 | +3.8 ±0.9 | 0.963 | -0.054 | 1 | -19.07 | +1.34 ±0.14 | -5.93 | -5.93 … -4.46 (11 bậc) |
| Adam | 4.67 | +2.4 ±1.0 | 0.976 | -0.035 | 1 | -20.13 | +0.28 ±0.38 | -4.87 | -5.18 … -2.45 (10 bậc) |
| Quang Sơn | 4.64 | +1.8 ±1.6 | 0.982 | -0.026 | 1 | -20.26 | +0.15 ±0.23 | -4.74 | -4.74 … -3.02 (11 bậc) |
| Đoan Trang | 4.62 | +1.3 ±1.3 | 0.987 | -0.019 | 1 | -20.07 | +0.34 ±0.18 | -4.93 | -5.20 … -3.88 (12 bậc) |
| Phạm Tuyên | 4.56 | +0.0 ±1.2 | 1.000 | +0.000 | 1 | -20.23 | +0.18 ±0.19 | -4.77 | -4.77 … -3.40 (11 bậc) |
| Thục Đoan | 4.53 | -0.6 ±2.1 | 1.006 | +0.009 | 1 | -20.34 | +0.06 ±0.25 | -4.66 | -4.66 … -3.38 (8 bậc) |
| Ngọc Linh | 4.36 | -4.4 ±1.2 | 1.045 | +0.063 | 1 | -19.98 | +0.43 ±0.26 | -5.02 | -5.16 … -4.57 (10 bậc) |
| Thái Sơn | 4.35 | -4.8 ±3.1 | 1.049 | +0.069 | 1 | -21.97 | -1.56 ±0.27 | -3.03 | -3.03 … -1.52 (10 bậc) |
| Adam bựa | 4.33 | -5.1 ±1.3 | 1.053 | +0.074 | 1 | -18.87 | +1.54 ±0.29 | -6.13 | -6.13 … -5.25 (11 bậc) |
| Ngọc Trân | 4.17 | -8.8 ±1.6 | 1.092 | +0.127 | 1 | -20.25 | +0.15 ±0.23 | -4.75 | -4.75 … -3.24 (9 bậc) |
| Quỳnh Anh | 4.16 | -9.2 ±1.4 | 1.097 | +0.133 | 1 | -20.88 | -0.47 ±0.28 | -4.12 | -4.12 … -3.51 (10 bậc) |
| Thiền Tâm Đức | 3.75 | -19.4 ±1.3 | 1.215 | +0.281 | 1.05 | -20.72 | -0.31 ±0.32 | -4.28 | -4.36 … -2.69 (10 bậc) |
| Đức Trí | 3.61 | -23.4 ±1.6 | 1.264 | +0.338 | 1.1 | -21.79 | -1.39 ±0.22 | -3.21 | -3.21 … -1.90 (11 bậc) |
| Mỹ Duyên | 3.49 | -26.7 ±2.2 | 1.306 | +0.385 | 1 | -20.31 | +0.09 ±0.26 | -4.69 | -4.93 … -3.81 (11 bậc) |
| Kim Thanh | 3.45 | -27.9 ±1.9 | 1.322 | +0.403 | 1.1 | -20.51 | -0.10 ±0.18 | -4.49 | -4.49 … -4.03 (10 bậc) |

- **Bảng:** 223 khoá VieNeu (21 preset × thang 7 bậc + bậc theo tuổi), đúng tập `castable_keys()`.
  - r_v dùng chung cho mọi bậc của một preset: bậc formant đổi tốc độ ±0,5 %.
- **Nhịp đo thật sau r_v:** |lệch mốc| lớn nhất 2.9 %.
- **CI 95 % của o_v:** trung vị ±0.31 dB, lớn nhất ±0.73.
- **Câu trung tính chạm trần −2 dBFS khi chỉ áp gain:** 0 % ở mọi giọng.

### Kiểm chéo (hằng số từ 22 câu hiệu chỉnh, áp lên 18 câu kiểm)

| thước | SD giữa giọng trước → sau | khoảng trước → sau | trong ngưỡng |
|---|---|---|---|
| tốc độ (19 preset + 2 người kể + Supertonic/ZeroTTS) | 15.2 → 2.3 % | 63.1 → 9.0 % | 38/39 trong ±5 % |
| độ to (mọi giọng, mọi bậc) | 1.36 → 0.33 dB | 7.09 → 2.00 dB | 240/241 trong ±1 dB |

- **Trượt:** chỉ Supertonic: F5 về tốc độ (+6,0 %), M2 về độ to (−1,08 dB).
- Mọi giọng VieNeu (21 preset, mọi bậc) và ZeroTTS đều trong ngưỡng. VieNeu lệch tốc độ lớn nhất 2,9 %; lệch độ to lớn nhất 0,93 dB (Quang Sơn f087).

### Cổng nhịp

`pace_floor_scale` = **0.990**, là giá trị ở x = 1; app dùng sàn = `pace_floor_scale · x`.
Cách tính: trung vị chữ/giây (đúng công thức `pace_is_outlier`) của VieNeu bậc f100 sau r_v, chia 15,64.
15,64 là trung vị 7 preset mà dải cổng được khớp năm 18-09.

% câu trung tính bị gọi CHẬM, trung bình 21 preset:
- (a) Studio hiện tại (hệ số tay + PRESET_PACE_SCALE cũ): 2.5 %
- (b) sau r_v, PRESET_PACE_SCALE cũ: 2.4 %
- (c) sau r_v, sàn chung: 2.0 %

Giọng cao nhất ở (c): Quang Sơn 6 %, Thanh Bình 6 %, Thục Đoan 4 %.

### Ngoài bảng: Supertonic 3 và ZeroTTS (Nghe ngay / máy khác, chưa vào voice_balance.json)

| giọng | r_v | speed áp | nhịp sau r_v lệch mốc % ±CI | o_v dB | gain ở L = −25 |
|---|---|---|---|---|---|
| supertonic:F1 | 1.415 | 1.49 (tham số gốc) | -6.3 ±12.9 | -4.92 | +0.33 |
| supertonic:F2 | 1.359 | 1.43 (tham số gốc) | -6.5 ±9.1 | -5.20 | +0.60 |
| supertonic:F3 | 1.668 | 1.75 (tham số gốc) | +1.8 ±9.3 | -5.48 | +0.89 |
| supertonic:F4 | 1.264 | 1.33 (tham số gốc) | -5.1 ±7.5 | -4.47 | -0.12 |
| supertonic:F5 | 1.352 | 1.42 (tham số gốc) | -9.3 ±7.5 | -4.72 | +0.13 |
| supertonic:M1 | 1.235 | 1.30 (tham số gốc) | -17.3 ±6.3 | -5.29 | +0.70 |
| supertonic:M2 | 1.282 | 1.35 (tham số gốc) | -6.9 ±10.6 | -4.39 | -0.21 |
| supertonic:M3 | 1.230 | 1.29 (tham số gốc) | -3.7 ±6.6 | -4.28 | -0.32 |
| supertonic:M4 | 1.317 | 1.38 (tham số gốc) | -8.5 ±7.2 | -5.12 | +0.53 |
| supertonic:M5 | 1.505 | 1.58 (tham số gốc) | -2.8 ±8.7 | -4.54 | -0.05 |
| zerotts:baotrang | 1.043 | 1.043 (WORLD) | +1.0 ±2.5 | -2.88 | -1.71 |
| zerotts:giahuy | 1.093 | 1.093 (WORLD) | -1.4 ±1.8 | -1.76 | -2.83 |
| zerotts:hamy | 1.231 | 1.231 (WORLD) | -0.0 ±3.0 | -2.35 | -2.24 |
| zerotts:huuduc | 1.098 | 1.098 (WORLD) | -0.6 ±1.6 | +0.84 | -5.43 |
| zerotts:kimoanh | 1.171 | 1.171 (WORLD) | +0.4 ±2.0 | -1.48 | -3.11 |
| zerotts:maichi | 1.019 | 1.019 (WORLD) | -0.5 ±2.3 | +1.60 | -6.19 |
| zerotts:quangminh | 0.911 | 0.911 (WORLD) | +0.9 ±1.8 | +0.17 | -4.76 |
| zerotts:tiendat | 0.980 | 0.980 (WORLD) | -0.3 ±1.9 | -0.91 | -3.68 |

- **ZeroTTS:** đạt; nhịp sau r_v trong mốc.
- **Supertonic TRƯỢT tốc độ:** tham số `speed` không tỉ lệ thuận với nhịp. Sau một lần chỉnh vẫn chậm, M1 −17 %.
  - Cần chỉnh lặp (r mới = r cũ × lệch đo được) trước khi dùng.
  - M5 cần speed 1,58, F1 1,49: chạm vùng ≥1,54 từng làm câu ngắn bị nuốt.
- **Supertonic theo cổng chữ/giây của Studio:** vẫn ~46 % câu bị gọi chậm. Nó chèn lặng dài hơn ngân sách dấu câu của cổng.
  - Nghe ngay không qua cổng này; ghi ra để biết nếu sau này Studio dùng Supertonic.

Hash chất lượng nhánh dev: trước `fddc4182` (5813112a) → sau `b1333192` (db537cf5: bỏ 4 giọng Tin tức, tập phủ = phân vai ∪ người kể, thả số, chốt WORLD_MIN_SECONDS trong tts.py). pytest toàn bộ: 4511 qua, 2 bỏ qua, 0 hỏng.

#### ZeroTTS với WSOLA chuẩn hoá (04-10, cho casting nhiều máy; 5 giọng chủ sách chọn)

Cùng 40 câu trung tính, kéo bằng `tts.apply_speed_change` của main a84e30b4 (WSOLA chuẩn hoá), x = 1, L = −25; engine
`zerotts 0.1.2 c2bfbd67`. `ref_lufs` = LUFS trung bình bản thô sau r_v (gain = L − ref_lufs). Bảng cũ phía trên đo khi tốc
độ còn kéo bằng WORLD - WORLD làm ZeroTTS nhỏ đi tới 2,3 dB tuỳ giọng, nên dùng số dưới đây.

| giọng | r_v | ref_lufs | (bảng WORLD cũ) | nhịp sau r_v so với mốc (kiểm chéo 18 câu) |
|---|---|---|---|---|
| baotrang | 1,043 | −22,56 | −23,29 | −0,7 ±2,7 % |
| giahuy | 1,093 | −20,39 | −22,17 | −1,2 ±1,8 % |
| huuduc | 1,098 | −17,32 | −19,57 | −0,8 ±1,5 % |
| kimoanh | 1,171 | −22,10 | −21,89 | −1,0 ±1,9 % |
| quangminh | 0,911 | −18,70 | −20,24 | +0,8 ±1,9 % |

Số máy đọc: scratchpad phiên Model `balance/zerotts_constants.json`.

### Kiểm cảm xúc sau hằng số (emo_check)

Mẫu kiểm:
- 9 giọng: 5 VieNeu ở f100 (Đức Trí, Thanh Bình, Mạnh Dũng, Ngọc Huyền, Trúc Ly), Supertonic F1, M4, ZeroTTS baotrang, giahuy;
- 6 câu cảm xúc (giận ×2, thì thầm ×2, vui ×2) và 40 câu trung tính; 2 hạt.

Ba cách được so:
- **thô**: màu giọng + tốc độ tay cũ, chưa chỉnh mức;
- **hiện tại**: chuẩn hoá từng câu (`normalize_segment_level`);
- **mới**: r_v, rồi gain_db + offset tương đối (soft/loud, cảm xúc × cường độ), KHÔNG chuẩn hoá từng câu; trần −2 dBFS giữ làm chốt.

**Khoảng cách cảm xúc trong giọng** = câu cảm xúc trừ trung bình câu trung tính của chính giọng ấy, trung bình qua 9 giọng:

| cảm xúc | thước | thô | hiện tại | mới |
|---|---|---|---|---|
| giận | dB | +0,63 | +1,20 | +1,94 |
| giận | tốc độ % | +7,3 | +7,3 | +8,2 |
| thì thầm | dB | −0,01 | −1,83 | −2,04 |
| thì thầm | tốc độ % | +11,2 | +11,2 | +12,7 |
| vui | dB | −0,23 | 0,00 | −0,07 |

- Cách mới giữ khoảng cách cảm xúc. Độ to theo cảm xúc nay = dao động tự nhiên CỘNG offset của app; cách hiện tại thì chỉ còn offset.
- Lệch theo từng giọng (±6–9 % tốc độ) chủ yếu ở Supertonic. Supertonic được tổng hợp LẠI ở speed mới nên ra bản thu khác, không phải sai số của phép đo.

**Giữa giọng trên CÙNG câu** (SD qua 9 giọng):

| câu | thô | hiện tại | mới |
|---|---|---|---|
| trung tính, độ to dB | 2,60 | 0,00 | 0,79 |
| trung tính, tốc độ % | 18,2 | 18,2 | 11,2 |
| giận, độ to / tốc độ | 2,73 / 15,4 | 0,00 / 15,4 | 1,27 / 5,6 |
| thì thầm, độ to / tốc độ | 2,41 / 10,4 | 0,00 / 10,4 | 0,62 / 7,4 |

- Tốc độ giữa giọng gần lại rõ. Phần còn lại phần lớn do Supertonic chưa đạt tốc độ, xem trên.
- Độ to: cách hiện tại ép mọi câu về một mức (SD 0). Cách mới để lại dao động thật của câu.

**Dao động độ to câu–câu TRONG giọng** (câu trung tính, SD dB):
- thô 0,37–1,63;
- hiện tại 0;
- mới 0,57–1,84. Cách mới giữ lại dao động tự nhiên; Thanh Bình 0,66 → 1,46 do WORLD (r 0,895) cộng cao độ −4.
- Câu chạm trần −2 dBFS với cách mới: 0/92 ở VieNeu và Supertonic; 1 câu ở mỗi giọng ZeroTTS (1/92, 1/91).

### Tự nhiên sau khi kéo tốc độ (UTMOSv2, 40 câu trung tính, cùng màu giọng, cùng −25 LUFS)

| giọng | hệ số cũ → r_v | gốc (không kéo) | hiện tại | mới (WORLD r_v) | mới − hiện tại | mới − gốc |
|---|---|---|---|---|---|---|
| Kim Thanh | 1,10 → 1,322 | 2,90 | 2,45 | 2,41 | −0,05 ±0,07 | −0,50 ±0,08 |
| Mỹ Duyên | 1,00 → 1,306 | 3,12 | 3,17 | 2,10 | **−1,07 ±0,10** | −1,02 ±0,10 |
| Đức Trí | 1,10 → 1,264 | 2,90 | 2,64 | 2,64 | +0,00 ±0,06 | −0,25 ±0,08 |
| Thiền Tâm Đức | 1,05 → 1,215 | 2,48 | 2,12 | 2,16 | +0,04 ±0,06 | −0,31 ±0,08 |
| Trúc Ly | 1,00 → 0,890 | 2,63 | 2,67 | 2,05 | **−0,62 ±0,09** | −0,58 ±0,09 |
| Thanh Bình | 1,00 → 0,895 | 2,70 | 2,68 | 2,45 | −0,23 ±0,09 | −0,25 ±0,10 |

- WORLD kéo tốc độ làm GIẢM độ tự nhiên theo máy, kể cả ở hệ số tay cũ: Kim Thanh ×1,10 đã mất 0,45.
- Giọng mới bị kéo (Mỹ Duyên, Trúc Ly) mất nhiều nhất.
- VieNeu Turbo không có tham số tốc độ gốc (chỉ Nano có), nên đã thử cách co giãn khác, xem mục kế.

### Cách kéo tốc độ: WORLD → WSOLA → WSOLA tương quan chuẩn hoá (04-10, main a84e30b4, hash 598d3c84)

UTMOSv2 như trên; chênh so với "không kéo" theo cặp câu, ±CI 95 %. Mã đo: scratchpad phiên Model `balance/tempo_alt.py`,
`tempo_sweep.py`, `tempo_near.py`, `wsola_var.py`, `tempo_ncc.py`, `tempo_options.py` (bản sao trong Corpus `claude/model_lane/voice_balance`).

**Ở chính r_v của giọng (40 câu trung tính):**

| giọng | r_v | gốc | WORLD | PSOLA (Praat) | WSOLA audiotsm | WSOLA tay, tương quan thô |
|---|---|---|---|---|---|---|
| Mỹ Duyên | 1,306 | 3,14 | −1,03 ±0,10 | −0,46 ±0,08 | −0,32 ±0,08 | −0,30 ±0,07 |
| Kim Thanh | 1,322 | 2,92 | −0,48 ±0,09 | −0,39 ±0,09 | −0,14 ±0,08 | −0,19 ±0,08 |
| Trúc Ly | 0,890 | 2,65 | −0,63 ±0,09 | −0,34 ±0,09 | −0,32 ±0,08 | −0,33 ±0,08 |

**Theo r (Mỹ Duyên, Trúc Ly, Phạm Tuyên × 22 câu hiệu chỉnh, gộp):**

| r | WORLD | PSOLA | WSOLA audiotsm | WSOLA tương quan thô | **WSOLA tương quan chuẩn hoá (app)** |
|---|---|---|---|---|---|
| 0,85 | −0,71 | −0,30 | −0,34 | −0,32 | **−0,15** |
| 0,9 | −0,67 | −0,30 | −0,28 | −0,27 | **−0,10** |
| 0,95 | | | | −0,23 | **−0,04** |
| 0,975 / 1,025 | | | | −0,19 / −0,16 | |
| 1,05 | | | | −0,16 | **−0,04** |
| 1,1 | −0,63 | −0,29 | −0,19 | −0,16 | **−0,10** |
| 1,2 | −0,62 | −0,41 | −0,20 | −0,26 | **−0,22** |
| 1,3 | −0,70 | −0,49 | −0,29 | −0,27 | **−0,36** |

CI gộp ±0,05–0,07. Theo giọng ở 1,3 (bản chuẩn hoá): Mỹ Duyên −0,31, Phạm Tuyên −0,19, Trúc Ly −0,59. Trúc Ly có r_v 0,89 nên
không bao giờ bị kéo nhanh.

- **WSOLA tương quan thô có PHÍ CỐ ĐỊNH:** kéo 2,5 % mất gần bằng kéo 30 %. Lý do: tương quan thô chọn điểm nối nghiêng về
  đoạn TO thay vì đoạn khớp dạng sóng; nó cũng nâng độ to +0,4..0,6 dB.
- **Chia cho năng lượng vùng ứng viên** (tương quan chuẩn hoá) xoá phí ấy:
  - ở r 1,05 (2 giọng × 22 câu): thô −0,17, chồng khung 75 % −0,18, chuẩn hoá −0,00 ±0,05;
  - chồng 75 % + chuẩn hoá −0,04; khung 60 ms −0,05;
  - độ to lệch ≤ 0,2 dB, độ dài đúng 1/r, cao độ lệch ≤ 0,05 bán cung, RTF 0,05–0,07.
  - Ở r ≥ 1,2 bản chuẩn hoá không hơn bản thô; mất mát ở đó là của chính việc nói nhanh hơn 20–30 %.
- **WORLD** tổng hợp lại toàn bộ nên đổi độ to TUỲ GIỌNG kể cả khi r gần 1: Xuân Vĩnh ×0,913 −2,03 dB, Thái Sơn ×1,049
  −1,88 dB, Thục Đoan ×1,006 +0,06 dB. Gain trong bảng WORLD cũ vì thế bù sai cho các giọng ấy. Bảng nay đo lại với WSOLA
  chuẩn hoá.

**Trần |log r|: KHÔNG đặt** (chọn (a), Lead 04-10, theo lệnh chủ sách "tốc độ chung lấy từ trung bình"). Mất UTMOS nội suy
từ đường trên cho 21 preset:

| phương án | mất TB / giọng | mất lớn nhất | lệch tốc độ còn lại |
|---|---|---|---|
| **(a) kéo như bảng** | −0,101 | −0,36 | 0 % |
| (b) bỏ kéo khi lệch < 5 % (10 giọng) | −0,090 | −0,36 | ≤ 4,6 % |
| (c) trần ±20 % | −0,081 | −0,22 | Kim Thanh −9,2 %, Mỹ Duyên −8,1 %, Đức Trí −5,1 % |
| (c) trần ±10 % | −0,058 | −0,10 | 4 giọng chậm 9–17 % |

Mất dồn vào 4 giọng có r_v > 1,2 (Thiền Tâm Đức, Đức Trí, Mỹ Duyên, Kim Thanh): −0,2 tới −0,36. Trần thì đổi lấy đúng cái lỗi
chủ sách gọi tên ("cùng câu mà giọng nhanh / chậm khác nhau"). Dự phòng nếu chủ sách nghe thấy 4 giọng ấy méo: (c) ±20 %.

### Trục thứ ba: cao độ nền = độ hưng phấn mặc định? (CHỈ ĐO)

Cách đo:
- Model cảm xúc dạng chiều audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim. Học trên tiếng ANH (MSP-Podcast), nên có thể lẫn với thanh điệu tiếng Việt.
- 40 câu trung tính × 2 hạt; tốc độ gốc; chỉ đổi cao độ (`apply_voice_variant`).
- Arousal ×100, lệch so với trung bình cùng câu qua 19 preset ở cao độ 0; trung vị 19 preset = +0,2.

**Ở cao độ 0, xếp theo arousal:**
- Thanh Bình +17,4 (hạng 1);
- Adam bựa +10,6 (2);
- Minh Quân Pro +9,6, Trúc Ly +9,4, Quỳnh Anh +7,5;
- Mạnh Dũng +7,4 (6);
- … Thiền Tâm Đức −9,4, Xuân Vĩnh −19,7, Đức Trí −21,1 (thấp nhất).
- CI ±0,6–1,5.
- F0 không giải thích thứ hạng: Kim Thanh F0 +6,3 st, arousal +0,2; Trúc Ly F0 +8,3 st, arousal +9,4.

**Theo bán cung:**

| giọng | 0 | −2 | −4 | −6 | độ dốc / bán cung |
|---|---|---|---|---|---|
| Thanh Bình | +17,4 | +15,9 | **+12,7** | +9,8 | 1,29 (R² 0,98) |
| Adam bựa | +10,6 | **+10,4** | +7,6 | | 0,74 (R² 0,80) |
| Mạnh Dũng | +7,4 | **+5,9** | +3,0 | | 1,09 (R² 0,97) |

Hạ cao độ cũng làm valence tăng 2–4 điểm, tức "dễ chịu" hơn.

**Trả lời ba câu hỏi:**
- (1) ĐÚNG: ở cao độ 0, 3 giọng chủ sách đã hạ đứng hạng 1, 2, 6 về arousal.
- (2) SAI theo máy: mức chủ sách chọn KHÔNG đưa chúng về gần trung vị. Thanh Bình −4 còn +12,7; Adam bựa −2 còn +10,4; Mạnh Dũng −2 còn +5,9.
- (3) ĐÚNG: giảm gần thẳng, ~1,1 điểm mỗi bán cung.

**Kết luận:**
- Vì (2) sai, KHÔNG đề xuất số bán cung cho giọng khác.
- Muốn về trung vị bằng cao độ thì cần −6 tới −9 (giọng cao) và +7 tới +20 (Đức Trí, Xuân Vĩnh). Như vậy là quá xa vùng an toàn của WORLD và màu giọng.
- Bán cung của 3 giọng GIỮ NGUYÊN: Thanh Bình −4, Adam bựa −2, Mạnh Dũng −2, chủ sách đã chốt bằng tai.
- *Ghi chú, giả thuyết chưa kiểm:* theo máy, hạ cao độ chỉ làm giảm hưng phấn một phần. Còn cảm giác "bình tĩnh, truyền cảm hơn" mà tai chủ sách nghe ra có thể đến từ valence tăng (+2–4) và giọng trầm hơn, thứ model dạng chiều này không gọi là arousal.

Số và mã: Corpus/claude/model_lane/voice_balance (emo_check.*, utmos_check.*, tempo_alt.*, arousal.*).
