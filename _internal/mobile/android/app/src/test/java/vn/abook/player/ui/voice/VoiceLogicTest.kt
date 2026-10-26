package vn.abook.player.ui.voice

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Lời và hình dữ liệu của Giọng đọc làm thêm: cỡ file, hàng giọng trên máy, đồng ý gửi chữ, khoá, Nhạc của tôi. Hàm thuần, không Android. */
class VoiceLogicTest {
    private val turbo = ModuleKind.Vieneu

    @Test
    fun `sizes use one decimal system the way the web does`() {
        assertEquals("850 MB", VoiceText.size(850_000_000))
        assertEquals("1,20 GB", VoiceText.size(1_200_000_000))
        assertEquals("3,5 MB", VoiceText.size(3_500_000))
        assertEquals("1 KB", VoiceText.size(400))
        assertEquals("198 MB", VoiceText.size(198_000_000))
    }

    @Test
    fun `the core status json becomes a status the screen can draw`() {
        val json = JSONObject()
            .put("state", "downloading").put("done", 99_000_000L).put("total", 198_000_000L).put("error", "").put("reason", "")
            .put(
                "choices",
                JSONArray().put(
                    JSONObject().put("id", "turbo").put("label", "Giọng VieNeu").put("detail", "Giọng nữ").put("bytes", 198_000_000L)
                        .put("installed", false).put("recommended", true).put("removable", true),
                ),
            )
            .put("benchmark", JSONObject().put("nano", JSONObject().put("rtf", 0.5).put("firstAudioMs", 900L)))
            .put("suggestion", JSONObject().put("tier", "turbo").put("rtf", 1.4).put("switchTo", "nano").put("installed", false))
            .put("metered", true)
        val status = ModuleJson.status(json)
        assertEquals(ModuleState.Downloading, status.state)
        assertEquals(50, status.percent)
        assertTrue(status.working)
        assertEquals("turbo", status.choices.single().id)
        assertEquals(0.5, status.benchmark.getValue("nano").rtf, 0.0)
        assertEquals("nano", status.suggestion?.switchTo)
        assertTrue(status.metered)
    }

    @Test
    fun `a missing module offers a download with its size and the recommended mark`() {
        val rows = VoiceText.rows(Fixtures.missing(turbo), emptyList())
        val first = rows.first()
        assertEquals("Giọng VieNeu", first.title)
        assertEquals(ModuleAction.Download("Tải (198 MB)"), first.action)
        assertTrue(first.hint.startsWith("Khuyên dùng"))
        assertFalse(first.progress)
        assertEquals(ModuleAction.Download("Tải (52 MB)"), rows[1].action)
    }

    @Test
    fun `downloading puts the progress and cancel on the row you pressed and nowhere else`() {
        val rows = VoiceText.rows(Fixtures.downloading(turbo, 40), listOf("nano"))
        assertEquals(ModuleAction.Cancel, rows[1].action)
        assertTrue(rows[1].progress)
        assertEquals("Đang tải 198 MB · 40%", rows[1].hint)
        assertEquals(ModuleAction.None, rows[0].action)
        assertFalse(rows[0].progress)
    }

    @Test
    fun `a failed download shows the problem in danger with a retry`() {
        val row = VoiceText.rows(Fixtures.failed(turbo), listOf("turbo")).first()
        assertEquals(ModuleAction.Retry, row.action)
        assertTrue(row.problem)
        assertTrue(row.hint.startsWith("Mất mạng"))
    }

    @Test
    fun `an installed choice says how fast this phone reads it and opens its sheet`() {
        val fast = VoiceText.rows(Fixtures.ready(turbo, mapOf("turbo" to ModuleBench(0.5, 800))), emptyList()).first()
        assertEquals(ModuleAction.Manage, fast.action)
        assertEquals("Đọc trực tiếp được · nhanh gấp 2,0 lần", fast.hint)
        val slow = VoiceText.rows(Fixtures.ready(turbo, mapOf("turbo" to ModuleBench(1.4, 800))), emptyList()).first()
        assertTrue(slow.hint.startsWith("Chậm hơn tốc độ nghe"))
        assertEquals("Có bản mới · 12 MB", VoiceText.rows(Fixtures.outdated(turbo), emptyList()).first().hint)
        assertEquals("Đã có trên máy", VoiceText.rows(Fixtures.ready(turbo), emptyList()).first().hint)
        assertTrue(VoiceText.rows(Fixtures.benchmarking(turbo), emptyList()).first().hint.startsWith("Đang thử giọng"))
    }

    @Test
    fun `an unsupported phone says why instead of offering a download`() {
        val row = VoiceText.rows(Fixtures.unsupported(turbo), emptyList()).first()
        assertEquals(ModuleAction.None, row.action)
        assertEquals("Máy này chưa dùng được: thiếu bộ nhớ trống.", row.hint)
    }

    @Test
    fun `a cancelled download is remembered on the row that was cancelled`() {
        val status = Fixtures.missing(turbo).copy(cancelled = true)
        val row = VoiceText.rows(status, listOf("nano"))[1]
        assertTrue(row.hint.startsWith("Đã huỷ"))
        assertTrue(VoiceText.hasLeftovers(Fixtures.leftover(turbo).choices.first()))
        assertFalse(VoiceText.hasLeftovers(Fixtures.ready(turbo).choices.first()))
    }

    @Test
    fun `supertonic fast says whose faster version it is`() {
        assertEquals("Supertonic nhanh hơn", VoiceText.choiceTitle(Fixtures.missing(ModuleKind.Supertonic).choices[1]))
    }

    @Test
    fun `metered data warns only when there is something to download`() {
        assertNull(VoiceText.metered(Fixtures.missing(turbo), 198_000_000))
        val warned = VoiceText.metered(Fixtures.missing(turbo, metered = true), 198_000_000)
        assertTrue(warned!!.contains("198 MB"))
        assertNull(VoiceText.metered(Fixtures.missing(turbo, metered = true), 0))
    }

    @Test
    fun `the benchmark sentence tells a slow phone to use prepare ahead`() {
        val slow = VoiceText.benchmark("turbo", ModuleBench(1.5, 2000), 0.8)
        assertTrue(slow.contains("không kịp đọc trực tiếp"))
        assertTrue(slow.contains("Làm trước"))
        val fast = VoiceText.benchmark("nano", ModuleBench(0.5, 1500), 0.8)
        assertTrue(fast.contains("nhanh gấp 2,0 lần"))
        assertTrue(fast.contains("1,5 giây"))
    }

    @Test
    fun `the suggestion offers a single action and never switches by itself`() {
        val (text, label) = VoiceText.suggestion(ModuleSuggestion("turbo", 1.4, "nano", installed = false))
        assertTrue(text.contains("đọc chậm"))
        assertEquals("Tải giọng VieNeu Nano", label)
        assertEquals("Dùng giọng VieNeu Nano", VoiceText.suggestion(ModuleSuggestion("turbo", 1.4, "nano", installed = true)).second)
        assertEquals("Dùng giọng trực tuyến", VoiceText.suggestion(ModuleSuggestion("supertonic", 1.4, "online", installed = false)).second)
        assertEquals("vieneu:turbo/", VoiceText.tierVoicePrefix("turbo"))
        assertEquals("supertonic:", VoiceText.tierVoicePrefix("supertonic"))
    }

    @Test
    fun `online providers need consent and the sentence names where the text goes`() {
        assertTrue(VoiceText.isOnline("edge"))
        for (provider in listOf("azure", "google", "fpt", "viettel")) assertTrue(VoiceText.isOnline(provider))
        for (provider in listOf("vieneu", "supertonic", "device")) assertFalse(VoiceText.isOnline(provider))
        assertEquals("Hoài My", VoiceText.spokenName("Hoài My (Edge)"))
        val edge = VoiceText.consent("Hoài My", "edge")
        assertTrue(edge.contains("máy chủ Microsoft"))
        val keyed = VoiceText.consent("Hoài My (Azure)", "azure")
        assertTrue(keyed.contains("tính tiền vào tài khoản của bạn"))
        assertTrue(keyed.contains("Azure Speech"))
    }

    @Test
    fun `a key row never shows more than the masked tail`() {
        assertEquals("Miễn phí 500.000 ký tự mỗi tháng", VoiceText.keyHint(Fixtures.provider("azure", "Azure Speech")))
        assertEquals("••••WXYZ · Dùng được · 4 giọng", VoiceText.keyHint(Fixtures.provider("azure", "Azure Speech", hasKey = true, valid = true)))
        assertEquals("••••WXYZ · Chưa dùng được", VoiceText.keyHint(Fixtures.provider("azure", "Azure Speech", hasKey = true)))
        assertEquals("Chưa có khoá", VoiceText.keySummary(VoiceText.KEYED.map { (id, name) -> Fixtures.provider(id, name) }))
        val some = listOf(Fixtures.provider("azure", "Azure Speech", hasKey = true), Fixtures.provider("google", "Google Cloud"), Fixtures.provider("fpt", "FPT.AI", hasKey = true))
        assertEquals("Azure Speech · FPT.AI", VoiceText.keySummary(some))
    }

    @Test
    fun `the key check json becomes a sentence the listener understands`() {
        val ok = KeyJson.check(JSONObject().put("ok", true).put("voices", 6).put("provider", JSONObject().put("id", "azure").put("hasKey", true)))
        assertTrue(ok.ok)
        assertEquals("Dùng được · 6 giọng tiếng Việt", ok.text)
        val bad = KeyJson.check(JSONObject().put("ok", false).put("message", "Khoá Azure bị từ chối (401)."))
        assertFalse(bad.ok)
        assertEquals("Khoá Azure bị từ chối (401).", bad.text)
        assertEquals("Khoá chưa dùng được.", KeyJson.check(JSONObject().put("ok", false)).text)
    }

    @Test
    fun `the provider json keeps only what the core makes public`() {
        val provider = KeyJson.provider(
            JSONObject().put("id", "azure").put("name", "Azure Speech").put("hasKey", true).put("masked", "••••abcd").put("region", "southeastasia")
                .put("valid", true).put("voices", 3).put("limits", JSONObject().put("free", "Miễn phí 500.000 ký tự mỗi tháng").put("region", true)),
        )
        assertEquals("••••abcd", provider.masked)
        assertTrue(provider.region)
        assertEquals("southeastasia", provider.regionValue)
        assertEquals(3, provider.voices)
    }

    @Test
    fun `my music lines and the import summary`() {
        val track = Fixtures.track("Bản nhạc", creator = "Nghệ sĩ", duration = 187.0)
        assertEquals("Nghệ sĩ · 3:07", VoiceText.trackLine(track))
        assertEquals("3:07", VoiceText.trackLine(track.copy(creator = "")))
        assertEquals("Chưa có bài nào", VoiceText.musicSummary(0))
        assertEquals("12 bài", VoiceText.musicSummary(12))
        assertEquals("Đã thêm: 2 bài mới, 1 bài đã có từ trước", VoiceText.imported(MusicImportResult(emptyList(), 2, 1, emptyList())))
        assertEquals("", VoiceText.imported(MusicImportResult(emptyList(), 0, 0, listOf("x"))))
    }

    @Test
    fun `the music json maps entries and the import answer`() {
        val rows = JSONArray().put(JSONObject().put("link", "local:abc").put("title", "Một bài").put("creator", "Ai đó").put("duration", 60.5).put("bytes", 1234L).put("analysed", true))
        val tracks = MusicJson.tracks(rows)
        assertEquals("local:abc", tracks.single().link)
        val answer = MusicJson.imported(
            JSONObject().put("tracks", rows).put("added", JSONArray().put(JSONObject())).put("existing", JSONArray()).put("failed", JSONArray().put("“x.txt”: không phải file nhạc.")),
        )
        assertEquals(1, answer.added)
        assertEquals(0, answer.existing)
        assertEquals(listOf("“x.txt”: không phải file nhạc."), answer.failed)
    }

    @Test
    fun `no user facing string cuts words with an ellipsis`() {
        val all = listOf(VoiceText.REMOVE_ASK, VoiceText.SAMPLE) + VoiceText.KEYED.keys.map(VoiceText::keyHelp) + listOf("azure", "google", "fpt", "viettel", "edge").map { VoiceText.consent("Giọng", it) }
        for (line in all) assertFalse(line, line.contains("…") || line.endsWith("..."))
    }
}
