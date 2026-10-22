package vn.abook.player

import android.content.Context
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
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.audio.AudioSink
import androidx.media3.exoplayer.audio.DefaultAudioSink
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
 * Phép thử khả thi P3 (PLAN_loop §41, SPEC_loop_p3.md; Corpus/research/music/loopseam41.py gọi): [LoopSeam] dựng Nối, MỘT ExoPlayer phát
 * [Clip, Nối, Clip, Nối, ...] và tee PCM ghi lại đúng byte đưa xuống AudioTrack. Tham số (`am instrument -e ...`): `id`, `file`, `file2` (bài kế cho R5),
 * `audibleStart` / `loopStart` / `loopEnd` (giây; `...2` cho file2), `seconds` (không dùng), `x` (giây mờ chéo, mặc định `MusicCues.mix.loopCrossfadeSeconds`),
 * `preroll` (số khung mở sớm của Clip lặp, mặc định 3; 0 = bản gốc không chữa), `runs` (mặc định `R1,R2,R3,R4,R5`).
 *
 * Ra `getExternalFilesDir(null)/loopseam/`: `<id>.txt` (SEAM, RFMT, RFMT2, RINFO, EV, FMT, PCM), `<id>_R.pcm` (bài giải mã liền từ đầu), `<id>_R2nd.pcm` (bài kế),
 * `<id>_seam.wav` (Nối của máy), `<id>_R1.pcm` ... `<id>_R5.pcm` (mỗi lượt một file tee). Dòng (giây 6 chữ số, `<ns>` là System.nanoTime):
 * `SEAM <buildMs> <sr> <ch> <audibleStart'> <loopStart'> <loopEnd'> <xFrames>`, `RFMT <sr> <ch>`, `EV <ns> seek <Rk> <mụcIndex> <msTrongMục> <loại>` (ms với Clip lặp tính từ mẫu đầu danh nghĩa, trừ phần mở sớm; loại = clip0 | seam | clip; ghi TRƯỚC seekTo, tee đổi file ngay lúc đó),
 * `EV <ns> item <index> <lý do> <loại>`, `EV <ns> switch` (R5, ghi trước setMediaItems), `FMT <ns> 0 <seg> <sr> <ch> <enc>`, `PCM 0 <seg> <f0> <n> <off>` (k = 0: một trình phát; seg đếm
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

        override fun flush(sampleRate: Int, channelCount: Int, encoding: Int) {
            seg++
            frames = 0
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
            armed = true
        }

        fun end(): ByteArray = synchronized(pcm) {
            armed = false
            pcm.toByteArray()
        }
    }

    private fun <T> onMain(block: () -> T): T {
        var result: Any? = null
        var error: Throwable? = null
        instrumentation.runOnMainSync {
            try {
                result = block()
            } catch (t: Throwable) {
                error = t
            }
        }
        error?.let { throw it }
        @Suppress("UNCHECKED_CAST")
        return result as T
    }

    /** Giải mã liền cả file ra PCM16 thô; trả định dạng. */
    private fun decodeToFile(file: File, out: File): LoopSeam.Decoded {
        FileOutputStream(out).use { stream ->
            var scratch = ByteArray(1 shl 16)
            return LoopSeam.decode(file) { _, pcm ->
                if (scratch.size < pcm.remaining()) scratch = ByteArray(pcm.remaining())
                val n = pcm.remaining()
                pcm.get(scratch, 0, n)
                stream.write(scratch, 0, n)
            }
        }
    }

    @Test
    fun seamOnOnePlayer() {
        val dir = File(context.getExternalFilesDir(null), "loopseam").apply { mkdirs() }
        val id = args.getString("id") ?: "manual"
        val file = File(args.getString("file") ?: File(dir, "track.mp3").path)
        assertTrue("không có file nhạc ${file.path}", file.isFile)
        val file2 = args.getString("file2")?.let(::File)
        val runs = (args.getString("runs") ?: "R1,R2,R3,R4,R5").split(',').map { it.trim() }.filter { it.isNotEmpty() }
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
            // 1. Nối
            val seam = LoopSeam.build(context, file, bounds, x, preroll)
            log("SEAM ${seam.buildMs} ${seam.sampleRate} ${seam.channels} ${sec(seam.audibleStart)} ${sec(seam.loopStart)} ${sec(seam.loopEnd)} ${seam.xFrames}")
            val seam2 = if (file2 != null && "R5" in runs) {
                val b2 = LoopSeam.Bounds(number("audibleStart2") ?: 0.0, number("loopStart2") ?: error("thiếu loopStart2"), number("loopEnd2") ?: error("thiếu loopEnd2"))
                LoopSeam.build(context, file2, b2, x, preroll).also {
                    log("SEAM2 ${it.buildMs} ${it.sampleRate} ${it.channels} ${sec(it.audibleStart)} ${sec(it.loopStart)} ${sec(it.loopEnd)} ${it.xFrames}")
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

            // 4. MỘT ExoPlayer
            val failure = java.util.concurrent.atomic.AtomicReference<String?>(null)
            onMain {
                val renderers = object : DefaultRenderersFactory(context) {
                    override fun buildAudioSink(context: Context, enableFloatOutput: Boolean, enableAudioTrackPlaybackParams: Boolean): AudioSink =
                        DefaultAudioSink.Builder(context)
                            .setEnableFloatOutput(enableFloatOutput)
                            .setEnableAudioOutputPlaybackParameters(enableAudioTrackPlaybackParams)
                            .setAudioProcessors(arrayOf(TeeAudioProcessor(tee)))
                            .setAudioTrackProvider(object : DefaultAudioSink.AudioTrackProvider {
                                // Mỗi AudioTrack mới của trình phát ghi một dòng EV: bằng chứng AudioTrack có bị dựng lại ở chỗ chuyển mục không (FMT chỉ đếm lần flush bộ xử lý).
                                override fun getAudioTrack(config: AudioSink.AudioTrackConfig, attributes: AudioAttributes, audioSessionId: Int, context: Context?) =
                                    DefaultAudioSink.AudioTrackProvider.DEFAULT.getAudioTrack(config, attributes, audioSessionId, context).also {
                                        log("EV ${System.nanoTime()} audiotrack ${it.sampleRate} ${it.channelCount}")
                                    }

                                override fun getAudioTrackChannelConfig(channelCount: Int) = DefaultAudioSink.AudioTrackProvider.DEFAULT.getAudioTrackChannelConfig(channelCount)
                            })
                            .build()
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
                player!!.playWhenReady = false
                player!!.setMediaItems(LoopSeam.mediaItems(seam))
                player!!.prepare()
            }
            var listener = onMain { LoopSeam.attach(player!!, seam) }
            val p = player!!

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

            /** Một lượt: ghi EV seek, tee đổi file, tua rồi chạy tới `done`; xong thì dừng, lưu file tee. */
            fun lap(k: Int, index: Int, ms: Long, afterSwitch: (() -> Unit)? = null, done: (Int, Long) -> Boolean) {
                // Clip lặp mở sớm: bộ đo tính vị trí từ mẫu đầu danh nghĩa (sau khi cắt preroll), cửa sổ ExoPlayer thì từ chỗ mở sớm.
                val shown = if (index >= 2 && index % 2 == 0) ms - seam.loopClipLeadMs else ms.toDouble()
                log("EV ${System.nanoTime()} seek R$k $index ${"%.3f".format(java.util.Locale.ROOT, shown)} ${kindOf(index)}")
                tee.begin()
                onMain {
                    p.seekTo(index, ms)
                    p.playWhenReady = true
                }
                try {
                    afterSwitch?.invoke()
                    waitUntil("R$k", done = done)
                } finally {
                    onMain { p.playWhenReady = false }
                    Thread.sleep(300)
                    File(dir, "${id}_R$k.pcm").writeBytes(tee.end())
                }
            }

            val before = 4000L // chạy tới 4 s trước chỗ nối
            val after = 4600L // và 4 s sau (cộng 0,6 s đệm; mốc đo bỏ 0,5 s đầu sau tua)
            if ("R1" in runs) lap(1, 0, (seam.clip0Ms - before).coerceAtLeast(0)) { i, pos -> i == 2 && pos >= after }
            if ("R2" in runs) lap(2, 2, (seam.loopClipMs - before).coerceAtLeast(0)) { i, pos -> i == 4 && pos >= after }
            if ("R3" in runs) lap(3, 4, (seam.loopClipMs - before).coerceAtLeast(0)) { i, pos -> i == 6 && pos >= after }
            if ("R4" in runs) lap(4, 3, seam.seamMs / 2) { i, pos -> i == 4 && pos >= after }
            if ("R5" in runs) {
                checkNotNull(seam2) { "R5 cần file2 và loopStart2 / loopEnd2" }
                var switched = false
                // Vào gần cuối Clip đầu, đợi tới GIỮA Nối đầu (mục 1), đổi bài rồi chạy 3 s (+0,6 s đệm).
                lap(5, 0, (seam.clip0Ms - 1000).coerceAtLeast(0), afterSwitch = {
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
