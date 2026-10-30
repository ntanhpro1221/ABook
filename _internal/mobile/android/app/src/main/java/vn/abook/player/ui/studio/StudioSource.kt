package vn.abook.player.ui.studio

import android.content.Context
import org.json.JSONObject
import vn.abook.player.StudioApi
import vn.abook.player.StudioError
import vn.abook.player.StudioLink
import vn.abook.player.StudioPaths

/** Lệnh của nút chính / hộp Dừng: mỗi lệnh một đường `POST /api/books/<id>/...` của Studio từ xa (`remote_studio.ALLOWED`). */
sealed interface StudioCommand {
    data object Start : StudioCommand

    /** `paused` = true: tạm dừng, false: làm tiếp. */
    data class Pause(val paused: Boolean) : StudioCommand
    data object Stop : StudioCommand

    /** Chỉ bỏ khỏi hàng chờ - không bao giờ dừng một cuốn đã được trao lượt (dừng giữa phân tích là đổi cả quyển sách). */
    data object Dequeue : StudioCommand
}

/**
 * Nguồn dữ liệu Studio của một máy tính (mã máy `computer`, "" = máy tính chính): màn và [StudioHomeState] / [StudioProjectState] chỉ biết giao diện này;
 * bản thật là [StudioRepo], bản thử là một lớp giả. Mọi hàm ném [StudioError].
 */
interface StudioSource {
    /** Tên máy như bạn thấy ở Cài đặt › Thiết bị. */
    fun name(computer: String): String

    suspend fun library(computer: String): List<StudioBook>

    suspend fun book(computer: String, id: String): StudioPage

    /** Làm lệnh; trả bản mới của sách (máy tính trả lại nó). */
    suspend fun command(computer: String, id: String, command: StudioCommand): StudioBook

    /** Máy tính khác phiên bản điện thoại (`/api/app`): không hỏi được = không biết = false. */
    suspend fun mismatched(computer: String): Boolean

    /** Việc cần duyệt (`GET /work`). */
    suspend fun work(computer: String, id: String): WorkView

    /** Trang kế câu ví dụ của một thẻ nhóm lớn (`GET /work/examples`). */
    suspend fun workExamples(computer: String, id: String, key: String, offset: Int, limit: Int): WorkExamplesPage

    /** Câu cần nghe lại (`GET /review`): `filter` todo | done; `all` = cả câu nhẹ; `cursor` rỗng = trang đầu. */
    suspend fun review(computer: String, id: String, filter: String, all: Boolean, cursor: String): ReviewPage

    suspend fun cast(computer: String, id: String): Cast

    /** Các giọng chọn được cho một nhân vật (`GET /voices`). */
    suspend fun voices(computer: String, id: String, character: String): VoiceChoices

    /** Gửi một bước ghi (khoá trong [StudioPaths.WRITES]); trả lời đáp JSON của máy. `slow`: việc máy tính làm lâu (nghe thử bằng giọng thật). */
    suspend fun write(computer: String, id: String, step: WorkStep, slow: Boolean = false): JSONObject
}

/** Bản thật: [StudioApi] trên đường ghim vân tay của [vn.abook.player.SyncLink]. `api` đổi được để thử không cần ghép máy. */
class StudioRepo(
    private val context: Context,
    private val api: (String) -> StudioApi = { StudioApi(context, it) },
    private val ours: () -> String = { runCatching { context.packageManager.getPackageInfo(context.packageName, 0).versionName }.getOrNull().orEmpty() },
) : StudioSource {
    override fun name(computer: String): String = StudioLink.name(context, computer)

    override suspend fun library(computer: String): List<StudioBook> = parsed { StudioJson.library(api(computer).getObject(StudioPaths.LIBRARY)) }

    override suspend fun book(computer: String, id: String): StudioPage = parsed { StudioJson.page(api(computer).getObject(StudioPaths.book(id))) }

    override suspend fun command(computer: String, id: String, command: StudioCommand): StudioBook = parsed {
        val client = api(computer)
        StudioJson.book(
            when (command) {
                StudioCommand.Start -> client.post(StudioPaths.start(id))
                is StudioCommand.Pause -> client.post(StudioPaths.pause(id), JSONObject().put("paused", command.paused))
                StudioCommand.Stop -> client.post(StudioPaths.stop(id))
                StudioCommand.Dequeue -> client.post(StudioPaths.dequeue(id))
            },
        )
    }

    override suspend fun mismatched(computer: String): Boolean = try {
        StudioLink.mismatched(api(computer).getObject(StudioPaths.APP).optString("version"), ours())
    } catch (error: StudioError) {
        false
    }

    override suspend fun work(computer: String, id: String): WorkView = parsed { StudioWorkJson.view(api(computer).getObject(StudioPaths.work(id))) }

    override suspend fun workExamples(computer: String, id: String, key: String, offset: Int, limit: Int): WorkExamplesPage =
        parsed { StudioWorkJson.examples(api(computer).getObject(StudioPaths.workExamples(id, key, offset, limit))) }

    override suspend fun review(computer: String, id: String, filter: String, all: Boolean, cursor: String): ReviewPage =
        parsed { StudioReviewJson.page(api(computer).getObject(StudioPaths.review(id, filter, all, cursor))) }

    override suspend fun cast(computer: String, id: String): Cast = parsed { StudioCastJson.cast(api(computer).getObject(StudioPaths.cast(id))) }

    override suspend fun voices(computer: String, id: String, character: String): VoiceChoices =
        parsed { StudioCastJson.voices(api(computer).getObject(StudioPaths.voices(id, character))) }

    override suspend fun write(computer: String, id: String, step: WorkStep, slow: Boolean): JSONObject {
        val client = api(computer)
        val path = StudioPaths.write(id, step.endpoint)
        return if (slow) client.postSlow(path, step.body) else client.post(path, step.body)
    }

    /** Lời đáp thiếu trường bắt buộc (mã sách...) là lời đáp hỏng: nói như mọi lời đáp hỏng khác, không để JSONException văng lên màn. */
    private suspend fun <T> parsed(block: suspend () -> T): T = try {
        block()
    } catch (error: org.json.JSONException) {
        throw StudioError.Server("Dữ liệu máy gửi không hợp lệ; bạn hãy thử lại.", 0)
    }
}
