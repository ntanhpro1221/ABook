package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ReseekCasesTest {
    private fun byName(cases: List<ReseekCases.Case>) = cases.associateBy { it.name }

    @Test
    fun ls06TargetsAndPlansAreTheMeasuredOnesAt44k() {
        val cases = byName(ReseekCases.build(44100, 44100L * 3))
        val ls = cases.getValue("LS06")
        assertEquals(listOf(12246L, 13872L, 21703L), ls.targets)
        assertEquals(183L, ls.deltaMs)
        assertTrue(ls.applicable)
        // ca D180_in_f lặp đúng lần 1 -> lần 3 của ls_06
        assertEquals(listOf(12246L, 21703L), cases.getValue("D180_in_f").targets)
        // seekPlan của Nối: (200 ms, 3426), (300 ms, 642), (400 ms, 4063) như bảng §44.7
        val seam = LoopSeam.Seam(java.io.File("a.mp3"), java.io.File("a.wav"), 1152, 115200, 1152000, 44100 * 3, 44100, 2, 1152, 0L)
        val plans = ls.targets.map { LoopSeam.seekPlan(seam, 1, it) }
        assertEquals(listOf(200L, 300L, 400L), plans.map { it.positionMs })
        assertEquals(listOf(3426L, 642L, 4063L), plans.map { it.trimFrames })
    }

    @Test
    fun gridCoversEveryDeltaKindAndFraction() {
        val sr = 44100
        val chunk = 4410L
        val cases = ReseekCases.build(sr, 44100L * 3)
        assertEquals(4 * 3 * 2 + 1 + 4 * 2, cases.size)
        val a = 12246L
        for (delta in longArrayOf(50, 100, 180, 300)) {
            val m = byName(cases)
            val inF = m.getValue("D${delta}_in_f").targets
            val in0 = m.getValue("D${delta}_in_0").targets
            val sameF = m.getValue("D${delta}_same_f").targets
            val same0 = m.getValue("D${delta}_same_0").targets
            val farF = m.getValue("D${delta}_far_f").targets
            val far0 = m.getValue("D${delta}_far_0").targets
            for (t in listOf(inF, in0, sameF, same0, farF, far0)) assertEquals(a, t[0])
            // (i) >= 1 khối sau khối của A
            assertTrue(inF[1] / chunk >= a / chunk + 1 && in0[1] / chunk >= a / chunk + 1)
            // (ii) cùng khối 100 ms với A, khác A
            assertEquals(a / chunk, sameF[1] / chunk)
            assertEquals(a / chunk, same0[1] / chunk)
            assertTrue(sameF[1] != a && same0[1] != a)
            // (iii) xa hơn 1,5 s
            assertTrue(farF[1] - a > sr * 3 / 2 && far0[1] - a > sr * 3 / 2)
            // phần lẻ so với ranh khối: khác 0 / bằng 0
            for (t in listOf(inF, sameF, farF)) assertEquals(4063L, t[1] % chunk)
            for (t in listOf(in0, same0, far0)) assertEquals(0L, t[1] % chunk)
            assertTrue(m.values.all { it.applicable })
            assertEquals(delta, m.getValue("D${delta}_far_0").deltaMs)
            // ca edge: chỉ A cố định, phần lẻ của B mang theo ca
            assertEquals(listOf(a), m.getValue("D${delta}_edge_f").targets)
            assertEquals(4063L, m.getValue("D${delta}_edge_f").edgeFraction)
            assertEquals(0L, m.getValue("D${delta}_edge_0").edgeFraction)
            assertEquals(-1L, m.getValue("D${delta}_in_f").edgeFraction)
        }
    }

    @Test
    fun edgeTargetIsTheChunkUnderThePositionPlusTheFraction() {
        assertTrue(ReseekCases.atChunkStart(400))
        assertTrue(ReseekCases.atChunkStart(401))
        assertFalse(ReseekCases.atChunkStart(402))
        assertFalse(ReseekCases.atChunkStart(399))
        assertFalse(ReseekCases.atChunkStart(0)) // ranh đầu Nối: không có ranh - 1 ms
        assertEquals(4 * 4410L + 4063, ReseekCases.edgeTarget(401, 44100, 4063))
        assertEquals(4 * 4800L, ReseekCases.edgeTarget(400, 48000, 0))
        // seekPlan của đích ấy tua tới đúng ranh khối (400 ms): cách vị trí <= 2 ms -> LoopSeam.seekIsNoop đúng -> có tua đệm 399 ms
        val seam = LoopSeam.Seam(java.io.File("a.mp3"), java.io.File("a.wav"), 1152, 115200, 1152000, 44100 * 3, 44100, 2, 1152, 0L)
        val plan = LoopSeam.seekPlan(seam, 1, ReseekCases.edgeTarget(401, 44100, 4063))
        assertEquals(400L, plan.positionMs)
        assertTrue(LoopSeam.seekIsNoop(1, 401, 1, plan.positionMs))
        assertEquals(399L, LoopSeam.stepAside(plan.positionMs)) // tua đệm của Clip (vòng 10 Nối cũng dùng: lệch lưới -45 khung)
        assertEquals(300L, LoopSeam.stepAside(1, plan.positionMs)) // Nối từ vòng 11: ranh khối trước, lưới giữ nguyên (SeamGridTest)
    }

    @Test
    fun shortSeamMarksFarCasesNotApplicable() {
        // Nối 1,2 s ở 44,1 kHz: "far" (đích ~1,8-1,9 s) không áp, các ca khác vẫn áp
        val cases = ReseekCases.build(44100, 52920)
        for (c in cases) assertEquals(c.name, !c.name.contains("_far_") && !c.name.contains("_edge_"), c.applicable)
        // edge cần A + Δ + 1 s chờ + 1 khối + 400 ms: Δ 50 ở 44,1 kHz = 12246 + 46305 + 4410 + 17640
        assertFalse(ReseekCases.build(44100, 80600).single { it.name == "D50_edge_f" }.applicable)
        assertTrue(ReseekCases.build(44100, 80601).single { it.name == "D50_edge_f" }.applicable)
        // đích + 400 ms phải còn trong Nối: LS06 cần 21703 + 17640
        assertFalse(ReseekCases.build(44100, 21703L + 17639).single { it.name == "LS06" }.applicable)
        assertTrue(ReseekCases.build(44100, 21703L + 17640).single { it.name == "LS06" }.applicable)
    }

    @Test
    fun otherRatesScaleWithTheChunk() {
        val cases = byName(ReseekCases.build(48000, 48000L * 3))
        // khối 4800: A = 2 khối + round(3426 * 4800 / 4410) = 9600 + 3729; B lẻ = round(4063 * 4800 / 4410) = 4422
        assertEquals(listOf(13329L, 4 * 4800L + 4422), cases.getValue("D50_in_f").targets)
        assertEquals(listOf(13329L, 3 * 4800L + 699, 4 * 4800L + 4422), cases.getValue("LS06").targets)
    }

    @Test
    fun selectMatchesExactNamesAndUnderscorePrefixes() {
        val cases = ReseekCases.build(44100, 44100L * 3)
        assertEquals(cases, ReseekCases.select(cases, null))
        assertEquals(cases, ReseekCases.select(cases, " , "))
        assertEquals(listOf("LS06"), ReseekCases.select(cases, "LS06").map { it.name })
        assertEquals(8, ReseekCases.select(cases, "D180").size)
        assertEquals(listOf("D180_in_f", "D180_in_0"), ReseekCases.select(cases, "D180_in").map { it.name })
        assertEquals(listOf("D50_same_0", "LS06"), ReseekCases.select(cases, "D50_same_0, LS06").map { it.name })
        // "D1" không phải tên cũng không phải tiền tố trước "_": không khớp D100 / D180
        assertTrue(ReseekCases.select(cases, "D1").isEmpty())
    }
}
