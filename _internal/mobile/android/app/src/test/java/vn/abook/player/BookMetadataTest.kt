package vn.abook.player

import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import org.junit.Assert.*
import org.junit.Test

class BookMetadataTest {
    @Test
    fun editsReplaceLabelsAndCoverWithoutChangingTheItemIdentity() {
        pretendMedia3IsUnderTest()
        val old = MediaItem.Builder().setMediaId("2410")
            .setMediaMetadata(MediaMetadata.Builder().setTitle("Cũ").build()).build()
        val cover = byteArrayOf(1, 2, 3)
        val edited = withBookMetadata(old, "Sách mới", "Giọng mới", "Chương mới", cover)
        assertEquals(old.localConfiguration, edited.localConfiguration)
        assertEquals(old.mediaId, edited.mediaId)
        assertEquals("Chương mới", edited.mediaMetadata.title)
        assertEquals("Chương mới", edited.mediaMetadata.displayTitle)
        assertEquals("Sách mới", edited.mediaMetadata.albumTitle)
        assertEquals("Giọng mới", edited.mediaMetadata.artist)
        assertArrayEquals(cover, edited.mediaMetadata.artworkData)
        assertEquals("Sách mới", withBookMetadata(old, "Sách mới", "", "Chương mới", cover).mediaMetadata.artist)
    }

    @Test
    fun openingABookWithUnchangedLabelsTouchesNothing() {
        val cover = byteArrayOf(1, 2, 3)
        val chapters = listOf(Playback.Chapter(1, "Một", "1.mp3", 10.0), Playback.Chapter(2, "Hai", "2.mp3", 10.0))
        assertFalse(labelsChanged("Sách", "Giọng", chapters, "Sách", "Giọng", chapters.map { it.copy() }, cover.copyOf(), cover))
        assertFalse(labelsChanged("Sách", "Giọng", chapters, "Sách", "Giọng", chapters, null, cover))
        assertTrue(labelsChanged("Sách", "Giọng", chapters, "Sách mới", "Giọng", chapters, cover, cover))
        assertTrue(labelsChanged("Sách", "Giọng", chapters, "Sách", "Giọng mới", chapters, cover, cover))
        assertTrue(labelsChanged("Sách", "Giọng", chapters, "Sách", "Giọng", listOf(chapters[0], chapters[1].copy(title = "Hai mới")), cover, cover))
        assertTrue(labelsChanged("Sách", "Giọng", chapters, "Sách", "Giọng", chapters, byteArrayOf(9), cover))
    }

    @Test
    fun theWholeQueueIsRelabelledAtOnceKeepingEachItem() {
        pretendMedia3IsUnderTest()
        val items = (1..3).map { id ->
            MediaItem.Builder().setMediaId("$id")
                .setMediaMetadata(MediaMetadata.Builder().setTitle("Cũ $id").build()).build()
        }
        val cover = byteArrayOf(4, 5)
        val edited = relabelled(items, "Sách mới", "Giọng", mapOf(2 to "Hai mới"), cover)
        assertEquals(items.map { it.mediaId }, edited.map { it.mediaId })
        assertEquals(items.map { it.localConfiguration }, edited.map { it.localConfiguration })
        assertEquals(listOf("Cũ 1", "Hai mới", "Cũ 3"), edited.map { it.mediaMetadata.title.toString() })
        assertTrue(edited.all { it.mediaMetadata.albumTitle == "Sách mới" && it.mediaMetadata.artworkData.contentEquals(cover) })
    }
}
