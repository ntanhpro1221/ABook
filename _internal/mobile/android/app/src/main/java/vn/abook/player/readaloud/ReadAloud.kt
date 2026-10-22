package vn.abook.player.readaloud

import android.content.Context
import android.net.Uri
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.Artwork
import vn.abook.player.BookEdits
import vn.abook.player.EditsSync
import vn.abook.player.Playback
import vn.abook.player.SleepTimer
import vn.abook.player.Store
import vn.abook.player.Streaming
import vn.abook.player.SyncLink
import vn.abook.player.mediaArtist
import vn.abook.player.vieneu.VieneuVoices
import java.io.File
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors

/**
 * "Nghe ngay" cho chương CHỈ CÓ CHỮ (docs/LISTEN_ANYTHING.md mục 1 và 3): một giọng máy đọc chương, không phân tích. Sống trong lõi phát (như chương audio) vì
 * tắt màn hình thì WebView bị treo - sang đoạn kế, sang chương kế, hẹn giờ ngủ, nút tai nghe, lưu vị trí đều phải chạy không cần JavaScript.
 *
 * Cách làm: chương chia thành các đoạn ([Paragraphs.of], đúng như màn đọc), mỗi đoạn một đoạn âm thanh ([Clip]) do [ClipReader] đọc ở luồng nền. Chỉ đọc đoạn đang
 * nghe + [AHEAD] đoạn sau (giọng trực tuyến mà clip về chậm thì nhiều hơn - [ReadAheadPolicy]); đoạn nào xong thì nối thêm vào hàng đợi của ExoPlayer (một MediaItem mỗi đoạn, `mediaId` = mã chương, `tag` = [Slot]) nên chuyển đoạn
 * liền mạch, và sang chương kế cũng chỉ là nối tiếp đoạn. Chương audio xen giữa (sách nửa chữ nửa tiếng) nối vào cùng hàng đợi. Giao diện thấy MỘT đồng hồ
 * chương ([VirtualTimeline]): vị trí = mốc đầu đoạn + vị trí trong đoạn.
 *
 * Mọi trạng thái chỉ đụng ở luồng chính; luồng nền chỉ đọc đoạn rồi `Playback.onMain` trả kết quả. Mỗi lần nhảy (tua, đổi chương, đổi giọng) tăng `generation`: kết
 * quả của việc cũ tới muộn bị bỏ.
 */
object ReadAloud {
    const val DEFAULT_VOICE = "edge:vi-VN-HoaiMyNeural"
    /** Giới của [DEFAULT_VOICE]: giọng VieNeu mặc định khi bản vừa tải không có giọng ưu tiên nào thì cùng giới này ([NarratorVoice]). */
    const val DEFAULT_VOICE_GENDER = "female"
    /** Đoạn đọc trước: đang nghe + chừng này đoạn sau (tối thiểu; giọng trực tuyến chậm thì dài ra - [policy]). */
    const val AHEAD = 2
    /** Nghỉ trước mỗi lần thử lại một đoạn hỏng vì lỗi thoáng qua của giọng trực tuyến (ms), ở luồng nền - đoạn đã nạp vẫn phát. [EdgeTts] đã tự thử lại lượt bị cắt 3 lần (nghỉ 6 giây) bên
     *  trong mỗi lần, nên chỉ thêm hai lần ngoài này (nghỉ 7 giây). Số lần chỉ là trần: các lần nghỉ cộng thời gian chờ thật của mỗi lần còn bị chặn bởi quỹ [ClipBudget.BUDGET_MS] (20 giây
     *  kể từ lần đọc đầu, cho cả hai tầng) - mạng còn nối mà im lìm thì rơi sang giọng của máy sau ~15-20 giây, không phải cả phút. Máy tính nghỉ 1 + 2,5 + 4,5 + 7 giây, cùng quỹ (listen/readAloud.ts). */
    val RETRY_DELAYS_MS = longArrayOf(2_000L, 5_000L)

    /** Gắn vào MediaItem của một đoạn: chương (vị trí trong danh sách chương), đoạn, độ to của giọng đã đọc, và đoạn ấy có DÀI không (từ [EdgePieces.WHOLE_CHARS] ký tự - chỉ đoạn dài tính vào rank
     *  của đoạn sau nó, [StalledClips.listenerRank]). `segment` -1 = không dùng. `baseMs` > 0 (uxfix58): mục này là phần nối sau phần đã về của một clip phát luồng đứt giữa chừng, nằm ở mục ExoPlayer
     *  trước nó - vị trí trong mục này cộng `baseMs` mới là chỗ trong đoạn ([Clip.baseMs]). */
    class Slot(val chapterIndex: Int, val segment: Int, val gainDb: Double, val long: Boolean = false, val baseMs: Long = 0)

    private class Chap(val index: Int, val parsed: List<Paragraphs.Paragraph>) {
        val paragraphs: List<String> = parsed.map { it.text }
        /** Quãng lặng (ms) của từng dòng ngăn cảnh ([Paragraphs.sceneBreakGaps]); đoạn thường 0. */
        val gaps: IntArray = Paragraphs.sceneBreakGaps(parsed)
        // Dòng ngăn cảnh có độ dài cố định ngay từ đầu (lặng, không đọc): quãng lặng, hay 0 nếu không đáng (đầu / cuối chương, dòng thứ hai liền nhau).
        val timeline = VirtualTimeline(IntArray(paragraphs.size) { paragraphs[it].length }).also { line ->
            parsed.forEachIndexed { i, paragraph -> if (paragraph.sceneBreak) line.setDuration(i, gaps[i].toLong()) }
        }
        val clips = arrayOfNulls<Clip>(paragraphs.size)
        /** Mốc chữ TẠM của đoạn đang phát luồng ([LiveJob]): màn đọc tô chữ theo đó tới khi clip xong ([clips] thay vào). */
        val liveWords = arrayOfNulls<List<Span>>(paragraphs.size)
        fun isBreak(segment: Int): Boolean = parsed[segment].sceneBreak
    }

    /**
     * Một lượt đọc đoạn người nghe đang đứng chờ (rank 0, giọng Edge) mà ExoPlayer nhận NGAY khi byte tiếng đầu về ([LiveClips]; máy tính: MediaSource, uxfix56). Chỗ nhận của giọng ([LiveClips.Target]):
     * chạy ở luồng đọc, việc chạm trạng thái chuyển sang luồng chính. `tail` > 0: clip đuôi từ chữ ấy ([SeekPlan.tailFrom]). Chỉ phát luồng MỘT lần ([accepting]): lần thử lại sau khi đã phát (hay giọng
     * đỡ) đi đường thường và kết quả vào [onClipReady] như mọi đoạn.
     */
    private class LiveJob(val token: Int, val chap: Chap, val segment: Int, val voice: String, val resume: Resume? = null) : LiveClips.Target {
        val entry = LiveClips.create()
        @Volatile var started = false
            private set
        @Volatile var tail = 0
        /** Chỗ giọng đã báo mốc thật tới (luồng chính; [LiveClips.Target.words]). */
        var heardMs = 0L
        /** Đã đứt giữa chừng và [onLiveBroke] đã lo (nối tiếp hay báo lỗi): kết quả muộn của lượt đọc này bị bỏ. Luồng chính. */
        var broke = false
        /** Huỷ của lượt đọc (luồng đọc): đứt giữa chừng thì không thử lại nữa - phần tiếp đã thay nó. */
        @Volatile var cancel: ClipCancel? = null
        /** Chữ (đếm trong clip) tiếng sẽ dừng trước nó - một mảnh giữa clip đã hỏng hẳn ([LiveClips.Target.cut]); -1 khi chưa có. */
        @Volatile var cutWord = -1
        /** [onLiveCut] đã xin phần nối sớm cho lượt này. Luồng chính. */
        var cutHandled = false
        /** Tốc độ phát lúc xin (giọng trên máy, [LiveClips.Target.speed]). */
        @Volatile var speed = 1f
        /** Lúc người nghe hết tiếng trước đoạn này ([LiveClips.Target.reachNanos], [soundReachesNanos]). */
        @Volatile var reach = Long.MAX_VALUE

        override fun accepting() = !started

        override fun format(durationMs: (Long) -> Long) {
            entry.durationOf = durationMs
        }

        override fun speed() = speed

        override fun reachNanos() = reach

        override fun grew(file: File, total: Long) {
            entry.grew(file, total)
            if (!started) {
                started = true
                Playback.onMain { onLiveStarted(this) }
            }
        }

        override fun words(words: List<Span>, durationMs: Long, heardMs: Long) = Playback.onMain {
            this.heardMs = heardMs
            onLiveWords(this, words)
        }

        override fun done(total: Long) = entry.finish(total)

        override fun failed(error: Exception) {
            entry.fail(error)
            if (started) Playback.onMain { onLiveBroke(this, error) } // đã phát rồi mới hỏng: phần đã về phát hết, phần còn lại xin ngay
        }

        override fun cut(word: Int) {
            cutWord = word
            if (started) Playback.onMain { onLiveCut(this) } // chưa có byte đầu: [onLiveStarted] lo
        }

        /** Lượt đọc đã ra kết quả (luồng đọc): clip vào bộ đệm thì đổi chỗ file cho các lần mở sau; không thì clip đang phát dở hỏng, ExoPlayer thôi chờ. */
        fun finish(result: Result<Clip>) {
            if (!started) return
            val clip = result.getOrNull()
            when {
                clip != null && entry.done -> entry.relocate(clip.file)
                clip != null -> entry.fail(VoiceException("Đoạn đã đọc bằng giọng khác"))
                else -> entry.fail(result.exceptionOrNull() as? Exception ?: VoiceException("Không đọc được đoạn này"))
            }
        }
    }

    /**
     * Phần còn lại của một đoạn phát luồng đứt giữa chừng (uxfix58): đọc tiếp TỪ chữ `from` (clip đuôi, phát luồng như thường), file bắt đầu ở `baseMs` của đoạn (độ dài phần đã về, đã phát ở mục
     * ExoPlayer trước), `prefix` = mốc cả đoạn đã có của phần đã về ([SeekPlan.tailWords]).
     * Xin SỚM (uxfix63, [onLiveCut]): `head` = lượt phát luồng còn đang về mà một mảnh giữa của nó đã hỏng - `baseMs` / `prefix` chưa biết tới khi nó đóng ([settle]); trong lúc ấy phần nối đọc như thường
     * nhưng chưa vào ExoPlayer: byte đầu ([started]) và kết quả ([parked]) chờ tới lúc ấy. Tiếng dừng sớm hơn `from` (mảnh trước cũng hỏng): phần nối này bỏ ([stale]), xin lại.
     */
    private class Resume(val chap: Chap, val segment: Int, val from: Int, var baseMs: Long, var prefix: List<Span>, val head: LiveJob? = null) {
        var settled = head == null
        var stale = false
        /** Lượt phát luồng của phần nối đã có byte đầu khi phần đầu chưa đóng. */
        var started: LiveJob? = null
        /** Kết quả của lượt đọc phần nối về khi phần đầu chưa đóng. */
        var parked: (() -> Unit)? = null
        /** Huỷ lượt đọc phần nối ([stale]). */
        var cancel: ClipCancel? = null
    }

    /** Chỗ cần phát mà chưa có đoạn âm thanh để đặt vào ExoPlayer: đang chờ đọc. `word` >= 0 thắng `offsetMs` (bắt đầu đúng chữ ấy). */
    internal class Target(val chapterIndex: Int, val segment: Int, val offsetMs: Long, val word: Int, var play: Boolean, private val origin: Place? = null) {
        /** Chỗ để đọc lại (đổi giọng, "Thử lại"). Chỗ tạm lúc chữ chương chưa về (đầu chương) mang [origin] = chỗ người nghe đã chọn - đọc lại từ chỗ tạm là về đầu chương. */
        fun place(): Place = origin ?: Place(chapterIndex, 0, segment, word, offsetMs)
    }

    /** Đối số của [startAt]: `segment` >= 0 thì đoạn ấy (`word`, `within` trong đoạn), không thì mốc `offsetMs` của chương. */
    internal data class Place(val chapterIndex: Int, val offsetMs: Long, val segment: Int = -1, val word: Int = -1, val within: Long = 0)

    /** Đổi giọng giữa lúc đọc ([setVoice]): nạp lại sau đoạn đang phát, đọc lại chỗ đang chờ khi ExoPlayer chưa có gì, hay không làm gì (chương audio, đang dừng vì lỗi). */
    internal enum class VoiceSwitch {
        NONE, REQUEUE, RESTART;

        companion object {
            /** [segment]: đoạn của mục đang phát (null = ExoPlayer chưa có gì, < 0 = chương audio); [waitingText]: đang chờ đọc một chỗ trong chương chữ;
             *  [textPending]: chữ chương ấy còn đang lấy từ máy giữ sách ([fetchText]) - chưa đọc gì bằng giọng cũ, chữ về thì đọc đúng chỗ đã chọn bằng giọng mới. */
            fun of(segment: Int?, waitingText: Boolean, failed: Boolean, textPending: Boolean = false): VoiceSwitch = when {
                segment != null -> if (segment >= 0) REQUEUE else NONE
                waitingText && !failed && !textPending -> RESTART
                else -> NONE
            }
        }
    }

    private var context: Context? = null
    private var reader: ClipReader? = null
    // Hai luồng: lần tua mới không phải đợi việc cũ (Edge có thể treo tới hạn 45 giây); giọng của máy tự xếp hàng riêng (DeviceEngine).
    // Bốn cái: một đoạn đang đọc + một đoạn đọc song song khi Edge chậm ([warm]) + chỗ cho lần tua sau (việc cũ chạy nốt, không huỷ giữa chừng được).
    private val worker = Executors.newFixedThreadPool(4) { Thread(it, "read-aloud").apply { isDaemon = true } }
    /** Lịch giữ đầu chương ([holdOpening]): luồng riêng, không xếp sau các lượt đọc của [worker]. */
    private val planner = OpeningPlanner("read-aloud-opening")
    /** Thời gian lấy clip thật của giọng trực tuyến đang chọn: quyết định phải đọc sẵn bao nhiêu đoạn ([needMore]) và có đọc song song đoạn kế không. */
    private val policy = ReadAheadPolicy(AHEAD)
    /** Dừng vì lỗi hay do người nghe tự dừng: dịch vụ trả lời lại thì tự nghe tiếp chỉ khi là lỗi dừng ([serviceAnswered]). */
    private val errorPause = ErrorPause()
    /** Đoạn hỏng vì dịch vụ trục trặc mà người nghe chưa tới: lượt đọc kế của nó là lần hỏi mới, cách [StalledClips.REASK_MS] khi còn âm thanh để nghe. */
    private val stalled = StalledClips()
    private val main by lazy { android.os.Handler(android.os.Looper.getMainLooper()) }
    private var policyVoice = ""
    /** Việc đọc đang chạy theo (giọng, chữ): đoạn kế đọc song song ([warm]) và lượt nạp thật của nó dùng chung một lượt gọi Edge, không gọi hai lần. */
    private val sharing = ConcurrentHashMap<String, java.util.concurrent.FutureTask<Result<Clip>>>()

    /** Giọng đang chọn ("edge:..." / "device:..."); đổi bằng [setVoice]. */
    var voiceId: String = DEFAULT_VOICE
        private set

    /** Cuốn đang nạp có chương chữ: hàng đợi do lõi này quản (không phải bản ExoPlayer tự chạy hết danh sách chương). */
    @Volatile
    var active = false
        private set

    private val chaps = HashMap<Int, Chap>()
    @Volatile private var generation = 0 // luồng nền đọc để biết việc của mình đã cũ chưa
    /** Các lượt đọc đang chạy ở luồng nền: nhảy sang chỗ khác ([bumpGeneration]) thì huỷ hết - ổ cắm của chúng đóng ngay, không giữ chỗ kết nối Edge tới hết lượt ([ClipCancel]). */
    private val jobs = java.util.concurrent.CopyOnWriteArraySet<ClipCancel>()

    /**
     * Việc đang làm thành cũ (tua, đổi chương, đổi giọng, dừng): kết quả tới muộn bị bỏ, lượt đọc đang chạy bị huỷ, hẹn hỏi lại cũng bỏ. Người nghe TẠM DỪNG thì không gọi: clip đang về dùng được khi bấm phát.
     * `keep` (uxfix60, chỉ [requeueAhead]): lượt phát luồng của đoạn ĐANG NGHE - không huỷ, kết quả của nó vẫn nhận ([kept]); mọi lần nhảy khác bỏ nó như thường.
     */
    private fun bumpGeneration(keep: LiveJob? = null) {
        generation += 1
        resume = null
        kept = keep
        running = keep
        reminder.cancel()
        opening = null
        planning = false
        for (job in jobs) if (job !== keep?.cancel) job.cancel()
    }
    /** Lượt phát luồng của đoạn đang nghe được giữ qua lần đổi giọng / cách đọc ([requeueAhead]): đoạn ấy nói nốt bằng giọng cũ (như máy tính). Đọc cả ở luồng đọc. */
    @Volatile private var kept: LiveJob? = null
    /** Lượt đọc chính đang chạy mà phát luồng ([startJob]; đã có byte đầu hay chưa); null khi không có. Luồng chính. */
    private var running: LiveJob? = null
    /** Việc của lượt phát luồng `job` còn là việc hiện hành? (cùng thế hệ, hay là lượt được giữ - [kept]). */
    private fun current(job: LiveJob): Boolean = job.token == generation || job === kept
    /**
     * Phần còn lại đang chờ đọc của đoạn phát luồng vừa đứt giữa chừng ([onLiveBroke]); [startJob] dùng nó khi tới đúng đoạn ấy. Giữ tới khi phần nối đọc THÀNH CÔNG (uxfix60): phần nối hỏng, người nghe
     * tạm dừng lúc đang thử lại, lần hỏi lại - đều nối đúng chữ chưa nghe, không đọc lại từ đầu đoạn.
     */
    private var resume: Resume? = null
    /** Một chỗ hỏng một lời báo ([FailureNotice]). */
    private val notices = FailureNotice()
    private var inFlight = false
    private var feedChapter = 0
    private var feedSegment = 0
    private var waiting: Target? = null
    /** Clip đầu của lần mở / nhảy bằng giọng trên máy đang được giữ ([holdOpening]): theo lịch đo được, hoặc chờ đoạn kế theo luật cũ khi chưa đủ số đo. Luồng chính. */
    private var opening: Opening? = null
    /** Lịch giữ đầu chương ([holdOpening]) đang tính ở luồng nền: [pump] đứng chờ như khi phép tính còn chạy trên luồng chính; [bumpGeneration] bỏ nó. Luồng chính. */
    private var planning = false
    private class Opening(val token: Int, item: MediaItem, val offsetMs: Long, scheduled: Boolean, val deadline: Long) {
        val queue = OpeningQueue(item, scheduled)
    }
    private var failure: String? = null
    /** Đứng ở đầu một chương chữ mà giọng trực tuyến chưa được đồng ý (chương trước hết rồi tự sang): không đọc gì tới khi người nghe bấm phát -
     *  giao diện hỏi đồng ý trước khi gửi lệnh phát (player.tsx withConsent). */
    private var held = false
    private var artwork: ByteArray? = null

    /** Bìa cho thẻ media của các đoạn đọc to dựng sau này (sửa sách đang nghe: [Playback.updateMetadata] đưa bìa nó vừa tính). */
    fun refreshArtwork(cover: ByteArray = Artwork.cover(Playback.bookTitle, Playback.bookId)) {
        artwork = cover
    }
    private val scriptListeners = mutableSetOf<(String, Int) -> Unit>()

    fun init(appContext: Context) {
        if (context != null) return
        context = appContext.applicationContext
        FetchWake.init(appContext)
        choices = VoiceChoices(File(appContext.applicationContext.filesDir, "readaloud-voices.json"))
    }

    /** Giọng đã chọn của từng cuốn, nhớ trong lõi ([VoiceChoices]). */
    internal var choices: VoiceChoices? = null

    private var cache: ClipCache? = null

    /** Bộ đệm đoạn dùng chung cho nghe và "Làm trước" (PrepareAhead.kt); danh sách đoạn ghim nằm ngoài thư mục cache. */
    @Synchronized
    internal fun cache(): ClipCache = cache ?: run {
        val ctx = context ?: throw VoiceException("Chưa khởi động")
        VoiceSpeed.setup(ctx)
        // giọng hai bậc ([VoiceSpeed]): mã giọng trần = bậc nghe trực tiếp lúc này; bản xuất hỏi [VoiceSpeed.quality]. Giọng trên máy: dấu model của bậc ấy trong khoá
        // (mô-đun tính một lần mỗi lần tải / cập nhật / gỡ - VoiceModule.mark).
        // Mô-đun lấy một lần: SupertonicVoices / VieneuVoices khoá cả lượt đọc, mỗi lần tra bộ đệm hỏi lại thì phải chờ đoạn đang đọc xong.
        val supertonic by lazy { SupertonicVoices.module(ctx) }
        val vieneu by lazy { VieneuVoices.module(ctx) }
        val modelMark = { voice: String, tier: String ->
            when {
                voice.startsWith("${SupertonicVoices.PREFIX}:") -> supertonic.mark(VoiceSpeed.isFast(tier))
                voice.startsWith("${VieneuVoices.PREFIX}:") -> vieneu.mark(voice)
                else -> ""
            }
        }
        ClipCache(File(ctx.cacheDir, "readaloud"), ClipCache.capFor(ctx.cacheDir), pinFile = File(ctx.filesDir, "readaloud-pins.txt"), tierOf = VoiceSpeed::liveTag, markOf = modelMark).also { cache = it }
    }

    /** Load the engine of an on-device voice before play is pressed (the book's page or player was opened with it chosen): [EnginePreload]. Returns at once; false = nothing started. */
    fun preload(voiceId: String): Boolean = EnginePreload.start(context, voiceId)

    private var speeds: VoiceSpeeds? = null

    /** Tốc độ đo được của từng giọng (ước thời gian "Làm trước"). */
    @Synchronized
    internal fun speeds(): VoiceSpeeds = speeds ?: run {
        val ctx = context ?: throw VoiceException("Chưa khởi động")
        VoiceSpeeds(File(ctx.filesDir, "readaloud-speeds.json")).also { speeds = it }
    }

    /** Số đoạn của người đang nghe đang được đọc: "Làm trước" đứng chờ khi khác 0 (nghe trực tiếp đi trước). */
    private val live = java.util.concurrent.atomic.AtomicInteger()

    fun liveJobs(): Int = live.get()

    @Synchronized
    private fun reader(): ClipReader = reader ?: run {
        val ctx = context ?: throw VoiceException("Chưa khởi động")
        // Giọng dùng khoá hỏng (khoá bị từ chối, hết hạn mức, mất mạng): Edge đỡ trước giọng của máy; mỗi chuyện báo người nghe một lần.
        ClipReader(cache(), ::voiceFor, { fallbackVoice(ctx) }, onlineFallback = { EdgeTts("vi-VN-HoaiMyNeural") }, notice = ::notice).also { reader = it }
    }

    private fun voiceFor(id: String): Voice {
        val (provider, name) = ClipCache.split(id)
        return when (provider) {
            "edge" -> EdgeTts(name.ifEmpty { "vi-VN-HoaiMyNeural" })
            "device" -> DeviceTts(context ?: throw VoiceException("Chưa khởi động"), name)
            VieneuVoices.PREFIX -> VieneuVoices.voice(context ?: throw VoiceException("Chưa khởi động"), id)
            SupertonicVoices.PREFIX -> SupertonicVoices.voice(context ?: throw VoiceException("Chưa khởi động"), id)
            else -> OnlineVoices.voiceFor(context ?: throw VoiceException("Chưa khởi động"), id) ?: throw VoiceException("Giọng lạ: $id")
        }
    }

    private fun fallbackVoice(ctx: Context): Voice? =
        DeviceTts.defaultId(ctx)?.let { DeviceTts(ctx, it.removePrefix("device:")) }

    fun addScriptListener(listener: (String, Int) -> Unit) { scriptListeners += listener }
    fun removeScriptListener(listener: (String, Int) -> Unit) { scriptListeners -= listener }

    private val noticeListeners = mutableSetOf<(String) -> Unit>()
    fun addNoticeListener(listener: (String) -> Unit) { noticeListeners += listener }
    fun removeNoticeListener(listener: (String) -> Unit) { noticeListeners -= listener }
    private fun notice(message: String) = Playback.onMain { noticeListeners.toList().forEach { runCatching { it(message) } } }

    /**
     * Đúng giọng này, không rơi sang giọng khác ("Thử giọng", "Làm trước"); qua bộ đệm. `origin`: gốc của cuốn ([originOf] / [originNow]); `readings`: cách
     * đọc riêng của cuốn ([readingsOf]). Chạy ở luồng nền.
     */
    fun readExactly(id: String, text: String, origin: String? = null, readings: Map<String, String>? = null): Clip =
        reader().readExactly(text, id, origin, readings)

    private val bookReadings = ConcurrentHashMap<String, Pair<List<Pair<Long, Long>>, Map<String, String>>>()

    /**
     * Cách đọc riêng người nghe đặt cho cuốn ("Đọc từ này là…", lớp sửa `readings` - [BookEdits]). Nhớ theo giờ sửa + cỡ của `edits.json`: lưu một cách đọc
     * thì đoạn đọc sau đó dùng ngay cách mới. Đọc file nhỏ - gọi được ở luồng chính.
     */
    fun readingsOf(bookId: String): Map<String, String> {
        if (bookId.isBlank()) return emptyMap()
        val dir = Store.bookDir(bookId)
        // The holder's readings (BookEdits.HOLDER_FILE) apply here too; the sent ledger (EditsSync.STATE_FILE) decides which side is newer.
        val stamp = listOf(BookEdits.EDITS_FILE, BookEdits.HOLDER_FILE, EditsSync.STATE_FILE).map { name ->
            File(dir, name).let { if (it.isFile) it.lastModified() to it.length() else 0L to -1L }
        }
        bookReadings[bookId]?.takeIf { it.first == stamp }?.let { return it.second }
        val found = if (stamp[0].second < 0 && stamp[1].second < 0) emptyMap()
        else runCatching { BookEdits.readingsOf(EditsSync.experienced(dir)) }.getOrDefault(emptyMap())
        bookReadings[bookId] = stamp to found
        return found
    }

    private val origins = ConcurrentHashMap<String, String>()

    private val guesser = Executors.newSingleThreadExecutor { Thread(it, "read-aloud-origin").apply { isDaemon = true } }
    private val guessing = ConcurrentHashMap.newKeySet<String>()

    /**
     * Gốc Nhật / Hàn của cuốn ("ja" / "ko", null = không) để giọng VieNeu đọc tên theo luật phiên âm ([Names]): người dùng ghi đè thì theo đó, không thì máy đoán từ các
     * chương đầu rồi nhớ ([VoiceChoices.originFor]). KHÔNG chờ: đoán đọc file nên chạy ở luồng nền riêng, một lần cho mỗi cuốn; trong lúc chưa có thì trả null (đọc như không
     * có gốc), có rồi mới dùng. An toàn ở luồng chính.
     */
    fun originOf(bookId: String): String? {
        if (bookId.isBlank()) return null
        origins[bookId]?.let { return it.ifEmpty { null } }
        if (guessing.add(bookId)) guesser.execute { try { originNow(bookId) } finally { guessing.remove(bookId) } }
        return null
    }

    /** Như [originOf] nhưng chờ lần đoán xong - chỉ cho luồng nền ("Làm trước" phải dùng đúng gốc ngay từ đoạn đầu). */
    fun originNow(bookId: String): String? {
        if (bookId.isBlank()) return null
        val found = origins[bookId] ?: (runCatching { choices?.originFor(bookId) { sampleTexts(bookId) } }.getOrNull() ?: "").also { origins[bookId] = it }
        return found.ifEmpty { null }
    }

    /** Người dùng chọn gốc của cuốn: "ja" / "ko" / "none" (không phiên âm); null = theo máy đoán. (Giao diện cho chọn là việc sau.) */
    fun setOrigin(bookId: String, value: String?) {
        choices?.setOriginOverride(bookId, value)
        origins.remove(bookId)
    }

    /** Chữ của các chương chữ đầu tiên (đủ để đoán gốc). */
    private fun sampleTexts(bookId: String): Sequence<String> {
        val array = runCatching { Store.manifest(bookId) }.getOrNull()?.optJSONArray("chapters") ?: return emptySequence()
        val ids = (0 until array.length()).mapNotNull { array.optJSONObject(it) }.filter { it.optString("text").startsWith("texts/") }
            .map { it.optInt("id") }.take(Names.SAMPLE_CHAPTERS)
        val texts = textChapters(bookId, ids)
        return ids.asSequence().mapNotNull { texts[it]?.second?.joinToString("\n") }.filter { it.isNotEmpty() }
    }

    // ---- giọng ----------------------------------------------------------------------------------------------

    /** Danh sách giọng cho giao diện (chạy ở luồng nền - hỏi bộ đọc của máy có thể chờ). */
    fun voices(ctx: Context): List<JSONObject> {
        val list = ArrayList<VoiceInfo>()
        list.add(VoiceInfo(DEFAULT_VOICE, "Hoài My (Edge)", "edge", true, true, DEFAULT_VOICE_GENDER))
        list.add(VoiceInfo("edge:vi-VN-NamMinhNeural", "Nam Minh (Edge)", "edge", true, false, "male"))
        list.addAll(VieneuVoices.voices(ctx)) // giọng VieNeu: chỉ khi mô-đun đã tải về điện thoại
        list.addAll(SupertonicVoices.voices(ctx)) // giọng Supertonic: như vậy
        list.addAll(OnlineVoices.voices(ctx)) // giọng dùng khoá của người dùng: chỉ khi khoá đã kiểm tra được
        list.addAll(DeviceTts.voices(ctx))
        return list.map {
            JSONObject().put("id", it.id).put("name", it.name).put("provider", it.provider).put("online", it.online)
                .put("default", it.default).put("gender", it.gender).put("gainDb", VoiceGain.db(it.id))
        }
    }

    /** Giao diện gửi giọng của cuốn `bookId` (lúc nạp, lúc người nghe đổi): nhớ cho cuốn ấy; cuốn ấy đang nạp thì đổi ngay. */
    fun chooseFor(bookId: String, id: String) {
        rememberFor(bookId, id)
        if (bookId.isEmpty() || bookId == Playback.bookId) setVoice(id)
    }

    /** Chỉ nhớ giọng của cuốn `bookId`, không đổi giọng đang đọc: lúc nạp cuốn ([vn.abook.player.PlayerPlugin.load]) - [useVoiceOf] của lần nạp đặt giọng ngay sau đó.
     *  Qua [chooseFor] thì nạp lại cùng cuốn với giọng khác sẽ đọc lại chỗ chờ của lượt cũ bằng giọng mới, rồi lần nạp bỏ ngay lượt đọc ấy. */
    fun rememberFor(bookId: String, id: String) {
        choices?.remember(bookId, id)
    }

    /** Giọng mặc định (Cài đặt) cho cuốn chưa chọn giọng riêng. Không đổi giọng của chương đang đọc - như giao diện máy tính; lần nạp kế theo nó. */
    fun chooseDefault(id: String) {
        choices?.rememberDefault(id)
    }

    /** Nạp một cuốn - bằng bất cứ đường nào (giao diện, widget, xe hơi, máy tính điều khiển): đọc bằng giọng đã nhớ của cuốn ấy. Chỉ đặt giọng;
     *  [begin] / [stop] ngay sau đó dựng lại hàng đợi. */
    fun useVoiceOf(bookId: String) {
        voiceBook = bookId
        voiceId = usableOrDefault(choices?.voiceFor(bookId).orEmpty())
    }

    /** Cuốn mà [voiceId] đang đọc (lần [useVoiceOf] gần nhất). */
    private var voiceBook = ""

    /** Giọng này còn trên máy không? Giọng tải thêm (VieNeu, giọng dùng khoá) chỉ khi còn trong danh sách của máy; Edge và giọng của máy luôn có. */
    internal var stillOffered: (String) -> Boolean = { id ->
        val ctx = context
        when {
            ctx == null -> true
            id.substringBefore(':') == VieneuVoices.PREFIX -> VieneuVoices.voices(ctx).any { it.id == id }
            id.substringBefore(':') == SupertonicVoices.PREFIX -> SupertonicVoices.voices(ctx).any { it.id == id }
            id.substringBefore(':') in OnlineVoices.NAMES -> OnlineVoices.voices(ctx).any { it.id == id }
            else -> true
        }
    }

    /** Giọng VieNeu kể chuyện trung tính ([NarratorVoice]; không có giọng ưu tiên thì cùng giới với giọng mặc định) nếu máy đã tải mô-đun, không thì
     *  null. Chữ của người nghe chưa chọn giọng không nên rời máy khi máy đã có giọng chạy trên máy. */
    internal var localVoice: () -> String? = {
        context?.let { ctx -> NarratorVoice.pick(VieneuVoices.voices(ctx).map { it.id to it.gender }, DEFAULT_VOICE_GENDER) }
    }

    /** Giọng khi người nghe CHƯA chọn: giọng VieNeu kể chuyện trung tính nếu máy có, không thì giọng mặc định - đúng luật `resolveVoice` của giao diện
     *  (listen/readAloudVoice.ts), nên tên giọng giao diện hiện và giọng lõi đọc là một. */
    private fun unchosenVoice(): String = localVoice() ?: DEFAULT_VOICE

    /** Chưa chọn giọng: [unchosenVoice]. Giọng đã nhớ mà giọng ấy đã gỡ khỏi máy (gỡ VieNeu, xoá khoá) thì đọc bằng đúng giọng giao diện sẽ tự quay về
     *  (resolveVoice: giọng mặc định của danh sách). Lựa chọn đã nhớ của cuốn (`choices`) giữ nguyên: tải lại giọng thì cuốn tự về giọng cũ ở lần nạp kế. */
    private fun usableOrDefault(id: String): String = if (id.isBlank()) unchosenVoice() else id.takeIf { stillOffered(it) } ?: DEFAULT_VOICE

    /** Một giọng tải thêm vừa mất (gỡ mô-đun VieNeu, xoá khoá): đang đọc bằng nó thì đổi ngay sang giọng mặc định như [setVoice] (cuốn chưa chọn giọng
     *  thì giọng của người chưa chọn: còn giọng VieNeu khác thì dùng nó). Gọi ở luồng chính. */
    fun voicesChanged() {
        if (stillOffered(voiceId)) return
        setVoice(if (choices?.voiceFor(voiceBook).isNullOrBlank()) "" else DEFAULT_VOICE)
    }

    /** Giao diện gửi danh sách nhà cung cấp đã được đồng ý (lúc mở app, mỗi lần người nghe đồng ý): đang dừng nạp ở ranh giới chương vì chưa
     *  đồng ý thì nạp tiếp. */
    fun allowOnline(providers: List<String>) {
        choices?.allowOnline(providers)
        pump()
    }

    /** Giọng đang chọn là giọng trực tuyến mà người nghe chưa đồng ý gửi chữ tới (giọng của máy, VieNeu, Supertonic: không gửi gì đi). */
    private fun needsConsent(): Boolean {
        val provider = ClipCache.split(voiceId).first
        return PreparePlan.online(voiceId) && choices?.onlineAllowed(provider) != true
    }

    /** Đổi giọng: các đoạn đã đọc sẵn mà chưa tới thì bỏ, đoạn kế đọc bằng giọng mới. */
    fun setVoice(id: String) {
        val value = usableOrDefault(id)
        if (value == voiceId) return
        voiceId = value
        if (!active) return
        val exo = Playback.player ?: return
        val slot = currentSlot()
        val target = waiting
        // Chữ chương chưa về: `waiting` chỉ là chỗ tạm (đầu chương), chỗ thật nằm trong việc chờ chữ - đọc lại ở đây là về đầu chương và ghi đè vị trí đã lưu.
        val textPending = target != null && chaps[target.chapterIndex] == null
        when (VoiceSwitch.of(slot?.segment, target != null && chapters().getOrNull(target.chapterIndex)?.isText == true, failure != null, textPending)) {
            VoiceSwitch.REQUEUE -> requeueAhead(exo, slot!!)
            // ExoPlayer chưa có gì (chờ đoạn đầu, hay clip đầu đang giữ - [holdOpening]): đọc lại đúng chỗ chờ bằng giọng mới; lượt đang chạy và clip đang giữ là của giọng cũ.
            VoiceSwitch.RESTART -> startAt(target!!.place(), target.play, held)
            VoiceSwitch.NONE -> Unit
        }
    }

    /** Cách đọc riêng của cuốn vừa đổi ("Đọc từ này là…", [LocalStudio]): các đoạn đã đọc sẵn mà chưa tới bỏ đi, đoạn kế đọc lại với cách đọc mới (bộ đệm khoá theo cách đọc
     *  nên đoạn không có chữ ấy lấy lại ngay). Đoạn đang phát nói nốt, nhưng clip của nó và của đoạn trước còn giữ để tua lùi cũng bỏ: nghe lại đoạn ấy thì đọc lại
     *  bằng cách đọc mới, như máy tính (soát a70). Gọi từ luồng nào cũng được. */
    fun readingsChanged(bookId: String) {
        if (!active) return
        Playback.onMain {
            if (!active || Playback.bookId != bookId) return@onMain
            val exo = Playback.player ?: return@onMain
            val slot = currentSlot()?.takeIf { it.segment >= 0 } ?: return@onMain
            requeueAhead(exo, slot)
            val index = exo.currentMediaItemIndex
            if (index > 0) exo.removeMediaItems(0, index)
            staleParagraph = slot.chapterIndex to slot.segment
        }
    }

    /** The paragraph playing when a reading changed: it finishes on its old clip; once playback moves on, its items leave the queue (no rewinding into the old clip). */
    private var staleParagraph: Pair<Int, Int>? = null

    /**
     * Bỏ hàng đợi sau đoạn đang phát và nạp lại từ đoạn kế (đổi giọng, đổi cách đọc). Đoạn đang nghe nói NỐT bằng giọng cũ (uxfix60, như máy tính `voiceChanged`): đang phát luồng thì lượt đọc của nó
     * không bị huỷ ([bumpGeneration] `keep`) - trước đây ExoPlayer phát hết byte đã về rồi im, mất phần còn lại; phần đã về / phần nối của cùng đoạn ở lại trong hàng đợi; phần nối chưa xin thì vẫn xin.
     */
    private fun requeueAhead(exo: Player, slot: Slot) {
        val keep = running?.takeIf { it.chap.index == slot.chapterIndex && it.segment == slot.segment && !it.broke }
        val rest = resume?.takeIf { it.chap.index == slot.chapterIndex && it.segment == slot.segment }
        bumpGeneration(keep)
        resume = rest
        if (keep == null) inFlight = false // lượt được giữ chạy nốt: [onClipReady] của nó mới mở đường cho đoạn kế (đọc bằng giọng mới)
        failure = null
        val index = exo.currentMediaItemIndex
        val sameParagraph = { i: Int -> (exo.getMediaItemAt(i).localConfiguration?.tag as? Slot)?.let { it.chapterIndex == slot.chapterIndex && it.segment == slot.segment } == true }
        val from = ((index + 1) until exo.mediaItemCount).firstOrNull { !sameParagraph(it) } ?: exo.mediaItemCount
        if (exo.mediaItemCount > from) exo.removeMediaItems(from, exo.mediaItemCount)
        feedChapter = slot.chapterIndex
        feedSegment = if (rest != null) slot.segment else slot.segment + 1
        pump()
    }

    // ---- trạng thái cho Playback ---------------------------------------------------------------------------

    private fun currentSlot(): Slot? = Playback.player?.currentMediaItem?.localConfiguration?.tag as? Slot

    /** Đang ở chương chữ (đoạn đang phát hay đang chờ đọc đoạn đầu). */
    fun inText(): Boolean = active && (currentSlot()?.segment?.let { it >= 0 } == true || waiting?.let { chapters().getOrNull(it.chapterIndex)?.isText } == true)

    private fun chapters() = Playback.chapters

    private fun chapterIndexNow(): Int? = currentSlot()?.takeIf { it.segment >= 0 }?.chapterIndex ?: waiting?.chapterIndex

    /** Mã chương đang chờ đọc (ExoPlayer chưa có gì để phát). */
    fun waitingChapterId(): Int? = waiting?.let { chapters().getOrNull(it.chapterIndex)?.id }

    val isWaiting: Boolean get() = waiting != null && failure == null && !held

    /** Người nghe muốn phát mà chưa có âm thanh để phát: chờ đoạn đầu, hay hàng đợi cạn vì đọc chậm hơn nghe (đoạn kế đang đọc). Với phiên media
     *  (thông báo, màn hình khoá, xe hơi) đó là "đang tải" - trước đây ExoPlayer hết hàng đợi nên phiên báo "đã dừng" vài giây: nút Phát hiện ra và
     *  thanh tiến độ biến mất (thấy 03-10 trên máy ảo, giọng Edge). */
    fun starved(): Boolean {
        if (!active || failure != null || held) return false
        val exo = Playback.player ?: return false
        return waiting?.play == true || (inFlight && exo.playbackState == Player.STATE_ENDED && exo.playWhenReady)
    }

    /** Người nghe muốn đang phát (kể cả lúc chờ đọc đoạn). */
    fun wantsPlay(): Boolean = waiting?.play ?: (Playback.player?.playWhenReady == true)

    /** Vị trí ảo trong chương (ms), null nếu không ở chương chữ. */
    fun positionMs(): Long? = chapterMs(Playback.player?.currentPosition ?: 0L)

    /** Vị trí chữ của đúng đoạn đang nghe/chờ đọc; lưu cùng giây, không dùng giây chương để suy đoạn. */
    fun anchor(): JSONObject? {
        if (!active) return null
        val slot = currentSlot()?.takeIf { it.segment >= 0 }
        val target = waiting
        val index = slot?.chapterIndex ?: target?.chapterIndex ?: return null
        val chap = chaps[index] ?: return null
        val segment = slot?.segment ?: target?.segment ?: return null
        val text = chap.paragraphs.getOrNull(segment) ?: return null
        val ms = if (slot != null) slot.baseMs + (Playback.player?.currentPosition ?: 0L) else target?.offsetMs ?: 0L
        val words = chap.clips[segment]?.words ?: chap.liveWords[segment]
        val word = if (slot == null && target != null && target.word >= 0) target.word else
            words?.indexOfLast { it.start <= ms && it.end > it.start }?.coerceAtLeast(chap.clips[segment]?.fromWord ?: 0)
                ?: 0
        return ReadingAnchor.make(chap.paragraphs, segment, word.coerceAtMost((WordTokens.count(text) - 1).coerceAtLeast(0)))
    }

    /**
     * Mốc `clipMs` của đoạn đang phát, đổi sang đồng hồ ảo của chương (ms); đang chờ đọc đoạn thì là chỗ sẽ bắt đầu. null nếu không ở chương chữ. Cũng dùng cho
     * mốc đã đệm tới (thanh tiến độ ở thông báo / màn hình khoá - PlaybackService).
     */
    fun chapterMs(clipMs: Long): Long? {
        if (!active) return null
        val slot = currentSlot()
        if (slot != null && slot.segment >= 0) {
            val chap = chaps[slot.chapterIndex] ?: return null
            val clip = chap.clips[slot.segment]
            // Phần nối: vị trí trong mục cộng độ dài phần đã về. Đoạn đang phát luồng (chưa có clip): kẹp ở độ dài ước như máy tính (uxfix60) - không thì đồng hồ chạy quá đoạn, chữ sáng tràn sang đoạn kế.
            val inClip = (slot.baseMs + clipMs).coerceIn(0L, clip?.durationMs ?: liveLimitMs(chap, slot.segment, slot.baseMs))
            return chap.timeline.startOf(slot.segment) + inClip
        }
        val target = waiting ?: return null
        val chap = chaps[target.chapterIndex] ?: return null
        if (!chapters().getOrNull(target.chapterIndex)!!.isText) return null
        return chap.timeline.startOf(target.segment) + target.offsetMs
    }

    /** Độ dài ảo của chương (ms): phần đã đọc + ước lượng phần còn lại. */
    fun durationMs(): Long? {
        if (!active) return null
        val index = chapterIndexNow() ?: return null
        return chaps[index]?.timeline?.totalMs()
    }

    /** Hệ số to/nhỏ của giọng đang phát (1 nếu không phải đoạn đọc to). */
    fun gainFactor(): Float = currentSlot()?.takeIf { it.segment >= 0 }?.let { VoiceGain.factor(it.gainDb) } ?: 1f

    // ---- nạp / dừng -----------------------------------------------------------------------------------------

    /** Nạp cuốn có chương chữ: bắt đầu ở chương `index`, `offsetMs` trong chương. */
    fun begin(index: Int, offsetMs: Long, autoplay: Boolean) {
        reset()
        active = true
        artwork = Artwork.cover(Playback.bookTitle, Playback.bookId)
        val last = Store.state(Playback.bookId).optJSONObject("last")
        val anchor = last?.takeIf {
            it.optInt("chapterId", -1) == chapters().getOrNull(index)?.id && Math.abs(it.optDouble("seconds", -1.0) * 1000 - offsetMs) < 1000
        }?.optJSONObject("anchor")
        startAt(index, offsetMs, autoplay, anchor = anchor)
    }

    /** Hết cuốn / sang cuốn khác / dịch vụ tắt: bỏ việc đang làm, quên mọi chương. */
    fun stop() {
        reset()
    }

    private fun reset() {
        active = false
        FetchWake.releaseAll()
        bumpGeneration()
        inFlight = false
        waiting = null
        failure = null
        errorPause.listenerActed()
        held = false
        stalled.clear()
        liveNow = null
        chaps.clear()
        feedChapter = 0
        feedSegment = 0
    }

    /** Dòng người nghe bỏ khỏi phần đọc của một chương (`skip` của book.json đã áp lớp sửa) - màn đọc bỏ đúng các dòng này. */
    private fun skipOf(manifest: org.json.JSONObject?, chapterId: Int): List<String> {
        val array = manifest?.optJSONArray("chapters") ?: return emptyList()
        val skip = (0 until array.length()).mapNotNull { array.optJSONObject(it) }.firstOrNull { it.optInt("id") == chapterId }?.optJSONArray("skip")
            ?: return emptyList()
        return (0 until skip.length()).map { skip.getString(it) }
    }

    /** Chữ chương đang lấy từ máy giữ sách ([fetchText]): khoá "<cuốn>/<mục chữ>" -> việc chờ chữ về (lần gọi sau thay lần trước). Luồng chính. */
    private val textWaits = HashMap<String, (Boolean) -> Unit>()

    /**
     * Chương chữ của cuốn NGHE THẲNG mà máy này chưa có chữ (`texts/<n>.txt` chưa về - soát a68 lỗi 1: trước đây báo "Không đọc được chữ" và Thử lại vô ích):
     * lấy từ máy giữ sách ở luồng nền (Streaming.fetchSmall cất vào thư mục sách - lần sau đọc ngay, kể cả khi mất mạng), xong thì `then` ở luồng chính nếu
     * chưa ai nhảy đi chỗ khác; không lấy được thì báo đúng lý do. False: không phải trường hợp này (cuốn đã tải, chữ đã có, chương không phải chương chữ).
     */
    private fun fetchText(index: Int, then: () -> Unit): Boolean {
        val chapter = chapters().getOrNull(index)?.takeIf { it.isText } ?: return false
        val book = Playback.bookId
        val ctx = context ?: return false
        if (Store.rawManifest(book) != null) return false
        if (runCatching { Store.file(book, chapter.text).isFile }.getOrDefault(true)) {
            // Chữ vừa về bằng đường khác giữa lúc chapFor đọc và lúc này (giao diện xin chữ chương để hiện - LibraryPlugin.readText): đọc lại ngay.
            if (chapFor(index) == null) return false
            then()
            return true
        }
        val token = generation
        val key = "$book/${chapter.text}"
        val running = key in textWaits
        textWaits[key] = { ok ->
            if (token == generation && Playback.bookId == book) {
                if (ok) then() else fail("Không lấy được chữ chương “${chapter.title}” từ ${SyncLink.holderName(ctx, book)} - kiểm tra kết nối rồi bấm phát lại")
            }
        }
        if (!running) {
            worker.execute {
                val ok = Streaming.fetchSmall(ctx, book, chapter.text) != null
                Playback.onMain { textWaits.remove(key)?.invoke(ok) }
            }
        }
        return true
    }

    private fun chapFor(index: Int): Chap? {
        chaps[index]?.let { return it }
        val chapter = chapters().getOrNull(index) ?: return null
        if (!chapter.isText) return null
        return try {
            val text = Store.file(Playback.bookId, chapter.text).readText(Charsets.UTF_8)
            Chap(index, Paragraphs.split(Paragraphs.withoutLines(text, skipOf(Store.manifest(Playback.bookId), chapter.id)))).also {
                fromCache(it, originOf(Playback.bookId), readingsOf(Playback.bookId))
                chaps[index] = it
            }
        } catch (error: Exception) {
            null
        }
    }

    /**
     * Phát từ chương `index`: `segment` >= 0 thì từ đoạn ấy (`word` >= 0: từ đúng chữ ấy), không thì từ mốc `offsetMs` của chương. Chương chữ: xoá hàng đợi và đợi đoạn
     * âm thanh đầu tiên (giao diện thấy `buffering`); chương audio: đặt ngay.
     */
    fun startAt(index: Int, offsetMs: Long, play: Boolean, segment: Int = -1, word: Int = -1, within: Long = 0, hold: Boolean = false, anchor: JSONObject? = null) {
        val exo = Playback.player ?: return
        val chapter = chapters().getOrNull(index) ?: return
        bumpGeneration()
        inFlight = false
        failure = null
        errorPause.listenerActed()
        if (!retryingByItself) notices.forget()
        held = hold
        feedChapter = index
        feedSegment = 0
        if (!chapter.isText) {
            waiting = Target(index, 0, offsetMs, -1, play)
            pump()
            return
        }
        val chap = chapFor(index)
        if (chap == null) {
            // Hàng đợi còn mục của cuốn / chương trước: bỏ TRƯỚC khi báo lỗi hay chờ chữ - không thì vị trí, độ dài báo ra (lưu lại, đồng bộ sang máy tính) là của
            // cuốn trước (soát a68 lỗi 2: "Nghe tiếp · 3:38" trên chương dài 3:15, rồi máy tính cũng nhận 3:38).
            exo.pauseAtEndOfMediaItems = false
            exo.clearMediaItems()
            exo.playWhenReady = play
            val place = Place(index, offsetMs, segment, word, within)
            waiting = Target(index, 0, 0, -1, play, place)
            if (fetchText(index) { startAt(index, offsetMs, play, segment, word, within, hold, anchor) }) {
                syncWants()
                Playback.emit("state")
                return
            }
            fail("Không đọc được chữ của chương “${chapter.title}”")
            return
        }
        val restored = if (segment < 0) ReadingAnchor.restore(chap.paragraphs, anchor) else null
        val seg = restored?.first ?: if (chap.paragraphs.isEmpty()) 0 else if (segment >= 0) segment.coerceIn(0, chap.paragraphs.size - 1) else chap.timeline.segmentAt(offsetMs)
        val inside = if (restored != null || chap.paragraphs.isEmpty()) 0L else if (segment >= 0) within else (offsetMs - chap.timeline.startOf(seg)).coerceAtLeast(0)
        waiting = Target(index, seg, inside, restored?.second ?: word, play)
        feedSegment = seg
        exo.pauseAtEndOfMediaItems = false
        exo.clearMediaItems()
        exo.playWhenReady = play
        syncWants()
        Playback.emit("state")
        pump()
    }

    /** [startAt] ở một chỗ đã ghi ([Target.place]). */
    private fun startAt(place: Place, play: Boolean, hold: Boolean = false) =
        startAt(place.chapterIndex, place.offsetMs, play, place.segment, place.word, place.within, hold)

    /**
     * Tua trong chương hiện tại tới `ms` (hay tới chữ `word` của đoạn `segment`). Đoạn đã có âm thanh và đang nằm trong hàng đợi: nhảy thẳng tới ĐÚNG chỗ trong đoạn
     * (không về đầu đoạn). Chưa có (chưa đọc, hay đã bỏ khỏi hàng đợi): đọc đoạn ấy rồi mới phát từ chỗ đó. Trả false nếu đang ở chương audio (để ExoPlayer tự tua).
     */
    fun seekMs(ms: Long, segment: Int = -1, word: Int = -1): Boolean {
        if (!active) return false
        val exo = Playback.player ?: return false
        val index = chapterIndexNow() ?: return false
        val chap = chaps[index] ?: return false
        notices.forget()
        // Đoạn đang phát luồng (uxfix60, máy tính: seek / seekWord trong MediaSource): đã nằm trong hàng đợi - tua trong phần đã về ngay trong mục ấy, không bỏ đi đọc lại.
        val growing = liveNow?.takeIf { it.chap === chap && !it.broke && chap.clips[it.segment] == null && liveIndex(exo, it) >= 0 }
        val plan = SeekPlan.plan(
            chap.timeline, { seg -> chap.clips.getOrNull(seg) ?: growing?.takeIf { it.segment == seg }?.let(::growingClip) },
            { seg -> (0 until exo.mediaItemCount).any { i -> (exo.getMediaItemAt(i).localConfiguration?.tag as? Slot)?.let { it.chapterIndex == index && it.segment == seg } == true } },
            ms, segment, word,
            growing = { seg -> growing?.takeIf { it.segment == seg }?.let { job -> (job.resume?.baseMs ?: 0L).let { base -> SeekPlan.Growing(base + job.heardMs, base + job.entry.durationMs()) } } },
        )
        when (plan) {
            is SeekPlan.Plan.InClip -> {
                // Đoạn đứt giữa chừng có hai mục cùng đoạn (phần đã về, phần nối): chỗ nào [SeekPlan.serves] nhận thì nằm ở mục sau.
                val at = (0 until exo.mediaItemCount).last { i -> (exo.getMediaItemAt(i).localConfiguration?.tag as? Slot)?.let { it.chapterIndex == index && it.segment == plan.segment } == true }
                exo.seekTo(at, plan.positionMs)
            }
            is SeekPlan.Plan.Synthesize -> startAt(index, 0, wantsPlay(), plan.segment, plan.word, plan.offsetMs)
        }
        return true
    }

    /** Clip TẠM của đoạn đang phát luồng cho [SeekPlan.plan]: độ dài = phần đã về, mốc chữ tạm, trên đồng hồ của đoạn. */
    private fun growingClip(job: LiveJob): Clip {
        val base = job.resume?.baseMs ?: 0L
        return Clip(job.entry.file() ?: File(""), base + job.entry.durationMs(), job.chap.liveWords[job.segment].orEmpty(), job.voice, job.tail, base)
    }

    /** Sang chương `index` (nút Sau/Trước, danh sách chương, giao diện nhảy thẳng tới chữ). */
    fun jump(index: Int, ms: Long, segment: Int = -1, word: Int = -1) {
        if (index == chapterIndexNow() && seekMs(ms, segment, word)) {
            waiting?.play = true
            Playback.player?.play()
            return
        }
        startAt(index, ms, true, segment, word)
    }

    // ---- nạp đoạn -------------------------------------------------------------------------------------------

    /** Giữ hàng đợi có đoạn kế: gọi mỗi khi đoạn đổi, đoạn mới sẵn sàng, đổi giọng, hủy hẹn giờ. */
    fun pump() {
        if (!active || inFlight || planning || failure != null || held) return
        val exo = Playback.player ?: return
        val all = chapters()
        var guard = 0
        while (guard++ < 8) {
            if (!needMore(exo)) return
            if (feedChapter >= all.size) return
            val chapter = all[feedChapter]
            if (!chapter.isText) {
                appendAudioRun(all)
                continue
            }
            // Tự sang một chương chữ (không phải người nghe chọn chỗ bắt đầu) bằng giọng trực tuyến chưa được đồng ý: dừng nạp ở đây, hàng đợi cạn
            // ở cuối chương trước rồi handleEnded đứng chờ ở đầu chương này.
            if (waiting == null && feedSegment == 0 && needsConsent()) return
            val chap = chapFor(feedChapter)
            if (chap == null) {
                // Cuốn nghe thẳng: chữ chương kế còn ở máy giữ sách - lấy về rồi nạp tiếp (hàng đợi vẫn phát phần đã có).
                if (fetchText(feedChapter) { pump() }) return
                fail("Không đọc được chữ của chương “${chapter.title}”")
                return
            }
            // Dòng ngăn cảnh không có quãng lặng (đầu / cuối chương, dòng thứ hai liền nhau) không phải là gì để phát: bỏ qua cả chuỗi mà không tốn vòng của `guard`.
            while (feedSegment < chap.paragraphs.size && chap.isBreak(feedSegment) && chap.gaps[feedSegment] == 0) feedSegment += 1
            if (feedSegment >= chap.paragraphs.size) {
                if (opening?.queue?.scheduled == true) return // cả chương đã vào hàng chờ: đợi phát clip đầu, không báo nhầm "không có chữ" hay đọc sang chương khác
                if (feedChapter + 1 >= all.size) {
                    if (waiting != null) fail("Chương “${chapter.title}” không có chữ để đọc")
                    return
                }
                // Hẹn giờ "hết chương": dừng nạp ở cuối chương này để ExoPlayer tự dừng đúng chỗ (handleEnded).
                if (SleepTimer.mode == SleepTimer.Mode.CHAPTER && waiting == null) return
                feedChapter += 1
                feedSegment = 0
                continue
            }
            if (chap.isBreak(feedSegment)) {
                feedBreak(chap, feedSegment)
                continue
            }
            // Đoạn này vừa hỏng vì dịch vụ trục trặc và người nghe còn âm thanh để nghe: hỏi lại sau nhịp nghỉ (mất mạng dài không thành bão lượt gọi); hàng đợi cạn thì hỏi ngay.
            val wait = stalled.cooldownMs(feedChapter, feedSegment)
            if (wait > 0 && listenerHasAudio(exo)) {
                remind(wait)
                return
            }
            startJob(chap, feedSegment)
            return
        }
    }

    /** Người nghe còn âm thanh để nghe (không phải đang chờ đoạn đầu, hàng đợi chưa cạn). */
    /** Số đoạn dài ([Slot.long]) từ đoạn đang phát tới hết hàng đợi: những gì người nghe còn phải nghe trước đoạn sắp nạp. */
    private fun longQueued(exo: Player): Int =
        (exo.currentMediaItemIndex until exo.mediaItemCount).count { (exo.getMediaItemAt(it).localConfiguration?.tag as? Slot)?.long == true }

    private fun listenerHasAudio(exo: Player): Boolean = waiting == null && exo.currentMediaItem != null && exo.playbackState != Player.STATE_ENDED

    private val reminder by lazy { Reminder({ task, ms -> main.postDelayed(task, ms) }, { task -> main.removeCallbacks(task) }) }

    /** Hẹn [pump] sau `ms` (hết nhịp nghỉ của [stalled]); một hẹn một lúc, [bumpGeneration] bỏ hẹn cũ. */
    private fun remind(ms: Long) {
        val token = generation
        reminder.schedule(ms + 50) { if (token == generation) pump() }
    }

    /** Hàng đợi còn thiếu đoạn đọc sẵn? Tối thiểu [AHEAD] đoạn; giọng trực tuyến mà clip gần đây về chậm thì tới khi đủ số giây âm thanh [ReadAheadPolicy] đòi (tối đa [ReadAheadPolicy.MAX_AHEAD] đoạn);
     *  giọng trên máy tới khi đủ [ReadAheadPolicy.LOCAL_BUFFER_MS] âm thanh (tối đa [ReadAheadPolicy.LOCAL_MAX_AHEAD] đoạn). */
    private fun needMore(exo: Player): Boolean {
        if (waiting != null) return true
        val ahead = ((exo.currentMediaItemIndex + 1) until exo.mediaItemCount).map { aheadMs(exo.getMediaItemAt(it)) }
        return if (PreparePlan.online(voiceId)) policy.needMore(ahead) else ReadAheadPolicy.localNeedsMore(ahead, AHEAD)
    }

    /**
     * Lúc (System.nanoTime) người nghe hết tiếng trước đoạn sắp đọc: ngay bây giờ khi không còn gì để nghe (đang chờ đoạn này, hàng đợi cạn), không thì sau phần còn lại của mục đang phát và các mục
     * đã nạp sau nó ở tốc độ đang nghe; [Long.MAX_VALUE] khi người nghe đang dừng hay có mục chưa biết độ dài. Giọng trên máy giữ khúc đã đọc tới lúc này là cùng ([LocalLive]).
     */
    private fun soundReachesNanos(): Long {
        val exo = Playback.player ?: return Long.MAX_VALUE
        if (!wantsPlay()) return Long.MAX_VALUE
        val now = System.nanoTime()
        opening?.takeIf { it.queue.scheduled }?.let { hold ->
            val lengths = hold.queue.items.map(::aheadMs)
            if (lengths.any { it >= ReadAheadPolicy.MAX_BUFFER_MS }) return Long.MAX_VALUE
            val leftMs = (lengths.sum() - hold.offsetMs).coerceAtLeast(0)
            return maxOf(now, hold.deadline) + (leftMs / maxOf(exo.playbackParameters.speed, 0.1f) * 1_000_000).toLong()
        }
        if (!listenerHasAudio(exo)) return now
        val current = exo.currentMediaItem?.let(::aheadMs) ?: return Long.MAX_VALUE
        val queued = ((exo.currentMediaItemIndex + 1) until exo.mediaItemCount).map { aheadMs(exo.getMediaItemAt(it)) }
        if (current >= ReadAheadPolicy.MAX_BUFFER_MS || queued.any { it >= ReadAheadPolicy.MAX_BUFFER_MS }) return Long.MAX_VALUE
        val leftMs = (current - exo.currentPosition).coerceAtLeast(0) + queued.sum()
        return now + (leftMs / maxOf(exo.playbackParameters.speed, 0.1f) * 1_000_000).toLong()
    }

    /** Độ dài (ms) của một mục đã nạp phía trước; mục không phải đoạn đọc to (chương audio) tính là dài - đã đủ đệm. */
    private fun aheadMs(item: MediaItem): Long {
        val slot = item.localConfiguration?.tag as? Slot
        return slot?.takeIf { it.segment >= 0 }?.let { chaps[it.chapterIndex]?.clips?.getOrNull(it.segment)?.durationMs } ?: ReadAheadPolicy.MAX_BUFFER_MS
    }

    /**
     * Dòng ngăn cảnh ("***"): không đọc, không gửi giọng nào. Có quãng lặng thì đặt một file WAV im lặng dài đúng quãng ấy vào hàng đợi như một đoạn âm thanh
     * (đồng hồ ảo, tua, lưu vị trí, hẹn giờ chạy y như đoạn khác; tốc độ nghe nhanh thì lặng cũng ngắn lại); không có (đầu / cuối chương, dòng thứ hai liền nhau) hay
     * không ghi được file thì bỏ qua như không có.
     */
    private fun feedBreak(chap: Chap, segment: Int) {
        val gap = chap.gaps[segment]
        val clip = if (gap > 0) silenceClip(gap.toLong()) else null
        // Dời chỗ nạp TRƯỚC khi đặt vào ExoPlayer (như onClipReady): setMediaItems báo đổi mục ngay trong lúc gọi, pump lồng vào không được thấy đoạn này là "đoạn kế".
        feedSegment = segment + 1
        if (clip == null) {
            chap.timeline.setDuration(segment, 0)
            return
        }
        chap.clips[segment] = clip
        val target = waiting
        deliver(listOf(clipItem(chap, segment, clip)), if (target != null) SeekPlan.offsetIn(clip, target.word, target.offsetMs) else 0L)
        notifyScript(chap)
        Playback.emit("state")
    }

    private fun silenceClip(ms: Long): Clip? {
        val dir = context?.cacheDir?.let { File(it, "readaloud-silence") } ?: return null
        return runCatching {
            dir.mkdirs()
            val file = File(dir, "silence-$ms.wav")
            if (!file.isFile) {
                // Ghi ra file tạm rồi đổi tên: máy tắt giữa chừng không để lại file cụt mà lần sau cứ phát.
                val part = File(dir, "silence-$ms.part")
                Wav.silence(part, ms)
                part.renameTo(file)
            }
            check(file.isFile) { "không ghi được file lặng" }
            Clip(file, ms, emptyList(), "silence")
        }.getOrNull()
    }

    private fun appendAudioRun(all: List<Playback.Chapter>) {
        var end = feedChapter
        while (end < all.size && !all[end].isText) end += 1
        val run = all.subList(feedChapter, end)
        val items = Playback.mediaItems(Playback.bookId, Playback.bookTitle, Playback.narrator, run)
        val offset = waiting?.takeIf { it.chapterIndex == feedChapter }?.offsetMs ?: 0L
        feedChapter = end
        feedSegment = 0
        deliver(items, offset)
    }

    /** Đặt `items` vào ExoPlayer: đang chờ chỗ bắt đầu thì thay cả hàng đợi, không thì nối đuôi. */
    private fun deliver(items: List<MediaItem>, offsetMs: Long) {
        opening?.takeIf { it.queue.scheduled }?.let {
            it.queue.items.addAll(items)
            return
        }
        val exo = Playback.player ?: return
        val target = waiting
        if (target != null) {
            waiting = null
            exo.setMediaItems(items, 0, offsetMs)
            exo.prepare()
            exo.playWhenReady = target.play
        } else {
            exo.addMediaItems(items)
            // Hàng đợi vừa cạn (đọc chậm hơn nghe): ExoPlayer đã ENDED, nối thêm không chắc tự phát tiếp - đặt chỗ phát rõ ràng.
            if (exo.playbackState == Player.STATE_ENDED) exo.seekTo(exo.mediaItemCount - items.size, 0)
        }
    }

    private fun startJob(chap: Chap, segment: Int) {
        val token = generation
        val text = chap.paragraphs[segment]
        val voice = voiceId
        inFlight = true
        live.incrementAndGet()
        syncWants()
        val bookId = Playback.bookId
        val online = PreparePlan.online(voice)
        if (policyVoice != voice) {
            policy.reset() // số đo là của giọng cũ
            policyVoice = voice
        }
        // Edge đang chậm: đọc song song đoạn kế (luồng thứ hai) để nó có sẵn trong bộ đệm khi tới lượt - hai lượt gọi cùng lúc, không hơn (Edge hạn chế khi dồn nhiều kết nối).
        // Việc nạp vào ExoPlayer vẫn lần lượt và đúng thứ tự: đoạn kế đọc xong sớm thì tới lượt nó chỉ lấy từ bộ đệm.
        val warm = if (online && policy.slow()) nextSpeakable(chap, segment)?.let { chap.paragraphs[it] } else null
        val fresh = stalled.takeFresh(chap.index, segment)
        // Đoạn vừa hỏng, tới nhịp hỏi lại mà người nghe còn âm thanh: hỏi thăm (một lượt, không thử lại, không giữ khoá) - xem [StalledClips].
        // Phần còn lại của đoạn phát luồng vừa đứt giữa chừng (uxfix58): người nghe còn đang nghe phần đã về, nhưng đoạn này là thứ họ sắp phải chờ - hỏi ngay, như đoạn họ đứng chờ (rank 0, phát luồng).
        val continuing = resume?.takeIf { it.chap === chap && it.segment == segment } // giữ tới khi phần nối đọc được ([onClipReady])
        val probe = continuing == null && StalledClips.isProbe(fresh, Playback.player?.let(::listenerHasAudio) == true)
        // Người nghe không còn âm thanh nào để nghe (nhảy tới, đầu chương, hàng đợi cạn): đoạn này là đoạn họ đang đứng chờ (rank 0), đoạn đọc song song ([warm]) kế nó - hết chỗ kết nối Edge thì đoạn gần
        // người nghe hơn đi trước, và việc nền (không rank) đứng sau cả hai (uxfix51). Đoạn nạp khi người nghe còn âm thanh: rank = số đoạn đã nạp sau đoạn đang phát + 1 (uxfix52; cũng là
        // tiêu đề / đoạn đầu của chương kế khi hàng đợi chạm cuối chương). Chỉ đoạn DÀI người nghe còn phải nghe (đang phát + đã nạp sau nó) mới tính (uxfix54: tiêu đề chương 2 giây đứng trước
        // đoạn 1 không đẩy đoạn 1 xuống rank 1 - cắt 3 mảnh thay vì 6, người nghe chờ thêm ~4 giây).
        val rank = if (continuing != null) 0 else Playback.player.let { exo ->
            StalledClips.listenerRank(exo?.let(::listenerHasAudio) == true, if (exo == null) 0 else longQueued(exo))
        }
        // Người nghe muốn nghe: giữ CPU (qua mạng thì cả Wi-Fi) tới khi lượt này xong - hàng đợi ExoPlayer cạn thì nó không giữ gì ([FetchWake]); đã tạm dừng thì không.
        val ticket = if (StalledClips.holdsWake(listenerWants, probe)) FetchWake.hold(network = online) else null
        val cancel = ClipCancel().also { jobs.add(it) }
        continuing?.cancel = cancel
        // Đoạn người nghe đứng chờ (rank 0) bằng giọng Edge: ExoPlayer nhận clip ngay khi byte đầu về (uxfix57, [LiveClips]); bấm giữa đoạn thì chỉ đọc từ chữ ấy ([SeekPlan.tailFrom]).
        val aim = waiting?.takeIf { it.chapterIndex == chap.index && it.segment == segment }
        val liveJob = if (LivePolicy.streams(voice, online, rank, probe, aim?.offsetMs, aim?.word ?: -1)) LiveJob(token, chap, segment, voice, continuing) else null
        liveJob?.cancel = cancel
        liveJob?.speed = Playback.player?.playbackParameters?.speed ?: 1f
        liveJob?.reach = soundReachesNanos()
        running = liveJob
        // Lượt này còn là việc hiện hành ở luồng đọc (thử lại, đọc lại sau lượt song song hỏng): cùng thế hệ, hay là lượt phát luồng được giữ qua lần đổi giọng ([kept]).
        val alive = { token == generation || (liveJob != null && liveJob === kept) }
        worker.execute {
            val began = System.nanoTime()
            val origin = originOf(bookId)
            val readings = readingsOf(bookId)
            // Đoạn đã đọc xong trong bộ đệm thì bấm giữa đoạn cũng lấy cả đoạn (không có gì để chờ); chưa có thì clip đuôi. Phần nối luôn là clip đuôi từ chữ chưa nghe (uxfix60): cả đoạn từ bộ
            // đệm mà nối sau phần đã về thì người nghe nghe lại từ đầu đoạn.
            val tailFrom = when {
                continuing != null -> continuing.from
                liveJob != null && !runCatching { cache().contains(voice, text, origin, readings) }.getOrDefault(false) -> SeekPlan.tailFrom(aim?.word ?: -1, text, true)
                else -> 0
            }
            liveJob?.tail = tailFrom
            val readText = if (tailFrom > 0) SeekPlan.tailText(text, tailFrom) else text
            // Lượt song song cũng là một kết nối tới Edge: tính vào `live` để "Làm trước" không mở thêm kết nối thứ ba (đọc thật + song song + làm trước).
            warm?.let { next ->
                live.incrementAndGet()
                worker.execute { try { warm(next, voice, origin, readings, token, StalledClips.rankAfter(rank, text)) } finally { live.decrementAndGet() } }
            }
            val result = try {
                val key = shareKey(voice, readText, origin, readings)
                LiveClips.receiving(liveJob) {
                    val (first, mine) = shared(key) { readWithRetry(alive, readText, voice, origin, readings, online, fresh, probe, cancel, rank) }
                    // Đoạn này đang được đọc song song mà lượt ấy hỏng (không thử lại): đọc lại cho đàng hoàng, có thử lại - và hỏi mới, lượt hỏng vừa rồi có thể đã làm giọng nghỉ.
                    if (!mine && first.isFailure && alive()) readWithRetry(alive, readText, voice, origin, readings, online, fresh = true, probe = probe, cancel = cancel, rank = rank) else first
                }
            } finally {
                jobs.remove(cancel)
                ticket?.let(FetchWake::release)
                live.decrementAndGet()
            }
            liveJob?.finish(result)
            result.getOrNull()?.let { clip ->
                // Người nghe đã tới đoạn này: đoạn làm trước thôi được ghim. Đọc thật (không phải lấy từ bộ đệm) bằng đúng giọng đã chọn thì ghi tốc độ.
                runCatching { cache().unpin(clip.voice, readText, origin, readings) }
                val seconds = (System.nanoTime() - began) / 1e9
                if (clip.voice == voice && seconds * 1000 > PrepareRunner.CACHED_MS) runCatching { speeds().recordRead(voice, readText, origin, readings, seconds, clip.durationMs / 1000.0) }
            }
            Playback.onMain { onClipReady(token, chap, segment, result, probe, tailFrom, liveJob, continuing) }
        }
    }

    /** Đoạn đọc được kế tiếp trong chương (bỏ dòng ngăn cảnh), null nếu hết chương. */
    private fun nextSpeakable(chap: Chap, segment: Int): Int? =
        ((segment + 1) until chap.paragraphs.size).firstOrNull { !chap.isBreak(it) }

    private fun shareKey(voice: String, text: String, origin: String?, readings: Map<String, String>?) =
        "$voice\u0000$origin\u0000${readings?.entries?.sortedBy { it.key }}\u0000$text"

    /** Chạy `work` một lần cho mỗi `key` đang chạy: lượt đến sau chờ kết quả của lượt đến trước. Trả (kết quả, có phải lượt của mình không). */
    private fun shared(key: String, work: () -> Result<Clip>): Pair<Result<Clip>, Boolean> {
        val mine = java.util.concurrent.FutureTask(java.util.concurrent.Callable { work() })
        val other = sharing.putIfAbsent(key, mine)
        if (other != null) return runCatching { other.get() }.getOrElse { Result.failure(it) } to false
        try {
            mine.run()
            return mine.get() to true
        } finally {
            sharing.remove(key, mine)
        }
    }

    /** Đọc sẵn một đoạn vào bộ đệm (kết quả bỏ): lần nạp thật của đoạn ấy sẽ lấy từ đó. Không thử lại - hỏng thì lần nạp thật tự lo. Thời gian đọc thật ghi vào [policy]
     *  (lượt nạp thật của đoạn này chỉ lấy từ bộ đệm / chờ lượt này nên không ghi gì - không thì Edge nhanh lại mà số đo đứng yên, "Edge chậm" dính mãi). */
    private fun warm(text: String, voice: String, origin: String?, readings: Map<String, String>?, token: Int = generation, rank: Int = EdgePieces.RANK_BACKGROUND) {
        val began = System.nanoTime()
        val (result, mine) = shared(shareKey(voice, text, origin, readings)) {
            val before = ClipBudget.enterRank(rank)
            try {
                policy.measure { runCatching { reader().read(text, voice, origin, readings, willRetry = true) } }
            } finally {
                ClipBudget.leaveRank(before)
            }
        }
        // Lượt thật (không phải bộ đệm) xong khi đang treo lỗi đọc: dịch vụ đã khoẻ lại ([serviceAnswered]).
        if (mine && result.isSuccess && (System.nanoTime() - began) / 1_000_000 > PrepareRunner.CACHED_MS) Playback.onMain { if (token == generation) serviceAnswered() }
    }

    /** Đọc một đoạn, thử lại lỗi thoáng qua của giọng trực tuyến ở nền ([ClipRetry]); việc đã cũ (tua, đổi chương, đổi giọng - `alive` false) thì thôi. */
    private fun readWithRetry(
        alive: () -> Boolean, text: String, voice: String, origin: String?, readings: Map<String, String>?, online: Boolean, fresh: Boolean = false, probe: Boolean = false, cancel: ClipCancel? = null, rank: Int = EdgePieces.RANK_BACKGROUND,
    ): Result<Clip> =
        ClipRetry.run(online, StalledClips.delaysFor(probe, RETRY_DELAYS_MS), sleep = { sleepWhileCurrent(alive, it) }, record = policy::record, cancel = cancel, rank = rank) { willRetry ->
            reader().read(text, voice, origin, readings, willRetry, fresh)
        }

    /** Nghỉ `ms` mili-giây; false nếu trong lúc ấy việc đã cũ (người nghe tua / đổi chương / đổi giọng - `generation` đổi), đã tắt, hay người nghe đã tạm dừng: lần thử lại không đáng gọi
     *  Edge khi chẳng ai chờ (máy tính cũng bỏ - listen/readAloud.ts retryLater); bấm phát lần sau thì [onPlay] xin lại đoạn. */
    private fun sleepWhileCurrent(alive: () -> Boolean, ms: Long): Boolean {
        val end = System.nanoTime() + ms * 1_000_000
        while (System.nanoTime() < end) {
            if (!alive() || !active || !listenerWants) return false
            Thread.sleep(50)
        }
        return alive() && active && listenerWants
    }

    /** [wantsPlay] cho luồng nền (ExoPlayer chỉ hỏi được ở luồng chính): cập nhật ở mọi chỗ người nghe đổi ý hay chỗ chờ đổi ([syncWants]). */
    @Volatile private var listenerWants = false

    /** Gọi ở luồng chính mỗi khi `waiting` hay `playWhenReady` đổi. */
    fun syncWants() {
        listenerWants = active && wantsPlay()
        if (!listenerWants) FetchWake.releaseAll() // chẳng ai chờ clip nữa: nhả khoá CPU / Wi-Fi ngay, không đợi lượt gọi Edge đang chạy dở xong
    }

    /** Đoạn đang phát luồng cho ExoPlayer ([LiveJob] đã có byte đầu); null khi không có. Luồng chính. */
    private var liveNow: LiveJob? = null

    /** Byte tiếng đầu tiên của đoạn người nghe đang chờ đã về (luồng chính): đặt nó vào ExoPlayer NGAY, không đợi đọc xong. Phần còn lại như [onClipReady]; đoạn xong thì [onClipReady] chỉ cập nhật mốc. */
    private fun onLiveStarted(job: LiveJob) {
        if (!current(job) || !active || job.resume?.stale == true) return
        job.resume?.takeIf { !it.settled }?.let {
            it.started = job // phần nối xin sớm: vào ExoPlayer khi phần đầu đóng ([settle])
            return
        }
        liveNow = job
        // Clip đầu đang giữ chờ đoạn này ([holdOpening]) phát TRƯỚC, đoạn này nối sau nó: `waiting` còn đó thì [deliver] thay cả hàng đợi và tiêu đề mất.
        releaseOpening(ready = true)
        // Dời chỗ nạp TRƯỚC khi đặt vào ExoPlayer (như [onClipReady]): setMediaItems báo đổi mục ngay trong lúc gọi.
        feedSegment = job.segment + 1
        deliver(listOf(itemFor(job.chap, job.segment, Uri.parse(LiveClips.uri(job.entry.id)), VoiceGain.db(job.voice), job.resume?.baseMs ?: 0L)), 0L)
        Playback.emit("state")
        if (job.cutWord >= 0) onLiveCut(job)
    }

    /** Đồng hồ của đoạn đang phát luồng không vượt chỗ này (ms trên đồng hồ đoạn): độ dài ước của đoạn (máy tính giữ độ dài ước tới khi clip xong), hay đầu phần nối nếu nó đã ở xa hơn. */
    private fun liveLimitMs(chap: Chap, segment: Int, baseMs: Long): Long = maxOf(chap.timeline.durationOf(segment), baseMs)

    /**
     * Mốc chữ tạm của đoạn đang phát luồng (luồng chính): màn đọc tô chữ theo đó tới khi clip xong. Clip đuôi: chữ trước chữ bấm mốc [0, 0]. Chữ chưa có tiếng đứng ngoài tầm đồng hồ ([SeekPlan.shownLiveWords]):
     * chữ sáng đứng ở chữ cuối đã có tiếng, không lóe sang chữ cuối đoạn; chỗ nối khi đứt ([SeekPlan.resumeWord]) vẫn nhận ra chúng (đầu >= chỗ đã nghe tới).
     */
    private fun onLiveWords(job: LiveJob, words: List<Span>) {
        if (!current(job) || !active || job.broke || job.chap.clips[job.segment] != null || job.resume?.let { !it.settled || it.stale } == true) return
        val base = job.resume?.baseMs ?: 0L
        val whole = when {
            job.resume != null -> SeekPlan.tailWords(job.tail, words, base, job.resume.prefix)
            job.tail > 0 -> SeekPlan.tailWords(job.tail, words)
            else -> words
        }
        job.chap.liveWords[job.segment] = SeekPlan.shownLiveWords(whole, job.tail, base + job.heardMs, liveLimitMs(job.chap, job.segment, base))
        notifyScript(job.chap)
    }

    /** Vị trí (chỉ số hàng đợi) của mục phát luồng của `job` trong ExoPlayer, -1 nếu không còn. Tìm theo địa chỉ clip: một đoạn đứt giữa chừng có hai mục (phần đã về, phần nối) cùng [Slot]. */
    private fun liveIndex(exo: Player, job: LiveJob): Int =
        (0 until exo.mediaItemCount).firstOrNull { isLiveItem(exo.getMediaItemAt(it), job) } ?: -1

    private fun isLiveItem(item: MediaItem, job: LiveJob): Boolean = item.localConfiguration?.uri?.toString() == LiveClips.uri(job.entry.id)

    /** Lượt phát luồng `job` không còn chạy (xong, đứt, hỏng): quên nó ở mọi chỗ theo dõi. */
    private fun liveEnded(job: LiveJob?) {
        if (job == null) return
        if (liveNow === job) liveNow = null
        if (running === job) running = null
        if (kept === job) kept = null
    }

    /**
     * Đoạn đang phát luồng đứt giữa chừng (luồng chính; uxfix58, máy tính: listen/readAloud.ts `salvage`). Phần đã về ở nguyên trong ExoPlayer và phát tới byte cuối ([LiveClips.Entry.awaitBytes]); phần còn lại
     * được xin NGAY, đồng thời với lúc nghe: clip đuôi từ chữ đầu tiên chưa nghe hết ([SeekPlan.resumeWord]; chưa có mốc nào thì từ đầu đoạn / đầu clip đuôi - đọc lặp vài chữ chấp nhận được), phát luồng như thường
     * và nối vào hàng đợi sau phần đã về (mục thứ hai cùng đoạn, [Slot.baseMs] giữ đồng hồ liền mạch). Lượt đọc cũ không thử lại nữa ([LiveJob.cancel]). Mọi chữ đã có tiếng trọn thì coi như đoạn xong
     * ([finishFromLive]). Chính phần nối mà cũng đứt (hỏng kép, uxfix60): chỗ nối dời tới chữ chưa nghe của phần nối, rồi đi đường lỗi quen của [onClipReady] (người nghe còn âm thanh để nghe thì không
     * dừng, hỏi lại theo nhịp; hết rồi mới báo MỘT lần).
     */
    private fun onLiveBroke(job: LiveJob, error: Exception) {
        // Phần đầu của lượt xin phần nối sớm ([onLiveCut]) đóng: chốt nó dù thế hệ đã đổi (đổi giọng giữ [resume] - [requeueAhead]).
        val early = resume?.takeIf { it.head === job && !it.settled }
        if ((early == null && !current(job)) || !active || job.broke) return
        val exo = Playback.player ?: return
        if (liveIndex(exo, job) < 0) {
            // Còn trong hàng giữ đầu chương ([Opening.queue]), chưa vào ExoPlayer: chưa ai nghe gì của nó - bỏ mục, đoạn đọc lại từ đầu; kết quả của lượt đọc (clip thay, hay lỗi)
            // vào [onClipReady] như đoạn chưa phát luồng, đúng một lần. Không bỏ thì tới hạn nhả cả mục hỏng lẫn clip thay nối sau nó.
            if (opening?.queue?.withdraw { isLiveItem(it, job) } == true) {
                liveEnded(job)
                feedChapter = job.chap.index
                feedSegment = job.segment
            }
            return
        }
        job.broke = true
        job.cancel?.cancel()
        liveEnded(job)
        val chap = job.chap
        val segment = job.segment
        val base = job.resume?.baseMs ?: 0L
        val received = base + job.entry.durationMs()
        val words = chap.liveWords[segment].orEmpty()
        val heard = minOf(base + job.heardMs, received)
        if (early != null) {
            settle(early, job, received, words, heard)
            return
        }
        feedChapter = chap.index
        feedSegment = segment
        inFlight = false
        if (SeekPlan.allHeard(words, heard, job.tail)) {
            finishFromLive(job)
            return
        }
        val from = SeekPlan.tailFrom(SeekPlan.resumeWord(words, heard, job.tail), chap.paragraphs[segment], true)
        val rest = Resume(chap, segment, from, received, words)
        resume = rest
        if (job.resume != null) {
            onClipReady(generation, chap, segment, Result.failure(error), false, job.tail, null, rest)
            return
        }
        pump()
    }

    /**
     * Một mảnh giữa của đoạn đang phát luồng hỏng hẳn trong lúc các mảnh trước nó còn đang về (luồng chính; uxfix63, máy tính: listen/readAloud.ts `salvageEarly`): tiếng sẽ dừng đúng trước chữ ấy, nên
     * phần nối (clip đuôi từ chữ ấy, rank 0, phát luồng) được xin NGAY - không đợi phần đầu về hết rồi mới báo lỗi (a59d e1: đợi thì người nghe chỉ còn 2,8 giây tiếng mà phần nối cần 4,8 giây, lặng
     * 2,11 giây). Phần đầu vẫn phát như thường; phần nối chỉ vào ExoPlayer khi phần đầu đóng ([settle]). Phần nối của chính một phần nối thì không: đường hỏng kép của [onLiveBroke] lo.
     */
    private fun onLiveCut(job: LiveJob) {
        val word = job.cutWord
        if (word < 0 || job.cutHandled || !current(job) || !active || job.broke || job.resume != null || liveNow !== job || resume != null) return
        val exo = Playback.player ?: return
        if (liveIndex(exo, job) < 0) return
        val chap = job.chap
        val segment = job.segment
        val from = job.tail + word
        if (from >= WordTokens.count(chap.paragraphs[segment])) return
        job.cutHandled = true
        resume = Resume(chap, segment, from, 0L, emptyList(), head = job)
        feedChapter = chap.index
        feedSegment = segment
        inFlight = false // lượt của phần đầu chạy nốt; kết quả của nó bị bỏ ([onLiveBroke] đặt `broke`)
        pump()
    }

    /**
     * Phần đầu của lượt xin sớm `rest` vừa đóng ở `received` ms (luồng chính): giờ mới biết đồng hồ của phần nối và mốc chữ đã nghe. Tiếng dừng đúng ở `rest.from`: phần nối vào ExoPlayer (byte đầu đã về
     * thì đặt ngay, kết quả đã về thì nhận luôn). Tiếng dừng sớm hơn (mảnh trước cũng hỏng): bỏ phần nối ấy, xin lại từ chữ đầu tiên chưa nghe - không bao giờ bỏ sót chữ.
     */
    private fun settle(rest: Resume, job: LiveJob, received: Long, words: List<Span>, heard: Long) {
        val chap = job.chap
        val segment = job.segment
        val from = SeekPlan.tailFrom(SeekPlan.resumeWord(words, heard, job.tail), chap.paragraphs[segment], true)
        rest.settled = true
        if (from >= rest.from) {
            rest.baseMs = received
            rest.prefix = words
            rest.started?.let { started ->
                rest.started = null
                onLiveStarted(started)
            }
            rest.parked?.let { parked ->
                rest.parked = null
                parked()
            }
            return
        }
        rest.stale = true
        rest.cancel?.cancel()
        rest.started?.let(::liveEnded)
        resume = Resume(chap, segment, from, received, words)
        feedChapter = chap.index
        feedSegment = segment
        inFlight = false
        pump()
    }

    /**
     * Clip phát luồng coi như XONG dù lượt đọc không trả clip (uxfix60): mọi chữ đã có tiếng trọn rồi mới đứt (máy tính cũng coi là xong), hay tiếng đã về đủ mà bước sau đó hỏng. Mục đang phát giữ
     * nguyên (phát tới byte cuối); đoạn có độ dài thật = phần đã về, mốc chữ = mốc tạm cuối cùng; đọc tiếp đoạn kế.
     */
    private fun finishFromLive(job: LiveJob) {
        liveEnded(job)
        val chap = job.chap
        val segment = job.segment
        val base = job.resume?.baseMs ?: 0L
        val duration = base + job.entry.durationMs()
        val words = chap.liveWords[segment].orEmpty().map { Span(minOf(it.start, duration), minOf(it.end, duration)) }
        if (resume?.let { it.chap === chap && it.segment == segment } == true) resume = null
        chap.clips[segment] = Clip(job.entry.file() ?: File(""), duration, words, job.voice, job.tail, base)
        chap.liveWords[segment] = null
        chap.timeline.setDuration(segment, duration)
        feedChapter = chap.index
        feedSegment = segment + 1
        inFlight = false
        notifyScript(chap)
        prune()
        pump()
        Playback.emit("state")
    }

    /** `rest`: lượt này là phần nối của đoạn đứt giữa chừng ([Resume]; phát luồng hay không). */
    private fun onClipReady(token: Int, chap: Chap, segment: Int, result: Result<Clip>, probe: Boolean = false, tail: Int = 0, live: LiveJob? = null, rest: Resume? = live?.resume) {
        if ((token != generation && (live == null || live !== kept)) || !active) return
        if (live?.broke == true) return // đã đứt giữa chừng và [onLiveBroke] lo xong: lượt đọc này chỉ chạy nốt (đã bị huỷ), kết quả của nó không còn là của ai
        if (rest?.stale == true) return // phần nối xin sớm từ chữ sau chỗ tiếng thật dừng: đã thay bằng lượt khác ([settle])
        if (rest != null && !rest.settled) {
            rest.parked = { onClipReady(token, chap, segment, result, probe, tail, live, rest) } // phần đầu chưa đóng: chưa biết đồng hồ của phần nối
            return
        }
        inFlight = false
        releaseOpening(ready = result.isSuccess) // chưa đủ số đo: đoạn kế xong thì nhả sớm; lịch nhiều đoạn giữ tới hạn. Lượt hỏng: nhả phần đã có.
        val streaming = live?.takeIf { it.started }
        val clip = result.getOrElse { error ->
            // Đã phát luồng mà lượt đọc hỏng không qua lời báo đứt ([LiveJob.failed]): tiếng đã về đủ thì đoạn coi như xong; chưa đủ mà mục còn trong hàng đợi thì như đứt giữa chừng.
            val exo = Playback.player
            if (streaming != null && streaming.entry.done) {
                finishFromLive(streaming)
                return
            }
            if (streaming != null && exo != null && liveIndex(exo, streaming) >= 0) {
                onLiveBroke(streaming, error as? Exception ?: VoiceException("Không đọc được đoạn này"))
                return
            }
            // Đoạn hết cách đọc: dịch vụ trục trặc (kể cả lời cuối của [ClipReader]) hay lỗi giọng khác - nhớ đoạn này, lượt đọc kế của nó là lần hỏi mới ([StalledClips]), dù do nhịp hỏi lại,
            // do người nghe tới nơi hay do "Thử lại". Người nghe đã tạm dừng (kể cả lần thử lại bị bỏ vì thế): bấm phát thì [onPlay] xin lại đoạn này. Người nghe còn âm thanh để nghe: chưa ai chờ
            // đoạn này - không dừng, không báo lỗi, [pump] hỏi lại sau nhịp nghỉ hay ngay khi hàng đợi cạn (a46; a50: cả lỗi không phải dịch vụ, như máy tính). Lần hỏi thăm hỏng không bao giờ dừng.
            // Phần nối hỏng: [resume] còn nguyên nên mọi lần hỏi lại vẫn nối đúng chữ chưa nghe.
            liveEnded(live)
            val listening = exo?.let(::listenerHasAudio) == true
            val verdict = StalledClips.verdict(error, wantsPlay(), listening, probe)
            if (verdict != StalledClips.Verdict.FAIL || StalledClips.isServiceTrouble(error)) stalled.failed(chap.index, segment)
            when (verdict) {
                StalledClips.Verdict.QUIET -> return
                StalledClips.Verdict.DEFER -> {
                    pump()
                    return
                }
                StalledClips.Verdict.FAIL -> Unit
            }
            // Phần nối hỏng hẳn khi người nghe đã nghe hết phần đã về: chỗ chờ là ĐÚNG chữ chưa nghe (máy tính `failRest`) - "Thử lại" đọc clip đuôi từ chữ ấy, không đọc lại từ đầu đoạn.
            if (rest != null && resume === rest) {
                resume = null
                waiting = Target(chap.index, segment, if (rest.from > 0) 0L else rest.baseMs, if (rest.from > 0) rest.from else -1, exo?.playWhenReady == true)
            }
            fail((error as? VoiceException)?.message ?: "Không đọc được đoạn này (${error.message})", chap.index to segment)
            return
        }
        // Clip đuôi: `words` đủ chữ của đoạn (chữ trước chữ bấm mốc [0, 0]), âm thanh bắt đầu từ chữ ấy ([SeekPlan.tailWords]).
        // Phần nối sau phần đã về (uxfix58): file bắt đầu ở `baseMs` của đoạn; độ dài và mốc chữ trên đồng hồ cả đoạn, chữ đã nghe giữ mốc của phần đã về.
        val whole = when {
            rest != null -> Clip(clip.file, rest.baseMs + clip.durationMs, SeekPlan.tailWords(tail, clip.words, rest.baseMs, rest.prefix), clip.voice, tail, rest.baseMs)
            tail > 0 -> Clip(clip.file, clip.durationMs, SeekPlan.tailWords(tail, clip.words), clip.voice, tail)
            else -> clip
        }
        liveEnded(live)
        if (rest != null && resume === rest) resume = null
        notices.forget()
        chap.clips[segment] = whole
        chap.liveWords[segment] = null
        chap.timeline.setDuration(segment, whole.durationMs)
        // Đọc được đoạn mới: lỗi cũ còn treo trên màn (vd người nghe nhảy sang chỗ khác sau khi dừng vì lỗi) không còn đúng.
        if (failure == null) Playback.clearError()
        // Đoạn đã vào ExoPlayer từ lúc byte đầu về và luồng đọc xong lành lặn: không nạp lại, chỉ có độ dài thật và mốc chữ thật ([LiveJob.finish] đã đổi chỗ file cho các lần mở sau).
        // Luồng mà hỏng khi mục còn trong hàng đợi thì [LiveJob.failed] đã đưa sang [onLiveBroke] (lượt này bị bỏ ở trên); mục không còn (đã bị bỏ khỏi hàng đợi) thì nạp clip như mục mới.
        val item = if (streaming != null && streaming.entry.failure == null) null else clipItem(chap, segment, whole)
        val target = waiting
        // Dời chỗ nạp TRƯỚC khi đặt vào ExoPlayer: setMediaItems báo đổi mục ngay trong lúc gọi (onMediaTransition -> onClipChanged -> pump), và pump lúc ấy
        // mà còn thấy đoạn này là "đoạn kế" thì đọc lại nó - hàng đợi có hai lần cùng một đoạn, đồng hồ ảo lùi về đầu đoạn (thấy 03-10 trên máy thật).
        feedSegment = segment + 1
        // Clip thay cho mục phát luồng hỏng còn nằm trong hàng giữ đầu chương: mục ấy chưa ai nghe, bỏ đi để chỉ clip này được nhả.
        if (item != null && streaming != null) opening?.queue?.withdraw { isLiveItem(it, streaming) }
        if (item != null) {
            val offset = if (target != null) SeekPlan.offsetIn(whole, target.word, target.offsetMs) else 0L
            // Lịch còn đang tính ([planning]): không tính lần hai - lần ấy thay mục đang chờ lịch và một trong hai mục mất.
            if (opening != null || planning || target == null || !holdOpening(chap, segment, whole, target, item, offset)) deliver(listOf(item), offset)
        }
        notifyScript(chap)
        prune()
        pump()
        Playback.emit("state")
    }

    /**
     * Mở chương bằng giọng trên máy: đủ số đo cả chi phí cố định mỗi khúc lẫn giây tiếng thì giữ theo lịch 60 s đầu ([OpeningSchedule]), tối đa 6 s. Đoạn tới trong lúc giữ nối vào
     * [Opening.queue], không nhả sớm chỉ vì đoạn kế đã xong. Chưa đủ số đo (hay nhảy giữa chương): giữ nguyên luật cũ, tối đa 1,5 s và nhả sớm theo [LocalLive.charsBeforeStreamStarts].
     * [pump] vẫn đọc tuần tự vì `waiting` còn đó. True = đã giữ, hay lịch đang tính ở luồng nền ([planning]): xong thì giữ hoặc phát, rồi mới [pump] - kết quả y như tính trên luồng chính.
     */
    private fun holdOpening(chap: Chap, segment: Int, clip: Clip, target: Target, item: MediaItem, offset: Long): Boolean {
        if (!target.play || PreparePlan.online(voiceId)) return false
        val next = nextSpeakable(chap, segment) ?: return false
        val text = chap.paragraphs[next]
        val bookId = Playback.bookId
        val origin = originOf(bookId)
        val readings = readingsOf(bookId)
        val cached = runCatching { cache().contains(voiceId, text, origin, readings) }.getOrDefault(false)
        val perChar = runCatching { speeds().secondsPerChar(voiceId) }.getOrNull()
        val measuredAudio = runCatching { speeds().audioPerChar(voiceId) }.getOrNull()
        val audioPerChar = measuredAudio ?: LocalLive.AUDIO_PER_CHAR
        val work = if (segment == 0 && measuredAudio != null) runCatching { speeds().work(voiceId) }.getOrNull() else null
        // Đoạn kế nhiều khúc thì nhập luồng được ngay khi đủ điều kiện bắt đầu ([onLiveStarted]): chỉ cần giữ tới lúc ấy, không phải tới khi đọc xong cả đoạn.
        val speed = (Playback.player?.playbackParameters?.speed ?: 1f).toDouble()
        val chars = if (cached) null else LocalLive.charsBeforeStreamStarts(voiceId, text, origin, readings, perChar, speed, audioPerChar)
        val legacy = { ReadAheadPolicy.openingHoldMs(clip.durationMs - offset, chars, perChar, speed, audioPerChar) }
        val model = work ?: return holdFor(legacy(), false, item, offset)
        // Đọc cả chương để xét RTF kéo dài, chỉ hạn chế lịch thiếu tiếng ở cửa sổ đầu. Cắt cả chương và tra bộ đệm từng đoạn: luồng nền, không chặn luồng chính.
        val token = generation
        val voice = voiceId
        val store = runCatching { cache() }.getOrNull()
        planning = true
        planner.plan({ token == generation }, {
            OpeningSchedule.forChapter(voice, chap.paragraphs, chap::isBreak, chap.gaps, segment, clip.durationMs - offset, model, audioPerChar, speed, origin, readings) {
                store!!.contains(voice, it, origin, readings)
            }
        }) { schedule ->
            Playback.onMain {
                if (token != generation || !planning) return@onMain
                planning = false
                if (!holdFor(schedule ?: legacy(), schedule != null, item, offset)) deliver(listOf(item), offset)
                pump()
                Playback.emit("state")
            }
        }
        return true
    }

    /** Giữ clip đầu [wait] ms ([holdOpening]); [scheduled] = theo lịch nhiều đoạn. False = không giữ, người gọi phát ngay. */
    private fun holdFor(wait: Long, scheduled: Boolean, item: MediaItem, offset: Long): Boolean {
        if (wait <= 0) return false
        val token = generation
        opening = Opening(token, item, offset, scheduled, System.nanoTime() + wait * 1_000_000)
        main.postDelayed({
            if (opening?.token == token) {
                releaseOpening()
                pump()
                Playback.emit("state")
            }
        }, wait)
        return true
    }

    /** Phát clip đang được giữ ([holdOpening]), nếu còn là việc hiện hành. `setMediaItems` gọi lồng [pump]: chặn nó - đoạn kế đang đọc, hay người gọi lo tiếp. */
    private fun releaseOpening(ready: Boolean = false) {
        val held = opening ?: return
        if (!held.queue.releases(ready)) return
        opening = null
        if (held.token != generation || waiting == null) return
        val busy = inFlight
        inFlight = true
        try {
            deliver(held.queue.items, held.offsetMs)
        } finally {
            inFlight = busy
        }
    }

    private fun clipItem(chap: Chap, segment: Int, clip: Clip): MediaItem = itemFor(chap, segment, Uri.fromFile(clip.file), VoiceGain.db(clip.voice), clip.baseMs)

    private fun itemFor(chap: Chap, segment: Int, uri: Uri, gainDb: Double, baseMs: Long = 0L): MediaItem {
        val chapter = chapters()[chap.index]
        val metadata = MediaMetadata.Builder()
            .setTitle(chapter.title).setArtist(mediaArtist(Playback.narrator, Playback.bookTitle)).setAlbumTitle(Playback.bookTitle)
            .setDisplayTitle(chapter.title).setSubtitle(Playback.bookTitle)
        artwork?.let { metadata.setArtworkData(it, MediaMetadata.PICTURE_TYPE_FRONT_COVER) }
        return MediaItem.Builder()
            .setMediaId(chapter.id.toString())
            .setUri(uri)
            .setTag(Slot(chap.index, segment, gainDb, StalledClips.isLong(chap.paragraphs[segment]), baseMs))
            .setMediaMetadata(metadata.build())
            .build()
    }

    /** Bỏ các đoạn đã phát xa (chỉ giữ một đoạn ngay trước đoạn đang nghe để tua lùi ngắn) cho hàng đợi không dài ra mãi; đoạn đọc bằng cách đọc cũ
     *  ([readingsChanged]) thì bỏ ngay khi đã qua. */
    private fun prune() {
        val exo = Playback.player ?: return
        val index = exo.currentMediaItemIndex
        if (index > 1) exo.removeMediaItems(0, index - 1)
        val stale = staleParagraph ?: return
        val current = currentSlot()
        if (current != null && current.chapterIndex == stale.first && current.segment == stale.second) return
        staleParagraph = null
        val at = exo.currentMediaItemIndex
        val old = (0 until at).filter { i -> (exo.getMediaItemAt(i).localConfiguration?.tag as? Slot)?.let { it.chapterIndex == stale.first && it.segment == stale.second } == true }
        for (i in old.reversed()) exo.removeMediaItem(i)
    }

    /** ExoPlayer vừa sang một đoạn (hay mục) khác. */
    fun onClipChanged() {
        if (!active) return
        val live = currentSlot()?.takeIf { it.segment >= 0 }?.chapterIndex
        chaps.keys.retainAll { it == live || it == feedChapter || it == waiting?.chapterIndex }
        prune()
        pump()
    }

    /**
     * ExoPlayer chạy hết hàng đợi. True = đã xử lý (đang chờ đọc đoạn kế, hay dừng vì hẹn giờ, hay sang chương kế); false = hết cuốn thật.
     */
    fun handleEnded(): Boolean {
        if (!active) return false
        if (waiting != null || inFlight || failure != null) return true
        pump()
        if (inFlight || waiting != null || failure != null) return true
        if (SleepTimer.mode == SleepTimer.Mode.CHAPTER) {
            SleepTimer.onPausedAtChapterEnd()
            Playback.saveNow()
            Playback.emit("pause")
            return true
        }
        val current = Playback.currentChapter ?: return false
        val index = chapters().indexOfFirst { it.id == current.id }
        if (index in 0 until chapters().size - 1 && feedChapter > index) {
            if (chapters()[index + 1].isText && needsConsent()) {
                startAt(index + 1, 0, false, hold = true)
                Playback.saveNow()
                Playback.emit("pause")
                return true
            }
            startAt(index + 1, 0, true)
            return true
        }
        return false
    }

    /** Hẹn giờ "hết chương" vừa bật lúc đang đọc to: bỏ các đoạn của chương SAU đã nạp sẵn để hàng đợi cạn đúng cuối chương này. */
    fun stopAtChapterEnd() {
        val exo = Playback.player ?: return
        val slot = currentSlot()?.takeIf { it.segment >= 0 } ?: return
        var first = -1
        for (i in exo.currentMediaItemIndex + 1 until exo.mediaItemCount) {
            val other = exo.getMediaItemAt(i).localConfiguration?.tag as? Slot
            if (other == null || other.chapterIndex != slot.chapterIndex) {
                first = i
                break
            }
        }
        if (first >= 0) exo.removeMediaItems(first, exo.mediaItemCount)
        if (first >= 0 || feedChapter != slot.chapterIndex) {
            bumpGeneration()
            inFlight = false
            val last = (exo.getMediaItemAt(exo.mediaItemCount - 1).localConfiguration?.tag as? Slot)?.takeIf { it.chapterIndex == slot.chapterIndex }
            feedChapter = slot.chapterIndex
            feedSegment = (last?.segment ?: slot.segment) + 1
        }
    }

    /** Chưa biết đang ở đâu trong chương (chương chữ không đọc được chữ): đừng lưu vị trí 0 đè chỗ nghe dở. */
    fun unknownPlace(): Boolean = active && Playback.player?.currentMediaItem == null && positionMs() == null

    /**
     * Người nghe bấm phát. True = đã xử lý hết (lỗi đọc: thử lại đúng đoạn hỏng; hàng đợi đã chạy hết: đọc lại từ chỗ đang đứng); false = để Playback phát như thường
     * (đang chờ đọc đoạn thì chỉ ghi nhớ là muốn phát).
     */
    fun onPlay(): Boolean {
        if (!active) return false
        if (retryAfterFailure()) return true
        waiting?.play = true
        syncWants()
        if (held) held = false
        val exo = Playback.player ?: return false
        if (waiting == null && !inFlight && exo.playbackState == Player.STATE_ENDED && inText()) {
            val index = chapterIndexNow() ?: return false
            val ms = positionMs() ?: return false
            // Hết cuốn: nghe lại từ đầu như nút "Nghe lại" trong app (EndPlan); báo "chapter" để giao diện bỏ trạng thái "đã nghe hết" và theo sang chương đầu.
            val spot = EndPlan.restartSpot(index, chapters().size, ms, durationMs() ?: ms)
            startAt(spot.chapterIndex, spot.offsetMs, true)
            Playback.emit("chapter")
            return true
        }
        // Đoạn đang đọc dở bị bỏ khi người nghe tạm dừng (lần thử lại - [sleepWhileCurrent]) và hàng đợi còn chưa cạn: nạp tiếp từ đây (không việc gì chạy thì pump không làm gì).
        pump()
        return false
    }

    /** Người nghe bấm dừng lúc đang chờ đọc đoạn đầu: khi đoạn tới thì đừng tự phát. */
    fun onPause() {
        errorPause.listenerActed()
        waiting?.play = false
        syncWants()
    }

    private var recoveries = ArrayDeque<Long>()

    /** ExoPlayer lỗi lúc phát một đoạn (file đã bị dọn khỏi bộ nhớ đệm...): đọc lại đúng chỗ, tối đa 3 lần trong 30 giây. True nếu đã xử lý. */
    fun recoverFromPlayerError(): Boolean {
        if (!active || currentSlot()?.segment?.let { it >= 0 } != true) return false
        val now = System.currentTimeMillis()
        while (recoveries.isNotEmpty() && now - recoveries.first() > 30_000) recoveries.removeFirst()
        if (recoveries.size >= 3) return false
        recoveries.addLast(now)
        val index = chapterIndexNow() ?: return false
        val ms = positionMs() ?: return false
        val slot = currentSlot()!!
        chaps[index]?.clips?.set(slot.segment, null)
        startAt(index, ms, true)
        return true
    }

    /**
     * Bấm phát sau một lỗi đọc: thử lại đúng chỗ đã hỏng. True nếu đã nhận. `byItself` (dịch vụ trả lời lại - [serviceAnswered]): máy tự hỏi lại - lời báo đang có GIỮ NGUYÊN tới khi đọc được (uxfix60;
     * trước đây gỡ đi rồi hỏng nữa thì dựng lời báo mới), hỏng nữa ở đúng chỗ ấy chỉ cập nhật nó ([FailureNotice]).
     */
    fun retryAfterFailure(byItself: Boolean = false): Boolean {
        if (!active || failure == null) return false
        failure = null
        if (!byItself) Playback.clearError()
        val target = waiting
        retryingByItself = byItself
        try {
            if (byItself) notices.retryingByItself()
            if (target != null) startAt(target.place(), true)
            else {
                Playback.player?.playWhenReady = true
                pump()
            }
        } finally {
            retryingByItself = false
        }
        return true
    }

    /** Đang trong lần máy tự hỏi lại ([retryAfterFailure] `byItself`): [startAt] không coi đó là người nghe chọn chỗ mới. */
    private var retryingByItself = false

    /** `spot` = (chương, đoạn) hỏng nếu biết: máy tự hỏi lại đúng chỗ vừa báo mà hỏng nữa thì không báo lần nữa ([FailureNotice]). */
    private fun fail(message: String, spot: Pair<Int, Int>? = null) {
        failure = message
        inFlight = false
        errorPause.failed(wantsPlay())
        Playback.fail(message, spot?.let { notices.shouldNotify(it.first, it.second) } ?: true.also { notices.forget() })
    }

    /**
     * Một lượt đọc THẬT (qua mạng, không phải lấy từ bộ đệm) vừa xong trong lúc đang treo lỗi đọc: dịch vụ khoẻ lại, lỗi cũ không còn đúng. Dừng vì lỗi (người nghe đang nghe thì đoạn họ chờ hỏng) -> thử lại
     * đúng đoạn hỏng và tự nghe tiếp khi nó sẵn sàng; người nghe đã tự dừng -> chỉ gỡ thông báo, bấm phát vẫn thử lại như cũ ([retryAfterFailure]). Máy tính: "recovered" trong listen/readAloud.ts.
     */
    private fun serviceAnswered() {
        if (!active || failure == null) return
        when (errorPause.recovered()) {
            ErrorPause.Recovery.RESUME -> retryAfterFailure(byItself = true)
            ErrorPause.Recovery.CLEAR -> Playback.clearError()
        }
    }

    // ---- kịch bản (mốc thời gian) cho màn đọc -----------------------------------------------------------------

    private fun notifyScript(chap: Chap) {
        val id = chapters().getOrNull(chap.index)?.id ?: return
        val book = Playback.bookId
        scriptListeners.toList().forEach { runCatching { it(book, id) } }
    }

    /**
     * Mốc các đoạn của một chương cho màn đọc (cùng đồng hồ với kịch bản audio của Studio: giây từ đầu chương cho câu, ms từ đầu chương cho từng chữ). Đoạn
     * chưa đọc: `words` rỗng, `start`/`end` là ước lượng. Chương đang nạp lấy từ đồng hồ ảo; chương khác chỉ thấy các đoạn còn trong bộ nhớ đệm. Phải gọi trên
     * luồng chính nếu cuốn đang nạp.
     */
    fun script(bookId: String, chapterId: Int): JSONObject {
        val chap = if (bookId == Playback.bookId && active) {
            chapters().indexOfFirst { it.id == chapterId }.takeIf { it >= 0 }?.let(::chapFor)
        } else {
            peek(bookId, chapterId)
        }
        val segments = JSONArray()
        if (chap != null) {
            for (i in chap.paragraphs.indices) {
                val start = chap.timeline.startOf(i)
                val words = JSONArray()
                (chap.clips[i]?.words ?: chap.liveWords[i])?.forEach { words.put(JSONArray().put(start + it.start).put(start + it.end)) }
                segments.put(JSONObject().put("index", i).put("start", start / 1000.0).put("end", chap.timeline.endOf(i) / 1000.0).put("words", words)
                    .put("timed", chap.clips[i] != null))
            }
        }
        return JSONObject().put("segments", segments)
    }

    /**
     * Giây bắt đầu từng đoạn của chương `chapterId` (cuốn đang nạp) trên đồng hồ ảo và tổng độ dài chương (giây) - đúng các con số `script` đưa cho màn đọc, không dựng
     * JSON: nhạc nền theo cảnh ([vn.abook.player.SceneAnchor]) hỏi mỗi nhịp để biết có clip mới về chưa. null: cuốn khác / chương không phải chữ / chưa nạp. Luồng chính.
     */
    fun segmentTiming(bookId: String, chapterId: Int): Pair<DoubleArray, Double>? {
        if (bookId != Playback.bookId || !active) return null
        val chap = chapters().indexOfFirst { it.id == chapterId }.takeIf { it >= 0 }?.let(::chapFor) ?: return null
        return DoubleArray(chap.paragraphs.size) { chap.timeline.startOf(it) / 1000.0 } to chap.timeline.totalMs() / 1000.0
    }

    /**
     * Đoạn nào đã đọc bằng giọng đang chọn (còn trong bộ nhớ đệm) thì đồng hồ ảo dùng độ dài thật ngay từ lúc nạp chương: nghe tiếp từ giây đã lưu (widget, xe
     * hơi, mở lại app) rơi đúng đoạn đã nghe, không lệch theo ước lượng 14 ký tự/giây.
     */
    private fun fromCache(chap: Chap, origin: String?, readings: Map<String, String>) {
        val cache = runCatching { cache() }.getOrNull() ?: return
        for (i in chap.paragraphs.indices) if (!chap.isBreak(i)) cache.get(voiceId, chap.paragraphs[i], origin, readings)?.let {
            chap.clips[i] = it
            chap.timeline.setDuration(i, it.durationMs)
        }
    }

    /** Chương của một cuốn không đang nạp: chữ từ gói sách, mốc từ bộ nhớ đệm (nếu đoạn đã từng được đọc bằng giọng đang chọn). */
    private fun peek(bookId: String, chapterId: Int): Chap? =
        parsedChapters(bookId, listOf(chapterId))[chapterId]?.let { Chap(-1, it.second).also { chap -> fromCache(chap, originOf(bookId), readingsOf(bookId)) } }

    /**
     * Các chương chỉ-có-chữ `ids` của một cuốn trên máy: mã -> (tên chương người nghe thấy, các đoạn đúng như lúc nghe). Chương không có chữ hay không đọc được
     * thì không có trong kết quả. Không cần cuốn đang nạp ("Làm trước" chạy cả khi app đã đóng).
     */
    fun textChapters(bookId: String, ids: List<Int>): Map<Int, Pair<String, List<String>>> =
        parsedChapters(bookId, ids).mapValues { (_, chapter) -> chapter.first to chapter.second.filter { !it.sceneBreak }.map { it.text } }

    /** Như [textChapters] nhưng giữ cả dòng ngăn cảnh (trình phát chỉ lặng ở đó): "Làm trước" không đọc chúng nên không đếm. */
    internal fun parsedChapters(bookId: String, ids: List<Int>): Map<Int, Pair<String, List<Paragraphs.Paragraph>>> {
        val manifest = runCatching { Store.manifest(bookId) }.getOrNull()
        val array = manifest?.optJSONArray("chapters") ?: return emptyMap()
        val wanted = ids.toSet()
        val out = HashMap<Int, Pair<String, List<Paragraphs.Paragraph>>>()
        for (chapter in (0 until array.length()).map { array.getJSONObject(it) }) {
            val id = chapter.optInt("id")
            if (id !in wanted) continue
            val entry = chapter.optString("text").takeIf { it.startsWith("texts/") } ?: continue
            // Các dòng người nghe đã bỏ khỏi phần đọc (khoá `skip`) cũng bỏ ở đây: đoạn phải chia đúng như lúc nghe.
            val paragraphs = runCatching {
                Paragraphs.split(Paragraphs.withoutLines(Store.file(bookId, entry).readText(Charsets.UTF_8), skipOf(manifest, id)))
            }.getOrNull() ?: continue
            out[id] = chapter.optString("title") to paragraphs
        }
        return out
    }
}
