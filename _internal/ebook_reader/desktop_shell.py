"""Phần vỏ cửa sổ dùng chung cho mọi giao diện máy tính: danh tính app trên Windows, khoá một phiên bản, báo "đã sẵn
sàng" cho trình khởi động.

Tách khỏi `gui.py` (giao diện cũ) vì `gui.py` nạp cả gói sản xuất (worker, pipeline, cấu hình...): cửa sổ mới
(`desktop.py`) - và sau này một bản chỉ-để-nghe - không được kéo theo dây chuyền chỉ để có vài hàm vỏ. Hằng số giữ
nguyên như cũ để giao diện cũ và mới dùng CHUNG một khoá: không bao giờ chạy hai cửa sổ app cùng lúc.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

APP_NAME = "ABook"
APP_USER_MODEL_ID = "EbookReader.Desktop"
INSTANCE_SERVER_NAME = f"{APP_USER_MODEL_ID}.SingleInstance"
INSTANCE_ACTIVATE_MESSAGE = b"activate"
INSTANCE_OPEN_PREFIX = b"open\n"
INSTANCE_CONNECT_TIMEOUT_MS = 250
STARTUP_READY_FILE_ENV = "EBOOK_READER_READY_FILE"
APP_ASSET_DIR = Path(__file__).resolve().parent / "assets"
APP_ICON_PATH = APP_ASSET_DIR / ("app.ico" if os.name == "nt" else "app.png")


def set_windows_app_identity() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass


def open_file_message(path: str) -> bytes:
    """Lần mở thứ hai mang theo một file (bấm đúp file `.abook` khi app đang mở): cửa sổ đang chạy mở file ấy."""
    return INSTANCE_OPEN_PREFIX + path.encode("utf-8")


def instance_message_file(message: bytes) -> str:
    """Đường dẫn file trong một lời nhắn của lần mở thứ hai, hoặc "" (chỉ gọi cửa sổ lên)."""
    if not message.startswith(INSTANCE_OPEN_PREFIX):
        return ""
    return message[len(INSTANCE_OPEN_PREFIX):].decode("utf-8", "replace").strip()


def notify_running_instance(server_name: str = INSTANCE_SERVER_NAME, message: bytes = INSTANCE_ACTIVATE_MESSAGE) -> bool:
    from PySide6.QtNetwork import QLocalSocket

    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if not socket.waitForConnected(INSTANCE_CONNECT_TIMEOUT_MS):
        socket.abort()
        return False
    socket.write(message)
    socket.flush()
    socket.waitForBytesWritten(INSTANCE_CONNECT_TIMEOUT_MS)
    socket.disconnectFromServer()
    return True


def claim_single_instance(app: Any, server_name: str = INSTANCE_SERVER_NAME,
                          message: bytes = INSTANCE_ACTIVATE_MESSAGE) -> Any | None:
    """QLocalServer giữ khoá, hoặc None nếu đã có một cửa sổ app đang chạy (và đã nhận `message`: gọi lên trước,
    hay mở một file)."""
    from PySide6.QtNetwork import QLocalServer

    if notify_running_instance(server_name, message):
        return None
    server = QLocalServer(app)
    if server.listen(server_name):
        return server
    if notify_running_instance(server_name, message):
        return None
    QLocalServer.removeServer(server_name)
    if server.listen(server_name):
        return server
    raise RuntimeError(f"Không thể khóa single-instance: {server.errorString()}")


def signal_startup_ready() -> None:
    ready_path = os.environ.get(STARTUP_READY_FILE_ENV, "").strip()
    if not ready_path:
        return
    try:
        Path(ready_path).write_text(str(os.getpid()), encoding="ascii")
    except OSError:
        # Launcher vẫn còn đường dự phòng bằng MainWindowHandle và process exit.
        pass


def connect_instance_activation(server: Any, show: Callable[[], None],
                                open_file: Callable[[str], None] | None = None) -> None:
    """Lần mở thứ hai của app gửi lời nhắn qua khoá: gọi `show` để đưa cửa sổ đang chạy lên trước, và `open_file` nếu
    lời nhắn mang một file (`open_file_message`)."""
    from PySide6.QtCore import QTimer

    def activate_pending_instance() -> None:
        received = False
        files: list[str] = []
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            if connection is None:
                continue
            if not connection.bytesAvailable():
                connection.waitForReadyRead(INSTANCE_CONNECT_TIMEOUT_MS)  # lời nhắn có thể tới sau tín hiệu kết nối
            file = instance_message_file(bytes(connection.readAll()))
            if file:
                files.append(file)
            connection.disconnectFromServer()
            received = True
        if received:
            show()
        if open_file is not None:
            for file in files:
                open_file(file)

    server.newConnection.connect(activate_pending_instance)
    QTimer.singleShot(0, activate_pending_instance)
