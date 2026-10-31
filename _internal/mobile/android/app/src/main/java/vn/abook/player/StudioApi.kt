package vn.abook.player

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

/**
 * Máy khách API `/api` của Studio từ xa: một máy tính đã ghép (`computer`: mã máy, "" = máy tính chính). Đi qua [SyncLink.request]
 * nên có sẵn HTTPS + ghim vân tay + `Authorization: Bearer` của ĐÚNG máy ấy - không có HTTP client thứ hai (NATIVE_REMOTE_STUDIO.md §3).
 * Mọi hàm chạy ở luồng IO, huỷ được tại điểm treo, và chỉ ném [StudioError].
 *
 * `transport` là đường gửi thật; test thay bằng bản giả (không cần ghép máy).
 */
class StudioApi(private val transport: Transport, private val slow: Transport, private val uploader: Uploader = Uploader { _, _ -> throw IllegalStateException("Chưa gửi được tệp") }) {
    constructor(transport: Transport) : this(transport, transport)

    /** Hạn chờ theo đường (net/HostWait.kt): việc máy tính trả lời sau khi làm xong (`HostWait.LONG_WORK`: nghe thử giọng / cách đọc, quét, tách nguồn, kể ngôi, tạo sách, dựng lại nhạc) im tới 100 giây, mọi việc khác 30 giây - nên không còn đường "chậm" riêng. */
    constructor(context: Context, computer: String) : this(
        Transport { method, path, body -> real(context, computer, method, path, body) },
        Transport { method, path, body -> real(context, computer, method, path, body) },
        Uploader { path, write -> upload(context, computer, path, write) },
    )

    /** Một yêu cầu đã xong: trả nguyên văn lời đáp JSON (đối tượng hay mảng), hay ném lỗi của [SyncLink.request]. */
    fun interface Transport {
        fun call(method: String, path: String, body: JSONObject?): String
    }

    /** Gửi một thân JSON dài ghi thẳng ra kết nối (nguồn sách): máy tính từ chối vì quá lớn thì [StudioError.TooBig]. */
    fun interface Uploader {
        fun call(path: String, write: (java.io.OutputStream) -> Unit): String
    }

    suspend fun getObject(path: String): JSONObject = call("GET", path, null) as? JSONObject ?: throw malformed()

    suspend fun getArray(path: String): JSONArray = call("GET", path, null) as? JSONArray ?: throw malformed()

    suspend fun post(path: String, body: JSONObject? = null): JSONObject = call("POST", path, body) as? JSONObject ?: throw malformed()

    suspend fun put(path: String, body: JSONObject? = null): JSONObject = call("PUT", path, body) as? JSONObject ?: throw malformed()

    /** Như [post] cho việc máy tính làm lâu (nghe thử bằng giọng thật); hạn chờ do đường quyết định ([HostWait.idleMs]). */
    suspend fun postSlow(path: String, body: JSONObject? = null): JSONObject = call("POST", path, body, slow) as? JSONObject ?: throw malformed()

    /** Như [put]: đổi thể loại / dựng lại nhạc nền máy tính làm ~30 giây. */
    suspend fun putSlow(path: String, body: JSONObject? = null): JSONObject = call("PUT", path, body, slow) as? JSONObject ?: throw malformed()

    suspend fun delete(path: String): JSONObject = call("DELETE", path, null) as? JSONObject ?: throw malformed()

    /** `POST` với thân do `write` ghi ra từng khúc; không khúc nào ghi được trong 30 giây (hay lời đáp im 30 giây) thì báo hết hạn, không gửi lại. */
    suspend fun postStream(path: String, write: (java.io.OutputStream) -> Unit): JSONObject = withContext(Dispatchers.IO) {
        val text = try {
            uploader.call(path, write)
        } catch (error: Throwable) {
            throw StudioErrors.of(error)
        }
        try {
            if (text.isBlank()) JSONObject() else StrictJson.parse(text)
        } catch (error: Exception) {
            null
        } as? JSONObject ?: throw malformed()
    }

    private suspend fun call(method: String, path: String, body: JSONObject?, via: Transport = transport): Any = withContext(Dispatchers.IO) {
        val text = try {
            via.call(method, path, body)
        } catch (error: Throwable) {
            throw StudioErrors.of(error)
        }
        try {
            if (text.isBlank()) JSONObject() else StrictJson.parse(text)
        } catch (error: Exception) {
            null
        } ?: throw malformed()
    }

    private fun malformed() = StudioError.Server("Dữ liệu máy gửi không hợp lệ; bạn hãy thử lại.", 0)

    private companion object {
        /** Máy tính `computer` lúc này (đường nối có thể đổi giữa các lần gọi); đã bỏ ghép thì 401 như máy kia bỏ ghép mình. */
        fun real(context: Context, computer: String, method: String, path: String, body: JSONObject?): String {
            val link = StudioLink.link(context, computer) ?: throw StudioError.Unauthorized()
            return SyncLink.request(context, method, path, body, auth = false, root = link.base, token = link.token, connectTimeoutMs = 3000)
        }

        fun upload(context: Context, computer: String, path: String, write: (java.io.OutputStream) -> Unit): String {
            val link = StudioLink.link(context, computer) ?: throw StudioError.Unauthorized()
            return SyncLink.request(context, "POST", path, null, auth = false, root = link.base, token = link.token, connectTimeoutMs = 3000, stream = write)
        }
    }
}
