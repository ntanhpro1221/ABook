package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Dữ liệu di động chỉ chặn tải nhạc MÁY TỰ CHỌN (soát a47 mục 5): chọn gì ở nút "Nhạc nền" (Theo cảnh, một danh sách, Nhạc của tôi) thì tải như thường.
 */
class MeteredMusicTest {
    private val textBook = JSONObject().put("chapters", JSONArray().put(JSONObject().put("text", true)))

    /** Chặn hay không cho lựa chọn `choice` (rỗng = chưa chọn gì), "Tự chọn nhạc nền" = `auto`, mạng tính phí = `metered`. */
    private fun holds(choice: String, auto: Boolean = true, metered: Boolean = true): Boolean {
        val scene = Playlists.sceneMode(textBook, choice, auto)
        return Playlists.holdsDownloadOnMetered(metered, Playlists.isAutomatic(scene, choice))
    }

    @Test
    fun automaticSceneMusicWaitsForWifiOnMeteredData() {
        assertTrue(holds(""))
    }

    @Test
    fun anythingTheListenerChoseDownloadsOnMeteredDataToo() {
        assertFalse("chọn Theo cảnh ở menu", holds(Playlists.SCENE))
        assertFalse("chọn một danh sách của danh mục", holds("calm-evening"))
        assertFalse("chọn Nhạc của tôi", holds(Playlists.MINE))
        assertFalse("chọn tắt thì không có gì để tải", holds(Playlists.OFF))
    }

    @Test
    fun wifiOrAutoOffNeverHolds() {
        assertFalse("Wi-Fi", holds("", metered = false))
        assertFalse("Tự chọn nhạc nền tắt, chưa chọn gì: không có nhạc", holds("", auto = false))
    }
}
