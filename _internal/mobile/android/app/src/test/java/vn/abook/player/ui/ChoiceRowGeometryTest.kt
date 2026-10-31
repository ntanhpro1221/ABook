package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.height
import androidx.compose.ui.unit.width
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.ChoiceRow
import vn.abook.player.ui.data.Choice
import vn.abook.player.ui.data.ReadingSurface
import vn.abook.player.ui.data.ShakeAction
import vn.abook.player.ui.data.ShakeSensitivity
import vn.abook.player.ui.data.ThemeMode
import vn.abook.player.ui.data.VoiceSpeedChoice
import vn.abook.player.ui.devices.PairMethod
import vn.abook.player.ui.export.ExportFormat
import vn.abook.player.ui.screens.SaveKind
import vn.abook.player.ui.studio.NewProfile
import vn.abook.player.ui.studio.ReviewFilter
import vn.abook.player.ui.studio.StudioExportKind
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.Dim

/**
 * Hàng chọn-một (ChoiceRow, kể cả hàng cách nối của màn Thiết bị): (1) mọi bộ lựa chọn THẬT của app nằm trọn một dòng ở 360 dp - soát 31-10 thấy "Tìm máy trong mạng" đẩy hai
 * lựa chọn kia xuống dòng thứ hai; (2) khoảng giữa hai CHỮ luôn bằng nhau dù chữ ngắn hay dài (ô chạm 44 dp không được nở thành khoảng trống thêm).
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class ChoiceRowGeometryTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private data class Opt(override val key: String, override val label: String) : Choice

    private var options by mutableStateOf<List<Choice>>(listOf(Opt("x", "x")))
    private var widthDp by mutableStateOf(328f)
    private var mounted = false

    /** Một setContent cho cả test (đặt lại lần hai là lỗi); đổi bộ lựa chọn bằng trạng thái. */
    private fun show(options: List<Choice>, widthDp: Float) {
        this.options = options
        this.widthDp = widthDp
        if (!mounted) {
            mounted = true
            rule.setContent {
                AbookTheme {
                    Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                        Box(Modifier.width(this@ChoiceRowGeometryTest.widthDp.dp)) {
                            val list = this@ChoiceRowGeometryTest.options
                            key(list) { ChoiceRow(list, list.first(), { _, _ -> }, tag = "c") }
                        }
                    }
                }
            }
        }
        rule.waitForIdle()
    }

    private val real: Map<String, List<Choice>> = mapOf(
        "PairMethod" to PairMethod.entries,
        "ThemeMode" to ThemeMode.entries,
        "ReadingSurface" to ReadingSurface.entries,
        "ShakeAction" to ShakeAction.entries,
        "ShakeSensitivity" to ShakeSensitivity.entries,
        "VoiceSpeedChoice" to VoiceSpeedChoice.entries,
        "ExportFormat" to ExportFormat.entries,
        "SaveKind" to SaveKind.entries,
        "StudioExportKind" to StudioExportKind.entries,
        "NewProfile" to NewProfile.entries,
        "ReviewFilter" to ReviewFilter.entries,
    )

    @Test
    fun everyRealChoiceSetFitsOneLineAt360() {
        val width = 360f - 2 * Dim.margin.value
        val wrapped = ArrayList<String>()
        for ((name, options) in real) {
            show(options, width)
            val tops = options.map { rule.onNodeWithTag("c_${it.key}").getUnclippedBoundsInRoot().top }
            if (tops.distinct().size > 1) wrapped += "$name ${options.map { it.label }} tops=$tops"
        }
        assertTrue("bộ lựa chọn xuống dòng ở 360 dp:\n" + wrapped.joinToString("\n"), wrapped.isEmpty())
    }

    @Test
    fun gapBetweenLabelsIsEqualWhateverTheirWidth() {
        val options = listOf(Opt("a", "Có"), Opt("b", "Chỉ khi cắm sạc"), Opt("c", "Tắt"), Opt("d", "Tự động"))
        show(options, 360f - 2 * Dim.margin.value)
        val ink = options.map { rule.onNodeWithText(it.label, useUnmergedTree = true).getUnclippedBoundsInRoot() }
        val gaps = ink.zipWithNext().map { (a, b) -> b.left.value - a.right.value }
        for (gap in gaps) assertEquals("khoảng giữa hai chữ $gaps", 24f, gap, 1.5f)
        // Ô chạm vẫn đủ 44 dp rộng, 48 dp cao.
        for (option in options) {
            val box = rule.onNodeWithTag("c_${option.key}").getUnclippedBoundsInRoot()
            assertTrue("ô '${option.label}' rộng ${box.width}", box.width >= 43.5.dp)
            assertTrue("ô '${option.label}' cao ${box.height}", box.height >= 47.5.dp)
        }
    }
}
