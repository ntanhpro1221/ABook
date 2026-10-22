package vn.abook.player

import java.io.File
import java.security.MessageDigest
import org.json.JSONArray
import org.json.JSONObject

/** Dấu byte audio: cùng cỡ không có nghĩa là cùng bản thu. */
object AudioRevision {
    private fun timestamp(value: String): java.math.BigDecimal? = runCatching {
        val match = Regex("""(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?(Z|[+-]\d\d:\d\d)""").matchEntire(value) ?: return@runCatching null
        // java.time cần API 26; app hỗ trợ Android 24. Giữ phần lẻ riêng để không mất dấu microsecond của máy tính.
        val parser = java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", java.util.Locale.ROOT).apply { isLenient = false }
        val date = parser.parse(match.groupValues[1] + match.groupValues[3]) ?: return@runCatching null
        val fraction = match.groupValues[2].ifEmpty { "0" }
        java.math.BigDecimal(date.time).add(java.math.BigDecimal("0.$fraction").movePointRight(3)).stripTrailingZeros()
    }.getOrNull()

    fun importState(local: JSONObject, incoming: JSONObject, localAt: String, incomingAt: String): String {
        fun entries(items: JSONObject): Map<String, Int> {
            return items.keys().asSequence().map { name ->
                val meta = items.opt(name)
                name.substringAfterLast('/') + ":" + if (meta is JSONObject) "${meta.optLong("size", -1)}:${meta.optString("sha256")}" else meta.toString()
            }.groupingBy { it }.eachCount()
        }
        val own = entries(local)
        val next = entries(incoming)
        val preserves = own.all { (key, count) -> (next[key] ?: 0) >= count }
        if (own == next) return "existing"
        if (incoming.length() < local.length()) return "older"
        val before = timestamp(localAt)
        val after = timestamp(incomingAt)
        if (before == null || after == null) return if (preserves) "updated" else "conflict"
        if (before == after && incoming.length() > local.length() && preserves) return "updated"
        return if (before == after) "conflict" else if (after < before) "older" else "updated"
    }

    fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val block = ByteArray(1024 * 1024)
            while (true) {
                val count = input.read(block)
                if (count < 0) break
                digest.update(block, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    /** Đúng cỡ và đúng mã băm? File của sách trong thư viện được nhớ mã băm theo (cỡ, mtime) (Store.audioSha256): không đọc lại cả file mỗi lần kiểm. */
    fun matches(file: File, size: Long, digest: String): Boolean =
        file.isFile && (size <= 0 || file.length() == size) && (digest.isEmpty() || Store.audioSha256(file) == digest)

    fun expected(book: JSONObject, relative: String): String {
        val chapters = book.optJSONArray("chapters") ?: JSONArray()
        for (index in 0 until chapters.length()) {
            val chapter = chapters.getJSONObject(index)
            if (chapter.optString("file") == relative) return chapter.getString("sha256")
        }
        return ""
    }

    fun chapterPrints(folder: File, book: JSONObject): JSONObject {
        val chapters = book.optJSONArray("chapters") ?: JSONArray()
        val audio = (0 until chapters.length()).map { chapters.getJSONObject(it) }
            .filter { it.optBoolean("available") && it.optString("file").isNotEmpty() }.map { it.getString("file") }
        val names = if (audio.isNotEmpty()) audio else (0 until chapters.length()).mapNotNull { chapters.getJSONObject(it).optString("text").takeIf { it.isNotEmpty() } }
        val files = names.distinct().map { it to Store.contained(folder, it) }.filter { it.second.isFile }
        val digests = Store.audioSha256s(files.map { it.second })
        return JSONObject().apply {
            files.forEachIndexed { index, (name, file) -> put(name, JSONObject().put("size", file.length()).put("sha256", digests[index])) }
        }
    }

    fun version(chapters: JSONArray): String {
        val values = JSONArray()
        for (index in 0 until chapters.length()) {
            val chapter = chapters.getJSONObject(index)
            values.put(JSONArray().put(chapter.getInt("id")).put(chapter.optString("sha256")))
        }
        return MessageDigest.getInstance("SHA-256").digest(values.toString().toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }
    }
}
