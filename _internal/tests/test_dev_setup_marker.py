from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from scripts import dev_setup_marker as command


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    """Tiny files exercise real contract hashing; only dependency imports are fake."""
    contract = command.runtime_contract
    root = tmp_path / "runtime"
    (root / ".venv").mkdir(parents=True)
    monkeypatch.setattr(sys, "prefix", str(root / ".venv"))
    monkeypatch.setattr(sys, "executable", str(root / ".venv/Scripts/python.exe"))
    data = b"test model payload"
    digest = hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(contract, "UTMOS_CHECKPOINT_SHA256", digest)
    monkeypatch.setattr(contract, "PERCEPTUAL_BASE_MODEL_FILES", tuple(
        (repo, rev, name, len(data), digest)
        for repo, rev, name, _, _ in contract.PERCEPTUAL_BASE_MODEL_FILES
    ))
    monkeypatch.setattr(contract, "VOICE_MODEL_FILES", tuple(
        (name, len(data), digest) for name, _, _ in contract.VOICE_MODEL_FILES
    ))
    hub = root / "models/huggingface/hub"
    for repo, rev in (
        (contract.WAV2VEC2_CACHE_REPOSITORY, contract.WAV2VEC2_CACHE_REVISION),
        (contract.TIMM_CACHE_REPOSITORY, contract.TIMM_CACHE_REVISION),
        (contract.VIENEU_CACHE_REPOSITORY, contract.VIENEU_CACHE_REVISION),
    ):
        ref = hub / repo / "refs/main"
        ref.parent.mkdir(parents=True)
        ref.write_text(rev, encoding="utf-8")
    files = list(contract.PERCEPTUAL_BASE_MODEL_FILES) + [
        (contract.VIENEU_CACHE_REPOSITORY, contract.VIENEU_CACHE_REVISION, name, size, sha)
        for name, size, sha in contract.VOICE_MODEL_FILES
    ]
    for repo, rev, name, _, _ in files:
        target = hub / repo / "snapshots" / rev / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    model = root / "models/utmosv2"
    model.mkdir()
    (model / contract.UTMOS_CHECKPOINT_FILENAME).write_bytes(data)
    (model / contract.PERCEPTUAL_CACHE_MARKER_FILENAME).write_text(json.dumps({
        "schema_version": contract.PERCEPTUAL_CACHE_SCHEMA_VERSION,
        "checkpoint_revision": contract.UTMOS_CHECKPOINT_REVISION,
        "checkpoint_sha256": digest.upper(),
        "wav2vec2_revision": contract.WAV2VEC2_CACHE_REVISION,
        "timm_backbone_revision": contract.TIMM_CACHE_REVISION,
        "model_config": contract.UTMOS_MODEL_CONFIG,
        "fold": contract.UTMOS_MODEL_FOLD,
        "seed": contract.UTMOS_MODEL_SEED,
    }), encoding="utf-8")

    class Distribution:
        def __init__(self, name):
            self.name = name
            self.version = contract.CRITICAL_RUNTIME_DISTRIBUTIONS[name][1]

        def read_text(self, name):
            if self.name == "utmosv2" and name == "direct_url.json":
                return json.dumps({"url": contract.UTMOS_SOURCE_URL,
                                   "vcs_info": {"commit_id": contract.UTMOS_SOURCE_COMMIT}})
            return None

    monkeypatch.setattr(contract.importlib.metadata, "distribution", Distribution)
    torch = SimpleNamespace(version=SimpleNamespace(cuda="12.8"),
                            cuda=SimpleNamespace(is_available=lambda: True), __file__="fake/torch.py")
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setattr(contract.importlib, "import_module", lambda name:
                        torch if name == "torch" else SimpleNamespace(__file__=f"fake/{name}.py"))
    return root


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_writes_marker_accepted_by_full_contract(runtime):
    assert command.main(["--runtime", str(runtime)]) == 0
    payload = json.loads((runtime / ".setup_complete").read_text(encoding="utf-8"))
    assert payload["schema_version"] == command.runtime_contract.SETUP_SCHEMA_VERSION
    assert payload["installed_by"] == "dev-check"
    assert payload["python"] == str(Path(sys.executable).resolve())
    assert payload["internal_root"] == str(command.INTERNAL_ROOT)
    assert set(payload["components"]) == set(command.runtime_contract.CRITICAL_RUNTIME_DISTRIBUTIONS)
    for name, (_, version) in command.runtime_contract.CRITICAL_RUNTIME_DISTRIBUTIONS.items():
        assert payload["components"][name]["version"] == version
    assert payload["components"]["utmosv2"]["direct_url"]["vcs_info"]["commit_id"] == (
        command.runtime_contract.UTMOS_SOURCE_COMMIT
    )
    assert command.runtime_contract.runtime_contract_errors(runtime) == []
    assert not list(runtime.glob("*.part"))


@pytest.mark.parametrize("existing", [False, True])
def test_dry_run_changes_nothing(runtime, existing, capsys):
    if existing:
        (runtime / ".setup_complete").write_bytes(b"existing marker")
    before = snapshot(runtime)
    assert command.main(["--runtime", str(runtime), "--dry-run"]) == 0
    assert snapshot(runtime) == before
    assert '"installed_by": "dev-check"' in capsys.readouterr().out


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("broken", [
    "voice", "checkpoint", "base_model", "cache_marker", "dependency", "version", "source", "cuda",
])
def test_contract_failures_never_write(runtime, monkeypatch, capsys, broken, existing):
    contract = command.runtime_contract
    if existing:
        (runtime / ".setup_complete").write_bytes(b"preserve old marker")
    if broken == "voice":
        (runtime / "models/huggingface/hub" / contract.VIENEU_CACHE_REPOSITORY / "refs/main").unlink()
    elif broken == "checkpoint":
        (runtime / "models/utmosv2" / contract.UTMOS_CHECKPOINT_FILENAME).write_bytes(b"wrong")
    elif broken == "base_model":
        repo, rev, name, _, _ = contract.PERCEPTUAL_BASE_MODEL_FILES[0]
        path = runtime / "models/huggingface/hub" / repo / "snapshots" / rev / name
        path.write_bytes(b"x" * path.stat().st_size)  # Same size, wrong hash.
    elif broken == "cache_marker":
        (runtime / "models/utmosv2" / contract.PERCEPTUAL_CACHE_MARKER_FILENAME).write_bytes(b"{}")
    elif broken == "dependency":
        def missing_import(name):
            raise ImportError(f"missing {name}")
        monkeypatch.setattr(contract.importlib, "import_module", missing_import)
    elif broken in {"source", "version"}:
        original = contract.importlib.metadata.distribution
        def wrong_distribution(name):
            distribution = original(name)
            if broken == "source" and name == "utmosv2":
                distribution.read_text = lambda filename: '{"url": "wrong source"}'
            if broken == "version" and name == "vieneu":
                distribution.version = "0.0.0"
            return distribution
        monkeypatch.setattr(contract.importlib.metadata, "distribution", wrong_distribution)
    elif broken == "cuda":
        monkeypatch.setattr(sys.modules["torch"].cuda, "is_available", lambda: False)
    before = snapshot(runtime)
    assert command.main(["--runtime", str(runtime)]) == 1
    assert snapshot(runtime) == before
    assert "[FAIL]" in capsys.readouterr().err


def test_rejects_other_runtime_without_creating_it(tmp_path, capsys):
    target = tmp_path / "not-installed"
    assert command.main(["--runtime", str(target)]) == 1
    assert not target.exists()
    assert "interpreter:" in capsys.readouterr().err


def test_atomic_publish_failure_preserves_marker(runtime, monkeypatch):
    marker = runtime / ".setup_complete"
    marker.write_bytes(b"original")
    before = snapshot(runtime)
    def fail_replace(*args):
        raise PermissionError("test publish blocked")
    monkeypatch.setattr(command.os, "replace", fail_replace)
    assert command.main(["--runtime", str(runtime)]) == 1
    assert snapshot(runtime) == before
