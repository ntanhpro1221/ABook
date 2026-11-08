package vn.abook.player

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioManager
import android.os.PowerManager
import android.os.SystemClock
import androidx.core.content.ContextCompat

/** Service-owned: keeps observing other apps, the lock screen and volume keys without an Activity. */
internal object ListenerActivity {
    val evidence = SleepPolicy()
    private var context: Context? = null
    private var volume = -1
    private val receiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            sampleScreen()
            if (intent.action == Intent.ACTION_USER_PRESENT) Playback.touched()
            sampleVolume()
        }
    }

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
        SleepTimer.onAwake()
        Motion.stop()
    }

    private fun power() = context!!.getSystemService(Context.POWER_SERVICE) as PowerManager
    private fun audio() = context!!.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    fun sampleScreen() {
        if (context == null) return
        val on = power().isInteractive
        val wasOn = evidence.screenOn
        evidence.screen(on, SystemClock.elapsedRealtime())
        if (on && !wasOn) Playback.touched()
        // While any app is visible, continuously refresh the awake boundary.
        if (on) Playback.touched()
    }

    fun sampleVolume() {
        if (context == null) return
        val current = audio().getStreamVolume(AudioManager.STREAM_MUSIC)
        if (current != volume) { volume = current; Playback.touched() }
    }

    fun allowsNightSchedule(): Boolean {
        sampleScreen()
        sampleVolume()
        return context != null && evidence.allows(SystemClock.elapsedRealtime(), SleepPolicy.NIGHT_IDLE_MS, Motion.available, 0L)
    }
}
