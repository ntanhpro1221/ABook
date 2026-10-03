package vn.abook.player.readaloud

import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.InetAddress
import java.net.ServerSocket
import kotlin.concurrent.thread

/**
 * Giọng dùng khoá của người dùng trên điện thoại (Azure, Google, FPT.AI, Viettel AI): mọi bài nói chuyện với máy chủ GIẢ trên máy này - không khoá thật, không
 * gọi dịch vụ trả tiền nào. Thử hình yêu cầu (header khoá, thân), đọc trả lời, mốc từng chữ, lý do lỗi, cất khoá.
 */
class OnlineVoicesTest {
    private val dir = java.nio.file.Files.createTempDirectory("online-voices").toFile()
    private val servers = mutableListOf<ServerSocket>()

    @After
    fun cleanUp() {
        servers.forEach { runCatching { it.close() } }
        dir.deleteRecursively()
    }

    companion object {
        const val KEY = "test-key-0123456789abcdef" // khoá giả
    }

    /** Kho trong bộ nhớ + hộp niêm giả (đảo chuỗi, có tiền tố) - Keystore thật chỉ có trên máy. */
    private class Memory : OnlineKeys.Store {
        val map = HashMap<String, String>()
        override fun get(name: String) = map[name]
        override fun put(name: String, value: String?) { if (value == null) map.remove(name) else map[name] = value }
    }

    private object Box : OnlineKeys.SecretBox {
        override fun seal(plain: String) = "sealed:" + plain.reversed()
        override fun open(sealed: String) = if (sealed.startsWith("sealed:")) sealed.removePrefix("sealed:").reversed() else null
    }

    private fun keys(provider: String, region: String = "", valid: Boolean = true, voices: List<OnlineKeys.VoiceRow> = listOf(OnlineKeys.VoiceRow("v", "V", ""))) =
        OnlineKeys(Memory(), Box).apply {
            put(provider, KEY, region)
            if (valid) mark(provider, true, voices)
        }

    private class Seen(val method: String, val path: String, val query: String?, val headers: Map<String, String>, val body: ByteArray)

    /** Máy chủ HTTP/1.1 giả tối thiểu (mỗi kết nối một yêu cầu): `route(yêu cầu)` -> (mã, content-type, thân; với 3xx thân là Location). */
    private fun server(route: (Seen) -> Triple<Int, String, ByteArray>): Pair<String, MutableList<Seen>> {
        val seen = mutableListOf<Seen>()
        val socket = ServerSocket(0, 20, InetAddress.getByName("127.0.0.1"))
        servers += socket
        thread(isDaemon = true) {
            while (true) {
                val client = runCatching { socket.accept() }.getOrNull() ?: break
                client.use { conn ->
                    val input = conn.getInputStream().buffered()
                    fun line(): String {
                        val out = ByteArrayOutputStream()
                        while (true) {
                            val b = input.read()
                            if (b < 0 || b == 10) break
                            if (b != 13) out.write(b)
                        }
                        return String(out.toByteArray(), Charsets.ISO_8859_1)
                    }
                    val (method, target) = line().split(' ').let { it[0] to it[1] }
                    val headers = HashMap<String, String>()
                    while (true) {
                        val header = line()
                        if (header.isEmpty()) break
                        headers[header.substringBefore(':').trim().lowercase()] = header.substringAfter(':').trim()
                    }
                    val length = headers["content-length"]?.toInt() ?: 0
                    val body = ByteArray(length)
                    var read = 0
                    while (read < length) read += input.read(body, read, length - read).also { if (it < 0) return@use }
                    val request = Seen(method, target.substringBefore('?'), target.substringAfter('?', "").ifEmpty { null }, headers, body)
                    synchronized(seen) { seen += request }
                    val (status, type, payload) = route(request)
                    val crlf = "\r\n"
                    val head = StringBuilder("HTTP/1.1 $status X$crlf" + "Connection: close$crlf")
                    if (type.isNotEmpty()) head.append("Content-Type: $type$crlf")
                    if (status in 300..399) head.append("Location: ${String(payload)}$crlf" + "Content-Length: 0$crlf$crlf")
                    else head.append("Content-Length: ${payload.size}$crlf$crlf")
                    val output = conn.getOutputStream()
                    output.write(head.toString().toByteArray(Charsets.UTF_8))
                    if (status !in 300..399) output.write(payload)
                    output.flush()
                }
            }
        }
        return "http://127.0.0.1:${socket.localPort}" to seen
    }

    private fun frames(count: Int) = ByteArray(96 * count) { i -> when (i % 96) { 0 -> 0xFF.toByte(); 1 -> 0xF3.toByte(); 2 -> 0x44; 3 -> 0xC4.toByte(); else -> 0 } }

    private fun out() = File(dir, "clip-${System.nanoTime()}.mp3")

    private fun expectReason(reason: String, block: () -> Unit) {
        try {
            block()
            fail("đáng ra lỗi $reason")
        } catch (error: VoiceException) {
            assertEquals(error.message, reason, error.reason)
            assertFalse("khoá không được nằm trong câu báo", KEY in (error.message ?: ""))
        }
    }

    // ---- cất khoá ---------------------------------------------------------------------------------------------------------

    @Test
    fun keysAreSealedMaskedAndRecheckedAfterAChange() {
        val memory = Memory()
        val store = OnlineKeys(memory, Box)
        store.put("azure", "  $KEY ", "SouthEastAsia")
        assertFalse("khoá thật không nằm trong preferences", memory.map.values.any { KEY in it })
        assertEquals(OnlineKeys.Entry(KEY, "southeastasia", false, emptyList()), store.get("azure"))
        val shown = store.public("azure")
        assertEquals("••••cdef", shown.getString("masked"))
        assertFalse(KEY in shown.toString())
        store.mark("azure", true, listOf(OnlineKeys.VoiceRow("vi-VN-HoaiMyNeural", "Hoài My", "female")))
        assertEquals(1, store.public("azure").getInt("voices"))
        store.put("azure", "", "eastus") // chỉ đổi vùng: giữ khoá, phải kiểm tra lại
        assertEquals(OnlineKeys.Entry(KEY, "eastus", false, emptyList()), store.get("azure"))
        store.remove("azure")
        assertFalse(store.public("azure").getBoolean("hasKey"))
        try {
            store.put("azure", "", "eastus")
            fail("chưa có khoá thì không lưu được vùng")
        } catch (expected: IllegalArgumentException) {
        }
        assertEquals("••••", OnlineKeys.mask("short"))
    }

    // ---- Google -----------------------------------------------------------------------------------------------------------

    private fun google(step: Long = 300): Pair<String, MutableList<Seen>> = server { request ->
        when {
            request.path == "/v1/voices" -> Triple(200, "application/json", """{"voices":[{"languageCodes":["vi-VN"],"name":"vi-VN-Wavenet-A","ssmlGender":"FEMALE"},
                {"languageCodes":["vi-VN"],"name":"vi-VN-Chirp3-HD-Achernar"},{"languageCodes":["vi-VN"],"name":"vi-VN-Standard-B","ssmlGender":"MALE"},
                {"languageCodes":["en-US"],"name":"en-US-Neural2-A"}]}""".toByteArray())
            request.headers["x-goog-api-key"] != KEY -> Triple(400, "application/json",
                """{"error":{"code":400,"message":"API key not valid. Please pass a valid API key.","status":"INVALID_ARGUMENT","details":[{"reason":"API_KEY_INVALID"}]}}""".toByteArray())
            else -> {
                val ssml = JSONObject(String(request.body)).getJSONObject("input").getString("ssml")
                val marks = ssml.split("<mark name=\"").drop(1).map { it.substringBefore('"') }
                val points = JSONArray()
                marks.forEachIndexed { i, name -> points.put(JSONObject().put("markName", name).put("timeSeconds", i * step / 1000.0)) }
                val audio = frames((marks.size * step / 24).toInt())
                Triple(200, "application/json", JSONObject().put("audioContent", WebSocket.base64(audio)).put("timepoints", points).toString().toByteArray())
            }
        }
    }

    @Test
    fun googleSendsMarksAndMapsTimepointsToWords() {
        val (base, seen) = google()
        val provider = GoogleTts(keys("google"), base)
        val text = "Xin chào, các bạn & tôi."
        val clip = provider.voice("vi-VN-Wavenet-A").synthesize(text, out())
        val request = seen.last()
        val payload = JSONObject(String(request.body))
        assertEquals("<speak><mark name=\"0\"/>Xin <mark name=\"1\"/>chào, <mark name=\"2\"/>các <mark name=\"3\"/>bạn <mark name=\"4\"/>&amp; <mark name=\"5\"/>tôi. <mark name=\"end\"/></speak>",
            payload.getJSONObject("input").getString("ssml"))
        assertEquals("vi-VN-Wavenet-A", payload.getJSONObject("voice").getString("name"))
        assertEquals("MP3", payload.getJSONObject("audioConfig").getString("audioEncoding"))
        assertEquals("SSML_MARK", payload.getJSONArray("enableTimePointing").getString(0))
        assertEquals(KEY, request.headers["x-goog-api-key"])
        assertTrue(seen.none { KEY in it.path || KEY in (it.query ?: "") })
        assertEquals(2088L, clip.durationMs)
        assertEquals(listOf(Span(0, 300), Span(300, 600), Span(600, 900)), clip.words.take(3))
        assertEquals(Span(1200, 1500), clip.words[4])
        assertEquals("google:vi-VN-Wavenet-A", clip.voice)
    }

    @Test
    fun googleCheckListsMarkedVietnameseVoicesAndABadKeySaysAuth() {
        val (base, _) = google()
        val store = keys("google", valid = false)
        val provider = GoogleTts(store, base)
        assertTrue("chưa kiểm tra: chưa hiện giọng", provider.voices().isEmpty())
        val result = provider.check(File(dir, "probe.mp3"))
        assertTrue(result.toString(), result.getBoolean("ok"))
        assertEquals(listOf("google:vi-VN-Standard-B", "google:vi-VN-Wavenet-A"), provider.voices().map { it.id })
        assertEquals(listOf("Standard B (Google Cloud)", "WaveNet A (Google Cloud)"), provider.voices().map { it.name })
        assertEquals(listOf("male", "female"), provider.voices().map { it.gender })
        store.put("google", "wrong-key-000000", "")
        val bad = provider.check(File(dir, "probe.mp3"))
        assertFalse(bad.getBoolean("ok"))
        assertEquals("auth", bad.getString("reason"))
        assertTrue(provider.voices().isEmpty())
    }

    @Test
    fun aRedirectIsNotFollowedSoTheKeyStaysWithTheProvider() {
        val (elsewhere, stolen) = server { Triple(200, "text/plain", ByteArray(0)) }
        val (base, _) = server { Triple(302, "", "$elsewhere/steal".toByteArray()) }
        expectReason("rejected") { GoogleTts(keys("google"), base).voice("vi-VN-Wavenet-A").synthesize("Xin chào", out()) }
        assertTrue(stolen.isEmpty())
    }

    @Test
    fun aClosedPortIsOffline() {
        val port = java.net.ServerSocket(0).use { it.localPort }
        expectReason("offline") { OnlineHttp.request("GET", "http://127.0.0.1:$port/", emptyMap(), null, "Giả", 2000) }
    }

    // ---- FPT.AI -----------------------------------------------------------------------------------------------------------

    @Test
    fun fptPostsPlainTextThenPollsTheLink() {
        var polls = 0
        lateinit var base: String
        val (url, seen) = server { request ->
            when (request.path) {
                "/hmi/tts/v5" -> if (request.headers["api_key"] != KEY) Triple(401, "application/json", """{"message":"Invalid authentication credentials"}""".toByteArray())
                else Triple(200, "application/json", """{"async":"$base/file/1.mp3","error":0,"message":"...","request_id":"1"}""".toByteArray())
                else -> if (++polls < 3) Triple(404, "", ByteArray(0)) else Triple(200, "audio/mpeg", frames(50))
            }
        }
        base = url
        val clip = FptTts(keys("fpt"), "$url/hmi/tts/v5", pollMs = 10).voice("banmai").synthesize("Xin chào các bạn.", out())
        val post = seen.first()
        assertEquals("Xin chào các bạn.", String(post.body, Charsets.UTF_8))
        assertEquals("banmai", post.headers["voice"])
        assertEquals("mp3", post.headers["format"])
        assertTrue("link tải file không kèm khoá", seen.drop(1).none { "api_key" in it.headers })
        assertEquals(3, polls)
        assertEquals(1200L, clip.durationMs)
        assertEquals(listOf(Span(0, 300), Span(300, 600), Span(600, 900), Span(900, 1200)), clip.words)
    }

    @Test
    fun fptErrorsBecomeReasons() {
        val answers = ArrayDeque(listOf(
            Triple(401, "application/json", """{"message":"Invalid authentication credentials"}""".toByteArray()),
            Triple(200, "application/json", """{"error":1,"message":"Quota exceeded"}""".toByteArray()),
            Triple(429, "application/json", """{"message":"API rate limit exceeded"}""".toByteArray()),
        ))
        val (url, _) = server { answers.removeFirst() }
        val store = keys("fpt")
        val provider = FptTts(store, "$url/hmi/tts/v5", pollMs = 10)
        expectReason("auth") { provider.voice("banmai").synthesize("Xin chào", out()) }
        assertTrue("khoá bị từ chối: giọng thôi hiện", provider.voices().isEmpty())
        store.mark("fpt", true)
        expectReason("quota") { provider.voice("banmai").synthesize("Xin chào", out()) }
        expectReason("quota") { provider.voice("banmai").synthesize("Xin chào", out()) }
    }

    // ---- Viettel AI -------------------------------------------------------------------------------------------------------

    @Test
    fun viettelPostsJsonAndSpreadsSyllables() {
        val (base, seen) = server { request ->
            when {
                request.path == "/tts/voices" -> Triple(200, "application/json", """[{"name":"Quỳnh Anh chất lượng cao","description":"Nữ miền Bắc","code":"hn-quynhanh"},
                    {"name":"Minh Quân","description":"Nam miền Nam","code":"hcm-minhquan"}]""".toByteArray())
                request.headers["token"] == KEY -> Triple(200, "audio/mpeg", frames(100))
                else -> Triple(401, "application/json", """{"vi_message":"Token không hợp lệ"}""".toByteArray())
            }
        }
        val store = keys("viettel", valid = false)
        val provider = ViettelTts(store, base)
        assertTrue(provider.check(File(dir, "probe.mp3")).getBoolean("ok"))
        assertEquals(listOf("Quỳnh Anh - miền Bắc (Viettel AI)", "Minh Quân - miền Nam (Viettel AI)"), provider.voices().map { it.name })
        assertEquals(listOf("female", "male"), provider.voices().map { it.gender })
        val text = "Ừ, đi thôi. Nhanh lên!"
        val clip = provider.voice("hn-quynhanh").synthesize(text, out())
        val payload = JSONObject(String(seen.last().body))
        assertEquals(text, payload.getString("text"))
        assertEquals("hn-quynhanh", payload.getString("voice"))
        assertEquals(3, payload.getInt("tts_return_option"))
        assertTrue(seen.none { KEY in it.path || KEY in (it.query ?: "") })
        assertEquals(2400L, clip.durationMs)
        assertEquals(listOf(Span(0, 300), Span(600, 900), Span(900, 1200), Span(1800, 2100), Span(2100, 2400)), clip.words)
        store.put("viettel", "wrong-key-000000", "")
        store.mark("viettel", true)
        try {
            provider.voice("hn-quynhanh").synthesize("Xin chào", out())
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertEquals("auth", error.reason)
            assertTrue(error.message!!.contains("Token không hợp lệ"))
        }
    }

    // ---- Azure (WebSocket giả qua Connector, REST giả) -------------------------------------------------------------------

    private fun frame(opcode: Int, payload: ByteArray): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(0x80 or opcode)
        if (payload.size < 126) out.write(payload.size) else { out.write(126); out.write(payload.size ushr 8); out.write(payload.size and 0xFF) }
        out.write(payload)
        return out.toByteArray()
    }

    private fun text(path: String, body: String = "") = frame(WebSocket.OP_TEXT, "Path:$path\r\nX-RequestId:r\r\n\r\n$body".toByteArray())

    private fun azureSession(words: List<String>): ByteArray {
        val parts = mutableListOf(text("turn.start", "{}"), text("something.new", "{}"))
        words.forEachIndexed { i, word ->
            parts += text("audio.metadata", """{"Metadata":[{"Type":"WordBoundary","Data":{"Offset":${i * 4_000_000},"Duration":3000000,"text":{"Text":"$word","Length":${word.length},"BoundaryType":"WordBoundary"}}}]}""")
        }
        val header = "Path:audio\r\nX-RequestId:r\r\nX-StreamId:1".toByteArray()
        parts += frame(WebSocket.OP_BINARY, byteArrayOf((header.size ushr 8).toByte(), header.size.toByte()) + header + ByteArray(12000) { 7 })
        parts += text("turn.end", "{}")
        return parts.fold(ByteArray(0)) { a, b -> a + b }
    }

    @Test
    fun azureSpeaksTheSdkProtocolWithTheKeyInAHeader() {
        val urls = mutableListOf<String>()
        val headers = mutableListOf<Map<String, String>>()
        val sent = ByteArrayOutputStream()
        val connector = EdgeTts.Connector { url, header ->
            urls += url
            headers += header
            WebSocket({ }, ByteArrayInputStream(azureSession(listOf("Xin", "chào", "các", "bạn."))), sent)
        }
        val clip = AzureTts(keys("azure", "southeastasia"), connector).voice("vi-VN-HoaiMyNeural").synthesize("Xin chào các bạn.", out())
        assertEquals(listOf("wss://southeastasia.tts.speech.microsoft.com/tts/cognitiveservices/websocket/v1"), urls)
        assertEquals(KEY, headers[0]["Ocp-Apim-Subscription-Key"])
        assertTrue(headers[0].containsKey("X-ConnectionId"))
        val wire = String(sent.toByteArray(), Charsets.ISO_8859_1)
        assertTrue(wire.isNotEmpty())
        assertEquals(2000L, clip.durationMs)
        // Mốc + 100 ms trễ bộ mã MP3 như Edge (EdgeProtocol.BOUNDARY_SHIFT_MS).
        assertEquals(listOf(Span(100, 400), Span(500, 800)), clip.words.take(2))
    }

    @Test
    fun azureMessagesAskForWordBoundariesAndNameTheVoice() {
        val context = JSONObject(AzureTts.synthesisContext()).getJSONObject("synthesis").getJSONObject("audio")
        assertEquals("true", context.getJSONObject("metadataOptions").getString("wordBoundaryEnabled"))
        assertEquals(AzureTts.OUTPUT_FORMAT, context.getString("outputFormat"))
        val message = AzureTts.message("ssml", "rid", "application/ssml+xml", AzureTts.ssml("vi-VN-HoaiMyNeural", "Xin &amp; chào"))
        assertTrue(message.startsWith("Path:ssml\r\nX-RequestId:rid\r\nX-Timestamp:"))
        assertTrue(message.endsWith("<voice name='vi-VN-HoaiMyNeural'>Xin &amp; chào</voice></speak>"))
    }

    @Test
    fun azureRefusalsAndQuotaClosesCarryAReason() {
        for ((status, reason) in listOf(401 to "auth", 429 to "quota", 500 to "service")) {
            val store = keys("azure", "eastus")
            val connector = EdgeTts.Connector { _, _ -> throw HandshakeException(status, emptyMap()) }
            expectReason(reason) { AzureTts(store, connector).voice("vi-VN-HoaiMyNeural").synthesize("Xin chào", out()) }
            assertEquals(reason != "auth", store.get("azure")!!.valid)
        }
        val close = frame(WebSocket.OP_CLOSE, byteArrayOf(0x03, 0xEF.toByte()) + "Quota exceeded for this subscription".toByteArray())
        val connector = EdgeTts.Connector { _, _ -> WebSocket({ }, ByteArrayInputStream(close), ByteArrayOutputStream()) }
        expectReason("quota") { AzureTts(keys("azure", "eastus"), connector).voice("vi-VN-HoaiMyNeural").synthesize("Xin chào", out()) }
        expectReason("auth") { AzureTts(keys("azure", "not a region!"), connector).voice("vi-VN-HoaiMyNeural").synthesize("Xin chào", out()) }
    }

    @Test
    fun azureVoicesComeFromTheRestListFilteredToVietnamese() {
        val (base, seen) = server { request ->
            if (request.headers["ocp-apim-subscription-key"] != KEY) Triple(401, "", ByteArray(0))
            else Triple(200, "application/json", """[{"ShortName":"vi-VN-HoaiMyNeural","LocalName":"Hoài My","Locale":"vi-VN","Gender":"Female"},
                {"ShortName":"en-US-JennyNeural","LocalName":"Jenny","Locale":"en-US","Gender":"Female"},
                {"ShortName":"vi-VN-NamMinhNeural","LocalName":"Nam Minh","Locale":"vi-VN","Gender":"Male"}]""".toByteArray())
        }
        val store = keys("azure", "eastus", valid = false)
        val connector = EdgeTts.Connector { _, _ -> WebSocket({ }, ByteArrayInputStream(azureSession(listOf("Xin", "chào."))), ByteArrayOutputStream()) }
        val provider = AzureTts(store, connector) { base }
        assertTrue(provider.check(File(dir, "probe.mp3")).getBoolean("ok"))
        assertEquals(AzureTts.VOICES_PATH, seen.single().path)
        assertEquals(listOf(OnlineKeys.VoiceRow("vi-VN-HoaiMyNeural", "Hoài My", "female"), OnlineKeys.VoiceRow("vi-VN-NamMinhNeural", "Nam Minh", "male")),
            store.get("azure")!!.voices)
        assertEquals("azure", provider.describe().getString("id"))
        assertTrue(provider.describe().getJSONObject("limits").getBoolean("region"))
        assertFalse(KEY in provider.describe().toString())
    }
}
