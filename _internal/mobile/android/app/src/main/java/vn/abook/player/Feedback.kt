package vn.abook.player

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.provider.Settings
import android.view.View
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.pow
import kotlin.math.sin

/** DESIGN 5.3/5.4. Same notes as shared/feedback.ts and desktop_qt/feedback.cpp.
 * Timer feedback lives in the playback process, so it also works without an Activity or with the screen off.
 */
object Feedback {
    data class Note(val pitch: Double, val at: Double, val length: Double, val level: Double)
    @Volatile var sounds = true
        internal set
    @Volatile var haptics = true
        internal set

    fun notes(kind: String): List<Note> = when (kind) {
        "toggle" -> listOf(Note(1568.0, 0.0, 0.06, -30.0))
        "tick" -> listOf(Note(1318.5, 0.0, 0.04, -32.0))
        "confirm", "sleepExtend" -> listOf(Note(1046.5, 0.0, 0.12, -24.0), Note(1318.5, 0.09, 0.16, -24.0))
        "done" -> listOf(Note(1046.5, 0.0, 0.1, -24.0), Note(1318.5, 0.08, 0.1, -24.0), Note(1568.0, 0.16, 0.09, -24.0))
        "sleepWarn" -> listOf(Note(220.0, 0.0, 0.25, -22.0))
        else -> emptyList() // Ordinary buttons, play/pause, long press and errors intentionally have no sound.
    }

    internal fun effect(kind: String): String? = when (kind) {
        "toggle" -> "SEGMENT_TICK"
        "tick" -> "CLOCK_TICK"
        "confirm", "done", "sleepExtend" -> "CONFIRM"
        "longPress" -> "LONG_PRESS"
        "reject" -> "REJECT"
        "tap", "playPause" -> "CONTEXT_CLICK"
        else -> null // No vibration for sleep warning or expiry.
    }

    internal interface Output {
        fun sound(notes: List<Note>, context: Context?)
        fun haptic(effect: String, view: View?, context: Context?)
    }

    internal var output: Output = AndroidOutput

    fun play(kind: String, view: View? = null) {
        val playing = Playback.player?.isPlaying == true
        val context = view?.context ?: runCatching { Playback.appContext }.getOrNull()
        val notes = notes(kind)
        // Dispatch both in this call, with no delayed vibration or UI event round trip.
        if (sounds && notes.isNotEmpty() && (!playing || kind == "sleepWarn" || kind == "sleepExtend"))
            runCatching { output.sound(notes, context) }
        val effect = effect(kind)
        if (haptics && effect != null) runCatching { output.haptic(effect, view, context) }
    }

    private val harmonics = doubleArrayOf(0.0, 1.0, 0.55, 0.35, 0.18, 0.08)
    private fun wave(phase: Double): Double = (1 until harmonics.size).sumOf { harmonics[it] * sin(it * phase) }
    private val wavePeak by lazy { (0 until 4096).maxOf { abs(wave(2 * PI * it / 4096)) } }

    internal fun pcm(notes: List<Note>, rate: Int = 48_000): ShortArray {
        val end = notes.maxOfOrNull { it.at + it.length } ?: return ShortArray(0)
        return ShortArray(kotlin.math.ceil(end * rate).toInt()) { i ->
            val t = i.toDouble() / rate
            val mixed = notes.sumOf { note ->
                val local = t - note.at
                if (local < 0 || local >= note.length) 0.0 else {
                    val peak = 10.0.pow(note.level / 20)
                    val gain = if (local < 0.004) 0.0001 * (peak / 0.0001).pow(local / 0.004)
                        else peak * (0.0001 / peak).pow((local - 0.004) / (note.length - 0.004))
                    gain * wave(2 * PI * note.pitch * local) / wavePeak
                }
            }
            (mixed.coerceIn(-1.0, 1.0) * 32767).toInt().toShort()
        }
    }

    private object AndroidOutput : Output {
        private val main by lazy { Handler(Looper.getMainLooper()) }
        private val attributes: AudioAttributes get() = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build()

        override fun sound(notes: List<Note>, context: Context?) {
            context ?: return
            val manager = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager ?: return
            if (manager.ringerMode != AudioManager.RINGER_MODE_NORMAL) return
            val samples = pcm(notes)
            val track = AudioTrack.Builder().setAudioAttributes(attributes)
                .setAudioFormat(AudioFormat.Builder().setSampleRate(48_000).setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                .setTransferMode(AudioTrack.MODE_STATIC).setBufferSizeInBytes(samples.size * 2).build()
            try {
                check(track.write(samples, 0, samples.size) == samples.size)
                track.play() // Independent of the audiobook fade; never requests or steals audio focus.
                main.postDelayed({ runCatching { track.stop() }; track.release() }, 500L)
            } catch (error: Exception) {
                track.release()
                throw error
            }
        }

        override fun haptic(effect: String, view: View?, context: Context?) {
            if (view != null) {
                Haptics.constant(effect)?.let { view.performHapticFeedback(it) }
                return
            }
            context ?: return
            // Screen-off gestures have no View. Respect the same OS switch as View feedback.
            if (Settings.System.getInt(context.contentResolver, Settings.System.HAPTIC_FEEDBACK_ENABLED, 1) == 0) return
            @Suppress("DEPRECATION")
            val vibrator = context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator ?: return
            val pulse = if (Build.VERSION.SDK_INT >= 29) VibrationEffect.createPredefined(VibrationEffect.EFFECT_CLICK)
                else VibrationEffect.createOneShot(20L, VibrationEffect.DEFAULT_AMPLITUDE)
            @Suppress("DEPRECATION")
            vibrator.vibrate(pulse, attributes)
        }
    }
}
