from scripts.check_unit_spacing import NBSP, breaks, findings, join, jsx_escape_lines, python_lines, source_lines


def test_jsx_attribute_strings_never_carry_javascript_escapes():
    """suffix="\\u00a0dBFS" in JSX renders the six characters, not a no-break space."""
    for line in ('<FxSlider suffix="\\u00a0dBFS" onChange={f}/>', "  title='Dòng 1\\nDòng 2'", '<X a={1} label="x\\x41"/>',
                 '<X label="tab\\there"/>'):
        assert jsx_escape_lines(line) == [1], line
    for line in ('<FxSlider suffix={"\\u00a0dBFS"} />', "<FxSlider suffix={DBFS}/>", "const raw='Chương 1\\n\\nCâu.';",
                 'let x="\\n";', 'function f(a="\\n") {}', 'items.join("\\n")', '<input pattern="\\d+"/>', 'x === "\\n"',
                 '// suffix="\\u00a0dB"'):
        assert jsx_escape_lines(line) == [], line


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


def test_python_scan_catches_server_copy_the_app_shows():
    assert python_lines('raise ValueError(f"Ảnh quá lớn (tối đa {limit // 2**20} MB)")') == [1]
    assert python_lines('self.log(f"Đã chờ RAM {waited / 60:.0f} phút.")') == [1]
    assert python_lines('LABEL = "~6 GB - bước lâu nhất"') == [1]
    assert python_lines('def size(n):\n    return f"{n:.1f} GB"') == [2]
    assert python_lines('text = "Còn %d giây" % left') == [1]
    assert python_lines('reason = (\n    "không có kết quả nào trong "\n    f"{seconds:.0f} giây"\n)') == [2]
    assert python_lines('notify("ABook", f"Chỉ còn {free:.1f} GB khả dụng.")') == [1]


def test_python_scan_skips_what_never_reaches_the_app():
    # Joined right, documentation, developer output, English developer text, and a number read out for the voice engine.
    assert python_lines('raise ValueError(f"Ảnh quá lớn (tối đa {limit}\u00a0MB)")') == []
    assert python_lines('def f():\n    """Đọc 8 KB đầu, cửa sổ 10 giây."""\n    return 1') == []
    assert python_lines('"""Chờ tới 30 giây."""\nX = 1') == []
    assert python_lines('import logging\nLOG = logging.getLogger(__name__)\nLOG.info(f"đã tải {n} MB")') == []
    assert python_lines('logging.getLogger(__name__).warning(f"chậm {ms} ms")') == []
    assert python_lines('print(f"chờ {n} giây")') == []
    assert python_lines('raise RuntimeError(f"disk free {gb:.1f} GB")') == []
    assert python_lines('said = f"{vietnamese_number(h)} giờ {vietnamese_number(m)}"') == []
    assert python_lines("said = integer_reading(str(hour)) + ' giờ'") == []
    assert python_lines("said += ' ' + integer_reading(str(minute)) + ' phút'") == []


def test_python_scan_does_not_mistake_a_formatter_for_a_reading():
    assert python_lines('text = f"{format_number(size)} MB"') == [1]
    assert python_lines("text = str(minutes) + ' phút'") == [1]
