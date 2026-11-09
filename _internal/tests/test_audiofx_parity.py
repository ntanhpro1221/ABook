"""Playback controls share the same public contract on all three surfaces."""
from pathlib import Path
import json
import pytest
from scripts.ui_copy_source import expand

ROOT = Path(__file__).resolve().parents[1]


def copy_source(path: Path) -> str:
    language = "kt" if path.suffix == ".kt" else "ts" if path.suffix in {".ts", ".tsx"} else "qml"
    return expand(path.read_text(encoding="utf-8"), language)


def test_tone_catalog_is_the_single_source_for_three_platforms():
    from scripts.gen_tone_presets import generate
    paths = [ROOT / "mobile/android/app/src/main/java/vn/abook/player/ToneCatalog.generated.kt",
             ROOT / "desktop_qt/src/tonecatalog.generated.h"]
    before = [p.read_bytes() for p in paths]
    generate()
    assert before == [p.read_bytes() for p in paths], "Native catalog must be regenerated before commit"
    catalog = json.loads((ROOT / "abook/webui/assets/tone_presets.json").read_text(encoding="utf-8"))
    strings = json.loads((ROOT / "ui_strings/vi.json").read_text(encoding="utf-8"))["strings"]
    assert [strings[p["label"]] for p in catalog["presets"]] == ["Tắt", "Giọng rõ", "Ấm", "Sáng", "Bớt xì", "Tai nghe nhỏ", "Loa ngoài"]
    assert "tone_presets.json" in (ROOT / "ui/src/listen/tonePresets.ts").read_text(encoding="utf-8")
    assert "Equalizer" not in strings.values()


@pytest.mark.parametrize("label", ["Giọng đọc", "Cao độ", "Về mặc định", "Âm sắc", "Riêng sách này", "Mono", "Cân bằng",
    "Bỏ khoảng lặng", "Ngưỡng lặng", "Dài tối thiểu", "Giữ khoảng nghỉ"])
def test_audio_panel_copy_matches(label):
    for path in [ROOT / "ui/src/listen/AudioFxPanel.tsx",
                 ROOT / "mobile/android/app/src/main/java/vn/abook/player/ui/nowplaying/AudioFxPage.kt",
                 ROOT / "desktop_qt/qml/AudioFxPanel.qml"]:
        assert label in copy_source(path), path


@pytest.mark.parametrize("label", ["Có sẵn", "Của tôi", "Lưu thành preset", "Lưu đè", "Lưu thành mới", "Nhân bản", "Đổi tên", "Xoá", "Hoàn tác", "Dùng riêng cho sách này"])
def test_preset_management_copy_matches(label):
    for path in [ROOT / "ui/src/listen/TonePage.tsx",
                 ROOT / "mobile/android/app/src/main/java/vn/abook/player/ui/nowplaying/TonePage.kt",
                 ROOT / "desktop_qt/qml/TonePage.qml"]:
        assert label in copy_source(path), path


def test_processing_is_narration_only():
    # Music players must never inherit voice pitch / EQ when switching chapters.
    assert "attachAudioFx" not in (ROOT / "ui/src/listen/musicBed.ts").read_text(encoding="utf-8")
    assert "AudioFxChain" not in (ROOT / "mobile/android/app/src/main/java/vn/abook/player/MusicBed.kt").read_text(encoding="utf-8")
    mixer = (ROOT / "desktop_qt/src/musicmixer.cpp").read_text(encoding="utf-8")
    assert "if (s->streaming) { s->fxDsp.configure" in mixer
