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

    // ---- "Kèm nhạc nền" khi xuất sách nói (music_export.packaged_music / packaged_state của máy tính) -----------------------------

    /**
     * Mục `music` của cuốn `id` cho bản xuất "Kèm nhạc nền": lớp sửa của người nghe (mức, đoạn im lặng, bài ghim) phủ lên gói, riêng
     * công tắc tắt bị bỏ qua - người dùng đã tích ô (`_book_music(include_disabled=True)`). Sách không có nhạc -> null.
     */
    fun exportMusic(id: String): JSONObject? {
        val raw = Store.rawManifest(id)?.opt("music")?.takeIf { it is JSONObject } ?: return null
        val edits = BookEdits.load(Store.bookDir(id))
        val shown = if (edits.optJSONObject("music")?.has("enabled") == true) {
            JSONObject(edits.toString()).also { it.getJSONObject("music").remove("enabled") }
        } else {
            edits
        }
        return BookEdits.applyMusic(raw, shown) as? JSONObject
    }

    /**
     * Ô "Kèm nhạc nền" của hộp xuất (`packaged_state`): `available` = có mốc nhạc ở ít nhất một chương (danh sách phát của sách chỉ có
     * chữ không tính), `enabled` = mặc định của ô theo công tắc Nhạc nền của cuốn.
     */
    fun exportState(id: String): Pair<Boolean, Boolean> {
        val chapters = exportMusic(id)?.optJSONObject("chapters")
        val available = chapters != null && chapters.keys().asSequence().any { (chapters.optJSONArray(it)?.length() ?: 0) > 0 }
        val enabled = available && BookEdits.load(Store.bookDir(id)).optJSONObject("music")?.opt("enabled") != false
        return available to enabled
    }

    /** Các bài mà mốc của `music` dùng nhưng chưa có (hay hỏng) trong thư mục sách `dir` - cần tải trước khi xuất. */
    fun missing(dir: File, music: JSONObject?): List<Track> = tracks(music).filter { track ->
        val file = runCatching { Store.contained(dir, track.name) }.getOrNull()
        file != null && !(file.isFile && problem(file, track) == null)
    }

    /**
     * Nhạc từng chương cho bộ trộn ([MusicExport.Mixer]) - `packaged_music`: mốc của chương (mốc thiếu `gainDb` - sách đóng gói bởi bản
     * cũ - lấy mức chung như trình phát), file bài trong thư mục sách `dir`. Mốc mà bài không có hay hỏng ([problem]) bị bỏ và đếm vào
     * `dropped` ("N đoạn thiếu nhạc vì chưa tải được bài"). Chương không có mốc nào: không có trong kết quả.
     */
    fun chapterMusic(dir: File, music: JSONObject?, chapterIds: Iterable<Int>): Map<Int, MusicExport.ChapterMusic> {
        if (music == null) return emptyMap()
        val level = BookEdits.trackNumber(music, "levelDb") ?: BookEdits.DEFAULT_LEVEL_DB
        val tracks = music.optJSONObject("tracks") ?: JSONObject()
        val described = tracks(music).associateBy { it.name }
        val usable = HashMap<String, File?>()
        val out = LinkedHashMap<Int, MusicExport.ChapterMusic>()
        for (chapterId in chapterIds) {
            val cues = MusicCues.of(music, chapterId).map { cue ->
                if (cue.gainDb != null) cue
                else {
                    val info = tracks.optJSONObject(cue.track)
                    cue.copy(gainDb = MusicGain.cueGainDb(level, BookEdits.trackNumber(info, "lufs"), BookEdits.trackNumber(info, "speechBand"),
                        BookEdits.trackNumber(info, "s95")))
                }
            }
            if (cues.isEmpty()) continue
            val files = LinkedHashMap<String, File>()
            for (name in cues.map { it.track }.distinct()) {
                val file = usable.getOrPut(name) {
                    val track = described[name] ?: return@getOrPut null
                    runCatching { Store.contained(dir, name) }.getOrNull()?.takeIf { it.isFile && problem(it, track) == null }
                }
                if (file != null) files[name] = file
            }
            val kept = cues.filter { it.track in files }
            out[chapterId] = MusicExport.ChapterMusic(kept, files, cues.size - kept.size,
                kept.map { it.track }.distinct().mapNotNull { name -> tracks.optJSONObject(name)?.let { name to it } }.toMap())
        }
        return out
    }

    /**
     * Chỗ trống thêm cho bộ đệm PCM bài của một lượt xuất ([TrackPcmCache]): cỡ PCM ở `rate`/`channels` của bài dài nhất mà mốc dùng, x3
     * (K2_SPEC 2.2). Độ dài theo số đo trong gói (`seconds`, `duration`); không có thì ước theo cỡ file, 12 000 byte một giây (MP3 96 kb/s -
     * bài nén nặng hơn thì ước dư).
     */
    fun pcmBytes(dir: File, music: JSONObject?, rate: Int, channels: Int): Long {
        val info = music?.optJSONObject("tracks") ?: return 0
        val longest = tracks(music).maxOfOrNull { track ->
            val known = info.optJSONObject(track.name)
            BookEdits.trackNumber(known, "seconds") ?: BookEdits.trackNumber(known, "duration") ?: run {
                val length = runCatching { Store.contained(dir, track.name).length() }.getOrDefault(0L)
                (if (length > 0) length else track.size) / 12000.0
            }
        } ?: return 0
        return TrackPcmCache.bytesFor(longest, rate, channels) * 3
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
                source.stream.use { input ->
                    val limit = PeerTransfer.budget(track.name, track.size)
                    if (source.length > limit) throw PeerTransfer.Limit()
                    java.io.FileOutputStream(part).use {
                        PeerTransfer.copy(input, it, limit, target.parentFile!!)
                        it.fd.sync()
                    }
                }
            } finally {
                runCatching { source.close() }
            }
            if (problem(part, track, source.length) != null) {
                part.delete()
                return false
            }
            if (!part.renameTo(target)) {
                part.delete()
                return false
            }
            true
        } catch (_: Exception) {
            part.delete()
            false
        }
    }
}
