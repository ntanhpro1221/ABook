package vn.abook.player

import android.content.Context
import android.media.AudioTimestamp
import android.media.AudioTrack
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import androidx.annotation.OptIn
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.common.util.Util
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.audio.AudioSink
import androidx.media3.exoplayer.audio.DefaultAudioSink
import androidx.media3.exoplayer.audio.TeeAudioProcessor
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.abs
import kotlin.math.pow

/**
 * Nhạc nền dưới giọng đọc - bản Android của ui/src/listen/musicBed.ts.
 *
 * Mốc nhạc từng chương nằm ở mục `music` của book.json (file `.abook` hay gói tải qua Wi-Fi - webui/music_plan.package):
 * `{levelDb, tracks: {"music/<sha1>.mp3": {...}}, chapters: {"<id>": [{start, end, track, gainDb, steps?, sibling?}]}}`
 * (`levelDb` = nhạc thấp hơn giọng bao nhiêu LU; `gainDb` tính sẵn cho từng bài ở máy chủ; `steps` / `sibling`: [MusicCues]).
 * File bài lấy cùng đường với
 * audio chương (Streaming.chapterUri): có trên máy thì đọc thẳng, không thì nghe thẳng từ máy tính, qua bộ đệm đĩa.
 *
 * Sách KHÔNG có mục `music` (sách chỉ có chữ nghe bằng "Nghe ngay") mà người nghe đã chọn một danh sách phát (`music.playlist` của
 * lớp sửa - [Playlists]): các bài của danh sách nối nhau theo thứ tự trộn sẵn trên một đồng hồ nhạc RIÊNG của cuốn, chạy khi giọng
 * chạy, không theo giây của chương - sang chương mới nhạc chơi tiếp. Chỗ đang tới trên đồng hồ nhớ theo cuốn + danh sách
 * (SharedPreferences "music_bed"), mở lại sách là nghe tiếp đúng bài. Giọng ngừng giây lát giữa hai đoạn / hai chương thì nhạc
 * không ngắt ([PAUSE_GRACE_MS]).
 *
 * Sách chỉ có chữ chưa chọn gì (mặc định khi "Tự chọn nhạc nền" còn bật) hay đã chọn "Theo cảnh" ([Playlists.sceneMode]) thì nhạc đổi theo CẢNH của truyện, máy tự dựng
 * từ chữ ([DeviceScenes], đường N0, không model): mốc từng chương theo giây ước được đặt lại theo đồng hồ đọc của chương ([SceneAnchor], [SceneBed]) để bài đổi đúng
 * lúc đoạn đầu cảnh bắt đầu phát, rồi chạy qua cùng bộ máy mốc như nhạc của người làm sách (mờ chéo, lặp, bước âm lượng, bài anh em). Bài lấy từ danh mục ([uriOf]):
 * chưa tải thì tải nền, đoạn ấy im tới khi xong. Chương chưa dựng xong thì chưa có nhạc, vào ở đầu câu kế khi xong - giọng không chờ nhạc.
 *
 * Một ExoPlayer riêng cho mỗi bài đang kêu (hai khi đang chuyển mờ), KHÔNG giành audio focus: trình phát giọng
 * đọc giữ focus, nhạc chỉ chạy khi giọng đang chạy (`sync` từ Playback mỗi nhịp 0,5 giây và mỗi lần phát / dừng / tua).
 * Mọi thao tác ở luồng chính, như Playback; danh mục / tải bài ở một luồng nền riêng.
 *
 * Nhạc của sách lặp bằng mờ chéo trong đoạn nghe được (lô 2 mix-loop, [MusicCues.loopBounds]): tới loopEnd - X một ExoPlayer MỚI của
 * chính bài vào từ loopStart (không có điểm vòng: E - X và A), cái cũ mờ đi trong X giây ([enterLoop]); bài quá ngắn và danh sách
 * phát thì vẫn REPEAT_MODE_ONE.
 */
object MusicBed {
    private const val STEP_MS = MusicCues.TICK_MS
    private const val SEEK_JUMP_SECONDS = 3.0
    private const val PAUSE_GRACE_MS = 2500L
    private const val MAX_STEP_SECONDS = 3.0 // đồng hồ nhạc không nhảy xa khi máy ngủ giữa hai nhịp
    private const val SAVE_EVERY_MS = 5000L
    private const val PREFS = "music_bed"
    /** Giọng của người nghe, không phải lỗi: nhạc nền chờ Wi-Fi (không tự tải bài nhạc lớn bằng dữ liệu di động). */
    private const val METERED_NOTICE = "Đang dùng dữ liệu di động nên nhạc nền tự chọn chờ có Wi-Fi mới tải. Muốn nghe ngay, bạn chọn nhạc ở nút Nhạc nền."
    private const val AUTO_KEY = "auto-scene-music"
    private const val SCENE_POLL_MS = 1500L // nhạc theo cảnh dựng nền: chương chưa xong thì hỏi lại mỗi chừng này, tối đa SCENE_POLLS lần (ui/src/listen/player.tsx)
    private const val SCENE_POLLS = 80
    /** Mốc cảnh của chương trả `unavailable` (danh mục chưa tải được) hay hỏi hỏng: hỏi lại sau chừng này, lùi dần, có hạn - như `sceneRetryDelay` của ui/src/listen/sceneCues.ts. */
    private val SCENE_RETRY_MS = longArrayOf(15_000, 30_000, 60_000, 120_000, 300_000)
    private const val METERED_CHECK_MS = 5000L
    private val CREDIT_KEYS = listOf("title", "creator", "attribution", "landing", "license", "licenseUrl")

    /** Một bài đang kêu. `goal` = âm lượng đang hướng tới, `perTick` = mỗi nhịp STEP_MS nhích bao nhiêu; `entering` = đang mờ vào
     *  (tua lúc này không nhảy thẳng tới mức) trong `fadeMs`; `cue` = mốc đang phát (bước âm lượng), null với danh sách phát. */
    private class Bed(val track: String, val player: ExoPlayer, var goal: Float, var perTick: Float, var cue: MusicCues.Cue?, val fadeMs: Long) {
        val listeners = mutableListOf<Player.Listener>() // gỡ trước khi nhả: không còn gì gọi về sau release
        var entering = true
        var fadeStep = 0.001f // âm lượng bớt mỗi nhịp khi mờ đi: bài to và bài nhỏ cùng tắt trong cùng thời gian
        var early = false // vào sớm: bài trước kết tự nhiên trước đầu mốc này; tới `cue.start` giọng vẫn ở mốc cũ - không chuyển ngược
        var final = false // vòng cuối của mốc `tail`: không mở phần tử lặp nữa, bài chơi tới E là hết
        var released = false // đã nhả: lỗi muộn của nó không tính là bài hỏng
        var at = 0.0 // bản lặp tạo sẵn: chỗ (giây trong bài) đã đặt, để biết có cần dời lại khi vào muộn
        var prerolled = false // đo (§40 nhóm E): bản chờ đã `play()` trước hạn ở âm lượng 0 - tới hạn chỉ mờ chéo, không tua, không `play()`
        var handoff: Handoff? = null // bản lặp nối vào bản nào (bước 3 của bản đã chạy trước hạn chạy lúc vào, không lúc `playing`)
        var tee: LoopTee? = null // chỉ khi đang đo ([debugLoopProbe] != null lúc tạo): ống tee PCM của trình phát này
    }

    /** Bản lặp mới và bản cũ nó nối vào: lúc bản mới có tiếng, sửa pha theo bản cũ một lần ([MusicCues.loopSettle]). */
    private class Handoff(val old: Bed, val bounds: MusicCues.Loop)

    /** Vòng lặp của bài `player` theo mốc `cue` (độ dài thật chưa biết: NaN). */
    private fun boundsOf(cue: MusicCues.Cue, player: ExoPlayer): MusicCues.Loop =
        MusicCues.loopBounds(cue, if (player.duration > 0) player.duration / 1000.0 else Double.NaN)

    /** Bài của mốc `cue` lặp thường (REPEAT_MODE_ONE) chỉ khi quá ngắn để mờ chéo; vòng cuối của mốc `tail` thì không lặp. Danh sách
     *  phát (`cue` null) lặp thường như cũ. */
    private fun repeatFor(cue: MusicCues.Cue?, player: ExoPlayer, final: Boolean = false): Int = when {
        cue == null -> Player.REPEAT_MODE_ONE
        final || boundsOf(cue, player).crossfade -> Player.REPEAT_MODE_OFF
        else -> Player.REPEAT_MODE_ONE
    }

    private val main = Handler(Looper.getMainLooper())

    /** Giờ vào bản lặp ([LoopHandoff]): hẹn đúng hạn loopEnd - X, vào muộn thì bù, không chờ nhịp đồng bộ của giọng. */
    private val loopHandoff = LoopHandoff<Bed>(main, ::lookLoop, ::prepareLoop, { release(it) }, ::enterLoop)

    // ---- móc đo của bài thử trên máy (MusicLoopOnDeviceTest, PLAN_loop §36): mặc định null / 0 / null nên bản thường không làm gì, không log, không cấp phát ----
    /** Nhận một dòng đo mỗi sự kiện của bản lặp: `EV <ns> standby|play|playing|drift <giây> applied|skipped|seek <ms>` và `POS <ns> <oldMs> <newMs> <oldVol> <newVol>`
     *  (20 ms một dòng, từ `standby` - hay từ `play` nếu không có bản tạo sẵn - tới 4,5 s sau `playing`; bản đã nhả / chưa có ghi `-`).
     *  Thước PCM (§39): thêm `FMT`, `PCM`, `TS` ([LoopTee], [probeArm]); mọi `<ns>` là System.nanoTime. Gọi từ nhiều luồng (luồng chính + luồng phát của từng trình phát):
     *  bên nhận phải an toàn đa luồng. Gán (kể cả null) là đặt lại toàn bộ trạng thái đo. */
    internal var debugLoopProbe: ((String) -> Unit)? = null
        set(value) {
            debugLoopSilentStop() // ghi `silent stop` vào bên nhận cũ trước khi đổi
            field = value
            probeReset()
        }
    /** Tiền tố đường file của các file PCM tee (`<tiền tố>_p<k>.pcm`, [debugLoopFlush]); null = chỉ đếm khung, không giữ byte. */
    internal var debugLoopPcmBase: File? = null
    /** false: bỏ bước 3 ([MusicCues.loopSettle]) - không tính, không tua; vẫn ghi `drift <giây> skipped` (thước hằng số pha của §38). Bản thường luôn true. */
    internal var debugLoopSettle = true
    /** false: bản chờ / bản lặp KHÔNG gắn [TeeAudioProcessor] (không đếm khung, không giữ PCM); vẫn giữ AudioTrack để có `TS`, và vẫn ghi `FMT` lúc provider tạo AudioTrack (§40). Bản thường luôn true. */
    internal var debugLoopTee = true
    /** Chu kỳ (ms) của dòng `TS` (§40; nhóm C thưa 200). Bản thường luôn 20. */
    internal var debugLoopTsEveryMs = PROBE_EVERY_MS
    /** true: [debugLoopSilentStart] chạy một AudioTrack câm ngoài ExoPlayer suốt bài kiểm, để số track của app luôn >= 2 (§40 nhóm D). Bản thường luôn false. */
    internal var debugLoopSilentTrack = false
    /** > 0 (giây, §40 nhóm E): bản chờ `seekTo(loopStart - preroll)` rồi `play()` ở âm lượng 0 lúc hạn - preroll (`EV preroll`); tới hạn không `play()` nữa, chỉ ghi `EV play` và mờ chéo. Bản thường luôn 0. */
    internal var debugLoopPreroll = 0.0
    /** Giây cộng thêm vào chỗ vào của bản lặp mới (bài kiểm lực của §36: cố ý đẩy lệch pha để bước 3 phải sửa). */
    internal var debugLoopInject = 0.0
    /** Mục `music` và file bài của cuốn giả [DEBUG_BOOK]: bài thử dựng mốc không qua Store (không đụng dữ liệu người dùng). */
    internal var debugMusic: JSONObject? = null
    internal var debugTrack: Uri? = null
    internal const val DEBUG_BOOK = "loopprobe"
    private const val PROBE_AFTER_PLAYING_MS = 4500L
    private const val PROBE_EVERY_MS = 20L

    private inline fun probe(line: () -> String) {
        val sink = debugLoopProbe ?: return
        sink("EV ${System.nanoTime()} ${line()}")
    }

    /** Bản lặp đang được đo (bản mới nhất đã gọi [probeLoopWatch]) và hạn dừng đo (ns, System.nanoTime; chưa `playing` thì vô hạn). */
    private var probeBed: Bed? = null
    private var probeUntil = Long.MAX_VALUE

    /** Mỗi lần gán [debugLoopProbe] tăng một: vòng đo (POS / TS) của lần gán trước tự dừng. */
    private var probeEpoch = 0
    @Volatile private var probeArmed = false // từ `standby` (hay `play` nếu không có bản chờ): tee bắt đầu giữ byte, TS bắt đầu chạy
    private val probeTees = CopyOnWriteArrayList<LoopTee>()
    private val probeNextK = AtomicInteger()

    private fun probeReset() {
        probeEpoch++
        probeArmed = false
        probeBed = null
        probeUntil = Long.MAX_VALUE
        probeTees.clear()
        probeNextK.set(0)
    }

    /** Bản lặp `new` vừa được gọi `play()` (nối vào `old`): ghi sự kiện `play`, rồi (nếu chưa đo từ `standby`) bắt đầu ghi vị trí. */
    private fun probeLoopPlay(old: Bed, new: Bed) {
        probe { "play" }
        probeArm()
        probeLoopWatch(old, new)
        if (new.prerolled) probeUntil = System.nanoTime() + PROBE_AFTER_PLAYING_MS * 1_000_000 // bản chờ đã chạy trước hạn: 4,5 s tính từ hạn (`play`), không từ `playing`
    }

    /** Bắt đầu thước PCM (một lần): các tee giữ byte từ giờ, và cứ 20 ms một dòng `TS <ns_gọi> <k> <seg> <framePosition> <nanoTime>` cho mỗi trình phát còn sống
     *  mà `AudioTrack.getTimestamp` trả true, tới hạn đo ([probeUntil]) hay khi [debugLoopProbe] đổi. */
    private fun probeArm() {
        if (probeArmed) return
        val sink = debugLoopProbe ?: return
        probeArmed = true
        val epoch = probeEpoch
        main.post(object : Runnable {
            private val stamp = AudioTimestamp()
            override fun run() {
                if (epoch != probeEpoch || System.nanoTime() > probeUntil) return
                for (tee in probeTees) {
                    if (!tee.alive) continue
                    val track = tee.track ?: continue
                    val call = System.nanoTime()
                    val ok = try { track.getTimestamp(stamp) } catch (_: Exception) { false } // AudioTrack đã nhả / chưa chạy: không có dấu thời gian
                    if (ok) sink("TS $call ${tee.k} ${tee.seg} ${stamp.framePosition} ${stamp.nanoTime}")
                }
                main.postDelayed(this, debugLoopTsEveryMs)
            }
        })
    }

    /** Một AudioTrack câm ngoài ExoPlayer ([debugLoopSilentTrack], §40): 48 kHz stereo PCM 16, USAGE_MEDIA / CONTENT_TYPE_MUSIC, MODE_STREAM, luồng riêng ghi số 0. */
    private class SilentTrack(val track: AudioTrack) {
        @Volatile var running = true
        val thread = Thread({
            val zeros = ByteArray(4096)
            while (running) {
                val n = try { track.write(zeros, 0, zeros.size, AudioTrack.WRITE_NON_BLOCKING) } catch (_: Exception) { -1 }
                if (n < 0) break
                if (n < zeros.size) Thread.sleep(10) // đầy bộ đệm: chờ nó cạn bớt
            }
        }, "abook-silent-track")
    }
    private var silent: SilentTrack? = null

    /** Bắt đầu track câm (gọi trước khi bài vào, sau khi gán [debugLoopProbe]); không làm gì nếu không đo / không bật / đã chạy. Ghi `EV <ns> silent start`. */
    internal fun debugLoopSilentStart() {
        if (debugLoopProbe == null || !debugLoopSilentTrack || silent != null) return
        val rate = 48_000
        val mask = android.media.AudioFormat.CHANNEL_OUT_STEREO
        val encoding = android.media.AudioFormat.ENCODING_PCM_16BIT
        val size = maxOf(AudioTrack.getMinBufferSize(rate, mask, encoding), rate / 5 * 4)
        val track = AudioTrack.Builder()
            .setAudioAttributes(android.media.AudioAttributes.Builder().setUsage(android.media.AudioAttributes.USAGE_MEDIA).setContentType(android.media.AudioAttributes.CONTENT_TYPE_MUSIC).build())
            .setAudioFormat(android.media.AudioFormat.Builder().setEncoding(encoding).setSampleRate(rate).setChannelMask(mask).build())
            .setBufferSizeInBytes(size)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()
        val one = SilentTrack(track)
        silent = one
        track.play()
        one.thread.start()
        probe { "silent start" }
    }

    /** Dừng + nhả track câm (gọi sau `stop()`; cũng tự gọi khi gán lại [debugLoopProbe]). Ghi `EV <ns> silent stop`. */
    internal fun debugLoopSilentStop() {
        val one = silent ?: return
        silent = null
        one.running = false
        one.thread.join(1000)
        try { one.track.stop() } catch (_: Exception) {}
        one.track.release()
        probe { "silent stop" }
    }

    /** Ghi các file `<debugLoopPcmBase>_p<k>.pcm` (PCM tee của từng trình phát từ lúc ARM; byte nối tiếp nhiều đoạn, `PCM` cho biết byte nào thuộc khung nào).
     *  Gọi sau khi dừng nhạc, trước khi gán lại [debugLoopProbe]. Byte giữ trong bộ nhớ tới đây: luồng phát không phải chờ ghi đĩa. */
    internal fun debugLoopFlush() {
        val base = debugLoopPcmBase ?: return
        if (!debugLoopTee) return // không có tee: không có byte
        for (tee in probeTees) File(base.path + "_p${tee.k}.pcm").writeBytes(tee.bytes())
    }

    /** Ống tee PCM của một ExoPlayer nhạc (§39): `FMT` mỗi lần sink cấu hình lại (một đoạn `seg` mới), `PCM` cho mỗi buffer đưa ra sink khi đã ARM. Chạy ở luồng phát của trình phát. */
    @OptIn(UnstableApi::class)
    private class LoopTee(val k: Int) : TeeAudioProcessor.AudioBufferSink {
        @Volatile var seg = 0
        @Volatile var track: AudioTrack? = null // AudioTrack mới nhất của trình phát này
        @Volatile var alive = true // false khi nhả
        private var frameSize = 0
        private var frames = 0L // số khung đã qua trong đoạn hiện tại
        private val pcm = ByteArrayOutputStream()

        override fun flush(sampleRate: Int, channelCount: Int, encoding: Int) {
            seg++
            frames = 0
            frameSize = runCatching { Util.getPcmFrameSize(encoding, channelCount) }.getOrDefault(0)
            debugLoopProbe?.invoke("FMT ${System.nanoTime()} $k $seg $sampleRate $channelCount $encoding")
        }

        override fun handleBuffer(buffer: ByteBuffer) {
            val bytes = buffer.remaining()
            val count = if (frameSize > 0) bytes / frameSize else 0
            val first = frames
            frames += count
            if (!probeArmed) return
            val copy = ByteArray(bytes)
            buffer.duplicate().get(copy)
            val offset = synchronized(pcm) { pcm.size().also { pcm.write(copy) } }
            debugLoopProbe?.invoke("PCM $k $seg $first $count $offset")
        }

        fun bytes(): ByteArray = synchronized(pcm) { pcm.toByteArray() }
    }

    /** Hãng trình phát nhạc khi đang đo: sink mặc định cộng [TeeAudioProcessor] (đường PCM trước AudioTrack) và giữ AudioTrack để hỏi dấu thời gian. */
    @OptIn(UnstableApi::class)
    @Suppress("DEPRECATION") // AudioTrackProvider: media3 1.11 khuyên AudioOutputProvider, nhưng sink mặc định vẫn dựng AudioTrackAudioOutputProvider từ nó - móc ngắn nhất tới AudioTrack
    private fun probeRenderers(appContext: Context, tee: LoopTee) = object : DefaultRenderersFactory(appContext) {
        override fun buildAudioSink(context: Context, enableFloatOutput: Boolean, enableAudioTrackPlaybackParams: Boolean): AudioSink {
            val base = DefaultAudioSink.AudioTrackProvider.DEFAULT
            val withTee = debugLoopTee
            return DefaultAudioSink.Builder(context)
                .setEnableFloatOutput(enableFloatOutput)
                .setEnableAudioOutputPlaybackParameters(enableAudioTrackPlaybackParams)
                .apply { if (withTee) setAudioProcessors(arrayOf(TeeAudioProcessor(tee))) }
                .setAudioTrackProvider(object : DefaultAudioSink.AudioTrackProvider {
                    override fun getAudioTrack(config: AudioSink.AudioTrackConfig, attributes: androidx.media3.common.AudioAttributes, audioSessionId: Int, context: Context?): AudioTrack =
                        base.getAudioTrack(config, attributes, audioSessionId, context).also {
                            tee.track = it
                            // Không có tee thì không có flush(): đoạn mới = AudioTrack mới, FMT lấy từ chính AudioTrack (§40).
                            if (!withTee) {
                                tee.seg++
                                debugLoopProbe?.invoke("FMT ${System.nanoTime()} ${tee.k} ${tee.seg} ${it.sampleRate} ${it.channelCount} ${it.audioFormat}")
                            }
                        }

                    override fun getAudioTrackChannelConfig(channelCount: Int): Int = base.getAudioTrackChannelConfig(channelCount)
                })
                .build()
        }
    }

    /** Mỗi 20 ms một dòng vị trí + âm lượng hai bản tới 4,5 s sau `playing` của `new` (hay khi `new` đã nhả); một bản đã nhả ghi `-`. Gọi lại với cùng `new` thì bỏ qua. */
    private fun probeLoopWatch(old: Bed, new: Bed) {
        val sink = debugLoopProbe ?: return
        if (probeBed === new) return
        probeBed = new
        probeUntil = Long.MAX_VALUE
        main.post(object : Runnable {
            override fun run() {
                val now = System.nanoTime()
                if (probeBed !== new || debugLoopProbe == null || new.released || now > probeUntil) return
                val oldMs = if (old.released) "-" else old.player.currentPosition.toString()
                val oldVol = if (old.released) "-" else old.player.volume.toString()
                sink("POS $now $oldMs ${new.player.currentPosition} $oldVol ${new.player.volume}")
                main.postDelayed(this, PROBE_EVERY_MS)
            }
        })
    }

    private const val TAG = "ABookMusic"
    /** Một bước tạo / nhả trình phát nhạc lâu hơn ngần này thì ghi logcat (soát a69: giọng đứng 19,2 s đúng lúc lặp mờ chéo tạo trình phát mới - lần soát sau
     *  thấy ngay bước nào chậm). */
    private const val SLOW_STEP_MS = 500L

    private inline fun <T> timed(step: String, block: () -> T): T {
        val began = SystemClock.elapsedRealtime()
        try {
            return block()
        } finally {
            val spent = SystemClock.elapsedRealtime() - began
            if (spent > SLOW_STEP_MS) Log.i(TAG, "$step chậm: $spent ms")
        }
    }

    /** Nhả trình phát của [bed] trên luồng chính (luồng tạo ra nó), gỡ listener trước. */
    private fun release(bed: Bed) = timed("nhả trình phát nhạc") {
        bed.released = true
        bed.tee?.alive = false
        bed.listeners.forEach(bed.player::removeListener)
        bed.listeners.clear()
        bed.player.release()
    }
    private val worker = Executors.newSingleThreadExecutor()
    private var context: Context? = null
    private var book = ""
    private var music: JSONObject? = null
    private var chapter = Int.MIN_VALUE
    private var cues: List<MusicCues.Cue> = emptyList()
    private var gain = 0.1f
    private var playing = false
    private var lastSeconds = 0.0
    private var current: Bed? = null
    private val fading = mutableListOf<Bed>()
    private var fadingTicker = false
    // Bài không phát được -> lúc được thử lại: tải hỏng (mất mạng) thì sau RETRY_MS, file hỏng thì không bao giờ trong phiên.
    private val failed = MusicFailures { SystemClock.elapsedRealtime() }

    // ---- nhạc theo cảnh (sách chỉ có chữ, "Theo cảnh") ----
    private var autoPicked = false // nhạc theo cảnh là do máy tự chọn (người nghe chưa chọn gì): dữ liệu di động chặn tải ([meteredNow])
    private var sceneMode = false // cuốn này theo cảnh: mốc của chương nằm ở `scene`, bài lấy từ danh mục
    private val scene = SceneBed { sceneTiming() }
    private var sceneRetry: Runnable? = null
    private var sceneNotice = "" // lý do chưa có nhạc theo cảnh (danh mục chưa tải được) - lời `unavailable` của DeviceScenes; rỗng khi ổn

    // ---- danh sách phát ("Nghe ngay") ----
    private var playlist: String? = null // danh sách đang dùng cho cuốn này; null = nhạc theo mốc của sách (hay không nhạc)
    private val queue = PlaylistQueue(failed) // hàng bài trên đồng hồ nhạc, trừ bài đang bị bỏ tạm
    private var infos: Map<String, JSONObject> = emptyMap()
    private var clockSeconds = 0.0
    private var clockAt = 0L // SystemClock.elapsedRealtime của lần cộng đồng hồ gần nhất; 0 = đồng hồ đang đứng
    private var savedAt = 0L
    private var generation = 0 // mỗi lần đổi cuốn / đổi lựa chọn: kết quả nạp muộn của lần trước bị bỏ
    private val downloading = mutableSetOf<String>()
    private val grace = Runnable { holdStill() }

    fun init(appContext: Context) {
        context = appContext.applicationContext
        MusicCues.mix = MusicMix.load(appContext)
        // "Tự chọn nhạc nền" do giao diện gửi mỗi lần mở app: tiến trình khởi động lại từ widget / tai nghe / Android Auto (không có WebView) phải theo lựa chọn đã lưu, không về mặc định "bật".
        Playlists.autoEnabled = prefs(appContext).getBoolean(AUTO_KEY, true)
    }

    /** Nhớ lựa chọn "Tự chọn nhạc nền" ([Playlists.autoEnabled]) qua lần khởi động tiến trình. */
    fun rememberAuto(value: Boolean) {
        val appContext = context ?: return
        prefs(appContext).edit().putBoolean(AUTO_KEY, value).apply()
    }

    /** Lớp sửa của cuốn `bookId` vừa đổi (nhạc bật/tắt, mức, im lặng một đoạn, danh sách phát): lần `sync` kế đọc lại. */
    fun invalidate(bookId: String) {
        if (bookId == book) book = ""
    }

    /** Bài đang kêu (tên trong gói, hay link với danh sách phát) hay null khi im lặng - cho kiểm thử trên máy. */
    val activeTrack: String? get() = current?.track

    /** Ghi công bài đang kêu (CC BY đòi nêu tên ở nơi nhạc phát) - cùng khoá với máy tính (`_music_credits` của webui/server.py):
     *  title, creator, attribution, landing, license, licenseUrl, chỉ khoá nào có. null khi im lặng hay bài không có thông tin. */
    fun credit(): JSONObject? {
        val track = current?.track ?: return null
        val info = infos[track] ?: music?.optJSONObject("tracks")?.optJSONObject(track) ?: return null
        val out = JSONObject()
        for (key in CREDIT_KEYS) info.optString(key).takeIf { it.isNotEmpty() }?.let { out.put(key, it) }
        return out.takeIf { it.length() > 0 }
    }

    /** Có bài nhạc của sách ở chương này đang bị bỏ vì không phát được (đoạn ấy im lặng, chờ thử lại) - giao diện nói ra thay vì chỉ
     *  "Nhạc nền: Bật" (ui/src/listen/musicBed.ts `failing`, soát a26 L7). */
    fun brokenHere(): Boolean = playlist == null && cues.any { isFailed(it.track) }

    /** Giọng đọc đang ở `seconds` của chương `chapterId` trong cuốn `bookId`; `isPlaying` = giọng đang chạy. `stopNow`: giọng dừng là do người nghe
     *  (nút, rút tai nghe, mất focus, cuộc gọi) chứ không phải khe nối hai đoạn - danh sách phát dừng ngay, không chờ [PAUSE_GRACE_MS]. */
    fun sync(bookId: String, chapterId: Int?, seconds: Double, isPlaying: Boolean, stopNow: Boolean = false) {
        val appContext = context ?: return
        if (MusicCues.staleAfterClose(closedBook, bookId, isPlaying)) return
        closedBook = ""
        if (bookId != book) {
            stop()
            failed.clear()
            book = bookId
            music = if (bookId.isEmpty()) null else debugMusic?.takeIf { bookId == DEBUG_BOOK } ?: Store.playableManifest(bookId)?.optJSONObject("music")
            val level = music?.optDouble("levelDb", -20.0) ?: -20.0
            gain = 10.0.pow(level.coerceIn(-40.0, -6.0) / 20.0).toFloat()
            chapter = Int.MIN_VALUE
            if (music == null && bookId.isNotEmpty()) openPlaylist(appContext, bookId)
        }
        if (playlist != null) {
            syncPlaylist(isPlaying, stopNow)
            return
        }
        val newChapter = (chapterId ?: Int.MIN_VALUE) != chapter
        val seeked = abs(seconds - lastSeconds) > SEEK_JUMP_SECONDS
        lastSeconds = seconds
        playing = isPlaying
        if (newChapter) {
            chapter = chapterId ?: Int.MIN_VALUE
            if (sceneMode) {
                // Chương khác: bỏ mốc cũ ngay, rồi hỏi mốc chương mới (chương mới đã phát từ giây 0 thì không được chơi tiếp bài cuối của chương cũ).
                scene.reset()
                cues = emptyList()
                if (chapterId != null) askScene(appContext, chapterId, 0)
            } else {
                cues = MusicCues.of(music, chapterId)
            }
        } else if (sceneMode && scene.tick(seconds, seeked)) {
            cues = scene.cues // clip về hay người nghe nhảy: mốc đặt lại theo đồng hồ đọc
        }
        if (sceneMode) prefetchNext(appContext, seconds)
        var cue = MusicCues.at(cues, seconds, failed)
        current?.takeIf { it.early }?.let { bed ->
            // Bài vào sớm giữ chỗ tới đầu mốc của nó; tua thì theo mốc tại chỗ tua như thường.
            val mine = bed.cue
            if (!seeked && mine != null && seconds < mine.start) cue = mine else bed.early = false
        }
        if (!MusicCues.continues(current?.track, cue, newChapter) && (cue != null || current != null)) {
            // Bài của mốc chưa có file (danh mục đang tải): bài trước mờ đi, bài này vào ngay khi có file - lần `sync` sau.
            val uri = cue?.let { uriFor(appContext, it.track) }
            if (cue != null && uri != null) switchTo(cue.track to uri, MusicCues.targetGain(cue, seconds, gain), seconds - cue.start, cue)
            else switchTo(null, gain, 0.0)
        } else if (cue != null) {
            current?.cue = cue // cùng bài sang mốc kề: chơi tiếp, bước âm lượng theo mốc mới
            // Vừa tua trong cùng bài: dời nhạc theo chỗ mới, không chơi tiếp từ chỗ cũ (soát a26 L8).
            if (seeked) current?.let { bed ->
                loopHandoff.reset() // vé hẹn và bản lặp tạo sẵn cho chỗ cũ không còn đúng
                bed.final = false // vòng cuối của mốc `tail` tính lại theo chỗ mới (finishTail)
                bed.player.repeatMode = repeatFor(cue, bed.player)
                MusicCues.offsetMs(cue, seconds, bed.player.duration)?.let(bed.player::seekTo)
            }
        }
        retarget(seconds, seeked)
        finishTail(appContext, seconds)
        loopHandoff.check()
        applyPlaying()
    }

    /** Mốc `tail`: vòng cuối thì thôi lặp ([MusicCues.finalLoop]), bài chơi tới E là hết ([MusicCues.finished]). Bài đã hết trước
     *  hết mốc mà mốc kế bắt đầu đúng ở đó ([MusicCues.nextAfter]): mốc kế vào ngay, mờ vào như thường, không để quãng im. Không có mốc
     *  kế thì im tới hết mốc. */
    private fun finishTail(appContext: Context, seconds: Double) {
        val bed = current ?: return
        val cue = bed.cue?.takeIf { it.tail } ?: return
        val player = bed.player
        val bounds = boundsOf(cue, player)
        val position = player.currentPosition / 1000.0
        if (!bed.final && player.duration > 0 && MusicCues.finalLoop(cue, seconds, position, bounds)) {
            bed.final = true
            player.repeatMode = Player.REPEAT_MODE_OFF // bài quá ngắn lặp thường: chơi nốt vòng này rồi thôi
        }
        val ended = player.playbackState == Player.STATE_ENDED
        val done = if (bed.final) MusicCues.finished(bounds, position, ended) else ended
        if (!done || seconds >= cue.end) return
        val next = MusicCues.nextAfter(cues, cue)?.takeUnless { it.track == cue.track || isFailed(it.track) } ?: return
        val uri = uriFor(appContext, next.track) ?: return
        switchTo(next.track to uri, MusicCues.targetGain(next, seconds, gain), 0.0, next)
        current?.early = true
    }

    /** Lặp mờ chéo: bài đang kêu tới loopEnd - X ([MusicCues.loopDue]) thì một ExoPlayer của chính bài vào từ loopStart, mờ chéo X giây; cái
     *  cũ mờ đi rồi nhả. Vòng cuối của mốc `tail` ([finishTail]), bài quá ngắn (lặp thường) và danh sách phát thì không. Giờ vào do [LoopHandoff] giữ
     *  ([loopHandoff]); đây là phần nhìn bài đang kêu. */
    private fun lookLoop(): LoopHandoff.Snapshot? {
        val bed = current ?: return null
        val cue = bed.cue ?: return null
        val player = bed.player
        if (bed.final || lastSeconds >= cue.end || player.duration <= 0) return null
        return LoopHandoff.Snapshot(bed, boundsOf(cue, player), player.currentPosition / 1000.0, player.isPlaying)
    }

    /** Chỗ vào bản lặp `target` (giây trong bài): bài mp3 vào ở ranh khung gần chỗ ấy nhất ([ExactSeekMp3Extractor.frameBoundarySeconds]). */
    @OptIn(UnstableApi::class)
    private fun frameAligned(player: ExoPlayer, target: Double): Double {
        val format = player.audioFormat
        return if (format?.sampleMimeType == MimeTypes.AUDIO_MPEG) ExactSeekMp3Extractor.frameBoundarySeconds(target, format.sampleRate) else target
    }

    /** Bước 0: tạo SẴN bản lặp của vòng hiện tại - ExoPlayer đã `prepare()` và đứng ở loopStart, câm, `playWhenReady` false (đo thật máy tính: trình phát mới
     *  mất cả trăm mili giây mới có tiếng; tới hạn chỉ còn phát). Không có file bài / chưa có context thì null: tới hạn mở mới như trước. */
    private fun prepareLoop(snap: LoopHandoff.Snapshot): Bed? {
        val owner = snap.owner as Bed
        val cue = owner.cue ?: return null
        val appContext = context ?: return null
        val uri = uriFor(appContext, owner.track) ?: return null
        val fadeMs = Math.round(MusicCues.mix.loopCrossfadeSeconds * 1000)
        // Bài kiểm (§36/§39): chỗ lệch cố ý áp NGAY ở đích tua của bản chờ - đến hạn không phải tua lại chỉ vì nó (tua ấy thêm ~110 ms trễ, làm nhiễu bài kiểm). Bản thường: 0.
        val startAt = frameAligned(owner.player, snap.bounds.loopStart + debugLoopInject)
        return timed("lặp mờ chéo: tạo sẵn trình phát") {
            open(appContext, owner.track to uri, owner.goal, 0.0, cue, fadeMs, startAt, Handoff(owner, snap.bounds), standby = true)
        }.also {
            it.at = startAt
            probe { "standby" }
            probeArm()
            probeLoopWatch(owner, it)
            probePreroll(owner, it, snap.bounds)
        }
    }

    /** Nhóm E (§40, [debugLoopPreroll] > 0): lúc bản cũ còn `preroll` giây tới hạn (loopEnd - X), bản chờ `seekTo(loopStart - preroll)` và `play()` ở âm lượng 0 (`EV preroll`).
     *  Hẹn một lần theo vị trí bản cũ lúc này; bản chờ đã bị bỏ / đã vào bản lặp thì thôi. */
    private fun probePreroll(owner: Bed, standby: Bed, bounds: MusicCues.Loop) {
        val preroll = debugLoopPreroll
        if (preroll <= 0.0 || debugLoopProbe == null) return
        val toDue = bounds.loopEnd - MusicCues.mix.loopCrossfadeSeconds - owner.player.currentPosition / 1000.0
        main.postDelayed({
            if (standby.released || !playing || loopHandoff.prepared() !== standby || standby.prerolled) return@postDelayed
            standby.prerolled = true
            standby.player.seekTo((frameAligned(standby.player, bounds.loopStart + debugLoopInject - preroll) * 1000).toLong())
            probe { "preroll" }
            standby.player.play()
        }, Math.round(maxOf(0.0, toDue - preroll) * 1000))
    }

    /** Bước 3 (sửa pha một lần, [MusicCues.loopSettle]) của bản lặp `bed`: ghi `drift`, tua nếu cần. Gọi lúc `playing` (bản thường) hay lúc vào bản lặp (bản đã chạy trước hạn, §40). */
    private fun settleLoop(bed: Bed, handoff: Handoff) {
        val player = bed.player
        val old = handoff.old
        val oldPos = old.player.currentPosition / 1000.0
        val newPos = player.currentPosition / 1000.0
        val to = if (debugLoopSettle) MusicCues.loopSettle(handoff.bounds, oldPos, newPos, player.volume, bed.goal, oldAlive = old in fading && old.player.isPlaying) else null
        probe { "drift ${MusicCues.loopDrift(handoff.bounds, oldPos, newPos)} ${if (to != null) "applied" else "skipped"}" }
        if (to != null) {
            val ms = (to * 1000).toLong()
            probe { "seek $ms" }
            player.seekTo(ms)
        }
    }

    /** Vào bản lặp: bản mới (`ready`: đã tạo sẵn, hay mở mới) ở loopStart cộng phần trễ so với hạn ([MusicCues.loopStartAt]). */
    private fun enterLoop(snap: LoopHandoff.Snapshot, ready: Bed?) {
        val bed = current ?: return
        val cue = bed.cue ?: return
        val player = bed.player
        val bounds = snap.bounds
        val appContext = context ?: return
        val uri = uriFor(appContext, bed.track) ?: return
        val fadeMs = Math.round(MusicCues.mix.loopCrossfadeSeconds * 1000)
        bed.fadeStep = maxOf(player.volume, 0.01f) * STEP_MS / fadeMs
        fading += bed
        val startAt = frameAligned(player, MusicCues.loopStartAt(bounds, snap.position) + debugLoopInject)
        val next = if (ready != null) {
            // Vào muộn: đặt lại chỗ; vẫn đúng loopStart thì không tua (khỏi đệm lại). Bản đã chạy trước hạn (đo §40) đang kêu: không tua.
            if (!ready.prerolled && abs(ready.at - startAt) > 0.0005) {
                ready.player.seekTo((startAt * 1000).toLong())
                ready.at = startAt
            }
            ready.cue = cue
            ready.goal = bed.goal
            ready.perTick = bed.goal * STEP_MS / ready.fadeMs
            if (playing) {
                probeLoopPlay(bed, ready)
                if (ready.prerolled) ready.handoff?.let { settleLoop(ready, it) } else ready.player.play()
            }
            ready
        } else {
            timed("lặp mờ chéo: mở trình phát mới") { open(appContext, bed.track to uri, bed.goal, 0.0, cue, fadeMs, startAt, Handoff(bed, bounds)) }
        }
        current = next.also { it.early = bed.early }
        startFade()
    }

    /** Mức đích của bài đang kêu đổi (sang bước âm lượng mới): trượt dần trong stepRampSeconds; vừa tua thì vào thẳng mức mới
     *  (trừ lúc bài đang mờ vào). */
    private fun retarget(seconds: Double, seeked: Boolean) {
        val bed = current ?: return
        val cue = bed.cue ?: return
        val goal = MusicCues.targetGain(cue, seconds, gain)
        if (abs(goal - bed.goal) < 1e-6f) return
        bed.goal = goal
        when {
            bed.entering -> bed.perTick = goal * STEP_MS / bed.fadeMs
            seeked -> {
                bed.player.volume = goal
                return
            }
            else -> bed.perTick = abs(goal - bed.player.volume) * STEP_MS / MusicCues.mix.stepRampMs
        }
        startFade()
    }

    /** Cuốn vừa đóng ([release]): tin "giọng dừng" đến muộn của chính cuốn ấy không được mở lại bài nhạc; chỉ giọng chạy lại hay cuốn khác mới thôi chặn. */
    private var closedBook = ""

    /** Đóng sách: như [stop] và nhớ cuốn đã đóng ([closedBook]) - tạm dừng giọng gửi tin `sync(false)` về sau, tin ấy không dựng lại trình phát nhạc. */
    fun release() {
        val was = book
        stop()
        book = ""
        closedBook = was
    }

    /** Dừng hẳn (đổi cuốn, tắt dịch vụ phát): nhả mọi trình phát nhạc, ghi chỗ đang tới của danh sách phát. */
    fun stop() {
        main.removeCallbacks(grace)
        catalogRetry?.let(main::removeCallbacks)
        catalogRetry = null
        sceneRetry?.let(main::removeCallbacks)
        sceneRetry = null
        loopHandoff.reset()
        sceneMode = false
        autoPicked = false
        sceneNotice = ""
        meteredHeld = false
        scene.reset()
        advanceClock()
        saveClock()
        for (bed in listOfNotNull(current) + fading) release(bed)
        current = null
        fading.clear()
        cues = emptyList()
        chapter = Int.MIN_VALUE
        playlist = null
        queue.clear()
        infos = emptyMap()
        clockAt = 0L
        generation++
    }

    private fun applyPlaying() {
        // Chỉ bài đang kêu được chơi lại; bài đang mờ đi thì chỉ dừng cùng giọng (như `MusicBed.sync` của trình phát web).
        for (bed in listOfNotNull(current) + fading) {
            if (playing && !bed.player.isPlaying && bed === current) bed.player.play()
            // Bài đang đệm có playWhenReady = true mà isPlaying = false: không pause thì đệm xong nó tự kêu riêng sau khi giọng đã dừng (soát a77 #1).
            if (!playing && (bed.player.isPlaying || bed.player.playWhenReady)) bed.player.pause()
        }
    }

    // ---- danh sách phát -------------------------------------------------------------------------------------------

    private fun prefs(appContext: Context) = appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun clockKey() = "playlist:$book:$playlist"

    /** Cuốn không có nhạc của người làm sách: nhạc theo cảnh ([Playlists.sceneMode]: người nghe chọn "Theo cảnh", hay chưa chọn gì mà "Tự chọn nhạc nền" còn bật - mặc định) hay nạp
     *  hàng bài của danh sách phát người nghe đã chọn ở luồng nền; "off" (hay chưa chọn mà máy không tự chọn) là không nhạc. */
    private fun openPlaylist(appContext: Context, bookId: String) {
        val dir = Store.bookDir(bookId)
        val changes = BookEdits.load(dir).optJSONObject("music") ?: JSONObject()
        val choice = changes.optString("playlist")
        if (Playlists.sceneMode(BookEdits.rawBookOrNull(dir) ?: JSONObject(), choice, Playlists.autoEnabled)) {
            sceneMode = true // mốc từng chương được hỏi ở lần `sync` kế (chương mới)
            autoPicked = Playlists.isAutomatic(true, choice)
            return
        }
        val stored = choice.takeIf { it != Playlists.SCENE }.orEmpty() // "scene" mà không phải sách chữ / sách có nhạc của người làm sách: như chưa chọn gì
        if (stored.isEmpty() || stored == Playlists.OFF) return
        val levelDb = changes.optDouble("levelDb", -20.0).takeIf { it.isFinite() } ?: -20.0
        playlist = stored
        clockSeconds = prefs(appContext).getFloat(clockKey(), 0f).toDouble()
        val ticket = generation
        worker.execute {
            val resolved = runCatching { resolve(appContext, stored, levelDb) }.getOrNull()
            main.post {
                if (ticket != generation) return@post
                infos = resolved?.infos ?: emptyMap()
                queue.load(resolved?.tracks ?: emptyList())
                syncPlaylist(playing)
                // Danh mục chưa đủ (mất mạng lần đầu, một mảnh lỗi): chơi các bài đã có, tải lại phần thiếu - không để danh sách im lặng tới khi mở lại cuốn.
                if (resolved == null || resolved.incomplete) retryCatalogLater(appContext, stored, levelDb, ticket)
            }
        }
    }

    /** Hàng bài của lựa chọn `choice` (luồng nền: danh mục cần mạng lần đầu): bài + thông tin bài (để tải / bản sao). */
    private fun resolve(appContext: Context, choice: String, levelDb: Double): Resolved {
        if (choice == Playlists.MINE) {
            val store = DeviceMusic.store(appContext)
            val entries = store.entries().reversed() // cũ trước: bài mới nhập nối vào cuối, chỗ đang nghe không xô lệch
            val found = entries.associateBy { it.getString("link") }
            return Resolved(Playlists.queue(found.keys.toList(), found, levelDb) { store.file(it) != null }, found, false)
        }
        val catalog = DeviceMusic.catalog(appContext)
        val links = Playlists.linksOf(catalog.playlists(), choice)
        val partial = if (links.isEmpty()) MusicCatalog.Lookup(emptyMap(), emptySet()) else catalog.lookupPartial(links)
        val found = partial.found
        // Bài quá MusicCatalog.TRACK_MAX_MB (theo `bytes` của danh mục, hay lần tải trước) không vào hàng: bài sau dồn lên, như máy tính.
        // Bài thuộc mảnh chưa tải được (mạng) cũng chưa vào: chưa biết độ dài / độ to - các bài còn lại phát, mảnh về sau thì thêm vào.
        val tracks = Playlists.queue(links, found, levelDb) { MusicCatalog.shardOf(it) !in partial.missingShards && catalog.usable(it, found[it]) }
        return Resolved(tracks, found, partial.missingShards.isNotEmpty())
    }

    /** Kết quả [resolve]: hàng bài + thông tin bài; `incomplete`: còn mảnh danh mục chưa tải được (mạng) - tải lại sau. */
    private class Resolved(val tracks: List<Playlists.Track>, val infos: Map<String, JSONObject>, val incomplete: Boolean)

    /** Một lần tải lại danh mục đang chờ ([retryCatalogLater]); null = không có. */
    private var catalogRetry: Runnable? = null

    /** Danh mục chưa đủ: sau [MusicFailures.RETRY_MS] tải lại phần thiếu (một việc chờ duy nhất, không vòng lặp bận); đủ rồi thì thêm các bài
     *  mới vào hàng, chưa đủ thì chờ lần nữa. Đổi cuốn / đổi lựa chọn ([generation]) thì thôi. */
    private fun retryCatalogLater(appContext: Context, choice: String, levelDb: Double, ticket: Int) {
        catalogRetry?.let(main::removeCallbacks)
        val job = Runnable {
            catalogRetry = null
            if (ticket != generation) return@Runnable
            worker.execute {
                val resolved = runCatching { resolve(appContext, choice, levelDb) }.getOrNull()
                main.post {
                    if (ticket != generation) return@post
                    if (resolved != null) {
                        infos = resolved.infos
                        queue.replace(resolved.tracks, current?.track, clockSeconds)
                    }
                    if (resolved == null || resolved.incomplete) retryCatalogLater(appContext, choice, levelDb, ticket)
                }
            }
        }
        catalogRetry = job
        main.postDelayed(job, MusicFailures.RETRY_MS)
    }

    /** Nhạc đang đổi theo cảnh của truyện (không phải danh sách phát người nghe chọn): giao diện nhắc người nghe một lần ở bài đầu tiên kêu. */
    fun sceneActive(): Boolean = sceneMode

    /** Lời báo "mất mạng" khi có bài của danh sách phát đang bị giữ lại vì mạng (một nguồn nhạc nghỉ vì mạng) - giao diện nói ra thay vì để nhạc
     *  im lặng không lời; rỗng khi ổn. */
    fun offlineNotice(): String =
        if (playlist != null || sceneMode) sceneNotice.ifEmpty { context?.let { DeviceMusic.catalog(it).offlineNotice() }.orEmpty() }.ifEmpty { if (meteredHeld) METERED_NOTICE else "" } else ""

    /** File của một bài để phát; bài danh mục chưa tải thì tải ở luồng nền (lần `sync` sau mới phát) và trả null. */
    private fun uriOf(appContext: Context, link: String): Uri? {
        if (isFailed(link)) return null
        if (link.startsWith(MusicStore.LOCAL_PREFIX)) return DeviceMusic.store(appContext).file(link)?.let { Uri.fromFile(it) }
        val catalog = DeviceMusic.catalog(appContext)
        catalog.use(link, infos[link])?.let { return Uri.fromFile(it) } // file cụt (khác `bytes` danh mục) bị xoá ở đây rồi tải lại
        fetch(appContext, link)
        return null
    }

    /** Dữ liệu di động (mạng tính phí): cùng luật với "Làm trước" ([vn.abook.player.readaloud.PrepareAhead] chỉ chạy khi Wi-Fi không tính tiền) - bài danh mục (tới 40 MB mỗi bài) không tự tải, NHƯNG chỉ với
     *  nhạc máy tự chọn ([Playlists.holdsDownloadOnMetered]); người nghe đã chọn nhạc ở nút "Nhạc nền" thì tải như thường. Bài đã
     *  tải thì vẫn phát. Hỏi mỗi vài giây thôi ([fetch] được gọi theo nhịp 0,5 giây); mạng đổi sang Wi-Fi thì lần gọi kế tải, nhạc vào ở đầu cảnh/bài kế. */
    private fun meteredNow(appContext: Context): Boolean {
        val now = SystemClock.elapsedRealtime()
        if (now - meteredAt > METERED_CHECK_MS) {
            meteredAt = now
            meteredValue = runCatching { AndroidMusicStudent.metered(appContext) }.getOrDefault(false)
            if (!meteredValue) meteredHeld = false
        }
        return meteredValue
    }

    private var meteredAt = -METERED_CHECK_MS - 1
    private var meteredValue = false
    /** Có bài đang chờ vì dữ liệu di động (hộp "Nhạc nền" nói lý do thay vì để nhạc im lặng không lời - [offlineNotice]). */
    private var meteredHeld = false

    private fun fetch(appContext: Context, link: String) {
        if (isFailed(link) || link.startsWith(MusicStore.LOCAL_PREFIX) || !downloading.add(link)) return
        if (Playlists.holdsDownloadOnMetered(meteredNow(appContext), autoPicked)) {
            downloading.remove(link)
            meteredHeld = true
            return
        }
        meteredHeld = false
        val info = infos[link]
        // Bài đang kêu / sắp tới / vừa tải không bị dọn khi thư mục bài vượt trần ([MusicCatalog.prune]); luồng chính biết bài nào.
        val keep = listOfNotNull(current?.track) + fading.map { it.track } + cues.map { it.track } + queue.spans.map { it.track.link } + link
        worker.execute {
            var tooBig = false
            var offline = false
            val file = try {
                DeviceMusic.catalog(appContext).download(link, info).also { if (it != null) runCatching { DeviceMusic.catalog(appContext).prune(keep) } }
            } catch (_: MusicCatalog.TrackTooBig) {
                tooBig = true
                null
            } catch (_: MusicCatalog.Offline) {
                offline = true
                null
            } catch (_: Exception) {
                null
            }
            main.post {
                downloading.remove(link)
                when {
                    file != null -> {}
                    tooBig -> drop(link) // quá MusicCatalog.TRACK_MAX_MB: máy này không dùng bài ấy, bài khác thay
                    offline -> { // mất mạng: bài vẫn tốt - bỏ qua một lúc, thử lại khi có mạng, không tính vào số lần bỏ bài (như máy tính)
                        failed.dropOffline(link)
                        replan(link)
                    }
                    else -> { // nguồn gỡ bài, bản sao sai...: bỏ qua bài này một lúc, lùi dần, có hạn
                        failed.dropDownload(link)
                        DeviceMusic.catalog(appContext).markUnavailable(link) // bộ chọn nhạc theo cảnh cũng tránh nó (như máy tính)
                        replan(link)
                    }
                }
            }
        }
    }

    /** Bài không phát được (`retry`: phát hỏng - thử lại sau [MusicFailures.RETRY_MS]; không thì cả phiên): với danh sách phát, các bài sau
     *  dồn lên thay vì im lặng suốt khoảng của nó. Trước đây tải hỏng một lần lúc mất mạng là bài ấy im tới khi mở lại cuốn. */
    private fun drop(link: String, retry: Boolean = false) {
        failed.drop(link, retry)
        replan(link)
    }

    private fun replan(link: String) {
        if (playlist != null) queue.drop(link, current?.track)
    }

    private fun isFailed(link: String): Boolean = failed.isFailed(link)

    private fun advanceClock() {
        val now = SystemClock.elapsedRealtime()
        if (playlist != null && playing && clockAt != 0L) clockSeconds += minOf((now - clockAt) / 1000.0, MAX_STEP_SECONDS)
        clockAt = if (playing) now else 0L
    }

    private fun saveClock() {
        val appContext = context ?: return
        if (playlist == null) return
        prefs(appContext).edit().putFloat(clockKey(), clockSeconds.toFloat()).apply()
        savedAt = SystemClock.elapsedRealtime()
    }

    /** Giọng dừng hẳn (quá [PAUSE_GRACE_MS]): nhạc dừng theo, đồng hồ đứng, ghi chỗ. */
    private fun holdStill() {
        advanceClock()
        playing = false
        clockAt = 0L
        applyPlaying()
        saveClock()
    }

    private fun syncPlaylist(isPlaying: Boolean, stopNow: Boolean = false) {
        val appContext = context ?: return
        if (isPlaying) {
            main.removeCallbacks(grace)
            if (!playing) {
                playing = true
                clockAt = SystemClock.elapsedRealtime()
            }
            advanceClock()
        } else if (playing) {
            main.removeCallbacks(grace)
            if (stopNow) {
                holdStill() // người nghe (hay hệ thống thay họ) đã dừng giọng: nhạc im ngay, không kêu thêm 2,5 giây
            } else {
                // Giọng vừa ngừng: có thể chỉ là chỗ nối hai đoạn / hai chương - chờ một chút rồi mới dừng nhạc.
                main.postDelayed(grace, PAUSE_GRACE_MS)
            }
        }
        // Sắp đổi bài: bài bỏ tạm vì mất mạng đã tới lúc thử lại thì về hàng (PlaylistQueue.at) - ngay lúc này chứ không giữa bài.
        val found = queue.at(clockSeconds, current?.track)
        if (found == null) {
            if (current != null) switchTo(null, 1f, 0.0)
            return
        }
        val (span, offset) = found
        if (span.index != queue.currentSpan) {
            val uri = uriOf(appContext, span.track.link)
            if (uri != null) {
                queue.currentSpan = span.index
                switchTo(span.track.link to uri, 10.0.pow(minOf(0.0, span.track.gainDb) / 20.0).toFloat(), offset)
            } else if (current != null) {
                switchTo(null, 1f, 0.0) // bài này đang tải: bài trước mờ đi, bài này vào ngay khi có file
            }
            // Bài kế tải sẵn trong lúc bài này chơi: sang bài không phải chờ mạng.
            queue.spans.getOrNull((span.index + 1) % queue.spans.size)?.let { next -> fetch(appContext, next.track.link) }
        }
        applyPlaying()
        if (SystemClock.elapsedRealtime() - savedAt > SAVE_EVERY_MS) saveClock()
    }

    // ---- nhạc theo cảnh -------------------------------------------------------------------------------------------

    /** Đồng hồ đọc của chương đang nghe (giây bắt đầu từng đoạn + tổng độ dài), null khi chưa có. */
    private fun sceneTiming(): SceneAnchor.Timing? {
        if (chapter == Int.MIN_VALUE) return null
        return vn.abook.player.readaloud.ReadAloud.segmentTiming(book, chapter)?.let { (starts, total) -> SceneAnchor.Timing(starts, total) }
    }

    /** File của bài `track` của mốc: bài theo cảnh lấy từ danh mục (chưa tải: tải nền, null), bài của người làm sách qua đường audio chương. */
    private fun uriFor(appContext: Context, track: String): Uri? =
        debugTrack?.takeIf { book == DEBUG_BOOK } ?: if (sceneMode) uriOf(appContext, track) else Streaming.chapterUri(appContext, book, track)

    /** Bài của mốc kế tiếp (khác bài đang kêu) tải sẵn trong lúc bài này chơi: sang mốc không phải chờ mạng. */
    private fun prefetchNext(appContext: Context, seconds: Double) {
        val sounding = MusicCues.at(cues, seconds, failed)?.track
        cues.firstOrNull { it.start > seconds && it.track != sounding }?.let { uriOf(appContext, it.track) }
    }

    /** Hỏi mốc nhạc theo cảnh của chương `chapterId` (luồng nền: dựng nền có thể tới vài giây, danh mục cần mạng lần đầu). Chương chưa dựng xong ([DeviceScenes] trả `pending`)
     *  thì hỏi lại sau [SCENE_POLL_MS], tối đa [SCENE_POLLS] lần; về rồi thì nhạc vào ở đầu câu kế ([SceneAnchor.Feed.arrive]). Đổi cuốn / chương thì lần hỏi cũ bị bỏ. */
    private fun askScene(appContext: Context, chapterId: Int, attempt: Int, misses: Int = 0) {
        val ticket = generation
        val bookId = book
        DeviceScenes.request(appContext, bookId, chapterId) { result, _ ->
            val pending = result?.optBoolean("pending", false) == true
            val notice = result?.optString("unavailable", "").orEmpty()
            val arrival = if (result == null || pending) null else runCatching { arrivalOf(appContext, bookId, result) }.getOrNull()
            main.post {
                if (ticket != generation || chapter != chapterId) return@post
                sceneNotice = notice
                if (pending && attempt < SCENE_POLLS) {
                    val job = Runnable {
                        sceneRetry = null
                        if (ticket == generation && chapter == chapterId) askScene(appContext, chapterId, attempt + 1, misses)
                    }
                    sceneRetry = job
                    main.postDelayed(job, SCENE_POLL_MS)
                    return@post
                }
                // Chưa có mốc vì danh mục chưa tải được / dựng hỏng: hỏi lại sau một quãng (mạng về giữa chương thì nhạc vào ở đầu câu kế), không đợi tới chương sau.
                if ((result == null || notice.isNotEmpty()) && misses < SCENE_RETRY_MS.size) {
                    val job = Runnable {
                        sceneRetry = null
                        if (ticket == generation && chapter == chapterId) askScene(appContext, chapterId, 0, misses + 1)
                    }
                    sceneRetry = job
                    main.postDelayed(job, SCENE_RETRY_MS[misses])
                }
                infos = infos + (arrival?.infos ?: emptyMap())
                if (arrival != null && scene.arrive(arrival, lastSeconds)) cues = scene.cues
            }
        }
    }

    /** Mốc thô + số đo bài của danh mục (độ khuếch đại, đoạn nghe được, ghi công) cho [SceneBed]; danh mục chưa trả lời thì chỉ mốc (mức mặc định). Luồng nền. */
    private fun arrivalOf(appContext: Context, bookId: String, result: JSONObject): SceneBed.Arrival {
        val cues = SceneAnchor.cuesOf(result)
        val level = (BookEdits.load(Store.bookDir(bookId)).optJSONObject("music")?.optDouble("levelDb", SceneBed.DEFAULT_LEVEL_DB) ?: SceneBed.DEFAULT_LEVEL_DB)
            .takeIf { it.isFinite() } ?: SceneBed.DEFAULT_LEVEL_DB
        val links = cues.map { it.link }.distinct()
        val found = if (links.isEmpty()) emptyMap() else runCatching { DeviceMusic.catalog(appContext).lookupPartial(links).found }.getOrDefault(emptyMap())
        return SceneBed.Arrival(cues, result.optDouble("estSeconds", 0.0), level, found)
    }

    // ---- nhạc theo mốc của sách --------------------------------------------------------------------------------

    /** Bài đang kêu mờ đi; `next` = (tên bài, file) thì bài ấy vào, bắt đầu ở giây `offsetSeconds` của nó, lên tới `targetGain`.
     *  `cue`: mốc của sách (bước âm lượng; mốc `sibling` = nối bài anh em ở điểm kết bài: mờ chéo dài hơn, bài cũ chơi nốt rồi thôi,
     *  không quay lại đầu bài, mờ trong phần còn lại tới E nếu ngắn hơn - [MusicCues.siblingFadeSeconds]). */
    private fun switchTo(next: Pair<String, Uri>?, targetGain: Float, offsetSeconds: Double, cue: MusicCues.Cue? = null) {
        loopHandoff.reset()
        val mix = MusicCues.mix
        val fadeMs = if (cue?.sibling == true) mix.siblingFadeMs else mix.fadeMs
        current?.let {
            var oldFadeMs = fadeMs
            if (cue?.sibling == true) {
                it.player.repeatMode = Player.REPEAT_MODE_OFF
                val was = it.cue
                if (was != null && it.player.duration > 0) {
                    oldFadeMs = Math.round(MusicCues.siblingFadeSeconds(boundsOf(was, it.player), it.player.currentPosition / 1000.0) * 1000)
                }
            }
            it.fadeStep = maxOf(it.player.volume, 0.01f) * STEP_MS / oldFadeMs
            fading += it
        }
        current = null
        val appContext = context ?: return
        if (next != null) current = open(appContext, next, targetGain, offsetSeconds, cue, fadeMs)
        startFade()
    }

    /** Một ExoPlayer mới cho bài `next`, mờ vào tới `targetGain` trong `fadeMs`. `startAt` (phần tử lặp, giây trong bài): vào đúng
     *  chỗ ấy (A), không căn theo giây chương - đồng hồ bài lệch giọng vài phần giây thì căn lại có khi rơi về cuối vòng. */
    @OptIn(UnstableApi::class)
    private fun open(appContext: Context, next: Pair<String, Uri>, targetGain: Float, offsetSeconds: Double, cue: MusicCues.Cue?,
                     fadeMs: Long, startAt: Double? = null, handoff: Handoff? = null, standby: Boolean = false): Bed {
        val (track, uri) = next
        // Bộ giải mã đồng bộ: chế độ hàng đợi bất đồng bộ (mặc định Android 12+) tắt luồng gọi lại của MediaCodec trước khi nhả codec - mỗi lần nhả một bài
        // (lặp mờ chéo ~40 lần / 5 phút) codec còn gửi sự kiện tới luồng đã chết ("sending message to a Handler on a dead thread", soát a69: 360 lần / 40 phút).
        // Đang đo (§39): sink có tee PCM + AudioTrack giữ lại; bản thường không tạo gì thêm.
        val tee = if (debugLoopProbe != null) LoopTee(probeNextK.getAndIncrement()).also { probeTees += it } else null
        val renderers = (if (tee != null) probeRenderers(appContext, tee) else DefaultRenderersFactory(appContext)).forceDisableMediaCodecAsynchronousQueueing()
        val player = ExoPlayer.Builder(appContext, renderers)
            .setAudioAttributes(
                AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MUSIC).build(),
                false,
            )
            .setMediaSourceFactory(Streaming.mediaSourceFactory(appContext, exactMp3Seek = true))
            // media3 1.11 bật dynamic scheduling mặc định: luồng phát chỉ thức khi bộ đệm cần (~250 ms), currentPosition đứng
            // yên rồi nhảy 250 ms - hẹn giờ lặp, độ trễ và độ trôi đọc vị trí này nên lệch tới chừng ấy (Music đo trên máy 22-10, PLAN_loop §36.1).
            .experimentalSetDynamicSchedulingEnabled(false)
            .build()
        player.repeatMode = Player.REPEAT_MODE_ONE // biết độ dài bài (STATE_READY) mới biết lặp mờ chéo hay lặp thường
        player.volume = 0f
        val offsetMs = (offsetSeconds.coerceAtLeast(0.0) * 1000).toLong()
        val bed = Bed(track, player, targetGain, targetGain * STEP_MS / fadeMs, cue, fadeMs)
        bed.tee = tee
        bed.handoff = handoff
        fun listen(listener: Player.Listener) {
            bed.listeners += listener
            player.addListener(listener)
        }
        listen(object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_READY) {
                    player.removeListener(this)
                    bed.listeners.remove(this)
                    failed.forget(track)
                    val duration = player.duration
                    player.repeatMode = repeatFor(bed.cue, player, bed.final)
                    if (startAt != null || duration <= 0) return
                    // Nhạc của sách tải xong sau khi giọng đã chạy tiếp (hay vừa tua): theo giây mới nhất của chương (soát a26 L8).
                    val mine = bed.cue
                    val latest = if (mine != null && current === bed) MusicCues.offsetMs(mine, lastSeconds, duration) else null
                    player.seekTo(latest ?: (offsetMs % duration))
                }
            }
        })
        if (handoff != null) listen(object : Player.Listener {
            // Bản lặp mới vừa có tiếng (STATE_READY + playWhenReady): bù độ trễ mở trình phát, một lần. Nó gần như câm nên cú dời không nghe thấy.
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                if (!isPlaying) return
                player.removeListener(this)
                bed.listeners.remove(this)
                probe { "playing" }
                if (bed.prerolled) return // đã chạy trước hạn (§40): hạn đo và bước 3 tính lúc vào bản lặp ([enterLoop])
                if (probeBed === bed && debugLoopProbe != null) probeUntil = System.nanoTime() + PROBE_AFTER_PLAYING_MS * 1_000_000
                settleLoop(bed, handoff)
            }
        })
        listen(object : Player.Listener {
            // Nhạc của sách hỏng (file thiếu trong gói, mạng tới máy tính rớt khi nghe thẳng): đoạn này im lặng, RETRY_MS sau thử
            // lại như máy tính. Bài của danh sách phát phát hỏng (file hỏng) thì bỏ cả phiên - tải hỏng đã có fetch lo.
            override fun onPlayerError(error: PlaybackException) {
                main.post {
                    if (bed.released) return@post // đã nhả (bản tạo sẵn bị bỏ, bài mờ xong): lỗi muộn không tính là bài hỏng
                    if (loopHandoff.prepared() === bed) { // bản lặp tạo sẵn hỏng trước khi dùng: bỏ êm, tới hạn mở mới
                        loopHandoff.discardReady()
                        return@post
                    }
                    drop(track, retry = playlist == null)
                    release(bed)
                    if (current?.player === player) {
                        current = null
                        queue.currentSpan = -1
                    }
                    fading.removeAll { it.player === player }
                }
            }
        })
        if (startAt != null) player.setMediaItem(MediaItem.fromUri(uri), (startAt * 1000).toLong())
        else player.setMediaItem(MediaItem.fromUri(uri))
        player.prepare()
        if (playing && !standby) {
            if (handoff != null) probeLoopPlay(handoff.old, bed)
            player.play()
        }
        return bed
    }

    private fun startFade() {
        if (fadingTicker) return
        fadingTicker = true
        main.post(object : Runnable {
            override fun run() {
                var busy = false
                current?.let { bed ->
                    val player = bed.player
                    // Bài còn tải / đệm thì chưa mờ vào: để lúc có tiếng mới nhích từ 0 lên, không nhảy thẳng tới mức (soát B3).
                    val ready = player.playbackState.let { it == Player.STATE_READY || it == Player.STATE_ENDED }
                    player.volume = MusicCues.towardWhenReady(player.volume, bed.goal, bed.perTick, ready)
                    if (ready && abs(player.volume - bed.goal) < 1e-4f) bed.entering = false else busy = true
                }
                val iterator = fading.iterator()
                while (iterator.hasNext()) {
                    val bed = iterator.next()
                    bed.player.volume = maxOf(0f, bed.player.volume - bed.fadeStep)
                    if (bed.player.volume <= 0.001f) {
                        release(bed)
                        iterator.remove()
                    } else {
                        busy = true
                    }
                }
                if (busy) main.postDelayed(this, STEP_MS) else fadingTicker = false
            }
        })
    }
}
