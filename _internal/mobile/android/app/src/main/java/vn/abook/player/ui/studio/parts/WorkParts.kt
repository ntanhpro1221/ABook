package vn.abook.player.ui.studio.parts

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import kotlinx.coroutines.flow.StateFlow
import vn.abook.player.ClipFailure
import vn.abook.player.ClipState
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.IconAction
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.PlayIcon
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.StopIcon
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.studio.StudioDecisions
import vn.abook.player.ui.studio.WorkExample
import vn.abook.player.ui.studio.WorkLogic
import vn.abook.player.ui.studio.WorkText
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** Trạng thái nghe của một tab (không có trình phát: đang thử trên màn không nối máy → luôn "không phát gì"). */
@Composable
fun StateFlow<ClipState>?.collectClip(): ClipState {
    val state = this?.collectAsState()?.value
    return state ?: ClipState()
}

/** Lời báo khi một đoạn không nghe được: mạng rớt (có thể thử lại) khác máy tính không còn file. */
@Composable
fun ClipProblem(clip: ClipState, modifier: Modifier = Modifier, tag: String = "studio_clip_problem") {
    val message = when (clip.failure) {
        ClipFailure.Offline -> WorkText.PLAY_FAILED_OFFLINE
        ClipFailure.Missing -> WorkText.PLAY_FAILED_MISSING
        null -> ""
    }
    InlineProblem(message, null, tag, modifier)
}

/** Nút nghe một đoạn: chạm phát, chạm lại dừng; đang tải hay đang phát đều hiện nút dừng. */
@Composable
fun ClipButton(clipId: String, clip: ClipState, onClick: () -> Unit, tag: String, modifier: Modifier = Modifier) {
    val active = clip.playing == clipId || clip.loading == clipId
    IconAction(if (active) WorkText.STOP else WorkText.PLAY, onClick, tag, modifier) {
        if (active) StopIcon(Abook.colors.accentText) else PlayIcon(Abook.colors.accentText)
    }
}

/**
 * Dải "Hoàn tác" (NATIVE_REMOTE_STUDIO.md §2.7): chữ đã ghi + nút. `onUndo` null thì là dải báo (lỗi, "vừa được sửa ở máy khác") với nút "Đóng" nếu có `onClose`.
 * Không biết gì về hàng chờ - xem [DecisionStrip].
 */
@Composable
fun UndoStrip(message: String, onUndo: (() -> Unit)?, onClose: (() -> Unit)?, tag: String, modifier: Modifier = Modifier) {
    Row(
        modifier.fillMaxWidth().clip(RoundedCornerShape(Dim.radiusControl)).background(Abook.colors.bgSunken).heightIn(min = Dim.s48).padding(start = Dim.s12).testTag(tag),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        BasicText(message, style = Abook.type.bodySmall, modifier = Modifier.weight(1f).padding(vertical = Dim.s12).testTag("${tag}_text"))
        if (onUndo != null) TextAction(WorkText.UNDO, onUndo, "${tag}_undo") else if (onClose != null) TextAction(WorkText.CLOSE, onClose, "${tag}_close")
    }
}

/** [UndoStrip] cho hàng chờ quyết định của dự án: hiện khi có quyết định đang giữ (nút "Hoàn tác") hay có lời báo (nút "Đóng"); mở / khép chiều cao. */
@Composable
fun DecisionStrip(decisions: StudioDecisions, modifier: Modifier = Modifier) {
    val held = decisions.held
    val message = held?.decision?.summary ?: decisions.notice
    // Giữ câu cuối trong lúc dải khép lại.
    var shown by remember { mutableStateOf(message) }
    if (message.isNotEmpty()) shown = message
    Reveal(message.isNotEmpty()) {
        Column(modifier.fillMaxWidth().padding(top = Dim.s12)) {
            UndoStrip(shown, if (held != null) decisions::undo else null, if (held == null) decisions::dismissNotice else null, "studio_undo")
        }
    }
}

/**
 * Nút trả lời của một thẻ: `primary` là gợi ý của máy (nền hổ phách), còn lại nền chìm; `hint` là cái giá ("đổi giọng, thu lại 12 câu") dưới nút.
 * Cao ít nhất 48, trải hết bề ngang.
 */
@Composable
fun AnswerButton(label: String, onClick: () -> Unit, tag: String, modifier: Modifier = Modifier, primary: Boolean = false, hint: String? = null, enabled: Boolean = true) {
    Column(modifier.fillMaxWidth()) {
        if (primary) {
            PrimaryButton(label, onClick, Modifier.fillMaxWidth().testTag(tag), enabled)
        } else {
            Box(
                Modifier.fillMaxWidth().heightIn(min = Dim.s48)
                    .then(if (enabled) Modifier.pressable(onClick = onClick) else Modifier.semantics { disabled() })
                    .clip(RoundedCornerShape(Dim.radiusControl)).background(Abook.colors.bgSunken)
                    .padding(horizontal = Dim.s16, vertical = Dim.s12).testTag(tag),
                contentAlignment = Alignment.Center,
            ) {
                BasicText(label, style = Abook.type.bodyStrong.copy(color = if (enabled) Abook.colors.text else Abook.colors.text3))
            }
        }
        if (hint != null) RowHint(hint, Modifier.padding(top = Dim.s4, start = Dim.s4))
    }
}

/** Một câu truyện làm ví dụ trên thẻ: câu trước, câu được hỏi (tên ứng viên tô màu nhấn), câu sau; nút nghe khi đã có bản thu. */
@Composable
fun LineSample(example: WorkExample, clip: ClipState, clipId: String, onPlay: (() -> Unit)?, tag: String, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    Row(
        modifier.fillMaxWidth().clip(RoundedCornerShape(Dim.radiusControl)).background(colors.bgSunken).padding(start = Dim.s12, top = Dim.s8, bottom = Dim.s8).testTag(tag),
        verticalAlignment = Alignment.Top,
    ) {
        Column(Modifier.weight(1f).padding(vertical = Dim.s4)) {
            if (example.before.isNotEmpty()) RowHint(example.before, Modifier.padding(bottom = Dim.s4))
            val parts = WorkLogic.markNames(example.text, example.names)
            val base = Abook.type.body.copy(color = if (example.narration) colors.text2 else colors.text)
            BasicText(
                buildAnnotatedString {
                    for (part in parts) {
                        if (part.mark) withStyle(SpanStyle(color = colors.accentText, fontWeight = FontWeight.Medium)) { append(part.text) } else append(part.text)
                    }
                },
                style = base,
                modifier = Modifier.testTag("${tag}_text"),
            )
            if (example.after.isNotEmpty()) RowHint(example.after, Modifier.padding(top = Dim.s4))
            val who = if (!example.narration && example.speaker.isNotEmpty()) " · ${example.speaker}" else ""
            Caption("${example.chapterTitle}$who", Modifier.padding(top = Dim.s4), colors.text3)
        }
        if (onPlay != null) {
            Spacer(Modifier.width(Dim.s4))
            ClipButton(clipId, clip, onPlay, "${tag}_play")
        } else {
            Spacer(Modifier.width(Dim.s12))
        }
    }
}

/** Hai nút đứng cạnh nhau cùng bề rộng (Ổn / Cần thu lại). */
@Composable
fun SideBySide(modifier: Modifier = Modifier, content: @Composable RowScope.() -> Unit) {
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(Dim.s8), content = content)
}
