package vn.abook.player

import org.json.JSONObject

/**
 * Cây duyệt của trình phát cho Android Auto và mọi trình duyệt media của hệ thống (PlaybackService là MediaLibraryService):
 * gốc -> các cuốn phát được trên máy (tải hẳn hay nghe thẳng), cuốn nghe gần nhất đứng đầu -> các chương có audio hay chỉ có chữ (giọng máy đọc).
 * Bấm một cuốn là nghe tiếp đúng chỗ đang dở; bấm một chương là nghe chương ấy (chương đang dở thì từ chỗ dở).
 *
 * Hàm thuần trên gói sách (book.json / stream.json) và trạng thái nghe của hồ sơ đang dùng (Store.state) - không đụng
 * Android, test JVM được (LibraryTreeTest).
 */
object LibraryTree {
    const val ROOT = "root"
    private const val BOOK = "book/"
    private const val CHAPTER = "chapter/"

    /** Một mục của cây: `bookId` rỗng ở gốc. */
    data class Node(
        val id: String,
        val bookId: String,
        val title: String,
        val subtitle: String,
        val playable: Boolean,
        val browsable: Boolean,
    )

    /** Chỗ bắt đầu phát khi trình điều khiển chọn một mục. */
    data class Start(val bookId: String, val chapterId: Int, val seconds: Double)

    /**
     * Mục chữ của một chương CHỈ CÓ CHỮ (giọng máy đọc to - ReadAloud), "" với mọi chương khác. Chương chữ = `state` "text", hay có
     * `text` mà không có `file` (như packages.py và androidSource.ts) - lệnh `load` của giao diện chỉ gửi `text`. Chung cho gói sách
     * (book.json) và `load` (PlayerPlugin), để hai đường thấy cùng một chương chữ.
     */
    fun textEntry(chapter: JSONObject): String {
        val text = chapter.optString("text").takeIf { it != "null" }.orEmpty()
        val file = chapter.optString("file").takeIf { it != "null" }.orEmpty()
        return when {
            chapter.optString("state") == "text" -> text.ifEmpty { "texts/${chapter.optInt("id")}.txt" }
            text.isNotEmpty() && file.isBlank() -> text
            else -> ""
        }
    }

    /** Các chương nghe được của một gói sách: chương có audio, và chương chỉ có chữ (giọng máy đọc to). Chương chưa có audio
     *  cũng chưa có chữ thì không có trong cây (bấm vào không phát được). */
    fun chapters(manifest: JSONObject): List<Playback.Chapter> {
        val array = manifest.optJSONArray("chapters") ?: return emptyList()
        return (0 until array.length()).map { array.getJSONObject(it) }.mapNotNull {
            val text = textEntry(it)
            val file = it.optString("file").takeIf { file -> file.isNotBlank() && file != "null" }
            when {
                text.isNotEmpty() -> Playback.Chapter(it.getInt("id"), it.optString("fullTitle"), "", 0.0, text)
                it.optBoolean("available") && file != null -> Playback.Chapter(it.getInt("id"), it.optString("fullTitle"), file, it.optDouble("duration", 0.0))
                else -> null
            }
        }
    }

    /** Các cuốn (gói sách, trạng thái nghe): cuốn nghe gần nhất đứng đầu, cuốn chưa nghe theo tên. */
    fun books(entries: List<Pair<JSONObject, JSONObject>>): List<Node> =
        entries.filter { (manifest, _) -> manifest.optString("id").isNotEmpty() && chapters(manifest).isNotEmpty() }
            .sortedWith(compareByDescending<Pair<JSONObject, JSONObject>> { (_, state) -> lastAt(state) }
                .thenBy { (manifest, _) -> manifest.optString("title") })
            .map { (manifest, state) ->
                val id = manifest.getString("id")
                val resume = resumable(manifest, state)
                Node(
                    id = BOOK + id,
                    bookId = id,
                    title = manifest.optString("title").ifBlank { "Sách" },
                    subtitle = if (resume != null) "Nghe tiếp: ${resume.first.title}" else "${chapters(manifest).size} chương",
                    playable = true,
                    browsable = true,
                )
            }

    fun chapterNodes(manifest: JSONObject, state: JSONObject): List<Node> {
        val id = manifest.getString("id")
        val current = resumable(manifest, state)?.first?.id
        val heard = state.optJSONObject("chapters")
        val parts = partsOf(manifest)
        return chapters(manifest).map { chapter ->
            val subtitle = when {
                chapter.id == current -> "Đang nghe dở"
                heard?.optJSONObject(chapter.id.toString())?.optBoolean("done") == true -> "Đã nghe"
                chapter.isText -> "Giọng máy đọc"
                else -> minutes(chapter.duration)
            }
            // Cả bộ nhiều phần trong một file (bookfile.pack_series): màn Android Auto không có tiêu đề nhóm nên mỗi dòng
            // tự nói mình ở phần nào.
            val part = parts[chapter.id]?.let { "Phần $it · " }.orEmpty()
            Node("$CHAPTER$id/${chapter.id}", id, chapter.title, part + subtitle, playable = true, browsable = false)
        }
    }

    /** Chương -> số phần, chỉ khi sách có nhiều hơn một phần (`parts` của book.json); sách một phần: rỗng. */
    private fun partsOf(manifest: JSONObject): Map<Int, Int> {
        if ((manifest.optJSONArray("parts")?.length() ?: 0) < 2) return emptyMap()
        val array = manifest.optJSONArray("chapters") ?: return emptyMap()
        return (0 until array.length()).mapNotNull { array.optJSONObject(it) }
            .filter { it.optInt("part", 0) > 0 }.associate { it.getInt("id") to it.getInt("part") }
    }

    fun isBook(mediaId: String) = mediaId.startsWith(BOOK)

    /** Mã sách trong mã một mục (cuốn hay chương); gốc hay mã lạ: null. */
    fun bookOf(mediaId: String): String? = when {
        mediaId.startsWith(BOOK) -> mediaId.removePrefix(BOOK).takeIf { it.isNotEmpty() }
        mediaId.startsWith(CHAPTER) -> mediaId.removePrefix(CHAPTER).substringBeforeLast('/', "").takeIf { it.isNotEmpty() }
        else -> null
    }

    /**
     * Chỗ bắt đầu cho mục `mediaId`. Cuốn: chỗ đang dở (chương ấy còn nghe được), không thì chương đầu. Chương: chỗ dở nếu
     * đang dở chính chương ấy, không thì đầu chương. Mục không còn trên máy (xoá rồi, máy tính bỏ chương): null.
     */
    fun start(mediaId: String, manifest: JSONObject, state: JSONObject): Start? {
        val id = bookOf(mediaId) ?: return null
        if (manifest.optString("id") != id) return null
        val available = chapters(manifest)
        val resume = resumable(manifest, state)
        if (mediaId.startsWith(BOOK)) {
            if (resume != null) return Start(id, resume.first.id, resume.second)
            return available.firstOrNull()?.let { Start(id, it.id, 0.0) }
        }
        val chapterId = mediaId.substringAfterLast('/').toIntOrNull() ?: return null
        if (available.none { it.id == chapterId }) return null
        return Start(id, chapterId, if (resume?.first?.id == chapterId) resume.second else 0.0)
    }

    private fun resumable(manifest: JSONObject, state: JSONObject): Pair<Playback.Chapter, Double>? {
        val last = state.optJSONObject("last") ?: return null
        val chapter = chapters(manifest).firstOrNull { it.id == last.optInt("chapterId", Int.MIN_VALUE) } ?: return null
        return chapter to last.optDouble("seconds", 0.0).coerceAtLeast(0.0)
    }

    private fun lastAt(state: JSONObject): Double = state.optJSONObject("last")?.optDouble("at", 0.0)?.takeIf { !it.isNaN() } ?: 0.0

    private fun minutes(seconds: Double): String {
        val total = (seconds / 60).toInt().coerceAtLeast(1)
        return if (total < 60) "$total phút" else "${total / 60} giờ ${total % 60} phút"
    }
}
