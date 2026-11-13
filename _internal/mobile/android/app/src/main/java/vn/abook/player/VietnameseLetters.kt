package vn.abook.player

/**
 * Chữ cái tiếng Việt viết HOA và viết THƯỜNG, dùng làm lớp ký tự regex - bản Kotlin y hệt `abook/vietnamese_letters.py`.
 * Đừng viết dải `À-Ỹ` / `à-ỹ` (U+00C0..U+1EF9 trộn hai cỡ chữ) hay `[A-ZĐ]` (thiếu mọi chữ hoa có dấu). Danh sách dùng chung:
 * tests/fixtures/vietnamese_letters/letters.json (đổi một bên là phải đổi cả hai).
 */
object VietnameseLetters {
    const val UPPER = """ABCDEFGHIJKLMNOPQRSTUVWXYZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬĐÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"""
    const val LOWER = """abcdefghijklmnopqrstuvwxyzàáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ"""
    const val UPPER_CLASS = "[" + UPPER + "]"
    const val LOWER_CLASS = "[" + LOWER + "]"
}
