package vn.abook.player.net

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Mọi kết nối TCP/HTTP đi ra phải qua [FastConnect] (đua địa chỉ IPv6/IPv4, RFC 8305): mạng nhà có IPv6 mà không có đường IPv6 thì cách nối
 * từng địa chỉ một của HttpURLConnection / Socket chờ trọn hạn ở MỖI địa chỉ IPv6 rồi mới tới IPv4 (31-10). Code mới gọi thẳng các hàm dưới đây là lỗi cũ
 * quay lại, nên máy dò này bắt ngay trong test thường. Chỉ thành phần `net/FastConnect.kt` + `net/Tunnel.kt` được phép; `ai/onnxruntime` là mã chép nguyên.
 */
class FastConnectRulesTest {
    private val main = File("src/main/java")

    private class Rule(val name: String, val pattern: Regex, val why: String)

    private val rules = listOf(
        Rule("openConnection", Regex("""\.openConnection\("""), "dùng FastConnect.open / FastConnect.get"),
        Rule("Socket(", Regex("""(?<![A-Za-z])Socket\("""), "dùng FastConnect.connect(host, port, timeoutMs)"),
        Rule("connect(InetSocketAddress", Regex("""\.connect\(\s*InetSocketAddress"""), "dùng FastConnect.connect(host, port, timeoutMs)"),
        Rule("createSocket(host, port)", Regex("""createSocket\(\s*[\w"$.]+\s*,\s*[\w"$.]+\s*\)"""), "nối bằng FastConnect.connect rồi createSocket(socket, host, port, true)"),
        Rule("URL(..).openStream/readText", Regex("""URL\([^)]*\)\.(openStream|readText|readBytes)\("""), "dùng FastConnect.open"),
        Rule("DefaultHttpDataSource", Regex("""DefaultHttpDataSource"""), "chỉ Streaming.kt, nơi nó nhận địa chỉ đã qua FastConnect.literalUrl"),
    )

    /** Vi phạm của một file (đã đọc thành dòng): "dòng N: luật". Dòng chú thích và import bị bỏ. */
    private fun offences(path: String, lines: List<String>): List<String> {
        val out = mutableListOf<String>()
        lines.forEachIndexed { index, raw ->
            val trimmed = raw.trimStart()
            if (trimmed.startsWith("//") || trimmed.startsWith("*") || trimmed.startsWith("/*") || trimmed.startsWith("import ")) return@forEachIndexed
            for (rule in rules) {
                if (!rule.pattern.containsMatchIn(raw)) continue
                if (rule.name == "DefaultHttpDataSource" && path.endsWith("/Streaming.kt")) continue
                out += "dòng ${index + 1}: ${rule.name} (${rule.why}): ${raw.trim()}"
            }
        }
        return out
    }

    @Test
    fun noCodeOutsideFastConnectOpensConnectionsByItself() {
        assertTrue("không thấy ${main.absolutePath}", main.isDirectory)
        val files = main.walkTopDown().filter { it.isFile && it.extension in setOf("kt", "java") }.filter { file ->
            val path = file.invariantSeparatorsPath
            "/ai/onnxruntime/" !in path && !path.endsWith("/net/FastConnect.kt") && !path.endsWith("/net/Tunnel.kt")
        }.toList()
        assertTrue("quét được quá ít file: ${files.size}", files.size >= 100)
        val offenders = files.flatMap { file -> offences(file.invariantSeparatorsPath, file.readLines()).map { "${file.relativeTo(main).invariantSeparatorsPath} $it" } }
        assertTrue("Kết nối ra ngoài không qua FastConnect (mạng IPv6 mù sẽ chờ N lần hạn): $offenders", offenders.isEmpty())
    }

    @Test
    fun theMediaPlayerOnlyGetsAddressesThatWentThroughFastConnect() {
        val streaming = File(main, "vn/abook/player/Streaming.kt").readText()
        assertTrue(streaming.contains("DefaultHttpDataSource"))
        assertTrue("Streaming.kt phải đổi tên máy thành địa chỉ thắng cuộc trước khi mở", streaming.contains("FastConnect.literalUrl("))
    }

    @Test
    fun theRuleCatchesDirectConnectionsAndLetsFastConnectThrough() {
        fun count(vararg code: String) = offences("A.kt", code.toList()).size
        assertEquals(1, count("val c = URL(u).openConnection() as HttpURLConnection"))
        assertEquals(1, count("val s = Socket()"))
        assertEquals(1, count("val s = Socket(\"127.0.0.1\", 80)"))
        assertEquals(1, count("raw.connect(InetSocketAddress(host, port), 3000)"))
        assertEquals(1, count("val s = factory.createSocket(host, port)"))
        assertEquals(1, count("URL(x).openStream()"))
        assertEquals(1, count("val h = DefaultHttpDataSource.Factory()"))
        assertEquals(0, count("val c = FastConnect.open(u, 3000)"))
        assertEquals(0, count("val s = factory.createSocket(raw, host, port, true)"))
        assertEquals(0, count("val d = DatagramSocket()", "val m = MulticastSocket(x)", "val b = ServerSocket(0)", "socket.connect()"))
        assertEquals(0, count("// URL(u).openConnection()", " * Socket()", "import java.net.Socket"))
        assertEquals(0, offences("x/Streaming.kt", listOf("val h = DefaultHttpDataSource.Factory()")).size)
    }
}
