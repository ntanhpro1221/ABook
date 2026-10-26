package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.sp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.ActionRow
import vn.abook.player.ui.components.ChoiceSetting
import vn.abook.player.ui.components.DisclosureRow
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.ListRow
import vn.abook.player.ui.components.MenuRow
import vn.abook.player.ui.components.Option
import vn.abook.player.ui.components.PencilIcon
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.TypeScale
import java.io.File

/**
 * Luật: dòng mô tả dưới tên một hàng là MỘT kiểu chữ cho mọi hàng - do thành phần hàng quyết định, không hàng nào tự chọn.
 * Hai máy dò: (1) mọi loại hàng dùng chung (ListRow, SwitchRow, ChoiceSetting, ActionRow, DisclosureRow, ListItem, MenuRow) vẽ dòng mô tả cùng cỡ / độ đậm / giãn dòng;
 * (2) quét nguồn: không còn tham số `hintStyle`; không hàng nào tự dựng dòng mô tả bằng BasicText(hint / summary); và không có dòng phụ (BasicText cỡ bodySmall / caption)
 * nằm ngay dưới một tên (BasicText cỡ body / bodyStrong / sectionTitle ...) ngoài ListParts.kt - chỗ nào có dòng phụ dưới tên thì gọi RowHint.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class RowHintStyleTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private fun styleOf(text: String): TextStyle {
        val layouts = mutableListOf<TextLayoutResult>()
        rule.onNode(hasText(text), useUnmergedTree = true).fetchSemanticsNode().config[SemanticsActions.GetTextLayoutResult].action!!(layouts)
        return layouts.single().layoutInput.style
    }

    @Test
    fun everyKindOfRowDrawsItsHintInTheSameStyle() {
        val options = listOf(Option(1, "Một"), Option(2, "Hai"))
        rule.setContent {
            AbookTheme(false) {
                Column(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    ListRow("Hàng một", hint = "mô tả ListRow")
                    SwitchRow("Hàng hai", true, {}, "sw", hint = "mô tả SwitchRow")
                    ChoiceSetting("Hàng ba", options, options.first(), { _, _ -> }, "cs", hint = "mô tả ChoiceSetting")
                    ActionRow("Hàng bốn", "Làm", {}, "ar", hint = "mô tả ActionRow")
                    DisclosureRow("Hàng năm", {}, "dr", summary = "mô tả DisclosureRow")
                    ListItem("Hàng sáu", hint = "mô tả ListItem")
                    MenuRow("Hàng bảy", tag = "mr", hint = "mô tả MenuRow") { ink -> PencilIcon(ink) }
                }
            }
        }
        rule.waitForIdle()
        val kinds = listOf("ListRow", "SwitchRow", "ChoiceSetting", "ActionRow", "DisclosureRow", "ListItem", "MenuRow")
        val styles = kinds.associateWith { styleOf("mô tả $it") }
        val first = styles.values.first()
        assertEquals("dòng mô tả là bodySmall của DESIGN.md (14)", TypeScale.BODY_SMALL.sp, first.fontSize)
        for ((kind, style) in styles) {
            assertEquals("cỡ chữ dòng mô tả của $kind", first.fontSize, style.fontSize)
            assertEquals("độ đậm dòng mô tả của $kind", first.fontWeight, style.fontWeight)
            assertEquals("giãn dòng của $kind", first.lineHeight, style.lineHeight)
        }
    }

    private val titleLine = Regex("""BasicText\(.*style\s*=\s*Abook\.type\.(body|bodyStrong|sectionTitle|screenTitle|label)\b""")
    private val subLine = Regex("""BasicText\(.*style\s*=\s*Abook\.type\.(bodySmall|caption)\b""")

    /** Các dòng phụ tự dựng: BasicText bodySmall / caption mà dòng mã liền trước (bỏ dòng khai báo val) là BasicText của một tên. */
    fun ownSubLines(file: String, source: String): List<String> {
        val lines = source.lines().map { it.substringBefore("//") }
        return lines.mapIndexedNotNull { index, line ->
            if (!subLine.containsMatchIn(line)) return@mapIndexedNotNull null
            val before = (index - 1 downTo 0).map { lines[it] }.firstOrNull { it.isNotBlank() && !it.trimStart().startsWith("val ") }
            if (before != null && titleLine.containsMatchIn(before)) "$file:${index + 1} dòng phụ tự dựng dưới một tên - dùng RowHint" else null
        }
    }

    @Test
    fun theScanCatchesAnOwnSubLine() {
        val title = "BasicText(title, style = Abook.type.body)"
        assertEquals(1, ownSubLines("t.kt", "$title\nBasicText(sub, style = Abook.type.caption)").size)
        assertEquals(1, ownSubLines("t.kt", "$title\nval x = 1\nBasicText(sub, style = Abook.type.bodySmall.copy(color = c))").size)
        assertEquals(0, ownSubLines("t.kt", "$title\nRowHint(sub)").size)
        assertEquals(0, ownSubLines("t.kt", "BasicText(a, style = Abook.type.bodySmall)\nBasicText(b, style = Abook.type.bodySmall)").size)
    }

    @Test
    fun rowsDoNotChooseTheirOwnHintStyle() {
        val dir = File("src/main/java/vn/abook/player/ui")
        assertTrue("không thấy ${dir.absolutePath}", dir.isDirectory)
        val own = Regex("""BasicText\(\s*(hint|summary)\b""")
        val findings = dir.walkTopDown().filter { it.extension == "kt" }.flatMap { file ->
            (if (file.name == "ListParts.kt") emptyList() else ownSubLines(file.name, file.readText())) + file.readLines().mapIndexedNotNull { index, line ->
                val code = line.substringBefore("//")
                when {
                    "hintStyle" in code -> "${file.name}:${index + 1} tham số hintStyle"
                    own.containsMatchIn(code) && file.name != "ListParts.kt" -> "${file.name}:${index + 1} tự dựng dòng mô tả"
                    else -> null
                }
            }
        }.toList()
        assertEquals(findings.joinToString("\n"), emptyList<String>(), findings)
    }
}
