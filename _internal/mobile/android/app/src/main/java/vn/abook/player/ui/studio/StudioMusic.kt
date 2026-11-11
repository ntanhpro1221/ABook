package vn.abook.player.ui.studio

import vn.abook.player.S

import vn.abook.player.ui.data.dotJoined
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
    fun swapText(scene: MusicScene): String = if (isContinuation(scene)) S.s_doi_tu_day_a54eee44 else S.s_doi_bai_7b81488f

    private val EMOTION_VI = mapOf(
        "peacefulness" to S.s_binh_yen_9e77ef15, "tenderness" to S.s_diu_dang_deaaa55a, "nostalgia" to S.s_hoai_niem_799529ae, "sadness" to S.s_buon_a474e7e0, "joy" to S.s_vui_tuoi_8ebbee23,
        "playful" to S.s_tinh_nghich_f27e1115, "power" to S.s_hao_hung_fec61823, "wonder" to S.s_ky_vi_ac54ac08, "tension" to S.s_cang_thang_48be6812, "fear" to S.s_rung_ron_e9a9ecec,
        "anger" to S.s_gian_du_1565d541, "mystery" to S.s_bi_an_ace8c102, "moved" to S.s_xuc_dong_bc36f9eb,
    )

    /** Không khí của đoạn: các cảm xúc mạnh nhất (tối đa hai); không cảm xúc nào đủ mạnh thì gọi theo vui/buồn và căng thẳng; còn lại "êm" (musicScenes.ts `moodOf`). */
    fun moodOf(scene: MusicScene, names: Map<String, String>): String {
        val strong = scene.emotions.filter { it.value >= 0.5 }.entries.sortedByDescending { it.value }.take(2).map { names[it.key]?.takeIf { name -> name.isNotEmpty() } ?: EMOTION_VI[it.key] ?: it.key }
        return when {
            strong.isNotEmpty() -> strong.dotJoined()
            scene.tension >= 0.5 -> S.s_cang_thang_48be6812
            scene.valence <= -0.4 -> S.s_buon_a474e7e0
            scene.valence >= 0.4 -> S.s_tuoi_vui_43fac912
            else -> S.s_em_07866b70
        }
    }

    /** Có nhãn "AI" cạnh không khí: AI đã đọc cả đoạn để chấm. */
    fun byAi(scene: MusicScene): Boolean = scene.moodSource == "llm" || scene.moodSource == "chapter" || scene.moodSource == "student"

    /** Tên một bài: "tên · tác giả" nếu kế hoạch còn biết bài ấy, không thì tên file trong liên kết. */
    fun trackLabel(link: String, info: MusicTrack?): String {
        if (info != null && info.title.isNotEmpty()) return listOf(info.title, info.creator).dotJoined()
        val name = link.substringBefore('?').substringBefore('#').split('/').filter { it.isNotEmpty() }.lastOrNull() ?: link
        return runCatching { java.net.URLDecoder.decode(name, "UTF-8") }.getOrDefault(name)
    }

    /** Dòng ghi công của một bài (dùng chung với trình phát: [vn.abook.player.ui.music.MusicText.creditText]); nhạc bạn nhập thì nói rõ không có giấy phép. */
    fun creditText(link: String, track: MusicTrack): String =
        if (track.source == "local") S.s_0_nhac_cua_ban_khong_co_thong_tin_giay_phe_71454f92(listOf(track.title, track.creator).dotJoined())
        else MusicText.creditText(MusicCredit(track.title, track.creator, track.attribution, license = track.license)).ifEmpty { link }

    /** Có bài giấy phép đòi ghi công (khác cc0) thì kèm lời "đã chỉnh sửa". */
    fun needsModifiedNote(view: MusicView): Boolean = view.tracks.values.any { it.license.trim().lowercase().let { code -> code.isNotEmpty() && code != "cc0" } }

    /** Số đoạn đang dùng bài `link` (báo trước khi loại bài khỏi cả cuốn). */
    fun usedIn(view: MusicView, link: String): Int = view.scenes.count { it.link == link }

    /** Đoạn kế để tính chỗ kết thúc: các đoạn nối liền, đoạn này hết ở đúng chỗ đoạn sau bắt đầu. */
    fun range(scenes: List<MusicScene>, index: Int): String = "${Fmt.clock(scenes[index].start)}–${Fmt.clock(scenes.getOrNull(index + 1)?.start ?: scenes[index].end)}"

    /** Dòng tiến độ tải sẵn: MB khi biết cỡ, không thì đếm bài. */
    fun downloadText(download: MusicDownload): String {
        val tracks = S.s_bai_0_1_515d0997(minOf(download.done + 1, download.total), download.total)
        if (download.totalBytes <= 0L) return S.s_dang_tai_san_nhac_nen_0_ca14ae35(tracks)
        return S.s_dang_tai_san_nhac_nen_0_1_2_48ce53ca(formatSize(download.doneBytes), formatSize(download.totalBytes), tracks)
    }

    /** Phần đã xong (0-1) cho vạch tiến độ. */
    /** Phần đã tải theo byte (không có thì theo số bài); null khi máy chủ chưa báo tổng nào - thanh chạy liên tục. */
    fun downloadShare(download: MusicDownload): Float? = when {
        download.totalBytes > 0L -> download.doneBytes.toFloat() / download.totalBytes
        download.total > 0 -> download.done.toFloat() / download.total
        else -> null
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
    const val LOADING = S.s_dang_tai_nhac_nen_0b8c4795
    const val ENABLED = S.s_nhac_nen_271fb292
    const val ENABLED_ON = S.s_dang_bat_cho_cuon_nay_6752e54b
    const val ENABLED_OFF = S.s_dang_tat_cac_doan_duoi_day_se_khong_phat_e93d8c97
    const val GENRE = S.s_the_loai_truyen_9c821aa0
    const val GENRE_NONE = S.s_chua_chon_e5f50074
    const val GENRE_HINT = S.s_chua_chon_thi_nhac_lay_tu_moi_the_loai_a144c9d2
    const val LEVEL = S.s_muc_nhac_nen_a45588ff
    const val LEVEL_HINT = S.s_nho_hon_giong_doc_bay_nhieu_may_tu_bu_bai_e1b269b4
    const val REBUILD = S.s_chon_lai_nhac_ebe26dde
    const val REBUILD_HINT = S.s_may_chon_lai_theo_the_loai_va_muc_nhac_o_t_927c2f67
    const val REBUILD_TITLE = S.s_chon_lai_nhac_cho_ca_cuon_2e88e27c
    const val REBUILD_LINE = S.s_bai_ban_da_ghim_van_duoc_giu_may_tinh_mat_0fe51780
    const val REBUILDING = S.s_dang_chon_lai_nhac_co_nua_phut_4166612f
    const val SAVING = S.s_dang_luu_lua_chon_d37252de
    const val CANCEL_DOWNLOAD = S.s_huy_tai_1a9ff73d
    const val CANCELLED = S.s_da_dung_tai_nhac_nen_6addc23d
    /** Nhãn đếm đoạn nhạc của một chương (cùng chữ với MusicTab.tsx); số trơ trọi không nói nó đếm gì. */
    fun sceneCount(n: Int) = S.s_0_doan_c2eb5200(n)
    const val NO_SCENES = S.s_chua_co_doan_nao_nhac_nen_dung_sau_khi_sac_b1bdaf8e
    const val OFF_NOTE = S.s_nhac_nen_dang_tat_cac_doan_duoi_day_se_kho_2cc431ba
    const val CONTINUED = S.s_tiep_bai_cua_doan_tren_79bb9e24
    const val SILENT_CHOSEN = S.s_im_lang_ban_chon_356a628b
    const val SILENT_AUTO = S.s_im_lang_khong_bai_nao_du_hop_6881c83f
    const val PINNED = S.s_da_ghim_f1645be7
    const val PIN_GONE = S.s_bai_ban_ghim_khong_con_tren_may_nay_doan_d_09b8894e
    const val AI = "AI"
    const val TRACK = S.s_bai_nhac_5d07657e
    const val SILENCE_ON = S.s_tat_nhac_doan_nay_8fb1136b
    const val SILENCE_OFF = S.s_bat_nhac_doan_nay_57d716ef
    const val UNPIN = S.s_bo_ghim_1600e29e
    const val BAN = S.s_loai_khoi_cuon_3b45b802
    const val MORE = S.s_them_dd92626f
    const val PLAY = S.s_nghe_thu_fa024065
    const val STOP = S.s_dung_nghe_f20939be
    const val CHOOSE = S.s_chon_1171ca97
    const val ALT_TITLE = S.s_doi_bai_7b81488f
    const val ALT_LOADING = S.s_dang_tai_bai_khac_2c0e1ec8
    const val ALT_EMPTY = S.s_khong_con_bai_nao_khac_trong_danh_muc_du_h_970fe053
    const val BANNED = S.s_bai_da_bo_756dc520
    const val UNBAN = S.s_dung_lai_01a1973f
    const val ADVANCED = S.s_nang_cao_d16fca15
    const val MOODS = S.s_doc_khong_khi_ca_doan_bang_ai_f0aaaea4
    const val MOODS_LEAD = S.s_hieu_ngu_canh_de_chon_nhac_1_phut_moi_gio_1ed08581
    const val MOODS_RUN = S.s_doc_lai_ngu_canh_edb18d3a
    const val MOODS_RUNNING = S.s_dang_doc_khong_khi_0640731b
    const val MOODS_DONE = S.s_da_doc_xong_khong_khi_cac_doan_nhac_da_cho_487aac39
    const val MOODS_ABSENT = S.s_may_tinh_chua_co_phan_doc_khong_khi_tai_no_af85f596
    const val CREDITS = S.s_ghi_cong_9c291f64
    const val CHOSEN_TITLE = S.s_chon_the_loai_0b964b7a

    fun banned(count: Int) = "$BANNED ($count)"
    fun bannedDone(label: String, used: Int) = S.s_da_bo_0_cho_ca_cuon_dang_dung_o_1_doan_388eec18(label, used)
    fun moodsDownloading(percent: Int?) = S.s_dang_tai_phan_doc_khong_khi_0_25520a88(percent?.let { " - $it%" }.orEmpty())
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
