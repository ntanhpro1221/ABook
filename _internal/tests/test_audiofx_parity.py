"""Playback controls share the same public contract on all three surfaces."""
from pathlib import Path
import pytest
from scripts.ui_copy_source import expand

ROOT = Path(__file__).resolve().parents[1]


def copy_source(path: Path) -> str:
    language = "kt" if path.suffix == ".kt" else "ts" if path.suffix in {".ts", ".tsx"} else "qml"
    return expand(path.read_text(encoding="utf-8"), language)


@pytest.mark.parametrize("label", ["Phẳng", "Rõ lời", "Trầm ấm", "Bổng", "Giảm chói",
    "80 Hz", "250 Hz", "1 kHz", "4 kHz", "12 kHz"])
def test_equalizer_choices_match(label):
    for path in [ROOT / "ui/src/listen/audioFx.ts",
                 ROOT / "mobile/android/app/src/main/java/vn/abook/player/AudioFxDsp.kt",
                 ROOT / "desktop_qt/qml/AudioFxPanel.qml"]:
        assert label in copy_source(path), path


@pytest.mark.parametrize("label", ["Âm lượng", "Tăng âm", "Cao độ", "Về mặc định", "Equalizer", "Tăng trầm",
    "Dùng chung mặc định. Chỉ chỉnh giọng đọc; nhạc nền có mức riêng.", "Riêng sách này", "Mono", "Cân bằng",
    "Bỏ khoảng lặng", "Ngưỡng lặng", "Dài tối thiểu", "Giữ khoảng nghỉ"])
def test_audio_panel_copy_matches(label):
    for path in [ROOT / "ui/src/listen/AudioFxPanel.tsx",
                 ROOT / "mobile/android/app/src/main/java/vn/abook/player/ui/nowplaying/AudioFxPage.kt",
                 ROOT / "desktop_qt/qml/AudioFxPanel.qml"]:
        assert label in copy_source(path), path


def test_processing_is_narration_only():
    # Music players must never inherit voice pitch / EQ when switching chapters.
    assert "attachAudioFx" not in (ROOT / "ui/src/listen/musicBed.ts").read_text(encoding="utf-8")
    assert "AudioFxChain" not in (ROOT / "mobile/android/app/src/main/java/vn/abook/player/MusicBed.kt").read_text(encoding="utf-8")
    mixer = (ROOT / "desktop_qt/src/musicmixer.cpp").read_text(encoding="utf-8")
    assert "if (s->streaming) { s->fxDsp.configure" in mixer
