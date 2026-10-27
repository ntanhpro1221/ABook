# Hidden playback - 27 October 2026

Fixed and uncommitted on `dev/desk-qt-hidden`. The original MF music path loses
about 9.2 seconds; the merged retire fix still loses about 5.4-5.8 seconds.
Routing music through the shared WASAPI mixer removes the loss in all three
final runs. The `>=118 s` assertion is unchanged and mixer readiness/playback
is additionally required, so failed music loading cannot produce a pass.

## Measurements

Native Windows QPA/RHI, separate Windows desktop, no SwitchDesktop, no native
tray, muted real audio. Chapter 4: full player -> mini for 10 s -> hidden for
120 s -> expand. The process starts suspended; the foreground guard is ready
before it resumes. All runs recorded zero foreground events. No guard bypass.

A/B use the original `3bc1d592` MF implementation plus timestamp diagnostics
inside the merged app/benchmark safety code; C uses merged retire. A-C have
`ABOOK_MUSIC_MIX=0`. The final app has only the mixer music path, with the old
flag and MF music factory removed. A/C/final use identical private WAV music
content; B has its own copy with music disabled. No shared fixture writes.

| Variant | Run | Media advance (s) | Hidden wall time (s) | >=118 s |
|---|---:|---:|---:|---|
| A: original MF, music on | 1 | 110.821 | 120.034 | FAIL |
| A: original MF, music on | 2 | 110.831 | 120.024 | FAIL |
| A: original MF, music on | 3 | 110.739 | 120.022 | FAIL |
| B: original MF, music off | 1 | 120.023 | 120.026 | PASS |
| B: original MF, music off | 2 | 120.015 | 120.018 | PASS |
| B: original MF, music off | 3 | 120.029 | 120.032 | PASS |
| C: merged retire, music on | 1 | 114.254 | 120.043 | FAIL |
| C: merged retire, music on | 2 | 114.606 | 120.020 | FAIL |
| C: merged retire, music on | 3 | 114.217 | 120.028 | FAIL |
| Final: WASAPI music, WAV unchanged | 1 | 120.017 | 120.020 | PASS |
| Final: WASAPI music, WAV unchanged | 2 | 120.014 | 120.017 | PASS |
| Final: WASAPI music, WAV unchanged | 3 | 120.013 | 120.017 | PASS |

Raw JSON, copied logs and executable SHA-256 values are under
`_internal/desktop_qt/build/hidden-evidence/`: `a-original.json`,
`b-music-off.json`, `c-retire.json`, `e-mixer.json`, matching `*-1.app.log`
through `*-3.app.log`, and derived `summary.json`. Original/retire control
executables are retained in `bin-original` and `bin-retire`.

## Cause and timestamps

Music loop handoff around narration position 38 s releases an MF music engine.
The original `MusicBed::release -> MfAudioOut::stop` path clears its source
synchronously; in A1 `state=stop` is at **29537989 ms**, followed by narration's
next TIMEUPDATE at **29547418 ms**. Narration loses real media-clock progress.
No narration PAUSE/WAITING event explains the loss.

Retire moves teardown off the UI thread but does not cure the media-clock
freeze. In C1 callbacks keep arriving about every 260 ms while narration stays
at **41.664 s**. Thus callback gaps alone are insufficient to detect this bug.
The table brackets consecutive narration samples with lost clock progress;
timestamps are monotonic milliseconds on the benchmark's steady clock.

| Variant/run | Trace interval (ms) | Seconds after hiding | Media positions (s) | Lost time (s) |
|---|---|---|---|---:|
| a-original, 1 | 29537741-29547418 | 24.574-34.251 | 37.764-38.231 | 9.210 |
| a-original, 2 | 29678690-29688192 | 24.749-34.251 | 37.901-38.221 | 9.182 |
| a-original, 3 | 29820037-29829706 | 24.527-34.196 | 37.713-38.102 | 9.280 |
| c-retire, 1 | 30956946-30962884 | 28.456-34.394 | 41.606-41.757 | 5.787 |
| c-retire, 2 | 31098265-31103961 | 28.713-34.409 | 41.871-42.156 | 5.411 |
| c-retire, 3 | 31238778-31244761 | 28.326-34.309 | 41.500-41.676 | 5.807 |

The failure is associated with MF music-engine teardown while narration is
playing. Its Windows-internal locking behavior is not established. Music-off
removes it; removing MF music-engine churn also removes it while music plays.

A rejected persistent-COM-worker experiment advanced 110.897 / 110.766 /
111.883 s in 120.031 / 120.008 / 120.016 s. In its first run retirement itself
took 9.330 s (31634347-31643677 ms), despite COM already being initialized.
That patch is removed; `d-fixed*` retains the failed experiment's evidence.

## Final diff

- Resolve the uncommitted merge of `origin/dev/desk-qt-musicmix` **84d72668**,
  which includes `origin/dev/desk-qt-cpu` **d1408cf7**. HEAD remains 3bc1d592.
- Integrate the playback/decoder/test subset of the subsequent committed music
  work **3a04cbde**. Music uses one WASAPI output and a PCM cache, never MF
  playback engines. MP3 uses minimp3; other recognized containers use
  IMFSourceReader once to build that cache. Unavailable codecs report failure.
  Narration keeps MF and the merged retire fix. The follow-up's cloak/benchmark
  changes are not imported; this task retains its separate-desktop launcher.
- Keep cheap `t_ms` timestamps and output identity on MF events/state lines,
  including retirement thread/COM/teardown boundaries. Disabled tracing adds
  no position queries.
- Preserve mini scenario, timeout, pre-start foreground guard, nonactivating
  launch and separate desktop during conflict resolution. Fix measure_mini's
  call for the merged off-screen-only launcher API.
- Add reproducible guarded suite/trace-analysis/build helpers. Keep strict
  negative-exit checks for the two merged mixer test executables.
- Fix the voice-test click helper to render after moving controls into view.
  Initial WidthTests had 223 passes / 2 failures; focused rerun passed 4/4 and
  the final full WidthTests passed 225/225. Original failed log is retained.

## Validation

`build.bat` flow, all tests and packaging exit **0** (`build-final.log`). This
Windows cmd.exe misparses the repository's LF batch file directly. The helper
executes a CRLF copy with HERE pointing to the original source directory and
only redirects QtTest reports; repository files remain LF. Every test uses
`QT_QPA_PLATFORM=offscreen`. No test selection/expectation is disabled.

| Suite | Passed |
|---|---:|
| DesktopApi | 8 |
| Player | 31 |
| ReadAlong | 14 |
| Music | 37 |
| Mix/decoder | 73 |
| MusicWindowActivity | 3 |
| SkipGlyph | 6 |
| Sidebar | 117 |
| Width/mini | 225 |
| Total, including init/cleanup/data rows | **514** |

Final packaged executable SHA-256: `1f198f78d9eaf68b3756863c69bb1719d263a88d38df94d53c2c24902706d02e`.
All three final runs use that exact file, exit 0 without forced termination,
have zero detected narration stalls, and report four `mix_playing` events each.
The original 40 s WAV is decoded once per run and reused across loop handoffs;
all ready events report `decodes=1`, with no `mix_failed`.

Locked hash, read from code before and after: `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`.
The code-derived implementation list has 41 entries (`quality-hash.json`).
No `_internal/abook/`, pyproject or lock-file changes. LF and Git whitespace
checks pass. No commit was created.

## Shared-machine waits and fixture

Before every timed run the helper checks all ABookDesk.exe processes and other
measure.py/ramrun.py launchers and waits; full pre-run records are in each JSON.
Nontrivial measurement waits: b-music-off run 1: 20.907 s; c-retire run 1: 5.112 s.
Focused tests also waited **412.059 s** for successive ABook_qtmix/ABook_qtsmtc
runs; C compilation waited **30.236 s**; the rejected worker build **175.879 s**;
the final full build **467.279 s**. No other job's process was stopped/modified.

The shared fixture's book metadata and media match the SHA-256 snapshot.
Shared `listening.json` and its journal changed while other worktrees ran
ramrun against that fixture; this task writes only private copies and did not
restore or modify those shared state files. See `shared-fixture-check.json`.

Reproduce the final verification with the authorized Python executable:

```powershell
& 'D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe' -X utf8 _internal/desktop_qt/tools/build_hidden.py review
& 'D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe' -X utf8 _internal/desktop_qt/tools/hidden_suite.py --label review-mixer --require-mixer --exe _internal/desktop_qt/dist/ABookDesk.exe
```
