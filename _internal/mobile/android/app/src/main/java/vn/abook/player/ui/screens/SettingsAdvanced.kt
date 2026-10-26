package vn.abook.player.ui.screens

import vn.abook.player.ui.components.ListSection
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.ListRow
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.IconAction
import vn.abook.player.ui.components.RefreshIcon
import vn.abook.player.ui.components.ActionRow
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.Caption
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.data.ThirdParty
import vn.abook.player.ui.data.ThirdPartySection
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.components.fadeEdges
import androidx.compose.foundation.lazy.rememberLazyListState

/** Lời của Chẩn đoán và Bộ nhớ: cùng chữ với bản WebView (android/Diagnostics.tsx, listen/ReadAloudStorage.tsx, listen/prepareAhead.ts). */
private object AdvancedCopy {
    const val LOG = "Việc app làm gần đây, để tìm lỗi. Xem lại trước khi gửi."
    const val LOG_NOTE = "Có tên sách; che khoá, mã ghép, IP và đường dẫn nhận ra được. Máy ghép đọc được khi bật “Chia sẻ thư viện”."
    const val SEND = "Bạn chọn gửi cho ai; app không tự gửi."
    const val CLEAR = "Gồm cả các lần văng đã ghi."
    const val CLEARED = "Đã xoá nhật ký."
    const val SOURCE = "Giấy phép MIT - github.com/ntanhpro1221/ABook"

    fun cache(bytes: Long?): String = when {
        bytes == null -> "Đang đo."
        bytes > 0 -> "Bản đọc đã làm chiếm ${Fmt.size(bytes)} trên máy này."
        else -> "Chưa có bản đọc đã lưu."
    }

    fun clearQuestion(bytes: Long): String =
        "Dọn ${Fmt.size(bytes)} bản đọc đã làm của mọi cuốn? Máy sẽ đọc lại khi nghe. Sách và chỗ đang nghe giữ nguyên."
}

/** Nâng cao: bộ nhớ (bản đọc đã làm), chẩn đoán (xem / gửi / xoá nhật ký), giới thiệu (phiên bản, mã nguồn, thành phần bên thứ ba). */
@Composable
fun AdvancedSettings(env: SettingsEnv, sheets: SheetHost, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val repo = env.repo
    val cache by repo.cache.collectAsState()
    var cleared by remember { mutableStateOf(false) }
    LaunchedEffect(repo) { repo.loadCache() }
    SettingsPage(SettingsGroup.Advanced.label, onBack, SettingsGroup.Advanced.screenTag, modifier) {
        ListSection("Bộ nhớ", first = true) {
            val bytes = cache
            ListRow("Bản đọc đã làm", hint = AdvancedCopy.cache(bytes)) {
                if (bytes != null && bytes > 0) {
                    TextAction("Dọn bản đọc", { sheets.show { dismiss -> ClearSheet(bytes, onClear = { repo.clearCache(); dismiss() }, dismiss) } }, "cache_clear")
                }
            }
        }
        ListSection("Chẩn đoán") {
            NavRow("Nhật ký", { sheets.show { LogSheet(repo) } }, "logs_view", AdvancedCopy.LOG)
            RowLine()
            ActionRow("Gửi nhật ký", "Gửi", env.links.shareLogs, "logs_send", AdvancedCopy.SEND)
            RowLine()
            // Việc phá huỷ là hàng thường tên màu nguy hiểm (cả hàng là chỗ chạm): mỗi phần chỉ có một chữ hổ phách.
            ListItem(
                "Xoá nhật ký", onClick = { repo.clearLogs(); cleared = true }, tag = "logs_clear", titleStyle = Abook.type.bodyStrong, titleColor = Abook.colors.danger,
                hint = if (cleared) AdvancedCopy.CLEARED else AdvancedCopy.CLEAR,
            )
        }
        ListSection("Giới thiệu") {
            ListRow("Phiên bản") { BasicText(repo.version, style = Abook.type.bodySmall, modifier = Modifier.testTag("app_version")) }
            RowLine()
            NavRow("Mã nguồn mở", env.links.openSource, "source_open", AdvancedCopy.SOURCE)
            RowLine()
            NavRow("Thành phần sử dụng", { sheets.show { ThirdPartySheet(repo) } }, "third_party")
        }
    }
}

/** Hàng mở một bảng hay trang ngoài: mũi tên cuối hàng, chữ cùng cỡ với các hàng khác của màn này (tên đậm, mô tả nhỏ). */
@Composable
private fun NavRow(title: String, onClick: () -> Unit, tag: String, hint: String? = null) {
    ListItem(title, onClick = onClick, tag = tag, hint = hint, titleStyle = Abook.type.bodyStrong, chevron = true)
}

/** Hỏi lại trước khi dọn (như hộp hỏi của bản WebView): MỘT nút chính "Dọn", "Thôi" là nút chữ. */
@Composable
private fun ClearSheet(bytes: Long, onClear: () -> Unit, dismiss: () -> Unit) {
    Column(Modifier.fillMaxWidth().testTag("clear_sheet")) {
        BasicText("Dọn bản đọc đã làm", style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s4))
        BasicText(AdvancedCopy.clearQuestion(bytes), style = Abook.type.bodySmall)
        Spacer(Modifier.height(Dim.s24))
        PrimaryButton("Dọn", onClear, Modifier.fillMaxWidth().testTag("clear_confirm"))
        Box(Modifier.fillMaxWidth().heightIn(min = Dim.s48).pressable(onClick = dismiss).testTag("clear_cancel"), contentAlignment = Alignment.Center) {
            BasicText("Giữ lại", style = Abook.type.label.copy(color = Abook.colors.accentText))
        }
    }
}

/** Nhật ký của ABook (500 dòng cuối, đã che như bản gửi đi): mới nhất ở dưới, cuộn sẵn tới đó; "Làm mới" đọc lại. Dòng dài xuống dòng. */
@Composable
private fun LogSheet(repo: SettingsRepo) {
    var lines by remember { mutableStateOf<List<String>?>(null) }
    var round by remember { mutableIntStateOf(0) }
    LaunchedEffect(round) { lines = repo.logLines() }
    Column(Modifier.fillMaxWidth().testTag("log_sheet")) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            BasicText("Nhật ký của ABook", style = Abook.type.sectionTitle, modifier = Modifier.weight(1f))
            IconAction("Làm mới", { round++ }, "logs_refresh") { RefreshIcon(Abook.colors.text2) }
        }
        Caption(AdvancedCopy.LOG_NOTE, Modifier.padding(bottom = Dim.s8))
        val shown = lines
        // Mỗi lần đọc một danh sách mới, mở sẵn ở dòng cuối (mới nhất) - không cuộn sau khi đã vẽ.
        val list = remember(shown) { LazyListState(shown?.lastIndex?.coerceAtLeast(0) ?: 0) }
        when {
            shown == null -> BasicText("Đang đọc nhật ký.", style = Abook.type.bodySmall, modifier = Modifier.padding(vertical = Dim.s16))
            shown.isEmpty() -> BasicText("Nhật ký đang trống.", style = Abook.type.bodySmall, modifier = Modifier.padding(vertical = Dim.s16))
            else -> LazyColumn(Modifier.fillMaxWidth().heightIn(max = 440.dp).fadeEdges(list), state = list) {
                itemsIndexed(shown, key = { index, _ -> index }, contentType = { _, _ -> "line" }) { _, line ->
                    BasicText(line, style = Abook.type.caption.copy(color = Abook.colors.text2), modifier = Modifier.padding(vertical = 2.dp))
                }
            }
        }
    }
}

/** "Thành phần sử dụng": docs/THIRD_PARTY.md (gói lúc build, cùng file bản WebView hiện), mỗi mục tiêu đề + các dòng. */
@Composable
private fun ThirdPartySheet(repo: SettingsRepo) {
    var sections by remember { mutableStateOf<List<ThirdPartySection>?>(null) }
    LaunchedEffect(repo) { sections = repo.thirdParty() }
    Column(Modifier.fillMaxWidth().testTag("third_party_sheet")) {
        BasicText("Thành phần sử dụng", style = Abook.type.sectionTitle)
        val shown = sections
        val list = rememberLazyListState()
        when {
            shown == null -> BasicText("Đang mở danh sách", style = Abook.type.bodySmall, modifier = Modifier.padding(vertical = Dim.s16))
            shown.isEmpty() -> BasicText("Chưa mở được danh sách.", style = Abook.type.bodySmall, modifier = Modifier.padding(vertical = Dim.s16))
            else -> LazyColumn(Modifier.fillMaxWidth().heightIn(max = 460.dp).fadeEdges(list), state = list) {
                for ((index, section) in shown.withIndex()) {
                    if (section.title.isNotEmpty()) {
                        item(key = "title:$index", contentType = "title") {
                            BasicText(ThirdParty.plain(section.title), style = Abook.type.label, modifier = Modifier.padding(top = Dim.s16, bottom = Dim.s4))
                        }
                    }
                    itemsIndexed(section.items, key = { line, _ -> "item:$index:$line" }, contentType = { _, _ -> "item" }) { _, item ->
                        Row(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
                            if (item.bullet) BasicText("•  ", style = Abook.type.caption.copy(color = Abook.colors.text2))
                            BasicText(ThirdParty.plain(item.text), style = Abook.type.caption.copy(color = Abook.colors.text2), modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
        }
    }
}
