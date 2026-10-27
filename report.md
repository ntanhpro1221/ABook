# Qt desktop integration - 27 October 2026

Worktree: `D:/Novels/ABook_qtint`, branch `dev/desk-qt-int`.
Sources applied in order:

1. `origin/dev/desk-qt-hidden` - `36c7c452fb9c9f2a2465b0f1a7c83b7e3f7cc13a`
2. `origin/dev/desk-qt-cpu` - `d1408cf7054a1ceece6d96d426b54224fb0407df`
3. `origin/dev/desk-qt-smtc` - `08a415c30a358397e71d55d60749a2ccf76c5268`

No commits created. HEAD stays at `efa56eade1878fe61523d5190e6c54fba55add10`.
The hidden branch was merged with `--squash`; subsequent three-way merges
used the resolved index tree and each branch's merge base. This preserves
ordered conflict resolution without intermediate commits. The combined diff
is staged for Lead review.

## Conflict decisions

| Merge | File | Resolution |
|---|---|---|
| hidden | `_internal/desktop_qt/qml/Main.qml` | Preserve D3's shared PlayerKeys handler, letter shortcuts and question-mark dialog. Add mini-specific shortcuts and WindowMode. Keep D3's actionable top-right Toast, suppress it in mini mode, and retain its `t > 0` visibility condition. |
| hidden | `_internal/docs/UI_PARITY_QT.md` | Regenerate from the combined source using `ui_parity_qt.py`; neither branch's copied counts describe the integrated QML. |
| cpu | `_internal/desktop_qt/src/audioout_mf.cpp` | Hidden already contains CPU's asynchronous retirement and MF-thread event filter. Keep its later timestamp diagnostics and comments describing the remaining voice path. Do not reintroduce MF music engines. |
| cpu | `_internal/desktop_qt/src/main.cpp` | Retain hidden's pre-start/window safety setup together with CPU's existing `QT_D3D_NO_VBLANK_THREAD=1` default and explicit environment override. |
| cpu | `_internal/desktop_qt/tools/measure.py` | Keep CPU/host sampling already present in hidden, plus the pre-resume foreground guard, separate desktop, configurable timeout, app logs, and normal-exit evidence needed by the longer mini scenario. |
| smtc | `_internal/desktop_qt/CMakeLists.txt` | Union MusicWindowActivity and MediaControls sources; union mixer/decoder, DWM and WinRT/shell libraries. Keep all mixer tests and add SMTC targets/tests. Link the actual SMTC adapter into WidthTests for cross-surface integration coverage. |
| smtc | `_internal/desktop_qt/build.bat` | Keep global offscreen QPA. Use SMTC's logged test helper for all ten suites, including Mix and MusicWindowActivity. Preserve rejection of nonzero/negative process exits and `FAIL!` log entries. |
| smtc | `_internal/desktop_qt/src/main.cpp` | Union mixer, all-window activity observer and SMTC setup. Keep alpha-buffer setup, vblank default and DWM/window guard; add SMTC's native CBT activation/focus guard before QGuiApplication. Attach SMTC to the shared main/mini QWindow after QML load. |
| smtc | `_internal/desktop_qt/tools/measure.py` | Keep hidden's guard, separate-desktop launch, DWM checks, timeout and process-exit evidence. Retain SMTC's machine-idle wait, AC check, bounded working-set sampler and audit metadata. Use unique output filenames without deleting old evidence. |
| smtc | `_internal/docs/CHANGELOG.md` | Keep both the mixer/hidden-clock entries and Windows media-card entry under the desktop section. |
| smtc | `_internal/docs/TEST_REPORT.md` | Preserve both branches' historical evidence; add this integration's separately identified validation results. |

## Integrated behavior

- Music uses only the shared WASAPI mixer. Narration, preview and feedback keep
  MF; MF voice source changes/stop retain off-thread retirement and ignored
  events are filtered before entering the UI queue. No migration or alternate
  MF music path was added.
- MusicWindowActivity examines every visible, non-minimized QWindow. This
  includes mini mode on the reused main window and a separate mini created
  after startup. Regression tests cover both, hiding, minimizing and restoring.
- Mini controls, tray commands and MediaControls use the same Player. A QML
  integration test clicks the real mini play/pause button, observes the actual
  SMTC adapter through a fake sink, then sends SMTC and tray commands back to
  the same Player. It checks labels, enabled states and closing the book.
- Tray previous/next availability now uses Player.canPrevious/canNext, matching
  SMTC, including the last chapter.
- Build execution uses `tools/build_hidden.py` to run a CRLF execution copy of
  the LF `build.bat`; only HERE is redirected to the original source directory.
  Test selection, assertions and offscreen settings are preserved. Every test
  writes its own report under `_internal/desktop_qt/build/`.

## Validation

Full `build.bat` build, all suites, and packaging completed with exit **0**.
Every suite used `QT_QPA_PLATFORM=offscreen`.

| Suite | Passed | Failed | Skipped |
|---|---:|---:|---:|
| MediaControls | 6 | 0 | 0 |
| DesktopApi | 12 | 0 | 0 |
| Player | 33 | 0 | 0 |
| ReadAlong | 14 | 0 | 0 |
| Music | 38 | 0 | 0 |
| Mix/decoder | 73 | 0 | 0 |
| MusicWindowActivity | 4 | 0 | 0 |
| SkipGlyph | 6 | 0 | 0 |
| Sidebar | 117 | 0 | 0 |
| Width/mini/D3 | 276 | 0 | 0 |
| **Total** | **579** | **0** | **0** |

QtTest totals include init/cleanup and data rows. No blacklisted cases.
Supplementary parity tests: **8 passed**, using `python -X utf8 -m pytest
tests/test_ui_parity_qt.py -q` from `_internal`. Theme generation, text-cut
checks, Python syntax checks and the generated parity document check pass.

The first full run exposed an integration issue: the new Main.qml
`Bench.note()` call was missing from the QML Bench stub, aborting D3Main setup.
That Width run had 270 passes / 1 failure; its log is retained as
`build/hidden-evidence/width-test-initial.txt`. Add the missing Bench API and
WindowChrome.setMini stub. The focused D3Main rerun passed 7/7, then the final
full Width suite passed 276/276. No tests or expectations were disabled.

## Single hidden-playback check

**PASS: 120.027 s media advance in 120.029731 s hidden** (required >=118 s).
Chapter 4 stayed playing throughout full -> mini -> hidden -> expanded:
position **13.275 -> 133.302 s** over the hidden interval.

- Exactly one measured application run, with native Windows QPA/RHI on a
  separate Windows desktop, no SwitchDesktop and no native tray icon.
- `tools/measure.py` installed the foreground guard before resuming the
  suspended app. **0 foreground events**, exit **0**, no forced termination.
- Music enabled through WASAPI; SMTC explicitly enabled; real output muted.
  Mixer ready/playing confirmed, four playing events, all ready events
  `decodes=1`, no mixer failure. No SMTC or QML runtime errors in the app log.
- Before launch both shared-machine checks were clear; initial check took
  0.090 s and measure.py required three quiet seconds. No foreign process was
  stopped or modified. Fixture and listening-state writes stayed in this
  worktree's private evidence directory.
- The first launcher invocation waited on its own venv wrapper before any
  application had been created. Only that verified own waiter was ended;
  measure.py now excludes its process ancestry from foreign-job detection.
  The measured run above then completed once, without retries.

Executable SHA-256:
`0924ef1fd28f63fb98c9dfb951f2cefb086b26f7bc29e7a0939405fabc5fced9`.

Evidence under `_internal/desktop_qt/build/hidden-evidence/`:

- `build-integration-final.log`: full successful build/test/deploy output;
  `build-integration-final-wait.json`: pre-build shared-machine check.
- `suite-totals.json`: totals extracted from the ten `build/*-test.txt` logs.
- `integration-final.json`: the single playback result, guard data, samples,
  mixer events, private fixture wait and executable hash.
- `integration-final-1.app.log`: MF timestamps and app diagnostics.
- `quality-hash.json`: code-derived locked-file list, hash and unchanged HEAD.

Reproduce with the approved interpreter (do not run alongside other worktrees):

```powershell
& D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe -X utf8 D:/Novels/ABook_qtint/_internal/desktop_qt/tools/build_hidden.py review
& D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe -X utf8 D:/Novels/ABook_qtint/_internal/desktop_qt/tools/hidden_suite.py --label review --rounds 1 --require-mixer --exe D:/Novels/ABook_qtint/_internal/desktop_qt/dist/ABookDesk.exe
```

Locked implementation hash read from code before merging and after validation:
`c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`.
The code-derived implementation list has 41 entries. No `_internal/abook/`,
pyproject or lock-file changes. All changed text files use LF; staged and
unstaged whitespace checks pass. No commits created.
