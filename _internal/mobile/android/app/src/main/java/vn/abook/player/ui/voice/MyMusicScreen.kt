package vn.abook.player.ui.voice

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import vn.abook.player.MusicImport
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.PageHeader
import vn.abook.player.ui.components.UploadIcon
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.devices.DownloadBar
import vn.abook.player.ui.music.MusicText
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * Nhạc của tôi: nhạc riêng của bạn, dùng làm nhạc nền cho mọi cuốn. "Thêm nhạc của bạn" mở hộp chọn file của hệ thống; tiến độ (xong / tổng) chạy ngay hàng ấy. Mỗi bài một hàng
 * (nghệ sĩ · độ dài, cỡ file); chạm một bài mở bảng "Xoá bài". Cùng kho với bản WebView ([vn.abook.player.MusicStore]).
 */
@Composable
fun MyMusicScreen(voice: VoiceState, sheets: SheetHost, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val ui by voice.music.collectAsState()
    LaunchedEffect(voice) { voice.loadMusic() }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris -> voice.importMusic(uris.map(Uri::toString)) }
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    val bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    val colors = Abook.colors
    LazyColumn(
        modifier.fillMaxSize().testTag("music_screen"),
        contentPadding = PaddingValues(top = top, start = Dim.margin, end = Dim.margin, bottom = bottom + Dim.s48),
    ) {
        item(key = "header", contentType = "header") { PageHeader("Nhạc của tôi", onBack) }
        item(key = "add", contentType = "add") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s16)) {
                ListItem(
                    if (ui.importing) "Đang thêm ${ui.done}/${ui.total}" else MusicText.ADD_LABEL, Modifier,
                    if (ui.importing) null else ({ picker.launch(MusicImport.MIME_TYPES) }), "music_add",
                    titleColor = if (ui.importing) colors.text else colors.accentText,
                    leading = { UploadIcon(if (ui.importing) colors.text2 else colors.accentText) },
                    below = if (ui.importing) ({ DownloadBar(voice.importProgress) }) else null,
                )
                RowLine()
                Caption(MusicText.MY_MUSIC_INTRO, Modifier.padding(top = Dim.s8).testTag("music_intro"))
            }
        }
        item(key = "feedback", contentType = "feedback") {
            Column(Modifier.fillMaxWidth()) {
                Reveal(ui.summary.isNotEmpty() && !ui.importing) { Caption(ui.summary, Modifier.padding(top = Dim.s8).testTag("music_summary")) }
                for ((index, problem) in ui.problems.withIndex()) {
                    BasicText(problem, style = Abook.type.bodySmall.copy(color = colors.danger), modifier = Modifier.padding(top = Dim.s8).testTag("music_problem_$index"))
                }
                InlineProblem(if (ui.failed && !ui.loaded) "Bạn hãy thử tải lại nhạc của bạn." else "", voice::loadMusic, "music_load_problem")
            }
        }
        items(ui.tracks, key = { it.link }, contentType = { "track" }) { track ->
            Column(Modifier.fillMaxWidth()) {
                TrackRow(track) { sheets.show { dismiss -> TrackSheet(track, voice, dismiss) } }
                RowLine()
            }
        }
        if (ui.loaded && ui.tracks.isEmpty()) item(key = "empty", contentType = "empty") {
            Caption("Chưa có bài nào", Modifier.padding(top = Dim.s16).testTag("music_empty"))
        }
    }
}
