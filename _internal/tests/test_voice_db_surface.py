"""Every stand-in for the project database offers every read `TTSCoordinator` makes, with the rows `ProjectDB` returns.

The list of reads is derived from the source (`tests/voice_db_surface.py`), never kept by hand: when the name reader began to
ask for the character list (`studio_names.book_name_readings_for_project`), `tts_pool.ReadOnlyVoiceDB` did not have it, so the
voice preview answered 422 and a synthesis-pool worker failed every line.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from abook.config import build_settings
from abook.tts import TTSCoordinator
from abook.tts_pool import ReadOnlyVoiceDB
from abook.webui.reading_preview import PreviewVoiceDB
from tests.test_listener_speakers import _book
from tests.voice_db_surface import missing_reads, tts_database_surface

# One way to build each stand-in over a project file, by class name. A new stand-in must be added here to be compared.
STAND_INS = {
    "ReadOnlyVoiceDB": lambda path: ReadOnlyVoiceDB(path),
    "PreviewVoiceDB": lambda path: PreviewVoiceDB(path, None, None, None, None),  # nothing overlaid: the book as it is
}


def _stand_in_classes() -> list[type]:
    """`ReadOnlyVoiceDB` and every class derived from it that is alive in this process (the preview script defines its own copy)."""
    found: list[type] = [ReadOnlyVoiceDB]
    for known in found:
        found.extend(child for child in known.__subclasses__() if child not in found)
    return found


def _arguments(db: Any) -> dict[str, tuple]:
    """What each read is called with here. A read the coordinator gains has no entry, which fails the comparison below."""
    profile = int(db.voice_profile_by_key("narrator")["id"])
    return {
        "list_chapters": (), "list_segments": (), "list_characters": (), "list_voice_profiles": (),
        "list_pronunciations": (0.58,), "voice_profile": (profile,), "voice_profile_by_key": ("narrator",),
    }


def _rows(result: Any) -> Any:
    return [dict(row) for row in result] if isinstance(result, list) else dict(result)


def test_the_derived_list_holds_the_reads_of_the_name_path() -> None:
    surface = tts_database_surface()
    # Direct reads, and the three made through `studio_names` (chapter text and the character list) - the ones that were missed.
    assert {"list_pronunciations", "list_voice_profiles", "voice_profile", "voice_profile_by_key", "path"} <= surface
    assert {"list_chapters", "list_segments", "list_characters"} <= surface


def test_every_stand_in_offers_every_read() -> None:
    classes = _stand_in_classes()
    assert {cls.__name__ for cls in classes} == set(STAND_INS), "a new stand-in: add it to STAND_INS so its rows are compared too"
    for cls in classes:
        assert missing_reads(cls) == [], cls


def test_the_shim_offers_nothing_but_those_reads() -> None:
    public = {name for name in dir(ReadOnlyVoiceDB) if not name.startswith("_")}
    assert public == tts_database_surface() - {"path"}


@pytest.mark.parametrize("name", sorted(STAND_INS))
def test_a_stand_in_returns_the_rows_the_project_database_returns(tmp_path: Path, name: str) -> None:
    paths, db = _book(tmp_path)
    db.upsert_pronunciation(surface="Lucien", normalized_surface="lucien", spoken_form="Lu-xi-en", confidence=0.9, locked=True)
    db.upsert_pronunciation(surface="Aalto", normalized_surface="aalto", spoken_form="An-tô", confidence=0.2)
    stand_in = STAND_INS[name](paths.db)
    arguments = _arguments(db)

    assert set(arguments) == tts_database_surface() - {"path"}, "a read without arguments here is a read nobody compares"
    for read, given in arguments.items():
        expected = _rows(getattr(db, read)(*given))
        assert expected, f"{read}: the sample book has nothing to compare"
        assert _rows(getattr(stand_in, read)(*given)) == expected, read
    assert Path(stand_in.path) == Path(db.path)


def test_a_coordinator_refuses_a_database_missing_one_of_its_reads() -> None:
    """The check `conftest` installs: a partial test double fails where it is handed over, with the missing reads named."""
    partial = SimpleNamespace(list_pronunciations=lambda _minimum: [])

    with pytest.raises(AssertionError) as refused:
        TTSCoordinator(build_settings(), partial, lambda _message: None)

    assert "SimpleNamespace" in str(refused.value) and "list_characters" in str(refused.value)
