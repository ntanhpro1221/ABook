"""Studio text normalization must receive the book's adjudicated readings."""
import pytest

from abook.config import build_settings
from abook.database import ProjectDB
from abook.readaloud.phoneme_policy import Rulings, remembered_rulings
from abook.tts import TTSCoordinator


@pytest.mark.parametrize("source,expected", [
    ("I can not do it, Can.", "Can."),
    ("An nói: I want an apple.", "An nói:"),
])
def test_studio_keeps_the_roster_occurrence_during_text_normalization(tmp_path, monkeypatch, source, expected):
    coordinator = TTSCoordinator(build_settings(), ProjectDB(tmp_path / "project.sqlite3"), lambda _: None)
    coordinator._shared_rulings = (Rulings(names={"an", "can"}),)
    monkeypatch.setattr(coordinator, "_row_speaks_english", lambda _: True)
    spoken, _ = coordinator.spoken_text_with_anchors({"text": source})
    assert expected in spoken
    if "can" in source:
        assert "<en>can</en>" in spoken
        assert "<en>Can</en>" not in spoken
    else:
        assert "want an apple." in spoken
        assert "<en>An</en>" not in spoken
    assert remembered_rulings() is None
