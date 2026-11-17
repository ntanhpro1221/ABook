""""NPC X" and "X" are two different people everywhere a speaker name is normalized or compared.

Dropping the NPC mark turned a nameless extra into a named character (main cast, a borrowed voice) and let a trusted
gold label be "repaired" into another person without tripping its guard. All names are synthetic.
"""
from __future__ import annotations

from collections import Counter

from abook import speaker_labels
from abook.analysis import _canonical_speaker
from abook.character_registry import canonical_speaker_names


def test_the_analysis_never_strips_the_npc_mark_even_before_a_latin_name() -> None:
    assert _canonical_speaker("NPC Sergeant Bell") == "NPC Sergeant Bell"
    assert _canonical_speaker("NPC: Torvin") == "NPC: Torvin"
    assert _canonical_speaker("NPC bác gác cổng") == "NPC bác gác cổng"
    assert _canonical_speaker("narrator") == "NARRATOR"


def test_the_name_merge_keeps_an_npc_apart_from_the_named_person() -> None:
    targets = canonical_speaker_names(Counter({"Torvin": 9, "NPC Torvin": 2}), "")
    assert targets.get("NPC Torvin", "NPC Torvin") != targets.get("Torvin", "Torvin")


def test_trusted_labels_treat_the_npc_mark_as_identity() -> None:
    key = speaker_labels.name_key
    assert key("NPC Torvin") == key("npc: torvin") == key("Npc_Torvin")
    assert key("NPC Torvin") != key("Torvin")
    labels = speaker_labels.SpeakerLabels({"s1": {"kind": "dialogue", "speaker": "NPC bác gác cổng", "text_sha256": "h"}})
    row = {"stable_id": "s1", "text_sha256": "h"}
    assert labels.allows(row, "Npc Bác Gác Cổng")
    assert not labels.allows(row, "Bác Gác Cổng"), "bỏ tiền tố là đổi sang người khác"
