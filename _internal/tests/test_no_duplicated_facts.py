"""Facts that must exist exactly once.

Five bugs in this project have been one value stated twice and the copies drifting: the
version pin across three files, the torch pin across two, "what counts as a delta" across
analysis and database, an ASR rule across two gates, and a flag that named a branch instead
of reading the verdict. None was visible by reading one file.

These pin the two that an audit of the package found still open. `scripts/audit_duplicated_facts.py`
lists the rest for a human to judge; most are coincidence.
"""

from __future__ import annotations

from abook import quality_policy, tts
from abook.database import CHAPTER_POST_ENCODE_QUALITY_STAGE


def test_removed_pitch_ranges_are_not_reintroduced() -> None:
    assert not hasattr(tts, "VOICE_VARIANT_PITCH_FLOOR_HZ")
    assert not hasattr(tts, "VOICE_VARIANT_PITCH_CEILING_HZ")


def test_the_chapter_quality_stage_has_one_definition() -> None:
    """Writer and reader must look the evidence up under the same name."""
    assert quality_policy.CHAPTER_QUALITY_STAGE is CHAPTER_POST_ENCODE_QUALITY_STAGE
