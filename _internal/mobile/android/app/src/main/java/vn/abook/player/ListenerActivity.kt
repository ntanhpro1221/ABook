package vn.abook.player

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioManager
import android.os.PowerManager
import android.os.SystemClock
import android.provider.Settings
import androidx.core.content.ContextCompat

/** Service-owned: keeps observing other apps, the lock screen and volume keys without an Activity. */
internal object ListenerActivity {
    val evidence = SleepPolicy()
    private var context: Context? = null
    private var volume = -1
    private var lastInput = -1L
    private val receiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            when (intent.action) {
                Intent.ACTION_SCREEN_ON -> Playback.touched("screen-on")
                Intent.ACTION_USER_PRESENT -> Playback.touched("unlock")
                Intent.ACTION_SCREEN_OFF -> {
                    val timeout = Settings.System.getInt(context.contentResolver, Settings.System.SCREEN_OFF_TIMEOUT, 30_000).toLong()
                    if (isDeliberateScreenOff(SystemClock.elapsedRealtime(), lastInput, timeout)) Playback.touched("screen-off")
                }
            }
            sampleScreen()
            sampleVolume()
        }
    }

    internal fun isDeliberateScreenOff(now: Long, last: Long, timeout: Long): Boolean =
        last >= 0 && timeout > 2_000 && now - last in 0 until (timeout - 2_000)

    fun inputObserved() { lastInput = SystemClock.elapsedRealtime() }

    fun start(app: Context) {
        if (context != null) return
        context = app.applicationContext
        volume = audio().getStreamVolume(AudioManager.STREAM_MUSIC)
        evidence.screen(power().isInteractive, SystemClock.elapsedRealtime())
        ContextCompat.registerReceiver(context!!, receiver, IntentFilter().apply {
            addAction(Intent.ACTION_SCREEN_ON)
            addAction(Intent.ACTION_SCREEN_OFF)
            addAction(Intent.ACTION_USER_PRESENT)
            addAction("android.media.VOLUME_CHANGED_ACTION")
        }, ContextCompat.RECEIVER_NOT_EXPORTED)
    }

    fun stop() {
        context?.unregisterReceiver(receiver)
        context = null
        evidence.screen(true, SystemClock.elapsedRealtime())
        Motion.stop()
    }

    private fun power() = context!!.getSystemService(Context.POWER_SERVICE) as PowerManager
    private fun audio() = context!!.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    fun sampleScreen() {
        if (context == null) return
        val on = power().isInteractive
        evidence.screen(on, SystemClock.elapsedRealtime())
    }

    fun sampleVolume() {
        if (context == null) return
        val current = audio().getStreamVolume(AudioManager.STREAM_MUSIC)
        if (current != volume) { volume = current; Playback.touched("volume") }
    }

    fun allowsNightSchedule(): Boolean {
        sampleScreen()
        sampleVolume()
        return context != null && evidence.allows(SystemClock.elapsedRealtime(), SleepPolicy.NIGHT_IDLE_MS, Motion.available, 0L)
    }
}
