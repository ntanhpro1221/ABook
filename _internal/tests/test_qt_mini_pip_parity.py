"""Cửa sổ mini (Qt) và cửa sổ nhỏ PiP (Android) là MỘT tính năng: cùng năm thứ, cùng thứ tự đọc, cùng chữ trên ba nút (chủ sách 26-10).

Năm thứ: bìa, tên sách, tên chương, dải tiến độ trong chương, ba nút "Lùi N giây" / "Phát"-"Tạm dừng" / "Tới N giây". Đọc nguồn, không chạy app:

  - Qt: desktop_qt/qml/MiniPlayer.qml (objectName miniCover, miniBookTitle, miniChapterTitle, miniSeek, miniBack, miniPlay, miniForward);
  - Android: ui/pip/PipContent.kt (testTag pip_content, pip_book_title, pip_chapter_title, pip_progress) và ui/pip/PipParams.kt (ba RemoteAction).

Khác biệt được phép, vì là giới hạn nền tảng: PiP không nhận chạm nên dải tiến độ chỉ để xem; ghim và mở rộng của Qt là nút app tự vẽ, PiP dùng nút
hệ thống (không có "nút giả" trong PiP). Luật ở đây chỉ đòi đủ năm thứ và chữ trùng; build.bat chạy nó qua desktop_qt/tools/qt_pytests.py (tên test_qt_*).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QML = ROOT / "desktop_qt" / "qml"
KT = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player"

PIP_ORDER = ("pip_content", "pip_book_title", "pip_chapter_title", "pip_progress")
QT_ORDER = ("miniCover", "miniBookTitle", "miniChapterTitle", "miniSeek")
BUTTONS = ("miniBack", "miniPlay", "miniForward")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def line_of(text: str, needle: str) -> str:
    """Dòng đầu tiên chứa `needle` (rỗng nếu không có)."""
    return next((line for line in text.split("\n") if needle in line), "")


def block_around(text: str, index: int) -> str:
    """Khối `{ ... }` nhỏ nhất bao quanh vị trí `index` (QML: một đối tượng)."""
    depth, start = 0, index
    while start > 0:
        start -= 1
        if text[start] == "}":
            depth += 1
        elif text[start] == "{":
            if depth == 0:
                break
            depth -= 1
    depth, end = 0, start
    for end in range(start, len(text)):
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
            if depth == 0:
                break
    return text[start:end + 1]


def qt_label(qml: str, name: str) -> tuple[str, ...]:
    """Chữ của nút Qt: (khi đang phát, khi tạm dừng) với nút giữa; còn lại một chữ. `${Player.skipSeconds}` -> `{N}`."""
    line = line_of(qml, f'objectName: "{name}"')
    match = re.search(r"tip: (`[^`]*`|[^;}]*)", line)
    if not match:
        return ()
    tip = match.group(1).strip().replace("${Player.skipSeconds}", "{N}")
    if tip.startswith("`"):
        return (tip.strip("`"),)
    return tuple(re.findall(r'"([^"]+)"', tip))  # `Player.playing ? "Tạm dừng" : "Phát"`


def pip_labels(params: str) -> dict[str, tuple[str, ...]]:
    """Chữ ba nút PiP theo PipKind: `PipButton(PipKind.Back, "Lùi ${Playback.SKIP_SECONDS} giây", ...)`."""
    found = {}
    for kind, key in (("Back", "miniBack"), ("Toggle", "miniPlay"), ("Forward", "miniForward")):
        match = re.search(rf"PipButton\(PipKind\.{kind}, ([^\n]*?), PlayerWidget\.", params)
        if not match:
            continue
        label = match.group(1).replace("${Playback.SKIP_SECONDS}", "{N}")
        found[key] = tuple(re.findall(r'"([^"]+)"', label)) if label.startswith("if") else (label.strip('"'),)
    return found


def offences(qml: str, content: str, params: str, theme_qml: str = "", tokens_kt: str = "") -> list[str]:
    """Mọi chỗ cửa sổ mini Qt và nội dung PiP lệch nhau (rỗng = cùng một tính năng)."""
    bad = []
    for name in QT_ORDER + BUTTONS:
        if f'objectName: "{name}"' not in qml:
            bad.append(f"Qt thiếu {name}")
    for tag in PIP_ORDER:
        if f'testTag("{tag}")' not in content:
            bad.append(f"PiP thiếu {tag}")
    # Cùng thứ tự đọc: bìa, tên sách, tên chương, dải tiến độ.
    for label, text, tokens, mark in (
        ("Qt", qml, QT_ORDER, 'objectName: "{}"'),
        ("PiP", content, PIP_ORDER[1:], 'testTag("{}")'),
    ):
        spots = [text.find(mark.format(token)) for token in tokens]
        if -1 not in spots and spots != sorted(spots):
            bad.append(f"{label} đọc sai thứ tự: {tokens}")
    # Tên sách và tên chương cùng nguồn: trường bookTitle / chapterTitle của trạng thái phát.
    for field, qt_name, tag in (("bookTitle", "miniBookTitle", "pip_book_title"), ("chapterTitle", "miniChapterTitle", "pip_chapter_title")):
        if f"property string {field}: Player.{field}" not in qml:
            bad.append(f"Qt: {field} không lấy từ Player.{field}")
        if f"root.{field}" not in line_of(qml[qml.find(f'objectName: "{qt_name}"'):], "text:"):
            bad.append(f"Qt: {qt_name} không vẽ {field}")
        if f"player.{field}" not in line_of(content, f'testTag("{tag}")'):
            bad.append(f"PiP: {tag} không vẽ player.{field}")
    # Ba nút: chữ trùng từng chữ (title và contentDescription của RemoteAction là cùng nhãn).
    pip = pip_labels(params)
    for name in BUTTONS:
        qt = qt_label(qml, name)
        if not qt:
            bad.append(f"Qt: {name} không có chữ")
        elif pip.get(name) != qt:
            bad.append(f"chữ nút {name} lệch: Qt {qt} - PiP {pip.get(name)}")
    if not re.search(r"RemoteAction\(\s*Icon\.createWithBitmap\([^\n]*\),\s*button\.label,\s*button\.label,", params):
        bad.append("PiP: RemoteAction không dùng cùng một nhãn cho title và contentDescription")
    # Bo góc bìa Qt là token radiusCover, và token ấy bằng token của điện thoại.
    cover = block_around(qml, qml.find('objectName: "miniCover"'))
    if "radius: Theme.radiusCover" not in cover:
        bad.append("Qt: miniCover không bo góc bằng Theme.radiusCover")
    if theme_qml and tokens_kt:
        qt_radius = re.search(r"radiusCover:\s*(\d+)", theme_qml)
        kt_radius = re.search(r"RADIUS_COVER\s*=\s*(\d+)", tokens_kt)
        if not qt_radius or not kt_radius or qt_radius.group(1) != kt_radius.group(1):
            bad.append("radiusCover Qt và điện thoại lệch nhau")
    return bad


def real_offences() -> list[str]:
    return offences(
        read(QML / "MiniPlayer.qml"), read(KT / "ui" / "pip" / "PipContent.kt"), read(KT / "ui" / "pip" / "PipParams.kt"),
        read(QML / "Theme.qml"), read(KT / "ui" / "theme" / "Tokens.kt"),
    )


def test_mini_window_and_pip_have_the_same_five_things():
    assert real_offences() == [], "cửa sổ mini (Qt) và PiP (Android) lệch nhau:\n" + "\n".join(real_offences())


def test_player_state_carries_the_two_titles_both_sides_read():
    state = read(KT / "ui" / "data" / "PlayerRepo.kt")
    assert "val bookTitle: String" in state and "val chapterTitle: String" in state


def test_labels_are_read_correctly_from_the_real_sources():
    """Chữ đọc ra phải là chữ thật (nếu đọc ra rỗng thì phép so ở trên vô nghĩa)."""
    qml = read(QML / "MiniPlayer.qml")
    pip = pip_labels(read(KT / "ui" / "pip" / "PipParams.kt"))
    assert qt_label(qml, "miniBack") == ("Lùi {N} giây",)
    assert qt_label(qml, "miniForward") == ("Tới {N} giây",)
    assert qt_label(qml, "miniPlay") == ("Tạm dừng", "Phát")
    assert pip["miniBack"] == ("Lùi {N} giây",) and pip["miniForward"] == ("Tới {N} giây",)
    assert pip["miniPlay"] == ("Tạm dừng", "Phát")


# --- Kiểm lực: làm hỏng từng thứ trên bản sao trong bộ nhớ, máy dò phải đỏ. ---

def _real():
    return read(QML / "MiniPlayer.qml"), read(KT / "ui" / "pip" / "PipContent.kt"), read(KT / "ui" / "pip" / "PipParams.kt")


def test_detector_goes_red_when_pip_loses_the_chapter_title():
    qml, content, params = _real()
    broken = content.replace('testTag("pip_chapter_title")', 'testTag("pip_x")')
    assert any("pip_chapter_title" in hit for hit in offences(qml, broken, params))


def test_detector_goes_red_when_pip_loses_the_book_title():
    qml, content, params = _real()
    broken = content.replace('testTag("pip_book_title")', 'testTag("pip_x")')
    assert any("pip_book_title" in hit for hit in offences(qml, broken, params))


def test_detector_goes_red_when_pip_draws_the_chapter_before_the_book():
    qml, content, params = _real()
    a, b = 'testTag("pip_book_title")', 'testTag("pip_chapter_title")'
    swapped = content.replace(a, "@@").replace(b, a).replace("@@", b)
    assert any("thứ tự" in hit for hit in offences(qml, swapped, params))


def test_detector_goes_red_when_one_button_label_differs():
    qml, content, params = _real()
    assert any("miniBack" in hit for hit in offences(qml, content, params.replace('"Lùi ${Playback', '"Về ${Playback')))
    assert any("miniPlay" in hit for hit in offences(qml, content, params.replace('"Tạm dừng"', '"Dừng"')))
    assert any("miniForward" in hit for hit in offences(qml, content, params.replace('"Tới ${Playback', '"Đến ${Playback')))
    assert any("miniBack" in hit for hit in offences(qml.replace("`Lùi ${", "`Lui ${"), content, params))


def test_detector_goes_red_when_the_qt_window_loses_a_thing_or_its_source():
    qml, content, params = _real()
    assert any("miniChapterTitle" in hit for hit in offences(qml.replace('"miniChapterTitle"', '"x"'), content, params))
    assert any("miniSeek" in hit for hit in offences(qml.replace('"miniSeek"', '"x"'), content, params))
    assert any("chapterTitle" in hit for hit in offences(qml.replace("Player.chapterTitle", "Player.chapterSubtitle"), content, params))


def test_detector_goes_red_when_the_cover_radius_leaves_the_token():
    qml, content, params = _real()
    assert any("radiusCover" in hit for hit in offences(qml.replace("radius: Theme.radiusCover", "radius: 8"), content, params))
