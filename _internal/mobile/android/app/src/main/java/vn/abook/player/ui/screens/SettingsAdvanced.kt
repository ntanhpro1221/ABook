package vn.abook.player.ui.screens

import vn.abook.player.formatSize

import vn.abook.player.ui.components.ListSection
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.ListRow
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.IconAction
import vn.abook.player.ui.components.RefreshIcon
import vn.abook.player.ui.components.ActionRow
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.Caption
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
import vn.abook.player.ui.components.ConfirmPage
import vn.abook.player.ui.components.DangerButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.keepUrlTogether
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.data.ThirdParty
import vn.abook.player.ui.data.ThirdPartySection
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.components.fadeEdges
import androidx.compose.foundation.lazy.rememberLazyListState

/** Lời của Chẩn đoán và Bộ nhớ. */
private object AdvancedCopy {
    const val LOG = "Việc app làm gần đây, để tìm lỗi. Xem lại trước khi gửi."
    const val LOG_NOTE = "Có tên sách; che khoá, mã ghép, IP và đường dẫn nhận ra được. Máy ghép đọc được khi bật “Chia sẻ thư viện”."
    const val SEND = "Bạn chọn gửi cho ai; app không tự gửi."
    const val CLEAR = "Gồm cả các lần văng đã ghi."
    const val CLEARED = "Đã xoá nhật ký."
    /** Lời hỏi lại trước khi xoá (web: CLEAR_QUESTION ở android/Diagnostics.tsx - cùng từng chữ). */
    const val CLEAR_QUESTION = "Nhật ký của ABook sẽ bị xoá khỏi máy này. $CLEAR"
    val SOURCE = keepUrlTogether("Giấy phép MIT - github.com/ntanhpro1221/ABook")

    fun cache(bytes: Long?): String = when {
        bytes == null -> "Đang đo."
        bytes > 0 -> "Bản đọc đã làm chiếm ${formatSize(bytes)} trên máy này."
        else -> "Chưa có bản đọc đã lưu."
    }

    fun clearQuestion(bytes: Long): String =
        "Dọn ${formatSize(bytes)} bản đọc đã làm của mọi cuốn? Máy sẽ đọc lại khi nghe. Sách và chỗ đang nghe giữ nguyên."
}

/** Nâng cao: bộ nhớ (bản đọc đã làm), chẩn đoán (xem / gửi / xoá nhật ký), giới thiệu (phiên bản, mã nguồn, thành phần bên thứ ba). */
@Composable
fun AdvancedSettings(env: SettingsEnv, sheets: SheetHost, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val repo = env.repo
    val cache by repo.cache.collectAsState()
    val notice by repo.notice.collectAsState()
    LaunchedEffect(repo) { repo.loadCache() }
    SettingsPage(SettingsGroup.Advanced.label, onBack, SettingsGroup.Advanced.screenTag, modifier) {
        MaintenanceSections(env, sheets)
        ListSection("Bộ nhớ", first = true) {
            val bytes = cache
            ListRow("Bản đọc đã làm", hint = AdvancedCopy.cache(bytes)) {
                if (bytes != null && bytes > 0) {
                    TextAction("Dọn bản đọc", { sheets.show { dismiss -> ClearSheet(bytes, onClear = { repo.clearCache(); dismiss() }, dismiss) } }, "cache_clear")
                }
            }
            vn.abook.player.ui.components.MoreInfo("Tìm hiểu thêm", "Nghe lại đoạn đã đọc xong thì không phải chờ máy đọc lại; dọn đi thì lấy lại chỗ trống.", "cache_more")
        }
        ListSection("Chẩn đoán") {
            ActionRow("Nhật ký", "Xem", { sheets.show { LogSheet(repo) } }, "logs_view", AdvancedCopy.LOG)
            vn.abook.player.ui.components.MoreInfo("Tìm hiểu thêm", AdvancedCopy.LOG_NOTE, "logs_more")
            RowLine()
            ActionRow("Gửi nhật ký", "Gửi", env.links.shareLogs, "logs_send", AdvancedCopy.SEND)
            RowLine()
            // Việc phá huỷ là hàng thường tên màu nguy hiểm (cả hàng là chỗ chạm): mỗi phần chỉ có một chữ hổ phách.
            ListItem(
                "Xoá nhật ký", onClick = { sheets.show { dismiss -> ClearLogsSheet({ repo.clearLogs(); dismiss() }, dismiss) } }, tag = "logs_clear", titleStyle = Abook.type.bodyStrong, titleColor = Abook.colors.danger,
                hint = if (notice == "Đã xoá nhật ký") AdvancedCopy.CLEARED else AdvancedCopy.CLEAR,
            )
        }
        ListSection("Giới thiệu") {
            ListRow("Phiên bản") { BasicText(repo.version, style = Abook.type.bodySmall, modifier = Modifier.testTag("app_version")) }
            RowLine()
            ActionRow("Mã nguồn mở", "Mở", env.links.openSource, "source_open", AdvancedCopy.SOURCE)
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

/** Hỏi lại trước khi dọn: bước xác nhận chung [ConfirmPage] - nút đỏ "Dọn", "Giữ lại" là nút chữ. */
@Composable
private fun ClearSheet(bytes: Long, onClear: () -> Unit, dismiss: () -> Unit) {
    ConfirmPage("Dọn bản đọc đã làm", "clear_sheet", listOf(AdvancedCopy.clearQuestion(bytes)), "") {
        DangerButton("Dọn", onClear, "clear_confirm")
        Spacer(Modifier.height(Dim.s8))
        QuietButton("Giữ lại", dismiss, "clear_cancel")
    }
}

/** Hỏi lại trước khi xoá nhật ký (không lấy lại được): cùng bước xác nhận với mọi việc phá huỷ khác. */
@Composable
private fun ClearLogsSheet(onClear: () -> Unit, dismiss: () -> Unit) {
    ConfirmPage("Xoá nhật ký?", "logs_clear_sheet", listOf(AdvancedCopy.CLEAR_QUESTION), "") {
        DangerButton("Xoá", onClear, "logs_clear_confirm")
        Spacer(Modifier.height(Dim.s8))
        QuietButton("Giữ lại", dismiss, "logs_clear_cancel")
    }
}

/** Nhật ký của ABook (500 dòng cuối, đã che như bản gửi đi): mới nhất ở dưới, cuộn sẵn tới đó; "Làm mới" đọc lại. Dòng dài xuống dòng. */
@Composable
private fun LogSheet(repo: SettingsRepo) {
    var lines by remember { mutableStateOf<List<String>?>(null) }
    var round by remember { mutableIntStateOf(0) }
    var problem by remember { mutableStateOf("") }
    LaunchedEffect(round) {
        problem = ""
        try { lines = repo.logLines() }
        catch (e: Exception) { problem = "Không đọc được nhật ký"; lines = emptyList() }
    }
    Column(Modifier.fillMaxWidth().testTag("log_sheet")) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            BasicText("Nhật ký của ABook", style = Abook.type.sectionTitle, modifier = Modifier.weight(1f))
            IconAction("Làm mới", { round++ }, "logs_refresh") { RefreshIcon(Abook.colors.text2) }
        }
        Caption(AdvancedCopy.LOG_NOTE, Modifier.padding(bottom = Dim.s8))
        vn.abook.player.ui.components.Reveal(problem.isNotEmpty()) { Caption(problem) }
        val shown = lines
        // Mỗi lần đọc một danh sách mới, mở sẵn ở dòng cuối (mới nhất) - không cuộn sau khi đã vẽ.
        val list = remember(shown) { LazyListState(shown?.lastIndex?.coerceAtLeast(0) ?: 0) }
        when {
            shown == null -> BasicText("Đang đọc nhật ký.", style = Abook.type.bodySmall, modifier = Modifier.padding(vertical = Dim.s16))
            shown.isEmpty() -> BasicText("Chưa có dòng nào.", style = Abook.type.bodySmall, modifier = Modifier.padding(vertical = Dim.s16))
            else -> LazyColumn(Modifier.fillMaxWidth().heightIn(max = 440.dp).fadeEdges(list), state = list) {
                itemsIndexed(shown, key = { index, _ -> index }, contentType = { _, _ -> "line" }) { _, line ->
                    BasicText(line, style = Abook.type.caption.copy(color = Abook.colors.text2), modifier = Modifier.padding(vertical = 2.dp))
                }
            }
        }
    }
}

/** "Thành phần sử dụng": docs/THIRD_PARTY.md (gói lúc build), mỗi mục tiêu đề + các dòng. */
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
