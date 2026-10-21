from pathlib import Path

import pytest
import requests

from abook.analysis import AnalysisModelDigestError, OLLAMA_TRANSPORT_RECONNECT_ATTEMPTS
from test_speaker_pass_pipeline import FakeOllama, LABELS, make_pass, make_project


class TagsOutage(FakeOllama):
    def __init__(self) -> None:
        super().__init__(LABELS)
        self.until_failure = -1
        self.faults = 0

    def get(self, url, timeout=0):
        if self.until_failure == 0 and self.faults:
            self.faults -= 1
            raise requests.ConnectionError("Ollama tắt giữa hai câu")
        if self.until_failure > 0:
            self.until_failure -= 1
        return super().get(url, timeout)


@pytest.mark.parametrize("phase", ["before", "after"])
@pytest.mark.parametrize("faults", [1, OLLAMA_TRANSPORT_RECONNECT_ATTEMPTS + 1])
def test_digest_transport_outage_uses_chat_retries_and_server_revival(tmp_path: Path, monkeypatch, phase: str, faults: int) -> None:
    db = make_project(tmp_path / "p")
    ollama = TagsOutage()
    pass_ = make_pass(db, ollama, monkeypatch)
    pass_._ready()
    ollama.until_failure = 0 if phase == "before" else 1
    ollama.faults = faults
    revived = []
    pass_.analyzer.ensure_server = lambda: revived.append(True) or True
    assert pass_.run(lambda: False) == 3
    assert not ollama.faults
    assert bool(revived) == (faults > OLLAMA_TRANSPORT_RECONNECT_ATTEMPTS)
    assert len(db.speaker_pass_done_chapters()) == 3


def test_a_real_digest_mismatch_before_chat_fails_without_retry(tmp_path: Path, monkeypatch) -> None:
    db = make_project(tmp_path / "p")
    ollama = TagsOutage()
    pass_ = make_pass(db, ollama, monkeypatch)
    pass_._ready()
    ollama.digest = "sha256:wrong"
    waited, revived = [], []
    monkeypatch.setattr(pass_, "_sleep", waited.append)
    pass_.analyzer.ensure_server = lambda: revived.append(True) or True
    with pytest.raises(AnalysisModelDigestError, match="changed before speaker request"):
        pass_.run(lambda: False)
    assert not waited and not revived and not ollama.prompts
