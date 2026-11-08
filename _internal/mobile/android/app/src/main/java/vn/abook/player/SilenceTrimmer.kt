package vn.abook.player

import kotlin.math.*

/** Bounded lookahead on source PCM, before gain/Sonic. All channels must be quiet.
 * Short pauses are byte-preserved; a long pause keeps both edges and at least 1.5 s.
 * The piecewise clock is queried at the HEARD frame, never from decode-ahead totals. */
class SilenceTrimmer(private val rate: Int, private val channels: Int) {
    private var settings = AudioFxSettings()
    private var quiet = ArrayDeque<DoubleArray>()
    private var longPause = false
    private var inputFrames = 0L
    private var outputFrames = 0L
    private var removed = 0L
    private var floor = 0.0
    private var trigger = 0
    private var keep = 0
    private val cuts = mutableListOf<Pair<Long, Long>>()
    private fun emitFrame(frame: DoubleArray, emit: (DoubleArray) -> Unit) { emit(frame); outputFrames++ }
    fun configure(value: AudioFxSettings, emit: (DoubleArray) -> Unit) {
        val next = value.safe()
        if (next.skipSilence != settings.skipSilence || next.silenceDb != settings.silenceDb ||
            next.silenceSeconds != settings.silenceSeconds || next.keepSeconds != settings.keepSeconds) finish(emit)
        settings = next
        floor = 10.0.pow(next.silenceDb / 20)
        trigger = (next.silenceSeconds * rate).roundToInt()
        keep = (next.keepSeconds * rate).roundToInt()
    }
    private fun finishPause(emit: (DoubleArray) -> Unit) {
        if (longPause) {
            removed = inputFrames - outputFrames - quiet.size
            cuts.add(outputFrames to removed)
        }
        while (quiet.isNotEmpty()) emitFrame(quiet.removeFirst(), emit)
        longPause = false
    }
    fun push(frame: DoubleArray, emit: (DoubleArray) -> Unit) {
        // Finish before counting the first voiced frame: it must not enter removed time.
        val silent = settings.skipSilence && frame.all { it.isFinite() && abs(it) <= floor }
        if (!silent) { finishPause(emit); inputFrames++; emitFrame(frame, emit); return }
        inputFrames++
        quiet.addLast(frame.copyOf(channels))
        if (!longPause && quiet.size > trigger) {
            repeat(keep / 2) { emitFrame(quiet.removeFirst(), emit) }
            longPause = true
        }
        if (longPause) while (quiet.size > keep - keep / 2) quiet.removeFirst()
    }
    fun finish(emit: (DoubleArray) -> Unit) = finishPause(emit)
    fun sourceDurationUs(compressedUs: Long): Long {
        val frame = compressedUs * rate / 1_000_000
        val cut = cuts.lastOrNull { it.first <= frame }?.second ?: 0L
        return compressedUs + cut * 1_000_000 / rate
    }
}
