package vn.abook.player.ui.data

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** "Làm trước": đọc trạng thái lõi, chỉ lắng nghe khi có chỗ đang xem, lỗi của lần bấm, dấu "Đã làm sẵn". */
class PrepareStateTest {
    private fun state(source: FakePrepareSource) = PrepareState(source, CoroutineScope(Dispatchers.Unconfined))

    @Test
    fun `status json becomes a status`() {
        val json = JSONObject("""{"state":"running","bookId":"b","voice":"vieneu:a","label":"2 chương tới","total":20,"offered":20,"done":4,"audioSeconds":600,
            "secondsLeft":null,"error":"","chargingOnly":false,"waitingFor":"wifi","chapters":[{"id":2,"title":"Hai","total":10,"done":10,"ready":true},{"id":3,"title":"Ba","total":10,"done":0,"ready":false}]}""")
        val status = PrepareStatus.parse(json)
        assertEquals("running", status.state)
        assertNull(status.secondsLeft)
        assertEquals("wifi", status.waitingFor)
        assertEquals(false, status.chargingOnly)
        assertEquals(setOf(2), status.readyIds("b"))
        assertEquals("việc của cuốn khác không đánh dấu chương", emptySet<Int>(), status.readyIds("other"))
        assertNull("khoá null không thành chữ null", PrepareStatus.parse(JSONObject("""{"state":"idle","waitingFor":null}""")).waitingFor)
    }

    @Test
    fun `plan json keeps an unknown estimate unknown`() {
        assertNull(PreparePlan.parse(JSONObject("""{"chapters":2,"offered":2,"audioSeconds":1800,"secondsEstimate":null}""")).secondsEstimate)
        assertEquals(1500L, PreparePlan.parse(JSONObject("""{"chapters":2,"offered":3,"audioSeconds":1800,"secondsEstimate":1500}""")).secondsEstimate)
    }

    @Test
    fun `listens only while something shows it`() {
        val source = FakePrepareSource(PrepareStatus("done", "v"))
        val prepare = state(source)
        assertEquals(0, source.listening)
        prepare.watch(true)
        prepare.watch(true)
        assertEquals("hai nơi xem, một listener", 1, source.listening)
        assertEquals("done", prepare.status.value.state)
        source.push(PrepareStatus("running", "v"))
        assertTrue(prepare.status.value.running)
        prepare.watch(false)
        assertEquals("còn một nơi xem", 1, source.listening)
        prepare.watch(false)
        assertEquals(0, source.listening)
    }

    @Test
    fun `plan is asked once per request and dropped for no chapters`() {
        val source = FakePrepareSource(plan = PreparePlan(2, 2, 600, null))
        val prepare = state(source)
        prepare.loadPlan("vieneu:a", "b", listOf(2, 3))
        prepare.loadPlan("vieneu:a", "b", listOf(2, 3))
        assertEquals(listOf("plan vieneu:a [2, 3]"), source.calls)
        assertEquals(2, prepare.plan.value?.chapters)
        prepare.loadPlan("vieneu:a", "b", emptyList())
        assertNull(prepare.plan.value)
    }

    @Test
    fun `start sends the charging choice and a failure becomes a sentence`() {
        val ok = FakePrepareSource()
        val prepare = state(ok)
        prepare.setChargingOnly(false)
        prepare.start("vieneu:a", "b", listOf(2), "Hai")
        assertEquals(listOf("charging=false", "start vieneu:a [2] Hai charging=false"), ok.calls)
        assertTrue(prepare.status.value.running)
        val bad = state(FakePrepareSource(failWith = "Chưa cho phép gửi chữ"))
        bad.start("vieneu:a", "b", listOf(2), "Hai")
        assertEquals("Chưa cho phép gửi chữ", bad.failure.value)
        assertEquals(false, bad.busy.value)
        bad.dismissFailure()
        assertNull(bad.failure.value)
    }
}
