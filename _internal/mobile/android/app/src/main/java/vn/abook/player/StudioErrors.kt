package vn.abook.player

import org.json.JSONObject
import java.io.IOException
import kotlin.coroutines.cancellation.CancellationException

/**
 * Lỗi của Studio từ xa theo LOẠI (thiết kế NATIVE_REMOTE_STUDIO.md §3.3): màn chọn nhịp hỏi và thẻ báo theo loại, không đoán từ chữ.
 * Lời cho người nghe nằm ở MỘT chỗ: ui/studio/StudioText.failure. `message` chỉ mang lời máy chủ ([Server], [Busy]) khi có.
 */
sealed class StudioError(message: String? = null, cause: Throwable? = null) : Exception(message, cause) {
    /** Không tới được máy tính (tắt, mạng rớt, quá hạn). */
    class Offline(cause: Throwable? = null) : StudioError(null, cause)

    /** 403 `listenOnly`: công tắc điều khiển sản xuất của máy tính hay quyền của điện thoại này đang tắt. */
    class ListenOnly : StudioError()

    /** 404: sách (hay trang) không còn - hỏi tiếp cũng vô ích. */
    class Gone : StudioError()

    /** 401: máy tính đã bỏ ghép điện thoại này, hay điện thoại không còn ghép với máy ấy. */
    class Unauthorized : StudioError()

    /** Chứng chỉ của máy tính đã đổi (vân tay không khớp ghim): không gọi tiếp. */
    class PinChanged(cause: Throwable? = null) : StudioError(null, cause)

    /** 413: gói gửi lên quá lớn. */
    class TooBig : StudioError()

    /** 409 / 423: máy tính đang bận việc khác hay trạng thái đã đổi - làm mới rồi thử lại. */
    class Busy(message: String) : StudioError(message)

    /** Lỗi khác của máy chủ; `status` 0 = lời đáp không đọc được. */
    class Server(message: String, val status: Int) : StudioError(message)
}

/** Phân loại lỗi - phần thuần (không Context), cùng lời với `ui/src/studio/api.ts` (ApiError, serverMessage) và `polling.ts`. */
object StudioErrors {
    /** Lỗi không ngờ của máy chủ (500 mang nguyên văn lỗi Python): câu người dùng hiểu thay cho nguyên văn (api.ts UNEXPECTED_ERROR). */
    const val UNEXPECTED = "Máy gặp lỗi không ngờ khi làm việc này. Thử lại; nếu vẫn lỗi, mở Chi tiết để gửi cho người hỗ trợ."

    private val PYTHON_ERROR = Regex("^[A-Z][A-Za-z]*(?:Error|Exception|Interrupt|Iteration|Exit)(?::|$)")

    /** Lời máy chủ cho một lỗi HTTP: khoá `error` của thân JSON, không có thì "Lỗi <mã>" (api.ts settle + serverMessage). */
    fun serverMessage(status: Int, body: String): String {
        val raw = runCatching { JSONObject(body).optString("error") }.getOrNull()?.takeIf { it.isNotBlank() } ?: "Lỗi $status"
        return if (status >= 500 && PYTHON_ERROR.containsMatchIn(raw.trim())) UNEXPECTED else raw
    }

    /** Máy chủ trả lỗi HTTP `status` kèm thân `body`. */
    fun classify(status: Int, body: String): StudioError {
        val listenOnly = status == 403 && runCatching { JSONObject(body).opt("listenOnly") == true }.getOrDefault(false)
        return when {
            listenOnly -> StudioError.ListenOnly()
            status == 401 -> StudioError.Unauthorized()
            status == 404 -> StudioError.Gone()
            status == 413 -> StudioError.TooBig()
            status == 409 || status == 423 -> StudioError.Busy(serverMessage(status, body))
            else -> StudioError.Server(serverMessage(status, body), status)
        }
    }

    /** Ngoại lệ của [SyncLink.request] thành lỗi Studio. Huỷ coroutine đi qua nguyên vẹn. */
    fun of(error: Throwable): StudioError = when {
        error is StudioError -> error
        error is CancellationException -> throw error
        error is NetErrors.Refused -> classify(error.code, error.body)
        error is Pin.ChangedException -> StudioError.PinChanged(error)
        Pin.isCertificateProblem(error) -> StudioError.PinChanged(error)
        NetErrors.kind(error) != null || error is IOException -> StudioError.Offline(error)
        else -> StudioError.Server(error.message.orEmpty().ifBlank { StudioErrors.UNEXPECTED }, 0)
    }
}

/**
 * Đường `/api/...` của Studio. Mã sách đi vào đường dẫn nên phải đúng `[A-Za-z0-9_-]+` (như [StudioLink.bookPath]): mã lạ bị từ chối
 * trước khi gửi, không bao giờ ghép nguyên vào đường dẫn.
 */
object StudioPaths {
    private val ID = Regex("[A-Za-z0-9_-]+")

    fun valid(id: String): Boolean = ID.matches(id)

    const val LIBRARY = "/api/library"
    const val APP = "/api/app"

    fun book(id: String): String = "/api/books/${checked(id)}"
    fun start(id: String): String = book(id) + "/start"
    fun stop(id: String): String = book(id) + "/stop"
    fun pause(id: String): String = book(id) + "/pause"
    fun dequeue(id: String): String = book(id) + "/dequeue"

    private fun checked(id: String): String {
        require(valid(id)) { "Mã sách không hợp lệ" }
        return id
    }
}
