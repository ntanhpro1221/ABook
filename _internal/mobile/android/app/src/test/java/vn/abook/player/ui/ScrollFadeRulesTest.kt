package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Luật mép cuộn (DESIGN.md §4.5, soát 26-10: dòng nhật ký đầu bị cắt ngang dưới câu "Có tên sách; khoá..."): mọi vùng cuộn dọc của giao diện native nằm dưới
 * một phần tử cố định - tiêu đề và tay nắm bảng trượt, thanh nút đáy, nút ←, thanh phát + thanh tab, thanh trạng thái - nên vùng nào cũng phải mờ mép bằng
 * `Modifier.fadeEdges` (ui/components/ScrollFade.kt), không có ngoại lệ:
 * - `LazyColumn` / `LazyVerticalGrid`: đối số có `.fadeEdges(s)` và `state = s` CÙNG một trạng thái;
 * - `verticalScroll(s)`: ngay trước nó trong chuỗi là `.fadeEdges(s)` (mặt nạ theo khung nhìn; đặt sau thì mặt nạ trôi theo nội dung).
 * Cùng luật với bản web (ui/src/shared/scrollFadeRules.test.ts).
 */
class ScrollFadeRulesTest {
    private val root = File("src/main/java/vn/abook/player/ui")

    private fun sources() = root.walkTopDown().filter { it.isFile && it.extension == "kt" }
        .map { it.relativeTo(root).invariantSeparatorsPath to it.readText() }

    private val lazyCall = Regex("""\b(LazyColumn|LazyVerticalGrid)\s*([({])""")
    private val faded = Regex("""\.fadeEdges\(\s*(\w+)\s*[,)]""")
    private val scrollCall = Regex("""\.verticalScroll\(\s*([^)]*)\)""")
    private val fadedScroll = Regex("""\.fadeEdges\(\s*(\w+)\s*(,[^)]*)?\)\s*$""")

    /** Bỏ chú thích (dòng mở đầu bằng sao, gạch chéo + sao, hai gạch chéo; cả phần hai gạch chéo cuối dòng) để chữ "LazyColumn" trong lời giải thích không bị tính. */
    private fun code(text: String): String = text.lines().joinToString("\n") { line ->
        val trimmed = line.trimStart()
        if (trimmed.startsWith("*") || trimmed.startsWith("/*") || trimmed.startsWith("//")) "" else line.replace(Regex("""\s//\s.*$"""), "")
    }

    /** Đối số trong cặp ngoặc mở ở [open] (chỉ số của '('). */
    private fun arguments(text: String, open: Int): String {
        var depth = 0
        for (index in open until text.length) {
            when (text[index]) {
                '(' -> depth++
                ')' -> if (--depth == 0) return text.substring(open + 1, index)
            }
        }
        return text.substring(open + 1)
    }

    /** Vùng cuộn thiếu mép mờ trong một file, dạng "dòng N: ...". */
    private fun offences(source: String): List<String> {
        val text = code(source)
        fun line(at: Int) = text.substring(0, at).count { it == '\n' } + 1
        val lazy = lazyCall.findAll(text).mapNotNull { match ->
            val args = if (match.groupValues[2] == "(") arguments(text, match.groups[2]!!.range.first) else ""
            val state = faded.find(args)?.groupValues?.get(1)
            val ok = state != null && Regex("""\bstate\s*=\s*$state\b""").containsMatchIn(args)
            if (ok) null else "dòng ${line(match.range.first)}: ${match.groupValues[1]} không có .fadeEdges(s) với state = s"
        }
        val scroll = scrollCall.findAll(text).mapNotNull { match ->
            val state = match.groupValues[1].trim()
            val before = fadedScroll.find(text.substring(maxOf(0, match.range.first - 200), match.range.first))
            if (before != null && before.groupValues[1] == state) null else "dòng ${line(match.range.first)}: verticalScroll không có .fadeEdges(cùng trạng thái) ngay trước"
        }
        return (lazy + scroll).toList()
    }

    @Test
    fun everyVerticalScrollFadesItsEdges() {
        val offenders = sources().flatMap { (path, text) -> offences(text).map { "$path $it" } }.toList()
        assertTrue("Vùng cuộn bị cắt cứng ở mép (dùng Modifier.fadeEdges của ui/components/ScrollFade.kt): $offenders", offenders.isEmpty())
    }

    @Test
    fun theSharedFadeIsUsedEverywhere() {
        // Một thành phần chung: không ai tự vẽ lại mặt nạ mép bằng BlendMode.DstIn ngoài ScrollFade.kt.
        val copies = sources().filter { (path, text) -> path != "components/ScrollFade.kt" && "BlendMode.DstIn" in code(text) }.map { it.first }.toList()
        assertTrue("Mép mờ tự vẽ (dùng Modifier.fadeEdges): $copies", copies.isEmpty())
    }

    @Test
    fun theRuleCatchesBareScrollsAndLetsFadedOnesThrough() {
        assertEquals(1, offences("LazyColumn(Modifier.fillMaxWidth()) { items(rows) { Row(it) } }").size)
        assertEquals(1, offences("else LazyColumn {\n items(rows) { Row(it) }\n}").size)
        assertEquals(1, offences("LazyColumn(Modifier.fadeEdges(list)) { }").size)
        assertEquals(1, offences("LazyColumn(Modifier.fadeEdges(list), state = other) { }").size)
        assertEquals(1, offences("LazyVerticalGrid(columns = GridCells.Fixed(2), state = grid, modifier = Modifier.fillMaxSize()) { }").size)
        assertEquals(1, offences("Column(Modifier.verticalScroll(rememberScrollState())) { }").size)
        assertEquals(1, offences("Column(Modifier.verticalScroll(scroll).fadeEdges(scroll)) { }").size)
        assertEquals(1, offences("Column(Modifier.fadeEdges(other).verticalScroll(scroll)) { }").size)
        assertEquals(0, offences(listOf(
            "LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag(\"x\"), state = list, contentPadding = PaddingValues(Dim.s16)) { }",
            "LazyColumn(\n    state = list,\n    modifier = Modifier.fillMaxSize().fadeEdges(list).testTag(\"book_list\"),\n) { }",
            "LazyVerticalGrid(columns = GridCells.Fixed(2), state = grid, modifier = Modifier.fillMaxSize().testTag(\"g\").fadeEdges(grid)) { }",
            "Column(modifier.fillMaxSize().testTag(tag).fadeEdges(scroll).verticalScroll(scroll).padding(top = top)) { }",
            "/** Dùng riêng trong LazyColumn (mỗi hàng là một mục). */",
            "// verticalScroll(rememberScrollState()) cũ",
        ).joinToString("\n")).size)
    }
}
