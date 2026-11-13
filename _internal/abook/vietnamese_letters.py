"""Chữ cái tiếng Việt viết HOA và viết THƯỜNG, dùng làm lớp ký tự regex - một chỗ cho cả app.

Đừng viết dải điểm mã `À-Ỹ` hay `à-ỹ`: U+00C0..U+1EF9 trộn cả hai cỡ chữ (à, đ, ă, ơ, ạ nằm trong `À-Ỹ`; Ạ, Ă, Đ nằm trong
`à-ỹ`), nên "đứng" thành "viết hoa" và "Ạ" thành "viết thường". Còn `[A-ZĐ]` thì thiếu mọi chữ hoa có dấu ("Ánh", "Ông").

Bản Kotlin y hệt: mobile/android/.../VietnameseLetters.kt; danh sách dùng chung ở tests/fixtures/vietnamese_letters/letters.json
(đổi một bên là phải đổi cả hai).
"""
from __future__ import annotations

VIETNAMESE_UPPERCASE_LETTERS = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬĐÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"
)
VIETNAMESE_LOWERCASE_LETTERS = (
    "abcdefghijklmnopqrstuvwxyz"
    "àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ"
)
VIETNAMESE_UPPERCASE_CLASS = f"[{VIETNAMESE_UPPERCASE_LETTERS}]"
VIETNAMESE_LOWERCASE_CLASS = f"[{VIETNAMESE_LOWERCASE_LETTERS}]"
