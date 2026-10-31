package vn.abook.player.ui.data

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.TimeZone

/** Thẻ "Tối qua": mốc nào hiện, mốc nào được gợi ý, khi nào thẻ còn đúng - cùng luật với web (MorningRecap.tsx, night.ts). */
class NightRecapTest {
    private fun event(type: String, at: Double, seconds: Double, action: String = "", chapter: Int? = 4) =
        NightEvent(type, at, action, chapter, if (chapter == null) "" else "Chương $chapter", seconds)

    private fun night(vararg events: NightEvent, endedAt: Double? = 1000.0) = NightSession("b", "Truyện", 0.0, endedAt, false, events.toList())

    @Test
    fun `a full night lists four markers and suggests where the phone went still`() {
        val markers = NightRecap.markers(night(event("timer", 1.0, 100.0), event("touch", 2.0, 300.0), event("still", 3.0, 500.0), event("stopped", 4.0, 800.0)))
        assertEquals(listOf("Hẹn giờ ngủ", "Lần cuối chạm máy", "Máy bắt đầu nằm yên", "Tự dừng"), markers.map { it.label })
        assertEquals("máy nằm yên: lùi hai phút vì cảm biến cần hai phút để chắc", 380.0, markers[2].seconds, 0.0)
        assertEquals(listOf(false, false, true, false), markers.map { it.suggested })
    }

    @Test
    fun `without stillness the last touch is suggested, and a safety stop hides the timer marker`() {
        val touched = NightRecap.markers(night(event("timer", 1.0, 100.0), event("shake", 2.0, 300.0), event("stopped", 4.0, 800.0)))
        assertEquals(MarkerKind.Touch, touched.first { it.suggested }.kind)
        val safety = NightRecap.markers(night(event("timer", 1.0, 100.0, "safety"), event("stopped", 4.0, 800.0)))
        assertEquals(listOf(MarkerKind.Stopped), safety.map { it.kind })
        assertEquals("không ai chạm máy suốt một lúc lâu", safety[0].hint)
    }

    @Test
    fun `events without a place are dropped and still never goes below zero`() {
        val markers = NightRecap.markers(night(event("timer", 1.0, 5.0, chapter = null), event("still", 3.0, 50.0), event("stopped", 4.0, 60.0)))
        assertEquals(listOf(MarkerKind.Still, MarkerKind.Stopped), markers.map { it.kind })
        assertEquals(0.0, markers[0].seconds, 0.0)
    }

    @Test
    fun `the card is fresh only after a stop and within eighteen hours`() {
        val stopped = night(event("stopped", 900.0, 10.0), endedAt = 1000.0)
        assertTrue(NightRecap.fresh(stopped, 1000.0 + 3600))
        assertFalse(NightRecap.fresh(stopped, 1000.0 + 19 * 3600))
        assertFalse("đêm chưa kết thúc", NightRecap.fresh(night(event("timer", 1.0, 1.0), endedAt = null), 1500.0))
        assertFalse("không có mốc tự dừng", NightRecap.fresh(night(event("timer", 1.0, 1.0)), 1500.0))
        assertFalse(NightRecap.fresh(stopped.copy(dismissed = true), 1500.0))
    }

    @Test
    fun `listening on after the night hides the card, a save right at the stop does not`() {
        assertTrue(NightRecap.heardSince(1000.0, 1000.0 + 61))
        assertFalse(NightRecap.heardSince(1000.0, 1000.0 + 30))
        assertFalse(NightRecap.heardSince(1000.0, null))
    }

    @Test
    fun `label is last night unless the timer ended in the morning of today`() {
        val zone = TimeZone.getTimeZone("Asia/Ho_Chi_Minh")
        val morning = java.util.Calendar.getInstance(zone).apply { clear(); set(2027, 0, 15, 8, 0, 0) }.timeInMillis / 1000.0
        val noon = (morning * 1000).toLong() + 4 * 3600_000
        assertEquals("Vừa hẹn giờ", NightRecap.sessionLabel(morning, noon, zone))
        assertEquals("Tối qua", NightRecap.sessionLabel(morning - 86_400, noon, zone))
        val dawn = morning - 4 * 3600 // 04:00 cùng ngày: còn là đêm qua
        assertEquals("Tối qua", NightRecap.sessionLabel(dawn, noon, zone))
        assertEquals("Tối qua", NightRecap.sessionLabel(null, noon, zone))
        assertEquals("08:00", NightRecap.clock(morning, zone))
    }

    @Test
    fun `a stored night parses and a missing end stays missing`() {
        val json = JSONObject("""{"bookId":"b","bookTitle":"T","startedAt":5.0,"events":[{"type":"timer","at":6.0,"action":"safety","position":{"chapterId":null,"chapterTitle":"","seconds":1.5}},
            {"type":"still","at":7.0,"position":{"chapterId":3,"chapterTitle":"Ba","seconds":9.0}}]}""")
        val session = NightSession.parse(json)
        assertNull(session.endedAt)
        assertEquals(2, session.events.size)
        assertNull(session.events[0].chapterId)
        assertEquals(3, session.events[1].chapterId)
        assertEquals("safety", session.events[0].action)
    }
}
