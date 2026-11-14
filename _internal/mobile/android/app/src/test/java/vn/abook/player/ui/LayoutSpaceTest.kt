package vn.abook.player.ui

import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Test
import vn.abook.player.ui.theme.remainingSpace

class LayoutSpaceTest {
    @Test fun insetsAndDocksCanConsumeTheEntireViewport() {
        for (size in listOf(0, 1, 24, 47, 48, 200, 320, 800)) {
            val expected = maxOf(0, size - 48)
            assertEquals(expected, remainingSpace(size, 48))
            assertEquals(expected.dp, remainingSpace(size.dp, 48.dp))
        }
    }
}
