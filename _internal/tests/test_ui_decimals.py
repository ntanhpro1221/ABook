from scripts.check_ui_decimals import findings, violations


def test_all_ui_sources_use_the_shared_decimal_formatter():
    assert list(findings()) == []


def test_detector_rejects_regressions_and_accepts_storage_and_shared_formatter():
    for source in ('value.toFixed(1)', '"%.1f".format(pitch)', 'value.toString()', 'v.toPlainString()', 'value.replace(".", ",")'):
        assert violations(source), source
    for source in ('UiNumber.decimal(pitch)', 'formatDecimal(value)', 'json.toString()', 'chapters.toString()', 'uri.toString()'):
        assert not violations(source), source
