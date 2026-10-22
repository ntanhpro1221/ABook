package vn.abook.player

import android.content.Context
import android.os.SystemClock
import androidx.annotation.OptIn
import androidx.media3.common.audio.AudioProcessor
import androidx.media3.common.util.UnstableApi
import androidx.media3.common.util.Util
import androidx.media3.exoplayer.audio.TeeAudioProcessor
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Đo đường P3 BÊN TRONG [MusicBed] (SPEC_loop_p3w_bed.md §43): cờ [MusicBed.musicSeamP3] bật, một sách giả có nhạc, đồng hồ giọng giả gọi [MusicBed.sync] mỗi 500 ms, bốn kịch bản
 * (S1 bình thường, S2 nhảy sớm tới chỗ cần Nối khi chưa dựng, S3 dựng không kịp, S4 đổi mốc giữa Nối). Không phát gì khác: nhạc ở âm lượng của MusicBed (levelDb -6),
 * tee PCM nằm TRƯỚC âm lượng nên bộ chấm đọc dòng `vol` để tính mức thật.
 *
 * Tham số (`am instrument -e ...`): `id` (tên bản ghi, mặc định `bed`), `file` / `file2` (mp3 của mốc A / B; S4 cần file2), `audibleStart` / `loopStart` / `loopEnd` (giây của bài A; `audibleEnd` tuỳ chọn;
 * hậu tố `2` cho bài B), `sc` (danh sách kịch bản, mặc định `S1,S2,S3,S4`), `seconds` (không dùng, giữ cho tương thích với MusicLoopSeamTest).
 *
 * Sách giả: ghi `book.json` + file nhạc thẳng vào `Store.bookDir(bookId)` (thư mục sách thật của app, nơi `Store.playableManifest` đọc - đúng đường MusicBed.sync dùng, cùng đường
 * `Streaming.chapterUri` lấy file bài `music/<sha1>.mp3`), thay vì giả `Store`/`MusicBed` - nên mốc, tên bài, `levelDb` và URI đều đi qua mã thật. `book.json` viết lại mỗi kịch bản
 * (S4 đổi độ dài mốc A); `MusicBed.release()` giữa các kịch bản để lần `sync` kế đọc lại sách. Xong thì `Store.deleteBook`.
 *
 * Ra `getExternalFilesDir(null)/loopseam/`: `<id>.txt` (dòng dưới đây), `<id>_<sc>_p<k>.pcm` (PCM đúng byte đưa xuống AudioTrack của trình phát k của kịch bản), `<id>_R.pcm` / `<id>_R2nd.pcm`
 * (hai bài giải mã liền mạch từ đầu như §41). Dòng (giây 6 chữ số, `<ns>` = System.nanoTime):
 * `SEAM ...` / `SEAM2 ...` như MusicLoopSeamTest, `RFMT`, `RFMT2`, `RINFO`, `RINFO2`, `GAIN <g>`,
 * `EV <ns> scenario <Sx>` / `EV <ns> scenario_end` (số trình phát k đánh lại từ 0 mỗi kịch bản), `EV <ns> sync <t> <nhảy 0|1>`,
 * và các sự kiện của MusicBed (xem [SeamEvents]): `open`, `plan`, `attach`, `demote`, `seek`, `pos`, `item`, `audiotrack`, `vol`, mỗi dòng sau `EV <ns> `;
 * cùng `FMT <ns> <k> <seg> <sr> <ch> <enc>` và `PCM <k> <seg> <f0> <n> <off> <ns>` (off = byte trong file `<id>_<sc>_p<k>.pcm`).
 */
@OptIn(UnstableApi::class)
@RunWith(AndroidJUnit4::class)
class MusicBedSeamOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context: Context = instrumentation.targetContext
    private val args = InstrumentationRegistry.getArguments()
    private val lines = mutableListOf<String>()

    private fun number(name: String): Double? = args.getString(name)?.toDoubleOrNull()?.takeIf { it.isFinite() }
    private fun log(line: String) = synchronized(lines) { lines += line }
    private fun sec(v: Double) = String.format(Locale.ROOT, "%.6f", v)
    private fun <T> onMain(block: () -> T): T = SeamTestSupport.onMain(instrumentation, block)

    /** Ống tee PCM của MỘT trình phát (như SeamTee của MusicLoopSeamTest nhưng ghi thẳng ra file của trình phát k, dòng PCM có thêm ns). Chạy ở luồng phát. */
    private inner class PlayerTee(val k: Int, file: File) : TeeAudioProcessor.AudioBufferSink {
        private val out = FileOutputStream(file)
        private var seg = 0
        private var frameSize = 0
        private var frames = 0L
        private var offset = 0L

        @Synchronized override fun flush(sampleRate: Int, channelCount: Int, encoding: Int) {
            seg++
            frames = 0
            frameSize = runCatching { Util.getPcmFrameSize(encoding, channelCount) }.getOrDefault(0)
            log("FMT ${System.nanoTime()} $k $seg $sampleRate $channelCount $encoding")
        }

        @Synchronized override fun handleBuffer(buffer: ByteBuffer) {
            val bytes = buffer.remaining()
            val count = if (frameSize > 0) bytes / frameSize else 0
            val first = frames
            frames += count
            val copy = ByteArray(bytes)
            buffer.duplicate().get(copy)
            out.write(copy)
            log("PCM $k $seg $first $count $offset ${System.nanoTime()}")
            offset += bytes
        }

        @Synchronized fun close() = out.close()
    }

    /** Đồng hồ giọng giả: `t` = mốc + thời gian thật đã trôi; gọi MusicBed.sync mỗi 500 ms (SYNC_TICK_SECONDS), mỗi lần ghi `EV <ns> sync <t> <nhảy>`. */
    private inner class Voice(private val book: String) {
        private var base = 0.0
        private var startNs = System.nanoTime()
        private var jump = false
        private var nextTick = 0L

        private fun sync() {
            val t = base + (System.nanoTime() - startNs) / 1e9
            log("EV ${System.nanoTime()} sync ${sec(t)} ${if (jump) 1 else 0}")
            jump = false
            onMain { MusicBed.sync(book, 0, t, true) }
        }

        /** Đặt t mới rồi đồng bộ ngay; `jumped` = true: cú nhảy (lớn hơn SEEK_JUMP_SECONDS). */
        fun at(t: Double, jumped: Boolean) {
            base = t.coerceAtLeast(0.0)
            startNs = System.nanoTime()
            jump = jumped
            sync()
            nextTick = SystemClock.elapsedRealtime() + 500
        }

        /** Trôi `seconds` giây thật (tới sớm hơn nếu `until`), đồng bộ mỗi 500 ms. */
        fun drift(seconds: Double, until: () -> Boolean = { false }) {
            val end = SystemClock.elapsedRealtime() + (seconds * 1000).toLong()
            while (!until()) {
                val now = SystemClock.elapsedRealtime()
                if (now >= end) return
                val wake = minOf(nextTick, end)
                if (wake > now) Thread.sleep(wake - now)
                if (SystemClock.elapsedRealtime() >= nextTick) {
                    sync()
                    nextTick += 500
                }
            }
        }
    }

    private fun trackName(c: Char) = "music/${c.toString().repeat(39)}1.mp3"

    private fun cueJson(start: Double, end: Double, track: String, a: Double, ls: Double, le: Double, ae: Double?) =
        JSONObject().put("start", start).put("end", end).put("track", track).put("audibleStart", a).put("loopStart", ls).put("loopEnd", le).also { if (ae != null) it.put("audibleEnd", ae) }

    @Test
    fun seamInsideMusicBed() {
        val dir = File(context.getExternalFilesDir(null), "loopseam").apply { mkdirs() }
        val id = args.getString("id") ?: "bed"
        val file = File(args.getString("file") ?: File(dir, "track.mp3").path)
        assertTrue("không có file nhạc ${file.path}", file.isFile)
        val file2 = args.getString("file2")?.let(::File)?.takeIf { it.isFile }
        val scenarios = (args.getString("sc") ?: "S1,S2,S3,S4").split(',').map { it.trim() }.filter { it.isNotEmpty() }
        val aStart = number("audibleStart") ?: 0.0
        val aLoopStart = number("loopStart") ?: error("thiếu loopStart")
        val aLoopEnd = number("loopEnd") ?: error("thiếu loopEnd")
        val aAudibleEnd = number("audibleEnd")
        val bStart = number("audibleStart2") ?: 0.0
        val bLoopStart = number("loopStart2")
        val bLoopEnd = number("loopEnd2")
        val bAudibleEnd = number("audibleEnd2")
        val hasB = file2 != null && bLoopStart != null && bLoopEnd != null

        val oldSeam = MusicBed.musicSeamP3
        val bookId = "p3bed_" + id.filter { it.isLetterOrDigit() || it == '_' || it == '-' }
        val trackA = trackName('a')
        val trackB = trackName('b')
        val tees = mutableListOf<PlayerTee>()
        val attached = AtomicBoolean(false)
        try {
            onMain {
                Store.init(context)
                MusicBed.init(context) // nạp hằng số trộn (MusicCues.mix), tuỳ chọn đã nhớ
                MusicBed.rememberSeamP3(true)
            }
            val x = MusicCues.mix.loopCrossfadeSeconds
            val level = -6.0
            val gain = Math.pow(10.0, level / 20.0)
            log("GAIN ${sec(gain)}")

            // Sách giả trong thư mục sách thật của app
            val bookDir = Store.bookDir(bookId)
            File(bookDir, "music").mkdirs()
            file.copyTo(File(bookDir, trackA), overwrite = true)
            if (hasB) file2!!.copyTo(File(bookDir, trackB), overwrite = true)

            // Hình học của Nối bài A đúng như MusicBed.planSeam tính (cùng vòng, cùng X)
            val durationA = checkNotNull(MusicBed.trackSeconds(file)) { "không đọc được độ dài ${file.name}" }
            val cueProbe = MusicCues.Cue(0.0, 1e6, trackA, null, audibleStart = aStart, audibleEnd = aAudibleEnd, loopStart = aLoopStart, loopEnd = aLoopEnd)
            val loopA = MusicCues.loopBounds(cueProbe, durationA)
            check(loopA.crossfade) { "bài A không lặp mờ chéo với các mốc đã cho" }
            val seam = LoopSeam.plan(context, file, LoopSeam.Bounds(loopA.start, loopA.loopStart, loopA.loopEnd), x)
            log("SEAM ${seam.buildMs} ${seam.sampleRate} ${seam.channels} ${sec(seam.audibleStart)} ${sec(seam.loopStart)} ${sec(seam.loopEnd)} ${seam.xFrames}")
            val sr = seam.sampleRate.toDouble()
            val clip0 = (seam.loopEndSamples - seam.xFrames - seam.audibleStartSamples) / sr // giây từ đầu mốc tới đầu Nối đầu
            val seamSec = seam.xFrames / sr
            val period = (seam.loopEndSamples - seam.loopStartSamples - seam.xFrames) / sr // chu kỳ P' của vòng
            val cacheDir = File(context.cacheDir, "loopseam")
            fun clearCache() = cacheDir.listFiles()?.forEach { it.delete() }

            // Hai bài giải mã liền mạch (R / R2nd) như bước 2 §41
            val full = SeamTestSupport.decodeToFile(file, File(dir, "${id}_R.pcm"))
            log("RFMT ${full.sampleRate} ${full.channels}")
            log("RINFO samples=${full.samples} firstPtsUs=${full.firstPtsUs} maxSkewSamples=${full.maxSkewSamples}")
            if (hasB) {
                val second = SeamTestSupport.decodeToFile(file2!!, File(dir, "${id}_R2nd.pcm"))
                log("RFMT2 ${second.sampleRate} ${second.channels}")
                log("RINFO2 samples=${second.samples} firstPtsUs=${second.firstPtsUs} maxSkewSamples=${second.maxSkewSamples}")
                val durationB = checkNotNull(MusicBed.trackSeconds(file2))
                val cueB = MusicCues.Cue(0.0, 1e6, trackB, null, audibleStart = bStart, audibleEnd = bAudibleEnd, loopStart = bLoopStart, loopEnd = bLoopEnd)
                val loopB = MusicCues.loopBounds(cueB, durationB)
                if (loopB.crossfade) {
                    val seam2 = LoopSeam.plan(context, file2, LoopSeam.Bounds(loopB.start, loopB.loopStart, loopB.loopEnd), x)
                    log("SEAM2 ${seam2.buildMs} ${seam2.sampleRate} ${seam2.channels} ${sec(seam2.audibleStart)} ${sec(seam2.loopStart)} ${sec(seam2.loopEnd)} ${seam2.xFrames}")
                }
            }

            MusicBed.testEvents = { line ->
                if (line.startsWith("attach ")) attached.set(true)
                log("EV ${System.nanoTime()} $line")
            }

            for (sc in scenarios) {
                // 1. Sách của kịch bản: mốc A đủ cho 3 vòng (S4: ranh B nằm 1 s sau chỗ nhảy, giữa Nối đầu), mốc B ngay sau
                val tMid = clip0 + seamSec / 2
                val endA = if (sc == "S4") tMid + 1.0 else clip0 + 3 * period + seamSec + 5.0
                if (sc == "S4" && !hasB) {
                    log("SKIP S4 cần file2 + loopStart2 + loopEnd2")
                    continue
                }
                val cues = JSONArray().put(cueJson(0.0, endA, trackA, aStart, aLoopStart, aLoopEnd, aAudibleEnd))
                val tracks = JSONObject().put(trackA, JSONObject())
                if (hasB) {
                    cues.put(cueJson(endA, endA + 600.0, trackB, bStart, bLoopStart!!, bLoopEnd!!, bAudibleEnd))
                    tracks.put(trackB, JSONObject())
                }
                val music = JSONObject().put("levelDb", level).put("tracks", tracks).put("chapters", JSONObject().put("0", cues))
                val manifest = JSONObject().put("format", "abook").put("version", 1).put("title", "P3 bed test")
                    .put("chapters", JSONArray().put(JSONObject().put("id", 0).put("title", "c0").put("file", "c0.mp3"))).put("music", music)
                File(bookDir, "book.json").writeBytes(manifest.toString().toByteArray(Charsets.UTF_8))

                // 2. Bộ nhớ đệm Nối: xoá trước S1, S2, S3; giữ cho S4 (có sẵn từ S1, chưa có thì dựng một lần ngoài kịch bản)
                MusicBed.awaitIdle(60_000) // việc dựng chậm của kịch bản trước phải xong, không thì nó ghi WAV vào cache của kịch bản này
                if (sc == "S4") {
                    val built = LoopSeam.build(context, file, LoopSeam.Bounds(loopA.start, loopA.loopStart, loopA.loopEnd), x)
                    log("SEAMSRC ${if (built.cached) "cache" else "built"} ${built.buildMs}")
                } else {
                    clearCache()
                }
                MusicBed.testRenderDelayMs = when (sc) {
                    "S2" -> 4000L
                    "S3" -> (clip0 * 1000).toLong() + 5000L
                    else -> 0L
                }
                MusicBed.testPlayerSeq = 0
                attached.set(false)
                MusicBed.testAudioProcessor = {
                    val k = MusicBed.testCreating
                    val tee = PlayerTee(k, File(dir, "${id}_${sc}_p$k.pcm"))
                    tees += tee
                    TeeAudioProcessor(tee) as AudioProcessor
                }

                // 3. Kịch bản
                log("EV ${System.nanoTime()} scenario $sc")
                val voice = Voice(bookId)
                try {
                    when (sc) {
                        "S1" -> {
                            voice.at(0.0, false)
                            voice.drift(3.0)
                            voice.drift(10.0) { attached.get() } // chờ `attach` (tối đa 10 s, trôi tiếp)
                            if (!attached.get()) log("NOATTACH S1")
                            voice.at(clip0 - 3, true)
                            voice.drift(6.0) // qua Nối đầu vào Clip lặp
                            voice.at(clip0 - 3 + period, true)
                            voice.drift(6.0) // qua Nối lần hai
                        }
                        "S2" -> {
                            // SPEC nói "nhảy như S1" (3 s trước Nối) nhưng chỗ ấy vẫn nằm trong Clip đầu (không cần Nối, chỉ rơi về `late`): để thấy `demote seek` nhảy vào GIỮA Nối đầu.
                            voice.at(0.0, false)
                            voice.drift(0.5)
                            voice.at(tMid, true)
                            voice.drift(6.0)
                        }
                        "S3" -> {
                            voice.at(clip0 - 8, false)
                            voice.drift(10.0)
                        }
                        "S4" -> {
                            voice.at(tMid, false) // giữa Nối đầu; ranh B ở endA = tMid + 1 s
                            voice.drift(5.0) // tới quá ranh B 4 s
                        }
                        else -> log("SKIP $sc kịch bản lạ")
                    }
                } finally {
                    log("EV ${System.nanoTime()} scenario_end")
                    onMain {
                        MusicBed.stop()
                        MusicBed.release() // lần sync kế (kịch bản sau) đọc lại sách
                    }
                    MusicBed.testAudioProcessor = null
                    Thread.sleep(300) // trình phát vừa nhả: tee ngừng ghi
                    tees.forEach { runCatching { it.close() } }
                    tees.clear()
                }
            }
        } finally {
            MusicBed.testAudioProcessor = null
            MusicBed.testEvents = null
            MusicBed.testRenderDelayMs = 0L
            onMain {
                MusicBed.stop()
                MusicBed.release()
                MusicBed.rememberSeamP3(oldSeam)
            }
            runCatching { Store.deleteBook(bookId) }
            val text = synchronized(lines) { lines.joinToString("\n") + "\n" }
            File(dir, "$id.txt").writeBytes(text.toByteArray(Charsets.UTF_8))
        }
    }
}
