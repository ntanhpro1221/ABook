package vn.abook.player.ui.data

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** [PlayerRepo] với lõi phát giả: trạng thái bất biến chỉ đổi khi có gì đổi, vị trí chạy riêng, lệnh chuyển xuống lõi. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class PlayerRepoTest {
    private fun snap(
        book: String = "b1",
        chapter: Int? = 1,
        playing: Boolean = false,
        position: Double = 12.5,
        duration: Double = 600.0,
        kind: String = "state",
    ): JSONObject = JSONObject()
        .put("kind", kind).put("bookId", book).put("bookTitle", "Tắt đèn").put("chapterId", chapter ?: JSONObject.NULL)
        .put("chapterTitle", "Chương 1").put("playing", playing).put("position", position).put("duration", duration).put("rate", 1.25)

    private fun plan(id: String) = LoadRequest(id, "T", "", emptyList(), 1, 30.0, 1.0)

    private fun repo(core: FakePlaybackCore, plans: Map<String, LoadRequest> = emptyMap(), cover: CoverRef? = CoverRef("/c.jpg", 1)): PlayerRepo =
        PlayerRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { cover }, { plans[it] })

    @Test
    fun `attach takes the state the player already has`() {
        val core = FakePlaybackCore(snap(playing = true, position = 12.5))
        val repo = repo(core)
        assertFalse(repo.state.value.hasTrack)
        repo.attach()
        val state = repo.state.value
        assertTrue(state.hasTrack)
        assertEquals("b1", state.bookId)
        assertEquals("Tắt đèn", state.bookTitle)
        assertEquals(1, state.chapterId)
        assertEquals("Chương 1", state.chapterTitle)
        assertTrue(state.playing)
        assertEquals(600_000L, state.durationMs)
        assertEquals(1.25f, state.rate, 0f)
        assertEquals(12_500L, repo.clock.positionMs.value)
    }

    @Test
    fun `attach twice listens once and detach stops listening`() {
        val core = FakePlaybackCore(snap())
        val repo = repo(core)
        repo.attach()
        repo.attach()
        assertEquals(1, core.listeners.size)
        repo.detach()
        assertTrue(core.listeners.isEmpty())
        repo.detach()
        repo.attach()
        assertEquals(1, core.listeners.size)
    }

    @Test
    fun `a tick moves the clock and leaves the state object alone`() {
        val core = FakePlaybackCore(snap())
        val repo = repo(core)
        repo.attach()
        val before = repo.state.value
        core.emit(snap(kind = "tick", position = 40.0))
        assertSame(before, repo.state.value)
        assertEquals(40_000L, repo.clock.positionMs.value)
    }

    @Test
    fun `a real change builds a new state and keeps the cover of the same book`() {
        val core = FakePlaybackCore(snap())
        val repo = repo(core)
        repo.attach()
        val cover = repo.state.value.cover
        assertEquals(CoverRef("/c.jpg", 1), cover)
        core.emit(snap(playing = true))
        assertTrue(repo.state.value.playing)
        assertEquals(cover, repo.state.value.cover)
        core.emit(snap(book = "b2", chapter = 4))
        assertEquals("b2", repo.state.value.bookId)
        assertEquals(4, repo.state.value.chapterId)
        assertEquals(CoverRef("/c.jpg", 1), repo.state.value.cover)
    }

    @Test
    fun `no chapter means no mini player`() {
        val repo = repo(FakePlaybackCore(snap(chapter = null)))
        repo.attach()
        assertFalse(repo.state.value.hasTrack)
        assertNull(repo.state.value.chapterId)
    }

    @Test
    fun `the sleep timer splits into the setting and the countdown`() {
        val json = snap().put("sleep", JSONObject().put("mode", "minutes").put("minutes", 30).put("remaining", 1500.0).put("counting", true))
        val core = FakePlaybackCore(json)
        val repo = repo(core)
        repo.attach()
        assertEquals(SleepSetting("minutes", 30, true), repo.state.value.sleep)
        assertTrue(repo.state.value.sleep.active)
        assertEquals(1_500_000L, repo.clock.sleepRemainingMs.value)
        core.emit(snap(kind = "tick", position = 1.0).put("sleep", JSONObject().put("mode", "minutes").put("minutes", 30).put("remaining", 1499.0)))
        assertEquals(1_499_000L, repo.clock.sleepRemainingMs.value)
        assertEquals(SleepSetting("minutes", 30, true), repo.state.value.sleep)
        assertFalse(SleepSetting.Off.active)
    }

    @Test
    fun `commands go straight to the core`() {
        val core = FakePlaybackCore(snap())
        val repo = repo(core)
        repo.play(); repo.pause(); repo.toggle(); repo.skip(-15.0); repo.seekTo(30.0); repo.next(); repo.previous(); repo.setRate(1.5); repo.jumpTo(3, 9.0)
        assertEquals(listOf("play", "pause", "toggle", "skip -15.0", "seek 30.0", "next", "previous", "rate 1.5", "jump 3 9.0"), core.calls)
    }

    @Test
    fun `the play button of the book in the player toggles it`() {
        val core = FakePlaybackCore(snap())
        val repo = repo(core, mapOf("b1" to plan("b1")))
        repo.attach()
        repo.togglePlay("b1")
        assertEquals(listOf("toggle"), core.calls)
        assertTrue(core.loads.isEmpty())
    }

    @Test
    fun `the play button of another book loads it where the listener left off`() {
        val core = FakePlaybackCore(snap())
        val repo = repo(core, mapOf("b2" to plan("b2")))
        repo.attach()
        repo.togglePlay("b2")
        assertEquals("b2", core.loads.single().id)
        assertEquals(30.0, core.loads.single().startSeconds, 0.0)
        assertTrue(core.calls.isEmpty())
    }

    @Test
    fun `a book with nothing to play loads nothing`() {
        val core = FakePlaybackCore(snap())
        val repo = repo(core)
        repo.togglePlay("ghost")
        repo.playNow("ghost")
        assertTrue(core.loads.isEmpty())
        assertTrue(core.calls.isEmpty())
    }

    @Test
    fun `play now continues a paused book leaves a playing one and loads another`() {
        val core = FakePlaybackCore(snap(playing = false))
        val repo = repo(core, mapOf("b2" to plan("b2")))
        repo.attach()
        repo.playNow("b1")
        assertEquals(listOf("play"), core.calls)
        core.emit(snap(playing = true))
        repo.playNow("b1")
        assertEquals(listOf("play"), core.calls)
        repo.playNow("b2")
        assertEquals(listOf("b2"), core.loads.map { it.id })
    }

    @Test
    fun `playChapter jumps inside the loaded book and loads another book at that chapter`() {
        val core = FakePlaybackCore(snap(book = "b1"))
        val repo = PlayerRepo(
            core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null },
            { id, chapter, seconds -> LoadRequest(id, "T", "", emptyList(), chapter, seconds, 1.0) },
        )
        repo.attach()
        repo.playChapter("b1", 3, 12.0)
        assertEquals(listOf("jump 3 12.0"), core.calls)
        repo.playChapter("b2", 5, 0.0)
        assertEquals(5, core.loads.single().startChapterId)
        assertEquals("b2", core.loads.single().id)
    }
}
