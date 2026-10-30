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

    /** 409 / 423: máy tính đang bận việc khác hay trạng thái đã đổi - làm mới rồi thử lại. `body`: thân JSON của lời đáp (mã `reason`...). */
    class Busy(message: String, val body: String = "") : StudioError(message)

    /** Lỗi khác của máy chủ; `status` 0 = lời đáp không đọc được. `body`: thân JSON của lời đáp (`reason`, `suggestion`...). */
    class Server(message: String, val status: Int, val body: String = "") : StudioError(message)
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
            status == 409 || status == 423 -> StudioError.Busy(serverMessage(status, body), body)
            else -> StudioError.Server(serverMessage(status, body), status, body)
        }
    }

    /** Một khoá chữ trong thân lỗi (`reason`, `suggestion`): "" khi không có. Lỗi nào mang thân thì đọc được, loại khác thì "". */
    fun detail(error: StudioError, key: String): String {
        val body = when (error) {
            is StudioError.Server -> error.body
            is StudioError.Busy -> error.body
            else -> ""
        }
        return runCatching { JSONObject(body).optString(key) }.getOrDefault("")
    }

    /** `busyBook` của thân lỗi (máy đã nói cuốn nào đang chặn): true khi có. */
    fun named(error: StudioError): Boolean {
        val body = when (error) {
            is StudioError.Server -> error.body
            is StudioError.Busy -> error.body
            else -> ""
        }
        return runCatching { JSONObject(body).has("busyBook") }.getOrDefault(false)
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

    /** Các đường GHI của một sách mà Studio gọi (đúng tên `remote_studio.ALLOWED`); khoá lạ bị từ chối trước khi gửi. */
    val WRITES = setOf(
        "speaker", "line", "narrator-section", "voice", "voice/preview", "pronunciation", "pronunciation/preview", "pronunciation/check", "review", "pending-changes/withdraw",
        "characters/rename", "shared-readings", "music/rebuild", "music/download/cancel", "music/moods",
    )

    /** Các đường GHI bằng PUT (đúng tên `remote_studio.ALLOWED`): nhạc nền, "Chờ tôi duyệt", bỏ dòng ghi công khỏi phần đọc. */
    val PUTS = setOf("music", "precast", "skip")

    fun put(id: String, endpoint: String): String {
        require(endpoint in PUTS) { "Đường không hợp lệ" }
        return book(id) + "/" + endpoint
    }

    /** Danh sách "Cách cuốn này đọc từng tên" (`GET /pronunciations`). */
    fun pronunciations(id: String): String = book(id) + "/pronunciations"

    /** Một chữ chạm tới bao nhiêu câu (`GET /pronunciations/reach`). */
    fun reach(id: String, surface: String): String = book(id) + "/pronunciations/reach?surface=${enc(surface)}"

    /** Cách đọc chung cho mọi sách. */
    const val READINGS = "/api/readings"

    /** Cách đọc chung có tên trong cuốn này mà cuốn đang đọc khác. */
    fun sharedReadings(id: String): String = book(id) + "/shared-readings"

    /** Dòng ghi công / xin ủng hộ máy gợi ý bỏ khỏi phần đọc. */
    fun suggestions(id: String): String = book(id) + "/suggestions"

    fun precast(id: String): String = book(id) + "/precast"

    fun music(id: String): String = book(id) + "/music"
    fun musicAlternatives(id: String, scene: String): String = book(id) + "/music/scenes/${enc(scene)}/alternatives"
    const val MOODS_MODEL = "/api/music/moods-model"

    /** Nghe thử một bài trong danh mục (`link` đã mã hoá). */
    fun musicTrack(link: String): String = "/api/music/track?link=${enc(link)}"

    /** Mục lục "Kịch bản" của cuốn, và kịch bản một chương. */
    fun casting(id: String): String = book(id) + "/casting"
    fun castingChapter(id: String, chapter: Int): String = book(id) + "/casting/$chapter"

    fun write(id: String, endpoint: String): String {
        require(endpoint in WRITES) { "Đường không hợp lệ" }
        return book(id) + "/" + endpoint
    }

    fun work(id: String): String = book(id) + "/work"

    /** Trang kế của ví dụ một thẻ nhóm lớn (`GET /work/examples`). */
    fun workExamples(id: String, key: String, offset: Int, limit: Int): String =
        book(id) + "/work/examples?key=${enc(key)}&offset=$offset&limit=$limit"

    /** `filter` todo | done; `all` = cả câu nhẹ; `cursor` rỗng = trang đầu (`GET /review`). */
    fun review(id: String, filter: String, all: Boolean, cursor: String): String =
        book(id) + "/review?filter=${enc(filter)}" + (if (all) "&all=1" else "") + (if (cursor.isNotEmpty()) "&cursor=${enc(cursor)}" else "")

    fun cast(id: String): String = book(id) + "/cast"
    fun voices(id: String, character: String): String = book(id) + "/voices?character=${enc(character)}"

    /** Bản thu riêng của một câu. */
    fun sample(id: String, segmentId: Int): String = "/media/books/${checked(id)}/samples/$segmentId"

    /** File chương đã ghép (một câu nằm trong đó ở [start, end] giây). */
    fun chapterAudio(id: String, chapterId: Int): String = "/media/books/${checked(id)}/chapters/$chapterId"

    /** Câu mẫu chung của một giọng. */
    fun voiceSample(key: String): String = "/media/voices/${enc(key)}"

    /** Đường `/media/...` an toàn để tải: không `..`, không truy vấn, không ký tự lạ (đường do máy tính gửi về cũng qua đây). */
    fun safeMedia(path: String): Boolean = path.contains("..").not() && (path.startsWith("/media/") && MEDIA.matches(path) || TRACK.matches(path))

    private val TRACK = Regex("/api/music/track[?]link=[A-Za-z0-9%_.~-]+")

    private val MEDIA = Regex("/media/[A-Za-z0-9/_.%-]+")

    /** encodeURIComponent của web: khoảng trắng là %20, không phải +. */
    private fun enc(text: String): String = java.net.URLEncoder.encode(text, "UTF-8").replace("+", "%20")

    private fun checked(id: String): String {
        require(valid(id)) { "Mã sách không hợp lệ" }
        return id
    }
}
