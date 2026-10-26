package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.Dp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.ui.components.*
import vn.abook.player.ui.theme.*

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class IconTextColumnTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun checkerRejectsTheOriginalTitleOnlyIndent() {
        rule.setContent {
            AbookTheme(false) {
                Column(Modifier.testTag("broken")) {
                    Row {
                        Box(Modifier.width(24.dp).testTag("row_leading")) { LaptopIcon(Abook.colors.text) }
                        Spacer(Modifier.width(12.dp))
                        Caption("Tên thiết bị", Modifier.testTag("row_title"))
                    }
                    Caption("Dòng phụ bị lệch")
                }
            }
        }
        assertThrows(AssertionError::class.java) {
            rule.onNodeWithTag("broken", useUnmergedTree = true).assertIconLedTextColumn()
        }
    }

    @Test fun listAndMenuKeepSupportingTextInTheColumnAtLargeFontSize() {
        var firstLine = Dp.Unspecified
        rule.setContent {
            AbookTheme(false) {
                val density = LocalDensity.current
                CompositionLocalProvider(LocalDensity provides Density(density.density, 1.3f)) {
                    firstLine = FirstLine
                    Column(Modifier.width(240.dp)) {
                        ListItem("Máy tính có tên dài xuống nhiều dòng", tag = "list", hint = "Đang phát",
                            leading = { LaptopIcon(Abook.colors.text) },
                            below = { Caption("Tên chương"); Caption("1:02 · 10:00") })
                        MenuRow("Mở Studio", "menu", unavailable = true, supporting = "Máy tính này chỉ cho nghe.") { LaptopIcon(it) }
                    }
                }
            }
        }
        rule.assertIconLedTextColumns()
        val title = rule.onNode(hasTestTag("row_title") and hasAnyAncestor(hasTestTag("list")), useUnmergedTree = true).getUnclippedBoundsInRoot()
        val icon = rule.onNode(hasTestTag("row_leading") and hasAnyAncestor(hasTestTag("list")), useUnmergedTree = true).getUnclippedBoundsInRoot()
        assertEquals(title.top.value + firstLine.value / 2, ((icon.top + icon.bottom) / 2).value, 0.5f)
    }
}
