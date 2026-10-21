package vn.abook.player.readaloud

import vn.abook.player.vieneu.VieneuAudio
import vn.abook.player.vieneu.VieneuSpeaker
import vn.abook.player.vieneu.VieneuUnits
import vn.abook.player.vieneu.VieneuVoices
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.RandomAccessFile
import java.security.MessageDigest
import java.util.concurrent.Future

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
 * Play starts only when the remaining units will be ready before the sound reaches them ([readyToPlay], same rule and constant as the desktop) - or once the listener has
 * no sound left before this paragraph ([reach]): from then on holding a finished unit back only makes the silence longer (dev/gap, OPPO, Supertonic fast: 4.0 s after a
 * chapter heading and 9.1 s before a long paragraph while its first unit was ready; started at once, 0.5 + 0.6 s and 0.1 + 1.3 s, the pauses at sentence ends).
 */
class LocalLive(
    private val target: LiveClips.Target,
    private val out: File,
    private val tokens: List<String>,
    private val units: List<VieneuUnits.Unit>,
    private val speed: Double = 1.0,
    private val clock: () -> Long = System::nanoTime,
    /** [clock] time at which the listener runs out of sound before this paragraph ([LiveClips.Target.reachNanos]); [Long.MAX_VALUE]: not known / not playing. */
    private val reach: Long = Long.MAX_VALUE,
    /** Runs a task after so many milliseconds (another thread; tests run it by hand): releases what is held when [reach] passes between two units. */
    private val later: (Long, () -> Unit) -> Future<*>? = ::schedule,
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

        /** Seconds of sound per character of text assumed when only the machine's work per character is known ([charsBeforeStart]); ~15 characters a second (a65: 293 characters, 16.2 s). */
        const val AUDIO_PER_CHAR = 0.06

        /** The shown words and the units [voice] will read [text] in (as [here] gets them from the voice); null for a voice that does not read by units. */
        fun unitsOf(voice: String, text: String, origin: String?, readings: Map<String, String>?): Pair<List<String>, List<VieneuUnits.Unit>>? {
            val (provider, rest) = ClipCache.split(voice)
            return when (provider) {
                SupertonicVoices.PREFIX -> SupertonicText.units(text, origin, readings)
                VieneuVoices.PREFIX -> VieneuSpeaker.MAX_CHARS[rest.substringBefore('/')]?.let { VieneuUnits.units(text, it, origin, readings) }
                else -> null
            }
        }

        /**
         * How many characters of a paragraph cut into units of [unitChars] must be read before its stream may start ([readyToPlay]) on a machine that works [workPerChar]
         * seconds per character (sound per character [audioPerChar]). A paragraph of one unit (or one that never gets ahead of the sound) is read whole. The opening hold of
         * a chapter waits for exactly this time, not for the whole paragraph ([ReadAheadPolicy.openingHoldMs]).
         */
        fun charsBeforeStart(unitChars: List<Int>, workPerChar: Double, speed: Double = 1.0, audioPerChar: Double = AUDIO_PER_CHAR): Int {
            var done = 0
            for (i in unitChars.indices) {
                done += unitChars[i]
                if (readyToPlay(done * audioPerChar, done * workPerChar, done, unitChars.drop(i + 1), speed)) return done
            }
            return done
        }

        /**
         * The characters of [text] to be read by [voice] before its stream starts ([charsBeforeStart] over the units the voice will cut it into); all of it when the voice is unknown,
         * its speed is not measured yet ([workPerChar] null) or the paragraph is one unit (no stream, [here] is null).
         */
        fun charsBeforeStreamStarts(
            voice: String, text: String, origin: String?, readings: Map<String, String>?, workPerChar: Double?, speed: Double = 1.0, audioPerChar: Double = AUDIO_PER_CHAR,
        ): Int {
            if (workPerChar == null) return text.length
            val (tokens, units) = runCatching { unitsOf(voice, text, origin, readings) }.getOrNull() ?: return text.length
            if (units.size < 2) return text.length
            return charsBeforeStart(units.map { it.text(tokens).length }, workPerChar, speed, audioPerChar)
        }

        /** The streaming of a read of [text] into [out] when this thread reads for a listener who waits for it ([LiveClips.receiving]); null otherwise, and for a
         *  paragraph of one unit (no sooner sound, one more lift - desktop `local_stream.for_clip`). [cut]: the shown words and the units as the voice will cut the paragraph (asked for only when a listener waits). */
        fun here(out: File, cut: () -> Pair<List<String>, List<VieneuUnits.Unit>>): LocalLive? {
            val target = LiveClips.here()?.target?.takeIf { it.accepting() } ?: return null
            val (tokens, units) = cut()
            if (units.size < 2) return null
            return LocalLive(target, out, tokens, units, target.speed().toDouble(), reach = target.reachNanos())
        }

        private val timer by lazy {
            java.util.concurrent.ScheduledThreadPoolExecutor(1) { Thread(it, "local-live-reach").apply { isDaemon = true } }
                .apply { removeOnCancelPolicy = true }
        }

        private fun schedule(delayMs: Long, task: () -> Unit): Future<*> =
            timer.schedule({ runCatching(task) }, delayMs, java.util.concurrent.TimeUnit.MILLISECONDS)
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
    /** [finish] or [failed] ran: a late [release] sends nothing. */
    private var closed = false
    private var waking = false
    private var wakeUp: Future<*>? = null

    /** A unit was just read: [wave] exactly as it is joined into the clip, [said] = what was read (the pause after it - [VieneuAudio.gapAfter]). */
    @Synchronized
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
        if (started || clock() >= reach || readyToPlay(joiner.samples.toDouble() / rate, (clock() - began) / 1e9, done, left, speed)) {
            flush()
        } else if (!waking && reach != Long.MAX_VALUE) {
            waking = true // the listener runs out of sound before the next unit is read: let them hear this one then
            wakeUp = later(maxOf(0L, (reach - clock()) / 1_000_000)) { release() }
        }
    }

    /** [reach] has passed: the held units go out now (nothing when the stream started meanwhile, failed or the clip is done). */
    @Synchronized
    fun release() {
        if (closed || broken) return
        try {
            flush()
        } catch (error: IOException) {
            broken = true
        }
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
    @Synchronized
    fun finish(samples: FloatArray, rate: Int) {
        closed = true
        wakeUp?.cancel(false)
        wakeUp = null
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
    @Synchronized
    fun failed(error: Exception) {
        closed = true
        wakeUp?.cancel(false)
        wakeUp = null
        runCatching { stream?.close() }
        stream = null
        if (started) target.failed(error)
    }
}
