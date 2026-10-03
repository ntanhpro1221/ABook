package vn.abook.player.readaloud

import android.content.Context
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.io.File
import java.util.Locale
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Giọng của chính chiếc máy (Android `TextToSpeech`, chỉ giọng tiếng Việt): không tải gì, không cần mạng (trừ giọng mạng của Google nếu người dùng chọn).
 * Đọc ra file WAV bằng `synthesizeToFile`; mốc từng chữ từ `onRangeStart(.., frame)` (số khung âm thanh ÷ tần số lấy mẫu). Bộ đọc không báo khung (Samsung, vài
 * bộ cũ) thì không có mốc và [WordTokens.map] chia đều theo độ dài chữ. Mọi chờ đều có hạn.
 */
class DeviceTts(private val context: Context, private val voiceName: String) : Voice {
    override val id = "device:$voiceName"
    override val extension = "wav"

    private class Range(val start: Int, val end: Int, val frame: Long)

    override fun synthesize(text: String, out: File): Clip {
        val tts = DeviceEngine.open(context)
        synchronized(DeviceEngine) {
            DeviceEngine.select(tts, voiceName)
            val limit = (TextToSpeech.getMaxSpeechInputLength() - 100).coerceIn(500, 3900)
            val chunks = TextChunks.split(text, limit)
            if (chunks.isEmpty()) throw VoiceException("Đoạn trống")
            val files = ArrayList<File>()
            val boundaries = ArrayList<Boundary>()
            var elapsed = 0L
            try {
                for ((offset, chunk) in chunks) {
                    val part = File(out.parentFile, out.name + ".${files.size}")
                    files.add(part)
                    val ranges = ArrayList<Range>()
                    val rate = speak(tts, chunk, part, ranges)
                    val format = Wav.format(part) ?: throw VoiceException("Giọng của máy ghi file âm thanh lạ")
                    val sampleRate = if (rate > 0) rate else format.sampleRate
                    // Khung phải tăng dần và có ít nhất một khung > 0 thì mới tin; không thì bỏ, chia đều.
                    val usable = ranges.size > 1 && ranges.zipWithNext().all { (a, b) -> b.frame >= a.frame } && ranges.any { it.frame > 0 }
                    if (usable) ranges.forEachIndexed { index, range ->
                        val start = elapsed + range.frame * 1000 / sampleRate
                        // Giọng của máy chỉ báo lúc BẮT ĐẦU: chữ kết thúc ở chỗ chữ sau bắt đầu (chữ cuối: hết mảnh).
                        val end = ranges.getOrNull(index + 1)?.let { next -> elapsed + next.frame * 1000 / sampleRate } ?: (elapsed + format.durationMs(part.length()))
                        val from = range.start.coerceIn(0, chunk.length)
                        boundaries.add(Boundary(start, end, chunk.substring(from, range.end.coerceIn(from, chunk.length)), text.codePointCount(0, offset + from)))
                    }
                    elapsed += format.durationMs(part.length())
                }
                if (files.size == 1) {
                    if (!files[0].renameTo(out)) {
                        files[0].copyTo(out, overwrite = true)
                        files[0].delete()
                    }
                } else {
                    Wav.concat(files, out)
                }
            } finally {
                files.forEach { it.delete() }
            }
            val duration = (Wav.format(out) ?: throw VoiceException("Giọng của máy ghi file âm thanh lạ")).durationMs(out.length())
            return Clip(out, duration, WordTokens.map(text, boundaries, duration), id)
        }
    }

    /** Đọc một mảnh ra `file`; trả tần số lấy mẫu nếu bộ đọc báo (0 nếu không). */
    private fun speak(tts: TextToSpeech, chunk: String, file: File, ranges: MutableList<Range>): Int {
        val done = CountDownLatch(1)
        val failure = java.util.concurrent.atomic.AtomicReference<String?>()
        var sampleRate = 0
        val utterance = "ra-" + System.nanoTime()
        tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) = Unit
            override fun onDone(utteranceId: String?) { if (utteranceId == utterance) done.countDown() }
            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) { if (utteranceId == utterance) { failure.set("Giọng của máy báo lỗi"); done.countDown() } }
            override fun onError(utteranceId: String?, errorCode: Int) { if (utteranceId == utterance) { failure.set("Giọng của máy báo lỗi ($errorCode)"); done.countDown() } }
            override fun onBeginSynthesis(utteranceId: String?, sampleRateInHz: Int, audioFormat: Int, channelCount: Int) { if (utteranceId == utterance) sampleRate = sampleRateInHz }
            override fun onRangeStart(utteranceId: String?, start: Int, end: Int, frame: Int) { if (utteranceId == utterance) ranges.add(Range(start, end, frame.toLong())) }
        })
        file.delete()
        if (tts.synthesizeToFile(chunk, Bundle(), file, utterance) != TextToSpeech.SUCCESS) throw VoiceException("Giọng của máy không nhận được đoạn này")
        if (!done.await(SYNTH_TIMEOUT_MS, TimeUnit.MILLISECONDS)) {
            tts.stop()
            throw VoiceException("Giọng của máy đọc quá chậm")
        }
        failure.get()?.let { throw VoiceException(it) }
        if (!file.isFile || file.length() < 44) throw VoiceException("Giọng của máy không ghi ra âm thanh")
        return sampleRate
    }

    companion object {
        const val SYNTH_TIMEOUT_MS = 40_000L

        /** Các giọng tiếng Việt của máy (rỗng nếu máy chưa có bộ đọc hay giọng nào). */
        fun voices(context: Context): List<VoiceInfo> = runCatching {
            val tts = DeviceEngine.open(context)
            val list = DeviceEngine.vietnamese(tts)
            list.mapIndexed { index, voice ->
                VoiceInfo("device:${voice.name}", voice.name, "device", voice.isNetworkConnectionRequired, index == 0)
            }
        }.getOrDefault(emptyList())

        /** Giọng mặc định của máy (id), hoặc null nếu không có giọng tiếng Việt. */
        fun defaultId(context: Context): String? = voices(context).firstOrNull()?.id
    }
}

/** Bộ `TextToSpeech` dùng chung của app: tạo một lần (cần luồng chính), mọi luồng nền chờ có hạn. */
internal object DeviceEngine {
    private const val INIT_TIMEOUT_MS = 10_000L
    private var tts: TextToSpeech? = null

    @Synchronized
    fun open(context: Context): TextToSpeech {
        tts?.let { return it }
        val ready = CountDownLatch(1)
        var status = TextToSpeech.ERROR
        var created: TextToSpeech? = null
        Handler(Looper.getMainLooper()).post {
            created = TextToSpeech(context.applicationContext) { code ->
                status = code
                ready.countDown()
            }
        }
        if (!ready.await(INIT_TIMEOUT_MS, TimeUnit.MILLISECONDS) || status != TextToSpeech.SUCCESS) {
            created?.shutdown()
            throw VoiceException("Máy chưa có bộ đọc giọng nói - cài trong Cài đặt > Chuyển văn bản thành giọng nói")
        }
        return created!!.also { tts = it }
    }

    fun vietnamese(engine: TextToSpeech): List<android.speech.tts.Voice> =
        engine.voices.orEmpty().filter { it.locale.language == "vi" && !it.features.orEmpty().contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED) }
            .sortedWith(compareBy({ it.isNetworkConnectionRequired }, { -it.quality }, { it.name }))

    /** Chọn giọng theo tên (không có thì giọng tiếng Việt đầu tiên; máy không có thì nói thẳng). */
    fun select(engine: TextToSpeech, name: String) {
        val voices = vietnamese(engine)
        val chosen = voices.firstOrNull { it.name == name } ?: voices.firstOrNull()
        if (chosen != null) {
            engine.voice = chosen
            return
        }
        val result = engine.setLanguage(Locale.forLanguageTag("vi-VN"))
        if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
            throw VoiceException("Máy chưa có giọng tiếng Việt - cài trong Cài đặt > Chuyển văn bản thành giọng nói")
        }
    }
}
