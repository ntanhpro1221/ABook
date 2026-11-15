package vn.abook.player.ui.studio

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.KeyboardType
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.S
import vn.abook.player.StudioErrors
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.addbook.FieldGroup
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.*
import vn.abook.player.ui.theme.Dim

data class VolumeDraft(val id: Int, val title: String, val number: String, val start: String,
                       val image: String? = null, val changeCover: Boolean = false)

object StudioVolumes {
    fun drafts(book: JSONObject): List<VolumeDraft> {
        val chapters = book.optJSONArray("chapters").objects()
        return book.optJSONArray("volumes").objects().map { volume ->
            val first = volume.optJSONArray("chapters")?.optJSONObject(0)?.optInt("id")
            VolumeDraft(volume.getInt("id"), volume.getString("title"), volume.getInt("number").toString(),
                (chapters.indexOfFirst { it.optInt("id") == first } + 1).toString())
        }
    }

    fun definitions(rows: List<VolumeDraft>, chapters: List<Int>): JSONObject {
        val starts = rows.map { it.start.toIntOrNull() ?: 0 }
        require(rows.isNotEmpty() && starts.first() == 1 && starts == starts.distinct().sorted()
            && starts.last() <= chapters.size && rows.size <= 99) { S.s_volume_invalid }
        val array = JSONArray()
        rows.forEachIndexed { i, row ->
            val number = row.number.toIntOrNull() ?: 0
            require(number in 1..9999 && row.title.isNotBlank() && row.title.length <= 240) { S.s_volume_invalid }
            array.put(JSONObject().put("id", row.id).put("title", row.title.trim()).put("number", number)
                .put("chapters", JSONArray(chapters.subList(starts[i] - 1, (starts.getOrNull(i + 1) ?: (chapters.size + 1)) - 1))))
        }
        return JSONObject().put("volumes", array)
    }
}

/** Boundaries only: Studio keeps the original global chapter queue and synthesis identity. */
@Composable
fun StudioVolumesScreen(session: StudioSession, bookId: String, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var book by remember(bookId) { mutableStateOf(JSONObject()) }
    var rows by remember(bookId) { mutableStateOf(emptyList<VolumeDraft>()) }
    var problem by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var picking by remember { mutableStateOf<Int?>(null) }
    val list = rememberLazyListState()
    val chapters = book.optJSONArray("chapters").objects().map { it.getInt("id") }
    fun failure(error: Throwable) {
        problem = if (error is IllegalArgumentException) error.message.orEmpty() else StudioText.failure(StudioErrors.of(error))
    }
    suspend fun load() {
        try {
            book = session.source.volumes(session.computer, bookId)
            rows = StudioVolumes.drafts(book)
            problem = ""
        } catch (cancelled: CancellationException) { throw cancelled }
        catch (error: Exception) { failure(error) }
    }
    LaunchedEffect(bookId) { load() }
    fun change(id: Int, update: (VolumeDraft) -> VolumeDraft) { rows = rows.map { if (it.id == id) update(it) else it } }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        val id = picking
        if (uri != null && id != null) scope.launch {
            try {
                val bytes = withContext(Dispatchers.IO) {
                    context.contentResolver.openInputStream(uri)!!.use { stream ->
                        val bytes = stream.readBytesBounded(16 * 1024 * 1024)
                        require(bytes.isNotEmpty()) { S.s_chua_doc_duoc_file_anh_09736d91 }
                        bytes
                    }
                }
                val mime = context.contentResolver.getType(uri) ?: "image/jpeg"
                val image = "data:$mime;base64," + vn.abook.player.readaloud.WebSocket.base64(bytes)
                change(id) { it.copy(image = image, changeCover = true) }
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (error: Exception) { failure(error) }
        }
    }
    BookForm(S.s_volume_manage, onBack, "studio_volumes", footer = {
        PrimaryButton(S.s_volume_save, {
            if (!busy) {
                busy = true
                scope.launch {
                val submitted = rows
                try {
                    session.source.put(session.computer, bookId, "volumes", StudioVolumes.definitions(submitted, chapters))
                    for (row in submitted.filter { it.changeCover }) session.source.put(session.computer, bookId,
                        "volumes/${row.id}/cover", JSONObject().put("image", row.image ?: JSONObject.NULL))
                    load()
                } catch (cancelled: CancellationException) { throw cancelled }
                catch (error: Exception) { failure(error) }
                finally { busy = false }
                }
            }
        }, Modifier.testTag("volumes_save"), enabled = !busy && rows.isNotEmpty(), pending = busy)
    }) {
        LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("volume_editor"), state = list, contentPadding = PaddingValues(vertical = Dim.s16), verticalArrangement = Arrangement.spacedBy(Dim.s16)) {
            item("help") { RowHint(S.s_volume_split_help) }
            itemsIndexed(rows, key = { _, row -> row.id }) { index, row ->
                Column(Modifier.animateItem(fadeInSpec = null, fadeOutSpec = null)) {
                    FieldGroup { Column(verticalArrangement = Arrangement.spacedBy(Dim.s8)) {
                    BookField(S.s_volume_title, row.title, { value -> change(row.id) { it.copy(title = value) } }, "volume_title_${row.id}", enabled = !busy)
                    BookField(S.s_volume_number(row.number), row.number, { value -> change(row.id) { it.copy(number = value) } }, "volume_number_${row.id}", enabled = !busy, keyboard = KeyboardType.Number)
                    BookField(S.s_volume_first_chapter, row.start, { value -> change(row.id) { it.copy(start = value) } }, "volume_start_${row.id}", enabled = !busy && index > 0, keyboard = KeyboardType.Number)
                    TextAction(S.s_volume_cover, { if (busy) return@TextAction; picking = row.id; picker.launch(arrayOf("image/*")) }, "volume_cover_${row.id}")
                    TextAction(S.s_volume_book_cover, { if (busy) return@TextAction; change(row.id) { it.copy(image = null, changeCover = true) } }, "volume_cover_clear_${row.id}")
                    Reveal(index > 0) { TextAction(S.s_xoa_777195ab, { if (!busy) rows = rows.filter { it.id != row.id } }, "volume_remove_${row.id}") }
                    RowLine()
                    } }
                }
            }
            item("add") {
                TextAction(S.s_volume_add, {
                    if (busy || rows.size >= 99) return@TextAction
                    val start = (rows.lastOrNull()?.start?.toIntOrNull() ?: 0) + 1
                    if (start <= chapters.size) rows = rows + VolumeDraft((rows.maxOfOrNull { it.id } ?: 0) + 1,
                        S.s_volume_number(rows.size + 1), (rows.size + 1).toString(), start.toString())
                }, "volume_add")
            }
            item("problem") { InlineProblem(problem, { scope.launch { load() } }, "volumes_problem") }
        }
    }
}

private fun java.io.InputStream.readBytesBounded(limit: Int): ByteArray {
    val output = java.io.ByteArrayOutputStream()
    val buffer = ByteArray(8192)
    while (true) {
        val read = read(buffer)
        if (read < 0) break
        require(output.size() + read <= limit) { S.s_chua_doc_duoc_file_anh_09736d91 }
        output.write(buffer, 0, read)
    }
    return output.toByteArray()
}
