package vn.abook.player

import org.json.JSONObject
import kotlin.math.floor

/** Artwork v1: 96x96 RGB bytes, identical to MusicArtRaster.mjs. */
object MusicArtwork {
    fun seed(link: String, info: JSONObject): Int {
        fun axis(key: String): Int {
            val v = (info.opt(key) as? Number)?.toDouble()?.takeIf { it.isFinite() } ?: 0.0
            return floor((v.coerceIn(-1.0, 1.0) + 1) * 100 + .5).toInt()
        }
        val emotions = info.optJSONObject("emotions")
        val dominant = emotions?.keys()?.asSequence()?.mapNotNull { key ->
            (emotions.opt(key) as? Number)?.toDouble()?.takeIf { it.isFinite() }?.let { key to it }
        }?.sortedWith(compareBy<Pair<String, Double>>({ -it.second }, { it.first }))?.firstOrNull()?.first ?: ""
        val text = "$link|${info.optString("style", "")}|${axis("valence")}|${axis("arousal")}|$dominant"
        var value = 7
        for (char in text) value = (value * 31 + char.code) % 65521
        val style = info.optString("style", "")
        val palette = when {
            style == "dark" || dominant in listOf("fear", "tension", "anger") || axis("valence") < 70 -> 3
            dominant in listOf("tenderness", "nostalgia", "moved") -> 1
            axis("valence") > 130 || dominant in listOf("joy", "playful") -> 2
            style in listOf("medieval_folk", "acoustic_light", "world_other") -> 4
            else -> 0
        }
        return value * 25 + (axis("arousal") / 41).coerceAtMost(4) * 5 + palette
    }

    fun rgb(seed: Int): ByteArray {
        val s = if (seed >= 0) seed % 1638025 else 7
        val palettes = arrayOf(
            arrayOf(intArrayOf(24,46,48), intArrayOf(73,127,125), intArrayOf(226,190,132)),
            arrayOf(intArrayOf(48,37,59), intArrayOf(129,103,141), intArrayOf(230,190,164)),
            arrayOf(intArrayOf(48,40,30), intArrayOf(159,113,64), intArrayOf(236,211,165)),
            arrayOf(intArrayOf(29,42,64), intArrayOf(88,124,159), intArrayOf(214,203,170)),
            arrayOf(intArrayOf(46,51,38), intArrayOf(115,133,90), intArrayOf(223,206,152)),
        )
        val p = palettes[s % 5]
        val cx = 22 + s % 51; val cy = 20 + s / 53 % 39
        val radius = 20 + (4 - s / 5 % 5) * 3
        val rr = radius * radius
        val out = ByteArray(96 * 96 * 3)
        for (y in 0 until 96) for (x in 0 until 96) {
            val d = (x-cx)*(x-cx) + (y-cy)*(y-cy)
            val glow = (96 - d / 90).coerceAtLeast(0)
            val wave = 64 + (x-48)*(x-48) / 100 - s % 13
            for (c in 0..2) {
                var v = (p[0][c] * (192-glow) + p[1][c] * glow) / 192
                if (d <= rr) v = (p[2][c] * 4 + v) / 5
                if (d > rr + 130 && d < rr + 210) v = (p[1][c] + v) / 2
                if (y >= wave) v = (v * 3 + p[1][c]) / 4
                out[(y*96+x)*3+c] = v.toByte()
            }
        }
        return out
    }
}
