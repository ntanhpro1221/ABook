package vn.abook.player

/**
 * How far the player steps back when the listener resumes, by how long the pause was: under half a minute nothing, up to ten minutes 5 s, longer
 * 10 s. One rule on both platforms (desktop `rewindAfter` in ui/src/listen/sleep.ts, same numbers; shared cases tests/fixtures/auto_rewind/cases.json).
 */
object AutoRewind {
    const val SHORT_MS = 30_000L
    const val LONG_MS = 10 * 60_000L

    fun seconds(pausedMs: Long): Double = when {
        pausedMs < SHORT_MS -> 0.0
        pausedMs <= LONG_MS -> 5.0
        else -> 10.0
    }
}
