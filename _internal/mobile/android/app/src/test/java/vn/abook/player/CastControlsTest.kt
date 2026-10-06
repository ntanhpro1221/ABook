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
}
