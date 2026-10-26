package vn.abook.player.ui.music

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Nhạc nền của một cuốn với nguồn giả, phạm vi chạy ngay (Unconfined): sau mỗi lời gọi trạng thái đã xong; chỉ lần lưu bị giữ bằng cổng mới dang dở. */
class MusicStateTest {
    private val source = FakeMusicSource().apply {
        books["text"] = BookMusic(MusicKind.Playlist, playlist = MusicText.SCENE, playlistAuto = true)
        books["audio"] = BookMusic(
            MusicKind.Packaged, levelDb = -18.0,
            cues = listOf(MusicCue("1:0", 1, "Chương 1", 0.0, 90.0, "Bài gốc", "Kevin MacLeod"), MusicCue("1:90000", 1, "Chương 1", 90.0, 200.0, "Đêm", "Kevin MacLeod")),
        )
        mine += MineTrack("local:rain", "Mưa", "Tôi", 120.0, analysed = true)
    }
    private var clock = 0L
    private val music = MusicState(source, CoroutineScope(Dispatchers.Unconfined), menuTtlMs = 1_000, now = { clock })

    @Test
    fun `opening reads the book every time and the menu once in a while`() {
        music.open("text")
        assertEquals(source.books["text"], music.ui.value.book)
        assertEquals(source.menu, music.ui.value.menu)
        music.open("audio")
        assertEquals("cuốn khác thì bắt đầu lại", MusicKind.Packaged, music.ui.value.book?.kind)
        assertEquals("menu giữ qua cuốn khác", source.menu, music.ui.value.menu)
        assertEquals(1, source.menuReads)
        clock = 2_000
        music.open("audio")
        assertEquals(2, source.menuReads)
    }

    @Test
    fun `choices go to the core and the answer is what shows`() {
        music.open("text")
        music.choose("rain")
        music.setLevel(-24.0)
        music.choose(null)
        assertEquals(listOf("choose text rain", "level text -24.0", "choose text null"), source.calls)
        assertTrue(music.ui.value.book!!.playlistAuto)
        assertEquals(-24.0, music.ui.value.book!!.levelDb, 0.0)
        music.open("audio")
        music.setEnabled(false)
        assertFalse(music.ui.value.book!!.enabled)
    }

    @Test
    fun `one save at a time, and an answer for another book is dropped`() {
        music.open("text")
        val gate = CompletableDeferred<Unit>()
        source.changeGate = gate
        music.choose("rain")
        assertTrue(music.ui.value.busy)
        music.choose("off")
        assertEquals("đang lưu thì lần bấm sau bị bỏ", listOf("choose text rain"), source.calls)
        source.changeGate = null
        music.open("audio")
        gate.complete(Unit)
        assertEquals(MusicKind.Packaged, music.ui.value.book?.kind)
        assertFalse(music.ui.value.busy)
    }

    @Test
    fun `failures stay in the panel with the core's words`() {
        source.bookError = MusicFailure("Không tìm thấy sách này trong thư viện")
        music.open("text")
        assertTrue(music.ui.value.failed)
        assertNull(music.ui.value.book)
        source.bookError = null
        music.retry()
        assertFalse(music.ui.value.failed)
        source.changeError = MusicFailure("Bài này không còn")
        music.choose("rain")
        assertEquals("Bài này không còn", music.ui.value.problem)
        assertFalse(music.ui.value.busy)
    }

    @Test
    fun `adding music picks my music for this book when the store has tracks`() {
        music.open("text")
        music.importMine(listOf("content://a", "content://b"))
        assertEquals(listOf("import 2", "choose text mine"), source.calls)
        assertEquals("Đã thêm 2 bài.", music.ui.value.notice)
        assertEquals(2, music.ui.value.menu?.mine)
        assertEquals(MusicText.MINE, music.ui.value.book?.playlist)
        assertFalse(music.ui.value.importing)

        source.calls.clear()
        source.importResult = { MusicImported("Chưa thêm được bài nào.", listOf("a.txt: không phải file nhạc"), false) }
        music.importMine(listOf("content://c"))
        assertEquals("kho không có bài mới thì không đổi lựa chọn", listOf("import 1"), source.calls)
        assertEquals("a.txt: không phải file nhạc", music.ui.value.problem)
    }

    @Test
    fun `a packaged cue goes silent, takes one of my tracks and goes back`() {
        music.open("audio")
        music.silence("1:0", true)
        assertTrue(music.ui.value.book!!.cues[0].silenced)
        music.swap("1:0")
        assertEquals(listOf("Mưa"), music.ui.value.mine?.map { it.title })
        music.pin("1:0", "local:rain")
        assertEquals(listOf("silence audio 1:0 true", "alternatives audio 1:0", "pin audio 1:0 local:rain"), source.calls)
        val cue = music.ui.value.book!!.cues[0]
        assertTrue("chọn bài cho đoạn đang im thì có nhạc lại", cue.pinned && !cue.silenced)
        assertEquals("chọn xong thì khép Đổi bài như web", "", music.ui.value.swapKey)
        assertEquals("", music.ui.value.choosing)
        music.pin("1:0", null)
        assertFalse(music.ui.value.book!!.cues[0].pinned)
    }

    @Test
    fun `the swap list can fail, retry, and a failed pin keeps it open`() {
        music.open("audio")
        source.alternativesError = MusicFailure("mất")
        music.swap("1:90000")
        assertTrue(music.ui.value.swapFailed)
        assertNull(music.ui.value.mine)
        source.alternativesError = null
        music.retrySwap()
        assertFalse(music.ui.value.swapFailed)
        assertEquals(1, music.ui.value.mine?.size)
        source.changeError = MusicFailure("Bài này không còn")
        music.pin("1:90000", "local:rain")
        assertEquals("1:90000", music.ui.value.swapKey)
        assertEquals("Bài này không còn", music.ui.value.problem)
        music.open("audio")
        assertEquals("mở lại bảng thì khép Đổi bài", "", music.ui.value.swapKey)
    }

    @Test
    fun `adding music from the swap list refreshes it and leaves a packaged book's choice alone`() {
        music.open("audio")
        music.swap("1:0")
        source.calls.clear()
        source.mine += MineTrack("local:new", "Mới", "", 0.0, analysed = false)
        music.importMine(listOf("content://new"))
        assertEquals(listOf("import 1", "alternatives audio 1:0"), source.calls)
        assertEquals(listOf("Mưa", "Mới"), music.ui.value.mine?.map { it.title })
    }
}
