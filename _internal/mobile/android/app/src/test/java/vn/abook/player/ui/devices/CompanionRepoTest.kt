package vn.abook.player.ui.devices

import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Test
import vn.abook.player.ui.FakeCompanionCore

/** Máy phát khác (CompanionRepo) không cần Android: lượt hỏi định kỳ, lỗi mạng thoáng qua. */
class CompanionRepoTest {
    @Test
    fun `a dropped poll stops saying it once the next poll gets through`() = runBlocking {
        val core = FakeCompanionCore()
        var offline = false
        val flaky = object : CompanionCore by core {
            override suspend fun players(): JSONArray = if (offline) error("offline") else core.players()
        }
        val repo = CompanionRepo(flaky) { 1_000 }
        offline = true
        repo.refresh()
        assertEquals("Chưa nối được, bạn thử lại", repo.state.value.problem)
        offline = false
        repo.refresh()
        assertEquals("", repo.state.value.problem)
        assertEquals(1, repo.state.value.players.size)
    }

    @Test
    fun `a refused command is still reported after the next poll`() = runBlocking {
        val core = FakeCompanionCore()
        core.rows.getJSONObject(0).put("acks", JSONArray().put(org.json.JSONObject().put("id", "a1").put("ok", false).put("message", "Không mở được cuốn này")))
        val repo = CompanionRepo(core) { 1_000 }
        repo.refresh()
        assertEquals("Máy tính phòng khách: Không mở được cuốn này", repo.state.value.problem)
        repo.refresh()
        assertEquals("Máy tính phòng khách: Không mở được cuốn này", repo.state.value.problem)
    }
}
