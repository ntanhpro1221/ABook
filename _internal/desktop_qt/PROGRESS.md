# desktop_qt D0 - progress (updated after every step)

## Lead scheduling review (28-10, complete; Lead review pending)
- FINAL 08:55: report.md REPLACED with current results, all 12 accepted AC/offscreen runs, per-thread tables, limits and evidence links. Four rounds ABC/CBA/ABC/CBA finished normally under supervisor94961 (exit0), no foreground events/forced termination, BatteryStatus2 start/end and AC1 throughout every run. Median CPU time one core: A0.744255%, B0.376794%, C0.844791%; B lower in3/4 CPU-time pairs, round2 reversal explicitly reported. Cycle proxy medians A0.910818/B0.447433/C0.782119; B lower in all4 pairs, proxy is not exact CPU elapsed time. B render wakes5.45/5.59/5.77/5.73 vs C101.85/101.99/102.26/101.85. Private commit medians A72.19/B68.52/C67.78MiB; WS17.01/13.48/12.88MiB. Do not claim the0.1-0.15% total-audio target established.
- Final build757 pass/0fail/1existing skip and B strict hidden120.050media/120.054385wall,0starvation. B executable ddcd3fbf2283901475c0c57cd952f4be7ab2c1890b4520a74c97f66994ae0e2c matches build/dist and all B measurements. Quality hash unchanged c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886, list read from code41entries, abook diffempty, HEADf92a0b3e. No commit.
- Exact A audio-only wake count unavailable: unchanged baseline has no loop counter; native per-thread scheduler dispatch counts saved, clearly labeled including preemption. Tried xperf PROC_THREAD+CSWITCH after machine wait; Windows NT Kernel Logger refused Access denied0x5 (build/voicemix-evidence/etw-probe.json). Do not relabel all-thread dispatches as audio-only wakes. All per-thread CPU/cycle/dispatch data: thread-cpu.json; raw per-run samples in raw-N-L.json. Verification manifest regenerated for B; Python syntax/LF/diff checks pass. Remaining action: Lead review; an exact A audio wake trace would require kernel tracing privileges. Existing physical loopback/BT limits remain explicit. Current data is complete for this binary; do not rerun it just to refresh timestamps.
- Notes below are chronological intermediate states; the FINAL entries above supersede their ACTIVE commands and next-step lists.
- 08:39: B strict AC hidden120s PASS: 120.050 media /120.054385 wall, delta -0.004385s, starvation_warnings0, clean exit0/foreground0; current build hash matches ddcd3fbf. Raw build/hidden-evidence/voicemix.json + voicemix-1.app.log. ABC supervisor94961 now in round1 A; next B,C,C,B,A,A,B,C,C,B,A. AC and shared-machine wait remain enforced per timed run. Report still awaiting all rounds; do not claim CPU gain yet.
- 08:37: FINAL full guarded build voicemix-B-final exit0: 757 pass / 0 fail / 1 existing intentional glyph skip. Voice35, Mix76, remaining suites unchanged. Final B dist SHA256 ddcd3fbf2283901475c0c57cd952f4be7ab2c1890b4520a74c97f66994ae0e2c; audit foreground0, isolated desktop/offscreen. Playback supervisor exec94961 is now ACTIVE in strict AC hidden120s, followed by alternating ABC rounds. Read current validation logs, do not duplicate runner. Locked hash reconfirmed unchanged, LF and git diff --check pass, HEAD remains f92a0b3e.
- 08:32: ACTIVE final build voicemix-B-final, exec56193. Voice35 PASS and Mix76 PASS; all earlier C++ suites pass, QML suites still running. Preceding B-largelead attempt found rate-phase discontinuity + loop-release issue, both fixed; B-rewind attempt Voice35 PASS but 12 Mix fixture reloads failed because its manual reader-only readiness helper did not service the queued reset; helper now services render control first. Added a bounded queued-PCM tail plus 5 ms transition bridge for Sonic rebuilds; gain ramps restore audible state, stop clears transition history. Do not use either failed intermediate binary for measurements.
- Queued measurement supervisor exec (see chat) waits for build-voicemix-B-final-audit.json and requires exit0, then runs pinned Python tools/voice_validate.py --resume --abc --playback-only. It performs strict AC hidden120s, then ABC/CBA/ABC/CBA. Do not start a second validation runner. Read build/voicemix-evidence/validation-hidden_suite.py.log and validation-voice_ab.py.log plus ab.json. Resume command after interruption: same voice_validate flags; binary hashes must match completed rows.
- Read report.md + this file before changes. Owner: no windows/focus, no commits/checkout/reset/stash/rm; pinned Python -X utf8 only. Quality list read from code (41 current entries), hash c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886 before edits; no abook changes planned.
- C preserved locally at build/voicemix-evidence/event30 with full runtime, source snapshots, provenance.json. Counted render-loop wakes + thread descriptions are the only C source changes. Full guarded build voicemix-C-counted exit0, original 752 pass + intentional glyph skip. Exe c87b2bde8107911847d41f7f1a21f574645b72e7bb98cbbff3df4558e833ba20. Do not commit the local event variant.
- B implementation: non-event WASAPI, no MMCSS/avrt; 500 ms lead and 250 ms timed wait in both visibility modes (no measured reason for visible short lead). Timer guard shortens wait for small endpoint capacity / padding floor. Rate/volume/pause/seek/stop/start-over-music request shared Stop+padding sample+Reset; all contributors rewind to that audible cursor, explicit seek targets preserved; reader cannot consume pending rewind early. Gain ramp state is restored at the audible cursor too.
- New tests: large-lead controls for rate/volume/pause/seek/stop with another contributor and reader-first ordering; small-device starvation-floor timer/control wake. Updated old short-lead/event assumptions. ACTIVE guarded full build: tools/build_hidden.py voicemix-B-largelead (exec session 95471). Check build/hidden-evidence/build-voicemix-B-largelead.log; resolve any failures before evidence runs.
- Instrumentation: tools/audio_thread_samples.py reads native per-thread CPU/cycles/context switches (validated IDs/times against psutil); measure.py records them, waits for BatteryStatus==2 plus AC, then samples AC throughout. voice_ab.py --abc --rounds 4 alternates ABC/CBA, fresh app state, chapter1 saved-state at0, empties only fixture journal, counts B/C render-loop wakes and scheduler dispatches for all threads. A's unmodified exe has no in-process wake counter; report scheduler dispatches explicitly as a proxy including preemption.
- Current AC verified: Win32_Battery.BatteryStatus=2, PowerOnline=True. Before EVERY timed run use existing shared-machine wait; never interfere with other jobs. Hidden gate tightened to <=0.1 s media/wall difference and zero device starvation warnings. Next: once B passes, tools/voice_ab.py --setup-only; hidden_suite.py --label voicemix-B-largelead --rounds 1 --offscreen --require-mixer --fixture-source build/voicemix-evidence/fixture; voice_ab.py --abc --rounds 4. Replace report.md with current numbers and limits, final locked hash/LF/diff checks. No commits; Lead reviews.

## D3 — chỗ hở của D2 (cloud, branch dev/cloud-qtd3 from origin/dev/desk-qt 775209ea), 26-10-2026

Same Linux setup as D2: Qt 6.10.2 from conda-forge (installed here with py-rattler into /opt/qt6env - micro.mamba.pm is blocked, conda.anaconda.org
is not), Ninja + conda g++, every test exe offscreen. App target (WIN32 only: main.cpp, backend.cpp, MF, QWindowKit) still NOT compiled here.
1. "Mở Studio" of a paired computer: OtherComputersRow button -> Nav.openPeerStudio(id) (Nav.studioPeer + Studio tab). StudioScreen asks
   GET /api/peers/<id>/studio/api/app (webui/peer_studio.py bridge) and shows: PeerBar.qml (desktop/PeerBar.tsx: laptop icon, "Đang mở Studio
   của <máy>", "Về máy này"; info-soft / warning-soft background, opens/closes by height), StudioClosed (listen-only: "Chỉ nghe - bật quyền sửa
   ở <máy>: Cài đặt > Thiết bị", "Về Thư viện") or PeerTrouble (server sentence; 503 unreachable -> "Studio tự mở khi máy ấy trả lời lại." and
   re-ask every 5 s up to 30 min, watchUntilBack). Words from shared/peerStudio.ts (qml/PeerStudio.js). EmptyState.qml = shared/ui.tsx
   EmptyState. Body swaps fade+8 px (ScriptAction reads the newest view - two changes in one tick land on the last one).
   The Qt Studio itself is still the D3 placeholder, so the peer Studio body is the same "Studio chưa mở trong bản này.".
2. Chapter row "…" (ChapterRow of listen/BookScreen.tsx): IconButton ellipsis, shown on row hover / focus / while its menu is open, place
   reserved. Menu (Popover, height computed so it never covers its button): "Nghe từ đầu chương" (play), "Đã nghe xong" / "Chưa nghe"
   (check-check / circle-dashed; POST .../chapters/<n>/done with the shown record, then reload page + library), "Đổi tên chương…"
   (text-cursor-input, only when canEditLayer) -> BookPage.renameRequested -> Main's EditBookRename.begin(book, chapter). Lucide
   check-check + text-cursor-input added to gen_lucide_icons.py (QML output only; the Kotlin output was restored, not written).
   Found + fixed on the way: BookPage's BookDetail had id `detail`, which inside the ChapterRow delegate resolved to ChapterRow's own
   `detail` string - clicking a chapter row on the book page never played it (TypeError). Renamed to bookDetail; test added.
3. "Tự chọn nhạc nền": after a saved change SettingsListen calls Music.reload("*") (+ library refresh): Music re-asks the view and the cues of
   the chapter playing now without clearing the bed first (MUSIC_CHANGED_EVENT/bedVersion of player.tsx). Book id other than the playing one: no-op.
4. letterShortcuts: PlayerKeys.qml (Main.qml key handler) = player.tsx keys + ShortcutsHost: Space, ←/→ 15 s, Shift+←/→ chapter, M mute
   (Player.volume / setVolume / toggleMute, remembers the level, else 0.9), [ ] speed, ? opens ShortcutsDialog.qml ("Phím tắt" + the same
   LookShortcuts list, tail sentence of the dialog variant). Letter keys off -> M, [ ], ? ignored; Space/arrows/Esc still work.
   touchSounds: src/feedback.{h,cpp} singleton Feedback = shared/feedback.ts (same note table, brass timbre harmonics, 4 ms attack +
   exponential decay, 5 ms lead) synthesised to WAV once per kind and played on its own AudioOut (MfAudioOut in main.cpp). Silent while the book
   plays except sleepWarn; Player emits sleepWarning 30 s before a minutes timer ends. Call sites as the web: Switch (+ DevicesToggle label),
   speed choice (toggle), seek-bar drag across a 15 s mark (tick), Add Book confirm / reject. Main binds Feedback.sounds to the preference.
   readingSurface: gen_theme reads ui/src/styles.css :root[data-surface=paper|ivory|night] -> Theme.readingSurfaces / Theme.read; Main binds
   Theme.readingSurface. ReadAlongView paints the surface background (crossfade motionSlow; reduced motion <= 120 ms), text, heard text,
   speaker, sentence (along %) and word (word %) highlights and the edge fades from the surface, not from the app theme.
5. Shell channel: src/hostmessage.h parses the host's stdout lines; Backend emits hostEvent(name, detail) and updateChecked(detail).
   AdvancedUpdate listens to Backend.updateChecked / hostEvent("abook-update-failed") - the 3 s /api/app polling is gone. Main re-reads
   /api/app on "abook-update". The Qt shell has no signed-package updater yet, so {"check_update"} answers at once with
   {state: "failed", message: "Bản chạy từ mã nguồn không tự cập nhật"} (the server's own sentence) instead of a 45 s silence.
6. Toasts with actions: Api.toast(text, {duration, action: {label, run}}), Api.noticeAction / noticeDuration / runNoticeAction(); a plain
   `Api.notice = ...` stays a plain toast. Toast.qml (sonner look of desktop/App.tsx Toaster): panel card top-right 16 px under the title
   strip, title + description (text-2), accent action button on the right, ✕ "Đóng thông báo" at the corner, 4 s default, hover pauses,
   opens by 16 px slide + 0.96 -> 1 scale (reduced motion: fade only), text wraps anywhere - never cut. BookTemplates delete -> "Hoàn tác"
   10 s (the in-page undo button is gone, like the web); "Lưu thành…" -> "Mở thư mục" 8 s (POST /api/reveal-export {folder}).
- DESIGN.md 5.1 + gen_theme: --warning-soft, --info-soft (values = styles.css; palette.test.ts token list extended, 94 pass).
- Tests: DesktopApi 12 (+host lines, feedback table / WAV / rules), Player 33 (+sleep warning, mute), Music 38 (+reload), ReadAlong 14,
  SkipGlyph 6, Sidebar 117, Width 260 (= 210 + tst_d3 43: all six items incl. geometry-in-motion checks, + tst_d3_main 7: the real
  Main.qml with a WindowChrome stub - "?" dialog, letter keys off, M, preferences, host update event, toast placement; QtTest counts
  include init/cleanupTestCase) = 480 pass, 0 fail. Changed old tests: tst_d2_settings update check (polling -> channel), tst_width
  studioCentred (full-bleed PeerBar), tst_d2_studio undo (toast action). Web: tsc clean, vitest 2463 pass / 55 skipped / 0 fail.
  Parity: pytest test_ui_parity + test_native_tokens + test_ui_parity_qt 14 pass.
  Shots (looked at): build/d2shots/d3_{peer_open,peer_listen_only,chapter_menu,shortcuts,toast_action,toast_undo}_{light,dark}.png,
  d3_reading_{paper,ivory,night}_light.png.
- ui_parity_qt: new screen "Studio máy khác" (StudioScreen, PeerBar, EmptyState ~ PeerBar.tsx, peerStudio.ts, App.tsx PeerTrouble /
  StudioClosed); Toast in "Chung" (+ App.tsx App); ShortcutsDialog / PlayerKeys in "Cài đặt". docs/UI_PARITY_QT.md regenerated.
- Open: "Đọc chương này" of the chapter menu is not in Qt (no reader screen yet); the peer Studio has no Studio body (Qt Studio is still the
  placeholder) and "Về Thư viện" there also leaves the peer (Qt Library always shows this computer); the shell has no updater (see 5);
  only one toast at a time (sonner shows 2); touch sound latency on MF (engine created on first sound) not measured on Windows.
  Windows-only files changed without a compile here: src/main.cpp, src/backend.cpp/.h - build.bat on the owner's machine needed.

## D2 — Cài đặt, Thêm sách, Sửa sách (cloud, branch dev/cloud-qtd2 from b840c2e1 Codex WIP), 26-10-2026

- Linux build: Qt 6.10.2 from conda-forge (download.qt.io is blocked by the cloud proxy, so not aqt / not 6.10.3). CMake builds the app target
  (Media Foundation, QWindowKit) only on WIN32; every QtTest / QtQuickTest exe builds and runs on Linux offscreen. Windows-only code unchanged
  and NOT compiled here (main.cpp sample MfAudioOut, audioout_mf, windowchrome) - build.bat on the owner's machine still needed.
- Shared primitives matching shared/ui.tsx + SettingsNav: SettingRow, SettingsItem, SectionBlock (= SettingsBlock, persisted fold via
  Platform "fold.settings.<key>"), ChoiceRow (sliding underline), DisclosureRow, MoreInfo, Collapse, Select (popup list, check first),
  Button (ghost/danger, sm/md/lg, wrap, busy + onActivated), Modal (= Dialog: title/description/✕, scroll fades, footer, keepOpen hook for
  inner steps), FormField (= input, wraps). DESIGN 5.1 + gen_theme: hover, control-line, danger-soft, scrim tokens.
- Screens: SettingsScreen shell (two columns, baseline-aligned group title, compact list/group pages with Back) + one file per group
  (Voice*, Listen/Sleep/Look/Advanced*, MyMusic*, Devices*/PhoneSync*/OtherComputers*, Studio settings/BookTemplates/SharedReadings/
  NewBookDefaults), AddBook + Import*, EditBook* + CoverSearch + BookMusicSettings, BookPage "Thêm" menu. Player night schedule fixed to
  the web semantics (+5 PlayerTests).
- Tests: DesktopApi 8, Player 31, ReadAlong 14, Music 37, SkipGlyph 6, Sidebar 117, Width 210 (tst_d2 + tst_d2_settings/voice/devices/
  studio/addbook/editbook + tst_d2_shots) = 423 pass. Screenshots: build/d2shots/*.png (light + dark, 1440 and narrow), written by the
  Width suite. ui_parity_qt maps Cài đặt / Thêm sách / Sửa sách; render 6 s (memoised key_loose).
- Open: "Mở Studio" of a paired computer and rename-chapter from the chapter row "…" have no Qt trigger/page yet; music cues of the playing
  book reload only next chapter after "Tự chọn nhạc nền"; letterShortcuts / touchSounds / readingSurface are saved but not used by Qt yet;
  update-checked event from the shell has no Qt channel (polls /api/app); web toast actions ("Hoàn tác", "Mở thư mục") not in Api.notice;
  offscreen software renderer paints Shape icons outside a clipping Flickable (not checked on D3D).
  -> D3 (below/above) closes all of these except the Shape/D3D note.

## RAM — 26/27-10-2026, dev/desk-qt-ram (Music lane, from 7a195ca9)

Display conditions for every number below: Parsec virtual display 60 Hz (laptop panel not attached), D3D11, window 1920x1080 client, fixture deskqt_fixture_music, player scenario, muted. RAM = private working set (Task Manager "Memory"), not commit. Runner: D:/Novels/native_desk_proto/ramrun.py (configs interleaved per round, EXE= picks another build); results in D:/Novels/native_desk_proto/results/ram_*.{txt,json}.

Changes:
- Working set trimmed 2 s after the window is minimised (Platform::eventFilter, SetProcessWorkingSetSize -1/-1). Background playback only touches the audio pages.
- Segment Heap opted in through src/abookdesk.manifest: freed heap goes back to the OS instead of staying in NT heap segments.
- Bench player scenario: restore step after minimise (restore_begin/end). measure.py reports private_min_settled_mb (median of the last 3 s minimised), restore_first_ms and restore_max_gap_ms.

Before/after, 4 interleaved rounds, medians (ram_final1; base = 7a195ca9 build):
| | idle loaded | follow | minimised, settled |
|---|---|---|---|
| scale 1.0 before → after | 49.5 → 47.2 | 56.2 → 54.4 | 55.0 → 8.8 |
| scale 1.4 before → after | 57.2 → 54.8 | 63.9 → 61.5 | 60.8 → 10.2 |
- Restoring after trim costs nothing visible: first frame 32 → 17 ms; the ~250 ms gap on restore is present with and without the trim (ram_trim1). Pages come back lazily: 17-26 MB 1.5 s after restore.
- CPU while minimised and playing: 1.8 → 1.6 % of one core (ram_gpu1); the trim does not add CPU. Both are above the < 1 % budget; this was not in scope.
- Segment Heap alone (ram_seg1): follow −2 MB, minimised −4 MB, idle −1 MB at 1.0.

Measured parts (ram_parts1..5, ram_probe1):
- QApplication instead of QGuiApplication: +1.5 MB.
- Music engines (MF): ~1.7 MB.
- Scale 1.4 vs 1.0: +8-11 MB.
- No gain: glyph atlas 512, no distance field, QQuickWindow::releaseResources on minimise, software backend.
- Cover decode already uses setScaledSize (decodes at shown size).

Open:
- Idle at 1.4 is bimodal, ~50 or ~58 MB, both before and after. A private region grows in place to ~30 MB after library_loaded/first_cover (cover texture uploads) and stays; it most likely belongs to the graphics driver.
- GPU adapter matters more than anything above (ram_gpu1, scale 1.4, new build):
  - NVIDIA (default here): idle 55.8, follow 61.5.
  - AMD Radeon 610M (QT_D3D_ADAPTER_INDEX=1): idle 62.9 (57-78), follow 76.9, minimised settled 8.7.
  - On the laptop panel, Windows may run the app on the AMD iGPU. Re-measure there when the panel is back.

## CPU — 26/27-10-2026, dev/desk-qt-cpu (Music lane, from 875f71b2)

Goal (Lead): < 1 % of one core while minimised and playing; nothing awake but the audio path. CPU = QueryProcessCycleTime / TSC MHz (GetProcessTimes moves in 15.6 ms steps and is useless near idle). Power and display are given with each number: 26-10 evening on battery, Parsec 60 Hz; 27-10 on AC, laptop panel (NVIDIA 2560x1600 180 Hz, AMD 610M driving a 1920x1080 60 Hz screen). Results in D:/Novels/native_desk_proto/results/cpu_*.json.

Changes:
- MfAudioOut::retire(): a source change or stop hands the old engine to a detached thread (Pause, Shutdown, MFShutdown there). Before, SetSource/Shutdown of an engine holding an HTTP source blocked the UI thread 0.3 s to ~6 s, found by an in-process sampling profiler on the main thread: MusicBed::fadeTick -> release -> stop, and Player::onEnded -> load -> openSource. The minimised phase stretched from 8 s to 11-14 s; after the fix 4/4 runs at 8.0 s, chapter 3 -> 4 keeps playing. Likely also behind the 500 ms stall still to re-check on the panel.
- MF events that onEvent ignores (TIMEUPDATE, PROGRESS, ...) are dropped on the MF thread: UI-thread wakes from MF while minimised 157 / 10 s -> 0. Total CPU unchanged (battery A/B 1.6 vs 1.6 %, cpu_ab_batt1).
- QT_D3D_NO_VBLANK_THREAD=1 set in main() unless the environment sets it. Qt's QDxgiVSyncService thread waits on every vblank (180/s on the panel) for as long as the D3D device lives, minimised or not; releaseResources with non-persistent graphics does not stop it. cpu_vblank_ac1 (AC, panel, 3 rounds): idle loaded 0.3 -> 0.1 %, minimised 2.0 -> 1.9 %, follow p99 7.2 -> 7.0 ms.
- measure.py: cycle-based CPU, idle-loaded CPU, host Python CPU, cpu_min_steady (from 5 s after minimise; the working-set trim at 2 s and the soft faults after it are one-off). Player scenario minimised phase 10 -> 20 s.

Where the minimised CPU goes (AC, panel, steady window, per-thread cycles + context switches, bench instrumentation in native_desk_proto/cpu_probe_full.diff):
| | process | MF thread pool | vblank thread | main thread | NVIDIA driver thread |
|---|---|---|---|---|---|
| no music | 1.0 % | 0.55 % (~120 wakes/s) | 0.22 % (180/s) | 0.13 % | 0.06 % |
| music (no loop crossfade in window) | 1.5 % | 1.08 % (~200/s) | 0.25 % | 0.15 % | 0.06 % |
- A loop crossfade in the window (fixture music is a 40 s WAV) opens a new engine and steps volume 20 times a second: 2.7 % for that window. Real tracks are 2-4 min, so this is rarer.
- Host Python 0.1 %.

Floor: IMFMediaEngine alone in a minimal C++ program (native_desk_proto/mffloor/mffloor2.cpp, STA thread with a message pump, volume 0, AC):
| source | CPU |
|---|---|
| voice mp3 (fixture) | 0.36-0.42 % |
| real music mp3 (Incompetech, 3.4 MB) | 0.61-0.72 % |
| voice + music mp3, two engines | 0.96-1.06 % |
| fixture WAV, file / over HTTP | 0.24 / 0.45 % |
=> With one IMFMediaEngine per source the < 1 % budget cannot be met while music plays (two engines are ~1 % on their own). Without music: ~0.8 % expected with the vblank change. Proposed to Lead: keep MF for the voice; music through one WASAPI stream with a ~1 s buffer, IMFSourceReader decoding in large chunks and the crossfade/volume mix done in code.

Open:
- Combined A/B (base 875f71b2 vs this branch, 4 interleaved rounds, steady + idle) on AC on the panel: not run yet. Each run brings the window on top of the owner's screen; waiting for Lead.
- On the panel, the window renders no frame in the 1.5 s after restore from minimise. This happens on 875f71b2 as well (Parsec: first frame 17-60 ms). DWM may be showing the last frame; still to check by eye.

## qtwide2 — lead review, 26-10-2026

- Book composition is centred and capped at 1360 px (summary + 32 px gap + chapters). Cover shares the title's left edge from expanded. ChapterRow keeps title/chapter on the left and duration at the right inset with tabular figures; current/hover fill and progress retain full row geometry.
- Replaced the box-only empty-band check with recursive Text.paintedWidth extents of complete visible rows, including text alignment. Negative control using the previous BookPage/ChapterRow fails at 1920 (64.70% empty) and 2560 (74.01%); current QML passes at 10.43% / 21.31%. Saved old QML and logs in build/qtwide/{old_BookPage.qml,old_ChapterRow.qml,old_ink_control.txt,new_width_test.txt}. Alignment tolerance <=1 px, composition cap/centring at 2560, duration tnum and actual hover/current pixels tested in light/dark.
- The newly captured intermediate resize frame exposed cover/text/list overlap. Routed the same 220 ms geometry transition in two stages; tested separation in both directions and reduced motion. Final build exit 0; CTest 6/6; Width 38, total 238 (=26+14+37+6+117+38). Theme/text-cut/diff checks pass.
- Re-shot and opened 44 PNGs: Book/Library 1024×700, 1440×900, 1920×1080, 2560×1440; Now Playing/Settings through 1920; current+hover, rail, scroll, resize and Studio, light/dark. Opened 14 new 2× edge crops. shot.py now bypasses monitor max-track clamping for client= and checks actual size; all PNG dimensions validated. Reproduce: venv Python tools/qtwide_review.py shots2 (or audit2 for dimensions/crops only). Evidence: build/qtwide/{shots2,zooms2,shots2_dimensions.json,build2.log,ctest2.log}. Now Playing composition kept as approved by lead.
- Auxiliary idle sample: 59.22 MB median of 3 runs (55.72–68.52 MB); earlier qtwide median was 58.85 MB. Isolated fixture/profile only, all windows opened here closed; no commit or protected-source/dependency changes.

## qtwide — 26-10-2026, dev/desk-qt-wide

- Content width thresholds live in the generated Theme: 600 / 840 / 1200 / 1600. DESIGN on this base has no "Khổ cửa sổ" section; generator marks the temporary block for moving into the DESIGN parser.
- Book: fixed 320–380 px summary and independent full-width chapter list from expanded; capped 2:3 cover; compact summary preserves at least four chapter rows even with the player bar. Conditional top/bottom fades. Now Playing splits at large. Library centres full/partial rows and keeps covers 160–200 px through 2560. Settings has two columns from expanded; Studio is centred at max 800 px. Geometry uses 220 ms Theme motion, disabled by reduced motion.
- WidthTests uses real screen QML and Player/BookDetail/ReadAlong, fake HTTP/audio. 31 pass; existing suites 26 + 14 + 37 + 6 + 117 pass (231 total). CTest 6/6, text-cut and generated-theme checks pass.
- Isolated fixture and LOCALAPPDATA under build/qtwide; 36 light/dark captures at exact 1024×700 / 1440×900 / 1920×1080, including rail, scroll and resize frames, all reviewed at full size and with 2× edge crops. Book idle private RAM, 1920×1080 client, three runs each: 55.73 → 58.85 MB (+3.12). Tools: qtwide_review.py, shot.py client=W,H. Results in build/qtwide; no owner's settings/library touched, no commit.


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

## Voice mixer (owner 27-10, dev/desk-qt-voicemix)
- Baseline f92a0b3e clean. Locked quality hash c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886 verified from code; do not touch abook. No commits. Every app/build offscreen with guard.
- Implementation: keep music PCM cache; add bounded streaming MP3 range source for voice; raw decode-ahead ring -> Sonic at render time so rate changes do not wait behind 2 s of stretched samples. One shared WASAPI client.
- Next: range source + indexed MP3 decoder, Sonic wrapper, integrate mixer and delete audioout_mf; add tests then guarded build; guarded A/B x4, hidden 120 s, capture analysis; root report.md.
- Implemented streamsource (QNAM ranged reads to compressed disk spool; 200 fallback spools from zero; validated Content-Range), indexed MP3 decoder in mp3source.cpp (gapless + ten-frame preroll), TimeStretch Sonic wrapper, MixVoice::Voice with source-speed 2 s ring and 30 ms device lead. Main audio/preview/Feedback all share mixer; git rm audioout_mf.*. Added VoiceTests and 16 s deterministic CBR/VBR fixtures. PlayerTests/MusicTests untouched.
- Extended WASAPI to mono float/PCM16/PCM32 and endpoint format property notifications; fixing initial linker include order (initguid before mmdeviceapi). Current build: tools/build_hidden.py voicemix-fourth; logs build/hidden-evidence/build-voicemix-fourth.log.
- Baseline binary+runtime copied read-only from ABook_qtint exact f92a0b3e (only report.md modified there), SHA f6fb3f840a30811f7e6e0ed4626eab8e0f5352a8d041961ee98314730fbfef94, in build/voicemix-evidence/baseline with provenance.json.
- Follow-up final build (before queue fix) exit 0, 746 pass / one existing intentional glyph skip. Found and fixed music-only 600 ms lead inherited on narration resume; now trims/rewinds shared queue and uses 30 ms from the first narration fill. Added two threaded fake-device cases; VoiceTests now 26 pass, including <50 ms all-pause Reset. Current source locked hash still c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886. LF check clean.
- ACTIVE validation runner: tools/voice_validate.py --build voicemix-queue-final --resume, tool exec session 28877. It runs final full guarded build, hidden 120 s real chapter, alternating A/B x4, offline PCM export, signal analysis in sequence. Logs build/voicemix-evidence/validation-*.log; build log build/hidden-evidence/build-voicemix-queue-final.log. If interrupted: read logs + ab.json, then run tools/voice_validate.py --resume (do not rebuild without a source change; --resume preserves completed A/B rounds and hidden evidence by executable hash).
- report.md at root is a draft with implementation and explicit limits. After validation, fill exact suite totals, per-round CPU/private commit/WS tables, hidden media advance, numerical signal evidence; inspect failures before claiming completion. Physical nonzero MF/WASAPI loopback is incompatible with mandatory mute. Device inventory has only Speakers (Senary Audio) and Microphone Array (AMD Audio Device), no Bluetooth endpoint present; A2DP/HFP real-hardware test unavailable.
- Voice final full guarded build voicemix-queue-final: exit 0; see build/hidden-evidence/build-voicemix-queue-final.log and -audit.json.
- 21:49 local: voicemix-queue-final full guarded build exit 0 (748 pass, existing glyph skip). Hidden/CPU/RAM launch REFUSED before starting an app: GetSystemPowerStatus ac=0, battery 64%, corroborated Win32_Battery status 1. Asked owner asynchronously to connect AC; no battery timings will be reported as AC results.
- Final contract audit: hold target until queued seeked actually delivers (not merely reader completion); restore playing notification after underrun/seek so unchanged Player audible/sleep accounting resumes. Added 2 regressions. ACTIVE command tools/voice_validate.py --build voicemix-contract-final --offline-only (build + signal independent of AC), exec session reported in chat. Next after it finishes: if AC restored run tools/voice_validate.py --resume for hidden+A/B; otherwise report these as pending and document why. Do not reuse stale 748-pass executable measurements after the contract fixes.
- Voice final full guarded build voicemix-contract-final: exit 0; see build/hidden-evidence/build-voicemix-contract-final.log and -audit.json.
- Offline chapter PCM rendered at 1x/1.5x with music crossfades, plus SourceReader reference. This is signal evidence, NOT an MFMediaEngine/WASAPI loopback capture. See build/voicemix-evidence/chapter.json.
- Offline signal analysis completed: build/voicemix-evidence/signal.json.
- voicemix-contract-final full guarded build exit 0: 750 pass, 1 existing intentional skip; offline whole real-chapter PCM validated at x1/x1.5 (750.950 s / 500.627771 s; length errors 0 / -0.001111%; RMS vs SourceReader +0.000785 / -0.100807 dB). 5 / 3 music crossfades. No special boundary spike enrichment (~0.1% over all-sample p99.9); zero nonfinite, peaks <0.81. This is offline evidence only. Signal JSON+WAVs under build/voicemix-evidence; offline render audit has executable/input SHA.
- Final nonblocking audit found voice reader held state mutex during local reads/index scans. Refactored decoder ownership to shared epoch; decoder open/seek/read now outside mixer/UI mutex, publish only on matching generation/seek target. Added 300 ms stalled fake-decoder regression for <50 ms pause/stop. Source end now reports full duration after Sonic rounding. ACTIVE final full build tools/build_hidden.py voicemix-final-io; after it passes, capture final test totals/hash and update report. Battery still AC=0 (59% at 21:57), so no valid CPU/RAM/hidden run yet. Resume AC work with tools/voice_validate.py --resume after charger is connected.
- voicemix-io-validated full guarded build exit 0: 751 pass, 1 existing intentional glyph skip. First battery functional hidden run passed: 119.519 media / 120.053173 wall seconds, exit0, foreground0, no source-buffering events during hide. Its 0.534 s media/wall deficit prompted multimedia scheduling audit.
- Added normal Windows MMCSS Audio task registration (HIGH) for render thread; revert on thread exit. Added trace-only mix_device_empty and mix_mmcss_failed diagnostics to distinguish endpoint starvation from source starvation. ACTIVE full build build_hidden.py voicemix-mmcss, followed automatically by battery-functional hidden run label voicemix-functional-mmcss (exec 87728). This run is not AC CPU/RAM evidence. Read its app log for empty/failure counts before concluding.
- Corrected A/B fixture preparation to replace ALL four narration chapter files with real book2/_book/001.mp3 (startup may select chapter1). Compressed input manifest now chapter-input.json; chapter.json is reserved for offline render results. No A/B data exists yet, so no stale timings reused.
- MMCSS-only hidden run: 119.488 media /120.026472 wall, 11 mix_device_empty warnings, no source-ring underrun, MMCSS registration succeeded. This confirms 30 ms queue + condition-variable timing is unreliable here; do NOT call that path gap-free.
- Replaced narration scheduling with shared WASAPI EVENTCALLBACK + render-ready wait and separate control event. Pause/seek/stop control still interrupts immediately. Music-only mode ignores render events and retains relaxed 250 ms/600 ms lead. Same single client; no legacy path. Added event-driven fake-device wake + pause regression. VoiceTests now 30 pass. ACTIVE build_hidden.py voicemix-events; after it exits0, automatic functional hidden test label voicemix-functional-events (supervisor exec session 26818) checks media/wall delta + device empty counts. Artifacts under build/hidden-evidence and build/voicemix-evidence/validation-hidden-events.log.

### Voice mixer FINAL STATUS (27-10, 22:44 local)
- FINAL CODE: source minimp3/ranged HTTP + Sonic, one WASAPI client for all outputs; MfAudioOut files git-rm; EVENTCALLBACK narration + separate control event + MMCSS. No commits; branch remains dev/desk-qt-voicemix at f92a0b3e.
- Full guarded build label voicemix-events EXIT0: 752 pass, 0 fail, 1 existing intentional glyph skip. VoiceTests30 (incl blocked300ms decoder, seek callback ordering, buffering recovery + sleep accounting, event wakes/pause), Mix76, Player33 and Music38 unchanged. Final exe SHA256 2bdd7b4438f1eee72a3e788a9bb41c1f4a9de9478a1d3eac43841814f101b0b8. Build/dist binary matches.
- FINAL hidden functional run voicemix-functional-events: 120.041 media /120.044753 wall, ZERO endpoint-empty warnings, ZERO MMCSS failures/source underruns/foreground events; clean exit0. Battery-only correctness evidence, not AC performance. Timer-polling starvation was reproduced and eliminated by buffer-ready events. No need to rerun this test on unchanged code for correctness.
- Whole real-chapter offline x1/x1.5 PCM signal checks PASS: length0 /-0.001111%, RMS vs SourceReader +0.000785/-0.100807dB, no exceptional boundary spike enrichment, 5/3 crossfades. NOT physical loopback or human listening. Source WAVs+signal.json+render audit retained. VoiceRender exe unchanged by mixer scheduling fix (hash checked).
- Quality hash unchanged c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886; abook diff empty; LF/diff-check/tool syntax clean. Sonic license/provenance copied into dist/licenses byte-for-byte and build.bat now ships them (packaging-only addition after full build; no binary change).
- BLOCKED ONLY EXTERNAL VALIDATION: AC CPU/RAM A/B x4 (Windows AC=0, owner asked to plug charger; no AC restoration), physical nonzero loopback/audition (mandatory MUTE=1), actual Bluetooth switch (no BT endpoint). Do not claim CPU target or audible equivalence. report.md now final for this state with all numbers, pending table, source/artifact links and exact resume command.
- NEXT only after AC restored: pinned Python -X utf8 tools/voice_validate.py --resume. It preserves completed A/B rounds by exe hash, uses real chapter for all 4 fixture chapters, fresh per-run LOCALAPPDATA/outbox, shared-machine wait and AC throughout. Then fill report CPU/RAM table from build/voicemix-evidence/ab.json. Do not rebuild/restart completed work unless source changes; no commits, Lead reviews.
- Voice hidden 120 s check passed; raw evidence build/hidden-evidence/voicemix.json.
- Voice A/B four alternating rounds complete: build/voicemix-evidence/ab.json, raw-*-*.json; ABOOK_MUTE=1, AC, no foreground events.

## Minimized CPU follow-up (28-10, active)
- Owner: no windows/focus, no commits, pinned Python only. Starting HEAD da5a1d4b; initial tracked modification report.md only. Baseline dist copied to build/idlecpu-evidence/baseline with provenance before source edits. Locked hash c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886.
- Audit: render and decoder already named; decoder uses predicate wait (no timer). Need resolve other threads with NtQueryInformationThread + DbgHelp, audit hidden timers/restore, guarded build and new A/B four alternating pairs plus 120s. Old voicemix A is NOT this task baseline.
- Probe A baseline preserved under build/idlecpu-evidence/probe-A; probe B (ring bulk copy, direct same-rate PCM, named timers + IdleAudit) under current idlecpu-evidence, NOT final measurements. Identified decoder as largest other worker (~0.168 nominal-cycle proxy), main ~0.164, render ~0.073. GetThreadDescription returns success HRESULT 0x10000000 here; fix sampler to SUCCEEDED >=0, not ==0. Start addresses now NtQuery class9 + DbgHelp (local/export nearest symbols retained with offsets).
- Probe hidden 20s timers: music sync80, progress20; clock/readalong counts unchanged. Changed to music deadlines, hidden progress5s, deferred library fetch, suspend UI clock with synchronous restore, visibility-aware QML polling + resumed refresh, stop infinite animations and shared durations0 while hidden. Bulk ring spans/direct PCM remove per-sample wrap checks and a per-MP3-frame temporary.
- Full guarded build idlecpu-first currently testing (first full build; new Player hidden-clock regression). Foreign D:/Novels/ABook_qtpar WidthTests also running; if width animation test fails rerun width alone. Strengthened wait_for_machine to include test/compiler/build tools and idle runner. No performance run while foreign work active. Next add deadline/restore regressions, resolve symbols off-line, final build, final A/B (archive probes first), hidden120s, replace root report.
- First build native suites green (including Player hidden clock). Width: 414 pass, 2 fail, 1 skip. Diagnosed studioCentred as our UiActivity zero-size Item entering child-layout audit; fixed it to a nonvisual QtObject with explicit target (less memory, no layout child). Chapter-menu intermediate-animation check overlapped foreign width tests; rerun alone in final build. Added deadline step/rate/loop tests, actual storage minimize/hide/restore network tests, main shell/motion restore test.
- ACTIVE final build command: pinned Python -X utf8 tools/build_hidden.py idlecpu-final, exec session46712, waiting for foreign compiler/WidthTests. Logs build/hidden-evidence/build-idlecpu-final*. No final A/B rows yet; probe-A and probe-B archived separately. Offline DbgHelp public PDB resolves system starts exactly (ucrt thread_start, ntdll TppWorkerThread, mswsock SockAsyncThread, WINMM timeThread); Qt/app release binaries expose nearest exports only, retained as such. tools/idle_symbols.py runs AFTER timings.
- Final full build idlecpu-final EXIT0: 765 pass, 0 fail, 1 existing intentional glyph skip. Width421 incl both new polling/restore cases and main minimize/motion case, all pass. Existing StudioSettings fixture warnings also occur in old voicemix-B-final; not introduced here. Final build/dist exe SHA53520fcade9d212e7d928b5f2becf2d229f887b0118e4adff0904e8ae81140c1. Locked hash rechecked unchanged.
- ACTIVE A/B: pinned Python -X utf8 tools/idle_ab.py --rounds 4 --resume, exec session82381. Started round1 A after 70.414s shared-machine wait; no final rows yet at09:45. Preserve this binary; --resume validates hashes and keeps completed rows. Evidence build/idlecpu-evidence. Each sample checks AC; compiler/test activity detected during a run excludes the attempt (raw retained under excluded/).
- After AB: pinned Python -X utf8 tools/idle_hidden.py --label idlecpu --rounds 1 --offscreen --require-mixer --fixture-source _internal/desktop_qt/build/idlecpu-evidence/fixture . Fresh task-local evidence build/idlecpu-evidence/hidden/idlecpu.json. Then idle_symbols.py after measurements, final report/table/hash/LF checks.
- Two initial A attempts excluded because foreign cl/link work started mid-run; foreground0, clean exits, raw under idlecpu-evidence/excluded/. No accepted AB rows yet at09:48. Added 30-second sustained quiet to shared gate and automatic requeue on contamination (functional/AC/focus failures still hard-fail). ACTIVE replacement AB session11332, same command --rounds4 --resume, same binary hash; sessions82381/13235 have exited.
- 09:53: four A attempts excluded so far; foreign build bursts continue starting after the quiet gate. Native code/testing complete, no accepted CPU rows yet. Session11332 automatically queues again and preserves every rejected attempt. Need an uninterrupted ~15-minute desktop build/test quiet window for eight final A/B runs + hidden check. Astera orchestration skill inspected to coordinate, but astera command and ASTERA_CLI absent; no external messages sent. Continue waiting; do not weaken gate or count contaminated attempts.
- STAGE1 complete: 4 clean alternating AB pairs, A medianCPU0.629636/cycleproxy0.430868; B53520f medianCPU0.265688/proxy0.323228. Target NOT met. Quiet hidden120 PASS: wall120.026378/media120.022, zero starvation/focus, AC2 start/end, no shared busy; steady114.799s CPU0.285825. First hidden run also clock-clean but excluded for foreign compile.
- Native Windows/D3D probe (never-switched desktop, x=-10000, guard): no SMTC error; NVIDIA nvwgf2umx worker96 dispatches/s plus ntdll worker64/s despite minimization; 21 frames at min+2.374..2.506s. Native driver work not visible in software-QPA AB. Thread-pool ETW attempt denied 0x80070005; no trace session started. Native full module maps captured. Need investigate releasing persistent Qt graphics while all windows hidden, then restore.
- BEFORE SOURCE CHANGE: stage1 AB rows/raw/app logs and exact B exe archived in build/idlecpu-evidence/stage1; native/ and hidden/ retained separately. Baseline da5a1d4b remains immutable baseline/. Native code last green765 exe53520f; if graphics fix lands require new build + final AB/hidden for new hash. No current active measurement process.
- Graphics candidate added: GraphicsIdle toggles persistent RHI/scene graph off and calls releaseResources once when all windows hidden; restores persistence when any window shown. New restore-pixel + retained-QML-state regression in MusicWindowActivityTests (links QtQuick). First compile-only probe failed because CMake was already configured with old Gui-only target before the CMake edit; not a code test failure. ACTIVE compile-only probe2 session (see chat), then run the graphics unit under guard and a separate native probe before deciding whether to keep. Need new final full build + AB/hidden only if kept.
- Graphics compile-only probe2 EXIT0. Guarded MusicWindowActivityTests5/5 incl actual QML state and restored pixel color PASS (graphics-unit/test.txt/audit.json). Candidate build exe SHA44b1a2819988249b834af278db6605185dc0c826cacb2ec998820a96770cf807; dist still previous53520f until full build. ACTIVE native candidate probe session96227: pinned Python -X utf8 tools/idle_ab.py --rounds1 --probe-b --native --evidence build/idlecpu-evidence/native-graphics (ABOOK_CAPTURE_MODULES=1). Need compare NVIDIA/Windows workers vs native/ raw old53520f, decide keep, then final full build (expected766 pass), fresh final AB4 + hidden120. Stage1 four AB and clean hidden still valid only for old hash53520f, never reuse as new binary timings.
- DECISION 10:37: reject graphics candidate44b1a2. It did not eliminate NVIDIA96dispatch/s; no native restore frames in this off-screen private-desktop setup for either candidate or prior build. Native sampling also sparse (~7.5s steady) due symbol work, so no reliable total CPU win claimed. Experimental header/test/binary moved/copied under graphics-experiment/. Production CMake/main/test restored exactly to measured source53520f; build/dist exe both restored to immutable measured53520f. Final full765-pass log is idlecpu-final (same final source, before rejected experiment); do not rerun source-changing ideas.
- Clean hidden120 old/final53520f: wall120.026378/media120.022; CPU0.285825 over114.799s, decoded0.122496/render0.068053/main0.040832, ntdll pool0.027221, QNAM0.013611 conventional CPU%; zero starvation/focus/foreign workloads, AC2 start/end. Thus actual audio threads alone~0.19055 exceed0.15: target missed even if all UI overhead removed. No physical global lower bound claimed.
- Remaining: offline final per-thread tables for ALL captured threads, public DbgHelp symbol resolution including native driver modules, final report.md replace, hash/LF/Python/diff checks. Source is final; no current app/benchmark running. Restore/focus tests already pass; never count graphics experimental data as final performance.
- New targeted public-event guard in MusicWindowActivity: skip UpdateRequest and positive re-exposure while minimized; still deliver obscurity. First version guarded all hidden QWindow objects and native probe produced ZERO frames even while visible (bad; NOT ship). Tightened to QQuickWindow + explicit Minimized only (hidden windows use normal Qt hide path); enhanced actual QQuickWindow regression asserts visible pixel before min and after restore, plus suppressed min update delivery. CMake test now links Quick.
- ACTIVE compile-only idlecpu-redraw-probe2 (session95880) for corrected guard. Prior redraw-native data under native-redraw/ belongs to bad prototype cf94cd4 and is NOT valid performance. Need unit+native probe with nonzero visible/restore frames and zero minimized frames; if not proven, reject guard and restore tested53520f source/artifact. No unsafe private Qt render-loop API used. Main source currently stage1 plus guard header change; graphics release hint removed.

- RESUME 28-10: corrected redraw native probe c486e8 also had zero visible/restore frames; reject, archive under redraw-experiment/. Restore MusicWindowActivity header/test exactly from HEAD and Gui test link; restore stage1 measured53520f build/dist. No runtime source changes beyond original765-pass source remain. Astera CLI absent; using owner-authorized guarded offscreen harness. Finalize thread/timer evidence and report.

### FINAL minimized CPU review (28-10; supersedes ACTIVE notes above)
- No task benchmark/app remains running. No commits. Final runtime source is the original765-pass stage1 source; rejected graphics/redraw guard removed. Header/test are byte-identical to HEAD and MusicWindowActivityTests links Gui. build/dist/preserved stage1 B all SHA53520fcade9d212e7d928b5f2becf2d229f887b0118e4adff0904e8ae81140c1.
- Root report.md REPLACED with complete final result: four clean alternating pairs A medianCPU0.629636 vs B0.265688 percent of one core; RAM and every round recorded. Target0.15 NOT achieved. Clean hidden120: wall120.026378/media120.022, CPU0.285825; decode0.122496+render0.068054=0.190550, above target before UI costs. Native driver/pool dispatches remain; no absolute lower-bound claim.
- Offline tables now include expiring threads omitted by first/last intersection:30 per AB run,32 long-hidden,96 native. All per-TID starts/modules/symbols/CPU/dispatches and available actual app wait counters in build/idlecpu-evidence/thread-tables.md and threads-final.json. Hidden expiring pool worker accounts for additional0.013611, reconciling process total. Exact private driver/Qt wake callbacks/rates remain UNKNOWN (ETW denied0x80070005); never label scheduler dispatches as wakes or distant exports as actual symbols.
- tools/idle_report.py reproduces tables, validates all8 accepted raw runs and power/binary identity, emits full timer-audit.md and audit-summary.json. tools/idle_symbols.py --input build/idlecpu-evidence/threads-final.json resolves only final identities without mixing prototype binaries; rerun report after symbols. Completed on resume; no need to repeat measurements for unchanged B.
- Final checks: full build totals765/0/1 confirmed from retained log; all modified/untracked text LF,10 changed/new Python tools parse, git diff --check clean, abook diff empty, locked hash unchanged c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886. Manifest final-manifest.json records current source/tool/doc hashes.
- Remaining owner target is explicitly missed, and exact driver wake attribution/native zero-repaint from the instant of minimize are not proven. Any further decoder/output/native renderer improvement must be a fresh source change with new build/functional checks/binary-specific timings; do not count rejected experiments as final. Lead reviews uncommitted diff.
