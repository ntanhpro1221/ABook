package vn.abook.player.ui.components

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import kotlinx.coroutines.launch
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

/*
 * Bước xác nhận ngay trong bảng trượt (xoá khỏi máy, bỏ ghép, thôi ghép một máy nghe thư viện): MỘT chỗ dựng cho mọi nơi hỏi "chắc chứ?" để chúng giống hệt nhau.
 */

/**
 * Các trang của một bảng trượt, đi sâu = trượt sang trái, Back = trượt ngược lại (đối xứng). `ordinal` cho biết trang nào "sâu" hơn để chọn hướng.
 */
@Composable
fun <T> SheetPages(page: T, ordinal: (T) -> Int, tag: String, content: @Composable (T) -> Unit) {
    AnimatedContent(
        targetState = page,
        transitionSpec = {
            val forward = ordinal(targetState) > ordinal(initialState)
            (slideInHorizontally(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) { if (forward) it else -it } togetherWith
                slideOutHorizontally(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate)) { if (forward) -it else it })
                .using(SizeTransform(clip = true))
        },
        label = tag,
        modifier = Modifier.fillMaxWidth().testTag(tag),
    ) { shown -> content(shown) }
}

/**
 * Trang xác nhận: câu hỏi, các dòng nói mất gì (chữ 16, mực phụ), lỗi tại chỗ màu nguy hiểm khi việc vừa thất bại, rồi các nút. Nút chính của bước này
 * là màu nguy hiểm ([DangerButton]) - việc không nhấn nhầm được.
 */
@Composable
fun ConfirmPage(title: String, tag: String, lines: List<String>, problem: String, buttons: @Composable ColumnScope.() -> Unit) {
    val colors = Abook.colors
    Column(Modifier.fillMaxWidth().testTag(tag)) {
        BasicText(title, style = Abook.type.sectionTitle)
        for (line in lines) {
            Spacer(Modifier.height(Dim.s8))
            BasicText(line, style = Abook.type.body.copy(color = colors.text2))
        }
        if (problem.isNotEmpty()) {
            Spacer(Modifier.height(Dim.s8))
            BasicText(problem, style = Abook.type.bodySmall.copy(color = colors.danger), modifier = Modifier.testTag("${tag}_problem"))
        }
        Spacer(Modifier.height(Dim.s24))
        buttons()
    }
}

/** Lời xác nhận "Xoá khỏi máy" của một cuốn: `holder` = tên máy còn giữ cuốn (cuốn chỉ nghe thẳng / tải dở), null = cuốn của riêng máy này. */
fun deleteBookLine(title: String, holder: String?): String =
    if (holder != null) "Phần đã tải của “$title” sẽ bị xoá khỏi máy này. Sách vẫn còn trên $holder."
    else "“$title” sẽ bị xoá khỏi máy này. Muốn nghe lại, bạn cần thêm lại file sách."

/**
 * Bước xác nhận xoá một cuốn khỏi máy - MỘT chỗ cho menu "Thêm" của trang sách và danh sách Dung lượng: nói rõ cái gì mất, nút đỏ "Xoá khỏi máy", nút chữ
 * "Giữ lại". `delete` chạy lõi (null = đã xoá, khác null = câu lỗi hiện tại chỗ); xoá xong gọi `onDeleted`.
 */
@Composable
fun DeleteBookPage(title: String, holder: String?, delete: suspend () -> String?, onDeleted: () -> Unit, onKeep: () -> Unit) {
    val scope = rememberCoroutineScope()
    var working by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    ConfirmPage("Xoá khỏi máy?", "delete_confirm", listOf(deleteBookLine(title, holder)), problem) {
        DangerButton(if (working) "Đang xoá" else "Xoá khỏi máy", {
            if (working) return@DangerButton
            working = true
            scope.launch {
                val error = delete()
                working = false
                problem = error.orEmpty()
                if (error == null) onDeleted()
            }
        }, "delete_yes")
        Spacer(Modifier.height(Dim.s8))
        QuietButton("Giữ lại", onKeep, "delete_keep")
    }
}

/** Nút đỏ của bước xác nhận. Chữ trên nền đỏ theo nền của giao diện để đủ tương phản cả hai chế độ. */
@Composable
fun DangerButton(label: String, onClick: () -> Unit, tag: String, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    val ink = if (colors.dark) colors.bg else colors.panel
    Box(
        modifier.fillMaxWidth().heightIn(min = Dim.s48)
            .pressable(onClick = onClick)
            .clip(RoundedCornerShape(Dim.radiusControl)).background(colors.danger).padding(horizontal = Dim.s24, vertical = Dim.s12)
            .testTag(tag),
        contentAlignment = Alignment.Center,
    ) {
        BasicText(label, style = Abook.type.bodyStrong.copy(color = ink))
    }
}

/** Nút chữ "Giữ lại" dưới các nút khác: cao 48, chữ nhấn, canh giữa. */
@Composable
fun QuietButton(label: String, onClick: () -> Unit, tag: String, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().height(Dim.s48).pressable(onClick = onClick).testTag(tag), contentAlignment = Alignment.Center) {
        BasicText(label, style = Abook.type.bodyStrong.copy(color = Abook.colors.accentText))
    }
}
