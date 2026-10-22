package vn.abook.player

import java.io.File
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Điện thoại hiện tên giọng máy khác như máy tính (`humanize.voice_label` / `labelled_voice` / `label_cast_voices`): nhãn đọc từ MỘT file
 * `abook/webui/assets/voice_labels.json` (pytest giữ nó khớp ENGINE_VOICES). Giọng VieNeu nhãn là chính khoá nên không thêm gì.
 */
class VoiceLabelsTest {
    private val file = File("../../../abook/webui/assets/voice_labels.json")

    @Before
    fun load() {
        VoiceLabels.labels = VoiceLabels.parse(file.readText())
    }

    @After
    fun unload() {
        VoiceLabels.labels = emptyMap()
    }

    @Test
    fun the_label_of_a_key_is_the_name_the_desktop_shows_and_a_vieneu_voice_keeps_its_own_name() {
        assertEquals("Bảo Trang", VoiceLabels.label("baotrang"))
        assertEquals("Supertonic F1", VoiceLabels.label("F1"))
        assertEquals("Thiện Minh", VoiceLabels.label("Thiện Minh"))
        assertEquals("", VoiceLabels.label(""))
        assertEquals(15, VoiceLabels.labels.size)
    }

    @Test
    fun a_voice_gets_a_label_only_when_it_differs_from_the_key_and_the_original_is_untouched() {
        val machine = JSONObject().put("key", "k").put("preset", "giahuy").put("tone", "")
        val labelled = VoiceLabels.labelled(machine)
        assertEquals("Gia Huy", labelled.getString("label"))
        assertEquals("giahuy", labelled.getString("preset"))
        assertFalse(machine.has("label"))
        val vieneu = JSONObject().put("preset", "Thiện Minh")
        assertFalse(VoiceLabels.labelled(vieneu).has("label"))
    }

    @Test
    fun a_cast_gets_a_label_on_every_voice_of_the_narrator_and_the_people() {
        val cast = JSONObject("""{"narrator":{"voice":"x","profile":{"preset":"baotrang","key":"k","tone":""},"pendingVoice":{"preset":"F1","gender":""}},
            "characters":[{"name":"A","voice":{"preset":"giahuy"},"pendingVoice":null},{"name":"B","voice":null}],"extras":[]}""")
        val labelled = VoiceLabels.labelCast(cast)
        assertEquals("Bảo Trang", labelled.getJSONObject("narrator").getJSONObject("profile").getString("label"))
        assertEquals("Supertonic F1", labelled.getJSONObject("narrator").getJSONObject("pendingVoice").getString("label"))
        val people = labelled.getJSONArray("characters")
        assertEquals("Gia Huy", people.getJSONObject(0).getJSONObject("voice").getString("label"))
        assertTrue(people.getJSONObject(1).isNull("voice"))
        assertFalse(cast.getJSONObject("narrator").getJSONObject("profile").has("label"))
        assertFalse(cast.getJSONArray("characters").getJSONObject(0).getJSONObject("voice").has("label"))
    }
}
