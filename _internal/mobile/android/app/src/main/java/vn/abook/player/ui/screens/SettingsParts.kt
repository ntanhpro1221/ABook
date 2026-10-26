package vn.abook.player.ui.screens

import vn.abook.player.ui.components.PageHeader
import vn.abook.player.ui.components.ListRow
import vn.abook.player.ui.components.Reveal
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.BackButton
import vn.abook.player.ui.components.ChevronIcon
import vn.abook.player.ui.components.ChoiceRow
import vn.abook.player.ui.components.Switch
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.Choice
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

/*
 * Khối dựng của các màn Cài đặt (shared/SettingsNav.tsx của bản WebView): khoảng trắng + tiêu đề nhỏ thay khung (DESIGN.md §4.2), hàng = tên (16) + mô tả
 * một dòng (12, mực phụ) bên trái, điều khiển bên phải; nhóm chọn-một nằm DƯỚI tên, trải hết bề ngang. Chữ dài xuống dòng, không cắt.
 */

/**
 * Màn con của Cài đặt (cấp hai): nút ← thẳng mép nội dung + tên nhóm (24, sát sau nút), rồi nội dung cuộn. Đệm dưới theo thanh điều hướng của máy - màn con phủ cả
 * thanh tab.
 */
@Composable
fun SettingsPage(title: String, onBack: () -> Unit, tag: String, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    val bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    Column(
        modifier.fillMaxSize().testTag(tag).verticalScroll(rememberScrollState())
            .padding(top = top, start = Dim.margin, end = Dim.margin, bottom = bottom + Dim.s48),
    ) {
        PageHeader(title, onBack)
        content()
    }
}

/** Tính năng mà lõi / giao diện native chưa có: nói thẳng "Sắp có", không giả một nút chạy được. */
@Composable
fun SoonRow(label: String, hint: String? = null, tag: String? = null) {
    ListRow(label, if (tag != null) Modifier.testTag(tag) else Modifier, hint = hint) {
        BasicText("Sắp có", style = Abook.type.caption)
    }
}
