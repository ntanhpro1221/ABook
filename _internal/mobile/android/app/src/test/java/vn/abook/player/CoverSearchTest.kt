package vn.abook.player

import java.io.File
import java.io.IOException
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/**
 * CoverSearch (điện thoại) phải ra đúng những gì cover_search.py ra: bộ ví dụ tests/fixtures/cover_search/cases.json do bản Python
 * chạy với lời đáp đóng khuôn của ba nguồn (tests/cover_search_fixtures.py). Mạng ở đây là bản giả trả đúng những lời đáp ấy.
 */
class CoverSearchTest {
    private val cases: JSONObject by lazy {
        val file = File("../../../tests/fixtures/cover_search/cases.json")
        if (!file.isFile) fail("Không thấy bộ ví dụ: ${file.absoluteFile} (chạy test từ mobile/android/app)")
        StrictJson.parse(file.readText(Charsets.UTF_8)) as JSONObject
    }

    @After
    fun tearDown() {
        CoverSearch.http = ForbiddenHttp
    }

    private object ForbiddenHttp : CoverSearch.Http {
        override fun getText(url: String): String = throw AssertionError("test không được ra mạng thật: $url")
        override fun getBytes(url: String, limit: Int, timeoutSeconds: Int): ByteArray = throw AssertionError("test không được ra mạng thật: $url")
    }

    /** Mạng giả: trả lời đóng khuôn theo địa chỉ, ghi lại địa chỉ đã hỏi; địa chỉ lạ hay lời đáp `$error` là lỗi mạng. */
    private class CannedHttp(private val responses: JSONObject) : CoverSearch.Http {
        val asked = java.util.Collections.synchronizedList(ArrayList<String>())

        override fun getText(url: String): String {
            asked += url
            val reply = responses.opt(url) ?: throw IOException("không có lời đáp đóng khuôn cho $url")
            if (reply is JSONObject && reply.has("\$error")) throw IOException(reply.getString("\$error"))
            return reply.toString()
        }

        override fun getBytes(url: String, limit: Int, timeoutSeconds: Int): ByteArray = throw AssertionError("tìm kiếm không tải ảnh")
    }

    private fun list(array: JSONArray) = (0 until array.length()).map { array.getString(it) }

    @Test
    fun every_shared_search_case_asks_the_same_urls_and_gets_the_same_answer_as_python() {
        val searches = cases.getJSONArray("search")
        assertTrue(searches.length() >= 8)
        for (index in 0 until searches.length()) {
            val case = searches.getJSONObject(index)
            val name = case.getString("name")
            val http = CannedHttp(case.getJSONObject("responses"))
            CoverSearch.http = http
            val answer = CoverSearch.search(case.getString("query"))
            assertEquals("$name: địa chỉ đã hỏi", list(case.getJSONArray("requested")), http.asked.sorted())
            val expected = case.getJSONObject("expected")
            if (!StrictJson.equal(expected, answer)) {
                fail("$name khác bản Python.\n--- mong đợi ---\n${StrictJson.dumps(expected)}\n--- thực tế ---\n${StrictJson.dumps(answer)}")
            }
        }
    }

    @Test
    fun the_image_host_allow_list_agrees_with_python() {
        val urls = cases.getJSONArray("allowed")
        for (index in 0 until urls.length()) {
            val item = urls.getJSONObject(index)
            assertEquals(item.getString("url"), item.getBoolean("allowed"), CoverSearch.allowedImageUrl(item.getString("url")))
        }
    }

    @Test
    fun the_phone_is_stricter_only_where_two_url_readers_could_disagree() {
        // Python cho qua "người dùng@tên miền" (lấy phần sau @); điện thoại từ chối - bộ đọc địa chỉ của hệ thống có thể hiểu khác.
        for (bad in listOf(
            "https://evil.example@covers.openlibrary.org/x.jpg", "https://covers.openlibrary.org\\@evil.example/x.jpg",
            "https://covers.openlibrary.org:x/x.jpg", "https://covers.openlibrary.org/x y.jpg", " https://covers.openlibrary.org/x.jpg",
            "https://covers.openlibrary.org\n.evil.example/x.jpg", "https://[::1]/x.jpg",
        )) assertFalse(bad, CoverSearch.allowedImageUrl(bad))
    }

    @Test
    fun a_foreign_image_url_is_refused_before_any_request_with_the_server_words() {
        CoverSearch.http = ForbiddenHttp
        val error = try {
            CoverSearch.downloadImage("http://192.168.1.1/admin.png")
            fail("phải từ chối")
            ""
        } catch (error: CoverCodec.CoverError) {
            error.message.orEmpty()
        }
        assertEquals(cases.getString("refusal"), error)
        assertEquals(CoverSearch.REFUSAL, error)
    }

    @Test
    fun a_downloaded_image_keeps_the_upload_limit_and_network_errors_are_explained() {
        fun fakeBytes(size: Int, error: IOException? = null) = object : CoverSearch.Http {
            override fun getText(url: String): String = throw AssertionError()
            override fun getBytes(url: String, limit: Int, timeoutSeconds: Int): ByteArray {
                if (error != null) throw error
                assertEquals("đọc dư một byte để thấy ảnh vượt trần", Covers.MAX_UPLOAD_BYTES + 1, limit)
                return ByteArray(minOf(size, limit)) { 7 }
            }
        }
        val url = "https://covers.openlibrary.org/b/id/42-L.jpg"
        CoverSearch.http = fakeBytes(5)
        assertEquals(5, CoverSearch.downloadImage(url).size)
        CoverSearch.http = fakeBytes(Covers.MAX_UPLOAD_BYTES)
        assertEquals(Covers.MAX_UPLOAD_BYTES, CoverSearch.downloadImage(url).size)
        CoverSearch.http = fakeBytes(Covers.MAX_UPLOAD_BYTES + 5)
        val tooBig = try {
            CoverSearch.downloadImage(url)
            ""
        } catch (error: CoverCodec.CoverError) {
            error.message.orEmpty()
        }
        assertEquals("Ảnh quá lớn", tooBig)
        CoverSearch.http = fakeBytes(0, IOException("HTTP 404"))
        val failed = try {
            CoverSearch.downloadImage(url)
            ""
        } catch (error: CoverCodec.CoverError) {
            error.message.orEmpty()
        }
        assertEquals("Không tải được ảnh: HTTP 404", failed)
    }

    @Test
    fun query_encoding_is_python_quote_plus() {
        assertEquals("a=T%E1%BA%AFt", CoverSearch.urlencode("a" to "Tắt"))
        assertEquals("q=a+b~c-d_e.f%2Ag%2Fh%3Fi%26j%3Dk%2Bl%25", CoverSearch.urlencode("q" to "a b~c-d_e.f*g/h?i&j=k+l%"))
        assertEquals("a=1&b=%F0%9F%98%80", CoverSearch.urlencode("a" to "1", "b" to "😀"))
    }
}
