package vn.abook.player

/**
 * A finger drag delivers one MOVE per input frame (60-120 a second). Each sleep-cycle restart persists the timer, emits "sleep"
 * (player widget refresh, remote kick) and rewrites the bedtime log, so a drag counts as listener activity at most once per
 * [INTERVAL_MS]. Taps, controls and resume are not limited: they arrive once per deliberate action.
 */
internal object ScrollActivity {
    const val INTERVAL_MS = 1_000L
    private var last = Long.MIN_VALUE

    @Synchronized fun due(now: Long): Boolean {
        if (last != Long.MIN_VALUE && now - last in 0 until INTERVAL_MS) return false
        last = now
        return true
    }

    @Synchronized fun reset() {
        last = Long.MIN_VALUE
    }
}
