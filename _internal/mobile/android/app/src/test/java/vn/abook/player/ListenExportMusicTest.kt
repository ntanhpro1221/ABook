package vn.abook.player

import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import vn.abook.player.readaloud.Paragraphs
import java.io.File
import java.nio.file.Files
import kotlin.math.PI
import kotlin.math.sin

/**
 * "Xuất sách nói" kèm nhạc nền trên điện thoại (ListenExport.Run với [ListenExport.Music], đường L của K2): chương có nhạc thành `<mã>.music.m4a` riêng, trộn đúng mốc
 * trên giọng ghép lại, đo đỉnh sau mã hoá và hạ cộng dồn chỉ chương ấy; dấu vân tay đổi theo nhạc; chương không nhạc y như trước. Bộ mã hoá và bộ đo đỉnh là bản giả.
 */
class ListenExportMusicTest {
    private lateinit var root: File
    private lateinit var work: File
    private lateinit var clips: File
    private val mixText = File("../../../abook/webui/assets/music_mix.json").readText()
    private val params = MusicRender.Params.parse(JSONObject(mixText))
    private val rate = 24000
    private val reading = ListenExport.Reading("edge:vi-VN-HoaiMyNeural", null, emptyMap())

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-listen-music").toFile()
        work = Files.createTempDirectory("abook-listen-music-work").toFile()
        clips = Files.createTempDirectory("abook-listen-music-clips").toFile()
        MusicCues.mix = MusicMix.parse(mixText)
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
        work.deleteRecursively()
        clips.deleteRecursively()
    }

    // ---- bản giả ------------------------------------------------------------------------------------------------------

    /** Chương ~7 s: mỗi chữ 100 mẫu giọng ở 24 kHz (giọng là một sóng sin để bộ chặn và việc hạ mức có việc thật). */
    private fun chapter(id: Int) = ListenExport.Chapter(id, "Chương $id", Paragraphs.split(List(2) { "Lời kể đoạn ${it + 1} của chương $id. ".repeat(30) }.joinToString("\n\n")))

    private val synth = ListenExport.Synth { text -> File(clips, "${text.hashCode()}.clip").also { it.writeBytes(ByteArray(text.length)) } }

    private val decoder = object : ListenExport.Decoder {
        override fun rate(file: File) = rate
        override fun decode(file: File, rate: Int, stopped: () -> Boolean, write: (ShortArray, Int) -> Unit) {
            val total = file.length().toInt() * 100
            var at = 0
            while (at < total) {
                val take = minOf(total - at, 700)
                write(ShortArray(take) { Math.rint(9000 * sin(2 * PI * 200.0 * (at + it) / rate)).toInt().toShort() }, take)
                at += take
            }
        }
    }

    /** Bộ mã hoá giả: giữ PCM đã nhận. */
    private class Sink(val file: File) : ListenExport.PcmOutput {
        val pcm = ArrayList<Short>()
        override val frames: Long get() = pcm.size.toLong()
        override fun write(pcm: ShortArray, count: Int) {
            for (i in 0 until count) this.pcm += pcm[i]
        }

        override fun finish() = file.writeBytes(ByteArray(8))
        override fun abort() {}
    }

    private fun track(): File = File(root, "a.pcm").apply {
        val n = 6 * rate
        val bytes = ByteArray(2 * n)
        for (k in 0 until n) {
            val v = Math.rint(32768 * 0.5 * sin(2 * PI * 523.0 * k / rate)).toInt()
            bytes[2 * k] = v.toByte()
            bytes[2 * k + 1] = (v shr 8).toByte()
        }
        writeBytes(bytes)
    }

    private fun chapterMusic(gainDb: Double = -6.0, dropped: Int = 0) =
        MusicExport.ChapterMusic(listOf(MusicCues.Cue(1.0, 5.0, "a", gainDb)), mapOf("a" to track()), dropped)

    private fun mixer(music: Map<Int, MusicExport.ChapterMusic>) =
        MusicExport.Mixer(music, TrackPcmCache(Files.createTempDirectory(root.toPath(), "pcm").toFile(), { name, _, _, out ->
            File(name).inputStream().use { it.copyTo(out) }
        }), params)

    private fun run(chapters: List<ListenExport.Chapter>, music: ListenExport.Music?, sinks: MutableList<Sink>, events: MutableList<ListenExport.Progress> = ArrayList()) =
        ListenExport.Run(chapters, reading, work, synth, decoder, { file, _ -> Sink(file).also { sinks += it } }, { events += it }, { false },
            sleep = {}, music = music)

    /** Giọng cả chương như bộ giải mã giả ghép (không có dòng ngăn cảnh nên không có quãng lặng). */
    private fun voiceOf(chapter: ListenExport.Chapter): ShortArray {
        val out = ArrayList<Short>()
        for (paragraph in chapter.speakable) decoder.decode(synth.clip(paragraph.text)!!, rate, { false }) { pcm, count -> for (i in 0 until count) out += pcm[i] }
        return out.toShortArray()
    }

    /** Tham chiếu: giọng qua bộ trộn MỘT lần (cả chương, biết độ dài), rồi hạ `db`. */
    private fun mixedOf(voice: ShortArray, music: MusicExport.ChapterMusic, db: Double = 0.0): ShortArray {
        val sink = Sink(File(root, "ref"))
        mixer(mapOf(1 to music)).wrap(1, sink, rate, 1, voice.size.toDouble() / rate).apply { write(voice, voice.size); finish() }
        return sink.pcm.toShortArray().also { if (db != 0.0) TruePeak.lower(it, db) }
    }

    // ---- test ---------------------------------------------------------------------------------------------------------

    @Test
    fun aChapterWithMusicIsMixedAtItsCuesIntoItsOwnFileAndAChapterWithoutStaysAsBefore() {
        val chapters = listOf(chapter(1), chapter(2))
        val music = chapterMusic()
        val sinks = ArrayList<Sink>()
        val events = ArrayList<ListenExport.Progress>()
        val stamps = run(chapters, ListenExport.Music(mixer(mapOf(1 to music)), params) { -3.0 }, sinks, events).build()
        assertEquals(2, sinks.size)
        val voice = voiceOf(chapters[0])
        assertArrayEquals(mixedOf(voice, music), sinks[0].pcm.toShortArray())
        assertTrue("có nhạc thật trong mốc", (2 * rate until 4 * rate).any { sinks[0].pcm[it] != voice[it] })
        assertArrayEquals("chương không nhạc: y giọng", voiceOf(chapters[1]), sinks[1].pcm.toShortArray())
        // file và dấu riêng; giọng tạm đã dọn; chương không nhạc giữ tên cũ và dấu vân tay cũ
        assertTrue(File(work, "1.music.m4a").isFile && File(work, "1.music.done").isFile)
        assertFalse(File(work, "1.m4a").exists() || File(work, "1.voice.pcm").exists())
        assertTrue(File(work, "2.m4a").isFile && File(work, "2.done").isFile)
        assertTrue(stamps[0].mixed)
        assertFalse(stamps[1].mixed)
        assertEquals(ListenExport.fingerprint(chapters[0], reading, music), stamps[0].fingerprint)
        assertEquals(ListenExport.fingerprint(chapters[0], reading), stamps[0].voice)
        assertEquals(ListenExport.fingerprint(chapters[1], reading), stamps[1].fingerprint)
        assertEquals(voice.size.toDouble() / rate, stamps[0].seconds, 1e-9)
        assertEquals(0.0, stamps[0].loweredDb, 0.0)
        assertEquals(-3.0, stamps[0].peakDbtp!!, 0.0)
        assertEquals(listOf("voice", "music", "peaks"), events.filter { it.chapter == 1 }.map { it.phase }.distinct())
        assertEquals("chương không nhạc của lượt kèm nhạc cũng kiểm đỉnh", listOf("voice", "peaks"), events.filter { it.chapter == 2 }.map { it.phase }.distinct())
        // bản cuối dùng đúng file từng chương
        val plan = ListenExport.exportPlan(JSONObject().put("title", "S"), "s", chapters, stamps, work, null, "")
        assertEquals(listOf("1.music.m4a", "2.m4a"), plan.chapters.map { it.file.name })
    }

    @Test
    fun anOverChapterIsLoweredCumulativelyAndOnlyItIsEncodedAgain() {
        val chapters = listOf(chapter(1), chapter(2))
        val music = chapterMusic()
        val peaks = ArrayDeque(listOf(-0.2, -0.5, -1.2))
        val sinks = ArrayList<Sink>()
        val events = ArrayList<ListenExport.Progress>()
        val stamps = run(chapters, ListenExport.Music(mixer(mapOf(1 to music)), params) { file -> if (file.name.startsWith("1.")) peaks.removeFirst() else -3.0 },
            sinks, events).build()
        assertEquals("3 lần mã hoá chương 1 + 1 lần chương 2", 4, sinks.size)
        val lowered = (-0.2 + 1 + AacJoin.MARGIN_DB) + (-0.5 + 1 + AacJoin.MARGIN_DB)
        assertEquals(lowered, stamps[0].loweredDb, 1e-9)
        assertEquals(-1.2, stamps[0].peakDbtp!!, 0.0)
        assertArrayEquals(mixedOf(voiceOf(chapters[0]), music, lowered), sinks[2].pcm.toShortArray())
        val again = events.filter { it.phase == "reencode" }
        assertEquals(listOf(1, 2), again.map { it.peakRound })
        assertTrue(again.all { it.peakOver == 1 && it.chapter == 1 })
        assertEquals(1.0, JSONObject(File(work, "1.music.done").readText()).getDouble("loweredDb") / lowered, 1e-9)
    }

    @Test
    fun afterTwoRetriesStillOverTheChapterIsKeptAndItsPeakRecorded() {
        val chapters = listOf(chapter(1))
        val sinks = ArrayList<Sink>()
        val stamps = run(chapters, ListenExport.Music(mixer(mapOf(1 to chapterMusic())), params) { 0.0 }, sinks).build()
        assertEquals(1 + ListenExport.Run.PEAK_RETRIES, sinks.size)
        assertEquals(0.0, stamps[0].peakDbtp!!, 0.0)
        assertEquals(ListenExport.Run.PEAK_RETRIES * (1 + AacJoin.MARGIN_DB), stamps[0].loweredDb, 1e-9)
        assertTrue(File(work, "1.music.m4a").isFile)
        assertEquals(0.0, JSONObject(File(work, "1.music.done").readText()).getDouble("peakDbtp"), 0.0)
    }

    @Test
    fun inARunWithMusicAChapterWithoutMusicIsCheckedTooAndRedoneFromTheClipsWhenOver() {
        val chapters = listOf(chapter(1), chapter(2))
        val peaks = ArrayDeque(listOf(-0.4, -1.5))
        val sinks = ArrayList<Sink>()
        val events = ArrayList<ListenExport.Progress>()
        val music = ListenExport.Music(mixer(mapOf(1 to chapterMusic())), params) { file -> if (file.name.startsWith("2.")) peaks.removeFirst() else -3.0 }
        val stamps = run(chapters, music, sinks, events).build()
        assertEquals(3, sinks.size)
        val db = -0.4 + 1 + AacJoin.MARGIN_DB
        assertArrayEquals(voiceOf(chapters[1]).also { TruePeak.lower(it, db) }, sinks[2].pcm.toShortArray())
        assertFalse(stamps[1].mixed)
        assertEquals(db, stamps[1].loweredDb, 1e-9)
        assertEquals(-1.5, stamps[1].peakDbtp!!, 0.0)
        assertEquals("ghép lại không tính hai lần vào tiến độ", 100, events.last().percent)
        assertTrue(events.all { it.percent <= 100 })
        // dấu vân tay không đổi: lượt không nhạc sau dùng lại chương đã hạ, không đo lại
        assertEquals(db, ListenExport.ready(work, chapters[1], reading)!!.loweredDb, 1e-9)
        val again = ArrayList<Sink>()
        run(listOf(chapters[1]), null, again).build()
        assertTrue(again.isEmpty())
    }

    @Test
    fun withoutMusicNothingIsMeasured() {
        val sinks = ArrayList<Sink>()
        val stamps = run(listOf(chapter(2)), null, sinks).build()
        assertEquals(1, sinks.size)
        assertNull(stamps[0].peakDbtp)
        assertFalse(JSONObject(File(work, "2.done").readText()).has("loweredDb"))
    }

    @Test
    fun aMixedChapterFromBeforeIsReusedWithItsMissingMusicCount() {
        val chapters = listOf(chapter(1))
        val music = chapterMusic(dropped = 2)
        val first = mixer(mapOf(1 to music))
        run(chapters, ListenExport.Music(first, params) { -3.0 }, ArrayList()).build()
        assertEquals(2, first.missing(listOf(1)))
        val again = mixer(mapOf(1 to music))
        val sinks = ArrayList<Sink>()
        val stamps = run(chapters, ListenExport.Music(again, params) { error("không đo lại") }, sinks).build()
        assertTrue(sinks.isEmpty())
        assertEquals(2, stamps[0].musicMissing)
        assertEquals(2, again.lost[1])
        assertEquals(2, again.missing(listOf(1)))
    }

    @Test
    fun changingTheMusicRedoesOnlyThatChapterAndTheDialogCountsTheParagraphsToReadAgain() {
        val chapters = listOf(chapter(1), chapter(2))
        val music = chapterMusic(-6.0)
        run(chapters, ListenExport.Music(mixer(mapOf(1 to music)), params) { -3.0 }, ArrayList()).build()
        val same = mapOf(1 to music)
        val louder = mapOf(1 to chapterMusic(-3.0))
        assertNotEquals(ListenExport.fingerprint(chapters[0], reading, music), ListenExport.fingerprint(chapters[0], reading, louder[1]))
        val uncached: (String) -> Long? = { null }
        val kept = ListenExport.plan(chapters, reading, work, null, music = { MusicExport.audible(same, it) }, cachedMs = uncached)
        assertEquals(2, kept.readyChapters)
        assertEquals(0, kept.rereads)
        val changed = ListenExport.plan(chapters, reading, work, null, music = { MusicExport.audible(louder, it) }, cachedMs = uncached)
        assertEquals(1, changed.readyChapters)
        assertEquals("cả hai đoạn của chương 1 đã bị đẩy khỏi bộ đệm", 2, changed.rereads)
        assertEquals(0, ListenExport.plan(chapters, reading, work, null, music = { MusicExport.audible(louder, it) }, cachedMs = { 1000L }).rereads)
        // tắt nhạc: chương 1 chưa từng có bản không nhạc - giọng đã đọc, phải ghép lại
        val off = ListenExport.plan(chapters, reading, work, null, cachedMs = uncached)
        assertEquals(1, off.readyChapters)
        assertEquals(2, off.rereads)
        // chương chưa từng làm không tính là đọc lại (đó là việc đọc thường)
        assertEquals(0, ListenExport.plan(listOf(chapter(3)), reading, work, null, cachedMs = uncached).rereads)
        assertEquals(2, changed.toJson().getInt("rereads"))
        // chương làm lại theo nhạc mới: chỉ chương 1, lần này mức -3 dB
        val sinks = ArrayList<Sink>()
        run(chapters, ListenExport.Music(mixer(louder), params) { -3.0 }, sinks).build()
        assertEquals(1, sinks.size)
        assertNull(ListenExport.ready(work, chapters[0], reading, music))
    }

    @Test
    fun theSpaceForMusicAddsTheLongestChapterVoiceAndTheTrackCache() {
        val chapters = listOf(chapter(1), chapter(2))
        val voice = ListenExport.voiceBytes(chapters)
        assertTrue(voice > 0)
        assertEquals(ListenExport.bytesNeeded(100, 200) + voice, ListenExport.bytesNeeded(100, 200, voice))
        assertEquals(voice, ListenExport.plan(chapters, reading, work, null, extra = voice).bytes - ListenExport.plan(chapters, reading, work, null).bytes)
    }
}
