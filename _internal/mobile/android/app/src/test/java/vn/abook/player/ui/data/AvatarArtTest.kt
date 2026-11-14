package vn.abook.player.ui.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Expected values come from abook/avatars.py; web (avatar.test.ts) and Qt (AvatarLogic.js) use the same table. */
class AvatarArtTest {
    private val table = listOf(
        listOf("Minh", "M", "#675f48", "6477", "voice-f269994d.webp"),
        listOf("Ngọc Linh", "NL", "#80565e", "3879", "voice-16178f27.webp"),
        listOf("LUCIEN", "L", "#4c6963", "6245", "voice-c3e21865.webp"),
        listOf("Vua Lê III", "VL", "#4c6963", "5131", "voice-42d1140b.webp"),
        listOf("😀 An", "😀A", "#675f48", "32463", "voice-26f3fecf.webp"),
        listOf("Phạm Tuyên", "PT", "#4c6963", "27855", "voice-fed1eccf.webp"),
    )

    @Test fun patternMatchesTheDesktop() {
        for ((name, initials, color, bits, voice) in table) {
            val pattern = AvatarArt.pattern(name)
            assertEquals(name, initials, pattern.initials)
            assertEquals(name, color, pattern.color)
            assertEquals(name, bits.toInt(), pattern.bits)
            assertEquals(name, voice, AvatarArt.voiceFile(name))
        }
        assertEquals(AvatarArt.pattern("Ngọc Linh"), AvatarArt.pattern("Ngo\u0323c Linh"))
    }

    @Test fun gridIsMirroredAndImageNamesAreStrict() {
        val bits = AvatarArt.pattern("Minh").bits
        for (y in 0..4) for (x in 0..4) assertEquals(AvatarArt.cell(bits, x, y), AvatarArt.cell(bits, 4 - x, y))
        assertTrue(AvatarArt.imageFile("avatars/" + "a".repeat(64) + ".webp"))
        assertFalse(AvatarArt.imageFile("avatars/../x.webp"))
        assertFalse(AvatarArt.imageFile("avatars/" + "a".repeat(64) + ".svg"))
    }
}
