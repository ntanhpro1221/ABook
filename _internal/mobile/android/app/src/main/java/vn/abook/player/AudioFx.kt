package vn.abook.player

import android.content.Context
import android.content.SharedPreferences
import androidx.media3.common.C
import androidx.media3.common.PlaybackParameters
import androidx.media3.common.audio.AudioProcessor.AudioFormat
import androidx.media3.common.audio.AudioProcessor.UnhandledAudioFormatException
import androidx.media3.common.audio.BaseAudioProcessor
import androidx.media3.common.audio.AudioProcessor
import androidx.media3.common.audio.AudioProcessorChain
import androidx.media3.common.audio.SonicAudioProcessor
import androidx.media3.common.util.UnstableApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.nio.ByteBuffer
import kotlin.math.pow

/** One app setting, shared by recorded chapters and read-aloud clips; music has its own player. */
object AudioFx {
    private var prefs: SharedPreferences? = null
    private val mutable = MutableStateFlow(AudioFxSettings())
    val state = mutable.asStateFlow()
    @Volatile var current = AudioFxSettings()
        private set
    fun init(context: Context) {
        if (prefs != null) return
        val p = context.getSharedPreferences("audio_fx", Context.MODE_PRIVATE)
        prefs = p
        current = AudioFxSettings(p.getBoolean("enabled", false), p.getInt("preset", 0),
            List(5) { p.getFloat("band$it", 0f).toDouble() }, p.getFloat("bass", 0f).toDouble(),
            p.getFloat("boost", 0f).toDouble(), p.getFloat("pitch", 0f).toDouble(), p.getFloat("volume", .9f).toDouble()).safe()
        mutable.value = current
    }
    fun update(value: AudioFxSettings) {
        current = value.safe(); mutable.value = current
        prefs?.edit()?.apply {
            putBoolean("enabled", current.enabled); putInt("preset", current.preset)
            current.bands.forEachIndexed { i, db -> putFloat("band$i", db.toFloat()) }
            putFloat("bass", current.bass.toFloat()); putFloat("boost", current.boost.toFloat())
            putFloat("pitch", current.pitch.toFloat()); putFloat("volume", current.volume.toFloat())
        }?.apply()
        Playback.player?.let { it.playbackParameters = PlaybackParameters(it.playbackParameters.speed, pitchRatio()) }
        Playback.applyVolume()
    }
    fun pitchRatio() = 2.0.pow(current.pitch / 12).toFloat()
}

/** Kept active even at default so changing EQ never tears down AudioTrack. The chain places this after Sonic. */
@androidx.annotation.OptIn(UnstableApi::class)
class AudioFxProcessor : BaseAudioProcessor() {
    private var dsp: AudioFxDsp? = null
    private var applied: AudioFxSettings? = null
    private var frame = DoubleArray(0)
    override fun onConfigure(inputAudioFormat: AudioFormat): AudioFormat {
        if (inputAudioFormat.encoding != C.ENCODING_PCM_16BIT) throw UnhandledAudioFormatException(inputAudioFormat)
        dsp = AudioFxDsp(inputAudioFormat.sampleRate, inputAudioFormat.channelCount)
        frame = DoubleArray(inputAudioFormat.channelCount)
        applied = null
        return inputAudioFormat
    }
    override fun onFlush() {
        if (inputAudioFormat.channelCount > 0) dsp = AudioFxDsp(inputAudioFormat.sampleRate, inputAudioFormat.channelCount)
        applied = null
    }
    override fun queueInput(inputBuffer: ByteBuffer) {
        val output = replaceOutputBuffer(inputBuffer.remaining())
        val value = AudioFx.current
        if (value != applied) { dsp!!.configure(value); applied = value }
        while (inputBuffer.remaining() >= frame.size * 2) {
            for (ch in frame.indices) frame[ch] = inputBuffer.short / 32768.0
            dsp!!.process(frame)
            for (ch in frame.indices) output.putShort((frame[ch] * 32767).toInt().toShort())
        }
        output.flip()
    }
}

/** Sonic first, EQ and limiter last: pitch interpolation cannot create a peak after the guard. */
@androidx.annotation.OptIn(UnstableApi::class)
class AudioFxChain : AudioProcessorChain {
    private val sonic = SonicAudioProcessor()
    private val processors = arrayOf<AudioProcessor>(sonic, AudioFxProcessor())
    override fun getAudioProcessors() = processors
    override fun applyPlaybackParameters(value: PlaybackParameters): PlaybackParameters {
        sonic.setSpeed(value.speed); sonic.setPitch(value.pitch)
        return value
    }
    override fun applySkipSilenceEnabled(enabled: Boolean) = false
    override fun getMediaDuration(playoutDuration: Long) = sonic.getMediaDuration(playoutDuration)
    override fun getSkippedOutputFrameCount() = 0L
}
