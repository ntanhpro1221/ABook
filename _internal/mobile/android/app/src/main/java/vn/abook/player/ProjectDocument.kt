package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap

/**
 * Phần chung của file dự án `.abookproj` (abook/webui/projectfile.py, phiên bản 3) cho bộ nhập ([BookFileImport]), bộ ghi
 * ([BookDocumentWriter]) và [LocalStudio]: luật bí danh, tên mục, và những gì một cuốn nhập từ file dự án để lại trong thư mục
 * (`project.json` NGUYÊN VĂN, `project/`, `sources/`, `views/`).
 *
 * Điện thoại không bao giờ mở `project/project.sqlite3`: nó chỉ chép `project/` và `sources/` nguyên byte để lưu lại được. Mục media
 * trùng cỡ + mã băm với mục khác là BÍ DANH (không nằm trong gói, `project.json` ghi `aliases`); phần nghe luôn là mục thật nếu có
 * (cùng luật `aliases_for` bên Python), nên giải ra thư mục sách là đủ phần nghe, còn bí danh của `project/` thì khỏi giải ra - lúc
 * lưu lại, bí danh được suy lại từ cỡ + mã băm.
 */
object ProjectDocument {
    const val MANIFEST = "project.json"
    const val FORMAT = "abookproj"
    const val VERSION = 3
    const val PRESENT = "present"
    const val PENDING = "pending"
    const val FOLDER_VIEWS = "views"
    val VIEWS = listOf("work", "casting", "names")
    val VIEW = Regex("""views/(?:work|casting|names)\.json""")
    const val MAX_VIEW_BYTES = 32L shl 20
    private val MEDIA = listOf(".mp3", ".wav", ".jpg", ".png", ".flac", ".ogg", ".opus", ".m4a", ".zip")
    private val PART = Regex("""[^\u0000-\u001f<>:"|?*\\/]+""")

    fun viewEntry(name: String) = "$FOLDER_VIEWS/$name.json"

    fun aliasable(name: String) = MEDIA.any { name.lowercase(Locale.ROOT).endsWith(it) }

    /** Tên mục của phần nghe: đúng tên mục của một file `.abook` mới nhất (kể cả lớp sửa). */
    fun listeningName(name: String) = BookFileImport.contentPattern(5).matches(name)

    /** `project/<đường dẫn>` hay `sources/<n>_<tên>` an toàn (không `..`, không ký tự cấm của Windows) - `_safe_entry` bên Python. */
    fun safeEntry(name: String): Boolean {
        val parts = name.split("/")
        return parts.size >= 2 && (parts[0] == "project" || parts[0] == "sources") &&
            parts.drop(1).all { PART.matches(it) } && parts.none { it == "." || it == ".." } && (parts[0] != "sources" || parts.size == 2)
    }

    /**
     * {bí danh: mục thật} từ cỡ + mã băm của mọi mục (`aliases_for` bên Python): mục media trùng nhau thì chỉ một mục nằm thật
     * trong gói - mục của phần nghe nếu có, không thì mục đứng đầu theo tên.
     */
    fun aliasesFor(described: Map<String, Pair<Long, String>>): Map<String, String> {
        val groups = LinkedHashMap<Pair<Long, String>, MutableList<String>>()
        for ((name, meta) in described) if (aliasable(name) && meta.first > 0) groups.getOrPut(meta) { ArrayList() }.add(name)
        val aliases = LinkedHashMap<String, String>()
        for (names in groups.values) {
            if (names.size < 2) continue
            val keeper = names.minWithOrNull(compareBy<String>({ !listeningName(it) }, { it }))!!
            for (name in names) if (name != keeper) aliases[name] = keeper
        }
        return aliases
    }

    /** Những gì `project.json` của một cuốn nhập từ file dự án cho biết (bản nguyên văn nằm trong thư mục sách). */
    class Kept(val workshop: String, val projectRoot: String, val sources: JSONArray, val missing: JSONArray, val files: JSONObject, val aliases: JSONObject)

    private val states = ConcurrentHashMap<String, Pair<Pair<Long, Long>, Kept?>>()

    /** `project.json` đã lưu trong thư mục một cuốn; None khi cuốn đến từ file `.abook` (hay file hỏng). Đệm theo lần ghi: dự án lớn liệt kê hàng chục nghìn file. */
    fun kept(bookDir: File): Kept? {
        val file = File(bookDir, MANIFEST)
        if (!file.isFile) return null
        val stamp = file.lastModified() to file.length()
        states[file.path]?.let { if (it.first == stamp) return it.second }
        val kept = runCatching {
            val json = JSONObject(file.readText())
            val workshop = json.getString("workshop")
            if (workshop != PRESENT && workshop != PENDING) null
            else Kept(workshop, json.getString("projectRoot"), json.getJSONArray("sources"), json.getJSONArray("missingSources"),
                json.getJSONObject("files"), json.getJSONObject("aliases"))
        }.getOrNull()
        states[file.path] = stamp to kept
        return kept
    }

    /** Phần `projectFile` của JSON sách cho giao diện: {workshop, views}; cuốn từ file `.abook` thì null. */
    fun info(bookDir: File): JSONObject? {
        val kept = kept(bookDir) ?: return null
        return JSONObject().put("workshop", kept.workshop).put("views", JSONArray(VIEWS.filter { File(bookDir, viewEntry(it)).isFile }))
    }

    /** Một bản chụp (`views/<tên>.json`) của cuốn, hay null khi không có / hỏng. */
    fun view(bookDir: File, name: String): Any? {
        if (name !in VIEWS) return null
        val file = File(bookDir, viewEntry(name))
        if (!file.isFile) return null
        return runCatching { StrictJson.parse(file.readText()) }.getOrNull()
    }
}
