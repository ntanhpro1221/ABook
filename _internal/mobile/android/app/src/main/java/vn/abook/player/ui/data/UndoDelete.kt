package vn.abook.player.ui.data

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** Native optimistic removal. No disk mutation until the web's 28 second action window ends.
 * Owned by the application: navigating away or recreating the Activity does not shorten the window. */
class UndoDelete(
    private val scope: CoroutineScope,
    private val erase: suspend (String) -> String?,
    private val changed: suspend () -> Unit,
    private val removed: (String) -> Unit = {},
) {
    private val jobs = linkedMapOf<String, Job>()
    private val flow = MutableStateFlow<List<String>>(emptyList())
    val pending = flow.asStateFlow()
    private val actions = MutableStateFlow<List<String>>(emptyList())
    val undoable = actions.asStateFlow()
    private val errors = MutableStateFlow("")
    val problem = errors.asStateFlow()
    private val lastName = MutableStateFlow("")
    /** Tên cuốn vừa bỏ (cho dòng "Đã xoá “X” khỏi điện thoại"); rỗng khi chưa biết tên. */
    val lastTitle = lastName.asStateFlow()
    private val visible = MutableStateFlow(false)
    val showing = visible.asStateFlow()

    fun contains(id: String) = id in flow.value

    suspend fun remove(id: String, title: String = "") {
        if (contains(id)) return
        errors.value = ""
        lastName.value = title
        flow.value = flow.value + id
        actions.value = actions.value + id
        visible.value = true
        removed(id)
        jobs[id] = scope.launch {
            delay(WINDOW_MS)
            // Claim expiry before suspending for I/O: a last-millisecond tap cannot restore an already deleting book.
            jobs.remove(id)
            actions.value = actions.value - id
            if (actions.value.isEmpty()) visible.value = false
            val error = try { erase(id) } catch (_: Exception) { "Chưa xoá được" }
            flow.value = flow.value - id
            errors.value = error.orEmpty()
            changed()
            if (error != null) scope.launch { delay(5_000); if (errors.value == error) errors.value = "" }
        }
        changed()
    }

    fun undo() {
        val ids = actions.value
        ids.forEach { jobs.remove(it)?.cancel() }
        flow.value = flow.value - ids.toSet()
        actions.value = emptyList()
        visible.value = false
        scope.launch { changed() }
    }

    /** Back dismisses the action, but expiry still owns the real deletion. */
    fun dismiss() { actions.value = emptyList(); visible.value = false; errors.value = "" }

    companion object { const val WINDOW_MS = 28_000L }
}
