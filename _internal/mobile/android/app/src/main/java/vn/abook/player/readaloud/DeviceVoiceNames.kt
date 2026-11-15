package vn.abook.player.readaloud

import android.speech.tts.TextToSpeech
import android.speech.tts.Voice
import vn.abook.player.S

/** Engine codes are identifiers, not evidence of gender or accent. */
internal object DeviceVoiceNames {
    fun describe(engine: String, engineLabel: String, voices: Collection<Voice>): List<VoiceInfo> {
        val label = when (engine) {
            "com.google.android.tts" -> S.s_device_engine_google
            "com.samsung.SMT" -> S.s_device_engine_samsung
            else -> engineLabel.trim().takeIf { it.isNotEmpty() && !it.any(Char::isWhitespace) }
                ?: S.s_device_engine_default
        }
        val installed = voices.filter {
            it.locale.language == "vi" && TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED !in it.features.orEmpty()
        }.distinctBy { it.name }
        fun base(voice: Voice) = if (voice.isNetworkConnectionRequired) S.s_device_voice_network(label)
            else S.s_device_voice_offline(label)
        // Number only collisions; Set iteration must not change labels.
        val names = installed.groupBy(::base).flatMap { (name, group) ->
            group.sortedBy { it.name }.mapIndexed { index, voice ->
                voice.name to if (group.size == 1) name else S.s_device_voice_number(name, index + 1)
            }
        }.toMap()
        return installed.sortedWith(compareBy({ it.isNetworkConnectionRequired }, { -it.quality }, { it.name }))
            .mapIndexed { index, voice ->
                VoiceInfo("device:${voice.name}", names.getValue(voice.name), "device", voice.isNetworkConnectionRequired, index == 0)
            }
    }
}
