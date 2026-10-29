package vn.abook.player.ui.nowplaying

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
            bookId = "native-player-demo", bookTitle = "Những ngày gió hát", chapterId = 1, chapterTitle = "Chương 1 · Một buổi sớm",
            durationMs = 360_000, playing = false, readAlongAvailable = true,
            chapters = List(12) { PlayerChapter(it + 1, "Chương ${it + 1} · ${if (it == 0) "Một buổi sớm" else "Trên con đường"}", 360_000, "texts/${it + 1}.txt") },
        )
        fun demoText(): ReadAlongState {
            val lines = listOf("Trời vừa hửng sáng, sương mù còn vương trên những tán lá.",
                "Bạn bước ra hiên nhà, nghe tiếng gió kể một câu chuyện cũ.",
                "Xa xa, con đường nhỏ dẫn qua khu vườn đang chờ nắng lên.")
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
    override suspend fun voices(): List<PlayerVoice> = listOf(PlayerVoice("demo:a", "Giọng thử A"), PlayerVoice("demo:b", "Giọng thử B"))
}
