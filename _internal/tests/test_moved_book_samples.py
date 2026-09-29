"""Câu mẫu của một cuốn đã chuyển chỗ vẫn nghe được (webui/store.segment_audio): đường dẫn WAV trong DB là tuyệt đối lúc thu -
thư mục dự án đổi tên (28-09: "Ebook Reader" -> "ABook"), hay chép sang máy khác, thì tìm lại theo phần đuôi của đường dẫn
ngay trong thư mục sách. Không bao giờ phục vụ file ngoài thư mục sách."""
from __future__ import annotations

from pathlib import Path

from ebook_reader.webui.store import segment_audio


def test_a_moved_book_finds_its_takes_by_the_tail_of_the_old_path(tmp_path: Path) -> None:
    book = tmp_path / "ABook" / "lo18_78b5dddf74"
    take = book / "work" / "chunks" / "chapter_00001" / "0000000.wav"
    take.parent.mkdir(parents=True)
    take.write_bytes(b"RIFF")
    recorded = r"D:\Novels\Ebook Reader\Audiobooks\lo18_78b5dddf74\work\chunks\chapter_00001\0000000.wav"

    assert segment_audio(book, recorded) == take.resolve()


def test_a_take_in_place_is_found_as_before(tmp_path: Path) -> None:
    take = tmp_path / "work" / "chunks" / "0001.wav"
    take.parent.mkdir(parents=True)
    take.write_bytes(b"RIFF")
    assert segment_audio(tmp_path, str(take)) == take.resolve()
    assert segment_audio(tmp_path, "work/chunks/0001.wav") == take.resolve()


def test_nothing_outside_the_book_is_ever_served(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    secret = tmp_path / "secret.wav"
    secret.write_bytes(b"RIFF")
    assert segment_audio(book, str(secret)) is None
    assert segment_audio(book, "../secret.wav") is None
    assert segment_audio(book, "D:/elsewhere/missing.wav") is None
    assert segment_audio(book, None) is None
