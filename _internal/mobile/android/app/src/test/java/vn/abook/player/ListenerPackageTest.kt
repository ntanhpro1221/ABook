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
    fun `sealing the shipped Hello book on the phone is refused, not stripped`() {
        val hello = JSONObject(File("../../../tests/fixtures/book_files/hello_published_book.json").readText()).getJSONObject("book")
        try {
            BookDocumentWriter.seal(hello, mapOf("chapters/00002_001.mp3" to ByteArray(4)), emptyMap(), JSONObject(), BookVolumes.TREE_VERSION, ByteArrayOutputStream())
            fail("gói có tên phụ \"Cần nghe lại\" phải bị từ chối")
        } catch (refused: BookDocumentWriter.Refused) {
            assertTrue(refused.message!!, refused.message!!.contains("Cần nghe lại"))
        }
        for (chapter in (0 until hello.getJSONArray("chapters").length()).map { hello.getJSONArray("chapters").getJSONObject(it) }) chapter.put("subtitle", "")
        try {
            BookDocumentWriter.seal(hello, mapOf("chapters/00002_001.mp3" to ByteArray(4)), emptyMap(), JSONObject(), BookVolumes.TREE_VERSION, ByteArrayOutputStream())
            fail("trạng thái QA trong book.json phải bị từ chối")
        } catch (refused: BookDocumentWriter.Refused) {
            assertTrue(refused.message!!, refused.message!!.contains("QA / nội bộ") && refused.message!!.contains("chapters["))
        }
    }
}
