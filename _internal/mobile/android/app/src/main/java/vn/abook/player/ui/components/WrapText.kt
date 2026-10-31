package vn.abook.player.ui.components

import androidx.compose.foundation.text.BasicText as FoundationText
import androidx.compose.foundation.text.InlineTextContent
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorProducer
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.text
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.foundation.text.TextAutoSize
import androidx.compose.ui.text.style.TextOverflow

/**
 * Chữ của app: thay cho `androidx.compose.foundation.text.BasicText` ở MỌI nơi (TextWrapRulesTest quét import) để hai luật xuống dòng chạy một chỗ - chữ + số ngắn đi
 * liền ("số 1"), dấu ngăn không mở dòng và không đóng dòng (cuối dòng thì vẽ trong suốt). Cây trợ năng và test vẫn thấy chữ GỐC; chỉ phần vẽ đổi.
 * Chữ không có số đứng sau chữ, không có dấu ngăn thì đi thẳng vào BasicText, không thêm trạng thái.
 */
@Composable
fun BasicText(
    text: String,
    modifier: Modifier = Modifier,
    style: TextStyle = TextStyle.Default,
    onTextLayout: ((TextLayoutResult) -> Unit)? = null,
    // cắt-có-chủ-ý: mặc định của foundation BasicText; chỗ gọi tự chọn kiểu (TextCutScanTest quét từng chỗ gọi)
    overflow: TextOverflow = TextOverflow.Clip,
    softWrap: Boolean = true,
    maxLines: Int = Int.MAX_VALUE,
    minLines: Int = 1,
    color: ColorProducer? = null,
    autoSize: TextAutoSize? = null,
) {
    val shaped = remember(text) { shapeForWrap(text) }
    val separated = remember(shaped) { hasSeparator(shaped) }
    val same = shaped == text
    val keepOriginal = if (same) modifier else modifier.semantics { this.text = AnnotatedString(text) }
    if (!separated) {
        FoundationText(shaped, keepOriginal, style, onTextLayout, overflow, softWrap, maxLines, minLines, color, autoSize)
        return
    }
    var hidden by remember(shaped) { mutableStateOf(emptyList<Int>()) }
    val shown = remember(shaped, hidden) {
        buildAnnotatedString {
            append(shaped)
            for (i in hidden) addStyle(SpanStyle(color = Color.Transparent), i, i + 1)
        }
    }
    FoundationText(
        shown, keepOriginal, style,
        { layout ->
            onTextLayout?.invoke(layout)
            val found = separatorsAtLineEnd(shaped, (0 until layout.lineCount).map { layout.getLineEnd(it) })
            if (found != hidden) hidden = found
        },
        overflow, softWrap, maxLines, minLines, emptyMap<String, InlineTextContent>(), color, autoSize,
    )
}

/** Chữ có kiểu từng đoạn: đi thẳng vào BasicText của foundation, không đổi chữ. */
@Composable
fun BasicText(
    text: AnnotatedString,
    modifier: Modifier = Modifier,
    style: TextStyle = TextStyle.Default,
    onTextLayout: ((TextLayoutResult) -> Unit)? = null,
    // cắt-có-chủ-ý: mặc định của foundation BasicText; chỗ gọi tự chọn kiểu (TextCutScanTest quét từng chỗ gọi)
    overflow: TextOverflow = TextOverflow.Clip,
    softWrap: Boolean = true,
    maxLines: Int = Int.MAX_VALUE,
    minLines: Int = 1,
    color: ColorProducer? = null,
    autoSize: TextAutoSize? = null,
) = FoundationText(text, modifier, style, onTextLayout, overflow, softWrap, maxLines, minLines, emptyMap<String, InlineTextContent>(), color, autoSize)
