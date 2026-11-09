package vn.abook.player.ui.addbook

import vn.abook.player.S

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
    BookForm(S.s_mo_sach_e84e9b67, back, "package_review", footer = {
        PrimaryButton(S.s_mo_sach_e84e9b67, { if (!state.busy) keep() }, Modifier.fillMaxWidth().testTag("package_keep"), enabled = !state.busy)
        TextAction(S.s_thay_bang_file_nay_3140e07e, { if (!state.busy) replace() }, "package_replace", Modifier.fillMaxWidth())
    }) {
        // Như trang xác nhận ([ConfirmPage]): câu hỏi, rồi từng đoạn chữ 16 cách nhau 8 - Caption chỉ cho một dòng tin phụ, không xếp chồng thành đoạn văn.
        val line = Abook.type.body.copy(color = Abook.colors.text2)
        Column(Modifier.fillMaxWidth().padding(top = Dim.s16)) {
            BasicText(S.s_file_nay_co_ban_thu_khac_6036a451, style = Abook.type.sectionTitle)
            Spacer(Modifier.height(Dim.s8))
            BasicText(review.title, style = Abook.type.body)
            Spacer(Modifier.height(Dim.s8))
            BasicText(S.s_chinh_sua_va_cho_nghe_cua_ban_van_duoc_giu_287783a6, style = line)
            Reveal(review.incomingTitle.isNotBlank() && review.incomingTitle != review.title) {
                Column {
                    Spacer(Modifier.height(Dim.s8))
                    BasicText(S.s_ten_trong_file_la_0_khac_ten_dang_dung_f6042eec(review.incomingTitle), style = line)
                }
            }
            InlineProblem(state.problem, tag = "package_problem")
        }
    }
}
