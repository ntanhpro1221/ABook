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
        Column(Modifier.fillMaxWidth().padding(top = Dim.s16)) {
            BasicText("File này có bản thu khác", style = Abook.type.sectionTitle)
            Caption(review.title)
            Caption("Chỉnh sửa và chỗ nghe của bạn vẫn được giữ.")
            Reveal(review.incomingTitle.isNotBlank() && review.incomingTitle != review.title) {
                Caption("Tên trong file là “${review.incomingTitle}”, khác tên đang dùng.")
            }
            InlineProblem(state.problem, tag = "package_problem")
        }
    }
}
