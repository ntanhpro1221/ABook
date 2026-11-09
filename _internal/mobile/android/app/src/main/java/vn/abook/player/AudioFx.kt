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
import org.json.JSONObject
import org.json.JSONArray

/** One app setting, shared by recorded chapters and read-aloud clips; music has its own player. */
object AudioFx {
    private var prefs: SharedPreferences? = null
    private val mutable = MutableStateFlow(AudioFxSettings())
    val state = mutable.asStateFlow()
    private var bookId = ""
    private val scoped = MutableStateFlow(false)
    val bookOnly = scoped.asStateFlow()
    @Volatile var current = AudioFxSettings()
        private set
    fun init(context: Context) {
        if (prefs != null) return
        val p = context.getSharedPreferences("audio_fx", Context.MODE_PRIVATE)
        prefs = p
        current = read("shared")
        mutable.value = current
    }
    private fun read(key: String): AudioFxSettings {
        val o = runCatching { JSONObject(prefs?.getString(key, "{}") ?: "{}") }.getOrDefault(JSONObject())
        return AudioFxSettings(o.optBoolean("enabled"), o.optInt("preset"),
            List(5) { o.optJSONArray("bands")?.optDouble(it, 0.0) ?: 0.0 },
            o.optDouble("bass", 0.0), o.optDouble("boost", 0.0), o.optDouble("pitch", 0.0), o.optDouble("volume", .9),
            o.optDouble("speed", 1.0), o.optBoolean("mono"), o.optDouble("balance", 0.0), o.optBoolean("skipSilence"),
            o.optDouble("silenceDb", -60.0), o.optDouble("silenceSeconds", 3.0), o.optDouble("keepSeconds", 1.5)).safe()
    }
    fun selectBook(id: String): AudioFxSettings {
        bookId = id
        scoped.value = id.isNotEmpty() && prefs?.contains("book:$id") == true
        current = read(if (scoped.value) "book:$id" else "shared")
        mutable.value = current
        Playback.applyVolume()
        return current
    }
    fun setBookOnly(enabled: Boolean) {
        if (bookId.isEmpty() || enabled == scoped.value) return
        scoped.value = enabled
        if (enabled) update(current) else {
            prefs?.edit()?.remove("book:$bookId")?.apply()
            update(read("shared"))
        }
    }
    fun update(value: AudioFxSettings) {
        current = value.safe(); mutable.value = current
        val s = current
        val o = JSONObject().put("enabled", s.enabled).put("preset", s.preset).put("bands", JSONArray(s.bands))
            .put("bass", s.bass).put("boost", s.boost).put("pitch", s.pitch).put("volume", s.volume).put("speed", s.speed)
            .put("mono", s.mono).put("balance", s.balance).put("skipSilence", s.skipSilence)
            .put("silenceDb", s.silenceDb).put("silenceSeconds", s.silenceSeconds).put("keepSeconds", s.keepSeconds)
        prefs?.edit()?.putString(if (scoped.value) "book:$bookId" else "shared", o.toString())?.apply()
        Playback.player?.let { it.playbackParameters = PlaybackParameters(s.speed.toFloat(), pitchRatio()) }
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
    private var sourceChannels = 0
    override fun onConfigure(inputAudioFormat: AudioFormat): AudioFormat {
        if (inputAudioFormat.encoding != C.ENCODING_PCM_16BIT) throw UnhandledAudioFormatException(inputAudioFormat)
        sourceChannels = inputAudioFormat.channelCount
        val channels = maxOf(2, sourceChannels)
        dsp = AudioFxDsp(inputAudioFormat.sampleRate, channels)
        frame = DoubleArray(channels)
        applied = null
        return AudioFormat(inputAudioFormat.sampleRate, channels, C.ENCODING_PCM_16BIT)
    }
    override fun onFlush() {
        if (inputAudioFormat.channelCount > 0) dsp = AudioFxDsp(inputAudioFormat.sampleRate, frame.size)
        applied = null
    }
    override fun queueInput(inputBuffer: ByteBuffer) {
        val output = replaceOutputBuffer(inputBuffer.remaining() / (sourceChannels * 2) * frame.size * 2)
        val value = AudioFx.current
        if (value != applied) { dsp!!.configure(value); applied = value }
        while (inputBuffer.remaining() >= sourceChannels * 2) {
            for (ch in 0 until sourceChannels) frame[ch] = inputBuffer.short / 32768.0
            if (sourceChannels == 1) frame[1] = frame[0]
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
    private val silence = SilenceProcessor()
    private val processors = arrayOf<AudioProcessor>(silence, sonic, AudioFxProcessor())
    override fun getAudioProcessors() = processors
    override fun applyPlaybackParameters(value: PlaybackParameters): PlaybackParameters {
        sonic.setSpeed(value.speed); sonic.setPitch(value.pitch)
        return value
    }
    override fun applySkipSilenceEnabled(enabled: Boolean) = false
    override fun getMediaDuration(playoutDuration: Long) = silence.sourceDurationUs(sonic.getMediaDuration(playoutDuration))
    override fun getSkippedOutputFrameCount() = 0L
}

@androidx.annotation.OptIn(UnstableApi::class)
class SilenceProcessor : BaseAudioProcessor() {
    private var trimmer: SilenceTrimmer? = null
    private var frame = DoubleArray(0)
    private var pending: ByteBuffer? = null
    override fun onConfigure(inputAudioFormat: AudioFormat): AudioFormat {
        if (inputAudioFormat.encoding != C.ENCODING_PCM_16BIT) throw UnhandledAudioFormatException(inputAudioFormat)
        return inputAudioFormat
    }
    override fun onFlush() {
        trimmer = SilenceTrimmer(inputAudioFormat.sampleRate, inputAudioFormat.channelCount)
        frame = DoubleArray(inputAudioFormat.channelCount)
    }
    private fun output(inputBytes: Int): ByteBuffer = replaceOutputBuffer(inputBytes + (inputAudioFormat.sampleRate * 10 + 1) * frame.size * 2)
    private fun emit(frame: DoubleArray) { for (x in frame) pending!!.putShort((x * 32768).toInt().toShort()) }
    override fun queueInput(inputBuffer: ByteBuffer) {
        val out = output(inputBuffer.remaining()); pending = out
        trimmer!!.configure(AudioFx.current, ::emit)
        while (inputBuffer.remaining() >= frame.size * 2) {
            for (ch in frame.indices) frame[ch] = inputBuffer.short / 32768.0
            trimmer!!.push(frame, ::emit)
        }
        out.flip(); pending = null
    }
    override fun onQueueEndOfStream() {
        val out = output(0); pending = out; trimmer?.finish(::emit); out.flip(); pending = null
    }
    fun sourceDurationUs(compressedUs: Long) = trimmer?.sourceDurationUs(compressedUs) ?: compressedUs
}
