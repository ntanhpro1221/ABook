# Nhập nhạc của tôi

Người dùng tự nhập nhạc của riêng mình làm nhạc nền, ngoài danh mục trên mây (`MUSIC_RESEARCH.md`, `MUSIC_SELECTION_MODEL.md`).
Mã: `abook/webui/music_local.py` (kho + phân tích), nối vào `server.py`, `music_plan.py`, `sync.py`, `bookfile.py`; giao diện:
`ui/src/studio/MusicTab.tsx` (phần "Nhạc của tôi" và nhóm cùng tên trong "Đổi bài"). Giai đoạn A: máy tính + file sách + đồng
bộ. Giai đoạn B (cuối file): nhập nhạc ngay trên điện thoại, ghim vào sách nhập từ file, lưu thành file.

## Kho của máy

- Thư mục `<dữ liệu app>/music/mine/` (cạnh bộ đệm danh mục, KHÔNG nằm trong sách): `files/<sha1 nội dung>.<đuôi>` và sổ
  `library.json`. Nhập mp3, m4a, ogg, opus, flac, wav; nhập hai lần cùng nội dung (dù tên khác) chỉ giữ một bản.
- Đọc thẻ (tên bài, nghệ sĩ, album, thể loại) và độ dài bằng **tinytag** (thuần Python, MIT, ~40 KB; bản 2.3.2 chép nguyên vào gói ở `abook/vendor/tinytag` nên không phụ thuộc pyproject / uv.lock; `read_tags`):
  nhập nhạc KHÔNG cần ffmpeg và KHÔNG cần mô-đun "Phân tích nhạc" - cả sáu đuôi mp3, m4a, ogg, opus, flac, wav đều đọc được, phát nguyên file
  và đóng vào .abook nguyên file (không bao giờ chuyển mã). Chưa có mô-đun thì bài ở "chưa phân tích" và chưa có số đo độ to (`lufs` vắng:
  `cue_gain_db` dùng mức mặc định của danh mục, giao diện không báo gì đáng ngại); có mô-đun rồi thì `measure_missing()` đo bù cùng lúc
  `analyze_pending()` phân tích nốt. Thẻ Ogg / Opus nằm ở luồng âm thanh, tinytag đọc cả hai chỗ. Không có thẻ thì tên bài là tên file.
- Độ to đo bằng đúng mã của bài danh mục (`music_plan.measured_lufs`, hai kênh, ghi `<sha1>.lufs2` cạnh file), nên `gainDb` của
  mốc nhạc tính bằng cùng một công thức (`cue_gain_db`) - bài nhập to hay nhỏ đều nằm đúng `levelDb` dưới giọng.
- File không phải nhạc / đuôi lạ / không thấy / quá 1 GB: bị từ chối kèm lý do bằng tiếng Việt, các file khác trong lượt vẫn vào.

## Link `local:<sha1>`

Bài của người dùng có link `local:<sha1 của file>` (`music_plan.LOCAL_PREFIX`), nằm ở mọi chỗ nhận link danh mục: ghim
(`music_overrides.json`), `plan["tracks"]`, bài đã bỏ, mốc nhạc. Thông tin bài theo hình bài danh mục
(`source: "local"`, `title`, `creator` = nghệ sĩ, `duration`, `lufs`) nhưng KHÔNG có `license` / `attribution`: nơi ghi công chỉ
hiện tên + nghệ sĩ của chính file, không tuyên bố giấy phép.

## Phân tích - chưa bịa số

`music_local.analyze(path)` trả mục theo hình danh mục `{valence, arousal, tension, vetVar, emotions{13}, confidence,
fitsUnderNarration, loudness}` hay `None`. Bộ phân tích âm thanh chỉ-nghe (trò của `music_theory/E_signal_sources.md` §6, phiên
Nhạc huấn luyện) cắm vào bằng `music_local.set_analyzer(hàm)`; kết quả qua `clean_analysis` (kẹp miền, bỏ khoá lạ,
`fitsUnderNarration` -> `background`, `loudness` -> `lufs` / `speechBand`). Thiếu valence hay arousal, hay bộ phân tích lỗi
-> `None`: bài ở trạng thái "chưa phân tích", KHÔNG bao giờ điền số thay model. `LocalMusic.analyze_pending()` (và
`POST /api/music/local/analyze`) phân tích nốt các bài nhập từ trước khi bộ phân tích có mặt.

- **Bộ phân tích "trò"** (`abook/webui/music_student.py`, `server.py` cắm lúc dựng kho nhạc qua `register()`): chỉ nghe, không dò
  "có lời", không chặn bài nào. Một bài: ffmpeg giải mã -> ba cửa sổ 10 giây ở 20 / 50 / 80% (bài ngắn: một cửa sổ) mono 48 kHz
  -> tháp âm thanh LAION-CLAP (L2 từng cửa sổ, trung bình, L2) -> đầu trò A `student_head_A.npz` (MỘT đầu cho mọi máy từ 05-10; z-score 512
  chiều CLAP, 16 hàng: 13 cường độ = sigmoid, valence / energy / tension kẹp -1..1, rồi hiệu chỉnh - xem đoạn dưới; đường torch còn đo 42 đặc trưng âm học 22.050 Hz, `music_acoustic.py`, chỉ cho `loudness.speechBand`). `confidence` cố định 0,5,
  `fitsUnderNarration` và `family` đọc từ vector nhúng so với vector chữ đã tính sẵn (họ ngoài danh sách của app như "rock"
  -> `other`), `loudness.speechBand` = tỉ lệ năng lượng 300-3000 Hz. Bài < 3 giây hay file không giải mã được -> `None`.
- **Hiệu chỉnh cho kho trộn** (`music_student.CALIBRATION`): V/E/T của trò bị nén về giữa, nên trong kho lẫn nhạc danh mục (số của thầy)
  và nhạc nhập, bài nhập được chọn quá thường. Mỗi trục, theo từng đường chạy: `v' = kẹp(a + b*v, -1, 1)`; trò KHÔNG còn ghi `sd`
  (bài nhập dùng `TRACK_SD_DEFAULT` như bài danh mục) mà ghi `vetVar` = phương sai dư của từng trục, và
  `music_select.z_distance` cộng `VET_VAR_WEIGHT` (0,1) x `vetVar` vào tử số của trục ấy. Bài danh mục không có `vetVar` nên
  khoảng cách không đổi. Số đã đo trên phép chấm mù, xem docs/MUSIC_RESEARCH.md "F2".
- **Hai đường chạy** (`music_student.backend()`): máy có Studio (torch + transformers + librosa) chạy đường **torch** như mô tả
  trên. Bản app chỉ-nghe (Python nhúng, `shell/python/requirements.txt`: numpy + onnxruntime CPU) chạy đường **onnx**: mel numpy
  (`music_mel.py`, khớp transformers 1e-5 dB) -> tháp CLAP fp16 `clap_audio_fp16.onnx` -> đầu A `student_head_A.npz` (chỉ 512 chiều
  CLAP, không âm học) - cùng cửa sổ, cùng phép tính đầu, nên khoá đầu ra như nhau TRỪ `loudness.speechBand` (cần âm học; độ to
  đã do app đo). Lệch V/E/T so với torch cùng đầu A < 0,001. Cả hai đủ thì torch thắng; ép bằng `ABOOK_MUSIC_STUDENT_BACKEND=onnx|torch`
  (bài thử trên máy có cả hai). Thiếu thư viện của cả hai -> không bộ phân tích.
- **Gói model** ở `huggingface.co/NGDtuanh/abook-music-student`, ghim một commit (`music_student.REVISION`; còn trống thì mô-đun không
  tải model) và SHA-256 từng file (`PACKAGE_HASHES`); mỗi đường chỉ cần file của mình, đặt vào `<dữ liệu app>/music/student/`, bằng HTTPS thuần
  (`studio_setup.download`: `.part`, kiểm băm, rồi mới đổi tên; không cần huggingface_hub). torch ~55 MB: `model.safetensors` fp16,
  `config.json`, `preprocessor_config.json`, `student_head_A.npz`. onnx ~59 MB: `clap_audio_fp16.onnx`, `student_head_A.npz`,
  `preprocessor_config.json`. Chưa có gói, hay thiếu thư viện của cả hai đường -> `analyze` trả `None` và `register()` không cắm gì: bài ở
  "chưa phân tích". Gói chỉ tải khi người dùng bấm "Phân tích nhạc" (mục dưới) - không bao giờ tự tải, kể cả lúc nhập.
  `ABOOK_MUSIC_STUDENT_DIR` trỏ tới một thư mục gói có sẵn (bài thử, máy không mạng); `ABOOK_MUSIC_STUDENT_DOWNLOAD=0` chặn mọi lần tải.
- **Mô-đun "Phân tích nhạc"** (`abook/webui/music_module.py`, quản lý như Studio): một nút, một thanh tiến độ, một tổng dung lượng cho mọi thứ
  bộ phân tích cần mà bộ cài không mang. Máy tính chỉ-nghe: **ffmpeg** (~31 MB, `ffmpeg_setup.py`) + **thư viện** (numpy 2.4.6, onnxruntime 1.28.0,
  flatbuffers, packaging, protobuf: ~27 MB wheel cp314 win_amd64, ghim URL + SHA-256, giải vào `<dữ liệu app>/music/lib` rồi thêm vào `sys.path`
  trước khi import) + **model** (~59 MB); máy Studio (đã có torch + ffmpeg) chỉ tải model. Giao diện: MỘT thẻ (`MusicModuleNotice`) ở "Nhạc của
  tôi" khi đã có bài, hiện tổng dung lượng và nút "Phân tích nhạc (N MB)"; không còn thẻ "bộ đọc nhạc" riêng, không còn đợi tải lúc nhập.
  `GET /api/music/local` -> khoá `module` (`state` missing / downloading / ready / outdated / error / unsupported, `done`, `total`, `error`,
  `parts`, `outdatedParts`, `outdatedBytes`, `stale`, `analysing`, `restart`); `POST /api/music/local/module` bắt đầu tải hay cập nhật;
  `POST /api/music/local/reanalyse` phân tích lại bài cũ. Cả hai chỉ máy chủ gọi được (không mở cho Studio từ xa).
  **Bản cũ / mới**: mỗi phần có một mã ghim (ffmpeg: SHA-256 wheel; thư viện: băm các wheel; model: REVISION + SHA-256 từng file). Lúc tải ghi
  `<dữ liệu app>/music/module.json` (phần -> ghim đã tải); `status()` so với ghim của bản app này, KHÔNG băm lại 59 MB mỗi lần mở. App lên bản
  mới đổi ghim của phần nào thì phần ấy `outdated` (cùng tên file, cùng cỡ vẫn bị bắt - lỗi cũ: model cũ nằm mãi), giao diện hiện "Phân tích nhạc có
  bản mới - N MB" và một lần bấm chỉ tải phần đổi, phần còn lại giữ nguyên. Bản cũ vẫn chạy cho tới khi cập nhật xong. Thư viện đã nạp vào
  tiến trình không thay tại chỗ được: bản mới giải vào `lib.next`, đổi chỗ ở lần mở app sau (`restart`). **Cập nhật không tự phân tích lại**: mỗi
  kết quả ghi kèm `by` (mã bản model, `music_student.model_id`); `stale` đếm bài do bản cũ phân tích, người dùng bấm "Phân tích lại N bài bằng bản mới"
  mới chạy (`LocalMusic.reanalyse`). Giấy phép / nguồn: `THIRD_PARTY.md`.
- **Đường onnx - chi phí**: bộ cài KHÔNG mang gì của đường này (numpy, onnxruntime, ffmpeg, model đều trong mô-đun, tải khi bấm: ~117 MB tổng); một bài ~3 phút ~0,4 giây trên CPU 32 luồng (ffmpeg giải mã 0,2 + mel 0,03 + tháp 0,16), nạp phiên ~0,7 giây. Bản
  đóng gói không mang ffmpeg: nó nằm trong mô-đun "Phân tích nhạc" (nhập nhạc thì không cần), nên bài nhập được rồi mới phân tích được.
- **Chi phí** của đường torch (CPU máy chủ sách, 16 luồng): nạp gói ~5 giây một lần; một bài ~3 phút ~1,2 giây (lần đầu ~3,8 giây vì numba biên dịch).
  Khớp bản nghiên cứu: đầu trò + âm học trùng V/E/T tới 1e-3 khi nhận đúng vector nhúng của bản nghiên cứu; cả đường chạy của app
  lệch tối đa ~0,05 trên V/E/T vì bản nghiên cứu cắt cửa sổ bằng `ffmpeg -ss` theo độ dài ghi trong đầu file mp3.
- **Đo cảm xúc nhạc chính xác hơn** (máy tính, tuỳ chọn, mặc định TẮT; `abook/webui/music_valence.py`): thang V của trò thiếu phần MuQ mà danh
  mục có, nên người dùng có thể bật thêm một lượt đo bằng tháp MuQ-MuLan ONNX (`muq/muq_mulan_audio.onnx`, 1,27 GB, CC BY-NC 4.0, cùng gói HF) chạy
  nền sau lúc nhập: V = V hợp (CLAP + MuQ, đổi sang hạng 101 phân vị của danh mục - `muq/valence_text.npz`, `muq/vhop_scale.json`), ghi đè `valence`
  của trò và đánh dấu `valenceBy: "vhop1"`; bài V hợp không áp `CALIBRATION["valence"]` và không có `vetVar.valence`; bài chưa tới lượt giữ V của trò.
  Tải chỉ khi bật (Nhạc của tôi > thẻ mô-đun, `POST /api/music/local/precise {enabled}`, khoá `module.precise` của `GET /api/music/local`), chỉ máy từ
  ~8 GB RAM, cần mô-đun "Phân tích nhạc" đã sẵn sàng (dùng lại vector nhúng CLAP). Nền: onnxruntime CPU 2 luồng, ưu tiên luồng thấp nhất, ~5 giây một
  bài, đỉnh ~1,5 GiB RAM và chỉ trong lúc có việc; làm tiếp được và làm lại không hại (chỉ bài chưa mang `valenceBy` hiện tại mới bị đo; mở app là làm tiếp).
  Tắt giữ file đã tải. Điện thoại chưa có (chỉ đầu A + bảng hiệu chỉnh mới).

- **Chưa phân tích**: không bao giờ được máy tự chọn; vẫn ghim tay được và có trong nhóm "Nhạc của tôi" của "Đổi bài".
- **Đã phân tích**: vào ứng viên tự động như bài danh mục (`LocalMusic.near` chia ô như `MusicCatalog.near`; `music_select`
  KHÔNG đổi). Khoá thiếu được đối xử như bài danh mục thiếu khoá (không `family` / `style` thì bị phạt khi cuốn đã chọn phong
  cách; có `background` thì bị phạt "giai điệu nổi" vì `source != incompetech`).

## Đi theo sách và sang điện thoại

- **Gói sách** (`.abook`, `.abookproj`, và gói đồng bộ): bài đang ghim / đang chọn được nhúng như bài danh mục thay thế
  (`music_plan.package`), tên `music/<sha1 nội dung>.<đuôi thật>` (bài danh mục vẫn `.mp3`, `music_plan.TRACK_EXTENSIONS` /
  `TRACK_NAME` là một nguồn cho mọi regex, kể cả Kotlin). Không nén (`_STORED`). Mục `music.tracks` mang `link: "local:..."`,
  tên + nghệ sĩ, `lufs`, không giấy phép. Máy khác mở file là phát được (file `.abookproj` chép bài vào bộ đệm nhạc qua
  `copy_music`, và `_music_lookup` lấy lại tên bài từ plan của cuốn). Không đổi số phiên bản gói: đuôi mới chỉ xuất hiện khi
  người dùng nhập nhạc.
- **Phục vụ file**: bài nhập KHÔNG đi qua `/api/music/track` (đường chung, chỉ phục vụ bài có trong danh mục). Trình phát máy tính
  lấy qua đường THEO SÁCH `/api/books/<id>/music/files/<sha1>.<đuôi>` (cũng là đường file trong gói, có trong danh sách trắng
  Studio từ xa), điện thoại qua `/sync/v1/books/<id>/files/music/<sha1>.<đuôi>`; cả hai qua `music_plan.track_file_named`:
  chỉ bài thuộc `plan["tracks"]` của chính cuốn đó (hay bài thay thế của nó) và đúng đuôi file thật mới được phục vụ.
- **Máy khác / bài đã xoá**: bài không còn trong kho thì `music_track_available` False, ghim thành `pinUnavailable` (đoạn chọn bài
  khác ở lần dựng này, lựa chọn của người dùng vẫn giữ); gói xuất sau đó bỏ mốc ấy hoặc dùng bài thay thế như mọi bài không lấy
  được. Sách đã xuất giữ bản của bài.
- **Điện thoại** (xem "Giai đoạn B"): `MusicBed.kt`, `BookFileImport.kt`, `BookDocumentWriter.kt` nhận đuôi mới (cùng danh sách
  với Python); `LibraryServer.kt` trả đúng Content-Type. Hạ mức / bật tắt / im lặng đoạn dùng lại công thức `gainDb` như mọi bài.

## Giao diện (Tiếng Việt, nói điều người dùng thấy)

- Tab Nhạc nền: phần "Nhạc của tôi" - nút "Nhập nhạc của tôi…" (hộp chọn file của máy: `POST /api/dialog/files` với
  `kind: "music"`; Tauri `main.rs`, `host.py`, `desktop.py` đều có bộ lọc nhạc), tiến độ "Đang nhập 2/5…", danh sách bài (tên ·
  nghệ sĩ · độ dài · "Đã phân tích" / "Chưa phân tích - máy chưa tự chọn, bạn vẫn ghim được"), "Nghe thử", "Xoá" (hai bước), lời
  giải thích bài nhập đi đâu và không có giấy phép. Câu báo sau nhập đếm bài mới / đã có / file lỗi và lý do.
- "Đổi bài": nhóm "Nhạc của tôi" liệt kê MỌI bài (bài hợp không khí đoạn ấy đứng trước, kèm ghi chú), "Chọn" = ghim.
- Studio từ xa (điện thoại điều khiển máy tính): không có hộp chọn file nên không nhập / xoá được (giao diện nói rõ); vẫn ghim
  bài đã nhập qua "Đổi bài" và phát được. Các đường `/api/music/local*` không nằm trong danh sách trắng. Nhập nhạc vào kho của
  MÁY TÍNH từ điện thoại vẫn ngoài phạm vi: kho điện thoại và kho máy tính là hai kho riêng, mỗi máy tự nhập.

## Kiểm

`tests/test_music_local.py` (kho, thẻ, trùng nội dung, từ chối, phân tích, ứng viên tự động, ghim, nhúng sách, đồng bộ, file
dự án, hộp chọn file, danh sách trắng Studio từ xa), `ui/src/studio/musicLocal.test.ts`, `BookFileImportTest` (đuôi flac).
Giai đoạn B: `tests/test_book_edits.py` (ghim vào sách đóng gói, lưu, mở lại, nhập lại), `tests/book_edits_fixtures.py` (ca `music_pin*`,
`music_pins` của hợp đồng, file `written/*_pins.abook`), `MusicStoreTest`, `Bs1770Test`, `LocalStudioTest`, `BookDocumentWriterTest`,
`BookEditsTest`, `ui/src/studio/musicImport.test.ts`.

## Giai đoạn B - điện thoại

Điện thoại không có xưởng và không chọn nhạc tự động, nên phần này làm đúng những gì người nghe làm được trên một cuốn nhập từ file:
nhập nhạc của mình, rồi ĐỔI MỘT ĐOẠN NHẠC của sách sang bài ấy. Cùng JSON, cùng câu báo lỗi với máy tính; mọi thứ chung đã có bộ ví
dụ `tests/fixtures/book_edits/` (xem `EDITING.md`).

- **Kho riêng của điện thoại** (`MusicStore.kt`, `<filesDir>/music/mine/`): cùng hình với kho máy tính - `files/<sha1>.<đuôi>` và sổ
  `library.json`, link `local:<sha1>`, trùng nội dung thì một bản, cùng sáu đuôi, cùng câu từ chối. Nhập qua hộp chọn file của hệ
  thống (`ACTION_OPEN_DOCUMENT`, chọn nhiều file; `LibraryPlugin.pickMusic`, sự kiện tiến độ `musicImport`), chép thẳng từ
  `content://` (không giữ bản thứ hai trong bộ nhớ đệm), đọc tên bài / nghệ sĩ / album / thể loại / độ dài bằng
  `MediaMetadataRetriever` (`AndroidMusicTags`; không có thẻ thì tên bài là tên file). Danh sách / xoá / "phân tích" đi qua
  `LocalStudio.kt` (`GET /api/music/local`, `DELETE /api/music/local/<sha1>`, `POST /api/music/local/analyze`).
- **Độ to**: `AndroidLoudness` giải mã bằng `MediaCodec` rồi đo `Bs1770` - cùng phép đo BS.1770-4 hai kênh với `music_plan.stereo_lufs`
  (số mong đợi do pyloudnorm tính, `Bs1770Test`) nên `gainDb` của bài nhập trên điện thoại ra cùng con số với máy tính. Chỉ giải mã
  8 phút đầu bài (một bản mix dài cả giờ không bắt người dùng chờ); không đo được thì dùng độ to trung vị của danh mục, như mọi bài
  thiếu `lufs`.
- **Phân tích** (`MusicStudent.kt`, bản Kotlin của đường onnx trong `music_student.py`): giải mã bằng `MediaExtractor` + `MediaCodec`
  (`AndroidAudioDecoder`: PCM float, mono kiểu ffmpeg `-ac 1` - cộng L+R nhân căn 1/2 -, ghi vào file tạm trong `cacheDir`, tối đa 30
  phút đầu) -> đổi sang 48 kHz bằng sinc cửa sổ Kaiser nhiều pha (`Resampler`, chỉ cho ba cửa sổ 10 giây ở 20 / 50 / 80% bài) ->
  log-mel (`MusicMel`, chép đúng `music_mel.py`) -> tháp CLAP fp16 bằng ONNX Runtime CPU (`OrtClapTower`, mở khi cần, đóng sau 20 giây
  không dùng) -> chuẩn hoá L2 / trung bình / chuẩn hoá L2 -> đầu trò A (`StudentHead`, đọc `student_head_A.npz` bằng `Npz`; hiệu chỉnh
  `CALIBRATION["onnx"]` kèm `vetVar`). Không dò "có lời", không chặn bài nào; bài ngắn hơn 3 giây hay không giải mã được thì "chưa
  phân tích" (không bịa số). Một lượt một lúc, ở luồng nền ưu tiên thấp, và NGOÀI khoá của kho (`analyzePending` ghi sổ từng bài) nên
  danh sách vẫn mở và nhập vẫn chạy. "Gói nhạc" của điện thoại = model (~59 MB, cùng gói và cùng ghim REVISION + SHA-256 với máy tính) + thư viện ONNX Runtime của đúng ABI
  (~12 MB nén arm64 / ~11 MB armeabi-v7a). APK KHÔNG mang ONNX Runtime (7,2 MB thay vì 31 MB): phần Java chép nguyên vào
  `app/src/main/java/ai/onnxruntime` (onnxruntime-android 1.30.0, MIT; chỉ `OnnxRuntime.java` khác bản gốc - nạp `.so` bằng đường
  tuyệt đối từ `onnxruntime.native.path`, thư viện lõi trước rồi JNI), hai file `.so` do `MusicStudentSetup` tải vào
  `<filesDir>/music/student/ort/` (ABI của tiến trình: `OrtRuntime.deviceAbi`; x86 32-bit chưa hỗ trợ -> `supported=false`). KHÔNG tự tải:
  người dùng bấm "Phân tích nhạc (N MB)" ở "Nhạc của tôi" - MỘT nút, MỘT tổng dung lượng (nén), nhắc nếu đang dùng dữ liệu di động, tiến độ,
  "Thử lại" khi hỏng. Mỗi file: `.part`, tải tiếp bằng Range, kiểm cỡ + SHA-256 rồi mới đổi tên; `.so` đặt trên máy chủ dưới dạng gzip
  (`ort/<phiên bản>/<abi>/<tên>.so.gz`; máy kiểm bản nén, giải nén, kiểm tiếp file thật, đặt chỉ-đọc). Dựng file để đăng:
  `python scripts/prepare_ort_runtime.py --out <thư mục>` (tải AAR Maven Central đã ghim SHA-256, in các dòng `Part(...)` cho `OrtRuntime.kt`; không
  tự đăng gì). Nâng ONNX Runtime = đổi `VERSION` + chép lại Java của đúng bản + dựng lại file + đổi bảng ghim.
  **Bản cũ / mới**: `files/music/student/bundle.json` ghi SHA-256 từng phần đã tải; ghim của app đổi (cùng tên, cùng cỡ cũng bắt được) thì
  trạng thái `outdated` kèm `outdatedParts`/`outdatedBytes`, một lần bấm chỉ tải phần đổi. Model cũ vẫn chạy cho tới lúc cập nhật; thư viện
  (`blocking`) phải khớp phần Java trong APK nên bản cũ của nó không được nạp. Kết quả phân tích ghi `by` (mã model): cập nhật không tự phân tích
  lại, `stale` đếm bài cũ và "Phân tích lại N bài" (`POST /api/music/local/reanalyse`) chạy khi người dùng bấm.
  Tải xong thì cắm `MusicStore.analyzer` rồi `analyzePending()` cho các bài đã nhập; bài nhập sau đó được phân tích ngay lúc nhập. Lần mở
  app sau có đủ file thì cắm luôn, không gọi mạng. `GET /api/music/local` thêm khoá `module` (cùng hình với máy tính: `state`, `done`, `total`,
  `error`, `analysing`, `metered`, `supported`, `outdatedParts`, `outdatedBytes`, `stale`), `POST /api/music/local/module` bắt đầu tải.
  Chưa có gói thì `analyze` vẫn trả 409 với đúng câu của máy tính. Không có `near` / `music_select` trên điện thoại.
  Kiểm: `MusicStudentTest` / `MusicStudentSetupTest` (JVM, so với `tests/fixtures/music_student/golden.json` do
  `tests/music_student_goldens.py` sinh từ bản Python), `MusicStudentOnDeviceTest` (máy ảo Android: ONNX Runtime + MediaCodec thật, so
  với `music_student.analyze` cùng file: lệch V/E/T và 13 cảm xúc < 0,02 - gói model đẩy bằng `adb push` vào `/data/local/tmp/student`, hai `.so` của ABI máy ảo vào `.../student/ort/`; bài thử chép vào `files/` rồi nạp bằng đường tuyệt đối như bản thật),
  `tests/test_music_student_android.py` (hằng số chép cứng khớp bên Python). Lưu ý: số của trò rất nhạy với dải mel ở sàn -100 dB (nguồn
  22 kHz hay mp3 cắt dải cao), nên sai khác 1e-5 của bộ đổi tần số so với ffmpeg có thể thành vài phần trăm ở bài như vậy; bài thật có
  nền ồn thì lệch cỡ 1e-4.
- **Ghim = một sửa L trong `edits.json`** (`music.pins` + `music.tracks`, xem `EDITING.md`; điều kiện thật của ghim là đoạn nhạc người
  làm sách đã gắn - sách không nhạc thì không có đoạn nào để đổi). File bài chép từ kho vào thư mục sách ở `music/<sha1>.<đuôi>`
  (đúng chỗ bài của người làm sách), "Lưu" / "Lưu thành…" (`BookDocumentWriter`, `bookfile.repack`) mang nó đi trong file `.abook`
  phiên bản 4 - không nén, mở ở máy khác là phát được dù kho của máy ấy không có bài này. Lớp phủ đổi `track` của mốc và thêm mục
  `music.tracks` (`file`, `link`, tên, nghệ sĩ, độ to; KHÔNG giấy phép), `gainDb` tính lại bằng `cue_gain_db`. Nhập lại cùng cuốn
  không làm mất file bài đã ghim; chủ máy sản xuất mở file thì các ghim này được bỏ qua (đếm vào "bỏ qua") vì bài chỉ có trong kho
  của người nghe. Bỏ ghim / "Bỏ mọi thay đổi" xoá file bài (trừ file nằm trong danh sách của lớp sách).
- **Máy tính cũng đọc, ghi, phát** (`book_edits.py`, `bookfile.py`, `packages.py`, `server.py`): file do điện thoại lưu mở ra ở máy tính
  là phát được; trang "Sửa sách" của máy tính cũng ghim được bài trong kho của MÁY TÍNH vào sách nhập từ file (cùng giao diện).
- **Giao diện** (`ui/src/listen/EditBook.tsx` + `MyMusic.tsx`, dùng chung hai nền tảng): trong "Nhạc nền" của hộp "Sửa sách", mỗi đoạn có
  "Đổi bài" (danh sách bài của tôi, "Chọn" = ghim) và "Về bài gốc" khi đã ghim; dưới danh sách là mục "Nhạc của tôi" (nhập, xem, xoá hai
  bước). `studio/musicImport.ts` là một cửa nhập: máy tính gọi hộp chọn file của máy chủ, điện thoại đăng ký bản native
  (`android/musicImport.ts`). MusicTab của Studio dùng lại cùng hàm. Không có "Nghe thử" trong hộp này (điện thoại không có máy chủ
  để phát thử; bài ghim nghe thử bằng cách phát sách).
- **Không có xử lý "giọng hát" nào**: người dùng chọn bài thì bài ấy được dùng, không bao giờ chặn.
- **Ngoài phạm vi**: nhập nhạc vào kho của máy tính từ điện thoại (Studio từ xa giữ nguyên lời giải thích cũ); ghim bài danh mục trên
  điện thoại (không có danh mục offline, không có không khí đoạn để xếp hạng); điện thoại phục vụ file nhạc cho máy khác qua
  `LibraryServer` (hiện nó không phục vụ nhạc của bất kỳ sách nào).
