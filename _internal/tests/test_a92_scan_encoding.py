"""Soát a92 T1: xem nguồn Studio đọc TXT UTF-16 / CP1258 hợp lệ cho đúng nhãn dòng đầu, số chữ, số ký tự, dòng ghi công - cùng bộ nhận
bảng mã `io_utils.decode_text` với dây chuyền; đọc phần đầu của file dài thì dừng đúng ranh ký tự."""
from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from abook.io_utils import decode_text
from abook.webui import actions

TEXT = "Chương 1: Người bạn mới\n\nTranslator: NicK\n\nTôi đi qua con đường nhỏ. Bạn đang chờ tôi bên dòng sông.\n\nỦng hộ nhóm dịch qua Momo 0912345678\n"
CP1258_TEXT = "Chương 1: Em đi chơi\n\nTranslator: NicK\n\nEm đi chơi. Trời đẹp quá.\n"


def _cp1258(text: str) -> bytes:
    """CP1258 chỉ có chữ cái gốc + dấu thanh rời: ờ = ơ (có sẵn) + dấu huyền."""
    out = bytearray()
    for char in text:
        try:
            out += char.encode("cp1258")
            continue
        except UnicodeEncodeError:
            pass
        decomposed = unicodedata.normalize("NFD", char)
        tone = decomposed[-1] if decomposed[-1] in "̣̀́̃̉" else ""
        out += unicodedata.normalize("NFC", decomposed[: len(decomposed) - len(tone)]).encode("cp1258") + tone.encode("cp1258")
    return bytes(out)


def _row(tmp_path: Path, raw: bytes) -> dict:
    folder = tmp_path / "t"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "001.txt").write_bytes(raw)
    return actions.scan_inputs([str(folder)])["files"][0]


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"])
def test_every_unicode_encoding_scans_like_plain_utf8(tmp_path: Path, encoding: str) -> None:
    raw = TEXT.encode(encoding)
    if encoding in ("utf-16-le", "utf-16-be"):
        raw = TEXT.encode(encoding)  # không BOM: nhận ra qua byte 0
    reference = _row(tmp_path / "ref", TEXT.encode("utf-8"))
    row = _row(tmp_path, raw)
    assert row["firstLine"] == "Chương 1: Người bạn mới"
    for key in ("words", "chars", "audioSeconds"):
        assert row[key] == reference[key], key
    assert row["credits"] == ["Translator: NicK"] and row["tailCredits"] == reference["tailCredits"]
    assert "\x00" not in row["firstLine"] and "\ufffd" not in row["firstLine"]


def test_a_cp1258_vietnamese_file_keeps_its_accents(tmp_path: Path) -> None:
    raw = _cp1258(CP1258_TEXT)
    assert decode_text(raw)[1] == "cp1258"
    row = _row(tmp_path, raw)
    assert row["firstLine"] == "Chương 1: Em đi chơi"
    assert row["credits"] == ["Translator: NicK"]
    assert row["words"] == len(decode_text(raw)[0].split())


def test_the_label_and_the_counts_come_from_the_same_decoder_as_the_pipeline(tmp_path: Path) -> None:
    raw = TEXT.encode("utf-16")
    text, _ = decode_text(raw)
    row = _row(tmp_path, raw)
    assert row["firstLine"] == text.splitlines()[0]
    assert row["chars"] == sum(not ch.isspace() for ch in text) and row["words"] == len(text.split())


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-16-be"])
def test_cutting_the_head_in_the_middle_of_a_character_never_garbles_the_text(encoding: str) -> None:
    full = "Chương 1: Người bạn mới. Tôi đi qua con đường nhỏ, bạn đang chờ tôi bên dòng sông 😀 xin chào đời\n" * 4
    raw = full.encode(encoding)
    for cut in range(120, 300):
        text, found = actions._decode_head(raw[:cut], truncated=True)
        assert full.startswith(text) or full.startswith(text.rstrip()), (encoding, cut, text[-12:])
        assert "\ufffd" not in text
        assert found.startswith(encoding.split("-")[0]), (encoding, cut, found)


def test_a_long_file_is_labelled_from_its_head_without_reading_it_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(actions, "SCAN_WORD_LIMIT_BYTES", 101)  # ranh giới rơi giữa một chữ có dấu
    raw = ("Chương 1: Người bạn mới\n\n" + "Tôi đi qua con đường nhỏ, bạn đang chờ tôi. " * 40).encode("utf-8")
    row = _row(tmp_path, raw)
    assert row["firstLine"] == "Chương 1: Người bạn mới"
    assert row["bytes"] == len(raw) and row["words"] > 5


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-16-be"])
def test_the_credits_at_the_end_of_a_long_file_are_found_in_any_encoding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, encoding: str) -> None:
    monkeypatch.setattr(actions, "SCAN_WORD_LIMIT_BYTES", 4096 + 1)  # lẻ: ranh giới đầu rơi giữa ký tự UTF-16 / UTF-8
    body = "Tôi đi qua con đường nhỏ, bạn đang chờ tôi bên dòng sông.\n\n" * 400
    text = "Chương 1: Người bạn mới\n\nTranslator: NicK\n\n" + body + "Ủng hộ nhóm dịch qua Momo 0912345678\n"
    row = _row(tmp_path, text.encode(encoding))
    assert row["firstLine"] == "Chương 1: Người bạn mới"
    assert row["credits"] == ["Translator: NicK"]
    assert row["tailCredits"] == ["Ủng hộ nhóm dịch qua Momo 0912345678"]
