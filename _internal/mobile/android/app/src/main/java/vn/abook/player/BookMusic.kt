package vn.abook.player

import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.security.MessageDigest

/**
 * Bài nhạc nền của MỘT cuốn sách: mục `music` của book.json (music_plan.package) nói mốc nào dùng bài nào, và bài là file
 * `music/<sha1>.<đuôi>` nằm trong thư mục sách. Một chỗ cho hai việc cần cùng một định nghĩa "bài mà sách đang dùng":
 * [LibraryServer] chỉ phục vụ các bài ấy cho máy đã ghép, và lúc tải sách ([LibraryPlugin.download]) chỉ tải các bài ấy về.
 */
object BookMusic {
    // Tên file một bài trong sách (music_plan.TRACK_FILE): bài trong file sách lẫn bài người nghe ghim.
    private val TRACK_FILE = Regex("music/([0-9a-f]{40})\\.(?:${MusicStore.EXTENSIONS.joinToString("|")})")
    private val SHA1 = Regex("[0-9a-f]{40}")

    /** Một bài cần có trong thư mục sách: `size` 0 = gói không nói; `sha1` = mã băm NỘI DUNG file nếu gói hay tên file cho biết. */
    class Track(val name: String, val size: Long, val sha1: String?)

    /** Nguồn một file từ máy kia: luồng byte, cỡ máy kia báo trước (-1 = không báo), và cách đóng. */
    class Source(val stream: InputStream, val length: Long = -1, val close: () -> Unit = {})

    /** Tên bài (`music/<sha1>.<đuôi>`) mà mốc `cue` dùng, nếu tên hợp lệ và có trong `music.tracks`; không thì null. */
    fun cuedTrack(music: JSONObject, cue: JSONObject): String? =
        cue.optString("track").takeIf { TRACK_FILE.matches(it) && music.optJSONObject("tracks")?.optJSONObject(it) != null }

    /** Các bài mà ít nhất một mốc đang dùng, theo thứ tự chương rồi mốc, mỗi bài một lần. Không có `music` -> rỗng. */
    fun tracks(music: JSONObject?): List<Track> {
        val chapters = music?.optJSONObject("chapters") ?: return emptyList()
        val found = LinkedHashMap<String, Track>()
        for (chapter in chapters.keys().asSequence().sortedWith(compareBy({ it.toIntOrNull() ?: Int.MAX_VALUE }, { it }))) {
            val cues = chapters.optJSONArray(chapter) ?: continue
            for (index in 0 until cues.length()) {
                val name = cues.optJSONObject(index)?.let { cuedTrack(music, it) } ?: continue
                if (name !in found) found[name] = describe(name, music.getJSONObject("tracks").getJSONObject(name))
            }
        }
        return found.values.toList()
    }

    private fun describe(name: String, info: JSONObject): Track {
        val size = (info.opt("size") as? Number)?.toLong()?.takeIf { it > 0 } ?: 0L
        // Bài người nghe ghim / bài nhập: tên file CHÍNH là sha1 nội dung (`local:<sha1>`). Bài danh mục: tên là sha1 của link, không
        // nói gì về nội dung - chỉ còn cỡ để kiểm.
        val stem = TRACK_FILE.matchEntire(name)!!.groupValues[1]
        val sha1 = info.optString("sha1").takeIf { SHA1.matches(it) } ?: stem.takeIf { MusicStore.localHash(info.optString("link")) == stem }
        return Track(name, size, sha1)
    }

    /** null = file đúng bài này; không thì lý do. `announced`: cỡ máy kia báo trước (-1 = không báo). */
    fun problem(file: File, track: Track, announced: Long = -1): String? {
        val length = file.length()
        if (length == 0L) return "file rỗng"
        if (track.size > 0 && length != track.size) return "sai cỡ ($length/${track.size})"
        if (announced >= 0 && length != announced) return "đứt giữa chừng ($length/$announced)"
        if (track.sha1 != null) {
            val digest = MessageDigest.getInstance("SHA-1")
            file.inputStream().use { input ->
                val buffer = ByteArray(1 shl 16)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    digest.update(buffer, 0, read)
                }
            }
            if (digest.digest().joinToString("") { "%02x".format(it) } != track.sha1) return "sai mã băm"
        }
        return null
    }

    /**
     * Có `track` trong thư mục sách `dir`: đã có và đúng thì thôi; không thì tải qua `open` vào `<tên>.part`, kiểm ([problem]) rồi
     * mới đổi tên - file hỏng không bao giờ nằm ở tên thật. Hỏng thì false (bài này im lặng, sách vẫn dùng được).
     */
    fun fetch(dir: File, track: Track, open: (String) -> Source?): Boolean {
        val target = Store.contained(dir, track.name)
        if (target.isFile && problem(target, track) == null) return true
        target.parentFile?.mkdirs()
        val part = File(target.path + ".part")
        part.delete()
        return try {
            val source = open(track.name) ?: return false
            try {
                source.stream.use { input -> part.outputStream().use { input.copyTo(it, 64 * 1024) } }
            } finally {
                runCatching { source.close() }
            }
            if (problem(part, track, source.length) != null) {
                part.delete()
                return false
            }
            if (!part.renameTo(target)) {
                target.delete()
                if (!part.renameTo(target)) {
                    part.delete()
                    return false
                }
            }
            true
        } catch (_: Exception) {
            part.delete()
            false
        }
    }
}
