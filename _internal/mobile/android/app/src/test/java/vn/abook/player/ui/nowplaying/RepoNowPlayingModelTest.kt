package vn.abook.player.ui.nowplaying

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.Playback
import vn.abook.player.ui.data.FakePlaybackCore
import vn.abook.player.ui.data.PlayerChapter
import vn.abook.player.ui.data.PlayerRepo
import vn.abook.player.ui.data.playerSnapshot

/** The window's model is a mapping of the one repo: one core listener, one clock, commands through the core. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class RepoNowPlayingModelTest {
    private class Source : ReadAlongSource {
        var loads = 0
        var fail = false
        override suspend fun paragraphs(bookId: String, chapter: PlayerChapter): List<ReadParagraph> {
            loads++
            if (fail) error("Bạn cần tải chữ của chương.")
            return listOf(ReadParagraph(0, "Chữ của ${chapter.id}", 0, 1000, true))
        }
        override suspend fun voices() = listOf(PlayerVoice("v1", "Giọng một"))
    }

    private val core = FakePlaybackCore(playerSnapshot(book = "b1", chapter = 2, playing = false, position = 10.0), simulate = true).also {
        it.chapterList = listOf(Playback.Chapter(1, "Một", "1.mp3", 60.0), Playback.Chapter(2, "Hai", "2.mp3", 90.0))
    }
    private val scope = CoroutineScope(Dispatchers.Unconfined)
    private val repo = PlayerRepo(core, scope, Dispatchers.Unconfined, { null }, { null }).also { it.attach() }
    private val source = Source()
    private val model = RepoNowPlayingModel(repo, scope, source)

    @Test
    fun `building the model adds no core listener and the clock is the repo's own`() {
        assertEquals("một người nghe lõi: PlayerRepo", 1, core.listeners.size)
        assertSame(repo.clock.positionMs, model.position.milliseconds)
        assertSame(repo.clock.sleepRemainingMs, model.position.sleepRemainingMs)
    }

    @Test
    fun `the state is the repo snapshot mapped once and ticks never touch it`() {
        val before = model.state.value
        assertEquals("b1", before.bookId)
        assertEquals(listOf(1, 2), before.chapters.map { it.id })
        assertTrue(before.readAlongAvailable)
        core.emit(playerSnapshot(book = "b1", chapter = 2, position = 30.0, kind = "tick"))
        assertSame(before, model.state.value)
        assertEquals(30_000L, model.position.milliseconds.value)
    }

    @Test
    fun `commands go through the repo to the core and a sample reads the exact position`() {
        model.toggle()
        model.skip(15)
        model.seek(45_000)
        model.jump(1)
        model.next()
        model.previous()
        model.setRate(1.5)
        model.setRate(1.37)
        model.setSleep(SleepKind.Minutes, 15)
        model.setSleep(SleepKind.Minutes, 7)
        model.setSleep(SleepKind.Chapter)
        model.setSleep(SleepKind.Off)
        assertEquals(
            listOf(
                "toggle", "skip 15.0", "seek 45.0", "jump 1 0.0", "next", "previous", "rate 1.5",
                "sleep minutes 15", "sleep chapter 0", "sleep off 0",
            ),
            core.calls,
        )
        core.position = 777
        model.position.sample()
        assertEquals(777L, model.position.milliseconds.value)
    }

    @Test
    fun `the return chip appears after a jump and takes you back to where you were`() {
        core.position = 20_000
        assertFalse(model.state.value.returnAvailable)
        model.seek(50_000)
        assertTrue(model.state.value.returnAvailable)
        val serial = model.state.value.returnSerial
        model.jump(1)
        assertEquals(serial + 1, model.state.value.returnSerial)
        core.calls.clear()
        model.returnToPreviousPlace()
        assertEquals(listOf("jump 2 20.0"), core.calls)
        assertFalse(model.state.value.returnAvailable)
    }

    @Test
    fun `only installed voices the model has listed can be chosen`() = runBlocking {
        model.setVoice("v1")
        assertTrue(core.calls.none { it.startsWith("voice") })
        model.loadVoices()
        model.setVoice("v1")
        assertEquals("voice v1", core.calls.last())
        assertEquals("v1", model.state.value.voiceId)
    }

    @Test
    fun `read-along text loads for the current chapter and says so when it cannot`() = runBlocking {
        model.loadReadAlong()
        assertEquals("Chữ của 2", model.readAlong.value.paragraphs.single().text)
        assertEquals(2, model.readAlong.value.chapterId)
        source.fail = true
        model.jump(1)
        core.emit(playerSnapshot(book = "b1", chapter = 1, playing = false, kind = "chapter"))
        model.loadReadAlong()
        assertEquals("Bạn cần tải chữ của chương.", model.readAlong.value.error)
        assertTrue(model.readAlong.value.paragraphs.isEmpty())
    }

    @Test
    fun `the engine pushing state refreshes open text but a tick or a closed window never does`() = runBlocking {
        model.loadReadAlong()
        val first = source.loads
        core.emit(playerSnapshot(book = "b1", chapter = 2, kind = "tick", position = 12.0))
        assertEquals(first, source.loads)
        core.emit(playerSnapshot(book = "b1", chapter = 2, kind = "state"))
        assertEquals(first + 1, source.loads)
        model.setReadAlongActive(false)
        core.emit(playerSnapshot(book = "b1", chapter = 2, kind = "state"))
        assertEquals(first + 1, source.loads)
    }

    @Test
    fun `another book drops the old text`() = runBlocking {
        model.loadReadAlong()
        core.emit(playerSnapshot(book = "b2", chapter = 1, kind = "load"))
        assertNull(model.readAlong.value.chapterId)
        assertEquals("b2", model.readAlong.value.bookId)
        assertTrue(model.readAlong.value.paragraphs.isEmpty())
    }

    private fun modelWith(books: kotlinx.coroutines.flow.MutableStateFlow<List<vn.abook.player.ui.data.ListenBook>>, now: Long = 1_000_000L) =
        RepoNowPlayingModel(repo, scope, source, books = books, clockMs = { now })

    @Test
    fun `a finished part plays the next part of the same book on and says so`() {
        val first = vn.abook.player.ui.data.ListenBook("b1", "Tên", chaptersAvailable = 2, chaptersTotal = 2)
        val second = vn.abook.player.ui.data.ListenBook("b1-2", "Tên · Phần 2", chaptersAvailable = 2, chaptersTotal = 2, series = vn.abook.player.ui.data.SeriesLink("b1", 2))
        val chosen = modelWith(kotlinx.coroutines.flow.MutableStateFlow(listOf(first, second)))
        core.emit(playerSnapshot(book = "b1", chapter = 2, kind = "ended"))
        assertEquals("Nghe tiếp Phần 2", chosen.note.value?.text)
        chosen.dismissNote(chosen.note.value!!.serial)
        assertNull(chosen.note.value)
    }

    @Test
    fun `a finished volume of a series is only offered`() {
        val first = vn.abook.player.ui.data.ListenBook("b1", "Bộ · Tập 1", chaptersAvailable = 2, chaptersTotal = 2)
        val second = vn.abook.player.ui.data.ListenBook("b2", "Bộ · Tập 2", chaptersAvailable = 2, chaptersTotal = 2)
        val chosen = modelWith(kotlinx.coroutines.flow.MutableStateFlow(listOf(first, second)))
        core.emit(playerSnapshot(book = "b1", chapter = 2, kind = "ended"))
        assertNull("tập khác của một bộ không tự phát", chosen.note.value)
        assertEquals("b2", chosen.endChoices().next?.id)
        assertFalse(chosen.endChoices().continues)
    }

    @Test
    fun `another device that listened further after this one loaded is offered once`() {
        val flow = kotlinx.coroutines.flow.MutableStateFlow(listOf(vn.abook.player.ui.data.ListenBook("b1", "Tên")))
        val chosen = modelWith(flow, now = 1_000_000L)
        assertNull(chosen.note.value)
        val older = vn.abook.player.ui.data.Last(1, 300.0, 900.0)
        flow.value = listOf(vn.abook.player.ui.data.ListenBook("b1", "Tên", state = vn.abook.player.ui.data.ListenState(last = older)))
        assertNull("ghi trước lúc nạp là của máy này", chosen.note.value)
        val newer = vn.abook.player.ui.data.Last(1, 300.0, 2_000.0)
        flow.value = listOf(vn.abook.player.ui.data.ListenBook("b1", "Tên", state = vn.abook.player.ui.data.ListenState(last = newer)))
        val note = chosen.note.value
        assertEquals("Máy khác đã nghe tới Một · 5:00", note?.text)
        assertEquals("Nghe tiếp từ đó", note?.action)
        chosen.noteAction()
        assertTrue(core.calls.any { it.startsWith("jump 1 300") })
        assertNull(chosen.note.value)
        // Cùng mốc không hỏi lại.
        flow.value = listOf(vn.abook.player.ui.data.ListenBook("b1", "Tên", state = vn.abook.player.ui.data.ListenState(last = newer)))
        assertNull(chosen.note.value)
    }

    @Test
    fun `restart goes to the first chapter and plays`() {
        model.restart()
        assertTrue(core.calls.any { it.startsWith("jump 1 0") })
        assertTrue(core.calls.contains("play"))
    }
}
