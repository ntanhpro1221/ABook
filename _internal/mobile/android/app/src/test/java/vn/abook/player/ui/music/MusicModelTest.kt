package vn.abook.player.ui.music

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Chữ và dữ liệu của nhạc nền (không cần màn): đọc lời đáp của lõi, giá trị ngắn của hàng "Nhạc nền", các dòng chọn, mức, lời dưới bảng, ghi công. */
class MusicModelTest {
    private val menu = MusicMenu(listOf(PlaylistSummary("rain", "Đêm mưa", "Pad trầm.", 480)), mine = 2, scene = true)

    @Test
    fun `the core's answers read into the model`() {
        val read = MusicJson.menu(JSONObject("""{"playlists":[{"id":"rain","name":"Đêm mưa","description":"Pad trầm.","minutes":480},{"name":"không mã"}],"mine":2,"scene":"scene"}"""))
        assertEquals(menu, read)
        assertFalse(MusicJson.menu(JSONObject("""{"playlists":[],"scene":null,"error":"Mất mạng"}""")).scene)
        val book = MusicJson.book(JSONObject("""{"playlist":"scene","playlistAuto":true,"levelDb":-24}"""), textOnly = true)
        assertEquals(BookMusic(MusicKind.Playlist, levelDb = -24.0, playlist = "scene", playlistAuto = true), book)
        assertEquals(MusicKind.Packaged, MusicJson.book(JSONObject("""{"hasMusic":true,"enabled":false}"""), false).kind)
        assertEquals(MusicKind.None, MusicJson.book(JSONObject("""{"playlist":null}"""), false).kind)
        assertNull("bài không tên không tác giả thì không ghi công", MusicJson.credit(JSONObject("""{"license":"cc0"}""")))
        val player = PlayerMusic.from(JSONObject("""{"musicCredit":{"title":"Rain","creator":"Kevin MacLeod","license":"by"},"musicBroken":true,"musicScene":true}"""))
        assertEquals("Rain · Kevin MacLeod", MusicText.creditLine(player.credit!!))
        assertTrue(player.broken && player.scene)
        assertEquals(PlayerMusic.None, PlayerMusic.from(JSONObject("{}")))
    }

    @Test
    fun `the row value names what plays and never flashes a guess`() {
        assertEquals("", MusicText.value(null, menu))
        assertEquals("", MusicText.value(BookMusic(MusicKind.None), menu))
        assertEquals("Theo cảnh", MusicText.value(BookMusic(MusicKind.Playlist, playlist = "scene", playlistAuto = true), menu))
        assertEquals("Tắt", MusicText.value(BookMusic(MusicKind.Playlist, autoOff = true), menu))
        assertEquals("Đêm mưa", MusicText.value(BookMusic(MusicKind.Playlist, playlist = "rain"), menu))
        assertEquals("Nhạc của tôi", MusicText.value(BookMusic(MusicKind.Playlist, playlist = "mine"), menu))
        assertEquals("Bật", MusicText.value(BookMusic(MusicKind.Packaged), menu))
        assertEquals("Tắt", MusicText.value(BookMusic(MusicKind.Packaged, enabled = false), menu))
    }

    @Test
    fun `the choices list auto, off, scene, the catalogue and my music`() {
        val options = MusicText.options(menu, BookMusic(MusicKind.Playlist, playlist = "scene", playlistAuto = true))
        assertEquals(listOf(null, "off", "scene", "rain", "mine"), options.map { it.id })
        assertEquals("Theo cảnh", options.first().hint)
        assertEquals("dài 8 giờ", options[3].hint)
        assertFalse(options.last().disabled)
        val empty = MusicText.options(menu.copy(mine = 0, scene = false), null)
        assertEquals(listOf(null, "off", "rain", "mine"), empty.map { it.id })
        assertTrue("kho trống thì chưa chọn được", empty.last().disabled)
        assertEquals("dài 45 phút", MusicText.length(45))
        assertNull(MusicText.chosen(BookMusic(MusicKind.Playlist, playlist = "scene", playlistAuto = true)))
        assertEquals("off", MusicText.chosen(BookMusic(MusicKind.Playlist, playlist = "off")))
    }

    @Test
    fun `levels keep the book's own level and run loud to quiet`() {
        assertEquals(MusicLevels.levels, MusicLevels.options(-20.0))
        val packaged = MusicLevels.options(-18.0)
        assertEquals(listOf(-14.0, -17.0, -18.0, -20.0, -24.0, -28.0), packaged.map { it.first })
        assertEquals("Của sách", packaged[2].second)
    }

    @Test
    fun `the note speaks only when there is something to know`() {
        assertEquals("", MusicText.note(BookMusic(MusicKind.Playlist, playlist = "rain"), menu, PlayerMusic.None))
        assertEquals(MusicText.AUTO_OFF_NOTE, MusicText.note(BookMusic(MusicKind.Playlist, autoOff = true), menu, null))
        assertEquals("Mất mạng", MusicText.note(BookMusic(MusicKind.Playlist, playlist = "rain"), menu, PlayerMusic(offline = "Mất mạng")))
        assertEquals(
            MusicText.BROKEN_PLAYLIST,
            MusicText.note(BookMusic(MusicKind.Playlist, playlist = "scene", playlistAuto = true), menu, PlayerMusic(broken = true, scene = true)),
        )
        assertEquals(
            MusicText.BROKEN_PACKAGED + "\n" + MusicText.PACKAGED_NOTE,
            MusicText.note(BookMusic(MusicKind.Packaged), menu, PlayerMusic(broken = true)),
        )
        assertEquals("", MusicText.note(BookMusic(MusicKind.None), menu, null))
    }

    @Test
    fun `credits and licences read like the web`() {
        assertEquals("CC BY 4.0", MusicText.licenseLabel("by", "https://creativecommons.org/licenses/by/4.0/"))
        assertEquals("CC0 1.0", MusicText.licenseLabel("cc0", "https://creativecommons.org/publicdomain/zero/1.0/"))
        assertEquals("CC BY-NC", MusicText.licenseLabel("by-nc"))
        assertEquals("CC0", MusicText.licenseLabel("CC0"))
        assertEquals("Riêng", MusicText.licenseLabel("Riêng"))
        assertEquals("\"Rain\" by Kevin", MusicText.creditText(MusicCredit("Rain", "Kevin", "\"Rain\" by Kevin")))
        assertEquals("Rain - Kevin", MusicText.creditText(MusicCredit("Rain", "Kevin")))
        assertTrue(MusicText.needsModifiedNote("by"))
        assertFalse(MusicText.needsModifiedNote("cc0"))
        assertFalse(MusicText.needsModifiedNote(""))
    }
}
