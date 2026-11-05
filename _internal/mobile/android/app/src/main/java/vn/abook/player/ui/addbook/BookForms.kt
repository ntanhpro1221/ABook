package vn.abook.player.ui.addbook

import vn.abook.player.ui.components.gestureSafe
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.foundation.shape.RoundedCornerShape
import vn.abook.player.ui.components.BasicText
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.PageHeader
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.insetSurface

/**
 * Khung chung của các màn Thêm sách / Sửa sách: đầu màn con như Cài đặt ([PageHeader]), nội dung chiếm phần còn lại, chân cố định (nút chính) ở đáy. Tên màn nhận
 * phần chiều ngang còn lại và tự xuống dòng, không đè nút Back.
 */
@Composable
fun BookForm(
    title: String,
    onBack: () -> Unit,
    tag: String,
    footer: (@Composable ColumnScope.() -> Unit)? = null,
    trailing: (@Composable () -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        Modifier.fillMaxSize().background(Abook.colors.bg).windowInsetsPadding(gestureSafe(WindowInsets.safeDrawing))
            .imePadding().padding(horizontal = Dim.margin).testTag(tag),
    ) {
        PageHeader(title, onBack, trailing = trailing)
        Column(Modifier.weight(1f), content = content)
        if (footer != null) Column(Modifier.fillMaxWidth().padding(vertical = Dim.s12)) { footer() }
    }
}

/** [FieldGroup] đang bao quanh: ô nhập gọi nó mỗi khi đang gõ để cả nhóm (ô + việc dưới ô) cuộn lên khỏi bàn phím và chân trang ghim. */
private val LocalFieldGroup = staticCompositionLocalOf<BringIntoViewRequester?> { null }

/**
 * Một ô nhập cùng NÚT/DÒNG nằm dưới nó ("Thêm chữ này", "Lưu", "Nghe thử"). Khi bàn phím mở, vùng nội dung chỉ còn thấp bằng vài dòng; ô nhập tự cuộn con trỏ vào
 * thấy, nhưng việc dưới ô thì không ai cuộn tới - chân trang ghim che nó (soát điện thoại thật 02-11: "Thêm chữ này" mất dưới "Tiếp"). Mọi ô có việc dưới nó đứng
 * trong nhóm này: đang gõ (hay bàn phím đang trượt lên) thì cả nhóm được đưa vào vùng thấy, trên chân trang.
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun FieldGroup(modifier: Modifier = Modifier, verticalArrangement: Arrangement.Vertical = Arrangement.Top, content: @Composable ColumnScope.() -> Unit) {
    val into = remember { BringIntoViewRequester() }
    CompositionLocalProvider(LocalFieldGroup provides into) {
        Column(modifier.bringIntoViewRequester(into), verticalArrangement, content = content)
    }
}

/**
 * Ô nhập một dòng trên mặt chìm (cao ≥ 48, chữ dài thì ô cao thêm, không cuộn ngang). `label` = nhãn nhỏ phía trên; null = ô đứng một mình (tên màn đã nói nó là gì,
 * `description` cho trợ năng).
 */
@Composable
fun BookField(
    label: String?, value: String, onChange: (String) -> Unit, tag: String, enabled: Boolean = true, description: String = label.orEmpty(),
    placeholder: String? = null, keyboard: KeyboardType = KeyboardType.Text,
    /** Chấm thay chữ (khoá, mật khẩu); `trailing` là việc ở cuối ô ("Hiện" / "Ẩn"). */
    masked: Boolean = false, trailing: (@Composable () -> Unit)? = null,
) {
    val group = LocalFieldGroup.current
    var focused by remember { mutableStateOf(false) }
    val keyboardHeight = WindowInsets.ime.getBottom(LocalDensity.current)
    if (group != null) LaunchedEffect(value, focused, keyboardHeight) { if (focused) group.bringIntoView() }
    Column(Modifier.fillMaxWidth()) {
        if (label != null) {
            BasicText(label, style = Abook.type.bodySmall)
            Spacer(Modifier.height(Dim.s8))
        }
        BasicTextField(
            value, onChange, enabled = enabled, textStyle = Abook.type.body,
            cursorBrush = SolidColor(Abook.colors.accentText),
            keyboardOptions = if (masked) KeyboardOptions(keyboardType = KeyboardType.Password, autoCorrectEnabled = false) else KeyboardOptions(keyboardType = keyboard),
            visualTransformation = if (masked) PasswordVisualTransformation() else VisualTransformation.None,
            // Đệm nằm TRONG decorationBox: để ngoài, hộp chạm của ô co còn phần chữ (24 dp trong ô vẽ 48 dp), chạm vào đệm không vào ô - cùng loại lỗi với "Thay bằng file này".
            modifier = Modifier.fillMaxWidth().heightIn(min = Dim.s48)
                .insetSurface(Abook.colors)
                .onFocusChanged { focused = it.hasFocus }
                .semantics { contentDescription = description }.testTag(tag),
            decorationBox = { inner ->
                val text: @Composable (Modifier) -> Unit = { box ->
                    Box(box) {
                        if (value.isEmpty() && placeholder != null) BasicText(placeholder, style = Abook.type.body.copy(color = Abook.colors.text3))
                        inner()
                    }
                }
                if (trailing == null) {
                    text(Modifier.fillMaxWidth().heightIn(min = Dim.s48).padding(Dim.s12))
                } else {
                    Row(Modifier.fillMaxWidth().heightIn(min = Dim.s48).padding(start = Dim.s12), verticalAlignment = Alignment.CenterVertically) {
                        text(Modifier.weight(1f).padding(vertical = Dim.s12))
                        Box(Modifier.padding(end = Dim.s12)) { trailing() }
                    }
                }
            },
        )
    }
}

/** "Về tên gốc" của màn tên chương: chỉ dựng khi tên khác bản gốc; một dòng nói tên gốc là gì, một việc để quay về. */
@Composable
fun RevertName(original: String, onRevert: () -> Unit, tag: String = "chapter_revert") {
    Column(Modifier.fillMaxWidth()) {
        Caption("Tên gốc: $original")
        TextAction("Về tên gốc", onRevert, tag, Modifier.fillMaxWidth(), align = Alignment.CenterStart)
    }
}
