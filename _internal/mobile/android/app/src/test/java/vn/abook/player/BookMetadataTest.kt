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
}
