package vn.abook.player.ui.nowplaying

import vn.abook.player.S

import android.os.SystemClock
import androidx.compose.runtime.Stable
import androidx.compose.runtime.mutableLongStateOf
import vn.abook.player.ui.data.PlayerChapter
import vn.abook.player.ui.music.MusicState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Deterministic test/demo adapter. Never touches Playback, network, files or the owner's library. */
@Stable
class FakeNowPlayingModel(
    initial: NowPlayingState = demoState(),
    initialText: ReadAlongState = demoText(),
    override val music: MusicState? = null,
    override val prepare: vn.abook.player.ui.data.PrepareState? = null,
) : NowPlayingModel {
    private val metadata = MutableStateFlow(initial)
    override val state = metadata.asStateFlow()
    private val text = MutableStateFlow(initialText)
    override val readAlong = text.asStateFlow()
    private var lastFrame = 0L
    val actions = mutableListOf<String>()
    private val positionMs = mutableLongStateOf(12_000)
    private val sleepLeft = mutableLongStateOf(0L)
    override val position = object : PlayerPosition {
        override val milliseconds = positionMs
        override val sleepRemainingMs = sleepLeft
        override fun sample() {
            val now = SystemClock.elapsedRealtime()
            if (lastFrame != 0L && state.value.playing) {
                val passed = now - lastFrame
                positionMs.longValue = (positionMs.longValue + (passed * state.value.rate).toLong()).coerceAtMost(state.value.durationMs)
                if (state.value.sleep.kind == SleepKind.Minutes) sleepLeft.longValue = (sleepLeft.longValue - passed).coerceAtLeast(0)
            }
            lastFrame = now
        }
    }
    fun update(state: NowPlayingState) { metadata.value = state }
    fun setPosition(ms: Long) { positionMs.longValue = ms }
    override fun toggle() { actions += "toggle"; metadata.value = state.value.copy(playing = !state.value.playing) }
    override fun skip(seconds: Int) { actions += "skip:$seconds"; seek(positionMs.longValue + seconds * 1000) }
    override fun seek(milliseconds: Long) {
        actions += "seek:$milliseconds"
        metadata.value = state.value.copy(returnAvailable = true, returnSerial = state.value.returnSerial + 1)
        setPosition(milliseconds.coerceIn(0, state.value.durationMs))
    }
    override fun jump(chapterId: Int) {
        actions += "jump:$chapterId"
        val chapter = state.value.chapters.firstOrNull { it.id == chapterId } ?: return
        metadata.value = state.value.copy(chapterId = chapter.id, chapterTitle = chapter.title, durationMs = chapter.durationMs)
        setPosition(0)
    }
    override fun next() { val list = state.value.chapters; list.getOrNull(list.indexOfFirst { it.id == state.value.chapterId } + 1)?.let { jump(it.id) } }
    override fun previous() { val list = state.value.chapters; list.getOrNull(list.indexOfFirst { it.id == state.value.chapterId } - 1)?.let { jump(it.id) } }
    override fun setRate(rate: Double) { actions += "rate:$rate"; metadata.value = state.value.copy(rate = rate) }
    override fun setSleep(kind: SleepKind, minutes: Int) {
        actions += "sleep:$kind:$minutes"
        sleepLeft.longValue = minutes * 60_000L
        metadata.value = state.value.copy(sleep = PlayerSleep(kind, minutes, state.value.playing))
    }
    var choices: PlayerEnd.Choices = PlayerEnd.Choices()
    override fun endChoices() = choices
    override fun listen(bookId: String) { actions += "listen:$bookId" }
    override fun restart() { actions += "restart" }
    private val noteFlow = kotlinx.coroutines.flow.MutableStateFlow<PlayerNote?>(null)
    override val note = noteFlow.asStateFlow()
    fun say(note: PlayerNote) { noteFlow.value = note }
    override fun noteAction() { actions += "note"; noteFlow.value = null }
    override fun dismissNote(serial: Int) { if (noteFlow.value?.serial == serial) noteFlow.value = null }
    override fun setVoice(id: String) { metadata.value = state.value.copy(voiceId = id) }
    override suspend fun loadVoices() { actions += "loadVoices" }
    override fun setReadAlongActive(active: Boolean) {}
    override fun returnToPreviousPlace() { actions += "return"; metadata.value = state.value.copy(returnAvailable = false) }
    override suspend fun loadReadAlong() { actions += "loadText" }

    companion object {
        fun demoState() = NowPlayingState(
            bookId = "native-player-demo", bookTitle = S.s_nhung_ngay_gio_hat_c6b4626f, chapterId = 1, chapterTitle = S.s_chuong_1_mot_buoi_som_74c20e6d,
            durationMs = 360_000, playing = false, readAlongAvailable = true,
            chapters = List(12) { PlayerChapter(it + 1, S.s_chuong_0_1_f0f29379(it + 1, if (it == 0) S.s_mot_buoi_som_0635ca65 else S.s_tren_con_duong_952afe11), 360_000, "texts/${it + 1}.txt") },
        )
        fun demoText(): ReadAlongState {
            val lines = listOf(S.s_troi_vua_hung_sang_suong_mu_con_vuong_tren_b365e644,
                S.s_ban_buoc_ra_hien_nha_nghe_tieng_gio_ke_mot_c7a8801c,
                S.s_xa_xa_con_duong_nho_dan_qua_khu_vuon_dang_e1a4b638)
            return ReadAlongState("native-player-demo", 1, List(80) { i ->
                val line = lines[i % lines.size]
                val tokens = Regex("\\S+").findAll(line).toList()
                ReadParagraph(i, line, i * 5000L, (i + 1) * 5000L, true, tokens.mapIndexed { j, match ->
                    WordTiming(i * 5000L + j * 300, i * 5000L + (j + 1) * 300, match.range.first, match.range.last + 1)
                })
            })
        }
    }
}

/** Demo text for the measuring intent (`abook.demo.books`): the same eighty paragraphs as the fake model, through the real model's text path. */
object DemoReadAlongSource : ReadAlongSource {
    override suspend fun paragraphs(bookId: String, chapter: vn.abook.player.ui.data.PlayerChapter): List<ReadParagraph> = FakeNowPlayingModel.demoText().paragraphs
    override suspend fun voices(): List<PlayerVoice> = listOf(PlayerVoice("demo:a", S.s_giong_thu_a_9fbd3685), PlayerVoice("demo:b", S.s_giong_thu_b_6cf84320))
}
