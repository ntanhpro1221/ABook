package vn.abook.player.vieneu

import java.io.File

/** JNI entry points of `libabook_sea_g2p.so` (mobile/sea_g2p_jni/src/lib.rs). Loaded from the module folder, never from the APK. */
internal object SeaG2pNative {
    @Volatile private var loaded: String? = null

    /** Load the library at [file] once per process (a second, different path is refused: the first one stays mapped). */
    @Synchronized
    fun load(file: File) {
        val path = file.absolutePath
        if (loaded == path) return
        check(loaded == null) { "sea-g2p is already loaded from $loaded" }
        System.load(path)
        loaded = path
    }

    @JvmStatic external fun nativeOpen(dictionary: String): Long
    @JvmStatic external fun nativeClose(handle: Long)
    @JvmStatic external fun nativeNormalize(handle: Long, text: String, puncNorm: Boolean): String
    @JvmStatic external fun nativePhonemize(handle: Long, text: String): String
    @JvmStatic external fun nativePuncNorm(text: String): String
}

/**
 * Text -> phonemes for VieNeu: sea-g2p 0.9.1 (pnnbao97/sea-g2p, Apache-2.0), the same Rust crate and the same 63 MB dictionary the desktop runs
 * from its wheel, built as a JNI library by scripts/prepare_sea_g2p_android.py. The dictionary is memory-mapped (page cache, not app heap).
 * Thread-safe: the crate's normaliser and G2P only read.
 */
class SeaG2p(library: File, dictionary: File) : AutoCloseable {
    private var handle: Long

    init {
        SeaG2pNative.load(library)
        handle = SeaG2pNative.nativeOpen(dictionary.absolutePath)
    }

    private fun open(): Long = handle.also { check(it != 0L) { "sea-g2p is closed" } }

    /** `Normalizer("vi").normalize(text, punc_norm)`: numbers, dates, abbreviations... spelled out, lower case. */
    fun normalize(text: String, puncNorm: Boolean = false): String = SeaG2pNative.nativeNormalize(open(), text, puncNorm)

    /** `G2P("vi").convert(text)` on already normalised text. */
    fun g2p(text: String): String = SeaG2pNative.nativePhonemize(open(), text)

    /** `sea_g2p.punc_norm`: one final "." (short sentences always end in "."). */
    fun puncNorm(text: String): String = SeaG2pNative.nativePuncNorm(text)

    /** Text of ONE unit made of [sentences], `vieneu_engine.normalize`: each sentence normalised without the final-punctuation rule, joined with
     *  spaces - what a voice that reads text (Supertonic) is given. */
    fun normalizeUnit(sentences: List<String>): String = sentences.map { normalize(it, false) }.filter { it.isNotEmpty() }.joinToString(" ")

    /**
     * Phonemes of ONE unit made of [sentences], exactly `vieneu_engine.phonemize` (= vieneu 3.8.1 for that unit): each sentence normalised
     * without the final-punctuation rule, joined with spaces, the unit's final punctuation settled, then the pipeline (normalise with
     * punc_norm + G2P). "" when nothing is left to read. One difference from vieneu: a unit that ends in "?" / "!" keeps that mark (punc_norm
     * would turn a short "Thật sao?" into "Thật sao." and lose the question tone); a unit without a final mark still gets ".".
     */
    fun phonemize(sentences: List<String>): String {
        val text = normalizeUnit(sentences)
        val chunk = puncNorm(text)
        if (chunk.isBlank()) return ""
        val phonemes = g2p(normalize(chunk, true))
        if (phonemes.endsWith(".") && (text.contains('?') || text.contains('!'))) {
            val written = g2p(normalize(text, false)).trimEnd()
            if (written.endsWith("?") || written.endsWith("!")) return phonemes.dropLast(1) + written.last()
        }
        return phonemes
    }

    @Synchronized
    override fun close() {
        if (handle != 0L) SeaG2pNative.nativeClose(handle)
        handle = 0L
    }

    companion object {
        private var shared: SeaG2p? = null

        /** The reader of this process, opened from [library] + [dictionary] the first time: the JNI library stays mapped from its first path, so
         *  "Giọng VieNeu" and "Giọng Supertonic" share one reader (both pin the same files) whichever module's copy came first. */
        @Synchronized
        fun shared(library: File, dictionary: File): SeaG2p = shared ?: SeaG2p(library, dictionary).also { shared = it }
    }
}
