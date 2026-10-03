package vn.abook.player.readaloud

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/**
 * Chia mốc theo âm tiết cho giọng không báo mốc (FPT.AI, Viettel AI) và độ dài MP3, trên bộ ví dụ DÙNG CHUNG với Python
 * (tests/fixtures/readaloud/spread: README.md viết thuật toán; syllables/counts.json: số âm tiết từng chữ của word_timing.syllable_count).
 */
class SyllableSpreadTest {
    private val dir: File = File("../../../tests/fixtures/readaloud/spread").also {
        if (!it.isDirectory) fail("Không thấy bộ ví dụ dùng chung: ${it.absoluteFile}")
    }

    @Test
    fun everySharedSpreadFixtureGivesTheHandComputedWords() {
        val cases = dir.listFiles { f -> f.name.endsWith(".json") }!!.sortedBy { it.name }
        assertTrue("thiếu ví dụ", cases.size >= 5)
        for (file in cases) {
            val json = JSONObject(file.readText(Charsets.UTF_8))
            val text = json.getString("text")
            val duration = json.getLong("durationMs")
            val got = WordTokens.map(text, SyllableSpread.boundaries(text, duration), duration)
            val want = json.getJSONArray("words")
            assertEquals("${file.name}: số chữ", want.length(), got.size)
            for (i in got.indices) {
                val pair = want.getJSONArray(i)
                assertEquals("${file.name}: chữ $i (${json.getString("note")})", Span(pair.getLong(0), pair.getLong(1)), got[i])
            }
        }
    }

    @Test
    fun syllableCountsMatchTheDesktop() {
        val counts = JSONObject(File(dir, "syllables/counts.json").readText(Charsets.UTF_8)).getJSONObject("counts")
        assertTrue(counts.length() >= 20)
        for (token in counts.keys()) assertEquals("chữ \"$token\"", counts.getInt(token), SyllableSpread.syllables(token))
    }

    @Test
    fun eachSpokenWordCarriesItsCodePointPosition() {
        val found = SyllableSpread.boundaries("Ừ, đi thôi.", 1600)
        assertEquals(listOf(Boundary(0, 400, "Ừ,", 0), Boundary(800, 1200, "đi", 3), Boundary(1200, 1600, "thôi.", 6)), found)
        assertEquals(emptyList<Boundary>(), SyllableSpread.boundaries("Xin chào", 0))
    }

    private fun frames(count: Int) = ByteArray(96 * count) { i -> when (i % 96) { 0 -> 0xFF.toByte(); 1 -> 0xF3.toByte(); 2 -> 0x44; 3 -> 0xC4.toByte(); else -> 0 } }

    @Test
    fun mp3DurationCountsFramesAndSkipsTagsAndJunk() {
        assertEquals(1200L, Mp3.durationMs(frames(50)))
        val id3 = byteArrayOf('I'.code.toByte(), 'D'.code.toByte(), '3'.code.toByte(), 4, 0, 0, 0, 0, 0, 20) + ByteArray(20)
        assertEquals(1200L, Mp3.durationMs(id3 + frames(25) + "junk".toByteArray() + id3 + frames(25)))
        // MPEG-1 128 kbps 44,1 kHz: 417/418 byte, 1152 mẫu (26 122 µs) - cùng con số với mp3.py.
        val mpeg1 = (0 until 38).fold(ByteArray(0)) { all, i ->
            val pad = if (i % 3 == 0) 1 else 0
            all + byteArrayOf(0xFF.toByte(), 0xFB.toByte(), (0x90 or (pad shl 1)).toByte(), 0x64) + ByteArray(417 + pad - 4)
        }
        assertEquals(38L * 26122 / 1000, Mp3.durationMs(mpeg1))
        assertEquals(0L, Mp3.durationMs(ByteArray(0)))
    }

    @Test
    fun base64RoundTrips() {
        for (size in 0..7) {
            val bytes = ByteArray(size) { (it * 37 + 5).toByte() }
            assertEquals(bytes.toList(), WebSocket.unbase64(WebSocket.base64(bytes)).toList())
        }
        assertEquals("Xin chào", String(WebSocket.unbase64("WGluIGNow6Bv"), Charsets.UTF_8))
    }
}
