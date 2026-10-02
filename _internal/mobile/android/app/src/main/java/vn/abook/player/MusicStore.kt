package vn.abook.player

import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.security.MessageDigest

/**
 * "Nhạc của tôi" trên điện thoại: nhạc người dùng tự nhập làm nhạc nền - bản Kotlin của abook/webui/music_local.py (docs/MUSIC_IMPORT.md),
 * cùng hình dạng sổ (`library.json`), cùng link `local:<sha1 của file>`, cùng câu báo lỗi, cùng JSON thông tin bài.
 *
 * Kho là của TỪNG MÁY (không nằm trong sách): mỗi file chép vào `files/<sha1 nội dung>.<đuôi>` (nhập hai lần cùng nội dung chỉ giữ
 * một bản), kèm sổ ghi tên bài, nghệ sĩ, album, thể loại, độ dài (đọc bằng [TagReader] - trên máy là MediaMetadataRetriever),
 * độ to ([LoudnessMeter]) và - khi đã phân tích - không khí của bài. Điện thoại không chọn nhạc tự động nên không có `near`:
 * bài nhập ở đây chỉ được GHIM tay vào một đoạn nhạc của sách (`BookEdits.setMusic`), file đi theo sách ở lớp sửa.
 *
 * Phân tích: [analyzer] (model chỉ-nghe của phiên Nhạc, chưa có) cắm vào đây; kết quả qua [cleanAnalysis] như bên Python. Chưa có
 * bộ phân tích thì bài là "chưa phân tích": KHÔNG BAO GIỜ bịa số.
 */
class MusicStore(
    private val root: File,
    private val tags: TagReader,
    private val loudness: LoudnessMeter? = null,
    private val clock: () -> Double = { System.currentTimeMillis() / 1000.0 },
) {
    /** Một file không nhập được. Câu chữ để người dùng đọc (tên file + lý do). */
    class ImportError(message: String) : Exception(message)

    /** Thẻ + độ dài của một file nhạc; thẻ có thể vắng (null). */
    class Tags(val duration: Double, val title: String? = null, val artist: String? = null, val album: String? = null, val genre: String? = null)

    /** Đọc file nhạc: không đọc được như âm thanh / không biết độ dài thì ném [ImportError] với lý do ngắn (không có tên file). */
    fun interface TagReader {
        fun read(file: File): Tags
    }

    /** Độ to LUFS hai kênh của file (như `music_plan.measured_lufs`), hay null khi chưa đo được. */
    fun interface LoudnessMeter {
        fun measure(file: File): Double?
    }

    /** Bộ phân tích âm thanh chỉ-nghe: file -> {valence, arousal, ...} (xem [cleanAnalysis]) hay null. Chưa có bộ nào cắm vào. */
    @Volatile
    var analyzer: ((File) -> JSONObject?)? = null

    private val lock = Any()
    private var index: LinkedHashMap<String, JSONObject>? = null

    fun analyzerAvailable(): Boolean = analyzer != null

    // ---- sổ -----------------------------------------------------------------------------------------------------------

    private fun tracks(): LinkedHashMap<String, JSONObject> {
        index?.let { return it }
        val found = LinkedHashMap<String, JSONObject>()
        try {
            val data = JSONObject(File(root, INDEX_FILE).readText(Charsets.UTF_8))
            val listed = data.optJSONObject("tracks")
            if (data.optInt("version", -1) == INDEX_VERSION && listed != null) {
                for (digest in listed.keys().asSequence().toList()) {
                    val entry = listed.optJSONObject(digest)
                    if (SHA1.matches(digest) && entry != null) found[digest] = entry
                }
            }
        } catch (_: IOException) {
        } catch (_: org.json.JSONException) {
        }
        index = found
        return found
    }

    private fun save() {
        val listed = JSONObject()
        for ((digest, entry) in tracks()) listed.put(digest, entry)
        Store.writeAtomic(File(root, INDEX_FILE), JSONObject().put("version", INDEX_VERSION).put("tracks", listed).toString())
    }

    private fun path(digest: String, entry: JSONObject) = File(File(root, "files"), "$digest.${entry.optString("ext", "mp3")}")

    // ---- đọc ----------------------------------------------------------------------------------------------------------

    /**
     * Một bài theo hình bài danh mục (kèm khoá giao diện): link, title, creator, duration, source "local", lufs, và các khoá của
     * phân tích nếu đã có. `analysed` cho giao diện; `name` là tên file gốc.
     */
    private fun info(digest: String, entry: JSONObject): JSONObject {
        val analysis = entry.optJSONObject("analysis")
        val title = entry.optString("title").ifEmpty { File(entry.optString("name")).nameWithoutExtension }.ifEmpty { "Bài nhạc" }
        val info = JSONObject().put("link", LOCAL_PREFIX + digest).put("title", title).put("creator", entry.optString("artist"))
            .put("duration", Math.rint(entry.optDouble("duration", 0.0)).toLong()).put("source", "local")
            .put("analysed", analysis != null && analysis.length() > 0).put("name", entry.optString("name"))
            .put("bytes", entry.optLong("bytes", 0)).put("added", entry.optDouble("added", 0.0))
        for (key in listOf("album", "genre")) entry.optString(key).takeIf { it.isNotEmpty() }?.let { info.put(key, it) }
        val lufs = entry.opt("lufs")
        if (lufs is Number) info.put("lufs", lufs.toDouble())
        if (analysis != null) for (key in analysis.keys().asSequence().toList()) info.put(key, analysis.opt(key))
        if (lufs is Number) info.put("lufs", lufs.toDouble()) // số đo từ chính file thắng số của bộ phân tích
        return info
    }

    /** Mọi bài trong kho, mới nhập trước. */
    fun entries(): List<JSONObject> = synchronized(lock) {
        tracks().map { (digest, entry) -> info(digest, entry) }
            .sortedWith(compareBy({ -it.optDouble("added", 0.0) }, { it.optString("title").lowercase() }))
    }

    /** Thông tin của một link `local:` có trong kho; link khác / không có thì null. */
    fun lookup(link: String): JSONObject? = synchronized(lock) {
        val digest = localHash(link) ?: return null
        tracks()[digest]?.let { info(digest, it) }
    }

    /** File của bài trong kho; không có (hay đã xoá) -> null. */
    fun file(link: String): File? = synchronized(lock) {
        val digest = localHash(link) ?: return null
        val entry = tracks()[digest] ?: return null
        path(digest, entry).takeIf { it.isFile }
    }

    /** `(thông tin, file)` của một bài - cho `BookEdits.setMusic` (ghim vào một đoạn của sách). */
    fun track(link: String): Pair<JSONObject, File>? = synchronized(lock) {
        val found = lookup(link)
        val source = file(link)
        if (found != null && source != null) found to source else null
    }

    // ---- ghi ----------------------------------------------------------------------------------------------------------

    /** Nhập một file nằm trên đĩa (`source`): [importStream] với tên file của nó. */
    fun importFile(source: File): Pair<JSONObject, Boolean> {
        if (!source.isFile) throw ImportError("“${source.name}”: không thấy file này.")
        return importStream(source.name) { source.inputStream() }
    }

    /**
     * Nhập một bản nhạc: kiểm đuôi, chép vào kho theo mã sha1 nội dung (đọc từ `open`, tối đa 1 GB), đọc thẻ, đo độ to, phân tích nếu
     * có bộ phân tích. Trả (thông tin bài, đã có sẵn trong kho?). Trùng nội dung với bài đã có thì không chép lại. `displayName` là
     * tên file người dùng thấy (đuôi quyết định định dạng).
     */
    fun importStream(displayName: String, open: () -> InputStream?): Pair<JSONObject, Boolean> {
        val name = displayName.substringAfterLast('/').substringAfterLast('\\').ifEmpty { "nhạc" }
        val extension = name.substringAfterLast('.', "").lowercase()
        if (extension !in EXTENSIONS) {
            throw ImportError("“$name”: chưa nhập được định dạng này - dùng ${EXTENSIONS.joinToString(", ") { ".$it" }}.")
        }
        val folder = File(root, "files").apply { mkdirs() }
        folder.listFiles { entry -> entry.name.startsWith(TEMPORARY) }?.forEach { it.delete() } // dư của lần nhập bị ngắt
        val part = File(folder, "$TEMPORARY${System.nanoTime()}.$extension")
        try {
            val digest = MessageDigest.getInstance("SHA-1")
            var size = 0L
            try {
                val input = open() ?: throw ImportError("“$name”: không đọc được file này.")
                input.use { source ->
                    part.outputStream().use { sink ->
                        val buffer = ByteArray(1 shl 16)
                        while (true) {
                            val read = source.read(buffer)
                            if (read < 0) break
                            size += read
                            if (size > MAX_TRACK_BYTES) throw ImportError("“$name”: file quá lớn để làm nhạc nền (tối đa 1 GB).")
                            digest.update(buffer, 0, read)
                            sink.write(buffer, 0, read)
                        }
                    }
                }
            } catch (error: IOException) {
                throw ImportError("“$name”: không chép được vào kho nhạc (${error.message ?: error.javaClass.simpleName}).")
            }
            val sha = digest.digest().joinToString("") { "%02x".format(it) }
            synchronized(lock) { duplicate(sha)?.let { return it to true } }
            // Đọc thẻ, đo độ to, phân tích: việc lâu, làm ngoài khoá để màn danh sách vẫn mở được trong lúc nhập.
            val found = try {
                tags.read(part)
            } catch (error: ImportError) {
                throw ImportError("“$name”: ${error.message}.")
            }
            val lufs = runCatching { loudness?.measure(part) }.getOrNull()
            val analysis = analyze(part)
            synchronized(lock) {
                duplicate(sha)?.let { return it to true }
                val target = File(folder, "$sha.$extension")
                if (!part.renameTo(target)) {
                    target.delete()
                    if (!part.renameTo(target)) throw ImportError("“$name”: không chép được vào kho nhạc.")
                }
                val entry = JSONObject().put("ext", extension).put("name", name).put("bytes", target.length()).put("added", clock())
                    .put("duration", Math.round(found.duration * 100) / 100.0).put("title", (found.title ?: "").take(TAG_MAX))
                    .put("artist", (found.artist ?: "").take(TAG_MAX)).put("album", (found.album ?: "").take(TAG_MAX))
                    .put("genre", (found.genre ?: "").take(TAG_MAX)).put("analysis", analysis ?: JSONObject.NULL)
                    .put("lufs", lufs ?: JSONObject.NULL)
                tracks()[sha] = entry
                save()
                return info(sha, entry) to false
            }
        } finally {
            part.delete()
        }
    }

    /** Thông tin của bài đã có trong kho với mã `sha` (kèm file còn trên đĩa), hay null. Gọi trong khoá. */
    private fun duplicate(sha: String): JSONObject? = tracks()[sha]?.takeIf { path(sha, it).isFile }?.let { info(sha, it) }

    /** Xoá một bài khỏi kho (file + sổ). Sách đã lưu / đã ghim bài này vẫn giữ bản của nó (file nằm trong sách). */
    fun remove(digest: String): Boolean = synchronized(lock) {
        val entry = tracks().remove(digest) ?: return false
        save()
        path(digest, entry).delete()
        true
    }

    /** Phân tích các bài chưa phân tích (khi bộ phân tích có mặt hay vừa cập nhật). Trả số bài vừa được phân tích. */
    fun analyzePending(): Int = synchronized(lock) {
        var done = 0
        for ((digest, entry) in tracks()) {
            val file = path(digest, entry)
            if (entry.optJSONObject("analysis") != null || !file.isFile) continue
            analyze(file)?.let {
                entry.put("analysis", it)
                done++
            }
        }
        if (done > 0) save()
        done
    }

    /** Kết quả đã làm sạch của bộ phân tích cho `file`, hay null khi chưa có bộ phân tích hoặc nó không cho ra gì dùng được. */
    private fun analyze(file: File): JSONObject? {
        val run = analyzer ?: return null
        return try {
            cleanAnalysis(run(file))
        } catch (_: Exception) {
            null // model lỗi thì bài chưa phân tích, không làm hỏng việc nhập
        }
    }

    companion object {
        const val LOCAL_PREFIX = "local:" // link của bài người dùng nhập: `local:<sha1 của file>` - không ai khác tải được
        val EXTENSIONS = listOf("mp3", "m4a", "ogg", "opus", "flac", "wav") // music_plan.TRACK_EXTENSIONS
        const val INDEX_FILE = "library.json"
        const val INDEX_VERSION = 1
        const val MAX_TRACK_BYTES = 1L shl 30 // 1 GiB: một bản nhạc dài hơn thế không phải nhạc nền
        private const val TAG_MAX = 200
        private const val TEMPORARY = ".nhap-"
        private val SHA1 = Regex("[0-9a-f]{40}")
        private val FAMILIES = setOf("eastern", "orchestral", "piano", "ambient", "acoustic", "electronic", "other") // music_plan.FAMILIES
        private val EMOTIONS = listOf("peacefulness", "tenderness", "nostalgia", "sadness", "joy", "playful", "power", "wonder", "tension",
            "fear", "anger", "mystery", "moved") // music_scenes.EMOTION_CLASSES
        const val NO_ANALYZER = "Chưa có bộ phân tích âm thanh - bài nhập vào vẫn ghim tay được, nhưng máy chưa tự chọn chúng."

        /** Mã sha1 (40 hex) của file trong link `local:<sha1>`; link khác dạng -> null. */
        fun localHash(link: String): String? = link.removePrefix(LOCAL_PREFIX).takeIf { link.startsWith(LOCAL_PREFIX) && SHA1.matches(it) }

        private fun finite(value: Any?): Double? = (value as? Number)?.toDouble()?.takeIf { it.isFinite() }

        /**
         * Kết quả của bộ phân tích -> khoá của một bài danh mục (như `music_local.clean_analysis`): valence / arousal (bắt buộc, kẹp
         * -1..1), tension, sd, emotions (13 cường độ 0..1), confidence, `fitsUnderNarration` -> `background`, `loudness` (số LUFS hay
         * {lufs, speechBand}) -> lufs / speechBand, family / style nếu có. Thiếu valence hoặc arousal -> null (không điền số nào thay
         * bộ phân tích).
         */
        fun cleanAnalysis(result: Any?): JSONObject? {
            if (result !is JSONObject) return null
            val valence = finite(result.opt("valence")) ?: return null
            val arousal = finite(result.opt("arousal")) ?: return null
            val out = JSONObject().put("valence", valence.coerceIn(-1.0, 1.0)).put("arousal", arousal.coerceIn(-1.0, 1.0))
            finite(result.opt("tension"))?.let { out.put("tension", it) }
            (result.opt("sd") as? JSONObject)?.let { sd ->
                val kept = JSONObject()
                for (axis in sd.keys().asSequence().toList()) finite(sd.opt(axis))?.let { kept.put(axis, maxOf(0.0, it)) }
                if (kept.length() > 0) out.put("sd", kept)
            }
            (result.opt("emotions") as? JSONObject)?.let { emotions ->
                val kept = JSONObject()
                for (name in EMOTIONS) finite(emotions.opt(name))?.let { kept.put(name, it.coerceIn(0.0, 1.0)) }
                if (kept.length() > 0) out.put("emotions", kept)
            }
            for ((source, target) in listOf("confidence" to "confidence", "fitsUnderNarration" to "background")) {
                finite(result.opt(source))?.let { out.put(target, it.coerceIn(0.0, 1.0)) }
            }
            val loud = result.opt("loudness")
            val lufs = finite(if (loud is JSONObject) loud.opt("lufs") else loud)
            val band = finite(if (loud is JSONObject) loud.opt("speechBand") else result.opt("speechBand"))
            if (lufs != null) out.put("lufs", lufs)
            if (band != null) out.put("speechBand", band)
            for (key in listOf("family", "style")) (result.opt(key) as? String)?.takeIf { it.isNotEmpty() }?.let { out.put(key, it) }
            if (out.has("family") && out.getString("family") !in FAMILIES) out.remove("family")
            return out
        }
    }
}
