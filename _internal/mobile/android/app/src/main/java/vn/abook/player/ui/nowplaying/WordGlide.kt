package vn.abook.player.ui.nowplaying

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.VectorConverter
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.geometry.Rect
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.MotionMs
import kotlin.math.abs

/** Display ranges only: timing offsets and tap targets remain unchanged. */
internal object WordInk {
    fun range(text: String, from: Int, until: Int): IntRange {
        fun edge(c: Char) = c.isWhitespace() || Character.getType(c) in setOf(
            Character.CONNECTOR_PUNCTUATION.toInt(), Character.DASH_PUNCTUATION.toInt(),
            Character.START_PUNCTUATION.toInt(), Character.END_PUNCTUATION.toInt(),
            Character.INITIAL_QUOTE_PUNCTUATION.toInt(), Character.FINAL_QUOTE_PUNCTUATION.toInt(),
            Character.OTHER_PUNCTUATION.toInt())
        var start = from.coerceIn(0, text.length)
        var end = until.coerceIn(start, text.length)
        while (start < end && edge(text[start])) start++
        while (end > start && edge(text[end - 1])) end--
        return start until end
    }
    fun duration(step: Long, rate: Double): Int = (step / rate.coerceAtLeast(0.1)).toInt().coerceIn(0, MotionMs.FAST)
}

/** Read only in drawBehind: animation frames invalidate ink, never the paragraph composition. */
@Stable
internal class WordGlide {
    val rect = Animatable(Rect.Zero, Rect.VectorConverter)
    var visible by mutableStateOf(false)
        private set

    suspend fun move(target: Rect?, duration: Int, sequential: Boolean) {
        if (target == null) { visible = false; return }
        val old = rect.value
        if (!visible || !sequential || duration <= 0) {
            rect.snapTo(target)
        } else if (abs(old.top - target.top) > 4f) {
            val half = duration / 2
            rect.animateTo(Rect(old.left, old.top, old.left, old.bottom), tween(half, easing = Motion.Standard))
            rect.snapTo(Rect(target.left, target.top, target.left, target.bottom))
            rect.animateTo(target, tween(duration - half, easing = Motion.Standard))
        } else rect.animateTo(target, tween(duration, easing = Motion.Standard))
        visible = true
    }
}
