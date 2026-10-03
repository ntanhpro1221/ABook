package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject

/**
 * Nhạc nền cho sách nghe bằng "Nghe ngay" - bản Kotlin của abook/webui/music_playlist.py (docs/LISTEN_ANYTHING.md mục 4). Sách chỉ có
 * chữ không có không khí từng cảnh, nên người nghe chọn một DANH SÁCH PHÁT cho cả cuốn (`music.playlist` của lớp sửa - [BookEdits]):
 * mã một danh sách của danh mục ([MusicCatalog], mục `playlists` của mục lục), hay [MINE] = "Nhạc của tôi" ([MusicStore]).
 *
 * Trình phát ([MusicBed]) chơi các bài nối nhau theo thứ tự đã trộn sẵn trên MỘT đồng hồ nhạc riêng của cuốn (không theo giây của
 * chương): sang chương mới nhạc chơi tiếp, không bắt đầu lại. Mỗi bài một khoảng trên đồng hồ ấy ([timeline]), bài sau bắt đầu
 * [OVERLAP_SECONDS] trước khi bài trước hết để hai bài chuyển mờ vào nhau như nhạc theo cảnh. Chỉ org.json: chạy trong test JVM.
 */
object Playlists {
    const val MINE = "mine"
    /** Bài không biết độ dài (thông tin danh mục thiếu): khoảng mặc định trên đồng hồ - bài vẫn lặp liền nếu ngắn hơn. */
    const val FALLBACK_SECONDS = 180.0
    /** Bằng thời gian chuyển mờ của [MusicBed]: bài sau vào lúc bài trước bắt đầu mờ đi, bài trước tắt hẳn đúng lúc nó hết. */
    const val OVERLAP_SECONDS = 2.0
    private val ID = Regex("[a-z0-9_]{1,40}")
    private const val TEXT_MAX = 200

    private fun text(value: Any?): String =
        if (value is String) value.split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ").take(TEXT_MAX) else ""

    /** `music_playlist.catalogue_playlists`: các danh sách đúng hình dạng {id, name, description, minutes, tracks}; mã lạ / trùng / "mine",
     *  hay không có link https:// nào thì bỏ. */
    fun catalogue(manifest: JSONObject): List<JSONObject> {
        val out = ArrayList<JSONObject>()
        val seen = HashSet<String>()
        val items = manifest.optJSONArray("playlists") ?: return out
        for (index in 0 until items.length()) {
            val item = items.opt(index) as? JSONObject ?: continue
            val id = item.opt("id") as? String ?: continue
            if (!ID.matches(id) || id == MINE || id in seen) continue
            val raw = item.optJSONArray("tracks") ?: continue
            val links = LinkedHashSet<String>()
            for (at in 0 until raw.length()) (raw.opt(at) as? String)?.takeIf { it.startsWith("https://") }?.let { links.add(it) }
            if (links.isEmpty()) continue
            seen.add(id)
            val minutes = (item.opt("minutes") as? Number)?.takeIf { it.toDouble() > 0 }?.toInt() ?: 0
            out.add(JSONObject().put("id", id).put("name", text(item.opt("name")).ifEmpty { id })
                .put("description", text(item.opt("description"))).put("minutes", minutes).put("tracks", JSONArray(links.toList())))
        }
        return out
    }

    /** Cho menu chọn (không kèm link): {id, name, description, minutes, count}. */
    fun summaries(playlists: List<JSONObject>): JSONArray = JSONArray(playlists.map { item ->
        JSONObject().put("id", item.getString("id")).put("name", item.getString("name")).put("description", item.getString("description"))
            .put("minutes", item.getInt("minutes")).put("count", item.getJSONArray("tracks").length())
    })

    /** Link của danh sách `id` đúng thứ tự trộn sẵn; danh mục không (còn) có danh sách ấy thì rỗng. */
    fun linksOf(playlists: List<JSONObject>, id: String): List<String> {
        val tracks = playlists.firstOrNull { it.getString("id") == id }?.getJSONArray("tracks") ?: return emptyList()
        return (0 until tracks.length()).map { tracks.getString(it) }
    }

    /** Một bài trong hàng phát: độ dài (giây, null = không biết) và độ khuếch đại đã tính ([MusicGain.cueGainDb], công thức Pha 4). */
    data class Track(val link: String, val duration: Double?, val gainDb: Double)

    private fun number(value: Any?): Double? = (value as? Number)?.toDouble()?.takeIf { it.isFinite() }

    /**
     * `music_playlist.queue` + `music_plan.apply_gain`: hàng bài theo đúng thứ tự `links`, bỏ bài máy này không dùng được (`available`);
     * mỗi bài nằm `levelDb` LU dưới giọng theo độ to (`lufs`) và độ lấn dải tiếng nói (`speechBand`) của nó trong `infos`.
     */
    fun queue(links: List<String>, infos: Map<String, JSONObject>, levelDb: Double, available: (String) -> Boolean = { true }): List<Track> =
        links.filter(available).map { link ->
            val info = infos[link]
            val duration = number(info?.opt("duration"))?.takeIf { it > 0 }
            Track(link, duration, MusicGain.cueGainDb(levelDb, number(info?.opt("lufs")), number(info?.opt("speechBand"))))
        }

    /** Khoảng của một bài trên đồng hồ nhạc của cuốn: [start, end) giây. */
    data class Span(val start: Double, val end: Double, val track: Track, val index: Int)

    /** Các bài nối nhau trên đồng hồ nhạc: mỗi bài dài (độ dài - [OVERLAP_SECONDS]), ít nhất 1 giây. */
    fun timeline(tracks: List<Track>): List<Span> {
        var at = 0.0
        return tracks.mapIndexed { index, track ->
            val length = maxOf(1.0, (track.duration ?: FALLBACK_SECONDS) - OVERLAP_SECONDS)
            Span(at, at + length, track, index).also { at += length }
        }
    }

    /** Bài đang ở giây `seconds` của đồng hồ nhạc (hết danh sách thì quay lại bài đầu) và giây trong bài ấy. Rỗng -> null. */
    fun at(spans: List<Span>, seconds: Double): Pair<Span, Double>? {
        val total = spans.lastOrNull()?.end ?: return null
        val wrapped = ((seconds % total) + total) % total
        val span = spans.firstOrNull { wrapped >= it.start && wrapped < it.end } ?: spans.last()
        return span to (wrapped - span.start)
    }
}
