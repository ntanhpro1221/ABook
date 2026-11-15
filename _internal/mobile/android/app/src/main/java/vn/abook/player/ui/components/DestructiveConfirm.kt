package vn.abook.player.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.window.Dialog
import kotlinx.coroutines.Job
import java.util.concurrent.atomic.AtomicBoolean
import vn.abook.player.S
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** All dismiss paths cancel. The destructive callback exists only inside this boundary. */
@Composable
fun DestructiveConfirm(title: String, description: String, onCancel: () -> Unit, onConfirm: () -> Any?,
                       label: String = S.s_xoa_777195ab, pending: Boolean? = null, problem: String = "") {
    val cancelFocus = remember { FocusRequester() }
    var submitted by remember { mutableStateOf(false) }
    val locked = remember { AtomicBoolean(false) }
    var ownedPending by remember { mutableStateOf(false) }
    var ownsJob by remember { mutableStateOf(false) }
    var ownedError by remember { mutableStateOf("") }
    val working = pending == true || ownedPending
    val failure = problem.ifEmpty { ownedError }
    LaunchedEffect(submitted, working, failure) {
        if (submitted && !working) {
            locked.set(false)
            if ((pending != null || ownsJob) && failure.isEmpty()) onCancel()
        }
    }
    fun accept() {
        if (!locked.compareAndSet(false, true)) return
        submitted = true; ownedError = ""; ownedPending = true
        try {
            val result = onConfirm()
            if (result is Job) {
                ownsJob = true
                result.invokeOnCompletion { error ->
                    if (error != null) ownedError = S.s_action_failed_retry
                    ownedPending = false
                }
            } else ownedPending = false
        } catch (_: Exception) { ownedError = S.s_action_failed_retry; ownedPending = false }
    }
    Dialog(onDismissRequest = { if (!working && !locked.get()) onCancel() }) {
        Column(Modifier.fillMaxWidth().background(Abook.colors.panel, RoundedCornerShape(Dim.radiusSheet))
            .padding(Dim.s24).testTag("destructive_confirm")) {
            ConfirmPage(title, "destructive_body", listOf(description), if (submitted) failure else "") {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    QuietButton(S.s_huy_96732485, { if (!working && !locked.get()) onCancel() }, "destructive_cancel", Modifier.weight(1f).focusRequester(cancelFocus))
                    Spacer(Modifier.width(Dim.s8))
                    DangerButton(if (submitted && failure.isNotEmpty()) S.s_thu_lai_c58d068c else label, { accept() }, "destructive_accept", Modifier.weight(1f), pending = working)
                }
            }
        }
        LaunchedEffect(Unit) { cancelFocus.requestFocus() }
    }
}
