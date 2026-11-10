package vn.abook.player.ui

import androidx.compose.ui.graphics.Color
import org.junit.Assert.assertEquals
import org.junit.Test
import vn.abook.player.ui.theme.*

class SwitchColorTest {
    @Test fun switchTokensMatchTheDesignInBothThemes() {
        assertEquals(Color(0xFFA0600C), LightColors.switchOn)
        assertEquals(Color(0xFFE9A945), DarkColors.switchOn)
        assertEquals(Color(LightPalette.SWITCH_OFF), LightColors.switchOff)
        assertEquals(Color(DarkPalette.SWITCH_OFF), DarkColors.switchOff)
        assertEquals(Color(LightPalette.SWITCH_THUMB), LightColors.switchThumb)
        assertEquals(Color(DarkPalette.SWITCH_THUMB), DarkColors.switchThumb)
    }
}
