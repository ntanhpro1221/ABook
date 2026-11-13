package vn.abook.player.ui.theme

import androidx.compose.ui.graphics.Color
import kotlin.math.*

/** OKLCH to sRGB, with the same coefficients, clipping and 8-bit rounding as Qt CastLogic.js and CSS. */
internal fun avatarColor(hue: Int, dark: Boolean, ink: Boolean): Color {
    val lightness = if (ink) (if (dark) DarkPalette.AVATAR_FG_L else LightPalette.AVATAR_FG_L)
        else (if (dark) DarkPalette.AVATAR_BG_L else LightPalette.AVATAR_BG_L)
    val chroma = if (ink) 0.085 else 0.03
    val a = chroma * cos(hue * PI / 180)
    val b = chroma * sin(hue * PI / 180)
    val l = (lightness + 0.3963377774 * a + 0.2158037573 * b).pow(3)
    val m = (lightness - 0.1055613458 * a - 0.0638541728 * b).pow(3)
    val s = (lightness - 0.0894841775 * a - 1.2914855480 * b).pow(3)
    fun channel(value: Double): Int {
        val c = value.coerceIn(0.0, 1.0)
        val g = if (c <= 0.0031308) 12.92 * c else 1.055 * c.pow(1 / 2.4) - 0.055
        return (g * 255).roundToInt()
    }
    return Color(channel(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
        channel(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
        channel(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s))
}
