package vn.abook.player.ui.data

import android.content.Context
import androidx.compose.runtime.Immutable
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import vn.abook.player.Playback
import vn.abook.player.readaloud.PrepareAhead
import vn.abook.player.readaloud.VoiceException

/** Một chương của việc "Làm trước": `ready` khi mọi đoạn đã nằm trong bộ đệm (web: prepareAhead.ts `PreparedChapter`). */
@Immutable
data class PreparedChapter(val id: Int, val title: String, val total: Int, val done: Int, val ready: Boolean)

/** Trạng thái việc "Làm trước" của cả máy (một việc một lúc; web: `PrepareStatus`). `state`: idle / running / done / cancelled / error. */
@Immutable
data class PrepareStatus(
    val state: String = "idle",
    val voice: String = "",
    val label: String = "",
    val total: Int = 0,
    val offered: Int = 0,
    val done: Int = 0,
    val audioSeconds: Long = 0,
    /** Ước thời gian còn lại (giây); null khi chưa biết tốc độ. */
    val secondsLeft: Long? = null,
    val error: String = "",
    val bookId: String = "",
    val online: Boolean = false,
    val chapters: List<PreparedChapter>? = null,
    val chargingOnly: Boolean = true,
    /** Vì sao việc chưa chạy lúc này: charging / wifi / battery / listening, hay null. */
    val waitingFor: String? = null,
) {
    val running: Boolean get() = state == "running"

    /** Các chương của cuốn `bookId` đã làm sẵn (dấu "Đã làm sẵn" ở danh sách chương); việc của cuốn khác không tính. */
    fun readyIds(bookId: String): Set<Int> =
        if (this.bookId != bookId) emptySet() else chapters.orEmpty().filter { it.ready }.map { it.id }.toSet()

    companion object {
        fun parse(json: JSONObject): PrepareStatus {
            val chapters = json.optJSONArray("chapters")?.let { array ->
                (0 until array.length()).mapNotNull { array.optJSONObject(it) }.map {
                    PreparedChapter(it.optInt("id"), it.optString("title"), it.optInt("total"), it.optInt("done"), it.optBoolean("ready"))
                }
            }
            return PrepareStatus(
                state = json.optString("state", "idle"), voice = json.optString("voice"), label = json.optString("label"),
                total = json.optInt("total"), offered = json.optInt("offered"), done = json.optInt("done"),
                audioSeconds = json.optLong("audioSeconds"), secondsLeft = if (json.isNull("secondsLeft") || !json.has("secondsLeft")) null else json.optLong("secondsLeft"),
                error = json.optString("error"), bookId = json.optString("bookId"), online = json.optBoolean("online"),
                chapters = chapters, chargingOnly = json.optBoolean("chargingOnly", true),
                waitingFor = json.optString("waitingFor").takeIf { it.isNotEmpty() && !json.isNull("waitingFor") },
            )
        }
    }
}

/** Ước trước khi bấm: số chương nhận, giờ nghe (giây), máy cần bao lâu (giây; null: chưa đo tốc độ giọng này). */
@Immutable
data class PreparePlan(val chapters: Int = 0, val offered: Int = 0, val audioSeconds: Long = 0, val secondsEstimate: Long? = null) {
    companion object {
        fun parse(json: JSONObject) = PreparePlan(
            json.optInt("chapters"), json.optInt("offered"), json.optLong("audioSeconds"),
            if (json.isNull("secondsEstimate") || !json.has("secondsEstimate")) null else json.optLong("secondsEstimate"),
        )
    }
}

/**
 * Việc của "Làm trước" với lõi (PrepareAhead.kt), tách khỏi màn để thử bằng nguồn giả. Hàm suspend tự chạy ở luồng nền; lỗi ném [IllegalStateException] với câu đã
 * sẵn cho người nghe. [listen] đăng ký nhận trạng thái mỗi khi nó đổi (sau mỗi đoạn), trả hàm gỡ.
 */
interface PrepareSource {
    suspend fun status(): PrepareStatus
    suspend fun plan(voice: String, bookId: String, chapterIds: List<Int>): PreparePlan
    suspend fun start(voice: String, bookId: String, chapterIds: List<Int>, label: String, chargingOnly: Boolean): PrepareStatus
    suspend fun cancel(): PrepareStatus
    suspend fun setChargingOnly(on: Boolean): PrepareStatus
    fun listen(onStatus: (PrepareStatus) -> Unit): () -> Unit
}

/** Nguồn thật: gọi thẳng [PrepareAhead] - cùng hàm mà `ReadAloudPlugin.prepare*` chuyển tiếp cho bản WebView. */
class AndroidPrepareSource(context: Context) : PrepareSource {
    private val app = context.applicationContext

    private suspend fun <T> io(block: () -> T): T = withContext(Dispatchers.IO) {
        Playback.init(app)
        block()
    }

    override suspend fun status() = io { PrepareStatus.parse(PrepareAhead.status(app)) }
    override suspend fun plan(voice: String, bookId: String, chapterIds: List<Int>) = io { PreparePlan.parse(PrepareAhead.plan(app, bookId, voice, chapterIds)) }

    override suspend fun start(voice: String, bookId: String, chapterIds: List<Int>, label: String, chargingOnly: Boolean) = io {
        try {
            PrepareStatus.parse(PrepareAhead.start(app, bookId, voice, chapterIds, label, chargingOnly))
        } catch (error: VoiceException) {
            throw IllegalStateException(error.message ?: "Không làm trước được")
        }
    }

    override suspend fun cancel() = io { PrepareStatus.parse(PrepareAhead.cancel(app)) }
    override suspend fun setChargingOnly(on: Boolean) = io { PrepareStatus.parse(PrepareAhead.setChargingOnly(app, on)) }

    override fun listen(onStatus: (PrepareStatus) -> Unit): () -> Unit {
        val listener: (JSONObject) -> Unit = { onStatus(PrepareStatus.parse(it)) }
        PrepareAhead.addListener(listener)
        return { PrepareAhead.removeListener(listener) }
    }
}
