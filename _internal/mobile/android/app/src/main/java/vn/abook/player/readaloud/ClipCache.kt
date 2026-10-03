package vn.abook.player.readaloud

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest

/**
 * Bộ nhớ đệm các đoạn đã đọc, trong thư mục cache của app (`readaloud/`): mỗi đoạn hai file `<khoá>.<mp3|wav>` + `<khoá>.json` (độ dài, mốc từng chữ), khoá =
 * sha256(nhà cung cấp | giọng | chữ) - cùng chữ cùng giọng thì nghe lại không đọc lại, đổi giọng thì đoạn mới. Quá `capBytes` (300 MB) thì xoá đoạn lâu không
 * dùng nhất trước (LRU theo giờ sửa file, mỗi lần dùng được cập nhật). Android tự dọn thư mục cache khi máy đầy, nên mất đoạn nào cũng chỉ là đọc lại.
 *
 * Đoạn "Làm trước" ([PrepareAhead]) được GHIM (danh sách khoá trong `pinFile`, ngoài thư mục đệm): khi dọn, đoạn không ghim đi trước hết, đoạn ghim chỉ đi khi
 * chỉ còn chúng - nghe trực tiếp không đẩy được đoạn đã làm trước ra trước khi người nghe tới. Nghe tới đoạn nào thì bỏ ghim đoạn ấy ([unpin]); phần dành cho đoạn
 * ghim có trần ([PreparePlan.SHARE]) nên chúng không chiếm hết chỗ.
 */
class ClipCache(
    private val dir: File,
    private val capBytes: Long = CAP_BYTES,
    private val pinFile: File? = null,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    companion object {
        const val CAP_BYTES = 300L * 1024 * 1024
        private val EXTENSIONS = setOf("mp3", "wav")

        fun key(provider: String, voice: String, text: String): String =
            MessageDigest.getInstance("SHA-256").digest("$provider|$voice|$text".toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }

        /** "edge:vi-VN-X" -> ("edge", "vi-VN-X"). */
        fun split(voiceId: String): Pair<String, String> = voiceId.substringBefore(':') to voiceId.substringAfter(':', "")
    }

    init { dir.mkdirs() }

    val cap: Long get() = capBytes

    private val pinned: MutableSet<String> = pinFile?.takeIf { it.isFile }
        ?.let { file -> runCatching { file.readLines().map { it.trim() }.filter { it.isNotEmpty() } }.getOrNull() }
        ?.toMutableSet() ?: mutableSetOf()

    private fun keyOf(voiceId: String, text: String): String = split(voiceId).let { (provider, voice) -> key(provider, voice, text) }

    private fun savePins() {
        val file = pinFile ?: return
        val part = File(file.path + ".part")
        part.writeBytes(pinned.joinToString("\n").toByteArray(Charsets.UTF_8))
        file.delete()
        part.renameTo(file)
    }

    /** Ghim đoạn (đã có hay sắp đọc): dọn bộ đệm chỉ đụng tới nó khi không còn đoạn không ghim nào. */
    @Synchronized
    fun pin(voiceId: String, text: String) {
        if (pinned.add(keyOf(voiceId, text))) savePins()
    }

    /** Người nghe đã tới đoạn này: nó lại là đoạn thường. */
    @Synchronized
    fun unpin(voiceId: String, text: String) {
        if (pinned.remove(keyOf(voiceId, text))) savePins()
    }

    @Synchronized
    fun clearPins() {
        if (pinned.isEmpty()) return
        pinned.clear()
        savePins()
    }

    @Synchronized
    fun isPinned(voiceId: String, text: String): Boolean = keyOf(voiceId, text) in pinned

    @Synchronized
    private fun pinnedKeys(): Set<String> = pinned.toSet()

    /** Byte các đoạn ghim đang chiếm. */
    fun pinnedBytes(): Long {
        val keys = pinnedKeys()
        if (keys.isEmpty()) return 0L
        return dir.listFiles()?.filter { it.isFile && !it.name.endsWith(".part") && it.name.substringBefore('.') in keys }?.sumOf { it.length() } ?: 0L
    }

    /** Đoạn đã có trong bộ đệm (không tính là một lần dùng - không đổi thứ tự dọn). */
    fun contains(voiceId: String, text: String): Boolean {
        val key = keyOf(voiceId, text)
        return File(dir, "$key.json").isFile && EXTENSIONS.any { File(dir, "$key.$it").length() > 0L }
    }

    /** File tạm cho giọng ghi vào (cùng thư mục để đổi tên không phải chép). Không tính vào bộ nhớ đệm tới khi [put]. */
    fun temp(extension: String): File = File(dir, "tmp-${java.util.UUID.randomUUID()}.$extension.part")

    fun get(voiceId: String, text: String): Clip? {
        val (provider, voice) = split(voiceId)
        val key = key(provider, voice, text)
        val meta = File(dir, "$key.json")
        if (!meta.isFile) return null
        return try {
            val json = JSONObject(meta.readText())
            val audio = File(dir, "$key.${json.getString("ext")}")
            if (!audio.isFile || audio.length() == 0L) return null
            val array = json.getJSONArray("words")
            val words = (0 until array.length()).map { array.getJSONArray(it).let { pair -> Span(pair.getLong(0), pair.getLong(1)) } }
            val now = clock()
            audio.setLastModified(now)
            meta.setLastModified(now)
            Clip(audio, json.getLong("duration"), words, voiceId)
        } catch (error: Exception) {
            null // json hỏng / thiếu file: coi như chưa có, đọc lại sẽ ghi đè
        }
    }

    /** Nhận file `tmp` (đã ghi xong) vào bộ nhớ đệm; trả đoạn trỏ tới file chính thức. */
    fun put(voiceId: String, text: String, tmp: File, extension: String, durationMs: Long, words: List<Span>): Clip {
        require(extension in EXTENSIONS) { "đuôi file lạ: $extension" }
        val (provider, voice) = split(voiceId)
        val key = key(provider, voice, text)
        val audio = File(dir, "$key.$extension")
        audio.delete()
        if (!tmp.renameTo(audio)) {
            tmp.copyTo(audio, overwrite = true)
            tmp.delete()
        }
        val array = JSONArray()
        words.forEach { array.put(JSONArray().put(it.start).put(it.end)) }
        val meta = File(dir, "$key.json")
        val part = File(dir, "$key.json.part")
        part.writeBytes(JSONObject().put("ext", extension).put("duration", durationMs).put("words", array).put("voice", voiceId).toString().toByteArray(Charsets.UTF_8))
        meta.delete()
        part.renameTo(meta)
        val now = clock()
        audio.setLastModified(now)
        meta.setLastModified(now)
        trim()
        return Clip(audio, durationMs, words, voiceId)
    }

    /** Dọn tới khi còn trong hạn mức: xoá cả cặp (âm thanh + json) của đoạn dùng lâu nhất - đoạn không ghim trước; file mồ côi và file tạm cũ xoá luôn. */
    fun trim() {
        val files = dir.listFiles()?.filter { it.isFile } ?: return
        val now = clock()
        files.filter { it.name.endsWith(".part") && now - it.lastModified() > 10 * 60_000L }.forEach { it.delete() }
        val groups = files.filter { !it.name.endsWith(".part") }.groupBy { it.name.substringBefore('.') }
        var total = groups.values.sumOf { group -> group.sumOf { it.length() } }
        if (total <= capBytes) return
        val keep = pinnedKeys()
        val order = compareBy<Map.Entry<String, List<File>>> { it.key in keep }.thenBy { (_, group) -> group.maxOf { it.lastModified() } }
        for ((_, group) in groups.entries.sortedWith(order)) {
            if (total <= capBytes) break
            total -= group.sumOf { it.length() }
            group.forEach { it.delete() }
        }
    }

    fun sizeBytes(): Long = dir.listFiles()?.filter { it.isFile }?.sumOf { it.length() } ?: 0L
}
