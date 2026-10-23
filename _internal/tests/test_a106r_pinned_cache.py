"""Soát a106r mục G: clip "Làm trước" được GHIM trong bộ đệm máy tính như trên điện thoại (ClipCache.kt) - nghe trực tiếp nhiều
không đẩy chúng ra trước khi người nghe tới; nghe tới đoạn nào thì đoạn ấy hết ghim; ghim có trần."""
from __future__ import annotations

import os
import time
from pathlib import Path

from abook.readaloud.cache import ClipCache, clip_key
from abook.readaloud.prepare import Prepare
from abook.readaloud.service import ReadAloud
from tests.test_readaloud import FakeProvider

AUDIO = b"x" * 90


def _fill(cache: ClipCache, names: list[str], *, pin: bool = False, age: float = 0.0) -> list[str]:
    keys = [clip_key("vieneu", "v", name) for name in names]
    for index, key in enumerate(keys):
        if pin:
            cache.pin(key)
        cache.put(key, AUDIO, "wav", 1000, [[0, 10]])
        stamp = time.time() - age + index
        try:
            os.utime(cache.folder / f"{key}.json", (stamp, stamp))
        except FileNotFoundError:
            pass  # đã bị tỉa ngay lúc ghi
    return keys


def test_live_clips_do_not_push_prepared_clips_out_of_a_full_cache(tmp_path: Path) -> None:
    cache = ClipCache(tmp_path / "c", limit=1000)
    prepared = _fill(cache, [f"chuẩn bị {i}" for i in range(4)], pin=True, age=100)
    live = _fill(cache, [f"nghe trực tiếp {i}" for i in range(8)])
    assert all(cache.get(key) for key in prepared), "đoạn làm trước còn nguyên dù cũ hơn mọi đoạn nghe trực tiếp"
    assert sum(bool(cache.get(key)) for key in live) < len(live), "bộ đệm vẫn phải tỉa: đoạn không ghim đi trước"


def test_an_unpinned_clip_is_trimmed_in_the_old_order_and_pinned_ones_go_only_when_nothing_else_is_left(tmp_path: Path) -> None:
    cache = ClipCache(tmp_path / "c", limit=1000)
    prepared = _fill(cache, [f"chuẩn bị {i}" for i in range(11)], pin=True, age=100)
    assert sum(bool(cache.get(key)) for key in prepared) < len(prepared), "toàn đoạn ghim mà vượt trần: cũ nhất đi trước, bộ đệm không phình mãi"
    assert cache.size() <= cache.limit


def test_unpinning_makes_a_clip_ordinary_again(tmp_path: Path) -> None:
    cache = ClipCache(tmp_path / "c", limit=1000)
    prepared = _fill(cache, [f"chuẩn bị {i}" for i in range(4)], pin=True, age=100)
    for key in prepared:
        cache.unpin(key)
    _fill(cache, [f"nghe trực tiếp {i}" for i in range(8)])
    assert not any(cache.get(key) for key in prepared), "hết ghim thì cũ nhất đi trước"


def test_pins_survive_a_restart_and_the_clear_all_drops_them(tmp_path: Path) -> None:
    pins = tmp_path / "pins.txt"
    cache = ClipCache(tmp_path / "c", limit=1000, pin_file=pins)
    keys = _fill(cache, ["một", "hai"], pin=True)
    again = ClipCache(tmp_path / "c", limit=1000, pin_file=pins)
    assert all(again.is_pinned(key) for key in keys)
    assert again.pinned_bytes() == cache.pinned_bytes() > 0
    again.clear()
    assert not any(again.is_pinned(key) for key in keys) and again.pinned_bytes() == 0
    assert not ClipCache(tmp_path / "c", limit=1000, pin_file=pins).is_pinned(keys[0])


def test_prepare_pins_what_it_makes_and_listening_to_it_unpins(tmp_path: Path) -> None:
    provider = FakeProvider()
    service = ReadAloud(tmp_path / "rd", [provider])
    service.clip("fake:ngoc", "Câu đã nghe rồi.")  # có sẵn trong bộ đệm khi "Làm trước" chạy tới
    service.prepare.start("fake:ngoc", ["Câu đã nghe rồi.", "Câu thứ hai.", "Câu thứ ba."])
    service.prepare.join(10)
    assert service.prepare.status()["state"] == "done"
    keys = {path.stem for path in service.cache.folder.glob("*.json")}
    assert len(keys) == 3 and all(service.cache.is_pinned(key) for key in keys), "kể cả đoạn đã có sẵn"
    heard = service.clip("fake:ngoc", "Câu thứ hai.")
    assert not service.cache.is_pinned(heard["file"].split(".")[0]), "người nghe tới đoạn nào thì đoạn ấy hết ghim"
    assert sum(service.cache.is_pinned(key) for key in keys) == 2
    service.clip("fake:ngoc", "Câu thứ ba.", background=True)  # việc nền khác (xuất sách nói) không bỏ ghim của ai
    assert sum(service.cache.is_pinned(key) for key in keys) == 2


def test_a_listen_export_clip_is_not_pinned(tmp_path: Path) -> None:
    service = ReadAloud(tmp_path / "rd", [FakeProvider()])
    clip = service.clip("fake:ngoc", "Một câu xuất sách nói.", background=True)
    assert not service.cache.is_pinned(clip["file"].split(".")[0])


def test_prepare_stops_when_the_pinned_share_is_full() -> None:
    made: list[str] = []
    prepare = Prepare(lambda voice, text, origin, readings, book: made.append(text), lambda: 0, 10**9, full=lambda: len(made) >= 2)
    prepare.start("fake:ngoc", ["Một hai.", "Ba bốn.", "Năm sáu.", "Bảy tám."])
    prepare.join(10)
    status = prepare.status()
    assert made == ["Một hai.", "Ba bốn."]
    assert status["state"] == "done" and status["full"] is True and status["done"] == 2
