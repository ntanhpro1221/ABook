package vn.abook.player

import android.content.Context
import android.media.AudioTimestamp
import android.media.AudioTrack
import android.os.SystemClock
import androidx.annotation.OptIn
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.common.util.Util
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.DecoderReuseEvaluation
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.analytics.AnalyticsListener
import androidx.media3.exoplayer.audio.AudioSink
import androidx.media3.exoplayer.audio.DefaultAudioSink
import androidx.media3.exoplayer.audio.ForwardingAudioSink
import androidx.media3.exoplayer.audio.TeeAudioProcessor
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.nio.ByteBuffer

/**
 * Phép thử khả thi P3 (PLAN_loop §41 / §42, SPEC_loop_p3.md; Corpus/research/music/loopseam42.py gọi): [LoopSeam] dựng Nối, MỘT ExoPlayer phát
 * [Clip, Nối, Clip, Nối, ...] và tee PCM ghi lại đúng byte đưa xuống AudioTrack. Tua đi qua API công khai [LoopSeam.seekToSample] với mốc cố ý lệch khỏi biên khung
 * (R1 / R2 / R3: cuối Clip - 4000 ms + 13 ms; R4: giữa Nối + 7 ms; R5: cuối Clip đầu - 1000 ms + 17 ms). Tham số (`am instrument -e ...`): `id`, `file`, `file2` (bài kế cho R5),
 * `audibleStart` / `loopStart` / `loopEnd` (giây; `...2` cho file2), `seconds` (không dùng), `x` (giây mờ chéo, mặc định `MusicCues.mix.loopCrossfadeSeconds`),
 * `preroll` (số khung mở sớm của Clip lặp, mặc định 3; 0 = không chữa), `runs` (mặc định `R1,R2,R3,R4,R2F,R5`, chạy theo thứ tự ghi; R2F = tua vào Clip lặp đúng ranh khung đầu >= đích R2, chẩn đoán;
 * Q / QC = chuỗi tua lặp để tự thử, `repeat` = số vòng), `land` = 1 (đo điểm đáp trong máy sau mỗi lượt, dòng LAND), `check` = 1 (so Nối với Nối dựng từ bản giải mã liền, dòng SEAMCHK).
 *
 * Ra `getExternalFilesDir(null)/loopseam/`: `<id>.txt` (SEAM, SEAMSRC, RFMT, RFMT2, RINFO, EV, FMT, PCM), `<id>_R.pcm` (bài giải mã liền từ đầu), `<id>_R2nd.pcm` (bài kế),
 * `<id>_seam.wav` (Nối của máy), `<id>_R1.pcm` ... (mỗi lượt một file tee). Dòng (giây 6 chữ số, `<ns>` là System.nanoTime):
 * `SEAM <buildMs> <sr> <ch> <audibleStart'> <loopStart'> <loopEnd'> <xFrames>`, `SEAMSRC built|cache <ms>`, `RFMT <sr> <ch>`,
 * `EV <ns> seek <Rk> <mụcIndex> <ms> <loại> <expSample>` (ms và expSample = round(ms * sr / 1000) trên TRỤC DANH NGHĨA của mục, không tính phần mở sớm; loại = clip0 | seam | clip; ghi TRƯỚC seekTo, tee đổi file ngay lúc đó),
 * `EV <ns> play <Rk>` (ngay lúc đặt playWhenReady = true của lượt), `EV <ns> ts <framePosition> <tsNanoTime>` (luồng phụ cứ 10 ms gọi AudioTrack.getTimestamp trên AudioTrack MỚI NHẤT; chỉ ghi khi trả true và framePosition đổi),
 * `EV <ns> underrun <count>` (AudioTrack.getUnderrunCount ở đầu mỗi lượt và mỗi khi giá trị đổi), `EV <ns> item <index> <lý do> <loại>` (lý do = số media3, 1 = tự động), `EV <ns> audiotrack <sr> <ch>`, `EV <ns> fmtin <index> <encoderDelay> <encoderPadding>` (thông tin), `EV <ns> switch` (R5, ghi trước setMediaItems),
 * `EV <ns> sinkcfg / sinkflush / sinkbuf` (nhật ký sink, thông tin), `FMT <ns> 0 <seg> <sr> <ch> <enc>`, `PCM 0 <seg> <f0> <n> <off>` (k = 0: một trình phát; seg đếm
 * tăng suốt bài; off = byte trong file tee của lượt chứa seg, lượt = `EV seek` gần nhất trước FMT). Bảng mục: 0 = Clip đầu, lẻ = Nối, chẵn >= 2 = Clip lặp.
 * Luồng nhạc của máy bằng 0 thì chạy im (tee lấy PCM trước AudioTrack): test không đổi âm lượng hay cài đặt nào.
 */
@OptIn(UnstableApi::class)
@Suppress("DEPRECATION") // AudioTrackProvider: như MusicBed.probeRenderers
@RunWith(AndroidJUnit4::class)
class MusicLoopSeamTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context: Context = instrumentation.targetContext
    private val args = InstrumentationRegistry.getArguments()
    private val lines = mutableListOf<String>()
    /** AudioTrack mới nhất mà sink đã tạo (luồng đo `ts` / `underrun` đọc). */
    @Volatile private var newestTrack: AudioTrack? = null

    private fun number(name: String): Double? = args.getString(name)?.toDoubleOrNull()?.takeIf { it.isFinite() }
    private fun log(line: String) = synchronized(lines) { lines += line }
    /** Loại mục theo bảng mục: 0 = Clip đầu, lẻ = Nối, chẵn >= 2 = Clip lặp (bộ đo đọc cột này). */
    private fun kindOf(index: Int) = if (index == 0) "clip0" else if (index % 2 == 1) "seam" else "clip"
    private fun sec(v: Double) = "%.6f".format(java.util.Locale.ROOT, v)

    /** Ống tee PCM (như LoopTee §39 của MusicBed, nhưng đổi file theo lượt): `FMT` mỗi lần sink cấu hình lại, `PCM` cho mỗi khối khi đang trong một lượt. Chạy ở luồng phát. */
    private inner class SeamTee : TeeAudioProcessor.AudioBufferSink {
        @Volatile var armed = false
        @Volatile var seg = 0
        private var frameSize = 0
        private var frames = 0L
        private val pcm = ByteArrayOutputStream()
        /** Mốc từng lần flush trong lượt: (seg, ns, byte trong file tee tại lúc đó). */
        val marks = mutableListOf<Triple<Int, Long, Int>>()

        override fun flush(sampleRate: Int, channelCount: Int, encoding: Int) {
            seg++
            frames = 0
            synchronized(pcm) { if (armed) marks += Triple(seg, System.nanoTime(), pcm.size()) }
            frameSize = runCatching { Util.getPcmFrameSize(encoding, channelCount) }.getOrDefault(0)
            log("FMT ${System.nanoTime()} 0 $seg $sampleRate $channelCount $encoding")
        }

        override fun handleBuffer(buffer: ByteBuffer) {
            val bytes = buffer.remaining()
            val count = if (frameSize > 0) bytes / frameSize else 0
            val first = frames
            frames += count
            if (!armed) return
            val copy = ByteArray(bytes)
            buffer.duplicate().get(copy)
            val offset = synchronized(pcm) { pcm.size().also { pcm.write(copy) } }
            log("PCM 0 $seg $first $count $offset")
        }

        /** Lượt mới: file mới (byte đếm lại từ 0). */
        fun begin() = synchronized(pcm) {
            pcm.reset()
            marks.clear()
            armed = true
        }

        fun end(): ByteArray = synchronized(pcm) {
            armed = false
            pcm.toByteArray()
        }
    }

    /** Sink bọc DefaultAudioSink chỉ để ghi nhật ký: cấu hình (encoderDelay / padding đang áp), flush, và buffer đầu sau mỗi flush (nhãn thời gian + cỡ). Không đổi hành vi. */
    private inner class LogSink(inner: AudioSink) : ForwardingAudioSink(inner) {
        private var first = 0

        override fun configure(config: AudioSink.AudioSinkConfig) {
            val f = config.format
            log("EV ${System.nanoTime()} sinkcfg ${f.sampleMimeType} ${f.sampleRate} ${f.channelCount} ${f.encoderDelay} ${f.encoderPadding}")
            super.configure(config)
        }

        override fun flush() {
            log("EV ${System.nanoTime()} sinkflush")
            first = 0
            super.flush()
        }

        override fun handleBuffer(buffer: ByteBuffer, presentationTimeUs: Long, encodedAccessUnitCount: Int): Boolean {
            if (first < 4) {
                first++
                log("EV ${System.nanoTime()} sinkbuf $presentationTimeUs ${buffer.remaining()}")
            }
            return super.handleBuffer(buffer, presentationTimeUs, encodedAccessUnitCount)
        }
    }

    /** Luồng phụ của một lượt: mỗi 10 ms đọc AudioTrack mới nhất (`ts`, `underrun`). Trả hàm dừng luồng. */
    private fun startTrackPoller(): () -> Unit {
        val stop = java.util.concurrent.atomic.AtomicBoolean(false)
        val thread = Thread {
            var lastTrack: AudioTrack? = null
            var lastFrame = -1L
            var lastUnderrun = -1
            val stamp = AudioTimestamp()
            while (!stop.get()) {
                val track = newestTrack
                if (track != null) {
                    try {
                        if (track !== lastTrack) {
                            lastTrack = track
                            lastFrame = -1L
                            lastUnderrun = -1
                        }
                        val underrun = track.underrunCount
                        if (underrun != lastUnderrun) {
                            lastUnderrun = underrun
                            log("EV ${System.nanoTime()} underrun $underrun")
                        }
                        if (track.getTimestamp(stamp) && stamp.framePosition != lastFrame) {
                            lastFrame = stamp.framePosition
                            log("EV ${System.nanoTime()} ts ${stamp.framePosition} ${stamp.nanoTime}")
                        }
                    } catch (_: IllegalStateException) {
                        // AudioTrack vừa bị nhả giữa hai lần đọc: lần sau đọc cái mới
                    }
                }
                try {
                    Thread.sleep(10)
                } catch (_: InterruptedException) {
                    return@Thread
                }
            }
        }
        thread.isDaemon = true
        thread.start()
        return {
            stop.set(true)
            thread.join(1000)
        }
    }

    private fun shortsOf(bytes: ByteArray, skip: Int) = SeamTestSupport.shortsOf(bytes, skip)

    /** Khung đầu (index p) của `w` (n khung xen kênh) trong `ref` quanh `center` ± `radius` khung, lệch từng mẫu <= 2; -1 nếu không thấy. */
    private fun locate(ref: ShortArray, channels: Int, center: Long, radius: Int, w: ShortArray): Long {
        val n = w.size / channels
        val lo = maxOf(0L, center - radius)
        val hi = minOf((ref.size / channels - n).toLong(), center + radius)
        var p = lo
        while (p <= hi) {
            var k = 0
            val base = (p * channels).toInt()
            while (k < w.size && Math.abs(ref[base + k] - w[k]) <= 2) k++
            if (k == w.size) return p
            p++
        }
        return -1
    }

    private fun <T> onMain(block: () -> T): T = SeamTestSupport.onMain(instrumentation, block)

    private fun decodeToFile(file: File, out: File): LoopSeam.Decoded = SeamTestSupport.decodeToFile(file, out)

    @Test
    fun seamOnOnePlayer() {
        val dir = File(context.getExternalFilesDir(null), "loopseam").apply { mkdirs() }
        val id = args.getString("id") ?: "manual"
        val file = File(args.getString("file") ?: File(dir, "track.mp3").path)
        assertTrue("không có file nhạc ${file.path}", file.isFile)
        val file2 = args.getString("file2")?.let(::File)
        val runs = (args.getString("runs") ?: "R1,R2,R3,R4,R2F,R5").split(',').map { it.trim() }.filter { it.isNotEmpty() }
        val x = number("x") ?: run {
            instrumentation.runOnMainSync { MusicBed.init(context) } // nạp hằng số trộn (MusicCues.mix)
            MusicCues.mix.loopCrossfadeSeconds
        }
        val preroll = number("preroll")?.toInt() ?: LoopSeam.PREROLL_FRAMES // 0 = không chữa khởi động nguội / đệm 0 (bản gốc SPEC)
        val loopEnd = number("loopEnd") ?: error("thiếu loopEnd")
        val bounds = LoopSeam.Bounds(number("audibleStart") ?: 0.0, number("loopStart") ?: error("thiếu loopStart"), loopEnd)

        var player: ExoPlayer? = null
        val tee = SeamTee()
        try {
            // 1. Nối (dựng vùng quanh chỗ lặp, có bộ nhớ đệm)
            val seam = LoopSeam.build(context, file, bounds, x, preroll)
            log("SEAM ${seam.buildMs} ${seam.sampleRate} ${seam.channels} ${sec(seam.audibleStart)} ${sec(seam.loopStart)} ${sec(seam.loopEnd)} ${seam.xFrames}")
            log("SEAMSRC ${if (seam.cached) "cache" else "built"} ${seam.buildMs}")
            val seam2 = if (file2 != null && "R5" in runs) {
                val b2 = LoopSeam.Bounds(number("audibleStart2") ?: 0.0, number("loopStart2") ?: error("thiếu loopStart2"), number("loopEnd2") ?: error("thiếu loopEnd2"))
                LoopSeam.build(context, file2, b2, x, preroll).also {
                    log("SEAM2 ${it.buildMs} ${it.sampleRate} ${it.channels} ${sec(it.audibleStart)} ${sec(it.loopStart)} ${sec(it.loopEnd)} ${it.xFrames}")
                    log("SEAMSRC ${if (it.cached) "cache" else "built"} ${it.buildMs}")
                }
            } else null
            // 2. bài giải mã liền mạch (R) + bài kế (R2nd)
            val full = decodeToFile(file, File(dir, "${id}_R.pcm"))
            log("RFMT ${full.sampleRate} ${full.channels}")
            log("RINFO samples=${full.samples} firstPtsUs=${full.firstPtsUs} maxSkewSamples=${full.maxSkewSamples}")
            if (seam2 != null) {
                val second = decodeToFile(file2!!, File(dir, "${id}_R2nd.pcm"))
                log("RFMT2 ${second.sampleRate} ${second.channels}")
                log("RINFO2 samples=${second.samples} firstPtsUs=${second.firstPtsUs} maxSkewSamples=${second.maxSkewSamples}")
            }
            // 3. Nối của máy
            seam.wav.copyTo(File(dir, "${id}_seam.wav"), overwrite = true)
            val sr = seam.sampleRate
            val ch = seam.channels
            // Bản giải mã liền nạp một lần khi cần (so Nối, định vị điểm đáp): ~80 MB tạm thời.
            val fullRef by lazy { shortsOf(File(dir, "${id}_R.pcm").readBytes(), 0) }
            val wantLand = (args.getString("land") ?: "0") == "1" || "Q" in runs || "QC" in runs
            if ((args.getString("check") ?: "0") == "1") {
                // Nối của máy (giải mã vùng) phải trùng từng byte với Nối dựng từ bản giải mã liền R: cùng công thức trộn, vùng cũ [loopEnd' - X', loopEnd'], vùng mới [loopStart', loopStart' + X'].
                val n = seam.xFrames * ch
                val old = fullRef.copyOfRange(((seam.loopEndSamples - seam.xFrames) * ch).toInt(), ((seam.loopEndSamples - seam.xFrames) * ch).toInt() + n)
                val new = fullRef.copyOfRange((seam.loopStartSamples * ch).toInt(), (seam.loopStartSamples * ch).toInt() + n)
                val expected = LoopSeam.mix(old, new, ch)
                val actual = shortsOf(seam.wav.readBytes(), 44)
                var diff = 0
                var maxDiff = 0
                var firstDiff = -1
                for (i in expected.indices) {
                    val d = Math.abs(expected[i] - actual[i])
                    if (d != 0) {
                        diff++
                        if (firstDiff < 0) firstDiff = i / ch
                        maxDiff = maxOf(maxDiff, d)
                    }
                }
                log("SEAMCHK ${if (diff == 0 && expected.size == actual.size) "equal" else "diff"} samples=${expected.size} differing=$diff maxAbs=$maxDiff firstFrame=$firstDiff")
            }

            // 4. MỘT ExoPlayer
            val failure = java.util.concurrent.atomic.AtomicReference<String?>(null)
            var loopSink: LoopSeam.LoopSink? = null
            onMain {
                val renderers = object : DefaultRenderersFactory(context) {
                    override fun buildAudioSink(context: Context, enableFloatOutput: Boolean, enableAudioTrackPlaybackParams: Boolean): AudioSink {
                        val base = DefaultAudioSink.Builder(context)
                            .setEnableFloatOutput(enableFloatOutput)
                            .setEnableAudioOutputPlaybackParameters(enableAudioTrackPlaybackParams)
                            .setAudioProcessors(arrayOf(TeeAudioProcessor(tee)))
                            .setAudioTrackProvider(object : DefaultAudioSink.AudioTrackProvider {
                                // Mỗi AudioTrack mới của trình phát ghi một dòng EV: bằng chứng AudioTrack có bị dựng lại ở chỗ chuyển mục không (FMT chỉ đếm lần flush bộ xử lý).
                                override fun getAudioTrack(config: AudioSink.AudioTrackConfig, attributes: AudioAttributes, audioSessionId: Int, context: Context?) =
                                    DefaultAudioSink.AudioTrackProvider.DEFAULT.getAudioTrack(config, attributes, audioSessionId, context).also {
                                        newestTrack = it
                                        log("EV ${System.nanoTime()} audiotrack ${it.sampleRate} ${it.channelCount}")
                                    }

                                override fun getAudioTrackChannelConfig(channelCount: Int) = DefaultAudioSink.AudioTrackProvider.DEFAULT.getAudioTrackChannelConfig(channelCount)
                            })
                            .build()
                        return LogSink(LoopSeam.LoopSink(base).also { loopSink = it })
                    }
                }.forceDisableMediaCodecAsynchronousQueueing()
                // Như MusicBed.open: cùng nguồn media (tua đúng khung), không giành audio focus, dynamic scheduling tắt; âm lượng 1, không offload / skip silence / đổi tốc độ.
                player = ExoPlayer.Builder(context, renderers)
                    .setAudioAttributes(AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MUSIC).build(), false)
                    .setMediaSourceFactory(LoopSeam.mediaSourceFactory(Streaming.mediaSourceFactory(context, exactMp3Seek = true)))
                    .experimentalSetDynamicSchedulingEnabled(false)
                    .build()
                player!!.volume = 1f
                player!!.addListener(object : Player.Listener {
                    override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                        val index = player!!.currentMediaItemIndex
                        log("EV ${System.nanoTime()} item $index $reason ${kindOf(index)}")
                    }

                    override fun onPlayerError(error: PlaybackException) {
                        failure.set("${error.errorCodeName}: ${error.message}")
                        log("EV ${System.nanoTime()} error ${failure.get()}")
                    }
                })
                player!!.addAnalyticsListener(object : AnalyticsListener {
                    // Thông tin: encoderDelay / encoderPadding trong Format đưa cho sink (delay là lời nhắn preroll cho LoopSink; sink trong luôn nhận 0).
                    override fun onAudioInputFormatChanged(eventTime: AnalyticsListener.EventTime, format: androidx.media3.common.Format, decoderReuseEvaluation: DecoderReuseEvaluation?) {
                        log("EV ${System.nanoTime()} fmtin ${eventTime.windowIndex} ${format.encoderDelay} ${format.encoderPadding}")
                    }
                })
                player!!.playWhenReady = false
                player!!.setMediaItems(LoopSeam.mediaItems(seam))
                player!!.prepare()
            }
            var listener = onMain { LoopSeam.attach(player!!, seam) }
            val p = player!!
            val sink = checkNotNull(loopSink) { "không dựng được LoopSink" }

            fun state(): Triple<Int, Long, Int> = onMain { Triple(p.currentMediaItemIndex, p.currentPosition, p.playbackState) }
            fun waitUntil(what: String, timeoutMs: Long = 90_000, done: (Int, Long) -> Boolean) {
                val deadline = SystemClock.elapsedRealtime() + timeoutMs
                while (true) {
                    failure.get()?.let { error("$what: lỗi phát $it") }
                    val (index, pos, st) = state()
                    if (done(index, pos)) return
                    check(st != Player.STATE_ENDED) { "$what: hết danh sách ở mục $index" }
                    check(SystemClock.elapsedRealtime() < deadline) { "$what: quá $timeoutMs ms (mục $index, ${pos} ms)" }
                    Thread.sleep(10)
                }
            }
            waitUntil("chuẩn bị") { _, _ -> onMain { p.playbackState == Player.STATE_READY } }

            /** Mẫu đầu của trục danh nghĩa của mục (trên trục giải mã liền R / file Nối): Clip đầu = audibleStart', Clip lặp = loopStart' + X', Nối = 0. */
            fun itemStart(index: Int) = when (kindOf(index)) { "clip0" -> seam.audibleStartSamples; "clip" -> seam.loopStartSamples + seam.xFrames; else -> 0L }

            /** Điểm đáp đo trong máy (chỉ để thử, không thuộc luật): `LAND <nhãn> <loại> <index> <mẫuDanhNghĩa> <khungĐích> <khungĐáp> <lệchMẫu> <lệchMs>`; tiếng sau tua phải bắt đầu đúng khung đích. */
            fun land(label: String, index: Int, sample: Long, seekNs: Long, marks: List<Triple<Int, Long, Int>>, bytes: ByteArray) {
                val kind = kindOf(index)
                val target = itemStart(index) + sample
                val ref = if (kind == "seam") shortsOf(seam.wav.readBytes(), 44) else fullRef
                // Đoạn tee của lượt = đoạn flush cuối cùng trong 300 ms sau lệnh tua (như bộ đo).
                val mark = marks.lastOrNull { it.second in seekNs..(seekNs + 300_000_000L) } ?: marks.firstOrNull { it.second >= seekNs }
                var landed = Long.MIN_VALUE
                if (mark != null) {
                    val data = shortsOf(bytes, mark.third)
                    for (jFrames in intArrayOf(13_230, 17_640, 22_050)) {
                        val from = jFrames * ch
                        if (from + 256 * ch > data.size) break
                        val w = data.copyOfRange(from, from + 256 * ch)
                        if (w.sumOf { Math.abs(it.toInt()) } < 256 * ch * 16) continue // im lặng: không định vị được
                        val hit = locate(ref, ch, target, 60_000, w)
                        if (hit >= 0) { landed = hit - jFrames; break }
                    }
                }
                if (landed == Long.MIN_VALUE) log("LAND $label $kind $index $sample $target nomatch")
                else log("LAND $label $kind $index $sample $target $landed ${landed - target} ${"%.3f".format(java.util.Locale.ROOT, (landed - target) * 1000.0 / sr)}")
            }

            /** Một lượt: ghi EV seek (mẫu kỳ vọng `exp` trên trục danh nghĩa của mục), tee đổi file, tua bằng API công khai của LoopSeam rồi chạy tới `done`; xong thì dừng, lưu file tee. */
            fun lap(label: String, index: Int, ms: Double, exp: Long, saveTee: Boolean = true, afterSwitch: (() -> Unit)? = null, done: (Int, Long) -> Boolean) {
                val seekNs = System.nanoTime()
                log("EV $seekNs seek $label $index ${"%.3f".format(java.util.Locale.ROOT, ms)} ${kindOf(index)} $exp")
                tee.begin()
                val stopPoller = startTrackPoller()
                try {
                    onMain {
                        LoopSeam.seekToSample(p, sink, seam, index, exp)
                        p.playWhenReady = true
                        log("EV ${System.nanoTime()} play $label")
                    }
                    afterSwitch?.invoke()
                    waitUntil(label, done = done)
                } finally {
                    onMain { p.playWhenReady = false }
                    Thread.sleep(300)
                    stopPoller()
                    val marks = synchronized(tee.marks) { tee.marks.toList() }
                    val bytes = tee.end()
                    if (saveTee) File(dir, "${id}_$label.pcm").writeBytes(bytes)
                    if (wantLand && afterSwitch == null) land(label, index, exp, seekNs, marks, bytes)
                }
            }

            fun msToSample(ms: Double) = Math.round(ms * sr / 1000.0)
            val before = 4000L // chạy tới 4 s trước chỗ nối
            val after = 4600L // và 4 s sau (cộng 0,6 s đệm; mốc đo bỏ 0,5 s đầu sau tua)
            // §42.0b: đích tua cố ý lệch khỏi biên khung (MusicBed tua tới vị trí tuỳ ý): +13 ms, +7 ms, +17 ms.
            val loopNominalMs = seam.loopClipMs - seam.loopClipLeadMs // độ dài Clip lặp trên trục danh nghĩa (không tính phần mở sớm)
            val r1Ms = (seam.clip0Ms - before).coerceAtLeast(0) + 13.0
            val r2Ms = (loopNominalMs - before).coerceAtLeast(0.0) + 13.0
            val r2Sample = msToSample(r2Ms)
            for (run in runs) when (run) {
                "R1" -> lap("R1", 0, r1Ms, msToSample(r1Ms)) { i, pos -> i == 2 && pos >= after }
                "R2" -> lap("R2", 2, r2Ms, r2Sample) { i, pos -> i == 4 && pos >= after }
                "R3" -> lap("R3", 4, r2Ms, r2Sample) { i, pos -> i == 6 && pos >= after }
                "R4" -> {
                    val ms = seam.seamMs / 2 + 7.0
                    lap("R4", 3, ms, msToSample(ms)) { i, pos -> i == 4 && pos >= after }
                }
                "R2F" -> {
                    // Chẩn đoán (không tính luật): tua vào Clip lặp đúng ranh khung đầu tiên >= đích R2.
                    val spf = seam.frameSamples.toLong()
                    val start = seam.loopStartSamples + seam.xFrames
                    val boundary = (start + r2Sample + spf - 1) / spf * spf
                    val exp = boundary - start
                    lap("R2F", 2, exp * 1000.0 / sr, exp) { i, pos -> i == 4 && pos >= after }
                }
                "R5" -> {
                    checkNotNull(seam2) { "R5 cần file2 và loopStart2 / loopEnd2" }
                    var switched = false
                    val ms = (seam.clip0Ms - 1000).coerceAtLeast(0) + 17.0
                    // Vào gần cuối Clip đầu (từ mục khác), đợi tới GIỮA Nối đầu (mục 1), đổi bài rồi chạy 3 s (+0,6 s đệm).
                    lap("R5", 0, ms, msToSample(ms), afterSwitch = {
                        waitUntil("R5 tới giữa Nối") { i, pos -> i == 1 && pos >= seam.seamMs / 2 }
                        log("EV ${System.nanoTime()} switch")
                        onMain {
                            p.removeListener(listener)
                            p.setMediaItems(LoopSeam.mediaItems(seam2), 0, 0L)
                            listener = LoopSeam.attach(p, seam2)
                        }
                        switched = true
                    }) { i, pos -> switched && i == 0 && pos >= 3600 }
                }
                "Q", "QC" -> {
                    // Độ chính xác tua (chỉ để tự thử): lặp nhiều cú tua vào Nối / Clip lặp / Clip đầu từ mục khác (và cùng mục), mỗi cú đo ngay trong máy (LAND).
                    val reps = number("repeat")?.toInt() ?: 6
                    var count = 0
                    fun probe(index: Int, ms: Long) {
                        val sample = msToSample(ms.toDouble())
                        val label = "Q${++count}"
                        val t0 = SystemClock.elapsedRealtime()
                        lap(label, index, ms.toDouble(), sample, saveTee = false) { i, _ -> i == index && SystemClock.elapsedRealtime() - t0 >= 800 }
                    }
                    if (run == "QC") for (r in 0 until reps) {
                        // đọc trước mục kế rồi tua vào nó: lặp Nối -> Clip lặp với mốc đổi dần
                        probe(3, (seam.seamMs * (0.1 + 0.02 * (r % 5))).toLong())
                        probe(4, minOf((loopNominalMs * (0.2 + 0.013 * r)).toLong(), loopNominalMs.toLong() - 2500) + r * 3)
                    } else for (r in 0 until reps) {
                        val f1 = 0.05 + 0.4 * ((r * 0.382) % 1.0)
                        val f2 = 0.2 + 0.4 * ((r * 0.618) % 1.0)
                        val inClip = minOf((loopNominalMs * f2).toLong(), loopNominalMs.toLong() - 2500).coerceAtLeast(500)
                        probe(3, (seam.seamMs * f1).toLong()) // Clip -> Nối
                        probe(4, inClip) // Nối -> Clip lặp
                        probe(3, (seam.seamMs * (0.5 - f1 / 2)).toLong()) // Clip -> Nối (lùi)
                        probe(2, inClip + 1234) // Nối -> Clip lặp (mục trước)
                        probe(0, (seam.clip0Ms * 0.5).toLong() + r * 37) // -> Clip đầu
                        probe(1, (seam.seamMs * f1).toLong()) // Clip đầu -> Nối
                        probe(4, inClip + 500) // Nối -> Clip lặp
                        probe(4, inClip + 1001) // cùng mục
                    }
                }
            }
        } finally {
            onMain {
                player?.release()
                player = null
            }
            val text = synchronized(lines) { lines.joinToString("\n") + "\n" }
            File(dir, "$id.txt").writeBytes(text.toByteArray(Charsets.UTF_8))
        }
    }
}
