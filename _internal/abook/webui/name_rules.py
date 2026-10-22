"""Phép kiểm chữ người nghe gõ cho TÊN và CÁCH ĐỌC ở phía máy chủ (soát a89 T1): giao diện chỉ chặn nhẹ, còn gửi thẳng qua API hay gõ lẫn ký tự
vô hình thì cần một cửa duy nhất - "Đổi tên", "Người mới…" và "Đọc từ này là…" cùng đi qua đây.

Chữ gõ được làm sạch TRƯỚC khi lưu: NFC (chữ tiếng Việt dựng sẵn - sách cũng NFC, nên khớp từ không lệch), bỏ ký tự định dạng vô hình (nhóm Cf: khoảng
trắng rộng 0, BOM, dấu nối mềm, đánh dấu chiều chữ), bỏ ký tự điều khiển, gộp khoảng trắng. Quá dài thì BÁO (không cắt lặng lẽ: 500 ký tự cắt còn
80 là một cái tên khác người gõ), chỉ có ký tự vô hình thì từ chối, và tên người không được trùng người khác hay tên dành riêng của máy.

Không chặn tên gần trùng ("Hà" / "Hạ", "Lucien" / "Lucién"): tiếng Việt phân biệt người bằng dấu, bỏ dấu để so sẽ chặn nhầm người thật."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .. import names

NAME_MAX = names.MAX_NAME
SURFACE_MAX = 80
SPOKEN_MAX = 120

# Nhãn dành riêng của máy (reviews.speaker_label / listener_overrides): người nghe thấy chúng như tên người thật thì hộp việc và tab Kịch bản lẫn.
RESERVED = frozenset({"người kể", "người kể đọc tất cả", "vai phụ không tên", "narrator", "unknown", "unnamed", "anonymous"})


class NameProblem(ValueError):
    """Lời báo cho người gõ (đã là tiếng Việt, hiện nguyên văn)."""


def clean(text: Any) -> str:
    """NFC, bỏ ký tự vô hình (Cf) và điều khiển, mọi khoảng trắng thành một dấu cách (names.tidy)."""
    return names.tidy(text)


def _typed(raw: Any, what: str) -> str:
    """`raw` đã làm sạch; chỉ gồm ký tự vô hình (rỗng sau khi sạch dù có gõ) thì từ chối thay vì coi như để trống."""
    cleaned = clean(raw)
    if not cleaned and isinstance(raw, str) and raw.strip():
        raise NameProblem(f"{what} chỉ có ký tự không nhìn thấy - bạn gõ lại bằng chữ thường.")
    return cleaned


def _too_long(cleaned: str, limit: int, what: str) -> None:
    if len(cleaned) > limit:
        raise NameProblem(f"{what} dài tối đa {limit} ký tự (bạn đang gõ {len(cleaned)}) - bạn rút ngắn lại.")


def is_reserved(name: str) -> bool:
    folded = name.casefold()
    return folded in RESERVED or folded.startswith(("anonymous_", "npc_local")) or "::" in name


def person(raw: Any, others: Iterable[str] = (), *, allow_empty: bool = False) -> str:
    """Tên một người (đổi tên, người mới). `others`: tên những người KHÁC trong sách. Rỗng chỉ khi `allow_empty` (đổi tên: trở về tên gốc)."""
    name = _typed(raw, "Tên")
    if not name:
        if allow_empty:
            return ""
        raise NameProblem("Bạn chưa gõ tên.")
    _too_long(name, NAME_MAX, "Tên")
    if is_reserved(name):
        raise NameProblem(f"“{name}” là tên máy dùng cho người kể hay vai phụ không tên - bạn đặt tên khác.")
    folded = name.casefold()
    for other in others:
        if clean(other).casefold() == folded:
            raise NameProblem(f"Trong sách đã có người tên “{clean(other)}” - bạn đặt tên khác để khỏi nhầm hai người.")
    return name


def surface(raw: Any) -> str:
    """Chữ trong sách cần đổi cách đọc ("Đọc từ này là…")."""
    word = _typed(raw, "Từ cần đổi cách đọc")
    if not word:
        raise NameProblem("Bạn chưa gõ từ cần đổi cách đọc.")
    _too_long(word, SURFACE_MAX, "Từ cần đổi cách đọc")
    return word


def spoken(raw: Any) -> str:
    """Cách đọc người gõ."""
    form = _typed(raw, "Cách đọc")
    if not form:
        raise NameProblem("Bạn chưa gõ cách đọc.")
    _too_long(form, SPOKEN_MAX, "Cách đọc")
    return form
