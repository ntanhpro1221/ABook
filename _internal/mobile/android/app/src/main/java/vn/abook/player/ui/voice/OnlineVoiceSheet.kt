package vn.abook.player.ui.voice

import vn.abook.player.S

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import vn.abook.player.ui.components.BasicText
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import vn.abook.player.ui.components.ConfirmPage
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.components.WorkingProgress
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

private enum class AskPage { Ask, Choose }

private val NoSample: StateFlow<SampleUi> = MutableStateFlow(SampleUi())

/**
 * Bảng hỏi trước lần đầu đọc bằng giọng trực tuyến (listen/OnlineVoicePrompt.tsx): nói chữ đi tới đâu, "Nghe" là đồng ý và nghe tiếp, "Chọn giọng khác" mở danh sách giọng ngay trong bảng
 * (mỗi giọng nghe thử được; chọn một giọng là chọn cho cuốn này, giọng trực tuyến thì cũng là đồng ý cho nhà cung cấp ấy). Đóng bảng (chạm nền, kéo xuống, Back) là không phát.
 * `requests`: luồng câu hỏi của cửa - câu này rời đi (đã trả lời, hay bị lệnh khác thay) thì bảng tự đóng. `voice` null: chưa có nghe thử. `openVoiceSettings`: tới Cài đặt > Giọng đọc.
 */
@Composable
fun OnlineVoiceSheet(
    request: ConsentRequest, requests: StateFlow<ConsentRequest?>, voice: VoiceState?, openVoiceSettings: () -> Unit, dismiss: () -> Unit,
) {
    var page by remember { mutableStateOf(AskPage.Ask) }
    BackHandler(enabled = page == AskPage.Choose) { page = AskPage.Ask }
    LaunchedEffect(request) {
        requests.first { it !== request }
        dismiss()
    }
    DisposableEffect(request) {
        onDispose {
            voice?.stopSample()
            request.answer(null)
        }
    }
    SheetPages(page, { it.ordinal }, "online_voice_sheet") { shown ->
        when (shown) {
            AskPage.Ask -> ConfirmPage(S.s_giong_doc_truc_tuyen_44ae53c1, "online_voice_ask", listOf(VoiceText.consent(request.voice.name, request.voice.provider)), "") {
                PrimaryButton(S.s_nghe_a43aafef, { request.answer(request.voice) }, Modifier.fillMaxWidth().testTag("online_voice_listen"))
                Spacer(Modifier.height(Dim.s8))
                QuietButton(S.s_chon_giong_khac_d31cfe89, { page = AskPage.Choose }, "online_voice_choose")
            }
            AskPage.Choose -> ChoosePage(request, voice, openVoiceSettings)
        }
    }
}

/** Bước "Chọn giọng đọc": mỗi giọng một hàng (chạm là chọn), nút nghe thử ở cuối hàng, và đường tới nơi tải giọng chạy trên máy. */
@Composable
private fun ChoosePage(request: ConsentRequest, voice: VoiceState?, openVoiceSettings: () -> Unit) {
    val sample by (voice?.sample ?: NoSample).collectAsState()
    val scroll = rememberScrollState()
    Column(Modifier.fillMaxWidth().testTag("online_voice_list")) {
        BasicText(S.s_chon_giong_doc_a3941a79, style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s8))
        BasicText(OnlineConsent.chooseText(request.voices, request.voice), style = Abook.type.body.copy(color = Abook.colors.text2))
        Spacer(Modifier.height(Dim.s8))
        Column(Modifier.fillMaxWidth().heightIn(max = 360.dp).fadeEdges(scroll).verticalScroll(scroll)) {
            for (item in request.voices) {
                val playing = sample.playing == item.id || sample.loading == item.id
                val failure = sample.failed?.takeIf { it.voice == item.id }?.message
                val current = item.id == request.voice.id
                ListItem(
                    VoiceText.spokenName(item.name), Modifier,
                    onClick = {
                        voice?.stopSample()
                        request.answer(item, chosen = true)
                    },
                    tag = "online_voice_${item.id}",
                    hint = failure ?: OnlineConsent.tag(item, request.voice.id),
                    hintColor = if (failure != null) Abook.colors.danger else Abook.colors.text2,
                    titleColor = if (current) Abook.colors.accentText else Abook.colors.text,
                    trailing = if (voice == null) null else ({
                        TextAction(
                            if (playing) S.s_dung_11554138 else S.s_nghe_thu_fa024065, { voice.play(item.id) }, "online_voice_sample_${item.id}",
                            Modifier.semantics { contentDescription = OnlineConsent.sampleLabel(playing, item.name) },
                        )
                    }),
                    below = if (sample.loading == item.id) ({ WorkingProgress() }) else null,
                    role = Role.RadioButton,
                )
                RowLine()
            }
            // Danh sách chỉ có giọng ĐANG dùng được; giọng chạy trên máy chưa tải thì không có mặt - chỉ đường tới nơi tải, hộp chưa phát gì.
            ListItem(
                S.s_tai_giong_ve_may_62bb0900, Modifier, onClick = {
                    voice?.stopSample()
                    request.answer(null)
                    openVoiceSettings()
                },
                tag = "online_voice_download", hint = S.s_vieneu_supertonic_doc_duoc_ca_khi_khong_co_68472ba2, titleColor = Abook.colors.accentText,
            )
        }
    }
}
