package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.fail

/**
 * Bộ ví dụ DÙNG CHUNG với pytest (tests/book_edits_fixtures.py, tests/fixtures/book_edits/): hai bản cài - Python
 * (webui/book_edits.py) và Kotlin (BookEdits.kt) - phải ra đúng những file này. Thư mục làm việc của Gradle là
 * mobile/android/app, nên bộ ví dụ nằm ở ../../../tests/fixtures/book_edits.
 */
object BookEditsFixtures {
    val dir: File by lazy {
        val found = File("../../../tests/fixtures/book_edits")
        if (!File(found, "base/book.json").isFile) {
            fail("Không thấy bộ ví dụ dùng chung: ${found.absoluteFile} (chạy test từ mobile/android/app; sinh lại bằng " +
                "runtime/.venv/Scripts/python.exe -m tests.book_edits_fixtures)")
        }
        found.canonicalFile
    }

    fun file(relative: String) = File(dir, relative)

    fun bytes(relative: String): ByteArray = file(relative).readBytes()

    /** JSON của một file ví dụ, đọc bằng bộ đọc chặt (kiểu như `json.loads`). */
    fun json(relative: String): Any? = StrictJson.parse(file(relative).readText(Charsets.UTF_8))

    fun obj(relative: String): JSONObject = json(relative) as JSONObject

    /** Tên các ca (không đuôi) của một thư mục con: edits/, invalid/, merge/, contract/. */
    fun cases(folder: String): List<String> =
        file(folder).listFiles { entry -> entry.isFile && entry.name.endsWith(".json") }!!.map { it.name.removeSuffix(".json") }.sorted()

    /** Bản sao của `base/` trong một thư mục tạm - một cuốn đã nhập, sẵn sàng để sửa. */
    fun copyBase(into: File): File {
        file("base").copyRecursively(into, overwrite = true)
        return into
    }

    fun tempDir(prefix: String): File = Files.createTempDirectory(prefix).toFile()

    /** Đặt thư mục thư viện của Store cho test JVM (như BookFileImportTest / StoreRekeyTest). */
    fun useStoreRoot(root: File) {
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
    }

    fun array(vararg items: Any?) = JSONArray(items.toList())
}
