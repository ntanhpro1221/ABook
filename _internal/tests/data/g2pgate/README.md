# Public token G2P gate

Only isolated tokens/names and their own phonemes are distributed. calibration.json
contains the same isolated token population as tokens.json, with token phones.
No sentence phones, sentence word lists, sentence hashes or sentence identities
are allowed. Book identifier hashes in tokens.json identify books, not sentences.

The former calibration fixture leaked sentence transcriptions. It was removed by
rebuilding dev/integ168b from 6398020de with a sanitized squash. Do not publish the
old dev/integ168 history. Nothing in this repair authorizes a push.

All 442 historical calibration rows, sentence hashes and contextual rulings are
private, in D:/Novels/ABook/Corpus/g2pgate/calibration_context.json. To replay them,
set G2PGATE_CALIBRATION_SOURCE to the external judge1 clips.json, and optionally
G2PGATE_CALIBRATION_FIXTURE to a different private context path. Missing private
inputs produce a SKIPPED result with an explicit reason. Never copy them here.

Run the CPU token test with the pinned Python:

    python -X utf8 -m pytest -q -rs -rf tests/test_g2pgate.py tests/test_public_fixture_privacy.py

The privacy guard scans every tracked or untracked public fixture under data,
fixtures and testdata directories, including non-JSON UTF-8 files and gzip text.
It rejects sentence/context fields and at least eight consecutive phonetic
syllables. Existing regression fixtures outside tests/data have exact-byte
exceptions in scripts/public_fixture_exceptions.json; these are printed explicitly,
never wildcard exemptions. The G2P data directory cannot be exempted. Review any
changed exception against its authored test/generator before updating its hash.
The historical unsafe calibration blob is rejected by a dedicated regression test.

expected.json is a policy-derived token regression oracle, not human phoneme gold.
Normalized metrics ignore stress, punctuation, length and level-tone 1; exact
regressions separately cover those details. No audio quality claim follows.

# Desktop and phone parity

scripts/generate_g2p_parity.py --check checks the desktop token snapshot.
For private parity pass --calibration-source, --calibration-context and
--private-out; all private inputs and output must be outside the checkout.
The private report can contain sentence phones and must also remain private.
Build host JNI with scripts/prepare_sea_g2p_android.py --host-only (AC power only).
Set ABOOK_REQUIRE_G2P_PARITY=1, ABOOK_SEA_G2P_LIB and ABOOK_SEA_G2P_DICT before
running G2pGateParityTest. Missing required native inputs must fail the release gate.
Historical parity measurements in TEST_REPORT predate this repair and do not
validate the repaired frontend; see its repair section for current results.

`stretches_parity.json` adds 115 synthetic cries and lexical regressions: all Vietnamese vowels
and five written tones, short-vowel codas, bare short-vowel cries, decomposed
Unicode, and ordinary syllables such as cứu/lưu/soóc/goòng that must stay intact.
`generate_g2p_parity.py` generates/checks it alongside the 744-token
fixture. `G2pGateParityTest.allMarkedStretchesMatchDesktopExactly` checks the same
exact phonemes and unit boundaries through the phone JNI pipeline. Bare ă/â/y
cries use sustainable a/ơ/i with their written tone, rather than letter names.
This is frontend parity on CPU; no regenerated speech or acoustic gain is claimed.
