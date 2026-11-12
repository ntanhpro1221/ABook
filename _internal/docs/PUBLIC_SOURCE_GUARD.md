# Public source checks

Run from the checkout root with the project's Python interpreter:

    <python> -X utf8 _internal/scripts/leak_scan.py
    <python> -X utf8 -m pytest _internal/tests/test_leak_scan.py -rf

The scanner reads all tracked text files, including docs, comments, gold labels and
pending patches. The Corpus check uses the original audit's Unicode word tokenizer,
seven consecutive words, four Vietnamese marked letters per candidate line and the
same excluded Corpus directories. It checks every shingle; the historical audit
sampled one third. Two gaps of the audit are closed: `\uXXXX`/`\xNN` escapes are
decoded before matching, and a line without diacritics is matched against the
Corpus folded to bare letters (both hid real book sentences in tests and pending
patches). Corpus is discovered beside the main Git directory or through
ABOOK_CORPUS. Absence prints SKIPPED explicitly; IPA and machine checks still run.
It runs in one process and never loads a model (about a minute with the Corpus).

IPA lines with at least eight IPA-bearing tokens require review. The phoneme
fixtures named one by one in `IPA_REVIEWED_FILES` were reviewed (their sentences
are written for the tests and stay under the Corpus check); any other file fails.
The machine name comes from COMPUTERNAME at runtime. Tailnet and home LAN addresses
outside the explicit sample list fail; new examples should use TEST-NET addresses
(192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24).

Reviewed false positives are individual stripped-line SHA-256 entries in
`scripts/leak_scan_allowlist.json`. Each entry states its reason. These cover
independently authored fixtures, public book titles, grammar and code expressions;
they do not exempt a directory or a future changed line. --raw includes these
matches in the failure count. --json writes counts and locations without excerpts.

Audio is not transcribed. `scripts/leak_scan_pending_audio.json` lists recordings
known to speak book text, by git blob. While a listed file is unchanged the scanner
prints `PENDING AUDIO` (and fails with --strict-audio). The 30 voice previews in
`abook/assets/voice_previews/` are listed: regenerate them with
`scripts/make_voice_previews.py` (GPU; the probe sentences are now self-written),
copy them in at a batch boundary (this changes the quality hash), then remove the
entries.

## Optional pre-push installation

From a checkout where the owner wants this hook:

    git config core.hooksPath _internal/scripts/hooks

This setting is not installed by the scrub task. Check an existing hooksPath before
replacing it (`git config --get core.hooksPath`). Set ABOOK_PYTHON if the
interpreter is outside the checkout/main worktree; set ABOOK_CORPUS if the private
corpus is elsewhere.

The hook scans every non-deleted local tip supplied by Git, using --rev to read that
commit's files and review manifest. A clean working tree cannot hide a leak in the
commit being pushed. This guard checks tips, not history or remote release assets.
