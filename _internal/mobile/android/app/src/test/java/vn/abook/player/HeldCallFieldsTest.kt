package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class HeldCallFieldsTest {
    private val cover = "data:image/png;base64," + "A".repeat(200_000)

    private fun exportCall() = JSONObject().put("bookId", "f-ccb6c81bfd1b0976903171a4").put("voice", "vieneu:Đức Trí").put("music", true).put("cover", cover)

    /**
     * What Capacitor parcels when the picker covers the app: the call options as JSON twice (capacitorLastPluginCallOptions and the
     * plugin bundle's `_json`), strings as UTF-16. a65 crashed at 522,612 bytes with a 127 KB cover; the 200 KB cover here would be ~800 KB.
     */
    private fun savedStateBytes(data: JSONObject) = 2 * 2 * data.toString().length

    @Test
    fun theSavedStateOfAnExportStaysSmallWhileThePickerIsOpen() {
        val data = exportCall()
        assertTrue(savedStateBytes(data) > 800_000)
        HeldCallFields().take("exportAudiobook", data)
        assertTrue("saved state ${savedStateBytes(data)} bytes", savedStateBytes(data) < 50_000)
        assertFalse(data.has("cover"))
        assertEquals("vieneu:Đức Trí", data.getString("voice"))
        assertEquals(true, data.getBoolean("music"))
    }

    @Test
    fun theAnswerGetsTheCoverBack() {
        val held = HeldCallFields()
        val data = exportCall()
        held.take("exportM4b", data)
        held.putBack("exportM4b", data)
        assertEquals(cover, data.getString("cover"))
        assertEquals(exportCall().toString().length, data.toString().length)
        // The slot is empty afterwards: a second answer gets nothing.
        val again = JSONObject().put("bookId", "x")
        held.putBack("exportM4b", again)
        assertFalse(again.has("cover"))
    }

    @Test
    fun anotherCallsAnswerDoesNotTakeTheHeldFields() {
        val held = HeldCallFields()
        held.take("exportMp3", exportCall())
        val other = JSONObject().put("kind", "folder")
        held.putBack("pickSource", other)
        assertFalse(other.has("cover"))
    }

    @Test
    fun aCallRestoredAfterTheProcessDiedGoesOnWithoutTheCover() {
        // The process died behind the picker: Capacitor rebuilds the call from the small saved options, a fresh plugin holds nothing.
        val saved = exportCall().also { HeldCallFields().take("exportAudiobook", it) }
        val rebuilt = JSONObject(saved.toString())
        HeldCallFields().putBack("exportAudiobook", rebuilt)
        assertFalse(rebuilt.has("cover"))
        assertEquals("f-ccb6c81bfd1b0976903171a4", rebuilt.getString("bookId"))
    }

    @Test
    fun smallOptionsStayInTheCall() {
        val data = JSONObject().put("id", "b1").put("as", "abookproj").put("ask", true).put("title", "T".repeat(HeldCallFields.LIMIT))
        val before = data.toString()
        HeldCallFields().take("saveBook", data)
        assertEquals(before, data.toString())
    }
}
