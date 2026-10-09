"""Khung chung của các mô-đun giọng đọc trên máy tải thêm (vieneu_module.py, supertonic_module.py): bộ cài không mang gì, người dùng bấm mới tải.
Phần dùng chung ở đây: dấu của mô-đun (`module.json`, ghim từng phần đã tải), trạng thái tải / đo, luồng nền (tải từng phần rồi tự đo vài giây,
lỗi thành một câu cho người dùng), tải danh sách file vào một thư mục. Phần riêng (có những phần nào, đặt ở đâu, đo ra sao) do từng mô-đun lo.
"""
from __future__ import annotations

import hashlib
import shutil
import threading
from pathlib import Path
from typing import Any, Callable

from .. import io_utils
from . import music_module, studio_setup
from .music_module import Component

STAMP_FILE = "module.json"
DOWNLOADS = "dl"


def pin(files: tuple[studio_setup.Download, ...]) -> str:
    return hashlib.sha256("\n".join(f"{item.name} {item.sha256}" for item in files).encode()).hexdigest()


def download_files(part: Component, target: Path, progress: Callable[[int], None], cancelled: Callable[[], bool] = lambda: False) -> None:
    """Tải các file của `part` thẳng vào `target`: `studio_setup.download` ghi `.part` rồi đổi tên sau khi khớp băm, nên engine đang chạy chỉ thấy file đủ.
    `cancelled` (người dùng bấm Huỷ): dừng giữa chừng, `.part` ở lại để lần tải sau làm tiếp bằng Range."""
    done = 0
    for item in part.downloads:
        studio_setup.download(item, target / item.name, lambda have, _total, offset=done: progress(offset + have), cancelled)
        done += item.size


class ModuleCore:
    """Trạng thái + luồng nền của MỘT mô-đun. `noun`: tên người dùng thấy trong câu báo lỗi ("giọng VieNeu"); `thread`: tên luồng; `shared`: các
    phần sống ở nơi khác (thư viện chạy model, bộ đọc chữ chung) - tự giữ dấu của mình, mô-đun này không ghi ghim của chúng; `usable()`: đã có
    giọng nào dùng được chưa (chưa thì không đo)."""

    def __init__(self, noun: str, thread: str, shared: frozenset[str], usable: Callable[[], bool]) -> None:
        self.noun, self.thread_name, self.shared, self.usable = noun, thread, shared, usable
        self.lock = threading.RLock()
        self.folder: Path | None = None
        # `cancelled`: lần tải vừa rồi bị người dùng huỷ (hiện "Đã huỷ - lần tải sau làm tiếp từ chỗ dừng"); xoá khi bắt đầu tải lại.
        self.state: dict[str, Any] = {"downloading": False, "benchmarking": False, "done": 0, "total": 0, "error": "", "cancelled": False}
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._bench: Callable[[str], dict[str, Any]] | None = None
        self._after: Callable[[], None] | None = None

    # ---- cấu hình, dấu ------------------------------------------------------------------------------------------------------------
    def configure(self, folder: Path | str | None, benchmark: Callable[[str], dict[str, Any]] | None,
                  after_install: Callable[[], None] | None) -> None:
        """`benchmark(tầng)`: tự đo sau khi tải; `after_install`: nạp lại giọng (bỏ engine đang nạp). Trạng thái về trắng."""
        with self.lock:
            self.folder = Path(folder) if folder is not None else None
            self._bench, self._after = benchmark, after_install
            self.state.update(downloading=False, benchmarking=False, done=0, total=0, error="", cancelled=False)

    def ensure_folder(self, name: str) -> None:
        """Cho Studio (tiến trình dây chuyền không gọi `configure`): chưa ai cấu hình thì dùng chỗ server đặt mô-đun - cạnh
        preferences.json (`library.preferences_path`), thư mục `name`."""
        with self.lock:
            if self.folder is None:
                from .library import preferences_path

                self.folder = preferences_path().with_name(name)

    def read_stamp(self) -> dict[str, Any]:
        import json

        if self.folder is None:
            return {}
        try:
            data = json.loads((self.folder / STAMP_FILE).read_bytes().decode("utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def write_stamp(self, data: dict[str, Any]) -> None:
        if self.folder is not None:
            io_utils.atomic_write_json(self.folder / STAMP_FILE, {"version": 1, **{k: v for k, v in data.items() if k != "version"}})

    def pins(self) -> dict[str, str]:
        pins = self.read_stamp().get("pins")
        return {str(k): str(v) for k, v in pins.items()} if isinstance(pins, dict) else {}

    def benchmarks(self) -> dict[str, Any]:
        bench = self.read_stamp().get("benchmark")
        return bench if isinstance(bench, dict) else {}

    # ---- tải ----------------------------------------------------------------------------------------------------------------------
    def busy(self) -> bool:
        return (self.state["downloading"] or self.state["benchmarking"]) and self._thread is not None and self._thread.is_alive()

    def begin(self, needed: list[Component], install: Callable[[Component, Callable[[int], None]], None],
              finish: Callable[[], None], tiers: Callable[[set[str]], list[str]]) -> None:
        """Tải `needed` ở luồng nền (người gọi giữ `lock`, đã kiểm `busy()` và cấu hình). Phần bị chặn thì ghi lỗi thay vì tải. `install(phần,
        báo tiến độ)`: cài một phần; `finish()`: việc sau khi mọi phần xong (đưa thư viện vào sys.path); `tiers(các phần đã tải)`: giọng cần đo lại."""
        self.state.update(error="", done=0, cancelled=False)
        self._cancel.clear()
        if not needed:
            return
        reason = next((part.blocked for part in needed if part.blocked and not part.external), "")
        if reason:
            self.state["error"] = reason[0].upper() + reason[1:] + "."
            return
        self.state.update(downloading=True, total=sum(part.size for part in needed))
        self._thread = threading.Thread(target=self._run, args=(needed, install, finish, tiers), name=self.thread_name, daemon=True)
        self._thread.start()

    def join(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def cancel(self) -> None:
        """Người dùng bấm Huỷ: dừng ở nhịp đọc kế của file đang tải (`.part` giữ lại, lần tải sau làm tiếp). Không có lần tải nào thì không làm gì."""
        if self.state["downloading"]:  # không lấy khoá: luồng tải có thể đang giữ nó (cài thư viện dùng chung)
            self._cancel.set()

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def _run(self, needed: list[Component], install: Callable[[Component, Callable[[int], None]], None], finish: Callable[[], None],
             tiers: Callable[[set[str]], list[str]]) -> None:
        assert self.folder is not None
        try:
            finished = 0
            stamp = self.read_stamp()
            pins = self.pins()
            if self._after is not None:
                self._after()  # bỏ engine đang nạp: file model sắp được thay
            for part in needed:
                def progress(done: int, base: int = finished) -> None:
                    with self.lock:
                        self.state["done"] = base + done

                install(part, progress)
                finished += part.size
                if part.id not in self.shared:
                    pins[part.id] = part.pin
                    stamp["pins"] = pins
                    self.write_stamp(stamp)
                with self.lock:
                    self.state["done"] = finished
            finish()
            shutil.rmtree(self.folder / DOWNLOADS, ignore_errors=True)
            if self._after is not None:
                self._after()
            with self.lock:
                self.state.update(downloading=False, error="")
            self.measure(tiers({part.id for part in needed}))
        except studio_setup.Cancelled:
            with self.lock:
                self.state.update(downloading=False, error="", done=0, cancelled=True)
        except Exception as error:  # noqa: BLE001 - mọi lỗi thành một câu cho người dùng
            with self.lock:
                self.state.update(downloading=False, error=f"Không tải được {self.noun}: {music_module._reason(error)}.")
        finally:
            with self.lock:
                self.state["downloading"] = False

    # ---- đo -----------------------------------------------------------------------------------------------------------------------
    def measure(self, tiers: list[str]) -> None:
        """Tự đo các giọng vừa tải (vài giây mỗi giọng); lỗi đo không làm hỏng lần tải."""
        if self._bench is None or not self.usable():
            return
        with self.lock:
            self.state["benchmarking"] = True
        try:
            results = self.benchmarks()
            for tier in tiers:
                try:
                    results[tier] = self._bench(tier)
                except Exception:  # noqa: BLE001
                    results.pop(tier, None)
            stamp = self.read_stamp()
            stamp["benchmark"] = results
            self.write_stamp(stamp)
        finally:
            with self.lock:
                self.state["benchmarking"] = False

    def remove(self, directory: Path, part: str, tier: str) -> None:
        """Gỡ một phần đã tải để lấy lại chỗ: bỏ engine đang nạp (giữ file), xoá `directory`, quên ghim của `part` và kết quả đo của `tier`."""
        import gc

        with self.lock:
            if self.busy():
                raise ValueError(f"Đang tải {self.noun} - chờ tải xong rồi hãy gỡ")
            if self._after is not None:
                self._after()
            gc.collect()  # phiên onnxruntime cuối cùng buông file thì Windows mới cho xoá
            shutil.rmtree(directory, ignore_errors=True)
            stamp = self.read_stamp()
            stamp["pins"] = {key: value for key, value in self.pins().items() if key != part}
            stamp["benchmark"] = {key: value for key, value in self.benchmarks().items() if key != tier}
            self.write_stamp(stamp)

    def measure_again(self, tiers: list[str]) -> None:
        """Người dùng bấm "Đo lại": đo lại `tiers` ở luồng nền (không làm gì khi đang tải / đang đo hay không có giọng nào)."""
        with self.lock:
            if self.state["downloading"] or self.state["benchmarking"] or not tiers:
                return
            self.state["benchmarking"] = True
            self._thread = threading.Thread(target=self.measure, args=(tiers,), name=self.thread_name + "-bench", daemon=True)
            self._thread.start()
