package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Callable
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject

/**
 * "Tìm bìa trên mạng" trên điện thoại - bản cài của abook/webui/cover_search.py (iTunes Search, Open Library, Google Books; không
 * khoá). Hai bản đọc cùng bộ ví dụ tests/fixtures/cover_search/ (CoverSearchTest): cùng địa chỉ hỏi, cùng kết quả, cùng chỗ nào
 * một nguồn hỏng thì ghi tên vào `failed` mà không làm hỏng các nguồn khác.
 *
 * An toàn như bản Python: chỉ tải ảnh từ đúng tên miền ảnh của ba nguồn, qua HTTPS ([allowedImageUrl]) - giao diện gửi lên một địa
 * chỉ, nếu cho tải địa chỉ bất kỳ thì trang nào lừa được người dùng cũng khiến điện thoại gọi vào mạng trong nhà. Chặt hơn bản Python
 * ở hai chỗ: địa chỉ có "user@", ký tự trắng/gạch ngược hay cổng không phải số bị từ chối (hai bộ đọc địa chỉ khác nhau về chúng là
 * kẽ hở), và mỗi lần nhảy (redirect) phải vẫn là HTTPS (Open Library chuyển ảnh sang archive.org nên không ràng tên miền ở bước nhảy).
 * Ảnh tải về qua đúng cổng của ảnh người dùng chọn: tối đa [Covers.MAX_UPLOAD_BYTES], rồi [CoverCodec] chuẩn hoá.
 */
object CoverSearch {
    /** Lấy nội dung một địa chỉ; hỏng (mất mạng, mã lỗi) thì ném [IOException]. Test JVM thay bằng bản giả. */
    interface Http {
        fun getText(url: String): String
        fun getBytes(url: String, limit: Int, timeoutSeconds: Int): ByteArray
    }

    @Volatile
    var http: Http = UrlConnectionHttp

    const val TIMEOUT_SECONDS = 8
    const val REFUSAL = "Chỉ lấy ảnh từ iTunes, Open Library hoặc Google Books"
    private const val USER_AGENT = "ABook/1 (cover search)"
    private const val QUERY_MAX = 120
    private const val RESULTS_MAX = 30
    private const val JSON_MAX_BYTES = 4 * 1024 * 1024
    private const val MAX_REDIRECTS = 5
    private val ALLOWED_HOST = Regex("""is\d+-ssl\.mzstatic\.com|covers\.openlibrary\.org|books\.google\.com|books\.googleusercontent\.com""")

    private class Provider(val name: String, val find: (String) -> List<JSONObject>)

    /** Thứ tự và tên như `PROVIDERS` của Python (`provider.__name__.strip("_")`): kết quả nối theo thứ tự này. */
    private val PROVIDERS = listOf(Provider("itunes", ::itunes), Provider("open_library", ::openLibrary), Provider("google_books", ::googleBooks))

    // ---- tìm ---------------------------------------------------------------------------------------------------------

    /** `cover_search.search`: {query, results (tối đa 30, mỗi địa chỉ ảnh một lần), failed}. Tên ngắn dưới 2 ký tự: không hỏi ai. */
    fun search(rawQuery: String): JSONObject {
        val query = BookEdits.cut(pySplit(rawQuery).joinToString(" "), QUERY_MAX)
        if (query.codePointCount(0, query.length) < 2) {
            return JSONObject().put("query", query).put("results", JSONArray()).put("failed", JSONArray())
        }
        val pool = Executors.newFixedThreadPool(PROVIDERS.size)
        val found = ArrayList<JSONObject>()
        val failed = ArrayList<String>()
        try {
            val futures = PROVIDERS.map { provider -> provider to pool.submit(Callable { provider.find(query) }) }
            for ((provider, future) in futures) {
                try {
                    found += future.get((TIMEOUT_SECONDS + 2).toLong(), TimeUnit.SECONDS)
                } catch (error: Exception) { // một nguồn hỏng không được làm hỏng các nguồn khác
                    future.cancel(true)
                    failed += provider.name
                }
            }
        } finally {
            pool.shutdownNow()
        }
        val seen = HashSet<String>()
        val unique = JSONArray()
        for (item in found) {
            val url = item.getString("url")
            if (!seen.add(url) || !allowedImageUrl(url)) continue
            unique.put(item)
            if (unique.length() == RESULTS_MAX) break
        }
        return JSONObject().put("query", query).put("results", unique).put("failed", JSONArray(failed))
    }

    private fun itunes(query: String): List<JSONObject> {
        val found = ArrayList<JSONObject>()
        for (media in listOf("audiobook", "ebook")) {
            val data = getJson("https://itunes.apple.com/search?" + urlencode("term" to query, "media" to media, "limit" to "8"))
            for (item in objects(data, "results")) {
                val art = BookEdits.pyText(item.opt("artworkUrl100"))
                if (art.isEmpty()) continue
                found += entry("iTunes", firstTruthy(item.opt("collectionName"), item.opt("trackName")), BookEdits.pyText(item.opt("artistName")),
                    art, // ảnh iTunes đổi cỡ theo tên file: 100x100bb -> 1000x1000bb là cùng ảnh, nét hơn
                    Regex("""/\d+x\d+bb\.""").replace(art, "/1000x1000bb."))
            }
        }
        return found
    }

    private fun openLibrary(query: String): List<JSONObject> {
        val data = getJson("https://openlibrary.org/search.json?" + urlencode("q" to query, "limit" to "10", "fields" to "title,author_name,cover_i"))
        val found = ArrayList<JSONObject>()
        for (doc in objects(data, "docs")) {
            val coverId = doc.opt("cover_i")
            if (!BookEdits.truthy(coverId)) continue
            val authors = doc.opt("author_name").let { list -> if (list is JSONArray) (0 until list.length()).map { list.get(it) as String } else emptyList() }
            found += entry("Open Library", firstTruthy(doc.opt("title")), BookEdits.cut(authors.joinToString(", "), 80),
                "https://covers.openlibrary.org/b/id/${BookEdits.pyStr(coverId)}-M.jpg", "https://covers.openlibrary.org/b/id/${BookEdits.pyStr(coverId)}-L.jpg")
        }
        return found
    }

    private fun googleBooks(query: String): List<JSONObject> {
        val data = getJson("https://www.googleapis.com/books/v1/volumes?" + urlencode("q" to query, "maxResults" to "10", "printType" to "books"))
        val found = ArrayList<JSONObject>()
        for (item in objects(data, "items")) {
            val info = item.optJSONObject("volumeInfo") ?: JSONObject()
            val links = info.optJSONObject("imageLinks") ?: JSONObject()
            val thumb = BookEdits.pyText(firstTruthy(links.opt("thumbnail"), links.opt("smallThumbnail"))).replace("http://", "https://")
            if (thumb.isEmpty()) continue
            val authors = info.opt("authors").let { list -> if (list is JSONArray) (0 until list.length()).map { list.get(it) as String } else emptyList() }
            found += entry("Google Books", firstTruthy(info.opt("title")), BookEdits.cut(authors.joinToString(", "), 80), thumb,
                // zoom=0 xin ảnh lớn nhất Google có cho cuốn ấy (có khi vẫn nhỏ)
                Regex("""([?&])zoom=\d""").replace(thumb, "$1zoom=0").replace("&edge=curl", ""))
        }
        return found
    }

    private fun entry(provider: String, title: Any, author: String, thumb: String, url: String): JSONObject =
        JSONObject().put("provider", provider).put("title", title).put("author", author).put("thumb", thumb).put("url", url)

    /** `a or b or ""` của Python: giá trị đầu tiên "có nghĩa", không có thì chuỗi rỗng. */
    private fun firstTruthy(vararg values: Any?): Any = values.firstOrNull { BookEdits.truthy(it) } ?: ""

    /** `data.get(key, [])` rồi duyệt từng phần tử như một đối tượng - sai hình thì ném lỗi (nguồn ấy vào `failed`, như bản Python). */
    private fun objects(data: JSONObject, key: String): List<JSONObject> {
        if (!data.has(key)) return emptyList()
        val list = data.get(key) as JSONArray
        return (0 until list.length()).map { list.get(it) as JSONObject }
    }

    private fun getJson(url: String): JSONObject = StrictJson.parse(http.getText(url)) as JSONObject

    // ---- chữ ---------------------------------------------------------------------------------------------------------

    private fun isSpace(char: Char) = Character.isWhitespace(char) || Character.isSpaceChar(char) || char == '\u0085'

    /** `str.split()` của Python: tách theo mọi khoảng trắng, bỏ phần rỗng. */
    private fun pySplit(text: String): List<String> {
        val words = ArrayList<String>()
        val word = StringBuilder()
        for (char in text) {
            if (isSpace(char)) {
                if (word.isNotEmpty()) words += word.toString()
                word.setLength(0)
            } else {
                word.append(char)
            }
        }
        if (word.isNotEmpty()) words += word.toString()
        return words
    }

    /** `urllib.parse.urlencode` (quote_plus): chữ-số và `_.-~` giữ nguyên, dấu cách thành `+`, còn lại %XX theo UTF-8. */
    internal fun urlencode(vararg pairs: Pair<String, String>): String = pairs.joinToString("&") { (key, value) -> quotePlus(key) + "=" + quotePlus(value) }

    private fun quotePlus(text: String): String {
        val out = StringBuilder()
        for (byte in text.toByteArray(Charsets.UTF_8)) {
            val code = byte.toInt() and 0xff
            val char = code.toChar()
            when {
                char in 'A'..'Z' || char in 'a'..'z' || char in '0'..'9' || char == '_' || char == '.' || char == '-' || char == '~' -> out.append(char)
                char == ' ' -> out.append('+')
                else -> out.append('%').append("0123456789ABCDEF"[code shr 4]).append("0123456789ABCDEF"[code and 15])
            }
        }
        return out.toString()
    }

    // ---- ảnh ---------------------------------------------------------------------------------------------------------

    /** `cover_search.allowed_image_url` (chặt hơn một chút, xem đầu file): HTTPS và đúng tên miền ảnh của ba nguồn. */
    fun allowedImageUrl(url: String): Boolean {
        if (url.any { it <= ' ' || it == '\u007f' || it == '\\' }) return false
        val colon = url.indexOf(':')
        if (colon < 0 || !url.substring(0, colon).equals("https", ignoreCase = true) || !url.startsWith("//", colon + 1)) return false
        val netloc = url.substring(colon + 3).takeWhile { it != '/' && it != '?' && it != '#' }
        if ('@' in netloc || '[' in netloc) return false
        val host = netloc.substringBefore(':')
        val port = netloc.substringAfter(':', "")
        if (port.isNotEmpty() && !port.all { it in '0'..'9' }) return false
        if (!ALLOWED_HOST.matches(host.lowercase())) return false
        // Bộ đọc địa chỉ của HttpURLConnection phải thấy đúng tên miền ấy.
        return try {
            URL(url).host.equals(host, ignoreCase = true)
        } catch (error: IOException) {
            false
        }
    }

    /** `cover_search.download_image`: byte của ảnh; địa chỉ lạ, quá lớn hay không tải được thì [CoverCodec.CoverError] với câu của máy tính. */
    fun downloadImage(url: String): ByteArray {
        if (!allowedImageUrl(url)) throw CoverCodec.CoverError(REFUSAL)
        val data = try {
            http.getBytes(url, Covers.MAX_UPLOAD_BYTES + 1, TIMEOUT_SECONDS * 2)
        } catch (error: IOException) {
            throw CoverCodec.CoverError("Không tải được ảnh: ${error.message}")
        }
        if (data.size > Covers.MAX_UPLOAD_BYTES) throw CoverCodec.CoverError("Ảnh quá lớn")
        return data
    }

    // ---- mạng thật ---------------------------------------------------------------------------------------------------

    private object UrlConnectionHttp : Http {
        override fun getText(url: String): String = String(fetch(url, JSON_MAX_BYTES, TIMEOUT_SECONDS), Charsets.UTF_8)

        override fun getBytes(url: String, limit: Int, timeoutSeconds: Int): ByteArray = fetch(url, limit, timeoutSeconds)

        private fun fetch(first: String, limit: Int, timeoutSeconds: Int): ByteArray {
            var url = first
            repeat(MAX_REDIRECTS + 1) {
                val connection = URL(url).openConnection() as HttpURLConnection
                try {
                    connection.instanceFollowRedirects = false
                    connection.connectTimeout = timeoutSeconds * 1000
                    connection.readTimeout = timeoutSeconds * 1000
                    connection.setRequestProperty("User-Agent", USER_AGENT)
                    val code = connection.responseCode
                    if (code in listOf(301, 302, 303, 307, 308)) {
                        val next = connection.getHeaderField("Location") ?: throw IOException("HTTP $code không có nơi chuyển tới")
                        url = URL(URL(url), next).toString()
                        if (!url.startsWith("https://", ignoreCase = true)) throw IOException("bị chuyển sang địa chỉ không an toàn")
                        return@repeat
                    }
                    if (code >= 400) throw IOException("HTTP $code")
                    return connection.inputStream.use { readUpTo(it, limit) }
                } finally {
                    connection.disconnect()
                }
            }
            throw IOException("chuyển hướng quá nhiều lần")
        }

        /** `response.read(limit)`: đọc tối đa `limit` byte (đủ để thấy ảnh vượt trần mà không nạp cả file khổng lồ). */
        private fun readUpTo(input: InputStream, limit: Int): ByteArray {
            val out = ByteArrayOutputStream()
            val buffer = ByteArray(16 * 1024)
            while (out.size() < limit) {
                val read = input.read(buffer, 0, minOf(buffer.size, limit - out.size()))
                if (read < 0) break
                out.write(buffer, 0, read)
            }
            return out.toByteArray()
        }
    }
}
