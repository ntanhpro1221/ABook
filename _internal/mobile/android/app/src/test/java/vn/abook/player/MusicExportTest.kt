package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import kotlin.math.PI
import kotlin.math.sin

/** [MusicExport]: bộ trộn theo khối = trộn một lần, chỗ không nhạc y hệt giọng, đếm đoạn thiếu nhạc, dấu vân tay. */
class MusicExportTest {
    @get:Rule
    val temp = TemporaryFolder()

    private val mixText = File("../../../abook/webui/assets/music_mix.json").readText()
    private val params = MusicRender.Params.parse(JSONObject(mixText))
    private val rate = 8000

    init {
        MusicCues.mix = MusicMix.parse(mixText)
    }

    /** "File bài" = PCM 16-bit LE thô một kênh ở đúng [rate]; bộ giải mã chỉ chép (không có file -> lỗi = bài hỏng). */
    private fun cache() = TrackPcmCache(temp.newFolder(), { track, _, _, out -> File(track).inputStream().use { it.copyTo(out) }; 1.0 })

    private fun track(name: String, seconds: Double, freq: Double, amp: Double): File {
        val n = (seconds * rate).toInt()
        val bytes = ByteArray(2 * n)
        for (k in 0 until n) {
            val v = Math.rint(32768 * amp * sin(2 * PI * freq * k / rate)).toInt()
            bytes[2 * k] = v.toByte()
            bytes[2 * k + 1] = (v shr 8).toByte()
        }
        return temp.newFile(name).apply { writeBytes(bytes) }
    }

    private fun voice(seconds: Double) = ShortArray((seconds * rate).toInt()) { k ->
        // giọng 220 Hz, 0,5 s đầu mỗi 4 s gần trần để bộ chặn làm việc thật
        val hot = (k / rate) % 4 == 0 && (k % rate) < rate / 2
        Math.rint(32768 * (if (hot) 0.85 else 0.3) * sin(2 * PI * 220.0 * k / rate)).toInt().toShort()
    }

    /** Ống nhận PCM đã trộn. */
    private class Collect : ListenExport.PcmOutput {
        val out = ArrayList<Short>()
        var finished = false
        override val frames: Long get() = out.size.toLong()
        override fun write(pcm: ShortArray, count: Int) { for (i in 0 until count) out.add(pcm[i]) }
        override fun finish() { finished = true }
        override fun abort() {}
    }

    @Test
    fun mixing_in_blocks_equals_mixing_the_whole_chapter_at_once_and_keeps_the_voice_where_there_is_no_music() {
        val a = track("a.pcm", 6.0, 523.0, 0.6)
        val cues = listOf(MusicCues.Cue(2.0, 14.0, "a", -6.0, tail = true))
        val music = MusicExport.ChapterMusic(cues, mapOf("a" to a))
        val speech = voice(20.0)
        val seconds = speech.size.toDouble() / rate
        val mixer = MusicExport.Mixer(mapOf(7 to music), cache(), params)
        val sink = Collect()
        val output = mixer.wrap(7, sink, rate, 1, seconds)
        var at = 0
        for (size in generateSequence(1) { it * 3 % 4097 + 1 }) {
            if (at >= speech.size) break
            val n = minOf(size, speech.size - at)
            output.write(speech.copyOfRange(at, at + n), n)
            at += n
        }
        output.finish()
        assertEquals(true, sink.finished)
        assertEquals(speech.size, sink.out.size)
        // tham chiếu: dòng thời gian + bus + bộ chặn một lần cho cả chương
        val pcm = TrackPcmCache(temp.newFolder(), { track, _, _, out -> File(track).inputStream().use { it.copyTo(out) }; 1.0 })
            .get(a.absolutePath, rate, 1)
        val timeline = MusicTimeline.build(cues, seconds, mapOf("a" to MusicTimeline.TrackInfo(pcm!!.frames.toDouble() / rate)))
        val bus = MusicRender.renderBus(timeline.map { it.element }, speech.size, rate, 1, { pcm }).data
        val (mixed, _) = MusicRender.guard(DoubleArray(speech.size) { speech[it] / 32768.0 }, bus, rate, 1, params)
        assertArrayEquals(ShortArray(mixed.size) { MusicRender.toInt16(mixed[it]) }, sink.out.toShortArray())
        // trước mốc (0-2 s) và sau khi nhạc mờ hết: từng mẫu y hệt giọng
        for (k in 0 until 2 * rate) assertEquals(speech[k], sink.out[k])
        for (k in 17 * rate until speech.size) assertEquals(speech[k], sink.out[k]) // mốc hết 14 s + mờ 2 s
        assertNotEquals(speech.copyOfRange(4 * rate, 5 * rate).toList(), sink.out.subList(4 * rate, 5 * rate))
        assertEquals(0, mixer.missing(listOf(7)))
    }

    @Test
    fun a_track_that_cannot_be_read_leaves_its_cues_silent_and_is_counted() {
        val good = track("g.pcm", 3.0, 440.0, 0.4)
        val cues = listOf(
            MusicCues.Cue(0.0, 4.0, "gone", -6.0), MusicCues.Cue(4.0, 8.0, "g", -6.0), MusicCues.Cue(8.0, 9.0, "gone", -6.0),
        )
        val music = MusicExport.ChapterMusic(cues, mapOf("g" to good, "gone" to File(temp.root, "không-có.pcm")), dropped = 2)
        val mixer = MusicExport.Mixer(mapOf(1 to music, 2 to MusicExport.ChapterMusic(emptyList(), emptyMap(), dropped = 1)), cache(), params)
        val speech = voice(12.0) // 12 s: mốc cuối kết muộn nhất 9,5 s, mốc 8-9 s còn nguyên
        val sink = Collect()
        mixer.wrap(1, sink, rate, 1, 12.0).apply { write(speech, speech.size); finish() }
        for (k in 0 until 4 * rate) assertEquals(speech[k], sink.out[k]) // đoạn của bài hỏng: không nhạc
        assertEquals(2 + 2, mixer.lost[1])
        assertEquals(false, mixer.has(2))
        assertEquals(4 + 1, mixer.missing(listOf(1, 2)))
    }

    @Test
    fun the_fold_offset_is_measured_on_the_stretch_played_and_raises_only_that_tracks_gain() {
        val a = track("long.pcm", 60.0, 523.0, 0.3)
        val cues = listOf(MusicCues.Cue(2.0, 14.0, "a", -12.0))
        val speech = voice(20.0)
        val asked = ArrayList<Pair<Int, Int>>()
        val fold = MusicExport.FoldOffset { file, _, r, start, end ->
            assertEquals(a, file)
            assertEquals(rate, r)
            asked += start to end
            6.0
        }
        fun mix(cues: List<MusicCues.Cue>, fold: MusicExport.FoldOffset?): List<Short> {
            val sink = Collect()
            MusicExport.Mixer(mapOf(1 to MusicExport.ChapterMusic(cues, mapOf("a" to a))), cache(), params, fold)
                .wrap(1, sink, rate, 1, 20.0).apply { write(speech, speech.size); finish() }
            return sink.out
        }
        val raised = mix(cues, fold)
        assertEquals(1, asked.size) // một lần mỗi bài mỗi chương
        val (start, end) = asked.single()
        assertEquals(0, start)
        assertEquals(true, end in 12..16) // phần đầu bài chương này phát (mốc 12 s + mờ ra), không phải 60 s
        assertEquals(mix(listOf(cues[0].copy(gainDb = -6.0)), null), raised) // = mốc to hơn 6 dB
    }

    @Test
    fun the_played_span_covers_every_element_of_the_track_and_a_loop_covers_the_whole_track() {
        fun element(from: Double, to: Double, position: Double, loop: Boolean = false) =
            MusicRender.Element("t", from, to, position, doubleArrayOf(from), arrayOf(-12.0), loop)
        assertEquals(10 to 46, MusicExport.playedSpan(listOf(element(0.0, 20.0, 10.4), element(30.0, 45.2, 30.0)), 100.0))
        assertEquals(0 to 100, MusicExport.playedSpan(listOf(element(0.0, 20.0, 10.0), element(20.0, 40.0, 0.0, loop = true)), 99.5))
        assertEquals(5 to 60, MusicExport.playedSpan(listOf(element(0.0, Double.POSITIVE_INFINITY, 5.0)), 60.0))
    }

    @Test
    fun the_fingerprint_follows_cues_levels_and_track_files() {
        val a = track("fa.pcm", 1.0, 440.0, 0.4)
        val cues = listOf(MusicCues.Cue(0.0, 4.0, "a", -6.0))
        val base = MusicExport.ChapterMusic(cues, mapOf("a" to a)).fingerprint()
        assertEquals(base, MusicExport.ChapterMusic(cues, mapOf("a" to a)).fingerprint())
        assertNotEquals(base, MusicExport.ChapterMusic(listOf(cues[0].copy(gainDb = -7.0)), mapOf("a" to a)).fingerprint())
        assertNotEquals(base, MusicExport.ChapterMusic(cues, mapOf("a" to a), dropped = 1).fingerprint())
        a.appendBytes(ByteArray(2))
        assertNotEquals(base, MusicExport.ChapterMusic(cues, mapOf("a" to a)).fingerprint())
    }
}
