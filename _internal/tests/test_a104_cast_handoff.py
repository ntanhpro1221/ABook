"""Soát a104 (phát ra loa / TV): chỗ nghe của phiên Cast thuộc hồ sơ đã bấm "Phát trên…", hai lệnh sang chương chồng nhau
đi tiếp nhau, và "Nghe trên máy này" chỉ dọn phiên khi thiết bị thật sự đã dừng. Không mở socket, không phát tiếng."""
from __future__ import annotations

import socket
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from abook.webui import cast
from abook.webui.listening import Listening
from abook.webui.server import App
from abook.webui.sync import remote_command


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("No networking in this harness")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "sendto", denied)


class Media:
    def __init__(self) -> None:
        self.paths: list[Path] = []

    def share(self, path: Path, _host: str) -> str:
        self.paths.append(Path(path))
        return f"http://127.0.0.1/track{len(self.paths)}.mp3"

    def close(self) -> None:
        pass


class Backend(cast.Backend):
    def __init__(self) -> None:
        self.loads: list[tuple[cast.Track, float]] = []
        self.stops: list[float] = []
        self.closed: list[bool] = []
        self.current: cast.Track | None = None
        self.stop_error: cast.CastError | None = None

    def load(self, track: cast.Track, seconds: float) -> float:
        self.loads.append((track, seconds))
        self.current = track
        return seconds

    def pause(self) -> bool:
        return False

    def play(self) -> None:
        pass

    def stop(self, timeout: float = 5) -> None:
        self.stops.append(timeout)
        if self.stop_error is not None:
            raise self.stop_error

    def close(self, release: bool = False) -> None:
        self.closed.append(release)

    def seek(self, seconds: float) -> None:
        pass

    def status(self) -> cast.Status:
        assert self.current is not None
        return cast.Status("PLAYING", 30, 300, self.current.url)


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    clock = [1000.0]
    monkeypatch.setattr(cast.time, "time", lambda: clock[0])
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"voice-only")
    view = {"title": "Sach thu", "chapters": [dict(id=i, title=f"Chuong {i}", available=True, duration=300) for i in (1, 2, 3)]}
    backend, media = Backend(), Media()
    saves: list[tuple[object, ...]] = []
    players = cast.CastPlayers(lambda _: view, lambda *_: audio, lambda *args: saves.append(args), media=media, find=list,
                               backend=lambda _: backend)
    renderer = cast.Renderer("dev", "Google TV", "tv", "127.0.0.1", protocol="gcast")
    players._renderers["dev"] = (renderer, clock[0])
    return SimpleNamespace(players=players, backend=backend, saves=saves, tmp=tmp_path)


def load(h: SimpleNamespace, chapter: int = 1, seconds: float = 20, **extra: object) -> None:
    h.players.send("dev", dict(action="load", bookId="sach", chapterId=chapter, seconds=seconds, **extra))


def listening_app(h: SimpleNamespace) -> tuple[Listening, str, str]:
    listening = Listening(h.tmp / "listening.json")
    a = listening.create_record("sach", "Nguoi A")["id"]
    b = listening.create_record("sach", "Nguoi B")["id"]
    listening.progress("sach", 1, 150, 300)  # B đang là hồ sơ dùng, nghe tới giây 150
    listening.activate("sach", a)
    app = App.__new__(App)
    app.listening = listening
    app.sync_remote_state = lambda *_args, **_kw: None
    h.players.save, h.players.record = app._cast_save, app._cast_record
    return listening, a, b


def test_cast_keeps_saving_into_the_profile_that_started_it(harness: SimpleNamespace) -> None:
    h = harness
    listening, a, b = listening_app(h)
    load(h, seconds=20)
    listening.activate("sach", b)  # ai đó đổi hồ sơ trên máy này trong lúc TV vẫn phát phiên của A
    h.players._poll("dev")  # TV báo giây 30
    assert listening.get("sach")["last"]["seconds"] == 150  # hồ sơ B không bị ghi đè
    listening.activate("sach", a)
    assert listening.get("sach")["last"]["seconds"] == 30


def test_the_profile_survives_moving_to_the_next_chapter(harness: SimpleNamespace) -> None:
    h = harness
    listening, a, b = listening_app(h)
    load(h)
    listening.activate("sach", b)
    h.players.send("dev", {"action": "next"})
    h.players._poll("dev")
    assert listening.get("sach")["last"]["chapterId"] == 1  # B vẫn ở chương 1 giây 150
    listening.activate("sach", a)
    assert listening.get("sach")["last"]["chapterId"] == 2


def test_the_profile_named_by_the_hand_off_wins_over_the_active_one(harness: SimpleNamespace) -> None:
    h = harness
    listening, a, b = listening_app(h)
    load(h, record=b)  # trình phát đang nghe bằng hồ sơ B, dù hồ sơ "đang dùng" của sách là A
    h.players._poll("dev")
    assert "last" not in listening.get("sach")  # A đang dùng, TV không ghi vào A
    listening.activate("sach", b)
    assert listening.get("sach")["last"]["seconds"] == 30


def test_only_cast_commands_carry_a_profile() -> None:
    body = {"action": "load", "bookId": "sach", "chapterId": 1, "seconds": 5, "record": "r1"}
    assert remote_command(body, cast=True)["record"] == "r1"
    assert "record" not in remote_command(body)


def test_overlapping_next_commands_reach_chapter_three(harness: SimpleNamespace) -> None:
    h = harness
    load(h)
    entered, queued, release = threading.Event(), threading.Event(), threading.Event()
    errors: list[BaseException] = []
    original = h.backend.load

    def delayed(track: cast.Track, seconds: float) -> float:
        if track.title == "Chuong 2" and not entered.is_set():
            entered.set()
            assert release.wait(3)
        return original(track, seconds)

    h.backend.load = delayed
    real = threading.Lock()

    class Gate:
        def __enter__(self) -> None:
            if threading.current_thread().name == "second":
                queued.set()
            real.acquire()

        def __exit__(self, *_exc: object) -> None:
            real.release()

    h.players._device = lambda _: Gate()

    def send() -> None:
        try:
            h.players.send("dev", {"action": "next"})
        except BaseException as error:  # noqa: BLE001
            errors.append(error)

    first, second = threading.Thread(target=send, name="first"), threading.Thread(target=send, name="second")
    first.start()
    assert entered.wait(3)
    second.start()
    assert queued.wait(3)
    release.set()
    first.join(3)
    second.join(3)
    assert not first.is_alive() and not second.is_alive() and not errors
    assert [track.title for track, _ in h.backend.loads] == ["Chuong 1", "Chuong 2", "Chuong 3"]
    assert h.players._sessions["dev"].chapter_id == 3


def test_a_device_that_will_not_stop_keeps_its_session(harness: SimpleNamespace) -> None:
    h = harness
    load(h)
    h.backend.stop_error = cast.CastError("không trả lời")
    with pytest.raises(cast.CastError, match="Google TV: không trả lời"):
        h.players.send("dev", {"action": "stop"})
    session = h.players._sessions["dev"]
    assert not session.ended and "dev" in h.players._backends  # còn theo dõi được, bấm lại là thử lại
    h.backend.stop_error = None
    h.players.send("dev", {"action": "stop"})
    assert session.ended and h.backend.closed == [True]
