"""Chọn model đọc hiểu truyện cho MỘT cuốn ở trình tạo sách (01-10, chủ sách: "phần studio ưu tiên hơn") - thử model mới
trên một cuốn thật mà không đổi model mặc định của app (đổi mặc định là quyết định của chủ sách, file khoá config.py)."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

TAGS = {"models": [
    {"name": "qwen3-8b-qlora-v6-e1-q4:latest", "size": 5_027_784_160,
     "details": {"family": "qwen3", "parameter_size": "8.2B", "quantization_level": "Q4_K_M"}},
    {"name": "nomic-embed-text:latest", "size": 274_000_000, "details": {"family": "nomic-bert"}},
    {"name": "abook-analyzer:v3", "size": 4_280_000_000, "details": {"family": "qwen3", "parameter_size": "4.0B"}},
]}


class _Tags(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - tên của BaseHTTPRequestHandler
        body = json.dumps(TAGS).encode("utf-8") if self.path == "/api/tags" else b"{}"
        self.send_response(200 if self.path == "/api/tags" else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        pass


class _Studio:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def settings_overrides(self) -> dict:
        return {"analysis": {"base_url": self.base_url}}


@pytest.fixture()
def app(tmp_path: Path):
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening
    from abook.webui.server import App
    from tests.test_webui_listen_and_sync import FakeRunner

    ollama = ThreadingHTTPServer(("127.0.0.1", 0), _Tags)
    threading.Thread(target=ollama.serve_forever, daemon=True).start()
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "lib")})
    application = App(preferences=preferences, runner=FakeRunner(), token="t",
                      listening=Listening(tmp_path / "prefs" / "l.json"))
    application.studio = _Studio(f"http://127.0.0.1:{ollama.server_address[1]}")
    source = tmp_path / "truyen"
    source.mkdir()
    (source / "001.txt").write_text("Chương 1\n\n“Đi thôi,” Lucien nói.\n", encoding="utf-8")
    yield application, source / "001.txt"
    ollama.shutdown()


def _settings(application, created: dict) -> dict:
    return json.loads((application._book(created["id"]) / "book_settings.json").read_text(encoding="utf-8"))


def test_the_wizard_lists_the_models_in_ollama_with_the_default_first(app) -> None:
    application, _chapter = app
    view = application.analysis_models()
    assert view["reachable"] and view["default"] == "abook-analyzer:v3"
    assert [model["name"] for model in view["models"]] == ["abook-analyzer:v3", "qwen3-8b-qlora-v6-e1-q4:latest"], \
        "mặc định đứng đầu, model nhúng (embedding) không phải model đọc hiểu"
    assert view["models"][1]["parameters"] == "8.2B" and view["models"][1]["quantization"] == "Q4_K_M"


def test_a_book_keeps_the_model_chosen_for_it_and_the_studio_ollama(app) -> None:
    from abook.webui.server import ApiError

    application, chapter = app
    chosen = application.create({"paths": [str(chapter)], "title": "Thử 8B", "profile": "high_quality",
                                 "analysisModel": "qwen3-8b-qlora-v6-e1-q4:latest"})
    analysis = _settings(application, chosen)["analysis"]
    assert analysis["model"] == "qwen3-8b-qlora-v6-e1-q4:latest"
    assert analysis["base_url"] == application.studio.base_url
    plain = application.create({"paths": [str(chapter)], "title": "Thử mặc định", "profile": "high_quality"})
    assert _settings(application, plain)["analysis"]["model"] == "abook-analyzer:v3"
    with pytest.raises(ApiError) as missing:
        application.create({"paths": [str(chapter)], "title": "Thử lạ", "profile": "high_quality",
                            "analysisModel": "khong-co:latest"})
    assert missing.value.status == 400
