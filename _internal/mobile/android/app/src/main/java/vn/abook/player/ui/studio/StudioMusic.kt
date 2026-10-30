package vn.abook.player.ui.studio

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.ClipSpec
import vn.abook.player.ClipState
import vn.abook.player.StudioErrors
import vn.abook.player.StudioPaths
import vn.abook.player.StudioPoller
import vn.abook.player.StudioPolling
import vn.abook.player.formatSize
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.music.MusicCredit
import vn.abook.player.ui.music.MusicLevels
import vn.abook.player.ui.music.MusicText

// Tab "Nhạc nền" (NATIVE_REMOTE_STUDIO.md §6.7). Port từ MusicTab.tsx / musicScenes.ts / musicLevels.ts: ba tầng chỉnh - cả cuốn (bật/tắt, thể loại, mức nhạc),
// từng đoạn (im lặng, bỏ ghim, đổi bài), từng bài (không dùng bài này nữa). Máy tự làm hết; mọi chỉnh ở đây là tuỳ chọn. Sửa nhạc không bao giờ phải đọc lại giọng.
// Bỏ so với web (nhạc cá nhân nằm trên máy tính, `/api/music/local` không có trong `ALLOWED`): "Nhạc của tôi", nhập nhạc, nhóm "Nhạc của tôi" của "Đổi bài".

/** Một đoạn nhạc (web `Scene`). `key` là khoá gửi lại khi ghim / im lặng / đổi bài. */
@Immutable
data class MusicScene(
    val key: String,
    val chapterId: Int,
    val start: Double,
    val end: Double,
    val valence: Double,
    val tension: Double,
    /** 13 cường độ cảm xúc độc lập 0..1: đoạn có thể vừa buồn vừa dịu. */
    val emotions: Map<String, Double>,
    val link: String?,
    val pinned: Boolean,
    val silenced: Boolean,
    /** Mảnh nối tiếp của một đoạn dài: chơi tiếp bài của đoạn trên, không phải một lựa chọn riêng. */
    val continued: Boolean,
    /** Bài đã ghim không còn dùng được trên máy này: lần dựng này đoạn dùng bài khác. */
    val pinUnavailable: Boolean,
    /** "llm" | "chapter" | "student" | "labels": ai đọc không khí của đoạn. */
    val moodSource: String,
)

@Immutable
data class MusicTrack(val title: String, val creator: String, val source: String, val attribution: String, val license: String)

/** Lượt tải sẵn nhạc nền của cuốn: bài thứ `done` trong `total`, MB đã tải / tổng (0 = chưa biết cỡ). */
@Immutable
data class MusicDownload(val active: Boolean, val done: Int, val total: Int, val doneBytes: Long, val totalBytes: Long)

/** Lời đáp của `GET /api/books/<id>/music`. */
@Immutable
data class MusicView(
    /** Có kế hoạch nhạc chưa (sau khi sách đã phân tích). */
    val planned: Boolean,
    val enabled: Boolean,
    val levelDb: Double,
    val genre: String?,
    val scenes: List<MusicScene>,
    val tracks: Map<String, MusicTrack>,
    val banned: List<String>,
    val bannedTracks: Map<String, MusicTrack>,
    val error: String,
    val moodsRunning: Boolean,
    val moodsError: String,
    val download: MusicDownload?,
    /** (mã, tên tiếng Việt). */
    val genres: List<Pair<String, String>>,
    val emotionNames: Map<String, String>,
)

/** Model AI đọc không khí cả đoạn (tuỳ chọn, tải trên máy tính). */
@Immutable
data class MoodsModel(val installed: Boolean, val downloading: Boolean, val percent: Int?, val error: String, val downloadable: Boolean)

@Immutable
data class MusicAlternative(val link: String, val title: String, val creator: String, val duration: Double, val score: Double)

internal object StudioMusicJson {
    private fun track(json: JSONObject) = MusicTrack(json.text("title"), json.text("creator"), json.text("source"), json.text("attribution"), json.text("license"))

    private fun tracks(json: JSONObject?): Map<String, MusicTrack> =
        json?.keys()?.asSequence()?.mapNotNull { key -> json.optJSONObject(key)?.let { key to track(it) } }?.toMap().orEmpty()

    private fun scene(json: JSONObject) = MusicScene(
        key = json.text("key"),
        chapterId = json.optInt("chapterId"),
        start = json.optDouble("start", 0.0),
        end = json.optDouble("end", 0.0),
        valence = json.optDouble("valence", 0.0),
        tension = json.optDouble("tension", 0.0),
        emotions = json.optJSONObject("emotions")?.let { e -> e.keys().asSequence().associateWith { e.optDouble(it, 0.0) } }.orEmpty(),
        link = json.textOrNull("link")?.takeIf { it.isNotEmpty() },
        pinned = json.optBoolean("pinned"),
        silenced = json.optBoolean("silenced"),
        continued = json.optBoolean("continued"),
        pinUnavailable = json.optBoolean("pinUnavailable"),
        moodSource = json.text("moodSource"),
    )

    fun view(json: JSONObject): MusicView {
        val plan = json.optJSONObject("plan")
        val overrides = json.optJSONObject("overrides") ?: JSONObject()
        val taxonomy = json.optJSONObject("taxonomy") ?: JSONObject()
        val genres = taxonomy.optJSONObject("genres")
        val emotions = taxonomy.optJSONObject("emotions")
        val download = json.optJSONObject("download")
        return MusicView(
            planned = plan != null,
            enabled = overrides.optBoolean("enabled", true),
            levelDb = overrides.optDouble("levelDb", MusicLevels.DEFAULT_DB),
            genre = overrides.textOrNull("genre")?.takeIf { it.isNotEmpty() },
            scenes = plan?.optJSONArray("scenes").objects().map(::scene).filter { it.key.isNotEmpty() },
            tracks = tracks(plan?.optJSONObject("tracks")),
            banned = overrides.optJSONArray("banned").strings(),
            bannedTracks = tracks(json.optJSONObject("bannedTracks")),
            error = json.text("error"),
            moodsRunning = json.optJSONObject("moods")?.optBoolean("running") == true,
            moodsError = json.optJSONObject("moods")?.text("error").orEmpty(),
            download = download?.let {
                MusicDownload(it.optBoolean("active"), it.optInt("done"), it.optInt("total"), it.optLong("doneBytes"), it.optLong("totalBytes"))
            },
            genres = genres?.keys()?.asSequence()?.mapNotNull { key -> genres.optJSONObject(key)?.let { key to it.text("vi") } }?.toList().orEmpty(),
            emotionNames = emotions?.keys()?.asSequence()?.associateWith { emotions.text(it) }.orEmpty(),
        )
    }

    fun moods(json: JSONObject): MoodsModel {
        val progress = json.optJSONObject("progress")
        val total = progress?.optInt("total") ?: 0
        return MoodsModel(
            installed = json.optBoolean("installed"),
            downloading = json.optBoolean("downloading"),
            percent = if (progress != null && total > 0) Math.round(progress.optInt("done") * 100f / total) else null,
            error = json.text("error"),
            downloadable = json.optBoolean("downloadable"),
        )
    }

    fun alternatives(json: JSONObject): List<MusicAlternative> =
        json.optJSONArray("alternatives").objects().map {
            MusicAlternative(it.text("link"), it.text("title"), it.text("creator"), it.optDouble("duration", 0.0), it.optDouble("score", 0.0))
        }.filter { it.link.isNotEmpty() }
}

object MusicLogic {
    /** Nghe thử một bài: ~20 giây từ đầu, không bao giờ tự phát (web `PREVIEW_SECONDS`). */
    const val PREVIEW_MS = 20_000

    /** Hỏi lại khi máy đang đọc không khí (3 giây) / tải sẵn nhạc (2 giây); không thì không hỏi theo nhịp. */
    const val MOODS_REFRESH_MS = 3000L
    const val DOWNLOAD_REFRESH_MS = 2000L

    /** Mảnh này chỉ chơi tiếp bài của đoạn trên (chưa bị ghim / để im lặng riêng) - hiện gọn, không đủ bộ nút. */
    fun isContinuation(scene: MusicScene): Boolean = scene.continued && scene.link != null && !scene.pinned && !scene.silenced

    /** Lời nút "Đổi bài": ở mảnh nối tiếp, ghim bài mới vào đây nên đổi từ chỗ này trở đi. */
    fun swapText(scene: MusicScene): String = if (isContinuation(scene)) "Đổi từ đây" else "Đổi bài"

    private val EMOTION_VI = mapOf(
        "peacefulness" to "bình yên", "tenderness" to "dịu dàng", "nostalgia" to "hoài niệm", "sadness" to "buồn", "joy" to "vui tươi",
        "playful" to "tinh nghịch", "power" to "hào hùng", "wonder" to "kỳ vĩ", "tension" to "căng thẳng", "fear" to "rùng rợn",
        "anger" to "giận dữ", "mystery" to "bí ẩn", "moved" to "xúc động",
    )

    /** Không khí của đoạn: các cảm xúc mạnh nhất (tối đa hai); không cảm xúc nào đủ mạnh thì gọi theo vui/buồn và căng thẳng; còn lại "êm" (musicScenes.ts `moodOf`). */
    fun moodOf(scene: MusicScene, names: Map<String, String>): String {
        val strong = scene.emotions.filter { it.value >= 0.5 }.entries.sortedByDescending { it.value }.take(2).map { names[it.key]?.takeIf { name -> name.isNotEmpty() } ?: EMOTION_VI[it.key] ?: it.key }
        return when {
            strong.isNotEmpty() -> strong.joinToString(" · ")
            scene.tension >= 0.5 -> "căng thẳng"
            scene.valence <= -0.4 -> "buồn"
            scene.valence >= 0.4 -> "tươi vui"
            else -> "êm"
        }
    }

    /** Có nhãn "AI" cạnh không khí: AI đã đọc cả đoạn để chấm. */
    fun byAi(scene: MusicScene): Boolean = scene.moodSource == "llm" || scene.moodSource == "chapter" || scene.moodSource == "student"

    /** Tên một bài: "tên · tác giả" nếu kế hoạch còn biết bài ấy, không thì tên file trong liên kết. */
    fun trackLabel(link: String, info: MusicTrack?): String {
        if (info != null && info.title.isNotEmpty()) return listOf(info.title, info.creator).filter { it.isNotEmpty() }.joinToString(" · ")
        val name = link.substringBefore('?').substringBefore('#').split('/').filter { it.isNotEmpty() }.lastOrNull() ?: link
        return runCatching { java.net.URLDecoder.decode(name, "UTF-8") }.getOrDefault(name)
    }

    /** Dòng ghi công của một bài (dùng chung với trình phát: [vn.abook.player.ui.music.MusicText.creditText]); nhạc bạn nhập thì nói rõ không có giấy phép. */
    fun creditText(link: String, track: MusicTrack): String =
        if (track.source == "local") "${listOf(track.title, track.creator).filter { it.isNotEmpty() }.joinToString(" · ")} - nhạc của bạn, không có thông tin giấy phép"
        else MusicText.creditText(MusicCredit(track.title, track.creator, track.attribution, license = track.license)).ifEmpty { link }

    /** Có bài giấy phép đòi ghi công (khác cc0) thì kèm lời "đã chỉnh sửa". */
    fun needsModifiedNote(view: MusicView): Boolean = view.tracks.values.any { it.license.trim().lowercase().let { code -> code.isNotEmpty() && code != "cc0" } }

    /** Số đoạn đang dùng bài `link` (báo trước khi loại bài khỏi cả cuốn). */
    fun usedIn(view: MusicView, link: String): Int = view.scenes.count { it.link == link }

    /** Đoạn kế để tính chỗ kết thúc: các đoạn nối liền, đoạn này hết ở đúng chỗ đoạn sau bắt đầu. */
    fun range(scenes: List<MusicScene>, index: Int): String = "${Fmt.clock(scenes[index].start)}–${Fmt.clock(scenes.getOrNull(index + 1)?.start ?: scenes[index].end)}"

    /** Dòng tiến độ tải sẵn: MB khi biết cỡ, không thì đếm bài. */
    fun downloadText(download: MusicDownload): String {
        val tracks = "bài ${minOf(download.done + 1, download.total)}/${download.total}"
        if (download.totalBytes <= 0L) return "Đang tải sẵn nhạc nền: $tracks"
        return "Đang tải sẵn nhạc nền: ${formatSize(download.doneBytes)} / ${formatSize(download.totalBytes)} ($tracks)"
    }

    /** Phần đã xong (0-1) cho vạch tiến độ. */
    fun downloadShare(download: MusicDownload): Float = when {
        download.totalBytes > 0L -> download.doneBytes.toFloat() / download.totalBytes
        download.total > 0 -> download.done.toFloat() / download.total
        else -> 0f
    }

    /** Thân `PUT /music` cho từng việc (đúng khoá của web). */
    fun enabled(value: Boolean) = JSONObject().put("enabled", value)
    fun level(db: Double) = JSONObject().put("levelDb", db)
    fun genre(code: String?) = JSONObject().put("genre", code ?: JSONObject.NULL)
    fun silence(key: String, on: Boolean) = JSONObject().put("silence", JSONObject().put(key, on))
    fun unpin(key: String) = JSONObject().put("pins", JSONObject().put(key, JSONObject.NULL))

    /** Đoạn đang im lặng (bạn chọn) mà chọn bài thì có nhạc lại. */
    fun pin(scene: MusicScene, link: String): JSONObject {
        val body = JSONObject().put("pins", JSONObject().put(scene.key, link))
        if (scene.silenced) body.put("silence", JSONObject().put(scene.key, false))
        return body
    }

    fun ban(link: String) = JSONObject().put("ban", JSONArray().put(link))
    fun unban(link: String) = JSONObject().put("unban", JSONArray().put(link))

    /** Việc đổi thể loại / chọn lại dựng lại nhạc cả cuốn (cỡ nửa phút); sửa một đoạn chỉ mất chốc lát. */
    fun rebuilds(body: JSONObject): Boolean = body.has("genre")

    /** Nhịp hỏi lại theo dữ liệu: đang đọc không khí / đang tải sẵn thì hỏi tới khi xong. */
    fun interval(view: MusicView?): Long? = when {
        view?.moodsRunning == true -> MOODS_REFRESH_MS
        view?.download?.active == true -> DOWNLOAD_REFRESH_MS
        else -> null
    }
}

object StudioMusicText {
    const val LOADING = "Đang tải nhạc nền"
    const val ENABLED = "Nhạc nền"
    const val ENABLED_ON = "Đang bật cho cuốn này."
    const val ENABLED_OFF = "Đang tắt: các đoạn dưới đây sẽ không phát."
    const val GENRE = "Thể loại truyện"
    const val GENRE_NONE = "Chưa chọn"
    const val GENRE_HINT = "Chưa chọn thì nhạc lấy từ mọi thể loại"
    const val LEVEL = "Mức nhạc nền"
    const val LEVEL_HINT = "Nhỏ hơn giọng đọc bấy nhiêu; máy tự bù bài to hay nhỏ"
    const val REBUILD = "Chọn lại nhạc"
    const val REBUILD_HINT = "Máy chọn lại bài cho từng đoạn theo thể loại và mức nhạc ở trên."
    const val REBUILD_TITLE = "Chọn lại nhạc cho cả cuốn?"
    const val REBUILD_LINE = "Bài bạn đã ghim vẫn được giữ. Máy tính mất cỡ nửa phút để chọn lại."
    const val REBUILDING = "Đang chọn lại nhạc, cỡ nửa phút."
    const val SAVING = "Đang lưu lựa chọn"
    const val CANCEL_DOWNLOAD = "Huỷ tải"
    const val CANCELLED = "Đã dừng tải nhạc nền"
    const val NO_SCENES = "Chưa có đoạn nào - nhạc nền dựng sau khi sách đã phân tích."
    const val OFF_NOTE = "Nhạc nền đang tắt - các đoạn dưới đây sẽ không phát."
    const val CONTINUED = "↳ tiếp bài của đoạn trên"
    const val SILENT_CHOSEN = "Im lặng (bạn chọn)"
    const val SILENT_AUTO = "Im lặng - không bài nào đủ hợp"
    const val PINNED = "Đã ghim"
    const val PIN_GONE = "Bài bạn ghim không còn trên máy này - đoạn dùng bài khác."
    const val AI = "AI"
    const val TRACK = "Bài nhạc"
    const val SILENCE_ON = "Tắt nhạc đoạn này"
    const val SILENCE_OFF = "Bật nhạc đoạn này"
    const val UNPIN = "Bỏ ghim"
    const val BAN = "Loại khỏi cuốn"
    const val MORE = "Thêm"
    const val PLAY = "Nghe thử"
    const val STOP = "Dừng nghe"
    const val CHOOSE = "Chọn"
    const val ALT_TITLE = "Đổi bài"
    const val ALT_LOADING = "Đang tải bài khác"
    const val ALT_EMPTY = "Không còn bài nào khác trong danh mục đủ hợp đoạn này."
    const val BANNED = "Bài đã bỏ"
    const val UNBAN = "Dùng lại"
    const val ADVANCED = "Nâng cao"
    const val MOODS = "Đọc không khí cả đoạn bằng AI"
    const val MOODS_LEAD = "Hiểu ngữ cảnh để chọn nhạc; ~1 phút mỗi giờ sách."
    const val MOODS_RUN = "Đọc lại ngữ cảnh"
    const val MOODS_RUNNING = "Đang đọc không khí"
    const val MOODS_DONE = "Đã đọc xong không khí các đoạn - nhạc đã chọn lại"
    const val MOODS_ABSENT = "Máy tính chưa có phần đọc không khí; tải nó trên máy tính."
    const val CREDITS = "Ghi công"
    const val CHOSEN_TITLE = "Chọn thể loại"

    fun banned(count: Int) = "$BANNED ($count)"
    fun bannedDone(label: String, used: Int) = "Đã bỏ “$label” cho cả cuốn (đang dùng ở $used đoạn)"
    fun moodsDownloading(percent: Int?) = "Đang tải phần đọc không khí${percent?.let { " - $it%" }.orEmpty()}"
}

/**
 * Tab "Nhạc nền" của một dự án. Hỏi `GET /music` khi mở tab; máy đang đọc không khí (3 giây) hay tải sẵn nhạc (2 giây) thì hỏi theo nhịp tới khi xong. Mỗi chỉnh là một
 * `PUT /music` rồi đọc lại; đổi thể loại / chọn lại dựng lại nhạc cả cuốn nên đi đường chậm.
 */
@Stable
class StudioMusicState(private val project: StudioProjectState, pause: suspend (Long) -> Unit = { delay(it) }) {
    private val session get() = project.session
    private val poller = StudioPoller<MusicView>({ session.source.music(session.computer, project.bookId) }, MusicLogic::interval, pause)
    val poll: StateFlow<StudioPolling.Poll<MusicView>> get() = poller.state

    val clip: StateFlow<ClipState>? get() = session.clips?.state

    /** Model đọc không khí trên máy tính; null = chưa biết (hay máy không nói). */
    var moodsModel by mutableStateOf<MoodsModel?>(null)
        private set

    /** "" | [StudioMusicText.SAVING] | [StudioMusicText.REBUILDING]: việc đang chạy, để các nút nhạt đi và có một dòng nói vì sao. */
    var busy by mutableStateOf("")
        private set

    var problem by mutableStateOf("")
        private set

    /** Lời báo một việc vừa xong (đã đọc xong không khí, đã dừng tải). */
    var notice by mutableStateOf("")
        private set

    private var moodsWas = false

    suspend fun run() {
        moodsModel = try {
            session.source.moodsModel(session.computer)
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Throwable) {
            null
        }
        poller.run()
    }

    suspend fun refresh() = poller.refresh()

    fun refreshSoon() {
        session.scope.launch { poller.refresh() }
    }

    /** Gọi sau mỗi lần dữ liệu về: việc "đọc lại ngữ cảnh" vừa xong thì báo (một lần). */
    fun seen(view: MusicView) {
        if (moodsWas && !view.moodsRunning) {
            if (view.moodsError.isNotEmpty()) problem = view.moodsError else notice = StudioMusicText.MOODS_DONE
        }
        moodsWas = view.moodsRunning
    }

    private fun work(label: String, block: suspend () -> Unit) {
        if (busy.isNotEmpty()) return
        busy = label
        problem = ""
        notice = ""
        session.scope.launch {
            try {
                block()
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                val failure = StudioErrors.of(error)
                session.note(failure)
                problem = StudioText.failure(failure)
            } finally {
                busy = ""
            }
            poller.refresh()
        }
    }

    /** Một chỉnh của cuốn hay của một đoạn: `PUT /music`. */
    fun change(body: JSONObject, onDone: () -> Unit = {}) {
        val slow = MusicLogic.rebuilds(body)
        work(if (slow) StudioMusicText.REBUILDING else StudioMusicText.SAVING) {
            session.source.put(session.computer, project.bookId, "music", body, slow)
            onDone()
        }
    }

    /** "Chọn lại nhạc": máy tính dựng lại nhạc cả cuốn (cỡ nửa phút). */
    fun rebuild() = work(StudioMusicText.REBUILDING) { session.source.write(session.computer, project.bookId, WorkStep("music/rebuild", JSONObject()), slow = true) }

    /** "Huỷ tải" nhạc nền đang tải sẵn trên máy tính. */
    fun cancelDownload() = work(StudioMusicText.SAVING) {
        session.source.write(session.computer, project.bookId, WorkStep("music/download/cancel", JSONObject()))
        notice = StudioMusicText.CANCELLED
    }

    /** "Đọc lại ngữ cảnh": máy tính cho AI đọc cả đoạn rồi chọn lại nhạc (chạy nền; theo dõi bằng `moods.running`). */
    fun computeMoods() = work(StudioMusicText.SAVING) { session.source.write(session.computer, project.bookId, WorkStep("music/moods", JSONObject())) }

    /** Các bài khác hợp đoạn này, hợp nhất trước. */
    suspend fun alternatives(scene: MusicScene): List<MusicAlternative> = session.source.alternatives(session.computer, project.bookId, scene.key)

    /** Nghe thử một bài trong danh mục (~20 giây từ đầu); bấm lại thì dừng. */
    fun playTrack(link: String) {
        session.clips?.toggle(trackClip(link), ClipSpec(session.computer, StudioPaths.musicTrack(link), 0, MusicLogic.PREVIEW_MS))
    }

    fun release() {
        session.clips?.stop()
    }

    companion object {
        fun trackClip(link: String) = "music-$link"
    }
}
