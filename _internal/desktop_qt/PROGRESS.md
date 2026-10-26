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

## Next
- final report (lead): files, numbers, controls list, gaps (empty-state has no action button yet; cover CPU copies keep RAM after a long scroll: peak 74 MB, idle 51 MB).
