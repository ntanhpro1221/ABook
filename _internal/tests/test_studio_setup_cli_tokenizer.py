from pathlib import Path

import pytest

from abook.webui import studio_setup


@pytest.mark.parametrize("runtime_override", [False, True])
def test_cli_installs_pinned_speaker_tokenizer_in_the_job_runtime(tmp_path: Path, monkeypatch, runtime_override: bool) -> None:
    downloads, app_root = tmp_path / "downloads", tmp_path / "app"
    runtime = tmp_path / "job-runtime" if runtime_override else app_root / "runtime"
    if runtime_override:
        monkeypatch.setenv("ABOOK_RUNTIME", str(runtime))
    else:
        monkeypatch.delenv("ABOOK_RUNTIME", raising=False)
    installed, fetched = [], []

    def fetch(item, target, progress, cancelled):
        fetched.append((item, target))
        return target

    setup = studio_setup.StudioSetup(downloads, app_root, gpu=lambda: None, fetch=fetch)
    monkeypatch.setattr(setup, "install_published_model", installed.append)
    monkeypatch.setattr(studio_setup, "StudioSetup", lambda *_args, **_kw: setup)
    args = ["--install-model", studio_setup.SPEAKER_MODEL, "--downloads", str(downloads)]
    assert studio_setup.main(args) == 0
    assert installed == [studio_setup.SPEAKER_MODEL]
    assert fetched == [(studio_setup.SPEAKER_TOKENIZER,
                        runtime / "models" / studio_setup.TOKENIZER_FOLDER / studio_setup.TOKENIZER_FILE)]
    fetched.clear()
    assert studio_setup.main(["--install-model", "abook-analyzer:v4", "--downloads", str(downloads)]) == 0
    assert not fetched
