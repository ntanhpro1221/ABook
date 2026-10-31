package vn.abook.player.ui.voice

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Việc của Giọng đọc làm thêm với nguồn giả: tải / huỷ / gỡ giọng trên máy (kể cả tiến độ chỉ đi tới và danh sách giọng đọc lại khi xong), đồng ý gửi chữ, khoá (lưu trước khi
 * kiểm, khoá chỉ đi xuống nguồn), nghe thử (mẫu về muộn bị bỏ), Nhạc của tôi. Phạm vi chạy ngay (Unconfined): sau mỗi lời gọi trạng thái đã xong; chỉ việc bị giữ bằng cổng mới dang dở.
 */
class VoiceStateTest {
    private val source = FakeVoiceSource()
    private val player = FakeSamplePlayer()
    private var changed = 0
    private val viet = ModuleKind.Vieneu

    private val scope = CoroutineScope(Dispatchers.Unconfined)
    private val imports = MineImports(source, scope)

    private fun state(pollMs: Long = 3_600_000) = VoiceState(source, scope, player, { changed++ }, pollMs, imports)

    private fun eventually(what: String, condition: () -> Boolean) {
        val until = System.currentTimeMillis() + 5_000
        while (!condition()) {
            if (System.currentTimeMillis() > until) throw AssertionError("không xảy ra: $what")
            Thread.sleep(5)
        }
    }

    // ---- giọng tải về máy ----

    @Test
    fun `opening the page reads both modules, the keys and the consents`() {
        source.modules[viet] = Fixtures.ready(viet)
        source.allowed += "edge"
        val voice = state()
        voice.openVoice()
        assertEquals(ModuleState.Ready, voice.modules.value.getValue(viet).status?.state)
        assertEquals(ModuleState.Missing, voice.modules.value.getValue(ModuleKind.Supertonic).status?.state)
        assertTrue(voice.keys.value.loaded)
        assertTrue(voice.allowed("edge"))
        assertFalse(voice.allowed("azure"))
    }

    @Test
    fun `pressing download asks the core for exactly that choice and remembers it for retry`() {
        val voice = state()
        voice.openVoice()
        voice.download(viet, listOf("nano"))
        assertEquals(listOf(viet to listOf("nano")), source.started)
        assertEquals(listOf("nano"), voice.modules.value.getValue(viet).pending)
    }

    @Test
    fun `a download the core refuses shows its sentence on the row and retry asks again`() {
        source.startError = VoiceFailure("Máy không còn đủ chỗ trống")
        val voice = state()
        voice.openVoice()
        voice.download(viet, listOf("turbo"))
        val shown = voice.modules.value.getValue(viet).shown
        assertEquals(ModuleState.Error, shown?.state)
        assertEquals("Chưa tải được Giọng VieNeu. Máy không còn đủ chỗ trống", shown?.error)
        assertEquals(ModuleAction.Retry, VoiceText.rows(shown!!, listOf("turbo")).first().action)
        source.startError = null
        voice.retry(viet)
        assertEquals(listOf(viet to listOf("turbo")), source.started)
        assertEquals("", voice.modules.value.getValue(viet).problem)
    }

    @Test
    fun `progress only moves forward, and finishing refreshes the voice list and the other module`() {
        val voice = state(pollMs = 10)
        voice.openVoice()
        source.modules[viet] = Fixtures.downloading(viet, 30)
        voice.download(viet, listOf("turbo"))
        eventually("30%") { voice.progress(viet).value == 0.3f }
        source.modules[viet] = Fixtures.downloading(viet, 20)
        Thread.sleep(60)
        assertEquals("tiến độ không lùi", 0.3f, voice.progress(viet).value, 0.0f)
        source.modules[viet] = Fixtures.downloading(viet, 80)
        eventually("80%") { voice.progress(viet).value == 0.8f }
        assertEquals(0, changed)
        source.modules[ModuleKind.Supertonic] = Fixtures.ready(ModuleKind.Supertonic)
        source.modules[viet] = Fixtures.ready(viet)
        eventually("xong") { voice.modules.value.getValue(viet).status?.state == ModuleState.Ready }
        eventually("danh sách giọng đọc lại") { changed == 1 }
        assertEquals(0f, voice.progress(viet).value, 0.0f)
        eventually("mô-đun kia hỏi lại") { voice.modules.value.getValue(ModuleKind.Supertonic).status?.state == ModuleState.Ready }
        assertTrue(voice.modules.value.getValue(viet).pending.isEmpty())
    }

    @Test
    fun `cancel goes to the core and the row falls back to a download`() {
        val voice = state()
        voice.openVoice()
        source.modules[viet] = Fixtures.downloading(viet, 10)
        voice.download(viet, listOf("turbo"))
        voice.cancel(viet)
        assertEquals(listOf(viet), source.cancels)
        assertEquals(ModuleState.Missing, voice.modules.value.getValue(viet).status?.state)
    }

    @Test
    fun `removing a voice reloads the list, and a refusal comes back as a sentence`() {
        source.modules[viet] = Fixtures.ready(viet)
        val voice = state()
        voice.openVoice()
        assertNull(runBlocking { voice.remove(viet, "turbo") })
        assertEquals(listOf(viet to "turbo"), source.removed)
        assertEquals(1, changed)
        source.removeError = VoiceFailure("Giọng đang được dùng để làm trước")
        assertEquals("Giọng đang được dùng để làm trước", runBlocking { voice.remove(viet, "turbo") })
        assertEquals(1, changed)
    }

    @Test
    fun `the suggestion downloads the light voice or switches the books, never silently`() {
        source.modules[viet] = Fixtures.ready(viet, suggestion = ModuleSuggestion("turbo", 1.4, "nano", installed = false))
        val voice = state()
        voice.openVoice()
        assertNull(runBlocking { voice.applySuggestion(viet) })
        assertEquals(listOf(viet to listOf("nano")), source.started)
        assertTrue(source.switched.isEmpty())

        source.modules[viet] = Fixtures.ready(viet, suggestion = ModuleSuggestion("turbo", 1.4, "nano", installed = true))
        voice.openVoice()
        changed = 0 // giọng Nano vừa tải xong ở trên cũng báo "danh sách giọng đổi"; đếm riêng lần đổi sách
        assertNull(runBlocking { voice.applySuggestion(viet) })
        assertEquals(Triple("vieneu:turbo/", "vieneu:nano/", VoiceState.ONLINE_VOICE), source.switched.single())
        assertEquals(1, changed)

        source.modules[viet] = Fixtures.ready(viet, suggestion = ModuleSuggestion("turbo", 1.4, "online", installed = false))
        voice.openVoice()
        runBlocking { voice.applySuggestion(viet) }
        assertEquals(Triple("vieneu:turbo/", VoiceState.ONLINE_VOICE, VoiceState.ONLINE_VOICE), source.switched.last())
    }

    // ---- đồng ý gửi chữ ----

    @Test
    fun `consent is remembered per provider`() {
        val voice = state()
        voice.openVoice()
        assertFalse(voice.allowed("azure"))
        runBlocking { voice.allow("azure") }
        assertTrue(voice.allowed("azure"))
        assertFalse(voice.allowed("google"))
        assertEquals(setOf("azure"), source.allowed)
    }

    // ---- khoá ----

    @Test
    fun `a key is saved trimmed and only the masked tail comes back`() {
        val voice = state()
        voice.openVoice()
        val azure = voice.keys.value.providers.first { it.id == "azure" }
        assertEquals("Dán khoá trước đã.", runBlocking { voice.saveKey(azure, "  ", "") })
        assertNull(runBlocking { voice.saveKey(azure, "  secret-0001-WXYZ ", " southeastasia ") })
        assertEquals(Triple("azure", "secret-0001-WXYZ", "southeastasia"), source.savedKeys.single())
        val after = voice.keys.value.providers.first { it.id == "azure" }
        assertTrue(after.hasKey)
        assertEquals("••••WXYZ", after.masked)
        assertFalse(after.toString().contains("secret"))
    }

    @Test
    fun `a bad region comes back as the core sentence`() {
        source.saveError = VoiceFailure("Vùng Azure chưa đúng (ví dụ: southeastasia)")
        val voice = state()
        voice.openVoice()
        val azure = voice.keys.value.providers.first { it.id == "azure" }
        assertEquals("Vùng Azure chưa đúng (ví dụ: southeastasia)", runBlocking { voice.saveKey(azure, "k", "???") })
    }

    @Test
    fun `checking saves a newly typed key first, then asks the service, then refreshes the voices`() {
        val voice = state()
        voice.openVoice()
        val google = voice.keys.value.providers.first { it.id == "google" }
        val result = runBlocking { voice.checkKey(google, "new-key-1234", "") }
        assertTrue(result.ok)
        assertEquals("google", source.savedKeys.single().first)
        assertEquals(listOf("google"), source.checked)
        assertTrue(voice.keys.value.providers.first { it.id == "google" }.valid)
        assertEquals(1, changed)
    }

    @Test
    fun `checking a saved key does not save again and a refusal is shown as is`() {
        source.keys = source.keys.map { if (it.id == "fpt") it.copy(hasKey = true, masked = "••••1234") else it }.toMutableList()
        source.checkResult = { KeyResult(false, "Khoá FPT.AI bị từ chối (401).") }
        val voice = state()
        voice.openVoice()
        val fpt = voice.keys.value.providers.first { it.id == "fpt" }
        val result = runBlocking { voice.checkKey(fpt, "", "") }
        assertFalse(result.ok)
        assertEquals("Khoá FPT.AI bị từ chối (401).", result.text)
        assertTrue(source.savedKeys.isEmpty())
    }

    @Test
    fun `a key that cannot be saved stops the check`() {
        source.saveError = VoiceFailure("Chưa lưu được khoá")
        val voice = state()
        voice.openVoice()
        val google = voice.keys.value.providers.first { it.id == "google" }
        val result = runBlocking { voice.checkKey(google, "k", "") }
        assertFalse(result.ok)
        assertEquals("Chưa lưu được khoá", result.text)
        assertTrue(source.checked.isEmpty())
    }

    @Test
    fun `removing a key clears the row and refreshes the voice list`() {
        source.keys = source.keys.map { if (it.id == "viettel") it.copy(hasKey = true, masked = "••••9999", valid = true, voices = 2) else it }.toMutableList()
        val voice = state()
        voice.openVoice()
        val viettel = voice.keys.value.providers.first { it.id == "viettel" }
        assertNull(runBlocking { voice.removeKey(viettel) })
        assertEquals(listOf("viettel"), source.removedKeys)
        assertFalse(voice.keys.value.providers.first { it.id == "viettel" }.hasKey)
        assertEquals(1, changed)
        assertEquals("Chưa có khoá", voice.summary.value.keys)
    }

    @Test
    fun `an unreadable key store is a retryable failure, not an empty list`() {
        source.keysError = VoiceFailure("lỗi")
        val voice = state()
        voice.loadKeys()
        assertTrue(voice.keys.value.failed)
        assertFalse(voice.keys.value.loaded)
        source.keysError = null
        voice.loadKeys()
        assertTrue(voice.keys.value.loaded)
        assertFalse(voice.keys.value.failed)
    }

    // ---- nghe thử ----

    @Test
    fun `a sample is fetched with the fixed sentence, played, and the row goes back to idle when it ends`() {
        val voice = state()
        voice.play("edge:vi-VN-HoaiMyNeural")
        assertEquals("edge:vi-VN-HoaiMyNeural" to VoiceText.SAMPLE, source.sampled.single())
        assertEquals("edge:vi-VN-HoaiMyNeural", voice.sample.value.playing)
        assertEquals(listOf("/cache/edge:vi-VN-HoaiMyNeural.mp3"), player.played)
        player.finish()
        assertEquals(SampleUi(), voice.sample.value)
    }

    @Test
    fun `pressing the playing voice again stops it`() {
        val voice = state()
        voice.play("a")
        voice.play("a")
        assertEquals(SampleUi(), voice.sample.value)
        assertEquals(2, player.stops)
        assertEquals(1, player.played.size)
    }

    @Test
    fun `a late sample of the first voice never plays over the second`() {
        val gate = CompletableDeferred<Unit>()
        source.sampleGate = gate
        val voice = state()
        voice.play("a")
        assertEquals("a", voice.sample.value.loading)
        voice.play("b")
        assertEquals("b", voice.sample.value.loading)
        gate.complete(Unit)
        assertEquals(listOf("/cache/b.mp3"), player.played)
        assertEquals("b", voice.sample.value.playing)
    }

    @Test
    fun `stopping while the sample is still being made means it never plays`() {
        val gate = CompletableDeferred<Unit>()
        source.sampleGate = gate
        val voice = state()
        voice.play("a")
        voice.stopSample()
        gate.complete(Unit)
        assertTrue(player.played.isEmpty())
        assertEquals(SampleUi(), voice.sample.value)
    }

    @Test
    fun `a sample that fails says so on that voice only`() {
        source.sampleError = VoiceFailure("Không có mạng để lấy giọng này")
        val voice = state()
        voice.play("azure:vi-VN-HoaiMyNeural")
        assertEquals(SampleFailure("azure:vi-VN-HoaiMyNeural", "Không có mạng để lấy giọng này"), voice.sample.value.failed)
        source.sampleError = null
        voice.play("azure:vi-VN-HoaiMyNeural")
        assertNull(voice.sample.value.failed)
        player.fail()
        assertEquals("azure:vi-VN-HoaiMyNeural", voice.sample.value.failed?.voice)
    }

    // ---- Nhạc của tôi ----

    @Test
    fun `my music lists the store and summarises it`() {
        source.tracks = listOf(Fixtures.track("Một"), Fixtures.track("Hai"))
        val voice = state()
        assertNull(voice.summary.value.music)
        voice.loadMusic()
        assertEquals(2, voice.music.value.tracks.size)
        assertEquals("2 bài", voice.summary.value.music)
    }

    @Test
    fun `importing reports progress, then a summary, and keeps the files that failed on their own lines`() {
        val gate = CompletableDeferred<Unit>()
        source.importGate = gate
        source.importResult = { uris -> MusicImportResult(uris.map { Fixtures.track(it) }, uris.size - 1, 0, listOf("“x.txt”: không phải file nhạc.")) }
        val voice = state()
        voice.importMusic(listOf("content://a", "content://b", "content://x"))
        assertTrue(voice.music.value.importing)
        assertEquals(3, voice.music.value.total)
        assertEquals(1f, voice.importProgress.value, 0f)
        gate.complete(Unit)
        val ui = voice.music.value
        assertFalse(ui.importing)
        assertEquals("Đã thêm: 2 bài mới", ui.summary)
        assertEquals(listOf("“x.txt”: không phải file nhạc."), ui.problems)
        assertEquals(3, ui.tracks.size)
    }

    @Test
    fun `a second pick while importing is ignored and an empty pick does nothing`() {
        val gate = CompletableDeferred<Unit>()
        source.importGate = gate
        val voice = state()
        voice.importMusic(emptyList())
        assertTrue(source.imported.isEmpty())
        voice.importMusic(listOf("content://a"))
        voice.importMusic(listOf("content://b"))
        assertEquals(1, source.imported.size)
        gate.complete(Unit)
    }

    @Test
    fun `removing a track updates the list and a refusal is a sentence`() {
        source.tracks = listOf(Fixtures.track("Một"), Fixtures.track("Hai"))
        val voice = state()
        voice.loadMusic()
        val first = voice.music.value.tracks.first()
        assertNull(runBlocking { voice.removeTrack(first.link) })
        assertEquals(1, voice.music.value.tracks.size)
        source.trackRemoveError = VoiceFailure("Bài này không còn trong Nhạc của tôi")
        assertEquals("Bài này không còn trong Nhạc của tôi", runBlocking { voice.removeTrack("local:zzz") })
    }
}
