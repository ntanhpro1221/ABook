package vn.abook.player.ui.studio

import kotlinx.coroutines.CancellationException
import vn.abook.player.StudioError
import vn.abook.player.StudioErrors

/** Kết quả một lần "Nghe thử" (cách đọc một tên hay một giọng bằng câu của sách): máy đọc thử rồi trả đường tới bản thu thử. */
sealed interface PreviewOutcome {
    data class Ready(val preview: VoicePreview) : PreviewOutcome

    /** 400: máy chê (cách đọc sai chính tả, giọng cần tải thêm...); `suggestion` là bản viết lại đúng nếu có. */
    data class Rejected(val message: String, val suggestion: String, val reason: String) : PreviewOutcome

    /** Máy không nghe thử được lúc này (đang làm sách, card bận, mất kết nối...): `text` là câu cho người nghe. */
    data class Refused(val text: String, val reason: String) : PreviewOutcome
}

/**
 * Gửi một bước "nghe thử" (`pronunciation/preview` hay `voice/preview`) và đọc lời đáp. Đi đường chậm (máy nạp giọng rồi đọc, tới ~2 phút). Mã `reason` của máy
 * đổi thành câu viết sẵn ([VoiceLogic.refusalText]); mọi lỗi khác thành [PreviewOutcome.Refused] - nghe thử không bao giờ ném lỗi lên màn.
 */
internal suspend fun StudioSession.preview(bookId: String, step: WorkStep): PreviewOutcome = try {
    PreviewOutcome.Ready(StudioCastJson.preview(source.write(computer, bookId, step, slow = true)))
} catch (cancelled: CancellationException) {
    throw cancelled
} catch (error: Throwable) {
    val failure = StudioErrors.of(error)
    note(failure)
    val reason = StudioErrors.detail(failure, "reason")
    if (failure is StudioError.Server && failure.status == 400 && reason != "no-line") {
        PreviewOutcome.Rejected(failure.message.orEmpty(), StudioErrors.detail(failure, "suggestion"), reason)
    } else {
        val message = StudioText.failure(failure)
        PreviewOutcome.Refused(VoiceLogic.refusalText(reason, message, StudioErrors.named(failure)), reason)
    }
}
