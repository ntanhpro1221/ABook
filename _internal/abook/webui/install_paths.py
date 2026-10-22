"""Keep user libraries outside directories owned by the Windows uninstaller."""
import os
from pathlib import Path
from typing import Any


def validate_library_folder(folder: Path, studio: Any = None) -> None:
    protected = []
    for variable, suffix in (("LOCALAPPDATA", "ABook"), ("LOCALAPPDATA", "com.ngdtuanh.abook"),
                             ("APPDATA", "com.ngdtuanh.abook")):
        if base := os.environ.get(variable):
            protected.append(Path(base) / suffix)
    if studio is not None:
        protected.extend((studio.root, studio.app_root))
    resolved = folder.resolve()
    if any(resolved.is_relative_to(root.resolve()) for root in protected):
        raise ValueError("Thư mục này có thể bị xoá khi gỡ ABook. Bạn hãy chọn thư viện ở nơi khác để giữ sách của bạn.")
