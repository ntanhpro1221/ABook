package vn.abook.player.ui.screens

import vn.abook.player.ui.components.PageHeader
import vn.abook.player.ui.components.ListSection
import vn.abook.player.ui.components.ListRow
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.ChoiceSetting
import vn.abook.player.ui.components.DisclosureRow
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SectionTitle
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.InlineProblem
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.data.VoiceList
import vn.abook.player.ui.data.VoiceOption
import vn.abook.player.ui.data.VoiceSpeedChoice
import vn.abook.player.ui.devices.CreepProgress
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.voice.ConsentSheet
import vn.abook.player.ui.voice.MeteredSheet
import vn.abook.player.ui.voice.ModuleAction
import vn.abook.player.ui.voice.ModuleChoiceRow
import vn.abook.player.ui.voice.ModuleKind
import vn.abook.player.ui.voice.ModuleSheet
import vn.abook.player.ui.voice.ModuleSuggestion
import vn.abook.player.ui.voice.ModuleUi
import vn.abook.player.ui.voice.SampleButton
import vn.abook.player.ui.voice.SampleUi
import vn.abook.player.ui.voice.VoicePage
import vn.abook.player.ui.voice.VoiceState
import vn.abook.player.ui.voice.VoiceSummary
import vn.abook.player.ui.voice.VoiceText
import vn.abook.player.ui.components.fadeEdges
import androidx.compose.foundation.lazy.rememberLazyListState

/** Máy chưa có giọng tiếng Việt của hệ điều hành (như `deviceHint` của bản WebView). */
private const val DEVICE_HINT = "Điện thoại chưa có giọng tiếng Việt. Cài ở Cài đặt điện thoại › Chuyển văn bản thành giọng nói."

private val NoSample: StateFlow<SampleUi> = MutableStateFlow(SampleUi())
private val NoModules: StateFlow<Map<ModuleKind, ModuleUi>> = MutableStateFlow(emptyMap())
private val NoSummary: StateFlow<VoiceSummary> = MutableStateFlow(VoiceSummary())

/**
 * Giọng đọc: giọng mặc định của "Nghe ngay" (cuốn chưa chọn giọng riêng), xếp theo nơi đọc, mỗi giọng có nút nghe thử ở cuối hàng (nơi bạn đang chọn); tốc độ đọc của giọng
 * trên máy; giọng tải về máy (VieNeu, Supertonic) và khoá giọng trực tuyến. Danh sách giọng có thể dài (giọng của máy) nên cả màn là MỘT danh sách lười, mỗi giọng một mục có khoá.
 * `env.voice` null (ảnh chụp không có lõi): danh sách giọng vẫn dựng, chưa có nghe thử, giọng tải về hay khoá.
 */
@Composable
fun VoiceSettings(env: SettingsEnv, sheets: SheetHost, openVoice: (VoicePage) -> Unit, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val repo = env.repo
    val voice = env.voice
    val voices by repo.voices.collectAsState()
    val speed by repo.speed.collectAsState()
    val sample by (voice?.sample ?: NoSample).collectAsState()
    val modules by (voice?.modules ?: NoModules).collectAsState()
    val summary by (voice?.summary ?: NoSummary).collectAsState()
    LaunchedEffect(repo) {
        if (repo.voices.value !is VoiceList.Ready) repo.loadVoices()
        repo.loadSpeed()
    }
    LaunchedEffect(voice) { voice?.openVoice() }
    // Rời màn thì mẫu đang phát dừng ngay.
    DisposableEffect(voice) { onDispose { voice?.stopSample() } }

    /** Chọn giọng mặc định; giọng trực tuyến chưa được bạn đồng ý gửi chữ thì hỏi trước, "Không" giữ giọng cũ. */
    fun choose(option: VoiceOption) {
        if (voice != null && VoiceText.isOnline(option.provider) && !voice.allowed(option.provider)) {
            sheets.show { dismiss ->
                ConsentSheet(option.name, option.provider, { voice.allow(option.provider); repo.chooseVoice(option.id) }, dismiss)
            }
        } else {
            repo.chooseVoice(option.id)
        }
    }

    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    val bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    val scroll = rememberLazyListState()
    LazyColumn(
        modifier.fillMaxSize().testTag(SettingsGroup.Voice.screenTag).fadeEdges(scroll),
        state = scroll,
        contentPadding = PaddingValues(top = top, start = Dim.margin, end = Dim.margin, bottom = bottom + Dim.s48),
    ) {
        item(key = "header", contentType = "header") { PageHeader(SettingsGroup.Voice.label, onBack) }
        when (val list = voices) {
            VoiceList.Loading -> item(key = "loading", contentType = "loading") { VoiceSkeleton() }
            VoiceList.Failed -> item(key = "failed", contentType = "failed") {
                ListRow("Chưa tải được giọng", hint = "Bạn hãy kiểm tra kết nối rồi tải lại giọng đọc.") {
                    TextAction("Thử lại", repo::loadVoices, "voices_retry")
                }
            }
            is VoiceList.Ready -> {
                item(key = "current", contentType = "current") {
                    BasicText(
                        "Đang dùng: ${list.chosenVoice?.name ?: "giọng mặc định"}",
                        style = Abook.type.bodyStrong,
                        modifier = Modifier.padding(top = Dim.s16).testTag("voice_current"),
                    )
                }
                for (group in list.groups) {
                    item(key = "group:${group.provider}", contentType = "group") {
                        val detail = if (group.detail.isEmpty()) "${group.voices.size} giọng" else "${group.detail} · ${group.voices.size} giọng"
                        Column(Modifier.fillMaxWidth().padding(top = Dim.s24, bottom = Dim.s4)) {
                            BasicText(group.title, style = Abook.type.sectionTitle)
                            RowHint(detail)
                        }
                    }
                    items(group.voices, key = { "voice:${it.id}" }, contentType = { "voice" }) { option ->
                        Column(Modifier.fillMaxWidth()) {
                            VoiceRow(
                                option, option.id == list.chosen, canHear = voice != null,
                                loading = sample.loading == option.id, playing = sample.playing == option.id,
                                failure = sample.failed?.takeIf { it.voice == option.id }?.message,
                                onChoose = { if (option.id != list.chosen) choose(option) }, onHear = { voice?.play(option.id) },
                            )
                        }
                    }
                }
                if (list.groups.none { it.provider == "device" }) {
                    item(key = "device_hint", contentType = "hint") {
                        Column(Modifier.fillMaxWidth().padding(top = Dim.s24)) {
                            BasicText("Giọng của máy", style = Abook.type.sectionTitle)
                            RowHint(DEVICE_HINT)
                        }
                    }
                }
            }
        }
        item(key = "speed", contentType = "speed") {
            Reveal(speed != null) {
                val state = speed ?: return@Reveal
                ListSection("Hiệu năng") {
                    ChoiceSetting(
                        "Tốc độ đọc", VoiceSpeedChoice.entries, state.choice,
                        { choice, _ -> repo.chooseSpeed(choice) }, "voice_speed",
                    )
                    for (line in state.lines) {
                        BasicText(line, style = Abook.type.caption.copy(color = Abook.colors.text2), modifier = Modifier.padding(top = Dim.s4))
                    }
                }
            }
        }
        if (voice != null) {
            for (kind in ModuleKind.entries) moduleItems(kind, modules[kind] ?: ModuleUi(), voice, sheets)
            item(key = "keys", contentType = "keys") {
                ListSection {
                    DisclosureRow("Khoá trực tuyến", { openVoice(VoicePage.Keys) }, "voice_keys", summary = summary.keys)
                }
            }
        }
    }
}

/**
 * Một mô-đun giọng chạy trên máy: tiêu đề, mỗi lựa chọn một hàng (cỡ cần tải, tiến độ, tốc độ máy đo được), và - khi giọng vừa tải đọc chậm hơn tốc độ nghe - một lời đề nghị
 * có một việc để làm. Chưa biết trạng thái thì chưa dựng gì.
 */
private fun LazyListScope.moduleItems(kind: ModuleKind, ui: ModuleUi, voice: VoiceState, sheets: SheetHost) {
    val status = ui.shown ?: return
    item(key = "module_title:${kind.key}", contentType = "title") { SectionTitle(kind.title) }
    val rows = VoiceText.rows(status, ui.pending)
    items(rows, key = { "module:${kind.key}:${it.id}" }, contentType = { "module" }) { row ->
        val choice = status.choice(row.id)
        Column(Modifier.fillMaxWidth()) {
            ModuleChoiceRow(
                kind, row, { voice.progress(kind) },
                onOpen = if (choice != null && (row.action == ModuleAction.Manage || VoiceText.hasLeftovers(choice))) {
                    { sheets.show { dismiss -> ModuleSheet(kind, choice, voice, dismiss) } }
                } else null,
                onAction = {
                    when (row.action) {
                        is ModuleAction.Download -> {
                            val warn = VoiceText.metered(status, choice?.bytes ?: 0)
                            if (warn != null) sheets.show { dismiss -> MeteredSheet(warn, { voice.download(kind, listOf(row.id)) }, dismiss) }
                            else voice.download(kind, listOf(row.id))
                        }
                        ModuleAction.Cancel -> voice.cancel(kind)
                        ModuleAction.Retry -> voice.retry(kind)
                        ModuleAction.Manage, ModuleAction.None -> Unit
                    }
                },
            )
            RowLine()
        }
    }
    status.suggestion?.let { suggestion -> item(key = "suggestion:${kind.key}", contentType = "suggestion") { SuggestionBlock(kind, suggestion, voice) } }
}

/** Lời đề nghị đổi giọng (không bao giờ tự đổi): một câu nói vì sao, một việc để làm; lỗi hiện ngay dưới. */
@Composable
private fun SuggestionBlock(kind: ModuleKind, suggestion: ModuleSuggestion, voice: VoiceState) {
    val scope = rememberCoroutineScope()
    var problem by remember { mutableStateOf("") }
    val (text, label) = remember(suggestion) { VoiceText.suggestion(suggestion) }
    Column(Modifier.fillMaxWidth().padding(top = Dim.s8).testTag("suggestion_${kind.key}")) {
        Caption(text)
        TextAction(label, { scope.launch { problem = voice.applySuggestion(kind).orEmpty() } }, "suggestion_${kind.key}_action", align = Alignment.CenterStart)
        InlineProblem(problem, null, "suggestion_${kind.key}_problem")
    }
}

/**
 * Một giọng trong danh sách chọn: dấu tích ĐẦU dòng (luôn giữ chỗ, nở / thu tại chỗ - không mờ) + tên; giọng đang chọn chữ hổ phách (DESIGN.md §6 "Hàng danh
 * sách"). Tên dài xuống dòng. Nút nghe thử ở cuối dòng đầu - ngay chỗ bạn quyết; đang lấy mẫu thì thanh tiến độ chạy dưới tên, mẫu không nghe được thì dòng đỏ kèm "Thử lại".
 */
@Composable
private fun VoiceRow(
    voice: VoiceOption, chosen: Boolean, canHear: Boolean, loading: Boolean, playing: Boolean, failure: String?, onChoose: () -> Unit, onHear: () -> Unit,
) {
    val colors = Abook.colors
    val mark by animateFloatAsState(if (chosen) 1f else 0f, Motion.Expand, label = "mark")
    val trailing: (@Composable () -> Unit)? = when {
        !canHear -> null
        failure != null -> ({ TextAction("Thử lại", onHear, "sample_retry_${voice.id}") })
        else -> ({ SampleButton(loading || playing, "Nghe thử ${voice.name}", "sample_${voice.id}", onHear) })
    }
    ListItem(
        voice.name, Modifier.semantics { selected = chosen }, onChoose, "voice_${voice.id}",
        hint = failure ?: if (loading) "Đang lấy giọng" else null,
        hintColor = if (failure != null) colors.danger else colors.text2,
        titleColor = if (chosen) colors.accentText else colors.text,
        leading = {
            Box(Modifier.size(Dim.s24).graphicsLayer { scaleX = mark; scaleY = mark }, contentAlignment = Alignment.CenterStart) {
                CheckIcon(colors.accentText)
            }
        },
        trailing = trailing,
        below = if (loading) ({ CreepProgress() }) else null,
        role = Role.RadioButton,
    )
}

/** Đang hỏi giọng: khung xám đúng hình ba hàng giọng (DESIGN.md §2 "đang tải"), không vòng xoay. */
@Composable
private fun VoiceSkeleton() {
    Column(Modifier.fillMaxWidth().padding(top = Dim.s24).testTag("voices_loading")) {
        for (width in SkeletonWidths) {
            Row(Modifier.fillMaxWidth().height(Dim.s48), verticalAlignment = Alignment.CenterVertically) {
                Spacer(Modifier.size(Dim.s24))
                Box(Modifier.fillMaxWidth(width).height(14.dp).clip(RoundedCornerShape(Dim.radiusControl)).background(Abook.colors.bgSunken))
            }
        }
    }
}

private val SkeletonWidths = floatArrayOf(0.5f, 0.38f, 0.44f)
