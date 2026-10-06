package vn.abook.player

import androidx.media3.common.C
import androidx.media3.common.Player
import org.json.JSONObject
import org.junit.Assert
import org.junit.Test

/**
 * Màn hình khoá, tai nghe, đồng hồ điều khiển loa / TV điện thoại đang phát (CastPlayer): mỗi lệnh của phiên media thành
 * đúng lệnh RemotePlayers gửi DlnaPlayers. Phiên media gọi `handleSeek(chương đích, vị trí, lệnh)` như SimpleBasePlayer.
 */
class CastControlsTest {
    private val chapters = listOf(1, 2, 3)

    private fun seek(command: Int, index: Int, positionMs: Long, current: Int = 1): JSONObject =
        CastControls.seek(command, index, positionMs, current, chapters)

    private fun json(vararg pairs: Pair<String, Any>) = JSONObject().also { out -> pairs.forEach { out.put(it.first, it.second) } }

    /** So nội dung, không so chuỗi: thứ tự khoá của JSONObject không cố định. */
    private fun assertEquals(expected: JSONObject, actual: JSONObject) = Assert.assertEquals(expected.asMap(), actual.asMap())

    private fun JSONObject.asMap(): Map<String, String> = keys().asSequence().associateWith { get(it).toString() }

    @Test
    fun playAndPauseGoToTheRenderer() {
        assertEquals(json("action" to "play"), CastControls.playPause(true))
        assertEquals(json("action" to "pause"), CastControls.playPause(false))
    }

    @Test
    fun backAndForwardSkipFifteenSeconds() {
        assertEquals(json("action" to "skip", "seconds" to -15.0), seek(Player.COMMAND_SEEK_BACK, 1, 5_000))
        assertEquals(json("action" to "skip", "seconds" to 15.0), seek(Player.COMMAND_SEEK_FORWARD, 1, 35_000))
    }

    @Test
    fun nextAndPreviousAreChapters() {
        // "Sau": chương kế từ đầu. "Trước" trong 3 giây đầu: chương trước; muộn hơn: về đầu chương này.
        assertEquals(json("action" to "next"), seek(Player.COMMAND_SEEK_TO_NEXT, 2, C.TIME_UNSET))
        assertEquals(json("action" to "next"), seek(Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM, 2, 0))
        assertEquals(json("action" to "previous"), seek(Player.COMMAND_SEEK_TO_PREVIOUS, 0, C.TIME_UNSET))
        assertEquals(json("action" to "seek", "seconds" to 0.0), seek(Player.COMMAND_SEEK_TO_PREVIOUS, 1, 0))
    }

    @Test
    fun aPlaceInTheChapterOrAnotherChapterIsAJump() {
        assertEquals(json("action" to "seek", "seconds" to 42.5), seek(Player.COMMAND_SEEK_IN_CURRENT_MEDIA_ITEM, 1, 42_500))
        assertEquals(json("action" to "jump", "chapterId" to 3, "seconds" to 0.0), seek(Player.COMMAND_SEEK_TO_MEDIA_ITEM, 2, 0, current = 0))
        assertEquals(json("action" to "jump", "chapterId" to 1, "seconds" to 12.0), seek(Player.COMMAND_SEEK_TO_MEDIA_ITEM, 0, 12_000, current = 2))
        // Chương ngoài danh sách (danh sách vừa đổi): coi như tua trong chương đang phát, không nhảy bừa.
        assertEquals(json("action" to "seek", "seconds" to 3.0), seek(Player.COMMAND_SEEK_TO_MEDIA_ITEM, 7, 3_000))
    }

    @Test
    fun theVolumeSliderAndKeysGoToTheRenderer() {
        assertEquals(json("action" to "volume", "level" to 40), CastControls.volume(40))
        assertEquals(json("action" to "volume", "level" to 100), CastControls.volume(140))
        assertEquals(json("action" to "volume", "level" to 0), CastControls.volume(-3))
        assertEquals(json("action" to "volume", "level" to 35), CastControls.step(30, up = true))
        assertEquals(json("action" to "volume", "level" to 25), CastControls.step(30, up = false))
        assertEquals(json("action" to "volume", "level" to 100), CastControls.step(98, up = true))
        assertEquals(json("action" to "volume", "level" to 0), CastControls.step(2, up = false))
    }

    @Test
    fun aCastVolumeIsAPercentUnlessTheDeviceKeepsItsOwn() {
        Assert.assertEquals(42, GCast.volumeOf(json("level" to 0.42, "muted" to false, "controlType" to "attenuation")))
        Assert.assertEquals(100, GCast.volumeOf(json("level" to 1.0)))
        Assert.assertNull(GCast.volumeOf(json("level" to 0.5, "controlType" to "fixed")))
        Assert.assertNull(GCast.volumeOf(json("muted" to false)))
    }

    private fun computer(state: JSONObject?, age: Double = 0.0) =
        json("id" to "abc123", "name" to "TV phòng khách", "age" to age).put("state", state ?: JSONObject.NULL)

    private fun playing(playing: Boolean = true, buffering: Boolean = false) = json(
        "bookId" to "sach", "bookTitle" to "Sách thử", "chapterId" to 2, "chapterTitle" to "Chương 2",
        "position" to 10.0, "duration" to 60.0, "playing" to playing, "buffering" to buffering)

    @Test
    fun aComputerCastLooksLikeAPhoneCastOnTheLockScreen() {
        val chapters = listOf(CastChapter(1, "Chương 1", 50.0), CastChapter(2, "Chương 2", 60.0), CastChapter(3, "Chương 3", 70.0))
        val now = ComputerCasts.snapshot(computer(playing(), age = 1.5), chapters, 500)!!
        Assert.assertEquals("cast:abc123", now.id) // lệnh đi qua máy tính (RemotePlayers.CAST)
        Assert.assertEquals("TV phòng khách", now.device)
        Assert.assertEquals("Sách thử", now.bookTitle)
        Assert.assertEquals(2, now.chapterId)
        Assert.assertEquals(listOf(1, 2, 3), now.chapters.map { it.id })
        Assert.assertEquals("vị trí nội suy như thanh “Đang phát trên…”", 12.0, now.position, 1e-9)
        Assert.assertNull("máy tính chưa chỉnh âm lượng loa / TV: phím âm lượng chỉnh điện thoại", now.volume)
        Assert.assertEquals(10.0, ComputerCasts.snapshot(computer(playing(playing = false), age = 9.0), chapters, 5_000)!!.position, 1e-9)
        Assert.assertEquals(10.0, ComputerCasts.snapshot(computer(playing(buffering = true), age = 9.0), chapters, 5_000)!!.position, 1e-9)
        Assert.assertEquals(60.0, ComputerCasts.snapshot(computer(playing(), age = 90.0), chapters, 0)!!.position, 1e-9)
        // Chưa biết chương của cuốn (gói chưa tải về): một mục là chương đang phát.
        val alone = ComputerCasts.snapshot(computer(playing()), emptyList(), 0)!!
        Assert.assertEquals(listOf(CastChapter(2, "Chương 2", 60.0)), alone.chapters)
        Assert.assertNull("thiết bị rảnh: không có phiên", ComputerCasts.snapshot(computer(null), chapters, 0))
    }

    @Test
    fun theComputerBookListsOnlyChaptersThatCanBePlayed() {
        val manifest = JSONObject().put("chapters", org.json.JSONArray()
            .put(json("id" to 1, "title" to "Một", "fullTitle" to "Chương 1: Một", "duration" to 50.0))
            .put(json("id" to 2, "title" to "Hai", "available" to false))
            .put(json("id" to 3, "title" to "Ba", "duration" to 70.0)))
        Assert.assertEquals(listOf(CastChapter(1, "Chương 1: Một", 50.0), CastChapter(3, "Ba", 70.0)), ComputerCasts.chaptersOf(manifest))
    }
}
