package vn.abook.player.ui.studio

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.StudioApi
import vn.abook.player.StudioError
import vn.abook.player.StudioLink
import vn.abook.player.StudioPaths
import vn.abook.player.ui.editbook.CoverResults
import java.io.InputStream

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

    /** Gửi một bước ghi bằng PUT (khoá trong [StudioPaths.PUTS]): nhạc nền, "Chờ tôi duyệt", bỏ dòng ghi công. `slow`: đổi thể loại nhạc máy làm lâu. */
    suspend fun put(computer: String, id: String, endpoint: String, body: JSONObject, slow: Boolean = false): JSONObject

    /** Cách đọc tên của cuốn (`GET /pronunciations`). */
    suspend fun readings(computer: String, id: String): NameReadings

    /** Một tên chạm tới bao nhiêu câu (`GET /pronunciations/reach`). */
    suspend fun reach(computer: String, id: String, surface: String): Reach

    /** Cách đọc tên dùng chung giữa các sách của máy (`GET /api/readings`). */
    suspend fun sharedReadings(computer: String): List<SharedReading>

    /** Cách đọc dùng chung máy đề nghị cho cuốn này (`GET /shared-readings`). */
    suspend fun sharedOffer(computer: String, id: String): List<SharedReading>

    /** Dòng ghi công máy gợi ý bỏ khỏi phần đọc (`GET /suggestions`). */
    suspend fun credits(computer: String, id: String): List<CreditGroup>

    /** Màn "Duyệt trước khi thu" (`GET /precast`). */
    suspend fun precast(computer: String, id: String): PrecastView

    /** Nhạc nền của cuốn (`GET /music`). */
    suspend fun music(computer: String, id: String): MusicView

    /** Model đọc không khí (`GET /api/music/moods-model`). */
    suspend fun moodsModel(computer: String): MoodsModel

    /** Bài khác cho một cảnh (`GET /music/scenes/<key>/alternatives`). */
    suspend fun alternatives(computer: String, id: String, scene: String): List<MusicAlternative>

    /** Mục lục kịch bản (`GET /casting`). */
    suspend fun castingContents(computer: String, id: String): ScriptContents

    /** Kịch bản một chương (`GET /casting/<chapterId>`). */
    suspend fun castingChapter(computer: String, id: String, chapter: Int): ChapterScript

    // ---- S4: xuất / bìa / nhật ký / sách mới ----

    /** Việc xuất gần nhất của kiểu `kind` (`GET .../<kiểu>-job`). */
    suspend fun exportJob(computer: String, id: String, kind: StudioExportKind): StudioExportJob

    /** Bắt đầu một lượt xuất (`POST .../<kiểu>-job`); trả trạng thái việc. */
    suspend fun exportStart(computer: String, id: String, kind: StudioExportKind, body: JSONObject): StudioExportJob

    /** Huỷ lượt xuất đang chạy (`POST .../<kiểu>-job/cancel`). */
    suspend fun exportCancel(computer: String, id: String, kind: StudioExportKind): StudioExportJob

    /** Cỡ file sách, nhạc nền kèm được không, ffmpeg và các lần xuất trước. Phần nào hỏi hụt thì để mặc định. */
    suspend fun exportOptions(computer: String, id: String): StudioExportOptions

    /** Nhật ký của sách (`GET .../activity[?technical=1]`, một mảng). */
    suspend fun activity(computer: String, id: String, technical: Boolean): List<StudioLogItem>

    /** "Tìm bìa" theo tên (`GET .../cover/search?q=`). */
    suspend fun coverSearch(computer: String, id: String, query: String): CoverResults

    /** Gửi một bước XOÁ (khoá trong [StudioPaths.DELETES]): bỏ ảnh bìa. */
    suspend fun delete(computer: String, id: String, endpoint: String): JSONObject

    /** Gửi một file nguồn lên thư mục tải lên của máy tính (`POST /api/sources/upload`); `input` mở luồng đọc khi bắt đầu gửi. */
    suspend fun uploadSource(computer: String, folder: String, name: String, input: () -> InputStream): UploadedSource

    /** Tách file gộp nhiều chương thành thư mục chương (`POST /api/sources/split`); trả thư mục. */
    suspend fun splitSource(computer: String, path: String, title: String): String

    /** Máy tính đọc các nguồn đã gửi ra chương (`POST /api/scan`). */
    suspend fun scan(computer: String, paths: List<String>): ScanView

    /** Truyện kể ngôi thứ nhất không (`POST /api/first-person`). */
    suspend fun firstPerson(computer: String, paths: List<String>): FirstPersonView

    /** Các bộ phân tích truyện máy tính có (`GET /api/analysis-models`). */
    suspend fun analysisModels(computer: String): AnalysisModels

    /** Tạo sách (`POST /api/books`). */
    suspend fun createBook(computer: String, body: JSONObject): CreatedBook
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

    override suspend fun put(computer: String, id: String, endpoint: String, body: JSONObject, slow: Boolean): JSONObject {
        val client = api(computer)
        val path = StudioPaths.put(id, endpoint)
        return if (slow) client.putSlow(path, body) else client.put(path, body)
    }

    override suspend fun readings(computer: String, id: String): NameReadings = parsed { StudioReadingsJson.readings(api(computer).getObject(StudioPaths.pronunciations(id))) }

    override suspend fun reach(computer: String, id: String, surface: String): Reach = parsed { StudioReadingsJson.reach(api(computer).getObject(StudioPaths.reach(id, surface))) }

    override suspend fun sharedReadings(computer: String): List<SharedReading> = parsed { StudioReadingsJson.shared(api(computer).getObject(StudioPaths.READINGS)) }

    override suspend fun sharedOffer(computer: String, id: String): List<SharedReading> = parsed { StudioReadingsJson.shared(api(computer).getObject(StudioPaths.sharedReadings(id))) }

    override suspend fun credits(computer: String, id: String): List<CreditGroup> = parsed { StudioReadingsJson.credits(api(computer).getObject(StudioPaths.suggestions(id))) }

    override suspend fun precast(computer: String, id: String): PrecastView = parsed { StudioPrecastJson.view(api(computer).getObject(StudioPaths.precast(id))) }

    override suspend fun music(computer: String, id: String): MusicView = parsed { StudioMusicJson.view(api(computer).getObject(StudioPaths.music(id))) }

    override suspend fun moodsModel(computer: String): MoodsModel = parsed { StudioMusicJson.moods(api(computer).getObject(StudioPaths.MOODS_MODEL)) }

    override suspend fun alternatives(computer: String, id: String, scene: String): List<MusicAlternative> =
        parsed { StudioMusicJson.alternatives(api(computer).getObject(StudioPaths.musicAlternatives(id, scene))) }

    override suspend fun castingContents(computer: String, id: String): ScriptContents = parsed { StudioScriptJson.contents(api(computer).getObject(StudioPaths.casting(id))) }

    override suspend fun castingChapter(computer: String, id: String, chapter: Int): ChapterScript =
        parsed { StudioScriptJson.chapter(api(computer).getObject(StudioPaths.castingChapter(id, chapter))) }

    override suspend fun exportJob(computer: String, id: String, kind: StudioExportKind): StudioExportJob =
        parsed { StudioExportJson.job(api(computer).getObject(StudioPaths.exportJob(id, kind.job))) }

    override suspend fun exportStart(computer: String, id: String, kind: StudioExportKind, body: JSONObject): StudioExportJob =
        parsed { StudioExportJson.job(api(computer).post(StudioPaths.write(id, kind.job), body)) }

    override suspend fun exportCancel(computer: String, id: String, kind: StudioExportKind): StudioExportJob =
        parsed { StudioExportJson.job(api(computer).post(StudioPaths.write(id, kind.job + "/cancel"), JSONObject())) }

    override suspend fun exportOptions(computer: String, id: String): StudioExportOptions = parsed {
        val client = api(computer)
        // Mỗi phần chỉ để nói thêm: máy tính cũ không có đường ấy (404) hay hỏng thì để mặc định, không chặn hộp Xuất. Mất mạng, chỉ nghe, bỏ ghép thì vẫn là lỗi.
        StudioExportJson.options(
            optional { client.getObject(StudioPaths.exportSize(id)) },
            optional { client.getObject(StudioPaths.exportMusic(id)) },
            optional { client.getObject(StudioPaths.FFMPEG) },
            optional { client.getArray(StudioPaths.exportHistory(id)).objects() },
        )
    }

    override suspend fun activity(computer: String, id: String, technical: Boolean): List<StudioLogItem> =
        parsed { StudioActivityJson.items(api(computer).getArray(StudioPaths.activity(id, technical))) }

    override suspend fun coverSearch(computer: String, id: String, query: String): CoverResults =
        parsed { StudioCoverJson.results(api(computer).getObject(StudioPaths.coverSearch(id, query)), query) }

    override suspend fun delete(computer: String, id: String, endpoint: String): JSONObject = api(computer).delete(StudioPaths.delete(id, endpoint))

    override suspend fun uploadSource(computer: String, folder: String, name: String, input: () -> InputStream): UploadedSource =
        parsed { StudioNewJson.uploaded(api(computer).postStream(StudioPaths.SOURCE_UPLOAD, StudioUpload.writer(folder, name, input()))) }

    override suspend fun splitSource(computer: String, path: String, title: String): String =
        parsed { StudioNewJson.folder(api(computer).postSlow(StudioPaths.SOURCE_SPLIT, JSONObject().put("path", path).put("title", title))) }

    override suspend fun scan(computer: String, paths: List<String>): ScanView =
        parsed { StudioNewJson.scan(api(computer).postSlow(StudioPaths.SCAN, JSONObject().put("paths", JSONArray(paths)))) }

    override suspend fun firstPerson(computer: String, paths: List<String>): FirstPersonView =
        parsed { StudioNewJson.firstPerson(api(computer).postSlow(StudioPaths.FIRST_PERSON, JSONObject().put("paths", JSONArray(paths)))) }

    override suspend fun analysisModels(computer: String): AnalysisModels = parsed { StudioNewJson.models(api(computer).getObject(StudioPaths.ANALYSIS_MODELS)) }

    override suspend fun createBook(computer: String, body: JSONObject): CreatedBook = parsed { StudioNewJson.created(api(computer).postSlow(StudioPaths.CREATE_BOOK, body)) }

    /** Một phần phụ của lời đáp: lỗi của máy (404, 409, 5xx) thì null; mất mạng / chỉ nghe / bỏ ghép / ghim đổi vẫn ném lên. */
    private suspend fun <T> optional(block: suspend () -> T): T? = try {
        block()
    } catch (error: StudioError) {
        when (error) {
            is StudioError.Server, is StudioError.Gone, is StudioError.Busy -> null
            else -> throw error
        }
    }

    /** Lời đáp thiếu trường bắt buộc (mã sách...) là lời đáp hỏng: nói như mọi lời đáp hỏng khác, không để JSONException văng lên màn. */
    private suspend fun <T> parsed(block: suspend () -> T): T = try {
        block()
    } catch (error: org.json.JSONException) {
        throw StudioError.Server("Dữ liệu máy gửi không hợp lệ; bạn hãy thử lại.", 0)
    }
}
