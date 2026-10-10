package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import vn.abook.player.readaloud.Paragraphs
import vn.abook.player.readaloud.VoiceException
import vn.abook.player.readaloud.Wav
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files

/**
 * "Xuất sách nói" cho sách Nghe ngay trên điện thoại (ListenExport.kt): chương của cuốn, dấu vân tay + làm tiếp từ chương đã xong, nhường người đang nghe, thử lại lỗi
 * thoáng qua, quãng lặng ở dòng ngăn cảnh, ước trước khi bấm, mốc chương của file cuối. Giọng, bộ giải mã clip và bộ mã hoá AAC là bản giả (MediaCodec chỉ chạy trên máy
 * Android: ListenExportOnDeviceTest).
 */
class ListenExportTest {
    private lateinit var root: File
    private lateinit var work: File
    private lateinit var clips: File

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-listen").toFile()
        work = Files.createTempDirectory("abook-listen-work").toFile()
        clips = Files.createTempDirectory("abook-listen-clips").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
        work.deleteRecursively()
        clips.deleteRecursively()
    }

    // ---- bản giả ------------------------------------------------------------------------------------------------------

    private val reading = ListenExport.Reading("edge:vi-VN-HoaiMyNeural", null, emptyMap())

    /** Mỗi chữ của đoạn là 100 mẫu PCM ở 24 kHz: độ dài chương tính được từ chữ. */
    private fun samplesOf(text: String) = text.length * 100

    private fun chapter(id: Int, vararg blocks: String) = ListenExport.Chapter(id, "Chương $id", Paragraphs.split(blocks.joinToString("\n\n")))

    private inner class Voice(val rate: Int = 24000) {
        val asked = ArrayList<String>()
        var failure: ((String, Int) -> VoiceException?)? = null
        private val attempts = HashMap<String, Int>()
        val synth = ListenExport.Synth { text ->
            asked += text
            val attempt = (attempts[text] ?: 0) + 1
            attempts[text] = attempt
            failure?.invoke(text, attempt)?.let { throw it }
            File(clips, "${text.hashCode()}.clip").also { it.writeBytes(ByteArray(text.length)) }
        }
        val decoder = object : ListenExport.Decoder {
            override fun rate(file: File) = rate
            override fun decode(file: File, rate: Int, stopped: () -> Boolean, write: (ShortArray, Int) -> Unit) {
                val total = file.length().toInt() * 100
                var left = total
                while (left > 0) {
                    if (stopped()) throw Mp3Export.Stopped()
                    val take = minOf(left, 700)
                    write(ShortArray(take) { 7 }, take)
                    left -= take
                }
            }
        }
    }

    private class Sink(val file: File, val rate: Int) : ListenExport.PcmOutput {
        override var frames = 0L
        override fun write(pcm: ShortArray, count: Int) {
            frames += count
        }

        override fun finish() = file.writeBytes(ByteArray(8))
        override fun abort() {}
    }

    private fun run(
        chapters: List<ListenExport.Chapter>,
        voice: Voice,
        reading: ListenExport.Reading = this.reading,
        events: MutableList<ListenExport.Progress> = ArrayList(),
        sinks: MutableList<Sink> = ArrayList(),
        stopped: () -> Boolean = { false },
        live: () -> Boolean = { false },
        sleeps: MutableList<Long> = ArrayList(),
    ) = ListenExport.Run(
        chapters, reading, work, voice.synth, voice.decoder, { file, rate -> Sink(file, rate).also { sinks += it } }, { events += it }, stopped, live,
        sleep = { sleeps += it },
    )

    // ---- chương của cuốn ---------------------------------------------------------------------------------------------

    private fun book(chapters: List<JSONObject>) {
        val dir = File(root, "books/sach").apply { mkdirs() }
        File(dir, "book.json").writeText(
            JSONObject().put("format", "abook-book/1").put("title", "Sách chữ").put("author", "Tác giả").put("chaptersTotal", chapters.size)
                .put("chapters", JSONArray(chapters)).toString(),
        )
    }

    private fun item(id: Int, fullTitle: String?, title: String?, text: Boolean = true) = JSONObject().put("id", id).put("index", id).apply {
        fullTitle?.let { put("fullTitle", it) }
        title?.let { put("title", it) }
        if (text) put("text", "texts/$id.txt")
    }

    @Test
    fun chaptersAreTheTextOnesWithSomethingToSayNamedAsTheListenerSeesThem() {
        book(listOf(item(1, "Chương 1 · Mở đầu", "Mở đầu"), item(2, null, "Về nhà"), item(3, null, null), item(4, "Chỉ dấu", null), item(5, "Âm thanh", null, text = false)))
        val parsed = mapOf(
            1 to ("Mở đầu" to Paragraphs.split("Một.\n\nHai.")),
            2 to ("Về nhà" to Paragraphs.split("Ba.")),
            3 to ("" to Paragraphs.split("Bốn.")),
            4 to ("" to Paragraphs.split("***\n\n...")), // chỉ dấu ngăn cảnh: không có gì để đọc
        )
        val asked = ArrayList<List<Int>>()
        val found = ListenExport.chapters("sach") { _, ids -> asked += ids; parsed }
        assertEquals(listOf(listOf(1, 2, 3, 4)), asked) // chương audio (không có "text") không hỏi
        assertEquals(listOf(1, 2, 3), found.map { it.id })
        assertEquals(listOf("Chương 1 · Mở đầu", "Về nhà", "Chương 3"), found.map { it.title })
    }

    @Test
    fun aBookThatIsNotOnThePhoneIsRefusedInWords() {
        try {
            ListenExport.chapters("khong-co") { _, _ -> emptyMap() }
            fail("phải từ chối")
        } catch (refused: Mp3Export.Refused) {
            assertEquals("Không tìm thấy sách này trên điện thoại", refused.message)
        }
    }

    // ---- ghép chương ---------------------------------------------------------------------------------------------------

    @Test
    fun aChapterIsOneFilePerChapterWithTheSceneBreakSilenceBetweenParagraphs() {
        val chapters = listOf(chapter(1, "Câu một.", "***", "Câu hai."), chapter(2, "Chương hai."))
        val voice = Voice()
        val sinks = ArrayList<Sink>()
        val stamps = run(chapters, voice, sinks = sinks).build()
        // "***" là dòng ngăn cảnh có chữ đọc được ở cả hai phía: 1,5 giây lặng ở 24 kHz; chính nó không gửi cho giọng.
        assertEquals(listOf("Câu một.", "Câu hai.", "Chương hai."), voice.asked)
        assertEquals(samplesOf("Câu một.") + 36000L + samplesOf("Câu hai."), sinks[0].frames)
        assertEquals(samplesOf("Chương hai.").toLong(), sinks[1].frames)
        assertEquals(24000, stamps[0].rate)
        assertEquals(sinks[0].frames / 24000.0, stamps[0].seconds, 1e-9)
        for (chapter in chapters) {
            assertTrue(ListenExport.audioFile(work, chapter).isFile)
            assertFalse(File(work, "${chapter.id}.m4a.part").exists())
            assertNotNull(ListenExport.ready(work, chapter, reading))
        }
    }

    @Test
    fun leadingAndTrailingSceneBreaksMakeNoSilence() {
        val chapters = listOf(chapter(1, "***", "Câu một.", "***"))
        val sinks = ArrayList<Sink>()
        run(chapters, Voice(), sinks = sinks).build()
        assertEquals(samplesOf("Câu một.").toLong(), sinks[0].frames)
    }

    @Test
    fun theRateOfTheBookIsTheRateOfTheFirstClipAndAllChaptersShareIt() {
        val sinks = ArrayList<Sink>()
        run(listOf(chapter(1, "Một."), chapter(2, "Hai.")), Voice(rate = 22050), sinks = sinks).build()
        assertEquals(listOf(22050, 22050), sinks.map { it.rate })
    }

    @Test
    fun theProgressCountsCharactersAndEndsAtOneHundredWithTheChapterNamed() {
        val events = ArrayList<ListenExport.Progress>()
        run(listOf(chapter(1, "Một."), chapter(2, "Hai ba.")), Voice(), events = events).build()
        assertEquals(0, events.first().percent)
        val last = events.last()
        assertEquals(100, last.percent)
        assertEquals("voice", last.phase)
        assertEquals(2, last.chapter)
        assertEquals(2, last.chapters)
        assertEquals("Chương 2", last.title)
        assertTrue(events.map { it.percent }.zipWithNext().all { (a, b) -> a <= b })
    }

    // ---- làm tiếp -----------------------------------------------------------------------------------------------------

    @Test
    fun anExportThatWasStoppedPicksUpAtTheFirstChapterWithoutAGoodStamp() {
        val chapters = listOf(chapter(1, "Một.", "Hai."), chapter(2, "Ba.", "Bốn."), chapter(3, "Năm."))
        val first = Voice()
        var asks = 0
        try {
            // Dừng ở đoạn thứ ba (giữa chương 2).
            run(chapters, first, stopped = { first.asked.size >= 3 }).build()
            fail("phải dừng")
        } catch (stopped: Mp3Export.Stopped) {
            asks = first.asked.size
        }
        assertTrue(asks >= 3)
        assertNotNull(ListenExport.ready(work, chapters[0], reading))
        assertNull("chương dở không có dấu", ListenExport.ready(work, chapters[1], reading))
        assertFalse("không để lại file dở", File(work, "2.m4a.part").exists())
        assertFalse(File(work, "2.m4a").exists())

        val second = Voice()
        val events = ArrayList<ListenExport.Progress>()
        val stamps = run(chapters, second, events = events).build()
        assertEquals("chương 1 đã xong: không đọc lại", listOf("Ba.", "Bốn.", "Năm."), second.asked)
        assertEquals(3, stamps.size)
        assertEquals(100, events.last().percent)
    }

    @Test
    fun aDifferentVoiceReadingOrTextDoesNotReuseTheOldChapter() {
        val chapters = listOf(chapter(1, "Một."))
        run(chapters, Voice()).build()
        assertNotNull(ListenExport.ready(work, chapters[0], reading))
        assertNull(ListenExport.ready(work, chapters[0], ListenExport.Reading("vieneu:turbo/Trúc Ly", null, emptyMap())))
        assertNull(ListenExport.ready(work, chapters[0], ListenExport.Reading(reading.voice, "ja", emptyMap())))
        assertNull(ListenExport.ready(work, chapters[0], ListenExport.Reading(reading.voice, null, mapOf("Tokyo" to "Tô-ky-ô"))))
        assertNull(ListenExport.ready(work, chapter(1, "Một. Đã sửa."), reading))
        assertNotNull(ListenExport.ready(work, chapter(1, "Một."), ListenExport.Reading(reading.voice, null, emptyMap())))
    }

    @Test
    fun aChapterWithAMissingFileOrBrokenStampIsNotReady() {
        val chapters = listOf(chapter(1, "Một."), chapter(2, "Hai."))
        run(chapters, Voice()).build()
        ListenExport.audioFile(work, chapters[0]).delete()
        File(work, "2.done").writeText("không phải json")
        assertNull(ListenExport.ready(work, chapters[0], reading))
        assertNull(ListenExport.ready(work, chapters[1], reading))
    }

    @Test
    fun chaptersOfAnotherRateAreRedoneSoTheWholeBookJoinsAtOneRate() {
        val chapters = listOf(chapter(1, "Một."), chapter(2, "Hai."))
        run(chapters, Voice(rate = 24000)).build()
        // Chương 2 làm lại ở lần khác với tần số khác (đổi máy đọc): chỉ chương cùng tần số với chương đầu còn dùng được.
        File(work, "2.done").writeText(JSONObject(File(work, "2.done").readText()).put("rate", 16000).toString())
        val stamps = ListenExport.readyStamps(work, chapters, reading)
        assertEquals(24000, stamps[0]?.rate)
        assertNull(stamps[1])
    }

    // ---- nhường người nghe, thử lại, lỗi ------------------------------------------------------------------------------------

    @Test
    fun theListenerComesFirstTheExportWaitsParagraphByParagraph() {
        var polls = 0
        val voice = Voice()
        val events = ArrayList<ListenExport.Progress>()
        val sleeps = ArrayList<Long>()
        // Người nghe đang đọc dở trong 5 lần hỏi đầu, rồi rảnh.
        run(listOf(chapter(1, "Một.")), voice, events = events, sleeps = sleeps, live = { ++polls <= 5 }).build()
        assertEquals(5, sleeps.count { it == ListenExport.Run.LIVE_POLL_MS })
        assertEquals(1, events.count { it.waiting == "listening" })
        assertNull("hết nhường thì báo lại bình thường", events.last().waiting)
        assertEquals(listOf("Một."), voice.asked)
    }

    @Test
    fun waitingForTheListenerCanBeStopped() {
        val voice = Voice()
        var stop = false
        try {
            run(listOf(chapter(1, "Một.")), voice, live = { true }, stopped = { stop.also { stop = true } }).build()
            fail("phải dừng")
        } catch (stopped: Mp3Export.Stopped) {
            assertTrue(voice.asked.isEmpty())
        }
    }

    @Test
    fun aPassingOnlineFailureIsRetriedThenTheParagraphIsRead() {
        val voice = Voice()
        voice.failure = { _, attempt -> if (attempt <= 2) VoiceException("mất mạng", offline = true) else null }
        val sleeps = ArrayList<Long>()
        run(listOf(chapter(1, "Một.")), voice, sleeps = sleeps).build()
        assertEquals(listOf(1000L, 2000L), sleeps)
        assertEquals(3, voice.asked.size)
        assertNotNull(ListenExport.ready(work, chapter(1, "Một."), reading))
    }

    @Test
    fun aRealFailureStopsWithWordsKeepsTheChaptersDoneAndNamesTheChapter() {
        val chapters = listOf(chapter(1, "Một."), chapter(2, "Hai."))
        val voice = Voice()
        voice.failure = { text, _ -> if (text == "Hai.") VoiceException("Khóa không dùng được.", reason = "auth") else null }
        try {
            run(chapters, voice).build()
            fail("phải dừng")
        } catch (refused: Mp3Export.Refused) {
            assertTrue(refused.message!!.contains("“Chương 2”"))
            assertTrue(refused.message!!.contains("Khóa không dùng được."))
            assertTrue(refused.message!!.contains("xuất lại để làm tiếp"))
        }
        assertNotNull(ListenExport.ready(work, chapters[0], reading))
        assertNull(ListenExport.ready(work, chapters[1], reading))
        assertFalse(File(work, "2.m4a.part").exists())
    }

    @Test
    fun aRetryRunsOutAfterTwoRetries() {
        val voice = Voice()
        voice.failure = { _, _ -> VoiceException("dịch vụ bận", reason = "service") }
        try {
            run(listOf(chapter(1, "Một.")), voice, sleeps = ArrayList()).build()
            fail("phải dừng")
        } catch (refused: Mp3Export.Refused) {
            assertEquals(1 + ListenExport.RETRIES, voice.asked.size)
        }
    }

    @Test
    fun aParagraphThePhoneCannotSayIsSkippedButAChapterOfNothingIsAnError() {
        val voice = Voice()
        voice.failure = { text, _ -> if (text == "Hai.") VoiceException("không có gì để đọc", reason = "empty") else null }
        val sinks = ArrayList<Sink>()
        run(listOf(chapter(1, "Một.", "Hai.", "Ba.")), voice, sinks = sinks).build()
        assertEquals((samplesOf("Một.") + samplesOf("Ba.")).toLong(), sinks[0].frames)

        val silent = Voice()
        silent.failure = { _, _ -> VoiceException("không có gì để đọc", reason = "empty") }
        try {
            run(listOf(chapter(2, "Bốn.")), silent).build()
            fail("chương không đọc được gì phải báo lỗi")
        } catch (refused: Mp3Export.Refused) {
            assertEquals("Giọng đọc không đọc được gì ở “Chương 2”.", refused.message)
        }
    }

    @Test
    fun newReadingsFeedTheSpeedMeterOnlyForRealReads() {
        val voice = Voice()
        val timed = ArrayList<Int>()
        var now = 0L
        val chapters = listOf(chapter(1, "Một.", "Hai."))
        // Đồng hồ nhảy 200 ms mỗi lần hỏi: mọi đoạn tính là đọc mới (chậm hơn 50 ms).
        ListenExport.Run(chapters, reading, work, voice.synth, voice.decoder, { file, rate -> Sink(file, rate) }, {}, { false }, timed = { chars, _ -> timed += chars },
            clock = { now += 100; now }).build()
        assertEquals(chapters[0].speakable.map { it.text.length }, timed)
    }

    // ---- ước trước khi bấm --------------------------------------------------------------------------------------------

    @Test
    fun thePlanCountsTheChaptersTheListeningTimeAndWhatIsAlreadyDone() {
        val chapters = listOf(chapter(1, "a".repeat(140)), chapter(2, "b".repeat(280)))
        val fresh = ListenExport.plan(chapters, reading, work, 0.05)
        assertEquals(2, fresh.chapters)
        assertEquals(420L, fresh.chars)
        assertEquals(30L, fresh.audioSeconds) // 420 chữ / 14 chữ mỗi giây
        assertEquals(21L, fresh.secondsEstimate) // 420 chữ x 0,05 giây
        assertEquals(0, fresh.readyChapters)
        assertNull(ListenExport.plan(chapters, reading, work, null).secondsEstimate)

        run(listOf(chapters[0]), Voice()).build()
        val resumed = ListenExport.plan(chapters, reading, work, 0.05)
        assertEquals(1, resumed.readyChapters)
        assertEquals(14L, resumed.secondsEstimate) // chỉ phần còn lại (280 chữ)
        assertTrue(resumed.bytes < fresh.bytes)
        assertEquals(JSONObject.NULL, ListenExport.plan(chapters, reading, work, null).toJson().get("secondsEstimate"))
        assertEquals(1, resumed.toJson().getInt("readyChapters"))
    }

    @Test
    fun theSpaceNeededGrowsWithTheBookAndAlwaysCoversTheJoinedFile() {
        val small = ListenExport.bytesNeeded(14_000, 14_000)
        val big = ListenExport.bytesNeeded(140_000, 140_000)
        assertTrue(big > small)
        // 1000 giây nghe x 8000 byte x 1,25 (ước dư) x hai lần (các chương + file nối) + dự phòng.
        assertEquals(1000 * 10_000L * 2 + (16L shl 20), small)
    }

    // ---- file cuối ----------------------------------------------------------------------------------------------------

    @Test
    fun theFinalPlanHasOneChapterPerFileWithTheRealLengthsTheTitleTheAuthorAndTheCover() {
        val chapters = listOf(chapter(1, "Một."), chapter(2, "Hai."))
        val stamps = run(chapters, Voice()).build()
        val cover = Id3Tag.Cover.of(byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 1, 2, 3))!!
        val plan = ListenExport.exportPlan(JSONObject().put("title", "Sách chữ").put("author", "Tác giả").put("chaptersTotal", 5), "sach", chapters, stamps, work, cover, "cover.jpg")
        assertEquals("Sách chữ", plan.title)
        assertEquals("Tác giả", plan.narrator)
        assertEquals(5, plan.chaptersTotal)
        assertEquals(listOf("Chương 1", "Chương 2"), plan.chapters.map { it.fullTitle })
        assertEquals(listOf(1, 2), plan.chapters.map { it.number })
        assertEquals(stamps[1].seconds, plan.chapters[1].duration, 1e-9)
        assertEquals(ListenExport.audioFile(work, chapters[0]), plan.chapters[0].file)
        assertEquals(cover, plan.cover)
    }

    @Test
    fun theWholeBookRunsThroughTheSameFinishingAsTheStudioM4b() {
        // Cả đường: ghép chương -> kế hoạch -> M4bExport.run với bộ nối giả -> cùng "lượt hai" (Mp4Finish) như M4B Studio.
        val chapters = listOf(chapter(1, "Một."), chapter(2, "Hai."))
        val stamps = run(chapters, Voice()).build()
        val plan = ListenExport.exportPlan(JSONObject().put("title", "Sách chữ").put("author", "Tác giả"), "sach", chapters, stamps, work, null, "cover.png")
        val seen = ArrayList<String>()
        val encoder = M4bExport.AudioEncoder { p, target, _, progress ->
            progress(0, p.chapters.size, 0.0)
            muxerLike(target)
            p.chapters.mapIndexed { index, chapter ->
                seen += chapter.fullTitle
                progress(index + 1, p.chapters.size, (index + 1.0) / p.chapters.size)
                Mp4Finish.Mark(chapter.fullTitle, index * 1000L, (index + 1) * 1000L)
            }
        }
        val out = ByteArrayOutputStream()
        val result = M4bExport.run(plan, File(work, "all.m4a"), out, encoder)
        assertEquals(listOf("Chương 1", "Chương 2"), seen)
        assertEquals("Sách chữ.m4b", result.name)
        assertEquals(2, result.chapters)
        assertEquals(out.size().toLong(), result.size)
        assertEquals("M4B ", String(out.toByteArray(), 8, 4, Charsets.ISO_8859_1))
        assertFalse("file nối trung gian dọn sau khi xong", File(work, "all.m4a").exists())
    }

    /** MP4 tối thiểu như MediaMuxer ghi (ftyp, mdat, moov một track) - đủ cho Mp4Finish. */
    private fun muxerLike(file: File) {
        fun u32(v: Int) = java.nio.ByteBuffer.allocate(4).putInt(v).array()
        fun box(type: String, vararg parts: ByteArray): ByteArray {
            val body = ByteArrayOutputStream().also { out -> parts.forEach(out::write) }.toByteArray()
            return u32(8 + body.size) + type.toByteArray(Charsets.ISO_8859_1) + body
        }
        val ftyp = box("ftyp", "isom".toByteArray(), u32(0), "isom".toByteArray(), "mp42".toByteArray())
        val start = ftyp.size + 8
        val stbl = box("stbl", box("stsd", u32(0), u32(0)), box("stts", u32(0), u32(0)), box("stsz", u32(0), u32(0), u32(0)), box("stco", u32(0), u32(1), u32(start)))
        val tkhd = box("tkhd", u32(7), u32(0), u32(0), u32(1), u32(0), u32(2000), ByteArray(60))
        val mdhd = box("mdhd", u32(0), u32(0), u32(0), u32(24000), u32(48000), ByteArray(4))
        val trak = box("trak", tkhd, box("mdia", mdhd, box("minf", stbl)))
        val mvhd = box("mvhd", u32(0), u32(0), u32(0), u32(1000), u32(2000), ByteArray(80), u32(2))
        file.writeBytes(ftyp + box("mdat", ByteArray(5)) + box("moov", mvhd, trak))
    }

    @Test
    fun chapterMarksStartWhereEachChapterStartsInTheJoinedStreamAndTheLastEndsWithIt() {
        // Ba chương dài 10, 5, 7 khung AAC ở 24 kHz (1024 mẫu một khung); luồng bị cắt 2048 mẫu ở đầu.
        val marks = ListenAudio.marks(listOf("A", "B", "C"), listOf(0L, 10L, 15L), 22L, 24000, 2048)
        assertEquals(listOf(0L, Math.round(10 * 1024 * 1000.0 / 24000), Math.round(15 * 1024 * 1000.0 / 24000)), marks.map { it.startMs })
        assertEquals(marks[1].startMs, marks[0].endMs)
        assertEquals(marks[2].startMs, marks[1].endMs)
        assertEquals(Math.round((22 * 1024 - 2048) * 1000.0 / 24000), marks[2].endMs)
        assertEquals(listOf("A", "B", "C"), marks.map { it.title })
    }

    // ---- clip WAV -----------------------------------------------------------------------------------------------------

    private fun wav(rate: Int, channels: Int, samples: ShortArray): File {
        val data = ByteArrayOutputStream()
        for (sample in samples) {
            data.write(sample.toInt() and 0xFF)
            data.write((sample.toInt() shr 8) and 0xFF)
        }
        val out = ByteArrayOutputStream()
        fun le32(v: Int) { for (i in 0 until 4) out.write((v shr (8 * i)) and 0xFF) }
        fun le16(v: Int) { out.write(v and 0xFF); out.write((v shr 8) and 0xFF) }
        out.write("RIFF".toByteArray()); le32(36 + data.size()); out.write("WAVEfmt ".toByteArray()); le32(16)
        le16(1); le16(channels); le32(rate); le32(rate * channels * 2); le16(channels * 2); le16(16)
        out.write("data".toByteArray()); le32(0x7FFFFFFF) // cỡ "data" sai như file ghi theo dòng: độ dài lấy từ cỡ file
        out.write(data.toByteArray())
        return File(clips, "x${samples.size}.wav").also { it.writeBytes(out.toByteArray()) }
    }

    @Test
    fun aMonoWavAtTheBookRateIsReadThroughUntouched() {
        val samples = ShortArray(20000) { (it % 300 - 150).toShort() }
        val file = wav(24000, 1, samples)
        val got = ArrayList<Short>()
        Clips.decodeWav(file, Wav.format(file)!!, 24000, { false }) { pcm, count -> for (i in 0 until count) got += pcm[i] }
        assertArrayEquals(samples, got.toShortArray())
        assertEquals(24000, Clips.rate(file))
    }

    @Test
    fun aStereoWavAtAnotherRateIsMixedDownAndResampledToTheBookRate() {
        val frames = 4800 // 0,1 giây ở 48 kHz
        val samples = ShortArray(frames * 2) { 1000 }
        val file = wav(48000, 2, samples)
        var total = 0
        Clips.decodeWav(file, Wav.format(file)!!, 24000, { false }) { pcm, count ->
            for (i in 0 until count) assertEquals(1000, pcm[i].toInt())
            total += count
        }
        assertTrue("khoảng 2400 mẫu mono ở 24 kHz, được $total", total in 2380..2400)
    }

    @Test
    fun readingAWavCanBeStopped() {
        val file = wav(24000, 1, ShortArray(100000))
        try {
            Clips.decodeWav(file, Wav.format(file)!!, 24000, { true }) { _, _ -> }
            fail("phải dừng")
        } catch (stopped: Mp3Export.Stopped) {
            // đúng
        }
    }

    @Test
    fun aWavSizeIsTakenFromTheFileNotTheHeader() {
        val file = wav(24000, 1, ShortArray(1234))
        var total = 0
        Clips.decodeWav(file, Wav.format(file)!!, 24000, { false }) { _, count -> total += count }
        assertEquals(1234, total)
        assertNotEquals(0x7FFFFFFF, total)
    }
}
