package vn.abook.player

import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.PI
import kotlin.math.log10
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Bộ mã hoá AAC CỦA CHÍNH MÁY (K2_SPEC mục 4 bậc 3): không Activity, không giao diện - chỉ MediaCodec. Đo, ghi ra logcat (thẻ
 * `ABOOK_K2`) và `files/k2-aac/result.json` của app để `adb pull`:
 *  - tên codec mà `createEncoderByType` chọn (c2.android.aac hay codec của hãng chip) và độ trễ mã hoá + giải mã (xung);
 *  - mức vọt đỉnh: tín hiệu tổng hợp chuẩn hoá về -1,75 dBTP (trần trước mã hoá của bản xuất kèm nhạc) -> AAC-LC 64k mono -> giải mã ->
 *    [TruePeak]; bao nhiêu ca > -1 dBTP;
 *  - nối theo chương: mã hoá từng mảnh kèm đệm chương kề rồi chỉ giữ khung của mảnh (LLM_Train/music/mixqa/aac_join.py) so với mã hoá
 *    liền - lặng thêm ở chỗ nối và mức lệch.
 * Đối số tuỳ chọn `-e pcm /data/local/tmp/x.pcm -e rate 24000`: thêm một file PCM 16-bit LE mono thật (một chương xuất của máy tính,
 * không đóng vào repo) vào phép đo vọt đỉnh.
 *
 *   ./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=vn.abook.player.AacCodecOnDeviceTest
 */
@RunWith(AndroidJUnit4::class)
class AacCodecOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val params = MusicRender.Params.load(context)
    private val results = JSONArray()

    private class Encoded(val units: List<ByteArray>, val csd: ByteArray, val codec: String)

    private fun log(json: JSONObject) {
        Log.i(TAG, json.toString())
        results.put(json)
    }

    private fun encode(pcm: ShortArray, rate: Int): Encoded {
        val format = MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_AAC, rate, 1).apply {
            setInteger(MediaFormat.KEY_BIT_RATE, 64_000)
            setInteger(MediaFormat.KEY_AAC_PROFILE, MediaCodecInfo.CodecProfileLevel.AACObjectLC)
            setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 1 shl 16)
        }
        val codec = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_AUDIO_AAC) // như M4bAudio
        val name = codec.name
        codec.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
        codec.start()
        val units = ArrayList<ByteArray>()
        var csd = ByteArray(0)
        val info = MediaCodec.BufferInfo()
        var at = 0
        var inputDone = false
        try {
            val deadline = SystemClock.elapsedRealtime() + CODEC_LIMIT_MS
            while (true) {
                check(SystemClock.elapsedRealtime() < deadline) { "codec " + codec.name + " không xong sau " + CODEC_LIMIT_MS + " ms" }
                if (!inputDone) {
                    val slot = codec.dequeueInputBuffer(10_000)
                    if (slot >= 0) {
                        val buffer = codec.getInputBuffer(slot)!!.order(ByteOrder.LITTLE_ENDIAN)
                        val n = minOf(pcm.size - at, buffer.remaining() / 2, 4096)
                        if (n <= 0) {
                            codec.queueInputBuffer(slot, 0, 0, at * 1_000_000L / rate, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            buffer.asShortBuffer().put(pcm, at, n)
                            codec.queueInputBuffer(slot, 0, 2 * n, at * 1_000_000L / rate, 0)
                            at += n
                        }
                    }
                }
                // Xả HẾT khung đang có mỗi vòng (như M4bAudio.drain): 4096 mẫu vào ra 4 khung, xả một khung một vòng thì
                // mỗi vòng chờ 10 ms - chương 13 phút chạy chậm hơn thời gian thực (máy chủ sách 18-10).
                var ended = false
                while (true) {
                    val out = codec.dequeueOutputBuffer(info, if (inputDone) 10_000 else 0)
                    if (out < 0) break
                    val bytes = ByteArray(info.size)
                    codec.getOutputBuffer(out)!!.apply { position(info.offset); get(bytes) }
                    if (info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG != 0) csd = bytes else if (bytes.isNotEmpty()) units.add(bytes)
                    codec.releaseOutputBuffer(out, false)
                    if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) { ended = true; break }
                }
                if (ended) break
            }
        } finally {
            codec.stop()
            codec.release()
        }
        return Encoded(units, csd, name)
    }

    private fun decode(units: List<ByteArray>, csd: ByteArray, rate: Int): ShortArray {
        val format = MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_AAC, rate, 1).apply {
            setByteBuffer("csd-0", ByteBuffer.wrap(csd))
        }
        val codec = MediaCodec.createDecoderByType(MediaFormat.MIMETYPE_AUDIO_AAC)
        codec.configure(format, null, null, 0)
        codec.start()
        var out = ShortArray(units.size * 1024 + 4096) // ArrayList<Short> của chương 13 phút = ~600 MB đối tượng
        var size = 0
        val info = MediaCodec.BufferInfo()
        var next = 0
        var inputDone = false
        try {
            val deadline = SystemClock.elapsedRealtime() + CODEC_LIMIT_MS
            while (true) {
                check(SystemClock.elapsedRealtime() < deadline) { "codec " + codec.name + " không xong sau " + CODEC_LIMIT_MS + " ms" }
                if (!inputDone) {
                    val slot = codec.dequeueInputBuffer(10_000)
                    if (slot >= 0) {
                        if (next == units.size) {
                            codec.queueInputBuffer(slot, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            codec.getInputBuffer(slot)!!.put(units[next])
                            codec.queueInputBuffer(slot, 0, units[next].size, next * 1024L * 1_000_000L / rate, 0)
                            next++
                        }
                    }
                }
                var ended = false
                while (true) {
                    val slot = codec.dequeueOutputBuffer(info, if (inputDone) 10_000 else 0)
                    if (slot < 0) break
                    val shorts = codec.getOutputBuffer(slot)!!.apply { position(info.offset); limit(info.offset + info.size) }
                        .order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
                    if (size + shorts.remaining() > out.size) out = out.copyOf(maxOf(out.size * 2, size + shorts.remaining()))
                    val n = shorts.remaining()
                    shorts.get(out, size, n)
                    size += n
                    codec.releaseOutputBuffer(slot, false)
                    if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) { ended = true; break }
                }
                if (ended) break
            }
        } finally {
            codec.stop()
            codec.release()
        }
        return out.copyOf(size)
    }

    private fun peak(pcm: ShortArray): Double = TruePeak(params, 1).apply { feed(pcm) }.finish().single()

    /** Tín hiệu `seconds` giây đưa về đỉnh thật đúng -1,75 dBTP (như sau bộ chặn của bản xuất). */
    private fun normalized(rate: Int, seconds: Int, shape: (Double) -> Double): ShortArray {
        val raw = DoubleArray(rate * seconds) { shape(it.toDouble() / rate) }
        val first = ShortArray(raw.size) { MusicRender.toInt16(raw[it] * 0.5) }
        val gain = 0.5 * 10.0.pow((CEILING - peak(first)) / 20)
        return ShortArray(raw.size) { MusicRender.toInt16(raw[it] * gain) }
    }

    private fun signals(rate: Int): Map<String, ShortArray> = linkedMapOf(
        // giọng giả: hoạ âm 140 Hz nhấp nhô 4 Hz
        "speechlike" to normalized(rate, 20) { t ->
            (1 + sin(2 * PI * 4 * t)) / 2 * (1..20).sumOf { h -> sin(2 * PI * 140.0 * h * t + h) / h }
        },
        // vuông giới hạn dải (đỉnh nhọn, AAC vọt nhiều)
        "square" to normalized(rate, 20) { t ->
            (1..39 step 2).filter { 220.0 * it < rate / 2.4 }.sumOf { h -> sin(2 * PI * 220.0 * h * t) / h }
        },
        // nhạc giả + giọng giả
        "mix" to normalized(rate, 20) { t ->
            0.6 * (1 + sin(2 * PI * 3 * t)) / 2 * (1..12).sumOf { h -> sin(2 * PI * 180.0 * h * t) / h } +
                0.3 * (sin(2 * PI * 440 * t) + 0.5 * sin(2 * PI * 659.3 * t) + 0.4 * sin(2 * PI * 880 * t + 1))
        },
    )

    private fun delayOf(rate: Int): Int {
        val pulse = ShortArray(rate).also { it[rate / 2] = 16384 }
        val got = encode(pulse, rate).let { decode(it.units, it.csd, rate) }
        var best = 0
        for (i in got.indices) if (kotlin.math.abs(got[i].toInt()) > kotlin.math.abs(got[best].toInt())) best = i
        return best - rate / 2
    }

    @Test
    fun the_devices_aac_encoder_overshoot_delay_and_chapter_joins() {
        // Chạy khi màn tắt (điện thoại để qua đêm): không giữ máy thức thì CPU ngủ giữa chừng - 17-10 treo 18 phút không một dòng log.
        val wake = (context.getSystemService(android.content.Context.POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "abook:aac-test")
        wake.acquire(30 * 60_000L)
        try {
            measure()
        } finally {
            wake.release()
        }
    }

    private fun measure() {
        for (rate in intArrayOf(24000, 48000)) {
            Log.i(TAG, "bắt đầu rate=" + rate)
            val delay = delayOf(rate)
            val sources = signals(rate).toMutableMap()
            val pcmPath = InstrumentationRegistry.getArguments().getString("pcm")
            val pcmRate = InstrumentationRegistry.getArguments().getString("rate")?.toIntOrNull()
            if (pcmPath != null && pcmRate == rate) {
                val bytes = File(pcmPath).readBytes()
                sources["file"] = ShortArray(bytes.size / 2) { ((bytes[2 * it + 1].toInt() shl 8) or (bytes[2 * it].toInt() and 0xff)).toShort() }
            }
            for ((name, pcm) in sources) {
                val t0 = SystemClock.elapsedRealtime()
                val encoded = encode(pcm, rate)
                val encodeMs = SystemClock.elapsedRealtime() - t0
                val out = decode(encoded.units, encoded.csd, rate)
                val before = peak(pcm)
                val after = peak(out)
                log(JSONObject().put("kind", "peak").put("codec", encoded.codec).put("rate", rate).put("signal", name).put("delay", delay)
                    .put("inDbtp", round2(before)).put("outDbtp", round2(after)).put("over", after > -1.0)
                    .put("seconds", round2(pcm.size.toDouble() / rate)).put("encodeMs", encodeMs))
                assertTrue("giải mã ra đủ dài", out.size >= pcm.size)
            }
            join(sources.getValue("speechlike"), rate, delay)
            join(sources.getValue("mix"), rate, delay)
        }
        val dir = File(context.getExternalFilesDir(null), "k2-aac").apply { mkdirs() }
        File(dir, "result.json").writeText(results.toString(1))
    }

    /** Như aac_join.py: 4 chỗ nối giữa tín hiệu, cách "overlap" so với mã hoá liền. */
    private fun join(x: ShortArray, rate: Int, delay: Int) {
        if (delay < 0) return
        val whole = encode(x, rate)
        val ref = decode(whole.units, whole.csd, rate)
        val total = whole.units.size
        val cuts = (1..4).map { x.size * it / 5 }
        val bounds = listOf(0) + cuts.map { Math.round((it + delay) / 1024.0).toInt() } + listOf(total)
        val pre = (delay + 1024 + 1023) / 1024
        val kept = ArrayList<ByteArray>()
        var csd = whole.csd
        for (k in 0 until bounds.size - 1) {
            val f0 = bounds[k]
            val f1 = bounds[k + 1]
            val start = if (k == 0) 0 else 1024 * f0 - 1024 * pre
            val end = minOf(x.size, 1024 * f1 - delay + 2048)
            val piece = encode(x.copyOfRange(start, end), rate)
            csd = piece.csd
            val skip = if (k == 0) 0 else pre
            val take = piece.units.drop(skip).take(f1 - f0)
            if (take.size != f1 - f0) {
                log(JSONObject().put("kind", "join").put("rate", rate).put("error", "mảnh $k thiếu khung: ${take.size}/${f1 - f0}"))
                return
            }
            kept += take
        }
        val y = decode(kept, csd, rate)
        for (f in bounds.subList(1, bounds.size - 1)) {
            val at = 1024 * f
            val lo = maxOf(0, at - 2048)
            val hi = minOf(y.size, ref.size, at + 2048)
            var diff = 0.0
            var energy = 0.0
            var silentRun = 0
            var run = 0
            for (i in lo until hi) {
                val d = (y[i] - ref[i]).toDouble()
                diff += d * d
                energy += ref[i].toDouble() * ref[i]
                run = if (kotlin.math.abs(y[i].toInt()) < 33) run + 1 else 0 // < -60 dBFS
                silentRun = maxOf(silentRun, run)
            }
            log(JSONObject().put("kind", "join").put("codec", whole.codec).put("rate", rate).put("atFrame", f)
                .put("diffDb", round2(10 * log10(maxOf(diff, 1e-9) / maxOf(energy, 1e-9))))
                .put("silenceMs", round2(1000.0 * silentRun / rate)).put("rmsRef", round2(sqrt(energy / (hi - lo)))))
        }
    }

    private fun round2(x: Double) = Math.round(x * 100) / 100.0

    private companion object {
        const val TAG = "ABOOK_K2"
        /** Một lần mã hoá / giải mã vài giây tín hiệu: quá mức này là codec treo - báo lỗi thay vì chờ mãi. */
        const val CODEC_LIMIT_MS = 120_000L
        const val CEILING = -1.75
    }
}
