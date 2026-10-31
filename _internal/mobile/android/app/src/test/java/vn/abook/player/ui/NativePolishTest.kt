package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.swipeLeft
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.bottomClearance
import vn.abook.player.ui.components.hasOrphanLastLine
import vn.abook.player.ui.components.keepUnitsTogether
import vn.abook.player.ui.components.keepUrlTogether
import vn.abook.player.ui.data.LibrarySort
import vn.abook.player.ui.devices.Storage
import vn.abook.player.ui.screens.BookTab
import vn.abook.player.ui.screens.BookTabs
import vn.abook.player.ui.screens.FilterBar
import vn.abook.player.ui.screens.LibraryUiState
import vn.abook.player.ui.screens.filterSpread
import vn.abook.player.ui.nav.Tab
import vn.abook.player.ui.nav.TabState
import vn.abook.player.ui.shell.TabBar
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.Dim
import java.io.File

/**
 * Các LOẠI lỗi của đợt soát điện thoại thật 30-10 (NATIVE_POLISH), mỗi loại một máy dò chứ không chỉ chỗ được chỉ:
 * hàng chip cuộn được + khe tối thiểu (320 / 360 / 411 dp, chữ hệ thống to), việc phá huỷ nào cũng phải qua bước xác nhận, chữ lẻ ở dòng cuối và địa chỉ web đứt giữa đường dẫn,
 * chữ "Sách 1 KB" khi chưa có sách, vạch tab sát mép dưới màn.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class NativePolishTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val ui = File("src/main/java/vn/abook/player/ui")

    // ---- hàng bộ lọc: khe tối thiểu 16 dp, thiếu chỗ thì cuộn ----

    @Test
    fun filterSpreadKeepsTheGapAndScrollsWhenShort() {
        val min = 16
        val max = 24
        // Đủ chỗ: nội dung = khung nhìn, khe trong [16, 24].
        for (viewport in listOf(300, 360, 411)) {
            val (content, gap) = filterSpread(viewport, ink = 180, count = 4, minGap = min, maxGap = max)
            assertEquals("đủ chỗ thì không cuộn ($viewport)", viewport, content)
            assertTrue("khe $gap trong [$min, $max]", gap in min..max)
        }
        // Thiếu chỗ (320 dp, chữ hệ thống 130 %): khe KHÔNG tụt dưới 16, nội dung dài hơn khung -> cuộn.
        val (content, gap) = filterSpread(viewport = 200, ink = 260, count = 4, minGap = min, maxGap = max)
        assertEquals(min, gap)
        assertEquals(260 + 3 * min, content)
        assertTrue(content > 200)
    }

    private fun showFilterBar(widthDp: Int) {
        rule.setContent {
            AbookTheme {
                val scope = rememberCoroutineScope()
                val state = remember { LibraryUiState(scope, LibrarySort.Recent) }
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    Box(Modifier.width(widthDp.dp)) { FilterBar(state, {}, Modifier.fillMaxWidth()) }
                }
            }
        }
        rule.waitForIdle()
    }

    private fun assertFilterRowIsRoomy(widthDp: Int) {
        showFilterBar(widthDp)
        val tags = listOf("filter_all", "filter_listening", "filter_new", "filter_finished")
        val row = rule.onNodeWithTag("filter_row").getUnclippedBoundsInRoot()
        val sort = rule.onNodeWithTag("sort_button").getUnclippedBoundsInRoot()
        assertTrue("hàng lọc ($widthDp dp) không đè nút Xếp theo: ${row.right} > ${sort.left}", row.right <= sort.left + 0.5.dp)
        val chips = tags.map { rule.onNodeWithTag(it).getUnclippedBoundsInRoot() }
        // Mỗi chữ có lề chạm 6 dp hai bên (ô chồng lên nhau 12 dp khi khe = 0): khe giữa CHỮ = khoảng giữa hai ô + 12 dp.
        for ((a, b) in chips.zipWithNext()) {
            val gap = b.left - a.right + 12.dp
            assertTrue("khe giữa hai chữ bộ lọc ở $widthDp dp là $gap, dưới 16 dp", gap >= 15.5.dp)
        }
    }

    @Test fun filterRowIsRoomyAt320() = assertFilterRowIsRoomy(320)

    @Test @Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi", fontScale = 1.3f)
    fun filterRowIsRoomyAt360WithBigSystemText() = assertFilterRowIsRoomy(360)

    @Test fun filterRowIsRoomyAt411() = assertFilterRowIsRoomy(411)

    @Test @Config(sdk = [35], qualifiers = "w320dp-h700dp-xxhdpi", fontScale = 1.3f)
    fun lastFilterIsReachableByScrollingAt320WithBigText() {
        showFilterBar(320)
        // Không mục nào bị bỏ: vuốt hàng sang trái thì "Xong" vào khung.
        rule.onNodeWithTag("filter_row").performTouchInput { swipeLeft() }
        rule.waitForIdle()
        val row = rule.onNodeWithTag("filter_row").getUnclippedBoundsInRoot()
        val last = rule.onNodeWithTag("filter_finished").getUnclippedBoundsInRoot()
        assertTrue("\"Xong\" vào khung sau khi cuộn", last.right <= row.right + 14.dp)
    }

    // ---- hàng mục của trang sách cũng cuộn khi hẹp ----

    @Test @Config(sdk = [35], qualifiers = "w320dp-h700dp-xxhdpi", fontScale = 1.3f)
    fun bookTabsStayWholeAndScrollAt320WithBigText() {
        rule.setContent {
            AbookTheme {
                var selected by remember { mutableStateOf(BookTab.Chapters) }
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    BookTabs(BookTab.entries, selected, chapterCount = 128, onPick = { selected = it })
                }
            }
        }
        rule.waitForIdle()
        for (tab in BookTab.entries) {
            rule.onNodeWithTag(tab.tag).performScrollTo()
            val bar = rule.onNodeWithTag("book_tabs").getUnclippedBoundsInRoot()
            val box = rule.onNodeWithTag(tab.tag).getUnclippedBoundsInRoot()
            assertTrue("mục ${tab.label} nằm trong khung sau khi cuộn", box.left >= bar.left - 0.5.dp && box.right <= bar.right + 0.5.dp)
        }
    }

    // ---- thanh tab: vạch không sát mép dưới ----

    @Test
    fun bottomClearanceNeverDropsBelowTheFloor() {
        assertEquals(Dim.s8, bottomClearance(0.dp))
        assertEquals(Dim.s8, bottomClearance(3.dp))
        assertEquals(24.dp, bottomClearance(24.dp))
    }

    @Test
    fun tabUnderlineClearsTheBottomEdgeEvenWithNoSystemInset() {
        rule.setContent {
            AbookTheme {
                val scope = rememberCoroutineScope()
                val tabs = remember { TabState(scope) }
                Column(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    Box(Modifier.weight(1f))
                    TabBar(tabs)
                }
            }
        }
        rule.waitForIdle()
        val root = rule.onRoot().getUnclippedBoundsInRoot()
        val indicator = rule.onNodeWithTag("tab_indicator").getUnclippedBoundsInRoot()
        // Robolectric không có thanh điều hướng (inset 0) = đúng ca của ColorOS giấu vạch cử chỉ.
        assertTrue("vạch tab cách mép dưới ${root.bottom - indicator.bottom}, cần >= 8 dp", root.bottom - indicator.bottom >= Dim.s8 - 0.5.dp)
        rule.onNodeWithTag(Tab.Library.tag).getUnclippedBoundsInRoot()
    }

    // ---- Dung lượng khi chưa có sách ----

    @Test
    fun storageLineSaysThereAreNoBooksInsteadOfOneKilobyte() {
        assertEquals("Chưa có sách · còn trống 20 GB", Storage(bytes = 0, free = 20L * 1024 * 1024 * 1024).line)
        assertEquals("Chưa có sách · còn trống 20 GB", Storage(bytes = 300, free = 20L * 1024 * 1024 * 1024).line)
        assertEquals("Sách 2 MB · còn trống 10 GB", Storage(bytes = 2L * 1024 * 1024, free = 10L * 1024 * 1024 * 1024).line)
    }

    // ---- chữ lẻ ở dòng cuối + địa chỉ web ----

    @Test
    fun orphanDetectorAndUrlGlue() {
        assertTrue(hasOrphanLastLine(listOf("Ngô Tất Tố · 12 chương ·", "giờ")))
        assertTrue(hasOrphanLastLine(listOf("Dàn nhân vật hiện ra khi truyện đã được phân", "vai.")))
        assertFalse(hasOrphanLastLine(listOf("Ngô Tất Tố · 12 chương", "· 2 giờ")))
        assertFalse(hasOrphanLastLine(listOf("Ngô Tất Tố · 12", "chương · 2 giờ")))
        assertFalse(hasOrphanLastLine(listOf("một dòng")))
        val glued = keepUrlTogether("Giấy phép MIT - github.com/ntanhpro1221/ABook")
        assertEquals("Giấy phép MIT - github.com/\u2060ntanhpro1221/\u2060ABook", glued)
        assertEquals("không địa chỉ thì không đổi", "Xoá khỏi máy này. Gồm cả log.", keepUrlTogether("Xoá khỏi máy này. Gồm cả log."))
    }

    /** Dòng của một đoạn chữ đã dàn ở bề rộng [width] bằng đúng kiểu chữ của app. */
    private var sample by mutableStateOf("")
    private var sampleWidth by mutableStateOf(100.dp)
    private var measured: TextLayoutResult? = null
    private var sampleShown = false

    private fun linesAt(text: String, width: Dp, small: Boolean = true): List<String> {
        if (!sampleShown) {
            sampleShown = true
            rule.setContent {
                AbookTheme {
                    Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                        BasicText(sample, style = if (small) Abook.type.bodySmall else Abook.type.body, modifier = Modifier.width(sampleWidth), onTextLayout = { measured = it })
                    }
                }
            }
        }
        measured = null
        rule.runOnIdle { sample = text; sampleWidth = width }
        rule.waitForIdle()
        val result = measured!!
        return (0 until result.lineCount).map { result.layoutInput.text.text.substring(result.getLineStart(it), result.getLineEnd(it)) }
    }

    @Test
    fun appTextStylesDoNotLeaveALoneWordOnTheLastLine() {
        val samples = listOf(
            keepUnitsTogether("Ngô Tất Tố · 12 chương · 2 giờ"),
            "Dàn nhân vật hiện ra khi truyện đã được phân vai.",
            "Bản đọc đã làm chiếm 12 MB trên máy này.",
        )
        // Quét nhiều bề rộng quanh cột chữ của điện thoại 360 dp (cột phụ của trang sách ~ 200 dp, câu trống ~ 320 dp).
        val offences = ArrayList<String>()
        for (text in samples) for (width in listOf(190, 205, 220, 240, 260, 280, 300, 320)) {
            val lines = linesAt(text, width.dp)
            if (hasOrphanLastLine(lines)) offences += "$width dp: $lines"
        }
        assertTrue("Chữ lẻ ở dòng cuối: $offences", offences.isEmpty())
    }

    @Test
    fun numberAndUnitAreNeverSplitAcrossLines() {
        assertEquals("Ngô Tất Tố · 12 chương · 2 giờ", keepUnitsTogether("Ngô Tất Tố · 12 chương · 2 giờ"))
        assertEquals("không số thì không đổi", "Giọng đọc chương trình", keepUnitsTogether("Giọng đọc chương trình"))
        for (width in listOf(190, 205, 215, 225, 240, 260, 280)) {
            val lines = linesAt(keepUnitsTogether("Ngô Tất Tố · 12 chương · 2 giờ"), width.dp)
            assertTrue("số không bị tách khỏi đơn vị ở $width dp: $lines", lines.none { it.trimEnd().endsWith("12") || it.trimEnd().endsWith("2") })
        }
    }

    @Test
    fun webAddressStaysOnOneLineWhenItFits() {
        val text = keepUrlTogether("Giấy phép MIT - github.com/ntanhpro1221/ABook")
        for (width in listOf(230, 260, 290, 320)) {
            val lines = linesAt(text, width.dp).map { it.replace("\u2060", "") }
            assertTrue("địa chỉ nằm nguyên một dòng ở $width dp: $lines", lines.any { "github.com/ntanhpro1221/ABook" in it })
        }
    }

    // ---- việc phá huỷ nào cũng qua bước xác nhận ----

    private val destructive = Regex("""\b(?:repo|state|source|voice|devices|music|editor)\.(?:clear|delete|remove|forget|revoke|discard|unpair)[A-Za-z]*\(""")
    private val guards = listOf("DangerButton(", "ConfirmPage(", "DeleteBookPage(", "ClearSheet(", "ClearLogsSheet(", "RemoveKeyPage(", "ModuleRemove(", "DiscardSheet(", "ForgetPage(", "RevokeSheet(")

    /** Dòng gọi việc phá huỷ trong một file giao diện mà trong hàm bao nó không có bước xác nhận. */
    private fun unguarded(lines: List<String>): List<String> = lines.mapIndexedNotNull { index, line ->
        val code = line.trimStart()
        if (code.startsWith("//") || code.startsWith("*") || code.startsWith("/*") || !destructive.containsMatchIn(line)) return@mapIndexedNotNull null
        // Hàm bao quanh cuộc gọi (từ dòng `fun` gần nhất phía trên) tới 60 dòng phía dưới phải có bước xác nhận.
        val start = (index downTo 0).firstOrNull { Regex("""^\s*(?:private |internal )?fun """).containsMatchIn(lines[it]) } ?: maxOf(0, index - 15)
        val window = lines.subList(start, minOf(lines.size, index + 61))
        if (window.any { row -> guards.any { it in row } }) null else "dòng ${index + 1}: ${code.take(110)}"
    }

    @Test
    fun everyDestructiveActionOfTheScreensAsksFirst() {
        val views = ui.walkTopDown().filter { it.isFile && it.extension == "kt" }.filter {
            val name = it.name
            val dir = it.parentFile.name
            dir in setOf("screens", "devices", "voice", "editbook", "music", "nowplaying", "export", "addbook", "player") &&
                !(name.endsWith("State.kt") || name.endsWith("Repo.kt") || name.endsWith("Source.kt") || name.endsWith("Model.kt") || name == "ImportQueue.kt" || name == "BookEditor.kt")
        }.toList()
        assertTrue("quét được quá ít file: ${views.size}", views.size >= 15)
        val offenders = views.flatMap { file -> unguarded(file.readLines()).map { "${file.name} $it" } }
        assertTrue("Việc phá huỷ chạy mà không hỏi lại (dùng ConfirmPage + DangerButton): $offenders", offenders.isEmpty())
    }

    @Test
    fun theDestructiveRuleCatchesAnUnguardedClear() {
        assertEquals(1, unguarded(listOf("ListItem(\"Xoá nhật ký\", onClick = { repo.clearLogs() })")).size)
        assertEquals(0, unguarded(listOf("ConfirmPage(\"Xoá?\", \"x\", listOf(), \"\") {", "    DangerButton(\"Xoá\", { repo.clearLogs() }, \"y\")", "}")).size)
    }

    @Test
    fun noSheetHostsAnUrlWithoutKeepingItWhole() {
        val offenders = ui.walkTopDown().filter { it.isFile && it.extension == "kt" && it.name != "TextWrap.kt" }.flatMap { file ->
            file.readLines().mapIndexedNotNull { index, line ->
                val code = line.trimStart()
                if (code.startsWith("//") || code.startsWith("*") || code.startsWith("/*")) return@mapIndexedNotNull null
                if (Regex("""\"[^\"]*[a-z0-9]\.(?:com|org|vn|net|io|dev)/[^\"]*\"""").containsMatchIn(line) && "keepUrlTogether" !in line &&
                    "https://" !in line.substringAfter("\"").take(8) && !line.contains("startsWith") && !line.contains("openConnection")
                ) "${file.name} dòng ${index + 1}: ${code.take(100)}" else null
            }
        }.toList()
        assertTrue("Địa chỉ web trong chữ giao diện phải qua keepUrlTogether: $offenders", offenders.isEmpty())
    }
}
