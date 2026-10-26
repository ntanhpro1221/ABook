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
        assertEquals("Chưa nối được máy kia.", repo.state.value.problem)
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

    @Test
    fun `a refused command without words says what the web says`() = runBlocking {
        val core = FakeCompanionCore()
        core.rows.getJSONObject(0).put("acks", JSONArray().put(org.json.JSONObject().put("id", "a2").put("ok", false)))
        val repo = CompanionRepo(core) { 1_000 }
        repo.refresh()
        assertEquals("Máy tính phòng khách: không làm được lệnh này", repo.state.value.problem)
    }

    @Test
    fun `a sleep timer shows on the other player before it answers`() = runBlocking {
        val core = FakeCompanionCore()
        lateinit var repo: CompanionRepo
        val shown = ArrayList<String>()
        val spy = object : CompanionCore by core {
            override suspend fun command(device: String, command: org.json.JSONObject) {
                shown += repo.state.value.players.single().sleep
                core.command(device, command)
            }
        }
        repo = CompanionRepo(spy) { 1_000 }
        repo.refresh()
        val player = repo.state.value.players.single()
        repo.send(player, "sleep", minutes = 30)
        repo.send(player, "sleep", mode = "chapter")
        repo.send(player, "sleep", minutes = 0)
        assertEquals(listOf("minutes", "chapter", "off"), shown)
    }
}
