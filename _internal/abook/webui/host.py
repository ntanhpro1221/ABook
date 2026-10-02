"""Host của app Windows đóng gói (docs/PACKAGING.md): đúng server giao diện của cửa sổ Qt (desktop.py) nhưng không có Qt.

Vỏ Tauri (`_internal/shell`) chạy tiến trình này và nói chuyện với nó qua stdin/stdout, mỗi dòng một JSON: host báo
địa chỉ để mở cửa sổ, nhờ vỏ mở hộp thoại Windows, nhờ vỏ phát sự kiện vào trang; vỏ chuyển file `.abook` được mở và
lệnh thoát; vỏ báo có bản mới, host chuyển lệnh "Cập nhật" của người dùng về vỏ. Trang web vẫn chỉ nói chuyện với
server Python như trong cửa sổ Qt - không mở IPC của Tauri cho một trang nằm ở địa chỉ http.

stdin đóng (vỏ chết, bị giết) cũng là thoát: không bao giờ bỏ lại một server mồ côi giữ cổng đồng bộ.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable, TextIO

# Trang web nghe các sự kiện này (desktop/App.tsx). Mở file sách: cùng tên với cửa sổ Qt (desktop.OPENED_EVENT).
OPENED_EVENT = "abook-opened"
UPDATE_EVENT = "abook-update"


class Channel:
    """Ống hai chiều với vỏ: `send` ghi một dòng JSON (có khoá - nhiều luồng cùng gửi), `serve` đọc từng dòng cho tới khi
    vỏ đóng ống hay gửi `quit`."""

    def __init__(self, reader: TextIO, writer: TextIO) -> None:
        self.reader = reader
        self.writer = writer
        self._lock = threading.Lock()

    def send(self, message: dict[str, Any]) -> None:
        line = json.dumps(message, ensure_ascii=False)
        with self._lock:
            try:
                self.writer.write(line + "\n")
                self.writer.flush()
            except (OSError, ValueError):
                pass  # vỏ đã đi: vòng đọc sẽ thấy stdin đóng và thoát

    def serve(self, handlers: dict[str, Callable[[dict[str, Any]], None]]) -> None:
        for line in self.reader:
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if not isinstance(message, dict):
                continue
            if message.get("quit"):
                return
            for key, handler in handlers.items():
                if key in message:
                    handler(message)
                    break


class PipeDialogs:
    """Hộp thoại Windows do vỏ mở (cửa sổ Qt: `desktop.Dialogs`). Gọi từ luồng xử lý HTTP; chờ tới khi người dùng
    chọn xong hay huỷ. Vỏ đi mất giữa chừng thì mọi hộp thoại đang chờ trả "không chọn gì"."""

    def __init__(self, channel: Channel) -> None:
        self.channel = channel
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        self._waiting: dict[int, tuple[threading.Event, dict[str, Any]]] = {}
        self._closed = False

    def _ask(self, kind: str, title: str, start: str) -> Any:
        done = threading.Event()
        box: dict[str, Any] = {}
        with self._lock:
            if self._closed:
                return None
            dialog = next(self._ids)
            self._waiting[dialog] = (done, box)
        self.channel.send({"dialog": dialog, "kind": kind, "title": title, "start": start})
        done.wait()
        return box.get("result")

    def answer(self, message: dict[str, Any]) -> None:
        with self._lock:
            waiting = self._waiting.pop(message.get("dialog"), None)  # type: ignore[arg-type]
        if waiting is not None:
            done, box = waiting
            box["result"] = message.get("result")
            done.set()

    def close(self) -> None:
        with self._lock:
            self._closed = True
            waiting, self._waiting = list(self._waiting.values()), {}
        for done, _box in waiting:
            done.set()

    def pick_folder(self, title: str, start: str) -> str | None:
        result = self._ask("folder", title, start)
        return result if isinstance(result, str) and result else None

    def pick_files(self, title: str, start: str) -> list[str]:
        result = self._ask("files", title, start)
        return [item for item in result if isinstance(item, str) and item] if isinstance(result, list) else []

    def pick_book_file(self, title: str, start: str) -> str | None:
        result = self._ask("book", title, start)
        return result if isinstance(result, str) and result else None


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="abook.webui.host")
    parser.add_argument("--version", default="", help="phiên bản app (vỏ biết, gói Python nhúng không có metadata)")
    parser.add_argument("--fake-runner", action="store_true", help="không khởi động worker thật (thử giao diện)")
    parser.add_argument("--studio", default="", help="thư mục Studio tải thêm (bản cài); trống: bản dev, runtime cạnh mã")
    return parser.parse_args(argv)


def run(reader: TextIO, writer: TextIO, argv: list[str] | None = None) -> int:
    from .actions import BackgroundRunner, FakeRunner
    from .library import Preferences
    from .server import ApiError, App, Server, new_token

    args = _arguments(argv)
    channel = Channel(reader, writer)
    dialogs = PipeDialogs(channel)
    preferences = Preferences()
    fake = args.fake_runner or os.environ.get("ABOOK_FAKE_RUNNER") == "1"
    studio = None
    if args.studio:
        from ..config import build_settings
        from .actions import StudioRunner
        from .studio_setup import StudioSetup

        studio = StudioSetup(Path(args.studio), Path(__file__).resolve().parents[2],
                             analysis_model=str(build_settings()["analysis"]["model"]))
    runner = FakeRunner() if fake else StudioRunner(studio) if studio is not None else BackgroundRunner()
    web = App(preferences=preferences, runner=runner, token=new_token(), dialogs=dialogs, version=args.version)
    web.studio = studio
    web.shell = channel.send  # "Cập nhật": App.install_update gửi {"install_update": true} về vỏ
    if preferences.get().get("syncEnabled"):
        web.set_sync(True)
    http = Server(web).start()

    def update_found(message: dict[str, Any]) -> None:
        update = message.get("update")
        web.update = ({"version": str(update.get("version") or ""), "notes": str(update.get("notes") or "")}
                      if isinstance(update, dict) and update.get("version") else None)
        channel.send({"event": UPDATE_EVENT, "detail": web.update})  # trang đã mở: đọc lại /api/app, hiện nút

    def open_book_file(message: dict[str, Any]) -> None:
        """Nhập ở luồng nền (kiểm mã băm cả cuốn: vài trăm MB), rồi nhờ vỏ báo trang web mở trang sách."""
        path = str(message.get("open") or "")

        def work() -> None:
            try:
                result: dict[str, Any] = web.open_book_file(path)
            except ApiError as error:
                result = {"id": None, "error": error.message, "file": Path(path).name}
            except Exception as error:  # noqa: BLE001 - lỗi lạ khi nhập không được làm sập app
                result = {"id": None, "error": f"Không mở được file sách: {error}", "file": Path(path).name}
            channel.send({"event": OPENED_EVENT, "detail": result})

        threading.Thread(target=work, name="open-book-file", daemon=True).start()

    channel.send({"ready": http.url})
    try:
        channel.serve({"dialog": dialogs.answer, "open": open_book_file, "update": update_found})
    finally:
        dialogs.close()
        web.close()
        http.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    # Ống là của giao thức: mọi `print` lạc (thư viện, gỡ lỗi) đi sang stderr - vỏ ghi stderr vào nhật ký.
    reader = sys.stdin
    writer = sys.stdout
    for stream in (reader, writer):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.stdout = sys.stderr
    if reader is None or writer is None:
        return 2  # chạy tay bằng pythonw: không có ống thì không có vỏ để nói chuyện
    return run(reader, writer, argv)


if __name__ == "__main__":
    raise SystemExit(main())
