# Test khẳng định theo giờ thật (wall-clock)

Triệu chứng gốc: `tests/test_ui_parity_qt.py` hỏng khi máy tải nặng (hạn 30 giây), chạy riêng thì xanh. Cùng loại với mọi test
mà kết quả phụ thuộc vào việc máy có kịp trong N giây: mã không sai, máy bận.

## Quy tắc

| Việc | Cách làm | Nơi |
|---|---|---|
| Chờ một điều kiện tới hạn (`deadline = now + 5`) | `now + scaled(5)` hoặc `tests.async_wait.wait_until` (đã nhân sẵn) | Python `tests/timing.py` |
| "Xong ngay / không quá N giây" | `assert_within(N, since, blocked=...)`, `assert_between(low, N, since)` | Python `tests/timing.py` |
| Chờ tín hiệu / join luồng | `event.wait(scaled(1))`, `thread.join(scaled(1))` | Python |
| Hạn chờ Kotlin | `TestTime.ms(..)`, `TestTime.nanos(..)`, `TestTime.seconds(..)` | `vn/abook/player/TestTime.kt` |
| Hạn chờ web | `scaledMs(..)`, `eventually(..)` (thay `vi.waitFor`, hạn mặc định 1 s) | `ui/src/testing/` |
| Đo hiệu năng thật (ngưỡng cố định) | marker `@pytest.mark.perf` (Python), `TestTime.perf { .. }` (Kotlin) - ngoài cổng thường | `pytest -m perf`, `ABOOK_PERF=1` |
| Giờ giả (đồng hồ bị thay, `vi.advanceTimersByTime`) | không đụng; dòng ghi `wallclock-ok: <lý do>` khi máy dò nhầm | |

Hệ số: biến môi trường `ABOOK_TEST_TIME_SCALE`, mặc định **5** (máy chậm hơn nữa thì đặt cao hơn). Chỉ nhân cận TRÊN; cận dưới
("đã chờ ít nhất 1,4 giây") giữ nguyên vì nó chứng minh có chờ thật. `blocked=` là thời gian mà hành vi SAI sẽ mất (cổng chờ
20 giây, hạn cũ 30 giây): hạn đã nhân bị chặn ở 80% con số đó để nới hạn không làm test mất khả năng bắt lỗi.

Máy dò: `scripts/flaky_patterns.py` có thêm ba luật không dung sai (`elapsed-bound`, `fixed-deadline`, `raw-waitfor`);
`tests/test_test_flakiness.py::test_hard_wall_clock_limits_are_banned_outside_the_shared_helpers` đỏ nếu còn dòng nào, và baseline
`tests/fixtures/flaky_patterns.json` không được chứa ba luật ấy. Hai file Android `TlsRouteResolverTest.kt` và `net/FastConnectTest.kt`
nằm trong `WALLCLOCK_DEFERRED` vì nhánh `dev/tlsleak` đang viết lại chúng (còn `FastConnectTest.kt:80,95`: `nanoTime() + toNanos(..)`);
khi tlsleak vào, sửa hai file theo bảng trên và bỏ chúng khỏi danh sách.

## Đã sửa (số chỗ, trước -> sau theo máy dò)

| Ngôn ngữ | Luật | Trước | Sau | Ghi chú |
|---|---|---|---|---|
| Python | elapsed-bound (cận trên của thời gian đã trôi) | 40 | 0 | 36 qua `assert_*`, 4 sang marker `perf` |
| Python | fixed-deadline (`đồng hồ + hằng`) | 46 | 0 | 39 nhân `scaled`, 7 ghi `wallclock-ok` (đồng hồ giả / mốc thời gian đưa vào mã) |
| Python | short-thread-timeout (`wait/join` <= 1 s) | 18 | 5 | 13 nhân `scaled`; còn lại: 3 nhịp thăm dò (vòng đã nhân số lần), `test_a89...:48` và `test_listen_export:403` (cửa sổ "không xảy ra" / nhịp) |
| Python | `tests/async_wait.wait_for/wait_until` | - | - | hạn nhân hệ số ngay trong helper: phủ 19 file đang dùng |
| Kotlin | fixed-deadline | 25 | 0 (+2 hoãn) | `TestTime.ms/nanos` |
| Kotlin | elapsed-bound | 3 | 0 | 1 qua `TestTime`, `BtMuxTest` đo tốc độ -> `TestTime.perf`, `BoundedTest` đổi nhịp 100 -> 200 ms để hạn có biên |
| Kotlin | short-thread-timeout | 28 | 5 (4 hoãn) | `join/await` qua `TestTime`; `BookImportReviewTest` ngân sách giây -> `TestTime.perf` |
| Web | `vi.waitFor` (hạn mặc định 1 s) | 20 | 0 | 8 file sang `eventually`; thêm `backLayers`, `queryClient.settle`, `gallery/actions.waitFor` |

Python, theo file (cận trên -> `assert_*`): `test_a109_security:261,270`, `test_a61_export_cancel_and_cleanup:99,132,251`,
`test_a62_listen_export:139`, `test_a_mp3_export_runs_in_the_background:40,76,102`, `test_a_projectfile_export_runs_in_the_background:102,181`,
`test_background_runner:649`, `test_bluetooth_desktop_client:472`, `test_casting_review:89`, `test_close_within_host_grace:50,71`,
`test_music_cache:169,172`, `test_readaloud_edge_pieces:269,319,489,755,775`, `test_readaloud_prepare:72,93`,
`test_readaloud_vieneu_gguf:198`, `test_reading_preview:325`, `test_remote_waking:138,165,182`, `test_tts_pool_lost_worker:110`,
`test_webui_covers:126`, `test_webui_host:181`, `test_webui_listen_and_sync:398,433`, `test_work_items:77`.
Sang marker `perf` (ngưỡng thật, tách phần đúng/sai khỏi phần đo): `test_ui_parity:41`, `test_ui_parity_qt:40` (render 30 s; phần
"xác định" vẫn trong cổng), `test_import_review:103` (ngân sách 5.000 phần), `test_bluetooth_fairness:307` (độ trễ trên ống giả 150 KB/s).

Hạn chờ điều kiện (`now + N` -> `now + scaled(N)`): `test_a105_profiles:160,178`, `test_a109_security:235`, `test_a113_security:155`,
`test_a62_listen_export:55,89,359`, `test_a92_install_survives_close:33`, `test_bluetooth_fairness:217`, `test_bluetooth_tunnel:181`,
`test_bookfile:532`, `test_bookfile_job:118,153,167`, `test_export_m4b:128`, `test_export_series:118`, `test_listen_export:316,407`,
`test_listening_records:177`, `test_music_download_resumes:154,202`, `test_pause_on_battery:102,158`, `test_precast_review:193`,
`test_readaloud_edge_stream:303,629`, `test_readaloud_vieneu_gguf:261,306`, `test_reading_preview:348`, `test_remote_studio:351,442`,
`test_remote_studio_paths:110,160`, `test_two_heartbeats:187`, `test_uxfix70_local_voices:326`, `test_uxfix76_long_listening:143`,
`test_webui_listen_and_sync:355`, `desktop_qt/tools/test_installer.py:229,269`.
Giữ nguyên, ghi `wallclock-ok`: `test_music_api:833`, `test_trash_undo:453` (đồng hồ giả đi trước), `test_readaloud_local_stream:214,237,476`
(mốc tương lai đưa cho luồng), `test_readaloud_edge_pieces:404` (hạn phải hết).
Tín hiệu / join: `test_peer_multiaddr_regressions:54-102` (10 chỗ), `test_peer_addresses:85,312`, `test_close_within_host_grace:65`.

Kotlin: `A104CastTest:103,141`, `A113SecurityTest:17`, `BtMuxTest:100,143,148,221,440`, `DlnaTest:57`, `GCastTest:65`,
`MusicStudentSetupTest:341,501,505`, `net/HostWaitSyncTest:121`, `readaloud/EdgeLiveTest:150,215,222`,
`readaloud/EdgePiecesTest:346,409,443,459,484,549,577,609`, `readaloud/LiveClipsTest:55,74,143,224`, `readaloud/OpeningScheduleTest:231`,
`vieneu/VieneuModuleTest:467,504,515`, `MusicManifestRefreshTest:87`, `DiscoveryHintsTest:32-64`, `PeerConnectionsTest:15-126`,
`BoundedTest:32`, `BookImportReviewTest:35`, `StudioClipsTest:63`, `ui/LibraryMembershipTest:23`, `ui/NativeIncomingFileTest:77`,
`ui/studio/StudioTabsStateTest:65`, `ui/voice/VoiceStateTest:29`; `RouteTest:77` ghi `wallclock-ok`.

Web: `desktop/handOff`, `desktop/openBookPath`, `listen/lateProgressAck`, `listen/playbackRefresh`, `listen/progressOutbox`,
`listen/silenceSkip`, `shared/trashUndo`, `studio/a90Undo` (mọi `vi.waitFor`), `shared/backLayers.test.ts:219` (vòng chờ 2 s thật),
`shared/queryClient.test.ts:9` (cửa sổ 200 ms "đứng" -> sai khi truy vấn thật chậm), `gallery/actions.ts:7` (hạn 6 s).

## Còn lại có chủ ý (đã xem, không đổi)

Máy dò vẫn kiểm kê chúng trong baseline (ratchet chỉ cho giảm), nhưng không phải hạn giờ thật:

- **Nghỉ để nhường lượt / nhịp thăm dò** (`time.sleep(0.01..0.2)` trong vòng chờ điều kiện, `Thread.sleep(10)`): hạn của vòng đã qua `scaled`, nhịp thì không phụ thuộc tải. Python 96, Kotlin 65.
- **Nghỉ để chứng minh KHÔNG xảy ra** (`time.sleep(0.6)` rồi khẳng định trạng thái vẫn đứng yên: `test_cast`, `test_gcast`, `test_work_items_at_scale`, `test_a89...:48`): máy chậm chỉ làm chúng dễ đậu hơn, không làm hỏng.
- **Đồng hồ làm dữ liệu** (`Date.now()`/`System.currentTimeMillis()` làm mốc `at`, `lastModified`, `receivedAt`), và web dùng `vi.useFakeTimers()`: giờ giả hoặc mốc thời gian, không chờ.
- **Chờ cố định trong Qt/QML**: đã có `tests/test_qt_fixed_waits.py` (BASELINE 0).
- **Web `setTimeout(resolve, 0)`/20-60 ms trong `act()`**: nhường vòng lặp sự kiện cho hiệu ứng rồi kiểm; không chờ giờ thật. Nếu cái nào hỏng dưới tải thì đổi sang `eventually`.
- `motion139.dom.test.tsx` (C5): đã đếm thay đổi DOM thay vì đo giờ; `performance.now()` chỉ để in số.
- `gallery_inspect_sheet.test.mjs:96`: cận DƯỚI 150 ms (chứng minh có chờ), không nhân.
