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
