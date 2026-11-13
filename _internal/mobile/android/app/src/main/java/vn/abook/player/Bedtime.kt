package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * Nhật ký đêm - cho "Tối qua bạn nghe tới đâu?".
 *
 * Không ai biết chính xác lúc người nghe thiếp đi, nhưng có những mốc chắc chắn:
 *  - lúc hẹn giờ ngủ: chắc chắn còn thức;
 *  - lần cuối chạm máy / bấm nút / lắc máy: chắc chắn còn thức;
 *  - lúc điện thoại bắt đầu nằm yên (cảm biến): rất có thể là lúc thiếp đi;
 *  - lúc tự dừng.
 * Mỗi mốc ghi kèm chương + giây đang phát, và cứ 30 giây một mốc vị trí để suy ra "lúc X đang nghe tới đâu".
 * Sáng hôm sau giao diện hiện các mốc kèm câu văn đang đọc lúc đó để người nghe nhận ra đoạn cuối mình còn nhớ.
 *
 * Đêm là của một HỒ SƠ nghe (soát a105 F5): `recordId` chốt lúc hẹn giờ, mỗi hồ sơ một file `bedtime/<hồ sơ>.json`; chỉ người nghe ấy nối được
 * đêm cũ, và thẻ buổi sáng chỉ hiện đêm của hồ sơ đang dùng của cuốn (không mời người này quay về chỗ của người kia).
 *
 * Đêm ĐÓNG khi hẹn giờ hết hẳn - tự dừng ([stopped]), tắt hay tự bỏ ([timerOff]): sau đó không ghi mốc 30 giây hay sự kiện nào nữa, nên giờ nghe
 * ban ngày không lẫn vào thẻ "Tối qua" và file không phình suốt đời tiến trình (soát Android 12-11 mục 4). Hẹn lại trong 90 phút thì mở lại đúng đêm ấy.
 * Ghi đĩa trên luồng ghi nền [DiskWrites] (lõi phát gọi từ luồng chính); mỗi lần ghi mang bản chụp của riêng nó.
 */
object Bedtime {
    private const val STILL_DEVIATION = SleepPolicy.STILL_DEVIATION   // m/s² - máy nằm yên trên đệm
    private const val STILL_WINDOWS = SleepPolicy.STILL_WINDOWS        // 4 cửa sổ 30 giây liền = 2 phút nằm yên
    private var session: JSONObject? = null
    /** Đêm vừa đóng: hẹn lại trong 90 phút ([continues]) thì mở lại nó thay vì bắt đầu đêm mới. */
    private var closed: JSONObject? = null
    /** Trần số sự kiện một đêm (mốc vị trí có trần riêng, 480 = 4 giờ): bỏ sự kiện cũ nhất. */
    internal const val MAX_EVENTS = 400
    private var lastCheckpointMs = 0L
    private var stillRun = 0
    private var stillSince = 0L
    private var stillRecorded = false

    private fun file(record: String) = File(Store.root, "bedtime/${record.ifEmpty { "latest" }}.json")

    private fun position(): JSONObject {
        val chapter = Playback.currentChapter
        return JSONObject()
            .put("chapterId", chapter?.id ?: JSONObject.NULL)
            .put("chapterTitle", chapter?.title ?: "")
            .put("seconds", Playback.positionSeconds)
    }

    private fun nowSeconds() = System.currentTimeMillis() / 1000.0

    /** Hẹn giờ mở (hoặc nối tiếp) một đêm: hẹn lại trong vòng 90 phút vẫn là cùng một đêm. */
    @Synchronized fun timerSet(minutes: Int, reason: String? = null) {
        val current = session ?: closed
        val continuing = continues(current, Playback.bookId, Playback.recordId, nowSeconds())
        closed = null
        if (continuing) {
            current!!.remove("endedAt")
            session = current
        } else {
            session = JSONObject()
                .put("bookId", Playback.bookId)
                .put("recordId", Playback.recordId)
                .put("bookTitle", Playback.bookTitle)
                .put("startedAt", nowSeconds())
                .put("events", JSONArray())
                .put("timeline", JSONArray())
            stillRun = 0
            stillRecorded = false
        }
        lastCheckpointMs = 0L
        stillRun = 0
        stillRecorded = false
        add("timer", JSONObject().put("minutes", minutes).also { if (reason != null) it.put("action", reason) })
    }

    /** Hẹn giờ lại có nối tiếp đêm `current` không: cùng cuốn, CÙNG hồ sơ, trong vòng 90 phút. */
    internal fun continues(current: JSONObject?, bookId: String, recordId: String, now: Double): Boolean =
        current != null && current.optString("bookId") == bookId && current.optString("recordId") == recordId &&
            now - current.optDouble("lastAt", 0.0) < 90 * 60

    @Synchronized fun interaction(kind: String) {
        if (session == null) return
        add("touch", JSONObject().put("action", kind))
    }

    @Synchronized fun event(kind: String) {
        if (session == null) return
        add(kind, JSONObject())
    }

    /** Hẹn giờ tự dừng: ghi mốc cuối rồi đóng đêm. */
    fun stopped() = close("stopped")

    /** Hẹn giờ tắt (người nghe tắt, đổi sách, hẹn tự động bị huỷ) hay tự bỏ vì dừng quá lâu: đóng đêm, không ghi thêm gì sau đó. */
    fun timerOff() = close("cancel")

    @Synchronized private fun close(kind: String) {
        val current = session ?: return
        add(kind, JSONObject())
        current.put("endedAt", nowSeconds())
        save()
        session = null
        closed = current
    }

    @Synchronized fun checkpoint() {
        val current = session ?: return
        val now = System.currentTimeMillis()
        if (now - lastCheckpointMs < 30_000) return
        lastCheckpointMs = now
        val timeline = current.getJSONArray("timeline")
        timeline.put(position().put("at", nowSeconds()))
        while (timeline.length() > 480) timeline.remove(0)   // 4 giờ
        save()
    }

    /** Một cửa sổ 30 giây của cảm biến: đủ 2 phút liền nằm yên thì ghi mốc "nằm yên" tại lúc bắt đầu yên. */
    @Synchronized fun window(startMs: Long, deviation: Double) {
        val current = session ?: return
        if (deviation < STILL_DEVIATION) {
            if (stillRun == 0) stillSince = startMs
            stillRun += 1
            if (stillRun >= STILL_WINDOWS && !stillRecorded) {
                stillRecorded = true
                val at = stillSince / 1000.0
                val events = current.getJSONArray("events")
                events.put(JSONObject().put("type", "still").put("at", at).put("position", positionAt(at)))
                while (events.length() > MAX_EVENTS) events.remove(0)
                save()
            }
        } else {
            if (stillRecorded) add("moved", JSONObject())
            stillRun = 0
            stillRecorded = false
        }
    }

    /** Vị trí đang phát ở một thời điểm đã qua, suy từ mốc 30 giây gần nhất trước đó. */
    private fun positionAt(at: Double): JSONObject {
        val timeline = session?.optJSONArray("timeline") ?: return position()
        var best: JSONObject? = null
        for (index in 0 until timeline.length()) {
            val point = timeline.getJSONObject(index)
            if (point.optDouble("at") <= at) best = point else break
        }
        return best ?: position()
    }

    private fun add(type: String, extra: JSONObject) {
        val current = session ?: return
        val at = nowSeconds()
        extra.put("type", type).put("at", at).put("position", position())
        val events = current.getJSONArray("events")
        events.put(extra)
        while (events.length() > MAX_EVENTS) events.remove(0)
        current.put("lastAt", at)
        save()
    }

    private fun save() {
        val current = session ?: return
        val file = file(current.optString("recordId"))
        val text = current.toString()
        DiskWrites.post("Bedtime") { Store.writeAtomic(file, text) }
    }

    internal fun write(night: JSONObject) {
        Store.writeAtomic(file(night.optString("recordId")), night.toString())
    }

    /** Mọi đêm đã lưu, mỗi hồ sơ một file. */
    internal fun all(): List<JSONObject> =
        File(Store.root, "bedtime").listFiles { f -> f.isFile && f.name.endsWith(".json") }.orEmpty()
            .mapNotNull { f -> runCatching { JSONObject(f.readText()) }.getOrNull() }

    /** Đêm gần nhất của hồ sơ ĐANG DÙNG của cuốn (`activeOf`: mã cuốn -> hồ sơ đang dùng): đêm của người khác trong cùng cuốn không hiện. */
    internal fun pickLatest(nights: List<JSONObject>, activeOf: (String) -> String?): JSONObject? =
        nights.filter { night -> night.optString("recordId").let { it.isEmpty() || activeOf(night.optString("bookId")) == it } }
            .maxByOrNull { it.optDouble("startedAt", 0.0) }

    /** Luồng nền (đọc file): đọc sau mọi lần ghi đã giao. */
    fun latest(): JSONObject? {
        DiskWrites.flush()
        return pickLatest(all()) { Store.knownActiveRecord(it) }
    }

    /** Luồng nền. Ghi thẳng sau khi hàng ghi cạn ([latest]) - lần ghi cũ đang chờ không đè dấu "dismissed". */
    fun dismiss() {
        val latest = latest() ?: return
        synchronized(this) {
            fun matches(night: JSONObject?) = night?.optDouble("startedAt") == latest.optDouble("startedAt") &&
                night?.optString("recordId") == latest.optString("recordId")
            val snapshot = if (matches(session)) JSONObject(session.toString()) else latest
            if (matches(session)) session = null
            if (matches(closed)) closed = null
            snapshot.put("dismissed", true)
            val target = file(snapshot.optString("recordId"))
            val text = snapshot.toString()
            DiskWrites.post("Bedtime") { Store.writeAtomic(target, text) }
        }
        DiskWrites.flush()
    }
}
