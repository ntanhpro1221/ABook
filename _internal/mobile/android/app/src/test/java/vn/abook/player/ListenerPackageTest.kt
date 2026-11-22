package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.io.File

/**
 * Bộ đóng gói của điện thoại chặn đúng điều `bookfile.seal` chặn: ca chung tests/fixtures/book_files/listener_package_cases.json (Python
 * test_listener_text_never_carries_qa_marks.py đọc cùng file), cộng book.json thật của gói Hello đã phát hành (tên phụ "Cần nghe lại",
 * trạng thái QA) - [BookDocumentWriter.seal] từ chối, không lặng lẽ bỏ.
 */
class ListenerPackageTest {
    private val shared = JSONObject(File("../../../tests/fixtures/book_files/listener_package_cases.json").readText())

    /** `base` đè `patch` theo đường chấm (số là chỉ mục mảng) - như `shared_book` bên Python. */
    private fun book(case: JSONObject): JSONObject {
        val book = JSONObject(shared.getJSONObject("base").toString())
        val patch = case.optJSONObject("patch") ?: return book
        for (path in patch.keys()) {
            val steps = path.split(".")
            var target: Any = book
            for (step in steps.dropLast(1)) target = if (target is JSONArray) target.get(step.toInt()) else (target as JSONObject).get(step)
            val last = steps.last()
            if (target is JSONArray) target.put(last.toInt(), patch.get(path)) else (target as JSONObject).put(last, patch.get(path))
        }
        return book
    }

    private fun strings(array: JSONArray) = (0 until array.length()).map { array.getString(it) }.sorted()

    @Test
    fun `the phone packer finds exactly what the desktop packer finds`() {
        val cases = shared.getJSONArray("cases")
        assertTrue(cases.length() >= 10)
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val files = HashMap<String, ByteArray>()
            case.optJSONObject("scripts")?.let { scripts -> for (name in scripts.keys()) files[name] = scripts.getString(name).toByteArray() }
            case.optJSONObject("cast")?.let { files["cast.json"] = it.toString().toByteArray() }
            val (leaked, internal) = ListenerPackage.problems(book(case), files.keys) { files.getValue(it) }
            assertEquals(case.getString("name"), strings(case.getJSONArray("leaked")) to strings(case.getJSONArray("internal")), leaked.sorted() to internal.sorted())
        }
    }

    @Test
    fun `new book and project seals refuse the same shared internal marks`() {
        val cases = shared.getJSONArray("cases")
        for (index in 0 until cases.length()) for (project in listOf(false, true)) {
            val case = cases.getJSONObject(index)
            val files = hashMapOf<String, Any>("chapters/1.mp3" to ByteArray(4))
            case.optJSONObject("scripts")?.let { scripts -> for (name in scripts.keys()) files[name] = scripts.getString(name).toByteArray() }
            case.optJSONObject("cast")?.let { files["cast.json"] = it.toString().toByteArray() }
            val bad = case.getJSONArray("leaked").length() > 0 || case.getJSONArray("internal").length() > 0
            try {
                if (project) BookDocumentWriter.writeProject(File("unused"), ByteArrayOutputStream(), book(case), files, hashMapOf(), JSONObject(), BookVolumes.TREE_VERSION)
                else BookDocumentWriter.seal(book(case), files, emptyMap(), JSONObject(), BookVolumes.TREE_VERSION, ByteArrayOutputStream())
                assertTrue(case.getString("name"), !bad)
            } catch (refused: BookDocumentWriter.Refused) {
                assertTrue(case.getString("name") + " " + refused.message, bad)
                assertEquals(JSONObject(BuildConfig.LISTENER_PACKAGE_RULES).getString("refusal"), refused.message)
            }
        }
    }

    @Test
    fun `imported listening layers are cleaned by the shared rules`() {
        val cases = shared.getJSONArray("cases")
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val book = book(case)
            val files = hashMapOf<String, Any>()
            case.optJSONObject("scripts")?.let { scripts -> for (name in scripts.keys()) files[name] = scripts.getString(name).toByteArray() }
            case.optJSONObject("cast")?.let { files["cast.json"] = it.toString().toByteArray() }
            val original = files.mapValues { (it.value as ByteArray).copyOf() }
            ListenerPackage.clean(book, files, hashMapOf())
            assertEquals(case.getString("name"), emptyList<String>() to emptyList<String>(), ListenerPackage.problems(book, files.keys) { files.getValue(it) as ByteArray })
            if (case.getJSONArray("leaked").length() == 0 && case.getJSONArray("internal").length() == 0) {
                assertTrue(case.getString("name"), StrictJson.equal(book(case), book))
                for ((name, data) in original) org.junit.Assert.assertArrayEquals(case.getString("name"), data, files.getValue(name) as ByteArray)
            }
        }
    }

    @Test
    fun `sealing new data with the shipped Hello marks is refused`() {
        val hello = JSONObject(File("../../../tests/fixtures/book_files/hello_published_book.json").readText()).getJSONObject("book")
        try {
            BookDocumentWriter.seal(hello, mapOf("chapters/00002_001.mp3" to ByteArray(4)), emptyMap(), JSONObject(), BookVolumes.TREE_VERSION, ByteArrayOutputStream())
            fail("gói có tên phụ \"Cần nghe lại\" phải bị từ chối")
        } catch (refused: BookDocumentWriter.Refused) {
            assertEquals(JSONObject(BuildConfig.LISTENER_PACKAGE_RULES).getString("refusal"), refused.message)
        }
        for (chapter in (0 until hello.getJSONArray("chapters").length()).map { hello.getJSONArray("chapters").getJSONObject(it) }) chapter.put("subtitle", "")
        try {
            BookDocumentWriter.seal(hello, mapOf("chapters/00002_001.mp3" to ByteArray(4)), emptyMap(), JSONObject(), BookVolumes.TREE_VERSION, ByteArrayOutputStream())
            fail("trạng thái QA trong book.json phải bị từ chối")
        } catch (refused: BookDocumentWriter.Refused) {
            assertEquals(JSONObject(BuildConfig.LISTENER_PACKAGE_RULES).getString("refusal"), refused.message)
        }
    }

    @Test
    fun `saving does not rewrite an unreadable cast`() {
        for (text in listOf("{", "[]", "\"cast\"", """{"narrator":{"chapterVoices":3,"exceptChapters":3},"characters":3,"extras":3}""")) {
            val data = text.toByteArray()
            val files = hashMapOf<String, Any>("cast.json" to data)
            val known = hashMapOf("cast.json" to JSONObject().put("size", data.size).put("sha256", "hash"))
            ListenerPackage.clean(JSONObject(), files, known)
            org.junit.Assert.assertArrayEquals(data, files.getValue("cast.json") as ByteArray)
            assertTrue(known.containsKey("cast.json"))
        }
    }
}
