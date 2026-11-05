package vn.abook.player.readaloud

import android.content.Context
import android.os.Build
import vn.abook.player.vieneu.VieneuVoices
import java.io.File

/** Local adapters share one engine interface; models and runtimes remain download-on-demand. */
object AndroidVoicePick {
    @Volatile private var picker: MachineVoicePick? = null

    fun engines(ctx: Context): List<LocalEngine> =
        (VieneuVoices.voices(ctx) + SupertonicVoices.voices(ctx)).groupBy { MachineVoicePick.engineOf(it.id) }.map { (key, offered) ->
            object : LocalEngine {
                override val id = key
                override val voices = offered
                override val capabilities = setOf("offline", "streaming", "vi-VN")
                override val resourceNeeds = mapOf("device" to "cpu", "runtime" to "download-on-demand", "RAM" to "measured")
                override val mark = if (key.startsWith("vieneu:")) VieneuVoices.module(ctx).mark(offered.first().id) else SupertonicVoices.module(ctx).mark(false)
                override fun synthesize(text: String, out: File): Clip =
                    if (key.startsWith("vieneu:")) VieneuVoices.voice(ctx, offered.first().id).synthesize(text, out)
                    else SupertonicVoices.voice(ctx, offered.first().id + "#q").synthesize(text, out)
                override fun forget() { if (key.startsWith("vieneu:")) VieneuVoices.forget() else SupertonicVoices.forget() }
            }
        }

    @Synchronized
    fun of(context: Context): MachineVoicePick = picker ?: run {
        val ctx = context.applicationContext
        MachineVoicePick(File(ctx.filesDir, "voice-pick.json"), "${Build.FINGERPRINT}/${Runtime.getRuntime().availableProcessors()}", { engines(ctx) }, {
            // VmRSS includes native ONNX model memory, unlike the Java heap counter.
            File("/proc/self/status").useLines { lines ->
                lines.firstOrNull { it.startsWith("VmRSS:") }?.split(Regex("\\s+"))?.getOrNull(1)?.toLongOrNull()?.times(1024) ?: 0L
            }
        }).also { picker = it }
    }
}
