// SINH TỰ ĐỘNG bởi scripts/gen_native_tokens.py từ docs/DESIGN.md (§5.1, §5.2, §5.5) và ui/src/shared/motion.ts. KHÔNG sửa tay:
// sửa DESIGN.md rồi chạy lại script (tests/test_native_tokens.py bắt lệch).
package vn.abook.player.ui.theme

/** Màu ARGB, bảng sáng. */
internal object LightPalette {
    const val BG = 0xFFF5F3EFL
    const val PANEL = 0xFFFFFFFFL
    const val BG_SUNKEN = 0xFFECE9E3L
    const val LINE = 0xFFE3DFD7L
    const val TEXT = 0xFF1A1814L
    const val TEXT_2 = 0xFF4F4A43L
    const val TEXT_3 = 0xFF67615AL
    const val FG_3 = 0xFF8A8478L
    const val ACCENT = 0xFFD4912BL
    const val ACCENT_INK = 0xFF1D1304L
    const val ACCENT_TEXT = 0xFF8A5309L
    const val ACCENT_SOFT = 0xFFF7EAD5L
    const val SUCCESS = 0xFF2A7554L
    const val DANGER = 0xFFB23B33L
}

/** Màu ARGB, bảng tối. */
internal object DarkPalette {
    const val BG = 0xFF121110L
    const val PANEL = 0xFF1B1A18L
    const val BG_SUNKEN = 0xFF0C0B0AL
    const val LINE = 0xFF2E2B27L
    const val TEXT = 0xFFECE8E1L
    const val TEXT_2 = 0xFFBAB3A8L
    const val TEXT_3 = 0xFFA0998EL
    const val FG_3 = 0xFF7A746AL
    const val ACCENT = 0xFFE9A945L
    const val ACCENT_INK = 0xFF1B1204L
    const val ACCENT_TEXT = 0xFFF0B961L
    const val ACCENT_SOFT = 0x24E9A945L
    const val SUCCESS = 0xFF5CC596L
    const val DANGER = 0xFFEF7B70L
}

/** Khoảng cách, bo góc, vùng chạm (dp). */
internal object Dimens {
    const val SPACE_4 = 4
    const val SPACE_8 = 8
    const val SPACE_12 = 12
    const val SPACE_16 = 16
    const val SPACE_24 = 24
    const val SPACE_32 = 32
    const val SPACE_48 = 48
    const val SPACE_64 = 64
    const val MARGIN_PHONE = 20
    const val SECTION_GAP_PHONE = 32
    const val RADIUS_CONTROL = 8
    const val RADIUS_COVER = 12
    const val RADIUS_SHEET = 20
    const val TOUCH_PHONE = 44
}

/** Cỡ chữ (sp) và dòng của chữ đọc theo. */
internal object TypeScale {
    const val CAPTION = 12
    const val BODY_SMALL = 14
    const val BODY = 16
    const val SECTION_TITLE = 18
    const val SCREEN_TITLE_PHONE = 24
    const val SCREEN_TITLE_DESKTOP = 32
    const val READING = 20
    const val READING_LEADING = 1.7f
}

/** Thời lượng chuyển động (ms): vào / ra. */
internal object MotionMs {
    const val FAST = 120
    const val FAST_OUT = 90
    const val MEDIUM = 220
    const val MEDIUM_OUT = 150
    const val SLOW = 300
    const val SLOW_OUT = 200
}

/** Đường cong cubic-bezier (x1, y1, x2, y2), Material 3. */
internal object Bezier {
    const val STANDARD_X1 = 0.2f
    const val STANDARD_Y1 = 0f
    const val STANDARD_X2 = 0f
    const val STANDARD_Y2 = 1f
    const val DECELERATE_X1 = 0.05f
    const val DECELERATE_Y1 = 0.7f
    const val DECELERATE_X2 = 0.1f
    const val DECELERATE_Y2 = 1f
    const val ACCELERATE_X1 = 0.3f
    const val ACCELERATE_Y1 = 0f
    const val ACCELERATE_X2 = 0.8f
    const val ACCELERATE_Y2 = 0.15f
}
