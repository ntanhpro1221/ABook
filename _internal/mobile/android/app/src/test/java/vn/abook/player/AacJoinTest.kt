package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.nio.ByteBuffer
import kotlin.math.PI
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/**
 * [AacJoin] (đường S của "Xuất M4B"): mỗi chương một bộ mã hoá nối thành luồng đúng từng mẫu, chương vượt đỉnh được mã hoá lại kèm lề
 * một khung mỗi bên, hạ cộng dồn hội tụ (hay bỏ cuộc sau 4 lượt và báo), nhạc trộn đúng chương có mốc.
 *
 * Bộ mã hoá giả không mất mát: khung e của nó chép mẫu vào [FRAME*e - D, FRAME*(e+1) - D) (như độ trễ D của AAC), nhân "độ vọt" riêng của
 * từng bộ mã hoá (mô phỏng mã hoá lại làm đỉnh lệch đi), và ghi số thứ tự bộ mã hoá vào khung để test biết khung nào do bộ nào làm.
 */
class AacJoinTest {
    @get:Rule
    val temp = TemporaryFolder()

    private val mixText = File("../../../abook/webui/assets/music_mix.json").readText()
    private val params = MusicRender.Params.parse(JSONObject(mixText))
    private val rate = 8000
    private val delay = 2048
    private val frame = AacJoin.FRAME

    init {
        MusicCues.mix = MusicMix.parse(mixText)
    }

    private class FakeCodec(override val delay: Int, private val rate: Int, private val overshootDb: (Int) -> Double) : AacJoin.Codec {
        val files = HashMap<File, ShortArray>()
        val muxed = ArrayList<ByteArray>()
        var made = 0

        override fun layout(file: File) = rate to 1

        override fun decode(file: File, rate: Int, channels: Int, stopped: () -> Boolean, fraction: (Double) -> Unit,
                            write: (ShortArray, Int) -> Unit) {
            val pcm = files.getValue(file)
            var at = 0
            while (at < pcm.size) { // khối lẻ như bộ giải mã thật
                val n = min(777, pcm.size - at)
                write(pcm.copyOfRange(at, at + n), n)
                at += n
                fraction(at.toDouble() / pcm.size)
            }
        }

        override fun encoder(rate: Int, channels: Int, unit: (ByteArray) -> Unit): ListenExport.PcmOutput {
            val id = made++
            val gain = Math.pow(10.0, overshootDb(id) / 20)
            return object : ListenExport.PcmOutput {
                val input = ArrayList<Short>()
                var emitted = 0
                override val frames: Long get() = input.size.toLong()

                fun emit(e: Int) {
                    val out = ByteBuffer.allocate(4 + 2 * AacJoin.FRAME).putInt(id)
                    for (i in 0 until AacJoin.FRAME) {
                        val at = AacJoin.FRAME * e - delay + i
                        val v = if (at in input.indices) Math.rint(input[at] * gain).coerceIn(-32768.0, 32767.0).toInt() else 0
                        out.putShort(v.toShort())
                    }
                    unit(out.array())
                }

                override fun write(pcm: ShortArray, count: Int) {
                    for (i in 0 until count) input += pcm[i]
                    while (AacJoin.FRAME * (emitted + 1) - delay + AacJoin.FRAME <= input.size) emit(emitted++)
                }

                override fun finish() {
                    val total = AacJoin.units(input.size.toLong(), delay)
                    while (emitted < total) emit(emitted++)
                }

                override fun abort() {}
            }
        }

        override fun decodeUnits(units: Iterator<ByteArray>, rate: Int, channels: Int, stopped: () -> Boolean,
                                 write: (ShortArray, Int) -> Unit) {
            for (unit in units) {
                val data = ByteBuffer.wrap(unit)
                data.int
                val pcm = ShortArray(AacJoin.FRAME) { data.short }
                write(pcm, pcm.size)
            }
        }

        override fun mux(target: File, rate: Int, channels: Int, units: Iterator<ByteArray>, stopped: () -> Boolean) {
            muxed.clear()
            units.forEach { muxed += it }
            target.writeBytes(byteArrayOf(1))
        }

        fun maker(index: Int): Int = ByteBuffer.wrap(muxed[index]).int

        fun decoded(): ShortArray {
            val out = ArrayList<Short>()
            decodeUnits(muxed.iterator(), rate, 1, { false }) { pcm, count -> for (i in 0 until count) out += pcm[i] }
            return out.toShortArray()
        }
    }

    private fun tone(n: Int, amp: Double, freq: Double = 300.0) = ShortArray(n) { Math.rint(32768 * amp * sin(2 * PI * freq * it / rate)).toInt().toShort() }

    private fun plan(codec: FakeCodec, chapters: List<ShortArray>, music: MusicExport.Mixer? = null, guard: MusicRender.Params? = null) =
        Mp3Export.Plan("Sách", "", chapters.mapIndexed { i, pcm ->
            val file = File(temp.root, "c$i.m4a")
            codec.files[file] = pcm
            Mp3Export.Chapter(i + 1, "Chương ${i + 1}", pcm.size.toDouble() / rate, file, id = i + 1)
        }, chapters.size, chapters.size, null, "", music, guard)

    /** Mẫu đầu từng chương và biên khung của chỗ nối (như [AacJoin]: f_0 = 0, f_k = rint((c_k + D) / FRAME)). */
    private fun grid(chapters: List<ShortArray>): Pair<LongArray, IntArray> {
        val starts = LongArray(chapters.size + 1)
        for (i in chapters.indices) starts[i + 1] = starts[i] + chapters[i].size
        val bounds = IntArray(chapters.size + 1) { if (it == 0) 0 else AacJoin.boundary(starts[it], delay) }
        bounds[chapters.size] = AacJoin.units(starts[chapters.size], delay)
        return starts to bounds
    }

    private fun concat(parts: List<ShortArray>): ShortArray = parts.fold(ShortArray(0)) { a, b -> a + b }

    /** Đỉnh thật của tín hiệu đã giải mã theo vùng khung của từng chương ([FRAME*f_k, FRAME*f_{k+1}) của luồng khung). */
    private fun chapterPeaks(decoded: ShortArray, bounds: IntArray): DoubleArray {
        val meter = TruePeak(params, 1, LongArray(bounds.size - 1) { bounds[it].toLong() * frame })
        meter.feed(decoded)
        return meter.finish()
    }

    private fun encode(codec: FakeCodec, plan: Mp3Export.Plan, phases: MutableList<String>? = null): AacJoin.Encoded =
        AacJoin.encode(plan, File(temp.root, "out.m4b"), codec, { false }, { _, _, _ -> }) { name, chapter, round, over ->
            phases?.add("$name/$chapter/$round/$over")
        }

    @Test
    fun the_overlap_join_is_as_long_as_one_whole_stream_encode_and_sample_exact() {
        // chương lẻ mẫu, một chương ngắn hơn đệm sau Q
        val chapters = listOf(tone(9001, 0.3), tone(700, 0.2, 500.0), tone(12345, 0.25, 440.0), tone(5000, 0.3, 200.0))
        val codec = FakeCodec(delay, rate) { 0.0 }
        val encoded = encode(codec, plan(codec, chapters))
        val voice = concat(chapters)
        val (starts, bounds) = grid(chapters)
        assertEquals(AacJoin.units(voice.size.toLong(), delay), codec.muxed.size)
        assertEquals(chapters.size, codec.made) // một bộ mã hoá mỗi chương, không lượt lại
        val decoded = codec.decoded()
        assertArrayEquals(voice, decoded.copyOfRange(delay, delay + voice.size))
        assertTrue(decoded.copyOfRange(delay + voice.size, decoded.size).all { it.toInt() == 0 })
        // khung [f_k, f_{k+1}) do đúng bộ mã hoá của chương k
        for (k in chapters.indices) for (u in bounds[k] until bounds[k + 1]) assertEquals("khung $u", k, codec.maker(u))
        // mục lục theo biên khung, chương cuối hết ở hết luồng
        assertEquals(0L, encoded.marks[0].startMs)
        for (k in 1 until chapters.size) {
            assertEquals(Math.round((frame.toLong() * bounds[k] - delay) * 1000.0 / rate), encoded.marks[k].startMs)
            assertTrue(Math.abs(frame.toLong() * bounds[k] - delay - starts[k]) <= frame / 2)
        }
        assertEquals(Math.round(voice.size * 1000.0 / rate), encoded.marks.last().endMs)
        assertTrue(encoded.peakOver.isEmpty())
    }

    @Test
    fun an_over_chapter_is_reencoded_with_one_frame_of_margin_each_side_and_only_its_own_region_lowered() {
        val chapters = listOf(tone(9001, 0.3), tone(8200, 0.3, 440.0), tone(7000, 0.3, 200.0))
        chapters[1][4000] = 32000 // đỉnh ~ -0,2 dBTP > -1
        val codec = FakeCodec(delay, rate) { 0.0 }
        val phases = ArrayList<String>()
        val encoded = encode(codec, plan(codec, chapters, guard = params), phases)
        val (_, bounds) = grid(chapters)
        assertEquals(chapters.size + 1, codec.made)
        val spliced = (0 until codec.muxed.size).filter { codec.maker(it) == chapters.size }
        assertEquals((bounds[1] - 1 until bounds[2] + 1).toList(), spliced)
        // giải mã: vùng khung của chương 1 hạ đúng (đỉnh + 1 + 0,1) dB, vùng của chương kề y nguyên (cả khung lề)
        val voice = concat(chapters)
        val decoded = codec.decoded()
        val first = ShortArray(frame * bounds.last())
        System.arraycopy(voice, 0, first, delay, voice.size)
        val peak = chapterPeaks(first, bounds)[1] // lượt đầu đo đúng thế (bộ giả không mất mát)
        assertTrue(peak > 20 * log10(32000 / 32768.0) - 1e-9)
        val expected = voice.copyOf()
        val from = frame * bounds[1] - delay
        val to = frame * bounds[2] - delay
        TruePeak.lower(expected, peak + 1 + AacJoin.MARGIN_DB, to - from, from)
        val got = decoded.copyOfRange(delay, delay + voice.size)
        assertArrayEquals(expected, got)
        assertTrue(chapterPeaks(decoded, bounds).all { it <= -1.0 })
        assertTrue(encoded.peakOver.isEmpty())
        assertEquals(listOf("null/1/0/0", "null/2/0/0", "null/3/0/0", "peaks/0/0/0", "reencode/0/1/1", "peaks/0/1/0"), phases)
    }

    @Test
    fun cumulative_lowering_converges_when_the_overshoot_jumps_to_the_neighbouring_chapter() {
        val chapters = listOf(tone(9001, 0.2), tone(8200, 0.2, 440.0), tone(7000, 0.2, 200.0))
        val (starts, bounds) = grid(chapters)
        chapters[0][3000] = (0.92 * 32768).toInt().toShort()
        // gai dưới trần ở đầu vùng khung của chương 1 và 2 - chỉ vượt khi khung lề của lần mã hoá lại bên cạnh vọt lên
        for (k in 1..2) {
            val at = max(starts[k], frame.toLong() * bounds[k] - delay) + 100 - starts[k]
            chapters[k][at.toInt()] = (0.85 * 32768).toInt().toShort()
        }
        val codec = FakeCodec(delay, rate) { id -> if (id < chapters.size) 0.0 else 1.5 }
        val phases = ArrayList<String>()
        val encoded = encode(codec, plan(codec, chapters, guard = params), phases)
        val rounds = phases.filter { it.startsWith("reencode") }
        assertTrue(rounds.toString(), rounds.size in 2..AacJoin.RETRIES)
        assertEquals("reencode/0/1/1", rounds[0])
        assertTrue(rounds.toString(), rounds[1].endsWith("/2")) // lượt 2: chương 0 còn vượt + chương 1 bị vượt lây
        assertTrue(encoded.peakOver.isEmpty())
        assertTrue(chapterPeaks(codec.decoded(), bounds).all { it <= -1.0 })
    }

    @Test
    fun after_four_rounds_still_over_the_book_is_finished_and_the_chapter_is_reported() {
        val chapters = listOf(tone(9001, 0.2), tone(8200, 0.2, 440.0))
        chapters[1][5000] = 32000
        val codec = FakeCodec(delay, rate) { id -> if (id < 2) 0.0 else 3.0 * (id - 1) } // mỗi lần mã hoá lại vọt thêm
        val phases = ArrayList<String>()
        val encoded = encode(codec, plan(codec, chapters, guard = params), phases)
        assertEquals(AacJoin.RETRIES, phases.count { it.startsWith("reencode") })
        assertEquals(listOf(2), encoded.peakOver.map { it.first })
        assertTrue(encoded.peakOver[0].second > -1.0)
        assertEquals(AacJoin.units(17201, delay), codec.muxed.size)
        assertTrue(File(temp.root, "out.m4b").isFile)
    }

    @Test
    fun cumulative_lowering_only_adds_and_touches_only_the_chapters_over() {
        val lowered = doubleArrayOf(0.0, 1.0, 0.5)
        assertEquals(listOf(1), AacJoin.lowerOver(doubleArrayOf(-3.0, -0.5, -1.0), -1.0, lowered))
        assertArrayEquals(doubleArrayOf(0.0, 1.6, 0.5), lowered, 1e-9)
        assertEquals(emptyList<Int>(), AacJoin.lowerOver(doubleArrayOf(-3.0, -1.0, Double.NEGATIVE_INFINITY), -1.0, lowered))
    }

    @Test
    fun music_is_mixed_into_its_chapter_only_at_its_cues() {
        val chapters = listOf(tone(16000, 0.3), tone(24000, 0.3, 440.0), tone(8000, 0.3, 200.0))
        val trackFile = temp.newFile("a.pcm").apply {
            val n = 3 * rate
            val bytes = ByteArray(2 * n)
            for (k in 0 until n) {
                val v = Math.rint(32768 * 0.5 * sin(2 * PI * 523.0 * k / rate)).toInt()
                bytes[2 * k] = v.toByte()
                bytes[2 * k + 1] = (v shr 8).toByte()
            }
            writeBytes(bytes)
        }
        val cues = listOf(MusicCues.Cue(0.5, 2.5, "a", -6.0))
        fun mixer() = MusicExport.Mixer(mapOf(2 to MusicExport.ChapterMusic(cues, mapOf("a" to trackFile))),
            TrackPcmCache(temp.newFolder(), { track, _, _, out -> File(track).inputStream().use { it.copyTo(out) } }), params)
        val codec = FakeCodec(delay, rate) { 0.0 }
        val phases = ArrayList<String>()
        encode(codec, plan(codec, chapters, music = mixer()), phases)
        // tham chiếu: chương 2 qua bộ trộn một lần, chương khác y nguyên
        val mixed = ArrayList<Short>()
        val sink = object : ListenExport.PcmOutput {
            override val frames: Long get() = mixed.size.toLong()
            override fun write(pcm: ShortArray, count: Int) { for (i in 0 until count) mixed += pcm[i] }
            override fun finish() {}
            override fun abort() {}
        }
        mixer().wrap(2, sink, rate, 1, null).apply { write(chapters[1], chapters[1].size); finish() }
        val expected = concat(listOf(chapters[0], mixed.toShortArray(), chapters[2]))
        val voice = concat(chapters)
        val decoded = codec.decoded()
        assertArrayEquals(expected, decoded.copyOfRange(delay, delay + expected.size))
        // có nhạc thật: trong mốc khác giọng, trước mốc 0,5 s y nguyên
        val start = chapters[0].size
        assertArrayEquals(voice.copyOfRange(start, start + rate / 2 - 64), expected.copyOfRange(start, start + rate / 2 - 64))
        assertTrue((start + rate until start + 2 * rate).any { expected[it] != voice[it] })
        assertEquals(listOf("null/1/0/0", "music/2/0/0", "null/3/0/0"), phases)
    }
}
