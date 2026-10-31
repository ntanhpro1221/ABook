package vn.abook.player.net

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.StudioPaths
import java.io.File

/**
 * Không lời gọi nào tới máy đã ghép được chờ lặng lẽ mãi (cùng chính sách với máy tính: web `shared/hostWait.ts`, Qt `hostwait.h`). Mọi lời gọi tới máy đã ghép đi qua [HostWait]
 * (hạn "không byte nào về" + gửi lại một lần + trình phát chốt 215 giây); code mới mở kết nối riêng với một máy tính, hay đặt hạn đọc riêng quá chính sách, là lỗi cũ quay lại - bắt ngay ở đây.
 * `net/FastConnectRulesTest` lo phần "mọi kết nối đi qua FastConnect"; ở đây là phần "kết nối tới MÁY ĐÃ GHÉP đi qua HostWait".
 */
class HostWaitRulesTest {
    private val main = File("src/main/java")

    /** Nơi được tự gọi `FastConnect.open/get`: không phải máy đã ghép (Internet, CDN, GitHub, thiết bị phát trong nhà, giọng trực tuyến) - mỗi nơi đã có hạn riêng của nó. */
    private val notPeers = setOf(
        "vn/abook/player/CoverSearch.kt", "vn/abook/player/Dlna.kt", "vn/abook/player/MusicCatalog.kt", "vn/abook/player/PinnedFiles.kt",
        "vn/abook/player/readaloud/OnlineVoices.kt", "vn/abook/player/ui/data/AndroidSettingsCore.kt", "vn/abook/player/net/HostWait.kt",
    )

    private class Rule(val name: String, val pattern: Regex, val why: String)

    private val open = Rule("FastConnect.open/get", Regex("""FastConnect\.(open|get)\("""), "tới máy đã ghép: HostWait.open(url, connectMs, idleMs); không phải máy đã ghép: thêm file vào notPeers kèm lý do")

    /** Trong code nói chuyện với máy đã ghép: không tự đặt hạn đọc (HostWait.open đặt rồi), không bao giờ "không hạn". */
    private val ownLimit = Rule("readTimeout", Regex("""(\.readTimeout\s*=|setReadTimeout\()"""), "HostWait.open đặt hạn đọc theo chính sách")
    private val unlimited = Rule("readTimeout 0", Regex("""[rR]eadTimeout(Ms)?\s*(=|\()\s*0\b"""), "không có hạn = chờ mãi")
    private val tooLong = Regex("""readTimeoutMs\s*=\s*([0-9_]+)\b""")
    private val mediaRead = Regex("""setReadTimeoutMs\(\s*(?!HostWait\.)""")

    private fun code(lines: List<String>): List<Pair<Int, String>> = lines.mapIndexedNotNull { index, raw ->
        val trimmed = raw.trimStart()
        if (trimmed.startsWith("//") || trimmed.startsWith("*") || trimmed.startsWith("/*") || trimmed.startsWith("import ")) null else (index + 1) to raw
    }

    /** Vi phạm của một file (đường tương đối `path`, các dòng của nó): "dòng N: luật". */
    private fun offences(path: String, lines: List<String>): List<String> {
        val out = mutableListOf<String>()
        val peerTalk = path !in notPeers && !path.startsWith("vn/abook/player/readaloud/") && !path.startsWith("vn/abook/player/net/")
        for ((number, raw) in code(lines)) {
            if (path !in notPeers && !path.endsWith("/net/FastConnect.kt") && !path.endsWith("/net/Tunnel.kt") && open.pattern.containsMatchIn(raw)) {
                out += "dòng $number: ${open.name} (${open.why}): ${raw.trim()}"
            }
            if (peerTalk && ownLimit.pattern.containsMatchIn(raw)) out += "dòng $number: ${ownLimit.name} (${ownLimit.why}): ${raw.trim()}"
            if (!path.startsWith("vn/abook/player/readaloud/") && unlimited.pattern.containsMatchIn(raw)) out += "dòng $number: ${unlimited.name} (${unlimited.why}): ${raw.trim()}"
            if (peerTalk) tooLong.findAll(raw).forEach { match ->
                val ms = match.groupValues[1].replace("_", "").toLongOrNull() ?: 0L
                if (ms > HostWait.IDLE_MS) out += "dòng $number: readTimeoutMs $ms ms vượt hạn ${HostWait.IDLE_MS} ms của chính sách (bỏ đi để theo đường, hay chia việc): ${raw.trim()}"
            }
            if (mediaRead.containsMatchIn(raw)) out += "dòng $number: setReadTimeoutMs không phải HostWait.IDLE_MS (trình phát nghe thẳng theo cùng chính sách): ${raw.trim()}"
        }
        return out
    }

    private fun mainFiles() = main.walkTopDown().filter { it.isFile && it.extension in setOf("kt", "java") }
        .filter { "/ai/onnxruntime/" !in it.invariantSeparatorsPath }.toList()

    @Test
    fun everyCallToAPairedMachineGoesThroughTheSharedWaitPolicy() {
        assertTrue("không thấy ${main.absolutePath}", main.isDirectory)
        val files = mainFiles()
        assertTrue("quét được quá ít file: ${files.size}", files.size >= 100)
        val offenders = files.flatMap { file ->
            val relative = file.relativeTo(main).invariantSeparatorsPath
            offences(relative, file.readLines()).map { "$relative $it" }
        }
        assertTrue("Lời gọi tới máy đã ghép không qua chính sách chờ chung (net/HostWait.kt): $offenders", offenders.isEmpty())
    }

    @Test
    fun theDoorsAreStillUsed() {
        fun text(path: String) = File(main, path).readText()
        assertTrue("SyncLink phải mở kết nối bằng HostWait.open", text("vn/abook/player/SyncLink.kt").contains("HostWait.open("))
        assertTrue("SyncLink phải gửi lại một lần qua HostWait.call", text("vn/abook/player/SyncLink.kt").contains("HostWait.call("))
        assertTrue("SyncLink phải canh phần GHI của tệp gửi lên", text("vn/abook/player/SyncLink.kt").contains("HostWait.writing("))
        assertTrue("openGet phải canh lượt trả lời đầu", text("vn/abook/player/PeerTransfer.kt").contains("HostWait.awaiting("))
        assertTrue("Streaming.fetchSmall phải mở bằng HostWait.open", text("vn/abook/player/Streaming.kt").contains("HostWait.open("))
        assertTrue("trình phát phải có chốt chặn đệm", text("vn/abook/player/Playback.kt").contains("bufferingGuard.observe("))
    }

    @Test
    fun thePolicyNumbersAreTheDesktopOnes() {
        assertEquals(30_000, HostWait.IDLE_MS)
        assertEquals(100_000, HostWait.LONG_IDLE_MS)
        assertEquals(2, HostWait.ATTEMPTS)
        assertEquals(215_000L, HostWait.STALL_MS)
    }

    @Test
    fun theLongWorkListMatchesTheSameRoutesAsTheWebCopy() {
        // Giống từng ca của web shared/hostWait.test.ts.
        for (long in listOf(
            "/api/readaloud/clip", "/api/readaloud/clip?x=1", "/api/books/abc/voice/preview", "/api/books/abc/pronunciation/preview",
            "/api/books/abc/music/rebuild", "/api/books/abc/music", "/api/books/abc/edits/fold", "/sync/v1/books/abc/edits",
            "/api/scan", "/api/sources/split", "/api/first-person", "/api/books",
        )) {
            assertTrue(long, HostWait.isLongWork(long))
            assertEquals(long, 100_000, HostWait.idleMs(long))
        }
        for (other in listOf(
            "/api/readaloud/voices", "/api/readaloud/prepare", "/api/books/abc/voice", "/api/books/abc/script", "/api/books/abc",
            "/api/books/a/b/voice/preview", "/api/scanx", "/api/cast/scan", "/api/listen/library", "/api/books/abc/music/track",
            "/sync/v1/books/abc/manifest",
        )) {
            assertFalse(other, HostWait.isLongWork(other))
            assertEquals(other, 30_000, HostWait.idleMs(other))
        }
    }

    @Test
    fun theRealStudioPathsOfLongJobsAreInTheList() {
        // Đúng đường StudioSource/StudioPreview/StudioMusic gửi đi (ghép bằng StudioPaths), không phải chuỗi chép tay.
        val id = "book_1-x"
        val long = listOf(
            StudioPaths.write(id, "voice/preview"), StudioPaths.write(id, "pronunciation/preview"), StudioPaths.write(id, "music/rebuild"), StudioPaths.put(id, "music"),
            StudioPaths.SOURCE_SPLIT, StudioPaths.SCAN, StudioPaths.FIRST_PERSON, StudioPaths.CREATE_BOOK,
        )
        for (path in long) assertTrue(path, HostWait.isLongWork(path))
        // Ghi thường của cùng sách vẫn là hạn ngắn.
        for (path in listOf(StudioPaths.write(id, "voice"), StudioPaths.write(id, "pronunciation"), StudioPaths.book(id), StudioPaths.LIBRARY, StudioPaths.SOURCE_UPLOAD)) {
            assertFalse(path, HostWait.isLongWork(path))
        }
    }

    @Test
    fun theRuleCatchesAHandRolledWaitAndLetsThePolicyThrough() {
        fun count(path: String, vararg lines: String) = offences(path, lines.toList()).size
        val peer = "vn/abook/player/Foo.kt"
        assertEquals(1, count(peer, "val c = FastConnect.open(url, 3000)"))
        assertEquals(1, count(peer, "val c = FastConnect.get(url, 3000) { }"))
        assertEquals(0, count(peer, "val c = HostWait.open(url, 3000)"))
        assertEquals(0, count("vn/abook/player/CoverSearch.kt", "val c = FastConnect.open(url, 3000)"))
        assertEquals(1, count(peer, "connection.readTimeout = 15_000"))
        assertEquals(1, count(peer, "builder.setReadTimeout(5000)"))
        assertEquals(0, count("vn/abook/player/CoverSearch.kt", "connection.readTimeout = 15_000"))
        assertEquals(1, count(peer, "SyncLink.request(context, \"POST\", \"/x\", readTimeoutMs = 130_000)"))
        assertEquals(0, count(peer, "SyncLink.request(context, \"GET\", \"/x\", readTimeoutMs = 2500, connectTimeoutMs = 1500)"))
        assertEquals(0, count(peer, "SyncLink.request(context, \"GET\", \"/x\", readTimeoutMs = 30_000)"))
        assertEquals(2, count(peer, "connection.readTimeout = 0")) // vừa tự đặt hạn, vừa không hạn
        assertEquals(1, count("vn/abook/player/CoverSearch.kt", "connection.readTimeout = 0"))
        assertEquals(1, count(peer, "DefaultHttpDataSource.Factory().setReadTimeoutMs(20_000)"))
        assertEquals(0, count(peer, "DefaultHttpDataSource.Factory().setReadTimeoutMs(HostWait.IDLE_MS)"))
        assertEquals(0, count(peer, "// connection.readTimeout = 15_000", " * FastConnect.open(url, 3000)"))
    }
}
