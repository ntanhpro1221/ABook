package vn.abook.player.ui.studio

import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ImageBitmap
import kotlinx.coroutines.CancellationException
import org.json.JSONObject
import vn.abook.player.StudioErrors
import vn.abook.player.readaloud.WebSocket
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.GlobeIcon
import vn.abook.player.ui.components.ImageIcon
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.MenuRow
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.components.TrashIcon
import vn.abook.player.ui.data.CoverRef
import vn.abook.player.ui.editbook.BookEditor
import vn.abook.player.ui.editbook.CoverCropRoute
import vn.abook.player.ui.editbook.CoverResults
import vn.abook.player.ui.editbook.CoverSearchRoute
import vn.abook.player.ui.editbook.CoverThumbnails
import vn.abook.player.ui.editbook.EditDiff
import vn.abook.player.ui.editbook.EditSnapshot
import vn.abook.player.ui.editbook.EditSource
import vn.abook.player.ui.editbook.FoundCover
import vn.abook.player.ui.theme.Dim

// Bìa của dự án trên máy tính (NATIVE_REMOTE_STUDIO.md §6.13): DÙNG LẠI màn tìm và màn cắt bìa của Sửa sách (CoverSearchRoute, CoverCropRoute) qua [BookEditor]; chỉ nguồn khác
// - [StudioCoverSource] gọi `GET .../cover/search`, `PUT .../cover {url | image}`, `DELETE .../cover` của máy tính. Không có màn bìa mới ngoài một trang chọn ba việc.

internal object StudioCoverJson {
    fun results(json: JSONObject, query: String) = CoverResults(
        json.text("query").ifEmpty { query },
        json.optJSONArray("results").objects().map { FoundCover(it.text("provider"), it.text("title"), it.text("author"), it.text("thumb"), it.text("url")) },
        json.optJSONArray("failed").strings(),
    )

    /** Ảnh đã cắt thành data URL cho `PUT /cover {image}` (máy tính nhận PNG, JPEG, WebP, GIF, BMP). */
    fun dataUrl(jpeg: ByteArray): String = "data:image/jpeg;base64," + WebSocket.base64(jpeg)
}

/**
 * Nguồn của [BookEditor] cho bìa của dự án trên máy tính. Chỉ bìa: tên sách và tên chương sửa ở máy tính hay trang dự án nên `save` / `revertChapter` / `send` không làm gì.
 * Bìa đổi thì phiên bản trong trang sách đổi - [CoverRef.stamp] theo đó, màn tìm bìa nhận ra "bìa vừa đổi" như với sách trên điện thoại.
 */
class StudioCoverSource(private val session: StudioSession) : EditSource {
    private suspend fun snapshot(id: String): EditSnapshot = guard {
        val book = session.source.book(session.computer, id).book
        EditSnapshot(id, book.title, cover = book.cover?.let { CoverRef("studio:$id", it.hashCode().toLong()) }, textOnly = false, holder = session.name)
    }

    /** Lỗi của máy tính thành câu cho người nghe (BookEditor hiện `message` của ngoại lệ). */
    private suspend fun <T> guard(block: suspend () -> T): T = try {
        block()
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (error: Throwable) {
        val failure = StudioErrors.of(error)
        session.note(failure)
        throw IllegalStateException(StudioText.failure(failure), error)
    }

    override suspend fun load(id: String) = snapshot(id)

    override suspend fun save(id: String, diff: EditDiff) = snapshot(id)

    override suspend fun cover(id: String, image: ByteArray?): EditSnapshot {
        guard {
            if (image == null) session.source.delete(session.computer, id, "cover")
            else session.source.put(session.computer, id, "cover", JSONObject().put("image", StudioCoverJson.dataUrl(image)))
        }
        return snapshot(id)
    }

    override suspend fun revertChapter(id: String, chapterId: Long) = snapshot(id)

    override suspend fun send(id: String) = snapshot(id)

    override suspend fun findCovers(id: String, query: String): CoverResults = guard { session.source.coverSearch(session.computer, id, query) }

    override suspend fun coverFromUrl(id: String, url: String): EditSnapshot {
        guard { session.source.put(session.computer, id, "cover", JSONObject().put("url", url)) }
        return snapshot(id)
    }

    override suspend fun thumbnail(url: String): ImageBitmap? = CoverThumbnails.load(url)
}

object StudioCoverText {
    const val TITLE = "Ảnh bìa"
    const val HAS = "Sách đã có ảnh bìa."
    const val NONE = "Sách chưa có ảnh bìa: dùng bìa vẽ từ tên."
    const val LEAD = "Ảnh bìa nằm ở máy tính và đi theo file xuất."
    const val PICK = "Chọn ảnh"
    const val FIND = "Tìm bìa"
    const val REMOVE = "Bỏ ảnh bìa"
}

private sealed class CoverStage(val index: Int) {
    data object Hub : CoverStage(0)
    data object Search : CoverStage(1)
    data class Crop(val uri: String) : CoverStage(2)
}

/** Trang bìa của một dự án: chọn ảnh trên máy, tìm bìa trên mạng, hay bỏ ảnh. Tìm và cắt là màn của Sửa sách, trượt vào rồi quay lại trang này. */
@Composable
fun StudioCoverRoute(editor: BookEditor, title: String, onBack: () -> Unit, active: Boolean = true) {
    var stage by remember { mutableStateOf<CoverStage>(CoverStage.Hub) }
    BackHandler(enabled = active && stage != CoverStage.Hub) { stage = CoverStage.Hub }
    SheetPages(stage, { it.index }, "studio_cover_pages") { shown ->
        when (shown) {
            CoverStage.Hub -> CoverHub(editor, onBack, { stage = CoverStage.Search }, { stage = CoverStage.Crop(it) })
            CoverStage.Search -> CoverSearchRoute(editor, title, { stage = CoverStage.Hub }, { stage = CoverStage.Crop(it) }, active)
            is CoverStage.Crop -> CoverCropRoute(editor, shown.uri, { stage = CoverStage.Hub })
        }
    }
}

@Composable
private fun CoverHub(editor: BookEditor, onBack: () -> Unit, find: () -> Unit, crop: (String) -> Unit) {
    val state by editor.state.collectAsState()
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let { crop(it.toString()) } }
    val has = state.saved?.cover != null
    BookForm(StudioCoverText.TITLE, onBack, "studio_cover") {
        RowHint(StudioCoverText.LEAD, Modifier.padding(top = Dim.s4))
        Column(Modifier.fillMaxWidth().padding(top = Dim.s8)) {
            RowHint(if (state.loading) "" else if (has) StudioCoverText.HAS else StudioCoverText.NONE, Modifier.padding(bottom = Dim.s8))
            MenuRow(StudioCoverText.PICK, "studio_cover_pick", onClick = { picker.launch(arrayOf("image/*")) }) { ink -> ImageIcon(ink) }
            MenuRow(StudioCoverText.FIND, "studio_cover_find", onClick = find) { ink -> GlobeIcon(ink) }
            if (has) MenuRow(StudioCoverText.REMOVE, "studio_cover_remove", danger = true, onClick = { editor.setCover(null) }) { ink -> TrashIcon(ink) }
            InlineProblem(state.problem, editor::retry, "studio_cover_problem")
        }
    }
}
