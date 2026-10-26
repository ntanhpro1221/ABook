# desktop_qt D0 - progress (updated after every step)

Worktree D:/Novels/ABook_deskqt, branch dev/desk-qt (from 860fe60f). No commits by the agent.
Build: `cmd /c D:\Novels\ABook_deskqt\_internal\desktop_qt\build.bat` (log to a file; output dist\ABookDesk.exe).
Run needs env ABOOK_HOST_PYTHON=D:/Novels/ABook/_internal/runtime/.venv/Scripts/pythonw.exe (the worktree has no runtime/) and ABOOK_HOST_APP=D:/Novels/ABook_deskqt/_internal.
Test profile (never the owner's library): ABOOK_PREFERENCES=<file> with libraryRoot pointing at a fixture.

## Done
- step0: read docs + Tauri shell + host.py + server routes (host protocol: `python -m abook.webui.host --version V`, JSON lines on stdout, {"ready": url?t=token}, {"quit":true}; GET /api/listen/library, /media/books/<id>/cover?v=).
- step1: tools/gen_theme.py -> qml/Theme.qml (colours, spacing, type, radii, motion, cover palettes parsed from DESIGN.md + motion.ts + cover.ts; `--check` in build.bat).
- step2: fonts merged to fonts/BeVietnamPro-{Regular,Medium,Bold}.ttf (tools/merge_fonts.py).
- step3: C++ (backend.cpp host supervisor + HTTP, librarymodel.cpp, coverprovider.cpp async decode off UI thread, platform.cpp, bench.cpp) + QML (Sidebar, ScreenStack, LibraryScreen, BookCell, BookPage, Settings, Studio placeholder, ConnectionChip/Popover, Nav singleton) written; CMake + build.bat; first full build OK (dist/ABookDesk.exe).

- step4a: duplicate-singleton bug fixed (Qt 6.10 prefers the default constructor over create(): constructors now take a mandatory parent arg). Library shows real covers (async decode) + titles; focus ring only around cover; Esc / Alt+Left / mouse Back / Ctrl+1-3 verified (Alt/Ctrl need tools/shot.py `rkey=` = real keys, PostMessage cannot set modifiers).
- fixture: D:/Novels/native_desk_proto/deskqt_fixture (200 books) and deskqt_fixture_small (6 books).

- step4b: shots (200-book grid, hover, popover, light theme, scrolled, narrow 1000 wide, empty library, failed backend, Tab focus ring) reviewed; error copy rewritten for the listener; popover no longer shows port/ms.
- step5: tools/measure.py written; 8/8 valid runs: cold first frame 384 ms median (worst 455), idle private RAM 51.2 MB median (worst 53.4), scroll frame p99 6.2 ms (worst 6.3), max 8.6 ms, 180 Hz. Results JSON: D:/Novels/native_desk_proto/results/deskqt_measure.json.
- step6: dist trimmed 74 -> 42 MB (no dxc, no qmltooling/generic plugins, no vc_redist installer; app-local VC145 CRT DLLs copied); .gitignore for build/dist; build.bat clean uses node fs.rmSync.

## D0.1 (after commit 55c16b53)
- text cut removed everywhere: BookCell / BookPage / ScreenHeader wrap, GeneratedCover uses fontSizeMode Fit (min 9 px), source chip wraps; no elide, maximumLineCount or Text clip left.
- library grid = ListView virtualised by ROW (delegate = one row of N BookCell, height = tallest cell + gap); keyboard nav (arrows, PgUp/PgDn, Home/End, Enter, F5) reimplemented on current index; LibraryModel gained `revision` and book() returns `subtitle`.
- tools/check_text_cut.py (fails the build on elide != ElideNone, maximumLineCount, truncate, clip: true on Text; `// text-cut-ok: reason` escape); build.bat runs it after gen_theme --check. Verified it flags all 9 old violations.
- status popover: no repeated title, details + two MenuRow actions (Khoi dong lai, Mo thu muc nhat ky), no accent text.
- failed message: "Khong tim thay phan chay nen cua ABook:" + path.
- make_fixture.py --long (very long titles + one unbreakable word): D:/Novels/native_desk_proto/deskqt_fixture_long.
- measure (8 runs, 200-book fixture): cold 373 ms median (worst 444), idle 50.9 MB median (one outlier 62.7, the known intermittent high mode), p99 6.0 ms (worst 6.3), max 7.6 ms. Before (D0): 384 / 51.2 (worst 53.4) / 6.2.
- shots dark + light: library, popover, book, failed (+popover), narrow in D:/Novels/native_desk_proto/shots/deskqt/ (d_* dark, w_* light, l_* long titles).

## Next
- D1 per lead.

## D1 - playback core, player bar, Đang nghe, Đọc theo (spec: scratchpad/deskqt/d1_spec.md; report -> scratchpad/deskqt/d1_report.md)
Resume rule: do the first step under "Next" below; every step appends here.

### Done
- step0 (read): player.tsx/engine.ts/sleep.ts/progressOutbox.ts/follow.ts/readingPosition.ts/model.ts/source.tsx/desktop/httpSource.ts + server routes.
  API contract used by the player (host token header `X-Ebook-Token`):
  GET /api/listen/books/<id> (book + chapters + state), GET /api/books/<id>/chapters/<n>/script (segments with start/end, words),
  GET /media/books/<id>/chapters/<n> (Range, mp3 audio/mpeg), POST /api/listen/books/<id>/progress/session {sessionId, record},
  POST .../progress {chapterId, seconds, duration, record, anchor, sessionId, revision} (409 = StalePlayback), POST .../rate {rate, record},
  POST .../chapters/<n>/done {done, record}, POST .../finished {finished, record}, POST/GET .../sessions.
  Studio-made books serve MP3 (output_mp3); imported .abook packages serve the file named in book.json (any format).
- Qt Multimedia 6.10.3 (with ffmpeg + windows backends) installed into D:/Novels/native_desk_proto/qt611 via aqt (-m qtmultimedia); qt611_mm_install.log.
  NOTE: that run also re-extracted qtbase (aqt quirk); rebuild checked afterwards.
- step1 (audio core, MEASURED): Media Foundation IMFMediaEngine wins over QMediaPlayer(FFmpeg): +0 MB dist (vs ~+22), RAM 9.6-10.6 MB (vs 27-28), CPU 0.8-1.7 % (vs 4-9 %), pitch kept (F0 90.06/90.06/89.55/90.23 Hz at 1/1.5/2/3x), gap 99 ms vs 125 ms.
  Table written to _internal/docs/NATIVE_PHONE_UI.md section 7.1 ("Lõi âm thanh"). Code: src/audioout.{h,cpp}, src/audioout_mf.{h,cpp}; bench in tools/audiobench (bench only, not in app).
  Pitch capture = WASAPI loopback at -66 dBFS (inaudible) - disclose in report. Opus/FLAC rate change unsupported in MF (D1b note).
- step2 in progress: written (not yet compiled) src/playerlogic.h, playernet.h, hostnet.{h,cpp}, progressoutbox.{h,cpp}, player.h (declarations).

### Next
- step2: write chaptersmodel.{h,cpp}, player.cpp, PlayerClock; add src/*.cpp to CMakeLists (static lib `abookcore` used by app + tests, Qt6::Test target tests/), fake AudioOut/PlayerNet tests; build.bat runs ctest.
- step2 (Player core) DONE: src/player.{h,cpp} (Player + PlayerClock), chaptersmodel.{h,cpp}, playerlogic.h, playernet.h, hostnet.{h,cpp}, progressoutbox.{h,cpp}; CMake: ABOOK_PLAYER_SOURCES shared by ABookDesk and PlayerTests (QtTest, tests/test_player.cpp + tests/fakes.h);
  build.bat runs PlayerTests before packaging. 26 QtTest cases pass (resume point/rewind, near-end -> next chapter, auto-advance, end of book/caught-up, sleep minutes+fade+pause-freeze, sleep end-of-chapter,
  extend, rate per book, save on pause/close/10 s/chapter change, outbox retry + 409 drop + survive restart, error+retry, jump-back, device-elsewhere, snapshot-stays-still, text-only not playable, listening session >=20 s).
  Helper: scratchpad/deskqt/quick.bat (build + tests -> tests.txt).

### Next
- wire Player into main.cpp (MfAudioOut + HostNet, restoreLast on library load, shutdown flush, listeningChanged -> refreshLibrary), then step 3 (QML bar, Đang nghe, read-along, popovers, keyboard, book page).

- step2b DONE: main.cpp wiring (MfAudioOut lazy engine + HostNet + Player singleton, restoreLast on libraryFetched, shutdown flush, listeningChanged -> debounced libraryRefresh). Build OK, 26/26 tests.

### Next
- step3a: C++ read-along (ScriptModel, ReadAlong controller, Geom rects), Player clock text helpers; step3b QML PlayerBar/NowPlaying/popovers/BookPage action; step4 measure; step5 shots; step6 report.

- step3a DONE (C++): scriptlogic.h (script -> paragraphs/sentences/words, sentence+word lookup, follow rules), readalong.{h,cpp} (ScriptModel, ReadAlong singleton: loads script, 60 ms ticker only while playing+active, signals only on change, rect helpers from QTextLayout, shade, listenFrom), bookdetail.{h,cpp} (book page: chapters + primary button wording), Player::clockText/lengthText/net(). tests/test_readalong.cpp = 13 passing (build target ReadAlongTests, run by build.bat); PlayerTests 26 passing.

### Next
- step3b: QML: Popover base, SeekBar, PlayerBar, NowPlaying (morph, wide/narrow), ReadAlongView, popovers (Tốc độ, Hẹn giờ, Chương), BookPage action + chapter rows, Main.qml integration + shortcuts, register ReadAlong singleton in main.cpp. Then Nhạc nền, step4 measure, step5 shots, step6 report.

- step3b DONE (QML): Popover, SeekBar, PlayerBar, NowPlaying (morph + wide/narrow + Bìa/Chữ switch), ReadAlongView, Speed/Sleep/Chapters popovers, BookPage action + chapter rows, Main.qml shortcuts. Build OK. Visual pass 1 (dark + light, narrow + wide): bar, Đang nghe cover/text, chip "Về chỗ đang đọc", 3 popovers, mid-morph frame OK. Fixed: pageT binding was broken by `pageT = 0` (Chữ switch did not slide); TextEdit in delegates now `enabled: false` so the paragraph TapHandler gets the click (click on a sentence plays from it: verified muted, 0:30 -> 0:43 with word highlight).
- Tooling notes: build via `scratchpad/deskqt/qb.bat` from PowerShell ONLY (Git Bash cmd.exe call silently does not build); shot.py hover (WM_MOUSEMOVE) is ignored by Qt unless the real cursor is over the window, so hover visuals cannot be shot; PowerShell needs 'click=X,Y' quoted; window size persists in %LOCALAPPDATA%\ABook\desktop_qt.ini (themeMode there too: set light for light shots, RESTORE to auto at the end).

### Next (lead additions 26-10, do before step4)
- A) Sidebar collapse/expand (Claude Desktop pattern) in Sidebar.qml + Main.qml; B) SkipButton +-15 icon with web geometry + pixel check. Then Nhạc nền, step4 measure, book page shots, report.

- step3c DONE (lead additions 26-10): (A) Sidebar collapse/expand: icon toggle at top (tip "Thu gọn / Mở rộng  (Ctrl+B)"), 56 px rail, hover 150 ms opens an OVERLAY (z 20, shadow, content x unchanged), closes 300 ms after leaving, click on an item navigates + closes; width/x animated with Theme easing, labels live in width-clipped Items (no elide); state in Platform setting `sidebarExpanded`. Tests: tests/qml/tst_sidebar.qml (12) via tests/test_sidebar.cpp, stubs in tests/qml/stub (exe in build/sidebar_tests so the real ABook module does not shadow the stub). (B) SkipGlyph.qml: web geometry exactly (arc r 8.5, arrowheads, "15" below, weight 600, 14.5 u, tnum); tests/test_skipglyph.cpp pixel check (gap >= 1 px, ink inside box) at 1x/2x and bar size. shot.py gained `hover=X,Y` / `unhover` (moves the REAL cursor briefly).
- Ini note: shots toggle themeMode in %LOCALAPPDATA%\ABook\desktop_qt.ini; restore `themeMode=auto` + `sidebarExpanded=1` at the end.

- step3d DONE (lead addition 3, lucide icons): scripts/gen_lucide_icons.py (untracked copy from native1) ICONS += audio-lines, chevron-up, clapperboard, folder-open, library, panel-left-close/open, refresh-cw, settings. Generated qml/LucidePaths.js (43 icons, lucide-react 1.61 from D:/Novels/ABook_native node_modules via scratchpad/deskqt/rungen.py, Kotlin output sent to scratch, NOT written into mobile/). qml/Icon.qml is now a Shape (CurveRenderer, stroke 2 grid units scaled by size/24, round caps/joins, `solid` = filled no stroke, default true for play/pause as the web does; `_FILL` second ShapePath), API `name` (wrappers Button/ControlChip/IconButton/MenuRow/NavItem got `icon` instead of `glyph`); BookDetail.primaryGlyph -> primaryIcon (play / pause / rotate-ccw); Platform.iconFamily and the Segoe fonts removed; CMake QML_FILES += qml/LucidePaths.js; dist gets qml/QtQuick/Shapes via windeployqt (+0.4 MB). tests/qml/tst_icons.qml (in SidebarTests exe): per icon at 16/18/20/24/28 px ink exists, no ink at >=50% coverage on the box edge, centre within 1/6, Pause bars do not touch, Play solid, unknown name draws nothing, writes build/icon_sheet_light.png + _dark.png (looked at: all 19 icons correct). Tests: Player/ReadAlong/SkipGlyph exit 0, SidebarTests 117 passed 0 failed.
- step4 IN PROGRESS (measurement): bench.cpp/bench.h gained scenario + book properties and noteCounters(tag, Player, ReadAlong) (events named count:<tag>:ticks:snapshotChanges:evaluations:changes); PlayerClock.ticks and ReadAlong.changes properties; qml/BenchScenario.qml has the "player" scenario (window 1500x860, load book paused, idle 3.5 s, 5x open/close Dang nghe, open + play muted 10 s with a 1 px heartbeat so frame gaps are meaningful, close, minimise 10 s still playing); tools/measure.py has --scenario player (launch/one_run split, CPU sampling via GetProcessTimes, morph/follow frame p99, counters delta). Build OK. FIRST player run was dropped twice as "covered" (top_at_center/iconic false in the morph/follow spans): I had just added bad_sample to the result and the log line to see which state; NOT yet run (usage brake hit).

### Next (exact)
1. Run: cd _internal/desktop_qt; python -X utf8 tools/measure.py --fixture D:/Novels/native_desk_proto/deskqt_fixture_a200 --scenario player --runs 1 --attempts 1 --topmost --out <scratch>.json ; read the bad_sample; fix (likely the window resize to 1500x860 moving the centre, or topmost placement before resize, or the minimise state leaking into the spans) ; then --runs 8 for the player scenario and --runs 8 for the library scenario (cold first frame must be <= 373+30 ms; idle loaded paused <= 60 MB; minimised playing <= 75 MB and < 1 % CPU; morph p99 <= 12 ms; follow p99 <= 12 ms; follow counters: snapshotChanges delta 0). Count how many runs show the 62.7 MB idle mode; try to find its cause if cheap. Also measure the sidebar-collapse animation frame time and report icon cost (Shapes: <= ~2 MB / 10 ms vs D0.1: cold 373, idle 50.9).
2. Static check that Player.clock is only read by SeekBar / SleepPopover / NowPlaying time labels (grep qml for Player.clock).
3. Book page shots (light+dark), bar hover shot via hover=, narrow dark text shot, a shot of the sidebar + popovers with the new lucide icons (dark + light), copy build/icon_sheet_*.png next to the shots; Nhac nen: decide (omit + document, or second MF engine) ; real muted playback check (seek, chapter change, resume after restart).
4. Restore %LOCALAPPDATA%\ABook\desktop_qt.ini: themeMode=auto, sidebarExpanded=1 (currently themeMode=dark).
5. Full build.bat (gen_theme --check, check_text_cut.py, all 4 test exes), update this file, write scratchpad/deskqt/d1_report.md, final chat report (<25 lines).

- step4a (26-10, after the brake): FOUND + FIXED a real crash: app started with a saved position and Dang nghe opened in the wide layout died in QQmlObjectCreator::finalize (async delegate incubation of the read-along ListView, cacheBuffer 900) because the delegate's Component.onCompleted -> root.currentRectsChanged() -> follow() -> positionViewAtIndex/scroll re-entered the ListView mid-incubation. Fix: ReadAlongView.currentRectsChanged() now only Qt.callLater(rectsSettled). (Found with a crash-trace hook in bench.cpp that writes <bench json>.crash with module+RVA frames when ABOOK_BENCH is set; RVAs mapped with dumpbin /exports.)
  Also: Main.qml builds NowPlaying lazily (Loader, alive once a book is loaded; kept until the book is closed and the view has folded) so a cold start without a book does not pay for it; BenchScenario heartbeat Rectangle no longer re-parents itself.
  Fixture a200 listening.json is reset to the empty state before each bench batch (clean copy in %TEMP%/listening_a200_clean.json) because the player scenario saves progress into it.
  A/B builds for the cost of the changes: scratch_d01 (git archive eebfe606 = D0.1), scratch_segoe (D1 with the old Segoe Text Icon), current = lucide Shape. Interleaved runs: results/ab3_*.json.
- Nhac nen decision: NOT in D1. The web bed is musicBed.ts 812 lines + playlistBed.ts 431 (cue crossfades, loop points, gain steps, music_mix.json, prefetch) - a separate port (D1c); the control is omitted from the chips, nothing half-working ships. Giong chip omitted too (recorded books only).

- step4b DONE (26-10 pm): measurement + shots + playback. Changes since 4a: ReadAlong drops its loaded script 8 s after Dang nghe closes (test inactiveScriptIsDroppedAndComesBackOnReopen, ReadAlongTests 14 passed); Main.qml unloads the lazy NowPlaying 8 s after it folded (immediately when minimised or the book is closed). A trimMemory()/HeapCompact experiment was tried and REVERTED (no measurable gain).
  Library scenario, no book, interleaved d01 (D0.1) vs current (results/ab5_*): cold d01 median ~418 / current ~448 ms (spread +-50, so delta +25 ms, inside +30); idle 52.4 vs 53.0 MB (+0.6). Earlier "D1 = 60 MB" readings were a machine mode: in some periods BOTH builds read ~8-10 MB higher (the lead's 62.7 mode); it follows the machine, not the build.
  Player scenario (results/deskqt_measure_d1_player3/4/5.json): idle with book 65-68 MB typical (55 once, 83-107 in a bad mode), playing minimised 70-90 MB (CPU 0.4-1 %, 2.5 % worst), morph p99 6.6-11 ms, follow p99 6-11 ms (one run 16 ms), snapshotChanges 0, clock ticks ~41 per 10 s, ReadAlong evaluations ~205 per 10 s, minimised: all counters 0. Budgets idle<=60 / minimised<=75 are NOT met with a book loaded (book + MF engine ~+8 MB idle, +20 MB after Dang nghe was opened; private bytes are not returned to the OS).
  Shots in shots/deskqt/final (dark + light: library, book page, chapter rows, hover time bubble on the bar line, Dang nghe wide/narrow cover + text + chip, 3 popovers, sidebar rail + hover overlay, connection menu, lucide in place, icon sheets). All read magnified; no visible fault.
  Real muted playback (shots q*/r*): play advances 1:1 (0:00 -> 0:05 -> 0:10), seek click at 32 % lands at 2:21 of 7:24, chapter row switches to Chuong 2 at 0:01, pause holds, restart restores Chuong 2.
  build.bat full: exit 0 (gen_theme --check, check_text_cut, 4 test exes: 26 + 14 + 6 + 117 passed).

- step5 DONE (26-10, lead priority): INTEGRATED TITLE BAR. QWindowKit 1.5.0 (Apache-2.0, static, Quick only; tools/build_qwindowkit.bat clones the tag + builds into QWK_ROOT\inst, build.bat calls it when missing; CMake find_package(QWindowKit) + Qt6 *Private components). src/windowchrome.{h,cpp} = thin QML wrapper (attach / keepClickable / cursorInside). qml/TitleBar.qml (strip height 40 = Theme.buttonHeight, transparent: both sides are Theme.bg), CaptionButton.qml (46 x 40, hover/press = IconButton tokens 0.06/0.10, Close #c42b1c hover / #a82419 press, white glyph, inactive window -> faint glyph), CaptionGlyph.qml (Segoe Fluent style 10x10 box, 1 px stroke; maximize <-> restore morph = fade + scale 0.8->1 in 120 ms). Sidebar: toggle moved into the strip (x 12, y 4, 32x32, centre 28 as the nav icons), the "ABook" text removed, nav items start at y 48. Main.qml: window created hidden, WindowChrome.attach before first show, content anchored under the strip.
  Verified (shot.py nchit/ncdbl/sc/size/screen steps): WM_NCHITTEST blank strip = HTCAPTION, toggle = HTCLIENT, min = HTMINBUTTON, max = HTMAXBUTTON (Windows 11 Snap Layouts), close = HTCLOSE, top edge = HTTOP; invisible 10 px resize frame outside the client; sc=max / restore work, double-click on the strip toggles maximized; hover visuals on all three buttons, max button keeps its hover fill while Snap Layouts is open (cursorInside latch); dark + light shots in shots/deskqt/tb. Display is 140 % (dpi 134), so fractional scale is covered; 125/150 could not be tested (would change the user's display setting).
  Cost: exe 2,727,936 -> 2,909,696 B (+177 KB), no new DLL; interleaved before/after x8 runs: idle 53.1 -> 52.2 MB, cold first frame 448 -> 442 ms (noise +-50).
  Deviation: no theme colour animation on the strip (the rest of the app switches theme instantly; an animated strip would lag the page). THIRD_PARTY.md got the QWindowKit line.

## D1c - Nhạc nền (Music lane, branch dev/desk-qt-music, worktree D:/Novels/ABook_qtmusic; lead brief 26-10)
Resume rule: do the first step under "Next"; append after every step. Build/tests via build.bat (PowerShell), shots tools/shot.py, measure tools/measure.py.

Scope decision: Qt plays only audio chapters (text chapters are "not playable" in D1), so the web's text-book menu (PlaylistSubmenu /
MusicMenuFor, scene music, Nhạc của tôi) has nothing to drive yet -> port only what audio books use on the web desktop:
PackagedMusicMenu (switch "Nhạc nền: Bật/Tắt", "Mức nhạc dưới giọng đọc", notes), the bed engine (musicBed.ts: cues per chapter,
fades, crossfade loops, steps, sibling/tail, retry, warm next), and the credit row in Đang nghe ("Nhạc nền: ..." + credit/licence/page).
Per-cue silence/swap is NOT in the web player (only Sửa sách), so not in the player here either.

### Plan
- m1: musiclogic.h (pure: cues, steps, loopBounds/loopPosition/loopSchedule/aligned/due/final/finished/sibling fade; constants from
  abook/webui/assets/music_mix.json embedded as a resource) + tests/test_music.cpp mirroring musicBed.test.ts.
- m2: musicbed.{h,cpp} (MusicBed on AudioOut instances made by a factory; QTimer 50 ms fades; loop ticket; standby) + fake tests.
- m3: music.{h,cpp} QML singleton (GET/PUT /api/books/<id>/music, GET /api/books/<id>/music/chapters/<n>, POST /api/music/warm,
  NextChapterWarm, credit of the active link, broken), wired to Player (position/playing/seek/chapter/volume incl. sleep fade).
- m4: QML: music chip in the bar + menu (Popover), credit row in Đang nghe; icons via scripts/gen_lucide_icons.py --qml.
- m5: build.bat, shots light/dark, measure (RAM/frame vs D1), report -> Lead.

### Done
- m0: worktree from origin/dev/desk-qt 9d2c9f15 + merged origin/dev/native1 f3ae8c70 (shared icon generator).
- m1+m2 (26-10): src/musiclogic.h (pure logic; mix constants from music_mix.json via CMake ABOOK_MIX_*), src/musicbed.{h,cpp}
  (MusicBed = musicBed.ts line by line; a "voice" = AudioOut + what <audio> remembers; AudioOut gained preload()/setLoop(), MF
  implements both; events are connected QUEUED before load() so they arrive after the call like DOM events; readyState < 3 =
  AudioOut::buffering). tests/test_music.cpp = MusicTests (29 pass): shared fixtures music_timeline + music_loop (same as server/web/
  Android), parse, steps, handoff numbers, and the bed on FakeOut (switch/silence, announce once, release after fade, paused book
  switch, gainDb x volume, step ramp/seek jump, broken song retry, seek in loop, crossfade loop with prepared voice, short loop,
  standby released, tail + early sibling, silent until sounding, warm next once). build.bat runs MusicTests.
  Gotcha: moc skips a file with C++ digit separators (1'000) or a raw string R"(..)" -> empty .moc, link error on metaObject.
- m3 (26-10): src/music.{h,cpp} = QML singleton Music (main.cpp: one MfAudioOut per bed voice). Book change -> GET /api/books/<id>/music
  (packaged view or Studio plan/overrides like musicEditView); chapter change -> bed cleared at 0 then GET .../music/chapters/<n> (pending
  polled 80 x 1.5 s, unavailable/failed retried 15/30/60/120/300 s); 250 ms sync tick while playing (seek = jump > 3 s), bed volume =
  Player::outputVolume() (volume x sleep fade); NextChapterWarm (in musicbed.h) warms the next chapter's first song; setEnabled/setLevel
  PUT then re-ask cues, failure -> Player notice "Chưa chỉnh được nhạc nền". src/musictext.h = levels/licence/credit words from the web.
  PlayerNet::mediaUrl (HostNet adds ?t=token). FakeNet gained `answers`/`statuses`. MusicTests 37 pass (text, NextChapterWarm, Music
  with a real Player: credit, chapter switch, warm, switch off, failed change, project view).
- m4 (26-10): the D1 bar has no extra controls by design, so music lives in Đang nghe: an icon-only ControlChip "eighth-note" after
  Chương (square, Theme.buttonHeight; width/opacity animate in when Music.hasMusic, the three text chips share the rest; struck through
  when off = web chip look; ControlChip gained `struck` and hides an empty text). qml/MusicPopover.qml = PackagedMusicMenu word for word
  (header "Nhạc nền: Bật/Tắt" + new qml/Switch.qml 44x24 like .ui-switch, warnings in Theme.warning that fade/slide, "Mức nhạc dưới giọng
  đọc" + CHOICE_ROW rows with a fading check, the panel stays open on choose, rows .5 + disabled when off/busy, the Studio/packaged note).
  qml/MusicCredit.qml = MusicCreditLine under the narrator ("Nhạc nền: title · creator" -> animated collapse: credit text, "Giấy phép: "
  + link, modified note, "Trang của bài nhạc"; links via Qt.openUrlExternally, text escaped, never elided; collapses on a new song; the
  last credit is kept while it fades). DESIGN.md + gen_theme.py: --warning/--focus/--switch-off/--switch-thumb (values = styles.css;
  palette.test.ts token list extended - not run here, no node_modules in this worktree; rows checked by hand). Merged origin/dev/native1
  07e84542, LucidePaths.js regenerated with its generator (58 icons). Not ported (Qt plays audio books only): playlist/scene menu.
  Shots (fixture D:/Novels/native_desk_proto/deskqt_fixture_music = audio fixture + a synthetic 40 s pad in book A; scratchpad runshot.py
  restores listening state, window and theme each run): D:/Novels/native_desk_proto/shots/music/{dark,light}_{credit,menu,off}.png,
  chip_4x.png - looked at: chip, strike, switch, rows, wrap all right in both themes.
- m5 (26-10): build.bat green (MusicTests 37). measure.py --scenario player, music fixture (book A has a 40 s pad), interleaved x4
  (results/abmusic_{d1,music}_N.json): idle with book D1 59-73 MB vs music 60-75 (same); minimised playing D1 82-84 vs music 72-90
  (~+5 MB, the second MF engine); CPU minimised 0.4-2.8 % vs 0.4-4.8 %; morph p99 both 7-40 ms (noisy); follow p99 both 6-11 ms.
  follow_max: D1 <= 17 ms, music 502 / 511 ms in 2 of 4 runs.
  Found on the way, fixed in the shared part: CoverView bound sourceSize to its animated size, so every frame of a size change
  re-decoded the cover and flashed the sunken plate (credit line appearing, window resize). Now it re-decodes after 150 ms of a stable
  size, retainWhileLoading keeps the old picture meanwhile. MusicCredit keeps its one-line slot while the music is silent (pause,
  stretch without a cue), so the big cover no longer resizes on every play/pause. After the fix x4 (abmusic_fix_N): follow_max 11, 529,
  13, 12 ms - the rare stall is still there. Traced build x3 (every MfAudioOut/MusicBed/Music call > 2 ms + a 10 ms GUI watchdog):
  engine create 5-18 ms, set source 0.5-3 ms, stop/destroy 1-5 ms, sync < 5 ms; a 300 ms GUI gap had no music call within 10 s; the
  500 ms stall did not reproduce (max 77 ms). Cause still OPEN (not on the GUI thread from music code; next: frame-swap timeline vs
  render thread / audio device start of the second engine).
- m6 (dev/desk-qt-stall 133fdf72): bench marks every MfAudioOut create/source/play/seek/stop/destroy + engine event and each
  afterAnimating tick; measure.py prints the worst follow gap with the marks before it. On the Parsec virtual display (60 Hz)
  12 music runs: follow max 18-34 ms, no stall (the 529 ms ones were on the laptop panel at high refresh). PARKED by lead until the
  machine is back on the laptop panel; then run `D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe -X utf8
  D:/Novels/native_desk_proto/stallrun.py 12 <out.json>` (player scenario on deskqt_fixture_music, prints the worst gap regardless
  of cover / refresh drops).
