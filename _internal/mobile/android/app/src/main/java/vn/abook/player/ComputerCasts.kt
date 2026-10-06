package vn.abook.player

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Loa / TV MÁY TÍNH đang phát (mã "cast:", webui/cast.py) cho phiên media của điện thoại (07-10): màn hình khoá, tai nghe
 * điều khiển chúng như loa / TV điện thoại tự phát. Lệnh đi đúng đường của thanh "Đang phát trên…" (RemotePlayers.command
 * -> POST /sync/v1/cast/<mã>); hẹn giờ tắt vẫn chỉ ở trong app.
 *
 * Không tự hỏi máy tính khi không ai cần: chỉ bắt đầu khi giao diện đang hiện thanh ấy ([observe], từ RemotePlayers.all -
 * giao diện hỏi 2 giây một lần khi app đang mở). Từ lúc đó CastService chạy (thông báo + phiên media) và, khi giao diện
 * thôi hỏi (app ở nền, màn hình khoá), tự hỏi GET /sync/v1/cast thưa ([poll]) tới khi máy tính hết phát hay không trả lời
 * suốt [LOST_MS]. Không giữ khoá CPU / Wi-Fi như lúc điện thoại phục vụ audio: máy tính phục vụ; điện thoại ngủ thì lượt
 * hỏi ngừng theo, bấm nút nguồn là máy thức và hỏi lại.
 */
object ComputerCasts : CastSource {
    private const val QUIET_MS = 3_000L // giao diện không hỏi chừng ấy: dịch vụ tự hỏi
    private const val LOST_MS = 60_000L // máy tính không trả lời liền chừng ấy: thôi

    private lateinit var appContext: Context
    private val lock = Any()
    private var entry: JSONObject? = null // loa / TV máy tính đang có sách, đúng như /sync/v1/cast trả
    private var seenAt = 0L // lượt hỏi cuối (được hay hỏng)
    private var failingSince = 0L // 0: lượt cuối trả lời được
    private val books = HashMap<String, List<CastChapter>>() // mã sách -> chương nghe được (gói sách của máy tính)

    /**
     * RemotePlayers.all vừa hỏi xong: [renderers] là /sync/v1/cast của máy tính (null: không tới được lượt này). Có loa / TV
     * đang có sách -> bật CastService (phiên media) nếu chưa chạy.
     */
    fun observe(context: Context, renderers: JSONArray?) {
        appContext = context.applicationContext
        if (record(renderers) != null) CastService.ensure(context)
    }

    /** Còn phiên máy tính cho phiên media không. */
    fun active(): Boolean = synchronized(lock) { entry != null }

    /** Giao diện đã thôi hỏi một lúc: CastService phải tự hỏi. */
    fun quiet(): Boolean = synchronized(lock) { entry != null && System.currentTimeMillis() - seenAt >= QUIET_MS }

    /** Hỏi máy tính một lượt (ngoài luồng chính). */
    fun poll() {
        record(runCatching {
            JSONObject(SyncLink.request(appContext, "GET", "/sync/v1/cast", readTimeoutMs = 2500, connectTimeoutMs = 1500))
                .optJSONArray("renderers") ?: JSONArray()
        }.getOrNull())
    }

    /** Ghi một lượt hỏi; không tới được thì giữ bản cũ - hỏng liền [LOST_MS] mới thôi (Wi-Fi vừa thức, máy tính chậm). */
    private fun record(renderers: JSONArray?): JSONObject? {
        val now = System.currentTimeMillis()
        val busy = renderers?.let { reply -> pick((0 until reply.length()).mapNotNull { reply.optJSONObject(it) }) }
        synchronized(lock) {
            seenAt = now
            if (renderers == null) {
                if (failingSince == 0L) failingSince = now
                if (now - failingSince >= LOST_MS) entry = null
                return entry
            }
            failingSince = 0L
            entry = busy
        }
        busy?.let { learn(it.optJSONObject("state")?.optString("bookId").orEmpty()) }
        return busy
    }

    override fun now(): CastNow? = synchronized(lock) {
        val current = entry ?: return null
        snapshot(current, books[current.optJSONObject("state")?.optString("bookId")].orEmpty(), System.currentTimeMillis() - seenAt)
    }

    /** Lệnh qua máy tính, rồi hỏi lại ngay: màn hình khoá thấy kết quả không phải đợi lượt hỏi sau. */
    override fun send(id: String, command: JSONObject): Any? = RemotePlayers.command(appContext, id, command).also { poll() }

    /** "Dừng": máy tính dừng hẳn thiết bị và lưu chỗ nghe (như "Nghe ở đây" trên thanh, chỉ là không phát tiếp ở đây). */
    override fun end(id: String) {
        RemotePlayers.command(appContext, id, JSONObject().put("action", "stop"))
        synchronized(lock) { entry = null }
    }

    /** Loa / TV đang có sách (đang phát trước). */
    private fun pick(renderers: List<JSONObject>): JSONObject? =
        renderers.filter { it.optJSONObject("state")?.optString("bookId").orEmpty().isNotEmpty() }
            .sortedByDescending { it.optJSONObject("state")?.optBoolean("playing") == true }.firstOrNull()

    /** Chương nghe được của cuốn (để "chương trước / sau" có nghĩa): gói đã có trên điện thoại, không thì hỏi máy tính một lần. */
    private fun learn(bookId: String) {
        synchronized(lock) {
            if (bookId.isEmpty() || bookId in books) return
            books[bookId] = emptyList() // một lần mỗi cuốn, kể cả khi hỏi hỏng
        }
        Thread {
            // Không qua Streaming.fetchManifest: nó cất gói vào thư viện, ở đây chỉ cần đọc danh sách chương.
            val chapters = runCatching {
                val manifest = Store.playableManifest(bookId)
                    ?: JSONObject(SyncLink.request(appContext, "GET", "/sync/v1/books/$bookId/manifest"))
                chaptersOf(manifest)
            }.getOrDefault(emptyList()) // không đọc được: chỉ có chương đang phát, như lúc chưa biết
            synchronized(lock) { books[bookId] = chapters }
        }.apply { isDaemon = true }.start()
    }

    /** Chương nghe được trong gói sách, theo thứ tự - như PhoneCast.book nhưng không cần file trên điện thoại (máy tính phục vụ). */
    fun chaptersOf(manifest: JSONObject): List<CastChapter> {
        val list = manifest.optJSONArray("chapters") ?: return emptyList()
        return (0 until list.length()).mapNotNull { list.optJSONObject(it) }.filter { it.optBoolean("available", true) && it.has("id") }
            .map { CastChapter(it.getInt("id"), it.optString("fullTitle").ifEmpty { it.optString("title") }, it.optDouble("duration", 0.0)) }
    }

    /**
     * Một mục /sync/v1/cast -> bản chụp cho phiên media; [elapsedMs]: thời gian từ lúc nhận. Vị trí nội suy như thanh "Đang
     * phát trên…" (`age` + thời gian đã trôi, khi đang phát). Âm lượng: máy tính chưa chỉnh âm lượng loa / TV - để null
     * (phím âm lượng vẫn chỉnh điện thoại).
     */
    fun snapshot(entry: JSONObject, chapters: List<CastChapter>, elapsedMs: Long): CastNow? {
        val state = entry.optJSONObject("state") ?: return null
        val bookId = state.optString("bookId")
        if (bookId.isEmpty() || !state.has("chapterId") || state.isNull("chapterId")) return null
        val playing = state.optBoolean("playing")
        val buffering = state.optBoolean("buffering")
        val duration = state.optDouble("duration", 0.0)
        var position = state.optDouble("position", 0.0)
        if (playing && !buffering) position += entry.optDouble("age", 0.0) + maxOf(0L, elapsedMs) / 1000.0
        if (duration > 0) position = minOf(position, duration)
        val chapterId = state.getInt("chapterId")
        val known = chapters.takeIf { list -> list.any { it.id == chapterId } }
            ?: listOf(CastChapter(chapterId, state.optString("chapterTitle"), duration))
        return CastNow(RemotePlayers.CAST + entry.optString("id"), entry.optString("name"), bookId, state.optString("bookTitle"),
            known, chapterId, position, duration, playing, buffering)
    }
}
