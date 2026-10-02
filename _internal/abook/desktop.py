"""Cửa sổ app máy tính: giao diện web (abook/webui) trong Qt WebEngine - thứ PySide6 đã có sẵn.

Giữ các bất biến của GUI cũ (gui.py): một phiên bản duy nhất theo phiên người dùng (lần mở sau chỉ kích hoạt cửa
sổ đang chạy), báo "đã sẵn sàng" cho trình khởi động (start_windows.ps1) sau khi trang vẽ xong, không hỏi người
dùng giữa lúc chạy sách. Sách chạy qua supervisor nền nên đóng cửa sổ không dừng sách.

Mở bằng một file sách (`app.py "<file>.abook"` - bấm đúp file trong Explorer, xem register_file_types.ps1): cửa sổ
nhập cuốn ấy vào thư viện (webui/packages.py) rồi mở trang sách; app đang mở sẵn thì lần mở thứ hai chuyển đường dẫn
qua khoá một phiên bản cho cửa sổ đang chạy.

GPU của trang web bị tắt: dây chuyền cần ~6,2 GB trên card 8 GB khi phân tích, và docs/THROUGHPUT.md đã đo một
Unity Editor nằm im (1,6 GB) là đủ đẩy Ollama tháo model giữa chừng. Giao diện này vẽ bằng CPU là đủ mượt.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from importlib import metadata
from pathlib import Path
from typing import Any, Callable

from .desktop_shell import (
    APP_ICON_PATH,
    APP_NAME,
    INSTANCE_ACTIVATE_MESSAGE,
    claim_single_instance,
    connect_instance_activation,
    open_file_message,
    set_windows_app_identity,
    signal_startup_ready,
)

WEB_FLAGS = "--disable-gpu --disable-gpu-compositing --disable-features=Translate"
BOOK_FILE_SUFFIX = ".abook"
PROJECT_FILE_SUFFIX = ".abookproj"  # cả dự án Studio (webui/projectfile.py) - mở thành dự án mới
# Trang web nghe sự kiện này (desktop/App.tsx): mở trang sách vừa nhập, hay báo vì sao không mở được.
OPENED_EVENT = "abook-opened"


def _version() -> str:
    try:
        return metadata.version("abook")
    except metadata.PackageNotFoundError:
        return ""


def book_file_argument(argv: list[str]) -> str:
    """File sách hay file dự án trong dòng lệnh (bấm đúp file `.abook`/`.abookproj`: `app.py "<file>"`), hoặc ""."""
    return next((arg for arg in argv[1:] if arg.lower().endswith((BOOK_FILE_SUFFIX, PROJECT_FILE_SUFFIX))
                 and Path(arg).is_file()), "")


def run_desktop() -> int:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", WEB_FLAGS)
    from PySide6.QtCore import QObject, QSettings, Qt, QUrl, Signal, Slot
    from PySide6.QtGui import QColor, QIcon
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow

    from .webui import actions
    from .webui.library import Preferences
    from .webui.server import ApiError, App, Server, new_token

    class Dialogs(QObject):
        """Hộp thoại của Windows, gọi từ luồng server HTTP nhưng phải chạy trên luồng giao diện Qt."""

        request = Signal(object)

        def __init__(self, window: QMainWindow) -> None:
            super().__init__()
            self.window = window
            self.request.connect(self._run, Qt.ConnectionType.QueuedConnection)

        @Slot(object)
        def _run(self, job: Callable[[], None]) -> None:
            job()

        def _call(self, function: Callable[[], Any]) -> Any:
            done = threading.Event()
            box: dict[str, Any] = {}

            def job() -> None:
                try:
                    box["value"] = function()
                finally:
                    done.set()

            self.request.emit(job)
            done.wait()
            return box.get("value")

        def pick_folder(self, title: str, start: str) -> str | None:
            return self._call(lambda: QFileDialog.getExistingDirectory(self.window, title, start) or None)

        def pick_files(self, title: str, start: str) -> list[str]:
            return self._call(lambda: QFileDialog.getOpenFileNames(self.window, title, start, "Chương truyện (*.txt)")[0])

        def pick_book_file(self, title: str, start: str) -> str | None:
            return self._call(
                lambda: QFileDialog.getOpenFileName(self.window, title, start, f"Sách hay dự án ABook (*{BOOK_FILE_SUFFIX} *{PROJECT_FILE_SUFFIX})")[0] or None
            )

    class Window(QMainWindow):
        opened = Signal(object)  # kết quả nhập một file sách, từ luồng nền về luồng giao diện

        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle(APP_NAME)
            self.setMinimumSize(1024, 680)  # hẹp hơn thì bảng Studio và thanh phát không còn chỗ
            self.settings = QSettings("ABook", "Desktop")
            geometry = self.settings.value("geometry")
            if geometry is not None:
                self.restoreGeometry(geometry)
            else:
                self.resize(1320, 860)
            self.view = QWebEngineView(self)
            page = QWebEnginePage(self.view)
            page.setBackgroundColor(QColor("#0e1115"))
            self.view.setPage(page)
            self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            self.setCentralWidget(self.view)
            self.loaded = False
            self.waiting: list[dict[str, Any]] = []  # nhập xong trước khi trang vẽ xong: gửi khi trang sẵn sàng
            self.view.loadFinished.connect(self._on_loaded)
            self.opened.connect(self._tell_page, Qt.ConnectionType.QueuedConnection)

        def _show_from_tray(self) -> None:
            """Lần mở thứ hai của app gọi hàm này (qua khoá một phiên bản) để đưa cửa sổ lên trước."""
            self.showNormal()
            self.raise_()
            self.activateWindow()

        @Slot(bool)
        def _on_loaded(self, _ok: bool) -> None:
            self.loaded = True
            waiting, self.waiting = self.waiting, []
            for result in waiting:
                self._tell_page(result)

        @Slot(object)
        def _tell_page(self, result: dict[str, Any]) -> None:
            if not self.loaded:
                self.waiting.append(result)
                return
            detail = json.dumps(result, ensure_ascii=False)
            self.view.page().runJavaScript(f"window.dispatchEvent(new CustomEvent({OPENED_EVENT!r}, {{detail: {detail}}}))")

        def closeEvent(self, event: Any) -> None:  # noqa: N802
            self.settings.setValue("geometry", self.saveGeometry())
            super().closeEvent(event)

    set_windows_app_identity()
    app = QApplication(sys.argv)
    # Định danh lưu trữ của QtWebEngine (%LOCALAPPDATA%/ABook: bộ nhớ đệm, localStorage của trang) - cùng thư mục với
    # tuỳ chọn của app (webui/library.py). Trước 28-09 là "Ebook Reader"; trang chỉ để tiện lợi ở đó, không cần chuyển.
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    book_file = book_file_argument(sys.argv)
    instance_server = claim_single_instance(
        app, message=open_file_message(book_file) if book_file else INSTANCE_ACTIVATE_MESSAGE
    )
    if instance_server is None:
        signal_startup_ready()
        return 0

    window = Window()
    preferences = Preferences()
    web = App(
        preferences=preferences,
        # ABOOK_FAKE_RUNNER=1: thử cửa sổ mà không khởi động worker thật (máy đang sản xuất sách).
        runner=actions.FakeRunner() if os.environ.get("ABOOK_FAKE_RUNNER") == "1" else actions.BackgroundRunner(),
        token=new_token(),
        dialogs=Dialogs(window),
        version=_version(),
    )
    if preferences.get().get("syncEnabled"):
        web.set_sync(True)
    http = Server(web).start()

    def open_book_file(path: str) -> None:
        """Nhập ở luồng nền (kiểm mã băm cả cuốn: vài trăm MB), rồi báo trang web mở trang sách."""
        def work() -> None:
            try:
                result: dict[str, Any] = web.open_book_file(path)
            except ApiError as error:
                result = {"id": None, "error": error.message, "file": Path(path).name}
            except Exception as error:  # noqa: BLE001 - lỗi lạ khi nhập không được làm sập cửa sổ
                result = {"id": None, "error": f"Không mở được file sách: {error}", "file": Path(path).name}
            window.opened.emit(result)

        threading.Thread(target=work, name="open-book-file", daemon=True).start()

    window.view.loadFinished.connect(lambda _ok: signal_startup_ready())
    window.view.setUrl(QUrl(http.url))
    connect_instance_activation(instance_server, window._show_from_tray, open_book_file)
    if book_file:
        open_book_file(book_file)
    window.show()
    try:
        return app.exec()
    finally:
        web.close()
        http.stop()
