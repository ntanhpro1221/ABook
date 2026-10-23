package vn.abook.player

import org.json.JSONObject

/** Kiểm tên do peer gửi bằng chuỗi, trước khi canonical/stat hay tạo thư mục. */
internal object PeerPaths {
    private val device = Regex("(?i)(CON|PRN|AUX|NUL|CONIN[$]|CONOUT[$]|COM[0-9¹²³]|LPT[0-9¹²³])")

    fun safeRelative(name: String): Boolean = name.isNotEmpty() && name.length <= 1024 &&
        name.none { it.code < 32 || it in "\\:<>\"|?*" } && name.split('/').all {
            it !in listOf("", ".", "..") && !it.endsWith('.') && !it.endsWith(' ') && !device.matches(it.substringBefore('.').trimEnd(' '))
        }

    fun checkManifest(book: JSONObject) {
        try {
            BookFileImport.checkShape(book)
            BookEdits.scrubCoverColor(book) // manifest của máy khác: màu bìa chỉ #rrggbb
            val names = mutableListOf<String>()
            fun add(obj: JSONObject, key: String) {
                if (obj.has(key) && !obj.isNull(key) && obj.optString(key).isNotEmpty()) names += obj.getString(key)
            }
            add(book, "cast")
            book.optJSONArray("chapters")?.let { chapters ->
                for (i in 0 until chapters.length()) {
                    val chapter = chapters.getJSONObject(i)
                    for (key in listOf("file", "script", "text")) add(chapter, key)
                }
            }
            book.optJSONArray("samples")?.let { samples -> for (i in 0 until samples.length()) names += samples.getString(i) }
            book.optJSONObject("cover")?.let { add(it, "file") }
            book.optJSONObject("music")?.optJSONObject("tracks")?.keys()?.forEach { names += it }
            require(names.all(::safeRelative)) { "Đường dẫn trong sách không hợp lệ; bạn hãy kiểm tra lại máy gửi sách." }
        } catch (error: Exception) {
            throw IllegalArgumentException("Dữ liệu sách không hợp lệ; bạn hãy kiểm tra lại máy gửi sách.", error)
        }
    }
}
