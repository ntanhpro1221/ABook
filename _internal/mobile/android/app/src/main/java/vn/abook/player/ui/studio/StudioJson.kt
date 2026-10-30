package vn.abook.player.ui.studio

import org.json.JSONArray
import org.json.JSONObject

/**
 * Đọc lời đáp của máy tính thành mô hình Studio (hình JSON của `webui/server.py` mà web `api.ts BookSummary` / `Chapter` mô tả). Thiếu trường thì lấy giá trị
 * rỗng / 0 (máy tính cũ hơn không có `canPause`, `precast`...); thiếu mã sách thì ném - không có mã thì không mở được gì.
 */
internal object StudioJson {
    /** JSON null đọc bằng optString ra chữ "null": nên đọc riêng. */
    private fun JSONObject.text(key: String): String = if (isNull(key)) "" else optString(key)

    private fun JSONObject.fraction(key: String): Float = optDouble(key, 0.0).let { if (it.isFinite()) it.toFloat().coerceIn(0f, 1f) else 0f }

    private fun pause(value: String): StudioPause? = when (value) {
        "battery" -> StudioPause.Battery
        "listener" -> StudioPause.Listener
        else -> null
    }

    fun book(json: JSONObject): StudioBook {
        val chapters = json.optJSONObject("chapters")
        val segments = json.optJSONObject("segments")
        val progress = json.optJSONObject("progress")
        val eta = json.optJSONObject("eta")?.takeIf { it.has("seconds") && it.optDouble("seconds").isFinite() }
        val speaker = json.optJSONObject("speakerPass")
        val waits = json.optJSONObject("queueWaitsOn")
        return StudioBook(
            id = json.getString("id"),
            title = json.text("title"),
            phase = json.text("phase"),
            statusLabel = json.text("statusLabel"),
            running = json.optBoolean("running"),
            starting = json.optBoolean("starting"),
            stopping = json.optBoolean("stopping"),
            paused = pause(json.text("paused")),
            canPause = json.optBoolean("canPause"),
            queuePosition = json.optInt("queuePosition", 0).takeIf { !json.isNull("queuePosition") && it > 0 },
            queueWaitsOn = waits?.let { StudioQueueWait(it.text("title"), pause(it.text("paused")) ?: StudioPause.Listener) },
            analysisInterrupted = json.optBoolean("analysisInterrupted"),
            precastHeld = json.optJSONObject("precast")?.optBoolean("held") == true,
            pendingChanges = json.optInt("pendingChanges", 0),
            seedPending = json.optBoolean("seedPending"),
            chaptersTotal = chapters?.optInt("total") ?: 0,
            chaptersCompleted = chapters?.optInt("completed") ?: 0,
            chaptersRedo = chapters?.optInt("redo") ?: 0,
            segmentsTotal = segments?.optInt("total") ?: 0,
            segmentsAnalyzed = segments?.optInt("analyzed") ?: 0,
            segmentsPending = segments?.takeIf { it.has("pending") && !it.isNull("pending") }?.optInt("pending"),
            overall = progress?.fraction("overall") ?: 0f,
            analysis = progress?.fraction("analysis") ?: 0f,
            synthesis = progress?.fraction("synthesis") ?: 0f,
            eta = eta?.let { StudioEta(it.text("phase"), it.optDouble("seconds")) },
            speaker = speaker?.let { StudioSpeakerPass(it.optInt("done"), it.optInt("total"), it.optBoolean("active")) },
            startError = json.text("startError"),
            lastError = json.text("lastError"),
            broken = json.text("broken"),
        )
    }

    fun chapter(json: JSONObject) = StudioChapter(
        id = json.getInt("id"),
        index = json.optInt("index"),
        title = json.text("displayTitle").ifEmpty { json.text("title") },
        status = json.text("status"),
        statusLabel = json.text("statusLabel"),
        redo = json.optBoolean("redo"),
        seconds = json.optDouble("seconds", 0.0).let { if (it.isFinite()) it else 0.0 },
        playable = json.optBoolean("playable"),
    )

    /** `GET /api/library`: `{root, books: [...]}`. */
    fun library(json: JSONObject): List<StudioBook> = json.optJSONArray("books").objects().map(::book)

    /** `GET /api/books/<id>`: `{book, chapters: [...]}`. */
    fun page(json: JSONObject) = StudioPage(book(json.getJSONObject("book")), json.optJSONArray("chapters").objects().map(::chapter))

    private fun JSONArray?.objects(): List<JSONObject> = if (this == null) emptyList() else (0 until length()).mapNotNull { optJSONObject(it) }
}
