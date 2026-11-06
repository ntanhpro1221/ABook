"""Copy contract for the chapter role and remote voice review across three native surfaces."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "ui/src/studio/WorkInbox.tsx"
QT = ROOT / "desktop_qt/qml/WorkLogic.js"
ANDROID = ROOT / "mobile/android/app/src/main/java/vn/abook/player/ui/studio/StudioWork.kt"


def test_caller_kind_has_one_shared_visible_label() -> None:
    sources = [path.read_text("utf-8") for path in (WEB, QT, ANDROID)]
    patterns = [r'caller:\s*"([^"]+)"', r'"caller":\s*"([^"]+)"', r'Caller\("caller",\s*"([^"]+)"\)']
    labels = [re.search(pattern, text).group(1) for pattern, text in zip(patterns, sources)]
    assert labels == ["Người gọi / ngoài khung"] * 3


def test_role_actions_are_named_consistently_on_all_surfaces() -> None:
    for relative in ("ui/src/studio/WorkInbox.tsx", "desktop_qt/qml/WorkSpeaker.qml",
                     "mobile/android/app/src/main/java/vn/abook/player/ui/studio/WorkTab.kt"):
        text = (ROOT / relative).read_text("utf-8")
        assert "Đặt tên" in text and "Giới / giọng" in text
        assert "suggestedName" in text
