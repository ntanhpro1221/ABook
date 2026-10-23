package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import vn.abook.player.readaloud.ReadingAnchor
import vn.abook.player.readaloud.TextBookmark

class TextBookmarkTest {
    @Test fun snapshotKeepsTheSentenceAndWordWithoutATimeline() {
        val paragraphs = listOf("First paragraph.", "Second paragraph.", "The chosen word.")
        val anchor = ReadingAnchor.make(paragraphs, 2, 1)!!
        val sentence = TextBookmark.from(paragraphs, anchor)!!
        assertEquals(2, sentence.getInt("index"))
        assertEquals(paragraphs[2], sentence.getString("quote"))
        assertTrue(StrictJson.equal(anchor, sentence.getJSONObject("anchor")))
        assertEquals(2 to 1, ReadingAnchor.restore(paragraphs, sentence.getJSONObject("anchor")))
        assertNull(TextBookmark.from(paragraphs, null))
        assertNull(TextBookmark.from(listOf("Changed text."), anchor))
    }

    @Test fun storeKeepsTheSharedAnchorThroughSyncReopenEditAndUndo() {
        val root = Files.createTempDirectory("text-bookmark").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        File(root, "state").mkdirs()
        val fixture = JSONObject(File("../../../tests/fixtures/records/text_bookmark.json").readText(Charsets.UTF_8))
        val anchor = fixture.getJSONObject("anchor")
        val mark = Store.addBookmark("b", 1, 6.0, "", 2, fixture.getString("quote"), anchor = anchor)
        assertTrue(StrictJson.equal(anchor, mark.getJSONObject("anchor")))
        Store.mergeRemote("remote", JSONObject().put("bookmarks", JSONArray().put(fixture)))
        Store.updateBookmark("remote", fixture.getString("id"), "Edited")
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        val edited = Store.state("remote").getJSONArray("bookmarks").getJSONObject(0)
        assertTrue(StrictJson.equal(anchor, edited.getJSONObject("anchor")))
        Store.deleteBookmark("remote", edited.getString("id"))
        val restored = Store.restoreBookmark("remote", edited)
        Store.mergeRemote("other", JSONObject().put("bookmarks", JSONArray().put(restored)))
        val received = Store.state("other").getJSONArray("bookmarks").getJSONObject(0)
        assertTrue(StrictJson.equal(anchor, received.getJSONObject("anchor")))
        assertEquals(2, received.getInt("index"))
        assertEquals(fixture.getString("quote"), received.getString("quote"))
    }
}
