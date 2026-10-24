"""Thư viện sách và tuỳ chọn của người dùng.

Thư viện = các thư mục sách nằm TRỰC TIẾP trong thư mục thư viện, cộng những sách người dùng tự mở ở nơi khác
("gần đây"). Server chỉ đọc sách nằm trong tập ấy.

Mã sách (`book_id`) là HMAC của đường dẫn với khoá bí mật của máy này (`book_ids.key` cạnh tuỳ chọn): cùng thư mục thì
cùng mã, mà mã không giải ngược ra đường dẫn - nên link `#/book/<mã>`, ảnh chụp màn hình, nghe từ xa không lộ tên tài
khoản Windows (docs/BOOK_IDS.md).

Tuỳ chọn và vị trí nghe dở lưu ở `%LOCALAPPDATA%/ABook/preferences.json` - ghi atomic.
"""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from ..io_utils import atomic_write_bytes, atomic_write_json, file_lock, file_stamp
from ..listener_overrides import overrides_path
from . import listing_cache, notices, store

DEFAULT_PREFERENCES: dict[str, Any] = {
    "libraryRoot": "",
    # Thư mục thư viện đã từng thấy có thật (Library.root_missing): nó biến mất thì báo, không tự tạo lại thư mục rỗng.
    "libraryRootSeen": "",
    "recents": [],
    "theme": "system",
    "positions": {},
    "playbackRate": 1.0,
    "readAloudVoice": "",
    "volume": 0.9,
    "syncEnabled": False,
    # Studio từ xa (remote_studio.py): thiết bị đã ghép được điều khiển sản xuất. Tắt mặc định, tách khỏi quyền nghe.
    "remoteStudio": False,
    # Hẹn giờ ngủ: nhỏ dần bao lâu trước khi tắt, và mỗi lần "nghe thêm" cộng bao nhiêu phút.
    "sleepFadeSeconds": 30,
    "sleepExtendMinutes": 10,
    # Lưới an toàn ngủ quên: phát liên tục chừng này giờ không ai chạm máy thì tự dừng (0 = tắt).
    "safetyStopHours": 2,
    # Lịch đêm tự hẹn giờ: {"from": "22:00", "to": "06:00", "minutes": 30} hoặc None.
    "sleepSchedule": None,
    # Máy tính xách tay rút sạc: tạm dừng tạo sách (supervisor đọc thẳng khoá này - power_source.PREFERENCE_KEY).
    "pauseOnBattery": True,
    # Trình tạo sách điền sẵn cho sách MỚI (Cài đặt > Studio; soát UX a5 01-10): giọng kể ("" = giọng máy đề xuất) và chất
    # lượng. "Làm tiếp cuốn này" vẫn lấy theo phần trước.
    "newBookNarrator": "",
    "newBookProfile": "high_quality",
    # Mẫu thiết lập có tên cho sách mới (trình tạo sách): [{name, narrator, profile, analysisModel, startNow, precastWait}], tối đa 20.
    "bookTemplates": [],
    # "Đo cảm xúc nhạc chính xác hơn" (music_valence.py): tháp MuQ 1,27 GB chỉ tải khi người dùng bật; mặc định tắt. Đổi qua /api/music/local/precise.
    "preciseMusicMood": False,
    # Nhạc nền MÁY TỰ CHỌN cho sách chỉ có chữ chưa được chọn nhạc (Cài đặt > Nhạc nền; mặc định bật): tắt thì sách chưa chọn gì không có nhạc, cuốn
    # nào người nghe đã chọn nhạc (menu "Nhạc nền" của sách) vẫn phát. Đọc ở server._scene_mode.
    "autoMusic": True,
    # Phím tắt MỘT CHỮ CÁI của máy tính (B, M, [ ], ?, J/K/1-9 ở Việc cần duyệt, O/R ở Cần nghe lại; Cài đặt > Phím tắt; mặc định bật):
    # tắt cho người dùng phần mềm nhập bằng giọng nói / phím dính (WCAG 2.1.4). Space, mũi tên, Esc và phím có Ctrl/Alt vẫn chạy.
    "letterShortcuts": True,
    # Tạm dừng rồi nghe tiếp thì lùi vài giây (listen/sleep.ts rewindAfter; Cài đặt > Nghe; mặc định bật). Theo máy này, không đồng bộ sang máy khác;
    # điện thoại có công tắc cùng tên ở lõi native (soát a100 T1).
    "autoRewind": True,
}
MAX_RECENTS = 30
BOOK_PROFILES = ("fast", "balanced", "high_quality")
MAX_BOOK_TEMPLATES = 20
BOOK_TEMPLATE_NAME_MAX = 40


def clean_book_templates(raw: Any, voice_names: set[str]) -> list[dict[str, Any]]:
    """Danh sách mẫu thiết lập do giao diện gửi lên -> danh sách sạch, hoặc ValueError kèm lời báo cho người dùng.

    Chỉ giữ đúng sáu trường (còn lại bị bỏ - nhất là KHÔNG có `dropCredits`: bỏ dòng ghi công là đồng ý riêng từng cuốn, không
    nằm trong mẫu). Tên cắt khoảng trắng, 1-40 chữ, không trùng nhau (không phân biệt hoa thường); giọng kể là "" hoặc một
    giọng có thật; chất lượng là một trong ba mức."""
    if not isinstance(raw, list):
        raise ValueError("Danh sách mẫu không hợp lệ")
    if len(raw) > MAX_BOOK_TEMPLATES:
        raise ValueError(f"Tối đa {MAX_BOOK_TEMPLATES} mẫu - xoá bớt một mẫu cũ trước")
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Mẫu không hợp lệ")
        name = item.get("name")
        name = " ".join(name.split()) if isinstance(name, str) else ""
        if not 1 <= len(name) <= BOOK_TEMPLATE_NAME_MAX:
            raise ValueError(f"Tên mẫu phải dài 1-{BOOK_TEMPLATE_NAME_MAX} chữ")
        if name.casefold() in seen:
            raise ValueError(f"Đã có mẫu tên “{name}”")
        seen.add(name.casefold())
        # Giọng đã gỡ khỏi máy: mẫu về "giọng máy đề xuất" thay vì chặn cả danh sách (đổi tên một mẫu khác cũng hỏng).
        narrator = item.get("narrator", "")
        narrator = narrator.strip() if isinstance(narrator, str) and narrator.strip() in voice_names else ""
        if item.get("profile") not in BOOK_PROFILES:
            raise ValueError(f"Mức chất lượng của mẫu “{name}” không hợp lệ")
        model = item.get("analysisModel", "")
        if not isinstance(model, str) or len(model.strip()) > 200:
            raise ValueError(f"Model đọc hiểu của mẫu “{name}” không hợp lệ")
        start_now = item.get("startNow", True)
        if not isinstance(start_now, bool):
            raise ValueError(f"Lựa chọn “bắt đầu ngay” của mẫu “{name}” không hợp lệ")
        precast_wait = item.get("precastWait", False)
        if not isinstance(precast_wait, bool):
            raise ValueError(f"Lựa chọn “chờ tôi duyệt trước khi thu” của mẫu “{name}” không hợp lệ")
        cleaned.append({"name": name, "narrator": narrator.strip(), "profile": item["profile"],
                        "analysisModel": model.strip(), "startNow": start_now, "precastWait": precast_wait})
    return cleaned


class BookTemplateError(ValueError):
    """Một thao tác mẫu không làm được: `status` = 400 (sai dạng), 404 (mẫu không còn - máy khác vừa xoá), 409 (trùng tên)."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _template_key(name: Any) -> str:
    return " ".join(name.split()).casefold() if isinstance(name, str) else ""


def apply_book_template_op(templates: list[dict[str, Any]], body: dict[str, Any], voice_names: set[str]) -> list[dict[str, Any]]:
    """Một thao tác của `POST /api/book-templates` áp lên danh sách mẫu MỚI NHẤT -> danh sách sau thao tác (đã qua `clean_book_templates`).

    Ghi cả danh sách từ giao diện là cách hai thiết bị đè mất mẫu của nhau; ở đây mỗi thiết bị chỉ nói việc mình làm: `save`
    (thêm, hay `replace` đè mẫu trùng tên tại chỗ), `rename`, `delete`, `restore` (đặt lại ở chỗ cũ - "Hoàn tác" sau khi xoá).
    Mẫu không còn -> 404, trùng tên -> 409, sai dạng -> 400 (cùng lời báo của `clean_book_templates`)."""
    op = body.get("op")
    current = list(templates)

    def find(name: Any) -> int:
        key = _template_key(name)
        return next((at for at, item in enumerate(current) if _template_key(item.get("name")) == key), -1)

    def missing(name: Any) -> BookTemplateError:
        return BookTemplateError(404, f"Không còn mẫu “{' '.join(str(name).split())}”")

    def one(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise BookTemplateError(400, "Mẫu không hợp lệ")
        return clean_book_templates([raw], voice_names)[0]

    if op == "save":
        replace = body.get("replace", False)
        if not isinstance(replace, bool):
            raise BookTemplateError(400, "Thao tác mẫu không hợp lệ")
        template = one(body.get("template"))
        at = find(template["name"])
        if at < 0:
            current.append(template)
        elif replace:
            current[at] = template
        else:
            raise BookTemplateError(409, f"Đã có mẫu tên “{template['name']}”")
    elif op == "rename":
        if not isinstance(body.get("from"), str) or not isinstance(body.get("to"), str):
            raise BookTemplateError(400, "Thao tác mẫu không hợp lệ")
        at = find(body["from"])
        if at < 0:
            raise missing(body["from"])
        target = " ".join(body["to"].split())
        clash = find(target)
        if clash >= 0 and clash != at:
            raise BookTemplateError(409, f"Đã có mẫu tên “{target}”")
        current[at] = {**current[at], "name": target}
    elif op == "delete":
        if not isinstance(body.get("name"), str):
            raise BookTemplateError(400, "Thao tác mẫu không hợp lệ")
        at = find(body["name"])
        if at < 0:
            raise missing(body["name"])
        del current[at]
    elif op == "restore":
        index = body.get("index")
        if not isinstance(index, int) or isinstance(index, bool):
            raise BookTemplateError(400, "Thao tác mẫu không hợp lệ")
        template = one(body.get("template"))
        if find(template["name"]) >= 0:
            raise BookTemplateError(409, f"Đã có mẫu tên “{template['name']}”")
        current.insert(max(0, min(index, len(current))), template)
    else:
        raise BookTemplateError(400, "Thao tác mẫu không hợp lệ")
    try:
        return clean_book_templates(current, voice_names)
    except ValueError as error:
        raise BookTemplateError(400, str(error)) from error


APP_DATA_FOLDER = "ABook"


def preferences_path() -> Path:
    override = os.environ.get("ABOOK_PREFERENCES")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return Path.home() / ".abook" / "preferences.json"
    return Path(base) / APP_DATA_FOLDER / "preferences.json"


ID_KEY_FILE = "book_ids.key"
ID_PATTERN = re.compile(r"[0-9a-f]{24}")  # 96 bit đầu của HMAC-SHA256, hex
_ID_KEYS: dict[str, bytes] = {}
_ID_LOCK = threading.Lock()


def _id_key() -> bytes:
    """Khoá bí mật của mã sách trên máy này: 32 byte ngẫu nhiên, tạo lần đầu cần tới, nằm cạnh preferences.json - đi
    cùng dữ liệu nghe nó đánh khoá (sao lưu / chép thư mục dữ liệu thì mã giữ nguyên). Không ghi được thư mục (ổ chỉ đọc):
    khoá suy từ đường dẫn thư mục dữ liệu - vẫn ổn định giữa các lần mở, chỉ kém bí mật."""
    path = preferences_path().with_name(ID_KEY_FILE)
    with _ID_LOCK:
        cached = _ID_KEYS.get(str(path))
        if cached is not None:
            return cached
        key = _read_or_create_key(path)
        _ID_KEYS[str(path)] = key
        return key


def _parse_key(raw: bytes) -> bytes | None:
    try:
        key = bytes.fromhex(raw.decode("ascii").strip())
    except ValueError:  # gồm UnicodeDecodeError
        return None
    return key if len(key) >= 16 else None


def _create_exclusive(path: Path, data: bytes) -> bool:
    """Ghi `data` thành `path` nếu chưa có - trọn vẹn (file tạm + fsync rồi mới hiện tên thật) và chỉ một tiến trình thắng. False: đã có."""
    temporary = path.with_name(f"{path.name}.{secrets.token_hex(4)}.part")
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            # Windows: rename không đè file có sẵn; nơi khác: link cũng vậy (rename thì đè).
            os.rename(temporary, path) if os.name == "nt" else os.link(temporary, path)
        except FileExistsError:
            return False
        return True
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


def _read_or_create_key(path: Path) -> bytes:
    """Khoá có sẵn, hay tạo mới (cùng bản sao `book_ids.key.bak`). Khoá hỏng (cắt cụt, rỗng, ký tự lạ - soát a28 lỗi 2) mà âm thầm thay
    bằng khoá khác thì MỌI mã sách đổi: chỗ nghe, dấu trang, lịch sử mồ côi. Nên khoá hỏng được giữ lại (`notices.keep_broken`) và lấy lại
    từ bản sao; không có bản sao mới phải tạo khoá mới - kèm lời báo."""
    backup = path.with_name(path.name + ".bak")
    for _attempt in range(20):
        try:
            key = _parse_key(path.read_bytes())
        except FileNotFoundError:
            key = None
            broken = False
        except OSError:
            break
        else:
            broken = key is None
        if key is not None:
            if not backup.is_file():
                try:
                    atomic_write_bytes(backup, key.hex().encode("ascii"))
                except OSError:
                    pass
            return key
        try:
            saved = _parse_key(backup.read_bytes())
        except OSError:
            saved = None
        if broken and notices.keep_broken(path, "Khoá mã sách của app", then=(
                "app lấy lại khoá từ bản sao" if saved else
                "app phải tạo khoá mới - chỗ nghe, dấu trang đã lưu không còn gắn được với sách")) is None:
            break  # không dời được file hỏng: dùng khoá suy từ đường dẫn, không đè bản hỏng
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fresh = saved or secrets.token_bytes(32)
            created = _create_exclusive(path, fresh.hex().encode("ascii"))
        except OSError:
            break
        if not created:
            time.sleep(0.05)  # tiến trình kia vừa tạo: đọc lại khoá của nó
            continue
        if saved is None:
            try:
                atomic_write_bytes(backup, fresh.hex().encode("ascii"))
            except OSError:
                pass
        return fresh
    return hashlib.sha256(b"abook-book-ids:" + str(path.parent).encode("utf-8")).digest()


def book_id(path: Path) -> str:
    """Mã sách của thư mục `path` trên máy này: cùng thư mục (không phân biệt hoa thường, dạng viết) thì cùng mã."""
    return hmac.new(_id_key(), listing_cache.resolved(Path(path), _key).encode("utf-8"), hashlib.sha256).hexdigest()[:24]


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


PREFERENCES_WHAT = "Cài đặt của app"
CHOICES: dict[str, tuple[str, ...]] = {"theme": ("system", "light", "dark"), "newBookProfile": BOOK_PROFILES}


# Hợp đồng của các tuỳ chọn hẹn giờ ngủ và trình phát: đúng các mức giao diện đưa ra. PUT /api/preferences và lúc ĐỌC file dùng chung
# bảng này (soát a100 V2: file sửa tay / bản app khác ghi `{"from": 12}`, `-10` từng qua bước nạp rồi làm trình phát ném lỗi); Android có
# bản cùng hợp đồng ở ui/src/android/settings.ts.
SLEEP_CHOICES: dict[str, tuple[int, ...]] = {
    "sleepFadeSeconds": (10, 30, 60),
    "sleepExtendMinutes": (5, 10, 15),
    "safetyStopHours": (0, 1, 2, 3),
}
SCHEDULE_MINUTES = (15, 30, 45, 60)
NUMBER_RANGES: dict[str, tuple[float, float]] = {"playbackRate": (0.5, 3.0), "volume": (0.0, 1.0)}
_CLOCK = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def clean_sleep_schedule(value: Any) -> dict[str, Any] | None:
    """Lịch đêm `{"from": "HH:mm", "to": "HH:mm", "minutes": 15|30|45|60}` đã làm sạch, hay None nếu `value` không đúng cấu trúc / miền giá trị
    (khoá thừa bỏ đi). None cũng là "không có lịch": người gọi phân biệt bằng `value is None`."""
    if not isinstance(value, dict):
        return None
    start, end, minutes = value.get("from"), value.get("to"), value.get("minutes")
    if not (isinstance(start, str) and _CLOCK.fullmatch(start) and isinstance(end, str) and _CLOCK.fullmatch(end)):
        return None
    if isinstance(minutes, bool) or minutes not in SCHEDULE_MINUTES:
        return None
    return {"from": start, "to": end, "minutes": minutes}


def _fits(key: str, value: Any) -> bool:
    """Giá trị `value` của tuỳ chọn `key` đúng kiểu chưa (file sửa tay, bản app khác ghi: `[1]`, `null`, `"libraryRoot": 5` - soát a28
    lỗi 3), và trong miền giao diện đưa ra (soát a100 V2). Khoá lạ (không có trong DEFAULT_PREFERENCES) không xét."""
    default = DEFAULT_PREFERENCES.get(key)
    if key in CHOICES:
        return value in CHOICES[key]
    if key == "sleepSchedule":
        return value is None or clean_sleep_schedule(value) == value
    if key in SLEEP_CHOICES:
        return _is_number(value) and value in SLEEP_CHOICES[key]
    if key in NUMBER_RANGES:
        low, high = NUMBER_RANGES[key]
        return _is_number(value) and low <= value <= high
    if key == "recents":
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    if key == "positions":
        return isinstance(value, dict) and all(isinstance(item, dict) for item in value.values())
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return default is None or isinstance(value, type(default))


class Preferences:
    """Tuỳ chọn + chỗ nghe dở. Hỏng thì giữ bản hỏng + báo (notices); hai tiến trình cùng hồ sơ thì mỗi lần sửa đọc lại file nếu bên kia
    vừa ghi, sửa trên bản mới nhất rồi ghi - dưới khoá file (`io_utils.file_lock`), không bên nào đè mất cập nhật của bên kia."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or preferences_path()
        self._lock = threading.Lock()
        # Có file mà không đọc được (chương trình khác giữ): mặc định trong bộ nhớ, KHÔNG ghi đè file thật; đọc lại ở lần sửa kế.
        self._unread = False
        try:
            self._data = self._load()
        except notices.Unreadable:
            self._data, self._unread = self._defaults({}), True
        self._stamp = file_stamp(self.path)

    def _parse(self) -> dict[str, Any] | None:
        """Tuỳ chọn trên đĩa, khoá sai kiểu đã bỏ; chưa có file / hỏng cả file: None. Có khoá sai kiểu: giữ bản cũ + báo, rồi ghi lại bản
        sạch ngay (lần mở sau không báo lại)."""
        raw = notices.read_json(self.path, PREFERENCES_WHAT, lambda data: isinstance(data, dict))
        if raw is None:
            return None
        bad = [key for key, value in raw.items() if key in DEFAULT_PREFERENCES and not _fits(key, value)]
        if not bad:
            return raw
        clean = {key: value for key, value in raw.items() if key not in bad}
        if notices.keep_broken(self.path, "Một vài cài đặt của app", then="các cài đặt ấy về mặc định", copy_only=True) is None:
            raise notices.Unreadable("Chưa giữ được cài đặt cũ của bạn. Bạn hãy thử lại.")
        try:
            atomic_write_json(self.path, clean)
        except OSError:
            pass
        return clean

    def _load(self, keep: dict[str, Any] | None = None) -> dict[str, Any]:
        """Tuỳ chọn mặc định đè bằng những gì đọc được. `keep`: file mất / hỏng giữa chừng (đọc lại khi tiến trình khác vừa ghi) thì giữ
        bản trong bộ nhớ - lần ghi kế đưa nó lại ra đĩa."""
        parsed = self._parse()
        if parsed is None and keep is not None:
            return keep
        return self._defaults(parsed or {})

    @staticmethod
    def _defaults(parsed: dict[str, Any]) -> dict[str, Any]:
        data = json.loads(json.dumps(DEFAULT_PREFERENCES))
        data.update(parsed)
        if not data["libraryRoot"].strip():
            data["libraryRoot"] = str(Path.home() / "Audiobooks")
        return data

    @contextlib.contextmanager
    def _changing(self) -> Iterator[None]:
        """Sửa tuỳ chọn: khoá luồng + khoá file, đọc lại nếu tiến trình khác đã ghi từ lần mình đọc / ghi cuối (soát a28 lỗi 14)."""
        with self._lock, file_lock(self.path):
            if self._unread or file_stamp(self.path) != self._stamp:
                try:
                    self._data = self._load(keep=None if self._unread else self._data)
                    self._unread = False
                except notices.Unreadable:
                    self._unread = True
                self._stamp = file_stamp(self.path)
            if self._unread:
                raise notices.Unreadable("Chưa đọc được cài đặt của bạn. Bạn hãy thử lại.")
            before = json.loads(json.dumps(self._data))
            try:
                yield
            except BaseException:
                self._data = before
                raise

    def get(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._data))

    def _apply(self, changes: dict[str, Any]) -> None:
        for key, value in changes.items():
            if key in DEFAULT_PREFERENCES and _fits(key, value) and not (key == "libraryRoot" and not value.strip()):
                self._data[key] = value

    def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        with self._changing():
            self._apply(changes)
            self._save()
            return json.loads(json.dumps(self._data))

    def modify(self, change: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        """Sửa theo giá trị MỚI NHẤT: `change` nhận tuỳ chọn hiện có (bản sao, sau khi đọc lại file nếu tiến trình khác vừa ghi) và trả những
        khoá cần đổi. Cả đọc lẫn ghi nằm trong cùng một khoá như `update` - hai thiết bị cùng sửa một danh sách (mẫu thiết lập) không đè
        mất nhau. `change` ném lỗi thì không ghi gì."""
        with self._changing():
            self._apply(change(json.loads(json.dumps(self._data))))
            self._save()
            return json.loads(json.dumps(self._data))

    def remember_position(self, book: str, chapter_id: int, seconds: float, duration: float) -> None:
        with self._changing():
            positions = self._data.setdefault("positions", {})
            positions[book] = {"chapterId": int(chapter_id), "seconds": round(float(seconds), 1),
                               "duration": round(float(duration), 1), "at": time.time()}
            self._save()

    def rename_positions(self, renamed: dict[str, str]) -> None:
        """Đổi khoá chỗ nghe dở ({mã cũ: mã mới}, `legacy_ids`); hai khoá về cùng một cuốn: chỗ ghi sau thắng."""
        with self._changing():
            positions = self._data.get("positions")
            if not isinstance(positions, dict) or not any(old in positions for old in renamed):
                return
            for old, new in renamed.items():
                if old == new or old not in positions:
                    continue
                moved = positions.pop(old)
                current = positions.get(new)
                if not isinstance(current, dict) or float((moved or {}).get("at") or 0) > float(current.get("at") or 0):
                    positions[new] = moved
            self._save()

    def add_recent(self, path: Path) -> None:
        with self._changing():
            recents = [item for item in self._data.get("recents", []) if _key(Path(item)) != _key(path)]
            self._data["recents"] = [str(path), *recents][:MAX_RECENTS]
            self._save()

    def forget_recent(self, path: Path) -> None:
        with self._changing():
            recents = [item for item in self._data.get("recents", []) if _key(Path(item)) != _key(path)]
            if recents != self._data.get("recents", []):
                self._data["recents"] = recents
                self._save()

    def _save(self) -> None:
        # Ghi nguyên tử + fsync (mất điện không để lại file rỗng). Supervisor của sách đang chạy đọc file này (power_source, khi máy chạy pin):
        # trên Windows, đổi tên đè lên file đang mở báo PermissionError - atomic_write_json thử lại như file state của dây chuyền (soát QA 29-09).
        if self._unread:
            return  # chưa đọc được bản trên đĩa: ghi bây giờ là đè mất cài đặt thật
        atomic_write_json(self.path, self._data, compact=True)  # ghi lại mỗi lần đổi một cài đặt
        self._stamp = file_stamp(self.path)


class Library:
    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    @property
    def root(self) -> Path:
        return Path(self.preferences.get()["libraryRoot"]).expanduser()

    def root_missing(self) -> bool:
        """Thư mục thư viện không còn: ổ rời rút ra (cả ổ cũng không có), hay thư mục ĐÃ TỪNG có (`libraryRootSeen`) bị đổi tên / chuyển /
        xoá (soát a28 lỗi 6). Thư mục chưa từng có (lần đầu dùng, mặc định ~/Audiobooks) thì không tính - app tạo nó khi thêm cuốn đầu tiên."""
        root = self.root
        if root.is_dir():
            return False
        seen = self.preferences.get().get("libraryRootSeen") == str(root)
        if not seen and _key(root) == _key(Path.home() / "Audiobooks"):
            return False  # mặc định CHƯA TỪNG có; đã thấy một lần rồi mà biến mất thì báo như mọi chỗ khác (soát a97 V4)
        return seen or not root.parent.is_dir()

    def _saw_root(self, root: Path) -> None:
        if self.preferences.get().get("libraryRootSeen") != str(root):
            try:
                self.preferences.update({"libraryRootSeen": str(root)})
            except OSError:
                pass  # thư mục dữ liệu chỉ đọc: chỉ mất lời báo "thư viện biến mất"

    def projects(self) -> list[Path]:
        root = self.root

        def scan() -> dict[str, Path]:
            found: dict[str, Path] = {}
            try:
                children = sorted(root.iterdir()) if root.is_dir() else []
            except OSError:
                children = []
            if root.is_dir():
                self._saw_root(root)
            for child in children:
                if child.is_dir() and store.is_project(child):
                    found.setdefault(_key(child), child.resolve())
            return found

        # Thư mục dự án: đệm theo mốc sửa của thư viện và các thư mục con (listing_cache) - mỗi yêu cầu theo mã sách liệt kê lại cả thư viện.
        found = dict(listing_cache.cached(("projects", str(root)), listing_cache.signature(root), scan))
        for item in self.preferences.get().get("recents", []):
            path = Path(item)
            if store.is_project(path):
                found.setdefault(_key(path), path.resolve())
        return list(found.values())

    def forget(self, project: Path) -> None:
        """Dự án đã bị xoá: bỏ khỏi danh sách gần đây và bộ đệm tóm tắt."""
        self.preferences.forget_recent(project)
        with self._lock:
            self._cache.pop(_key(project), None)

    def resolve(self, value: str) -> Path | None:
        """Dự án mang mã `value`; ngoài thư viện: None."""
        return self.find(value, self.projects())

    @staticmethod
    def find(value: str, allowed: list[Path]) -> Path | None:
        """Cuốn mang mã `value` trong `allowed`."""
        if ID_PATTERN.fullmatch(value):
            return next((path for path in allowed if book_id(path) == value), None)
        return None

    def packages(self) -> list[Path]:
        """Cuốn mở từ file `.abook` (webui/packages.py) - nghe được, không phải dự án của Studio."""
        from . import packages  # packages -> listening -> library: nhập lúc gọi, không lúc nạp module

        return packages.folders(self.root)

    def imported_packages(self) -> list[Path]:
        """Chỉ cuốn người dùng nhập từ file (không cuốn ảo của máy khác) - phần thư viện này chia sẻ cho máy đã ghép."""
        from . import packages

        return packages.local_folders(self.root)

    def resolve_sharable(self, value: str) -> Path | None:
        """Cuốn máy đã ghép đòi được: dự án, hay cuốn nhập từ file (không cuốn ảo của máy khác - chống vòng soi nhau)."""
        project = self.resolve(value)
        if project is not None:
            return project
        return self.find(value, self.imported_packages())

    def resolve_listenable(self, value: str) -> Path | None:
        """Như `resolve`, cho phía Nghe: dự án hoặc cuốn đã nhập từ file."""
        project = self.resolve(value)
        if project is not None:
            return project
        return self.find(value, self.packages())

    def summary(self, project: Path, *, running: bool, starting: bool = False, lease_after: float | None = None) -> dict[str, Any]:
        # Cả mốc của overrides.json (yêu cầu mới của người nghe đổi "pendingChanges") và tên đặt lại - không chạm DB.
        stamp = (store.touched(project), _mtime(overrides_path(project)), _mtime(project / store.RUN_MARKER),
                 _mtime(project / store.TITLE_FILE))
        key = _key(project)
        with self._lock:
            cached = self._cache.get(key)
        if cached and cached[0] == stamp and not running and not cached[1].get("running") and not starting:
            result = dict(cached[1])
        else:
            result = store.summarize(project, running=running, lease_after=lease_after)
            with self._lock:
                self._cache[key] = (stamp, result)
            result = dict(result)
        result["id"] = book_id(project)
        result["starting"] = starting
        position = self.preferences.get().get("positions", {}).get(result["id"])
        result["position"] = position
        return result
