# Casting invariants

`base_5c008b85a.json` records fresh casting from the base tree. Fresh-cast comparisons use the speakers and the partition
of lines sharing a voice; keys and both kinds of seed are checked against the current voice registry. Catalog order or
an engine version update therefore does not require changing this fixture.

`base_locked_5c008b85a.sqlite3.gz` is a real SQLite database cast and finalized by the archived `5c008b85a` Python modules.
The adjacent JSON records its uncompressed SHA-256 and speaker/voice/seed snapshot; the adjacent `speaker_labels.json`
file contains the trusted labels installed before casting, including the original `NPC Cha Rita` and `NPC Anh trai`
inputs. The base canonicalizer removes the NPC role mark from the stored name.

This project was seeded with the real `continuation.seed_casting` path from an earlier part. Rita has an unknown gender
on every new segment and receives her known female gender and a deliberately different female voice from that part.
The fixture preserves the exact voice keys that were locked then. A new registry must never rewrite those keys on resume.

To reproduce the locked fixture, archive `_internal/abook` from `5c008b85a`, put that archive's `_internal` first on
`sys.path`, write `base_source.json` with `{"commit":"5c008b85a"}` beside the archive's `_internal` directory (or use a
checkout at that commit), then run `tests/test_a_locked_cast_keeps_voices_and_seeds.py <output-stem> --locked` with `runpy`.
Use the project's pinned interpreter and a hidden detached process, as required by the workspace rules.

The resume test opens that base SQLite under the current code and calls the real `BookPipeline.run` through the finalized
casting branch. Model and TTS boundaries are fakes; all segments, characters and voice profiles, gold protections, and
every synthesis seed must survive unchanged. A separate fresh continuation test exercises the current code's gender,
voice and gold handling instead of merely reading the fixture.
