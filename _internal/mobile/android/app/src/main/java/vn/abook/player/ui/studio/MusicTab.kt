package vn.abook.player.ui.studio

import vn.abook.player.ui.data.dotJoined
import vn.abook.player.ui.components.fadeEdges
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.ClipState
import vn.abook.player.StudioPolling
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.ClockLabel
import vn.abook.player.ui.components.ConfirmPage
import vn.abook.player.ui.components.DisclosureRow
import vn.abook.player.ui.components.Fold
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.MenuRow
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.StageProgress
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.music.MusicLevels
import vn.abook.player.ui.music.MusicText
import vn.abook.player.ui.screens.PickRow
import vn.abook.player.ui.studio.parts.ClipButton
import vn.abook.player.ui.studio.parts.ClipProblem
import vn.abook.player.ui.studio.parts.collectClip
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** Những gì tab "Nhạc nền" đọc từ các luồng (lần hỏi gần nhất, tiếng đang phát). */
@Immutable
class MusicData(val poll: StudioPolling.Poll<MusicView>, val clip: ClipState)

@Composable
internal fun rememberMusicData(music: StudioMusicState): MusicData {
    val poll by music.poll.collectAsState()
    return MusicData(poll, music.clip.collectClip())
}

/**
 * Tab "Nhạc nền" (NATIVE_REMOTE_STUDIO.md §6.7): đầu tab là công tắc, thể loại, mức nhạc, "Chọn lại nhạc"; rồi tiến độ tải sẵn (có "Huỷ tải"), các đoạn theo chương -
 * mỗi đoạn một bài đang dùng, nghe thử và "Đổi bài". "Đọc không khí cả đoạn bằng AI" nằm trong "Nâng cao", chỉ khi máy tính đã có model. Nhạc riêng nằm trên máy tính nên
 * không có ở đây.
 */
internal fun LazyListScope.musicTab(music: StudioMusicState, data: MusicData, chapters: List<StudioChapter>, sheets: SheetHost, slide: Modifier) {
    val view = data.poll.data
    item("music_notice", "music_notice") {
        Column(Modifier.fillMaxWidth().then(slide)) {
            InlineProblem(music.problem.ifEmpty { data.poll.error?.let { StudioText.failure(it) }.orEmpty() }, music::refreshSoon, "studio_music_problem")
            if (music.notice.isNotEmpty()) RowHint(music.notice, Modifier.padding(top = Dim.s8).testTag("studio_music_notice"))
            ClipProblem(data.clip)
        }
    }
    if (view == null) {
        if (data.poll.error == null) item("music_loading", "status") {
            BasicText(StudioMusicText.LOADING, style = Abook.type.body.copy(color = Abook.colors.text2), modifier = Modifier.then(slide).padding(top = Dim.s24).testTag("studio_music_loading"))
        }
        return
    }
    item("music_settings", "music_settings") { Settings(music, view, sheets, slide) }
    view.download?.takeIf { it.active }?.let { download ->
        item("music_download", "music_download") {
            Column(Modifier.fillMaxWidth().then(slide).padding(top = Dim.s12).testTag("studio_music_download")) {
                ClockLabel(MusicLogic.downloadText(download), Modifier.testTag("studio_music_download_text"), Abook.type.bodySmall.copy(color = Abook.colors.text2))
                StageProgress { MusicLogic.downloadShare(download) }
                TextAction(StudioMusicText.CANCEL_DOWNLOAD, music::cancelDownload, "studio_music_download_cancel", Modifier.fillMaxWidth())
            }
        }
    }
    if (view.banned.isNotEmpty()) item("music_banned", "music_banned") {
        Fold(StudioMusicText.banned(view.banned.size), "studio_music_banned", Modifier.then(slide).padding(top = Dim.s12)) {
            for (link in view.banned) {
                ListItem(
                    MusicLogic.trackLabel(link, view.bannedTracks[link] ?: view.tracks[link]), Modifier, null, null,
                    trailing = { TextAction(StudioMusicText.UNBAN, { music.change(MusicLogic.unban(link)) }, "studio_music_unban_${link.hashCode()}") },
                )
                RowLine()
            }
        }
    }
    if (music.moodsModel?.installed == true) item("music_moods", "music_moods") {
        Fold(StudioMusicText.ADVANCED, "studio_music_advanced", Modifier.then(slide).padding(top = Dim.s12)) {
            BasicText(StudioMusicText.MOODS, style = Abook.type.bodyStrong)
            RowHint(StudioMusicText.MOODS_LEAD, Modifier.padding(top = Dim.s4))
            TextAction(
                if (view.moodsRunning) StudioMusicText.MOODS_RUNNING else StudioMusicText.MOODS_RUN, { if (!view.moodsRunning) music.computeMoods() },
                "studio_music_moods_run", Modifier.fillMaxWidth(), Alignment.CenterStart,
            )
            if (view.moodsError.isNotEmpty()) RowHint(view.moodsError, Modifier.testTag("studio_music_moods_error"), Abook.colors.danger)
        }
    }
    if (view.error.isNotEmpty()) item("music_error", "status") { RowHint(view.error, Modifier.then(slide).padding(top = Dim.s12).testTag("studio_music_error"), Abook.colors.danger) }
    if (!view.enabled && view.scenes.isNotEmpty()) item("music_off", "status") { RowHint(StudioMusicText.OFF_NOTE, Modifier.then(slide).padding(top = Dim.s12).testTag("studio_music_off")) }
    if (view.scenes.isEmpty()) {
        item("music_empty", "status") { RowHint(StudioMusicText.NO_SCENES, Modifier.then(slide).padding(top = Dim.s12).testTag("studio_music_empty")) }
    } else {
        val byChapter = view.scenes.groupBy { it.chapterId }
        items(byChapter.entries.toList(), key = { "music_chapter_${it.key}" }, contentType = { "music_chapter" }) { (chapterId, scenes) ->
            val title = chapters.firstOrNull { it.id == chapterId }?.title ?: "Chương $chapterId"
            Fold(title, "studio_music_chapter_$chapterId", Modifier.then(slide).padding(top = Dim.s12), summary = "${scenes.size}") {
                scenes.forEachIndexed { index, scene -> SceneRow(music, view, scenes, index, data.clip, sheets) }
            }
        }
    }
    if (view.tracks.isNotEmpty()) item("music_credits", "music_credits") {
        Fold("${StudioMusicText.CREDITS} (${view.tracks.size})", "studio_music_credits", Modifier.then(slide).padding(top = Dim.s12)) {
            for ((link, track) in view.tracks) Caption(MusicLogic.creditText(link, track), Modifier.padding(bottom = Dim.s8))
            if (MusicLogic.needsModifiedNote(view)) Caption(MusicText.MODIFIED_NOTE, Modifier.padding(bottom = Dim.s8))
        }
    }
}

/** Đầu tab: bật / tắt, thể loại, mức nhạc, chọn lại. Việc đang chạy thì các hàng nhạt đi (không chặn bằng chữ xám). */
@Composable
private fun Settings(music: StudioMusicState, view: MusicView, sheets: SheetHost, slide: Modifier) {
    val genreName = view.genres.firstOrNull { it.first == view.genre }?.second ?: StudioMusicText.GENRE_NONE
    Column(Modifier.fillMaxWidth().then(slide).testTag("studio_music_settings")) {
        SwitchRow(
            StudioMusicText.ENABLED, view.enabled, { music.change(MusicLogic.enabled(it)) }, "studio_music_enabled",
            hint = if (view.enabled) StudioMusicText.ENABLED_ON else StudioMusicText.ENABLED_OFF,
        )
        RowLine()
        DisclosureRow(
            StudioMusicText.GENRE, { sheets.show { dismiss -> GenreSheet(music, view, dismiss) } }, "studio_music_genre",
            summary = genreName,
        )
        RowLine()
        DisclosureRow(
            StudioMusicText.LEVEL, { sheets.show { dismiss -> LevelSheet(music, view, dismiss) } }, "studio_music_level",
            summary = MusicLevels.label(view.levelDb),
        )
        RowLine()
        ListItem(
            StudioMusicText.REBUILD, Modifier, { sheets.show { dismiss -> RebuildSheet(music, dismiss) } }, "studio_music_rebuild",
            hint = StudioMusicText.REBUILD_HINT, chevron = true,
        )
        RowLine()
        if (music.busy.isNotEmpty()) RowHint(music.busy, Modifier.padding(top = Dim.s8).testTag("studio_music_busy"))
    }
}

@Composable
private fun GenreSheet(music: StudioMusicState, view: MusicView, dismiss: () -> Unit) {
    Column(Modifier.fillMaxWidth().testTag("studio_music_genre_sheet")) {
        BasicText(StudioMusicText.CHOSEN_TITLE, style = Abook.type.sectionTitle)
        RowHint(StudioMusicText.GENRE_HINT, Modifier.padding(top = Dim.s4, bottom = Dim.s8))
        val list1 = rememberLazyListState()
        LazyColumn(Modifier.heightIn(max = 420.dp).fadeEdges(list1), state = list1) {
            item("genre_none") { PickRow(StudioMusicText.GENRE_NONE, null, view.genre == null, { dismiss(); music.change(MusicLogic.genre(null)) }, "studio_genre_none") }
            items(view.genres, key = { "genre_${it.first}" }) { (code, name) ->
                PickRow(name, null, view.genre == code, { dismiss(); music.change(MusicLogic.genre(code)) }, "studio_genre_$code")
            }
        }
    }
}

@Composable
private fun LevelSheet(music: StudioMusicState, view: MusicView, dismiss: () -> Unit) {
    Column(Modifier.fillMaxWidth().testTag("studio_music_level_sheet")) {
        BasicText(StudioMusicText.LEVEL, style = Abook.type.sectionTitle)
        RowHint(StudioMusicText.LEVEL_HINT, Modifier.padding(top = Dim.s4, bottom = Dim.s8))
        for ((db, name) in MusicLevels.options(view.levelDb)) {
            PickRow(name, null, db == view.levelDb, { dismiss(); music.change(MusicLogic.level(db)) }, "studio_level_${db.toInt()}")
        }
    }
}

@Composable
private fun RebuildSheet(music: StudioMusicState, dismiss: () -> Unit) {
    ConfirmPage(StudioMusicText.REBUILD_TITLE, "studio_music_rebuild_sheet", listOf(StudioMusicText.REBUILD_LINE), "") {
        PrimaryButton(StudioMusicText.REBUILD, { dismiss(); music.rebuild() }, Modifier.fillMaxWidth().testTag("studio_music_rebuild_confirm"))
        QuietButton("Để sau", dismiss, "studio_music_rebuild_later")
    }
}

/** Một đoạn nhạc: giờ, không khí, bài đang dùng (nghe thử được), "Đổi bài" và "Thêm" (im lặng, bỏ ghim, loại bài khỏi cuốn). */
@Composable
private fun SceneRow(music: StudioMusicState, view: MusicView, scenes: List<MusicScene>, index: Int, clip: ClipState, sheets: SheetHost) {
    val scene = scenes[index]
    val track = scene.link?.let { view.tracks[it] }
    val follows = MusicLogic.isContinuation(scene)
    val link = scene.link
    Column(Modifier.fillMaxWidth().padding(vertical = Dim.s8).testTag("studio_music_scene_${scene.key}")) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            ClockLabel(MusicLogic.range(scenes, index), Modifier.testTag("studio_music_range"), Abook.type.bodySmall.copy(color = Abook.colors.text2))
            BasicText(
                "  ${MusicLogic.moodOf(scene, view.emotionNames)}${if (MusicLogic.byAi(scene)) " · ${StudioMusicText.AI}" else ""}",
                style = Abook.type.bodySmall.copy(color = Abook.colors.text2), modifier = Modifier.testTag("studio_music_mood"),
            )
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                when {
                    follows -> RowHint(StudioMusicText.CONTINUED, Modifier.testTag("studio_music_continued"))
                    link != null -> {
                        BasicText(
                            track?.let { MusicLogic.trackLabel(link, it) } ?: StudioMusicText.TRACK, style = Abook.type.body,
                            modifier = Modifier.padding(top = Dim.s4).testTag("studio_music_track"),
                        )
                        if (scene.pinned) Caption(StudioMusicText.PINNED, Modifier.testTag("studio_music_pinned"))
                        if (scene.pinUnavailable) RowHint(StudioMusicText.PIN_GONE, Modifier.testTag("studio_music_pin_gone"), Abook.colors.danger)
                    }
                    else -> RowHint(if (scene.silenced) StudioMusicText.SILENT_CHOSEN else StudioMusicText.SILENT_AUTO, Modifier.padding(top = Dim.s4).testTag("studio_music_silent"))
                }
            }
            if (link != null && !follows) ClipButton(StudioMusicState.trackClip(link), clip, { music.playTrack(link) }, "studio_music_play_${scene.key}")
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(Dim.s8), verticalAlignment = Alignment.CenterVertically) {
            TextAction(MusicLogic.swapText(scene), { sheets.show { dismiss -> AlternativesSheet(music, scene, dismiss) } }, "studio_music_swap_${scene.key}", align = Alignment.CenterStart)
            if (!follows) TextAction(StudioMusicText.MORE, { sheets.show { dismiss -> SceneMenu(music, view, scene, dismiss) } }, "studio_music_more_${scene.key}", align = Alignment.CenterStart)
        }
        RowLine()
    }
}

/** "Thêm" của một đoạn: im lặng / có nhạc, bỏ ghim (khi đã ghim), loại bài đang dùng khỏi cả cuốn (có báo trước số đoạn đang dùng bài ấy). */
@Composable
private fun SceneMenu(music: StudioMusicState, view: MusicView, scene: MusicScene, dismiss: () -> Unit) {
    Column(Modifier.fillMaxWidth().testTag("studio_music_scene_menu")) {
        MenuRow(if (scene.silenced) StudioMusicText.SILENCE_OFF else StudioMusicText.SILENCE_ON, "studio_scene_silence", onClick = { dismiss(); music.change(MusicLogic.silence(scene.key, !scene.silenced)) }) { }
        if (scene.pinned) MenuRow(StudioMusicText.UNPIN, "studio_scene_unpin", onClick = { dismiss(); music.change(MusicLogic.unpin(scene.key)) }) { }
        scene.link?.let { link ->
            val used = MusicLogic.usedIn(view, link)
            MenuRow(
                StudioMusicText.BAN, "studio_scene_ban", danger = true, hint = "Đang dùng ở $used đoạn",
                onClick = { dismiss(); music.change(MusicLogic.ban(link)) },
            ) { }
        }
    }
}

/** "Đổi bài": các bài khác hợp đoạn này, hợp nhất trước. Chọn = ghim bài ấy cho đoạn; "Nghe thử" ~20 giây, không tự phát. */
@Composable
private fun AlternativesSheet(music: StudioMusicState, scene: MusicScene, dismiss: () -> Unit) {
    var items by remember { mutableStateOf<List<MusicAlternative>?>(null) }
    var problem by remember { mutableStateOf("") }
    LaunchedEffect(scene.key) {
        try {
            items = music.alternatives(scene)
        } catch (cancelled: kotlinx.coroutines.CancellationException) {
            throw cancelled
        } catch (error: Throwable) {
            problem = StudioText.failure(vn.abook.player.StudioErrors.of(error))
        }
    }
    val clip = music.clip.collectClip()
    Column(Modifier.fillMaxWidth().testTag("studio_music_alt_sheet")) {
        BasicText(MusicLogic.swapText(scene), style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s8))
        InlineProblem(problem, null, "studio_music_alt_problem")
        val loaded = items
        when {
            loaded == null && problem.isEmpty() -> RowHint(StudioMusicText.ALT_LOADING, Modifier.testTag("studio_music_alt_loading"))
            loaded != null && loaded.isEmpty() -> RowHint(StudioMusicText.ALT_EMPTY, Modifier.testTag("studio_music_alt_empty"))
            loaded != null -> {
                val list2 = rememberLazyListState()
                LazyColumn(Modifier.heightIn(max = 420.dp).fadeEdges(list2), state = list2) {
                    items(loaded, key = { "alt_${it.link}" }) { alt ->
                        Column(Modifier.fillMaxWidth().padding(vertical = Dim.s8).testTag("studio_music_alt_${alt.link.hashCode()}")) {
                            BasicText(listOf(alt.title.ifEmpty { StudioMusicText.TRACK }, alt.creator).dotJoined(), style = Abook.type.body)
                            if (alt.duration > 0) ClockLabel(Fmt.clock(alt.duration), Modifier, Abook.type.bodySmall.copy(color = Abook.colors.text2))
                            Row(horizontalArrangement = Arrangement.spacedBy(Dim.s8), verticalAlignment = Alignment.CenterVertically) {
                                val active = clip.playing == StudioMusicState.trackClip(alt.link) || clip.loading == StudioMusicState.trackClip(alt.link)
                                TextAction(if (active) StudioMusicText.STOP else StudioMusicText.PLAY, { music.playTrack(alt.link) }, "studio_alt_play_${alt.link.hashCode()}", align = Alignment.CenterStart)
                                TextAction(StudioMusicText.CHOOSE, { music.release(); dismiss(); music.change(MusicLogic.pin(scene, alt.link)) }, "studio_alt_choose_${alt.link.hashCode()}", align = Alignment.CenterStart)
                            }
                            RowLine()
                        }
                    }
                }
            }
        }
    }
}
