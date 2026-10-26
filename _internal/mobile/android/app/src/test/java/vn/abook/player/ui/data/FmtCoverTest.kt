package vn.abook.player.ui.data

import java.util.Calendar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Ca test của format.test.ts và cover.ts cho [Fmt] và [CoverArt]. */
class FmtCoverTest {
    @Test
    fun `length speaks hours and minutes`() {
        assertEquals("0 phút", Fmt.length(0.0))
        assertEquals("0 phút", Fmt.length(Double.NaN))
        assertEquals("dưới 1 phút", Fmt.length(20.0))
        assertEquals("1 phút", Fmt.length(30.0))
        assertEquals("45 phút", Fmt.length(45 * 60.0))
        assertEquals("1 giờ", Fmt.length(3600.0))
        assertEquals("9 giờ 12 phút", Fmt.length(9 * 3600.0 + 12 * 60))
    }

    @Test
    fun `lengthUp rounds up to the minute`() {
        assertEquals("0 phút", Fmt.lengthUp(0.0))
        assertEquals("1 phút", Fmt.lengthUp(60.0))
        assertEquals("2 phút", Fmt.lengthUp(61.0))
        assertEquals("1 giờ", Fmt.lengthUp(3541.0))
    }

    @Test
    fun `clock reads like a player`() {
        assertEquals("3:07", Fmt.clock(187.0))
        assertEquals("13:05", Fmt.clock(13 * 60 + 5.0))
        assertEquals("1:02:05", Fmt.clock(3725.0))
        assertEquals("0:00", Fmt.clock(-1.0))
        assertEquals("0:00", Fmt.clock(Double.NaN))
    }

    private fun at(day: Int, hour: Int, minute: Int, second: Int = 0): Long =
        Calendar.getInstance().apply { clear(); set(2026, Calendar.OCTOBER, day, hour, minute, second) }.timeInMillis

    @Test
    fun `whenText speaks like a person`() {
        val now = at(26, 12, 0)
        fun text(then: Long) = Fmt.whenText(then / 1000.0, now)
        assertEquals("vừa xong", text(now - 30_000))
        assertEquals("hôm nay 09:00", text(at(26, 9, 0)))
        assertEquals("hôm qua 09:15", text(at(25, 9, 15)))
        assertEquals("tối qua 23:41", text(at(25, 23, 41)))
        assertEquals("3 ngày trước", text(at(23, 8, 0)))
        assertEquals("16/10/2026", text(at(16, 8, 0)))
        assertEquals("", Fmt.whenText(0.0, now))
    }

    @Test
    fun `resumeWhere names chapter and second`() {
        assertEquals("Chương 3 · 12:04", Fmt.resumeWhere("Chương 3", 724.0))
        assertEquals("12:04", Fmt.resumeWhere("", 724.0))
    }

    @Test
    fun `hash is FNV-1a over the UTF-16 units`() {
        assertEquals(2166136261L, CoverArt.hash(""))
        assertEquals(0xE40C292CL, CoverArt.hash("a"))
        assertNotEquals(CoverArt.hash("Tắt đèn"), CoverArt.hash("Tat den"))
    }

    @Test
    fun `a title always gets the same cover and case or spacing around it do not matter`() {
        val a = CoverArt.style("Tắt đèn")
        val b = CoverArt.style("  tắt đèn ")
        assertEquals(a.seed, b.seed)
        assertEquals(a.from, b.from)
        assertEquals(a.to, b.to)
        assertEquals(a.ink, b.ink)
        val first = CoverArt.style("a")
        assertEquals(0xFF1F3B57.toInt(), first.from)
        assertFalse(first.arcsFromRight)
    }

    @Test
    fun `titles split into the main part and the volume`() {
        assertEquals("Throne of Magical Arcana" to "Tập 16", CoverArt.splitTitle("Throne of Magical Arcana · Tập 16"))
        assertEquals("X" to "Phần 3", CoverArt.splitTitle("X", 3))
        assertEquals("X" to "", CoverArt.splitTitle("X", 1))
        assertEquals("X" to "", CoverArt.splitTitle(" X ", null))
    }

    @Test
    fun `small cover label is the volume number or two initials`() {
        assertEquals("16", CoverArt.label("Throne of Magical Arcana · Tập 16"))
        assertEquals("CP", CoverArt.label("Chí Phèo"))
        assertEquals("LR", CoverArt.label("The Lord of Rings"))
        assertEquals("TĐ", CoverArt.label("Tắt đèn"))
        assertTrue(CoverArt.label("Số đỏ").isEmpty())
    }
}
