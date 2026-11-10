package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.Normalizer
import kotlin.math.roundToInt
import kotlin.math.sqrt

/**
 * Kho nhạc (màn "Nhạc") của điện thoại: lõi không Android - bản Kotlin của abook/webui/music_library.py. Lướt / tìm / lọc cả danh mục nhạc nền ký số
 * ([MusicCatalog.everything]), bài đã lưu ([SavedTracks], ghim khỏi bộ dọn [MusicCatalog.prune]). Cùng bộ ca với máy chủ và Qt:
 * tests/fixtures/music_library/cases.json (MusicLibraryCasesTest).
 */
object MusicLibrary {
    const val EMOTION_THRESHOLD = 0.5
    const val SLOW_BPM = 90.0
    const val FAST_BPM = 130.0
    const val SHORT_SECONDS = 120.0
    const val LONG_SECONDS = 300.0
    val TEMPOS = listOf("slow", "mid", "fast")
    val LENGTHS = listOf("short", "mid", "long")

    private val MARKS = Regex("\\p{Mn}+")
    private val SPACES = Regex("\\s+")

    /** Chữ để so khi tìm: bỏ dấu tiếng Việt (cả đ/Đ), không phân biệt hoa thường, gộp khoảng trắng - như `music_library.fold`. */
    fun fold(text: String): String {
        val plain = MARKS.replace(Normalizer.normalize(text.replace('đ', 'd').replace('Đ', 'D'), Normalizer.Form.NFD), "")
        return plain.lowercase().trim().split(SPACES).filter { it.isNotEmpty() }.joinToString(" ")
    }

    fun tempoOf(bpm: Double?): String? = when {
        bpm == null || bpm <= 0 -> null
        bpm < SLOW_BPM -> "slow"
        bpm > FAST_BPM -> "fast"
        else -> "mid"
    }

    fun lengthOf(seconds: Double?): String? = when {
        seconds == null || seconds <= 0 -> null
        seconds < SHORT_SECONDS -> "short"
        seconds > LONG_SECONDS -> "long"
        else -> "mid"
    }

    /** Năng lượng (arousal -1..1 của danh mục) thành 0-100 % - như `energyPercent` của web. */
    fun energyPercent(arousal: Double?): Int? = arousal?.let { (((it + 1) / 2).coerceIn(0.0, 1.0) * 100).roundToInt() }

    fun percent(score: Double): Int = (score.coerceIn(0.0, 1.0) * 100).roundToInt()

    /** Một bài của chỉ mục: đủ để lọc, vẽ dòng và nghe thử; [info] là mục gốc của danh mục (chi tiết bài đọc từ đây). */
    class Track(val link: String, val info: JSONObject) {
        val title: String = text(info, "title")
        val creator: String = text(info, "creator")
        val duration: Double? = number(info, "duration")
        val bpm: Double? = number(info, "bpm")
        val style: String = text(info, "style")
        val bytes: Long = number(info, "bytes")?.toLong() ?: 0L
        val lufs: Double? = number(info, "lufs")
        val audibleStart: Double = number(info, "audibleStart") ?: 0.0
        val arousal: Double? = number(info, "arousal")
        val emotions: Map<String, Double> = info.optJSONObject("emotions")?.let { raw ->
            raw.keys().asSequence().mapNotNull { key -> number(raw, key)?.let { key to it } }.toMap()
        } ?: emptyMap()
        internal val titleKey = fold(title)
        internal val creatorKey = fold(creator)
        internal val haystack = "$titleKey $creatorKey"
        fun emotion(id: String): Double = emotions[id] ?: 0.0

        /** 13 cảm xúc theo điểm giảm dần (rồi theo mã) - thanh ngang của sheet chi tiết. */
        fun rankedEmotions(): List<Pair<String, Double>> = emotions.entries.sortedWith(compareBy({ -it.value }, { it.key })).map { it.key to it.value }
    }

    /** Bộ lọc của Kho nhạc (rỗng / false = không lọc). Cùng khoá với chuỗi truy vấn của web và `filter` của cases.json. */
    data class Filters(
        val q: String = "",
        val playlist: String = "",
        val style: String = "",
        val emotion: String = "",
        val tempo: String = "",
        val length: String = "",
        val downloaded: Boolean = false,
    ) {
        /** Có chip nào đang bật (chữ tìm không tính). */
        val filtering: Boolean get() = playlist.isNotEmpty() || style.isNotEmpty() || emotion.isNotEmpty() || tempo.isNotEmpty() || length.isNotEmpty() || downloaded

        companion object {
            fun of(json: JSONObject) = Filters(
                q = json.optString("q"), playlist = json.optString("playlist"), style = json.optString("style"), emotion = json.optString("emotion"),
                tempo = json.optString("tempo"), length = json.optString("length"), downloaded = json.optBoolean("downloaded"),
            )
        }
    }

    fun tracksOf(raw: Map<String, JSONObject>): List<Track> = raw.map { (link, info) -> Track(link, info) }

    private val BY_NAME = compareBy<Track>({ it.titleKey }, { it.creatorKey }, { it.link })

    /**
     * Các bài qua bộ lọc, theo thứ tự hiện (`music_library.select`): mọi từ tìm phải có trong tên bài + người sáng tác (bỏ dấu); cảm xúc: điểm
     * >= 0,5, xếp theo điểm giảm dần; còn lại xếp theo tên bài bỏ dấu, rồi người sáng tác. `playlists`: mã -> link; `downloaded`: link đã tải.
     */
    fun select(tracks: List<Track>, filters: Filters, playlists: Map<String, List<String>>, downloaded: Set<String> = emptySet()): List<Track> {
        val words = fold(filters.q).split(' ').filter { it.isNotEmpty() }
        val members = filters.playlist.takeIf { it.isNotEmpty() }?.let { playlists[it]?.toHashSet() ?: emptySet() }
        val found = tracks.filter { track ->
            (members == null || track.link in members) &&
                (!filters.downloaded || track.link in downloaded) &&
                (filters.style.isEmpty() || track.style == filters.style) &&
                (filters.tempo.isEmpty() || tempoOf(track.bpm) == filters.tempo) &&
                (filters.length.isEmpty() || lengthOf(track.duration) == filters.length) &&
                (filters.emotion.isEmpty() || track.emotion(filters.emotion) >= EMOTION_THRESHOLD) &&
                words.all { it in track.haystack }
        }
        return if (filters.emotion.isNotEmpty()) {
            found.sortedWith(compareBy<Track> { -it.emotion(filters.emotion) }.then(BY_NAME))
        } else {
            found.sortedWith(BY_NAME)
        }
    }

    /** Một cảm xúc khớp của khối "Vì sao bài này": điểm ở đoạn và ở bài. */
    data class Match(val id: String, val scene: Double, val track: Double)
    data class Why(val fit: Double, val matches: List<Match>)

    /** `music_library.why`: độ khớp cosine (như `music_select.emotion_cosine`) + `count` cảm xúc có tích đoạn x bài lớn nhất. Không có cảm xúc ở một bên -> null (ẩn khối). */
    fun why(scene: Map<String, Double>, track: Map<String, Double>, count: Int = 3): Why? {
        if (scene.isEmpty() || track.isEmpty()) return null
        val names = (scene.keys + track.keys).toSortedSet()
        var dot = 0.0
        var a = 0.0
        var b = 0.0
        val pairs = names.map { name ->
            val x = (scene[name] ?: 0.0).coerceAtLeast(0.0)
            val y = (track[name] ?: 0.0).coerceAtLeast(0.0)
            dot += x * y
            a += x * x
            b += y * y
            Triple(name, x, y)
        }
        val norm = sqrt(a) * sqrt(b)
        if (norm <= 0) return null
        val matches = pairs.filter { it.second * it.third > 0 }.sortedWith(compareBy({ -(it.second * it.third) }, { it.first })).take(count)
            .map { Match(it.first, it.second, it.third) }
        return Why(dot / norm, matches)
    }

    /** "Nhạc trong sách": các bài một cuốn dùng (gộp trùng theo lần đầu), số đoạn mỗi bài, khoá đoạn đầu tiên. `scenes`: (khoá đoạn, link). */
    data class BookTrack(val link: String, val scenes: Int, val scene: String?)

    fun bookTracks(scenes: List<Pair<String?, String>>): List<BookTrack> {
        val found = LinkedHashMap<String, BookTrack>()
        for ((key, link) in scenes) {
            if (link.isEmpty()) continue
            val held = found[link]
            found[link] = held?.copy(scenes = held.scenes + 1) ?: BookTrack(link, 1, key)
        }
        return found.values.toList()
    }

    private fun text(info: JSONObject, key: String): String = if (info.isNull(key)) "" else (info.opt(key) as? String).orEmpty()

    private fun number(info: JSONObject, key: String): Double? = (info.opt(key) as? Number)?.toDouble()?.takeIf { !it.isNaN() }
}

/**
 * Sổ bài người dùng lưu (`saved.json`: {"version": 1, "links": [...]}, mới lưu sau cùng) - cùng hình với `music_library.SavedTracks` của máy tính.
 * Bài đã lưu là bài GHIM: [MusicCatalog.prune] không xoá (qua [MusicCatalog.pinned]).
 */
class SavedTracks(private val file: File) {
    private var links: List<String>? = null

    @Synchronized
    fun links(): List<String> = links ?: read().also { links = it }

    private fun read(): List<String> = runCatching {
        val data = JSONObject(file.readText(Charsets.UTF_8))
        if (data.optInt("version") != VERSION) return emptyList()
        val raw = data.optJSONArray("links") ?: return emptyList()
        (0 until raw.length()).mapNotNull { (raw.opt(it) as? String)?.takeIf { link -> link.startsWith("https://") } }.distinct()
    }.getOrDefault(emptyList())

    @Synchronized
    fun add(more: Collection<String>): List<String> {
        val current = links()
        val added = more.distinct().filter { it.startsWith("https://") && it !in current }
        if (added.isNotEmpty()) write(current + added)
        return added
    }

    @Synchronized
    fun remove(gone: Collection<String>): List<String> {
        val current = links()
        val removed = current.filter { it in gone }
        if (removed.isNotEmpty()) write(current - removed.toSet())
        return removed
    }

    private fun write(next: List<String>) {
        links = next
        runCatching {
            Store.writeAtomic(file, JSONObject().put("version", VERSION).put("links", JSONArray(next)).toString().toByteArray(Charsets.UTF_8))
        }
    }

    companion object {
        const val VERSION = 1
    }
}
