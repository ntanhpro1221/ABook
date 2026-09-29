"""scripts/publish_model.py: model có lớp khuôn chat / tham số / giấy phép (nền Qwen3-8B cần khuôn qwen3 của Ollama - tạo chỉ
từ GGUF thì ra khuôn Jinja thô, đo 29-09) vẫn đăng được - khuôn ghi đúng từng byte để đi cùng app, tham số và giấy phép vào
Modelfile; lớp Studio không tạo lại được (adapter...) thì từ chối."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import publish_model

TEMPLATE = b"{{ .Prompt }}<|im_end|>\n"
PARAMS = rb'{"repeat_penalty":1,"stop":["\u003c|im_start|\u003e","\u003c|im_end|\u003e"],"temperature":0.6}'


def _ollama(root: Path, layers: dict[str, bytes]) -> None:
    blobs = root / "blobs"
    blobs.mkdir(parents=True)
    entries = []
    for media, data in layers.items():
        digest = hashlib.sha256(data).hexdigest()
        (blobs / f"sha256-{digest}").write_bytes(data)
        entries.append({"mediaType": media, "digest": f"sha256:{digest}", "size": len(data)})
    manifest = root / "manifests" / "registry.ollama.ai" / "library" / "thu-8b" / "latest"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"layers": entries}), encoding="utf-8")


def test_the_template_and_parameters_travel_with_the_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ollama(tmp_path / "models", {
        "application/vnd.ollama.image.model": b"GGUF" * 64,
        "application/vnd.ollama.image.template": TEMPLATE,
        "application/vnd.ollama.image.license": b"Apache License 2.0",
        "application/vnd.ollama.image.params": PARAMS,
    })
    monkeypatch.setenv("OLLAMA_MODELS", str(tmp_path / "models"))
    monkeypatch.setattr(publish_model, "TEMPLATES", tmp_path / "templates")
    monkeypatch.setattr(publish_model, "quantization", lambda _name: "Q4_K_M")
    notes = tmp_path / "the.md"
    notes.write_text("# thẻ", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["publish_model.py", "thu-8b:latest", "abook-analyzer:v9", "--notes", str(notes),
                                      "--out", str(tmp_path / "out")])

    assert publish_model.main() == 0

    assert (tmp_path / "templates" / "abook-analyzer-v9.gotmpl").read_bytes() == TEMPLATE
    modelfile = (tmp_path / "out" / "abook-analyzer-v9" / "Modelfile").read_text(encoding="utf-8")
    assert modelfile.startswith("FROM ./abook-analyzer-v9.Q4_K_M.gguf\nTEMPLATE \"\"\"{{ .Prompt }}")
    assert 'PARAMETER stop "<|im_start|>"\nPARAMETER stop "<|im_end|>"\n' in modelfile
    assert "PARAMETER temperature 0.6" in modelfile and 'LICENSE """Apache License 2.0"""' in modelfile


def test_a_layer_the_studio_cannot_rebuild_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ollama(tmp_path / "models", {
        "application/vnd.ollama.image.model": b"GGUF" * 64,
        "application/vnd.ollama.image.adapter": b"lora",
    })
    monkeypatch.setenv("OLLAMA_MODELS", str(tmp_path / "models"))
    with pytest.raises(SystemExit, match="không tạo lại được"):
        publish_model.model_layer("thu-8b:latest")
