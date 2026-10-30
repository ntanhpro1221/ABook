package vn.abook.player.ui.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.StudioLink
import vn.abook.player.SyncLink

/** Live production is never inferred from a partial downloaded bundle. */
data class Production(val producing: Boolean, val paused: Boolean, val pauseReason: String?, val etaPhase: String?, val etaSeconds: Double?) {
    companion object {
        // server.Application.listen_library returns an array, exactly as the web ListenSource reads it.
        fun catalogue(raw: String): Map<String, Production> {
            val rows = JSONArray(raw)
            return buildMap {
                for (i in 0 until rows.length()) rows.optJSONObject(i)?.let { row ->
                    row.optString("id").takeIf { it.isNotBlank() }?.let { put(it, parse(row)) }
                }
            }
        }

        fun parse(row: JSONObject) = Production(row.optBoolean("producing"), row.optBoolean("paused"),
            row.optString("pauseReason").takeIf { it == "battery" || it == "listener" },
            row.optJSONObject("eta")?.optString("phase"), row.optJSONObject("eta")?.optDouble("seconds")?.takeIf { it.isFinite() })
    }
}

/** Same GET /api/listen/library and pinned Studio link as the web's remote listening UI. No new server endpoint. */
class ProductionSource(private val context: Context) {
    fun read(): Map<Pair<String, String>, Production> {
        val result = HashMap<Pair<String, String>, Production>()
        for (computer in StudioLink.computers(context)) {
            val link = StudioLink.link(context, computer.key) ?: continue
            val rows = runCatching {
                Production.catalogue(SyncLink.request(context, "GET", "/api/listen/library", auth = false, root = link.base, token = link.token,
                    readTimeoutMs = 4000, connectTimeoutMs = 2000))
            }.getOrNull() ?: continue
            rows.forEach { (id, state) -> result[computer.key to id] = state }
        }
        return result
    }
}

object ProductionText {
    fun upcoming(book: ListenBook): String {
        val where = book.remote?.let { "trên ${it.deviceName}" }
        if (where != null) {
            if (book.producing && book.pauseReason != null) return "Đang tạm dừng $where"
            return if (book.producing) "Đang làm $where" else "Chưa có chương nghe được · làm $where"
        }
        if (book.producing && book.pauseReason != null) return if (book.pauseReason == "battery") "Đang tạm dừng · máy đang chạy pin" else "Đang tạm dừng"
        val eta = if (book.etaSeconds != null && book.etaPhase in listOf("analysis", "speaker")) "chương đầu nghe được sau khoảng ${Fmt.length(book.etaSeconds + 600)}" else "đang chuẩn bị"
        return if (book.producing) "Đang làm · $eta" else "Chưa có chương nghe được"
    }
}
