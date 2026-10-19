package vn.abook.player.readaloud

import vn.abook.player.vieneu.VieneuAudio
import vn.abook.player.vieneu.VieneuSpeaker
import vn.abook.player.vieneu.VieneuUnits
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.RandomAccessFile
import java.security.MessageDigest

/**
 * Local voices (VieNeu, Supertonic) STREAM the paragraph the listener is waiting for (desktop: abook/readaloud/local_stream.py): each unit goes into the clip file
 * as soon as it is read, so the first sound comes after the FIRST unit instead of the whole paragraph. The file is a growing 16-bit WAV
 * ([VieneuAudio.wavHeader] with both sizes 0xFFFFFFFF: Media3's WavExtractor then reads until the end of input, [vn.abook.player.Streaming.liveExtractors]) that
 * ExoPlayer reads through [LiveClips] exactly like Edge's growing MP3.
 *
 * The finished clip is byte-identical to the one made without streaming: the streamed samples are those of [VieneuAudio.wavBytes] of the joined clip, and
 * [finish] only patches the two sizes in the header. A one-unit paragraph does not stream ([here] is null): its first unit IS the clip, so nothing comes sooner.
 * The clip-wide lift ([ClipLift.lifted]) is known only at the end: a paragraph that gets lifted (rare) is rewritten in place with the final samples (same length
 * and timings).
 * Play starts only when the remaining units will be ready before the sound reaches them ([readyToPlay], same rule and constant as the desktop).
 */
class LocalLive(
    private val target: LiveClips.Target,
    private val out: File,
    private val tokens: List<String>,
    private val units: List<VieneuUnits.Unit>,
    private val speed: Double = 1.0,
    private val clock: () -> Long = System::nanoTime,
) {
    companion object {
        /** Margin on the guesses of the remaining units' length and of the machine's speed (desktop `local_stream.SAFETY`). */
        const val SAFETY = 1.2
        private const val HEADER = 44

        /**
         * Can play start: [madeS] seconds of sound made in [workS] seconds of work (for [charsDone] characters), the units [charsLeft] (characters, in order) still
         * to read, heard at [speed]. r = workS / madeS, unit k ~ madeS / charsDone * its characters. Yes when for EVERY remaining unit k:
         * SAFETY * r * (L_1 + ... + L_k) <= (madeS + L_1 + ... + L_{k-1}) / speed - unit k is read before the sound reaches it (desktop `local_stream.ready_to_play`).
         */
        fun readyToPlay(madeS: Double, workS: Double, charsDone: Int, charsLeft: List<Int>, speed: Double = 1.0): Boolean {
            if (charsLeft.isEmpty()) return true
            if (madeS <= 0 || charsDone <= 0) return false
            val rate = workS / madeS
            val perChar = madeS / charsDone
            var ahead = madeS
            var need = 0.0
            for (chars in charsLeft) {
                val length = perChar * chars
                need += SAFETY * rate * length
                if (need > ahead / maxOf(speed, 0.1)) return false
                ahead += length
            }
            return true
        }

        /** The streaming of a read of [text] into [out] when this thread reads for a listener who waits for it ([LiveClips.receiving]); null otherwise, and for a
         *  paragraph of one unit (no sooner sound, one more lift - desktop `local_stream.for_clip`). Units as the voice will cut them ([VieneuUnits.units], [maxChars]). */
        fun here(out: File, text: String, maxChars: Int, origin: String?, readings: Map<String, String>?): LocalLive? {
            val target = LiveClips.here()?.target?.takeIf { it.accepting() } ?: return null
            val (tokens, units) = VieneuUnits.units(text, maxChars, origin, readings)
            if (units.size < 2) return null
            return LocalLive(target, out, tokens, units, target.speed().toDouble())
        }
    }

    private val began = clock()
    private var joiner: VieneuAudio.Joiner? = null
    private var rate = 0
    private var pause = 0.0
    private val words = ArrayList<Span>()
    /** Units read but not sent yet (waiting for [readyToPlay]). */
    private val held = ArrayList<ByteArray>()
    /** The samples sent, to compare with the final clip in [finish]. */
    private val sent = MessageDigest.getInstance("SHA-1")
    private var stream: FileOutputStream? = null
    private var written = 0L
    var started = false
        private set
    /** Writing the stream failed: nothing more is sent; [finish] still writes the final clip. */
    private var broken = false

    /** A unit was just read: [wave] exactly as it is joined into the clip, [said] = what was read (the pause after it - [VieneuAudio.gapAfter]). */
    fun unit(wave: FloatArray, rate: Int, said: String) {
        if (broken) return
        try {
            add(wave, rate, said)
        } catch (error: IOException) {
            broken = true
        }
    }

    private fun add(wave: FloatArray, rate: Int, said: String) {
        val joiner = joiner ?: VieneuAudio.Joiner(rate).also {
            joiner = it
            this.rate = rate
        }
        val index = joiner.spans.size
        val pad = joiner.add(wave, pause)
        pause = VieneuAudio.gapAfter(said)
        val span = joiner.spans.last()
        held += ByteArray(pad * 2) + VieneuAudio.pcm16(wave)
        if (index < units.size) words += VieneuSpeaker.timedWords(tokens, listOf(units[index]), listOf(span), rate, span[1])
        val done = units.take(index + 1).sumOf { it.text(tokens).length }
        val left = units.drop(index + 1).map { it.text(tokens).length }
        if (started || readyToPlay(joiner.samples.toDouble() / rate, (clock() - began) / 1e9, done, left, speed)) flush()
    }

    private fun flush() {
        if (held.all { it.isEmpty() }) return
        val output = stream ?: FileOutputStream(out).also {
            it.write(VieneuAudio.wavHeader(rate, null))
            stream = it
            written = HEADER.toLong()
            started = true
            val format = Wav.Format(rate, 1, 16, HEADER)
            target.format(format::durationMs)
        }
        for (pcm in held) {
            output.write(pcm)
            sent.update(pcm)
            written += pcm.size
        }
        held.clear()
        output.flush()
        target.grew(out, written)
        val duration = (written - HEADER) / 2 * 1000 / rate
        val shown = words.take(tokens.size).map { Span(minOf(it.start, duration), minOf(it.end, duration)) }
        target.words(shown + List(tokens.size - shown.size) { Span(duration, duration) }, duration, duration)
    }

    /** The clip is read: [samples] = the final clip (lifted) at [rate]. Leaves [out] exactly as [VieneuAudio.writeWav] would, then tells the listener it is done. */
    fun finish(samples: FloatArray, rate: Int) {
        if (!started) {
            VieneuAudio.writeWav(samples, rate, out)
            return
        }
        runCatching { stream?.close() }
        stream = null
        val bytes = VieneuAudio.wavBytes(samples, rate)
        val final = MessageDigest.getInstance("SHA-1").apply { update(bytes, HEADER, bytes.size - HEADER) }.digest()
        RandomAccessFile(out, "rw").use { file ->
            if (!broken && written == bytes.size.toLong() && final.contentEquals(sent.digest())) {
                file.write(bytes, 0, HEADER) // the same samples: only the sizes change
            } else {
                file.write(bytes) // lifted as a whole (or the stream broke): the final samples in place, same length
                file.setLength(bytes.size.toLong())
            }
        }
        target.done(out.length())
    }

    /** The read failed after the stream started: the listener hears what came and the player handles the rest ([LiveClips.Target.failed]). */
    fun failed(error: Exception) {
        runCatching { stream?.close() }
        stream = null
        if (started) target.failed(error)
    }
}
