"""Hộp "Đổi giọng" gửi KHOÁ giọng, không gửi nhãn (soát a94, F1): người nghe thấy "Bảo Trang" / "Supertonic F1", máy chủ chỉ biết
"baotrang" / "F1". Máy chủ không nhận nhãn (một nguồn sự thật) mà từ chối bằng lời tiếng Việt; sách .abook (không có xưởng) từ chối
giọng lạ ngay lúc nhận thay vì ghi rồi để Studio bỏ lặng lẽ lúc áp. Cả đường nghe thử cũng chỉ nhận khoá."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest

from abook import listener_overrides as overrides
from abook.voice_catalog import castable_engine_voices
from abook.webui import book_edits, book_wishes, store, server as server_module, voice_picker
from abook.webui.humanize import voice_label
from abook.webui.library import book_id
from tests.test_book_wishes import _post as _wish_post
from tests.test_book_edits import imported  # noqa: F401 - fixture
from tests.test_listener_voices import MALE
from tests.test_voice_try import _noah, studio_app  # noqa: F401 - fixture
from tests.test_webui_listen_and_sync import _request

HEADERS = {"X-Ebook-Token": "t"}
# Một giọng nam của mỗi máy đọc khác (NOAH là nam): ZeroTTS và Supertonic.
ENGINE_KEYS = {"zerotts": "giahuy", "supertonic": "M4"}


def _voice(server, paths, route: str, body: dict):
    status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(paths.root)}/{route}", headers=HEADERS, body=body, timeout=10)
    return status, json.loads(data)


@pytest.fixture()
def installed(monkeypatch):
    """Cả hai mô-đun giọng đã tải (route và hộp cùng thấy)."""
    monkeypatch.setattr(server_module, "engine_installed", lambda engine: True)
    monkeypatch.setattr(voice_picker, "engine_installed", lambda engine: True)


def test_every_voice_of_the_picker_carries_the_key_the_server_accepts(tmp_path: Path, installed) -> None:
    paths, _db = _noah(tmp_path)
    view = voice_picker.voice_choices(paths.root, "NOAH")
    by_key = {voice["key"]: voice for voice in view["voices"]}
    assert len(by_key) == len(view["voices"]), "khoá không trùng nhau"
    for engine_voice in castable_engine_voices("male"):
        shown = by_key[str(engine_voice["name"])]
        assert shown["name"] == engine_voice["label"] != shown["key"], "nhãn để hiện, khoá để gửi"
    narrator = voice_picker.voice_choices(paths.root, "NARRATOR")
    assert all(voice["key"] and voice["name"] == voice_label(voice["key"]) for voice in narrator["voices"])


@pytest.mark.parametrize("engine", sorted(ENGINE_KEYS))
def test_choosing_a_voice_of_another_engine_works_by_key_and_never_by_label(studio_app, installed, engine: str) -> None:  # noqa: F811
    _app, server, paths, _launcher, _runner = studio_app
    key = ENGINE_KEYS[engine]
    label = voice_label(key)
    assert label != key

    status, answer = _voice(server, paths, "voice", {"character": "NOAH", "preset": label})
    assert status == 400 and answer["error"] == server_module.VOICE_PROBLEMS[overrides.UNKNOWN_PRESET], "nhãn không phải khoá"
    assert "voices" not in overrides.read_overrides(paths.root), "không ghi gì khi từ chối"
    status, answer = _voice(server, paths, "voice", {"character": "NOAH", "preset": "không-có-giọng-này"})
    assert status == 400 and answer["error"] == server_module.VOICE_PROBLEMS[overrides.UNKNOWN_PRESET]

    status, answer = _voice(server, paths, "voice", {"character": "NOAH", "preset": key})
    assert status == 200 and answer["preset"] == key
    assert overrides.read_overrides(paths.root)["voices"]["NOAH"]["preset"] == key


@pytest.mark.parametrize("engine", sorted(ENGINE_KEYS))
def test_a_voice_that_still_needs_downloading_is_told_so_by_key(studio_app, monkeypatch, engine: str) -> None:  # noqa: F811
    """Với nhãn, `_needs_download` không bao giờ chạy (soát a94): theo khoá thì máy báo đúng "cần tải thêm"."""
    _app, server, paths, _launcher, _runner = studio_app
    monkeypatch.setattr(server_module, "engine_installed", lambda name: name != engine)
    key = ENGINE_KEYS[engine]
    status, answer = _voice(server, paths, "voice", {"character": "NOAH", "preset": key})
    assert status == 400 and "cần tải thêm" in answer["error"]
    status, answer = _voice(server, paths, "voice/preview", {"character": "NOAH", "preset": key})
    assert status == 400 and "cần tải thêm" in answer["error"]


@pytest.mark.parametrize("engine", sorted(ENGINE_KEYS))
def test_trying_a_voice_of_another_engine_takes_the_key_only(studio_app, installed, engine: str) -> None:  # noqa: F811
    _app, server, paths, _launcher, _runner = studio_app
    key = ENGINE_KEYS[engine]
    status, answer = _voice(server, paths, "voice/preview", {"character": "NOAH", "preset": voice_label(key)})
    assert status == 400 and answer["reason"] == overrides.UNKNOWN_PRESET
    assert answer["error"] == server_module.VOICE_PROBLEMS[overrides.UNKNOWN_PRESET]
    status, answer = _voice(server, paths, "voice/preview", {"character": "NOAH", "preset": key})
    assert status == 200 and answer["url"], answer


# ---- sách .abook (không có xưởng): ý muốn mang giọng lạ bị từ chối ngay -------------------------------------------------------


def test_a_package_refuses_an_unknown_voice_on_the_spot_and_accepts_a_key(imported, installed) -> None:  # noqa: F811
    _app, folder, _identifier, call = imported
    for key in ENGINE_KEYS.values():
        status, answer = _wish_post(call, "/voice", {"character": "HEIDI", "preset": voice_label(key)})
        assert status == 400 and "không dùng được" in answer["error"], "nhãn không phải khoá"
    assert _wish_post(call, "/voice", {"character": "HEIDI", "preset": "không-có-giọng-này"})[0] == 400
    assert _wish_post(call, "/voice", {"character": "NARRATOR", "preset": "giahuy"})[0] == 400, "giọng thêm không làm giọng kể chuyện"
    assert "voices" not in book_edits.load(folder).get("wishes", {}), "không ghi gì khi từ chối"

    assert _wish_post(call, "/voice", {"character": "HEIDI", "preset": MALE[1]["name"]})[0] == 200
    assert _wish_post(call, "/voice", {"character": "LUCIEN", "preset": ENGINE_KEYS["zerotts"]})[0] == 200
    assert book_edits.load(folder)["wishes"]["voices"]["LUCIEN"]["preset"] == ENGINE_KEYS["zerotts"]


def test_the_package_check_is_the_catalog_not_a_second_list() -> None:
    cast = [{"name": "HEIDI", "displayName": "Heidi", "voice": {"preset": "x"}}]
    assert book_wishes.voice_problem(cast, "HEIDI", preset="baotrang") is None
    assert book_wishes.voice_problem(cast, "HEIDI", preset="Bảo Trang") == overrides.UNKNOWN_PRESET
    assert book_wishes.voice_problem(cast, "NARRATOR", preset="Bảo Trang") == overrides.UNKNOWN_PRESET
    assert book_wishes.voice_problem(cast, "HEIDI") is None, "không chọn giọng: chỉ giới"


# ---- gỡ mô-đun giọng: máy chủ nói cuốn nào còn dùng (soát a94, F2) ---------------------------------------------------------------


def _use(server, engine: str):
    status, data, _ = _request(server.port, "GET", f"/api/studio/{engine}/use", headers=HEADERS, timeout=10)
    return status, json.loads(data)


def _noah_reads_supertonic(paths) -> None:
    """Noah đọc bằng hồ sơ giọng Supertonic M4; câu đầu của Noah chưa thu."""
    with sqlite3.connect(paths.db) as conn:
        conn.execute("INSERT INTO voice_profiles(voice_key, engine, preset_name, description, seed, status, created_at, updated_at)"
                     " VALUES('supertonic_M4_f100_p+00', 'supertonic', 'M4', '', 1, 'ready', 0, 0)")
        profile = conn.execute("SELECT id FROM voice_profiles WHERE voice_key='supertonic_M4_f100_p+00'").fetchone()[0]
        noah = conn.execute("SELECT id FROM characters WHERE canonical_name='NOAH'").fetchone()[0]
        rows = conn.execute("SELECT id FROM segments WHERE canonical_character_id=? ORDER BY seq", (noah,)).fetchall()
        assert len(rows) >= 2
        conn.execute("UPDATE segments SET voice_profile_id=? WHERE canonical_character_id=?", (profile, noah))
        conn.execute("UPDATE segments SET wav_path=NULL WHERE id=?", (rows[0][0],))


def test_removing_a_voice_module_can_ask_which_books_still_use_it(studio_app) -> None:  # noqa: F811
    _app, server, paths, _launcher, _runner = studio_app
    for engine in ENGINE_KEYS:
        status, answer = _use(server, engine)
        assert status == 200 and answer["bookCount"] == 0 and answer["books"] == [], "chưa cuốn nào dùng"
    assert _use(server, "vieneu")[0] in (400, 404), "chỉ máy đọc tải thêm mới gỡ được"

    # Noah đọc bằng một giọng Supertonic: 1 câu chưa thu. Lucien còn ý muốn chờ áp một giọng ZeroTTS.
    _noah_reads_supertonic(paths)
    overrides.request_voice(paths.root, "LUCIEN", preset=ENGINE_KEYS["zerotts"], now=time.time())

    status, answer = _use(server, "supertonic")
    assert status == 200 and answer["bookCount"] == 1 and answer["peopleCount"] == 1
    (book,) = answer["books"]
    assert book["people"] == ["Noah"] and book["left"] == 1 and answer["left"] == 1
    status, answer = _use(server, "zerotts")
    assert status == 200 and answer["bookCount"] == 1 and answer["books"][0]["people"] == ["Lucien"], "ý muốn chưa áp cũng tính"
    assert answer["left"] == 0


# ---- người nghe thấy nhãn, không thấy khoá (soát a94) ---------------------------------------------------------------------------


def test_the_cast_names_a_voice_by_label_and_keeps_the_key_in_preset(tmp_path: Path) -> None:
    paths, _db = _noah(tmp_path)
    _noah_reads_supertonic(paths)
    since = time.time() - 1
    overrides.request_voice(paths.root, "LUCIEN", preset="giahuy", now=time.time())

    cast = store.cast(paths.root)
    noah = next(person for person in [*cast["characters"], *cast["extras"]] if person["name"].upper() == "NOAH")
    assert noah["voice"]["preset"] == "M4" and noah["voice"]["label"] == "Supertonic M4"
    lucien = next(person for person in [*cast["characters"], *cast["extras"]] if person["name"].upper() == "LUCIEN")
    assert lucien["pendingVoice"]["preset"] == "giahuy" and lucien["pendingVoice"]["label"] == "Gia Huy"
    assert store.pending_voices(paths.root, since)["LUCIEN"]["label"] == "Gia Huy"
    assert "label" not in lucien["voice"], "giọng VieNeu: nhãn là chính khoá - không thêm (hợp đồng với app Android)"


def test_the_apply_box_and_the_inbox_say_the_label(tmp_path: Path) -> None:
    paths, _db = _noah(tmp_path)
    since = time.time() - 1
    overrides.request_voice(paths.root, "NOAH", preset="giahuy", now=time.time())
    assert store.label_voice("Noah", {"preset": "giahuy"}) == "Giọng của Noah: Gia Huy"
    assert store.label_voice("Noah", {"preset": MALE[1]["name"]}) == f"Giọng của Noah: {MALE[1]['name']}"
    assert store.label_voice("Noah", {"gender": "male"}) == "Giọng của Noah: giọng nam"
    (item,) = [item for item in store.pending_details(paths.root, since)["items"] if item["kind"] == "voice"]
    assert item["label"] == "Giọng của Noah: Gia Huy" and item["voiceLabel"] == "Gia Huy"
    assert item["voice"]["preset"] == "giahuy", "nghe thử gửi lại khoá"


def test_a_package_cast_shows_labels_too_and_the_originals_stay_untouched(imported, installed) -> None:  # noqa: F811
    _app, folder, _identifier, call = imported
    assert _wish_post(call, "/voice", {"character": "HEIDI", "preset": ENGINE_KEYS["zerotts"]})[0] == 200
    status, shown = call("GET", "/api/books/{id}/cast")
    assert status == 200
    people = [*shown["characters"], *shown["extras"]]
    heidi = next(person for person in people if person["name"].upper() == "HEIDI")
    assert "label" not in heidi["voice"], "giọng VieNeu: không thêm nhãn"
    assert heidi["pendingVoice"]["preset"] == "giahuy" and heidi["pendingVoice"]["label"] == "Gia Huy", "ý muốn chờ Studio: khoá + nhãn"


def test_label_cast_voices_labels_every_voice_and_never_mutates_the_input() -> None:
    from abook.webui.humanize import label_cast_voices

    cast = {"narrator": {"voice": "x", "profile": {"preset": "baotrang", "key": "k", "tone": ""}, "pendingVoice": {"preset": "F1", "gender": ""}},
            "characters": [{"name": "A", "voice": {"preset": "giahuy"}, "pendingVoice": None}, {"name": "B", "voice": None}], "extras": []}
    labelled = label_cast_voices(cast)
    assert labelled["narrator"]["profile"] == {"preset": "baotrang", "label": "Bảo Trang", "key": "k", "tone": ""}
    assert labelled["narrator"]["pendingVoice"]["label"] == "Supertonic F1"
    assert labelled["characters"][0]["voice"]["label"] == "Gia Huy" and labelled["characters"][1]["voice"] is None
    assert label_cast_voices({"characters": [{"voice": {"preset": "Thiện Minh"}}]})["characters"][0]["voice"] == {"preset": "Thiện Minh"}
    assert "label" not in cast["narrator"]["profile"] and "label" not in cast["characters"][0]["voice"]


def test_the_shared_label_file_for_the_phone_is_the_engine_voice_catalogue() -> None:
    """`abook/webui/assets/voice_labels.json` ({khoá: nhãn}) là bản của ENGINE_VOICES cho điện thoại (Kotlin `VoiceLabels` đọc đúng file này như
    asset): đổi danh mục giọng thì file phải đổi theo, nếu không điện thoại hiện khoá thô ("baotrang") thay vì tên máy tính hiện."""
    from abook.voice_catalog import ENGINE_VOICES
    from abook.webui import humanize

    file = Path(server_module.__file__).parent / "assets" / "voice_labels.json"
    shared = json.loads(file.read_text(encoding="utf-8"))
    assert shared == {voice["name"]: voice["label"] for voice in ENGINE_VOICES}, "chạy lại: ghi {name: label} của ENGINE_VOICES vào voice_labels.json"
    assert shared == humanize._ENGINE_VOICE_LABELS
    assert b"\r" not in file.read_bytes() and file.read_bytes().endswith(b"\n")
