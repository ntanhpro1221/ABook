Các clip WAV, FLAC, M4A, Ogg và Opus là hai giây đầu giải mã từ `stereo_44k.mp3` có sẵn tại đây: nhạc tổng hợp của bộ thử, không lấy từ sách hay danh mục nhạc.

Tạo cục bộ bằng FFmpeg, đầu vào `stereo_44k.mp3`, chung các cờ `-t 2 -map_metadata -1`:

- `stereo_44k.wav`: `-c:a pcm_u8 -ar 44100 -ac 2`.
- `stereo_44k.flac`: `-af aformat=sample_fmts=u8 -c:a flac -sample_fmt s16 -compression_level 12 -ar 44100 -ac 2`.
- `stereo_44k.m4a`: `-c:a aac -b:a 128k -ar 44100 -ac 2`.
- `mono_22k.wav`: `-c:a pcm_s16le -ar 22050 -ac 1`.
- `stereo_44k.ogg`: `-c:a libvorbis -q:a 4 -ar 44100 -ac 2`.
- `stereo_48k.opus`: `-c:a libopus -b:a 96k -ar 48000 -ac 2`.

WAV stereo và FLAC lượng tử hoá 8 bit để clip hai giây vẫn dưới 200 KB; MixTests kiểm mức RMS so với MP3 gốc trong 1 dB. AAC có dung sai riêng cho tổn hao codec. Ogg/Opus kiểm cả nhánh báo lỗi rõ ràng khi Windows thiếu bộ giải mã.
