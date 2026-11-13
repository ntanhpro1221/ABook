# parity3

## 1. Baseline — 2026-11-13

- Worktree: `D:/Novels/ABook_parity2`, branch `dev/parity2`, HEAD `73473dfb2` (clean).
- Read parity2 result/spec and both AGENTS.md files.
- Quality implementation list read from code; baseline hash: `71563e9c1a2ecee91b3be33d3300e0f529f3af7ceb77d7c0e18b6ee800489d9d`.
- Previous measured baseline: WidthTests 1603 pass / 14 fail / 4 QML type errors; L7 web 124, Android 161, Qt 0.
- Work in this worktree only; new commits, no push. Python uses the production interpreter with `-X utf8`.

## 2. Qt diagnosis and first repairs

- Stale copy expectations: CastTab, shared readings, chapter menu and two apply-change tests; use current copy (including the L8 menu name).
- Cover button uses the shared 12 px spacing; its test still expected 10 px.
- Toast overlap test compared coordinates from different parents after Collapse was introduced; map both edges into the toast.
- Studio loading test must wait for the outgoing skeleton to finish fading.
- Real layout fixes: apply TextWrap.pretty to pairing instructions, provider limits and toast descriptions; WorkField height now includes both actual paddings.
- Four QML errors are Repeater delegates losing their visual parent during destruction, not singleton lookup. Guard those four width bindings during detach.

## Next

Diagnose and repair Qt failures, then remaining web/Android presence transitions; run all requested gates and record actual counts.

## 3. Remaining L7 sites

- Web: shared Presence retains the last React value, animates custom components' actual DOM roots without requiring forwarded props, and disables outgoing content. Dialog/Sheet receive the presence context so portals close on their own animation clock.
- Web first typecheck: 0 errors. Presence runtime regression tests: 3 passed (custom root, nullable value, reduced fade, exit interruption).
- Android: shared SwapContent snapshots values for AnimatedContent branches; reduced motion uses a real short fade independent of OS scale zero. Layout grouping follows the enclosing Row/Column/Box.
- First structural scan: Qt 0, web 0, Android 0 hard sites. The reduced-motion implementation selector is explicitly classified as motion policy (both paths animate).
- Ratchet edited from 285 to 0; still awaiting full compile/runtime gates.
- Resource checks: free RAM fluctuated from 12 GiB to 1.1 GiB with unrelated machine workloads. Gradle has not started below the 6 GiB floor. Existing WidthTests run remains active offscreen.

## 4. First complete Qt results

- WidthTests: **1615 passed / 2 failed / 1 skipped**, 1085 s; no TypeError lines. All original 14 failure sites passed except Studio1's later assertion (now reachable).
- Remaining failures: toast test expected raw spacing after pretty wrapping; Studio1 expected an older missing-folder title. Both corrected to the actual shared display/copy contract.
- qt_pytests: **166 passed / 2 failed / 3 skipped**; the only failures are generated parity documents becoming stale after source line changes. Regenerate both documents before the final gate.
- Android audit also moved parent-data alignment/weight onto animation hosts and converted early-return render branches into complete retained alternatives.

## 5. Web and Android transition audit

- First full Vitest: 2878 passed / 14 failed / 227 skipped (3119 total); skipped reading forms came from the missing worktree Python. Use ABOOK_TEST_PYTHON pointing at the production interpreter.
- Fixed the seven stale web expectations from parity2 (medium weight and generated skeleton timing tokens), plus three hard-unmount assertions now checking the live tree while exit is inert.
- Fixed new list-key warnings and invalid dl/span nesting. Targeted gallery rerun: 10 passed; targeted web fixes including reading forms: 265 passed; Presence/navigation follow-up: 16 passed.
- Native DOM roots now use wrapper-free Reveal; custom roots use the contents host. Existing animation-end handlers are preserved, outgoing portals close through shared presence context, and custom-root enter animations release their opacity override.
- Android snapshots mutable fields/callbacks explicitly where required; ordinary immutable data snapshots retain their nullable values. Added normal/reduced-motion retention regressions.
- Strengthened the Android L7 proof: an if inside SwapContent must match its contentKey expression, not merely mention any captured parameter. Generic composables are now discovered, exposing four additional real sites that were repaired.
- Current scan: zero hard sites; shared reduced-animation selectors (2) and native PiP window handoff (1) have explicit structural reasons.
- Gradle compilation is scheduled behind the 6 GiB and four-heavy-process resource gate, with one worker and in-process Kotlin compilation. Qt full build follows the Gradle verification.

## 6. Verification in progress

- Full Vitest rerun: **338 files, 3120 passed / 0 failed / 0 skipped**, 521.54 s. Latest Presence follow-up: **4 passed**. Final tsc: **0 errors**.
- Python parity/context regressions: **36 passed** (32 parity-rule tests + 4 QML-context tests).
- Gradle `compileDebugUnitTestKotlin`: **BUILD SUCCESSFUL**, 95 s, after regenerating parity documents. Kotlin app and unit tests both compiled. Launch preflight: 7.96 GiB available, 3 existing heavy processes, 1 compiler slot reserved.
- Starting the complete `testDebugUnitTest` gate with one worker; test totals will come from fresh XML, not the Gradle exit code alone.

## 7. Android first full runtime results and repairs

- Fresh JUnit XML: **3686 tests, 8 failures, 0 errors** (the original 3684 plus two new retention regressions, both passing).
- Five old failures: stale remote accessibility names (2), stale Cast waiting copy (1), skeleton/reduced-fade policy missing in MotionScan (1), and an existing subtitle exception comment placed too far from its binding (1).
- Three new runtime failures: ValuePicker lost its inherited 8 dp gap; DoneButtons used a Box for two vertical actions; Studio export footer depended on its parent's poll subscription and did not observe its own job updates across the animation boundary.
- Repairs: shared group spacing parameter; explicit vertical grouping for DoneButtons; footer collects its own export poll. Tests keep current shared copy; the subtitle's existing documented exception now sits on the relevant Text line.
- MotionScan now proves the skeleton token clock, and accepts fixed reduced fades only with a project-wide check that every helper call is under the positive reduced-motion guard. Planted-fault tests cover unguarded/negated calls and unrelated alpha values.

## 8. Final source review while Qt runs

- Qt full build: qt_pytests **169 passed / 0 failed / 3 skipped**; CMake **51/51** steps succeeded. All completed QtTest suites are green; WidthTests is running offscreen.
- Audited optional web slots: their current content must determine menu/footer availability, even while Presence retains an outgoing tree. Added shared hasPresentContent and a real dialog-footer regression.
- Tightened web motion proof to direct Presence children; an always-present wrapper around an unrelated nested conditional is no exemption.
- The theme snapshot must not receive an extra retained fade: its Bitmap is recycled two frames after release. Restored its original clear-circle layer. New structural b-animated-mask proof requires the displayed snapshot, a full-surface radius, an Animatable clock completed at 1, and BlendMode.Clear; planted wrong-clock/blend faults remain hard sites.
- Layout audit found no remaining multi-node Box branches after fixing DoneButtons and two explicit button/spacer groups. The Precast group also keeps its original 8 dp spacing.

## 9. Qt complete

- Full `build.bat` completed successfully, including packaging and packaged smoke.
- WidthTests: **1617 passed / 0 failed / 1 skipped**, **QML_TYPE_ERROR 0**, glyph missing 0, text leak 0; 1016.923 s.
- All **19** Qt suites reported their totals; every suite has 0 failed / 0 QML type errors.
- qt_pytests in this build: **169 passed / 0 failed / 3 skipped**.
- Dist checks: 0 dependency problems, 46 binary imports checked; SMOKE_OK (Main.qml loaded and drew its first frame without QML warnings).
- Log: `external-artifacts/parity3-qtbuild-final.txt`.
- Committed Qt repairs as **3fce94045** (`Fix Qt width failures and detached delegate bindings`), on top of 73473dfb2; no push.
- Latest Android compilation passed again in 93 s. Runtime tests use a 512 MB Gradle coordinator plus one test JVM after compilation, preserving the four-heavy-process limit.

## 10. Android focused rerun

- 102 tests executed, 3 failures: the actual toggle accessibility name uses a different sentence shape than skip controls; the new reduced-helper detector incorrectly treated SheetLayer (which chooses normal/reduced internally) as a reduced-only helper.
- The previous ValuePicker gap, overlapping export actions, Studio export polling, waiting copy and text-cut-comment failures are now green, as are both normal/reduced snapshot-retention tests.
- Corrected the exact three remote-control name expectations independently. Reduced helper discovery excludes surfaces that choose their own motion policy; regression covers this distinction without exempting unguarded helper calls.
- Queued full final Vitest on the frozen web sources; Android unit-test compilation and rerun follow that serialized resource slot.

## 11. Final full web gate

- Full Vitest on the latest web sources: **338 files, 3121 passed / 0 failed / 0 skipped**, 498.04 s.
- Log: `external-artifacts/parity3-vitest-final.txt`.
- Android test-only corrections are now compiling after the web process released the shared resource lease. No Qt or web implementation changes remain pending.

## 12. Final static gates

- Final tsc invocation: **0 errors**, log `parity3-tsc-last.txt`.
- Final Python parity/context invocation: **38 passed**, log `parity3-rules-last.txt`; includes direct Presence ownership, exact SwapContent keys, mask completion, positive reduced guard and detached-parent runtime faults.
- Complete final Gradle test run launched with **6.36 GiB** free, two existing heavy processes and one reserved test JVM. App/test compilation is already complete; coordinator heap is 512 MB.

## 13. Final Android gate complete

- `testDebugUnitTest`: **BUILD SUCCESSFUL**, 5m26s.
- Fresh XML: **430 suites, 3688 tests = 3676 passed / 0 failed / 0 errors / 12 skipped**.
- Suite timestamps all belong to this run: 2026-11-13T05:00:30.543Z through 05:04:54.187Z (UTC).
- Log: `external-artifacts/parity3-gradle-final.txt`.
- All eight first-run Android failures are resolved, including the five existing failures; no failure budget retained.

## 14. Implementation committed and report finalized

- Committed all remaining implementation/test/detector changes as **eebcb15b9** (`Animate remaining web and Android conditional content`). Staged an explicit 115-file manifest; control-character and LF audits passed before commit.
- Quality hash still exactly `71563e9c1a2ecee91b3be33d3300e0f529f3af7ceb77d7c0e18b6ee800489d9d` before and after the implementation commits.
- Final checks: Qt 2241 pass (WidthTests 1617, all failures/type errors zero); qt_pytests 169 pass; Vitest 3121 pass; Android 3676 pass, 0 failures/errors, 12 skipped; parity/context pytest 38 pass; tsc 0 errors; L1-L10 all 0; ratchet L7 285 -> 0.
- Vietnamese `result.md` contains commits, individual Qt suite totals, root causes, classification counts and all 31 special exemptions with a one-line reason.
- Evidence saved under the requested parity3 scratch directory. No push, amend, branch switch, reset or stash; no production quality files edited.
