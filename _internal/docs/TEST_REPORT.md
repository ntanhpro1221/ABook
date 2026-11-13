# Test report

## 14-11-2026 — complete integration fixture and motion repairs

- Complete diagnostic pytest: **13,552 passed / 20 failed / 17 skipped / 2 deselected**. The same source passed browser geometry, TypeScript and full Vitest. Android unit XML reported **3,750 passed / 5 failed / 5 skipped**; snapshot Verify also found changed renderings after the completed review branches. These red results are retained as diagnostics, not release approval.
- Model-cache fixtures now declare their isolated runtime, pipeline mocks supply the trusted book root, and reading examples store absolute in-book WAV paths. Relative stored paths remain rejected. The new occurrence dataset lives in its own folder so both existing word-timing readers keep their one-object-per-file contract.
- Shared speech data regenerated exactly seven cache keys without changing any text/reading field. Two symbol expectations follow the dotted-number fix on Android. Exact fixture privacy reviews were refreshed after checking the inherited self-written sentences and regenerated TN output; no corpus exemption or new narrative fixture was added.
- ValuePicker starts with the ruler layout and reveals fallback chips only after actual overflow measurement, using the shared motion component. This preserves motion while avoiding retention of an unmeasured fallback during sheet opening. Eight stopwatch lines in the Android lifecycle regressions now carry the documented wallclock-ok rationale: their bounds already use TestTime and remain below the deliberately blocked operation deadline; assertions and ratchet budgets were not relaxed.
- Focused failure groups: **287 passed / 1 skipped / 0 failed**. Reviewed 12 old/new image sheets and adopted 46 exact layout renderings. The intentionally failing widget pixel probe is excluded. Fresh complete Android Verify and final release gate remain required.

## 14-11-2026 — fail invalid synthetic executables before native loading

- A second full-gate attempt reached the music-module tests, where an intentionally fake ffmpeg image blocked in the same Windows CreateProcess boundary. Both attempts retain stack dumps, partial output and exact process identities; neither is reported as a completed pytest suite.
- The test harness now intercepts only invalid `.exe` files under pytest's temporary root and returns Windows bad-image error 193 before native dispatch. It checks the DOS header and PE signature, including short files that start with MZ. Missing/inaccessible paths keep the native error path; valid images and paths outside the test root keep their original arguments and dispatch. Production process-launch code is unchanged.
- Five boundary regressions plus both observed stall cases passed **7/7 in each of three isolated invocations**. The full adjacent process/setup/music/disk selection passed **149 tests, zero failures**, in 121.66 seconds. Native fake-image dispatch is never performed by those controls. The complete gate must repeat at the new clean revision.

## 14-11-2026 — isolate offline setup process boundaries

- The full gate was stopped after its pytest process blocked in Windows CreateProcess while an offline setup test tried to launch a fake Ollama executable. A read-only stack dump identified the call. Partial output and process identities were retained; no production process was stopped.
- Three setup cases now replace server startup/model discovery and reject any real process creation. Each passed in three separate pytest invocations (3/3 each); the surrounding setup/assets/disk suites passed **95 tests**. Explicit console-suppression flags also cover native tools in the touched test module.
- Runtime, UI, native code, dependency declarations and packaging inputs did not change. Existing signed artifacts are retained only after checking the exact non-shipped file delta and all six artifact SHA-256 values; the full gate must repeat on the new clean test revision.

## 13-11-2026 — final review-branch integration preflight

- Integrated all completed review fixes, generic attribution through its noun-phrase guard, background tools and the reading-dock surface. Combined dotted-number rules with the shared Vietnamese letter classes on both Python and Kotlin. Preserved the reviewed share-screen geometry and isolated TLS test identity.
- Focused CPU preflight with inherited HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1: **592 passed, zero failures**, covering runtime pins, NFC/direct English, TN, G2P occurrence parity, generic descriptors, Compose layout scanning and release tooling. This is not the full release gate.
- Release/build preparation now supplies CREATE_NO_WINDOW to child tools and passes log handles explicitly. Regression cases cover normal and below-normal Windows tool launches; explicit cmd launchers were removed from the release entry points. Android's sound-policy assertion follows cache rule 20.

## 13-11-2026 — integ168c full-gate repairs

- The first full release-gate attempt passed CPU pytest: **13,065 passed, 17 skipped, 2 deselected**, with no failed cases. The attempt remained red in browser geometry, Android unit/snapshot checks and three web progress-label expectations; it was stopped after the static gallery, retaining the evidence. This is not release approval.
- Browser repairs cover an imported book with `remote: null`, current player action labels, correct inherited button alignment, and the localized chapter-count template. Player geometry uses explicit column/panel anchors across presence wrappers. Value-picker layout measurement no longer retains an obsolete fallback during an opening sheet's animation.
- Android repairs preserve certificate checking while supplying fingerprints in transport test fixtures, isolate shared preference/store/service state, refresh the cache-rule expectation, and lay out fingerprint instructions and emotion bars vertically. The latter have geometric regression assertions. The focused Android diagnostic passed **50/50, zero skipped**, including all **442 private calibration rows**, before the last visual layout repairs; a fresh verification remains required.
- All 25 initial old/new snapshot contact sheets were inspected. The initially rejected share/music frames were fixed and rerendered; the detail middle/bottom captures were also inspected. A later full Verify reached previously blocked captures: **3,703 passed, 13 snapshot failures, 5 skipped**, with **339/360** proofs. The affected seven screen suites then passed **132/132** in ordinary non-recording mode, producing every remaining actual frame. Three further comparison sheets were inspected, accepting 19 additional images: **217 exact PNGs** reviewed in total, including the full synthetic certificate fingerprint/pairing string. Binary diff review accepts only snapshot PNG paths with an exact SHA-256 review, valid dimensions and no PNG metadata. Independent verification still requires every tracked golden and forbids recording. **67 release-gate regression tests passed**, including missing/stale/outside-path/metadata review rejection, explicit-base ancestry/propagation, and separation of Python corpus tooling from private corpus data.
- Fresh focused Android rendering/geometry checks passed **81/81, zero skipped**, followed by **2/2** share checks with the full fingerprint. The browser measurement helpers passed **60/60**, then **15/15** sheet helper cases after adding a trusted Escape propagation regression (61 distinct cases across these runs). Final full verification remains required.
- The scrubbed history needs the user-specified comparison base `645239bda`, as release tags remain on the earlier lineage. The gate validates an explicit ancestor and nonempty range, propagates it to source workers and records it in the report. Source checks reuse that validated range while scanning every changed file. Latin-eth and folded-component variable names now describe their phonetic role; all comparisons remain covered by the existing regressions. These protected-file edits changed the direct quality hash from `dbb460d54ae91c9da882d7a565bac191c47919913818ff93eb19292016243e64` to `2f93df7ab8ca44fc3e78bbe3cee8469b08e85614428e2d0aa9ecc1faad7f4ac2` in the isolated dev tree.
- The next complete Android Verify passed **3,716 cases, zero failures/errors, 5 skips**, but the independent proof check rejected **358/360**: two widget tests unconditionally wrote their PNGs. Bitmap captures now use Roborazzi Verify and the shared post-success proof writer; release mode is checked before capture. Focused widget Verify passed **3/3** and produced all **6** exact expected proofs. Its planted pixel mismatch was rejected while preserving the golden bytes. Full verification must repeat after this test-harness fix.
- All **360/360** image proofs then passed with zero differences. The source path guard rejected the new helper declaration and intentional negative Verify capture; its parser now distinguishes declarations and permits only a probe-directory Verify directly inside the expected-error assertion. Explicit regressions still reject an unwrapped Verify and a negative image outside the probe folder. Widget and path-rule focused Verify passed **5/5**, zero skips; the complete suite must repeat on the final commit.
- The following full Android diagnostic passed **3,717 cases, zero failures/errors, 5 skips**, with **360/360** identical verified images. Its source binding was invalidated by tightening the path parser during that run: only actual capture-extension declarations are exempt, while calls in one-line helper functions remain checked. The final parser and widget group passed **5/5** afterward. The full release gate must repeat Android verification at the final clean HEAD.
## 13-11-2026 — fix168sec: stored paths and fatal synthesis failures

- Stored take/session/exception paths pass book containment before resolving, probing, hashing or deleting. Optional unsafe evidence is ignored with a warning. Cleanup also checks derived rejected-take paths and referenced DB paths.
- The audit includes CLI roots, GUI sources/outputs, segmentation, continuation links, audio locator probes, source glob results, chapter fingerprints and locked model settings. Model reads/hashes are confined to the current trusted runtime; legacy model paths only supply a validated suffix.
- Cause and context traversal is cycle-safe. Programming errors, unsafe paths and unclassified failures stop fatally without consuming a seed or writing a failure verdict. The same boundary applies to candidates, splits, tempo rescue and retention/checkpoint handlers.
- Early synthetic checks: 61 new regression cases passed; the first three-file diagnostic run had 184 passed / 1 failed (a stale RuntimeError fixture), then all 58 rejected-take cases passed after correcting that fixture. The runtime/model/policy group passed all 96 cases.
- Full diagnostic invocation: **1,014 passed / 16 failed / 0 errors / 2 skipped** (1,032 cases). Recovery helpers retained an OOM context across simulated process boundaries; other failures exposed incomplete split mocks, relative-path fixtures, a stale unclassified-runtime verdict expectation, and one malformed-provider-output retention regression. All were corrected without relaxing fatal handling.
- Follow-up full-file invocations with `-rf`: recovery **121 passed / 2 skipped**; word-break **101 passed**; pipeline/work-item fixtures **140 passed**; retention **167 passed**; final fault-boundary/rejected-take checks **144 passed**. All have zero failures/errors. Latest results per file, replacing earlier diagnostic rows: **1,044 passed / 0 failed / 0 errors / 2 skipped**, **1,046 unique cases in 31 files**, including **86 new synthetic regression cases**. This is aggregated final coverage, not a second complete-suite invocation.
- Known libsndfile format/malformed/encoding errors only prevent retaining already-refused provider output. System code 2 and machine/programming contexts remain fatal; the system error also follows the same-seed machine retry boundary through cause/context wrappers.
- JUnit, logs and exact counts are saved outside the checkout in the fix168sec scratch directory. CPU/mocked checks only; the broad invocation started with 7.69 GiB free, with CUDA disabled. Final commit privacy verification is recorded in `result.md`.
- Implementation commit `7c917ad208de5b7256f6c69d104b91dd03e41c46`: `scripts/leak_scan.py --rev HEAD` exited 0 with 0 findings in 4,637 files; no corpus skip. Quality hash changed from `dbb460d54ae91c9da882d7a565bac191c47919913818ff93eb19292016243e64` to `aa593ea08778853281fb76aefc8a7cf4dd3fed103f8917873dce03d2beb74623` on this dev branch.
## 13-11-2026 — fix168asr: keep legacy sentence folding beside locked names

- Sentence alignment and canonical metrics fold đ to d again; only name forms/component/regional comparisons retain the stroke. The alias guard accepts the sentence fold or a voice-region alias per corresponding token, without chaining the stroke fold into a regional d/r/gi merger.
- Synthetic coverage includes transliterated names beside đến đây/dến dây and đi đâu/di đâu, both alias modes, four voice regions, repeated-short copies, every canonical metric branch, and a mixed stroke/dialect sentence. Existing ra/đa and giá/đã rejections and locked-name stroke tests remain green.
- Negative control against unchanged `1fa5b77d5`: all 58 new sentence-normalization cases fail. Final related suites, run separately with `pytest -rf`: **884 passed, 1 skipped, 0 FAILED, 0 errors** (885 JUnit cases). The unload test ran separately after the machine reached 6.21 GiB available RAM; no test remains omitted. The unchanged calibration skip remains. Complete `test_asrjudge.py`: **293 passed**.
- Checks use the production runtime interpreter with `-X utf8`, `ABOOK_RUNTIME` set and CUDA disabled. Measured small-suite peak process-tree RSS is at most 266.8 MiB. No build or model inference was run with low available RAM.
- Complete replay of the original private dataset: 13,468 rows, 14,677 saved decodes. On the 524 failed/warning rows, best-take PASS is **27 / 64 / 64** for `8c90dc47b^` / `1fa5b77d5` / this fix; decode PASS is **32 / 131 / 131** out of 1,193. On the 12,944 stored-verified rows, best-take PASS remains **12,763**, decode PASS **12,765** out of 13,484. Internal adjudication on 5,016 verified rows with anchors: **1,936 / 2,539 / 2,539** PASS.
- **0 PASS losses and 0 rank regressions** against both controls, at best-take, individual-decode and internal-verified levels. **0 decode label/verdict changes against the branch baseline**, which also reproduces the saved asrjudge4 results exactly. No new corpus PASS is claimed; the synthetic tests expose the missing stroke cases.
- Dataset SHA-256: `3b54f84d89d28f98b5c11cb1cb86399e1349bd3c4e668c9d5cf3c87aff7cdf15`. Replay uses the saved dataset without new ASR/audio or text generation. Its row-scoped edit-distance memoization asserts identical function ASTs across revisions and calls the original function on cache misses. Replay starts with 6.53 GiB available RAM, peaks at 403.8 MiB process-tree RSS, exits 0.
- Quality implementation hash: `dbb460d54ae91c9da882d7a565bac191c47919913818ff93eb19292016243e64` -> `b0d055488ff0c1304f770d1b419b0d97ae9f8f47030ef1d42224356811d8101f`. `compileall` passes; changed files have LF, no unexpected control characters, and a clean diff check. Dev branch only.
- Implementation commit `9b7283ef4`: full-corpus `scripts/leak_scan.py --rev HEAD` exits 0, 0 findings in 4,636 files; 1,577 pre-existing exact reviewed false positives. No allowlist changes.
## 13-11-2026 — fix168tn: dotted numbers and fractional zeroes

- Python and Kotlin now resolve explicit dotted version, valid day/month, and valid hour/minute contexts before numeric fallback. Short ambiguous pairs retain the base dotted reading. Definite decimals, attached-unit quantities, decimal scores, and dotted multipliers read every fractional digit, including trailing zeroes. Comma thousands (`8,125`, `3,000`) retain the approved policy.
- Extended the existing shared reading-forms contract to **411 cases**, with **60** downstream-normalizer expectations checked by both Python and host JNI. Clip-cache rule advanced together from 19 to 20; dependent cache-key fixtures were refreshed.
- Final 29-file CPU pytest invocation with `-rf`: **2459 passed, 0 FAILED/errors, 2 skipped**, 57.18 seconds. Skips are the optional private 442-row calibration replay and the real network Edge service. The final run began at **8.02 GiB** free with `CUDA_VISIBLE_DEVICES=-1`.
- Filtered Gradle `:app:testDebugUnitTest`: **98 tests = 97 passed, 0 failed/errors, 1 skipped**, BUILD SUCCESSFUL in 1m31s; **6.79 GiB** free before launch. Both shared numeric contracts ran. Exact JNI parity: **748 public tokens** and **115 marked stretches**, **0 phoneme mismatches**. The JVM skip is optional private calibration.
- The broad gates exposed stale pre-NFC stretch snapshots and frozen quality-hash metadata. Refreshed four short synthetic cry rows and added Python freshness coverage for this snapshot; no stretch implementation, oracle policy, or long IPA was added or changed. Initial diagnostics and their repaired reruns are recorded in `PROGRESS.md` and external logs.
- Quality implementation list loaded from code: **70 entries**. Before: `dbb460d54ae91c9da882d7a565bac191c47919913818ff93eb19292016243e64`; after: `3e83369310dcbcfaf798ec746ccbfc9960d747a17428b0a6f44dac597e060c74`. Changes are confined to `dev/fix168tn`.
## 13-11-2026 — fix168g2p: occurrence positions through numeric normalization

- Python and Kotlin carry generated/ruled occurrence positions through sea-g2p normalization. Number/unit gaps stay together; the mapped sequence must match whole-text normalization and the actual G2P input before any phone is repaired. Studio consumes normalized chunk/cue occurrences in order. Multiword English tags retain their whitespace positions, and English occurrences keep their own phones. Cache namespace is now `direct-en9`.
- Twelve authored contexts cover names before/between/after number-unit expressions, decimals, bare numbers, generated name syllables, multiword English tags and English uses of the same spelling. Additional tests cover repeated chunks, cues and rejection when partitioning changes normalization context. Sentence phonemes for the desktop/JNI contract are generated outside Git; the release gate supplies that input and requires the new native suite.
- Final focused `pytest -q -rf`: **402 passed, 0 failed/errors/skipped**. Replaying the original helper on the new 31-case suite gives **11 FAILED, 20 passed**. Final Gradle XML: **88 passed, 0 failed/errors, 1 skipped, 15 suites**; the skip is the optional private calibration fixture. Host JNI has **0 exact phoneme mismatches** on **744 public tokens, 115 stretches and 12 new contexts**. The new contexts and stretches also have identical pieces.
- The first JVM run exposed a stale stretch snapshot: four combining-Unicode rows differed, three in phones. Both the original helper and the new helper produce the same current desktop result, also matched by JNI. Regenerated those four rows, removed obsolete quality-hash metadata, and added a desktop regeneration test. No sentence IPA was added to the new fixture.
- The actual quality policy lists **70 files**. Before: `dbb460d54ae91c9da882d7a565bac191c47919913818ff93eb19292016243e64`; after: `805538555ab513f9ffa2bf098785c7ebf6ba763826dbaf387c5a8b3d1e457f47`. Work remains on `dev/fix168g2p`; no audio synthesis or acoustic-quality measurement was performed.
## 13-11-2026 — fix168reveal: explicit animation content layouts

- Audited all 476 Kotlin files in the app's main source set, including `Reveal`, `ReducedFade`, `AnimatedVisibility`, `AnimatedContent` and `SheetPages` callbacks. The release source set has no animation calls. Wrapped 31 sibling groups in their original flow direction: 26 columns and five rows. Preserved horizontal alignment for chapter counts, character metadata, music chips and undo actions; the animation primitives retain their behavior.
- Added a lexical source guard with synthetic snippets for branches, loops, transparent scopes, named content and nested animations. Its findings on the original changed sources are 31; the updated app has zero findings. Added 14 Robolectric Compose tests measuring the five reported surfaces in normal and reduced motion, plus row/column bounds during entry, settled display and exit. All 14 pass both alone and in the complete app run.
- Related pytest with `-rf`: **101 passed, zero failures/errors/skips**, including 55 layout scanner cases. Earlier dependency setup runs had 10 and nine actual FAILED entries; their logs/XML remain in the external task folder. Build preparation required regenerating the parity document's source references. An initial test compile used unsupported DpRect size properties, and four animation tests initially needed explicit layout/clock synchronization; the final focused run passes 14/14.
- Complete `:app:testDebugUnitTest`, without a test filter: **3,735 tests, 3,714 passed, 15 failures, zero errors, six skipped**, from 437 fresh XML files; Gradle exits 1. This is not a green full-suite gate. Failing classes: `LibraryServerUnpairTest` (2), `ListenPrefsRangesTest` (3), `ListenPrefsTest` (2), `PairingWordsTest` (2), `ShareDurabilityTest`, `SoundfixTest`, `CaptionRulesTest`, `LibraryMembershipTest`, `NativeActivityLinksTest` and `G2pGateParityTest` (one each). The adjacent captions reported by CaptionRulesTest already occur in the base ShareScreen; this change adds their missing layout. No assertions or input requirements were relaxed.
- Every Gradle launch waited for at least 6 GiB available RAM; one worker, CPU-only environment, no emulator. JNI inputs were supplied with `ABOOK_REQUIRE_G2P_PARITY=1`. Quality policy was read from code (70 entries); implementation hash remains `dbb460d54ae91c9da882d7a565bac191c47919913818ff93eb19292016243e64`.

## 13-11-2026 — integ168c release integration follow-up

- The first complete CPU pass after integration reported **13,045 passed, 18 failed, 19 skipped**. This was a diagnostic run, not a release approval. Failures exposed stale test doubles and expectations, exact-byte privacy reviews from before the scrub, cache-key fixtures from rule 18, source containment assumptions, and two real redo regressions.
- Redo now compares selected source content and creation choices before reusing an unstarted book. Restarting interrupted analysis copies its selected source files before holding the draft in recoverable trash. Creation failure restores the draft; the fresh book owns its source copies and retains the original display-only source hint. Existing restart, rollback and workshop merge tests cover these paths.
- Focused Qt checks: **26 device tests and 38 Studio tests passed**, with zero failures, QML type errors, missing glyphs or leaked JavaScript values. The initial native builds also exposed missing namespace qualifications in the shared paused-sleep getter and tests; these were corrected without duplicating the constant. The complete Qt/build/release gate is still required.
- Follow-up focused checks: **36 redo/merge/flakiness tests passed**, **18 web tests passed**. Both live-state writer tests passed three consecutive isolated runs (**2/2 each**) after replacing the module-local clock proxy instead of mutating process-wide `time.sleep`. The private calibration replay passed all **442 rows** without copying sentence data into the checkout. Android verification and the final full gate remain pending at this checkpoint.
## 13-11-2026 — Generic appearance phrases require noun evidence

- The `có/với` descriptor branch now requires an appearance or accessory noun followed only by supported nominal modifiers. A noun followed by a perception, intention or other clause also abstains. Unfamiliar descriptions remain for the model to resolve. Wear/hold and bare clothing rules retain their existing behavior.
- Self-written regressions exercise hair, eyes, clothing, accessories, build and complexion, as well as clauses with another speech subject. Validation checks speaker and casting traits, both neighbor directions, the six-syllable limit, capitalization and the existing 0.8 identity threshold.
- Focused pytest with `-rf`: **171 passed, 0 FAILED, 0 errors, 0 skipped**, across 11 files; JUnit XML agrees. An intermediate expansion exposed four missing-size-modifier failures; they were corrected before rerunning all 11 files.
- Read-only comparison against `aa0f3fc99`: six synthetic false attributions become zero; all three requested positive forms remain. Across 200 archived project databases, 121,538 narration rows contain 438 distinct generic lead-ins: **15 attributions before and after, with identical labels**. The existing `measure_phantom_speakers.py --all-books --min-lines 1` also completed. These are stored-text checks, not a new model run or a gold accuracy measurement.
- Each test/measurement launch checked at least 6 GiB available RAM, with CUDA disabled. No Android source changed and no Gradle task was run for this fix.
- Quality implementation list read from code: **70 entries**. Hash before: `8fe0f3a554a6089a60d4ca2d9a191fae05b802980664ec6f5a1c1847a614e7f4`; after: `a47e1f177eee0a19cfd8eda1aa8bfd6ce1b8c4a660dcf4feff7063fcff6c8eca`. The change stays on the development branch.

## 13-11-2026 — fix167: resume preparation, resource failures and music UI

- Continued from `9f90ced9b`, retaining its shared-rulings resume fix. Preparation of narration voice and music now also runs before synthesis on resumed books. A stop during music preparation propagates immediately. Shared rulings mark the file incomplete before the first request; discovery faults propagate, and explicitly incomplete sets are rejected by direct and package readers.
- Word-break measurement distinguishes deterministic inconclusive results from resource or unexpected failures. The latter stop at a checkpoint; regressions cover a retry measurement failing, reopening the database and finishing with the reserved seed. Both saved-track writers hold the same lock across reading, mutation and writing; concurrent add/add and remove/add tests verify memory and disk results.
- Restored unconditional Qt `changed()` after loading a chapter, as before `dfa51eb4e`. Web music previews remove obsolete metadata listeners and ignore stale play rejections, including A/B/A switches. P1 bans direct Radix dropdown imports outside the shared wrapper; P2 measures tabular cells at both precisions; P3 retains toast targets across half-pixel noise.
- Focused pytest only, with `-rf`: **306 passed, 2 skipped, 0 failures/errors**, **308 unique cases** across 10 files (latest result per case, duplicates excluded). Focused vitest: **8 files, 79 passed, 0 failures/skips**. `tsc --noEmit` passed. Both parity documents were regenerated and remained byte-identical. Logs and JUnit XML are in the external `codex/fix167` scratch directory.
- Initial focused runs exposed one OOM-marker regression and two unsupported TypeScript compiler-API assertions; both were fixed and the affected files rerun successfully. No whole-suite run, build, release gate, gallery run, native Qt compilation, GPU inference or listening comparison was performed while on battery.
- Quality implementation list read from code: **69 files**. Task baseline: `71563e9c1a2ecee91b3be33d3300e0f529f3af7ceb77d7c0e18b6ee800489d9d`; final: `ed4fbd8eaf326136b972e587dad7b4a4720b28ebc34add77b1a9ed0fec88148f`. Changes remain on `dev/integ167`.

## 13-11-2026 — asrjudge4: glued regional name spellings are compared per syllable

- The regional path for a glued transcript span no longer compares joined `_name_spelling_key` strings. `_regional_syllables_match` cuts the span into exactly one piece per locked syllable and each piece must equal that syllable's regional key; the only letters a piece may omit are a coda repeated as the next onset (`Sát-ta`/`sata`). Joined keys read gi+e as one syllable, so `Fuze` passed `Phu-gi-e` and `Shizai` passed `Xi-gi-ai`; both now fail. `Hinohaza`/`Hi-nô-ha-ra` (Nam) still passes through the per-syllable romaji path.
- Replay of 13,468 stored rows: 0 regressions against integ168 (best take, every decode, internal); 0 best-take or decode changes against fa0a1dc51 on the 524 rows; 0 VERIFIED changes. One internal VERIFIED change: nhung:465 `Xi-gi-ai`/`Shizai` (Bắc) anchor pass -> fail, verdict already mismatch.
- Required `pytest -rf` gate: 0 failures, 0 errors, 1 existing private-calibration skip. G2P parity `--check` 744 + 115, only quality-hash metadata changed.
- Hash before `9a153d8f18c77c28e29fac0e1e8bcba7755beedcb25aaa077cd50d4cb018f049`; after `bd4ca0fda67c27e92764f940855ae4abaed5b4396f23e284fa6152bffdbc685f`. Keep on dev until active books finish.

## 13-11-2026 — asrjudge3: romaji names read by the app's Japanese rule

- A transcript token of plain Latin letters that is not a `valid_syllable` (no tone, hat, breve or horn) may match a hyphenated name part of two or more syllables when `romanization.romanized_reading(token, "ja")` - the same rule that locks Japanese readings - yields that reading syllable by syllable after `_name_spelling_key` (tone and voice-region consonants only; Southern voices also read romaji z as r). Vowels must match exactly. `Joshi Kun`/`Giô-si-cun`, `Josuke`/`Giô-xu-ke`, `Hino Haza`/`Hi-nô-ha-ra` (Nam), `Jindo`/`Rin-đô` (Bắc) pass; `Jushi`/`Giô-si`, `Hina Haza`, `Haru`/`Ha-rư` (the rule gives u, not ư) and every marked Vietnamese token such as `Há dù` still fail. `Josie` has no Japanese reading and is unchanged. Three earlier expectations (`yona`/`Dô-na` Nam and Bắc, `Jindo`/`Rin-đô` Bắc) now pass as valid romaji. No Kotlin name adjudicator exists to mirror.
- Required `pytest -rf` gate (`test_asr*.py`, `test_readaloud_sounds.py`, `test_g2pgate.py`, `test_quality_policy.py`): **743 passed, 0 failures, 0 errors, 1 existing private-calibration skip** (744 JUnit cases). `compileall` passed; G2P parity `--check` 744 + 115, only quality-hash metadata changed.
- Replay of 13,468 stored rows: 0 regressions against integ168 and against e92cede4e (best take, every decode, internal); 0 VERIFIED label/verdict changes. 14 of the 17 rows blocked by asrjudge2 are restored (hello:2516 `Ha-rư`/`Há dù` stays fail; the two `Josie` rows stay review), plus 4 further best-take upgrades. Internal VERIFIED: 116 of the 142 asrjudge2 blocks restored, 89 other rows upgraded, mostly Southern romaji z read as d (`Zuki`/`Giu-ki`, `Aza`/`A-ya`).
- Hash before `ed345a26e350741ecf90f565ef32712cbb5824be4958440e028f4e9e69982441`; after `9a153d8f18c77c28e29fac0e1e8bcba7755beedcb25aaa077cd50d4cb018f049`. Keep on dev until active books finish.

## 13-11-2026 — asrjudge2: preserve vowels in additional regional name matches

- Regional name keys now remove tone only and retain the vowel sequence alongside exact phonemes. Component matching keeps vowel marks until it chooses either the existing component comparison or the additional regional comparison. A new consonant merger cannot also forgive a changed vowel. Existing integ168 diacritic/component equivalences, including its `đ -> d` normalization, remain separate.
- Regressions cover ư/u, ơ/o, â/a, ê/e, iê/i, ă/a and ô/o on token and component paths; known/unknown regions; NFC/NFD/case; punctuation; Haru, Yuki, Rita Vrataski, Mizuki, Alderaban and Fujieda. `Ha-rư` / `Há dù` is rejected; Northern `Giu-ki` / `Ruki` or `Zuki` remains accepted. No Kotlin name adjudicator exists to mirror.
- Required final `pytest -rf` gate (`test_asr*.py`, `test_readaloud_sounds.py`, `test_g2pgate.py`, `test_quality_policy.py`): **726 passed, 0 failures, 0 errors, 1 existing private-calibration skip**, 727 JUnit cases. `compileall` passed. Generated G2P parity check passed for 744 public tokens and 115 stretches; only fixture quality-hash metadata changed. An optional full-suite attempt was stopped after a later source correction; no full-suite success is claimed.
- Replay of 13,468 stored rows against integ168, 8c90dc47b and this tree: 17/46 previous best-take relaxations and 142/844 internal VERIFIED relaxations depended on a vowel change and are blocked again; 0 regressions against integ168 (best take, every decode, internal). One row moves above 8c90dc47b: a Southern `Ri-ta vờ-ra-ta-xờ-ki` / `Zita vờ ra ta sờ kỳ`, where stripping every mark had turned `sờ` into English `so` against `xờ`; retaining ơ on both sides fixes that false miss (regression added).
- Implementation list read from code: 69 files. Hash before `28c0a261a30bb3e0ffa3f684aaf4546ea1c5424ea502bb6431d957275c3851a0`; after `ed345a26e350741ecf90f565ef32712cbb5824be4958440e028f4e9e69982441`. `asr.py` remains LF. Keep this implementation on dev until active books finish.

## 13-11-2026 — Rejtake review follow-up (rejtake2)

- Persistent synthesis failures are retried with the same seed. Only OSError/MemoryError and named machine faults (including wrapped causes) stop at a checkpoint; deterministic engine and split errors become audio verdicts in the take ledger. The next seed/split can run, a bad line can finish failed, and later lines continue. Named machine faults also remain machine faults when an AudioQualityError has no cause.
- High-quality selection ranks signal tier, then HQ refusal (pace/repetition), then soft flags. Segment retention, archived takes and word-break candidates use the book's profile. A passing take beats an off-pace take even when it has a frame-ceiling or word-break flag; the signal tier still comes first. Seed-dependent fixture audio exercises distinct checksums.
- Live supervisor state writes make one atomic-write attempt, schedule backoff from after a failure, and keep draining events and forwarding controls. Only the terminal state write waits for retries. Regressions cover a held state file with 300 worker events and a pending stop request.
- Rejected WAV retention is opt-in for the main pipeline take session. Preview/probe callers use the default refusal without leaving `.rejected.wav` files. Tests cover both modes with the real writer.
- CPU only, `-rf` and JUnit: final 24-file run **747 passed / 0 failed / 0 errors / 2 existing skips** (906.22 s, exit 0); three direct TTS caller files **53 passed / 0 failed / 0 errors / 3 existing model skips** (6.64 s, exit 0). Total: **800 passed / 0 FAILED / 5 skipped** across 27 files; both final logs have zero `FAILED` lines. Focused regressions also passed **150/150** (170.75 s), counted separately. No UI files changed, so no TypeScript check was required.
- The previous interrupted run had two failing word-break expectations (736 passed / 2 failed / 2 skipped). They now require the HQ-accepted first take to survive its off-pace retry, including crash/reopen. The first direct-caller run found two writer mocks missing `keep_rejected`; their signatures now accept it and assert the default is False. No assertion was disabled. Logs, JUnit, exact commands and counts are in the external rejtake2 task folder.
- Quality implementation list read from code: **69 entries**. Before edits (also verified from the base Git files): `a05d7f28188f4154f51c9b2e04e9c8539fa5c361f42f11250b0fead2a234161f`; after edits and tests: `f7e2295d4159dce6bb4b2f43e8fb8ac6f66c302f37dead2d25dbb4b0d802c3d2`. Dev branch only; no GPU, push, production job or model download.

## 13-11-2026 — Retained signal rejections (rejtake v2)

- Signal passes outrank every rejected take. Acceptance checks the retained checksum and its own quality metrics; the database rejects signal-rejected checkpoints except an explicitly retained edge warning. Fatal waveforms are discarded. Retainable refusals use the locked gain/peak cap, full measurements and PCM_16 at a separate `.rejected.wav` path. No 5–10 ms edge fade was added.
- After all attempts, edge refusals proceed through ASR as `TTS_SIGNAL_EDGE_KEPT` and remain warnings through content/perceptual finalization. This warning permits chapter delivery and appears by default as the shared `signal` review kind. Clipping and unknown refusals remain failed with audio. Same-policy recovery preserves a checksum-matching retained edge take.
- Synthesis and split ledgers retry machine faults with the same seed; persistent faults stop at a checkpoint without recording a quality verdict. Atomic WAV replacement retries briefly. Live supervisor state writes back off for approximately 30 seconds and cannot kill the worker on failure. Session cleanup preserves referenced artifacts and removes losing attempt files.
- CPU only, using the existing `D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe -X utf8`; no GPU, build or full test suite. Initial related run: **423 passed / 3 failed / 3 skipped** across 12 files. Fixed the three failures: a missing adapter unload method, an old provider fixture writing the wrong sample rate, and generated UI parity line references. The provider regression still requires unknown refusal + failed status + retained canonical audio.
- Final six-file run: **116 passed / 0 failed / 0 errors / 1 skipped** (89.13 s). Final artifact-reference/crash checks from `test_take_session.py` and `test_word_break_gate.py`: **13 passed / 0 failed / 0 errors** (24.25 s). Both used `-rf` and JUnit; actual `FAILED` line count is zero in both final logs. Synthetic 508/751 regressions use generated tones and invented text, with no book audio/text fixtures. The exhaustion case spends all 10 attempts.
- Vitest: **11/11 passed** in `ReviewQueue.test.tsx`, `reviewActions140.dom.test.tsx` and `reviewText.test.ts`; dependencies installed from the lock with lifecycle scripts disabled. Kotlin `WorkLogicTest` was updated but **not run** on battery. UI parity checks passed after regeneration.
- Quality implementation list read from code: **69 entries**. Before edits: `663ab9eb4a3f752b57e13644a89f0567d82f18922f8923cc85cf1ca3c948d270`; on resuming this interrupted task: `2a281956a23ec9c927f78e2582ee8df626600e0d8e198282ab6d21302b8c830b`; final: `a05d7f28188f4154f51c9b2e04e9c8539fa5c361f42f11250b0fead2a234161f`. Changes are confined to `dev/rejtake`; no push or production-worktree access.

## 12-11-2026 — andfix Android playback and sleep review (battery mode)

- Continued from `31dc98b4b` and `8a92c581d`. Timer/preferences, listening sessions and night snapshots now use an ordered background writer. Import replacement and permanent/trash book cleanup release Store's monitor before recursive deletion.
- Nights close on timer expiry/cancellation, keep a bounded event list and reject further daytime checkpoints. Explicitly setting a timer may reopen the same recent night.
- Added/extended `PlaybackIoOffMainTest`, `ListenPrefsTest`, `StoreStagingTest`, `BedtimeLifecycleTest`. Kotlin/Qt tests have NOT been run: battery constraint prohibits Gradle/build/emulator/ADB. Existing paused-timer persistence test now checks the new 30-minute lifetime.
- Quality implementation hash at resume: `71563e9c1a2ecee91b3be33d3300e0f529f3af7ceb77d7c0e18b6ee800489d9d` (matches the initial recorded hash).

## 11-11-2026 — Verify Android references after the integ167 UI merges

- Audited all 63 original snapshot mismatches and the five images previously blocked by Java heap OOM against source history. The four root tabs (including Music), the intentional auto-rewind removal, picker controls/chapter count, measured/indeterminate progress, cover-flight ownership, sized cover cache and design1 styles remain. No production UI change was needed. Recorded 83 updated references and one separate 130% filter reference; viewed every changed region at native resolution. The external mergeui2 report has the per-image provenance and SHA-256 evidence.
- Roborazzi comparison allocates full-size reference/actual/diff/comparison canvases. Four 1080 x 10200 audio images and a 3900 x 2340 settings image exhausted Gradle's default 512 MiB test-worker heap. Set the worker heap to 2 GiB with one parallel fork. Against the unchanged old references, the same full 3,678 tests then reported 68 image mismatches and zero OOM, separating the resource fix from recording. No test, image resolution, tolerance or assertion was disabled.
- Fixed a baseline-path collision: the normal and 130% font-scale dark filter tests both wrote filters_360_dark.png. The 130% case now uses filters_360_font130_dark.png, with both tests retained. Gallery error cases now wait for the required alert before the unchanged retry-text assertion; DOM quiet time alone could finish between retries and React's error commit.
- Final **compare mode**, with record=false / verify=true: verifyRoborazziDebug **3,678 tests / 0 failures / 0 errors / 11 existing skips**; a forced fresh testDebugUnitTest run **3,678 / 0 / 0 / 11**; a forced fresh testReleaseUnitTest run **3,678 / 0 / 0 / 11**. All three left reference PNG hashes unchanged. XML counts are from fresh runs, not an up-to-date task or record-mode verdict.
- Full Vitest **3,110 passed / 0 failed / 0 pending**, direct Node exit 0; TypeScript exit 0. Offscreen Qt width **1,606 passed / 0 failed / 1 existing skip**, with 0 missing glyphs, QML type errors or text leaks; 44 previous tested Qt source fingerprints match current files. The first Vitest run had three gallery-state failures before the condition-based wait fix; all three and the complete suite passed afterwards.
- Every Gradle launch checked at least 6 GiB available RAM. Locked implementation list read from code (66 entries); quality hash unchanged before/after: `e151a0d2e4fd932915d70603d311bc0d81b97aaadf5898051c32c8d8e63686a2`. No phone, push, release, version bump or migration.

## 10-11-2026 — g2pvi5: shared words in two tiers, each roster name by its own origin

- Design: `docs/SHARED_WORDS.md` ("Two tiers"). Frozen at `2029f2b8d` BEFORE the sixth sample was drawn; baseline `2caf9af4c` (g2pvi4). Labels are model-only (two blind keys, Sonnet 5.5 then Opus 5.5, from the written window alone; they agree on Vietnamese-or-not for 1,170 / 1,210 rows, the 40 disputes were settled from the text before scoring against the final key). The owner has not judged them.
- Sixth sample: every shared-word occurrence with `sha256("g2pvi5-holdout6|...") % 100 < 12` in the five test pools, minus earlier samples: 3,936 windows, 1,210 asked. Key: 499 English words, 381 Vietnamese words, 58 Western names, 258 romaji / sounds, 14 mixed.

  | | Vietnamese read English | real English kept | Western names kept | romaji / sounds read Vietnamese |
  |---|---|---|---|---|
  | `2caf9af4c` | 22 / 381 | 497 / 499 | 56 / 58 | 32 / 258 |
  | tier 1 (listen-now) | 22 / 381 | 497 / 499 | 56 / 58 | 32 / 258 |
  | tier 1 + tier 2 | **18 / 381** | **495 / 499** | 56 / 58 | 35 / 258 |

  Tier 1 marks 60 rows (5 %) as doubtful. The sure part is 889 / 901 = **98.67 %** right on Vietnamese / English / Western rows: the 99.5 % goal was **not** reached. In the doubtful part tier 2 (analysis model `abook-analyzer:v5`) finds 4 of 14 Vietnamese words and loses 2 of 9 English ones ("Cresent Moon Bay", "Stairway to Heaven"), 0 of 14 Western names. The 18 Vietnamese errors left: 8 capitalised in doubt, 6 sure prose (scores -210 to -608), 2 prose in doubt, 2 sure capitals.
- g2pvi4 regressions repaired at tier 1 (the capital rule reads the written text): "admin BAN nick", "Lalaport TOKYO BAY" English again; name particles ("gia tộc de Valis", "Hikaru no Go") not claimed.
- Roster names (227 names, analysis model, CPU, 0.68 s per name): 222 right (Japanese 99 / 102, Korean 53 / 55, Western 40 / 40, Vietnamese 30 / 30); every miss answers "other" = no change. Self-written must-cases through the real road: with a Vietnamese roster "An An.", "Ban?", "Bin!", "Son!" read Vietnamese; "Do trans sắp thi.", "guild Say xỉn", "[Bay Lv0]" Vietnamese by tier 2; Chiaki / Haruto / Sakura read Japanese in a mixed roster, Jieun / Seojun / Minho Korean in a Japanese roster. Tier 2 also calls the invented "Do exercise đi." Vietnamese (wrong). Listen-now (no tier 2): "An An." and "Do trans sắp thi." read English, as before.
- Spoken strings identical on **1,210 / 1,210** rows against `2caf9af4c`. CPU phonemize of the 1,210 windows, best of alternating runs: 0.739 s -> 0.754 s (+2 %, noise). Tier 2 itself: 2.45 s per doubtful occurrence on CPU; whole books of 291k to 2.4M words hold 0, 0, 0, 3 and 26 doubtful occurrences (scan 4 to 56 s).
- Related pytest (117 files, junit): **4,664 tests, 0 failures, 3 skipped**. Related JVM with the real sea-g2p JNI: **70 classes / 571 tests / 0 failures / 1 skipped**. Full JVM: **408 classes / 3,505 tests / 0 failures / 4 skipped**. Shared fixture `shared_vietnamese/cases.json` carries rulings cases, same claims, doubts and phonemes in Python and Kotlin.
- Quality hash `7d3ab0d7...` -> **`8690a3c96a8e2c3ba212b01aa6232126a0cabd00584d1596b850d6ae256dd60f`** (`shared_rulings.py` joins the list): dev branch only until running books finish.

## 10-11-2026 — g2pvi4: shared words decided by a corpus-learned score table

- Design and method: `docs/SHARED_WORDS.md`. Implementation and table frozen at `f773607b9` BEFORE the fifth sample was drawn (sha1 residue 4, 486 series, 7,503 chapters, 350 stratified windows, labels written from text only and sealed before any phoneme run). Baseline is `5820f3232`. Labels are model-only; the owner has not judged them.
- Target-level readings, before -> after. "V" = Vietnamese word read English (errors), "E" = real English read English (must not fall), "N/S en->vi" = names, romaji, sounds that lost their English reading.

  | sample | V read English | E read English | E en->vi | N/S en->vi |
  |---|---|---|---|---|
  | design (68 V / 68 E) | 0 -> 1 | 66 -> 66 | 0 | 0 |
  | holdout 1 (39 / 20) | 0 -> 0 | 20 -> 20 | 0 | 0 |
  | holdout 2 (144 / 98) | 3 -> 5 | 89 -> 89 | 0 | 0 |
  | holdout 3 (121 / 115) | 15 -> 2 | 111 -> 111 | 0 | 0 |
  | holdout 4 (145 / 84) | 8 -> 3 | 78 -> 79 | 0 | 0 |
  | **holdout 5, verdict (150 / 88)** | **7 -> 3** | **82 -> 83** | **0** | **0** |

  Holdouts 3 and 4 supplied training rows, so only holdout 5 is a clean verdict: 4 of 7 fixed, none lost; the 3 left are Vietnamese words written with a capital mid-sentence ("Kỵ Sĩ Tự Do,", "(Bay),", "[Bay Lv0]"). Leave-one-sample-out over the five earlier samples: V 26 -> 11 (19 fixed, 4 lost), E en->vi 0, names en->vi 0. Zero Vietnamese errors was **not** reached; design and holdout 2 lose 4 cases the hand rules had ("Do trans sắp tới", "Leila in qua", "orc non một", "Yuna no đâu").
- Unlabelled scan of the whole fifth pool (6,874 windows, judged by hand after the verdict, so not blind): 73 readings moved. 29 Vietnamese fixed, 8 Vietnamese lost ("Regulus bang hoàng", "Copy, in và in poster", "hăm he Aria"...), 4 English fixed, **2 English lost** ("admin BAN nick", "Lalaport TOKYO BAY": all-caps words are lower-cased before the capital rule sees them), 3 name particles lost ("gia tộc de Valis" x2, "Hikaru no Go'"), 3 typos "Sauk hi" now English, 24 sounds / romaji either way. Corpus-weighted: about 59 occurrences fixed and 9 lost per 133,714 shared-word occurrences; total read English 3,830 -> 3,834 (2.87 % both), because most of that mass is real English and names.
- Spoken pieces and normalized strings identical on **2,010 / 2,010** windows of the six samples (baseline code exported from `5820f3232`); phonemes changed in 46. CPU phonemize latency on the same 2,294 corpus lines, two alternating runs: best 0.993 / 1.058 -> 1.069 / 1.034 ms per sentence, median 1.064 / 1.123 -> 1.090 / 1.216 ms (**about +2 to +8 %**, within +20 %; machine under load). Android data: `SharedWords.kt` 428 KB (limit 1 MB).
- Related pytest (`-k` readaloud / vieneu / shared / phoneme / english / quality / parity / book_edits..., junit): **3,472 tests, 0 failures, 0 errors, 3 skipped**. Related JVM with the real sea-g2p JNI: **70 classes / 569 tests / 0 failures / 1 skipped**. Full JVM: **408 classes / 3,503 tests / 0 failures / 0 errors / 4 skipped** (the first full run had 1 failure: `CopyRulesTest` read the generated corpus table as interface text; `vieneu/SharedWords.kt` is now on its data-file list, as in `scripts/ui_parity.py`).
- Shared fixture: 89 self-written cases, same claims and phonemes in Python and Kotlin. Two fixture readings changed on purpose: "Do trans sắp thi." is now a recorded miss (English "do"), "Cô nói `<en>the</en>` thé." is now Vietnamese. Policy version 5 -> 6; seven clip keys of `book_edits/readings/speech.json` regenerated. Quality hash **dc2aad8128c6124b9ecd132df906f7b22a9f1af36d684ef6f8576fb59e55bc0b -> 7d3ab0d732bee7dbd035b2b9df484f855356210dbb5ff9fe0a8b25a2f4ee3192** (phoneme_policy.py, english_policy.json, quality_policy.py + new locked entry `readaloud/shared_words.json`): the change must wait on a dev branch for running projects to finish.
- CPU listening page outside git: 12 sentences (8 seeded-random among the 38 changed windows, 4 counter-examples), RAW / `5820f3232` / `f773607b9`, spoken string, G2P input, engine phonemes.

## 10-11-2026 — Vietnamese compound phonemes after g2pvi

- Mined all 227 different-sounding shared sea-g2p words in the exposed residue-1 corpus. The shared JSON now contains 146 compounds/reduplications (143 text-reviewed additions, 3 retained pairs); aggregate counts and label criteria are in `docs/SHARED_VIETNAMESE_PAIRS.md`. Python and Kotlin use the same data. Newly searched words keep their previous contextual language until a pair proves them Vietnamese; Vietnamese-only partners are evidence rather than replacement targets. Mid-sentence capitals and explicit English remain protected. Bounded `do trans` and `in logo` contexts address the known examples without generalizing to arbitrary English phrases.
- Rule frozen at `3da9d086b` before third-holdout extraction and blind text labelling. Baseline is `3644901a5`: Vietnamese read English **1 -> 0 / 68** on design, **6 -> 2 / 144** on the g2pvi holdout, **14 -> 13 / 121** on a new 350-window residue-2 holdout (587 series, 9,990 chapters). Real English read English stays **66 -> 66 / 68**, **89 -> 89 / 98**, **111 -> 111 / 115**; no new name/romaji changes observed. Labels are model-only. Zero Vietnamese errors across all sets was **not achieved**; the original holdout retains capitalized Ban and isolated An An. Do not retune using the third holdout.
- Reused the g2pvi extraction, stratification, phoneme evaluation, weighting, spoken-text and latency scripts with explicit adapters. Spoken pieces and normalized strings are identical across **1,310 / 1,310** windows. CPU phonemize latency on the same 2,294-sentence sample: best 1.161 -> 1.068 ms; median 1.258 -> 1.275 ms (**+1.4%**, within +20%). Background load prevents treating the best decrease as a proven speedup. Weighted English-reading counts (including real English/names, not error counts): old pool 4,313 -> 4,290; g2pvi pool 3,768 -> 3,722; third pool 11,197 -> 11,149.
- Final related pytest (37 files, `-o addopts= -q -rf`, Qt offscreen): **2,347 passed, 0 FAILED, 3 skipped**. Focused shared fixtures: **181 passed, 0 FAILED**. Related JVM: **70 classes / 569 tests / 0 failures / 0 errors / 1 skipped**. Full JVM: **408 classes / 3,503 tests / 0 failures / 0 errors / 4 skipped**; started with 12,392,884 KiB free RAM. Both PhonemePolicy JNI tests and all three SeaG2pParity tests executed without skips. No physical phone was used. Full pytest was not rerun for this task.
- Shared fixtures contain 73 self-authored cases. The CPU listening page outside git contains 12 sentences and 24 embedded WAVs, with traced actual spoken strings, normalized G2P inputs, engine phonemes and commits. Six audio pairs change and six remain byte-identical; all twelve text/G2P input pairs are byte-identical. The page has no external dependencies and was rendered headlessly at desktop and narrow widths.
- Pronunciation policy/cache version **4 -> 5** (`direct-en5`), with seven regenerated shared clip keys; app version unchanged. This cache-only follow-up does not alter the frozen rules. Quality hash **83ee07ea67d4d2c41c8501707c669b12912b5d7fce6ab1c2cd828353422587b6 -> dc2aad8128c6124b9ecd132df906f7b22a9f1af36d684ef6f8576fb59e55bc0b**. Keep this on the dev branch until existing book runs finish.

## 10-11-2026 — g2pvi: Vietnamese words beside English names keep their Vietnamese phonemes

- sea-g2p gives a word found in both of its dictionaries the language of its nearest unambiguous neighbour, and an unknown name counts as English, so "con boss to quá", "quay sang Susan", "Lucy bay ngang" were phonemized as English. `phoneme_policy.restore_vietnamese` (Python, both desktop frontends) and `PhonemePolicy.restoreVietnamese` (Kotlin, real JNI) restore the Vietnamese phonemes; the text handed to the voice is byte-identical. Rules, data and measurements: `docs/TEXT_NORMALIZATION.md` section 6.
- Shared cases `tests/fixtures/readaloud/shared_vietnamese/cases.json` (39): decision, phonemes of Nghe ngay and Studio, and "only the claimed words change" in `tests/test_shared_vietnamese.py`; decision and real-JNI phonemes in `PhonemePolicyTest.kt`. The JNI tests ran (not skipped) against the host library.
- Related pytest (37 files, `-rf`): **2,244 passed, 0 failed, 3 skipped**. Related JVM (`vieneu.*` + `readaloud.*`, 70 classes): **569 tests, 0 failed, 1 skipped**.
- Full suites: JVM **3,503 tests, 0 failed, 4 skipped** (408 classes). pytest `-rf`: **11,093 passed, 4 failed, 14 skipped, 2 xfailed**; none of the four touches this change: `test_android_debug_id` (no vitest in this worktree's linked node_modules), `test_dev_endpoints` discovery probe (passes when rerun alone), and two source lints on files this branch does not edit (`scripts/audit_navigation_frames.py:115`, `ui/src/desktop/remoteToastOffset.dom.test.tsx`).
- New held-out set (523 series never read before, labels assigned before the phonemizer was run, rule frozen): Vietnamese words read as English **60 -> 6 of 144**; real English words read as English **89 -> 89 of 98**. Phonemize latency on CPU 0.894 -> 0.920 ms per sentence (+2.9%). Labels are the agent's; the book owner has not scored them.
- `english_policy.json` version 3 -> 4 (clip cache namespace `direct-en4`); the quality implementation hash changes, so this stays on a dev branch until no book is mid-run.
## 10-11-2026 — music library visual review

- Music rows now share a compact title/creator-duration layout on web, Android and Qt, with a fixed download-status column. Style stays in the detail sheet to leave room for long names. The shared buttons provide a primary preview and an outline download action on one row. Emotion comparisons use one labelled pair of thin, borderless progress tracks per emotion, a single legend and a sentence derived from the existing match data. The Information block includes tempo, style, duration, license, playlists, full attribution and the source link.
- Complete Android Debug JVM results, counted from all 399 XML suites: **3,451 tests, 3,442 passed / 0 failures / 0 errors / 9 skipped**, including native rendering snapshots. Actual TextWrap layouts at 360 dp and 100%/130% font scale pass the existing separator/orphan detectors: creator and duration stay on one line, titles use at most two lines, and download-column right edges differ by **0.0 px**. Download/cancel interactions use the existing queue.
- Complete Vitest JUnit results: **324 suites, 2,905 passed / 0 failures / 0 errors**. TypeScript `tsc --noEmit` and both generated parity-document checks pass. Related Python tests with `-rf`: **45 passed / 0 failed**. The outline exception in the layout inspector is limited to the shared primary/outline action pair; the fixture still detects an isolated outlined button.
- The completed Qt `build.bat` run passes **160 source-rule Python tests** and **18 native/QML suites: 2,146 passed / 0 failed / 1 skipped**. Glyph, QML type and text-leak counts are all zero; dependency/import checks and the packaged first-frame smoke pass. The run started with **6,370,756 KiB free RAM** and `CMAKE_BUILD_PARALLEL_LEVEL=1`. Earlier interrupted/red attempts remain in the task dossier; detector thresholds and skips were not relaxed.
- All **146/146** original gallery findings belong to the music branch and are classified individually against the original `(story, theme, ID)` and evidence. Final gallery inspection covers **20 views**, both themes, and **296/296 completed sheet geometry trials**, with **0 findings / 0 runtime errors**. Five full-resolution before/after comparisons cover the library at 100% and 130%, saved tracks, the complete Android detail sheet and the complete Qt detail sheet. Top/middle/bottom captures and enlarged visual checks include attribution and source links. Evidence, XML archives, screenshot hashes and comparisons are under the `musiclib2` task directory.
- The quality implementation hash is unchanged: `0157775d5c45d0fb6100014adc0ed2828b2b9090b1c73725b7723eb5f44e4e16`. No quality-locked source, catalog format, migration, version or release metadata changed. Existing limits remain: scene emotions are absent from shipped phone books, Qt's bundled font lacks some CJK glyphs, and emulator scroll jank has not been measured; these are not covered by the visual-regression results above.

## 09-11-2026 — mixfix Qt remix review

- The gated two-thread control regression failed on the original mixer (the control only returned when the two-second fake pull expired). The final test covers volume, seek and stop while the render thread is waiting, records control duration, verifies the new volume in the same PCM commit and rejects an extra reset on the next pass. Remix preparation now stages queue edits without consuming joining PCM or publishing voice state; after the unlocked wait, changed controls or an advanced cursor rebuild the plan before publication. Two deterministic cursor advances, 25 and 45 ms, preserve the entire 20 ms pivot budget after the wait. The call-order test was renamed to describe its first-padding-sample assertion; join retries are paced by the engine outside the lock.
- Temporary sink traces were removed from the source after measurement. The original idle Stop-to-Start maximum was **6,793.9 us** (120 remixes, 0/3 red); the final idle maximum is **114.1 us** (118 remixes, 0/3 red). The original six-process load was 0/8 red; its 36-process overload was 2/8 red with 3/326 boundary crossings. The final load uses three busy processes plus the test pinned to two logical CPUs, respecting the four-heavy-process limit: **0/8 red**, **0/315 crossings**, **651.7 us** maximum. These are different load configurations, not a controlled failure-rate comparison. The intermediate 32 ms-pivot version retained a 1/24 overload failure; its results are separate from the final version. These measurements use the periodic file sink, not physical WASAPI hardware.
- The complete default `build.bat` invocation exits 0 after **1,644.531 s**: **17 suites, 2,132 passed / 0 failed / 1 skipped**, including VoiceTests **60/0/0**, MixTests **93/0/0** and WidthTests **1,565/0/1**. Source-rule checks report **159 passed / 0 failed / 1 skipped**; QML member checks, dependency checks and packaged smoke pass. Three additional complete VoiceTests invocations each pass **60/0/0** on freshly rebuilt objects; the cache fixture passes **50/50** exact rechecks. After these runs only one duplicated test comment was corrected; restoring that line reproduces the tested source SHA-256 exactly. The earlier stale-object cache comparisons are excluded; the fixture now waits for the background decoder to finalize its header instead of asserting immediately on its placeholder zero-frame header. No detector threshold or skip was changed. The quality implementation hash remains `0157775d5c45d0fb6100014adc0ed2828b2b9090b1c73725b7723eb5f44e4e16`.

## 09-11-2026 — tlsleak: isolate JVM TLS and control resolver time

- Robolectric installs Conscrypt and a default hostname verifier in the shared JVM; Pin.install also replaces the default HTTPS socket factory and verifier. These outlive their sandbox. FastConnectTest now uses PristineJvmTls to establish JDK TLS for each case and restore the previous provider positions, verifier and factory afterwards. Removed IdentityCheckingFactory and the per-fixture withJdkTls workaround. The fixed-order FastConnectAfterRobolectricTest runs a real Robolectric/Pin suite before FastConnectTest with Conscrypt enabled; removing the rule produces 3 failures in 23 cases. JvmTlsIsolationTest checks both isolation and restoration.
- TlsRouteResolverTest's negative-cache assertions raced a 20 ms real deadline against worker startup, independently of TLS provider order: the retained load probe found 436 bad rounds out of 1,500 before the fix, zero after. TlsRouteResolver accepts a monotonic clock (System.nanoTime in production); cache/invalidation tests use a fake clock, including the exact 1,999/2,000 ms expiry boundary. Resolver tests no longer use Thread.sleep.
- Code commit ccb597543, based directly on dev/integ166 44cad40c8: three consecutive complete Debug + Release runs, each variant **399 XML suites / 3,449 tests / 3,440 passed / 0 failures / 0 errors / 9 skipped**. Both Test tasks were cleaned before every run, so these were executions rather than up-to-date results. FastConnectTest runs twice per variant, including the ordered regression. No new skip annotation was added.
- Recheck from _internal/mobile/android: `./gradlew --no-daemon --offline --max-workers=1 -Dkotlin.compiler.execution.strategy=in-process :app:testDebugUnitTest --tests vn.abook.player.net.FastConnectAfterRobolectricTest --tests vn.abook.player.net.JvmTlsIsolationTest --tests vn.abook.player.TlsRouteResolverTest`. Full-run logs, reproducer sources, mutation evidence and counts are retained in the external tlsleak task dossier.
- ChapterMusic* and their ConscryptMode.OFF annotations are absent from this integration base; remove that TLS-order workaround when integrating the separate musicclass branch. Robolectric suites no longer need to be placed after the net package to protect FastConnectTest. Quality implementation list read from code: 63 entries; hash unchanged at 0157775d5c45d0fb6100014adc0ed2828b2b9090b1c73725b7723eb5f44e4e16. No push, release, version bump or migration.

## 09-11-2026 — repeated speech and replay prevention

- Saved direct ASR for the two listening books flags 28/8,137 segments (16/2,694 and 12/5,443); 14 flags have MFCC self-similarity above the sampled control p95, including 12 verified segments. These are machine signals, not new owner listening judgments. All 1,845 short segments have saved direct ASR. Three short rows are flagged in AYNIK (one verified extra final word, one name-related warning, one already failed); none in the other book. Five short rows exceed the duration screen. Twenty traced examples and counts by voice are in the repeat2x task dossier, outside the repository.
- ASR now rejects local repeated content even when aggregate similarity/WER passes, preserves repetition evidence in decode/audio gates, and prevents name/repeat-context rescues from clearing it. The existing bounded repair schedule retains deterministic seed salts and requires two passing decodes. The mock repair regression reproduces the same seed and WAV checksum in two independent projects; no real book audio was regenerated.
- Android, Qt and web resume/reopen at the held position. Removed automatic 5/10-second rewind and its controls. Explicit seeks still replay as requested. Qt pause accounts for the audible fade tail and device consumption through the commit, while keeping the reader blocked until the final source position is published. Clock updates run after Start, outside the Stop..Start audio commit window.
- Red/green: original ASR tests had 15 FAILED lines before implementation; final ASR file has 20 passed. Web cursor tests had 3 failed before the fix; final related files have 25 passed. Qt pause had 2 failed before the fix; final complete VoiceTests has 58 passed/0 failed and complete PlayerTests has 50 passed/0 failed, including reader-during-commit coverage. The unchanged periodic audio assertion passes.
- One complete pytest invocation with `-rf`: **10,978 passed, 0 failed, 14 skipped, 2 xfailed**, three warnings, 2,239.61 seconds. The actual number of `FAILED` summary lines is **0**. Compileall and TypeScript checks pass. No new Ruff diagnostic codes in the changed existing Python files; the new test file is clean.
- One complete Android Debug unit run: **3,412 passed, 2 failed, 9 skipped, 0 errors** (3,423 tests). Both failures expected the removed rewind summary. After updating those expectations, the two complete affected files pass **37/37**. One complete Vitest run: **2,643 passed, 1 failed, 227 skipped**, plus one suite setup error. The failed assertion expected the removed rewind control; the setup error was the worktree lacking its own Python runtime. After fixing the assertion and setting ABOOK_TEST_PYTHON to the existing pinned runtime, both complete affected files pass **235/235**. Focused passes do not relabel the initial full runs as green. No extra full runs were made.
- Quality implementation list read from code: **63 paths**. Baseline hash **0157775d5c45d0fb6100014adc0ed2828b2b9090b1c73725b7723eb5f44e4e16**; final hash **192b8eae562d65da18b3472e4344eaba3affacb979f449d37474c5e8866ab06d**. Changes remain on dev/repeat2x from 44cad40c8; production and book DB/package contents were not changed. No release, push, version bump or migration. OPPO was unreachable; no real player/focus log was available.

## 09-11-2026 — cast167 child voices and gender resolution

- Restored automatic casting of every child, including boys and unknown-gender children, from the untouched female pool. Female character ranking applies; manually pinned male voices for boys remain valid. Registry integration covers two boys sharing a chapter, a preserved manual pin across recasting, and the common pre-export gender check. Recorded-profile provenance remains mandatory.
- Gender-ambiguous Japanese given names consult source-text evidence even when model votes agree. Tests cover both directions, insufficient evidence, whole-word name matching and listener gender locks. This is a heuristic for romanized names, not a new model evaluation or a guarantee for every name.
- Full pytest on 5c2e2d169: **10,966 passed, 2 failed, 15 skipped, 2 xfailed**; failures counted from both progress and `-rf` rows. The failures were a continuation HTTP timeout and missing worktree TypeScript dependencies. The existing shared dependency junction was added without installation; complete affected files plus child/gender/export tests then passed **74/74**. Additional registry/name cases passed **16/16**. The final 18 related files passed **255/255**, with **0 FAILED** rows; compileall of abook, tests and scripts exited 0. Raw logs are in the cast167 task dossier. A second full invocation was refused before pytest started because available RAM was below 6 GiB; the original full run is not reported as green.
- Read-only replay of the actual resolver, allocator and pin helpers on three Sugaru books and two other books gives **10/11** children female voices, up from **6/11**; the remaining boy keeps the listener's pinned Thái Sơn. No rejected voice appears among the six largest character roles in any book, and no Mai Anh is selected. Source SQLite and WAL hashes remain unchanged. Replay preserves stored speaker identities and does not run analysis, repair speakers, convert schemas or generate audio; tables and fingerprints are in the task dossier.
- The locked implementation list contains **63 entries**, read from code. Quality hash: **0157775d5c45d0fb6100014adc0ed2828b2b9090b1c73725b7723eb5f44e4e16 → 8c0a4d398c5e07513df601ca427c3014f327f676db961cef01771463b4042394**. The pre-export follow-up does not change the latter hash. All changes stay on dev/cast167; no push, release, version bump, production mutation or migration.

## 09-11-2026 — integ166b periodic audio regression

- The periodic sink assertion remains unchanged. MusicMixer waited for an engine pull before preparing replacement PCM; preparation could use the remaining period, leaving Stop/Reset/Write/Start across the next pull and producing real silence. A deterministic device models 9 ms of preparation and a 2 ms commit in a 10 ms period: the original code misses one period, while waiting after preparation misses none. This is a product scheduling defect, also present in 0.4.165, rather than an assertion to relax.
- Moved the pull wait into the shared remix commit after PCM preparation. Full VoiceTests passes three times, each **52 passed / 0 failed / 0 skipped**, including the new regression and the unchanged periodic ear assertion. The timing thresholds and skip policy are unchanged. The deterministic red/green logs, subsequent complete Qt and pytest results, final HEAD and quality hash are recorded in the integ166b task dossier.

## 09-11-2026 — integ166 integration regression

- Merged galwait, wavcache, timerbug2/shakesfx, audiofx/audiofx2, strsrc and latin166 in order from c128d6885; perf165 is excluded. File-level conflict decisions and durable raw results are in the integ166 task dossier.
- Complete pytest with `-rf`: **10,945 passed, 9 failed, 14 skipped, 2 xfailed** (10,970 collected, zero errors). Six failures were source-copy checks that did not expand the shared catalog; one fixture still expected the former female narrator ranking; one test-flakiness ratchet rejected a zero-duration delay in the audioFx test. Updated those checks without changing product algorithms, quality policy, thresholds or skips. The shared Mai fixture now explicitly reserves Ngọc Linh and expects Kim Thanh for narration. Complete affected files, including A+/chapter-teller tests: **94 passed, 0 failed, 0 skipped**. The ninth failure was a concurrent speaker-request timeout; exact unchanged case rechecked **3/3 passed**. These focused results do not turn the earlier full run into a green full run.
- Final full Vitest: **2,860 passed, 0 failed**, 320 files and all 79 DOM files present; tsc passes. The later test-only change replaces setTimeout(0) with waiting for the actual 5.95-second source-time seek; the full audioFx test file passes **17/17**.
- Complete Android `gradle test`, both variants, 397 suites each: Debug **3,420 passed / 0 failed / 4 skipped**; Release **3,419 passed / 1 failed / 4 skipped**. Registering Compose hosts only in the Robolectric sandbox fixes Release UI execution without changing the application manifest. The single Release TLS-route timing failure passes **3/3** exact rechecks. Real host JNI cases run. The four opt-in/environment skips are corpus dump, Python Bluetooth peer, Windows symlink privilege and Supertonic model.
- `build.bat test` was invoked and retained its red result; the Qt worker then ran all **17 suites** rather than stopping at VoiceTests. After fixing the stale settings hint expectation, complete WidthTests passes **1,565/0/1**. Latest per-suite aggregate: **2,122 passed / 1 failed / 1 skipped**, including setup/cleanup. No glyph, binding, text-leak, lint or timeout errors. VoiceTests.controlsLeaveNoHoleOrStepOnAPeriodicEngine remains red, with **0/3** rechecks and the same failure on the c128d6885 baseline; it is a release blocker, not a claimed pass.
- Immutable final gallery: **194 static views, 3,344/3,344 geometry trials, 0 findings, 0 errors**. Positive tap audit is **21/21**; the injected-pointer negative returns exit 1 as expected. Older failed/incomplete attempts are retained separately.
- Quality implementation hash: **67f8c360d80b19c73b66e6beaf2146e28179f2abcf1df200be15ef90e7d9febc → 7a917451aab99ce480ba3be9b61a05112de72d60826e3ff9e14cc364a414545d** (56 → 63 entries read from code). Integration fixes leave the merged hash unchanged. Version remains 0.4.165/code167. No push, version bump, release or packaging was performed; manual Android/artifact checks and hash approval remain required.

## 09-11-2026 — wbgate3: deterministic takes across memory pressure and crashes

- Primary synthesis, ASR candidates, word-break retakes and split fallback share a bounded resource retry budget. A transient OOM, including a wrapped exception or a native `MemoryError`, reruns the same take and salt. A lasting shortage stops at its reservation instead of spending a quality attempt.
- Every primary/clarity synthesis call keeps a durable take session: its starting segment snapshot (including the logical attempt count), reserved paths/seeds and completed take results. Recovery replays an open call through the chapter loop, including voices with no word-break gate, and retains the original clarity round. Completed takes are read back after checksum verification.
- The CPU fault matrix compares actual WAV bytes, the complete segment row except paths/timestamps, signals and artifact ledgers against uninterrupted runs. It covers each take, resource exhaustion and recovery, reservation/synthesis/result checkpoints, accept/close boundaries, candidates and split parts. Removing resource retry fails four regressions; removing session re-entry fails the plain-segment status regression; removing attempt-count restoration fails the DB comparison while audio still matches.
- Full `pytest -rf` ran once: **10,865 passed, 17 skipped, 2 xfailed, 3 warnings, 0 FAILED**, exit 0, 2,909.03 s. The raw log has zero `^FAILED ` lines. Real available RAM before starting was 12.240585 GiB. Related files first reported 1,053 passed, 2 skipped and eight fixture import failures; all eight were corrected and rerun with **8 passed, 0 failed** before the full invocation. The full invocation includes those corrections and the complete fault matrix.
- Quality implementation hash: `644488c3129f51a908beff757b4f1d03c1869f2f7ccd2e8fcd92e3e92f64b646` before the change, `4b53b8404d46218d17e6c8bfd21b77f4df5fb0ef838455f6bf97c804c96ce6dd` after; the latter stayed identical before/after the full suite. Changes stay on `dev/wbgate`; wait until runs pinned to the old hash finish before integrating. GPU repeatability and F8 gate overhead remain unmeasured. No schema migration, dependency/version change or release is included.

## 09-11-2026 — word-break retry review fixes

- The retry is now a pure function of the input and its reserved seed: crash at any point, out-of-memory and file-lock faults give the same selected take and metadata as an unbroken run (`tests/test_word_break_gate.py`, invariance matrix over 8 single-take and 7 candidate fault points, resume through the real chapter loop). Removing the chapter-loop re-entry alone fails 20 of those 26 tests.
- Replay of the 400 saved measurement pairs through the new rule: rank changes 0 of 17 retried pairs; the swallowed-syllable rule demotes one case only and that case already kept its first take. No new audio was generated; GPU overhead of the gate is still unmeasured.
- The final gate test file on the previous commit: **72 failed, 17 passed**. On this code: **89 passed, 0 failed**. Full `pytest -rf` at the fix commit: **2 failed**, 10,741 passed, 15 skipped, 2 xfailed, 3786 s. Both failures were test stubs/fixtures, fixed after that run: the affected files then gave **170 passed, 0 failed**; the full suite was not repeated, since only those test files changed.

## 09-11-2026 — word-break retry gate

- Enable the balanced-WAV in-word pause gate only for individually calibrated presets: Ngọc Linh (72.8 ms) and Đức Trí (frozen voice-local closure classifier). Kim Thanh and Đoan Trang remain disabled after failing independent validation/holdout; no sampling or source-text change.
- The existing candidate selector reserves one durable retry before inference, retains separate WAVs and records measurements plus before/after retry history in `signal_json.word_break_gate`. Reopening cannot spend another retry. An inconclusive retry alignment cannot displace a measured incumbent with otherwise equal signal quality.
- Focused gate tests: **16 passed, 0 failed**. Related regression: **796 passed, 0 failed**, `pytest -vv -rf`, 148.54 s. Coverage includes actual phonemizer invariance through a fake waveform engine, clean/inserted/persistent gaps, punctuation/newline exclusion, crash/reopen, ASR candidate isolation, signal-cache recovery, voice constants, locked policy and packaged assets. This is a development change, not a release check.
- Private frozen calibration and app-path measurement artifacts are retained in the wbgate task dossier; final sentence-bootstrap rates, PhoWhisper CER and observed CPU overhead are reported there separately from these regression results.

## 09-11-2026 — musicclass2 chapter music review fixes

- One mode vocabulary on all three players: continuous (the voice runs into the next chapter), manual (next()), jump (jumpTo(n, 0)), seek (jumpTo(n, 40), then a seek inside the chapter past the cue end and back across the cue edge), resume (pause, next(), play) and buffering (jumpTo while the voice stalls; Qt and web also hold the cue answer, Android cues are local). The step into chapter 3 repeats the cell's mode. 6 modes x 5 transitions = 30 cells per player. Android now has real next()/previous() cells (FakeExo implements hasNext/seekToNext/hasPrevious/seekToPrevious).
- Extra cells on all three: next then previous inside the 2 s crossfade (one audible track, every other element released), a cue starting at 30 s (Qt: reached only through the music sync timer, no position event fires while waiting), a late cue answer while paused in the next chapter (checked after the answer), paused in a quiet chapter then next into a chapter with music, and a rate change inside the crossfade.
- Mutation proof, run once and reverted (not committed). Android, perf165 gating `if (MusicBed.needsVoiceClock() || !exo.isPlaying) syncMusic(true)`: new suite 13 of 35 red (12 matrix cells: quiet->quiet, quiet->music, music->quiet in continuous/manual/jump/seek, plus the 30 s cue cell); the previous 25-cell matrix gives 11 red, as the review predicted. Resume and buffering cells stay green because onPlayingChanged/onWantsChanged sync without the ticker; music->other/same keep `current` set so the gated clock still runs. Qt, chapterChanged->onChapter disconnected: 30 of 30 matrix cells and 5 of 5 extra cells red (plus 5 older MusicTests), then MusicTests crashed. Web, `if (!bed.cues.length) return` at the top of sync: 0 of 25 old cells and 0 of 34 new ones red, because setCues starts the next chapter's track itself; the paused-in-a-quiet-chapter cell catches it (1 red), since the bed then still believes the voice plays.
- Android ChapterMusicTest reads the owner's music from the book's own book.json through Store.playableManifest and loads mix constants with MusicBed.init (packaged asset), so it no longer depends on the working directory. PlaybackService's ExoPlayer listener is an anonymous object inside onCreate; the test forwards the same two events (onIsPlayingChanged, onMediaItemTransition with reason SEEK) itself.
- Qt matrix waits with QTRY_COMPARE instead of one processEvents after releasing held answers, and drains queued player events before each fade tick. FakeOut.voiceAhead is settable: a buffering stream has little voice ahead, so Music does not prefetch the next chapter's cues and the held answer is genuinely late.
- FakeExo.seekTo(index, ms) changing the index: among FakeExo tests only ChapterMusicTest calls jumpTo; PausedSeekSaveTest and SleepExtendTest use the one-argument seekTo; ReplaceRefreshesPlayerTest checks `exo.items[exo.index]` after a replace and stays green.
- Separate task, not fixed: enabling Conscrypt in a codec-double Robolectric suite made two FastConnectTest cases fail depending on suite order, so TLS provider state leaks across Robolectric suites in the shared JVM. ChapterMusic* keep Conscrypt off.
- listen_audit: `run --quiet-chapter N` silences every music scene of chapter N through PUT /api/books/<id>/music {"silence": ...} and checks the server then returns no cues; a chapter without scenes stops the run instead of recording a fake scenario. The quiet chapters are stored in run.json and analyze reads them by default. Selftest now runs analyze() on synthetic sinks (music, declared quiet, music back / missing / leaking / undeclared). It is a Qt-app detector and does not replace the Android JVM matrix.
## 09-11-2026 — musicclass chapter transitions

- From origin/main c128d6885, added 25 chapter transition cases per player: quiet/quiet, quiet/music, music/quiet, different tracks and the same track, each through continuous play, manual selection, seeking, pause/resume and voice buffering. Every case also enters a third musical chapter. Assertions cover active/audible tracks, old-track release, new chapter position and paused music. Qt/web also delay the cue response.
- The 75 matrix cells pass. Main's Android voice ticker already calls syncMusic unconditionally; the needsVoiceClock optimization described in the perf165 review is absent here. Playback.kt, Qt playback/mixer logic and web playback logic are unchanged. Android only adds a codec factory override for JVM integration tests, null by default.
- Full Android testDebugUnitTest: XML 3,418 tests, 3,410 passed, 8 skipped, zero failures/errors across 392 suites; the 36 music suites contain 351 passing tests. The new Robolectric matrix disables Conscrypt, since its codec doubles need no TLS. This removes two order-dependent FastConnectTest failures exposed by the initial full run; the isolated 22 TLS tests, the coupled music/TLS run and the final full run pass without changing network code.
- Qt MusicTests, MixTests, VoiceTests, PlayerNativeTests and MusicWindowActivityTests pass offscreen. Final MusicTests rebuilt with position/pause assertions: 79 passed, zero failed/skipped (including setup/cleanup).
- Full vitest passed 320 files / 2,645 tests; readingForms could not start because the new worktree has no local Python venv. Rerunning readingForms plus the final chapter matrix with the explicit shared ABOOK_TEST_PYTHON path passed 252/252. This covers all 321 files and 2,872 unique tests. TypeScript noEmit passes.
- listen_audit analyze accepts explicit --quiet-chapters IDs, rejects missing music elsewhere and music leaking into quiet chapters after the fade, and treats an empty music: credit mark as a clear rather than a song selection. Planted quiet-middle/missing-return/leak controls pass its selftest. Related audio-sink pytest: JUnit XML 35 passed, zero failed/errors/skipped, with -rf.
- Heavy runs started only after at least 5 GiB free RAM, with at most two test jobs from this task. No emulator, migration, push or release. Tests use codec/device doubles; no new physical-device audio claim is made. Quality hash before/after is 67f8c360d80b19c73b66e6beaf2146e28179f2abcf1df200be15ef90e7d9febc; the implementation list read from code has 56 entries.
## 09-11-2026 — perf165c: review fixes and final-branch audit — not ready to merge

- Reproduce the quiet-chapter-to-music-chapter heartbeat regression before fixing it: 1 test fails with chapter 1 instead of 2. Remove music-clock gating and its one-second interval; the targeted music/buffering/events/checkpoint run then passes 36 tests. Remove the split tick listeners, lazy read-along paths in draw, prepareToDraw, the ungenerated disk-player/profile flag and the one-off Perf165Benchmark. Retain cover sizing, native density scaling, bounded periodic checkpoints and screen-off tick suppression.
- Use frozen origin/main c128d688511821616780b42cbe905cd2381c5773 versus the final2 runtime on the private headless API 34 AVD with SwiftShader. Startup and all seven frame flows have eight valid pairs each. Library-scroll >16 ms medians are 55.386% -> 36.667%, paired mean difference -19.251 percentage points, CI95 [-27.443, -10.974]. Other overall frame metrics and startup have intervals containing zero. Do not claim equivalence or identify a single cause of the earlier GPU-host regressions from this comparison; the renderer and baseline differ from perf165b. Retain real slow frames and all rejected raw data.
- Move Playback initialization/preparation, StudioClips cache-directory access, StudioAlerts access and Streaming cache opening to background paths. The expanded StrictMode audit includes pause, parked seek and resume: eight valid priority-notification pairs, five rejected RAM pairs, medians 71 -> 30; paired mean -40.5 violations, CI95 [-41, -39.75]. Periodic startTicking violations are 30 -> 0. Event saveNow remains 20 -> 20, and load-triggered Streaming.missingScript/keepScript and MusicBed.sync manifest reads remain 10 -> 10. Immediate durability and atomic sync/rename/corrupt-file rules remain intact. The main-I/O goal is incomplete; count event saves separately from baseline periodic saveNow calls.
- An exploratory StrictMode campaign suffered repeated Google Play services notification audio-focus interruptions. Preserve it without pooling it with the fresh eight-pair priority-DND campaign. The latter explicitly permits media, checks notification mode before/after both sides and restores it afterwards. Actual-runtime close-during-load preparation passes on the AVD. Final evidence review re-parses raw frames, checks all 80 retained pairs across ten campaigns, RAM/AC, APK/source identity and actual XML failure tags; the 29 rejected/aborted attempts within these campaigns remain archived outside git. Each campaign has eight retained pairs; the earlier perf165b campaigns are not pooled with them.
- Final2 source passes JVM Debug and Release separately: 3,393 tests each, zero failures/errors and the same eight existing skips. Both read-along golden tests pass without tolerance changes. Release's baseline-reproduced missing Compose test activity is fixed by a Release-unit-test-only Robolectric shadow that registers the same host/theme after the real Application.onCreate; exact endpoint assertions follow the current build variant. No test host is added to the production manifest, verified with aapt. Production release builds successfully: 6,425,607 bytes, SHA256 bebd9ea9a1962a752950ae7db7df91bef93a875b0c3da5a3a1234531c33ebecc.
- Fresh PSS/CPU measurements have eight valid 120-second PLAYING/Asleep pairs and two rejected/aborted attempts. All 48 media/power observations pass; final sample duration is 120.171-120.203 seconds, retained host RAM at least 2.412 GiB. PSS medians are 79,115 -> 70,551 KiB; paired mean -8,633.875 KiB, CI95 [-9,082.259, -8,294.250], or -8.432 MiB [-8.869, -8.100]. CPU medians are 7.01229% -> 7.06196% of one core; paired mean +0.15085 percentage points, CI95 [-0.03199, 0.36003], inconclusive. The 120-second window was fixed before its first sample after repeated short-audit RAM failures; it does not re-establish perf165b's ten-minute PSS result. Full mean and median paired intervals, all seven frame flows, resource conditions, failures and limitations are in the manually maintained perf165c result/report.
- Boot requires at least 6 GiB available RAM; discard complete pairs below 2 GiB or on loss of AC. Resource failures end the stage and stop the owned AVD before retrying. The private emulator is now stopped and DND restored. All ADB commands use the absolute SDK path, port 5038, the private emulator serial and timeouts. No real device, migration, dependency change, push or publication is involved. Quality hash is unchanged: 0f178264cdfa197d1449811716621f7319d7e3257d878b6aac3e2f237f8b27dc, 56 entries read directly from code. Overall verdict remains NOT READY because main-thread load/event I/O is still present, and the cause of earlier frame regressions has not been isolated.

## 09-11-2026 — perf165b: paired Android measurements and final artifact review

- Use the same private headless API 34 `perf165` AVD and ADB server 5038. Each comparison alternates A/B, records host CPU and available RAM, rejects whole pairs below 2 GiB, and bootstraps paired differences. Final evidence review passes for 21 campaigns, each with eight valid pairs (168 accepted and 31 rejected pairs within these campaigns). Keep all rejected raw data outside git in task `scratchpad/codex/perf165b/`; the manually maintained `result.md` records the measured benefits and remaining limitations.
- Original parent versus b319f2022 startup: eight valid pairs, no rejected pairs; COLD/WARM paired mean differences are +315.5/+38.25 ms, with 95% intervals [-13.75, 899.875]/[-27.875, 117.628] ms. Do not claim a startup improvement. A separate eight-pair onCreate experiment is also inconclusive and is not retained.
- Move periodic position checkpoints to one bounded worker, with a separate queue monitor and Store's own write monitor. Immediate pause/seek/chapter/record events retain their durable return contract; atomic sync/rename and corrupt-file preservation are unchanged. Eight PLAYING-validated audit pairs show median StrictMode violations 57 -> 27; paired mean difference -23.75, CI95 [-32.5, -12.5]. Three pairs are rejected for playback failure, including one also below the RAM threshold. Event/initialization I/O remains on main.
- Suppress UI/widget clock delivery while the screen is off and use a one-second heartbeat when UI/music does not need the half-second clock. Keep five-second durable checkpoints and the music clock when required. The earlier APK's eight one-minute screen-off pairs show CPU 9.6402% -> 8.9267% of one core (medians), paired mean -0.71298 percentage points, CI95 [-1.22074, -0.17543], with four rejected pairs. After the music reload correction, a separate eight-pair campaign on the final heartbeat APK is inconclusive: CPU medians 19.5057% -> 19.6388%, paired mean -0.21412 percentage points, CI95 [-3.79585, 2.23293]. Its 16 rejected attempts include 12 with RAM below 2 GiB. The final campaign runs after the private AVD's failing ConfigUpdater package is disabled; do not pool the environments or claim the earlier CPU benefit for the final source. Neither one-minute comparison is the original/b319 ten-minute comparison below.
- Native cover scaling keeps the same retained bitmap sizes. Eight pairs of 60 covers show the 840-pixel slot's paired mean decode-time change -74.24 ms, CI95 [-136.45, -21.21]; the 300-pixel slot is inconclusive. Sampled process PSS and kernel RSS high-water changes are inconclusive; do not claim a process peak-RAM reduction.
- Before the final music reload correction: **3,390 JVM tests, 0 FAILED, 0 errors, 8 skipped**, 393 XML suites. The first candidate had four genuine save regressions; preserve that failed run and the passing repaired tests. Five new checkpoint tests cover ordering, bounded queuing, failure recovery, nonblocking offers and the owner monitor. No production TLS/dependency/profile change is made.
- Diagnose the two read-along goldens causally: reverting only the gesture inset makes both old images pass; restoring the current 24 dp minimum makes both fail. Current actual light/dark images match the original runtime's actual PNGs byte-for-byte. Review both images and update only these two goldens; both then pass. The selected production release builds successfully (6,425,607 bytes).
- Original parent versus b319 ten-minute playback now has eight valid pairs and three rejected RAM pairs: PSS medians 81,442.5 -> 71,511.5 KiB; paired mean -9,945.625 KiB, CI95 [-10,025.25, -9,857.125]. CPU change is inconclusive, -0.11960 percentage points of one core, CI95 [-0.46078, 0.21507]. All 176 accepted media/power observations are PLAYING/Asleep. The previous selected APK also passes a separate ten-minute gate and retains a durable checkpoint 2,378 ms behind the extrapolated media position after force-stop.
- Recompute frame summaries from raw using an observed device-clock bound; retain real slow frames and archive previous summaries. Thirteen raw occurrences have impossible future completion timestamps. Independent review also catches a 1.890 GiB host-after snapshot missed by the two-second monitor: reject the entire original/b319 read-along pair. Replacement is now complete: eight valid read-along pairs and two rejected RAM pairs, including one new failed attempt. Its >16 ms paired mean difference is -1.94695 percentage points, CI95 [-6.59077, 2.35292], so the earlier seven-pair reduction is inconclusive at eight pairs. All fourteen frame campaigns have eight pairs; several metrics worsen, so do not claim smoother rendering or performance non-regression. The manual report includes every flow's paired differences and intervals.
- A quiet book invalidated by enabling music must wake the next music synchronization. Add the empty-book reload condition to needsVoiceClock and a regression test through chooseAuto/invalidate. The final source now passes the tests/goldens below and all three APK builds. Its production release is 6,425,607 bytes, SHA256 8a383ad8ad1caa3e0ded675b5ff07695c9e438ae84a09b07e24bd70cc89b97a1. Do not attribute the previous APK's measurements to this new source.
- The first reviewed targeted invocation ran 36 tests with one failure in the new music test: its fixture set MusicBed.book but omitted Playback.bookId, which chooseAuto uses. Preserve that failed XML/log separately. Set both book identities, restore them in finally, and assert that a playing fake voice remains playing. The retry passes all 36 tests. The final source then passes **3,391 JVM tests, 0 FAILED, 0 errors, 8 skipped**, 393 XML suites, exit 0 (11m53s), followed by both read-along goldens, 2/2 passed. Use one Gradle worker and a 1 GiB heap for these tests; sampled total process-tree RSS peaks at 2.08 GiB in the full run. No emulator measurement overlaps the tests. All three reviewed APK builds pass; the failed first run remains reported as failed.
- Final selected APK playback passes 600.172 seconds with 11/11 PLAYING/Asleep observations, host RAM at least 3.238 GiB throughout the monitor/snapshots. After force-stop, the durable checkpoint is 2,047 ms behind the extrapolated media position; this is one observation, not a zero-loss guarantee. PSS at minute ten is 71,109 KiB and CPU is 20.8224% of one core in this single gate, not an A/B speed result. The final Macrobenchmark passes diskLibraryScroll, OK (1 test), with five iterations and five matching nonempty Perfetto traces; host RAM stays at least 3.003 GiB. Final artifact review rechecks raw media/power, host snapshots, APK/source hashes and actual XML failure counts. The private emulator and owner have finished. Quality hash remains 0f178264cdfa197d1449811716621f7319d7e3257d878b6aac3e2f237f8b27dc (56 entries read from code). No commit or push. Functional gates pass; remaining main-thread event/initialization I/O, inconclusive final CPU/startup benefits and worse frame metrics prevent an overall performance non-regression claim.

## 08-11-2026 — rel165 integration regression

- Integrated timerbug2, ui165, nomig165 and audiofx into dev/integ165. The first full pytest run reported 39 failed, 10,612 passed, 14 skipped and 2 xfailed; its raw `-rf` summary is retained in the rel165 task dossier.
- Fixed a current-schema integration defect: continuation previously created character_exposure during seeding, so the strict schema gate rejected the seeded project on reopening. Fresh ProjectDB schemas now include that table; continuation only writes rows. Missing-table refusal remains covered, with the existing crash/reopen and atomic seeding tests. No schema conversion is performed.
- Updated diagnostics/peer/stop fixtures to the current contracts. Replaced historical SQLite copies in candidate tests with synthetic current-schema scenarios constructed through checkpoint and promotion APIs. Candidate checks, file hashes, replacement refusal and crash rollback remain exercised without adding skips.
- Cancellation fixtures now supply track measurements separately from cancellation phases; fake download/mix gates release only on the test's completion signal. Replaced the JVM wall-clock benchmark with a sustained finite-output/limiter assertion; device CPU measurement remains in the separate instrumentation tool.
- Targeted regression after these fixes: **189 passed, 0 failed, 0 skipped**, with `-rf`, JUnit XML and a real summary. The completed Windows build.bat invocation also ran **17 Qt suites: 2,111 passed, 0 failed, 1 opt-in skip**, including WidthTests **1,563/0/1** and AudioFxTests **12/0/0**. Counts include Qt setup/cleanup. Glyph, binding and text-leak checks are all zero.
- Quality hash after the four merges was fc26deb8e7481acdb8484098f84e6b0330ab653d84d7124b78bec90453d0f5a5; including the canonical exposure table it is **67f8c360d80b19c73b66e6beaf2146e28179f2abcf1df200be15ef90e7d9febc**. Full gate and packaging evidence are recorded separately in the manually written rel165/result.md; this targeted result alone is not a release certificate.
- The first packaged audio gate correctly stayed red when one of its two runs reported a 38.5 ms offset spread at 3x. Inspection of retained bytes found distinct source matches above the same 0.9 correlation threshold (for example .91865 at -68.58 ms versus .91539 at +20.65 ms). The matcher now refuses a measurement with accepted alternatives at least one complete window apart; all offset/drift/saw thresholds remain unchanged. A repeated-occurrence regression and a unique-offset control join the full audio-sink test file: **35 passed, 0 failed**. Original red WAVs/reports remain in audiosink-evidence.
- Full gallery inspection hit its 1800 s deadline with 3312 completed trials, zero findings/errors, and two voice-error story/themes still pending. This invocation remains FAIL. The full-matrix deadline is now 3600 s; coverage, pointer tests and geometry tolerances are unchanged.
- The subsequent full pytest invocation finished with **10,652 passed, 0 failed, 14 skipped, 2 xfailed**, three warnings, in 2474.69 s; the raw `-rf` log contains zero `FAILED` lines. The two newly added matcher regressions are also covered by the separate 35/0 invocation; they were added while the full invocation was already running, so its collection is not claimed to include them.
- Windows packaging completed with `INSTALLER_OK`, `SIG_OK` and packaged smoke. The 31,568,386-byte installer and signed 6,425,615-byte release APK are provisional: a new audio gate remains **FAIL** (first run has real stop/zero/click/cut findings, second run is clean). Do not replace the failed gate with its clean run. A gallery replay error is also being investigated; see the retained reports in rel165. No publish has been performed.
- A controlled-clock counterexample subsequently isolated an error in FileSinkDevice: advance sampled its deadline once, then file emission could cross a new engine period; stop changed state before accounting that interval, so the next advance recorded a false stop. Advance now catches up under its current state before changing it. The same 20-to-30 ms probe changes from a false 480-frame stop to no stop; a second regression still records a real 40 ms pause. No WASAPI/player behavior or detector threshold was changed. The complete new Qt invocation reports **2,113 passed, 0 failed, 1 skipped across 17 suites**, including MixTests **93/0/0**. The new packaged audio gate passes both fresh runs and every strength control. Repackaging, fake-profile install/update/uninstall and signature verification pass; final installer is 31,579,494 bytes, SHA-256 `9614a49d8e66ab487d4a2241b743dfbf4f54b3b03b306b56ccacd0d4b21e392b`.
- Tap audit initially dereferenced an undefined layer immediately after reopening a surface. The runner now waits for a real surface and fails if none appears; two regression cases cover pending-to-present and permanently absent layers. Regression **20/0**; all **21/21** live pointer scenarios pass, and the injected pointer-fault run exits 1 with **0/21** passing, as expected. Gallery geometry/static timeouts remain separate unresolved evidence and are not erased by targeted clean diagnostic runs.
- Full Kotlin JVM after fixture fixes: **3,385 passed, 0 failed, 0 errors, 8 skipped in 391 suites**, with new XML and Gradle exit 0 (388.0 s gate time). The POST fixture now consumes both request bodies before replying/closing. JDK TLS assertions run with Conscrypt temporarily displaced and restored in finally; a regression actively inserts it first and reruns both original-name SNI and wrong-name rejection checks. Selecting only a SunJSSE context was insufficient because JSSE's XDH generator also consults global providers; that intermediate red run is retained. No APK networking code/dependency was changed.
- Final harness regression: **122 passed, 0 failed** with `-rf` (150.81 s); gallery harness Vitest **48/0**. A subsequent full Vitest run found a motion snapshot test using real cleanup timers for its early phases while faking only its final row-exit phase. The complete C6 case now freezes timeout timers before the first render, preserving every existing snapshot assertion. The full motion test file passes **15/0**; the final complete Vitest invocation is recorded in the rel165 dossier.
- Complete Vitest after that fixture correction: **2,847 passed, 0 failed, 320 files**, 172.02 s. DOM coverage is **79/79** files against HEAD and verified in the verbose log. Typecheck, parity for both platforms, contrast, versions, quality hash, licenses, diff-safety, forbidden terms and CRLF checks pass. These are recorded individual invocations, not a signed full release certificate; gallery failures and the missing native packaged screenshot/pointer acceptance remain open.
- The final full gallery diagnostic, with phase trace plus DOM/PNG/input capture on error, completes **194 static states, 97 screens, 388 width/theme combinations, 836 openers and 3,344/3,344 geometry trials**, **0 findings, 0 errors** (1742.4 s). It does not reproduce the earlier replay or static timeout, so their causes remain unresolved; this clean diagnostic is not claimed as a root-cause fix. The original failed reports remain retained. Packaged Qt EQ/sleep screenshot/pointer acceptance is still missing because the required astera-app CLI is unavailable.

## 08-11-2026 — widthbook2: shared Qt visual readiness

- `VisualReady.js` previously began a single 5s wall deadline before polish, potentially leaving a 1ms allowance for a transition started during layout. It also accepted animation endpoints without proving that measured text geometry and post-render polish had settled. A controlled virtual-clock probe reproduces the budget error; the original failed full-run log has no phase durations, so it cannot prove that this specific timeout exhausted its budget that way.
- Preserve the 5s Qt polish/animation/render waits, drain polish after rendering/metric reads, and require matching text geometry across consecutive requested frames before auditing. Convergence is bounded by observed frames, returning as soon as stable; no blind sleep or numeric assertion/tolerance change. Input waits retain perpetual indicators. Three regressions cover queued width/font-size layout, a layout change queued after an actual frame, and live indicators; the queued-after-frame regression fails with the original helper.
- Studio3/4/5/6 `noCut()` now waits before reading text and parent geometry. Audit all 16 suites called by `desktop_qt/build.bat`: additionally fix SidebarTests icon captures to assert polish/render completion and selector checks to re-read both moving/target geometry. Complete SidebarTests: **166 passed / 0 failed / 0 skipped**. Complete Studio6 repeated five times: **51 passed / 0 failed** each. Qt Python rules pass (143 passed / 1 existing skip, exit 0).
- Final complete WidthTests, fresh hidden Windows processes, `QT_QPA_PLATFORM=offscreen`, unchanged test-source SHA-256 fingerprints throughout all five runs:

| Run | Passed | Failed | Skipped | QtTest time |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1532 | 0 | 1 | 873688 ms |
| 2 | 1532 | 0 | 1 | 893590 ms |
| 3 | 1532 | 0 | 1 | 870081 ms |
| 4 | 1532 | 0 | 1 | 839685 ms |
| 5 | 1532 | 0 | 1 | 830255 ms |

- Every process and `check_test_results.py` exits 0; zero missing glyphs, QML type errors or displayed value leaks. Studio4 long-text, Studio6 restored-position and all new readiness regressions pass in all five full suites. The single skip is the existing opt-in missing-glyph negative control. The three added regressions account for the pass-count increase from widthbook.
- Preserve all earlier development failures separately: the first prototype used a render-producing `tryVerify` predicate, later diagnostics dereferenced destroyed QML wrappers, and a later full run exposed missing post-render polish draining. None substitutes for the final five clean full invocations. Raw logs, source fingerprints, exact reused widthbook run commands, controlled probes, the 16-suite audit and development history are in task `scratchpad/codex/widthbook2/` (`audit.md`, `width-complete-1.txt` through `width-complete-5.txt`, `width-complete-results.json`, `final-verification.json`, `result.md`). Test/documentation changes only; no commit or removal.
## 08-11-2026 — shakesfx: timer extension sound and feedback audit

- Android Compose/native now shares `Feedback.kt` for sound and haptics. A successful shake or explicit timer extension plays the existing C6/E6 confirmation once, with its haptic in the same call. It runs without an Activity through AudioTrack sonification, respects the sound/haptic preferences independently and keeps the OS silent/vibrate mode. Ordinary feedback remains muted during book playback; warning and explicit extension are the two documented exceptions.
- Audited all six existing Android vibration call sites, including the service waveform. View/Compose calls now honor the app haptic preference; seek/setting ticks have the matching sound when paused. Long press, ordinary buttons, play/pause and errors intentionally remain silent under DESIGN. Remove vibration at timer expiry. All three platforms warn once before both minute and chapter timers; expiry remains silent. Qt/web extension buttons and fade input use the same confirmation notes.
- Final Kotlin JVM: **3,387 passed, 0 failures/errors, 8 skipped**, 391 XML suites / 3,395 cases. Final Vitest: **1,907 passed, 0 failed**, 200 files. Qt: **147 passed, 0 failed/skipped** (PlayerTests 49, DesktopApiTests 43, QML D3 45, PlayerStates 10; Qt totals include eight setup/cleanup entries). Related pytest with `-rf`: **21 passed, 0 FAILED/errors/skipped**, checked against XML. TypeScript typecheck and `git diff --check` pass.
- Updated three Android setting screenshots; record and verify each run **3 passed, 0 failed**. Inspected the light settings screenshot: the new timer exception hint wraps without clipping.
- Final APK and instrumentation APK built offline. Dedicated headless emulator `emulator-5596`, API 36, tested with its screen off and an actual looping Media3 source. Injected accelerometer input reached the production sensor listener: one sonification track (usage 13), one CLICK vibration and unchanged book playback. **2 passed, 0 failed**. Dispatch gap after `AudioTrack.play()` was **0.0175 ms**; this is not a physical speaker/motor latency measurement. Emulator audio was disabled; acoustic masking/startle perception was not measured. No real phone was accessed.
- Kept failed attempts in the task logs: two early targeted Vitest runs each had 62 pass / 1 fail while correcting the chapter branch; a readonly test assignment initially failed typecheck; an unquoted PowerShell Gradle property caused one build failure before tests; the first emulator run had 1 pass / 1 fail because sensor injection arrived after its deadline. Final reruns above passed. MSVC setup emitted a `vswhere.exe` warning but all requested Qt targets built and the tests ran.
- Read the quality implementation list from code: **56 files**, hash unchanged before/after: `0f178264cdfa197d1449811716621f7319d7e3257d878b6aac3e2f237f8b27dc`. Kept the existing `nosafety` removal on `dev/timerbug2`; no commit/push. Commands, XML, detailed audit and limitations: `scratchpad/codex/shakesfx/report.md` in the assigned task directory.

## 08-11-2026 — timerbug2: automatic sleep requires a chosen setting

- Audited 14 activation paths on the 0.4.165 `abook` tree: Compose Android (`mobile/android`), native Qt and web. The remaining cause from the previous audit was the default two-hour safety stop, which armed a one-minute timer while listening without a timer request. Change startup, settings, invalid-value and UI fallbacks to zero on all three platforms. Keep explicitly saved choices and night schedules.
- The other two old findings are already guarded here: extend from OFF is ignored, and cancel clears the recent-stop shake window. Existing JVM regression tests cover both.
- Red before production edits: JVM 2 failed, pytest 3 failed, web 1 failed, Qt 1 failed. Final green: JVM/Compose 220, pytest 159, Vitest 1282, Qt player 46, QML settings 21; **1728 tests passed, 0 failed, 0 skipped**, plus four passing Qt setup/cleanup entries. Counts come from JUnit/Gradle XML, with pytest run using `-rf`. The expanded web run needs `ABOOK_TEST_PYTHON` pointing to the shared runtime; the first attempt failed setup because this worktree has no Python runtime, then all 112 files passed after setting that environment variable.
- TypeScript typecheck, Python compileall and diff whitespace checks pass. The shared settings fixture now defaults safety to zero. Automatic sleep remains available after an explicit 1/2/3-hour choice, with the existing OS/screen/motion evidence gates.
- OPPO diagnostics through `scripts/phone_diag.py --device OPPO` cannot find a paired device; the device list is empty. No adb, install or deployment. The actual phone incident is unconfirmed. A previously saved value of two hours is preserved; this change does not reset user settings.
- Read the locked-file list from code (56 entries). Quality implementation hash is unchanged: `0f178264cdfa197d1449811716621f7319d7e3257d878b6aac3e2f237f8b27dc`. Evidence and full route audit: task `scratchpad/codex/timerbug2/`. No commit or push.
## 08-11-2026 — UI165 acceptance and action parity

- Reviewed the baseline 47 Qt candidate pairs and 241 native-only labels in `UI_PARITY_TRIAGE.md`; these are not counts of confirmed defects. Preserve unresolved capability/copy items. The generated inventories now contain 46 Qt candidates and 240 native-only labels after aligning the create-record confirmation and excluding an HTTP header setter argument.
- Fixed library scroll reset when the numeric grid model changes column count, and retained the manually scrolled reader paragraph/viewport offset after text reflow. The reader restores after a rendered frame; playback following keeps ownership when enabled. Qt's create-record confirmation now says `Tạo và nghe`, matching web/Android.
- Added hard checks for five reviewed operations at 13 source sites: create/delete/move listening records, enter a mini window, and automatically enter mini. Word mutation, icon mutation and missing-control negative controls must fail. Existing mode-switch/copy/icon/radius checks remain. Updated the obsolete Tauri mini exception reason without adding any exemption.
- Final Python Qt/parity gate: **144 passed, 0 failed, 2 skipped**, with `-rf` and JUnit counts. Skips: packaged `dist/ABookDesk.exe` unavailable; installed Lucide node package unavailable. No dependency installation was attempted. An earlier run had 4 failures while changes were in progress; its log remains in the acceptance dossier.
- Final selected Qt suites: **127 passed, 0 failed, 0 skipped**, including setup/cleanup: AcceptanceResize 27, Width 46, LibraryParity 7, Records 19, NavigationGeometry 6, NowPlayingGeometry 16, ScreenStackDirection 6. The result checker reports zero missing glyphs, QML binding errors and displayed value leaks. This is not a new full 1,500-test WidthTests run.
- AcceptanceResize uses the same live instances for 12 screen/mode fixtures × light/dark × seven resize steps (560, 839, 840, 1199, 1200, 1600, 840). Tests preserve a focused control and available scroll position, and the manually scrolled reader paragraph/offset. Geometry negative control shifts a visible label outside the frame and must be detected. **96 PNGs** cover four widths per fixture/theme.
- Android JVM/Robolectric: **106 tests, 0 failures/errors/skips** across SettingsScreen, NowPlayingUi, PlayPauseGeometry, BookCoverFlight, ShellRoutes, TabHost and MotionScan. No physical device is listed by `adb -P 5038 devices -l`; this is not physical-device acceptance or a new full Android screenshot set.
- Evidence: task dossier `scratchpad/codex/ui165acc/` contains `report.md`, manually written `result.md`, JUnit XML, retained red logs, `final-verification.json`, `screenshots.html`, 96 PNGs and two contact sheets. No commit. Quality implementation list read from code: 56 files, before/after hash unchanged (`0f178264cdfa197d1449811716621f7319d7e3257d878b6aac3e2f237f8b27dc`).
- **P8 remains open** for packaged/physical-device and complete-screen acceptance, remaining copy/capability review, and the original R28 gesture video `VID_20261026064113`. Existing ledgerui anchor/morph/Back measurements are retained; they are not relabelled as a new packaged run.
## 08-11-2026 — nomig165: current schema only (R34 / P6)

- Removed ProjectDB's migration backup, ALTER and legacy row conversion. Fresh initialization creates the complete schema and user_version atomically; reopening validates the version and all schema objects before opening a writable connection. The schema stays at version 13 because its 45 objects (28 tables, 11 indexes, 6 triggers) match a fresh fully initialized database from the received HEAD; SQL token comparison found zero differences.
- Same-version WAL recovery and initialization interruption are covered by subprocess exits; committed events survive and uncommitted work is discarded. Missing columns/tables/indexes/triggers and old/future versions are refused without schema repair. Store observation remains read only; restore candidates must pass the current-schema gate before any database replacement. Both accepted current-schema recovery and refused old backup HTTP paths are tested.
- Removed locked-settings default injection, peer host/port-to-addresses upgrades on Python/Kotlin, and old listening-profile normalization. Current-format damage preservation, journal replay and adopt/rekey recovery remain covered.
- Final CPU pytest with `-rf`: **1,047 passed / 0 FAILED / 0 errors / 0 skipped**, two disjoint invocations (971 cases across 22 files, 76 across 3 files). JUnit failure/error nodes and raw FAILED-line counts agree. JVM offline: **55 passed / 0 failures / 0 errors / 0 skipped**, 10 related classes; debug Kotlin/Java compilation passed. `compileall -q abook tests scripts` and `git diff --check` passed. No model, GPU synthesis, app window, phone or production book/DB was used.
- Earlier iterations are retained outside git: pytest 5, 16 and 2 failures; JVM 1 failure. Final checks above are separate successful runs. The Store gate was reviewed and limited to mutation/restore boundaries so observational fixture tests and diagnostics do not require initialization; the current-schema backup fixture and peer fixture were corrected.
- All work remains uncommitted on dev/nomig165. Read the locked set from code: **56 files**, 3 changed (`config.py`, `database.py`, `webui/store.py`). Quality implementation hash: `0f178264cdfa197d1449811716621f7319d7e3257d878b6aac3e2f237f8b27dc` → `fc26deb8e7481acdb8484098f84e6b0330ab653d84d7124b78bec90453d0f5a5`. Integrate after the active production run; use a clean project for the changed pipeline. Detailed report, logs and XML: `external task dossier (not published)`.
## 08-11-2026 — audiofx2: silence shortening, channel controls and book profiles

- Android Compose, Qt and web share the existing `… → Âm thanh` entry: Mono, Balance, conservative silence shortening, and a device-local per-book profile switch. Profiles include volume and speed. Default scope is shared; disabling an override restores the shared profile. DESIGN and UI inventories are updated.
- Silence shortening defaults off: peak threshold −60 dBFS, trigger strictly longer than 3 s, retain 1.5 s split across both edges. The 1.5 s floor preserves the current TTS scene-break rhythm. Source-time maps keep subtitle/progress clocks after trimming; seek resets the map. Web only seeks across decoded verified intervals and preserves live/unscannable clips.
- Kotlin JVM full coverage: 3,387 passed, 8 skipped, 0 failed (3,395 discovered), with all 21 FastConnect TLS tests in a separate JVM via an external init script. The ordinary shared-JVM full command previously had 2 TLS failures; it is not claimed fixed. An intermediate isolated run had 1 existing polling/timing failure; its recheck and final full run pass. No TLS assertions or timing tolerances were weakened.
- Vitest final full run: 2,857 passed, 0 failed / 320 files. Related pytest with `-rf`: 53 passed, 0 failed. Qt DSP/Player/Native/Mix/Voice/UI: 238 passed, 0 failed, including QtTest init/cleanup. Emulator: 1 passed, 0 failed, headless/read-only only; captures reject a foreground System UI error dialog.
- Web real OfflineAudioContext checks 20 mono/stereo/balance combinations; real media playback shortens a 6.8 s fixture to about 3.60 s at 1x / 2.50 s at 1.5x including startup, with final source clock 6.8 s. Source speech and the 1.5 s structural pause remain intact. Web light/dark inspection: 0 findings/errors, 48 geometry trials.
- Full suites precede a final disabled-slider opacity polish. After that visual change, all three builds, TypeScript, the 17 DSP tests, 14 Qt UI tests, 1 emulator test and web inspection pass; full suites were not repeated for opacity alone.
- No denoiser is added without a noisy imported-book corpus and listening evidence. No physical phone, release or commit. Quality implementation hash unchanged: `0f178264cdfa197d1449811716621f7319d7e3257d878b6aac3e2f237f8b27dc`. Detailed failed/final runs, probes, screenshots and limits: task `scratchpad/codex/audiofx2/report.md` and `result.md`.

## 08-11-2026 — audiofx: playback EQ, volume/boost and independent pitch

- Android Compose, Qt/WASAPI and web share `… → Âm thanh`, five bands/presets, bass shelf, app volume, 0–12 dB boost with linked peak limiter, and ±6 semitone pitch. Playback settings are device-wide; recording/quality files remain unchanged.
- Kotlin JVM full run: 3,381 passed, 8 skipped, 0 failed (3,389 discovered). Vitest full run: 320 files / 2,848 passed, 0 failed. Related pytest with `-rf`: 56 passed, 0 failed.
- Qt: AudioFxTests 12, PlayerTests 47, PlayerNativeTests 18, MixTests 91, VoiceTests 50, AudioFxUi/PlayerParity 7: 225 passed, 0 failed. UI tests and screenshots use offscreen rendering; the full WidthTests suite was not rerun.
- Each platform's 75 EQ measurements has worst error <0.249 dB. Android/Qt pitch checks cover ±3/±6 semitones at 1×/1.5×; web covers ±3/±6 with a real OfflineAudioContext/AudioWorklet. All stay within 3% F0 and 0.5% duration (web has exactly the requested frame count). Limiter sample peaks stay ≤−1 dBFS; these are not true-peak or perceptual listening results.
- Web gallery: light/dark, 0 findings/errors including 48 geometry trials. Android headless emulator captures light/dark and measures DSP CPU; no physical phone. Detailed logs and screenshots: task `scratchpad/codex/audiofx/`, report.md/result.md.
- Quality hash before/after: `0f178264cdfa197d1449811716621f7319d7e3257d878b6aac3e2f237f8b27dc` (unchanged). No commit or push.
## 08-11-2026 — strsrc: shared copy and design token sources

- `ui_strings/vi.json`: 5,751 unique copy keys; generated Kotlin, Android XML, TypeScript, Qt JavaScript and C++.
  `ui_design/tokens.json`: shared color, radius, type, spacing, width, motion, easing, reading and cover values, checked against DESIGN.md.
- npm, Gradle and CMake run `scripts/prepare_ui.py`. Raw copy gate: 0 violations; 83 exact exceptions with reasons.
  Mutation probes caught new handwritten copy on all three platforms (3/3). Ten web/Compose screen pairs have zero unexplained differences;
  all 41 remaining Qt wording candidates and four icon candidates have individual explanations.
- Complete JVM run (OpenJDK 21.0.8): 3,375 passed, 0 failed, 8 skipped. Complete Vitest run: 2,837 passed, 0 failed (319 files).
  Qt build's pytest rules: 155 passed, 0 failed, 1 skipped. Sixteen native/QML suites: 2,065 passed, 0 failed, 1 skipped;
  WidthTests accounts for 1,529 of those passes. Glyph, QML type and displayed-value errors: 0. Dependency/import/smoke checks passed.
- An earlier full WidthTests run had two stale expected-label failures and one VisualReady timeout (1,526 passed, 3 failed, 1 skipped).
  The label expectations were updated to the selected shared copy; the timeout was not widened. The three focused rechecks passed,
  followed by the complete green build above. JVM TLS tests failed under JBR 21.0.10, then passed targeted and complete runs under the installed OpenJDK 21.0.8.
- Offscreen evidence: four headless web images, three fresh Roborazzi images, 372 Qt matrix images and three selected long-text Qt images.
  Logs, before/after QA hash and the handwritten detailed report are in the assigned `scratchpad/codex/strsrc` task folder.
  QA implementation hash stayed `0f178264cdfa197d1449811716621f7319d7e3257d878b6aac3e2f237f8b27dc`. No commit or push.

## 08-11-2026 — perf165: Android allocation audit on an isolated emulator

- Continue the interrupted 0.4.165 audit on the headless API 34 x86_64 `perf165` AVD, using the absolute SDK ADB path and server 5038. The fixture contains 60 synthetic disk books, 2400×3600 JPEG covers, timed text and local synthetic audio; no owner's library or physical device is used.
- Retain only measured runtime allocation improvements: cover slot 840×840 keeps 4,320,000 -> 2,116,800 bitmap bytes (-51%); 1,000 clock events with no clock recipients allocate 1,376,256 -> 0 bytes; constructing 240 inactive paragraph geometry caches allocates 2,850,816 -> 49,152 managed bytes (-98.28%). Cover cache keys include both dimensions, with a landscape square/portrait regression test. Event tests preserve UI clock delivery, service state events and listener removal.
- Complete JVM gate on the final runtime source: **3,385 tests, 0 FAILED, 0 errors, 8 skipped**, 392 XML suites, Microsoft OpenJDK 21.0.8. The HTTPS fixture selects SunJSSE explicitly after Robolectric's global provider changes and asserts the exact hostname rejection rather than accepting unrelated transport errors. No production TLS change is included.
- Four opt-in emulator audits pass. Paired original/edited word-path bounds are equal. The two existing read-along screenshot goldens fail on both HEAD and edited source; actual light/dark PNGs are byte-identical across that pair. No golden is updated.
- Production release and R8 benchmark APKs build successfully. Extend the disk player Baseline Profile journey and fix Windows compiler-metrics filenames. Profile captures pass, but the new packaged rules have no demonstrated startup benefit, so the original packaged profiles remain byte-identical. Bounded profile capture is opt-in; normal generation keeps the library's stability defaults.
- Do not claim an overall startup, frame-jank, playback-CPU or process-PSS improvement. The host reaches approximately 0.76 GiB free RAM and the same original APK's cold-start median drifts from 1,286 to 1,925 to 2,992 ms. Keep raw startup, all seven gfxinfo flows, ten-minute screen-off playback, Macrobenchmark traces, allocation/StrictMode reports and full XML outside git in task `scratchpad/codex/perf165/`; `report.md` and `result.md` contain the final measured table and limitations. No commit or push.
- The chosen artifact retains the original packaged profiles: cold/warm medians 3,557.5/1,220 ms (10 each); 600.687-second playback PSS 80,858 KiB and CPU 13.6927% of one core, with all 11 media/power samples PLAYING/Asleep. Final five-iteration Macrobenchmark CPU-frame p90/p99 is 278.10382/364.137944 ms. These timings regress versus the earlier baseline under the observed host pressure; the lower PSS is not attributed to the runtime edits. An auxiliary 60-second CPU control with an initial Awake sample is explicitly excluded.

## 08-11-2026 — widthbook: retry settled Qt width measurements

- Apply the `80cde88c3` settings pattern throughout `tests/width/tst_width.qml`: retry post-open row layout, painted text bounds, cover geometry and page centering with fresh measurements inside each callback. Chapter delegates are re-enumerated after the asynchronous model count arrives. Keep every numeric bound/tolerance, the four-complete-row requirement and the deliberate intermediate/reduced-motion checks.
- Run the complete `build/width_tests/WidthTests.exe -o <log>,txt` suite three times in fresh processes, with offscreen QPA and hidden processes. The QML source SHA-256 is unchanged across all three runs.

| Run | Passed | Failed | Skipped | QtTest time |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1529 | 0 | 1 | 890127 ms |
| 2 | 1529 | 0 | 1 | 841023 ms |
| 3 | 1528 | 1 | 1 | 913140 ms |

- All 46 `Width` checks pass in each run, including `Width::test_book(rail1024)`. The existing opt-in glyph negative control accounts for the skip. All logs have zero missing glyphs, QML type errors and displayed value leaks; the project's `check_test_results.py` passes runs 1/2 and correctly rejects run 3.
- Run 3 fails in unchanged `Studio4::test_longTextWrapsAtBothWidths()`, at the shared `VisualReady.js:37` settled-frame deadline, before the `Width` test case runs. An isolated offscreen recheck of that unchanged Studio4 test passes (3 passed including setup/cleanup, 0 failed, exit 0); this does not replace the failed full-suite result. No shared-helper change is included.
- Raw logs, per-run glyph audits, commands, source hashes and the isolated recheck are in task `scratchpad/codex/widthbook/` (`width-run-1.txt` through `width-run-3.txt`, `results.json`, `studio4-recheck.txt`). Test/documentation changes only; no commit.

## 08-11-2026 — castaudit2: restore the owner's default A+

- Default A+ aligns an automatic unrecorded book narrator to the first-person teller's known gender, avoiding held presets and respecting narrator choices. Own first-person thoughts use the narration profile with unchanged speaker/character/kind; other thoughts retain their voice. Chapter exceptions compare against the aligned base; B remains explicit.
- Shared narrator presets freeze once any recording exists; automatic presentation only changes unrecorded lines. SQLite provenance supports reopen/undo, thought-only tellers and B pricing. Voice checks and held-preset checks use original character profiles, including listener choices that restore the base over a chapter exception. Read-only audits do not create absent provenance tables.
- Related pytest: **272 passed / 0 FAILED**, 20 files. Full final across four disjoint module groups: **10,595 passed / 0 FAILED / 14 skipped / 2 xfailed**, 10,611 XML cases matching the selected collection; 0 failure/error nodes. All fixture modules included, -rf throughout; seven real synthesis function names excluded with -k. No GPU/TTS. An audit plugin blocks production book writes; frozen fixture reads are allowed. Commands, full collection, logs/XML, per-shard results and skip reasons are outside git.
- Copy simulations preserve every recorded row and identity: Three Days keeps Phạm Tuyên, Pain and Your Story keep Đức Trí; 0 recorded voice changes. Pain/Your Story pass voice_integrity. Three Days retains 231 owner and 7 gender/attribution issues already present; allowing unrecorded chapter changes resolves only the 231 owner issues. Synthetic plan provenance is not audio evidence.
- The six ranked female narrators match the owner's tiers; the selector retains three unranked options (Ngọc Huyền, Trúc Ly, Ngọc Trân) after them. Mai Anh is unavailable; no catalog edits. Direct import returns 56 quality entries: `399466d2d36947cad30817d144b69c61b24892ab8df88742f3c64f57267d3cf7` -> `0f178264cdfa197d1449811716621f7319d7e3257d878b6aac3e2f237f8b27dc`. Compileall, LF and diff checks pass. Uncommitted dev/castaudit only; detailed report/logs/XML/copies stay outside git in task castaudit2.

## 08-11-2026 — castaudit: two unintended paths from f01a158e8

- Crowd casting still supplied only a source hint to an attribution helper that now requires accepted speaker/confidence. Supply the accepted kind, speaker and confidence; preserve an individual speech tag when semantic kind differs from the hint. Six synthetic SQLite/casting cases cover the caller and reopen. The two crash cases pass on f01^, fail on f01 and received HEAD, and pass after the fix.
- The new quote stack treated every straight apostrophe as a thought closer, dropping the previous non-space/non-word predicate. Reuse `THOUGHT_CLOSING_PATTERN` within the stack scan. Twelve synthetic cross-paragraph cases pass on f01^, fail from f01 through received HEAD, and pass after the fix; existing nesting and single-paragraph cases remain covered.
- Related final pytest: **2,604 passed, 0 FAILED, 0 errors**, 52 files, 6 deselected. Full final pytest `-rf`: **10,557 passed, 1 FAILED, 0 errors, 14 skipped, 2 xfailed, 8 deselected**, 3 warnings; JUnit and raw FAILED-line count both report 1. The sole failure is the perceptual environment-restoration test because this audit's harness pre-set `TRANSFORMERS_OFFLINE=1`. It fails on both received HEAD and the changed tree with that variable set; the entire 27-test module passes on both with it absent. The full invocation remains reported as failed; rechecks are separate.
- Excluded real voice/model synthesis with `-k`, ignored four modules that read Audiobooks fixtures, and redirected external speaker evaluation to an empty task directory. No model inference, GPU use, or Audiobooks access. Compileall, LF and diff checks pass. Directly imported 56 quality entries: `e33e20f4d109266753ff58c956f8be4eb949fd936e4226bc6e107c9dad1a0120` -> `399466d2d36947cad30817d144b69c61b24892ab8df88742f3c64f57267d3cf7`. Changes stay uncommitted on dev/castaudit. The full behavioral inventory, older-code probes, commands and XML are outside the repository in the castaudit task directory's report.md.
## 08-11-2026 — short English delivery and Japanese frontend syllables

- The fixed eight English capital cases improve from **6/8 to 8/8** using the same CPU ASR check, voice and seeds. Preserve strong stress for a short unambiguous English word before ?/!, and sustain its stressed diphthong after /w/. The shared phoneme policy has no per-word WHAT/WAIT table; source words, punctuation and inference boundaries remain intact.
- Restore the missing /i/ of standalone romanized `gi`, preserve a generated name's `o_` through Studio's first normalization and its syllabic /ɔ/ through the second, and render unprotected Japanese components beside a locked joined suffix with exact anchor maps. Whole listener readings and protected bytes retain priority. Python and the actual host JNI share phoneme fixtures.
- Japanese spelling ASR improves **12/34 to 14/34**. An independent Vietnamese wav2vec2 CTC model matches exact expected Vietnamese phoneme sequences on **26/34** targets, versus **24/34** before. Fourteen remaining romaji misses have that independent reference match; six remain inconclusive. These are model diagnostics with owner-style Vietnamese approximations, not human or native Japanese accuracy labels.
- The owner source search covers all seven AYNIK/Noi ma project DBs and both exported AYNIK packages. Only AYNIK segment 2488 has a surviving Hello WAV; stored and fresh Whisper plus independent CTC retain Hello in the WAV and chapter excerpt. Both packages contain the same chapter checksum. The reported omission is **not reproduced or claimed fixed**. Sixteen short English ?/! cases retain **14/16** strict spelling hits; all 24 prior short cases retain **17/24**, with zero new misses.
- Final verification: **1541 related pytest passed**. Full collection and execution: **10818 tests, 10802 passed, 14 skipped, 2 xfailed, zero failed/errors**, eight disjoint partitions, all exits 0 and **zero FAILED lines with -rf**. Kotlin full task: **3395 tests, 3391 passed, 4 skipped, zero failed/errors**; all three new tests, including native JNI, execute. Compileall and diff checks pass. Qt is offscreen, Java is headless; all **116 linked MP3s** decode fully.
- Cache rules **13 to 14** in Python/Kotlin. The code-derived quality list has **60 entries**, including `readaloud/phoneme_policy.py`. Hash `f6f3ad14fef4bfc8cac07148287255c4e2002674419632d46c48e1541168430c` becomes `f7d5a0f8daa66ad0e8dd1264ebb39349e0c3ecd6ce9580625cf95d05f951b2c7`. No commit/staging, dependency/model changes, migration code or source project writes. Private clips, per-target transcripts, report, listen.html and logs remain in the latin166d task directory outside the repository.

## 08-11-2026 — spoken capitals, owner abbreviations and automatic voice choices

- Keep lexical English capitals lowercase at the final VieNeu reading boundary. Apply the owner's mixed letter/word readings and common Vietnamese expansions from one `english_policy.json`, embedded unchanged into Kotlin. VN and KTX use occurrence context; explicit listener readings keep priority. Unknown short codes retain English letter names, with Z pronounced zed.
- Narrator female tiers are Ngọc Linh/Kim Thanh, then Đoan Trang, then Mỹ Duyên/Quỳnh Anh/Thục Đoan. The shared `never_auto` list excludes Ngọc Huyền, Trúc Ly and Ngọc Trân from automatic roles and fallbacks while retaining manual selection. Web, Kotlin and Qt default selection follow the updated data; equal tiers use deterministic catalog order.
- CPU audio: fixed English targets **29/37**, Japanese **12/34**, sound pairs **26/26 unchanged WAV and MP3**. Eight capital-word cases improve from **3/8 to 6/8** exact ASR matches. The requested Hello omission was not reproduced: preprocessing retains its phonemes, the exact sentence and its source WAV contain the ASR target; 24 self-written isolated-English cases retain **17/24** strict spelling matches. These are machine checks with documented misses, not a listening verdict or proof that every isolated English word is audible.
- Preserve the frozen text labels. Under the owner's updated abbreviation references, enaudit **596→611/671**, held-out #4 **951→952/1076**, primary **1690→1698/1855**, soundfix **343→350/391**; zero newly broken occurrences. The unchanged old labels are also reported separately because they prescribe different HP/MP/NPC readings. English and sound groups do not regress.
- Final Python: **1509 related passed**; full collection and execution **10786 tests: 10770 passed, 14 skipped, 2 xfailed, 0 failed/errors**. Four complete partitions exit 0; `-rf` logs contain **0 FAILED lines**. Kotlin full `:app:testDebugUnitTest`: **3392 tests, 3388 passed, 4 skipped, 0 failed/errors**. Web voice tests **27/27**, TypeScript, compileall and diff checks pass. Test-only synchronization fixes cover callback publication, process disappearance and a cache-identity test's clock; production playback/network behavior is unchanged.
- Reading cache rules **12→13** in Python/Kotlin. The code-derived quality list has **59 entries**; hash `00621d2fe93b76496889e6aea804c9944699e586f0011e1707a908a40b3c5a5b` → `f6f3ad14fef4bfc8cac07148287255c4e2002674419632d46c48e1541168430c`. Private source context, CPU clips, per-occurrence scores, full logs and the detailed report remain outside the repository. No commit or production project mutation.

## 08-11-2026 — kotfix: Windows JVM atomic file replacement

- Unchanged origin/main `5678fddf7` reproduces the exact 25 reported failures on Microsoft OpenJDK 21.0.8; the same 45 tests pass on JetBrains 21.0.10. A standalone file probe confirms that `File.renameTo` refuses an existing target on the former and replaces it on the latter. These failures predate the integ165 merges.
- The release gate already runs the complete Kotlin unit task with `--rerun-tasks` and checks fresh XML plus the process exit. Its default JBR environment passes the original tests; the parser correctly counts and rejects the new main/MS failure evidence. No Kotlin gate omission was found.
- Share atomic replacement across Store, book music downloads, small peer downloads and cover-size caching. Windows uses an atomic NIO move in a separate host class; Android keeps its POSIX rename path, including minSdk 24. Keep Store's sync, completed-writer publication, old destinations on failure and existing download validation. No delete-before-replace or copy fallback.
- Two new Store durability regressions cover repeated binary replacement and partial-write failure preserving committed bytes. Before the product fix: 4 passed / 1 failed. The first full MS run after fixing Store exposed three other writers: 3370 passed / 3 failed / 7 skipped. After routing them through the shared primitive: 9 affected classes, 63/63 passed on both MS and JBR.
- Final full `:app:testDebugUnitTest --rerun-tasks --info` on MS: **3380 tests, 3373 passed, 0 failed/errors, 7 skipped, 388 suites**, exit 0, 4m54s. Skips require the import corpus, Python Bluetooth endpoint, symlink privilege, Supertonic model and three sea-g2p host fixtures; no skip or relaxed assertion was added. Raw logs and immutable XML copies are in task `scratchpad/codex/kotfix/report.md`.
- No repository Python, dependency, version, GPU or device changes; no commit/push. Directly imported 53 quality entries; hash remains `998bbdbf94139368cb858e3347247ae23779700ae5eba911f5dac9d03f613fe8`.

## 08-11-2026 — dev/enword-direct: VieNeu English spelling

- VieNeu Studio and desktop/Android ReadAloud share policy data and synthetic fixtures. English/Western names retain spelling; English acronyms use letter spans with automatic provenance. Japanese/Korean routes, explicit listener readings, Vietnamese abbreviations and established acronym-as-word readings retain their current behavior.
- Protect Vietnamese homographs in decomposed proposals and automatic pronunciation substitution, including capitalized tokens. Added a read-only detector. Preserve vocalizations, structural numerals, codes and arrow meanings when applying English spans. Western full/short forms share component rows. VieNeu clip keys include the policy namespace; policy data/code participate in quality and casting hashes.
- One final CPU pytest invocation: **3,750 passed / 0 FAILED / 3 skipped**, 79 related files, `-rf`; JUnit and raw FAILED-line counts agree. Kotlin changed scope: **507 passed / 0 failed / 1 skipped** across 61 classes, including native sea-g2p frontend parity. Broad Kotlin run: 527 passed / **25 failed** / 1 skipped; all 25 failures reproduce by name on the unchanged HEAD snapshot, with zero new failures. Existing optional service/model conditions account for skips.
- Private 28-segment paired synthesis through the real coordinator: exact ASR spelling **27/37 vs 19/37** in the existing package, 10 added hits / 2 newly missed hits; Vietnamese homograph controls **2/2 vs 0/2**. Newly missed ASR targets are MADE IN CHINA and BIOHAZARD. UTMOSv2 **2.881 vs 2.908**, NISQA-TTS **4.189 vs 4.158**, sentence speaker cosine to package **0.933** (26 clips at least 3 seconds). These are machine diagnostics from one selected book, not human listening verdicts or mobile audio measurements. No story sentences or audio were added to the repository.
- Final synthesis: CPU, same harness presets/seeds, median RTF **1.161**, **0 GPU borrows**. All 56 comparison MP3s fully decode and match the ASR/NISQA/speaker-score checksums. Identical MP3 bytes between private iterations reuse scores by SHA-256; iterations do not add independent samples.
- Read the implementation list from code: 53 entries before, **55 after** adding policy code/data. Quality hash `998bbdbf94139368cb858e3347247ae23779700ae5eba911f5dac9d03f613fe8` → `80e4c2d1b4f22b892b26638404c234f1d754d6e02be5fde3efc52e3baedce2aa`, stable throughout final synthesis/scoring. Compileall and diff checks pass; changed Python/Kotlin use LF. Uncommitted dev changes only; source project SQLite is unchanged.

## 07-11-2026 — voxfix on dev/integ165

- Inline quote shape only resolves an empty/UNKNOWN owner; named/local speakers and thinkers survive. Existing speech-tag attribution and batch-edge context remain authoritative. Explicit teller presentation covers NARRATOR in every kind without changing identity; default mode stays inert. Nullable provenance supports undo of an initially absent character/profile, with no migration.
- Added a read-only pre-export voice gate for single books, series and partial exports: chapter ownership, gender, signal and nested split provenance. Named thoughts keep their own voice. Intermediate backup layers remain available.
- Archived batch replay: **0/35 female speakers erased** (old result: 35/35). On frozen copies of 7,418 source rows, gate issue sets exactly match the prior audit: 41 owner mismatches and 29 gender conflicts, 67 distinct rows; both require calls refuse export. No acoustic inference or regeneration.
- Full frozen castrules replay, baseline verified against all 184 local and 15 gold detail files: raw **3,887 -> 3,933** errors (6 rescued / 52 newly wrong), envelope **1,577 -> 1,587** (0 / 10), gold **112 -> 56** (56 / 0). The raw/envelope acceptance limits are **not met**. Every local delta preserves a name previously replaced by NARRATOR; kind correctness is unchanged. Gold uses saved model labels with some adjudication, not wholly human labels.
- Pytest `-rf`: 187-file run had 4,577 passed / **10 FAILED** / 3 skipped. Corrected the old name-erasure expectation and incomplete recording/continuation fixtures; reran all six affected files: **92 passed / 0 FAILED / 0 errors**. Latest complete result per file: **4,587 passed / 0 failed / 3 skipped**, 4,590 unique cases. This is the combined final state, not a single clean full invocation. JUnit and raw FAILED-line counts agree. The skips require unavailable optional voice models.
- Compileall, both UI parity checks and diff check pass; changed Python files use LF. Directly imported 53 quality implementation entries: hash `e1825affd77d1b7ba5766f9b91784b959e8caaafde34348d2fd6ae798cf50aa9` -> `72070ca5df3d2dae375938f8315e2b5971e939462c511f954bc8eaa9dd46d16a`. Uncommitted on dev only; CPU replay, no model/API/GPU calls.

## 07-11-2026 — dev/castrules: speaker and kind postprocessing

- Quote hints are advisory across schema, validation and durable critic acceptance. Speech attribution requires a real speech tag; weak generic cues cannot replace confident identities or propagate through a paragraph. Kinship roles and conflicting gender evidence block name merging; vocatives and introductions cannot seed ABAB.
- Inner speech retains the thinking character and voice. Explicit narration presentation changes only the voice profile, with SQLite provenance, atomic audio resets and undo after reopen. Worker and review cards use the same identity policy.
- CPU regression run: **1660 passed, 0 failed, 3 skipped**, 92 related test files, `-rf`, verified from JUnit (1663 cases, 0 failure/error nodes). The skips require uninstalled voice models; no model was downloaded or called. Initial unchanged baseline: 1304 passed, 0 failed across 58 files.
- Synthetic Vietnamese regressions cover all requested classes, source-text preservation, semantic kind crossing a hint through accepted-candidate reopen, and narration profile rollback/undo. `_calibrated_intensity` is unchanged. Measurements and remaining tradeoffs: [castrules/result.md](castrules/result.md).

## 07-11-2026 — flake164: deterministic Qt test readiness

- Test-only changes; rebuilt WidthTests only. Product source/dependencies are unchanged. The original builder helper can return at phase 1 while its 1 → 0 → 1 sequence is running; controlled precondition probe fails. Historical assertion did not recur naturally in 120 focused baseline runs or one full baseline suite.
- Share animation/polish/render readiness and recheck after the rendered frame; apply it to builder, route, scroll and geometry helpers. Open the six-chapter fold explicitly before asserting wrapped chapter rows. Await WindowMode.transitioning before geometry assertions/edits. Replace an export 200 ms wait with request/timer conditions.
- D3 motion contracts use a scoped QAnimationDriver test clock and actual rendered frames: busy wall-clock scheduling can skip every intermediate frame, even with signal capture. Preserve intermediate/end assertions, real product durations, existing visual/glyph audits and absence windows. Three added regressions cover helper readiness, repeated sequence endpoints and the controlled clock/normal-driver recovery.
- Final WidthTests: 10/10 complete fresh processes PASS, each 1515 passed / 0 failed / 1 existing opt-in skip, under 32 CPU burners, BelowNormal, offscreen/software. CPU 99.3–100.0% (trung bình mẫu 99.85%). Targeted matrix: 50 passes each for clock/builder/Mini/D3 (200 processes). Current target without added load: 10/10. SidebarTests: 5/5 × 157 passes. Full qt_pytests.py: 144 passed, 1 warning in 248.66s (0:04:08).
- Directly imported 53 locked entries; implementation hash remains `5769f2787088e6389c7b9d1fe860db839923247fead4d6e3428e141804af4e9e`. No product rebuild, GPU task, stage or commit. Details, all failed exploratory phases, per-run logs and process cleanup evidence: root report.md and _internal/runtime/flake164. Diff check PASS.


## 07-11-2026 — smoke164: packaged file-open observer race

- Rebuilt `ABookDesk` and ran the complete `smoke_packaged` three times at each first-parent boundary: `e7aa8ec90` (before merges) 3/3 PASS; `d1c579a03` (merge-164) 3/3 PASS; `2d947f4ef` (perfaudit) 3/3 PASS; `47b3d6015` (perfandroid) 2/3 PASS. The failing natural run captured `.Sách thử · Tập 1 (af4356eb).ad605074.part` as the first book and reproduced "cuốn đầu biến mất sau lần mở thứ hai". Another passing run counted the second book's staging directory early: the old observer could also pass before publication.
- Root cause is `smoke_open.books`, which counted every directory while `BookFile.extract` writes into a hidden `.part` directory and then atomically renames it. The observer, packaged smoke and extractor are byte-identical across these merge boundaries. A controlled scheduling reproduction (600 ms hold before swap; 800 ms delay before launching B) makes all four old observers fail with the reported message; the corrected observer passes the same full packaged smoke. This is a pre-existing observer race, not evidence that perfaudit loses a book.
- Count only published, non-hidden book directories containing `book.json`. Keep the existing exact book counts, first-book retention, live-instance, handoff timeout and second-process exit checks. No smoke verdict, threshold or negative audio check was relaxed or skipped; no application/performance code was reverted.
- Two ordinary regression tests in `test_qt_smoke_open.py` fail before the fix and pass after it. They observe two real imports immediately before/after atomic swaps, verify all imported file sizes/checksums, reject staged/retired/unpublished directories, and still expose a removed first book. `qt_pytests.py` discovers them before packaging. The targeted regressions plus startup-import test pass (3/3); compileall passes.
- Installer rebuild: 144 Python rules PASS; all 16 Qt suites total 2,037 passed / 0 failed. WidthTests contributes 1,512 passes (652.703 s); its one existing opt-in glyph-fault probe remains unselected exactly as in the original build. No skip was added.
- Audio release gate PASS: 2/2 runs, 165.24 s each, zero findings; all 52 planted-fault checks PASS. Fresh packaged smoke PASS, including real MP3 playback, broken-MP3 rejection, both file launches and signed-update rejection. Installed app host/file-open, install/update/uninstall and real-state preservation checks report `INSTALLER_OK`; final signature reports `SIG_OK`.
- The first full `build.bat installer` reached all preceding gates but exited 1 because the machine lacked `%LOCALAPPDATA%/tauri/NSIS/makensis.exe`. Restored NSIS 3.11 and its plugin from the hashes pinned by [the repository's Tauri CLI 2.12.0](https://github.com/tauri-apps/tauri/blob/tauri-cli-v2.12.0/crates/tauri-bundler/src/bundle/windows/nsis/mod.rs); no project dependency/version change. Continued the packaging script with `-SkipResources -Installer` (exit 0), reusing the resources just built and rerunning host, packaged and installer gates; no test or smoke gate was skipped. Logs retain both invocations.
- Built `_internal/desktop_qt/build/installer/ABook_0.4.164_x64-setup.exe` (31,525,871 bytes), `.sig` and `latest.json` version 0.4.164. Installer SHA-256: `de7760e4f6ac6c9b271c9e7170f824a292780a662fc3530f7019bfb8a5093c48`.
- `SMOKE_PLAY_BROKEN ... Chapter is not a supported MP3 file` is the intentional random-byte negative control: exit 6 and no audible signal are required. Real MP3 playback passed (2.6 s heard at 440 Hz) at every boundary and after the fix.
- Bisect, controlled reproduction and final installer runs use offscreen/software rendering and private desktops/profiles; packaged smoke gets the matching build Qt's offscreen QPA plugin through the task-local launcher, without changing the shipped package. The first stock smoke rerun used its built-in private-desktop mode (the tool strips inherited `QT_*` settings); subsequent runs explicitly configure the launcher. An initial offscreen attempt without the matching plugin could not load the platform and its process tree was terminated. Evidence and launcher scripts are in task `smoke164` (`bisect.log`, per-commit smoke/build logs, `race-*.log`, `regression-red.log`, `regression-green.log`, `installer-build.log`).
- Quality implementation hash before/after: `5769f2787088e6389c7b9d1fe860db839923247fead4d6e3428e141804af4e9e`. No `_internal/abook/`, dependency, version, production book/audio or installed-app changes; no inference/GPU job, commit or push.

## 07-11-2026 — gate164b: hồi quy trên cây tích hợp (dev/integ164)

- Soát phần gộp hợp: hai bảng `wav_signal_metrics` và `chapter_teller_lines` tồn tại ở DB mới và sau reopen; integrity/foreign-key check qua, không sửa schema. Sắp các mục báo cáo mới theo ngày, giữ nguyên nội dung bằng chứng; CHANGELOG không có mục trùng hay câu bị cắt. Tái sinh cả hai tài liệu parity từ nguồn tích hợp.
- Lượt pytest đầu: 10.380 passed, 5 failed, 14 skipped, 2 xfailed; giữ log gốc. Thẻ local của vai chưa có nhân vật được thẻ gom cả cuốn thay thế; vai có nhân vật vẫn giữ thẻ local để đổi giọng đúng chương. Sửa khôi phục môi trường của caller sau kiểm setup marker, cập nhật kỳ vọng pin PySide6 đúng `pyproject.toml` hiện hành và cô lập phép quan sát sleep của test tải vào đúng luồng. Không đổi dependency, phiên bản hay ngưỡng.
- Bảy file test đích đầy đủ: 125 passed, 0 failed/error (141,19 s); thêm sáu ca hồi quy môi trường có/không có biến cho thành công, dry-run và lỗi kiểm contract. Test tải riêng trước và sau: mỗi bên 3/3 PASS; đối chứng chèn sleep từ luồng khác làm test cũ đỏ, bản sửa qua, giữ nguyên kiểm Range/checksum/part/retry.
- Lượt full sau sửa: 10.386 passed, 5 failed (HITL), 14 skipped, 2 xfailed. Bản sửa đầu bỏ cả thẻ local có quyền đổi giọng; sửa lại theo ranh giới nhân vật/giọng và thêm ca tích hợp hai phạm vi. Dừng riêng cây tiến trình gate đã bị thay thế, giữ log lỗi, rồi chạy full gate mới từ đầu.
- Gallery phát hiện tám lỗi INK EDGE ở ba story Studio mới. Bù đệm nút đầu hàng bằng utility dùng chung; kiểm lại ba story sáng/tối: 6 lượt, 0 findings, 0 errors; đã xem crop nút liên quan. Không nới luật hoặc miễn story.
- Danh sách khóa đọc trực tiếp từ code: 53 mục; hash trước/sau sửa `a6d8883d7586a7bb93ba4b726022b860ed6f1af3b94699f1b6424177d4006ebf`. Bằng chứng cổng đầy đủ trước/sau sửa, các mục MANUAL chưa ký và giới hạn nằm trong task `scratchpad/codex/gate164b/report.md`; không GPU, thiết bị, commit hay push.

## 07-11-2026 — recovcache (dev/recovery-cache, chưa commit)

- Cache số đo waveform theo SHA-256 WAV và version (hash audio_io, hằng số đo, NumPy/soundfile/libsndfile) trong SQLite project. Mỗi miss commit độc lập; không lưu verdict, không bỏ kiểm băm, validation chữ/settings/drift hay QA. Không thêm migration.
- Bản sao Your Story sugaru_v6: 3.543 dòng, nhánh quét sâu dùng cấu hình hiện hành chung. Trước: lần 1 668,362081 s / mở lại 603,897911 s; sau: cache trống 658,541211 s / cache ấm 104,683375 s. Onset lượt mở lại 3.504 -> 0; số kiểm băm/inspection giữ nguyên. Các lượt chạy nối tiếp, không đồng thời pytest; đây là thời gian recover_project, không phải toàn bộ Pipeline/model startup.
- 0 khác biệt RecoveryReport, 3.510/3.504 inspection, các trạng thái DB ở cả hai lượt và 4.692 runtime events (bỏ thời điểm ghi). Hai model-path mặc định khác do package đối chứng không được recovery dùng; phần settings còn lại bằng nhau. Sách nguồn chỉ đọc; lượt raw settings cũ bị lỗi pace giữ riêng, không dùng để kết luận warm-cache.
- Pytest -q -rf: 33 file đầy đủ, 667 passed / 0 FAILED / 0 errors / 5 skipped, đếm XML; cache mới 15/15 qua, gồm ngắt/reopen. Có 12 warning UnicodeDecodeError ở luồng đọc subprocess; đối chứng HEAD cùng loại trên test_perceptual_prefetch_concurrency: 10/10 qua, 4 warning. Cửa sổ offscreen. Log/XML, lệnh tái hiện, comparison.json và report.md nằm trong scratchpad/codex/recovcache của task.
- Hash trước `3818e7751fec8680b70e3f148d1f0a63ede8de1a6599fad3ab043ff632c5467b`, sau `8944f563a6bd23d845c1eb5dbcb5e7ffdb30e22bc674d1f3a8569ad08892ec9e` (53 file đọc trực tiếp từ code). Hash đổi; chỉ ở nhánh dev, chờ hết run cần hash cũ trước khi tích hợp. Không commit/push.

## 07-11-2026 — flakyhunt (dev/flakyhunt, chưa commit)

- Quét 1.395 file test gốc / 1.398 file sau sửa (pytest, Kotlin JVM, vitest, Qt QML/C++). Bỏ 82 vị trí phụ thuộc thời gian/tài nguyên; helper điều kiện thêm hai lời monotonic có chủ đích. Ratchet theo từng site/call, không dùng ngân sách tổng để đổi chỗ cũ lấy chỗ mới. Cổng listener cố định và cổng bị thả trước khi dùng: máy dò còn 0; 756 ứng viên thời gian khác vẫn được ghi rõ, chưa kết luận cả cây hết flaky.
- Sửa clock/selector giả cho ngân sách mạng; birth time và mtime xác định; handshake bằng event/latch/Future; fake server treo giữ bằng event tới teardown; cổng từ OS giữ suốt test; Gateway cô lập cổng; timer vitest giả và dọn sau mỗi ca. Giữ deadline socket updater 0,5 s, kiểm slot tức thì bằng timeout 0; không nới ngưỡng.
- Đối chứng mã HEAD riêng bằng git archive, 6 lượt/nhóm, 3 test process đồng thời + 2 worker CPU: updater 3/6 hỏng (cả ba sleep-off), Bluetooth 5/6 hỏng, Edge silent 3/6 hỏng. Trash startup còn có bằng chứng 2/6 ở lượt khám phá all-sleep-off. Số stress cũ trong lịch sử không gộp vào lượt này.
- Vòng cuối: pytest 6 × (323 passed / 1 skipped / 0 failed / 0 errors), XML thật và `-rf`; JVM 6 × 85 passed; vitest cache-off/shuffle 6 × 5 passed. Đảo thứ tự file/lớp ở nửa sau; lane Python ngủ thật dùng biến không tồn tại, lane bỏ ngủ đặt 1 (chuỗi 0 cũng bật chế độ bỏ ngủ). Gradle offline chỉ chạy 4 lớp sửa: 64 passed, actual exit 0. Không full release gate/GPU/emulator/GUI; không commit/push.
- Danh sách khoá đọc từ code có 53 mục; hash trước/sau `3818e7751fec8680b70e3f148d1f0a63ede8de1a6599fad3ab043ff632c5467b` không đổi. Chi tiết file:dòng, luật, log/XML, giới hạn và số trước/sau: [report.md](../../report.md).

## 07-11-2026 — rev163fix (dev/rev163fix, chưa commit)

- Đọc trọn review163/report.md và hai probe. Trước sửa: pytest `-rf` có 9 FAILED thật (6 ca warning/bản chụp MP3, 3 ca hoàn tác người kể); slider DOM có 2 failed/2 passed. Test hàng đợi với hook thật cũng đỏ 1 ca khi bỏ serialization.
- Chương warning nghe được dùng chung predicate và đường đánh dấu thu lại với chương completed; bản chụp kịch bản gắn checksum MP3. Xuất xứ đổi giọng người kể nằm trong SQLite cùng transaction đổi câu/reset, hoàn tác giữ người nghĩ ban đầu và sửa từng câu của người nghe.
- React so với ý định vừa gửi, giữ mức cuối qua ACK cũ; các lệnh sửa nhạc cùng cuốn chạy tuần tự ở trình phát, hộp sửa sách và Studio. Qt/Android khóa thanh khi lưu, không có phép so với giá trị đã xác nhận làm nuốt reset; giữ nguyên hành vi này.
- Test đích Python: 200 passed/0 failed; sau bổ sung ca MP3 tổng hợp thật, chạy lại hai file trọng tâm: 30 passed/0 failed (201 test khác nhau giữa hai lượt, không cộng trùng). Ca MP3 kiểm reopen trước khi ghép lại, checksum giữ nguyên và `audio_coverage.project` decode/xuất đủ chương. Có test rollback và retry sau reopen cho cả áp và hoàn tác giọng.
- Vitest đích: 22 passed/0 failed trong 6 file; TypeScript typecheck qua. Android headless/offline, một worker Gradle: 18 tests/0 failures/0 errors/0 skipped trong XML (LevelMeterSaveTest 1, MusicStateTest 9, MusicModelTest 8). Qt offscreen/software: 4 ca control pass, cộng init/cleanup thành 6 passed/0 failed; dùng QML thật, Music singleton chỉ giả hằng số/nhãn, không chạy backend C++.
- Không chạy release gate đầy đủ, model, GPU, emulator hay adb. File sửa đều LF; git diff --check qua; không commit/push. Hash quality trước `3818e7751fec8680b70e3f148d1f0a63ede8de1a6599fad3ab043ff632c5467b`, sau `cf657dee9b3e384188b5d4b4b3992d2e924c066542200ad9e2f9f33113e2b8a2` (53 mục đọc từ code; file khóa đổi: database.py, webui/store.py). Chỉ tích hợp nhánh dev sau khi hết run.

## 07-11-2026 — tnnext2 (cùng dev/tnnext, chưa phát hành)

- Thêm `v.v.`/`v.v` → vân vân và gạch Unicode U+2010..U+2013 nối hậu tố Nhật, tái dùng luật ASCII; không chọn cách đọc tên mới. Python/Kotlin cùng luật; Studio và Edge/Nghe ngay dùng đường chung. Cách đọc riêng của cuốn và protected span vẫn thắng, chữ hiện và mốc Edge giữ nguyên.
- Soát Chap/Vol: kiểm nguyên token trước bước tách dấu, tránh nhận nhầm `Chap.12..5` và `Vol.1...2`; thêm ca mã dính dấu ngập ngừng. Mẫu curated cũ vẫn 547 Chap + 19 Vol, 566 dòng đổi; SHA-256 nguồn khớp báo cáo tnnext.
- Fixture chung 190 → 227 ca, giữ toàn bộ 190 ca trước: thêm 17 ca đổi và 20 ca bảo vệ. Cache 7 → 8 trên cả hai nền; fixture cách đọc riêng chỉ đổi 19 key, các trường khác giữ nguyên.
- Kiểm cuối: pytest **408/408** (27,45 giây), JVM **27/27 methods** (ReadingFormsTest duyệt cả 227 ca), vitest **227/227** gọi backend Python thật; failures/errors/skipped đều 0. Chỉ test đích, không full release gate/GPU, chưa tổng hợp/chấm audio. Tất cả 11 file trong manifest dùng LF, `git diff --check` qua.
- Mẫu Hako `_full` hạt 20261107: 534 file / 276 cuốn / 89.197 dòng / 1.881.652 chữ; truyen 200 cuốn, ai-dich 70, khac 6, tối đa 2 chương/cuốn. `v.v.` 7 lượt/7 cuốn, kính ngữ Unicode 5 lượt/1 cuốn; bật/tắt riêng hai luật đổi tương ứng 7/7 và 5/5 dòng ứng viên. Không cộng với curated vì có thể trùng tác phẩm. 49 lượt dấu chấm số phần lớn lẫn số chương; không dùng tần suất regex làm số lỗi audio. Chữ nguồn được băm lại sau đo, không đổi.
- Hash đầu tnnext2 `3125a1944a0b173d85cc477e273a368a33f33dea007215c74f3f4dded66704f5`, cuối `2afa92af11e76d1f59ec109f33ed89256ee100587c6f26a5b96243b0c297c878`. Đọc danh sách trực tiếp từ code: 53 mục; file khoá đổi là `readaloud/vieneu.py`. Chỉ giữ nhánh dev, chờ hết run trước tích hợp.

## 06-11-2026 — setupmark (dev/setupmark, chưa commit)

- Thêm `scripts/dev_setup_marker.py`: kiểm trực tiếp dependency/provenance, cache perceptual và model giọng từ runtime contract trước khi ghi marker schema 2, `installed_by=dev-check`. Bắt buộc interpreter thuộc runtime đích; ghi atomic, có `--dry-run`.
- Test đích `tests/test_dev_setup_marker.py tests/test_runtime_contract.py`, chạy từ `_internal` với `-q -rf`: 32 passed, 0 failed, 0 errors, 0 skipped (XML thật). Runtime giả dùng file nhỏ, kiểm SHA-256 thật và dependency giả; không dùng GPU.
- Dry-run thật trên `D:/Novels/ABook/_internal/runtime`: exit 0, tất cả phép kiểm đạt; marker cũ giữ nguyên SHA-256 và mtime. Không nạp model/chạy suy luận, không chạy release gate đầy đủ.
- Hash file khoá trước/sau cùng `3818e7751fec8680b70e3f148d1f0a63ede8de1a6599fad3ab043ff632c5467b`. Chi tiết và một lần gọi pytest sai cwd đã sửa: `D:/Novels/ABook_setupmark/report.md`.

## 06-11-2026 — tnnext (dev/tnnext, chưa commit)

- Chuẩn hoá nhãn Chap/Vol đi với số thành chương/tập, dùng chung Studio, VieNeu và Edge; Python/Kotlin cùng luật, giữ nguồn và mốc chữ. Cache 6 → 7; chỉ cập nhật 19 key trong fixture cách đọc riêng.
- Fixture chung reading_forms.json 146 → 190 ca tự viết, giữ nguyên 146 ca cũ. Có 20 ca đổi và 24 ca bảo vệ mới; kiểm listener readings thắng và ánh xạ một chữ hiện thành hai chữ đọc.
- Chỉ chạy test đích: pytest `-rf` 368/368, FAILED/errors/skipped = 0; JVM 25/25 methods trong ReadingFormsTest/ReadingMarksTest/SpokenTextTest/ReadingsTest (ReadingFormsTest còn duyệt cả 190 ca); vitest readingForms.test.ts 190/190 gọi backend Python thật. Không full suite/release gate/GPU.
- Corpus chỉ đọc: 637 file / 30 LN Nhật / 174.217 dòng / 3.722.710 chữ; Chap+số 547 lượt, Vol+số 19, 566 dòng đổi. Mẫu cố định không cân bằng, 542 lượt Chap ở một cuốn; không suy rộng tỉ lệ lỗi/audio. Normalizer CPU xác nhận hai câu tự viết; chưa tổng hợp hay chấm audio.
- Đọc danh sách khoá từ code: 53 mục. Hash trước `3818e7751fec8680b70e3f148d1f0a63ede8de1a6599fad3ab043ff632c5467b`, sau `3125a1944a0b173d85cc477e273a368a33f33dea007215c74f3f4dded66704f5`. Chỉ nhánh dev, chờ hết run trước tích hợp. Lệnh, số đếm, lỗi trung gian đã sửa và giới hạn nằm ở `D:/Novels/ABook_tnnext/report.md`.
## 07-11-2026 — Qt startup (dev/perfaudit, chưa commit)

- Năm nhóm hộp thao tác sách chỉ được dựng đồng bộ ở lần dùng đầu; giữ instance và request sau khi đóng. Thư viện toàn sách đủ audio không liệt kê giọng; sách chữ, sách có chương chỉ-chữ/thiếu audio, trang sách mở trực tiếp và Cài đặt vẫn tải danh sách, giữ giọng mặc định và gộp request đang tải.
- QML liên quan: 55 hàm test, 61 mục JUnit gồm init/cleanup (Main 12, Voice 27, Settings 22), 0 failures/errors/skips. Test mới kiểm nạp hộp, mở lại cùng instance, lưu nhanh, không hỏi giọng ở thư viện audio, hỏi giọng cho sách chữ/Cài đặt và giữ lựa chọn giọng. Các cửa sổ dùng offscreen trên desktop riêng; guard 0 foreground events.
- Python startup/host: 8 passed, 0 failures/errors/skips. Không full release gate, không model/GPU, không đổi Android. Kết quả benchmark và protocol được ghi riêng trong report của task.
- Hash khoá trước/sau lượt này giữ `88cef8f94e9e98907298d8252ccba68e253956bdbc2a503617686673abdb0d94` (53 mục đọc từ code); nhánh đã có thay đổi file khoá ở đợt tối ưu import trước đó, chỉ dùng ở dev.
## 07-11-2026 — Android startup (dev/perfandroid, chưa commit)

- WorkManager khởi tạo khi `getInstance(context)` đầu tiên thay cho ContentProvider; giữ cấu hình mặc định và các initializer khác. Worker thật kiểm trên AVD riêng không mở Activity: 1 test / 0 failure / 0 error.
- Đồng bộ catalogue không đọc Thư viện thêm lần nữa sau khi nguồn đã công bố; lỗi nguồn vẫn làm mới phần đã ghi. Polling thiết bị/Studio đợi callback first-content hiện có. Không sửa UI, thang hoạt ảnh, điều kiện splash hoặc mốc reportFullyDrawn.
- JVM/Robolectric đích: 105 tests / 0 failures / 0 errors / 0 skipped, gồm LibraryMembership, DevicesState, NativeActivityLinks, LibraryScreen, ShellRoutes, SettingsData, PlayerRepo, NativeDevicesFlow, TabHost, MotionScan. Hai hồi quy DevicesState kiểm nguồn tự công bố và lỗi giữa chừng/giữ một lượt đồng bộ.
- Macrobenchmark cold startup: >=10 Perfetto trace mỗi APK/thay đổi trên cùng AVD 2 vCPU/1536 MiB, SwiftShader CPU, không cửa sổ, adb riêng cổng 5038, package com.ngdtuanh.abook.perfaudit. Profile bổ sung graph startup thật, hợp với coverage UI cũ; generator 1/1 pass. Số startup từng lượt, RAM PSS sau thư viện/phát MP3 60 s, đối chứng APK gốc và thử nghiệm loại bỏ: D:/Novels/ABook_perfandroid/report.md cùng perfandroid_evidence. Không suy số emulator thành điện thoại thật.
- Không release gate đầy đủ, không GPU host, không chạm điện thoại thật/package sản phẩm hoặc `_internal/abook/`.

## 06-11-2026 — tnbig (dev/tn-bigint, chưa commit)

- Python/Kotlin nhóm số liền từ 7 chữ số có ngữ cảnh lượng; sửa gốc luật nghìn kiểu Anh để không sinh số dài liền, kèm dấu ~ và dấu chấm cuối câu. Cache 5 → 6; cập nhật 19 khoá fixture cache. Fixture chung 146 ca: thêm 46 câu bịa, đổi 1 ca cũ `thousands-2`; 99 ca cũ giữ nguyên. Hai kỳ vọng trùng của số sinh từ bỏ phẩy trong test Python/Kotlin được đổi tương ứng.
- Pytest -q -rf một lượt đầy đủ mới, 55 file importer/consumer: 2226 passed / 8 skipped / 0 failed / 0 errors, đếm XML thật; có 1 cảnh báo thread máy chủ test timeout. Vitest reading forms: 146 passed. Android tập trung lượt cuối: 45 passed / 0 failed, gồm 22 test bắt buộc, kiểm regex Android, ca bỏ phẩy và 21 test FastConnect.
- JVM đầy đủ lượt cuối: 3.350 tests = 3.335 passed / 8 failed / 7 skipped. Sáu lỗi nền đã được Lead cho bỏ qua (đã sửa ở dev/merge-163, 92d489163); hai lỗi TLS/SNI của FastConnect không tái hiện trong lượt chạy riêng cả lớp (21/21 qua). Không khẳng định full suite xanh.
- Mẫu riêng đúng tn-tier25: 349 chương / 186 cuốn / 61.678 đoạn, 0 số liền từ 7 chữ số, 0 dòng đổi. Đọc trực tiếp 11 + 12 file nguồn Sugaru, khớp SHA-256 23/23; 3.016 + 2.592 dòng nội dung, 0 số dài liền thô. Một số lượng 9 chữ số do bỏ phẩy sinh ra đã sửa; đọc kiểm riêng 1/1 dòng đổi, sea-g2p 0.9.1 xác nhận cách đọc hàng triệu. Không tổng hợp hay chấm audio.
- compileall và git diff --check qua. Hash trước task `6e1970d021c22a6d1ece64cc582bde90c7a15369c18de09d09c74598a9abd198`, sau `0cf564b70ce299b3777f7c5285a07237042cbb88da91145509fd886509c9d8e2`: thay đổi, chỉ nhánh dev, chờ hết run trước khi tích hợp.

## 06-11-2026 — metaupd (dev/metaupd, chưa commit)

- Gói có audio luôn đối chiếu lớp nền khi nhập lại, kể cả caller truyền cờ giữ nền; Android và bộ nhập Python dùng chung cho web/Qt cùng luật. Giữ nguyên hồ sơ nghe và lớp sửa; file giống hệt vẫn là existing.
- Android tập trung: 67/67 pass. Toàn bộ: 3351 test trong 385 XML suite, 3338 pass / 6 fail / 7 skip, 0 error. Sáu lỗi nằm ở ký hiệu đọc, nhãn phân vai và luật icon/chuyển cảnh/dấu chấm; không tuyên bố toàn bộ xanh.
- Python: 253/255 pass, chỉ 2 tài liệu parity lệch sẵn (render HEAD bằng render sau sửa); thêm 5/5 ca API lớp nền pass. Web import + reading forms: 105/105 pass khi chỉ định đúng Python. Full Vitest còn 3 AbortError của MusicLevelSlider; typecheck có 5 lỗi ở test không đổi.
- Bằng chứng, lệnh chạy, XML đầy đủ và giới hạn: D:/Novels/ABook_metaupd/report.md. Quality implementation hash trước/sau không đổi.

## 06-11-2026 — sửa cổng phát hành 0.4.163 (gatefix, dev/merge-163, chưa commit)

- Bản chỉ nghe không kéo thư viện Studio khi khởi động hoặc kiểm file sách: kiểm audio coverage dùng giải mã FFmpeg toàn bộ, lấy thời lượng từ byte đã giải mã, giữ đối chiếu mã băm/phụ đề. Bài hồi quy gói MP3 thật chạy trong tiến trình chặn cả NumPy và soundfile PASS; 90 bài bookfile/export/coverage hiện có PASS. Không sửa file thuộc `QUALITY_IMPLEMENTATION_FILES`; hash trước/sau cùng `6e1970d021c22a6d1ece64cc582bde90c7a15369c18de09d09c74598a9abd198`.
- Hai bài kiểm ngoại lệ của ứng viên giữ DB bằng chứng thật và dùng settings harness hiện hành, không mở settings pace cũ qua bộ nạp project mới. Danh sách pin startup khớp việc gỡ WORLD/Praat; fixture trang giọng Qt dùng người kể Đức Trí hiện hành. Startup/gate unit: 49 PASS; Qt D2Voice offscreen: 27 PASS.
- Android: nét slider qua bộ vẽ control chung, giữ nguyên luật/danh sách kiểm icon; nhãn mức nhạc chuyển cả hình và độ mờ; mô tả đo giọng dùng bộ nối dấu chấm chung. Kỳ vọng đọc dấu ngoặc sau số khớp chuẩn Python; nhãn preset không mang thông tin chỉnh giọng đã bỏ. Sáu nhóm lỗi Android ban đầu: 59 PASS; nhóm vẽ/chuyển động/xuống dòng PASS lại sau khi gom nét slider. FastConnect riêng: 21 PASS.
- Gate dùng interpreter đang chạy cho bài hợp đồng Python trong bản sao UI; giữ đầu vào QML tương đối và khai báo Node của tác vụ toast. Bài chuyển cảnh thư viện điều khiển thời gian thoát hàng trước khi kiểm ảnh inert, giữ nguyên assertion. Gate UI mới: typecheck PASS, Vitest 2656 PASS/0 lỗi/0 bỏ qua, DOM inventory 75/75. Chạy lại hai script parity sau khi tác vụ toast hoàn tất.
- Khôi phục toàn bộ ghi chú 0.4.163 về `[Chưa phát hành]` trước bước cắt phát hành. Lượt full chẩn đoán `runtime/release_gate/0.4.163-20261106T074235093633Z` có 10.127 pytest PASS, một fixture nối chữ rác vào MP3 bị bộ giải mã từ chối. Fixture nay tạo master MP3 thật có tín hiệu đổi, giữ nguyên kiểm checksum/gói cập nhật; 97 bài đóng gói/coverage/export PASS. Lượt full cuối và kết quả từng check được ghi riêng trong `report.md` của task gatefix. Không commit, không chạy model/điện thoại.

## 06-11-2026 — toast không che lớp nổi (toastcover, dev/merge-163, chưa commit)

- Cả 7 gate yêu cầu và 2 bước build phụ thuộc PASS trong `runtime/release_gate/0.4.163-20261106T065613508294Z.json`: tap 21/21, đối chứng âm bắt đủ 21 lỗi cấy, gallery 188 trạng thái sáng/tối, 3.232/3.232 lượt hình học trên 94 màn, 0 vi phạm/lỗi. Audit toast đo 2.501 khung chuyển động, không che điều khiển lần nào.
- Web và Qt đặt toast dưới mặt điều khiển của mọi lớp nổi, giữ nguyên chuyển động; web tiếp tục dịch ra vùng trống và mờ dần khi thiếu chỗ. Android đã giữ lời báo trong dòng chảy, dưới SheetLayer; không sửa production Android.
- Tap audit tạo toast thật trước mỗi bước mở lớp và kiểm chạm từng khung; gallery kiểm thứ tự lớp ngay cả khi toaster rỗng. Danh sách đầy đủ nơi dùng nằm trong `report.md` của task toastcover; DESIGN và hai tài liệu UI_PARITY đã cập nhật/sinh lại.
- Typecheck PASS; Vitest 2.656 passed, 0 failed/skipped; hai gate parity PASS. Python audit/release-gate: 61 passed. Qt ModalLayer 140 + D3Main 9 passed (145 bài thử + 4 init/cleanup), 0 failed/skipped; cửa sổ offscreen. Android liên quan: 72 passed trong 5 suite (NowPlayingUi, BookNotes, ScrimRules, InsetSurfaceRules, BottomInsetScan), 0 failed/skipped.
- Lượt Android toàn bộ bổ sung: 3.335 passed, 8 failed, 7 skipped; lỗi ngoài phạm vi ở FastConnect (2), Symbols, ListenExtras, IconRules, MotionScan, TextWrapRules, ReadingMarks. Lượt UI rộng: 1.367 passed, 4 lỗi nền tương ứng, không gộp vào số 72 của lượt liên quan.
- Hash audio trước/sau giữ `6e1970d021c22a6d1ece64cc582bde90c7a15369c18de09d09c74598a9abd198`; không sửa `_internal/abook/`, không commit. Build web của gate ghi vào thư mục riêng; workspace gate có nguồn Qt để test đọc được VoiceLogic.

## 06-11-2026 — master cố định, kiểm lại hai sách (dev/merge-163, chưa commit)

- Bỏ loudnorm lượt hai và giới hạn gain riêng từng chương trong harness. Mọi chương/mọi sách nhận +5 dB chọn từ hiệu chuẩn (median danh định -20,574 LUFS), sau đó alimiter true-peak oversample 4 lần, không auto-level. Báo cáo phần thời gian envelope bị hạ và mức hạ lớn nhất. LUFS chương chỉ chẩn đoán; giữ gate peak/clipping/dropout/mối nối.
- Dựng lại 23/23 MP3, script và word timing tại `D:/Novels/LLM_Train/ys_redo/novar/<project>_master/`; giữ WAV nguồn và hash DB/settings/WAV khớp trước/sau. Your Story PASS: trải giọng 0,414311 phon (CI 0,253059..0,879232), trải chương 0,481324 (CI 0,382023..0,933303). Pain PASS: 0,876323 (CI 0,564354..1,361752), trải chương 0,825747 (CI 0,579211..1,270285). Không chương nào vượt +/-1 phon; ngưỡng giọng đủ >=12 câu vẫn <=1,5 phon. Đây là đo lại MP3, không trừ số học từ kết quả cũ, không fit bằng sách.
- Sau cả hai PASS: gỡ kế hoạch target chương, bù mức theo sách, vòng master lại, cache nền, journal công bố và test của vòng kín. Một detector ghi `output/reports/levelQa.json`, chỉ cảnh báo; checksum MP3 và mốc câu/giọng giữ phép đo khi resume. Receipt `.mp3.levels.json` chỉ giữ hash và mốc câu, không chứa gain bù.
- Pytest `-q -rf`: ban đầu 343 file, 6169 passed / 0 failed / 9 skipped; sau gỡ vòng kín 144 file, 3004 passed / 0 failed / 6 skipped; chạy mới 14 importer quality_policy sau cập nhật nhãn thuật toán: 909 passed / 0 failed / 0 skipped. Hồi quy tập trung sau gỡ: 98 passed. Kết quả toàn file mới nhất, không cộng trùng rerun, bỏ file test đã gỡ: 6489 passed / 0 failed / 10 skipped. Log/XML và bảng từng chương/giọng ở task vtable4. Compileall, git diff --check và grep symbol vòng kín qua. Không đổi bảng/r; không tổng hợp/GPU/build trong lượt này.
- Đọc danh sách khoá từ code: 54 -> 53 mục (gỡ chapter_loudness.py). Hash trước: `5fa8bf6da65f57e16d3799e5ed35dbf30fdc2609b9538141cbe58396c59ca985`; sau: `26e20236a163a25a0761a043f8b76c8225a158591f5d3578fba936a9647bd0ad`. Mọi sửa còn ở dev, chưa commit; không chạm production hay dừng guard/pause.

## 06-11-2026 — cân bằng preset, bỏ biến đổi giọng (dev/merge-163, chưa commit)

- Mỗi preset một giọng; bỏ pitch/formant, gain theo tuổi/cảm xúc/volume/người kể và bù nghỉ cảm xúc/lời dẫn thoại. Giữ WSOLA, nghỉ cấu trúc và các trần an toàn. Hằng số ISO từ 36 giọng × 40 câu trung tính × hai seed; Nghe ngay 34 giọng Turbo/Nano dùng cùng số Python/Kotlin, không đo Mai Anh.
- Importer `-q -rf`: lượt rộng 6.109 passed / 11 failed / 9 skipped; sửa và chạy lại toàn file. Kết quả mới nhất theo module: 6.145 passed / 9 skipped / 0 failed; lượt hồi quy cuối 252 passed, kiểm bảng cuối 147 passed / 3 skipped. Log/XML và quy tắc gộp nằm trong task vtable3, không cộng trùng rerun. Android biên dịch production/test Kotlin qua; 19 test gain/clip/WAV passed, 0 failure/error. Compileall và git diff --check qua.
- Sách chỉ là dữ liệu kiểm định, đang chờ novar/DONE; chưa có PASS/FAIL sách, chưa gỡ vòng hiệu chỉnh. Gain không được fit bằng sách. Hash trước lần tiếp nhận bỏ nghỉ: 53c26fe9862a5999262b26741c2882c4b653c4c148ecef25da7a0d06aa2334a6; sau: 5fa8bf6da65f57e16d3799e5ed35dbf30fdc2609b9538141cbe58396c59ca985. Mọi sửa ở nhánh dev; không chạm runtime sản xuất.

## 06-11-2026 — keepline (dev/keep-line, chưa commit)

- Lời đọc được chuẩn bị một lần cùng span; test sinh bảng phát âm kiểm idempotence của hàng đã chuẩn bị và ranh giới chia câu.
- Giữ take có tiếng qua từ chối mềm, writer thật từ chối trước khi ghi, crash/retry và nhánh normal; im lặng/NaN/audio không giải mã được không thay lời đọc.
- Detector xuyên SQLite/WAV/MP3: dòng failed vẫn có chương cảnh báo, thiếu audio chỉ rõ dòng; phá bảng chương/băm/phụ đề/giải mã/nhãn QA phải bị bắt. Đưa file detector vào cổng phát hành trong `RELEASING.md`.
- Xuất mặc định cần đủ chương; partial ghi N/M và tên thiếu trong manifest/CLI/UI web và Qt. Fixture đóng gói dùng MP3 thật và checkpoint băm tương ứng; fixture sách dở yêu cầu partial rõ ràng.
- TypeScript typecheck và 16 test UI nhập các module đổi qua; parity web/Qt `--check` qua. Qt Studio5 offscreen/software: 67 kiểm tra qua; test partial mới 3/3 gồm init/cleanup.
- Bộ Python rộng 248 file `-q -rf --tb=short` và các lượt sửa/rerun được ghi log/XML tại thư mục task; kết quả cuối và số `FAILED` thực ghi trong `report.md`/`keepline_test_summary.json`.
- Lượt rộng: 4.981 testcase, 19 FAILED raw; sau sửa và chạy lại chung chín file từng lỗi: 221/221 passed, 0 FAILED. Detector cuối 29/29; tổng hợp kết quả testcase mới nhất 4.976 passed, 6 skipped, 1 xfailed, 0 failed. Ba test inspect được chạy lại nguyên file sau khi số dòng code ổn định, không nới assertion.
- Pace chỉ đo trên hai SQLite đã sao chép, không mở gốc/đổi ngưỡng. Sàn kép chạm 0/3.691 dòng plain, 0/736 foreign-name, 0/61 number-heavy đủ điều kiện; chỉ đánh giá take còn lưu.

## 06-11-2026 — Studio: Gọi hay nói (dev/caller-card)

- Pure vocative detector uses character names/aliases, titles, call particles and reply pairs; synthetic fixtures only. The card offers up to three alternative named speakers plus narrator/unnamed, plays existing recorded/preset samples, uses the existing speaker override path and appears in precast step (c).
- Read-only gold measurement: 95 chapters, 40 book folders; precision 498/503, conditional mention-pair recall 498/1007. These are development-set results using gold identities, not deployed-model precision or independent held-out results.
- Pytest: 94 files, 1,731 passed / 3 skipped / 1,734 cases; 0 FAILED lines, 0 F, 0 E in real `-q -rf` output, matched against per-file XML. Includes all 68 test files with direct imports of changed Python modules; caller detector/card 36, existing self-addressed card 4, work_items 32, work_items_at_scale 9, work_items_speaker_suggestions 10, UI parity 17 and Qt parity 11.
- Studio + motion vitest: 374/374 passed across 70 files, 0 failures. Earlier whole-UI run had 26 environment failures from the junction's missing lucide EighthNote export in music/gallery. Gradle: WorkLogicTest 25 and StudioWorkScreenTest 13, 0 failures/errors; XML newer than the saved run start. Both parity scripts `--check` and `git diff --check` passed. No screenshot or visual verification.
- Locked list read from code: 42 entries; before/after hash `f10085f96acd7f9fe6a066f2bf5a74338b0a351bea3d98f58f6d2807912cbfff`. CUDA disabled, Qt offscreen, CPU checks BelowNormal; no Ollama, device/emulator, commit or push. Per-file counts, raw logs/XML and measurement script are in the caller task scratchpad.

## 05-11-2026 — release gate, milestone 2 (dev/release-gate)

- `scripts/release_gate.py` chạy các cổng nguồn với timeout, đọc summary pytest/Vitest, XML Gradle mới và đủ suite Qt offscreen; lưu bảng/JSON/log tại `runtime/release_gate`. Kiểm tra cần người/thiết bị hiện MANUAL và chặn exit 0. `release.py publish` gọi cổng trước mọi thao tác đăng.
- Tự kiểm: fake runner exit 0 nhưng có failed/error, output rỗng, timeout, all-pass exit 0, thiếu công cụ, dependency đỏ, XML sai, từ cấm, CRLF và dữ liệu riêng; publish không được đi tiếp khi gate đỏ. Fixture summary pytest chạy thật tại worktree này và dòng Vitest từ báo cáo a90a có ghi nguồn.
- Kết quả tự kiểm, bảng chạy thật toàn bộ và fault injection được ghi đầy đủ ở `result.md` của task; không sửa lỗi nền, không commit, không dùng GPU/Ollama/adb/thiết bị. Hash file khoá đọc từ code, trước sửa `f10085f96acd7f9fe6a066f2bf5a74338b0a351bea3d98f58f6d2807912cbfff`.
- Kết quả cuối: 50 bài tự kiểm passed; full gate exit 1 (14 PASS, 10 FAIL, 5 MANUAL). Android: 3303 passed/7 skipped, 377 suite, 0 failed/error. Qt sau sửa harness: 523 passed/0 failed từ 15 suite, QML lint qua; WidthTests timeout 360 giây/thiếu summary. Full pytest timeout 2400 giây trước summary; Vitest thiếu module, UI/gallery build thiếu export EighthNote từ dependency ở junction. Cheap checks exit 0; fault injection exit 1. Hash sau kiểm vẫn bằng trước sửa.

## 05-11-2026 — TN tầng 5 và vá tầng 2 (dev/tn-tier25)

- Fixture chung `tests/fixtures/readaloud/spoken/reading_forms.json`: 100 ca, gồm 39 ca bảo vệ cách đọc / không đoán thêm (25 chuỗi giữ nguyên). Python kiểm Nghe ngay, Studio và Edge; vitest gọi backend Python thật, không thêm bộ luật TypeScript; JVM kiểm VieNeu và Edge.
- Pytest `-q -rf`: 24 file nhập các mô-đun đổi và phần Studio / cache liên quan, 954 passed, 3 skipped, 0 FAILED / errors; đếm trực tiếp 954 dấu chấm, 3 `s`, 0 `F` / `E`, khớp JUnit XML. Vitest: 100 passed, 0 failed. Android `:app:testDebugUnitTest --tests <class>`: 15 lớp, 133 tests (132 passed, 1 skipped), 0 failures / errors; chỉ đếm XML mới hơn lúc bắt đầu Gradle.
- Corpus chỉ đọc: 349 chương / 186 cuốn, 61.678 đoạn / 1.423.904 chữ. Cách đọc khác chữ gốc trước/sau: 6.138 / 9.756 đoạn; 4.175 đoạn đổi trực tiếp. 4.458/105.700 khoảng câu gốc đổi; theo lớp: ngập ngừng 2.714, mở đầu 1.674, kéo giọng 104, nghìn mơ hồ 1 (có giao nhau). Đọc tay 40/40 đạt theo luật; chưa tổng hợp hay chấm audio. Phương pháp và phân tầng ở `TEXT_NORMALIZATION.md` mục 4; không đưa chữ truyện vào repo.
- Cache luật đọc Python/Kotlin tăng 4 → 5, cập nhật fixture khoá cache. Không đổi chữ truyện / giao diện; không cần chạy `ui_parity.py`. Kiểm thử CPU, BelowNormal, offscreen; không dùng GPU, Ollama, adb, phone hay emulator; không commit / push.
- Hash trước task: `f10085f96acd7f9fe6a066f2bf5a74338b0a351bea3d98f58f6d2807912cbfff`; trước continuation: `6ce5ef4db5001e0acca1c686abb303f28e4c37a7de0220d15522111036f9ef52`; sau: `596c6b95d593a6200fb5fc56e3213135596f0d112995f6b589ed5222056ef476`. Các thay đổi vẫn ở nhánh dev, chưa tích hợp vào run đang thu.

## 05-11-2026 — pinfix2: Bluetooth choices follow advertised services

- `paired_devices` now queries both ABook UUIDs through the existing SDP path and returns per-device `services` (release/dev). Both desktop UIs keep the ordinary release choice and show `<name> · bản thử` only when the corresponding service is actually advertised; dev-only phones have no release pairing choice. Fixture-only listing, React component and existing Qt D2Devices tests cover release-only, dev-only, both and neither.
- Exact previous 119-file pytest selection, `-q -rf`: **1259 passed, 3 skipped, 0 FAILED**, 356.61 s; 0 actual FAILED summary lines in `measurements/pinfix2-pytest-all.log`. Same six Kotlin classes rerun: **46 passed**, 0 failures/errors/skips (PeerEndpoints 2, StudioLink 4, LibraryServerBluetoothName 2, LibraryServerDiagnostics 3, PeerAddresses 13, DevicesLogic 22). Full Vitest: **2513 passed / 310 files**; tsc and compileall pass. Qt D2Devices: **25 passed**, including init/cleanup; glyph audit has 0 hits/leaks.
- Earlier pinfix evidence did not record parity validation. Both parity checks initially found stale generated reports. Regenerated both exclusively through their scripts; both `--check` commands now pass and `tests/test_ui_parity*.py` gives **28 passed**.
- Quality implementation list read from code: 42 entries. Before/after this follow-up: `4f9fe74290a4c180b5cf30dd11c5e95b4d6f6c10297a515d11c17ceb23173ab4`. LF verified; git diff --check passes. No commit or real Bluetooth/phone/GPU/Ollama use. Full follow-up report: task `result.md` and worktree `result2.md`; evidence: `measurements/pinfix2-*`.

## 05-11-2026 — pin narrator exclusion and Android dev endpoints (dev/pin-narrator-port)

- Pins now pass the same narrator-preset exclusion as ordinary casting, including continuation, named/local/anonymous characters, silent reservations, direct pin writes and listener requests. Both narrator mutation paths use one transaction that re-casts conflicting holders and updates their pins/recording state. Listener explicit character requests still refuse narration presets; existing narrator-picker occupancy protection remains.
- Android release keeps TCP 47630, UDP 47631 and UUID a1f667fe-352a-49b7-9b91-a5463677cac0. Debug uses TCP 47640, UDP 47641 and UUID b2e7780f-463b-5ac8-ac02-b6574788dbd1, generated from the same JSON source Python reads. Discovery probes both; labelled desktop Bluetooth dev pairing and separate gateway identity retain the selected app through fallback and diagnostics.
- Final validation: 1255 pytest passed, 3 skipped, 0 FAILED across 119 files; final focused routing/pin reruns passed (94 / 8 tests). JVM: 46 tests passed (PeerEndpointsTest, StudioLinkTest, LibraryServerBluetoothNameTest, LibraryServerDiagnosticsTest, PeerAddressesTest, DevicesLogicTest); generated release BuildConfig inspected. TypeScript typecheck and 5 computerRoutes vitests passed. Evidence is in the task's `result.md` and `measurements/`.
- No phone/adb or commit. Quality implementation list read from code (42 entries); policy hash changes, confined to the uncommitted dev worktree. Test fixtures were corrected to use matching voice presets and to forward the selected service UUID without permitting real Bluetooth.

## 05-11-2026 — thanh trượt mức nhạc nền (dev/music-slider)

- Shared `music_mix.json`: −40..−6 dB, step 1, default −20; Python, TypeScript, generated Android BuildConfig and Qt CMake read one source. Zone/number/clamp tests read the shared settings fixture.
- Python core: settings ranges 4, music plan 19, music mix 25, book edits 231 passed. Final parity: 28 dots, F=0, E=0; both parity scripts `--check` passed. Initial three stale-doc/radius failures resolved.
- Vitest: musicLevels 6, MusicLevelSlider DOM 2, sheetRows 7, projectMusicMenu 4, playerMusic 9, musicBed 97 = 125 passed / 0 failed; browser-port helper 6 passed. Typecheck passed with read-only rel437 dependencies (the existing node_modules junction lacks Vitest and has stale icons).
- Android XML newer than 20:22:35 +07: BookEdits 24, MusicModel 8, MusicScreen 11, NowPlayingUi 59, MusicBedIntegration 25, SceneMusic 13 = 140 passed / 0 failures/errors. No device/emulator.
- Chromium software rendering: six real page/theme cases pass thumb `elementFromPoint`, drag to −6 with no save until release, exactly one save on release and ArrowLeft to −7. Six full screenshots + six crops viewed at native 2×; six Android Robolectric snapshots refreshed, level crops viewed at native 3×; no overlap.
- Qt build/test validation is in progress; final counts follow here.
- Quality implementation hash unchanged: `f10085f96acd7f9fe6a066f2bf5a74338b0a351bea3d98f58f6d2807912cbfff` (42 entries read from code). No commit/push, GPU, Ollama, phone or emulator.

## 03-11-2026 — unchanged-audio cover re-import (dev/cover-reimport)

- Android and desktop `.abook` imports now compare the base book layer even when audio is identical, then stage and swap changed metadata/assets while reusing unchanged audio. Cover addition, replacement, metadata-only updates and removal preserve listener title/cover precedence. Local sidecars/workshop survive listening-package refreshes. Desktop cover metadata is staged with the image. Repeating an EPUB/TXT selection retains its existing behavior.
- Regression tests exercise cover-only changes, book.json-only changes, scripts, cover removal with/without a listener cover, audio reuse and corrupt-update rollback. Android `BookFileImportTest`: 38 tests, 0 failures. Python bookfile/import/edits/text/project suites: 421 tests, 0 failures/errors/skips. Explicitly restore production files to HEAD with the regression tests retained: Android 38 tests / 2 failures; Python 3 tests / 3 failures. Restore fixes: pass.
- Locked-file list read from code: 41 entries. Hash before/after: `c95fac04433a97e3b6a8c701514891b85718df8829d73313b7cd742dfb5fc9b8`. No phone/emulator, commit, push or process termination.

## 02-11-2026 — thanh tiêu đề Windows và hai test Android chập chờn (dev/m1-chrome)

- `tst_titlebar.qml` (WidthTests, Main.qml thật + WindowChrome giả có nhớ lời gọi): dải cao 40, sát mép trên và rộng bằng cửa sổ, không nền riêng (điểm ảnh trên thanh bên, nội dung và ngay dưới dải cùng màu), ba nút 46 x 40 sát nhau ở mép phải, nét tự vẽ ở giữa nút (gạch Thu nhỏ đúng 10 cột, 1 hàng, Shape chứ không chữ/ảnh), nút thu / mở thanh bên lọt trong dải, nền Đóng #C42B1C rê / #A82419 nhấn và chữ trắng, nền hai nút kia 6 % / 10 % màu chữ, cửa sổ mất tiêu điểm thì nét nhạt, phóng to đổi nét. 15 phép phá (mut1.json) đều đỏ.
- `test_windowchrome.cpp` (`WindowChromeTests`, vào `build.bat`): dải là vùng kéo, ba nút là nút hệ thống, chỉ mục khai bằng `keepClickable` bấm được, mini bỏ vùng kéo và trả lại, `cursorInside` đo con trỏ ảo (offscreen) theo toạ độ màn hình. 7 phép phá đều đỏ.
- `FastConnectTest` / `EdgePiecesTest` chập chờn khi máy bận: gốc là giả định thời gian trong test (bước so le 50-250 ms so với độ trễ chạy luồng, giấc ngủ 250 ms để các mảnh "kịp mở cùng lúc", đếm ổ cắm theo số mảnh dù mảnh chưa kịp mở ổ cắm), không phải mã app. Lặp riêng từng lớp trong JVM mới dưới 64 luồng ngốn CPU + 8 JVM song song: trước 22/48 và 43/48 lượt hỏng, sau 0/48 và 0/48; ở 128 luồng ngốn CPU + 12 JVM sau là 0/96 và 0/96.

## 02-11-2026 — parity trong build và hình học Đang nghe (dev/m1-gates)

- `desktop_qt/tools/qt_pytests.py` đưa máy dò Android–web `tests/test_ui_parity.py` vào PARITY; test mới kiểm danh sách, đầu vào pytest thực tế và lời gọi từ `build.bat`. Nhóm pytest parity/build/fixed-waits: 50 passed, 0 failed.
- `tst_nowplaying_geometry.qml`: đo khung mở đầu từ PlayerBar thật (sai số 2 px), khung kết thúc, vị trí/cỡ bìa và hàng điều khiển khi mở/đóng tốc độ, hẹn giờ, ở khổ 792 và 1200 px. Chạy riêng bằng WidthTests.exe có sẵn của ABook_qtsink, nhập QML từ cây này, offscreen/phần mềm/BelowNormal: 8 passed (6 ca dữ liệu + init/cleanup), 0 failed.
- Web `nowPlayingOpen.dom.test.tsx`: thêm 6 ca cấu trúc cho tốc độ/hẹn giờ/chương, kiểm Portal ngoài root, `fixed`, lớp/style/khoảng cách của vùng cuộn và luật CSS theo trạng thái. Cả file 10 passed; TypeScript noEmit thành công. DOM giả không chứng minh hình học trình duyệt thật.
- Kiểm lực trên mã thật rồi khôi phục: bỏ mục PARITY; đổi điểm đầu/cuối hiệu ứng; dịch/co bìa và hàng điều khiển; bỏ Portal/đổi fixed; thêm padding/margin theo trạng thái tấm. Mọi ca tương ứng đều đỏ. Không chạy build.bat, GPU, Ollama, emulator hoặc adb; không sửa `_internal/abook/`, không commit.

## 27-10-2026 - Qt desktop integration (dev/desk-qt-int)

- Integrate hidden -> cpu -> smtc without commits. Keep WASAPI-only music, MF voice retirement/event filtering, vblank default, tray/mini and Windows media card. All-window music scheduling covers both the reused main/mini window and a late separate mini.
- Real mini QML buttons, tray model and actual MediaControls adapter share Player in a new integration test; SMTC/tray commands update the mini in return. Tray chapter availability matches SMTC, including the last chapter.
- Full build/test/deploy exit 0, every suite offscreen: **579 passed**, 0 failed/skipped (MediaControls 6, DesktopApi 12, Player 33, ReadAlong 14, Music 38, Mix 73, MusicWindowActivity 4, SkipGlyph 6, Sidebar 117, Width/mini/D3 276). Parity pytest: **8 passed**. Initial D3Main setup failure from the missing Bench.note stub is fixed; focused 7/7 and full 276/276 reruns pass, original failure log retained.
- One native separate-desktop hidden-playback run, foreground guard installed before app resume: **120.027 s media in 120.029731 s hidden**, >=118 s passes. Music mixer and SMTC enabled, mixer ready/playing, no mixer/SMTC errors, 0 foreground events, normal exit 0. Launcher excludes its own venv ancestry from the shared-machine wait.
- Hash before/after: `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`. Conflict decisions and evidence locations: root `report.md`; raw evidence under `desktop_qt/build/hidden-evidence/` in this worktree.

## 27-10-2026 - hidden playback clock, uncommitted

- Native Windows QPA on a separate desktop, foreground guard installed before process resume. Three runs each: original MF music advanced 110.821/110.831/110.739 s in 120 s hidden; music off 120.023/120.015/120.029 s; merged retire 114.254/114.606/114.217 s. Timestamps locate MF music teardown stalls; moving teardown alone is insufficient.
- Integrate the playback/decoder/test subset of committed music follow-up `3a04cbde`: music only through WASAPI, narration stays MF. The unchanged WAV fixture now advances 120.017/120.014/120.013 s in 120.020/120.017/120.017 s hidden. All have mixer ready/playing, no mixer failure or foreground event, and normal process exit. The >=118 s assertion is unchanged.
- Full build/test/packaging flow exit 0, all tests offscreen: **514 passed**, 0 failed/skipped (DesktopApi 8, Player 31, ReadAlong 14, Music 37, Mix 73, MusicWindowActivity 3, SkipGlyph 6, Sidebar 117, Width/mini 225). Voice click tests wait for a rendered frame after repositioning the page.
- Locked implementation hash unchanged: `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`; code-derived list has 41 entries. Source files remain LF; cmd.exe executes a CRLF build-script copy. Shared-machine waits, raw traces, exact executable hashes and rejected experiment are documented in [the task report](../../report.md).

## 27-10-2026 — mixer là đường nhạc duy nhất, sáu định dạng

- Nhạc luôn dùng MixVoice; bỏ cờ A/B và factory MF cho nhạc. MfAudioOut giữ cho giọng, bỏ preload/loop không còn caller. Nhận MP3/WAV/FLAC/M4A/Ogg/Opus bằng magic, không phụ thuộc đuôi URL.
- MfSource giải mã luồng nhớ trên reader thành float32 ở tần số gốc, giữ số kênh trước khi nhân đôi mono/lấy hai kênh đầu; dùng Resampler chung và cache PCM cũ. COM MTA/MF sống theo luồng reader. Cắt khung mồi/đệm AAC theo timestamp và độ dài trình bày.
- `build.bat` exit 0; kết quả văn bản riêng kiểm đủ **314** ca, **0 FAIL!**, 0 lỗi/bỏ qua: Player 26, ReadAlong 14, Music 37, Mix 73, MusicWindowActivity 3, SkipGlyph 6, Sidebar 117, Width 38. MusicTests không sửa; mọi bộ thử chạy offscreen với foreground guard. MixTests dùng FakeDevice, kiểm ba tần số ra, thời lượng/mức RMS, mono/đa kênh, cache/header/tái dùng và lỗi đúng một lần.
- Sáu clip mới dài hai giây, sinh cục bộ từ MP3 tổng hợp sẵn có, mỗi file dưới 200 KB; README cạnh fixture ghi lệnh sinh. MP3/WAV/FLAC/M4A đọc được. MF từ chối Ogg/Opus với `0xc00d36c4` cả qua URL và luồng nhớ có MIME/tên nguồn dù Web Media Extensions 2.1.51.0 đã cài; kiểm thông báo lỗi tiếng Việt rõ ràng, không cache dở/phát im lặng như thành công.
- Không sửa QML, `_internal/abook/`, THIRD_PARTY hay dòng changelog nhạc nền ít CPU khi thu nhỏ; không có migration/fallback. Hash policy đọc từ code vẫn `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886` (danh sách hiện có 41 mục).
- MP3 bốn vòng cùng desktop Windows riêng chưa được chuyển lên màn hình như mốc trước: trung vị CPU thu nhỏ ổn định **0,827%** so với **0,822%**, RAM riêng ổn định **18,66 MB** so với **18,58 MB**, trong nhiễu. Có đủ ready/playing, không failed/foreground event; AC được kiểm trước và lấy mẫu xuyên suốt. Lượt desktop hiện tại 0,915% cũng được giữ nguyên trong bằng chứng, không dùng để khẳng định CPU không đổi.
- Probe cloak trước show giữ được qua focus/minimise/restore; hai lượt player có **2542/2583 frameSwapped**, morph p99 **16,760/17,199 ms**, khung restore đầu **15,020/18,956 ms**, 0 foreground/mất cloak. Qt có vẽ khi cảnh chuyển động dù cloak; đây là thời gian frameSwapped, không phải độ trễ hiển thị nhìn thấy. Không thay cấu hình màn hình; danh sách monitor chỉ đọc nằm trong báo cáo.
- Bằng chứng build/test, phép đo MP3 bốn vòng và probe cloak: `D:/Novels/native_desk_proto/musicmix_step1b_task/report.md`.

## 27-10-2026 — musicmix: sửa theo Lead review, chưa commit

- `deskqt_fixture_music` đã khôi phục `book.json` đúng từng byte từ `music_mix_task/fixture_before`; MP3 và lượt A/B dùng fixture riêng `deskqt_fixture_mp3`.
- Thiết bị không phải float32 hoặc có dưới hai kênh báo `AudioOut::failed`; MusicBed nhận lỗi và đánh dấu nhạc im lặng. Kiểm định dạng WASAPI, lỗi lúc mở/đang phát, hai voice, phục hồi bằng lần load mới và đường MusicBed thật.
- Nhịp mixer xét mọi QWindow còn hiện, kể cả cửa sổ phụ được tạo muộn; có hook rõ cho mini khi merge. Kiểm main thu nhỏ/ẩn, mini hiện/thu nhỏ/khôi phục/đóng và cửa sổ không nhận focus.
- `build.bat` exit 0; 8 bộ QtTest/QuickTest đạt **284**, 0 lỗi, 0 bỏ qua: Player 26, ReadAlong 14, Music 37, Mix 43, MusicWindowActivity 3, SkipGlyph 6, Sidebar 117, Width 38. Tất cả chạy với QPA offscreen và process ẩn.
- A/B 4 cặp MF/mixer trên fixture MP3 riêng: CPU ổn định khi thu nhỏ từ **1,407% xuống 0,822% một nhân** (giảm **41,5%**). Cả 8 lượt trên desktop Windows riêng không được chuyển lên màn hình; worker kiểm tên desktop thật, audit không có foreground event, cả 4 lượt mixer có `mix_ready`/`mix_playing`, không có `mix_failed`. Không suy diễn thời gian khung từ phép đo ngoài màn hình.
- Hash khoá trước và sau kiểm tra không đổi: `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`. Bằng chứng build/test và báo cáo bàn giao: `D:/Novels/native_desk_proto/music_mix_task/followup/`, `music_mix_task/report.md`.

## 27-10-2026 — Qt SMTC (dev/desk-qt-smtc)

- MediaControlsTests: 6 đạt, 0 lỗi; tên chương dự phòng, trạng thái/nút, 60 giây nhịp đồng hồ không cập nhật timeline, seek/chương/tốc độ/thời lượng cập nhật theo sự kiện, lệnh về luồng UI, cache bìa và bỏ lời đáp bìa cũ.
- `build.bat` hoàn tất và deploy dist: 8 bộ, 486 ca đạt, 0 lỗi/bỏ qua; đếm 0 dòng `FAIL!` từ từng log QtTest. Theme, máy dò cắt chữ và `git diff --check` đạt.
- Probe C++/WinRT đọc phiên `ABook.Desktop` qua GSMTC trên HWND không bao giờ show: đúng tên chương/sách, Playing, Next/Previous đổi chương, Seek tới 42 giây, Pause tới Player trên luồng UI. `visible=false`, `foreground=false` suốt kiểm tra. Không mở flyout trên màn hình chủ máy.
- Smoke app thật: một lượt bị guard huỷ vì Qt restore kích hoạt cửa sổ; đã thêm chốt Win32 WH_CBT trước QGuiApplication. Lượt chạy lại đọc bìa 47.480 byte và Pause tới Player, 0 foreground; chốt từ chối hai yêu cầu activation/focus lúc restore. Giữ log sự cố riêng, không tính lượt ấy vào A/B.
- Báo cáo build, số đo A/B và log thô: `D:/Novels/native_desk_proto/smtc_task/report.md`. Launcher đo được port từ `origin/dev/desk-qt-musicmix`, có bộ gác foreground trước khi app chạy và vị trí (-10000,-10000). Không giữ nhịp PlayerClock cho SMTC.
- A/B 4 cặp, 8/8 lượt AC/off-screen, 0 foreground: RAM nghỉ 54,68 → 55,40 MiB; CPU thu nhỏ ổn định 1,223 → 1,197% một nhân theo công cụ. RAM thu nhỏ sau trim biến động ở 2/4 lượt bật SMTC (trung vị 21,20 → 37,00 MiB); chưa xác định nguyên nhân, không kết luận chỉ tốn vài MiB khi chạy nền. Cả 8 pha thu nhỏ không tăng bộ đếm PlayerClock/ảnh chụp/ReadAlong.

## 26-10-2026 — qtwide2: sửa theo lead review

- Trang Sách: cụm hai cột tối đa 1360 px, căn giữa; bìa thẳng mép tiêu đề; thời lượng cuối hàng dùng tnum. Nền hover/chương hiện tại và thanh tiến độ giữ hết chiều rộng hàng. Sửa đường chuyển động để bìa/chữ/chương không đi xuyên nhau.
- Phép kiểm đo Text.paintedWidth thay khung hàng: QML cũ thất bại với dải trống 64,70% / 74,01% (1920 / 2560); bản mới 10,43% / 21,31%. Có kiểm mép bìa–tiêu đề ≤1 px, cap/căn giữa, pixel cuối hàng sáng/tối, chuyển động hai chiều.
- Build exit 0, CTest 6/6; 238 ca đạt (Width tăng 31 → 38; các bộ còn lại 26+14+37+6+117). Theme --check, check_text_cut.py và git diff --check đạt.
- Đã mở 44 ảnh sáng/tối và 14 crop mép 2×; Sách/Thư viện có 2560×1440 thật, các màn còn lại 1024/1440/1920. Công cụ chụp phát hiện sai kích thước thay vì âm thầm gắn nhãn 2560 cho cửa sổ bị Windows ép nhỏ. Bằng chứng: desktop_qt/build/qtwide/{shots2,zooms2,shots2_dimensions.json,old_ink_control.txt,new_width_test.txt,build2.log,ctest2.log}. Không commit; mọi cửa sổ mở ở lượt này đã đóng.

## 26-10-2026 — qtwide: bố cục Qt theo chiều rộng nội dung

- Sách/Cài đặt đổi hai cột từ 840 px nội dung; Đang nghe có đọc theo bên phải từ 1200 px; Thư viện căn giữa, bìa 160–200 px; Studio giữa màn, tối đa 800 px. Chuyển hình học 220 ms theo Theme, tôn trọng giảm chuyển động.
- CTest 6/6 bộ đạt; QtTest/QuickTest: Player 26, ReadAlong 14, Music 37, SkipGlyph 6, Sidebar/icons 117, Width 31 — tổng 231 đạt, 0 lỗi. Width kiểm hình học thật của QML ở 1024×700, 1440×900, 1920×1080, rail và compact, lưới tới 2560; kiểm ≥4 hàng chương, bìa ≤45%, lề/cột, đọc theo, mép mờ và chuyển động. check_text_cut.py và gen_theme.py --check đạt.
- Đã mở 36 PNG sáng/tối, gồm 4 màn × 3 khổ, thu thanh bên, cuộn và khung resize; soát mép ở 2×. Fixture audio sao chép riêng, thêm hàng chương tổng hợp chỉ cho ảnh; không sửa thư viện/profile thật. Bằng chứng: desktop_qt/build/qtwide/{shots,zooms,ctest.txt,WidthTests.txt}.
- RAM riêng lúc nghỉ trên trang Sách, client 1920×1080, scale 1, ba lượt/bản: 55,73 → 58,85 MB (+3,12 MB), dùng bộ lấy mẫu tools/measure.py. Không thay title bar/backend/dependency, không commit. Chi tiết ở desktop_qt/PROGRESS.md và scratchpad codex/qtwide/report.md.

Ngày cập nhật: 2026-10-26

Đợt gap1b, worktree `D:/Novels/ABook_ngap`, nhánh `dev/native-gaps`: sửa transport từ xa sang glyph ±15 dùng chung và phát/dừng biến hình; thêm icon loại thiết bị và làm mới đồng bộ ở bảng thiết bị phát, tìm máy trống, nhật ký. Timer cast dùng danh sách cùng mép trái, có ảnh 360/411dp và cỡ chữ 1,3. Một UndoBar nằm trên thiết bị phát/thanh phát nhỏ/tab, mở chiều cao có chuyển động; kiểm cả lỗi xoá trong Shell thật, sáng/tối. Lệnh đầy đủ có ghi ảnh: **2251 test, 2244 passed, 7 skipped, 0 failure/error**, **271 XML**, không có dòng `^e: `; IconRulesTest/IconSheetTest/MotionScanTest/TextCutScanTest đều qua. Đã mở 21 PNG thay đổi và crop phóng to hàng icon; APK native **21.573.885 → 21.590.269 byte** (+16 KiB). Bằng chứng và báo cáo ở scratchpad `codex/gap1b/report.md`. Không commit/push, không adb; không sửa Voice, lõi Python, dependency hay Capacitor settings.

Đợt c14, worktree `D:/Novels/ABook_c14`, nhánh `dev/c14`, nền `3195a78c`: dùng chung bộ đặt vị trí thông báo trên vùng Sonner, bỏ biến `--toast-bottom` ở HTML của thanh điện thoại từ xa; policy chặn ghi biến style ở gốc. Thêm 6 test, mở rộng test đổi chiều cao thanh đầu màn đọc. Trace View Transition máy tính chỉ invalidation `.now-playing-vt`, giữ nguyên. Các thử nghiệm hoãn đo / nạp font màn đọc đều có dải p99 mở đầu chồng baseline nên hoàn tác; không tuyên bố đã sửa lần mở đầu. Báo cáo và đủ mẫu trước/sau ở scratchpad `codex/c14/report.md`.

- TypeScript: **0 lỗi**. Vitest toàn bộ: **2521 passed, 0 failed, 1 skipped**, **317 file** (316 passed, 1 skipped); nhóm tập trung **17/17 passed**. Skip corpus PDF có sẵn. Contrast: **94 nhóm, 2744 cặp, 0 nhóm không đạt**.
- Bộ đo trước/sau reader **10 + 10 mẫu**, baseline bổ sung **35 mẫu**, lượt cuối đủ sáu nhóm **45 mẫu**. p99 trung vị mở đầu màn đọc **427,5 → 422,8 ms**, mở nóng (4 lần lặp) **200,0 → 210,5 ms**; các dải vẫn chồng nhau. **26/26 asset JS/CSS** bản đo khớp gallery cuối.
- Inspector sáng/tối: nhóm tập trung **30/30 khung**, lượt cuối toàn bộ **290/290 khung**, **0 phát hiện / 0 lỗi chạy**, exit 0. Không đổi luật hay dung sai bộ soi, không chạy cùng Vitest. Không sửa audio/Python/Kotlin, không dùng adb/thiết bị, không commit/push.

Đợt c13, worktree `D:/Novels/ABook_c13`, nhánh `dev/c13`, nền `472abf80`: giới hạn selector `:has` của hàng dự án, chỉ đánh dấu tiêu điểm trên phần tử đang nhận, menu xếp sách không khoá body, vị trí thông báo của màn đọc chỉ đặt biến trên toaster. Giữ mọi chuyển động và thời lượng. Thêm bộ đo CDP `gallery_jank.mjs` (412×915, DPR 2,625, CPU 6×), trace và stack/elementCount; thêm retry khoá file cổng Edge và sửa phép đo nhãn text node trần của bộ soi, có đối chứng dấu đặt sai vẫn bị bắt.

- TypeScript: **0 lỗi**. Vitest cuối: **2491 passed, 0 failed, 1 skipped**, **313 file** (312 passed, 1 skipped); thêm **16 test**. Skip có sẵn cần corpus PDF. Contrast: **94 nhóm, 2744 cặp, 0 nhóm không đạt**.
- 5 lượt mỗi thao tác, p99 trung vị trước → sau: mở Đang nghe **122,2 → 61,1 ms**, thu nhỏ **155,6 → 83,4 ms**, mở menu xếp sách **338,8 → 83,3 ms**, đóng menu **122,3 → 44,5 ms**, mở màn đọc **222,2 → 138,7 ms**. Máy đo gần 180 Hz; không coi đây là số đo OPPO. Mở đầu màn đọc vẫn còn tác vụ bố cục lớn, khoảng mẫu còn chồng nhau; các thử nghiệm không thắng vùng nhiễu đã hoàn tác.
- Gate tập trung **30 khung, 0 phát hiện / 0 lỗi**; menu xếp sách đang mở trên điện thoại/máy tính, sáng/tối **4/4 sạch**; lượt toàn bộ **290/290 khung, 0 phát hiện / 0 lỗi**. Báo cáo, mọi mẫu và các thử nghiệm hoàn tác ở scratchpad `codex/c13/report.md`. Không sửa audio/Python/runtime/Kotlin, không dùng adb/thiết bị, không commit/push.

Đợt npm141, worktree `D:/Novels/ABook_npm141`, nhánh `dev/npm141`, nền `d692fc39`: nâng 16 dependency UI và 4 dependency mobile trong range semver cũ, đổi Music2 sang EighthNote. Sửa MenuShell không ghi đè quan hệ ARIA của Radix bằng props undefined; bộ soi chỉ cho phép lặp giá trị đang chọn khi nút mở liên kết đúng popup bằng aria-controls.

- TypeScript: **0 lỗi**. Vitest trước nâng: **2423 passed, 0 failed, 1 skipped**; sau sửa: **2426 passed, 0 failed, 1 skipped**, **302 file** (301 passed, 1 skipped). Thêm 2 ca ARIA desktop/điện thoại và 1 ca fixture trình duyệt gồm một đối chứng đúng, bốn đối chứng sai ở hai khổ/hai theme; nhóm hồi quy liên quan **25/25 passed**.
- Gradle `testDebugUnitTest assembleDebug`: **BUILD SUCCESSFUL**, trước/sau đều **1743 test**, **1736 passed, 0 failures, 0 errors, 7 skipped**, 232 suite. Contrast trước/sau: **94 nhóm, 2744 cặp, 0 nhóm không đạt**. Audit production UI **0 → 0**, mobile **3 moderate → 3 moderate**. Log, số gallery/tap và APK nằm trong thư mục task `codex/npm141/report.md`; không sửa Python, không dùng adb/thiết bị, không commit.
- Gallery đủ **270/270 lượt** sáng/tối: trước nâng **2 REPEATED LABEL**, sau sửa ARIA và bộ soi **0 phát hiện, 0 lỗi chạy**; đối chứng bộ soi mới trên bundle cũ vẫn báo 2 lỗi. Tap audit trước/sau **21/21 PASS**; chèn lỗi trước/sau **exit 1, 0/21 PASS**.

Đợt lib139, worktree `D:/Novels/ABook_lib139`, nhánh `dev/lib139`, nền `0bec019f`: Thư viện mở lưới bìa 2:3, gom bộ thành bìa chồng; điện thoại chuyển sang Thư viện · Studio · Cài đặt, đưa tải/cập nhật sách lên bìa và ghép máy vào Cài đặt › Thiết bị.

- `npx tsc -p tsconfig.json --noEmit`: 0 lỗi. Vitest toàn bộ, tối đa 2 worker: **2073 passed, 0 failed, 1 skipped**, **270 file** (269 passed, 1 skipped). Skip corpus PDF có sẵn. DOM kiểm bìa bộ/Back, dấu nguồn, ba tab, Studio rỗng/mở máy, đường Thiết bị hai chạm, tải từ điện thoại ghép và danh mục chưa có gói nghe trực tiếp; test tương phản hai chủ đề đạt AA.
- Pytest `tests/test_webui_listen_and_sync.py`, CUDA tắt, `-p no:cacheprovider -rf -q`: **32 passed**. Python và Kotlin chỉ đổi chú thích chỉ đường; hash khoá trước/sau giữ `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886` (danh sách đọc trực tiếp: 41 mục). Không sửa primitive chuyển động, không cài dependency, không commit. Ảnh Edge trước/sau: 166/176 ảnh, 0 lỗi ở hai bộ cuối; đã đóng Edge gallery. Báo cáo nằm ở scratchpad `codex/lib139/result.md`; chưa kiểm thiết bị Android thật.

Đợt shell139, nhánh `dev/shell139`: thanh bên ba điểm đến, tối đa ba dự án đang chạy/chờ; skeleton theo nội dung, lỗi tại chỗ có thử lại, dải mất mạng giữ nội dung. Thêm 21 test DOM chuyên biệt và 27 mục gallery, kiểm tra trạng thái tải/lỗi ở màn thật; thử lại thực sự gọi truy vấn, hàng dự án ra có inert và dải mất mạng khép bằng presence. `npx tsc -p tsconfig.json --noEmit`: 0 lỗi; `npx vitest run --maxWorkers=2`: **2105 passed, 1 skipped**, **269 file passed, 1 skipped**. Skip có sẵn cần corpus PDF. Ảnh sáng/tối và danh sách các vị trí giữ nguyên ở scratchpad `codex/shell139/result.md`; không sửa Python/runtime, không cài dependency, không commit.

Đợt fix139, worktree `D:/Novels/ABook_fix139`, nhánh `dev/fix139`, nền `8a76056e` (0.4.138): xác minh chín finding UI; sửa CAO1/CAO2/CAO3/V5/V6/V7/V8/L9. V4 đã có Back stack và 6 test DOM xanh ở nền nên giữ nguyên. Chuyển 18 caller toast sang wrapper chung; Back chỉ nhận đã đóng khi thật sự gỡ toast. Giữ lịch sử nhóm Cài đặt, focus khi lưu lịch đêm, focus ring và các chuyển động exit/empty/badge.

- Test mới: **15 test DOM** trong 4 file (2 mới, 2 mở rộng); chạy trên mã nền cho **14 đỏ**, ca bảo vệ replace ở bố cục rộng đã xanh sẵn. Sau sửa: **1923 passed, 0 failed, 1 skipped**, **258 file** (257 passed, 1 skipped); **19 file DOM, 146 test DOM xanh**. Skip có sẵn: `pdfPages.corpus.test.ts` cần corpus PDF cục bộ. `npx tsc -p tsconfig.json --noEmit`: **0 lỗi**; `git diff --check` xanh.
- Chạy offline với node_modules junction sẵn có, không cài dependency, không sửa Python/audio/runtime, không commit. Kiểm DOM/CSS bằng happy-dom, chưa chạy trên thiết bị thật. Báo cáo file:dòng và log ở scratchpad `codex/fix139/result.md`.

Đợt kt138, worktree `D:/Novels/ABook_kt138`, nhánh `dev/kt138`, nền `85c2790f` (0.4.137): sửa r136 M3/L1. Chẩn đoán share chỉ đọc/validate, không init Store/Remote/server, không tạo bản corrupt; kho lạnh báo chưa sẵn. Reader cho writer vẫn giữ bản hỏng rồi từ chối ghi. Store/LibraryServer serialize init, ghim filesDir canonical đầu tiên, từ chối thư mục khác bằng log; root/context chỉ công bố sau recovery.

- Đỏ: nền cộng test và seam quan sát recovery, **1749 JUnit, 7 FAILED, 0 errors, 7 skipped**. Sau sửa và thêm ca A/B đồng thời, recovery lỗi/retry, socket sống và staging/rekey khi mở lại: **1753 JUnit, 0 FAILED, 0 errors, 7 skipped** (1746 passed), **13/13 test chẩn đoán/init xanh**. BackupRulesTest chuyển phép kiểm chuỗi source sang kiểm đường dẫn share.json thực, 5/5 xanh; quy tắc backup giữ nguyên.
- Lệnh: `gradlew.bat testDebugUnitTest --max-workers=4 --offline -x :capacitor-android:bundleLibRuntimeToJarDebug -x :capacitor-app:bundleLibRuntimeToJarDebug`, JAVA_HOME Android Studio jbr, ANDROID_HOME SDK hiện có, ActiveProcessorCount=4. Mọi lượt giữ khoá chung đúng điều kiện HOLD_MAYAO và trả GRADLE_LEAD_BUSY vào `_dup`, kể cả lượt lỗi. Không GPU, không npm install, không sửa capacitor.settings.gradle, không commit. Hash khoá trước/sau: `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`. Bảng file:dòng, XML và log ở scratchpad `fixkt/result.md`. Chưa chạy thiết bị Android thật.

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

Vòng 16 nhạc P3 trên `dev/loopp3w`, nền `94466b3a` (PLAN_loop §46.21): `SeamClock.gate` dự đoán nhịp kế bằng `remainingMs - gapMs <= 2500`; `MusicBed` đo khoảng cách nhịp bằng `System.nanoTime`, kẹp 0–1000 ms và bỏ mốc khi tua/reset. Thêm 4 test JVM: gap 0 giữ hành vi cũ, biên dự đoán, READY/DEAD/attached độc lập gap, đủ 500 pha của nhịp 0,5 s đều demote khi còn 2500–3000 ms. `:app:testDebugUnitTest` exit 0; XML 1626 tests, 1619 passed, 7 skipped, 0 failures, 0 errors (208 suite). Hash khoá trước/sau `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`. Chưa đo lại audio trên thiết bị.
Build `assembleDebug assembleDebugAndroidTest` ở root vướng `:capacitor-cordova-android-plugins:checkDebugAndroidTestDuplicateClasses`; build lại riêng `:app:assembleDebug :app:assembleDebugAndroidTest` exit 0. Hai APK app đã chép vào `p3w8/apk51`, SHA-256 nguồn/đích trùng; checksum và log bàn giao ở `D:/Novels/LLM_Train/codex/v16/`.
Gộp `dev/loopp3w` 1494365e vào main 013cc7a0 (26-10, luật APK51 §46.23 đạt cả bốn: bed51thu 10/10, bed51s6thu, bed51s6p (i)–(iv), bed51p 10/10 trên OPPO): gộp sạch, không xung đột. `:app:testDebugUnitTest :app:assembleDebug :app:assembleDebugAndroidTest` exit 0; XML 1818 tests, 0 failures, 0 errors, 7 skipped. Hash khoá `c9176123`.

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


## 24-10-2026 — Ảnh MotionRegion theo phạm vi trang và surface

- Vùng trang giữ ảnh fixed trên body theo viewport, không clip tổ tiên hay đăng ký scroll riêng. Vùng trong Dialog/Sheet/Popover/menu giữ absolute theo surface; một scheduler rAF chung đặt lại vị trí/clip sau layout effect và trong suốt thời gian fade, được gỡ khi ảnh cuối biến mất. Menu static chỉ bù scroll chưa được containing block bù. Font kế thừa chép longhand, kể cả feature/variation settings. Giữ fade, inert, aria-hidden và pointer-events:none; giữ lọc ảnh lồng nhau và loại bóng đôi cha/con.
- Bộ DOM cuối: 8 failed / 9 passed khi chạy trên source d3224daf; 17/17 đạt sau sửa, có Collapse production, resize không phát scroll, menu positioned/static, font shorthand rỗng và cleanup remove/animationend/timeout/unmount. Nhóm liên quan: 91 test/8 file đạt.
- Edge 155.0.4283.62 qua CDP headless: tái dùng fixture r137 và 18 ca cũ, 39 ca candidate với sai số tối đa 0.012543px. Sticky 20→0px; clip Fold trong surface sai 36.984375→0.000005px, frame đầu sau commit clip 0px; resize 90→0px; overflow thừa 462→0px và bề ngang thanh cuộn 10→0px; menu 20→0px; header 14px/400→18px/600 đúng source. Hai ảnh surface dùng chung 1 rAF, unmount còn 0 ảnh/0 rAF/0 listener. Chạm thật qua CDP đi tới nút live; ảnh không chặn input.
- Median capture danh sách Windowed (15 mẫu/loại/revision): 200 sách (60 hàng mounted) 5.5→4.9ms; 3000 chương (80 hàng mounted) 5.1→4.9ms, so với trước d3224daf. Median toàn commit tương ứng 7.9→7.2ms và 6.9→7.7ms; mẫu hữu hạn, không kết luận tăng tốc toàn ứng dụng.
- Vitest toàn UI: đủ 254 file, 253 đạt / 0 lỗi / 1 bỏ qua; 1884 test đạt / 0 lỗi / 1 bỏ qua (corpus PDF cục bộ). Đủ 15/15 file *.dom.test.tsx, không test DOM bị bỏ qua; tối đa 2 worker, affinity 4 CPU, 43.10s. Tsc -p tsconfig.json: 0 lỗi, exit 0. Hash khoá trước/sau c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886.
- Không Git ghi, không npm install/update, không GPU/Gradle/backend. Edge chỉ dùng profile/PID riêng, đã đóng và xoá profile bằng Python đường tuyệt đối. capacitor.settings.gradle khớp HEAD, không bị sửa. Bằng chứng chi tiết và lệnh tái lập ở scratchpad/fix137b ngoài cây; chưa kiểm Android/WebView thật.


## 24-10-2026 — studio139: chuyển động Studio/desktop và emu138

- Đối chiếu part_D1/D2/E tại code hiện tại: sửa 49 mục VỪA/THẤP; giữ CAO PartLinks và toàn bộ internals MotionRegion/motion. Form inline dùng Collapse/region; trạng thái hộp, menu, toast và query tới sau giữ vùng chuyển động; lỗi chương dùng Radix Popover có Back. Nhãn và mô tả chính rút gọn.
- emu138: chân hộp thêm sách sticky trong vùng cuộn; không autofocus ô chữ khi any-pointer:coarse; gập nhóm thư viện giữ nền kệ đủ cao và chỗ cuộn, nhường thao tác cuộn mới.
- Thêm 21 ca DOM (17 ở hai file studio139 mới, 4 ở AddBook/LibraryScreen); tổng inventory 21 file DOM, không skip DOM. Full npx vitest run: 259 file đạt / 1 file bỏ qua, 1944 test đạt / 1 bỏ qua; tổng 260 file / 1945 test, 0 lỗi, 6,54 s. Skip có sẵn là corpus PDF cục bộ. npx tsc -p tsconfig.json --noEmit: exit 0.
- Đồng bộ nhãn Kết nối Wi-Fi với remote_books.SYNC_SWITCH; pytest tests/test_sync_switch_label.py: 1 đạt. QUALITY_IMPLEMENTATION_FILES đọc từ code có 41 mục; hash trước/sau c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886. Không đổi dependency/runtime, không mạng, không Git ghi.
- Bằng chứng và trạng thái từng finding ở scratchpad/codex/studio139/result.md, log tsc.log/vitest.log cùng thư mục task. DOM dùng geometry/WAAPI mô phỏng; chưa chạy emulator hoặc đo frame trên thiết bị thật.

Đợt gap1, 26-10-2026, worktree `D:/Novels/ABook_ngap`, nhánh `dev/native-gaps`, nền `2d294798`: bổ sung Hoàn tác xoá 28 giây, đóng cả trình phát khi sách rời Thư viện, Báo từ Studio qua thông báo Android, bảng điều khiển thiết bị phát và lựa chọn nghe thẳng/tải ngay từ sách máy tính. Dữ liệu mạng dùng lõi Kotlin hiện có; không sửa backend, Voice settings, dependency hay manifest của bản WebView. JVM toàn bộ: **2242 test, 2235 đạt, 0 lỗi, 7 bỏ qua có sẵn**, đếm từ 270 XML; kiểm lại UI cuối **496/496**, luồng gap Compose **15/15**. Quét log các lượt thành công: không dòng `e: `. 152 PNG đã mở/soát, 12 ảnh mới sáng/tối. Native debug APK: **21491965 → 21573885 byte** (+81920, +0.38%). Báo cáo đầy đủ và lý do đặt từng điều khiển: scratchpad `codex/gap1/report.md`. Không dùng adb/emulator, không commit/push; chưa đo hiệu năng trên điện thoại thật. Hàng chờ xoá giữ qua Activity recreation, chưa giữ qua process death (file gốc vẫn nguyên nếu tiến trình chết trước hạn).

## 27-10-2026 — Qt: bố cục theo khổ cửa sổ

- Worktree `ABook_qtint`, nhánh `dev/desk-qt-int`, HEAD `dbc19aad`; không commit. Thêm / Sửa sách chia cột theo khổ, Thiết bị chia Máy này / Máy đã ghép theo bề ngang cột, Cài đặt mờ qua khi đổi khổ, Studio đổi bố cục trạng thái hiện có, mini cho kéo rộng và đặt nút phát cạnh tên. Giữ bố cục rộng sẵn có của Thư viện / Trang sách / Đang nghe.
- 72 ảnh trước + 72 ảnh sau: chín màn × 1024 / 1366 / 1630 / 1920 × sáng / tối. QML thật, HTTP/audio giả, offscreen QPA + software renderer trên desktop Windows riêng; foreground guard cài trước resume: 0 sự kiện foreground. Không mở thư viện thật, không đo GPU / frame time.
- `build.bat` qua `tools/build_hidden.py qtwide-final`: exit 0, tổng **667 đạt, 0 lỗi, 0 bỏ qua**. Bộ Width gồm kiểm chữ, cột, reflow hai chiều, bản nháp, reduced motion, mini kéo rộng và khôi phục cửa sổ. UI parity: 8 đạt. Theme / text-cut / parity / LF / diff checks đạt.
- Hash khoá trước / sau giữ `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`. Chi tiết từng màn và từng khổ, lệnh và log: `../../report.md`; ảnh và viewer ở `D:/Novels/native_desk_proto/qtwide_shots/`.

## 28-10-2026 — Qt: minimized playback CPU, Round 2

- Worktree `ABook_voicemix`, HEAD `ca491857`; no commit. Guarded full build: **779 passed, 0 failed, 1 existing intentional skip**. Final runtime sources match the saved build manifest; build/dist match preserved measured B `20ebb801`.
- Target **<=0.15% of one core remains unmet**: four alternating A/B pairs give A **0.211239%**, B **0.214011%** median. Final software hidden check: **120.022817 s wall / 120.020 s media**, CPU **0.258486%**, private/working set **58.33/14.98 MiB**. Accepted runs require AC, no foreign build/test activity and zero foreground events.
- Hidden output wait returns fall to **1.33/s**. Matched native graphics probes remove recurring NVIDIA/pool scheduling and reduce private commit **150.93 -> 59.20 MiB**, with about **98 ms** additional first restored frame latency in that single comparison. Visible motion and PCM cursor continuity are tested. Hidden bookmarks now save every 30 seconds plus forced controls/shutdown; a crash can lose that unsaved wall-time window.
- QoS and larger compressed-fetch experiments were rejected after reversed pairs. No `_internal/abook/` change; locked hash remains `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`. [Full report](../../report.md) preserves Round 1, all measurements, per-thread tables, limitations and the earlier launcher isolation/focus breach correction. Final runs verify the native startup and actual thread desktop before accepting evidence.

## 30-10-2026 - Native phone gap 3

- Worktree dev/native-gap3: settings 36 -> 0, devices 48 -> 0, voice 29 -> 0, add-edit-book 39 -> 0; library-book production 7 -> 0 and shared Đang thu âm 1 -> 0. Full per-string evidence and reasons for platform exceptions: worktree report.md and shots/string-audit.md.
- Added recovery/update/settings feedback, permission/sharing/Studio/device flows, provider/voice/key copy and actions, explicit package replacement, bulk import and sync receipts, and live production from the existing pinned /api/listen/library array. All file-size UI uses one 1024-based vi-VN formatter with the 17 desktop size cases and a duplicate-formatter guard.
- Emulator caught file-URI display-name loss and a 411 dp ChoiceRow collision. Repaired both; measured child widths now determine option placement, and a geometry test checks the 24 dp gap. New UI has light/dark Robolectric images in app/build/shots; 19 adb screenshots were opened at original resolution.
- Final full native debug unit/build: 2862 tests total, 2855 passed, 0 failures/errors, 7 skipped; XML saved in shots/test-results-native.zip. Parity pytest: 8 passed, 0 failures/skipped. One additional bulk failure/explicit-choice test was added after the full run and is reported separately in report.md.
- Native APK uses -PnativeUi -PbenchAppId=com.ngdtuanh.abook.dev. Headless ebook_pixel, ports 5584/5585, adb server 5038 only; emulator killed on completion. No physical phone app was operated, no adb server killed, no online voice/module downloaded, no commit.
- Quality hash before/after c95fac04433a97e3b6a8c701514891b85718df8829d73313b7cd742dfb5fc9b8; no abook/ or desktop_qt/ source changes. Physical paired-Studio/Cast/Bluetooth network behavior was not exercised; endpoint shape and dispatch paths were source/JVM-verified.

## 03-11-2026 - ASR spelling alternatives, digit quotes and sentence boundaries

- Worktree `dev/asr-tn-fix`, HEAD `e5777732`; no commit/push. Quality implementation list read live: 41 files. Hash `c95fac04433a97e3b6a8c701514891b85718df8829d73313b7cd742dfb5fc9b8` -> `76f6a2ca6fde2ca373aece9df1767f3024d30902d9a9767e8729e0e27d2c0556`.
- Focused CPU-only pytest: **605 passed, 0 failed**; includes 63 new synthetic cases. Real VieNeu/sea-g2p CPU phonemizer checks retain the complete grouped number and remove spoken quote units. Android offline `VieneuParityTest` passed with the updated shared fixtures and quote guard.
- Forced isolated reversions: TN 36 FAILED lines -> restored 37 passed; ASR 7 FAILED lines -> restored 10 passed; signal 3 FAILED lines -> restored 3 passed. No source reversions raced the live suite.
- Read-only production replay: 3,327 transcribed rows, including all 3,283 verified takes. No old ASR pass becomes a failure. Of the 23 requested rescues, 11 pass directly, 7 qualify for the existing anchor-review publication route, and ids 870/1119/2055/2906/2971 retain transcript/reference discrepancies. All seven specified real wrong-word cases remain rejected; all five off-audio hallucination warnings retain their warning. A saved transcript alone does not establish whether the corresponding audio or Whisper is wrong.
- First/last 5 ms RMS threshold 0.05 flags 4/3,283 verified WAVs (0.12184%), including the reported onset. Tail RMS p99/p99.9: 0.000660/0.022948; head: 0.000651/0.001528. This is a flag rate, not a human false-positive measurement. The gate retries before chapter assembly; raw TTS, inference models, source text and production artifacts are unchanged by this audit.
- Full four-shard verification and per-row evidence are recorded in the requested external `result.md`; the failed shard is being rerun after giving synthetic recovery/preview tones quiet boundaries. Final counts are appended below when that run completes.

### 2026-11-06 - dev/teller-per-chapter (uncommitted)

A+ chapter narrators reuse a differing-gender teller's character profile, including their own thoughts. Explicit narrator wishes/applied listener choices win globally; a missing auto flag alone is not a choice. No schema or preset additions.

Final unique pytest results across 106 files: 2544 passed, 5 skipped, 0 FAILED/errors (105 direct-import files plus UI parity; corrected complete-file reruns replace earlier results). Chapter cases include TTS/preview/QA/candidate profile consistency, CLI settings-file auto selection, idempotence and transaction rollback/reopen. Initial failures and per-file JUnit counts are retained in scratchpad/codex/teller3/tests-per-file.md. Vitest: 34 passed; TypeScript: exit 0 in an isolated scratch copy because the shared dependency junction lacks Vitest. Kotlin targeted JVM suites: 45 passed, 0 failures/errors; parity checks passed. No live app, synthesis, GPU or devices.

Preserved Your Story snapshot copy: 672 narration profiles changed in chapters 8-10 to Touka's existing Doan Trang profile; 670 recorded rows reset (146/263/261), 2 already unrecorded; 2871 other rows unchanged; repeat ensure changed zero rows. Source books queried using SQLite mode=ro only. Current live narration generation provenance already matches character profiles in all 672 Your Story and 619 Pain Pain Go Away affected rows; exact SELECT queries/IDs are in scratchpad/codex/teller3.

Quality hash: f10085f96acd7f9fe6a066f2bf5a74338b0a351bea3d98f58f6d2807912cbfff -> 2ae1ce6e982077c17fa49a61ce1c561bac9bd237f031358650aa7159c7d31a35 (42 locked entries read from code). Dev branch only; merge waits for current book runs.
## chaplevel2 (dev/voice-loudness)

Kiểm vòng kín trên giọng tổng hợp qua FFmpeg thật: chương một giọng nhỏ theo phon, giới hạn cuối, lần chạy thứ hai dùng lại, lỗi meter/master giữ audio, loại vòng xấu, holdout không trùng câu fit. Mốc câu được đối chiếu độ dài MP3 sau cắt lặng; cache words cũ không đính kèm audio mới. Kết quả importer suite và đo hai sách thật ghi trong report.md của thư mục tác vụ; chưa phải bằng chứng phát hành.
# HITL mốc 2 — 07-11-2026

Thẻ vai phụ nhiều câu theo chương có đề xuất tên, đặt giới theo nhóm và mở bộ chọn giọng; thẻ `caller` hỏi người nói qua điện thoại/ngoài khung theo bằng chứng lời kể cạnh câu. UI vẫn ghi ý muốn qua speaker/voice, worker áp ở ranh giới an toàn và chỉ đặt lại audio bị đổi. Đồng bộ React/Qt/Android, DESIGN và parity; không thêm hiệu ứng điện thoại.

Lượt triển khai: pytest `-rf` 9 file, **121 passed, 0 FAILED**; vitest Studio **29 passed** và gallery **3 passed** (chỉ story liên quan); Qt Quick offscreen/software **6 passed** gồm init/cleanup; Android 2 lớp **40 tests, 0 failures/errors**, đối chiếu XML. TypeScript và hai máy dò parity `--check` đạt. Story web chỉ kiểm DOM, chưa kiểm hình browser.

Soát chéo rev164b: hai test mới tái hiện việc mở lại câu đã quyết riêng / vai đã tách hết, đỏ trước sửa và xanh sau sửa. Thẻ chương chỉ lấy câu chưa quyết khi còn câu mở. Pytest đích sau sửa **47 passed**; Qt render không còn ghi vào thư mục báo cáo ngoài commit. Trên cổng `score_bd` 23 chương (`b9lps1234`), regex caller không khớp câu nào: 0 thẻ / 1.849 câu có gold người nói; precision không xác định, recall đối với 404 lỗi người nói là 0%. Gold không có nhãn kênh điện thoại, nên không suy ra precision/recall nhận diện người nói từ xa. Hash đọc từ 53 file khóa giữ nguyên `3818e7751fec8680b70e3f148d1f0a63ede8de1a6599fad3ab043ff632c5467b`. Không GPU hoặc release gate đầy đủ.

# pacetag — 06-11-2026

Nhãn pace không đổi âm thanh hoặc QA: cùng bản thu, band `[12.5, 24.5]` sau bù dấu câu và sàn âm tiết `3.75`, nhân sàn bằng `pace_floor_scale * x` và hệ số engine hiện có. Đây là band normal đang có trong config, không phải sàn 10.5 của phép đo cũ. Ngân sách frame cũng dùng band chung, vẫn chia theo `r` cho bản thô. Không đổi bảng giọng, gain, WSOLA, trần im lặng hoặc nghỉ cấu trúc. Schema/prompt phân tích giữ nguyên. VieNeu cho phép bỏ `silence_p` (mặc định 0.15); Studio không gửi tham số này nữa. Gỡ vòng nới band, metric và warning riêng, không có migration.

Test `test_pace_label_is_metadata.py` kiểm cùng take dưới slow/normal/fast/unknown, gồm nhận, cảnh báo và lỗi safety, hai hệ số sàn; đối chiếu cả metrics, ngân sách frame và tham số sinh. Kết quả importer thực và audit chỉ đọc hai sách, gồm stable ID không kèm nội dung, nằm trong `scratchpad/codex/pacetag/report.md` của phiên làm việc.

Kiểm `-q -rf`: lượt đầu 123 module có 2862 đạt, 3 lỗi, 5 bỏ qua; sau sửa fixture/assertion, chạy lại trọn 12 module được 239 đạt, 0 lỗi. Kết quả mới nhất từng module: 2865 đạt, 0 lỗi, 5 bỏ qua (không cộng trùng lượt chạy). Lượt rộng có 8 cảnh báo thread đọc stdout không giải mã được UTF-8; lượt chạy lại không có. Compileall và diff check đạt. Audit: slow trượt band chung 0/715 và 2/642; fast có bằng chứng ít nhất 2 và 12 lượt retry riêng do band fast. Hash `26e20236…` → `6e1970d0…`; chưa commit.

# castrules2 — kiểm raw model local, 07-11-2026

CPU replay 116 lượt chương Qwen 4B/9B, 47 sách, 27.726 câu có gold: origin/main 5678fddf7 có 3.902 lỗi speaker/kind gộp, cây nhận từ lượt trước có 3.977, sau sửa thêm còn 3.928 (107 câu hỏng mới, 81 câu cứu so với main). Còn 20 sách tăng lỗi; chưa đạt mục tiêu từng sách. Tập envelope sau validation được báo riêng, không giả làm raw. Không có cặp raw 8B/gold fingerprint chắc chắn trong phạm vi đã tìm.

Khôi phục sửa trích thuật ngữ có đủ ngữ cảnh và hồi phục phase hai người có hai neo lời gọi cùng một mâu thuẫn trực tiếp của model. Giữ phản ví dụ một neo, thiếu context và hành động nối tiếp; thêm bốn test tổng hợp. Nguồn TXT của harness được đóng băng riêng từng sách trước cả hai vế, tránh việc registry đọc nhầm sách khác qua sibling TXT. Gold passthrough cùng snapshot 15 sách: 2.041 → 118 lỗi, không sách tăng; không dùng nó để kết luận model tốt hơn.

Pytest trực tiếp bằng interpreter quy định, `-m pytest -rf`, 149 file: **3.976 passed, 9 FAILED, 0 errors, 3 skipped**. JUnit và log đều đếm 9 failure. Cả 9 ở test_database_safety.py, liên quan giao ước kind từ hint đã đổi và fixture dùng giao ước ấy; không xóa/đổi expected để làm xanh. Lượt invocation sai import và lượt qua stdin được lưu riêng, không dùng làm kết quả cuối. Compileall, LF và diff check đạt. Báo cáo từng sách, 67 test cũ đổi/xóa tên và các đánh đổi nằm trong thư mục tác vụ castrules2. Chưa commit/push; chỉ sửa cây dev/castrules.

# castrules3 — chọn stage bằng ablation CPU, 07-11-2026

Giữ snapshot lượt 2, chạy 16 ablation thật: toàn bộ cây SAU nhận vào nhưng từng stage/loại thay đổi dùng hành vi TRƯỚC, rồi chạy tiếp các stage sau. Chọn lai stage gọi tên: hồi phục phase một neo với thứ tự duy nhất, giữ và mở rộng chặn tự giới thiệu/trả lời tên/trích lồng/tên người con trong nhãn quan hệ; stage lead-in không lan ABAB. Các stage khác giữ mới.

Kết quả cuối speaker/kind gộp: raw 27.726 câu **3.902 → 3.887**, envelope 9.742 câu **1.603 → 1.577**, gold passthrough 42.142 câu **2.041 → 112**. Đạt hai ngưỡng tổng, còn 12/47 sách raw và 2/18 sách envelope tăng lỗi; gold 0/15. Raw có 49 hỏng mới/64 cứu, envelope 8/34, gold 2/1.931. Riêng speaker đúng trên raw giảm 5; kind không đổi. Không dùng lỗi gộp hay gold passthrough để kết luận mọi trục hoặc chất lượng audio tăng.

Giữ bỏ khóa kind thuần ngoặc: gold kind đúng 40.408 → 42.141, local kind không đổi. Chín FAILED cũ được sửa theo ngữ nghĩa mới, vẫn kiểm bằng chứng giả, speaker local ngoài phạm vi và rehash/reopen/commit; khóa nguồn ngữ nghĩa độc lập vẫn được cưỡng chế. Pytest trực tiếp 149 file, gồm toàn bộ test_database_safety.py, `-rf`: **3.991 passed, 0 FAILED, 0 errors, 3 skipped**; JUnit 0 failure node, log 0 dòng FAILED. Compileall, LF và diff check đạt.

TRƯỚC và SAU nhận vào khớp toàn bộ JSON với lượt 2 (184 local + 15 gold mỗi phía). Lỗi template rỗng của harness mới đã được phát hiện và toàn gold matrix chính thức chạy lại bằng template đúng, backup read-only thấy WAL; mỗi invocation có runtime sidecar riêng. Parser/prompt/critic/ledger/opt-in nằm ngoài đường accuracy replay đã đóng băng, được kiểm bằng test thay vì gán số ablation giả.

Cả bốn tài liệu castrules cũ, gồm deltas.csv, được move ra thư mục tác vụ; repo chỉ giữ số tổng ở docs/castrules. Báo cáo đầy đủ, từng sách, lý do từng test và bằng chứng riêng ở scratchpad/codex/castrules3. Hash dev `71aa3370…` → `e1825aff…`; không commit/push hay sửa cây khác, không LLM/API/GPU/kill.

# nosafety — 08-11-2026

Gỡ hoàn toàn tự hẹn/tự dừng vì lâu không tương tác trên Android Compose/native, Qt, web và Python preferences/API. Không còn field/range/UI/nhánh safety; không đọc, migrate hay xoá khoá cũ. Giữ lịch đêm mặc định tắt do người nghe bật, hẹn phút/hết chương, cử chỉ opt-in và các đường dừng do hết nội dung/lỗi/audio focus. Invariant trong AGENTS.md; sinh lại parity; cập nhật năm ảnh chuẩn settings Android. Test giả lập nghe không thao tác 3 giờ giữ timer OFF và audio không pause.

Kotlin JVM toàn bộ: **3.377 passed, 0 failures/errors, 8 skipped** (390 suite, 3.385 cases). Vitest liên quan 113 file: **1.305 passed, 0 failed**, typecheck đạt. Qt PlayerTests **47 passed**; WidthTests toàn bộ ba file settings/d2/shots **38 passed**, 0 failed. Android ảnh record và verify mỗi lượt **6 passed**. Tất cả GUI headless/offscreen.

Pytest full một invocation `-rf`: **10.610 passed, 2 FAILED, 14 skipped, 2 xfailed, 3 warnings**, 3.012,56 giây; đối chiếu đúng hai dòng FAILED với hai XML failure nodes. Hai lỗi là kỳ vọng copy safety đã gỡ (module collect trước khi sửa test) và kỳ vọng giữ khoá lạ trong Preferences.get. Đã đổi contract test theo schema hiện tại, kiểm raw file vẫn giữ dữ liệu lạ khi nạp; không sửa thêm code sản phẩm. Recheck toàn bộ **12 file: 162 passed, 0 FAILED/errors/skipped**. Không gọi lượt full là xanh.

Danh sách quality đọc trực tiếp có **56 mục**. Hash trước/sau giữ nguyên `0f178264cdfa197d1449811716621f7319d7e3257d878b6aac3e2f237f8b27dc`. LF/compileall/diff check đạt. Chỉ nhánh dev/timerbug2, HEAD f7eca3884, chưa commit/push. Bằng chứng, danh sách 11 loại đường hẹn/dừng còn lại và chi tiết các lượt lỗi/recheck ở scratchpad/codex/nosafety/report.md.

# safetystop — 07-11-2026

Hẹn tự động trên Android cần màn tắt liên tục, không tương tác và bốn cửa sổ nằm yên khi có cảm biến; desktop dùng thời gian rảnh toàn OS (Windows GetLastInputInfo). Dấu hiệu còn thức huỷ hẹn tự động; hẹn tay giữ nguyên. Không khôi phục hẹn tự động từ đĩa; hẹn tay gắn sách/hồ sơ. Giao diện và thông báo nêu lý do, dùng hoạt ảnh sẵn có. Chữ và mô tả ba nền đã đồng bộ, sinh lại parity.

Kiểm cuối: Android JVM 93 passed (13 lớp, 0 failed/error/skipped); Vitest 88 passed (12 file); typecheck đạt; Qt PlayerTests build/chạy ẩn offscreen 47 passed; pytest tín hiệu OS và hai máy dò parity 33 passed. Compileall và diff check đạt. Probe Windows thật trả thời gian rảnh hợp lệ. Hash chất lượng trước/sau giữ nguyên `5769f2787088e6389c7b9d1fe860db839923247fead4d6e3428e141804af4e9e`. Không GPU, không ADB/điện thoại thật, không commit/push. Còn cần kiểm OEM về cảm biến/âm lượng/Bluetooth khi tắt màn, pin nền và hiển thị/hoạt ảnh trên thiết bị.

# vox165b — luật trích giữa câu có điều kiện

Giữ kiểm hai nửa câu kể và attribution mạnh, bổ sung safeguard cho ngôi 1–2, tiếng kêu/cười, đáp lễ, đáp ngắn có cue và trích nối liên từ. Cue chỉ xét mệnh đề cuối với bổ ngữ hữu hạn; khung giải nghĩa và hướng dẫn cách nói được xét riêng. Không dùng tên, ID sách, gold hoặc nguồn model làm điều kiện. Không đổi kind, schema hay các sửa teller/gate của vox165.

Replay CPU toàn bộ input đóng băng: raw 27.726 câu **3.887 → 3.886**, envelope 9.742 câu **1.577 → 1.577**, gold 42.142 câu **112 → 58**, voxfix **0/35 bị xoá**. So mốc cũ còn 3/47 sách raw tăng, envelope 0/18, gold 0/15; so cây vox165 nhận vào là 0/47, 0/18 và 2/15. So vox165, raw cứu 47/hỏng 0, envelope cứu 10/hỏng 0; gold còn mất hai tên. Gold là nhãn model có phân xử, không hoàn toàn human gold; chưa có holdout hoặc nghe audio mới.

Code app trực tiếp khớp 199 JSON của arm chọn, baseline nhận vào khớp 199 JSON vox165, đều 0 mismatch. Pytest cuối **187 file, 4.627 passed, 0 FAILED, 0 errors, 3 skipped**, 0 dòng FAILED thật; một invocation đầy đủ, không ghép recheck. Ba skip do giọng ZeroTTS/Supertonic chưa tải. Lượt trung gian có 4 FAILED ở kỳ vọng cũ giữ mọi tên của cụm danh ngữ, được sửa theo luật mới và giữ kiểm kind/gender. Thêm 40 ca tổng hợp; không chép chữ truyện vào repo.

Compileall, hai UI parity check, LF và diff check đạt. Danh sách khoá đọc trực tiếp có 53 mục; hash `72070ca5df3d2dae375938f8315e2b5971e939462c511f954bc8eaa9dd46d16a` → `998bbdbf94139368cb858e3347247ae23779700ae5eba911f5dac9d03f613fe8`. Chỉ cây dev, chưa commit/push; không dùng để resume project có hash cũ. Ma trận 10 phương án và các delta riêng ở thư mục tác vụ ngoài repo `scratchpad/codex/vox165b/report.md`.

# voxverify — ngoại lệ giọng chương ở mode mặc định, 08-11-2026

Bản chép Three Days tái hiện 238 phát hiện: 231 owner/giọng chương, 6 xung đột nhãn NARRATOR với giới, 1 nhân vật nam mang preset nữ. Giọng dẫn cả cuốn được cấp cho mọi NARRATOR; bước áp giọng chương không được gọi ở mode mặc định. Sửa quy tắc chung cho người kể được khai riêng theo chương/đoạn khác giới giọng dẫn, áp mọi kind của NARRATOR và nội tâm chưa rõ chủ thể, giữ speaker/character và provenance. Sửa chữ/delivery hoặc chọn owner NARRATOR không miễn trừ giọng chương; preset dẫn được chọn rõ và lựa chọn người nói có tên vẫn thắng. Công tắc teller cùng giá bật/tắt tách khỏi ngoại lệ mặc định.

Giữ casting đã thu: 231/231 câu chương 18 về Ngọc Huyền. Phân vai mới từ nhãn hiện có, không model/TTS: lỗi kế hoạch Three Days 237 → 6, Pain 634 → 0, Your Story 693 → 0. Sáu cờ còn lại đã mang nhãn NARRATOR xung đột giới trong candidate trước casting, không tự đoán lại người nói. Pain và Your Story đã có sửa nhãn trước snapshot; số 0 không phải phép đo trên nhãn model thô. Audio chưa thu không được chứng nhận pass. DB/WAL/JSON nguồn và ba snapshot ban đầu khớp SHA-256; chỉ đọc nguồn, không chép audio hoặc văn bản truyện vào repo.

Test tổng hợp mới 12 ca, có chapter/section, mọi kind, quyền chọn của người nghe, giá công tắc, reopen/idempotence/undo và crash rollback. Pytest liên quan 12 file: **180 passed, 0 FAILED**. Full một invocation `-m pytest -o addopts= -q -rf --durations=30`: **10.560 passed, 1 FAILED, 15 skipped, 2 xfailed, 3 warnings**, 2.240,72 giây; đúng 1 dòng FAILED. Lỗi duy nhất `test_load_sensitive_sites_only_shrink` có sẵn ở HEAD: 5 vị trí gọi đồng hồ trong ba file test Android/UI. Source ba file, scanner, baseline và test đều trùng byte HEAD; dò source HEAD tái hiện đúng 5 vị trí. Không sửa file ngoài phạm vi hoặc nâng baseline để làm xanh.

Compileall, LF và diff check đạt. Danh sách khóa đọc từ code: 55 → 56 mục, thêm teller_voice.py. Hash `80e4c2d1b4f22b892b26638404c234f1d754d6e02be5fde3efc52e3baedce2aa` → `e33e20f4d109266753ff58c956f8be4eb949fd936e4226bc6e107c9dad1a0120`. Chỉ cây dev/voxverify, chưa commit. Báo cáo đầy đủ ở `report.md`; DB mô phỏng, log full, chứng cứ HEAD và JSON từng dòng ở thư mục tác vụ ngoài repo `scratchpad/codex/voxverify`.

Sai sót phạm vi kiểm: full suite có `test_readaloud_vieneu.py::test_parity_turbo_and_nano_waveforms`, đã chạy engine VieNeu ONNX thật trên CPU để so waveform. Bài này bị bỏ sót khi kiểm yêu cầu không TTS; không coi lượt full là tuân thủ hoàn toàn yêu cầu đó. Không chạy thêm suy luận sau khi phát hiện. Các mô phỏng gán giọng không gọi TTS; không thu lại hay thay audio của ba sách, DB/WAL/JSON nguồn vẫn khớp băm cuối tác vụ.
# Sound reading rules (2026-11-08)

The shared `readaloud/sound_policy.json` supplies vocal patterns, common emoticon
sounds, repetition limits, note boundaries, and the long-initialism bound to
Python and Android BuildConfig. Display text and word ownership stay intact.
R1-R3 also preserve the Vietnamese GVCN convention, underscore-framed stutters,
and the guarded vv. enumeration form. VieNeu cache rules are now 10 on both
platforms. The policy data is included in package data and the quality hash.

Self-authored shared cases cover repeated vowels/consonants, multiple stretches,
rhythmic laughter, stretched honorifics, syllable stutters, note anchors, listener
readings, and false-positive guards for words, names, identifiers, ranks and units.
Detailed route measurements, SHA freezes, CPU audio/ASR and test logs are private
artifacts in the soundfix work folder; they are not listening gold labels.
# 08-11-2026 — dev/jp-names: luật romaji chung và held-out

Policy Nhật dùng một JSON Python/Kotlin, namespace `jp-fallback1`. Định tuyến bằng bảng âm đầy đủ,
ít nhất ba âm tiết, kính ngữ dính hoặc cặp romaji viết hoa; bảo vệ âm Việt và từ điển Anh hiện có.
Không có danh sách tên nhân vật theo sách; `fixed` chỉ giữ từ phổ thông onigiri. Mọi cách đọc sinh tự động
giữ provenance `auto`; cách đọc người nghe cho từ/cụm vẫn thắng.

- Held-out riêng ngoài repo: 14 cuốn khác dev, 416 lượt Nhật / 129 loại tên sau gộp biến thể, 413 lượt âm tính.
  Dùng gốc cuốn app tự đoán: recall **91,83% → 84,62%**, precision **97,70% → 99,15%**.
  Đây là đánh đổi precision/recall; không tuyên bố nhận đúng mọi tên. Ngưỡng chọn trước khi chấm held-out.
- Dev: bộ nhận diện mới 65/70 từ ngữ cảnh câu; materialization theo pronunciation của chính cuốn giữ 70/70,
  12/12 nhóm nhất quán. Hai phép đo này có lượng thông tin đầu vào khác nhau.
- Audio thật trên CPU: 52 câu. ASR Nhật **12/34 → 12/34**, Anh **27/37 → 27/37**; không có mục tiêu mới mất.
  19/24 MP3 Nhật và 28/28 MP3 Anh trùng SHA-256 với jpimpl. Không dùng ASR làm phán quyết phát âm của chủ sách.
- Pytest liên quan **740 passed / 0 FAILED**; toàn bộ **10665 passed / 0 FAILED / 0 error / 15 skipped / 2 xfailed**.
  Bốn partition có 10682 node ID, đối chiếu đầy đủ với collection; JUnit và `-rf` cùng xác nhận.
- Kotlin readaloud/vieneu: 555 passed / 0 failure / 1 skip trong 67 lớp; thêm 14 test SleepExtend đạt.
  Tổng JVM 569 passed / 0 failure / 1 skip, 68 lớp. Test ghi đè file dùng cùng bytecode trên Linux;
  các test còn lại, gồm JNI frontend, chạy Windows. 13 test UI về đồng hồ giả đạt.
- Fixture Nhật là tên phổ thông/câu tự viết; grep tên cấm trên mọi file thay đổi: 0. Mọi file thay đổi LF;
  compileall và diff check đạt. Ba file test ngoài tên Nhật chỉ thay thời gian bằng giá trị kiểm soát được,
  để ratchet test không phụ thuộc tải máy; không đổi baseline hay hành vi app của các tính năng đó.
- Import trực tiếp danh sách khóa: 57 file. Hash đầu lượt
  `f6b51ed26cb3443f5ae118ae3297d54df5b20c5be035d8bc8d8df2929fe096ea`;
  hash cuối `3d7e3f337b55366ae8ea92f5426c0fe0e8fed876a44bc2ae002a79510a2de0a9`.

Nhãn ngữ cảnh, câu truyện, nguồn/hash, số từng cuốn, giới hạn và log đầy đủ ở `codex/jpimpl2/report.md`
trong thư mục việc ngoài repo. Năm DB nguồn giữ nguyên hash. Chỉ cây dev, chưa commit/push; không dùng GPU.

# 08-11-2026 — latin166: kết hợp âm kêu và policy Nhật

Python/Kotlin giữ tiếng kêu, kéo dài và nói lắp trước fallback Nhật, đồng thời xử lý mảnh tên còn nguyên cạnh âm kêu. Cách đọc người nghe vẫn áp cuối. Không thêm từ/tên theo sách, không đổi bảng âm, ngưỡng hoặc policy JSON; hai nền dùng chung JSON/asset. Cache tăng một lần 10 → 11.

Chấm theo đường đọc hoặc phoneme cả câu bằng tham chiếu chung: primary 1.642/1.855 (4 mục mơ hồ trong 1.859); enaudit 607/671; soundfix mới 341/391. Giữ cả sửa đúng và hỏng mới; không diễn giải FP nhận diện tên thành lỗi đọc. Đây là nhãn model, chưa là phán quyết nghe. Nhãn, ngữ cảnh, số từng loại/cuốn và mọi hỏng mới ở report.md trong thư mục việc latin166 ngoài repo.

CPU: Nhật 12/34 mục tiêu trong 24 câu; Anh 27/37 trong 26 câu và hai đối chứng Việt ngoài mẫu số; 26 cặp tiếng kêu không tụt. Thu lại 104 WAV/MP3 trên hash cuối; ASR chỉ tái dùng khi byte giao/byte WAV tương ứng trùng SHA.

Kiểm cuối: Python liên quan 1.082 pass; toàn bộ 10.743 pass, 15 skip, 2 xfail, 0 FAILED/error, đủ 10.760 node rời nhau qua bốn log -rf. Kotlin liên quan 558 pass/1 skip; toàn :app:testDebugUnitTest 3.385 pass/4 skip, 0 failure/error. :app:assembleDebug, compileall và whitespace đạt.

Danh sách quality đọc trực tiếp có 59 mục; hash cuối 8b2743893f2ce90b706cc451ba14e2c5fe6c993df40083ac2b0d497e2b54fd7b. Chỉ cây dev; merge chưa commit.

# 08-11-2026 — giữ quyền của từng đường đọc

Direct JA giữ kết quả số, viết tắt, từ mượn và kính ngữ của lớp trước. Từ Nhật quen tách khỏi nhận diện tên; tên nối gạch kiểm từng phần. Khi chưa rõ gốc cuốn, tên đơn không tự đủ bằng chứng chỉ nhờ ba âm tiết. Laugh atom không nuốt nguyên âm khác nhau; chuỗi HOA không kéo dài giữ đường viết tắt. Python/Kotlin dùng chung JSON và asset; namespace Nhật 3, cache rules 12.

Nhãn model và phép chấm đường đọc/phoneme cả câu: primary 1.697/1.855, JA_NAME 463/491; enaudit 611/671; soundfix 350/391. Held-out mới gồm 1.080 lượt từ 13 cuốn, khóa nhãn SHA trước sửa luật: 951/1.076 xác định, JA_NAME 284/302. Mọi ô loại có mẫu >= max(base, soundfix); không xem đây là phán quyết nghe hoặc độ chính xác tự nhiên toàn Corpus. Chi tiết và mọi hỏng mới nằm trong thư mục việc ngoài repo.

CPU giữ Nhật 12/34, Anh 27/37 và 26/26 cặp tiếng kêu không tụt; hai clip Nhật khác byte được ASR CPU mới, các transcript tái dùng có checksum trùng. Không GPU/API trả tiền.

Kiểm cuối: Python đường đọc 1.093 pass; hai test khởi động dùng Event chờ callback thật thay thời gian ngủ cố định. Toàn bộ 10,754 pass, 15 skip, 2 xfail, 0 FAILED/error; đủ 10,771 node qua bốn partition rời nhau. Lượt đầu lộ một race trong test; giữ log đầu và kiểm lại nguyên hai partition chứa nó. Kotlin :app:testDebugUnitTest 3.386 pass/4 skip, 0 failure/error; compileall và whitespace đạt.

Quality đọc trực tiếp 59 mục, hash 00621d2fe93b76496889e6aea804c9944699e586f0011e1707a908a40b3c5a5b. HEAD a695c934e giữ nguyên; thay đổi chỉ ở nhánh dev, chưa commit.


### 08-11 dev/jppause: ranh giới âm trong tên Nhật

Đo CPU 10 cách × 40 câu × hai giọng mặc định, đủ 800 clip/CTC/ASR/UTMOS. Luật chung nối phoneme mỗi từ và hạ các trọng âm sau thành nhẹ, cùng JSON Python/Kotlin; namespace jp-fallback4. Khoảng yên trong từ ≥120 ms 12/160 → 4/160; ≥200 ms 7 → 1. Còn một khoảng 400 ms, chưa bảo đảm mọi tên hết ngắt. Sửa được 10 lần đọc từ, có 2 cảnh báo mới. ASR bộ cố định Nhật 12/34 → 13/34, Anh 27/37; Nhật có 4 mục mới đúng/3 mục mới sai.

Pytest cuối -rf: 10783 passed, 15 skipped, 2 xfailed, 0 failure/error; bộ liên quan 509 passed. Kotlin ReadAloud/VieNeu 558 passed, 5 skipped, 0 failure/error. Phonemizer Studio/Nghe ngay 40/40 cùng đầu vào mô hình; tokenizer native/portable 400/400 cùng ID. Hash đọc trực tiếp 60 mục: cc4adbb2075b5935e0d500989fb8ea11f5b9cbe3ebf6ab152ba459e6581cb097. Không commit; chỉ nhánh dev. Báo cáo chi tiết, 20 cặp MP3, trang nghe HTML và từng phép đo ở thư mục việc jppause ngoài repo; không đưa chữ truyện vào cây.

### 08-11 dev/jppause: sửa khoảng yên còn lại trong tên

Tái dùng đủ 800 WAV cũ; bốn ca còn lại có phoneme đã nối đúng, không có dấu câu/ngắt chunk trong tên. Seed +1 chỉ sửa 2/4 ca; Ishige còn 240/310 ms. Thêm sửa audio bằng CTC: chỉ rút run năng lượng thấp >=120 ms hoàn toàn trong một từ Nhật tự động về 80 ms, giữ 5 ms crossfade; confidence >=0,7, không dùng mốc ước lượng. Studio áp sau tempo và trước QA; Nghe ngay desktop áp trước ghép/căn mốc chữ. Cache thêm jp-name-audio1 cùng trạng thái có CTC. Android chưa có bước sửa waveform này.

Bộ cũ 4/160 -> 0/160; 40 tên held-out mới, chốt trước khi sinh, 7/160 -> 0/160; max tương ứng 400/340 -> 115 ms. 149/160 WAV không đổi SHA; mọi mẫu ngoài cửa sổ sửa của 160 WAV giữ nguyên. ASR từ hoàn chỉnh cũ 53/160 giữ nguyên, mới 50/160 -> 49/160 do Whisper ghép hai tên thành một từ; matcher chuỗi gấp mới giữ 68/160. UTMOS trên 4/7 cặp đổi byte giảm mean 0,048/0,022; không suy hết ngắt thành tăng độ tự nhiên.

Pytest liên quan -rf cuối: 715 passed, 3 skipped, 0 FAILED/error (718 node). Lượt đầu có 2 FAILED do kỳ vọng cache cũ, đã sửa và chạy lại nguyên bộ. Kotlin ReadAloud/VieNeu ép chạy Test task: 558 passed, 5 skipped, 0 failure/error. BPE native/portable 440/440 chuỗi khớp; render lại mã cuối 160/160 WAV trùng byte với bản đã đo; compileall và diff check đạt. Quality đọc trực tiếp 61 mục, hash 85f60b3009ade9d91783aaee8200cfa36e511fc7183f52f85100179fc924e8af. HEAD 8c25eedabe4b6c30c6bb18ecea5e6b40fa6776f0 không đổi, không commit. Báo cáo tiếng Việt, số từng ca, 20 mẫu/44 MP3 và listen.html ở thư mục việc jppause2 ngoài repo.

### 08-11 dev/latin166: hoàn tất giải quyết merge dev/jppause

Giữ luật HOA tiếng Anh, acronym theo ngữ cảnh, never_auto và các sửa frontend gi/o của latin166; nối tên Nhật theo jp-fallback4 và rút yên trong span tên bằng CTC của jppause. Khi tìm span, cả chuỗi đầy đủ và tiền tố dùng cùng luật sửa phoneme trong Studio, Nghe ngay và Kotlin. Bổ sung các file mới còn untracked ở hai nhánh mà code đã import; không thêm migration/legacy code. speech.json sinh từ merged code: chỉ 7 key VieNeu đổi do namespace đọc Nhật, không đổi chữ đọc/kỳ vọng engine khác.

Pytest toàn bộ -q -rf -o addopts=, 8 partition rời nhau: 10847 passed, 14 skipped, 2 xfailed, 0 FAILED/error. Đối chiếu JUnit với kế hoạch: đủ 10863/10863 node duy nhất, thiếu/thừa 0; exit cả 8 = 0; đếm 0 dòng FAILED. Bộ liên quan 88/88 pass. Kotlin :app:testDebugUnitTest ép chạy lại toàn bộ: 3394 passed, 4 skipped, 0 failure/error / 3398 test. Lượt Kotlin đầu có 1 failure do test streaming dùng đồng hồ thật: WAV vẫn trùng byte nhưng host load làm gộp flush. Ca fast-producer dùng clock giả sẵn có, giữ toàn bộ assertion, rồi chạy lại nguyên task; giữ XML/log đầu.

Audio merged code: ASR HOA 8/8 với scorer/giọng/model/seed cũ, sinh mới cả 8 WAV. Đủ 160 clip Nhật/320 lượt từ, gap >=120 ms = 0/320, dài nhất 115 ms; 12 clip có phoneme gi mới được sinh lại cùng seed/giọng, 148 clip chỉ reuse khi đầu vào/checksum khớp. Căn và render lại đủ 160 clip bằng helper sản phẩm rồi đo lại bằng align_measure.py. Studio/Nghe ngay khớp 160/160 đầu vào; JNI Kotlin/Python khớp 84/84 câu, gồm các ca gi/o cùng cảm thán Anh. Android chỉ áp phoneme, chưa có CTC waveform repair. Các số đo không phải gold phát âm Nhật hay phán quyết tự nhiên của người nghe.

compileall, git diff --check và staged diff check đạt. Qt offscreen, Java AWT headless, process con CREATE_NO_WINDOW; không dùng rm. Quality đọc trực tiếp 62 file: hash a0df5a7aa162f690bfd01b06a553559e2fa10e0aa2b5d72ff42499cc8700a5d4. Giữ HEAD 217103929f9a9206f8d2558a8ed709476f0c16fe, MERGE_HEAD da3f379c0a767576471def67a7cb8c86a8767696; không commit. File giải quyết và mã/test cần thiết staged bằng exact paths; ba file owner_reading untracked ban đầu được giữ nguyên. Log/XML/script và báo cáo chi tiết ở scratchpad/codex/merge166 ngoài repo.
# 2026-11-10: listener tone presets (dev/eqpreset)

Android, Web and Qt use one `tone_presets.json` catalog for seven Vietnamese voice presets, frequencies and Q. The listener library supports named presets, rename/duplicate/delete/undo/order, persistent drafts and independent per-book selection. Off bypasses filtering; Android PCM16 conversion preserves every source value.

Validation: 2,881 Vitest tests passed; TypeScript passed; 26 focused Android JVM/UI tests passed; 23 catalog/copy parity tests passed. Each actual platform DSP matched the shared 31-frequency fixture for seven presets at three sample rates (651 measurements per platform). Maximum reference deviation: Android 0.0103015474 dB, Qt 0.0103015 dB, WebAudio 0.0000017264 dB; the pairwise upper bound is below 0.020604 dB. Off is bit-exact in all three tests.

Qt `build.bat` compiled the app and ran all 18 suites: 2,141 passed, 3 failed, 1 skipped. Two failures reproduce the phonefix baseline (`Mini::test_minimizeSetting`, obsolete `Player.play()`, and `PlayerParity::test_more_help_history_tabs_and_back`). The third, `TitleBar::test_3_glyphsAreDrawnCentredAndNotFontsOrImages`, passed on a focused rerun. New tone suites passed: 8 core cases and 4 QML/gallery cases, including undo visibility. The full build gate remains red on the baseline fixtures; no release was made.

Gallery: light/dark, 360 dp, 130% text, list and bands on all three platforms; enlarged images reviewed. Final Android rerun includes the tone page's own Back button after editing a user preset (26 passed, no failures/errors/skips). The final Qt app loaded and drew Main.qml on a private hidden desktop without QML warnings. Locked implementation hash remains `0157775d5c45d0fb6100014adc0ed2828b2b9090b1c73725b7723eb5f44e4e16`.


## Activity ownership of native player subscriptions (2026-11-10)

PlayerRepo now tracks identity tokens for visible Activity instances. Starting B before stopping A keeps one core listener; duplicate starts/stops are idempotent and the last owner releases it. NativeActivity owns a token without retaining the Activity in the shared repo. AppShell only clears its own SettingsRepo.openAdvanced callback. PrepareState already counts watchers, AndroidPrepareSource removes its own listener, and device/export links already check identity before cleanup.

Validation: PlayerRepoTest 28 tests passed, including two overlapping-owner regressions. Restoring the old boolean behavior while retaining the test API caused exactly those two tests to fail (listener count 0 instead of 1). Physical-device bootstrap and the complete JVM suite are recorded in the external oppofix result.


## Unpaired native Studio (2026-11-10)

The Studio tab only offers notification preferences after a computer has been paired. An unpaired phone shows its header, one connection hint and the Connect computer action. Paired and listen-only computers retain their notification controls. IA2NavigationTest now supplies a CompanionRepo; omitting it previously hid the faulty branch in tests. Five cases passed; restoring the old condition makes the unpaired case fail on studio_notices. Web desktop App.tsx/StudioClosed and Qt StudioScreen.qml were inspected: both use the local Studio or an existing remote computer and have no unpaired-phone notification opt-in block. No web or Qt source change was necessary.
## 12-11-2026 — rel167b gallery blockers

- Corrected fractional toast clearance feedback (25px/26px oscillation at 400px), and prevented toast focus clearance from scrolling the page behind fixed surfaces or a locked document. Recorded raster/CSSOM coordinates reproduce the clearance regression in a unit test.
- All web dropdown content now uses the shared opening-release guard: releasing the pointer which opened a menu cannot select a newly appeared item. Fresh press/release and keyboard Enter remain covered.
- RHYTHM resolves glyph edges at 1/16px while retaining its 2px threshold. A real-font Vietnamese fixture passes equal spacing and fails a planted 4px shift. The previous whole-pixel Canvas metric reported 2.21875px where the 4x raster shows 1.25px.
- Related validation: TypeScript clean; 58 Vitest tests passed. Focused pytest: 179 passed, 2 skipped, plus two stale generated parity documents; regenerated both and reran parity: 30 passed, 2 skipped. Full build and release-gate evidence is recorded in the rel167b handoff.
- Baseline 0.4.166 (bd07ae23d) focused gallery: 0 findings/errors. The toast-clearance code is identical there; timing-dependent failures were reproduced on the retained 0.4.167 build, with screenshots and native input traces. No quality implementation changes.

## Gold replay half-credit preservation (2026-11-13)

`gold_replay.py` now keeps half-credit speaker choices in the saved generator
targets as `speaker_alt: [{speaker, credit: 0.5}]`. The response returned to the
host retains its production schema. Gold rows containing only half-credit
choices use a fallback and record `speaker_credit: 0.5` in the saved target.
Existing training artifacts were not rebuilt.

Verification: 11 focused synthetic tests in `test_gold_replay_half_credit.py`
passed. Coverage includes book spelling, NPC normalization, duplicate choices,
thought/narration, all-half choices, critic isolation, and UTF-8/LF output.
The test loader compiles the real replay class and helpers with standard
library dependencies; it does not start workers, models, or GPU jobs.


## Class-conditioned text pronunciation gate (2026-11-12, dev/g2pgate)

The fixed public gate contains 744 source-verified tokens/name groups (739
casefold-distinct): Japanese 377, Korean 20, Chinese/Sino-Vietnamese 80,
Western 100, English loans 19, acronyms 21, mixed tokens 88 and Vietnamese
controls 39. Corpus contributes 551 tokens and hand18 gold speaker lists 193.
The 442 calibration identities represent 81 distinct source hashes. Private
sentences remain outside the repository; only isolated tokens, hashes,
phonemes and class/owner metadata are distributed. See
`tests/data/g2pgate/README.md` and `tests/test_g2pgate.py`.

The oracle is policy code and explicit owner decisions, not independent human
phoneme annotation. The app materializes its own readings from roster origins;
precomputed automatic reading aliases are not replay inputs. The normalization
follows judge2's text scorer, with corrected acute-probe placement. Case-sensitive
Vietnamese words and two-letter capital codes are scored normally. The only
remaining mismatching token is the ambiguous platform/initialism `KAKI`.
`LV` also lacks its original numeral/code context but matches the default.
Two personal names without source-language evidence remain ambiguous in 12
calibration rows. These declarations do not certify automatic language inference
or acoustic pronunciation.

Against the baseline G2P code at d8710f23f, harvested-token mismatches are
20/744 -> 1/744 (19 unambiguous -> 0), and calibration source replay is
7/442 -> 0/442. Historical sent phonemes are retained unchanged; this is
regeneration of the source, not rewriting old clips. The runtime preserves
generated syllable positions across both frontends, uses only Vietnamese
sea-g2p probes for replacement phones, and keeps the split Japanese-name route.
The cache namespace is direct-en7. Instrumentation observed 3,984 probes over
596 valid Vietnamese syllables, with all 2,674 emitted probe results matching
the independent Vietnamese phone oracle. These are probe counts, not repairs.

Validation with the pinned Python and `-rf`: the gate passed all 11 tests with
the private calibration source; the final full suite for touched/reading modules
passed 4,725 tests in 81 files, with 7 skipped and 0 FAILED. The earlier entire
repository run recorded 12,131 passed, 2 FAILED, 21 skipped and 2 xfailed. Its
two failures were an order-dependent assumption of an unpatched upstream
frontend and stale text parity expectations. The test now gets pristine upstream
functions while retaining its original assertions; text/BPE fixtures were
refreshed without audio generation, and their sea-g2p metadata now records the
installed version instead of an obsolete literal. Both failing files passed in
the final module suite. The entire repository run was not repeated after these
test/fixture-only fixes; the app implementation hash did not change. Compileall
and diff checks passed. Kotlin was explicitly rerun: 22 passed, 7 skipped,
0 failures/errors. Host JNI parity remains unverified (Rust JNI pins 0.9.1;
the Python gate uses sea-g2p 0.10.0). No acoustic evaluation or release was made.

Quality implementation hash, read from the worktree's `_internal`:
`bd0e02b4d872503d8a396c7b2b3a5befde44b0fd8f7def641c56e5b280a1eced`
-> `3b089118a842cc74fb53736357c704fa41c5bf656d7cf109a7442e22de4ccb48`.

### Full repository and host JNI verification (2026-11-12)

The entire repository suite was rerun after c227bcfaf's fixture fixes, from
the worktree's `_internal`, using the pinned Python, private calibration source
and `-o addopts= -q -rf`: **12133 passed, 0 FAILED, 21 skipped, 2 xfailed,
4 warnings**, exit 0, in 2881.80 seconds. Both earlier failing tests passed.
No implementation failure required a runtime fix.

Host parity now runs the actual Kotlin `VieneuUnits` -> `SeaG2p` /
`PhonemePolicy` -> Rust JNI sea-g2p **0.9.1**, against desktop sea-g2p **0.10.0**.
Both use dictionary SHA-256
`4346e690d0711ebc5231e7a42c5c88aaf6e40377e894b4617c018fd81c6f4096`.
The comparison is exact per-unit UTF-8 phoneme strings and unit boundaries:
no normalization, accepted alternatives or ambiguity exemptions.

| Class | Rows | Before mismatches | Final mismatches |
|---|---:|---:|---:|
| Japanese | 377 | 0 | 0 |
| Korean | 20 | 0 | 0 |
| Chinese/Sino-Vietnamese | 80 | 0 | 0 |
| Western | 100 | 0 | 0 |
| English loans | 19 | 0 | 0 |
| Acronyms | 21 | 0 | 0 |
| Mixed | 88 | 0 | 0 |
| Vietnamese | 39 | 0 | 0 |
| Private calibration | 442 | 0 | 0 |

The 442 calibration identities still represent 81 distinct source hashes.
Seven rows differ only in intermediate `Ban`/`BAN` -> `ban` case, and three
in the English tag around `do`; their exact final phonemes and unit boundaries
match. These spelling diagnostics are separate from phoneme mismatches.
Source inspection found 36 identical Rust files and an identical single-text
`Normalizer.normalize` body; 0.10.0 adds binding/feature and C-ABI support.
The JNI pin is retained because no differing phoneme behavior was measured;
no Android engine/library download pins were changed.

`scripts/generate_g2p_parity.py` freezes all 744 desktop outputs in
`tests/data/g2pgate/desktop_parity.json`; each also matches the existing gate
runner byte for byte. `--check` verifies the snapshot. Optional private
calibration generation validates every source hash and refuses output inside
the repository. Book readings/rulings are transported inputs, as in production;
this does not certify independent language inference or acoustic pronunciation.

`G2pGateParityTest` asserts the public fixture and optional private replay on
JVM/host JNI. `ABOOK_REQUIRE_G2P_PARITY=1` makes missing native inputs fail CI.
`prepare_sea_g2p_android.py --host-only` builds JNI without the NDK and preserves
previous source trees. The final rebuilt host DLL was tested with all
`vieneu.*` and `readaloud.*` JVM tests: **583 passed, 2 skipped, 0 failures/errors**.
The skips require an optional private punctuation corpus and Supertonic model;
all native G2P/parity tests actually ran. The older 209-sentence native text
contract also passed. Commands are in `tests/data/g2pgate/README.md`.
Compileall, the two scripts' lint and exact fixture regeneration checks passed.

The quality list was read from code (69 entries). Before and after this follow-up,
the worktree implementation hash remained
`3b089118a842cc74fb53736357c704fa41c5bf656d7cf109a7442e22de4ccb48`.
This measures host JNI text parity, not Android runtime performance or audio.
No emulator, real phone, release, model upload or push was used.

## integ168: G2P/collapse integration and stale CMake caches (2026-11-12)

Merged `dev/g2pgate` and `dev/collapsefix` into `dev/integ168`, starting at
`6398020de`. Both merges were conflict-free. The ASR implementation and its
locked-name regression test file have identical Git blobs in the starting
release, collapse branch and integrated result; the second merge records ancestry.

All five CMake configure entrypoints (desktop, QWindowKit, audiobench, decoder
profiling and release-gate Qt tests) now call one `drop_stale_cmake_cache.py`
helper. A missing cached C/C++ compiler or linker invalidates only
`CMakeCache.txt` and `CMakeFiles`, after containment checks. Intact caches and
other build products are preserved. The three edited batch files retain CRLF.
Nine synthetic helper cases cover missing tools, intact tools, mixed tool
states, absent caches, containment and CLI paths with spaces/parentheses.
Final cache/VCVars/batch checks: **15 passed, 0 failures/errors**, exit 0.

The integrated parity fixture needed only its `quality_hash` metadata refreshed:
all 744 case payloads remain identical. Desktop snapshot checks pass for all
744 public tokens and 442 private calibration rows; private-source G2P pytest:
**11 passed, 0 failures/errors**. Rebuilt host Rust JNI and reran all
`vieneu.*`/`readaloud.*` JVM tests with strict native parity enabled:
**583 passed, 0 failures/errors, 2 skipped**, 74 XML files. Both native G2P gate
tests executed, with zero exact phoneme/unit-boundary mismatches across all
1,186 rows. The skips require an optional punctuation corpus and Supertonic
model. The first Gradle attempt was blocked before tests by missing local
TypeScript dependencies; a local locked `npm ci --ignore-scripts` resolved it
without changing source or lockfiles.

The implementation list was read from code (69 entries). The starting hash was
`bfbf90f934c2a5d8bce0622b29ed1752d74cbe56a5e81e3f1969dac98f5c762b`;
after the G2P merge it is
`d73a53dedf1b2ea61384c23951423763bc1894694a1dd2f2a8aa69e5da416b92`,
unchanged by collapse/cache/test work. Compileall, new-file Ruff checks and diff
checks passed. Validation uses CPU, offscreen/software Qt and headless JVM;
host JNI text parity does not measure phone performance or audio quality.
No protected sibling worktree, release, push or GPU was used.

Final full repository pytest, one invocation with `-o addopts= -q -rf`:
**12,146 passed, 0 FAILED, 0 errors, 21 skipped, 2 xfailed, 4 warnings**,
exit 0, 3,384.08 seconds. All 12,169 XML cases reconcile with the summary;
the actual `^FAILED` line count is zero. This invocation omitted the private
calibration environment variable; its 442 rows were covered separately above.
The warnings are a duplicate synthetic EPUB entry, an AST invalid-escape
deprecation, the queue test's deliberate thread `SystemExit`, and a mock music
server's `accept()` timeout. Their source files match `6398020de`; no unrelated
warning fixes were made. There are no final failures to classify against baseline.

The full run started with 12.56 GiB free RAM and numerical thread pools capped
at two. Shared free RAM later fell to 3.76 GiB in the recorded samples; no new
heavy workload was launched during that dip. External evidence (full/focused
logs and XML, exact JNI reports, source-derived hash list and RAM samples) is
retained in the task's external `scratchpad/codex/integ168` directory.


## 2026-11-12 g2pfix privacy repair (dev/integ168b)

Supersedes the earlier claims that calibration.json contained no sentence data:
it contained recoverable whole-sentence phonemes and sentence hashes. Those
claims were incorrect. Private context is now outside this public repository in
Corpus/g2pgate/calibration_context.json; the public calibration holds token phones
only. The new branch squashes sanitized content onto 6398020de and must not be
pushed until Lead reviews it. Historical probe-oracle and parity measurements
above are not evidence for the repaired code. Current validation is recorded in
the final repair entry; heavy checks are pending AC power.

### Finding 2: preserve native level-tone 1 and primary stress

Each changed text.json entry below follows the same requirement: preserve the
unaltered sea-g2p Vietnamese reading if its segmental phones match the probe.
Frames are a sorted set, so replacement entries can move adjacent indices;
frame/tokenizer snapshots are regenerated from these exact phonemes.

- `$.g2p[342].phonemes`: `sha256:808674b62caaa59a913841a1a73bc8d3035cc2a8125c74c60fe45217a2a64c06` -> `sha256:16b92616b04ca75e93f4cd36e41aef8bfac93ff8180729b7d308e383aae666c2` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.g2p[343].phonemes`: `sha256:808674b62caaa59a913841a1a73bc8d3035cc2a8125c74c60fe45217a2a64c06` -> `sha256:16b92616b04ca75e93f4cd36e41aef8bfac93ff8180729b7d308e383aae666c2` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.g2p[344].phonemes`: `sha256:179fcf9f906d7624074581c8fb00eb1ab3e1ebc78ea6c423a0b96287f6f94b34` -> `sha256:706656c7afe5626c2ac649f6e559a49fa6eed0fba1182c95e107096640ae02ac` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.g2p[355].phonemes`: `sha256:f73227f5c7386b871da9374438a3aebdb10506b7920dfaa036902e77106568c3` -> `sha256:6d19d18487a8ed9e0771ec5232901022e8e9e07aadc8c2ee08daeee69057fbe6` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.g2p[356].phonemes`: `sha256:f73227f5c7386b871da9374438a3aebdb10506b7920dfaa036902e77106568c3` -> `sha256:6d19d18487a8ed9e0771ec5232901022e8e9e07aadc8c2ee08daeee69057fbe6` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.units[156].units[0].phonemes`: `sha256:808674b62caaa59a913841a1a73bc8d3035cc2a8125c74c60fe45217a2a64c06` -> `sha256:16b92616b04ca75e93f4cd36e41aef8bfac93ff8180729b7d308e383aae666c2` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.units[157].units[0].phonemes`: `sha256:808674b62caaa59a913841a1a73bc8d3035cc2a8125c74c60fe45217a2a64c06` -> `sha256:16b92616b04ca75e93f4cd36e41aef8bfac93ff8180729b7d308e383aae666c2` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.units[158].units[0].phonemes`: `sha256:179fcf9f906d7624074581c8fb00eb1ab3e1ebc78ea6c423a0b96287f6f94b34` -> `sha256:706656c7afe5626c2ac649f6e559a49fa6eed0fba1182c95e107096640ae02ac` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.units[168].units[0].phonemes`: `sha256:f73227f5c7386b871da9374438a3aebdb10506b7920dfaa036902e77106568c3` -> `sha256:6d19d18487a8ed9e0771ec5232901022e8e9e07aadc8c2ee08daeee69057fbe6` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.units[169].units[0].phonemes`: `sha256:f73227f5c7386b871da9374438a3aebdb10506b7920dfaa036902e77106568c3` -> `sha256:6d19d18487a8ed9e0771ec5232901022e8e9e07aadc8c2ee08daeee69057fbe6` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.units[170].units[0].phonemes`: `sha256:ce00f4af88a5c0c00ef655ea9685769581558c1e4e282c5cc92c73d7b5f63744` -> `sha256:4867909344b80c74f2e9f0320e2d24e27d649c94db9acc927c11246154bce4cd` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.units[204].units[0].phonemes`: `sha256:7c7438d02b0fad8ce5cc881b29a2701a8e71ca0882f81e2dd38dc99b1e70aa67` -> `sha256:93ffd9d84a5f7d5b879b0d290e89aa03c22d4b852557ac0e4900d562d3de5a94` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.units[205].units[0].phonemes`: `sha256:7c7438d02b0fad8ce5cc881b29a2701a8e71ca0882f81e2dd38dc99b1e70aa67` -> `sha256:93ffd9d84a5f7d5b879b0d290e89aa03c22d4b852557ac0e4900d562d3de5a94` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.units[206].units[2].phonemes`: `sha256:3e21adf74fa5c65a7f10fd59641e2a004f97aaf66cd7c36084dc7a0361680a36` -> `sha256:0689375c150435ad8badcca122ca121b348614b80e3b7878eda6e907eb3747d4` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.units[231].units[0].phonemes`: `sha256:015a8b82e1b1b6413dbba069153f5a5419fa91cea08173e7dde830bbd621a819` -> `sha256:8f8c08a4ecd9b493107bc16db6cfa54016b448d4c1deedf033834de4e1177802` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.units[232].units[0].phonemes`: `sha256:015a8b82e1b1b6413dbba069153f5a5419fa91cea08173e7dde830bbd621a819` -> `sha256:8f8c08a4ecd9b493107bc16db6cfa54016b448d4c1deedf033834de4e1177802` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.units[233].units[1].phonemes`: `sha256:d2340d6d423a19a6974a535d083e9a95d892f276fd1830f12af3fd9e15ff9d36` -> `sha256:d9dc1cb11ccc331dd0708955d4a79a108a82ea4db7f71d7bf6dce3397ba3b5bd` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.frames[36].cap`: `238` -> `240` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.frames[36].phonemes`: `sha256:f73227f5c7386b871da9374438a3aebdb10506b7920dfaa036902e77106568c3` -> `sha256:6d19d18487a8ed9e0771ec5232901022e8e9e07aadc8c2ee08daeee69057fbe6` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.frames[37].cap`: `156` -> `158` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.frames[37].phonemes`: `sha256:179fcf9f906d7624074581c8fb00eb1ab3e1ebc78ea6c423a0b96287f6f94b34` -> `sha256:706656c7afe5626c2ac649f6e559a49fa6eed0fba1182c95e107096640ae02ac` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.frames[38].cap`: `360` -> `362` (native Vietnamese stress/level marker retained; derived frames follow).
- `$.frames[38].phonemes`: `sha256:808674b62caaa59a913841a1a73bc8d3035cc2a8125c74c60fe45217a2a64c06` -> `sha256:16b92616b04ca75e93f4cd36e41aef8bfac93ff8180729b7d308e383aae666c2` (native Vietnamese stress/level marker retained; derived frames follow).

### Findings 3-9

- 3 (0282f1295): roster rulings apply by token position, not by spelling, on
  desktop and phone. "An nói: I want an apple." keeps English `æn` for the
  article and `ˈaːn` for the name; "I can not do it, Can." keeps `kˈæn` for the
  modal verb (`tests/test_g2p_ruling_positions.py`, Kotlin
  `GeneratedSyllablesTest`).
- 4 (1108b646f): Studio text normalization runs inside the book rulings, so the
  same sentence reads like Reader/phone (`tests/test_g2p_studio_rulings.py`).
- 5 (25a3691fe): generated-syllable corrections align with each Studio chunk and
  emotion-tag fragment; a line over 256 characters is tested
  (`tests/test_g2p_studio_chunks.py`).
- 6 (4020e4055): legacy Ð becomes Đ in unaccented and NFD syllables; gate tokens
  Ði, Ðang, Ðan, Ðông added (`tests/test_g2p_legacy_d.py`).
- 7 (f889e98d3): G2pGateParityTest passes `BookReadings` with rulings; Kotlin
  unit tests for `levelProbe`, `restoreGeneratedSyllables` and
  `ruledVietnameseWords` run without JNI; release_gate sets the parity
  variables and fails before Gradle when an input is missing
  (`tests/test_g2p_release_inputs.py`).
- 9 (ae71dc701): the gate oracle (`tests/g2pgate_dictionary.py`) reads native
  entries from sea-g2p's SEAP dictionary and uses only tone variants the
  dictionary attests; it shares no code with `_level_probe`. Spellings without
  an attested syllable (Mylene, Rhasa, Fitts, Magali, Celestina heads) get no
  Vietnamese target. Level-tone p/t/c/ch syllables are invalid Vietnamese: the
  probe and the oracle both refuse them. 39 expected entries changed; each keeps
  sea-g2p's level-tone 1 or stress, or drops a fabricated target. The gate
  runner and the parity generator use production-shaped rulings (roster names
  within the table only); still zero gate failures.
- 8 (0ec5f5f15): `tests/test_g2p_desktop_parity.py` regenerates the public cases
  and compares them with `desktop_parity.json` (it failed on the stale snapshot
  before regeneration). The fixture no longer carries a `quality_hash`: the hash
  recorded in the integ168 entry above (`d73a53de…`) was already stale at
  `0118ef100` (`663ab9eb…`, audio_io.py). Regeneration changed 34 cases in
  level-tone 1/stress only and the rulings field of 117; no segmental phonemes.

Quality implementation hash (69 entries, read from code): `6398020de`
`bfbf90f9…`, old `dev/integ168` tip `663ab9eb…`, this branch after finding 9
`5cec934fcc5fd76da4125ad26cf6fa232d84c30cb832446ebe3684542b79d76b`. The branch
changes locked files (phoneme_policy, vieneu, tts, english_policy) and must wait
for runs to finish before reaching production.

The 442-row private replay was not run: the external judge1 `clips.json`
named by `G2PGATE_CALIBRATION_SOURCE` is not on this machine; the test reports
SKIPPED with that reason. The private context itself is committed only in the
private Corpus repository.
## 13-11-2026 — secfix2: continuation requires freshly selected sources

- Base: `dev/secfix`, `29008c77c`. Continuation returns settings and an original-folder hint with no source discovery. Web/Studio (including Android's web Studio) and Qt open a fresh picker; remote clients upload their selection. `next_chapters` filters only that selection. New books retain byte copies under `sources/<chapter>/`; shared readings use these copies. Restored drafts do not automatically reopen a picker or probe a hint.
- Updated continuation fixtures to use contained source copies, preserving voice/reading/pin and spelling-merge assertions. Added picker/cancel, selected-file, remote-upload, and hostile-hint no-I/O coverage. Removed the obsolete source-repoint script, test and documentation references. Old external-source rejection and browser pairing HTTP 410 remain.
- Final related Python run: `pytest -rf -o addopts=` over 18 files: **331 passed, 3 skipped, 0 failures, 0 errors** (334 collected). XML: external `scratchpad/codex/secfix2/pytest-final.xml`. Includes continuation, remote Studio/paths, secfix path/origin, multi-volume creation, CLI, creation lock, project files/workshop, shared readings, narrator creation, pairing/TLS, shared strings and both UI parity suites.
- Final Vitest: **8 files, 45 passed, 0 failed, 0 pending**; JSON: external `scratchpad/codex/secfix2/vitest-final.json`. TypeScript `tsc --noEmit`, `gen_ui_strings --check`, `ui_parity --check`, `ui_parity_qt --check` all exit 0. Existing `ui/node_modules` used; no junction created. No Gradle or Qt build/test run; native build validation is deferred to Lead's combined pass.
- Used only `D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe -X utf8` for Python. Read `QUALITY_IMPLEMENTATION_FILES` from code: **70 entries**. Quality hash before: `dc26dc0c1ba77f08ccefdedfd0a810644ed19cc4a9327e09e48fc0e814cd8502`; after: `a73a9758856baf13fd70f04b55b4d4eb441cccb4f66e585102827b120d37b250` (`webui/store.py` changed). This is a dev change awaiting the end of any production run. No version bump, push or migration.

## 12-11-2026 — release guard coverage

- Removed the a85 expected-failure snapshot proposal: it demanded an unsupported old-pin conversion and did not test the current code-for-book contract. No conversion code exists in StudioSetup to remove. Existing snapshot/pin safety tests remain mandatory.
- Removed the design-only first-use relay expected-failure test. Its desired pairing protocol is not implemented on this branch; deleting the expected failure does not claim the first-use MITM gap is fixed. Pairing protocol work remains separate; existing pairing and TLS tests remain mandatory.
- Removed the two optional audiotsm comparator cases, which always skipped without an undeclared package. The same module retains direct measured pitch (1%), LUFS (0.3 dB), exact duration and finite-output assertions. No extra dev dependency is needed.
- Pytest skip ceiling: released report had 19; removing the two comparator cases sets the ceiling to 17. No full-suite remeasurement on battery. Xfailed ceiling is zero; skip reasons are logged with -rfs. Installer end-to-end CLI is now a separate gate row; tap-audit and phone-frame unit tests are in testpaths.
- Qt end-ellipsis is a hard rule in `ui_parity_qt.py --check`, matching the web DESIGN rule. 80 Qt findings cleared through the shared catalog: 58 ellipsis keys folded into their existing plain twins, 10 values stripped; web export/music/player strings that used the same keys follow. Parity exemptions now have per-pair ceilings (`scripts/ui_parity_limits.json`) and unused exemptions fail; 46 unused entries removed.
- Not run on battery: Gradle (Android unit, Roborazzi verify), Qt build/QuickTest, Vitest/typecheck (no lock-matched ui/node_modules in this worktree), full release gate.

## 0.4.168 integration fixes and focused checks (2026-11-13)

Integrated 69 distinct source commits on the scrubbed 0.4.167 base 645239bda.
The advertised 21-commit TN lineage includes 84b3cf29b, already the final
integ168b pick; it contributes 20 additional commits. Source task reports are
retained, with sentence phonemes replaced by hashes and local paths scrubbed.

The combined tree retains the actual secfix certificate-confirmation tests;
the earlier gatefix note about an unimplemented first-use protocol describes
that source branch before secfix integration. Continuation requires a fresh
source selection. Shared motion also covers the added continuation, pairing
confirmation and sleep timer controls.

The ten package declarations that differed from installed metadata now record
the measured runtime, including CTranslate2 4.8.2. No installed package changed.
Runtime provenance checks both ASR packages and tests compare all registry
lock versions against actual installed metadata.

Host environment switches are isolated in the tests. Offline restoration is
tested with absent and pre-existing flags. Source input is NFC per line after
invisible-marker removal, before segmentation and stable identities; TTS and
Reader comparisons normalize tokens and listener readings on both platforms.
Reader cache rules advance from 18 to 19 for the integrated TN/NFC behavior.

Focused invocations (overlapping coverage, not additive): 172 runtime/offline/
reading tests; 146 UI/security/gate integration tests with 3 optional/perf skips;
63 gate/input tests; 15 public-scanner tests; 149 final Unicode, segmentation
and English-reading tests; 75 Reader/cache tests with 1 optional network skip.
All these invocations have zero failures. Android build and the complete
release gates follow the predecessor's resource handoff; their final measured
counts belong to the external integration result, not these focused totals.

The new public scanner keeps exact hash-bound reviews: 948 baseline-identical
files, 114 with inherited flagged strings and 29 with reviewed new technical
or synthetic content. A regression proves changed bytes invalidate a review
and no review can waive a corpus match. The independent strict HEAD scan
reported zero findings and zero pending audio before the final focused fixes;
the final HEAD scan remains a required release step.

Quality implementation hash: 5fb3551d9dac1a6f84072eff3baccedf76ec32cb4bb2f77e9d7a94cfa2f710bf
to dbb460d54ae91c9da882d7a565bac191c47919913818ff93eb19292016243e64.
This is an isolated development pipeline change; no production project or
running analysis was stopped or resumed. No acoustic quality claim follows
from these text and mock-adapter checks.

### 0.4.168 gallery integration follow-up

Focused browser regressions: 38 passed. Semantic Tailwind text sizes now retain
their independent foreground colors. Selected picker labels use the supported
bold weight; chapter metadata shares the title baseline; long button labels
remain centered; search dividers stay inside the content column.
Popover note alignment only uses visible choices from the same menu body.
A nested/hidden-menu fixture accepts correctly aligned bodies and still catches
an injected 8 px note offset in both themes and viewport sizes. No rule tolerance
or release failure list was relaxed. Full release verification remains pending.

### fix168and: durable Android playback teardown

PlaybackService destruction no longer drains the place/disk queues on the main
looper. Close and teardown sync only a small final-place journal independent of
Store's monitor, then drain both queues on a process-owned executor with one
timeout. A timeout leaves writes running. Cold Store initialization replays the
journal before publishing root. Local writer/sequence tokens make recovery
idempotent and prevent an old undeleted journal from rewinding a newer cursor;
those tokens are excluded from state sync payloads. Deleted/moved profiles are
not resurrected.

Service/widget initialization, widget library/artwork work, tone commits, rate
writes, record mutation/reload and held-record checks now run off main. Player
snapshots and prepared-queue installation remain on main; late record reloads
cannot reopen a book after Close or a newer load. Media3 commands are lazy so
reading service state does not eagerly construct Android objects.

The focused JVM/Robolectric sweep passed 40 tests. With Store held and both
writers blocked, onDestroy returned in 9 ms and the final cursor was already
journaled; both queues completed after the lock was released. Cold service
create/destroy returned in 8 ms. A shared 100 ms flush budget measured 101 ms,
and its writes still completed afterward. These are controlled Windows JVM
measurements, not Android-device latency claims. Cold-recovery, deleted-profile,
stale-journal, Close, initialization, tone/rate, record-switch and resumption
regressions are included. Final full-module XML and pytest totals are recorded
in result.md and PROGRESS.md.

The complete app testDebugUnitTest run passed: **442 suites, 3734 tests =
3719 passed / 0 failures / 0 errors / 15 skipped**. Fresh suite timestamps are
2026-11-13T11:39:28.284Z through 11:44:44.255Z; wall time was 6m55s. No exclusions
or skips were introduced. Earlier full-run source-scan, lazy-initialization,
pairing-fixture, cache-expectation, caption-spacing and fixture-drain failures
were corrected and included in this final run.

Related pytest: **74 passed / 0 failed / 0 errors / 0 skipped**, invoked with
`-q -rf` across Android debug-ID, listening-record/reliability/write, and both
leak-scanner modules. Actual progress markers and collected node IDs both total
74, with zero FAILED summary lines. LF/control audit checked all 33 changed/new
files without findings; git diff --check passed.

Quality implementation hash before/after is unchanged:
`dbb460d54ae91c9da882d7a565bac191c47919913818ff93eb19292016243e64`.
