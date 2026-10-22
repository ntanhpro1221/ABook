package vn.abook.player.readaloud

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ReadingAnchorTest {
    @Test
    fun text_anchor_survives_a_new_timeline_and_rejects_changed_text() {
        val paragraphs = listOf("Chương một", "😀 Một hai ba.", "Đoạn sau.")
        val type = Class.forName("vn.abook.player.readaloud.ReadingAnchor")
        val instance = type.getField("INSTANCE").get(null)
        val make = type.getDeclaredMethod("make", List::class.java, Int::class.javaPrimitiveType, Int::class.javaPrimitiveType)
        val restore = type.getDeclaredMethod("restore", List::class.java, JSONObject::class.java)
        val anchor = make.invoke(instance, paragraphs, 1, 2) as JSONObject
        assertEquals("fnv1a64:bb657205cfbee8a0", anchor.getString("textHash"))
        assertEquals(6, anchor.getInt("charOffset")) // code points: emoji chiếm một ký tự
        assertEquals(1 to 2, restore.invoke(instance, paragraphs, anchor))
        assertNull(restore.invoke(instance, paragraphs + "Nội dung mới", anchor))
        assertNull(restore.invoke(instance, paragraphs, JSONObject(anchor.toString()).put("segment", 99)))
    }
}
