package vn.abook.player.ui

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ui.components.PlayPauseGeometry

class PlayPauseGeometryTest {
    private fun at(t: Float) = PlayPauseGeometry.points(t, FloatArray(PlayPauseGeometry.POINTS))

    @Test
    fun `play is a triangle and pause is two bars`() {
        val play = at(0f)
        // Tam giác: ba góc thật là (8,5) (19,12) (8,19); đỉnh thừa (13,...) nằm trên hai cạnh nghiêng.
        assertEquals(8f, play[0], 0f)
        assertEquals(19f, play[10], 0f)
        assertEquals(12f, play[11], 0f)
        val pause = at(1f)
        // Hai thanh đứng: đỉnh trái-phải của mỗi thanh cùng x, cùng chiều cao 14.
        assertEquals(pause[0], pause[6], 0f)
        assertEquals(pause[2], pause[4], 0f)
        assertEquals(14f, pause[7] - pause[1], 0f)
        assertEquals(pause[8], pause[14], 0f)
        assertEquals(14f, pause[15] - pause[9], 0f)
    }

    @Test
    fun `every vertex moves straight from play to pause without leaving the box`() {
        val from = at(0f)
        val to = at(1f)
        for (step in 0..20) {
            val t = step / 20f
            val now = at(t)
            for (i in now.indices) {
                assertEquals(from[i] + (to[i] - from[i]) * t, now[i], 1e-5f)
                assertTrue(now[i] in 0f..PlayPauseGeometry.GRID)
            }
        }
    }

    @Test
    fun `progress outside 0 to 1 is clamped`() {
        assertArrayEquals(at(0f), at(-2f), 0f)
        assertArrayEquals(at(1f), at(3f), 0f)
    }
}
