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
