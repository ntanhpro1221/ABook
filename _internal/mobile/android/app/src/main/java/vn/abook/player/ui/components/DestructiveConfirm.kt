package vn.abook.player.ui.components

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.window.Dialog
import kotlinx.coroutines.Job
import kotlinx.coroutines.withContext
import java.util.concurrent.atomic.AtomicBoolean
import vn.abook.player.S
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs
import vn.abook.player.ui.motion.FadeDurationScale
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.motion.rememberReducedMotion

/** Submit state of one opening: a reopened dialog never inherits the last attempt's lock, error or job. */
@Stable
private class ConfirmSession {
    var submitted by mutableStateOf(false)
    val locked = AtomicBoolean(false)
    var ownedPending by mutableStateOf(false)
    var ownsJob by mutableStateOf(false)
    var ownedError by mutableStateOf("")
}

/** The one destructive confirmation. Callers keep it composed and pass [visible]; the dialog fades and scales in and out
 * itself (web Dialog `open`, Qt DestructiveConfirm.show()), holding its last content through the exit. All dismiss paths
 * cancel. The destructive callback exists only inside this boundary. */
@Composable
fun DestructiveConfirm(visible: Boolean, title: String, description: String, onCancel: () -> Unit, onConfirm: () -> Any?,
                       label: String = S.s_xoa_777195ab, pending: Boolean? = null, problem: String = "") {
    val reduced = rememberReducedMotion()
    val shown = remember { Animatable(0f) }
    var retained by remember { mutableStateOf(visible) }
    var opening by remember { mutableIntStateOf(0) }
    LaunchedEffect(visible) {
        if (visible) { opening++; retained = true }
        val spec = tween<Float>(if (reduced) MotionMs.REDUCED_FADE_MS else if (visible) MotionMs.MEDIUM else MotionMs.MEDIUM_OUT,
            easing = if (visible) Motion.Decelerate else Motion.Accelerate)
        withContext(FadeDurationScale) { shown.animateTo(if (visible) 1f else 0f, spec) }
        if (!visible) retained = false
    }
    val session = remember(opening) { ConfirmSession() }
    val cancelFocus = remember { FocusRequester() }
    val working = pending == true || session.ownedPending
    val failure = problem.ifEmpty { session.ownedError }
    LaunchedEffect(session, session.submitted, working, failure) {
        if (session.submitted && !working) {
            session.locked.set(false)
            if ((pending != null || session.ownsJob) && failure.isEmpty()) onCancel()
        }
    }
    fun accept() {
        if (!visible || !session.locked.compareAndSet(false, true)) return
        session.submitted = true; session.ownedError = ""; session.ownedPending = true
        try {
            val result = onConfirm()
            if (result is Job) {
                session.ownsJob = true
                result.invokeOnCompletion { error ->
                    if (error != null) session.ownedError = S.s_action_failed_retry
                    session.ownedPending = false
                }
            } else session.ownedPending = false
        } catch (_: Exception) { session.ownedError = S.s_action_failed_retry; session.ownedPending = false }
    }
    fun cancel() { if (visible && !working && !session.locked.get()) onCancel() }
    if (retained) {
        Dialog(onDismissRequest = { cancel() }) {
            Column(Modifier.fillMaxWidth()
                .graphicsLayer { alpha = shown.value; val scale = if (reduced) 1f else .96f + .04f * shown.value; scaleX = scale; scaleY = scale }
                .background(Abook.colors.panel, RoundedCornerShape(Dim.radiusSheet))
                .padding(Dim.s24).testTag("destructive_confirm")) {
                ConfirmPage(title, "destructive_body", listOf(description), if (session.submitted) failure else "") {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        QuietButton(S.s_huy_96732485, { cancel() }, "destructive_cancel", Modifier.weight(1f).focusRequester(cancelFocus))
                        Spacer(Modifier.width(Dim.s8))
                        DangerButton(if (session.submitted && failure.isNotEmpty()) S.s_thu_lai_c58d068c else label, { accept() }, "destructive_accept", Modifier.weight(1f), pending = working)
                    }
                }
            }
            LaunchedEffect(Unit) { cancelFocus.requestFocus() }
        }
    }
}
