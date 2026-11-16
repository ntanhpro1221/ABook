from scripts.check_unit_spacing import NBSP, breaks, findings, join, source_lines


def test_catalog_and_sources_keep_numbers_with_their_units():
    assert list(findings()) == []


def test_detector_catches_plain_spaces_between_a_number_and_its_unit():
    for text in ("97 %", "Đang tải {0} %", "%1 phút", "{0} giờ {1} phút", " giây trước khi dừng", "12,5 MB", "-18 dB", "3 s", "120 nhịp/phút"):
        assert breaks(text), text
    for text in ("97" + NBSP + "%", "khung giờ này", "Đã nghe 42% cả cuốn", "~7–10" + NBSP + "phút/chương", "ms-kanji", "5 chương", "mỗi giờ sách"):
        assert not breaks(text), text


def test_join_keeps_the_unit_and_only_changes_the_space():
    assert join("{0} giờ {1} phút") == "{0}" + NBSP + "giờ {1}" + NBSP + "phút"
    assert join(" giây trước") == NBSP + "giây trước"
    assert join(" %") == NBSP + "%"


def test_source_scan_reads_literals_and_jsx_text_but_not_comments_or_logs():
    assert source_lines('return "${grouped(mb)} MB"', False) == [1]
    assert source_lines("x = value + ' %'", False) == [1]
    assert source_lines('<span>{value} %</span>', True) == [1]
    assert source_lines('// 30 giây liền = 2 phút', False) == []
    assert source_lines('AppLog.w("Save", "sau $timeoutMs ms")', False) == []
    assert source_lines('return S.s_percent(value)', False) == []
