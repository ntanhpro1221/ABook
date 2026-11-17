package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.ui.editbook.*

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class BookDescriptionMetadataTest {
    @Test fun preservesParagraphsAndAudioIdentity() {
        val summary = "Một chiếc thuyền giấy. ".repeat(40) + "\n\nĐoạn cuối."
        val base = JSONObject().put("title", "Hồ giấy").put("version", "package-fixed").put("audioVersion", "audio-fixed")
        val edits = BookEdits.empty().put("summary", summary).put("illustrator", "Người Vẽ").put("genres", JSONArray(listOf("Fantasy")))
        val valid = BookEdits.validate(edits)
        val shown = BookEdits.applyManifest(base, valid)
        assertEquals(summary, shown.getString("summary"))
        assertEquals("audio-fixed", shown.getString("audioVersion"))
        assertEquals("package-fixed", shown.getString("version"))
        assertEquals(3, BookEdits.count(valid))
        assertNotEquals(BookMetadata.version(base), BookMetadata.version(shown))
    }
    @Test fun descriptionAndHeaderKeepSourceWords() {
        assertEquals("Đầu tiên.\n\nSau đó.", BookImport.descriptionMetadata("<p>Đầu tiên.</p><p>Sau <b>đó</b>.</p>"))
        val header = BookImport.headerMetadata("Hồ giấy\nTác giả: Người Viết\nHọa sĩ: Người Vẽ\nTóm tắt: Đầu tiên.\n\nSau đó.\n\nChương 1\nChữ truyện.")
        assertEquals("Đầu tiên.\n\nSau đó.", header.getString("summary"))
        assertEquals("Người Vẽ", header.getString("illustrator"))
    }
    @Test fun draftRebaseAndDiffIncludeMetadata() {
        val snapshot = EditSnapshot("sample", "Hồ giấy")
        val draft = EditLogic.draft(snapshot).copy(metadata = snapshot.metadata.copy(summary = "Đoạn mới."))
        val diff = EditLogic.diff(snapshot, draft)
        assertFalse(diff.empty)
        assertEquals("Đoạn mới.", diff.metadata?.summary)
        assertEquals("Đoạn mới.", EditLogic.rebase(snapshot, draft, snapshot.copy(author = "Người Viết")).metadata.summary)
    }
    @Test(expected = IllegalArgumentException::class) fun rejectsMalformedGenres() {
        BookMetadata.validate(JSONObject().put("genres", "Fantasy"))
    }
    @Test fun clearedListsDoNotCreateEmptyChips() {
        val raw = JSONObject().put("genres", JSONArray(listOf("", " ", "Fantasy")))
        assertEquals("[\"Fantasy\"]", BookMetadata.validate(raw).getJSONArray("genres").toString())
    }
}
