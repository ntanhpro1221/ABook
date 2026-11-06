# Phát hành một phiên bản

Chủ sách, 27-09: *"mỗi bản release ra phải viết readme, changelog các thứ"*. Một bản phát hành chưa đủ các mục dưới đây thì
chưa phải bản phát hành.

## Số phiên bản - một số cho cả hai nền tảng

App máy tính và app điện thoại phát hành CÙNG một số `major.minor.patch`, ghi ở ba chỗ:

| chỗ | trường |
|---|---|
| `_internal/pyproject.toml` | `version` |
| `_internal/ui/package.json` | `version` |
| `_internal/mobile/android/app/build.gradle` | `versionName` (= số phiên bản) và `versionCode` (tăng 1 mỗi bản) |

`pyproject.toml` nằm trong `QUALITY_IMPLEMENTATION_FILES`: đổi `version` là đổi hash chất lượng, sách đang làm dở không
tiếp tục được. Chỉ đổi khi không có sách nào cần tiếp tục (AGENTS.md).

## Tài liệu bắt buộc

1. **`docs/CHANGELOG.md`**: đổi mục `[Chưa phát hành]` thành `[x.y.z] - ngày`, viết theo góc NGƯỜI DÙNG (họ thấy gì khác), có
   mục "Lưu ý khi nâng cấp" nếu có gì phải làm tay; mở lại một mục `[Chưa phát hành]` trống ở trên.
2. **`README.md`**: soát lại phần giới thiệu tính năng, cách cài, yêu cầu máy, cách dùng điện thoại - khớp với bản này.
3. **Giấy phép**: `_internal/LICENSE` (MIT) đi kèm mọi bản; `docs/THIRD_PARTY.md` liệt kê đúng các thành phần THẬT SỰ
   được đóng gói trong bản này (thư viện, font, model) cùng giấy phép của chúng - thêm cái mới, bỏ cái không còn dùng.
4. **Ghi chú phát hành** trên GitHub Release: dán nguyên mục CHANGELOG của phiên bản, cộng dòng yêu cầu hệ thống và cách
   cài/nâng cấp.

## Kiểm tra trước khi phát hành

Từ `_internal`, chạy **`runtime/.venv/Scripts/python.exe -X utf8 scripts/release_gate.py`; lệnh phải exit 0**.
Nếu worktree dùng runtime chung, gọi đường dẫn interpreter tường minh của runtime ấy. `--list` liệt kê check/timeout;
`--only <tên>` (lặp cờ hoặc phân cách bằng dấu phẩy) dùng để chẩn đoán, tự chạy cả điều kiện trước và **không chứng nhận
phát hành**. `--inject-failure <tên>` cấy một check đỏ để kiểm cổng, không dùng cho bản phát hành.

Gate in một bảng và lưu JSON cùng log/bằng chứng ở `runtime/release_gate/<version>-<timestamp>.json`. Thiếu công cụ,
timeout, không thu được test hay thiếu summary/XML đều FAIL. Chưa hoàn tất mục MANUAL cũng exit khác 0; không coi
chạy được các check tự động là đủ quyền đăng. Người duyệt dùng `--confirm manual-ui="ghi chú bằng chứng"` (lặp cờ cho
từng hàng MANUAL đã thực sự duyệt). Hàng được ký ghi CONFIRMED, note, UTC, HEAD và SHA-256 cây nguồn trong JSON;
chưa ký vẫn MANUAL và chặn exit 0. Xác nhận chỉ áp dụng lần gọi này, không đọc lại báo cáo cũ, mất hiệu lực nếu
commit/cây nguồn đổi trong lúc chạy. Không dùng `--only` để chứng nhận phát hành. `release.py publish` nhận cùng cờ
`--confirm` và chuyển trực tiếp tới full gate trước mọi thao tác đăng, rồi kiểm cây đã kiểm khớp commit sẽ gắn tag.

Gate cài UI dependency gồm devDependencies bằng `npm ci --include=dev` vào `runtime/release_gate/dependencies/<hash>`
theo package + lock hiện tại, tái sử dụng khi đủ phiên bản khóa. Kiểm UI chạy trên bản sao nguồn mới riêng mỗi lượt;
junction node_modules dùng chung không đổi. Thiếu npm/module hoặc cài thất bại là FAIL có log, không bỏ kiểm.
Pytest có summary thật và `--durations=30`; deadline 7200 giây. Qt offscreen/phần mềm: WidthTests có deadline riêng
1800 giây, các suite khác 360 giây; mọi subprocess gate chạy BELOW_NORMAL trên Windows.

Ý nghĩa các bằng chứng (lệnh cụ thể xem `--list`):

- Python: compile, toàn bộ pytest (`-q -rf`, số passed/failed/error từ summary); UI: typecheck và Vitest (đọc dòng Tests).
  Số file DOM không được giảm so HEAD và từng file phải thực sự có trong log Vitest. Android unit test đọc XML mới,
  không tin dòng BUILD SUCCESSFUL hoặc XML còn lại từ lần trước. Qt dựng các target test, chạy offscreen, đối chiếu đủ
  suite từ `build.bat`, kiểm Totals và lỗi glyph/binding/chữ rò; không cần mở app hay thiết bị.
- Parity web/Android và web/Qt kiểm tài liệu sinh khớp nguồn cùng các luật cứng. Gallery dựng từ cây hiện tại rồi soi
  cả sáng/tối, gồm pointer `elementFromPoint` và hình học sheet; lỗi chạy và luật chặn mặc định phải sạch. Contrast kiểm
  các cặp màu. Tap audit chạy mọi kịch bản (số lượng đọc từ scenarios.json), chuột/touch thật, rồi chạy đối chứng âm:
  phải exit 1 vì lỗi pointer được cấy, không phải vì thiếu browser/server. `tests/test_tap_audit_targets.py` chặn đích mất.
  Những kiểm này bắt hộp thoại không chạm được như 0.4.134 mà pytest/vitest logic không phát hiện.
- Nguồn: ghi quality_implementation_hash và toàn bộ danh sách file khoá từ code để Lead duyệt tác động tới sách đang làm;
  CHANGELOG `[Chưa phát hành]` phải có nội dung; số phiên bản/lock/Android versionCode/nguồn version Qt khớp; giấy phép
  hiện diện; `.bat`/`.cmd` có CRLF; quét diff (cả staged, unstaged và file mới) tìm dữ liệu riêng/khoá/audio cùng từ chỉ mã
  chuyển đổi cũ. Máy quét chỉ phát hiện dấu hiệu: nguồn truyện, README, thành phần đóng gói và ảnh vẫn phải có người duyệt.
- MANUAL: kiểm Android trên thiết bị/máy ảo (`docs/UI.md`), duyệt ảnh/nội dung/giấy phép/hash/dependency; kiểm artifact
  cuối (chữ ký, packaged smoke, audio sink, cài/cập nhật/gỡ). Mapping R8 và bằng chứng đăng được kiểm tự động bằng `release.py verify` sau publish. Gate nguồn không khởi động
  GPU, Ollama, adb, điện thoại hay emulator. Các kiểm artifact trong bước đóng gói dưới đây vẫn bắt buộc.

- `python -m pytest` toàn bộ, `npm run typecheck` và `npm test` (vitest, logic thuần của giao diện) của `ui/` đều qua; kiểm tra tay trên máy ảo Android (`docs/UI.md`).
- Cổng đủ chương: `python -m pytest tests/test_one_line_never_removes_a_chapter.py -q -rf` phải qua. Detector dùng audio/SQLite thật, chủ động làm mất chương, băm, phụ đề và nhãn QA; một dòng chưa đạt không được làm mất chương đủ lời đọc hoặc giả thành đã đạt.
- Bắt buộc trước publish: dựng UI của cây phát hành (`node node_modules/vite/bin/vite.js build` trong `ui/`), rồi từ `_internal` chạy `python scripts/tap_audit/run.py`: phải PASS mọi kịch bản (21/21 từ khi gỡ dấu trang), exit 0; `tests/test_tap_audit_targets.py` chặn kịch bản trỏ tới nhãn không còn trong giao diện.
  Chạy tiếp `python scripts/tap_audit/run.py --inject-fault`: phải FAIL, exit 1 (đối chứng âm).
  Kiểm hình học player trên app thật trong gallery (Edge headless, CPU): từ root chạy
  `D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe -X utf8 _internal/scripts/tap_audit/run_sheetgeo.py`:
  phải PASS cả năm khổ nội dung §5.5 ở sáu cửa sổ 390/840/1080/1280/1440/1840×900.
  Chạy lại thêm `--inject-fault --no-build`: phải FAIL, exit 1 vì sheet đẩy nội dung 32 px.
  Pytest: cùng interpreter, `-X utf8 -m pytest -q -rf _internal/scripts/tap_audit/test_sheetgeo.py`
  (bỏ qua khi thiếu Edge). JSON giữ rect từng frame, opacity, trusted input và lỗi; xem README của tap_audit.
  Kiểm chạm chuột/touch thật để bắt lỗi hộp thoại không chạm được như 0.4.134; pytest/vitest logic không phát hiện được lỗi này.
- Không có gì bị cấm lọt vào gói: khoá ký (Android keystore, khoá updater), audio, dữ liệu cá nhân (`listening.json`,
  `devices.json`, `computers.json` - mã thiết bị máy tính khác cấp, `reviews.json`, tuỳ chọn), token, văn bản truyện (kho nghiên cứu ở repo riêng tư, clone vào `Corpus/`
  - thư mục này bị bỏ qua; một thông báo DMCA sẽ khoá cả repo công khai lẫn trang tải bản phát hành).

## Runtime dev cài tay: xác minh rồi ghi marker

Từ root checkout, dùng interpreter của chính runtime cần kiểm:

```powershell
& 'D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe' -X utf8 _internal/scripts/dev_setup_marker.py --runtime D:/Novels/ABook/_internal/runtime --dry-run
```

Bỏ `--dry-run` để ghi `runtime/.setup_complete`. Lệnh gọi trực tiếp các phép kiểm trong
`abook.runtime_contract`: dependency (phiên bản, import, nguồn Git UTMOS và khả năng truy cập CUDA),
cache perceptual (marker, revision, kích thước, SHA-256) và model giọng (revision, kích thước, SHA-256).
Chỉ yêu cầu marker setup được bỏ ở bước trước khi tạo chính marker đó; không bỏ kiểm nào khác của
`runtime_contract_errors(runtime)` khi không truyền settings. Đây là chứng nhận runtime, không kiểm
settings riêng của từng sách hay thay thế release gate/doctor đầy đủ.

Lệnh từ chối nếu interpreter không thuộc `.venv` trong `--runtime`; luôn dùng hợp đồng của checkout
chứa script, kể cả venv đang cài editable từ checkout khác. Không cài/tải dependency, không gọi Ollama,
không nạp model hoặc chạy suy luận. Kiểm CUDA là truy vấn availability (ưu tiên NVML), không chạy GPU workload.
Thiếu/sai thành phần: in `[FAIL]`, exit 1, giữ nguyên marker cũ nếu có. `--dry-run` chạy cùng phép kiểm,
in JSON dự kiến khi đạt và không ghi marker. Thành công: exit 0; marker schema lấy từ code
(hiện là 2), `installed_by=dev-check`, thời điểm UTC, đường dẫn Python/checkout và phiên bản/provenance
các dependency đã kiểm. Ghi file tạm riêng, flush/fsync rồi atomic replace. Lệnh không sửa dữ liệu sách.

## Đóng gói và đăng

Từ 01-10 cả bốn bước dưới đây là một script (`scripts/release.py`, chạy bằng `runtime/.venv`, từ worktree có commit phát
hành); mỗi bước dừng ở chỗ đầu tiên không đúng:

```
python scripts/release.py bump X.Y.Z --commit   # 7 file + commit "Release X.Y.Z"; hash chất lượng phải giữ nguyên
python scripts/release.py build X.Y.Z           # bộ cài + APK; kiểm latest.json và chứng chỉ APK
python scripts/release.py publish X.Y.Z --commit <commit phát hành>
python scripts/release.py verify X.Y.Z          # chỉ đọc; cũng nhận vX.Y.Z và --commit <sha>
```

`publish` gọi `verify` ở cuối, sau khi endpoint latest trả đúng bản. `verify` dùng `git ls-remote origin` và
`gh api --method GET`: tag (kể cả annotated tag) phải trỏ đúng commit phát hành và commit ấy nằm trên main của origin;
Release công khai, không prerelease, có đúng 6 asset với size/SHA-256 khớp `--out`; notes không rỗng và phần
"Thay đổi" khớp nguyên mục CHANGELOG tại commit phát hành. Không cần HEAD hiện tại là phiên bản đang kiểm.
Không còn hàng MANUAL `manual-publish` trong gate trước phát hành.

Endpoint và khoá công khai lấy cùng cấu hình updater; mọi endpoint phải trả latest.json khớp file phát hành,
đúng version, URL bộ cài và chữ ký `.sig`. Chữ ký minisign được xác minh trên bộ cài với trusted version.
Mapping riêng tư tại `D:/Novels/ABook/Corpus/releases/android/X.Y.Z/mapping.txt` phải có hash nội dung R8 hợp lệ
và `pg_map_id` khớp marker trong DEX của APK đã phát hành. Nếu mapping build còn ở cây hiện tại, SHA-256 của
hai file cũng phải khớp; kiểm bản lịch sử vẫn dùng bằng chứng build nhúng trong APK khi output Gradle đã mất.
Lệnh không cất/copy mapping thay người dựng và không sửa GitHub Release. Lỗi mạng, thiếu digest hoặc thiếu bằng chứng
đều làm lệnh thất bại. Vì kiểm endpoint latest hiện tại, bản đã bị bản mới thay thế sẽ thất bại ở bước này.

File phát hành nằm ở thư mục tạm của máy (`abook-release/X.Y.Z`, hay `--out`), không bao giờ trong repo. Các bước tay
tương ứng, để hiểu script làm gì:

1. Tag git `vX.Y.Z` trên commit phát hành, đẩy tag.
2. App máy tính (bản Qt, `docs/QT_INSTALLER.md`): `desktop_qt\build.bat installer` - test Qt, đóng gói, smoke bản đóng gói,
   cổng tai kiểm (`tools\audio_sink.py gate`: phát bản đóng gói hai lượt trên bàn làm việc ẩn, nghe WAV - lỗ, tách, mất giọng,
   rò, đột im (nhạc tắt phụt không do thao tác), trôi, lệch, mức - cả hai lượt xanh và mọi lỗi cấy vào lượt đầu phải đỏ; đỏ thì bằng chứng ở
   `desktop_qt\build\audiosink-evidence\`, cần cuốn thử `D:\Novels\Audiobooks\book2`), test bộ cài trong hồ sơ giả (cài, cập nhật thật N -> N+1, tham số bộ cập nhật Tauri, gỡ) - ra trong
   `desktop_qt\build\installer\`: bộ cài `ABook_X.Y.Z_x64-setup.exe`, chữ ký `.sig` (khoá ở `%USERPROFILE%\.abook-keys`,
   không bao giờ commit; kiểm lại bằng khoá công khai ngay sau khi ký) và `latest.json` (ghi chú lấy từ mục `[X.Y.Z]` của
   CHANGELOG - đổi tên mục trước khi dựng; `release.py build` kiểm latest.json mang đúng chữ ký của `.sig`). App điện thoại (Kotlin + Compose, không có bước web):
   `gradlew assembleRelease` trong `mobile\android\` - Gradle ký bằng `%USERPROFILE%\.abook-keys\android-release.properties`
   (thiếu file ấy thì APK không ký, không phát hành được). Bản release chạy R8 (thu nhỏ mã + tài nguyên, luật ở
   `mobile\android\app\proguard-rules.pro`): ngay sau khi dựng, CẤT `mobile\android\app\build\outputs\mapping\release\mapping.txt`
   vào `D:\Novels\ABook\Corpus\releases\android\X.Y.Z\mapping.txt` (Corpus là repo riêng tư; không bao giờ đưa vào repo công
   khai hay GitHub Release). Không có nó thì stack trace của người dùng (logcat, báo lỗi) không dịch ngược được về tên hàm; mỗi
   bản dựng ra một mapping khác nhau, nên mapping phải đúng với APK đã đăng. Thêm mã dùng JNI, phản chiếu hay nạp lớp theo tên
   thì thêm luật giữ vào file ấy (kèm lý do) và thử trên máy ảo trước khi phát hành. Mất khoá APK là người dùng phải gỡ app rồi cài lại: bản sao lưu
   của cả hai khoá nằm ở `keys/` trong repo riêng tư `ntanhpro1221/ABook-Private` (README ở đó chỉ cách khôi phục).
   Bộ cài chỉ-nghe KHÔNG mang từ điển phát âm và giọng nghe thử (`webui/studio_setup.py` > `STUDIO_ASSETS`: Studio tải gói
   ghim ở bước đầu tiên). Gói đổi (file trong `abook/assets/voice_previews` hay `cmudict.dict` đổi) thì: `python
   scripts/pack_studio_assets.py`, đăng gói lên nơi chứa, điền URL ghim theo commit + băm + cỡ vào `STUDIO_ASSETS`;
   `release.py build` từ chối khi URL còn `PIN_REVISION`. Script dựng cũng cắt Python nhúng (Pillow,
   thư viện chuẩn) rồi chạy `scripts/smoke_embedded_python.py` trên chính bản đã cắt - đừng bỏ qua khi nâng Python hay gói phụ.
3. `gh release create vX.Y.Z` (dùng `GH_TOKEN="$(gh auth token --user ntanhpro1221)"` cho riêng lệnh ấy) với ghi chú ở mục
   "Tài liệu bắt buộc" và đính kèm bộ cài, `.sig`, `latest.json`, APK, `LICENSE`, `THIRD_PARTY.md`. Các bản đã cài đọc
   `releases/latest/download/latest.json`: Release phải là bản "latest" (không đánh dấu pre-release) thì mới tự cập nhật.
