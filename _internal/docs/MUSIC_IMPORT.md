# Nhập nhạc của tôi

Người dùng tự nhập nhạc của riêng mình làm nhạc nền, ngoài danh mục trên mây (`MUSIC_RESEARCH.md`, `MUSIC_SELECTION_MODEL.md`).
Mã: `abook/webui/music_local.py` (kho + phân tích), nối vào `server.py`, `music_plan.py`, `sync.py`, `bookfile.py`; giao diện:
`ui/src/studio/MusicTab.tsx` (phần "Nhạc của tôi" và nhóm cùng tên trong "Đổi bài"). Giai đoạn A: máy tính + file sách + đồng
bộ. Giai đoạn B (cuối file): nhập nhạc ngay trên điện thoại, ghim vào sách nhập từ file, lưu thành file.

## Kho của máy

- Thư mục `<dữ liệu app>/music/mine/` (cạnh bộ đệm danh mục, KHÔNG nằm trong sách): `files/<sha1 nội dung>.<đuôi>` và sổ
  `library.json`. Nhập mp3, m4a, ogg, opus, flac, wav; nhập hai lần cùng nội dung (dù tên khác) chỉ giữ một bản.
- Đọc thẻ (tên bài, nghệ sĩ, album, thể loại) và độ dài bằng ffmpeg đã có sẵn trong app - không thêm thư viện nào (`THIRD_PARTY.md`
  không đổi). Thẻ Ogg / Opus nằm ở luồng âm thanh, `read_tags` đọc cả hai chỗ. Không có thẻ thì tên bài là tên file.
- Độ to đo bằng đúng mã của bài danh mục (`music_plan.measured_lufs`, hai kênh, ghi `<sha1>.lufs2` cạnh file), nên `gainDb` của
  mốc nhạc tính bằng cùng một công thức (`cue_gain_db`) - bài nhập to hay nhỏ đều nằm đúng `levelDb` dưới giọng.
- File không phải nhạc / đuôi lạ / không thấy / quá 1 GB: bị từ chối kèm lý do bằng tiếng Việt, các file khác trong lượt vẫn vào.

## Link `local:<sha1>`

Bài của người dùng có link `local:<sha1 của file>` (`music_plan.LOCAL_PREFIX`), nằm ở mọi chỗ nhận link danh mục: ghim
(`music_overrides.json`), `plan["tracks"]`, bài đã bỏ, mốc nhạc. Thông tin bài theo hình bài danh mục
(`source: "local"`, `title`, `creator` = nghệ sĩ, `duration`, `lufs`) nhưng KHÔNG có `license` / `attribution`: nơi ghi công chỉ
hiện tên + nghệ sĩ của chính file, không tuyên bố giấy phép.

## Phân tích - chưa bịa số

`music_local.analyze(path)` trả mục theo hình danh mục `{valence, arousal, tension, sd, emotions{13}, confidence,
fitsUnderNarration, loudness}` hay `None`. Bộ phân tích âm thanh chỉ-nghe (trò của `music_theory/E_signal_sources.md` §6, phiên
Nhạc huấn luyện) cắm vào bằng `music_local.set_analyzer(hàm)`; kết quả qua `clean_analysis` (kẹp miền, bỏ khoá lạ,
`fitsUnderNarration` -> `background`, `loudness` -> `lufs` / `speechBand`). Thiếu valence hay arousal, hay bộ phân tích lỗi
-> `None`: bài ở trạng thái "chưa phân tích", KHÔNG bao giờ điền số thay model. `LocalMusic.analyze_pending()` (và
`POST /api/music/local/analyze`) phân tích nốt các bài nhập từ trước khi bộ phân tích có mặt.

- **Bộ phân tích "trò"** (`abook/webui/music_student.py`, `server.py` cắm lúc dựng kho nhạc qua `register()`): chỉ nghe, không dò
  "có lời", không chặn bài nào. Một bài: ffmpeg giải mã -> ba cửa sổ 10 giây ở 20 / 50 / 80% (bài ngắn: một cửa sổ) mono 48 kHz
  -> tháp âm thanh LAION-CLAP (L2 từng cửa sổ, trung bình, L2) -> cùng 42 đặc trưng âm học 22.050 Hz của bản nghiên cứu
  (`music_acoustic.py`, bản chép đúng số của `acoustic_features2.py`) -> đầu trò `student_head.npz` (z-score, 16 hàng: 13 cường
  độ = sigmoid, valence / energy / tension kẹp -1..1). `sd` = RMSE giữ ngoài của từng trục, `confidence` cố định 0,5,
  `fitsUnderNarration` và `family` đọc từ vector nhúng so với vector chữ đã tính sẵn (họ ngoài danh sách của app như "rock"
  -> `other`), `loudness.speechBand` = tỉ lệ năng lượng 300-3000 Hz. Bài < 3 giây hay file không giải mã được -> `None`.
- **Gói model** (~55 MB: `model.safetensors` fp16, `config.json`, `preprocessor_config.json`, `student_head.npz`) ở
  `huggingface.co/NGDtuanh/abook-music-student`, ghim một commit (`music_student.REVISION`; còn trống thì app không tải gì), tải
  một lần vào `<dữ liệu app>/music/student/` khi bài đầu tiên cần phân tích. Chưa có gói, không mạng, hay thiếu torch / transformers
  / librosa (app đóng gói chỉ có phần nghe) -> `analyze` trả `None` và `register()` không cắm gì: bài ở "chưa phân tích", giao diện
  nói chưa có bộ phân tích. `ABOOK_MUSIC_STUDENT_DIR` trỏ tới một thư mục gói có sẵn (bài thử, máy không mạng).
- **Chi phí** (CPU máy chủ sách, 16 luồng): nạp gói ~5 giây một lần; một bài ~3 phút ~1,2 giây (lần đầu ~3,8 giây vì numba biên dịch).
  Khớp bản nghiên cứu: đầu trò + âm học trùng V/E/T tới 1e-3 khi nhận đúng vector nhúng của bản nghiên cứu; cả đường chạy của app
  lệch tối đa ~0,05 trên V/E/T vì bản nghiên cứu cắt cửa sổ bằng `ffmpeg -ss` theo độ dài ghi trong đầu file mp3.

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
- **Phân tích**: móc `MusicStore.analyzer` + `cleanAnalysis` (bản Kotlin của `music_local.clean_analysis`) chưa cắm bộ phân tích nào
  nên mọi bài là "Chưa phân tích": không bịa số, và điện thoại không có chọn nhạc tự động để mà chọn nó. `analyze` trả 409 với đúng
  câu của máy tính. Không có `near` / `music_select` trên điện thoại.
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
