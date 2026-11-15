package vn.abook.player.readaloud

import android.speech.tts.TextToSpeech
import android.speech.tts.Voice
import java.util.Locale
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class DeviceVoiceLabelTest {
    private fun voice(name: String, online: Boolean = false, quality: Int = Voice.QUALITY_NORMAL,
                      language: String = "vi-VN", features: Set<String> = emptySet()) =
        Voice(name, Locale.forLanguageTag(language), quality, Voice.LATENCY_NORMAL, online, features)

    @Test fun enginesAreNamedWithoutInferringGenderOrAccent() {
        for ((engine, label, expected) in listOf(
            Triple("com.google.android.tts", "Speech Services", "Google ngoại tuyến"),
            Triple("com.samsung.SMT", "Samsung TTS", "Samsung ngoại tuyến"),
            Triple("oem.reader", "OPPO", "OPPO ngoại tuyến"),
            Triple("third.party", "Acme", "Acme ngoại tuyến"),
            Triple("unknown.reader", "", "Máy ngoại tuyến"),
            Triple("unknown.reader", "A long engine label", "Máy ngoại tuyến"),
        )) {
            val result = DeviceVoiceNames.describe(engine, label, listOf(voice("vi-vn-x-vif-local"))).single()
            assertEquals(expected, result.name)
            assertEquals("", result.gender)
            assertEquals("device:vi-vn-x-vif-local", result.id)
        }
    }

    @Test fun metadataWinsOverSuffixAndOfflineThenQualityWinsOverName() {
        val result = DeviceVoiceNames.describe("com.google.android.tts", "", listOf(
            voice("a-local", online = true, quality = Voice.QUALITY_VERY_HIGH),
            voice("b-network", quality = Voice.QUALITY_NORMAL),
            voice("z-local", quality = Voice.QUALITY_HIGH),
            voice("english", language = "en-US"),
            voice("missing", features = setOf(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED)),
        ))
        assertEquals(listOf("device:z-local", "device:b-network", "device:a-local"), result.map { it.id })
        assertEquals(listOf("Google ngoại tuyến 2", "Google ngoại tuyến 1", "Google cần mạng"), result.map { it.name })
        assertEquals(listOf(false, false, true), result.map { it.online })
        assertEquals(listOf(true, false, false), result.map { it.default })
        assertTrue(result.all { it.name.split(" ").size <= 4 })
    }

    @Test fun numberingIsStableWhenTheEngineReturnsADifferentOrder() {
        val input = listOf(voice("vi-vn-x-gft-local"), voice("vi-vn-x-vie-local"), voice("vi-vn-x-vif-network", true))
        assertEquals(DeviceVoiceNames.describe("com.google.android.tts", "", input),
            DeviceVoiceNames.describe("com.google.android.tts", "", input.reversed()))
        assertTrue(DeviceVoiceNames.describe("", "", emptyList()).isEmpty())
    }
}
