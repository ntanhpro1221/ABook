package vn.abook.player.ui.addbook

import androidx.compose.foundation.layout.*
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import vn.abook.player.ui.components.*
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

@Composable
fun PackageReviewScreen(state: ImportState, back: () -> Unit, keep: () -> Unit, replace: () -> Unit) {
    val review = state.packageReview ?: return
    BookForm("Mở sách", back, "package_review", footer = {
        PrimaryButton("Mở sách", { if (!state.busy) keep() }, Modifier.fillMaxWidth().testTag("package_keep"), enabled = !state.busy)
        TextAction("Thay bằng file này", { if (!state.busy) replace() }, "package_replace", Modifier.fillMaxWidth())
    }) {
        // Như trang xác nhận ([ConfirmPage]): câu hỏi, rồi từng đoạn chữ 16 cách nhau 8 - Caption chỉ cho một dòng tin phụ, không xếp chồng thành đoạn văn.
        val line = Abook.type.body.copy(color = Abook.colors.text2)
        Column(Modifier.fillMaxWidth().padding(top = Dim.s16)) {
            BasicText("File này có bản thu khác", style = Abook.type.sectionTitle)
            Spacer(Modifier.height(Dim.s8))
            BasicText(review.title, style = Abook.type.body)
            Spacer(Modifier.height(Dim.s8))
            BasicText("Chỉnh sửa và chỗ nghe của bạn vẫn được giữ.", style = line)
            Reveal(review.incomingTitle.isNotBlank() && review.incomingTitle != review.title) {
                Column {
                    Spacer(Modifier.height(Dim.s8))
                    BasicText("Tên trong file là “${review.incomingTitle}”, khác tên đang dùng.", style = line)
                }
            }
            InlineProblem(state.problem, tag = "package_problem")
        }
    }
}
