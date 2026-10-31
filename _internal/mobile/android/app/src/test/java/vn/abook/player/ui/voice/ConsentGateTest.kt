package vn.abook.player.ui.voice

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Nguồn đồng ý giả: ghi lại điều bạn đã đồng ý / chọn; có thể ném lỗi. */
class FakeConsentSource : ConsentSource {
    var all = listOf(
        ConsentVoice("edge:vi-VN-HoaiMyNeural", "Hoài My (Edge)", "edge", true),
        ConsentVoice("edge:vi-VN-NamMinhNeural", "Nam Minh (Edge)", "edge", true),
        ConsentVoice("vieneu:nano/aihan", "Ái Hân (VieNeu)", "vieneu", false),
    )
    var chosenVoice = "edge:vi-VN-HoaiMyNeural"
    val agreed = mutableSetOf<String>()
    val picked = ArrayList<Pair<String, String>>()
    var fail: Exception? = null
    var asked = 0

    override suspend fun voices(): List<ConsentVoice> {
        asked++
        fail?.let { throw it }
        return all
    }

    override suspend fun chosen(bookId: String) = chosenVoice
    override suspend fun consents(): Set<String> = agreed.toSet()
    override suspend fun grant(provider: String) { agreed += provider }
    override suspend fun choose(bookId: String, voiceId: String) { picked += bookId to voiceId }
}

/** Cửa hỏi đồng ý: chưa chữ nào đi (lệnh phát chưa chạy) khi chưa có câu trả lời, mỗi cách trả lời làm đúng việc của nó. Phạm vi Unconfined: sau mỗi lời gọi mọi thứ đã xong tới chỗ chờ. */
class ConsentGateTest {
    private val source = FakeConsentSource()
    private val gate = ConsentGate(source, CoroutineScope(Dispatchers.Unconfined))
    private var played = 0
    private val play = { played++; Unit }

    private fun request() = gate.request.value

    @Test
    fun `a chapter with audio plays at once and asks nothing`() {
        gate.before("b1", false, play)
        assertEquals(1, played)
        assertNull(request())
        assertEquals("không chạm tới lõi", 0, source.asked)
    }

    @Test
    fun `a text chapter with a voice that stays on the phone plays at once`() {
        source.chosenVoice = "vieneu:nano/aihan"
        gate.before("b1", true, play)
        assertEquals(1, played)
        assertNull(request())
    }

    @Test
    fun `an online voice already agreed plays at once`() {
        source.agreed += "edge"
        gate.before("b1", true, play)
        assertEquals(1, played)
        assertNull(request())
    }

    @Test
    fun `an online voice not agreed yet asks first and plays nothing before the answer`() {
        gate.before("b1", true, play)
        assertEquals("chữ chưa đi đâu", 0, played)
        val ask = request()
        assertNotNull(ask)
        assertEquals("edge:vi-VN-HoaiMyNeural", ask!!.voice.id)
        assertEquals("danh sách đủ cho bước chọn giọng", 3, ask.voices.size)
        assertTrue("chưa đồng ý gì", source.agreed.isEmpty())
    }

    @Test
    fun `Nghe remembers the provider and plays, the book keeps following the default voice`() {
        gate.before("b1", true, play)
        val ask = request()!!
        ask.answer(ask.voice)
        assertEquals(1, played)
        assertEquals(setOf("edge"), source.agreed)
        assertTrue("không chọn giọng cho cuốn", source.picked.isEmpty())
        assertNull(request())
    }

    @Test
    fun `picking an online voice in the list agrees for its provider and chooses it for the book`() {
        gate.before("b1", true, play)
        val ask = request()!!
        ask.answer(ask.voices[1], chosen = true)
        assertEquals(1, played)
        assertEquals(setOf("edge"), source.agreed)
        assertEquals(listOf("b1" to "edge:vi-VN-NamMinhNeural"), source.picked)
    }

    @Test
    fun `picking a voice that stays on the phone chooses it and agrees to nothing`() {
        gate.before("b1", true, play)
        val ask = request()!!
        ask.answer(ask.voices[2], chosen = true)
        assertEquals(1, played)
        assertTrue(source.agreed.isEmpty())
        assertEquals(listOf("b1" to "vieneu:nano/aihan"), source.picked)
    }

    @Test
    fun `closing the box plays nothing and remembers nothing`() {
        gate.before("b1", true, play)
        request()!!.answer(null)
        assertEquals(0, played)
        assertTrue(source.agreed.isEmpty())
        assertTrue(source.picked.isEmpty())
        assertNull(request())
    }

    @Test
    fun `answering twice does nothing the second time`() {
        gate.before("b1", true, play)
        val ask = request()!!
        ask.answer(ask.voice)
        ask.answer(null)
        ask.answer(ask.voice)
        assertEquals(1, played)
    }

    @Test
    fun `a newer play replaces the question and the old one never plays`() {
        var first = 0
        gate.before("b1", true) { first++ }
        val old = request()!!
        gate.before("b2", false, play)
        assertEquals("lệnh mới chạy", 1, played)
        assertNull("câu hỏi cũ đóng", request())
        old.answer(old.voice)
        assertEquals("trả lời muộn không phát lệnh cũ", 0, first)
        assertTrue("cũng không ghi đồng ý", source.agreed.isEmpty())
    }

    @Test
    fun `a second question takes the place of the first`() {
        var first = 0
        gate.before("b1", true) { first++ }
        val old = request()!!
        gate.before("b2", true, play)
        val now = request()!!
        assertFalse(old === now)
        now.answer(now.voice)
        assertEquals(0, first)
        assertEquals(1, played)
    }

    @Test
    fun `pausing or closing the book drops the waiting play`() {
        gate.before("b1", true, play)
        gate.cancel()
        assertNull(request())
        assertEquals(0, played)
    }

    @Test
    fun `when the core cannot tell the voice the play goes on and the core stops the text itself`() {
        source.fail = IllegalStateException("không đọc được danh sách giọng")
        gate.before("b1", true, play)
        assertEquals(1, played)
        assertNull(request())
    }
}
