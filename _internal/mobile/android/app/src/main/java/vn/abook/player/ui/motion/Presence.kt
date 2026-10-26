package vn.abook.player.ui.motion

import androidx.compose.animation.core.MutableTransitionState
import androidx.compose.runtime.*
import kotlinx.coroutines.delay
import vn.abook.player.ui.theme.MotionMs

class Presence<T>(item: T, initiallyVisible: Boolean) {
    var item by mutableStateOf(item)
    val visible = MutableTransitionState(initiallyVisible)
}

/** Keep outgoing rows until their height has closed; a fast undo reverses the same transition in place. */
@Composable
fun <T> rememberPresence(items: List<T>, key: (T) -> String): List<Presence<T>> {
    val rows = remember { mutableStateListOf<Presence<T>>().apply { addAll(items.map { Presence(it, true) }) } }
    LaunchedEffect(items) {
        val ids = items.map(key).toSet()
        val byKey = rows.associateBy { key(it.item) }
        rows.forEach { row -> row.visible.targetState = key(row.item) in ids }
        for ((index, item) in items.withIndex()) {
            val old = byKey[key(item)]
            if (old == null) rows.add(index.coerceAtMost(rows.size), Presence(item, false).also { it.visible.targetState = true })
            else old.item = item
        }
        delay(MotionMs.MEDIUM.toLong())
        rows.removeAll { !it.visible.targetState }
        // Once exits finish, restore sort order; lazy placement animates the remaining rows.
        val remaining = rows.associateBy { key(it.item) }
        val ordered = items.mapNotNull { item -> remaining[key(item)] }
        if (rows.toList() != ordered) { rows.clear(); rows.addAll(ordered) }
    }
    return rows
}
