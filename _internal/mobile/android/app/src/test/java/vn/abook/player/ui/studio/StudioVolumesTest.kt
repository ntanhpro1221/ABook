package vn.abook.player.ui.studio

import org.junit.Assert.*
import org.junit.Test
import org.json.JSONObject

class StudioVolumesTest {
    @Test fun boundariesAssignEveryChapterOnceInGlobalOrderEvenWithRepeatedTitles() {
        val drafts = listOf(VolumeDraft(1, "Tập một", "1", "1"), VolumeDraft(2, "Tập hai", "2", "3"))
        val definitions = StudioVolumes.definitions(drafts, listOf(11, 15, 20, 23)).getJSONArray("volumes")
        assertEquals("[11,15]", definitions.getJSONObject(0).getJSONArray("chapters").toString())
        assertEquals("[20,23]", definitions.getJSONObject(1).getJSONArray("chapters").toString())
        assertEquals(2, definitions.getJSONObject(1).getInt("number"))
    }

    @Test fun refusesCrossedBoundariesEmptyVolumesAndAnInvalidNumber() {
        val first = VolumeDraft(1, "Một", "1", "1")
        for (last in listOf(VolumeDraft(2, "Hai", "2", "1"), VolumeDraft(2, "Hai", "2", "5"), VolumeDraft(2, "Hai", "0", "3"))) {
            assertThrows(IllegalArgumentException::class.java) { StudioVolumes.definitions(listOf(first, last), listOf(11, 15, 20, 23)) }
        }
    }

    @Test fun editableStartsArePositionsRatherThanChapterIds() {
        val book = JSONObject("""{"chapters":[{"id":11},{"id":15},{"id":20}],"volumes":[{"id":1,"title":"Một","number":1,"chapters":[{"id":11},{"id":15}]},{"id":2,"title":"Hai","number":2,"chapters":[{"id":20}]}]}""")
        assertEquals(listOf("1", "3"), StudioVolumes.drafts(book).map { it.start })
    }

    /** Soát 0.4.173 B13c: xoá quyển 2 rồi thêm quyển mới trong cùng lần sửa - id mới là 3, không tái dùng 2 (bìa riêng của quyển 2 ghép theo id). */
    @Test fun aVolumeAddedAfterARemovalNeverReusesTheRemovedId() {
        val book = JSONObject("""{"chapters":[{"id":11},{"id":15},{"id":20}],"volumes":[{"id":1,"title":"Một","number":1,"chapters":[{"id":11}]},{"id":2,"title":"Hai","number":2,"chapters":[{"id":15},{"id":20}]}]}""")
        val kept = StudioVolumes.drafts(book).take(1)
        assertEquals(3, StudioVolumes.nextId(kept, book))
        assertEquals(1, StudioVolumes.nextId(emptyList(), JSONObject()))
    }
}
