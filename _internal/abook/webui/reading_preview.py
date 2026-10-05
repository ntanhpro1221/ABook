"""Nghe thử một cách đọc tên TRƯỚC KHI lưu (nút "Nghe thử" ở "Cách đọc tên" và thẻ hộp việc).

Người nghe gõ "Hên-khơ" theo tai; lưu là cả cuốn thu lại các câu có tên ấy, nên họ muốn nghe trước. Câu nghe thử đi đúng
đường của lần thu thật: cùng mã đã ghim cho cuốn (`studio_code.json`), cùng cài đặt đã khoá của cuốn, cùng giọng của người
nói câu ấy, cùng hạt giống của lần thu đầu (`primary_0`) - chỉ có bảng cách đọc là bảng của sách cộng MỘT dòng người nghe đang
cân nhắc (`PreviewVoiceDB`, ghi y như `apply_listener_pronunciation` sẽ ghi). Không ghi gì vào sách: SQLite mở chỉ đọc,
`overrides.json` không đụng tới. Lần thu thật có thể không trùng từng byte (âm thanh không phải lúc nào cũng tái lập), nên giao
diện nói đây là "lần thu đầu sẽ nghe như vầy", không hứa hơn.

Cùng đường ấy nghe thử một GIỌNG trước khi đổi giọng nhân vật (`voice_preview`, hộp "Đổi giọng" và "Áp dụng"): một câu của
chính nhân vật đó, đọc bằng hồ sơ giọng dây chuyền sẽ tạo khi áp (`PreviewVoiceDB` thay hồ sơ của câu, không chồng cách đọc).

Tiến trình: MỘT tiến trình python của Studio (chạy `PREVIEW_SCRIPT` bằng `python -c`), nói chuyện bằng từng dòng JSON qua
stdin/stdout, giữ model nạp sẵn giữa hai lần nghe thử và tự tắt sau `IDLE_SECONDS` không ai hỏi. Mỗi lúc chỉ một việc (các
việc khác xếp hàng, tối đa `MAX_WAITING` - quá thì 429). Không bao giờ chạy chung với một cuốn đang làm: `shutdown()` được gọi
trước khi cuốn nào bắt đầu, và nghe thử bị từ chối (409) khi có cuốn đang chạy hay đang khởi động.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import closing
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable

from ..database import LISTENER_PRONUNCIATION_SOURCE, thought_reads_as_narrator
from ..listener_overrides import surface_key
from ..tts_pool import ReadOnlyVoiceDB
from . import store
from .remote_studio import FORWARD_SECONDS
from .reviews import speaker_label

# Ngưỡng của lần nạp VieNeu thật: ~2,3 GiB VRAM (đo trên card 8 GB) và ~6 GB RAM trống - dưới đó nạp là tranh với việc khác
# trên máy, hay hết bộ nhớ giữa chừng.
MIN_FREE_VRAM_MIB = 2300
MIN_FREE_RAM_GB = 6.15
MAX_WAITING = 2
LOAD_TIMEOUT = 60.0  # khởi động tiến trình + nạp model
JOB_TIMEOUT = 45.0  # một câu
IDLE_SECONDS = 120.0
# Studio từ xa chuyển tiếp yêu cầu tối đa FORWARD_SECONDS: cả lượt (chờ hàng + nạp + đọc) phải xong trước đó.
REQUEST_BUDGET = FORWARD_SECONDS - 10.0
KEEP_PER_BOOK = 50
LINE_LENGTH = (24, 160)  # câu mẫu mặc định: đủ dài để nghe ngữ điệu, đủ ngắn để đọc nhanh
MAX_FALLBACK_LENGTH = 400
# Câu nghe thử một giọng cho nhân vật (`character_line`): đủ dài để nghe ra chất giọng, đủ ngắn để đọc nhanh.
VOICE_LINE_LENGTH = (40, 160)
KEY_LENGTH = 32
# Hạt giống của lần thu đầu một câu: pipeline._process_single_segment ghép "primary" + "_" + số lần thử (0).
FIRST_TAKE_SALT = "primary_0"
CREATE_NO_WINDOW = 0x08000000
KEY_PATTERN = re.compile(r"[0-9a-f]{%d}" % KEY_LENGTH)
# Cột của câu làm đổi tiếng đọc (cả hạt giống lẫn cách lấy mẫu): vào khoá bản nghe thử.
_LINE_COLUMNS = ("text_sha256", "listener_text", "listener_retakes", "kind", "speaker", "emotion", "intensity", "pace",
                 "volume", "voice_profile_id")

# Dòng người nghe đang cân nhắc chồng lên bảng cách đọc của sách - ghi y như `ProjectDB.apply_listener_pronunciation`
# (confidence 1.0, locked 1, nguồn người nghe) và xếp lại như `ReadOnlyVoiceDB.list_pronunciations` (từ dài trước). Là MỘT đoạn
# mã chạy được ở hai nơi: ở đây (khoá bản nghe thử) và trong PREVIEW_SCRIPT, nên cuốn đã ghim bản mã cũ không có module này
# vẫn chạy được. `source` do bên gọi đưa vào (database.LISTENER_PRONUNCIATION_SOURCE) để không chép hằng số.
_OVERLAY = '''
class PreviewVoiceDB(ReadOnlyVoiceDB):
    """Sổ giọng chỉ đọc của sách, thêm hay thay đúng một cách đọc (chưa lưu ở đâu cả) - `key` None: bảng cách đọc như sách.
    `voice`: hồ sơ giọng đang cân nhắc cho một nhân vật, đứng thay hồ sơ mang cùng `id` (giọng câu ấy đang đọc)."""

    def __init__(self, path, key, surface, spoken_form, source, voice=None):
        super().__init__(path)
        self.key, self.surface, self.spoken_form, self.source = key, surface, spoken_form, source
        self.voice = voice

    def voice_profile(self, profile_id):
        if self.voice is not None and int(profile_id) == int(self.voice["id"]):
            return self.voice
        return super().voice_profile(profile_id)

    def list_voice_profiles(self):
        rows = list(super().list_voice_profiles())
        return rows if self.voice is None else rows + [self.voice]

    def list_pronunciations(self, minimum_confidence=0.0):
        if self.key is None:
            return super().list_pronunciations(minimum_confidence)
        rows = [dict(row) for row in super().list_pronunciations(minimum_confidence)]
        current = next((row for row in rows if row["normalized_surface"] == self.key), None)
        mine = {"id": 0, "created_at": 0.0, "updated_at": 0.0, **(current or {}), "surface": self.surface,
                "normalized_surface": self.key, "spoken_form": self.spoken_form, "confidence": 1.0,
                "source": self.source, "locked": 1}
        rows = [row for row in rows if row["normalized_surface"] != self.key] + [mine]
        rows.sort(key=lambda row: (-len(str(row["surface"])), str(row["normalized_surface"])))
        return rows
'''

_HEAD = '''
import contextlib
import json
import os
import sys
from pathlib import Path

from abook.config import normalize_legacy_locked_settings
from abook.tts import TTSCoordinator
from abook.tts_pool import ReadOnlyVoiceDB
'''

# Giọng GIẢ cho lúc dựng giao diện và bài thử (FakeRunner / ABOOK_FAKE_RUNNER): vẫn chạy cả TTSCoordinator thật - chỉ model là
# một tiếng ngân. Các tên giọng lấy từ chính sổ giọng của sách để phép kiểm "giọng đã khoá còn đó" vẫn đúng.
_BODY = r'''

def fake_voice(db, settings):
    import types

    import numpy as np

    names = [str(profile["preset_name"]) for profile in db.list_voice_profiles() if profile["preset_name"]]
    # Tên giọng giả không có bản ghi đo; bộ chạy giả này (và chỉ nó) cho chúng hằng số trung tính.
    from abook import voice_balance

    voice_balance.register_neutral_voices(db.list_voice_profiles())

    class Runtime:
        sample_rate = int(settings["tts"]["sample_rate"])

        def list_preset_voices(self):
            return [(name, name) for name in names]

        def infer(self, text, **kwargs):
            moments = np.arange(int(min(6.0, 0.5 + 0.07 * len(text)) * self.sample_rate)) / self.sample_rate
            return (0.2 * np.sin(2 * np.pi * 220 * moments)).astype(np.float32)

    module = types.ModuleType("vieneu")
    module.Vieneu = lambda **kwargs: Runtime()
    sys.modules["vieneu"] = module


def run_job(request, state, emit):
    """Đọc một câu của sách (chỉ đọc), thu nó bằng bảng cách đọc đã chồng dòng đang nghe thử, hay bằng giọng đang cân nhắc
    (`voice`). Trả {"ok", "seed"}."""
    db = PreviewVoiceDB(Path(request["project"]) / "project.sqlite3", request.get("key"), request.get("surface"),
                        request.get("spoken"), request.get("source"), request.get("voice"))
    with contextlib.closing(db._connect()) as connection:
        book = connection.execute("SELECT settings_json FROM book WHERE id=1").fetchone()
        row = connection.execute("SELECT * FROM segments WHERE id=?", (int(request["segment"]),)).fetchone()
    if book is None or row is None:
        return {"error": "Không đọc được câu này trong sách."}
    settings = normalize_legacy_locked_settings(json.loads(str(book["settings_json"])))
    if os.environ.get("ABOOK_PREVIEW_FAKE") == "1":
        fake_voice(db, settings)
        state.pop("engine", None)
    coordinator = TTSCoordinator(settings, db, lambda _message: None)
    if state.get("engine") is not None:
        coordinator.vieneu = state["engine"]  # model đã nạp từ lần trước
        coordinator.vieneu.settings = settings
    coordinator.vieneu.load()
    state["engine"] = coordinator.vieneu
    emit({"event": "loaded", "id": request["id"]})
    _checksum, _metrics, seed = coordinator.synthesize_atomic(row, Path(request["output"]), seed_salt=request["salt"])
    return {"ok": True, "seed": int(seed)}


def main():
    channel = sys.stdout
    sys.stdout = sys.stderr  # in lạc của thư viện không được lẫn vào đường truyền

    def emit(message):
        channel.write(json.dumps(message, ensure_ascii=False) + "\n")
        channel.flush()

    state = {}
    emit({"event": "ready"})
    for line in sys.stdin:
        if not line.strip():
            continue
        request = json.loads(line)
        if request.get("op") == "quit":
            break
        try:
            result = run_job(request, state, emit)
        except Exception as error:
            result = {"error": f"{type(error).__name__}: {error}"}
        emit({"id": request["id"], **result})


if __name__ == "__main__":
    main()
'''

PREVIEW_SCRIPT = _HEAD + _OVERLAY + _BODY

# Cùng đoạn mã ấy, dựng thành lớp ở đây (khoá bản nghe thử và bài thử) - không có bản chép thứ hai.
_namespace: dict[str, Any] = {"ReadOnlyVoiceDB": ReadOnlyVoiceDB}
exec(compile(_OVERLAY, "<reading_preview overlay>", "exec"), _namespace)  # noqa: S102 - hằng số của chính module này
PreviewVoiceDB: type[ReadOnlyVoiceDB] = _namespace["PreviewVoiceDB"]


class PreviewError(Exception):
    """Lý do không nghe thử được: `status` HTTP, `reason` mã cho giao diện (câu chữ của nó nằm ở giao diện), `message` cho người."""

    def __init__(self, status: int, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.status = int(status)
        self.message = message
        self.reason = reason


class _Died(Exception):
    pass


class _Child:
    """Tiến trình giọng đang sống. Đọc stdout ở luồng riêng để chờ được CÓ HẠN (một dòng đọc không có hạn là một tiến trình
    treo kéo cả giao diện treo theo)."""

    def __init__(self, popen: Any, identity: tuple[str, str]) -> None:
        self.popen = popen
        self.identity = identity
        self.lines: queue.Queue[dict[str, Any] | None] = queue.Queue()
        threading.Thread(target=self._pump, name="reading-preview-reader", daemon=True).start()

    def _pump(self) -> None:
        try:
            for line in self.popen.stdout:
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if isinstance(message, dict):
                    self.lines.put(message)
        except (OSError, ValueError):
            pass
        finally:
            self.lines.put(None)

    def send(self, message: dict[str, Any]) -> None:
        try:
            self.popen.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            self.popen.stdin.flush()
        except (OSError, ValueError) as error:
            raise _Died from error

    def wait(self, deadline: float, wanted: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        """Dòng đầu tiên thoả `wanted`; hết hạn thì queue.Empty, tiến trình chết thì _Died."""
        while True:
            message = self.lines.get(timeout=max(0.0, deadline - time.monotonic()))
            if message is None:
                self.lines.put(None)
                raise _Died
            if wanted(message):
                return message

    def alive(self) -> bool:
        return self.popen.poll() is None

    def kill(self) -> None:
        for action in (self.popen.kill, self.popen.stdin.close):
            try:
                action()
            except (OSError, ValueError):
                pass


def _free_resources() -> tuple[int | None, float | None]:
    """(VRAM trống MiB, RAM trống GB) - None khi máy không đo được (không có card NVIDIA)."""
    import psutil

    from ..resource_manager import NvidiaProbe

    free_vram, _total = NvidiaProbe().gpu_memory()
    return free_vram, psutil.virtual_memory().available / 1024**3


def line_text(row: Any) -> str:
    """Chữ mà giọng sẽ đọc cho câu: chữ người nghe sửa (`listener_text`) hay chữ gốc - như `TTSCoordinator.spoken_text_with_anchors`."""
    return str((row["listener_text"] if "listener_text" in row.keys() else "") or row["text"] or "")


def character_line(connection: sqlite3.Connection, character: str, segment_id: int | None = None) -> sqlite3.Row:
    """Câu để nghe thử một giọng cho nhân vật `character` (khoá sổ): câu người dùng chỉ (phải của người ấy), không thì câu
    "đại diện" - lời thoại dài VOICE_LINE_LENGTH, ưu tiên cảm xúc bình thường (nghe giọng chứ không nghe cơn giận), dài gần
    giữa khoảng nhất, câu sớm nhất khi hoà. Không có thì câu nội tâm của chính người ấy, rồi câu gần khoảng ấy nhất (không quá
    MAX_FALLBACK_LENGTH). Câu đọc bằng giọng người kể (nội tâm không rõ ai nghĩ) không nghe được giọng nhân vật nên không lấy.
    Không câu nào: PreviewError "no-line" - giao diện quay về bản nghe thử chung của giọng."""
    rows = [row for row in connection.execute(
        "SELECT s.* FROM segments s JOIN characters c ON c.id = s.canonical_character_id"
        " WHERE c.canonical_name=? AND s.voice_profile_id IS NOT NULL ORDER BY s.chapter_id, s.seq", (character,))
        if not thought_reads_as_narrator(row["kind"], row["speaker"], row["voice_profile_id"])]
    if segment_id is not None:
        chosen = next((row for row in rows if int(row["id"]) == int(segment_id)), None)
        if chosen is None:
            raise PreviewError(HTTPStatus.BAD_REQUEST, "Câu này không phải lời của nhân vật ấy.", "no-line")
        return chosen
    low, high = VOICE_LINE_LENGTH
    middle = (low + high) / 2

    def fits(row: sqlite3.Row) -> bool:
        return low <= len(line_text(row)) <= high

    tiers = (
        lambda row: row["kind"] == "dialogue" and fits(row) and str(row["emotion"] or "neutral") == "neutral",
        lambda row: row["kind"] == "dialogue" and fits(row),
        fits,
    )
    for tier in tiers:
        found = [row for row in rows if tier(row)]
        if found:
            return min(found, key=lambda row: abs(len(line_text(row)) - middle))  # min giữ câu sớm nhất khi hoà
    rest = [row for row in rows if line_text(row).strip() and len(line_text(row)) <= MAX_FALLBACK_LENGTH]
    if rest:
        return min(rest, key=lambda row: max(low - len(line_text(row)), len(line_text(row)) - high))
    raise PreviewError(HTTPStatus.UNPROCESSABLE_ENTITY, "Nhân vật này chưa có câu nào để nghe thử.", "no-line")


def name_pattern(surface: str) -> re.Pattern[str]:
    """Phép khớp của TTS (`tts._load_pronunciations`): nguyên từ, không phân biệt hoa thường."""
    return re.compile(r"(?<!\w)" + re.escape(surface) + r"(?!\w)", re.IGNORECASE)


class ReadingPreviews:
    """Nghe thử cách đọc tên của MỘT máy: tiến trình giọng dùng chung, bản nghe thử cất theo từng cuốn.

    `studio()`: StudioSetup hay None (bản dev: chạy bằng chính python này, mã cạnh app). `fake()`: dựng giao diện/bài thử -
    giọng giả, không đòi Studio hay card đồ hoạ. `busy()`: có cuốn nào đang chạy/khởi động không. `launcher`, `probe`: thay được
    để thử không cần python thứ hai hay card thật."""

    def __init__(self, root: Path, *, studio: Callable[[], Any], fake: Callable[[], bool], busy: Callable[[], bool],
                 launcher: Callable[[list[str], dict[str, str], Path], Any] | None = None,
                 probe: Callable[[], tuple[int | None, float | None]] = _free_resources,
                 idle_seconds: float = IDLE_SECONDS, load_timeout: float = LOAD_TIMEOUT,
                 job_timeout: float = JOB_TIMEOUT) -> None:
        self.root = Path(root)
        self.studio = studio
        self.fake = fake
        self.busy = busy
        self.launcher = launcher or self._spawn
        self.probe = probe
        self.idle_seconds = idle_seconds
        self.load_timeout = load_timeout
        self.job_timeout = job_timeout
        self._lock = threading.Lock()  # một việc một lúc
        self._guard = threading.Lock()  # bảo vệ `_waiting`, `_child`, `_timer`, `_generation`
        self._waiting = 0
        self._child: _Child | None = None
        self._timer: threading.Timer | None = None
        self._generation = 0
        self._sequence = 0

    # ---- giao diện cho server --------------------------------------------------------------------------------

    def preview(self, project: Path, book: str, surface: str, spoken: str, segment_id: int | None = None) -> dict[str, Any]:
        """Thu thử một câu có `surface` đọc là `spoken`; trả {url, segmentId, text, speaker, cached}. Đã nghe rồi (cùng mọi
        thứ làm đổi tiếng đọc) thì phát lại bản cất - không khởi động gì."""
        started = time.monotonic()
        fake, studio = self._engine()
        if not (Path(project) / store.DB_NAME).is_file():
            raise PreviewError(HTTPStatus.UNPROCESSABLE_ENTITY, "Sách này chưa có câu nào để nghe thử.", "no-line")
        key_name = surface_key(surface)
        database = Path(project) / store.DB_NAME
        overlay = PreviewVoiceDB(database, key_name, surface, spoken, LISTENER_PRONUNCIATION_SOURCE)
        line = self._line(Path(project), surface, key_name, segment_id)
        code_id, code_root = self._code(studio, Path(project))
        key = self._key(overlay, line, code_id, key_name, spoken)
        view = {"segmentId": int(line["id"]), "text": line_text(line),
                "speaker": speaker_label("NARRATOR" if thought_reads_as_narrator(line["kind"], line["speaker"], line["voice_profile_id"])
                                      else str(line["speaker"] or ""))}
        job = {"key": key_name, "surface": surface, "spoken": spoken, "source": LISTENER_PRONUNCIATION_SOURCE}
        return self._produce(studio, fake, code_root, Path(project), book, line, job, key, view, started)

    def voice_preview(self, project: Path, book: str, character: str, *, preset: str = "", gender: str = "", avoid: str = "",
                      segment_id: int | None = None) -> dict[str, Any]:
        """"Nghe thử bằng câu của sách" ở hộp "Đổi giọng" và hộp "Áp dụng": thu thử MỘT câu của nhân vật bằng đúng hồ sơ giọng
        dây chuyền sẽ tạo khi áp yêu cầu ấy (`listener_overrides.voice_target`, cùng phép POST /voice dùng để từ chối), cùng
        hạt giống của lần thu đầu bằng giọng ấy. Bảng cách đọc là của sách, không chồng gì. Trả {url, segmentId, text, speaker,
        cached}; bản cất theo (giọng, câu) như cách đọc tên."""
        from ..listener_overrides import voice_target

        started = time.monotonic()
        fake, studio = self._engine()
        project = Path(project)
        if not (project / store.DB_NAME).is_file():
            raise PreviewError(HTTPStatus.UNPROCESSABLE_ENTITY, "Sách này chưa có câu nào để nghe thử.", "no-line")
        with closing(store.connect(project)) as connection:
            target, problem = voice_target(connection, store.book_voices(project), character=character, preset=preset,
                                           gender=gender, avoid=avoid)
            if target is None:
                raise PreviewError(HTTPStatus.BAD_REQUEST, "Không nghe thử được giọng này cho nhân vật ấy.", str(problem or ""))
            line = character_line(connection, str(target["canonical_name"]), segment_id)
        # Không có hồ sơ mới: giọng đang đọc đã là giọng ấy - câu đọc bằng chính hồ sơ của nó.
        profile = target["profile"]
        voice = None if profile is None else {
            **profile, "id": int(line["voice_profile_id"]), "locked": 1, "created_at": 0.0, "updated_at": 0.0}
        overlay = PreviewVoiceDB(project / store.DB_NAME, None, None, None, None, voice)
        code_id, code_root = self._code(studio, project)
        key = self._key(overlay, line, code_id, "voice")
        view = {"segmentId": int(line["id"]), "text": line_text(line), "speaker": speaker_label(str(line["speaker"] or ""))}
        return self._produce(studio, fake, code_root, project, book, line, {"voice": voice}, key, view, started)

    def _engine(self) -> tuple[bool, Any]:
        """(giọng giả?, Studio hay None) - Studio chưa cài / đã cũ thì không nghe thử được."""
        fake = bool(self.fake())
        studio = None if fake else self.studio()
        if studio is not None and (not studio.installed() or studio.outdated()):
            raise PreviewError(HTTPStatus.SERVICE_UNAVAILABLE, "Cần cài phần làm sách (Studio) trước khi nghe thử.", "studio")
        return fake, studio

    def _produce(self, studio: Any, fake: bool, code_root: Path, project: Path, book: str, line: sqlite3.Row,
                 job: dict[str, Any], key: str, view: dict[str, Any], started: float) -> dict[str, Any]:
        """Bản cất `key` của câu `line`, thu nếu chưa có: không bao giờ chen vào một cuốn đang làm hay một card đang bận -
        từ chối (409) với lý do, việc đến sau xếp hàng (`_queue`)."""
        url = f"/media/books/{book}/reading-previews/{key}.wav"
        target = self.root / book / f"{key}.wav"
        if self._reuse(target):
            return {**view, "url": url, "cached": True}
        if self.busy():
            raise PreviewError(HTTPStatus.CONFLICT, "Đang làm sách - nghe thử khi máy rảnh.", "producing")
        if not fake:
            free_vram, free_ram = self.probe()
            if (free_vram is not None and free_vram < MIN_FREE_VRAM_MIB) or (free_ram is not None and free_ram < MIN_FREE_RAM_GB):
                raise PreviewError(HTTPStatus.CONFLICT, "Card đồ hoạ đang bận - thử lại sau ít phút.", "gpu")
        self._queue(started)
        try:
            if self._reuse(target):  # việc đứng trước vừa thu đúng câu này
                return {**view, "url": url, "cached": True}
            if self.busy():
                raise PreviewError(HTTPStatus.CONFLICT, "Đang làm sách - nghe thử khi máy rảnh.", "producing")
            self._run(studio, fake, code_root, {"project": str(project), "segment": int(line["id"]), **job}, target, started)
            self._tidy(target.parent)
        finally:
            self._lock.release()
        return {**view, "url": url, "cached": False}

    def file(self, book: str, key: str) -> Path | None:
        """Bản nghe thử đã cất, hoặc None."""
        if not KEY_PATTERN.fullmatch(key) or not re.fullmatch(r"[A-Za-z0-9_-]+", book):
            return None
        target = self.root / book / f"{key}.wav"
        return target if target.is_file() else None

    def shutdown(self) -> None:
        """Tắt tiến trình giọng ngay (cả khi đang giữa một câu - câu ấy báo "đang làm sách"). Gọi trước khi cuốn nào bắt đầu:
        model nghe thử giữ VRAM, mà cuốn sách cần cả card."""
        with self._guard:
            self._generation += 1
            child, self._child = self._child, None
            timer, self._timer = self._timer, None
        if timer is not None:
            timer.cancel()
        if child is not None:
            child.kill()

    # ---- chọn câu, khoá, bản cất -----------------------------------------------------------------------------

    def _line(self, project: Path, surface: str, key_name: str, segment_id: int | None) -> sqlite3.Row:
        """Câu để đọc thử: câu người dùng chỉ (phải có tên ấy), không thì câu NGẮN NHẤT có tên ấy dài 24-160 ký tự, không có
        nữa thì câu mẫu của mục "Cách đọc tên" (name_readings). Câu phải đã có giọng (đã qua bước phân vai)."""
        pattern = name_pattern(surface)
        with closing(store.connect(project)) as connection:
            if "segments" not in store._table_names(connection):
                raise PreviewError(HTTPStatus.UNPROCESSABLE_ENTITY, "Sách này chưa có câu nào để nghe thử.", "no-line")
            if segment_id is not None:
                row = connection.execute("SELECT * FROM segments WHERE id=?", (int(segment_id),)).fetchone()
                if row is None or not pattern.search(line_text(row)):
                    raise PreviewError(HTTPStatus.BAD_REQUEST, f"Câu này không có tên “{surface}”.", "no-line")
                if row["voice_profile_id"] is None:
                    raise PreviewError(HTTPStatus.UNPROCESSABLE_ENTITY, "Câu này chưa có giọng đọc (chưa qua bước phân vai).", "no-line")
                return row
            having = [row for row in connection.execute("SELECT * FROM segments WHERE voice_profile_id IS NOT NULL ORDER BY chapter_id, seq")
                      if pattern.search(line_text(row))]
            short = [row for row in having if LINE_LENGTH[0] <= len(line_text(row)) <= LINE_LENGTH[1]]
            if short:
                return min(short, key=lambda row: len(line_text(row)))
            from .name_readings import name_readings

            for item in name_readings(project)["items"]:
                example = item.get("example")
                if surface_key(item["surface"]) == key_name and example:
                    row = connection.execute("SELECT * FROM segments WHERE id=? AND voice_profile_id IS NOT NULL",
                                             (int(example["segmentId"]),)).fetchone()
                    if row is not None:
                        return row
            # Tên người nghe vừa thêm (chưa có dòng nào trong bảng cách đọc) không có câu mẫu: lấy câu ngắn nhất có nó - câu
            # quá dài thì bỏ, một lần thu không được kéo dài quá hạn.
            fallback = [row for row in having if len(line_text(row)) <= MAX_FALLBACK_LENGTH]
            if fallback:
                return min(fallback, key=lambda row: len(line_text(row)))
        raise PreviewError(HTTPStatus.UNPROCESSABLE_ENTITY, "Chưa có câu nào mang tên này đã phân vai để nghe thử.", "no-line")

    def _code(self, studio: Any, project: Path) -> tuple[str, Path]:
        """(mã bản mã, thư mục mã) của cuốn: bản đã ghim trong dự án (`studio_code.json`), đọc mà không ghi gì."""
        if studio is None:
            from ..quality_policy import quality_implementation_hash

            return quality_implementation_hash()[:16], Path(__file__).resolve().parents[2]
        try:
            return studio.peek_code(project)
        except Exception as error:  # noqa: BLE001 - SetupError: mất bản mã đã làm cuốn này
            raise PreviewError(HTTPStatus.UNPROCESSABLE_ENTITY, str(error), "failed") from error

    def _key(self, overlay: ReadOnlyVoiceDB, line: sqlite3.Row, code_id: str, *extra: str) -> str:
        """Khoá bản nghe thử: mọi thứ làm đổi tiếng đọc - bản mã, cài đặt đã khoá, câu (chữ, lượt thu lại, giọng - giọng đang
        cân nhắc nếu có), điều đang thử (`extra`: cách đọc đang gõ) và cả bảng cách đọc (các tên khác trong câu)."""
        with closing(overlay._connect()) as connection:
            settings_hash = connection.execute("SELECT settings_hash FROM book WHERE id=1").fetchone()
        profiles = [dict(overlay.voice_profile(int(line["voice_profile_id"])))]
        try:
            profiles.append(dict(overlay.voice_profile_by_key("narrator")))  # câu nội tâm không rõ người nghĩ đọc bằng giọng người kể
        except KeyError:
            pass
        material = [code_id, str(settings_hash[0]) if settings_hash else "", int(line["id"]),
                    {name: line[name] for name in _LINE_COLUMNS if name in line.keys()},
                    profiles, *extra,
                    [[row["surface"], row["spoken_form"], row["source"], row["locked"], row["confidence"]]
                     for row in overlay.list_pronunciations(0.0)]]
        digest = hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8"))
        return digest.hexdigest()[:KEY_LENGTH]

    @staticmethod
    def _reuse(target: Path) -> bool:
        if not target.is_file():
            return False
        try:
            os.utime(target)  # gần đây nhất: bản cất cũ nhất bị bỏ trước (`_tidy`)
        except OSError:
            pass
        return True

    @staticmethod
    def _tidy(folder: Path) -> None:
        """Mỗi cuốn giữ tối đa KEEP_PER_BOOK bản (cũ nhất bỏ trước); bản dở của lần bị ngắt thì xoá."""
        try:
            entries = list(folder.iterdir())
        except OSError:
            return
        kept = []
        for entry in entries:
            if KEY_PATTERN.fullmatch(entry.stem) and entry.suffix == ".wav":
                kept.append(entry)
            elif entry.name.endswith(".part.wav"):
                entry.unlink(missing_ok=True)
        for entry in sorted(kept, key=lambda item: item.stat().st_mtime, reverse=True)[KEEP_PER_BOOK:]:
            entry.unlink(missing_ok=True)

    # ---- hàng chờ và tiến trình -----------------------------------------------------------------------------

    def _queue(self, started: float) -> None:
        """Giữ `_lock` khi trả về (nơi gọi nhả). Có người đang làm: xếp hàng tối đa MAX_WAITING, quá thì 429; chờ không quá
        phần còn lại của ngân sách thời gian."""
        if self._lock.acquire(blocking=False):
            return
        with self._guard:
            if self._waiting >= MAX_WAITING:
                raise PreviewError(HTTPStatus.TOO_MANY_REQUESTS, "Đang nghe thử vài câu khác - chờ một chút rồi bấm lại.", "busy")
            self._waiting += 1
        try:
            # Còn dưới LOAD_TIMEOUT/4 thì chờ nữa cũng không kịp nạp + đọc trong ngân sách: báo bận.
            remaining = REQUEST_BUDGET - (time.monotonic() - started)
            acquired = remaining > 5 and self._lock.acquire(timeout=remaining - 5)
        finally:
            with self._guard:
                self._waiting -= 1
        if not acquired:
            raise PreviewError(HTTPStatus.TOO_MANY_REQUESTS, "Đang nghe thử vài câu khác - chờ một chút rồi bấm lại.", "busy")

    def _spawn(self, command: list[str], environment: dict[str, str], cwd: Path) -> subprocess.Popen[str]:
        self.root.mkdir(parents=True, exist_ok=True)
        log = self.root / "preview.log"
        if log.is_file() and log.stat().st_size > 512 * 1024:
            log.unlink(missing_ok=True)
        with log.open("ab") as errors:
            return subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, env=environment,
                                    cwd=str(cwd), text=True, encoding="utf-8", bufsize=1,
                                    creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)

    def _environment(self, studio: Any, fake: bool, code_root: Path) -> dict[str, str]:
        base = dict(studio.environment(code_root)) if studio is not None else {
            "PYTHONPATH": str(code_root), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        # Mô hình đã tải lúc cài Studio: lúc nghe thử không được tự kéo bản mới (như worker - `_apply_model_network_policy`).
        offline = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1"}
        return {**os.environ, **base, **offline, **({"ABOOK_PREVIEW_FAKE": "1"} if fake else {})}

    def _run(self, studio: Any, fake: bool, code_root: Path, job: dict[str, Any], target: Path, started: float) -> None:
        """Dưới `_lock`: đưa việc (`job`: dự án, câu, và điều đang thử) cho tiến trình giọng (khởi động nó nếu chưa có / là
        bản mã khác), chờ có hạn."""
        python = str(studio.python) if studio is not None else sys.executable
        identity = (python, str(code_root), "fake" if fake else "")
        deadline = started + REQUEST_BUDGET
        # Khởi động + nạp model chung MỘT hạn; sau đó mỗi câu một hạn riêng. Cả hai nằm trong ngân sách của lượt.
        load_deadline = min(time.monotonic() + self.load_timeout, deadline)
        with self._guard:
            generation = self._generation
            child = self._child
            timer, self._timer = self._timer, None
        if timer is not None:
            timer.cancel()
        if child is not None and (child.identity != identity or not child.alive()):
            child.kill()
            child = None
        try:
            if child is None:
                popen = self.launcher([python, "-c", PREVIEW_SCRIPT], self._environment(studio, fake, code_root), code_root)
                child = _Child(popen, identity)
                with self._guard:
                    self._child = child
                child.wait(load_deadline, lambda message: message.get("event") == "ready")
            self._sequence += 1
            number = self._sequence
            target.parent.mkdir(parents=True, exist_ok=True)
            child.send({"op": "job", "id": number, **job, "salt": FIRST_TAKE_SALT, "output": str(target)})

            def mine(message: dict[str, Any]) -> bool:
                return message.get("id") == number

            loaded = child.wait(load_deadline, mine)
            # Lỗi trước khi nạp xong (không đọc được câu) là kết quả luôn; nạp xong thì chờ câu thu có hạn riêng.
            result = loaded if loaded.get("event") != "loaded" else child.wait(
                min(time.monotonic() + self.job_timeout, deadline), lambda message: mine(message) and "event" not in message)
        except queue.Empty:
            self._discard(child)
            raise PreviewError(HTTPStatus.UNPROCESSABLE_ENTITY, "Máy đọc thử quá lâu - thử lại sau ít phút.", "timeout") from None
        except _Died:
            self._discard(child)
            if self._generation != generation:
                raise PreviewError(HTTPStatus.CONFLICT, "Đang làm sách - nghe thử khi máy rảnh.", "producing") from None
            raise PreviewError(HTTPStatus.UNPROCESSABLE_ENTITY, "Phần đọc thử tắt giữa chừng - thử lại.", "failed") from None
        if not result.get("ok") or not target.is_file():
            self._discard(child)  # tiến trình sau một lỗi có thể mang bộ nhớ card hỏng: khởi động lại cho sạch
            raise PreviewError(HTTPStatus.UNPROCESSABLE_ENTITY,
                               f"Không nghe thử được: {result.get('error') or 'không có âm thanh'}", "failed")
        if self._generation == generation:  # `shutdown` giữa chừng thì không hẹn lại tiến trình đã tắt
            self._arm(child)

    def _discard(self, child: _Child | None) -> None:
        if child is None:
            return
        child.kill()
        with self._guard:
            if self._child is child:
                self._child = None

    def _arm(self, child: _Child) -> None:
        """Hẹn tắt tiến trình sau IDLE_SECONDS không ai hỏi (nhả VRAM)."""
        def expire() -> None:
            if self._lock.acquire(blocking=False):  # đang có việc thì thôi, việc ấy hẹn lại khi xong
                try:
                    self._discard(child)
                finally:
                    self._lock.release()

        timer = threading.Timer(self.idle_seconds, expire)
        timer.daemon = True
        with self._guard:
            previous, self._timer = self._timer, timer
        if previous is not None:
            previous.cancel()
        timer.start()
