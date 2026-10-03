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

- **Tốc độ.** `tempo` áp bằng WORLD (`tts.apply_speed_change`), khoảng cho phép
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

cao độ → tempo → gain. `o_v` phải đo SAU khi áp `r_v`, vì WORLD kéo tốc độ làm đổi độ to. Trong `tts.py`
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
  - WORLD kéo tốc độ làm đổi độ to, không đều giữa giọng: Thanh Bình ở tempo 0,76 lệch −3,7 dB so với dự kiến.
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

Hash chất lượng nhánh dev: trước `fddc4182` (5813112a) → sau khi bỏ 4 giọng Tin tức, đổi tập phủ và thả số: xem commit.
