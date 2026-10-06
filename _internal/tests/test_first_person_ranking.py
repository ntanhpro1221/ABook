"""Gợi ý "'Tôi' là ai?" xếp người kể lên ĐẦU (2026-10-06): đếm tên theo VỊ TRÍ, không chỉ theo số lần.

Kho 20 chương đầu, 25 truyện ngôi thứ nhất dò tham số: đúng top-1 từ 72% lên 96%. Các ca dưới đây là bản rút gọn của từng lý do
(văn bản tổng hợp, không chép truyện): tên đứng đầu câu thoại không được đếm (Zenith), tên gọi tắt tách điểm của người khác (YMP
"Juli"/"Juliana"), người đối diện hay GỌI nhưng cũng hay được KỂ cạnh chữ "tôi" (TwoCF "Kirako" trước "Yoshihito").
"""
from __future__ import annotations

from pathlib import Path

from abook.first_person import _bare, _names, first_person_hint


def _book(folder: Path, chapter: str, count: int = 4) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(1, count + 1):
        path = folder / f"{index:03d}.txt"
        path.write_bytes(chapter.encode("utf-8"))
        paths.append(path)
    return paths


def _suggest(tmp_path: Path, chapter: str, name: str = "book") -> list[str]:
    return first_person_hint(_book(tmp_path / name, chapter))["suggestions"]


def test_a_name_at_the_start_of_a_quote_counts_as_being_called(tmp_path: Path) -> None:
    """Zenith: "“Yangcheon, ...”" không có chữ thường hay dấu phẩy phía trước nên bị bỏ sót; tên đứng giữa câu chỉ có 1 lần/chương."""
    chapter = "\n\n".join([
        "Tôi bước vào sân tập. Tôi thấy Seolah đang đứng chờ, Seolah vẫy tay.",
        "“Yangcheon, cậu đến muộn rồi.”",
        "“Seolah, xin lỗi nhé.”",
        "“Yangcheon! Đi thôi nào.”",
        "“Được rồi, Seolah.” “Nhanh lên, Seolah.”",
        "“Yangcheon, nghe này.” “Chờ đã, Yangcheon.”",
    ]) + "\n"

    assert _suggest(tmp_path, chapter)[0] == "Yangcheon"


def test_the_name_in_narration_next_to_i_is_the_counterpart_not_the_narrator(tmp_path: Path) -> None:
    """TwoCF: cô gái được gọi nhiều ngang người kể nhưng lời kể cứ "Kirako nhìn tôi" - người kể không nằm cạnh chính mình."""
    chapter = "\n\n".join([
        "Tôi quay sang thì Kirako đã nhìn tôi. Tôi đáp lại Kirako bằng một cái gật đầu, Kirako cười với tôi.",
        "“Yoshihito, đi thôi.” “Kirako, đợi tôi với.”",
        "“Được rồi, Kirako.” “Nhanh lên, Kirako!”",
        "“Kirako, nhìn kìa.” “Ừ, Yoshihito.”",
        "“Kirako!” “Này, Kirako.” “Kirako, đợi đã.”",
        "“Chờ chút, Yoshihito.” “Cẩn thận, Yoshihito.”",
    ]) + "\n"

    assert _suggest(tmp_path, chapter)[0] == "Yoshihito"


def test_a_nickname_is_merged_into_the_full_name(tmp_path: Path) -> None:
    """YMP: "Juli" (gọi tắt của Juliana) được gọi 9 lần, tên người kể 6 lần - gộp lại thì Juliana mang cả số lần được KỂ."""
    chapter = "\n\n".join([
        "Tôi nhìn Juliana. Juliana nhìn lại tôi, Juliana khẽ nghiêng đầu.",
        "“Này, Juli.”",
        "“Đợi đã, Samael.”",
        "Juliana cười với tôi. Tôi lườm Juliana.",
        "“Juli, đi thôi.”",
        "“Vâng, Juli.”",
        "“Ừ, Samael.”",
    ]) + "\n"
    suggestions = _suggest(tmp_path, chapter)

    assert suggestions[0] == "Samael"
    assert "Juli" not in suggestions


def test_a_short_name_is_merged_into_the_full_name_and_labelled_by_the_commoner_form(tmp_path: Path) -> None:
    """Zenith: "Yangcheon" và "Gu Yangcheon" là một người; điểm cộng dồn và nhãn là dạng hay gặp hơn."""
    chapter = "\n\n".join([
        "Tôi nhìn Aria. Aria nhìn tôi, Aria cười với tôi.",
        "“Được rồi, Yangcheon.”",
        "“Đi nào, Gu Yangcheon.”",
        "“Chờ chút, Yangcheon.”",
    ]) + "\n"
    suggestions = _suggest(tmp_path, chapter)

    assert suggestions[0] == "Yangcheon"
    assert "Gu Yangcheon" not in suggestions


def test_a_self_introduction_ties_the_name_to_i(tmp_path: Path) -> None:
    chapter = "\n\n".join([
        "Tôi cúi chào Minami và Hoshino.",
        "“Tên tôi là Takeru.”",
        "“Rất vui được gặp, Takeru.”",
        "Minami nhìn tôi. Hoshino cũng nhìn tôi, Hoshino mỉm cười với Minami.",
        "“Chào, Minami.” “Chào, Hoshino.”",
    ]) + "\n"

    assert _suggest(tmp_path, chapter)[0] == "Takeru"


def test_stacked_honorifics_are_stripped_to_the_bare_name() -> None:
    assert _bare("Kin-chan-sama") == "Kin"
    assert _bare("Hayan-ssi") == "Hayan"
    assert _bare("Seol-Ah") == "Seol-Ah"
    assert _names("Cậu nhìn Kin-chan-sama và Hyung-nim rồi bỏ đi.") == ["Kin", "Hyung"]


def test_a_capitalised_common_word_is_ranked_below_a_real_name(tmp_path: Path) -> None:
    """"Quỷ" viết hoa giữa câu nhưng cũng đầy ở dạng chữ thường: bị trừ điểm, không bị cấm (có thể là biệt danh thật)."""
    chapter = "\n\n".join([
        "Tôi thấy một con quỷ lớn, quỷ ấy gầm lên rồi lao tới. Tôi chạy qua Quỷ và Yuki.",
        "“Chạy đi, Quỷ.” “Nhanh lên, Yuki.”",
        "Có thêm một con quỷ nữa. Quỷ lùi lại, quỷ khác tiến lên.",
        "“Cẩn thận, Quỷ.” “Cẩn thận, Yuki.”",
    ]) + "\n"
    suggestions = _suggest(tmp_path, chapter)

    assert "Quỷ" in suggestions and suggestions.index("Yuki") < suggestions.index("Quỷ")


def test_a_book_without_names_has_no_suggestions(tmp_path: Path) -> None:
    assert _suggest(tmp_path, "Tôi đứng lặng nhìn ra cửa sổ.\n\n“Đi thôi.”\n") == []
