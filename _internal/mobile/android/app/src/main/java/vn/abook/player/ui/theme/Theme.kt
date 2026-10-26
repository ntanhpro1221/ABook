package vn.abook.player.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import vn.abook.player.R

/** Bảng màu "phòng nghe ấm" (DESIGN.md §5.1). Giá trị ở [LightPalette] / [DarkPalette] (sinh từ DESIGN.md). */
@Immutable
class AbookColors(
    val bg: Color, val panel: Color, val bgSunken: Color, val line: Color,
    val text: Color, val text2: Color, val text3: Color, val fg3: Color,
    val accent: Color, val accentInk: Color, val accentText: Color, val accentSoft: Color,
    val success: Color, val danger: Color,
    val dark: Boolean,
)

internal val LightColors = AbookColors(
    Color(LightPalette.BG), Color(LightPalette.PANEL), Color(LightPalette.BG_SUNKEN), Color(LightPalette.LINE),
    Color(LightPalette.TEXT), Color(LightPalette.TEXT_2), Color(LightPalette.TEXT_3), Color(LightPalette.FG_3),
    Color(LightPalette.ACCENT), Color(LightPalette.ACCENT_INK), Color(LightPalette.ACCENT_TEXT), Color(LightPalette.ACCENT_SOFT),
    Color(LightPalette.SUCCESS), Color(LightPalette.DANGER), dark = false,
)

internal val DarkColors = AbookColors(
    Color(DarkPalette.BG), Color(DarkPalette.PANEL), Color(DarkPalette.BG_SUNKEN), Color(DarkPalette.LINE),
    Color(DarkPalette.TEXT), Color(DarkPalette.TEXT_2), Color(DarkPalette.TEXT_3), Color(DarkPalette.FG_3),
    Color(DarkPalette.ACCENT), Color(DarkPalette.ACCENT_INK), Color(DarkPalette.ACCENT_TEXT), Color(DarkPalette.ACCENT_SOFT),
    Color(DarkPalette.SUCCESS), Color(DarkPalette.DANGER), dark = true,
)

/** Be Vietnam Pro 400 / 500 / 700 (res/font, OFL) - tối đa ba mức đậm một màn. */
val BeVietnamPro = FontFamily(
    Font(R.font.be_vietnam_pro_regular, FontWeight.Normal),
    Font(R.font.be_vietnam_pro_medium, FontWeight.Medium),
    Font(R.font.be_vietnam_pro_bold, FontWeight.Bold),
)

private fun style(size: Int, weight: FontWeight, color: Color, line: Int = size + size / 2) =
    TextStyle(fontFamily = BeVietnamPro, fontSize = size.sp, lineHeight = line.sp, fontWeight = weight, color = color)

/** Kiểu chữ theo thang DESIGN.md §5.5 (màu chữ mặc định = mực; chữ phụ đổi màu tại chỗ dùng). */
@Immutable
class AbookType(
    val caption: TextStyle, val bodySmall: TextStyle, val label: TextStyle, val body: TextStyle, val bodyStrong: TextStyle,
    val sectionTitle: TextStyle, val screenTitle: TextStyle, val tab: TextStyle,
)

internal fun typeFor(colors: AbookColors) = AbookType(
    caption = style(TypeScale.CAPTION, FontWeight.Normal, colors.text3),
    bodySmall = style(TypeScale.BODY_SMALL, FontWeight.Normal, colors.text2),
    label = style(TypeScale.BODY_SMALL, FontWeight.Medium, colors.text),
    body = style(TypeScale.BODY, FontWeight.Normal, colors.text),
    bodyStrong = style(TypeScale.BODY, FontWeight.Medium, colors.text),
    sectionTitle = style(TypeScale.SECTION_TITLE, FontWeight.Medium, colors.text),
    screenTitle = style(TypeScale.SCREEN_TITLE_PHONE, FontWeight.Bold, colors.text, line = 32),
    tab = style(TypeScale.BODY_SMALL, FontWeight.Medium, colors.text2),
)

/** Khoảng cách / bo góc / vùng chạm (DESIGN.md §5.5) dưới dạng Dp. */
@Immutable
object Dim {
    val s4 = Dimens.SPACE_4.dp
    val s8 = Dimens.SPACE_8.dp
    val s12 = Dimens.SPACE_12.dp
    val s16 = Dimens.SPACE_16.dp
    val s24 = Dimens.SPACE_24.dp
    val s32 = Dimens.SPACE_32.dp
    val s48 = Dimens.SPACE_48.dp
    val margin = Dimens.MARGIN_PHONE.dp
    val sectionGap = Dimens.SECTION_GAP_PHONE.dp
    val radiusControl = Dimens.RADIUS_CONTROL.dp
    val radiusCover = Dimens.RADIUS_COVER.dp
    val radiusSheet = Dimens.RADIUS_SHEET.dp
    val touch = Dimens.TOUCH_PHONE.dp
}

private val LocalColors = staticCompositionLocalOf { LightColors }
private val LocalType = staticCompositionLocalOf { typeFor(LightColors) }

/** Truy cập token: `Abook.colors.bg`, `Abook.type.body`. */
object Abook {
    val colors: AbookColors
        @Composable @ReadOnlyComposable get() = LocalColors.current
    val type: AbookType
        @Composable @ReadOnlyComposable get() = LocalType.current
}

@Composable
fun AbookTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val colors = if (dark) DarkColors else LightColors
    val type = androidx.compose.runtime.remember(dark) { typeFor(colors) }
    CompositionLocalProvider(LocalColors provides colors, LocalType provides type, content = content)
}
