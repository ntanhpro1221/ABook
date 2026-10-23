package vn.abook.player

import android.content.Context
import android.media.AudioTimestamp
import android.media.AudioTrack
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import androidx.annotation.OptIn
import androidx.annotation.VisibleForTesting
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.audio.AudioProcessor
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.audio.AudioSink
import androidx.media3.exoplayer.audio.DefaultAudioSink
import androidx.media3.exoplayer.audio.ForwardingAudioSink
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.util.concurrent.Executors
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
    // Bước 3 của nối vòng (sửa pha một lần khi bản lặp mới vừa có tiếng) TẠM TẮT trên điện thoại: đo trên máy 22-10 (PLAN_loop §37.1),
    // lúc ấy vị trí bản mới còn đang được media3 làm mượt (~+100 ms/s) nên độ trôi đọc ra có thể là ảo, và seekTo làm bản lặp im ~0,4 s.
    // Bật lại khi §38 đo được bước này có ích.
    private const val LOOP_SETTLE = false
    private const val PREFS = "music_bed"
    /** Giọng của người nghe, không phải lỗi: nhạc nền chờ Wi-Fi (không tự tải bài nhạc lớn bằng dữ liệu di động). */
    private const val METERED_NOTICE = "Đang dùng dữ liệu di động nên nhạc nền tự chọn chờ có Wi-Fi mới tải. Muốn nghe ngay, bạn chọn nhạc ở nút Nhạc nền."
    private const val AUTO_KEY = "auto-scene-music"
    private const val SEAM_P3_KEY = "music-seam-p3"
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
        // Đường P3 ([musicSeamP3], MusicSeamBed.kt): một ExoPlayer phát [Clip, Nối, Clip lặp, ...] qua LoopSink; built null = đường cũ (a87).
        var built: SeamPicker.Built? = null
        var sink: LoopSeam.LoopSink? = null
        var attached = false // đã nối Nối / Clip lặp vào hàng phát (trước đó chỉ có Clip đầu)
        // Bài a87 mở vào giữa vòng khi Nối chưa dựng xong (hay vừa rơi về): Nối đang dựng, xong thì chuyển sang P3 ở ranh lặp kế ([enterLoop]).
        var pending: SeamPicker.Built? = null
        var forcedTarget: SeamClock.Target? = null // bản P3 tạo sẵn để nhận ranh lặp: đích tua cố định (Nối, mẫu 0), [promoteTo] chỉnh lại theo chỗ bài cũ đang ở
        var testK = 0 // số thứ tự trình phát trong kịch bản đo ([testPlayerSeq]); chỉ cho dòng testEvents
        var trackRef: TrackRef? = null // AudioTrack mới nhất + mốc của nó (cờ P3 bật / đang đo): P3 thật sự ra loa, pha P3 - a87 ([stepHandover])
        var volume = 0f // âm lượng LOGIC (mờ vào / mờ đi / bước âm lượng, dòng đo `vol`); ExoPlayer.volume = volume x [sleepFactor] - mọi chỗ đọc mức đọc từ đây, không đọc ngược player.volume
    }

    /**
     * AudioTrack MỚI NHẤT của một trình phát (tạo ở luồng phát, đọc ở luồng chính) và mốc của nó ([TrackedSink]): `flushedNano` = [System.nanoTime] của lần xả bộ đệm cuối (mỗi lần tua;
     * DefaultAudioSink nhả AudioTrack cũ và tạo cái mới, framePosition lại từ 0), `startUs` = giây bài (µs) của khung đầu tiên ghi vào AudioTrack ấy (buffer đang ghi lúc nó được tạo,
     * `handlingUs`), [C.TIME_UNSET] khi chưa có.
     */
    private class TrackRef {
        @Volatile var track: AudioTrack? = null
        @Volatile var flushedNano = 0L
        @Volatile var startUs = C.TIME_UNSET
        @Volatile var handlingUs = C.TIME_UNSET

        /** AudioTrack mới vừa được tạo (luồng phát, giữa lúc ghi buffer `handlingUs`). */
        fun created(track: AudioTrack) {
            startUs = handlingUs
            this.track = track
        }
    }

    /**
     * Sink ghi mốc của [TrackRef]: giây bài của buffer đang ghi = presentationTimeUs - outputStreamOffsetUs (như DefaultAudioSink tính startMediaTimeUs). Không đổi gì ở tiếng.
     * `onFlush`: gọi lúc xả, trước khi AudioTrack cũ bị nhả (móc đo bỏ AudioTrack cũ khỏi [testTracks]).
     */
    @OptIn(UnstableApi::class)
    private class TrackedSink(inner: AudioSink, private val ref: TrackRef, private val onFlush: () -> Unit = {}) : ForwardingAudioSink(inner) {
        private var offsetUs = 0L

        override fun setOutputStreamOffsetUs(outputStreamOffsetUs: Long) {
            offsetUs = outputStreamOffsetUs
            super.setOutputStreamOffsetUs(outputStreamOffsetUs)
        }

        override fun flush() {
            ref.track = null // AudioTrack cũ sắp bị nhả: không đọc nó nữa
            ref.startUs = C.TIME_UNSET
            ref.flushedNano = System.nanoTime()
            onFlush()
            super.flush()
        }

        override fun handleBuffer(buffer: ByteBuffer, presentationTimeUs: Long, encodedAccessUnitCount: Int): Boolean {
            ref.handlingUs = maxOf(0L, presentationTimeUs - offsetUs)
            return super.handleBuffer(buffer, presentationTimeUs, encodedAccessUnitCount)
        }
    }

    /**
     * Một lần chuyển a87 -> P3 đang diễn ra ([SeamHandover]): `old` (a87) vẫn là [current] và vẫn kêu; `p3` phát câm cho tới khi pha khớp. `lag` = trễ khởi động dùng cho lần tua kế;
     * `targetSample` / `issuedNano` = lần tua cuối của P3 (mẫu đích của Nối, [System.nanoTime] lúc tua: chỉ AudioTrack sinh ra sau lần xả SAU mốc này mới tin, [SeamHandover.fresh]);
     * `readings` = pha P3 - a87 (ms) của các lần đọc tin được kể từ lần tua cuối ([SeamHandover.decide]); `landing` = lưới an toàn của lần tua cuối (mẫu đáp thật), `seeks` đánh số
     * lần tua để bỏ kết quả muộn của lần tua cũ. Dịch trong dòng ([SeamHandover.Act.SHIFT]): `shifted` = các dịch đã áp sau lần tua cuối (cũ trước), `shiftPending` = đã ra lệnh mà
     * sink chưa báo áp xong (không lần đọc nào tính), `shifts` = số lần dịch của cả lần chuyển; `seekPhase` = pha ổn định đầu tiên của lần tua cuối, trước mọi dịch (tua lại sửa trễ theo nó).
     */
    private class Handover(val p3: Bed, val old: Bed, val startedAt: Long, var lag: Long) {
        var issued = false
        var targetSample = 0L
        var issuedNano = 0L
        var landing: SeamHandover.Landing = SeamHandover.Landing.Pending
        var seeks = 0
        var retunes = 0
        val readings = ArrayList<Double>()
        var learned = false
        var shifts = 0
        var shiftPending = false
        val shifted = ArrayList<LoopSeam.Shift>()
        var seekPhase: Double? = null
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

    /** Lần chuyển a87 -> P3 đang diễn ra ([beginHandover]); null = không có. */
    private var handover: Handover? = null

    /** Trễ khởi động P3 (ms, từ lệnh tua tới khi ra loa) đo ở lần chuyển gần nhất; lần đầu là số ước lượng ([SeamHandover.DEFAULT_LAG_MS]). */
    @Volatile private var p3LagMs = SeamHandover.DEFAULT_LAG_MS
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
        bed.listeners.forEach(bed.player::removeListener)
        bed.listeners.clear()
        bed.player.release()
    }
    private val worker = Executors.newSingleThreadExecutor()
    private var context: Context? = null
    @Volatile private var book = ""
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
        musicSeamP3 = prefs(appContext).getBoolean(SEAM_P3_KEY, false)
    }

    /**
     * TUỲ CHỌN THỬ NGHIỆM (mặc định TẮT): bài nhạc mp3 có vòng lặp mờ chéo phát bằng MỘT trình phát nối chính xác từng mẫu ([LoopSeam], MusicSeamBed.kt) thay vì mở trình phát mới ở
     * mỗi chỗ lặp (đường a87). Bật: `PlayerPlugin.configure({musicSeamP3: true})` hay [rememberSeamP3]; chỉ ảnh hưởng bài mở SAU đó. Bài không dùng được (mốc `tail`, không phải mp3,
     * dựng Nối lỗi / không kịp) tự rơi về a87 và ghi logcat "ABookMusic".
     */
    @Volatile var musicSeamP3 = false
        private set

    /** Bật / tắt [musicSeamP3] và nhớ qua lần khởi động tiến trình. */
    fun rememberSeamP3(value: Boolean) {
        musicSeamP3 = value
        val appContext = context ?: return
        prefs(appContext).edit().putBoolean(SEAM_P3_KEY, value).apply()
    }

    // ---- MÓC ĐO (chỉ cho androidTest MusicBedSeamOnDeviceTest; SPEC_loop_p3w_bed.md §1). Mặc định null / 0: bản phát hành không tốn gì và không đổi hành vi. ----

    /** MÓC ĐO: mỗi ExoPlayer MusicBed tạo (đường P3 lẫn a87, kể cả bản lặp tạo sẵn) gắn thêm bộ xử lý này CUỐI chuỗi âm thanh (để ghi PCM). Đọc [testCreating] để biết đang tạo trình phát nào. */
    @VisibleForTesting @Volatile var testAudioProcessor: (() -> AudioProcessor)? = null

    /** MÓC ĐO: nhận một dòng sự kiện (định dạng ở [SeamEvents], không có `EV <ns>`: bên đo tự thêm). Gọi từ luồng chính, riêng `audiotrack` từ luồng phát. */
    @VisibleForTesting @Volatile var testEvents: ((String) -> Unit)? = null

    /** MÓC ĐO: ngủ thêm chừng này ms trước khi dựng Nối ở luồng nền (kịch bản dựng chậm). */
    @VisibleForTesting @Volatile var testRenderDelayMs = 0L

    /** MÓC ĐO: số thứ tự (từ 0) của trình phát kế tiếp MusicBed tạo; bên đo đặt 0 ở đầu mỗi kịch bản. */
    @VisibleForTesting @Volatile var testPlayerSeq = 0

    /**
     * MÓC ĐO: AudioTrack MỚI NHẤT của từng trình phát k (chỉ điền khi [testEvents] đặt); bên đo đọc `getTimestamp` / `underrunCount` và tự xoá ở đầu kịch bản.
     * Mỗi lần xả (tua) bỏ mục k cho tới khi AudioTrack mới được tạo: không đọc timestamp của AudioTrack cũ sau lần tua (như [SeamHandover.fresh]).
     */
    @VisibleForTesting val testTracks = java.util.concurrent.ConcurrentHashMap<Int, android.media.AudioTrack>()

    /** MÓC ĐO: số thứ tự của trình phát đang được tạo (hợp lệ trong lúc [testAudioProcessor] được gọi). */
    @VisibleForTesting @Volatile var testCreating = 0

    /** MÓC ĐO: chờ việc nền đang chạy / đã xếp ([worker]: dựng Nối, tải bài) xong, tối đa `timeoutMs`; true nếu xong. */
    @VisibleForTesting fun awaitIdle(timeoutMs: Long): Boolean {
        val done = java.util.concurrent.CountDownLatch(1)
        worker.execute { done.countDown() }
        return done.await(timeoutMs, java.util.concurrent.TimeUnit.MILLISECONDS)
    }

    private fun emit(line: () -> String?) {
        val sink = testEvents ?: return
        line()?.let(sink)
    }

    /** Chọn đường cho bài của mốc ([musicSeamP3]); việc dựng Nối ở luồng [worker], không bao giờ chặn việc phát. */
    private val seamPicker = SeamPicker(
        enabled = { musicSeamP3 },
        async = { worker.execute(it) },
        plan = { file, cue -> planSeam(file, cue) },
        render = { built ->
            if (testRenderDelayMs > 0) Thread.sleep(testRenderDelayMs)
            LoopSeam.render(built.seam)
        },
        note = { Log.w(TAG, it) },
    )

    /** Hình học Nối của `file` theo vòng của `cue` (null: bài không lặp mờ chéo). Cỡ mili giây: đọc độ dài + định dạng file; bản WAV Nối dựng sau ([LoopSeam.render]). */
    private fun planSeam(file: File, cue: MusicCues.Cue): SeamPicker.Built? {
        val appContext = context ?: return null
        val duration = trackSeconds(file) ?: return null
        val bounds = MusicCues.loopBounds(cue, duration)
        if (!bounds.crossfade) return null
        val seam = LoopSeam.plan(appContext, file, LoopSeam.Bounds(bounds.start, bounds.loopStart, bounds.loopEnd), MusicCues.mix.loopCrossfadeSeconds)
        return SeamPicker.Built(seam, bounds, duration, SeamPicker.keyOf(file, cue))
    }

    internal fun trackSeconds(file: File): Double? {
        val extractor = MediaExtractor()
        try {
            extractor.setDataSource(file.absolutePath)
            for (i in 0 until extractor.trackCount) {
                val format = extractor.getTrackFormat(i)
                if (format.getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true && format.containsKey(MediaFormat.KEY_DURATION)) {
                    return format.getLong(MediaFormat.KEY_DURATION) / 1_000_000.0
                }
            }
            return null
        } finally {
            extractor.release()
        }
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

    /** Nhập/xoá kho riêng: thay hàng bài, giữ bài đang kêu và đồng hồ nhạc. */
    fun refreshMine() {
        val appContext = context ?: return
        if (playlist != Playlists.MINE) return
        val ticket = generation
        worker.execute {
            // Sách mang theo đúng các bài đã chọn (BookEdits.setMusic): kho vừa đổi thì chụp lại các bài hiện có vào sách rồi mới dựng hàng bài.
            runCatching {
                BookEdits.setMusic(Store.bookDir(book), JSONObject().put("playlist", Playlists.MINE), null, DeviceMusic.store(appContext).let { store ->
                    { store.entries().reversed().mapNotNull { info -> store.file(info.getString("link"))?.let { info to it } } }
                })
            }
            val resolved = runCatching { resolve(appContext, Playlists.MINE, 20 * kotlin.math.log10(gain.toDouble())) }.getOrNull()
            main.post {
                if (ticket != generation || playlist != Playlists.MINE || resolved == null) return@post
                advanceClock()
                infos = resolved.infos
                queue.replace(resolved.tracks, current?.track, clockSeconds)
                syncPlaylist(playing)
            }
        }
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
            music = if (bookId.isEmpty()) null else Store.playableManifest(bookId)?.optJSONObject("music")
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
        val sameSeam = current?.built?.let { built -> cue != null && SeamPicker.compatible(built, cue) } ?: true // bài P3 sang mốc kề có vòng khác (hay `tail`): mở lại bằng đường chọn lại
        if ((!MusicCues.continues(current?.track, cue, newChapter) || !sameSeam) && (cue != null || current != null)) {
            // Bài của mốc chưa có file (danh mục đang tải): bài trước mờ đi, bài này vào ngay khi có file - lần `sync` sau.
            if (cue == null || !startCue(appContext, cue, seconds, seconds - cue.start)) switchTo(null, gain, 0.0)
        } else if (cue != null) {
            current?.cue = cue // cùng bài sang mốc kề: chơi tiếp, bước âm lượng theo mốc mới
            // Vừa tua trong cùng bài: dời nhạc theo chỗ mới, không chơi tiếp từ chỗ cũ (soát a26 L8).
            if (seeked) current?.let { bed ->
                resetLoop() // vé hẹn, bản lặp tạo sẵn và lần chuyển sang P3 cho chỗ cũ không còn đúng
                bed.final = false // vòng cuối của mốc `tail` tính lại theo chỗ mới (finishTail)
                if (bed.built != null) {
                    if (!seamSeek(bed, seconds - cue.start)) demote(appContext, bed, DemoteReason.SEEK, reject = false)
                } else {
                    bed.player.repeatMode = repeatFor(cue, bed.player)
                    MusicCues.offsetMs(cue, seconds, bed.player.duration)?.let(bed.player::seekTo)
                }
            }
        }
        retarget(seconds, seeked)
        finishTail(appContext, seconds)
        seamTick(appContext)
        emit { current?.takeIf { it.built != null && it.cue != null }?.let { SeamEvents.pos(it.testK, positionOf(it), MusicCues.alignedPosition(it.cue!!, seconds, it.built!!.bounds)) } }
        loopHandoff.check()
        applyPlaying()
    }

    /** Mở bài của mốc `cue` (bắt đầu `offsetSeconds` giây trong mốc), chọn đường P3 hay a87 ([seamPicker]); false khi chưa mở được (chưa có file: bài trước mờ đi, lần `sync` sau thử lại).
     *  `startAt`: trình phát a87 vào thẳng chỗ ấy (giây trong bài, [open]) - chỉ [demote] truyền. */
    private fun startCue(appContext: Context, cue: MusicCues.Cue, seconds: Double, offsetSeconds: Double, allowSeam: Boolean = true, startAt: Double? = null): Boolean {
        val uri = uriFor(appContext, cue.track) ?: return false
        var built: SeamPicker.Built? = null
        var later: SeamPicker.Built? = null
        if (allowSeam && musicSeamP3 && uri.scheme == "file") {
            built = (seamPicker.choose(File(uri.path!!), cue) as? SeamPicker.Choice.Use)?.built
            // Chỗ vào nằm sau Clip đầu mà Nối chưa dựng xong thì Clip đầu không phục vụ được: a87 phục vụ chỗ vào, Nối dựng nền, xong thì chuyển sang P3 ở ranh lặp kế ([promoteTo]).
            // Nối đã có trên đĩa (SeamPicker.choose thấy WAV đúng khoá -> READY ngay) thì vào P3 luôn, tới đúng mục / vị trí.
            if (built != null && !SeamClock.servesEntry(built, offsetSeconds)) {
                later = built
                built = null
            }
        }
        switchTo(cue.track to uri, MusicCues.targetGain(cue, seconds, gain), offsetSeconds, cue, built, startAt)
        later?.let { current?.pending = it }
        return true
    }

    /** Nhịp đồng bộ của bài P3 ([SeamClock.gate]): Nối dựng xong thì nối vào hàng; hỏng / không kịp trước khi hết Clip đầu thì rơi về a87. */
    private fun seamTick(appContext: Context) {
        val bed = current ?: return
        val built = bed.built ?: return
        val player = bed.player
        when (SeamClock.gate(built.state, bed.attached, SeamClock.clip0RemainingMs(built.seam, player.currentMediaItemIndex, player.currentPosition))) {
            SeamClock.Gate.ATTACH -> attachSeam(bed)
            SeamClock.Gate.DEMOTE -> demote(appContext, bed, SeamClock.demoteReason(built.state), reject = false)
            else -> {}
        }
    }

    /** Nối Nối + Clip lặp vào hàng phát của bài P3 (hàng đang chỉ có Clip đầu) và giữ hàng gọn khi các vòng trôi qua ([SeamClock.stale]). */
    @OptIn(UnstableApi::class)
    private fun attachSeam(bed: Bed) {
        val built = bed.built ?: return
        if (bed.attached) return
        bed.attached = true
        val player = bed.player
        player.addMediaItems(LoopSeam.mediaItems(built.seam).drop(1))
        bed.listeners += LoopSeam.attach(player, built.seam)
        val trim = object : Player.Listener {
            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                SeamClock.stale(player.currentMediaItemIndex)?.let { player.removeMediaItems(it.first, it.last + 1) }
            }
        }
        bed.listeners += trim
        player.addListener(trim)
        emit { SeamEvents.attach(bed.testK, player.mediaItemCount, built) }
    }

    /** Tua bài P3 tới `sinceSeconds` giây kể từ đầu mốc bằng [LoopSeam.seekToSample]; false khi chỗ ấy cần Nối / Clip lặp mà hàng chưa có (bài rơi về a87). */
    @OptIn(UnstableApi::class)
    private fun seamSeek(bed: Bed, sinceSeconds: Double): Boolean {
        val built = bed.built ?: return false
        return seamSeekTo(bed, SeamClock.target(built.seam, built.bounds, sinceSeconds), sinceSeconds)
    }

    /**
     * `onLand`: mẫu đáp thật của lần tua (lưới an toàn của Nối, [LoopSeam.seekToSample]), gọi ở luồng chính; chỉ lần chuyển a87 -> P3 dùng. Ngoài ra lưới an toàn chỉ chạy khi đang đo
     * (dòng `land`), không đổi quyết định nào.
     */
    @OptIn(UnstableApi::class)
    private fun seamSeekTo(bed: Bed, target: SeamClock.Target, sinceSeconds: Double, onLand: ((Long?) -> Unit)? = null): Boolean {
        val built = bed.built ?: return false
        val sink = bed.sink ?: return false
        if (target.index != 0 && !bed.attached) return false
        emit { SeamEvents.seek(bed.testK, sinceSeconds, target) }
        val k = bed.testK
        val landed: ((Long?) -> Unit)? = if (target.index % 2 == 1 && (onLand != null || testEvents != null)) {
            { sample ->
                main.post {
                    emit { SeamEvents.land(k, target.sample, sample) }
                    onLand?.invoke(sample)
                }
            }
        } else null
        LoopSeam.seekToSample(bed.player, sink, built.seam, target.index, target.sample, landed)
        return true
    }

    /** Vị trí nhạc (giây trong bài) của `bed`: bài P3 tính theo (mục, vị trí) của hàng phát ([SeamClock.trackSeconds]), bài a87 là vị trí của trình phát. */
    private fun positionOf(bed: Bed): Double =
        bed.built?.let { SeamClock.trackSeconds(it.seam, bed.player.currentMediaItemIndex, bed.player.currentPosition) } ?: (bed.player.currentPosition / 1000.0)

    /** Vị trí nhạc của bài đang kêu (giây trong bài), null khi im lặng - cho kiểm thử trên máy. */
    val trackPosition: Double? get() = current?.let(::positionOf)

    /**
     * Bài P3 `bed` rơi về a87 (Nối chưa kịp / hỏng / tua tới chỗ chưa có Nối): bài ấy mờ ra, trình phát a87 vào ở chỗ giọng đang tới ([startCue] không chọn P3 lần này). `reject`: Nối hỏng thật, bỏ cả phiên.
     * Mọi lý do đi cùng đường: a87 mở thẳng ở chỗ ấy ([SeamClock.legacyStart], `startAt` của [open]) chứ không từ giây 0 rồi mới tua lúc READY - lần tua ấy tạo AudioTrack thứ hai, trễ thêm
     * 50-86 ms (PLAN_loop §44.2). Chỗ tính lúc rơi về, không theo giây chương lúc READY: nhạc chậm hơn giọng đúng phần trễ mở trình phát.
     */
    private fun demote(appContext: Context, bed: Bed, reason: DemoteReason, reject: Boolean) {
        val built = bed.built ?: return
        val why = when (reason) {
            DemoteReason.LATE -> "Nối chưa dựng kịp trước loopEnd"
            DemoteReason.FAIL -> "dựng Nối lỗi"
            DemoteReason.SEEK -> "tua tới chỗ Nối chưa dựng xong"
            DemoteReason.ERROR -> "lỗi phát"
        }
        Log.w(TAG, "đường P3 rơi về a87: $why (${built.key})")
        emit { SeamEvents.demote(bed.testK, reason) }
        if (reject) seamPicker.reject(built, why)
        val cue = bed.cue
        if (current === bed && cue != null) {
            if (!startCue(appContext, cue, lastSeconds, lastSeconds - cue.start, allowSeam = false, startAt = SeamClock.legacyStart(built, cue, lastSeconds))) switchTo(null, gain, 0.0)
            // Chưa kịp / tua sớm (không phải hỏng): Nối vẫn dựng tiếp, xong thì P3 nhận lại ở ranh lặp kế.
            else if (!reject && built.state != SeamPicker.State.DEAD) current?.pending = built
        } else if (current === bed) {
            switchTo(null, gain, 0.0)
        }
    }

    /** Mốc `tail`: vòng cuối thì thôi lặp ([MusicCues.finalLoop]), bài chơi tới E là hết ([MusicCues.finished]). Bài đã hết trước
     *  hết mốc mà mốc kế bắt đầu đúng ở đó ([MusicCues.nextAfter]): mốc kế vào ngay, mờ vào như thường, không để quãng im. Không có mốc
     *  kế thì im tới hết mốc. */
    private fun finishTail(appContext: Context, seconds: Double) {
        val bed = current ?: return
        if (bed.built != null) return // bài P3 không bao giờ ở mốc `tail` (sync mở lại bằng a87)
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
        if (!startCue(appContext, next, seconds, 0.0)) return
        current?.early = true
    }

    /** Lặp mờ chéo: bài đang kêu tới loopEnd - X ([MusicCues.loopDue]) thì một ExoPlayer của chính bài vào từ loopStart, mờ chéo X giây; cái
     *  cũ mờ đi rồi nhả. Vòng cuối của mốc `tail` ([finishTail]), bài quá ngắn (lặp thường) và danh sách phát thì không. Giờ vào do [LoopHandoff] giữ
     *  ([loopHandoff]); đây là phần nhìn bài đang kêu. */
    private fun lookLoop(): LoopHandoff.Snapshot? {
        val bed = current ?: return null
        val cue = bed.cue ?: return null
        val player = bed.player
        if (bed.built != null) return null // bài P3 tự lặp trong hàng phát của nó
        if (handover != null) return null // đang chuyển sang P3 ([stepHandover]): ranh lặp này đã có người lo
        if (bed.final || lastSeconds >= cue.end || player.duration <= 0) return null
        return LoopHandoff.Snapshot(bed, boundsOf(cue, player), player.currentPosition / 1000.0, player.isPlaying)
    }

    /** Chỗ vào bản lặp `target` (giây trong bài): bài mp3 vào ở ranh khung gần chỗ ấy nhất ([ExactSeekMp3Extractor.frameBoundarySeconds]). */
    @OptIn(UnstableApi::class)
    private fun frameAligned(player: ExoPlayer, target: Double): Double {
        val format = player.audioFormat
        return MusicCues.frameAligned(target, format?.takeIf { it.sampleMimeType == MimeTypes.AUDIO_MPEG }?.sampleRate)
    }

    /** Bước 0: tạo SẴN bản lặp của vòng hiện tại - ExoPlayer đã `prepare()` và đứng ở loopStart, câm, `playWhenReady` false (đo thật máy tính: trình phát mới
     *  mất cả trăm mili giây mới có tiếng; tới hạn chỉ còn phát). Không có file bài / chưa có context thì null: tới hạn mở mới như trước. */
    private fun prepareLoop(snap: LoopHandoff.Snapshot): Bed? {
        val owner = snap.owner as Bed
        val cue = owner.cue ?: return null
        val appContext = context ?: return null
        val uri = uriFor(appContext, owner.track) ?: return null
        val fadeMs = Math.round(MusicCues.mix.loopCrossfadeSeconds * 1000)
        // Bài a87 mở vào giữa vòng mà Nối giờ đã dựng xong: bản tạo sẵn là trình phát P3 đứng ở đầu Nối (đón ranh lặp này, [promoteTo]).
        val later = owner.pending?.takeIf { SeamPicker.compatible(it, cue) && SeamClock.promote(it.state) == SeamClock.Promote.NOW }
        if (later != null) {
            return timed("lặp mờ chéo: tạo sẵn trình phát P3") {
                open(appContext, owner.track to uri, owner.goal, 0.0, cue, fadeMs, standby = true, built = later, forced = SeamClock.Target(1, 0))
            }
        }
        val startAt = frameAligned(owner.player, snap.bounds.loopStart)
        return timed("lặp mờ chéo: tạo sẵn trình phát") {
            open(appContext, owner.track to uri, owner.goal, 0.0, cue, fadeMs, startAt, Handoff(owner, snap.bounds), standby = true)
        }.also { it.at = startAt }
    }

    /** Vào bản lặp: bản mới (`ready`: đã tạo sẵn, hay mở mới) ở loopStart cộng phần trễ so với hạn ([MusicCues.loopStartAt]). */
    private fun enterLoop(snap: LoopHandoff.Snapshot, prepared: Bed?) {
        val bed = current ?: return
        val cue = bed.cue ?: return
        val player = bed.player
        val bounds = snap.bounds
        val appContext = context ?: return
        val uri = uriFor(appContext, bed.track) ?: return
        var ready = prepared
        if (ready?.built != null) {
            if (beginHandover(ready, bed, snap)) return
            release(ready) // không chuyển được (giọng đang dừng, sát hết Nối): a87 lặp mờ chéo như khi không có Nối
            ready = null
        }
        val fadeMs = Math.round(MusicCues.mix.loopCrossfadeSeconds * 1000)
        bed.fadeStep = maxOf(bed.volume, 0.01f) * STEP_MS / fadeMs
        fading += bed
        val startAt = frameAligned(player, MusicCues.loopStartAt(bounds, snap.position))
        val next = if (ready != null) {
            // Vào muộn: đặt lại chỗ; vẫn đúng loopStart thì không tua (khỏi đệm lại).
            if (abs(ready.at - startAt) > 0.0005) {
                ready.player.seekTo((startAt * 1000).toLong())
                ready.at = startAt
            }
            ready.cue = cue
            ready.goal = bed.goal
            ready.perTick = bed.goal * STEP_MS / ready.fadeMs
            if (playing) ready.player.play()
            ready
        } else {
            timed("lặp mờ chéo: mở trình phát mới") { open(appContext, bed.track to uri, bed.goal, 0.0, cue, fadeMs, startAt, Handoff(bed, bounds)) }
        }
        current = next.also {
            it.early = bed.early
            it.pending = bed.pending // Nối chưa xong ở ranh này: bản lặp a87 giữ phần chờ, ranh sau thử nhận lại
        }
        startFade()
    }

    /** Huỷ vé hẹn + bản lặp tạo sẵn ([loopHandoff]) và lần chuyển sang P3 đang diễn ra: tua, đổi bài, dừng. */
    private fun resetLoop() {
        cancelHandover()
        loopHandoff.reset()
    }

    /** Bỏ lần chuyển đang diễn ra, không ồn: nhả P3 câm. Bài a87 không bị đụng. */
    private fun cancelHandover() {
        val h = handover ?: return
        handover = null
        main.removeCallbacks(handoverTick)
        release(h.p3)
    }

    /** Lần chuyển hỏng / không kịp: nhả P3, a87 vào bản lặp mờ chéo của nó như khi không có Nối (ranh lặp này vẫn đang tới hạn). */
    private fun abortHandover(reason: DemoteReason) {
        val h = handover ?: return
        Log.w(TAG, "chuyển a87 sang P3 không kịp / hỏng (${reason.word}), a87 lặp mờ chéo")
        emit { SeamEvents.demote(h.p3.testK, reason) }
        cancelHandover()
        loopHandoff.check()
    }

    private val handoverTick = Runnable { stepHandover() }

    /**
     * a87 -> P3 ở ranh lặp ([SeamHandover]): `old` (a87) đang ở đầu Nối, `ready` là trình phát P3 tạo sẵn đứng ở đầu Nối. a87 KHÔNG đổi gì (vẫn kêu, âm lượng cũ); P3 khởi động CÂM ở chỗ a87 sẽ ở khi P3 ra loa
     * ([stepHandover] tua + phát, đo pha theo AudioTrack, đổi tiếng khi khớp). False = không bắt đầu được, `ready` do người gọi nhả.
     */
    private fun beginHandover(ready: Bed, old: Bed, snap: LoopHandoff.Snapshot): Boolean {
        val built = ready.built ?: return false
        if (!playing) return false
        if (SeamHandover.target(built.seam, snap.position, p3LagMs) == null) {
            Log.w(TAG, "chuyển a87 sang P3 không kịp: a87 sát hết Nối")
            emit { SeamEvents.demote(ready.testK, DemoteReason.LATE) }
            return false
        }
        handover = Handover(ready, old, SystemClock.elapsedRealtime(), p3LagMs)
        emit { SeamEvents.promote(ready.testK, snap.position) }
        main.post(handoverTick)
        return true
    }

    /** Tua P3 tới chỗ a87 sẽ ở sau `h.lag` ms rồi phát (câm); false khi không còn chỗ trong Nối / tua không được. Các lần đọc pha trước đó bỏ hết (nói về AudioTrack cũ). */
    private fun issueHandover(h: Handover, legacySeconds: Double): Boolean {
        val p3 = h.p3
        val seam = p3.built?.seam ?: return false
        val target = SeamHandover.target(seam, legacySeconds, h.lag) ?: return false
        h.targetSample = target.sample
        h.issuedNano = System.nanoTime()
        h.readings.clear()
        h.landing = SeamHandover.Landing.Pending
        h.shifted.clear() // lần xả của lần tua này bỏ mọi dịch (cả lệnh chưa áp) ở sink
        h.shiftPending = false
        h.seekPhase = null
        val seek = ++h.seeks
        if (!h.issued) setVolume(p3, 0f) // P3 câm tới lúc đổi tiếng
        // Lưới an toàn: mẫu đáp thật của lần tua này; kết quả của lần tua cũ (đã tua lại) hay của lần chuyển đã xong / bỏ thì không tính.
        val onLand: (Long?) -> Unit = { landed ->
            if (handover === h && h.seeks == seek) h.landing = SeamHandover.Landing.of(landed)
        }
        if (!seamSeekTo(p3, target, lastSeconds - (h.old.cue?.start ?: 0.0), onLand)) return false
        h.issued = true
        p3.player.play()
        return true
    }

    /** Timestamp phần cứng của AudioTrack hiện tại của `ref` cùng mốc xả của nó; null khi chưa có AudioTrack / máy không cho timestamp. Tin hay không do [SeamHandover] quyết. */
    private fun stampOf(ref: TrackRef?): SeamHandover.Stamp? {
        ref ?: return null
        val flushed = ref.flushedNano
        val track = ref.track ?: return null
        val stamp = AudioTimestamp()
        val ok = try { track.getTimestamp(stamp) } catch (_: IllegalStateException) { false }
        return if (ok) SeamHandover.Stamp(stamp.framePosition, stamp.nanoTime, track.sampleRate, flushed) else null
    }

    /** Vị trí a87 (giây trong bài) đo như P3 ([SeamHandover.legacySeconds]); AudioTrack của nó không cho timestamp (bài mở trước khi bật P3, máy không hỗ trợ) thì currentPosition. */
    private fun legacyPosition(bed: Bed): Double {
        val ref = bed.trackRef
        val start = ref?.startUs ?: C.TIME_UNSET
        if (start != C.TIME_UNSET) stampOf(ref)?.let { stamp ->
            val seconds = SeamHandover.legacySeconds(start, stamp, System.nanoTime())
            if (seconds != null && ref?.startUs == start) return seconds
        }
        return bed.player.currentPosition / 1000.0
    }

    /** Một nhịp ([SeamHandover.POLL_MS]) của lần chuyển sang P3: tua + phát P3 câm khi P3 sẵn sàng, đo pha khi AudioTrack P3 chạy, rồi đổi tiếng / tua lại / bỏ ([SeamHandover.decide]). */
    private fun stepHandover() {
        val h = handover ?: return
        val old = h.old
        val p3 = h.p3
        val seam = p3.built?.seam
        if (seam == null || current !== old || old.released || !playing) {
            cancelHandover()
            return
        }
        val a87 = legacyPosition(old)
        val elapsed = SystemClock.elapsedRealtime() - h.startedAt
        if (!h.issued) {
            if (elapsed >= SeamHandover.DEADLINE_MS) return abortHandover(DemoteReason.LATE)
            if (p3.player.playbackState == Player.STATE_READY && !issueHandover(h, a87)) return abortHandover(DemoteReason.LATE)
            main.postDelayed(handoverTick, SeamHandover.POLL_MS)
            return
        }
        // Pha theo AudioTrack MỚI của P3 (sinh sau lần tua cuối, đã phát >= SETTLE_MS) và theo MẪU ĐÁP thật của lần tua (lưới an toàn); thiếu một trong hai thì nhịp này không có lần đọc.
        // Có dịch trong dòng: chờ sink báo áp xong, rồi chờ AudioTrack phát qua chỗ dịch + khung chèn + SETTLE_MS; vị trí P3 trừ khung lặng / cộng khung bỏ đã ra loa.
        val now = System.nanoTime()
        val stamp = stampOf(p3.trackRef)
        val landing = h.landing
        val delta = if (h.shiftPending) null else stamp?.let { SeamHandover.landedReading(seam, landing, h.issuedNano, it, now, a87, h.shifted) }
        if (delta != null && stamp != null) {
            h.readings += delta
            emit { SeamEvents.handoverReading(p3.testK, delta, SeamHandover.played(seam, stamp, now) * 1000.0 / seam.sampleRate) }
        }
        val settled = SeamHandover.settled(h.readings)
        if (settled != null && h.shifted.isEmpty() && h.seekPhase == null) h.seekPhase = SeamHandover.lagPhase(seam, h.targetSample, landing, settled)
        if (settled != null && !h.learned) {
            // trễ khởi động đo ở lần khởi động nguội đầu tiên (pha đã ổn định, trước mọi dịch trong dòng): dùng cho các ranh sau. Dịch trong dòng không bao giờ cộng vào trễ.
            h.learned = true
            p3LagMs = SeamHandover.nextLag(h.lag, SeamHandover.lagPhase(seam, h.targetSample, landing, settled))
        }
        // Nhịp không có lần đọc mới thì chỉ xét hạn chót: không đổi tiếng / tua theo số cũ. Lần tua không tìm thấy mẫu đáp: tua lại ngay.
        val counted = if (delta != null) h.readings else emptyList()
        when (SeamHandover.decide(elapsed, SeamHandover.remainingMs(seam, a87), h.retunes, counted, landing, muted = p3.volume == 0f, shifts = h.shifts)) {
            SeamHandover.Act.SWITCH -> return completeHandover(h, a87, a87 + delta!! / 1000.0)
            SeamHandover.Act.FALLBACK -> return abortHandover(DemoteReason.LATE)
            SeamHandover.Act.RETUNE -> {
                h.retunes++
                // Tua lại = AudioTrack mới: sửa trễ theo pha của lần tua này TRƯỚC các dịch (pha sau dịch chỉ là phần dư của AudioTrack cũ).
                h.lag = SeamHandover.nextLag(h.lag, h.seekPhase ?: SeamHandover.lagPhase(seam, h.targetSample, landing, settled ?: 0.0))
                if (!issueHandover(h, a87)) return abortHandover(DemoteReason.LATE)
            }
            SeamHandover.Act.SHIFT -> if (!shiftHandover(h, settled!!)) return abortHandover(DemoteReason.LATE)
            SeamHandover.Act.WAIT -> {}
        }
        main.postDelayed(handoverTick, SeamHandover.POLL_MS)
    }

    /**
     * Dịch pha P3 (câm, đã đáp đúng) TRONG DÒNG thay vì tua lại ([SeamHandover.Act.SHIFT]): pha `settledMs` > 0 thì chèn K khung lặng, < 0 thì bỏ |K| khung ([SeamHandover.shiftFrames]).
     * Các lần đọc bắt đầu lại; tới khi sink báo đã áp (luồng phát -> luồng chính) không lần đọc nào tính. Báo của lần tua cũ (đã tua lại) hay của lần chuyển đã xong / bỏ thì bỏ qua.
     * False = không dịch được (không có sink của P3).
     */
    private fun shiftHandover(h: Handover, settledMs: Double): Boolean {
        val p3 = h.p3
        val seam = p3.built?.seam ?: return false
        val sink = p3.sink ?: return false
        val frames = SeamHandover.shiftFrames(seam, settledMs)
        h.shifts++
        h.readings.clear()
        h.shiftPending = true
        val seek = h.seeks
        emit { SeamEvents.shift(p3.testK, frames, settledMs) }
        sink.shift(frames) { applied ->
            main.post {
                if (handover === h && h.seeks == seek && h.shiftPending) {
                    h.shifted += applied
                    h.shiftPending = false
                }
            }
        }
        return true
    }

    /** Pha đã khớp, P3 đang kêu câm: P3 lên âm lượng của a87 và a87 về 0 trong cùng một lần (cùng nội dung, lệch <= [SeamHandover.TOLERANCE_MS] nên không chồng nghe ra); a87 nhả ở nhịp mờ kế. */
    private fun completeHandover(h: Handover, a87: Double, p3Seconds: Double) {
        handover = null
        val p3 = h.p3
        val old = h.old
        p3.cue = old.cue
        p3.goal = old.goal
        p3.perTick = old.perTick
        p3.entering = old.entering
        setVolume(p3, old.volume) // mức logic: hệ số hẹn giờ ngủ do setVolume nhân một lần ở p3
        setVolume(old, 0f)
        old.fadeStep = 0.001f
        fading += old
        current = p3.also { it.early = old.early }
        emit { SeamEvents.handover(p3.testK, a87, p3Seconds) }
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
                setVolume(bed, goal)
                return
            }
            else -> bed.perTick = abs(goal - bed.volume) * STEP_MS / MusicCues.mix.stepRampMs
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
        seamPicker.clear()
        catalogRetry?.let(main::removeCallbacks)
        catalogRetry = null
        sceneRetry?.let(main::removeCallbacks)
        sceneRetry = null
        resetLoop()
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
            // Sách mang theo đúng các bài người nghe đã chọn (file nằm trong sách): phát bản của cuốn, không giải lại từ kho của máy này.
            BookEdits.carriedMine(Store.bookDir(book))?.let { carried ->
                val found = carried.infos.mapValues { (link, info) -> info.put("path", carried.files.getValue(link).path) }
                return Resolved(Playlists.queue(found.keys.toList(), found, levelDb), found, false)
            }
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
        if (link.startsWith(MusicStore.LOCAL_PREFIX)) {
            infos[link]?.optString("path")?.takeIf { it.isNotEmpty() }?.let(::File)?.takeIf { it.isFile }?.let { return Uri.fromFile(it) } // bài sách mang theo
            return DeviceMusic.store(appContext).file(link)?.let { Uri.fromFile(it) }
        }
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
        if (sceneMode) uriOf(appContext, track) else Streaming.chapterUri(appContext, book, track)

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
    private fun switchTo(next: Pair<String, Uri>?, targetGain: Float, offsetSeconds: Double, cue: MusicCues.Cue? = null, built: SeamPicker.Built? = null, startAt: Double? = null) {
        resetLoop()
        val mix = MusicCues.mix
        val fadeMs = if (cue?.sibling == true) mix.siblingFadeMs else mix.fadeMs
        current?.let {
            var oldFadeMs = fadeMs
            if (cue?.sibling == true) {
                it.player.repeatMode = Player.REPEAT_MODE_OFF
                val was = it.cue
                if (was != null && it.player.duration > 0) {
                    oldFadeMs = Math.round(MusicCues.siblingFadeSeconds(it.built?.bounds ?: boundsOf(was, it.player), positionOf(it)) * 1000)
                }
            }
            it.fadeStep = maxOf(it.volume, 0.01f) * STEP_MS / oldFadeMs
            fading += it
        }
        current = null
        val appContext = context ?: return
        if (next != null) current = open(appContext, next, targetGain, offsetSeconds, cue, fadeMs, startAt = startAt, built = built)
        startFade()
    }

    /** Một ExoPlayer mới cho bài `next`, mờ vào tới `targetGain` trong `fadeMs`. `startAt` (giây trong bài): vào đúng chỗ ấy từ `setMediaItem`, lúc READY không tua lại.
     *  Dùng cho phần tử lặp (A: không căn theo giây chương - đồng hồ bài lệch giọng vài phần giây thì căn lại có khi rơi về cuối vòng) và cho a87 khi bài P3 rơi về
     *  ([demote]: chỗ giọng đang tới theo bản đồ khai báo, đỡ một lần tua = một AudioTrack). */
    @OptIn(UnstableApi::class)
    private fun open(appContext: Context, next: Pair<String, Uri>, targetGain: Float, offsetSeconds: Double, cue: MusicCues.Cue?,
                     fadeMs: Long, startAt: Double? = null, handoff: Handoff? = null, standby: Boolean = false, built: SeamPicker.Built? = null, forced: SeamClock.Target? = null): Bed {
        val (track, uri) = next
        // Bộ giải mã đồng bộ: chế độ hàng đợi bất đồng bộ (mặc định Android 12+) tắt luồng gọi lại của MediaCodec trước khi nhả codec - mỗi lần nhả một bài
        // (lặp mờ chéo ~40 lần / 5 phút) codec còn gửi sự kiện tới luồng đã chết ("sending message to a Handler on a dead thread", soát a69: 360 lần / 40 phút).
        // Đường P3 (`built`): sink bọc LoopSink (việc cắt mẫu của Nối) + nguồn media của LoopSeam; còn lại như nhau.
        var loopSink: LoopSeam.LoopSink? = null
        val k = testPlayerSeq++
        testCreating = k
        val trackRef = TrackRef()
        // Cờ P3 bật thì cả bài a87 cũng giữ AudioTrack + mốc của nó ([TrackRef]): lúc chuyển sang P3, vị trí a87 đo cùng cách với P3 ([legacyPosition]). Cờ tắt: renderers mặc định như cũ.
        val renderers = if (built == null && testAudioProcessor == null && testEvents == null && !musicSeamP3) {
            DefaultRenderersFactory(appContext).forceDisableMediaCodecAsynchronousQueueing()
        } else {
            hookedRenderers(appContext, k, seam = built != null, trackRef) { loopSink = it }
        }
        val sourceFactory = Streaming.mediaSourceFactory(appContext, exactMp3Seek = true)
        val player = ExoPlayer.Builder(appContext, renderers)
            .setAudioAttributes(
                AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MUSIC).build(),
                false,
            )
            .setMediaSourceFactory(if (built == null) sourceFactory else LoopSeam.mediaSourceFactory(sourceFactory))
            // media3 1.11 bật dynamic scheduling mặc định: luồng phát chỉ thức khi bộ đệm cần, currentPosition đứng yên rồi nhảy ~250 ms -
            // hẹn giờ lặp đọc vị trí ấy nên lệch tới chừng đó. Tắt đi, bước vị trí còn 10-40 ms (đo trên máy 22-10, PLAN_loop §37.1).
            .experimentalSetDynamicSchedulingEnabled(false)
            .build()
        if (built == null) player.repeatMode = Player.REPEAT_MODE_ONE // biết độ dài bài (STATE_READY) mới biết lặp mờ chéo hay lặp thường; bài P3 tự lặp trong hàng phát
        player.volume = 0f
        val offsetMs = (offsetSeconds.coerceAtLeast(0.0) * 1000).toLong()
        val bed = Bed(track, player, targetGain, targetGain * STEP_MS / fadeMs, cue, fadeMs)
        bed.built = built
        bed.sink = loopSink
        bed.trackRef = trackRef
        bed.forcedTarget = forced
        bed.testK = k
        emit { SeamEvents.open(k, built != null, track) }
        if (built != null) emit { SeamEvents.plan(k, built.seam) }
        emit { SeamEvents.volume(k, 0f) } // player.volume = 0f ở trên
        if (testEvents != null) player.addListener(object : Player.Listener {
            // Móc đo: mỗi lần chuyển mục của trình phát (hàng P3: 0 = Clip đầu, lẻ = Nối, chẵn >= 2 = Clip lặp; a87 chỉ một mục).
            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                emit { SeamEvents.item(k, player.currentMediaItemIndex, reason, if (built != null) SeamEvents.kindOf(player.currentMediaItemIndex) else "a87") }
            }
        }.also { bed.listeners += it })
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
                    if (built != null) {
                        // Như đường a87 bên dưới: theo giây mới nhất của chương; vào ở đầu mốc (Clip đầu, mẫu 0) thì không tua.
                        val mine = bed.cue
                        val since = if (mine != null && current === bed) lastSeconds - mine.start else offsetSeconds
                        val target = bed.forcedTarget ?: SeamClock.target(built.seam, built.bounds, since)
                        if ((target.index != 0 || target.sample != 0L) && !seamSeekTo(bed, target, since)) demote(appContext, bed, DemoteReason.SEEK, reject = false)
                        return
                    }
                    val duration = player.duration
                    player.repeatMode = repeatFor(bed.cue, player, bed.final)
                    // Nhạc của sách tải xong sau khi giọng đã chạy tiếp (hay vừa tua): theo giây mới nhất của chương (soát a26 L8). Mở với `startAt` thì đã đứng đúng chỗ: không tua.
                    val mine = bed.cue
                    val latest = if (mine != null && current === bed) MusicCues.offsetMs(mine, lastSeconds, duration) else null
                    MusicCues.readySeekMs(startAt, duration, latest, offsetMs)?.let(player::seekTo)
                }
            }
        })
        watchPlaying(bed)
        if (handoff != null && LOOP_SETTLE) listen(object : Player.Listener {
            // Bản lặp mới vừa có tiếng (STATE_READY + playWhenReady): bù độ trễ mở trình phát, một lần. Nó gần như câm nên cú dời không nghe thấy.
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                if (!isPlaying) return
                player.removeListener(this)
                bed.listeners.remove(this)
                val old = handoff.old
                val to = MusicCues.loopSettle(handoff.bounds, old.player.currentPosition / 1000.0, player.currentPosition / 1000.0, bed.volume, bed.goal,
                    oldAlive = old in fading && old.player.isPlaying)
                if (to != null) player.seekTo((to * 1000).toLong())
            }
        })
        listen(object : Player.Listener {
            // Nhạc của sách hỏng (file thiếu trong gói, mạng tới máy tính rớt khi nghe thẳng): đoạn này im lặng, RETRY_MS sau thử
            // lại như máy tính. Bài của danh sách phát phát hỏng (file hỏng) thì bỏ cả phiên - tải hỏng đã có fetch lo.
            override fun onPlayerError(error: PlaybackException) {
                main.post {
                    if (bed.released) return@post // đã nhả (bản tạo sẵn bị bỏ, bài mờ xong): lỗi muộn không tính là bài hỏng
                    if (bed.built != null && handover?.p3 === bed) { // P3 hỏng khi đang khởi động câm: bỏ Nối này, a87 lặp mờ chéo
                        seamPicker.reject(bed.built!!, "lỗi phát ${error.errorCodeName}")
                        abortHandover(DemoteReason.ERROR)
                        return@post
                    }
                    if (loopHandoff.prepared() === bed && bed.built != null) { // bản P3 tạo sẵn hỏng trước khi dùng: bỏ Nối này, bài ở lại a87
                        seamPicker.reject(bed.built!!, "lỗi phát ${error.errorCodeName}")
                        loopHandoff.discardReady()
                        return@post
                    }
                    if (bed.built != null) {
                        // Đường P3 hỏng giữa chừng (Nối / Clip không phát được): bỏ Nối này cả phiên, bài phát tiếp bằng a87 ở chỗ giọng đang tới - không im lặng, không văng.
                        if (current === bed) demote(appContext, bed, DemoteReason.ERROR, reject = true)
                        else { seamPicker.reject(bed.built!!, "lỗi phát ${error.errorCodeName}"); release(bed); fading.removeAll { it === bed } }
                        return@post
                    }
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
        if (built != null) {
            // Chỉ Clip đầu: phát ngay, không chờ Nối. Nối + Clip lặp nối vào khi dựng xong ([seamTick] -> [attachSeam]).
            player.setMediaItem(LoopSeam.mediaItems(built.seam).first())
            if (built.state == SeamPicker.State.READY) attachSeam(bed)
        } else if (startAt != null) player.setMediaItem(MediaItem.fromUri(uri), (startAt * 1000).toLong())
        else player.setMediaItem(MediaItem.fromUri(uri))
        player.prepare()
        if (playing && !standby) player.play()
        return bed
    }

    /** MÓC ĐO ([testAudioProcessor], [testEvents]) và cờ P3: như renderers mặc định, thêm bộ xử lý đo CUỐI chuỗi, dòng `audiotrack`, [TrackedSink] (mốc AudioTrack); `seam`: bọc [LoopSeam.LoopSink] (đường P3). */
    @OptIn(UnstableApi::class)
    @Suppress("DEPRECATION") // AudioTrackProvider: chỉ để đo, như MusicLoopSeamTest
    private fun hookedRenderers(appContext: Context, k: Int, seam: Boolean, trackRef: TrackRef, onSink: (LoopSeam.LoopSink) -> Unit): DefaultRenderersFactory =
        object : DefaultRenderersFactory(appContext) {
            override fun buildAudioSink(context: Context, enableFloatOutput: Boolean, enableAudioTrackPlaybackParams: Boolean): AudioSink {
                val builder = DefaultAudioSink.Builder(context)
                    .setEnableFloatOutput(enableFloatOutput)
                    .setEnableAudioOutputPlaybackParameters(enableAudioTrackPlaybackParams)
                testAudioProcessor?.let { builder.setAudioProcessors(arrayOf(it())) }
                // Cờ P3 bật: mọi bài giữ AudioTrack mới nhất (đo pha lúc chuyển a87 -> P3, [stepHandover]); cờ tắt thì chỉ khi đang đo.
                if (testEvents != null || seam || musicSeamP3) builder.setAudioTrackProvider(object : DefaultAudioSink.AudioTrackProvider {
                    override fun getAudioTrack(config: AudioSink.AudioTrackConfig, attributes: AudioAttributes, audioSessionId: Int, context: Context?) =
                        DefaultAudioSink.AudioTrackProvider.DEFAULT.getAudioTrack(config, attributes, audioSessionId, context).also {
                            trackRef.created(it)
                            if (testEvents != null) testTracks[k] = it
                            emit { SeamEvents.audioTrack(k, it.sampleRate, it.channelCount) }
                        }

                    override fun getAudioTrackChannelConfig(channelCount: Int) = DefaultAudioSink.AudioTrackProvider.DEFAULT.getAudioTrackChannelConfig(channelCount)
                })
                // Móc đo: xả thì bỏ AudioTrack cũ khỏi testTracks - nó còn chạy vài ms sau lần tua, timestamp của nó lọt vào thước pha thì P3 sai ~10 ms (bed44thu, vòng 7).
                val base = TrackedSink(builder.build(), trackRef) { if (testEvents != null) testTracks.remove(k) }
                return if (seam) LoopSeam.LoopSink(base).also(onSink) else base
            }
        }.forceDisableMediaCodecAsynchronousQueueing()

    /** Đặt âm lượng trình phát của `bed` (mọi chỗ MusicBed đổi volume đi qua đây); móc đo ghi `vol <k> <v>` mỗi lần, kể cả từng nhịp mờ. */
    private fun setVolume(bed: Bed, volume: Float) {
        bed.volume = volume
        bed.player.volume = volume * sleepFactor
        emit { SeamEvents.volume(bed.testK, volume) }
    }

    /** Hệ số mờ dần của hẹn giờ ngủ (1 = không mờ), nhân vào âm lượng THẬT của mọi bài nhạc nền, một chỗ duy nhất ([setVolume]); mức logic không đổi nên mờ vào / mờ đi / chuyển Nối chạy như cũ. */
    @Volatile
    private var sleepFactor = 1f

    /** Hẹn giờ ngủ ([Playback.applyVolume]) đổi hệ số mờ: áp ngay cho bài đang kêu và các bài đang mờ đi (kể cả đang mờ chéo); 1 = trả về mức cũ. */
    fun setSleepFade(factor: Float) {
        val to = factor.coerceIn(0f, 1f)
        main.post {
            sleepFactor = to
            current?.let { it.player.volume = it.volume * to }
            for (bed in fading) bed.player.volume = bed.volume * to
            handover?.p3?.let { it.player.volume = it.volume * to }
        }
    }

    /** Một nhịp mờ ([STEP_MS]) của bài đang kêu (mờ vào / trượt bước âm lượng) và các bài đang mờ đi; còn việc thì hẹn nhịp kế. */
    private val fadeTick: Runnable = object : Runnable {
        override fun run() {
            var busy = false
            current?.let { bed ->
                val player = bed.player
                // Bài còn tải / đệm thì chưa mờ vào: để lúc có tiếng mới nhích từ 0 lên, không nhảy thẳng tới mức (soát B3).
                val ready = player.playbackState.let { it == Player.STATE_READY || it == Player.STATE_ENDED }
                setVolume(bed, MusicCues.towardWhenReady(bed.volume, bed.goal, bed.perTick, ready))
                if (ready && abs(bed.volume - bed.goal) < 1e-4f) bed.entering = false else busy = true
            }
            val iterator = fading.iterator()
            while (iterator.hasNext()) {
                val bed = iterator.next()
                setVolume(bed, maxOf(0f, bed.volume - bed.fadeStep))
                if (bed.volume <= 0.001f) {
                    release(bed)
                    iterator.remove()
                } else {
                    busy = true
                }
            }
            if (busy) main.postDelayed(this, STEP_MS) else fadingTicker = false
        }
    }

    private fun startFade() {
        if (fadingTicker) return
        fadingTicker = true
        main.post(fadeTick)
    }

    /**
     * Chạy NGAY một nhịp mờ và đặt lại pha của ticker từ lúc này (bỏ nhịp đang hẹn): bài đang mờ vào vừa thật sự chạy ([watchPlaying]) thì nhích khỏi 0 luôn, không chờ tới nhịp
     * [STEP_MS] kế (trễ thêm 0-50 ms, đo 24-76 ms ở PLAN_loop §44.2). Bước mờ không đổi, chỉ đổi lúc bắt đầu. Các bài đang mờ đi đi cùng ticker nên nhịp ấy của chúng có thể sớm vài ms.
     */
    private fun kickFade() {
        main.removeCallbacks(fadeTick)
        fadingTicker = true
        main.post(fadeTick)
    }

    /**
     * Bài `bed` đang là bài kêu và còn mờ vào mà trình phát báo bắt đầu chạy ([Player.Listener.onIsPlayingChanged]): [kickFade]. Mọi bài mờ vào (a87, P3) đều nghe; bản P3 khởi động câm lúc chuyển
     * a87 -> P3 chưa phải bài kêu nên không ảnh hưởng. Dùng isPlaying (có cả khi cờ P3 tắt, renderers mặc định) thay vì AudioTrack ([TrackRef] chỉ có khi cờ P3 bật / đang đo).
     */
    private fun watchPlaying(bed: Bed) {
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                if (isPlaying && current === bed && bed.entering && !bed.released) kickFade()
            }
        }
        bed.listeners += listener
        bed.player.addListener(listener)
    }
}
