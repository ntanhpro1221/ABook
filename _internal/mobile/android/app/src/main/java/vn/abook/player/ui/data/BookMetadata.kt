package vn.abook.player.ui.data

import androidx.compose.runtime.Immutable
import org.json.JSONArray
import org.json.JSONObject

@Immutable
data class BookMetadata(
    val illustrator: String = "", val altTitles: List<String> = emptyList(), val genres: List<String> = emptyList(),
    val summary: String = "", val sourceUrl: String = "", val sourceSite: String = "",
) {
    fun json() = JSONObject().put("illustrator", illustrator).put("altTitles", JSONArray(altTitles)).put("genres", JSONArray(genres))
        .put("summary", summary).put("source", JSONObject().put("url", sourceUrl).put("site", sourceSite))
    companion object {
        fun from(raw: JSONObject): BookMetadata {
            fun list(key: String): List<String> = raw.optJSONArray(key)?.let { a -> (0 until a.length()).map { a.getString(it) } }.orEmpty()
            return BookMetadata(raw.optString("illustrator"), list("altTitles"), list("genres"), raw.optString("summary"),
                raw.optJSONObject("source")?.optString("url").orEmpty(), raw.optJSONObject("source")?.optString("site").orEmpty())
        }
    }
}
