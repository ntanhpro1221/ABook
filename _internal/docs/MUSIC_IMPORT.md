# Nhập nhạc của tôi

Người dùng tự nhập nhạc của riêng mình làm nhạc nền, ngoài danh mục trên mây (`MUSIC_RESEARCH.md`, `MUSIC_SELECTION_MODEL.md`).
Mã: `abook/webui/music_local.py` (kho + phân tích), nối vào `server.py`, `music_plan.py`, `sync.py`, `bookfile.py`; giao diện:
`ui/src/studio/MusicTab.tsx` (phần "Nhạc của tôi" và nhóm cùng tên trong "Đổi bài"). Giai đoạn A: máy tính + file sách + đồng
bộ. Nhập nhạc ngay trên điện thoại là giai đoạn B; điện thoại đã PHÁT được bài nhập khi nó nằm trong sách hay đến qua đồng bộ.

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
- **Điện thoại**: `MusicBed.kt`, `BookFileImport.kt`, `BookDocumentWriter.kt` nhận đuôi mới (cùng danh sách với Python);
  `LibraryServer.kt` trả đúng Content-Type. Hạ mức / bật tắt / im lặng đoạn dùng lại công thức `gainDb` như mọi bài.

## Giao diện (Tiếng Việt, nói điều người dùng thấy)

- Tab Nhạc nền: phần "Nhạc của tôi" - nút "Nhập nhạc của tôi…" (hộp chọn file của máy: `POST /api/dialog/files` với
  `kind: "music"`; Tauri `main.rs`, `host.py`, `desktop.py` đều có bộ lọc nhạc), tiến độ "Đang nhập 2/5…", danh sách bài (tên ·
  nghệ sĩ · độ dài · "Đã phân tích" / "Chưa phân tích - máy chưa tự chọn, bạn vẫn ghim được"), "Nghe thử", "Xoá" (hai bước), lời
  giải thích bài nhập đi đâu và không có giấy phép. Câu báo sau nhập đếm bài mới / đã có / file lỗi và lý do.
- "Đổi bài": nhóm "Nhạc của tôi" liệt kê MỌI bài (bài hợp không khí đoạn ấy đứng trước, kèm ghi chú), "Chọn" = ghim.
- Studio từ xa (điện thoại điều khiển máy tính): không có hộp chọn file nên không nhập / xoá được (giao diện nói rõ); vẫn ghim
  bài đã nhập qua "Đổi bài" và phát được. Các đường `/api/music/local*` không nằm trong danh sách trắng.

## Kiểm

`tests/test_music_local.py` (kho, thẻ, trùng nội dung, từ chối, phân tích, ứng viên tự động, ghim, nhúng sách, đồng bộ, file
dự án, hộp chọn file, danh sách trắng Studio từ xa), `ui/src/studio/musicLocal.test.ts`, `BookFileImportTest` (đuôi flac).
