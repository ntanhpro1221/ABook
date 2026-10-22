package vn.abook.player

import org.junit.Assert.*
import org.junit.Test

class QueueRefreshTest {
    @Test fun completedChaptersJoinQueueWhileCurrentKeepsItsSource() {
        val current = Playback.Chapter(1, "Một", "old.mp3", 100.0)
        val fresh = listOf(current.copy(file="new.mp3"), Playback.Chapter(2, "Hai", "two.mp3", 120.0))
        val result = refreshedChapters(listOf(current), fresh, 1)
        assertEquals(listOf(1,2), result.map { it.id })
        assertEquals("old.mp3", result[0].file)
        assertEquals(120.0, result[1].duration, 0.0)
    }

    @Test fun removedCurrentStaysUntilNextLoad() {
        val old = listOf(Playback.Chapter(1,"Một","one.mp3",100.0), Playback.Chapter(2,"Hai","two.mp3",100.0))
        assertEquals(listOf(1,2,3), refreshedChapters(old,listOf(old[1],Playback.Chapter(3,"Ba","three.mp3",100.0)),1).map { it.id })
    }
}
