package vn.abook.player.ui.data

import androidx.compose.runtime.Immutable
import java.text.Normalizer
import org.json.JSONObject

@Immutable
data class AvatarRef(val kind: String, val key: String = "", val file: String = "", val initials: String = "", val color: String = "", val bits: Int = 0)

object AvatarArt {
    private val colors = listOf("#805c38", "#675f48", "#73594c", "#4c6963", "#66607a", "#80565e")
    fun hash(name: String): Long {
        var value = 2166136261L
        for (byte in Normalizer.normalize(name, Normalizer.Form.NFC).toByteArray(Charsets.UTF_8)) {
            value = ((value xor (byte.toLong() and 255)) * 16777619L) and 0xffffffffL
        }
        return value
    }
    fun pattern(name: String): AvatarRef {
        val key = Normalizer.normalize(name, Normalizer.Form.NFC)
        val value = hash(key)
        val initials = key.replace('_', ' ').split(Regex("\\s+")).filter { it.isNotEmpty() && !it.matches(Regex("[IVXLCDM]+")) }
            .take(2).joinToString("") { it.substring(0, it.offsetByCodePoints(0, 1)) }.uppercase(java.util.Locale.ROOT)
        return AvatarRef("pattern", key, initials = initials, color = colors[(value % colors.size).toInt()], bits = (value and 32767).toInt())
    }
    fun voiceFile(name: String): String = "voice-${hash(name).toString(16).padStart(8, '0')}.webp"
    fun parse(json: JSONObject?): AvatarRef? = json?.let {
        AvatarRef(it.optString("kind"), it.optString("key"), it.optString("file"), it.optString("initials"), it.optString("color"), it.optInt("bits"))
    }
    fun cell(bits: Int, x: Int, y: Int): Boolean = bits and (1 shl (y * 3 + minOf(x, 4 - x))) != 0
    fun imageFile(file: String): Boolean = file.matches(Regex("avatars/[0-9a-f]{64}\\.webp"))
}
