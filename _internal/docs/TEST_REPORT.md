# Test report

Ngày cập nhật: 2026-10-24

Đợt fix137, cây `ABook_rel135`, nền `fe359786` (0.4.136): sửa snapshot MotionRegion lệch trong hộp/bảng có translate/transform. Ảnh cũ dùng toạ độ containing block thực, bù border/scale/scroll, cắt theo khung cuộn và cập nhật clip sau commit; giữ font tiêu đề, fade, inert và lớp xếp chồng. Khử ảnh cha/con sau xác nhận nội dung đổi để không mất fade của vùng con.

- Vitest toàn bộ: **1877 passed, 0 failed, 1 skipped**, **254 file** (253 passed, 1 skipped), tối đa 2 worker; đủ **15/15 file `*.dom.test.tsx`, 100 test DOM xanh**. Skip duy nhất là corpus PDF cục bộ tuỳ chọn. `tsc -p tsconfig.json`: **0 lỗi**. Test mới: 6 ca đỏ trên mã cũ → 10/10 xanh sau bổ sung ca nested/clip/font.
- Edge headless/CDP, CPU tối đa 4 lõi, GPU tắt: fixture dùng MotionRegion thật, **18/18 ca đạt**. Trước sửa hộp lệch `(30.5, 283.5)` px, bảng trượt `(30.5, 409)` px; sau sửa `(0, 0)` px. Ca scale 0.8 có sai số vị trí/kích thước tối đa **0.012543 px**. Đã kiểm cuộn giữa fade và khung co khi commit; không kiểm lại APK/Android. Đã đóng tiến trình Edge riêng và xoá profile tạm.
- Hash trước/sau giữ **c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886**. Không Git ghi, không cài/cập nhật dependency; thay đổi `capacitor.settings.gradle` có sẵn được giữ nguyên. Bằng chứng, lệnh, file:dòng và git status ở scratchpad `fix137/result.md`.

Đợt fix136b, cây `ABook_rel135` trên `dev/rel135`: sửa M1/M2/M4/L2/L3 của rà r136. Header Dialog/Sheet chuyển động cục bộ và giữ ARIA; Back đóng tooltip trực tiếp, không phát Esc xuống hộp. Setter không VT thắng cả yêu cầu VT cùng giá trị đang chờ; chỗ tự cuộn được lưu trước lượt phục hồi muộn; hint sửa câu nêu rõ việc làm được.

- Vitest toàn bộ: **1859 passed, 0 failed, 1 skipped**, **253 file** (252 passed, 1 skipped), tối đa 2 worker. Đủ **14/14 file `*.dom.test.tsx`, 82 test DOM xanh**; skip duy nhất là corpus PDF cục bộ tuỳ chọn. `tsc -p tsconfig.json`: **0 lỗi**.
- Có log đỏ → xanh từng mục trong scratchpad `fix136b`; hash trước/sau giữ `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`. Không Git ghi, không cài/cập nhật dependency, không dùng GPU. Kiểm DOM với happy-dom, chưa nghiệm thu chuột/chạm trên trình duyệt hay điện thoại thật. Chi tiết file:dòng và lệnh kiểm: `fix136b/result.md`.

Đợt fix136, cây `ABook_rel135` trên `dev/rel135`: sửa bốn mục emu135. Reset Thêm sách và đóng Đổi bài dùng chuyển động cục bộ, không mở View Transition toàn trang; hook bỏ cập nhật bằng nhau và bảo vệ callback đến muộn. Hiệu năng chỉ tóm tắt lựa chọn, Bộ nhớ/hint ngắn hơn. Chẩn đoán khởi tạo dữ liệu chia sẻ trước đọc, phân biệt lỗi thu thập/lỗi phát, chi tiết kỹ thuật nằm sau phần mở rộng.

- Vitest toàn bộ: **1842 passed, 0 failed, 1 skipped**, **250 file** (249 passed, 1 skipped), gồm `*.dom.test.tsx`, tối đa 2 worker; skip corpus PDF tuỳ chọn có sẵn. `tsc -p tsconfig.json`: **0 lỗi**. Pytest 4 file diagnostics/voice_speed, CUDA tắt, `-p no:cacheprovider -rf`: **75 passed**.
- Fixture `diagnostics_states.json` dùng chung TypeScript/Python/Kotlin. JUnit mới: `DiagnosticsShareTest` (3 ca) và ca hợp đồng trong `DiagnosticsTest`; **chưa chạy Gradle**, Lead chạy. Chưa kiểm lại máy ảo/thiết bị thật. Hash trước/sau giữ `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`; không sửa file khoá, không Git ghi, không npm install/update. Chi tiết đỏ → xanh, file:dòng và lệnh kiểm nằm ở scratchpad `fix136/result.md`.

Đợt hot135 trên `dev/hot135`, nền `bcdc4ff7` (0.4.134): kiểm máy ảo Android (AVD riêng, emulator-5580) thấy chạm nút trong hộp Thêm sách làm hộp đóng; Chromium máy tính cho cùng kết quả (`elementFromPoint` ở nút trả `HTML`, hộp `pointer-events: none`). Nguyên nhân: Radix đặt `pointer-events: auto` cho hộp/nền rồi trải `style` của ta đè, khoá `pointerEvents: undefined` xoá mất `auto`. Test DOM mới (Dialog + Sheet đang mở giữ `auto`) đỏ trên mã cũ, xanh sau sửa. Vitest toàn bộ **1787 passed, 0 failed, 1 skipped**; `tsc` 0 lỗi. Hash khoá giữ `c9176123`.

Đợt ux131, cây `ABook_ux131`, nhánh `dev/ux131`, nền `2805d419`: bổ sung chuyển động cho nhãn nút, trạng thái, số đếm, huy hiệu bìa, nghe thử, hàng nhập sách và sidebar; gấp nhóm thư viện/chương/nhân vật, các bước Studio và phần chi tiết tạo sách. Rút chữ giao diện, đồng nhất lỗi PDF giữa TypeScript/Python/Kotlin qua fixture. Có **29 test Vitest mới**, gồm **26 test DOM component thật** và 3 test chữ/hợp đồng.

- Vitest toàn bộ: **1814 passed, 0 failed, 1 skipped**, 247 file; tối đa 2 worker. Skip sẵn có là corpus PDF cục bộ tuỳ chọn. `tsc -p tsconfig.json`: **0 lỗi**.
- Pytest chỉ 7 file nhập sách liên quan, `-p no:cacheprovider -rf`, CUDA tắt: **296 passed**, 0 failed; một cảnh báo zip trùng mục từ fixture. Thêm 2 test Python kiểm lời lỗi PDF qua fixture chung.
- `npm run build` và `npm run build:android`: exit 0. Tổng JS/mjs so với build nền cùng cấu hình: web 1.524.016 → 1.524.350 byte (+334); Android 2.944.290 → 2.943.735 byte (-555). Hash trước/sau: `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`.
- Junction hiện thiếu happy-dom; loader riêng trong scratch dùng bản 21.0.4 đã có ở `ABook_a119`, không cài gói hay sửa junction. Chưa đo chiều cao/FPS ở browser 375×812, WebView/TalkBack hoặc thiết bị thật. Kotlin chỉ sửa chuỗi production và kỳ vọng chuỗi trong `BookImportTest`; Lead cần chạy JVM `BookImportTest`, không chạy Gradle ở lượt này. Chi tiết, lệnh tái chạy, bảng file:dòng, chuỗi trước/sau và logs: scratchpad `ux131/result.md`.

Đợt fix134 trên `dev/fix134`, nền `2805d419`: sửa nhánh chờ điện thoại ngủ có nhiều địa chỉ; che hostname `host/IP` và URL không cổng; nhận bản FFmpeg cần cập nhật qua stamp riêng; chuẩn hoá dữ liệu peer hỏng ở biên đọc và giữ bản lỗi; tách nhận UDP Android khỏi xác minh TLS (tối đa 2 I/O, 16 việc chờ). Fixture nhật ký/địa chỉ sai dạng dùng chung Python và Kotlin. CHANGELOG ghi trần 8 địa chỉ; THIRD_PARTY bổ sung Tink Android 1.24.0. Giữ hash khoá `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`.

- Test tái hiện từng mục đỏ → xanh: V1 2 FAILED → 184 passed/1 xfailed; V2 6 FAILED → 104 passed; V5 4 FAILED và 1 UI failed → 78 Python/33 UI passed; V3 15 FAILED → 209 passed/1 xfailed; V4 1 JUnit failure → 28 tests/0 failures và 83 Python passed; T1/T2 2 FAILED → 5 passed. Rà thêm cache wake và stamp UTF-8 hỏng: mỗi ca 1 FAILED → xanh.
- Mục 7: bốn test Bluetooth hồi quy được giữ nguyên, sửa `Computers.note` cập nhật danh sách địa chỉ khi đổi host/cổng rõ ràng. Các test chữ cũ được đối chiếu ý nghĩa trước khi đổi kỳ vọng; khôi phục ý không hoàn tác/rút được và hướng dẫn thử lại khi không lưu được. Danh sách lỗi toàn phần cũ: 18 FAILED/1 passed ở lần tái hiện → 19 passed/0 FAILED. Test Vitest cũ là timeout khi import (không phải lệch chữ), chạy riêng 5/5 đạt, không sửa test ấy.
- Kiểm toàn phần cuối: pytest 9518 passed, 9 skipped, 2 xfail, 0 FAILED/errors (9529 ca XML); Vitest 1785 passed, 1 skipped, 0 failed; `tsc --noEmit` và compileall abook/tests/scripts exit 0. Gradle `:app:testDebugUnitTest` offline theo khoá chung: 1739 tests, 0 failures/errors, 7 skipped; khoá đã dời vào `_dup` sau chạy. Hash vẫn `c9176123…`. Bảng phân loại từng test và log nằm trong scratchpad `fix134/result.md`.
- Không GPU, không Git ghi, không npm install/update. Lượt Vitest đầu đã ghi cache qua junction `node_modules` sang cây dùng chung; đã báo chủ sách và chạy lại toàn bộ với `--no-cache --configLoader=runner`, xác nhận thời gian sửa cache không đổi. Gói test thiếu được đọc từ cache theo SHA-512 của lock vào overlay chỉ ở scratchpad. Chưa thử thiết bị thật, chuyển Wi-Fi/Tailscale/Bluetooth, điện thoại ngủ trên phần cứng thật hay tải FFmpeg từ mạng thật.

Đợt m134 ngày 24-10, cây `ABook_rel134`, nhánh `dev/rel134` trên nền `27ab6434` (0.4.133): gộp lần lượt `dev/sec135`, `dev/copy131`, `dev/multiaddr129`, mỗi nhánh một merge commit. Giữ logic Lamport của 0.4.133 và chữ ngắn Python/Kotlin qua fixture chung; giữ che địa chỉ mới cùng basename/số dòng stack trace. Pytest sau từng nhánh: 360/363/483 đạt, 0 FAILED; lượt mở rộng copy131 có 68 file (1375 ca), hai kỳ vọng chữ cũ đã sửa và chạy lại trong nhóm 363 ca. Gradle `:app:testDebugUnitTest` offline theo khoá chung: 1732 tests, 0 failures/errors, 7 skipped; Vitest toàn bộ: 1674 passed, 1 skipped, 0 failed; `tsc --noEmit` và compileall abook/tests/scripts exit 0. Hash khoá giữ `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`. GPU tắt, giới hạn worker/CPU 4. Chi tiết xung đột, sửa test và log ở scratchpad `m134/result.md`.

- 24-10 dev/multiaddr129 (a117h): sửa AppLog/diagnostics che nhầm dấu giờ ISO thành hostname:port (kể cả múi giờ âm). Giữ nguyên test định dạng; thêm 6 ca fixture chung giữ giờ/mức/tag/pid/luồng và vẫn che địa chỉ. Gradle testDebugUnitTest: 1712 test, 1705 passed / 7 skipped / 0 failures/errors; pytest tests -k "diagnostics or peer or route": 190 passed / 0 skipped / 0 FAILED; compileall abook/tests/scripts đạt; hash khoá giữ c9176123. CPU, tối đa 4; Gradle chạy theo khoá chung và đã trả khoá.

Đợt a117g2 (rà soát a117r2, giữ nền a117/a117f): sửa F1–F6 trên Python/Kotlin. Gộp endpoint IPv6/mapped theo IP chuẩn, giữ lần thành công cao nhất; waiter Python nối qua slot/deadline; TCP nền bỏ job dư, không DNS và cho thử TLS lại khi kết quả cũ hết hạn; che hostname/exception DNS/tail; đóng socket khi ghi lịch sử lỗi; DNS/TCP/TLS chung deadline 1,5 giây. Discovery đồng nhất port nguyên, scope broadcast và host+cổng. Giữ ngoại lệ chờ máy ngủ có deadline riêng.

- Python cuối: **372 passed, 0 FAILED**, 24 file liên quan + 53 hàm test có peer/route/remote/diagnostics/sync trong tên ở file khác; interpreter production, GPU tắt, affinity 4 CPU, OMP/BLAS 1, `pytest -p no:cacheprovider -rf`. File hồi quy mới có **33 ca**; fixture alias/log/port dùng chung với JUnit. Test mã sách cũ thêm revision vào fixture theo giao thức hiện hành (đã xác nhận HTTP 400 cũng xảy ra với TLS trước sửa).
- Probe a117r2 gốc trước sửa: 26 pass/8 FAILED; sau sửa: **32 pass/2 FAILED**. Hai assertion còn lại: port float/bool từng được chấp nhận (nay bị loại đúng hợp đồng Kotlin); fake F6 thay toàn bộ `connect()` nên không đi qua mã trừ timeout mới. Giữ nguyên probe gốc; bản đối chiếu có ghi rõ hai điều chỉnh đạt **34 pass/0 FAILED**, F6 chạy connector thật với DNS/TCP/TLS giả. Bằng chứng/giải thích trong scratchpad `a117g2/result.md`, `probe-adaptation.md`, các XML/log.
- Thêm **10 JUnit** trong `PeerAddressesTest`, `TlsRouteResolverTest`, `RouteTest`, `AppLogTest`, `DiagnosticsTest`, `PeerProbeTest`; **chưa biên dịch/chạy**, Lead biên dịch Kotlin sau. Không Gradle/app/GPU. Không sửa UI nên không chạy Vitest trong lượt này.
- Hash trước/sau **c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886**, mọi file khóa/pyproject/uv.lock giữ nguyên; không Git ghi. Giữ xuống dòng gốc, kể cả LF xen CRLF. DNS OS không hủy được vẫn giữ slot riêng tới khi trả; HTTP Android pin lại ở kết nối riêng, không dùng socket probe.


Đợt sửa rà soát a117f (giữ toàn bộ a117 chưa commit): xử lý đủ 6 phát hiện của a117r trên Python và Android. Fixture mapped IPv6 dùng chung; giữ địa chỉ/cổng mới khi đủ 8; discover kiểm cổng trước probe và cô lập lỗi; log nhiều dòng/cắt cụt được che trước tách stack. TLS resolver gộp lượt theo identity, cache lỗi 2 giây, giới hạn 2 tác vụ I/O/peer và 32 peer, tránh hàng chờ DNS chung; ưu tiên TCP đã thông nhưng vẫn kiểm TLS. Đường ưu tiên đi trước 150 ms, ngân sách tối đa 6,15 giây cho 8 ứng viên; ứng viên chưa tới lượt được luân phiên sau timeout.

- Kiểm lại từng file Python, interpreter production, affinity 2 CPU, GPU tắt, `pytest -p no:cacheprovider -rf`: **159 passed trong 14 file** như danh sách a117 dưới đây, riêng `test_peer_addresses.py` tăng lên **19**, `test_diagnostics_privacy.py` lên **27**. Có test 7 lỗi chậm 1,2 giây + địa chỉ thứ 8 sống, 3 caller chung peer, peer khoẻ khi DNS peer khác kẹt, cache/invalidation và giới hạn hàng chờ.
- Vitest offline từng file, 2 worker, affinity 2 CPU: **20 passed** (`connectionRoute` 12, `computerRoutes` 5, `DevicesScreen` 3). `tsc --noEmit`: **exit 0**.
- Thêm 11 JUnit trong `PeerAddressesTest`, `TlsRouteResolverTest`, `AppLogTest`; **chưa chạy/biên dịch các sửa Kotlin mới**, không Gradle theo yêu cầu. `a117g/gradle.log` của Lead trước lượt sửa này đã compile Kotlin, 1691 tests, chỉ lỗi `A113SecurityTest:36` (Lead đã sửa; giữ nguyên). Không có lỗi compiler Kotlin trong log đó. Chưa thử thiết bị thật/đổi Wi-Fi–Tailscale–Bluetooth. DNS không chịu ngắt vẫn giữ slot của peer tương ứng tới khi hệ điều hành trả về; không chặn peer khác.
- Tiến độ, log từng file và bảng phát hiện ở scratchpad `a117f/PROGRESS.md`, `a117f/REPORT.md`; không thao tác Git ghi, không mạng ngoài/GPU/emulator/adb.

Đợt a117 (`dev/multiaddr129`, nền `0b004ca4`, chưa commit): máy đã ghép nhớ tối đa 8 địa chỉ với lần TLS thành công gần nhất; nâng dữ liệu cũ một lần; học địa chỉ từ pair/library/state và discovery sau kiểm pin; chọn đường trước HTTP, giữ Bluetooth dự phòng. Nhãn đường nối dùng chung hai giao diện, danh sách địa chỉ được che trong chẩn đoán.

- Python, chạy từng file bằng interpreter production, `pytest -p no:cacheprovider -rf`, CPU tối đa 2 luồng, `CUDA_VISIBLE_DEVICES=-1`: **150 passed** trong 14 file. `test_peer_addresses.py` 11; `test_computers_file.py` 4; `test_remote_computers.py` 8; `test_bluetooth_desktop_client.py` 24; `test_pairing_tells_the_routes.py` 2; `test_diagnostics_privacy.py` 26; `test_phone_diagnostics.py` 12; `test_remote_download_and_edits.py` 24; `test_remote_waking.py` 5; `test_remote_connection_errors.py` 3; `test_peer_get_retry.py` 9; `test_sync_tls_pinning.py` 11; `test_unpair_both_sides.py` 3; `test_peer_connections.py` 8. Có TLS thật qua loopback IPv4/IPv6, server sai chứng chỉ không nhận token, deadline bao DNS và đóng socket tới muộn.
- Vitest, npm offline, từng file, `--maxWorkers=2 --no-file-parallelism`: **20 passed** (`connectionRoute.test.ts` 12, `computerRoutes.test.ts` 5, `DevicesScreen.test.tsx` 3). `npx tsc --noEmit` chạy đúng một lần: **exit 0**.
- Kotlin: viết `PeerAddressesTest.kt` (migration, pin sai, trần, bộ lọc địa chỉ, đổi đường, phạm vi pin Media3, che nhật ký), cập nhật `RouteTest.kt`; đã đọc rà call sites, **chưa biên dịch/chạy JUnit**. Không chạy Gradle, app, emulator, adb, GPU hay mạng ngoài; chưa thử chuyển Wi-Fi/Tailscale/Bluetooth trên thiết bị thật.
- Hash file khoá trước/sau: `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`, không đổi. `git diff --check` sạch; tiến độ từng bước ở scratchpad `a117/PROGRESS.md`.

Đợt a121g trên `ABook_a121`, nhánh `dev/copy131`: đồng bộ chữ Python/Kotlin/fixture, sửa 16 lỗi JUnit chữ cũ và 6 CAO + 19 VỪA của rà a121r. Pytest 170 file: 4571 passed, 5 skipped, 0 failed; Gradle testDebugUnitTest: 1684 tests, 0 failures, 0 errors, 7 skipped. Bốn lỗi fixture đồng bộ có sẵn được bổ sung revision theo hợp đồng hiện hành. Hash khoá `c9176123` giữ nguyên; CPU tối đa 4, không GPU.

Đợt `0.4.134` trên `ABook_rel134` (27ab6434 = 0.4.133 + `dev/sec135` + `dev/copy131` + `dev/multiaddr129` + `dev/androidx135` + `dev/rust135` + `dev/ux130` + `dev/fix134`): vá bảo mật (Pillow, certifi, uv, FFmpeg 8.1.2 tải bằng Range, MinGit, rustls, AndroidX, Tink, Tauri 2.12.5), chữ ngắn hai nền, máy đã ghép nhớ tối đa 8 địa chỉ, giao diện một ngăn xếp Back + chuyển động mọi lớp + Cài đặt chia nhóm; sửa theo rà phát hành r134 (chờ điện thoại thức qua nhiều địa chỉ, Bluetooth dự phòng, che tên máy trong nhật ký, dữ liệu địa chỉ hỏng, báo cập nhật FFmpeg). Bộ đầy đủ t134 trên 2805d419 bắt 19 pytest + 1 vitest hỏng -> sửa ở fix134; bộ đầy đủ trên 256c5b10: pytest 9529 passed, 11 skipped, 0 failed; Vitest 1785 passed, 1 skipped; tsc exit 0; Gradle testDebugUnitTest XML 1739 tests, 0 failures, 0 errors, 7 skipped. Hash khoá `c9176123`.

Đợt `0.4.133` trên `ABook_rel437` (0b004ca4 = 0.4.132 + `dev/uxfix127` + `dev/diag128` + `dev/uxfix126` + sửa a116f/a118f): đồng bộ tiến độ nghe theo phiên bản Lamport (không theo giờ máy) trên cả máy tính và điện thoại, hồ sơ cũ tự gắn phiên bản một lần; chẩn đoán điện thoại từ xa; vá bảo mật Cast/DLNA và máy chủ đồng bộ. 6 test đồng bộ cũ viết lại theo hợp đồng phiên bản. Bộ đầy đủ t119: pytest 9369 passed, 9 skipped, 0 failed (6 test viết lại chạy riêng 82/82 cùng các file a116/a118); Vitest 1662 passed, 1 skipped; tsc --noEmit exit 0; build web + cap copy exit 0; Gradle testDebugUnitTest XML 1703 tests, 0 failures, 0 errors, 7 skipped; assembleDebug OK. Hash khoá `c9176123`.

Đợt `0.4.132` trên `ABook_rel437` (a002af08 = 0.4.131 + a106r fix `dev/uxfix123` + a107fix `dev/uxfix124` + a108fix `dev/uxfix125`): Nghe ngay (đổi giọng giữa chừng, ghim Làm trước, tải giọng chịu lỗi SSL/ổ đầy, gỡ VieNeu); điện thoại sống cùng Android (tải sách và xuất chạy nền nối lại sau khi app bị đóng, hệ thống dừng xuất không tạo thư mục trùng, sao lưu không mang mã ghép); đọc + nghe trên điện thoại (đồng hồ chữ khi đệm, nghe từ câu đúng giọng cuốn đích, dấu trang sách chữ giữ câu, widget ba cỡ). Bộ đầy đủ t118: pytest 9155 passed, 9 skipped, 0 failed; Vitest 1603 passed, 1 skipped; tsc --noEmit exit 0; Gradle testDebugUnitTest XML 1613 tests, 0 failures, 0 errors, 7 skipped. Hash khoá `c9176123`.

Đợt `0.4.131` trên `ABook_rel437` (00ed7325 = 0.4.130 + a105fix `dev/uxfix121` + a106fix `dev/uxfix122`): hồ sơ người nghe (hai máy tính ghép và điện thoại làm máy giữ sách gộp theo mã hồ sơ, phát giữ hồ sơ đã chốt, tốc độ/giọng/đêm/dấu trang/đánh dấu chương ghi đúng hồ sơ, giọng riêng theo hồ sơ, đổi tên/xoá hồ sơ cuốn một hồ sơ); màn Bản lưu cũ trên điện thoại. Bộ đầy đủ t117: pytest 9135 passed, 9 skipped, 0 failed; Vitest 1574 passed, 1 skipped; tsc --noEmit exit 0; Gradle testDebugUnitTest XML 1586 tests, 0 failures, 0 errors, 7 skipped. Hash khoá `c9176123`.

Đợt `0.4.130` trên `ABook_rel437` (fc6075e1 = 0.4.129 + phần còn lại a99/a100 `dev/uxfix118` + a101fix `dev/uxfix117` + a102fix (trong uxfix118) + a103fix `dev/uxfix119` + a104fix `dev/uxfix120`): hiệu năng (nhớ tạm danh sách sách/chương/vai, nhật ký chỗ nghe thay ghi cả file, danh sách giới hạn trên điện thoại); lưu .abook giữ bản cũ trên điện thoại, khoảng số cài đặt chung hai nền; nhạc nền riêng của cuốn (nhạc của tôi, mức to logic, hẹn giờ ngủ giảm dần); phát ra loa/TV (dừng chắc trước khi phát ở máy, báo loa chỉ phát giọng, bìa trên TV/màn khoá). Bộ đầy đủ t116: pytest 9099 passed, 9 skipped, 0 failed; Vitest 1553 passed, 1 skipped; tsc --noEmit exit 0; Gradle testDebugUnitTest XML 1560 tests, 0 failures, 0 errors, 7 skipped. Hash khoá `c9176123`.

Đợt `0.4.129` trên `ABook_rel437` (6d0d770a = 0.4.128 + a98fix `dev/uxfix114` + a99fix `dev/uxfix115` + nhạc P3 vòng 8 `dev/loopp3w` fe0779a0 + a100fix `dev/uxfix116`): nhập sách (mã TCVN3/VNI báo trước, file nén hỏng báo lỗi rõ, tiêu đề chương 'Chương 12a'/'cuối', dòng lề PDF, đề xuất phần đầu/cuối sách); xuất và chia sẻ (lưu .abook có bản lưu phòng, nhạc kèm sách đã nhập, ước cỡ đủ phần ngoài audio); cài đặt (hẹn giờ ngủ, khoảng số chung hai nền); nhạc P3 chỗ nối bed44gthu 10/10. Bộ đầy đủ t114: pytest 9060 passed, 9 skipped, 1 failed (test a68 còn chờ cỡ chỉ-audio, sửa theo ước cỡ mới - chạy lại file xanh); Vitest 1513 passed, 1 skipped; tsc --noEmit exit 0; Gradle testDebugUnitTest XML 1519 tests, 0 failures, 0 errors. Hash khoá `c9176123`.

Đợt `0.4.128` trên `ABook_rel437` (90ef404d = 0.4.127 + a96fix `dev/uxfix111` + băm mô-đun nhớ qua lần mở `dev/uxfix113` + nhạc P3 vòng 6-7 `dev/loopp3w` c5ea23c0 + a97fix `dev/uxfix112`): Studio kiểm file mô-đun theo SHA, báo thiếu chỗ đĩa đúng ổ, tiến trình thu âm chết không treo lô; chỗ nối nhạc P3 khớp ≤ 0,5 ms (bed44chinh 10/10); quản lý thư viện (đổi thư viện, xoá/Bắt đầu chung khoá, metaVersion, series, Tải sách liệt kê phần tải dở, bìa theo nội dung). Bộ đầy đủ t113: pytest 9001 passed, 9 skipped, 0 failed; Vitest 1433 passed, 1 skipped; tsc --noEmit exit 0; Gradle testDebugUnitTest XML 1493 tests, 0 failures, 0 errors. Hash khoá `c9176123`.

Đợt `0.4.127` trên `ABook_rel437` (245eff98 = 0.4.126 + a94 `dev/uxfix108` + a95fix `dev/uxfix109` + nhãn giọng điện thoại `dev/uxfix110`): hộp Đổi giọng gửi khoá giọng, tên giọng máy khác trên cả hai nền, gỡ mô-đun giọng hỏi trước; chỗ đọc theo hồ sơ + anchor, hàng đợi nhận chương mới, chữ và tiếng giữ khớp tới lần nạp sau. Bộ đầy đủ t111: pytest 8963 passed, 9 skipped, 0 failed; Vitest 1419 passed, 1 skipped; tsc --noEmit exit 0; Gradle testDebugUnitTest XML 1481 tests, 0 failures, 0 errors. Hash khoá `c9176123`.

Đợt `a95fix` trên `dev/uxfix109`, nền `895ea9a2` (0.4.126): sửa V1–V7, T1, T2 của soát đọc/nghe.
Test nháp đã đưa cạnh mã và đảo thành hành vi đúng: lượt đầu 11 failed / 14 ca, sau sửa xanh.
Chỗ đọc theo hồ sơ có anchor/thời điểm, bản mới hơn thắng, flush khi rời/ẩn và retry; native lưu/đồng bộ cùng hợp đồng.
Hàng đợi nhận chương mới; cache script theo phiên bản audio/mốc; bản chữ đang đọc to giữ cùng mốc tới lần nạp sau.
Dấu trang tìm bằng câu trích, recap chia khoảng theo chương; Nhạc của tôi làm mới hàng bài và cỡ chữ có tên trợ năng riêng.
Kiểm cuối: Vitest 1413 passed, 1 skipped (176 file); tsc --noEmit exit 0; pytest liên quan 76 passed,
4 deselected vì cần socket HTTP (kiểm offline chặn mạng thật); Gradle testDebugUnitTest exit 0,
XML 1478 tests, 0 failures, 0 errors, 7 skipped (192 suite). Các test Kotlin mới: StoreReadingTest, QueueRefreshTest.
Hash khoá đầu/cuối `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`; không sửa file khoá.
Chưa kiểm nghe/hiển thị trên thiết bị thật hay NVDA/TalkBack; không tạo model/audio. Bộ đầy đủ t109: pytest 1 trượt (chương của gói thiếu audioVersion/wordsVersion như chương dự án) -> sửa package_share._chapter, file liên quan xanh.

Đợt `0.4.126` trên `ABook_rel437` (b1e1986e = a90a + a90b + a92 `dev/uxfix106` + a93 `dev/uxfix107` + p3w `dev/loopp3w`): Studio lần đầu (nút Tạo chờ quét nguồn hiện tại, đóng app dừng lượt cài + khoá cài liên tiến trình, Whisper tải nối, huỷ gửi nguồn, xem trước UTF-16/CP1258, thời gian là số tham khảo); liên kết hai máy (dấu băm audio lưu đĩa: 4200 file lượt sau 27,16 s -> 0,08 s kể cả sau khởi động lại; ghép lại theo vân tay chứng chỉ; dọn sách ảo đã mất; /sync/v1/library cô lập cuốn lỗi; điện thoại giữ chữ Đọc theo của chương không đổi); nhạc nền P3 sau cờ tắt (chuyển a87 -> P3 chờ AudioTrack P3 ra loa, khớp |δ| <= 10 ms; máy ảo §43 thử vòng 6 đạt 6/6, S6 δ 3,7 ms). Toàn bộ: pytest 1 failed (test hẹn giờ chập chờn khi máy bận, chạy riêng qua; nới hạn 0,05 -> 0,5 s ở 9847d0f2); vitest 1385 passed, 1 skipped; tsc exit 0; JVM 1474 tests, 0 F/E. Hash khoá c9176123 không đổi.

Đợt `a90b` trên `dev/uxfix105` (nền 6aae011e): hàng "Cần nghe lại" tách mã cảnh báo ghép, cả họ "ASR không phán xử được" vào
"Chưa kiểm được" và không hiện transcript ảo; một câu một thẻ (thẻ mang thêm lý do logprob); Hoàn tác sau khi điện thoại đã gửi:
gói gửi mang lời nhờ rút (edits_removed wishes), máy giữ sách rút đúng thao tác theo mốc (cancelled.withdraw_folded), Python + Kotlin;
"Việc cần bạn"/"Cần nghe lại" tự làm mới mỗi 15 s khi sách đang chạy. Toàn bộ: pytest exit 0 (9 skipped, 2 xfailed, 0 F/E);
vitest 1361 passed, 1 skipped; tsc exit 0; JVM 1403 tests, 7 skipped, 0 F/E. Hash khoá c9176123 không đổi.

Đợt `a90a` (C1/C2/V3) trên `dev/uxfix104`, nền `6aae011e`: dấu SHA-256 chương qua đồng bộ/thư viện/bộ đệm; nhập lại .abook cập nhật audio và hỏi trước bản cũ, giữ sửa/chỗ nghe; lưu dấu bản xuất, nhắc bản cũ và xuất riêng MP3 đổi. Kiểm 130 file pytest: 2 failed, 2046 passed, 3 skipped, 1 xfailed, 1 warning in 863.16s (0:14:23); chạy lại: 54 passed in 32.11s. Vitest: Tests  1354 passed | 1 skipped (1355); tsc exit 0. JVM 1401 passed, 0 F/E, 7 skipped. Hash khoá c9176123 không đổi. Thêm bộ đệm băm (máy tính theo cỡ+mtime_ns, điện thoại prints.json ghi lúc tải): sync.manifest lần 2 1,38 s -> 0,021 s (100 chương x 20 MB). Toàn bộ: pytest exit 0 (0 F/E); vitest 1354 passed, 1 skipped; tsc exit 0; JVM 1415 tests, 7 skipped, 0 F/E. Hash khoá c9176123 không đổi.

Đợt `a88fix` trên `dev/uxfix102` (nền d787857c): Tạm dừng / Dừng / Tiếp tục / hồi phục sự cố trong Studio - trạng thái "Đang dừng…"
khoá hai nút tới checkpoint kế; Dừng khi supervisor đã chết trả 409 tiếng Việt thay 500; "Làm lại phân tích từ đầu" kiểm trước, đưa bản dở
vào chỗ chờ Hoàn tác và khôi phục nếu tạo cuốn mới hỏng; "Tiếp tục" lần hai giữ đồng ý chạy trên pin; UI dùng phản hồi máy chủ ngay, làm mới
khi lỗi; điện thoại + máy tính báo "tạm dừng vì pin"; toast đúng, lời hộp Dừng nhất quán, nguyên nhân sự cố hiện trên trang sách, sách xếp
hàng nói rõ chờ cuốn nào; giữ máy thức (không giữ màn hình) khi sách đang chạy thật. Toàn bộ (Lead chạy): pytest 8764 passed, 9 skipped,
2 xfailed, 0 F/E; vitest 1343 passed, 1 skipped; tsc exit 0; JVM 1378 tests, 7 skipped, 0 F/E. Hash khoá c9176123 không đổi.
Đợt `a89fix` trên `dev/uxfix103` (nền 6a053bc5): soát can thiệp người dùng trong Studio - chuyển lời dẫn thành thoại chọn được
mọi người nói (dùng SpeakerMenu), sửa dòng có Hoàn tác + rút lại, yêu cầu bị pipeline từ chối hiện thẻ trong "Việc cần bạn",
Reviews.set_many đọc/ghi một lần, GET không ghi, review_view có cache; shared_readings/workshop_merge ghi overrides trong khoá;
trộn workshop có bia mộ (cancelled.json, cả Kotlin); kiểm tên nhân vật (name_rules.py + NameRules.kt); khay "Bỏ qua" khôi phục được.
8 file test mới (47 test). Toàn bộ: pytest 8844 thu được, exit 0 (9 skipped, 2 xfailed, 0 F/E); vitest 1347 passed, 1 skipped;
tsc exit 0; JVM 1382 tests, 7 skipped, 0 F/E. Hash khoá c9176123 không đổi.
Đợt `a80fix2` trên `dev/uxfix99` (Codex tk3 bị cắt ở lượt kiểm cuối, Lead chạy toàn bộ): gói sửa lớn từ máy đã ghép có hạn đọc theo cỡ
(30 s + cỡ / 16 KiB/s), máy chưa ghép vẫn 30 s; trần kết nối 32 tổng / 8 mỗi nguồn (máy tính), 8 / 6 (điện thoại); GET đóng sớm/503 thử
lại tối đa 2 lần (200/800 ms), không POST. Toàn bộ a80fix + a80fix2: pytest 8690 passed, 9 skipped, 1 xfailed (lỗi 3), 0 F/E;
vitest 1329 passed, 1 skipped; tsc exit 0; JVM 1370 tests, 7 skipped, 0 F/E. Hash khoá c9176123 không đổi.
Đợt `a80fix` trên `dev/uxfix99` (nền cdba76cd): đã tái hiện trước sửa và xử lý 9 lỗi về mã sách/đường file peer,
containment Android, bảo toàn danh sách máy đã ghép, công bố file tải đồng thời, giới hạn ghi đĩa/đọc RAM,
MIME của file sách/dự án và tài nguyên cổng đồng bộ. Python/Kotlin dùng cùng luật đường dẫn và ngân sách tải;
changelog và AGENTS ghi invariant mới. Không sửa file quality khóa; hash trước/sau c9176123.
Lỗi 3 (MITM ghép lần đầu) chỉ có thiết kế giao thức mới, test `test_pairing_first_use_gap.py` strict xfail giữ dấu lỗi còn tồn tại;
lỗi 11 chưa tái hiện được vì JVM không có Android CookieManager/WebView, không sửa phần Studio Bluetooth.
Kiểm tra: pytest liên quan 222 passed, 1 xfailed, 0 F/E; vitest toàn bộ 1329 passed, 1 skipped, 0 failed; tsc exit 0;
JVM toàn bộ 1356 tests: 1349 passed, 7 skipped, 0 F/E. Sau chỉnh containment dùng separator để không đòi API 26,
kiểm lại Store*/PeerPaths/BookFileImport: 63 tests, 62 passed, 1 skipped, 0 F/E. Ca symlink mới skip vì runner Windows thiếu quyền.
Chưa chạy relay TLS/Android WebView thật, flood LAN hay đo NTLM. Lượt JVM đầu có một fixture cũ dùng ServerSocket(0)
để lấy cổng rồi đóng ngay (bind wildcard); đã sửa fixture OnlineVoicesTest chỉ bind loopback trước các lượt tiếp theo.

Đợt `a82loop` trên `dev/uxfix93` (nền cd9c766b): nhạc nền vào bản lặp đúng hạn - tạo sẵn phần tử/ExoPlayer lặp khi còn < 3 s,
hẹn giờ đúng loopEnd - X thay vì chờ nhịp đồng bộ (250 ms máy tính / 500 ms điện thoại), mở ở loopStartAt (bù phần trễ), sửa pha một lần khi
bản mới có tiếng; ba hàm thuần loopHandoffDelay/loopStartAt/loopDrift cùng ca số ở TS và Kotlin (MusicLoopTest). Đo thật máy tính (Music,
PLAN_loop §34.3, 59 bài, Edge headless): lệch trung vị 120 -> 2,3 ms, lệch phách 98 % -> 22 % (= mức vào đúng giờ). Điện thoại chưa đo máy thật.
Toàn bộ (Lead chạy): pytest 8573 passed, 9 skipped, 0 F/E, exit 0; vitest 1327 passed, 1 skipped; tsc exit 0; JVM 1335 tests, 6 skipped,
0 F/E. Hash khoá c9176123 không đổi.

Đợt `a83fix` trên `dev/uxfix94` (nền 3b87b35c): hàng chờ và hộp thay đổi Studio - "Bỏ xếp hàng" chỉ bỏ khỏi hàng (409 khi cuốn đã chạy,
không dừng giữa phân tích); sửa từ điện thoại và nút sửa máy tính dùng chung khoá dự án (không nuốt nhau); bản sửa mới hơn thay bản cũ trong hộp;
danh sách yêu cầu tạm không đọc được thì báo "thử lại sau vài giây" thay vì ghi đè; bỏ thay đổi chờ áp khi đã tạm dừng ở chỗ nghỉ; hoàn tác
người nói cả nhóm; một sửa lời kể -> lời thoại là một mục. Phần cần file khoá (đọc-sửa-ghi overrides, rút yêu cầu ở dây chuyền) nằm ở
`dev/locked100`. Toàn bộ (Lead chạy): pytest 8646 passed, 9 skipped, 0 F/E, exit 0; vitest 1311 passed, 1 skipped; tsc exit 0;
JVM 1329 tests, 6 skipped, 0 F/E. Hash khoá c9176123 không đổi.
Đợt `a85fix` trên `dev/uxfix97` (nền 3b87b35c): cập nhật app, cài/gỡ và gói tuỳ chọn - cập nhật Studio bị từ chối khi sách đang chạy/tạm dừng
(kiểm lại ngay trước thay runtime); bộ gỡ Windows đọc vị trí thư viện trước mọi xoá đệ quy, không đọc được thì giữ; chế độ nâng cấp truyền bằng
cờ rõ ràng (không đoán tên bộ cài); thư viện tuỳ chọn giải ở staging, khoá đích suốt tải-giải-commit; Studio cài theo hash của uv.lock đi kèm
(--require-hashes, commit Git đủ 40 hex); dấu cài xong chỉ ghi sau kiểm; đầy ổ / không ghi được báo rõ; điện thoại xoá được phần tải dở.
Lỗi 1 (ghim mã cho worker đang chạy) chỉ thiết kế, giữ test strict xfail. Toàn bộ (Lead chạy): pytest 8644 passed, 9 skipped, 1 xfailed,
0 F/E (sau khi Lead sửa test hook cũ còn tìm `RMDir /r` trần); vitest 1308 passed, 1 skipped; tsc exit 0; JVM 1333 tests, 6 skipped,
0 F/E. Hash khoá c9176123 không đổi.
Đợt `a84fix` trên `dev/uxfix95` (nền 3b87b35c): nhập TXT/DOCX/PDF/thư mục, 19 mục, luật chung Python + Kotlin qua fixture chung
`tests/fixtures/import/a84_*` - không tự bỏ chữ của truyện: chữ dẫn, dòng tên truyện và Heading 1 đơn ở lại trong thân ("Mở đầu" tích sẵn);
dòng đầu/chân trang PDF thành gợi ý bỏ đọc bỏ chọn được; lời chú/dấu gọi DOCX giữ mặc định; thêm sách từ chối khi nguồn đổi sau lần xem trước;
một file con không đọc được làm hỏng cả thư mục kèm tên file; Studio dùng cùng luật mục lục/tập/tiêu đề với Nhập; ngắt dòng/trang DOCX và
ký tự điều khiển TXT giữ ranh giới từ; tracked move đọc một lần; kiểu Heading kế thừa/outline; byte TXT hỏng báo rõ, không thay ký tự âm thầm;
thứ tự thư mục theo tên gốc dài + casefold Unicode 14 như Python; PDF thưa chữ giữ chữ và cảnh báo trang ảnh; lỗi PDF nêu lý do và việc bạn
làm được (OCR/mở khoá/TXT/DOCX). Lead sửa A84ImportTest (JSONObject.similar không có trong vỏ android.jar) và cập nhật 6 test JVM cũ theo luật
mới. Toàn bộ: pytest 8645 passed, 9 skipped, 0 F/E; vitest 1310 passed, 1 skipped; tsc exit 0; JVM 1347 tests, 6 skipped, 0 F/E.
Hash khoá c9176123 không đổi.
Đợt `a79fix` trên `dev/uxfix91` (nền cây phát hành dcbd33a0): "Nghe ngay" không gửi chữ khi chưa đồng ý - chuỗi giọng
thay thế chỉ có Edge khi đã đồng ý "edge" (máy tính + điện thoại); menu Giọng đọc hỏi đồng ý trước khi đổi sang giọng trực tuyến;
lõi Android giữ (held) chương chữ với giọng chưa đồng ý ở startAt/onPlay/voicesChanged và "Làm trước" (Android Auto, widget, tai nghe);
wordIndexAt([]) không ném (close/load không đứng); vị trí đọc giữ khi sửa đoạn khác (băm đoạn, fixture chung Python/TS/Kotlin);
Prepare không kẹt "running", dọn .part cũ, hợp cách đọc vượt trần, hẹn "hết chương" đứng ở đầu chương kế. Lỗi 11 làm nửa
(readings.py/word_timing.py là file khoá). Toàn bộ (Lead chạy): pytest 8501 passed, 9 skipped, 0 F/E, exit 0; vitest 1288 passed,
1 skipped; tsc exit 0; JVM 1312 tests, 6 skipped, 0 F/E. Hash khoá c9176123 không đổi.
Đợt `a81fix` trên `dev/uxfix92` (nền a74aca2e): mở/nhập .abook/.abookproj - book.json sai kiểu bị từ chối lúc nhập và một cuốn hỏng
không kéo sập thư viện; trần tỉ lệ nén (20:1 media, 100:1 chữ) cả hai nền; nhập cùng file hai lần liền chờ nhau; thay cuốn đang phát báo "đang phát"
và trả bản cũ; tên mục trùng khi bỏ hoa-thường/dấu chấm cuối bị từ chối; sổ dự án bản mới hơn bị từ chối trước khi giải nén; báo tên khác khi
mở lại cùng sách; điện thoại nhập ở luồng riêng, zip cụt báo "chép chưa xong", dọn import-*.abook cũ, trần độ lồng JSON; bộ file vàng chung
tests/fixtures/book_files (18 ca) cho pytest và JVM. Toàn bộ (Lead chạy): pytest 8633 passed, 9 skipped, 0 F/E, exit 0; vitest 1292 passed,
1 skipped; tsc exit 0; JVM 1314 tests, 6 skipped, 0 F/E. Hash khoá c9176123 không đổi.

Đợt `a77fix` trên `dev/uxfix88` (nền rc123): 12 mục nghe trên Android - nút tai nghe/xe sau khi dịch vụ bị dọn (MediaButtonReceiver),
một đường phát tiếp duy nhất qua Playback.play (tự lùi, chuẩn bị lại sau lỗi), tuỳ chọn nghe + hẹn giờ ngủ phút nhớ ở kho native (ListenPrefs),
tốc độ từ controller ngoài lên giao diện, lời giải thích quyền thông báo, khoá riêng danh sách giọng VieNeu/Supertonic. Mỗi mục test đỏ trước rồi xanh.
Toàn bộ: JVM 1284 tests, 6 skipped, 0 F/E, exit 0; vitest 1262 passed, 1 skipped; tsc exit 0. Không đổi Python (pytest chạy ở lượt kiểm bản phát hành).
Chưa thử trên máy thật: ANR khi đổi giọng chỉ đo trong test (voices() < 200 ms khi khoá chính bị giữ).
Đợt `a78fix` trên `dev/uxfix89` (nền rc123, Codex tk1 bị cắt ở 99 % lúc kiểm cuối, Lead soát + làm nốt): máy tính nghe tin cậy -
phiên phát theo lần nạp trang (`/progress/session`, 409 khi cửa sổ khác đã thay; giữ 16 phiên gần nhất), hộp chờ tiến độ sống qua
nạp lại và chỉ gỡ khi ACK đúng bản, hẹn giờ phút chỉ đếm thời gian có tiếng, mờ dần áp cả nhạc nền, ý định phát chặn lần thử lại /
chờ máy nguồn cũ, kết quả mở file giữ ở host tới khi trang ACK, đóng app dừng cả xuất .abook và xuất sách chữ. F13 (nhớ cửa sổ)
làm riêng ở `dev/winstate90`. Lead sửa thêm: đổi chương lúc dừng không lưu (load coi chỗ mới là đã lưu) - test
`playerReliability` đỏ 1F rồi xanh. Toàn bộ: pytest 8470 passed, 9 skipped, 0 F/E, exit 0; vitest 1271 passed, 1 skipped; tsc exit 0.
Không đổi Kotlin. Hash khoá c9176123 không đổi.

Đợt `a73fix2` trên `dev/uxfix81` (nền c9a9baf1): nhận lượt hàng đợi và nút chạy dưới cùng khoá,
đánh dấu khởi động trước khi chuẩn bị, giữ hàng trên đĩa tới khi jobs nhận start; dọn Thùng rác nền theo hạn đóng app.
Android ghi dấu huỷ theo id việc trước khi cancel (nút trong app, thông báo, xuất thay lượt cũ); dừng không rõ lý do giữ URI/quyền/bìa.
Test đỏ trước: bỏ đầu hàng trong khe và ngắt trước jobs.start đều hỏng (2 F, exit 1); sweep chậm hỏng (1 F);
JVM quyết định giữ tài nguyên với UNKNOWN/API cũ hỏng (1 F, exit 1). Sau sửa nhóm pytest liên quan **119 passed, 0 F/E, exit 0**.
Test phục hồi tạo TrashPending mới từ metadata `recycling` đã xác nhận lần dọn kế tiếp nhận đúng byte audio.
Các bài dùng runner/Thùng rác giả và thư mục tạm; JVM kiểm quyết định và thứ tự commit dấu huỷ trước cancel,
không kiểm SAF/receiver trên Android thật. Toàn bộ (Lead chạy lại): pytest 8390 passed, 9 skipped, 0 F/E, exit 0; vitest 1239 passed; tsc exit 0; JVM 1202 tests, 0 F/E.
Đợt `dev/uxfix87` (`a76fix`, worktree từ `dev/uxfix82`, HEAD `74caa860`): sửa lệch giữa máy tính và điện thoại theo findings a76.
Mục tải file/Range để `dev/uxfix83` xử lý.

- Lời đáp đồng bộ hợp với trạng thái hiện tại của đúng hồ sơ (kể cả `activeState` và máy giữ sách đời cũ), giữ bia mộ dấu trang;
  hồ sơ bị xoá lúc đang chờ mạng không sống lại. Fixture `listening_records/inflight_reply.json` chung Python/JVM;
  trước sửa JVM 3F, sau 4 test qua (cộng ca xoá hồ sơ xen giữa).
- Xuất MP3 chọn thư mục mới `(2)`, `(3)` ở SAF và thư mục thường; test xuất ba lần so byte các bản bìa: đỏ rồi xanh.
- Dấu trang trùng bổ sung ghi chú nếu ghi chú cũ trống, giữ `createdAt`; cửa sổ gộp ±5 giây và phân biệt dấu theo câu như Python.
  Fixture `bookmark_places.json` chung 8 ca. Hai test JVM đỏ trước, xanh sau.
- Hoàn tác dấu trang đi qua API riêng giữ ID và gỡ tombstone; fixture `restore_bookmark.json` chung kiểm gộp với edit/delete cũ.
  Vitest kiểm cầu nối đỏ 1F rồi xanh 1 test.
- Hẹn “Hết chương” chia thời lượng audio còn lại cho tốc độ (sàn 0,25 như web). JVM đỏ rồi xanh ở 2×/0,5× và trường hợp hết chương.
- Bỏ bìa chỉ giữ `cover:null` khi có bìa gốc; nếu không gỡ khoá `cover`. Fixture `cover_removal.json` chung 4 ca,
  Python qua; JVM đỏ trước, xanh sau.
- Bìa nghe thẳng của thiết bị ghép: so màu/phiên bản từ danh sách, so toàn mô tả khi lấy manifest, gỡ ảnh cache cũ để tải lại;
  không đụng ảnh người nghe sửa. Fixture `stream_covers.json` chung kiểm Python `_refresh_book` và policy JVM.
  Thêm ca danh sách thiếu kích thước/tên file để không tải lại vô ích; test đỏ rồi xanh.
- ID chương và mốc nhạc trong phần sửa chỉ nhận `[0-9]`; ba fixture invalid Unicode dùng chung, Python đỏ 3F trước rồi xanh.
- Lead thêm: cổng đồng bộ giữ `deleted` dạng dict (bia mộ dấu trang) thay vì bỏ cùng cờ đồng bộ - test qua cổng thật đỏ khi bỏ sửa;
  máy tính nghe sách của máy tính khác gửi/gộp cả `sessions`/`night` như điện thoại (`test_remote_computers` mở rộng).
- Toàn bộ (Lead chạy lại): pytest 8399 passed, 9 skipped, 0 F/E, exit 0; vitest 1242 passed, 1 skipped; tsc exit 0;
  JVM 1232 tests, 6 skipped, 0 F/E. Hash khoá 67286434 không đổi.

Đợt `dev/uxfix82` (`a74fix`, từ `c9a9baf1`): đã đối chiếu từng khẳng định với mã trong cây này, sửa #1, #2, #5, #6,
#7, #10, #11, #8 theo thứ tự. #3 xác nhận là lỗi nhưng hoãn: cần receipt sau từng commit trong `pipeline.py` (khoá),
không thể suy “đã áp” từ READY/run marker. #4 và #9 bỏ qua theo phạm vi được giao.

- #1: giữ state nguồn đến sau commit records; `StoreMigrationCrashTest` đỏ 1F rồi xanh 1 test.
- #2: snapshot điện thoại lưu ID bền trước gửi; desktop reserve receipt/dấu giờ trước ghi retake, retry giữ dấu cũ;
  `test_book_wishes` đỏ 2F, JVM đỏ 1F; sau Python 24 test và JVM EditsSync/BookWishes 34 test qua.
- #5: journal trước đổi thư mục; khởi động/retry hoàn tất manifest, liên kết và fingerprints. `StoreRekeyTest` đỏ 1F rồi xanh.
  Rà thêm tình huống lỗi ghi liên kết rồi retry cùng tiến trình: đỏ 1F; copy records trước moveLinks, cache chỉ đổi sau commit;
  rekey/record sync xanh 9 test.
- #6: checkpoint thay nguyên tử qua Store, không xoá đích trước; đối chiếu job running với unique work khi mở plugin/status,
  enqueue KEEP khi thiếu. `PrepareAheadTest` đỏ 2F, sau 17 test qua.
- #7: pending chứa book/record/revision và snapshot; flush đúng hồ sơ, ACK chỉ gỡ đúng revision. Pending đời cũ gửi mọi hồ sơ
  của cuốn. `StateSyncCrashTest` đỏ 1F; sau pending/hai thiết bị xanh 8 test.
- #10: JSON bỏ tham chiếu bìa commit trước dọn asset. Kotlin đỏ 2F, Python remove_cover đỏ 1F; sau JVM 25 và Python 221 test qua.
  Python subtract không phải lỗi: đã save trước dọn asset, giữ nguyên.
- #11: FileOutputStream.fd.sync trước rename, kiểm lỗi thay file; giữ JSON hỏng ở .corrupt-time-UUID. Reader state/index/prints,
  job và pending dùng cùng nguyên tắc. Đỏ 2F, sau nhóm durability/migration/rekey/sync/prepare xanh 31 test.
  JVM kiểm lỗi ghi/thay file và giữ nguyên byte hỏng; không mô phỏng mất điện phần cứng.
- #8: last.anchor gồm segment/charOffset/textHash (code point, FNV-1a64 UTF-8 các đoạn nối LF); khôi phục bằng chữ khi hash khớp.
  Kotlin và TypeScript có cùng số vàng tiếng Việt+emoji. Python/HTTP lưu anchor, sync giữ nguyên last; dữ liệu cũ vẫn dùng giây.
  Trước sửa JVM/Python/UI mỗi bộ 1F; sau JVM anchor/record/seek 14 test và UI đọc/anchor 136 test qua.

Pytest liên quan tuần tự: **306 passed, 0 F/E, exit 0**, JUnit `S/a74fix/pytest-related.xml`.
Các lượt đỏ có exit 1, mọi lượt xanh kể trên exit 0; log nằm ở `S/a74fix` (01/02/05/06/07/10/11/08-before/after).
Rà thêm trước khi chốt: ID retake mới không lấy lại ID của entry cũ khi hai lần bấm trùng dấu giờ; checkpoint PrepareAhead
hợp JSON nhưng thiếu schema vẫn được giữ thành .corrupt và không làm lỗi lúc mở. `review-before`: **2 F/0 E, exit 1**;
cả hai ca qua trong full Gradle cuối sau sửa.

Kiểm tổng tuần tự trên mã cuối:

| Bộ | Passed | Failed | Error | Skipped | Exit |
| --- | ---: | ---: | ---: | ---: | ---: |
| pytest liên quan | 306 | 0 | 0 | 0 | 0 |
| pytest toàn bộ | 8450 | 0 | 0 | 9 | 0 |
| vitest toàn bộ | 1241 | 0 | 0 | 1 | 0 |
| tsc --noEmit | — | — | 0 | — | 0 |
| Gradle toàn bộ, lượt cuối | 1211 | 0 | 0 | 6 | 0 |

Pytest toàn bộ: 1586,132 giây; 5 warnings (1 duplicate EPUB entry, 3 cp1252 subprocess reader, 1 timeout server giả),
không F/E. Log/JUnit tại `S/a74fix/pytest-full.log/xml`; UI: vitest-full.log, tsc-full.log; Android: gradle-final.log.
Gradle đầu cũng exit 0 (1209 passed/6 skipped); đã chạy lại toàn bộ sau hai sửa Kotlin từ rà soát.
Compileall abook/tests/scripts và git diff --check đều exit 0. Không còn tiến trình kiểm thử của a74fix.
Hash trước và sau sửa: `67286434ac06a6706d20fd8fe7ee4b1fda99dc0f1c1310fd3d925775768337ff`.
Danh sách khoá đọc từ `QUALITY_IMPLEMENTATION_FILES`; không sửa file khoá, pyproject.toml/uv.lock hay main.rs.
Không Ollama/GPU/adb/điện thoại/GUI; pytest CUDA_VISIBLE_DEVICES=-1, không đặt TRANSFORMERS_OFFLINE; tối đa 4 luồng.
Gradle offline, --no-daemon và Kotlin compiler in-process; cấu hình Android local không đưa vào diff.
Đợt `imp80fix` (`dev/uxfix80`, nền 396400e2): sáu lỗi nhập sách rev_396 được kiểm bằng pytest và JVM,
cùng fixture trong `tests/import_fixtures.py` và `tests/fixtures/import/expected/`.

- Byte giải nén được đếm thực theo khối 64 KiB: 20 MiB/mục, 300 MiB/gói, cả bìa; đọc lại cùng mục không tính trùng.
  Stream giả khai 1 byte tái hiện đường vượt trần (Python 3F, JVM 1F trước sửa); ca bìa gọi trực tiếp _epub_cover/epubCover.
  Chưa khẳng định exploit ZIP thật vượt được zipfile CPython.
- 401 NUL và các C0 vô hình được bỏ trước khi xuất chữ; form feed ngắt đoạn, tab/newline/CR giữ nguyên. Round-trip extract → decode_text
  giữ nguyên chữ thấy được (Python 2F, JVM 1F trước sửa). Form feed trong script/HTML ẩn không ngắt chữ thấy được
  (bổ sung Python 1F trước guard, fixture review_controls dùng chung). Snapshot rights_odd_pages bỏ NUL có chủ ý.
- Bảng alias XML/XHTML Kotlin dùng chung, XML vẫn giữ whitelist; chương và DRM kiểm latin-1/latin1/l1/cp1252/utf8/x-sjis,
  thêm mọi alias XML Python biết (JVM 1F trước sửa; Python đã đúng).
- UTF-16LE/BE không BOM được nhận trước UTF-8 ở đường chương và DRM, có/không khai báo XML (Python 4F, JVM 1F trước sửa).
- XML strict kiểm một root, thẻ đóng/mở, chữ ngoài root, thuộc tính, entity và namespace bằng SAX; external DTD không được tải.
  Container/OPF/DOCX cũng strict giống ElementTree. 16 ca XML chung và ba gói bị thêm root (JVM 2F trước sửa; Python đã đúng).
- EPUB 5.000 mảnh khoảng 4 KiB/mảnh, mục lục chỉ trỏ mảnh đầu: ghép list rồi nối một lần, giữ SHA-256 chữ/thứ tự/chú thích.
  Python 12,139 → 0,787 giây; JVM sau sửa 1,033 giây; cả hai vượt ngưỡng 12 giây trước sửa (mỗi bên 1F).

Kiểm liên quan: `test_import_review.py`, `test_importers.py`, `test_import_library_fixes.py`, `test_epub_import.py`,
`test_txt_split.py`: **236 passed, 0 F/E, exit 0**.
Hash khoá trước/sau sửa: `67286434ac06a6706d20fd8fe7ee4b1fda99dc0f1c1310fd3d925775768337ff`, không đổi.
Không sửa file trong QUALITY_IMPLEMENTATION_FILES; không dùng Ollama/GPU/điện thoại.
Vitest đầy đủ: **1239 passed, 1 skipped, 0 F/E, exit 0** (140 file pass, 1 skipped). `npx tsc --noEmit`: **0 lỗi, exit 0**.
Gradle offline `:app:testDebugUnitTest --max-workers=4 --no-daemon`: XML **1205 tests, 0 F/E, 6 skipped, exit 0**, 139 suites.
Lượt pytest đầy đủ đầu hoàn tất: **8478 passed, 1 F, 0 E, 9 skipped, exit 1**, 1456,394 giây.
Failure duy nhất là kiểm catalog XML cũ trong `test_encoding_names_are_normalised_the_same_way_on_both_platforms`:
fixture nay có thêm các alias hợp lệ. Đã bổ sung kiểm từng alias mới phải ra chữ A, giữ nguyên tập ca hỏng; cả 236 test liên quan qua.
Lượt đầy đủ sau cập nhật test: **8478 passed, 1 F, 0 E, 9 skipped, exit 1**, 1535,602 giây. Mọi test nhập sách qua.
Failure duy nhất lần này là `test_work_items_at_scale.py::test_many_deletes_share_one_sweep_timer_and_the_earliest_deadline_wins`:
callback hẹn giờ chạy ba lần thay vì hai. Test này đã qua trong lượt đầy đủ trước; kiểm lại nguyên file, không đổi mã/test:
**9 passed, 0 F/E, exit 0**. Giữ nguyên phạm vi sáu lỗi nhập sách; không gọi lượt đầy đủ là exit 0.
Các lượt đầy đủ có warning cp1252 ở subprocess readerthread và timeout socket ở server giả tải nhạc, ngoài phạm vi nhập sách.
Toàn bộ (Lead chạy lại): pytest 8453 passed, 9 skipped, 0 F/E, exit 0; vitest 1239 passed; tsc exit 0; JVM 1205 tests, 0 F/E.
Đợt `musedge` trên `dev/uxfix84`: soát 10 ca biên của nhạc nền (catalog rỗng, tải thân rỗng, điểm vòng sát cuối file, đóng sách khi đang tải...).
Thêm 26 lượt test nhạc Python/TS/JVM; sửa nhận thân tải rỗng trên Android và điểm vòng vượt cuối file thật trên cả ba nền tảng.
Pytest các file nhạc: 544 pass, 2 skip, 0 F/E; Vitest 130 pass; JVM 203 pass; tsc --noEmit exit 0. Tất cả runner exit 0; hash quality implementation giữ nguyên.
Toàn bộ (Lead chạy lại, kể cả stub android/os trong cây test JVM): pytest 8389 passed, 9 skipped, 0 F/E, exit 0; vitest 1252 passed; tsc exit 0; JVM 1222 tests, 0 F/E.
Đợt `offfix` trên `dev/uxfix83`: tải tiếp có kiểm phiên bản (ETag + If-Range) ở cả máy tính lẫn điện thoại (PartResume.kt, PinnedFiles),
206 lệch chỗ/ETag hay 416 thì bỏ phần dở và hỏi lại cả file; cỡ cuối khác cỡ sách thì không nhận; hạn kiểm/tải bản mới của vỏ Tauri (30 s kiểm,
60 s đứng yên) và nút "Kiểm tra bản mới"; tìm bìa có hạn 12 s; bìa quá 40 triệu điểm ảnh bị từ chối hai nền. Test mới: PartResumeTest, CoverPixelsTest,
PinnedFilesTest (đuôi lạ, 416), pytest 416 tải tiếp, cargo tải đứng yên. Toàn bộ (Lead chạy lại): pytest 8392 passed, 9 skipped, 0 F/E, exit 0;
vitest 1245 passed; tsc exit 0; JVM 1210 tests, 0 F/E; cargo 4 passed. Hash khoá giữ nguyên.
Đợt `dev/uxfix85` (a75fix, từ 0.4.122): ghi đủ nhóm người nói trên 2.000 câu (Python/Kotlin), thông báo theo số máy chủ;
hàng nghe lại lọc ở máy chủ rồi phân trang bằng cursor; phán quyết nghe gắn checksum và lưu lịch sử khi bản thu đổi;
huỷ `.abook` trong lúc băm/ghi và khi đóng app; huỷ FFmpeg ghép M4B và dọn bản dở; xuất cả bộ dùng job nền có tiến độ/nối lại;
đối chiếu checksum byte thực ghi để từ chối nguồn thay đổi giữa băm và ghi. Không sửa F1/N1 hoặc file khoá.

Test đỏ trước sửa: F2 Python 1F (2.000 != 2.501), JVM 1F cùng nguyên nhân; F4 2F thiếu phân trang/lọc;
F3 1F phán quyết che bản thu mới, thêm 1F chống chấm từ trang giữ bản thu cũ; F5 3F (endpoint 404, không ngắt băm, thiếu shutdown);
F6 2F (vẫn công bố sau huỷ, chưa theo dõi subprocess); F7 Python 2F thiếu tiến độ và Vitest 3F gọi đồng bộ/nối lại;
N2 2F: thay MP3 bằng file cùng cỡ sau băm làm gói đã công bố bị verify từ chối (cả có/không callback tiến độ).
Tất cả test hồi quy mới đã xanh; hai kiểu xuất bộ qua Studio từ xa chạy lâu hơn hạn chuyển tiếp giả 0,5 giây vẫn nối lại đúng job/kết quả.

Pytest liên quan: lượt đầu **260 passed, 1F/0E, exit 1** (test hủy M4B mất 2,125 s, quá ngưỡng 2 s khi đang biên dịch Gradle);
giữ nguyên mã/ngưỡng test, lượt sau **261 passed, 0F/0E, exit 0**, 141,07 s. Toàn bộ (Lead chạy lại): pytest 8383 passed, 9 skipped, 0 F/E, exit 0; vitest 1244 passed, 1 skipped; tsc exit 0; JVM 1199 tests, 6 skipped, 0 F/E.
Vitest toàn bộ sau sửa cuối: **1244 passed, 1 skipped, 0F/E, exit 0** (142 file qua, 1 bỏ qua), 25,76 s; `npx tsc --noEmit`: **0 lỗi, exit 0**.
Gradle offline `:app:testDebugUnitTest --max-workers=2`: lượt đầu **1199 tests, 1F/0E, 6 skipped, exit 1** ở EdgePiecesTest chờ đóng socket;
LocalStudioTest chạy riêng **20 passed**, EdgePiecesTest chạy riêng **34 passed**; chạy lại toàn bộ không sửa Edge: **1199 tests, 1193 passed,
0F/0E, 6 skipped, exit 0**, 123,92 s. Capacitor build dùng dependency trong worktree; cấu hình trỏ tạm đã khôi phục nguyên byte.

Mọi lượt kiểm giới hạn CPU affinity 4 lõi, OMP/MKL/OPENBLAS/NUMEXPR=4, CUDA_VISIBLE_DEVICES=-1; không đặt TRANSFORMERS_OFFLINE.
Gradle dùng JVM ActiveProcessorCount=4, compiler in-process, --no-daemon; không GPU/Ollama/adb hay thư viện thật.
Hash khoá trước và sau sửa: **67286434ac06a6706d20fd8fe7ee4b1fda99dc0f1c1310fd3d925775768337ff** (41 mục đọc từ code), không đổi.
LF và `git diff --check` qua. Chưa commit/stage/push. Log/JSON kiểm chi tiết nằm ở scratchpad `a75fix`.

Đợt `dev/rvfix` (từ 0.4.120): giữ giới/tuổi khi lượt người nói đổi namespace của cùng vai local trong cùng chương;
không checkpoint hoà giải khi thiếu model (request lỗi giữ nhãn cũ như trước); đóng luồng cả khi bù độ to/hoàn tất clip lỗi;
huỷ hẹn giờ release khi clip xong/bị bỏ (Python và Kotlin); script Windows giữ `setuptools<82`.

Test đỏ trước sửa (`S/rvfix/before-valid.log`): **8 failed, 3 passed, exit 1**; sau sửa cùng lựa chọn **11 passed, exit 0**.
Các test mới: `test_local_pass_relabel_preserves_traits_only_for_the_same_role_in_the_same_chapter` (cùng vai đỏ;
vai khác/chương khác xanh), `test_unreachable_model_reconciliation_is_retried_before_the_speaker_pass` (model không tới được thì thử lại; request lỗi thì giữ nhãn local, không kẹt - Lead sửa),
`test_failure_before_local_close_drops_the_stream` (lift/close), `test_finished_local_stream_cancels_and_releases_its_timer`
(close/drop), `test_windows_setup_keeps_pkg_resources_for_pyworld`. Không ứng viên vẫn hoàn tất không cần model
(`test_local_reconciliation_without_candidates_completes_without_a_model`); các test named traits sẵn có vẫn qua.
SQLite thật, reopen/resume qua BookPipeline.run, model/engine/HTTP giả; không Ollama/GPU/điện thoại.

Pytest liên quan tuần tự: mọi `test_speaker_pass*`, `test_readaloud_local_stream*`, `test_pipeline_mock.py`,
`test_perceptual_pipeline.py`, `test_analysis_required.py`, `test_one_click_startup.py`: **715 passed, 0 F/E, exit 0**,
282,58 giây. Có 1 warning cp1252/UnicodeDecodeError trong subprocess readerthread ở test pipeline (ngoài phạm vi sửa).
Toàn bộ pytest: **8365 passed, 1 FAILED, 0 ERROR, 9 skipped, 5 warnings, exit 1**, 1751,19 giây.
Failure duy nhất: `test_perceptual_qa.py::test_model_load_is_offline_and_environment_is_restored`; runner của đợt này
đặt sẵn `TRANSFORMERS_OFFLINE=1`, trong khi test yêu cầu biến ấy không tồn tại sau khi load giả kết thúc. Đã bỏ biến
khỏi runner, chạy lại CẢ `test_perceptual_qa.py`: **28 passed, 0 F/E, exit 0**, 3,26 giây. Không sửa mã/test perceptual QA.
Không gọi kết quả này là full-suite exit 0: lượt toàn bộ duy nhất vẫn có exit 1 như trên. Các warning là duplicate EPUB
entry, ba cp1252 readerthread và một socket accept timeout trong server giả của test tải nhạc.

Android offline `:app:testDebugUnitTest --max-workers=4`: XML **1166 tests, 0 failures, 0 errors, 6 skipped, exit 0**.
Test mới `LocalLiveTest.finishingOrFailingCancelsThePendingWakeUp` đỏ trước sửa (1/11 failure, exit 1), xanh sau sửa
(11/11 LocalLiveTest qua). Lượt toàn bộ đầu tiên có 1 failure EdgePiecesTest do hết 5 giây chờ đóng socket;
chạy lại riêng test và toàn bộ không sửa mã đều qua. Không đổi logic Edge. Hỗ trợ build Capacitor được chép vào cây rvfix,
init script trong scratchpad trỏ project dependency về cây này; không sửa cấu hình dependency đã theo dõi.

CPU affinity 4 lõi, CUDA_VISIBLE_DEVICES=-1, OMP/MKL/OPENBLAS/NUMEXPR_NUM_THREADS=4; Gradle JVM ActiveProcessorCount=4,
compiler in-process, no-daemon. Compileall, `git diff --check`, LF và BOM PowerShell đều qua.
Hash khoá đọc từ code (41 mục): trước `49e8fd2dc212c7207cd0fbf66b308e6b0d1b49d220d64a16501d170bc906635f`;
sau `f4adb8d13e3f714e52bf070a8819c014938711925af81014673036244fee08f1`. Mã chỉ sửa ở nhánh dev, chưa commit.

Giữ đầu chương điện thoại (`dev/openhold`, từ 0.4.120): `VoiceSpeeds` khớp thời gian = chi phí mỗi khúc + giây/ký tự,
theo tổng có trọng số 20.000 ký tự; ít hơn 4 mẫu hay không phân biệt được hai hệ số thì dùng luật cũ. Lịch 60 s tiếng đầu lấy
mức giữ nhỏ nhất để các đoạn kịp bắt đầu, cộng biên 200 ms, trần 6.000 ms; RTF dự đoán toàn chương >= 1 thì phát ngay.
Chỉ đổi lịch, không đổi bộ sinh/cắt/ghép tiếng. Desktop không có giữ đầu chương tương ứng (`holdUntil` ở UI là nhịp chờ sau nhảy).

JVM offline, 4 worker, JVM ActiveProcessorCount=4, Kotlin in-process: **1.176 tests, 0 failures, 0 errors, 6 skipped, exit 0**
(137 XML suites). `OpeningScheduleTest` **11/11**: sách A dựng từ số OPPO giữ **5.913 ms**, không đoạn nào muộn trong 60 s;
sách B dạng đoạn dài với máy nhanh giữ **1.210 ms**, cũ **1.105 ms**; chưa đo / JSON cũ **1.500 ms** như cũ; RTF >= 1 **0 ms**.
Kiểm thêm hồi quy/lưu/mờ số đo, bộ cắt thật, hàng chờ clip thường + phát luồng, ngăn cảnh/bộ đệm/cửa sổ, biên sát hạn **100 ms**.
`LocalLiveTest` **10/10**, gồm đối chiếu byte clip phát luồng. Không đo điện thoại, máy ảo hay GPU; chưa đo trên máy thật.

Riêng log OPPO nóng `c2_stB` của đợt gap: tiêu đề 2.230 ms, khúc đầu 5.367 ms => cần ít nhất **3.137 ms** chưa cộng biên,
lịch giữ **3.337 ms**. Ca `theRecordedHotOppoBookBCannotFitTheOldCapPlusHalfASecond` ghi rõ yêu cầu B <= 2.000 ms không thể
đồng thời thoả điều kiện không bắt đầu muộn với số đo ấy; ca B máy nhanh ở trên không thay cho log này. Đã hỏi người dùng về ưu tiên.
Vitest/tsc không chạy vì không sửa UI. Hash khoá trước/sau cùng `49e8fd2dc212c7207cd0fbf66b308e6b0d1b49d220d64a16501d170bc906635f` (41 mục đọc từ code).

Đợt a71fix2 (`dev/uxfix78`, nền 3b41e4a3): cả bảy lỗi có test đỏ trước sửa.
Python tái hiện metadata quyền / OpenType / đếm chương complete; JVM bốn test riêng đều FAILED, 0 ERROR
(metadata, MIME, XML UTF-16, URI ngoài BMP). Vitest ba test FAILED cho bộ chọn một/nhiều file trả muộn và
mở .abook sau khi đóng hộp; kiểm bỏ riêng guard trước opened() cũng FAILED. Mỗi bộ đỏ exit 1.
Sau sửa, pytest liên quan 239 passed, 0 FAILED / 0 ERROR, exit 0. Các fixture mới dùng chung Python/Kotlin và
expected JSON bao phủ metadata rights/sinf rõ chữ, rights kèm font, ADEPT kèm chương mã hoá, toàn bộ MIME font
trong bảng EPUB 3.3 (https://www.w3.org/TR/epub-33/#sec-core-media-types), OpenType IDPF/Adobe không đuôi font,
XML UTF-16 có BOM và UTF-16LE/BE có khai báo, URI trộn emoji thô với percent-encoding.
UI kiểm callback thật của AddBookDialog và useOpenBookPath: đóng hộp bỏ lựa chọn và lỗi muộn, không preview,
không điều hướng/toast; cả đường một file và hàng .abook truyền session tới trước tác dụng phụ.
Hash sau sửa vẫn `49e8fd2dc212c7207cd0fbf66b308e6b0d1b49d220d64a16501d170bc906635f`, trùng trước sửa.
Kiểm tuần tự trên mã cuối: pytest toàn bộ 8395 ca = 8386 passed + 9 skipped, 0 FAILED / 0 ERROR, exit 0
(1632,4 giây); Vitest 1214 passed + 1 skipped, 0 failed / 0 errors, exit 0; tsc --noEmit không lỗi, exit 0.
Gradle :app:testDebugUnitTest --max-workers=4 --offline: 1171 ca = 1165 passed + 6 skipped,
0 FAILED / 0 ERROR, exit 0 (106,1 giây). Giới hạn bốn CPU, CUDA_VISIBLE_DEVICES=-1; không đặt TRANSFORMERS_OFFLINE.
Pytest có hai cảnh báo ngoài phạm vi sửa: ZIP trùng tên trong test EPUB và timeout accept của máy chủ giả trong
test_music_truncated_download. Không có FAILED/ERROR. Compileall, LF và git diff --check qua; không còn tiến trình thử nền.

Đợt a72fix2 (`dev/uxfix79`): năm lỗi do rà a72fix, mỗi lỗi có test đỏ trước sửa:
1 điện thoại gửi nhãn cả cuốn xuống lõi mỗi lần mở sách, lõi thay từng mục hàng đợi (nay so nhãn, thay một lần `replaceMediaItems`);
2 Sonner gỡ toast Hoàn tác hiện lại trong 200 ms sau cú bấm (nay mã toast mới mỗi lần bấm); 3 gạt toast không bỏ cuốn khỏi hàng hoàn tác;
4 hoàn tác sang "<tên> (2)" mất dữ liệu nghe, cuốn chiếm chỗ nhận nhầm (nay chuyển mã; dự án trong chuỗi phần: 409 như cũ);
5 đổi tên lúc đã hết sách phát sự kiện "chapter" (nay "metadata"). Test: `trackMetadata.test.ts`, `nativeMetadata.test.ts`,
`trashUndo.test.ts`, `test_trash_undo.py`, JVM `BookMetadataTest`. Vitest 1223 passed + 1 skipped, exit 0; `tsc --noEmit` exit 0;
Gradle 1170 ca = 1164 passed + 6 skipped, 0 FAILED / 0 ERROR, exit 0 (137 XML); pytest toàn bộ (XML) 8385 ca, 9 skipped,
0 FAILED / 0 ERROR, exit 0, 1817,956 giây. Hash khoá trước/sau `49e8fd2d…` (không đổi).

Đợt a72fix (`dev/uxfix79`): sáu lỗi thư viện/trình phát có test đỏ trước sửa:
L1 media session còn nhãn cũ; L2 thư viện 226 cuốn không gọi nhớ cuộn;
L3 HTTP 409 khi đường khôi phục bị chiếm; L4 ba lần xoá không dùng toast chung;
L5 đóng trình phát chưa gỡ toast `jump`; L6 tab Chương dựng 2500 nút thay vì 80.
Test UI: `playerMetadata.test.tsx`, `libraryPlayerWindow.test.tsx`, `trashUndo.test.ts`,
và `nativeMetadata.test.ts`; test Python: `test_trash_undo.py`; JVM: `BookMetadataTest`.
Sau sửa, Vitest toàn bộ: 1217 passed + 1 skipped, 0 failed, exit 0; `tsc --noEmit`: exit 0.
Gradle `:app:testDebugUnitTest --max-workers=4 --offline`: 1168 ca = 1162 passed + 6 skipped,
0 FAILED / 0 ERROR, exit 0 (137 XML). Metadata Media3 thay nhãn và bìa của cả hàng đợi;
đoạn đọc to tiếp theo cũng lấy bìa mới. Hoàn tác dùng chung trên máy tính/điện thoại, mỗi mã giữ hạn riêng;
một mã lỗi không chặn các mã khác và vẫn có thể thử lại trong hạn.
Pytest toàn bộ (đếm XML): 8380 ca = 8371 passed + 9 skipped, 0 FAILED / 0 ERROR, exit 0,
1798,456 giây. Lượt này thu thập trước khi thêm ca mở lại app; file Hoàn tác được kiểm riêng thêm sau đó:
27 passed, 0 FAILED / 0 ERROR, exit 0 (18,585 giây), gồm ca app mở lại và đường gốc bị chiếm.
Có ba cảnh báo cùng loại đã ghi ở đợt a71: ZIP trùng tên; subprocess đọc cp1252 gặp UnicodeDecodeError;
máy chủ giả của `test_music_truncated_download` hết thời gian accept. Nguyên văn ở `S/a72fix/pytest-full.log`.
Hash khoá trước/sau: `49e8fd2dc212c7207cd0fbf66b308e6b0d1b49d220d64a16501d170bc906635f` (không đổi).
Compileall và `git diff --check` qua; nguồn đã giữ LF. CHANGELOG có sáu dòng sửa lỗi, xưng “bạn”.

Đợt a71fix (`dev/uxfix78`): bốn lỗi nhập sách/thư viện đã tái hiện bằng test đỏ trước sửa. Pytest mới:
13 FAILED / 0 ERROR trong 15 ca (hai ca font hợp lệ đã qua); Vitest importQueue: 3 FAILED / 17 passed;
JVM: 2 FAILED / 0 ERROR trong hai ca DRM và chữ hoa. Ca font không khai báo OPF được kiểm thêm: Python và JVM đều đỏ trước sửa bổ sung.
Sau sửa, bộ pytest liên quan: 209 passed / 0 FAILED / 0 ERROR,
exit 0; Vitest toàn bộ: 1207 passed, 1 skipped, 0 failed, exit 0; TypeScript `tsc --noEmit`: exit 0.
Bộ ví dụ chung có DRM mã hoá chương, rights.xml, sinf.xml, thuật toán font gắn vào chương, cùng font IDPF/Adobe hợp lệ (cả font không khai báo OPF).
Test nhập lại file gốc xác nhận chép bù chương mất/rỗng, giữ nguyên byte chữ; HTTP phân biệt mất chữ với chương không có chữ.
Huỷ đọc ngăn kết quả/lỗi cũ, không đi tiếp hàng hay mở file .abook phía sau. CHANGELOG có một dòng cho mỗi lỗi.
Hash khoá trước và sau: `49e8fd2dc212c7207cd0fbf66b308e6b0d1b49d220d64a16501d170bc906635f` (không đổi).
Kiểm CPU tối đa bốn lõi, CUDA tắt; Gradle offline dùng dependency cục bộ và `--no-daemon`, không dùng thiết bị hay Ollama.
JVM toàn bộ trên mã cuối (đếm XML): 1167 ca = 1161 passed + 6 skipped, 0 FAILED / 0 ERROR, exit 0.
Pytest toàn bộ trên mã cuối (đếm XML): 8380 ca = 8371 passed + 9 skipped, 0 FAILED / 0 ERROR, exit 0, 1549,9 giây.
Có ba cảnh báo: ZIP trùng tên trong test EPUB; luồng subprocess đọc cp1252 gặp UnicodeDecodeError; máy chủ thử của
test_music_truncated_download chờ accept hết hạn. Các vùng này nằm ngoài phạm vi sửa; nguyên văn ở log full-py-final.
Compileall, kiểm LF và `git diff --check` qua; tiến trình thử đã thoát hết.

Đợt pqfix B41 (`dev/pqfix`): xác nhận cả 5 lỗi bằng test đỏ trước sửa (resume hoà giải lại chương đã commit; NPC thiếu phạm vi
chương; câu đổi vai giữ giới/tuổi cũ; CLI cài thiếu tokenizer; kiểm digest rớt mạng không retry). Thêm 20 ca kiểm trong 5 file
`test_speaker_pass_reconcile_resume.py`, `test_speaker_pass_local_scope.py`, `test_speaker_pass_traits.py`,
`test_studio_setup_cli_tokenizer.py`, `test_speaker_pass_digest_transport.py`. Test qua BookPipeline.run, SQLite thật với
crash/reopen và migration DB cũ, HTTP/model giả; prompt vẫn dùng nhãn NPC không phạm vi. Không chạy Ollama/GPU hay tải mạng.

Pytest tuần tự trên CPU (CUDA_VISIBLE_DEVICES=-1, OMP/MKL/OPENBLAS/NUMEXPR_NUM_THREADS=4), toàn bộ test speaker_pass,
pipeline/resume, database, casting, studio_setup và analysis_replay: **898 passed, 0 FAILED, 0 ERROR, exit 0**, 390,57 giây.
Có 1 PytestUnhandledThreadExceptionWarning tại test_perceptual_qa_uses_unshifted_baseline_when_pitch_variant_was_skipped:
luồng subprocess._readerthread giải mã cp1252 gặp byte 0x90 (UnicodeDecodeError). Chưa sửa đường perceptual ngoài phạm vi này.
Suite Studio trên ổ D ban đầu vướng 5 test do chỉ còn 25 GB < ngưỡng cài 35 GB; basetemp chuyển sang scratchpad trên C,
26/26 test Studio qua, không đổi ngưỡng hay test. Compileall và git diff --check qua. Các file sửa giữ nguyên LF.

Hash triển khai chất lượng trước: `4da08e178713be1cb53bc34a9eb4edddd537c649da116bbf9a8e74c07757055f`;
sau: `922e4f135b7abfe4dd1060c722377a925ce5869e36e55fc002fb9edf87838b5a` (41 mục đọc từ QUALITY_IMPLEMENTATION_FILES).
Hash đổi nằm trên nhánh dev, chưa đưa sang production.

Truyện kể ngôi thứ nhất (nhánh `feat/narrator`, 2026-09-27): `voices.first_person_identity` giờ vào prompt phân tích mỗi
batch và dấu vân tay sổ ứng viên (chỉ khi có đặt); Studio hỏi "'Tôi' là ai?" ở bước chọn giọng khi ~20 chương đầu có >= 30%
đoạn lời kể chứa "tôi", kèm gợi ý tên. Test mới: `test_a_first_person_book_names_its_narrator_to_the_model.py` (prompt thật
gửi Ollama có dòng người kể; ngôi thứ ba và danh tính là đại từ thấy prompt + dấu vân tay y hệt trước) và
`test_first_person_question.py` (nhận ra truyện, "mình" phản thân không tính, câu trả lời lưu vào cài đặt sách, đại từ bị
từ chối) - 9/9 qua. Toàn bộ pytest: mọi test qua trừ `test_doctor_uses_actual_critical_dependency_and_runtime_contract_checks`,
hỏng vì worktree mới không có `runtime/` (file model VieNeu) - cùng test ấy qua trên cây chính. Kiểm bằng mắt trong
trình duyệt: YMP gợi ý Samael đầu tiên, bước xác nhận có dòng "Người kể 'tôi'"; TMA (ngôi thứ ba) chỉ có liên kết mở tay.
Đo trên model thật (docs/LLM_EVAL.md): LoRA 34,0% -> 89,4% người nói ở YMP 248 khi biết người kể.

Đợt sửa confidence contract V22: **634/634 test trọng tâm pass** cho analysis bắt buộc,
database safety và quality policy trên Python 3.11.9. Compileall cho source/test, `git diff --check`
và Ruff trên toàn bộ file bị ảnh hưởng đều pass; đợt này không chạy model/GPU hoặc pipeline audiobook thật.
Hardening sau bằng chứng V23 `“Ha…”` đã khóa critic schema/prompt theo durable floor, exact singleton target + source hash,
bỏ boolean accept khỏi model contract và tách reason confidence/rationale/quote; suite analysis + quality policy liên quan pass.
Hardening sau bằng chứng V24 giữ confidence derived/validated/commit của chapter heading structural-lock ở đúng `0.95`
trong cả agreement, structural override và batch trộn; raw critic confidence vẫn được lưu và vẫn phải qua durable floor,
còn content tiếp tục dùng `min(generator, critic, cap)`. Suite analysis/database/quality liên quan, Ruff, compileall và
`git diff --check` đều pass; đợt này không gọi model/GPU hay pipeline thật.
Hardening V27 sau failure thật tại seq18 dài 261 ký tự thay singleton substring tự do bằng tập source anchor deterministic:
contract khóa source SHA + anchor-set SHA/count, schema dùng exact enum và host chỉ nhận đúng membership. Regression dùng nguyên
text V26, biên 240/241 ký tự, short singleton và multi-row đều pass trong combined analysis + database + quality-policy suite;
đợt sửa này không gọi model/GPU hoặc pipeline audiobook thật.
Hardening V28 sau forensic V27 seq32 thay multi-row substring tự do bằng canonical ordered per-ID source-anchor map:
schema `items.oneOf` khóa từng nhánh vào exact ID + enum riêng, contract khóa map SHA/tổng anchor và host từ chối anchor
mượn từ ID khác. Narration dẫn ngay trước thought cùng chapter/paragraph giữ previous nhưng ẩn next thought khỏi critic
bằng policy source-bound riêng; generator vẫn thấy adjacent context và không có kind override. Regression dùng nguyên
seq31/32/33 V27, hai control khác paragraph/next dialogue và critic stub leak-sensitive đã pass trong combined
analysis + database safety + quality-policy suite **723/723**; Ruff, compileall và `git diff --check` cũng pass.
Đợt sửa không gọi model/GPU.
Hardening V29 sau failure thật V28 seq10 thêm authority nguồn hẹp cho motif bóng đè còn nhận thức nhưng bất lực:
predicate dùng chung với DB replay chỉ nhận grammar allowlist, cùng chủ thể và chuỗi cue liền mạch; phủ định, giả định,
meta, trích dẫn, affect đối nghịch, trạng thái đã giải quyết, chủ thể/tân ngữ mơ hồ và mọi tiền tố ngoài allowlist đều
fail-closed. Candidate khóa chính xác `kind=narration` + `emotion=afraid`; critic vẫn lưu nguyên verdict/delta thô và chỉ
compose override cho hai field đã khóa, còn `intensity/pace/speaker/volume` vẫn unresolved. Một verdict protocol-invalid
làm invalid toàn payload và retry cùng durable candidate. Regression exact seq10, negative adversarial, accepted/rejected
reserve/reopen/replay/commit và policy fingerprint đã pass **818/818** test trong ba file thay đổi; auditor độc lập không còn
P0/P1. Full repository **1.264/1.264** test, Ruff, compileall, `pip check` và `git diff --check` đều pass.
Runtime V29 chạy project sạch tới seq38: exact seq10 giữ `narration/afraid`, seq18 giữ đúng per-ID evidence và seq32 giữ
`narration_before_thought_previous_only`; mọi hash/candidate/critic/commit envelope kiểm lại hợp lệ. Lượt chạy dừng fail-safe
trước casting/TTS vì `hỗn loạn|thất thần` bị cue chung ép sai sang `afraid`, đồng thời source narration dẫn seq38 chưa có
kind lock nên generator/critic từng có thể đồng thuận relabel thành thought. Không có audio/casting dở được commit.
Hardening V30 tách đúng ba cue nhận thức mơ hồ thành lớp `disoriented`: vẫn chặn `happy` sai nhưng không từ chối `neutral`
hoặc phát `allowed_emotions`; explicit fear cùng câu vẫn hoạt động độc lập. Narration dẫn ngay trước thought cùng
chapter/paragraph trở thành kind-only source lock từ immutable original context ở cả generator và critic. Raw critic/delta
được giữ nguyên, override chỉ phủ `kind`, còn related stable ID/hash được bind và SQLite tính lại hash từ text khi
allocate/reopen/accept/commit; text-only tamper có stale hash bị chặn cho cả context mới và adjacent-wake semantic provenance.
Regression exact seq38, controls, composition, accepted/rejected replay/commit và tamper pass **845/845** test trong ba file
analysis/database/quality; auditor độc lập chạy 33 test và kết luận không còn P0/P1. Full repository **1.291/1.291** test,
Ruff, compileall, `pip check` và `git diff --check` đều pass trước runtime V30.
Runtime V30 chạy project sạch tới 24/107 segment rồi dừng fail-safe ở seq24 trước casting/TTS. Forensic cho thấy target là
narration không có câu hỏi, nhưng critic ở batch 1-2 dòng gọi nó là “câu hỏi bối rối” do mượn source thought seq25 đang lộ
trong `next_text`; ở batch lớn chính critic từng đồng ý cả delivery neutral lẫn afraid. Không có bằng chứng để khóa
emotion/intensity/pace hoặc nới kind authority qua mọi paragraph; project V30 không được resume sau khi policy đổi.
Hardening V31 thêm policy riêng cho narration đứng ngay trước thought ở paragraph kế tiếp: chỉ critic bị xóa `next_text`,
generator vẫn thấy adjacent context và policy mới không tự tạo kind/semantic lock hay override. Critic chỉ correction khi
candidate không tương thích, không correction vì một phương án khác cũng hợp lý; cue `disoriented` đơn lẻ vẫn cho phép
neutral, intensity 0/1 và pace normal. SQLite tính lại context hash từ current + neighbor stable ID, text SHA, chapter,
seq, paragraph và kind khi allocate/reopen/critic completion/commit; injected policy, lock, override và source tamper đều
fail-closed, còn semantic lock độc lập vẫn compose. Regression analysis/database/quality pass **886/886**, full repository
**1.332/1.332**; Ruff, compileall, `pip check`, `git diff --check` và hai audit độc lập đều sạch trước runtime V31.
Hardening V32 sau failure thật ở seq43 giữ source unit nguyên tử qua ranh giới batch: lời dẫn seq42 cùng paragraph và phần
ngoặc kép ngoài tiếp tục qua seq43–44 được đóng gói chung `[42,43,44]`, trong khi prefix thành `[38,39,40,41]`. Retry của
profile high-quality không cắt một source unit hội thoại không quá cap 5; unit vượt cap vẫn hard-split hữu hạn. Source
`kind_hint=dialogue` tạo kind-only lock bền; critic dissent trên kind được audit/override theo exact source, nhưng speaker
không bao giờ được lock che và vẫn fail-closed nếu còn delta. SQLite dựng lại text/hash/kind/lock khi allocate, reopen,
critic completion và commit, đồng thời từ chối evidence thiếu lock, giả rule hoặc giả covered/unresolved partition.
Regression exact seq42–44 cùng database replay/tamper và quality policy pass **897/897**; full repository **1.343/1.343**,
Ruff, compileall, `pip check`, `git diff --check` đều pass. Mọi test đều gọi interpreter rõ ràng; `OpenWith.exe` giữ **0**.
Runtime V32 dùng project sạch đã checkpoint 24/107 segment rồi dừng fail-safe trước casting/TTS ở exact seq24. Target
chỉ có cue active `hỗn loạn`, không có câu hỏi; cùng delivery `neutral/0/normal` từng được critic đồng ý trong batch,
nhưng các lượt singleton lại bịa “câu hỏi bối rối” và ép `afraid`, intensity `2|3`, pace `fast`. Project V32 không được
resume sau khi policy đổi và không có audio/casting dở được commit.
Hardening V33 thêm compatibility override source-bound duy nhất cho trường hợp này: source phải là narration/NARRATOR,
chỉ có cue active `disoriented`, không có dấu hỏi/cảm thán; candidate phải `neutral`, intensity `0|1`, pace/volume
`normal`; critic chỉ bị bác khi suy diễn đúng `afraid` kèm ít nhất một escalation intensity hoặc pace và toàn bộ delta
nằm trong `emotion,intensity,pace`. Cue affect khác, emotion khác, delta kind/speaker/volume, intensity không tăng hoặc
pace không thành fast đều giữ fail-closed. Verdict/delta thô vẫn được lưu; SQLite dựng lại exact rule từ source/hash,
candidate, critic và partition khi completion/reopen/commit, đồng thời từ chối override thiếu/giả hoặc xuất hiện trong
rejected evidence. Analysis/database/quality pass **908/908**; full repository **1.354/1.354**; Ruff, compileall,
`pip check`, `git diff --check` đều pass và `OpenWith.exe` giữ **0** trước runtime V33.
Runtime V33 dùng project sạch đã dừng fail-safe ở 8/107 segment, trước casting/TTS. Forensic exact batch seq8–11 cho thấy
parent đã tích lũy đúng correction cho seq9 và host lock `afraid` cho seq10, nhưng sau khi tách `[8,9,10] + [11]`, child
không nhận feedback của parent: ba lượt retry luân phiên sửa seq9 rồi làm seq10 quay về `sad`, nên host từ chối. Source unit
seq8–10 vẫn được giữ nguyên tử; project V33 không được resume sau khi fingerprint analysis đổi.
Hardening V34 khóa `allowed_emotions` source-authoritative của host theo từng request ID ngay trong schema generator
`segments.items.oneOf`; nhiều constraint cùng ID lấy giao, giao rỗng fail-closed trước HTTP, còn semantic choices vẫn chỉ
là advisory và không thu hẹp enum. Mọi đường split dùng chung một hàm lọc feedback typed theo `stable_id` và chuyển nó vào
đúng child, nên correction của câu khác không rò sang child và host lock đã có không bị mất. Policy nâng lên
`analysis_ledger_v19`, `per_id_host_emotion_enum_v1`, casting stage v22/algorithm v23. Regression schema per-ID,
intersection/conflict, semantic non-lock và split carry pass trong analysis/database/quality **911/911**; full repository
**1.357/1.357**; Ruff, compileall, `pip check`, `git diff --check` đều pass và `OpenWith.exe` giữ **0**. Runtime V34 chưa
được tính vào các kết quả này.
Runtime V34 dùng project sạch đã chứng minh hai sửa đổi trước hoạt động thật: child `[seq8,seq9,seq10]` nhận feedback cha,
pass ngay lượt đầu sau split và giữ exact seq10 `narration/afraid`; exact seq24 giữ
`narration/NARRATOR/neutral/0/normal`, raw critic vẫn ghi câu “câu hỏi bối rối” cùng delta `afraid/2/fast`, còn compatibility
override V33 được dựng lại đúng. Lượt chạy sau đó dừng fail-safe ở 25/107, trước casting/TTS, tại exact thought seq25
`‘Đây rốt cuộc là nơi nào?!`: generator chỉ nhận tên field mismatch nên qua nhiều batch/singleton vẫn trả neutral, trong khi
critic lặp correction `afraid|surprised`, intensity `2|3`, pace `fast`. Project V34 không được resume sau khi policy đổi.
Hardening V35 thêm `suggested_values` advisory typed cho `DIRECTOR_FIELD_MISMATCH`, chỉ cho phép enum/số canonical của
`emotion|intensity|pace|volume`; không chuyển kind, speaker, source, quote hay rationale và không thu hẹp schema như HOST.
Projection delivery đã sửa được giữ qua retry/split vì mỗi request sinh lại từ đầu; correction critic mới ghi đè đúng field
nó thay đổi nhưng không làm field vừa được critic đồng ý quay về mặc định. Policy nâng lên `analysis_ledger_v20`,
`per_id_host_emotion_director_advisory_v2`, casting stage v23/algorithm v24. Regression exact seq25, projection nhiều lượt,
split carry, advisory non-lock và payload độc hại/sai kiểu pass trong analysis/database/quality **917/917**; full repository
**1.363/1.363**; Ruff, compileall, `pip check`, `git diff --check` đều pass và `OpenWith.exe` giữ **0**. Runtime V35 chưa
được tính vào các kết quả này.

## Tổng hợp hardening và runtime V36–V43 (2026-08-24)

Hardening V36–V43 khóa retry khi `neutral` bị cue trực tiếp bác bỏ bằng rejection/advisory typed theo đúng ID, đồng thời
khóa `speaker` trong schema director vào exact speaker của candidate thay vì cho model phát sinh identity mới. Ledger hiện
ở `analysis_ledger_v26`/casting ledger v28; DB dùng aggregate validator chung cho state machine và mọi public read/mutation,
kiểm lại generator-contract history, critic-attempt history liên tục, terminal/superseded state và replay payload trước/sau
transition. High-quality ASR tăng immutable clarity repair budget từ **3 lên 5** và đưa giá trị này vào quality policy.

Runtime sạch V40 kết thúc **101 verified / 1 warning / 5 failed**. Runtime sạch V43 cải thiện thành
**102 verified / 1 warning / 4 failed**; exact `seq84` được cứu ở clarity round 3. Exact `seq99–101` cùng giữ provenance
speaker `NPC_LOCAL::c00001::rf4306ee4f88ce933::người phụ nữ áo đen`. Ở exact `seq45`, candidate `neutral` cho cue
“vẻ tự hào” bị rejection contract loại và lượt sau commit `happy/intensity=2/pace=normal`. V43 promotion đúng
**8 clarity + 4 perceptual**, chạy **3039.802 giây**, giữ `OpenWith.exe=0`; bốn segment fail vẫn chặn chapter nên không
xuất MP3, đúng fail-closed.

Sau V43, repeated-short ASR đã đổi khoảng lặng giữa ba bản sao từ **0,24 lên 0,50 giây**; các probe phát âm standalone
trên artifact đích cho kết quả tốt hơn mà không đổi content/timeline gate. Runtime sạch V44 sau thay đổi này kết thúc
**100 verified / 2 warning / 5 failed** trong **3156,396 giây**. Exact seq17 được dual-pass ngay round 0, còn seq106
chứng minh nhánh `source_spelling_v1` có thể sửa `Lucien` và promote an toàn. Tuy nhiên policy V44 vẫn luân phiên source
ở mọi round lẻ chỉ vì segment có locked name; seq43 và seq64 là lỗi content nhưng vẫn mất round 1 cho source, và seq43
kết thúc fail dù candidate canonical mới có thể cứu được.

## Evidence-gated pronunciation repair và runtime V45 (2026-08-24)

V45 chỉ cấp `source_spelling_v1` khi **candidate ngay trước đó** có đủ hai decode beam/greedy bền trong SQLite và ít nhất
một decode đã adjudicate đúng `ASR_LOCKED_NAME_ANCHOR_MISMATCH`. Evidence phải khớp policy hiện hành, incumbent SHA,
voice profile, selected decode, quality-check metrics/failure codes và locked-anchor metrics v2; evidence thiếu, stale,
méo hoặc bị sửa đều fail-closed. Lỗi content thuần giữ `locked_spoken_v1` và seed canonical; policy ASR nâng thành
`evidence_gated_name_pronunciation_delivery_v8`.

Full repository **1.438/1.438**, Ruff, compileall, `pip check` và `git diff --check` đều pass. Runtime sạch V45 dùng cùng
manifest `375bd57ab4ee8230d2ecb74da67bb526446f5a36f5a031ebfb40d5d6fceb1a6a`, kết thúc
**101 verified / 2 warning / 4 failed** trong **3150,150 giây**. Exact seq43 giữ canonical ở round 1, dual-pass rồi
được UTMOS xác minh/promote; seq64 giữ canonical ở round 1 và chỉ chuyển source ở round 3 sau khi greedy round 2 thật sự
ghi locked-name mismatch; seq106 vẫn chuyển source ở round 1 và đạt beam/greedy `1,0 similarity / 0,0 WER` trước promote.
Perceptual repair cũng cứu exact seq18 bằng candidate round 0 qua cả hai Whisper và UTMOS.

Hai warning cuối là seq8 `PERCEPTUAL_NATURALNESS_REVIEW` và seq83 `TTS_GENERATION_CEILING_REACHED`; bốn failure là
seq35/44/65 locked-name mismatch và seq64 content mismatch. SQLite schema v9 trả `integrity_check=ok`, không có lỗi khóa
ngoại; quality report được xuất, `validate --require-complete` từ chối publish và **0 MP3** tồn tại đúng fail-closed.
Sau khi worker thoát không còn Python/Ollama/FFmpeg con và `OpenWith.exe` giữ **0**.

Setup chỉ cài runtime dependency/model và chạy system check trên máy đích trước khi ghi marker hoàn tất;
pytest/Ruff không được cài hoặc chạy trong luồng mở app của người dùng.

## Immutable repair hardening và runtime V48 (2026-08-29)

Hardening sau V45 tách contract ASR/perceptual/TTS thành module độc lập, khóa lại provenance của mọi candidate và
checkpoint repair. Clause recovery có hai strategy bất biến: `sentence_v1` tối đa 170 ký tự và `clause_v1` tối đa
120 ký tự; final source-spelling candidate chỉ dùng clause split khi evidence trước thật sự yêu cầu. Root seed được
tính lại từ stable ID + voice key + salt canonical, từng part seed được tính lại từ stable ID part + exact prefix;
SQLite từ chối root/part seed, strategy, max chars, thứ tự, checksum text, voice, pitch hoặc pronunciation variant bị
sửa. Token đơn dài hơn giới hạn không còn làm worker crash: allocator nhận biết split không khả dụng và giữ finite
fallback, còn checkpoint đã cấp phát vẫn fail-closed bằng candidate TTS failure có thể resume.

Mọi candidate `dual_failed` và exhaustion summary giờ được dựng lại từ quality-check gốc thay vì tin JSON tổng hợp đã
lưu. Beam/greedy, failure code, selected result, ASR/signal blocker, UTMOS result và terminal reason đều được kiểm lại;
tamper một check, kết quả perceptual hoặc lý do exhaustion bị từ chối trước resume/finalize. Trường hợp ASR đã pass nhưng
UTMOS vẫn review hết budget kết thúc bằng `PERCEPTUAL_NATURALNESS_REVIEW`, không bị ghi nhầm thành ASR failure.

Delivery `ha_vocalization_v2` giới hạn 23 frame, temperature/top-p thận trọng và không còn chèn silence giả để đạt độ dài.
Raw/target/final sample count, padding bằng 0, sample rate, cap và endpoint-active được lưu, kiểm lại và xuất report.
Exact seq8 V48 bắt đầu bằng waveform 1,84 giây chạm trần; candidate round 1 tạo waveform 1,44 giây, không chạm endpoint,
beam/greedy cùng pass rồi được promote với transcript `Ha ha, ha!`.

Audit tiếp ngày 2026-08-30 nâng schema lên v11 và tách `generation_strategy=direct_v1|split_v1` thành ledger field bền,
không còn suy ra split chỉ từ seed. Strategy chỉ được chuyển một chiều direct -> split trong checkpoint generating và
bất biến sau khi signal đã commit; xóa toàn bộ split provenance đồng thời đổi root seed sang lịch direct vẫn bị từ chối.
`perceptual_required` có trigger bất biến và được đối chiếu lại với `settings.perceptual_qa.enabled` của quality policy
đã khóa khi allocate/resume/promote, kể cả caller gọi thẳng promotion API mà bỏ qua resume plan; sửa `true -> false`
không thể bỏ qua UTMOS. Direct promotion cũng kiểm lại split/vocalization/delivery provenance ngay trong cùng transaction.
Với profile `ha_vocalization_v2`,
WORLD pitch không được phép zero-pad: output pitch ngắn hơn bị bỏ, waveform thô được giữ, và coordinator hậu kiểm exact
sample count trước khi ghi provenance.

Runtime sạch V48 dùng lại manifest
`375bd57ab4ee8230d2ecb74da67bb526446f5a36f5a031ebfb40d5d6fceb1a6a`, cold bootstrap được đợi tối đa 120 giây.
Worker bị dừng sau checkpoint **59/107** rồi resume thế hệ kế tiếp mà không làm lại phần đã commit. Kết quả cuối là
**104 verified / 1 warning / 2 failed**, tốt hơn V45 **+3 verified / -1 warning / -2 failed**. Exact seq44 đi đủ năm
candidate, final source + `clause_v1` giữ nguyên văn bản thành bốn part dài **53/111/40/102** ký tự nhưng `Wayne` vẫn bị
nhận sai nên kết thúc `ASR_LOCKED_NAME_ANCHOR_MISMATCH`. Exact seq64 giữ đúng locked `A-đe-ron`; candidate cuối có beam
canonical pass nhưng greedy vẫn content mismatch nên kết thúc `ASR_MISMATCH_UNRESOLVED`. Exact seq83 là warning duy nhất
`TTS_GENERATION_CEILING_REACHED` với ASR đúng `Điên rồi!`.

Các probe đối chứng sau runtime không được đưa vào policy: hạ clarity temperature/top-p làm seq64 kém hơn, chia câu sau
`Aderon` làm nửa đầu kém hơn, và seed repair thứ sáu làm cả seq44/64 kém hơn. Vì vậy budget vẫn hữu hạn 5 round, dual gate
vẫn giữ nguyên, không đổi voice, không hạ threshold và không promote artifact chỉ có một decoder pass.

SQLite V48 thật được kiểm raw read-only, vẫn ở schema 10 và không bị migrate: `integrity_check=ok`, `foreign_key_check`
rỗng, worker lease rỗng sau exit; quality report đã xuất nhưng chapter bị hai failure chặn nên **0 MP3**, đúng fail-closed.
Bản sao calibration migrate lên schema 11 thành công, dựng lại đủ **34 candidate summary / 14 segment**, backfill
**33 direct / 1 split**, `integrity_check=ok` và foreign key bằng 0. Full repository **1.552/1.552** test pass; Ruff toàn
source/test, compileall, `pip check`, `git diff --check` đều pass. Tất cả Python trong runtime và validation đều được gọi
bằng interpreter `.venv` rõ ràng; sau toàn bộ run/probe `OpenWith.exe` giữ **0**.

## Phạm vi tự động

- CLI headless tạo exact numeric range inclusive, dry-run không ghi dữ liệu, đọc status/report/log qua SQLite read-only,
  chạy component test, validate artifact QA và phát JSON/exit code UTF-8 ổn định kể cả database hỏng;
- supervisor nền không mở console, redirect log, khóa double-start, xác minh PID/create-time/project/token,
  chỉ handshake READY sau worker bootstrap, giữ stop request bền qua process độc lập và chặn force-stop ABA;
- creation lock serialize hai lệnh tạo cùng manifest/title nhưng khác settings; recovery bỏ qua namespace control
  `runtime/background` để không xóa state/handshake atomic đang được ghi;
- settings bất biến và cấm prompt/silent replacement;
- import nhiều TXT hoặc folder, natural sort và loại file không hợp lệ;
- one-click startup qua shortcut `ABook` ở root/Start Menu trỏ thẳng tới `_internal\ABook.vbs`;
  console hiện ngay, báo tiến độ và tự đóng theo ready marker do GUI ghi sau khi render;
  output được append vào `runtime/logs/startup.log`, boundary ngoài cùng bắt lỗi và giữ console mở cho tới khi
  người dùng chủ động đóng; runtime cũ thiếu dependency chỉ chạy repair Python, không cài lại PyTorch/model;
- single-instance dùng local IPC: lần mở thứ hai chỉ kích hoạt/đưa cửa sổ đang chạy lên trước rồi đóng launcher;
- system tray có hành động hiện/ẩn/thoát hoàn toàn; nút `X` chỉ ẩn và giữ worker chạy, còn thoát từ tray
  kết thúc cây worker ngay;
- GUI không còn tiêu đề lớn, tự đổi nút `Bắt đầu`/`Tiếp tục`, tự mở project được chọn gần nhất;
  `Bắt đầu` bị vô hiệu hóa khi chưa có chapter nguồn và mỗi dòng Log có timestamp;
  nút chọn TXT/folder vẫn dùng được khi project cũ đang dừng và chuyển sang book mới sau khi chọn nguồn;
  khối `Thiết lập` chỉnh được ngay sau khi mở lại và thay đổi sẽ tạo project mới theo settings hash;
  thêm/xóa TXT tạo draft mới mà không sửa sách cũ; bốn nút nguồn có cùng kích thước; danh sách/bảng
  có alternate-row tối hơn nền thường và selection dùng đúng màu highlight của ô Log kể cả khi mất focus;
  nested splitter và từng cột tiến độ kéo được, kích thước cột được lưu, đường dẫn MP3 không bị elide;
  nhấn lặp vào ô MP3 dài không làm bảng tự kéo thanh cuộn ngang sau độ trễ double-click;
  nút chính tự đổi `Bắt đầu`/`Tạm dừng`/`Tiếp tục`, chỉ còn một nút `Dừng` riêng và chỉ xuất MP3
  theo từng chapter nguồn; WAV checkpoint bắt buộc được giữ nội bộ, không hiển thị như một tùy chọn;
  đóng cửa sổ kết thúc cây worker mà không đợi checkpoint;
- bảng chapter hiển thị riêng tiến độ phân tích, tạo audio, kiểm tra, giai đoạn và MP3;
- double-click ô MP3 trống không mở Explorer;
- progress event bao phủ chuẩn bị văn bản, TTS, Whisper, repair, ghép chapter và xuất báo cáo;
- analysis dùng ID ngắn bị ràng buộc theo batch rồi ánh xạ chính xác về stable ID;
- Ollama analysis chạy dạng stream có thể hủy khi dừng, giới hạn schema/token/wall-time và ghi
  heartbeat vào Log mỗi phút để không còn im lặng trong một request dài;
- stream analysis thiếu gói kết thúc được phân loại riêng và tự chia đôi batch ngay; batch con giữ nguyên
  checkpoint/progress, còn stdout/stderr của Ollama ẩn được nối vào `runtime/logs/ollama-server.log`;
- semantic delivery gate từ chối output Qwen đúng schema nhưng suy biến: batch `happy` mâu thuẫn hàng loạt hoặc
  template `neutral/intensity=0/normal` phủ lên nhiều cue cảm xúc rõ ràng; evidence ghi
  đúng cụm từ đã khớp, retry có feedback theo đúng ID rồi chia đôi hữu hạn; batch vui thật, narration trung tính,
  mixed-affect và cue nằm trong phủ định/ngăn cấm cục bộ vẫn được chấp nhận; template neutral-zero vẫn bị chặn
  riêng sau khi batch đã chia dưới 8 segment và kết thúc bắt buộc ở singleton thay vì checkpoint dữ liệu suy biến;
- cue `thất thần|bàng hoàng|hỗn loạn` được giữ ở lớp `disoriented` chống happy, không còn ép neutral thành afraid hay
  phát allowed-emotion advisory; cue sợ hãi rõ ràng cùng câu vẫn được xét độc lập;
- critic self-review chỉ có thể bị compatibility override ở đúng narration/NARRATOR `disoriented`-only, không có dấu
  hỏi/cảm thán, candidate neutral low-arousal và correction `afraid` tăng intensity hoặc pace; exact evidence source/hash,
  candidate/critic/delta được DB replay, mọi correction ngoài contract vẫn fail-closed;
- compound gate từ chối narration phẳng khi cùng một segment có cả tổn thương phổi/yết hầu và ý thức mơ hồ, nhưng giữ
  neutral cho suy kiệt thể chất hoặc quan sát lâm sàng đơn lẻ để không biến keyword gate thành đạo diễn cảm xúc rộng;
- host affect nguồn hẹp được adjudicate trước semantic cue chung và mọi constraint typed đã xác minh được tích lũy trong
  cùng target group, nên retry sửa câu sau không làm câu trước quay lại delivery đã bị từ chối;
- neutral bị semantic cue chung từ chối nhận `allowed_emotions` advisory là hợp deterministic các emotion tương thích với
  cue trực tiếp của chính source. Payload typed không mang source/cue/rationale; phủ định, historical/meta, affect đối nghịch,
  distressed chung và physical/host-rule không tạo lựa chọn này. Non-neutral không bị exact-membership gate hay auto-mutation,
  và candidate retry vẫn phải qua nguyên validation cùng director critic;
- hai rule narration hẹp cho nỗi sợ còn dai dẳng khi hồi tưởng và trạng thái sững người đầu óc trắng xóa dùng chung predicate
  source-only với DB replay; chúng khóa `kind=narration`, gửi allowed emotion typed theo đúng ID, không lan từ hàng xóm và
  vẫn bắt model trả candidate mới trước director critic;
- rule narration bóng đè/bất lực chỉ nhận đúng grammar tiền tố allowlist và chuỗi cue cùng chủ thể, source-only; nó khóa
  `kind=narration` + `emotion=afraid`, không relabel lời kể “cậu biết... muốn...” thành thought và fail-closed với mọi
  tiền tố/chủ thể/phủ định mơ hồ;
- semantic lock bền khóa affect rule vào source hash và critic candidate. Lock một field chỉ override đúng delta field đó;
  lock bóng đè được compose riêng source-kind + emotion nhưng vẫn giữ raw verdict/delta, còn mọi delta delivery khác bị chặn.
  Agreement luôn được host suy từ sáu field; protocol-invalid ở bất kỳ row nào làm invalid toàn critic payload;
- dialogue và thought boundary đã được source parser nhận diện là source-owned: model không được đổi chúng sang loại khác để
  né speaker/semantic lock. Narration dẫn ngay trước thought hoặc khớp semantic narration bắt buộc cũng source-owned;
  narration thường vẫn có thể được nâng thành implicit thought để giữ compatibility;
- `notes` và `personality_hint` tự do không còn thuộc output model hay acceptance envelope. Host tạo `delivery_note_v1`
  chỉ từ delivery đã kiểm; segment note không chứa marker điều khiển và marker repair tạm bị xóa trước candidate. Projection
  analysis đã chấp nhận nằm trong ledger+critic source-bound; bước casting chỉ reconcile speaker bằng transform source-derived,
  deterministic và có fingerprint stage riêng. DB tính lại và từ chối note/personality/marker không canonical khi allocate,
  reopen, direct update và commit. Character registry không còn dùng prose delivery làm personality hay marker legacy làm
  quyền điều khiển identity, và speaker repair không sao chép note lân cận;
- high-quality director critic chạy lượt self-review thứ hai mà không thấy confidence/notes/personality của generator;
  content generator confidence dưới floor bị feedback typed và retry trước mọi critic/ledger allocation; schema/prompt mang
  floor ở batch không có heading, còn batch hỗn hợp giữ schema floor `0` để proposal confidence thô của heading vẫn tới host.
  Contract critic khóa cả floor/cap và evidence policy. Singleton có target dài 1..240 ký tự dùng
  `singleton_full_target_v1`, exact source SHA và enum quote bằng toàn target; singleton dài hơn dùng
  `singleton_source_anchor_enum_v1`, exact source SHA + deterministic anchor-set SHA/count và enum chỉ gồm source anchor
  nguyên văn không quá 240 ký tự; multi-row dùng `per_id_source_anchor_enum_v1`, ordered map SHA/tổng anchor và
  `items.oneOf` khóa exact ID + enum riêng, không còn union/substr tự do.
  Model không còn trả boolean accept: host suy agreement từ sáu field không delta, correction từ field delta, rồi chỉ lưu
  `critic.accept` compatibility bằng đúng kết quả host-derived. Root/item thừa, ID thiếu/trùng/lạ, string thay số, NaN/Inf,
  confidence dưới ngưỡng, rationale lỗi và quote lỗi có category durable riêng;
  candidate hash, exact field agreement và confidence cap được kiểm tra trước checkpoint, còn deterministic semantic gate
  luôn có precedence vì critic cùng Qwen là correlated self-review chứ không phải model độc lập;
- source thought được gửi riêng cho critic theo `previous_context_only`: giữ lời dẫn trước nhưng xóa `next_text`.
  Narration dẫn ngay trước thought cùng chapter/paragraph dùng `narration_before_thought_previous_only`, giữ previous nhưng
  ẩn thought kế tiếp để critic không mượn affect. Kind narration được khóa từ immutable original context ngay trong generator
  và critic; bất đồng critic chỉ override đúng kind, giữ raw delta, khóa related stable/hash và tính lại hash từ source text
  trên mọi replay/commit. Narration/dialogue còn lại vẫn dùng adjacent context, generator vẫn giữ đủ adjacent context.
  Regression V21 seq13, V27 seq31/32/33 và V29 seq37/38/39 khóa split singleton, hash/contract resume source-bound,
  text-only tamper và ngăn cue tương lai bị mượn sang target;
- host affect gate khóa hẹp hai beat tự-bảo-toàn: thought có cue tử vong trực tiếp và wake/self-rescue thought liền kề;
  feedback là JSON typed/whitelist không chứa source/rationale tự do, trường hợp third-party/meta/khác chapter-paragraph không
  bị lan cue. Context/group fingerprint bao gồm stable ID, source hash, chapter, paragraph, kind và hai hàng xóm;
- tiêu đề chương thật được nhận diện hẹp bằng vị trí/metadata/grammar, canonical thành narrator trung tính với candidate
  confidence `0.95`, đồng thời giữ proposal confidence thô trong structural audit, rồi gửi critic theo `target_only` không có
  neighbor text. Critic confidence thô vẫn phải qua floor và được lưu để audit, nhưng confidence derived/validated/commit
  của heading đã khóa luôn giữ đúng `0.95`; bất đồng delivery thô
  trên riêng heading được lưu cùng structural override, còn bất đồng hoặc quote sai ở content vẫn từ chối cả batch;
- schema v8 lưu acceptance envelope đầy đủ, projection hash mà critic nhìn thấy, mọi generator contract và critic intent/outcome.
  Intent được reserve trước HTTP; protocol-invalid retry đúng candidate với seed mới, field mismatch lặp projection thì chia
  batch hữu hạn, còn crash sau `critic_accepted` resume/commit không gọi Ollama. Hash JSON, quan hệ parent-child, attempt liên tục,
  exact confidence `min(generator, critic, cap)` cho content cùng ngoại lệ deterministic heading khóa ở `0.95`,
  evidence policy/full-target SHA/anchor-set SHA/count, source role/seq/paragraph/kind/text và
  model/policy/context CAS đều được kiểm
  tra lại khi đọc/commit; forged content override, quote lấy từ row khác và structural clearance bị sửa đều fail-closed;
- resume coi durable analysis candidate là checkpoint đã bắt đầu ngay cả khi segment vẫn `pending`, vì vậy casting fingerprint
  mới không thể tái dùng ledger critic theo contract cũ;
- Ollama model name/digest được khóa bền theo book và đối chiếu trước/sau mọi request generator, critic và name review;
  digest đổi giữa request/resume fail-closed. Batch segment, pronunciation proposal và event ACCEPTED commit cùng một
  transaction CAS; regression trigger/reopen chứng minh lỗi event rollback cả segment lẫn pronunciation. Legacy
  high-quality đã có checkpoint trước critic bị từ chối để tránh trộn hai contract analysis;
- Ollama server do worker tự khởi động chạy ẩn, được theo dõi quyền sở hữu và chỉ tiến trình do app tạo
  mới bị dừng sau giai đoạn phân tích;
- project lock, voice profile lock và resume;
- Resource Manager: foreground, RAM, SSD và stop policy; RAM critical đơn lẻ unload model/cache, đo cưỡng bức
  lại và chỉ dừng nếu lần đo sau thu hồi vẫn critical;
- recovery: kill khi đang ghi `.part`, kill sau atomic replace nhưng trước SQLite commit, checksum và
  giữ nguyên WAV/MP3 đã commit hợp lệ;
- settings tamper, source mutation và khóa độc quyền một worker/project;
- source đổi cùng kích thước trong cửa sổ đọc, CP1258/UTF-16 không BOM và tên output an toàn;
- warning code hợp nhất và pronunciation ưu tiên confidence cao;
- chuẩn hóa tên tiếng Anh thu thập cả tên chỉ xuất hiện một lần; CMUdict nhận diện tên phổ biến và cung cấp
  ARPAbet bắt buộc Qwen trả cách đọc thuần Việt, còn từ/tên Việt bị loại theo ngữ cảnh; pronunciation chuyên biệt
  được khóa trong SQLite, áp dụng dưới mọi confidence threshold và không thể bị lần phân tích sau ghi đè;
- required-analysis batch failure không được fallback ngầm;
- stereo WAV bị từ chối, ASR optional chuyển lỗi inference thành warning;
- cụm từ đặt trong ngoặc kép không bị nhận nhầm thành hội thoại, segment chỉ có dấu câu không đi vào TTS;
- cụm cảm thán (`ha...`, `haiz...`, `hừm...`) và từ tượng thanh (`rầm`, `uỳnh`...) giữ nguyên trong câu
  narration/dialogue/thought; parser không tạo kind hiệu ứng riêng;
- `spoken_text` chuẩn hóa cách viết kéo dài và chuyển thẻ VieNeu thử nghiệm thành âm tiết có thể đọc, trong khi
  văn bản/hash nguồn không đổi; cùng `spoken_text` được dùng cho TTS và expected ASR;
- `Ha...`, `Aaaaah`, `Uuu` được đổi thành âm tiết ổn định; output VieNeu chạm đúng trần frame được giữ để
  signal/Whisper kiểm tra thay vì bị từ chối cơ học;
- mọi nội tâm bị ép về `NARRATOR` bất kể Qwen trả tên nhân vật nào và không phát warning danh tính;
- câu một từ ngắn bị giới hạn 24 frame, dùng sampling thận trọng và vẫn là ứng viên ASR repair;
- transcript Whisper có số từ không thể tồn tại trong thời lượng WAV được nhận diện là verifier hallucination;
- transcript Whisper kéo dài vô lý vào phần đệm 30 giây của model cũng được nhận diện là verifier hallucination,
  thay vì làm hỏng một vocalization ngắn có waveform hợp lệ;
- circuit breaker reset sau TTS thành công và không cộng dồn failure giống nhau nằm rải rác ở nhiều chapter;
- lần tạo lại audio xóa ASR/TTS warning cũ nhưng giữ warning phân tích; recovery đưa segment đã có
  analysis/voice profile về `analyzed`, không phân tích và phân vai lại rồi làm đổi giọng nhân vật;
- ngân sách frame và validator dùng chung một duration policy dựa trên codec VieNeu v3 3.840 sample/frame;
  ma trận kind/pace/độ dài chứng minh mọi ngân sách sinh đều còn headroom validation và không audio nào bị
  fade-out để lách kiểm tra;
- giới hạn frame VieNeu thay đổi theo độ dài/pace để câu ngắn không chạy tới trần model; lệch pace nhẹ
  trở thành warning còn sai lệch cực đoan vẫn bị từ chối;
- nhánh kết thúc còn chapter lỗi gửi Windows notification, giữ `BookStatus.ERROR`/checkpoint và worker phát
  `finished.ok=false` thay vì báo thành công;
- NPC có nhãn cục bộ giữ identity riêng, NPC vô danh tách nam/nữ; phân vai loại hoàn toàn preset tin tức,
  ưu tiên cao nhất giọng tự nhiên miền Bắc → tự nhiên miền Nam, giữ thứ tự cũ cho các giọng còn lại và chỉ đưa giọng
  Trung vào pool NPC ngắn;
- dropdown kể chuyện chỉ hiện tên của đủ 10 preset không phải tin tức; bộ lọc giới tính và miền không làm thay đổi
  preset đang chọn nếu preset đó vẫn còn trong kết quả lọc; label `Giọng kể chuyện` là header foldout có
  chevron style dropdown ở đầu, bên dưới lần lượt là nghe thử, giới tính và miền, thụt khoảng bốn ký tự;
  Phạm Tuyên và Ngọc Linh đứng đầu danh sách; hai dòng filter ẩn khi narrator bị khóa nhưng preview vẫn hiện;
- thay đổi narrator trực tiếp tự phát preview, nút preview phát lại; 10 WAV không phải tin tức được đóng gói
  bằng package-data và mapping preset nào cũng phải trỏ tới file tồn tại;
- profile chất lượng và narrator được khóa theo sách; resource mode và ngưỡng GPU là global, không detach
  sách đang mở và có thể cập nhật AdaptiveResourceManager khi worker đang chạy; `Sách mới` reset profile,
  bộ lọc và narrator về mặc định nhưng giữ nguyên resource mode và ngưỡng GPU; nút chỉ bật khi đang mở
  một project đã tồn tại và tắt trong bản nháp sách mới chưa chạy;
- cùng normalized speaker name giữ nguyên preset và biến thể cao độ; median F0 của 10 preview được đo để khóa
  pitch âm theo preset: Phạm Tuyên `0`, Xuân Vĩnh/Thái Sơn/Ngọc Trân `-1`, các preset còn lại `-2`;
  test tín hiệu xác nhận WORLD vocoder đổi F0 đúng bán âm, giữ nguyên thời lượng, spectral
  envelope và aperiodicity; không còn resampler integer-ratio từng gây allocation 2.442.336.000 byte;
  lỗi lớp pitch hoặc thiếu voiced frame giữ waveform gốc;
  mọi thought dùng narrator profile kể cả khi một row cũ còn chứa speaker/voice của nhân vật;
  segment mới dùng K-weighted LUFS thay active RMS, narrator có anchor `+0,5 dB`, target hội thoại
  trung tính `-19 LUFS` và `loud` thu hẹp còn `-17,8 LUFS`; test giọng thấp 100 Hz và sáng 260 Hz
  cùng hội tụ về target cảm nhận;
- nhãn NPC cục bộ trùng tên trong cùng chapter được hợp nhất trước casting; hội thoại ngoặc kép
  cong/ASCII kéo qua nhiều paragraph giữ nguyên kind và ngoặc đơn cong tạo thought hint;
- cùng speaker `Lucien` ở nhiều chapter khóa đúng một character/voice, trong khi tên khác như `Hạ Phong`
  vẫn là character độc lập; tên người được gọi trong “Anh Lucien!” hoặc “Iven, …” bị tách khỏi speaker;
- pronunciation checkpoint theo từng tên, tự sửa `A-der-on → A-đe-ron` mà không lặp request; khi một tên
  không thể sửa, các tên hợp lệ vẫn được khóa và retry chỉ còn đúng ID lỗi với feedback validator;
- Whisper nhận waveform mono 16 kHz được đọc/resample trong process, không gọi FFmpeg theo từng WAV;
- evidence của từng decode Whisper được lưu ở stage riêng và không thể làm final ASR gate đạt; repeated-short chỉ
  promote khi chính lượt lặp `pass`, còn lượt lặp vẫn lỗi không được ghi đè direct transcript/metrics tốt hơn;
- locked English-name anchor giữ pronunciation ID, source span và occurrence; regression chấp nhận đúng spelling,
  spoken form/dạng ghép token nhưng chặn `Lucien → Lucy/Lucian/Lusienne`, thiếu occurrence, sai thứ tự, repeat3 thiếu
  và homograph ở sai vị trí (`Mây may áo` không được lấy động từ `may` để thay cho tên bị đọc sai);
  mọi verdict `ASR_INCONCLUSIVE` giữ nguyên để không quy lỗi model/ngữ cảnh thành lỗi TTS;
- ASR repair dùng delivery `clarity` với voice/profile/pitch/text khóa nguyên và sampling variance thấp hơn; mỗi candidate
  nằm ở path bất biến riêng và không thay incumbent trước khi cả beam lẫn greedy cùng `pass`. Ledger SQLite khóa round,
  seed, voice/pitch, checksum và evidence; promotion commit final gate + CAS con trỏ + trạng thái trong một transaction.
  Regression bao phủ crash/reopen, replay payload khác, casting đổi, path trùng, WAV mất/tamper, promotion rollback,
  budget hữu hạn và exhaustion vẫn giữ đúng checksum/transcript incumbent;
- pipeline chạy ledger end-to-end: crash trước decode checkpoint chạy lại đúng candidate, WAV candidate bị tamper được
  đánh `invalid`, crash sau dual-pass chỉ resume giao dịch promotion mà không chạy lại TTS/Whisper; báo cáo
  `segment_repair_candidates` xuất từng policy/round/path/SHA/seed, signal, beam, greedy, UTMOS và trạng thái promote/fail;
- perceptual repair không còn reset/ghi đè incumbent: mỗi candidate phải qua signal gate, hai decode Whisper và UTMOS
  trên cùng checksum trước promotion. Review hết budget giữ nguyên path/SHA/bytes incumbent; restart không synth hoặc
  decode thêm, còn crash sau UTMOS pass chỉ resume transaction promotion;
- final ASR pass/fail cùng danh sách decode evidence, checksum và policy được xuất cho từng segment trong
  `audiobook_quality_report.json`;
- thermal hysteresis, atomic chapter assembly và cleanup file `.part` trong recovery;
- pipeline mock không cần model;
- cache inference VieNeu được thu hồi trong `finally` sau cả attempt thành công lẫn thất bại;
- unload VieNeu/Whisper trên Windows trim working set sau GC/CUDA cache release, tránh RAM physical
  bị giữ lại qua nhiều lần chuyển model trong book dài;
- hội thoại một hoặc hai từ có tối đa tám ký tự dùng ngân sách cực ngắn; waveform chạm trần vẫn qua
  Whisper, nhưng endpoint còn hoạt động buộc repair kể cả transcript đúng và câu ngắn không bị split;
- repair câu đã chạm trần VieNeu giảm ngân sách từ 24 xuống 12 frame, riêng câu một ký tự giảm xuống 6 frame;
  cap được checkpoint riêng trong SQLite qua `mark_generating`, failure, recovery/reopen và các vòng ASR, rồi
  chỉ xóa ở commit `verified`;
- FFmpeg thật: ghép, khoảng nghỉ, encode và decode verify.
- Windows `fsync` cho WAV/silence dùng descriptor read-write, được bao phủ bởi test FFmpeg thật.
- điều khiển điện thoại từ máy tính (`tests/test_webui_listen_and_sync.py`, 27-09): lệnh tới điện thoại đang "hỏi
  dài" ngay chứ không đợi hết lượt chờ; lệnh quá 15 giây chưa giao bị bỏ, điện thoại im quá 40 giây không nhận lệnh
  (giao diện được báo 409 thay vì tưởng đã dừng); tắt đồng bộ trả lời ngay mọi lượt đang treo; trạng thái điện thoại
  gửi lên bị lọc kiểu và có trần (không NaN, không chuỗi dài, không mã sách lạ); trọn vòng HTTP thật ghép nối →
  báo đang phát → giao diện thấy → bấm dừng → điện thoại nhận, gỡ ghép là biến mất. Thử tay trên máy ảo với app
  thật: dừng/phát, lùi 15 giây, "Nghe trên máy tính" và "Phát trên điện thoại" đúng chương, đúng giây.
- nghe thẳng thư viện máy tính trên điện thoại (27-09, thử tay trên máy ảo với app thật): cuốn chưa tải hiện trong Thư
  viện với nhãn "Máy tính"; máy tính ra lệnh phát một cuốn chưa tải -> điện thoại lấy gói sách và phát qua mạng đúng
  chương, đúng giây (thư mục sách không có MP3, bộ đệm ghi 2,1 MB); trang sách, tab Nhân vật (45 người + câu mẫu) và
  chế độ Đọc chạy như sách đã tải; tắt máy chủ rồi tua ra ngoài phần đã đệm -> "Mất kết nối với máy tính - kiểm tra
  Wi-Fi rồi bấm phát lại"; bật lại máy chủ, bấm phát -> phát tiếp từ đúng giây lỗi. Máy chủ chỉ nhận cờ `stream` khi là
  đúng kiểu boolean (`test_what_a_phone_reports_is_typed_and_bounded`).

GUI PySide6 đã mở thực tế trên Windows. Test6 đã chạy thật xuyên suốt bằng VieNeu-TTS và Whisper Turbo
trên CUDA: **11/11 chapter**, **1.080/1.080 segment**, **0 segment lỗi**, **11/11 MP3** giải mã/xác minh;
SQLite `integrity_check` trả `ok` và không có lỗi khóa ngoại. Các segment được tạo lại trong chapter 000,
002–006 vẫn giữ đúng narrator/Benjamin/Lucien/Hạ Phong đã khóa; báo cáo review được xuất lại sau lần chạy.

## Chưa xác nhận trên máy đích

- Windows Toast và foreground GPU detection;
- kill/resume giữa CUDA inference;
- OOM/backoff và thermal behavior dài giờ;
- startup thực tế sau khi đóng gói release;
- bộ dependency đã pin trên máy đích.

Bắt buộc smoke test một chapter 2.000–5.000 từ trước khi chạy book rất lớn.

- 22-10 dev/uxfix82 (a74fix: dữ liệu điện thoại bền khi app bị giết - migration/rekey journal/fsync/.corrupt, retake có operation_id, chỗ nghe ReadAloud có anchor, bìa xoá sau khi JSON đã ghi): pytest 8391 passed / 9 skipped / 0 F/E; vitest 1241 passed; tsc 0; gradle 1219 / 0 F/E / 6 skip; hash 67286434.
- 22-10 dev/uxfix84 (musfix: ghi công nhạc trong bản xuất, bỏ bài thiếu tác giả, kiểm bytes/sha1 bài tải, mờ vào khi sẵn sàng, nhả nhạc khi đóng sách): pytest 8381 passed / 9 skipped / 0 F/E; vitest 1243 passed; tsc 0; gradle 1213 / 0 F/E / 6 skip; hash 67286434.


- 23-10 a116f, cây 0.4.133 / 0b004ca4 (chưa commit): sửa migration hồ sơ 0.4.132, metadata phục hồi, số dòng nhật ký, che đường dẫn/capability Cast, nhật ký ngắt luồng và tiến độ từng việc. Chạy riêng 11 file pytest liên quan: 227 đạt; 4 file vitest: 18 đạt; tsc --noEmit chạy một lần, exit 0. Có 11 phương thức JUnit mới và fixture migration/đường dẫn dùng chung; chưa chạy Kotlin/Gradle theo giới hạn phiên làm việc. Chỉ CPU, affinity 2 lõi; không chạy app/GPU/adb/emulator, không mạng ngoài. Hash trước và sau sửa c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886.

## 24-10-2026 — Back và chuyển động giao diện

- Vitest toàn bộ UI: 1770 pass, 0 fail, 1 skip; thêm 20 test DOM hồi quy cho Switch, Toaster, Dialog/Sheet/Menu, details, ghi chú và vùng rỗng.
- V1–V7 có log test đỏ trước sửa và xanh sau sửa. Timer ngắn được thu hồi khi unmount; các bước Back trả focus về thao tác mở.
- `tsc -p tsconfig.json`: 0 lỗi. `npm run build` và `npm run build:android`: exit 0; không chạy Gradle/GPU.
- Tổng JS web: 1517520 → 1521575 byte; Android: 1620853 → 1624602 byte, so với build source trước sửa trong scratch.
- Hash implementation trước/sau: c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886.
- Test dùng happy-dom, geometry/WAAPI có stub; chưa xác nhận FPS/pixel, Tab/focus và Back trên WebView/TalkBack thật.


## 24-10-2026 — Sửa bốn phát hiện ux131

- V1: nhóm chứa chương đang nghe mở mặc định khi chưa có lựa chọn gấp; giữ trạng thái đã lưu và dấu Đang nghe. Khi mở nhóm, đợi Collapse hoàn tất mới cuộn; khôi phục cuộn đợi layout/hoạt ảnh hữu hạn và huỷ khi rời trang.
- V2: cảnh báo đổi giọng phần nối tiếp và nút Dùng lại ở ngoài Fold bộ lọc/lưới giọng.
- T1/T2: chỉ dẫn chuột phải đầy đủ, giữ nhánh cảm ứng; nhắc nghe thử nói rõ đang làm sách và bạn thử lại khi xong.
- Vitest toàn UI: 1818 pass, 0 fail, 1 skip (246 file pass, 1 file skip), 32,19 s; tối đa 2 worker. Tsc `-p tsconfig.json`: 0 lỗi, exit 0. `git diff --check`: exit 0.
- Bổ sung 4 test DOM happy-dom: mở chương giữa nhóm dài/quay lại, gấp đã lưu và cuộn sau hoạt ảnh, đợi layout/huỷ, cảnh báo giọng khi Fold lưu đóng. Các test chữ được cập nhật.
- Hash trước/sau: c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886.
- Không cài dependency, không Git ghi, không GPU/Gradle. Dùng loader happy-dom sẵn có từ scratchpad/ux131; chưa kiểm giao diện trên thiết bị thật.

## 24-10-2026 — Sửa F1/F2 của lượt rà r136b (fix136c)

- F1: tooltip đóng dở được Back kết thúc animation/chờ Radix nhả lớp trước Esc cho Dialog/Menu phía dưới; tooltip có inert và pointer-events:none khi đóng, giữ nguyên fade. Ba ca DOM đỏ trước sửa, xanh sau sửa; nhóm Back liên quan 27/27 test đạt.
- F2: useScrollMemory lấy mẫu trong listener scroll, cleanup flush mẫu thay vì đọc layout mới đã clamp/reset. Kiểm đổi key/nội dung co cho element/window, key mới/null, mẫu cuộn thật 900, về 0, trước RAF/animation.finished. Bốn ca đỏ trước sửa, xanh sau sửa; nhóm cuộn liên quan 15/15 test đạt.
- Vitest toàn UI: 253 file được thu thập, 252 file đạt / 0 lỗi / 1 bỏ qua; 1867 test đạt / 0 lỗi / 1 bỏ qua, 80,55 s, 1 worker. Đối chiếu inventory: đủ 14/14 file *.dom.test.tsx, không file hay test DOM nào bị bỏ qua. File bỏ qua là pdfPages.corpus.test.ts (corpus PDF cục bộ).
- `tsc -p tsconfig.json`: exit 0, không lỗi; `git diff --check`: exit 0. Không chạy pytest/Gradle/GPU, không cài/cập nhật dependency, không Git ghi.
- Hash khoá trước/sau: c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886. Log đỏ/xanh, toàn bộ test và inventory ở scratchpad/fix136c ngoài cây. Test happy-dom dùng geometry/WAAPI mô phỏng; chưa kiểm browser/thiết bị thật.
