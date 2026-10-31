package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.testTag
import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.BasicText
import vn.abook.player.ui.components.hasSeparator
import vn.abook.player.ui.components.keepNumbersTogether
import vn.abook.player.ui.components.separatorsAtLineEnd
import vn.abook.player.ui.components.shapeForWrap
import vn.abook.player.ui.components.tieSeparators
import vn.abook.player.ui.data.dotJoin
import vn.abook.player.ui.data.dotJoined
import java.io.File

/**
 * Hai luật xuống dòng của soát 31-10, mỗi luật một máy dò chạy trên MỌI chữ chứ không chỉ chỗ được chỉ:
 *  1. dấu ngăn (" · ", " - ", " – ", " | ", " / ") không mở dòng và không đóng dòng ("Tác giả 1 ·" treo cuối, "· 0 chương" mở đầu);
 *  2. chữ + số ngắn đi liền ("số" / "1" không rơi hai dòng).
 * Và hai điều làm cho luật đúng trọn app: không file nào dùng BasicText của foundation (chỉ trình bao [BasicText]), không file nào tự nối bằng " · " ngoài `dotJoin`.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class TextWrapRulesTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val main = File("src/main/java/vn/abook/player")

    private fun sources(): List<File> = main.walkTopDown().filter { it.isFile && it.extension == "kt" }.toList()

    // ---- hàm thuần ----

    @Test
    fun separatorsAreTiedToTheWordBeforeThem() {
        assertEquals("Tác giả · 3 chương", tieSeparators("Tác giả · 3 chương"))
        assertEquals("a - b – c | d / e", tieSeparators("a - b – c | d / e"))
        // Gạch nối trong từ, đường dẫn, ngày: không phải dấu ngăn đứng riêng.
        assertEquals("Spider-Man 12/05 a/b", tieSeparators("Spider-Man 12/05 a/b"))
        assertEquals("không có", tieSeparators("không có"))
    }

    @Test
    fun onlyStandaloneSeparatorsAreDetected() {
        assertTrue(hasSeparator("A · B"))
        assertTrue(hasSeparator("A · B"))
        assertFalse(hasSeparator("Spider-Man"))
        assertFalse(hasSeparator("12/05"))
        assertFalse(hasSeparator("không có dấu"))
    }

    @Test
    fun separatorAtTheEndOfALineIsReportedButNotTheLastLine() {
        val text = "Tác giả · 3 chương"
        // Dòng 1 kết thúc ngay sau "· " (offset 10), dòng 2 là phần còn lại.
        assertEquals(listOf(8), separatorsAtLineEnd(text, listOf(10, text.length)))
        // Dấu ở cuối dòng CUỐI thì không ẩn (không còn gì phía sau để dồn).
        assertEquals(emptyList<Int>(), separatorsAtLineEnd("A ·", listOf(3)))
        // Dòng kết thúc bằng chữ: không có gì để ẩn.
        assertEquals(emptyList<Int>(), separatorsAtLineEnd(text, listOf(8, text.length)))
    }

    @Test
    fun shortNumbersStayWithTheirWord() {
        assertEquals("số 1", keepNumbersTogether("số 1"))
        assertEquals("Tập 2 · Chương 12", keepNumbersTogether("Tập 2 · Chương 12"))
        // Giờ, số thập phân, số lớn: để nguyên.
        assertEquals("lúc 1:40", keepNumbersTogether("lúc 1:40"))
        assertEquals("rộng 2,0 lần", keepNumbersTogether("rộng 2,0 lần"))
        assertEquals("năm 2026", keepNumbersTogether("năm 2026"))
        assertEquals("a 1 · b 2", shapeForWrap("a 1 · b 2"))
    }

    @Test
    fun aNumberBeforeAUnitStaysWithItsUnitNotWithTheWordBefore() {
        // "chiếm 12 MB": ngắt trước "12 MB" tốt hơn ngắt giữa "12" và "MB" (soát lại 31-10: "chiếm 12 / MB").
        assertEquals("chiếm 12 MB trên máy", shapeForWrap("chiếm 12 MB trên máy"))
        assertEquals("lùi/tới 15 giây", shapeForWrap("lùi/tới 15 giây"))
        assertEquals("Nghe 2 giờ", shapeForWrap("Nghe 2 giờ"))
        // Số không có đơn vị vẫn đi với chữ đứng trước.
        assertEquals("Tập 2 hay", shapeForWrap("Tập 2 hay"))
    }

    @Test
    fun dotJoinDropsEmptyPartsSoNoDanglingDot() {
        assertEquals("4 MB · hôm qua", dotJoin("4 MB", "hôm qua"))
        assertEquals("4 MB", dotJoin("4 MB", "", null, "  "))
        assertEquals("", dotJoin(null, ""))
        assertEquals("a · b", listOf<String?>("a", null, "b").dotJoined())
        assertEquals("câu 3", dotJoin("", "câu 3"))
    }

    // ---- quét mã nguồn ----

    @Test
    fun noFileUsesTheFoundationBasicText() {
        val offenders = sources().filter { it.name != "WrapText.kt" }.mapNotNull { file ->
            val bad = file.readLines().filter { Regex("""^\s*import\s+androidx\.compose\.foundation\.text\.BasicText(\s+as\s+\w+)?\s*$""").matches(it) }
            if (bad.isEmpty()) null else "${file.name}: $bad"
        }
        assertTrue("BasicText của foundation lách qua luật xuống dòng; import vn.abook.player.ui.components.BasicText:\n" + offenders.joinToString("\n"), offenders.isEmpty())
        // Tên đầy đủ trong thân hàm cũng không.
        val inline = sources().filter { it.name != "WrapText.kt" }.filter { file ->
            file.readLines().any { !it.trimStart().startsWith("//") && !it.trimStart().startsWith("*") && Regex("""androidx\.compose\.foundation\.text\.BasicText\(""").containsMatchIn(it) }
        }
        assertTrue("gọi thẳng foundation BasicText: " + inline.map { it.name }, inline.isEmpty())
    }

    @Test
    fun noFileJoinsWithTheDotByHand() {
        val offenders = ArrayList<String>()
        for (file in sources()) {
            if (file.name == "Format.kt") continue
            file.readLines().forEachIndexed { i, line ->
                val code = line.substringBefore("//")
                if (code.contains("joinToString(\" · \"") || code.contains("\" · \" +") || code.contains("+ \" · \"")) offenders += "${file.name}:${i + 1}: ${line.trim()}"
            }
        }
        assertTrue("nối ' · ' bằng tay có thể để lại dấu treo khi một mẩu rỗng; dùng dotJoin / dotJoined:\n" + offenders.joinToString("\n"), offenders.isEmpty())
    }

    // ---- bố cục thật ----

    private var text by mutableStateOf("")
    private var widthDp by mutableStateOf(200)
    private var useColor by mutableStateOf(false)
    private var last: TextLayoutResult? = null
    private var mounted = false

    /** Dựng chữ trong khung `widthDp`; một setContent cho cả test, các lần sau đổi trạng thái. Trả về bố cục cuối. */
    private fun lay(text: String, widthDp: Int, color: Boolean): TextLayoutResult {
        this.text = text
        this.widthDp = widthDp
        this.useColor = color
        last = null
        if (!mounted) {
            mounted = true
            rule.setContent {
                Box(Modifier.fillMaxSize().background(Color.White)) {
                    Box(Modifier.width(this@TextWrapRulesTest.widthDp.dp).testTag("t")) {
                        val style = TextStyle(color = Color.Black, fontSize = 20.sp)
                        val shown = this@TextWrapRulesTest.text
                        if (this@TextWrapRulesTest.useColor) BasicText(shown, style = style, onTextLayout = { last = it }, color = { Color.Black })
                        else BasicText(shown, style = style, onTextLayout = { last = it })
                    }
                }
            }
        }
        rule.waitForIdle()
        return last!!
    }

    private fun assertNoSeparatorAtEdges(widthDp: Int, color: Boolean) {
        val layout = lay("Tác giả Ngô Tất Tố · 3 chương · 2 giờ nghe · xong", widthDp, color)
        val shown = layout.layoutInput.text.text
        for (line in 0 until layout.lineCount) {
            val body = shown.substring(layout.getLineStart(line), layout.getLineEnd(line)).trim { it == ' ' || it == ' ' }
            assertFalse("dòng $line mở bằng dấu ngăn ($widthDp dp): '$body'", body.startsWith("· ") || body == "·")
        }
    }

    @Test fun separatorNeverOpensALineWhateverTheWidth() {
        for (width in listOf(120, 150, 180, 210, 240, 280)) assertNoSeparatorAtEdges(width, false)
    }

    @Test fun separatorNeverOpensALineWithColorProducer() {
        for (width in listOf(120, 150, 180, 210, 240, 280)) assertNoSeparatorAtEdges(width, true)
    }

    @Test fun separatorAtTheEndOfALineIsDrawnTransparentWithStyleColor() = assertTransparentAtLineEnd(false)

    @Test fun separatorAtTheEndOfALineIsDrawnTransparentWithColorProducer() = assertTransparentAtLineEnd(true)

    /** Tìm bề rộng làm dấu rơi cuối dòng 1, rồi đọc ảnh vùng dấu: phải là nền trắng (chữ thì vẫn có mực ở chỗ khác). */
    private fun assertTransparentAtLineEnd(color: Boolean) {
        var found = false
        for (width in 100..300 step 6) {
            val layout = lay("Tác giả · hai", width, color)
            val hidden = separatorsAtLineEnd(layout.layoutInput.text.text, (0 until layout.lineCount).map { layout.getLineEnd(it) })
            if (hidden.isEmpty()) continue
            found = true
            val decor = rule.activity.window.decorView
            val bitmap = Bitmap.createBitmap(decor.width, decor.height, Bitmap.Config.ARGB_8888)
            decor.draw(Canvas(bitmap))
            val origin = rule.onNodeWithTag("t").fetchSemanticsNode().positionInRoot
            val box = layout.getBoundingBox(hidden.first())
            val white = Color.White.toArgb()
            var ink = 0
            for (y in (origin.y + box.top).toInt().coerceAtLeast(0) until (origin.y + box.bottom).toInt().coerceAtMost(bitmap.height)) {
                for (x in (origin.x + box.left).toInt().coerceAtLeast(0) until (origin.x + box.right).toInt().coerceAtMost(bitmap.width)) {
                    if (bitmap.getPixel(x, y) != white) ink++
                }
            }
            assertEquals("dấu cuối dòng ($width dp, colorProducer=$color) vẫn hiện mực", 0, ink)
            var total = 0
            for (y in 0 until bitmap.height step 2) for (x in 0 until bitmap.width step 2) if (bitmap.getPixel(x, y) != white) total++
            assertTrue("chữ khác vẫn phải có mực (colorProducer=$color)", total > 0)
            break
        }
        assertTrue("không tìm được bề rộng nào để dấu rơi cuối dòng (colorProducer=$color)", found)
    }
}
