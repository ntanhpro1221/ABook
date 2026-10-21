from pathlib import Path

from abook.analysis import _scope_local_speaker
from test_speaker_pass_pipeline import FakeOllama, LABELS, make_pass, make_project, speakers


def test_pass_local_speakers_have_chapter_scope_without_changing_prompts(tmp_path: Path, monkeypatch) -> None:
    db = make_project(tmp_path / "p")
    labels = {**LABELS, "“Dậy đi nào.”": "NPC_LOCAL:lính gác", "“Ai đó?”": "NPC_LOCAL:lính gác",
              "“Mưa to quá.”": "NPC_LOCAL:lính gác"}
    ollama = FakeOllama(labels)
    make_pass(db, ollama, monkeypatch).run(lambda: False)
    first, second, _ = speakers(db)
    assert first[3] == first[5]
    assert first[3] != second[1]
    chapters = db.list_chapters()
    for label, chapter in ((first[3], chapters[0]), (second[1], chapters[1])):
        assert label == _scope_local_speaker("NPC_LOCAL:lính gác", {"chapter_id": chapter["id"]}, "speaker_pass")
    assert any("NPC_LOCAL:lính gác" in prompt for prompt in ollama.prompts)
    assert all("NPC_LOCAL::" not in prompt and "speaker_pass::" not in prompt for prompt in ollama.prompts)
