package vn.abook.player.readaloud

import android.app.ActivityManager
import android.content.Context
import android.os.BatteryManager
import vn.abook.player.vieneu.VieneuVoices
import java.util.concurrent.ConcurrentHashMap

/**
 * Loads an on-device voice engine before anyone presses play (a book's page or player was opened with that voice chosen), so play does not wait for the load - 4.6 s on
 * the OPPO (livejoin3). Reads nothing. Counts as one use for [IdleEngine] (the engine is let go again 180 s after the last use), and is skipped on a phone that is
 * short of battery or memory (desktop `power_source.spare_for_preload`, `ReadAloud.preload`: same two numbers).
 */
object EnginePreload {
    /** Not on battery below this percent. */
    const val LOW_BATTERY_PERCENT = 20
    /** Less free memory than this: an engine is 300-450 MB, do not add one nobody asked for. */
    const val LOW_MEMORY_BYTES = 1L shl 30

    private val loading = ConcurrentHashMap.newKeySet<String>()

    fun spare(charging: Boolean, percent: Int, availableBytes: Long): Boolean =
        (charging || percent !in 0 until LOW_BATTERY_PERCENT) && availableBytes >= LOW_MEMORY_BYTES

    private fun spare(context: Context): Boolean {
        val battery = context.getSystemService(BatteryManager::class.java)
        val charging = battery?.isCharging == true
        val percent = battery?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: 100
        val info = ActivityManager.MemoryInfo()
        context.getSystemService(ActivityManager::class.java)?.getMemoryInfo(info)
        return spare(charging, percent, if (info.totalMem == 0L) Long.MAX_VALUE else info.availMem)
    }

    /** Whether [voice] has an engine to load (VieNeu, Supertonic). */
    fun hasEngine(voice: String): Boolean = ClipCache.split(voice).first.let { it == SupertonicVoices.PREFIX || it == VieneuVoices.PREFIX }

    /** Start loading [voice]'s engine on a background thread; false when there is nothing to load, it is loading already or the phone has no spare. [load] is the work (tests pass their own). */
    fun start(context: Context?, voice: String, spare: Boolean = context?.let { spare(it) } ?: false, load: () -> Unit = { loadEngine(voice) }): Boolean {
        if (!hasEngine(voice) || !spare || !loading.add(voice)) return false
        Thread({
            try {
                load()
            } catch (_: Exception) {
                // only a head start: a real read loads the engine and reports what is wrong
            } finally {
                loading.remove(voice)
            }
        }, "abook-preload").apply { isDaemon = true }.start()
        return true
    }

    private fun loadEngine(voice: String) {
        if (ClipCache.split(voice).first == SupertonicVoices.PREFIX) SupertonicVoices.preload(voice) else VieneuVoices.preload(voice)
    }
}
