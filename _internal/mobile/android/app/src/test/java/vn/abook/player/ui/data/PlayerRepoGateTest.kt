package vn.abook.player.ui.data

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.Playback
import vn.abook.player.ui.voice.ConsentRequest
import vn.abook.player.ui.voice.PlayGate

/** Cửa giả: giữ lệnh phát lại tới khi test cho chạy; ghi chương có phải chữ không. */
private class HoldingGate : PlayGate {
    override val request: StateFlow<ConsentRequest?> = MutableStateFlow(null)
    val asked = ArrayList<Pair<String, Boolean>>()
    var cancels = 0
    private var held: (() -> Unit)? = null

    override fun before(bookId: String, textChapter: Boolean, go: () -> Unit) {
        asked += bookId to textChapter
        held = go
    }

    override fun cancel() { cancels++; held = null }
    fun answer() { held?.invoke(); held = null }
    val waiting: Boolean get() = held != null
}

/** Mọi lệnh làm chữ rời máy của trình phát đi qua cửa hỏi đồng ý TRƯỚC khi chạm lõi; lệnh không làm chữ đi đâu thì qua thẳng. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class PlayerRepoGateTest {
    private val audio = Playback.Chapter(1, "Một", "1.mp3", 60.0)
    private val text = Playback.Chapter(2, "Hai", "", 0.0, "texts/2.txt")
    private val text3 = Playback.Chapter(3, "Ba", "", 0.0, "texts/3.txt")

    private val gate = HoldingGate()
    private val scope = CoroutineScope(Dispatchers.Unconfined)

    private fun makeCore(chapter: Int = 2, playing: Boolean = false, buffering: Boolean = false) =
        FakePlaybackCore(playerSnapshot(book = "b1", chapter = chapter, playing = playing).put("buffering", buffering), simulate = true).also {
            it.chapterList = listOf(audio, text, text3)
        }

    private fun repo(core: FakePlaybackCore, plans: Map<String, LoadRequest> = emptyMap()) =
        PlayerRepo(core, scope, Dispatchers.Unconfined, { null }, { plans[it] }, { null }, { id, chapter, _ -> plans[id]?.copy(startChapterId = chapter) }, gate).also { it.attach() }

    @Test
    fun `play on a paused text chapter waits for the answer, then reaches the core`() {
        val core = makeCore()
        val repo = repo(core)
        repo.toggle()
        assertEquals(listOf("b1" to true), gate.asked)
        assertTrue("chưa lệnh nào tới lõi", core.calls.isEmpty())
        gate.answer()
        assertEquals(listOf("toggle"), core.calls)
    }

    @Test
    fun `an audio chapter is let through by the gate at once`() {
        val core = makeCore(chapter = 1)
        val repo = repo(core)
        repo.play()
        assertEquals(listOf("b1" to false), gate.asked)
        gate.answer()
        assertEquals(listOf("play"), core.calls)
    }

    @Test
    fun `pausing or toggling while it plays never asks, and drops a question still waiting`() {
        val core = makeCore(playing = true)
        val repo = repo(core)
        repo.toggle()
        repo.pause()
        assertTrue("không hỏi khi đang phát", gate.asked.isEmpty())
        assertEquals(listOf("toggle", "pause"), core.calls)
        assertEquals(2, gate.cancels)
    }

    @Test
    fun `waiting for the first segment counts as playing and does not ask again`() {
        val core = makeCore(buffering = true)
        val repo = repo(core)
        repo.toggle()
        assertTrue(gate.asked.isEmpty())
        assertEquals(listOf("toggle"), core.calls)
    }

    @Test
    fun `jumping to a text chapter of the loaded book asks, jumping to an audio one does not read text`() {
        val core = makeCore(chapter = 1)
        val repo = repo(core)
        repo.jumpTo(2, 5.0)
        assertEquals(listOf("b1" to true), gate.asked)
        assertTrue(core.calls.isEmpty())
        gate.answer()
        assertEquals(listOf("jump 2 5.0"), core.calls)
        repo.jumpTo(1, 0.0)
        assertEquals("b1" to false, gate.asked.last())
    }

    @Test
    fun `next asks about the chapter it goes to`() {
        val core = makeCore(chapter = 1)
        val repo = repo(core)
        repo.next()
        assertEquals("b1" to true, gate.asked.last())
        gate.answer()
        assertEquals(listOf("next"), core.calls)
    }

    @Test
    fun `previous after the first seconds asks about the chapter it goes back to`() {
        val core = makeCore(chapter = 3).also { it.position = 1_000 }
        val repo = repo(core)
        repo.previous()
        assertEquals("b1" to true, gate.asked.last())
        val audioFirst = makeCore(chapter = 2).also { it.position = 2_000 }
        gate.cancel()
        val second = PlayerRepo(audioFirst, scope, Dispatchers.Unconfined, { null }, { null }, { null }, { _, _, _ -> null }, gate).also { it.attach() }
        second.previous()
        assertEquals("về chương audio trước", "b1" to false, gate.asked.last())
    }

    @Test
    fun `starting a book whose resume chapter is text asks before the core loads it`() {
        val core = FakePlaybackCore(playerSnapshot(book = "", chapter = null), simulate = true)
        val plan = LoadRequest("b2", "T", "", listOf(audio, text), 2, 0.0, 1.0)
        val repo = repo(core, mapOf("b2" to plan))
        repo.togglePlay("b2")
        assertEquals(listOf("b2" to true), gate.asked)
        assertTrue("chưa nạp gì", core.loads.isEmpty())
        gate.answer()
        assertEquals(listOf(plan), core.loads)
    }

    @Test
    fun `starting a book whose resume chapter has audio is not a question`() {
        val core = FakePlaybackCore(playerSnapshot(book = "", chapter = null), simulate = true)
        val plan = LoadRequest("b2", "T", "", listOf(audio, text), 1, 0.0, 1.0)
        val repo = repo(core, mapOf("b2" to plan))
        repo.playNow("b2")
        assertEquals(listOf("b2" to false), gate.asked)
        gate.answer()
        assertEquals(1, core.loads.size)
    }

    @Test
    fun `playing a chosen text chapter of another book asks about that chapter`() {
        val core = FakePlaybackCore(playerSnapshot(book = "", chapter = null), simulate = true)
        val plan = LoadRequest("b2", "T", "", listOf(audio, text), 1, 0.0, 1.0)
        val repo = repo(core, mapOf("b2" to plan))
        repo.playChapter("b2", 2, 0.0)
        assertEquals(listOf("b2" to true), gate.asked)
        gate.answer()
        assertEquals(2, core.loads.single().startChapterId)
    }

    @Test
    fun `putting the book in the player paused never asks - no text leaves while paused`() {
        val core = FakePlaybackCore(playerSnapshot(book = "", chapter = null), simulate = true)
        val plan = LoadRequest("b2", "T", "", listOf(audio, text), 2, 0.0, 1.0)
        val repo = repo(core, mapOf("b2" to plan))
        kotlinx.coroutines.runBlocking { repo.prepare("b2") }
        assertTrue(gate.asked.isEmpty())
        assertEquals(1, core.loads.size)
        assertEquals(false, core.loads.single().autoplay)
    }

    @Test
    fun `removing the playing book drops a question still waiting`() {
        val core = makeCore()
        val repo = repo(core)
        repo.toggle()
        assertTrue(gate.waiting)
        repo.bookRemoved("b1")
        assertTrue(gate.cancels >= 1)
        gate.answer()
        assertTrue("không lệnh nào tới lõi", core.calls.none { it == "toggle" })
    }
}
