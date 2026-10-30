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
class StudioApi(private val transport: Transport, private val slow: Transport) {
    constructor(transport: Transport) : this(transport, transport)

    constructor(context: Context, computer: String) : this(
        Transport { method, path, body -> real(context, computer, method, path, body, 20_000) },
        // Nghe thử giọng / cách đọc: máy tính nạp giọng rồi đọc, giữ kết nối tới ~120 giây (docs mục 1.2).
        Transport { method, path, body -> real(context, computer, method, path, body, SLOW_READ_MS) },
    )

    /** Một yêu cầu đã xong: trả nguyên văn lời đáp JSON (đối tượng hay mảng), hay ném lỗi của [SyncLink.request]. */
    fun interface Transport {
        fun call(method: String, path: String, body: JSONObject?): String
    }

    suspend fun getObject(path: String): JSONObject = call("GET", path, null) as? JSONObject ?: throw malformed()

    suspend fun getArray(path: String): JSONArray = call("GET", path, null) as? JSONArray ?: throw malformed()

    suspend fun post(path: String, body: JSONObject? = null): JSONObject = call("POST", path, body) as? JSONObject ?: throw malformed()

    /** Như [post] cho việc máy tính làm lâu (nghe thử bằng giọng thật): chờ lời đáp tới ~130 giây. */
    suspend fun postSlow(path: String, body: JSONObject? = null): JSONObject = call("POST", path, body, slow) as? JSONObject ?: throw malformed()

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
        const val SLOW_READ_MS = 130_000

        /** Máy tính `computer` lúc này (đường nối có thể đổi giữa các lần gọi); đã bỏ ghép thì 401 như máy kia bỏ ghép mình. */
        fun real(context: Context, computer: String, method: String, path: String, body: JSONObject?, readTimeoutMs: Int): String {
            val link = StudioLink.link(context, computer) ?: throw StudioError.Unauthorized()
            return SyncLink.request(context, method, path, body, auth = false, root = link.base, token = link.token, readTimeoutMs = readTimeoutMs, connectTimeoutMs = 3000)
        }
    }
}
