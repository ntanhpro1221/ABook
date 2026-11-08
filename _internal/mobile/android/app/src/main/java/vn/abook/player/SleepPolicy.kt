package vn.abook.player

/** Evidence for the listener-enabled night schedule. No Android dependencies; unknown evidence never means asleep. */
internal class SleepPolicy {
    companion object {
        const val WINDOW_MS = 30_000L
        const val STILL_WINDOWS = 4
        const val STILL_DEVIATION = 0.06
        const val NIGHT_IDLE_MS = WINDOW_MS * STILL_WINDOWS
    }

    var screenOn = true
        private set
    private var offSince = 0L
    private var lastAwake = 0L
    private var stillWindows = 0
    private var lastWindowEnd = 0L

    fun screen(on: Boolean, now: Long) {
        if (on || screenOn != on || offSince == 0L) {
            awake(now)
            offSince = if (on) 0 else now
        }
        screenOn = on
    }

    fun awake(now: Long) {
        lastAwake = now
        stillWindows = 0
        lastWindowEnd = 0
    }

    fun motionWindow(start: Long, end: Long, deviation: Double) {
        val continuous = lastWindowEnd == 0L || start - lastWindowEnd in 0..1_000L
        if (screenOn || start < maxOf(offSince, lastAwake) || end - start !in WINDOW_MS..(WINDOW_MS + 5_000L) ||
            !deviation.isFinite() || deviation >= STILL_DEVIATION) {
            stillWindows = 0
        } else {
            stillWindows = if (continuous) stillWindows + 1 else 1
        }
        lastWindowEnd = end
    }

    fun allows(now: Long, idleMs: Long, sensorAvailable: Boolean, lastInteraction: Long): Boolean =
        idleMs > 0 && !screenOn && offSince > 0 &&
            now - maxOf(offSince, lastAwake, lastInteraction) >= idleMs &&
            (!sensorAvailable || (stillWindows >= STILL_WINDOWS && now - lastWindowEnd in 0..(WINDOW_MS + 5_000L)))

    fun resetMotion() { stillWindows = 0; lastWindowEnd = 0 }
}

/** Shared, word-for-word with the web and Qt player. */
object AutoSleepText {
    const val SCHEDULE = "Tự hẹn theo lịch đêm"
    const val CONTINUE = "Chạm để nghe tiếp"
    fun reason(reason: String): String = when (reason) { "schedule" -> SCHEDULE; else -> "" }
}
