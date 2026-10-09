package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.file.Files

/**
 * "Xuất M4B" trên điện thoại: phần ghi hộp MP4 (Mp4Finish - mục lục chương chpl + track văn bản QuickTime, tag, bìa, nhãn M4B), đổi định dạng
 * PCM, và cả lượt xuất một cuốn giả với bộ mã hoá giả (bộ mã hoá thật dùng MediaCodec của Android - có bài thử trên máy ảo,
 * M4bExportOnDeviceTest). File "MediaMuxer" ở đây là file MP4 tối thiểu dựng tay, cùng bố cục MediaMuxer ghi: ftyp, mdat, moov.
 */
class M4bExportTest {
    private lateinit var root: File
    private lateinit var scratch: File

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-m4b").toFile()
        scratch = Files.createTempDirectory("abook-m4b-out").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
        scratch.deleteRecursively()
    }

    // ---- dựng và đọc hộp ----------------------------------------------------------------------------------------

    private fun u32(value: Int) = ByteBuffer.allocate(4).putInt(value).array()

    private fun box(type: String, vararg parts: ByteArray): ByteArray {
        val body = ByteArrayOutputStream().also { out -> parts.forEach(out::write) }.toByteArray()
        return u32(8 + body.size) + type.toByteArray(Charsets.ISO_8859_1) + body
    }

    /** MP4 một track âm thanh như MediaMuxer ghi: `mdat` giữa, `moov` sau cùng; chunk đầu của track ở đầu `mdat`. */
    private fun muxerFile(payload: ByteArray, file: File, durationMs: Int = 1000, wide: Boolean = false): Int {
        val ftyp = box("ftyp", "isom".toByteArray(), u32(0), "isom".toByteArray(), "mp42".toByteArray(), "iso2".toByteArray())
        val mdatStart = ftyp.size + 8
        val offsets = if (wide) {
            box("co64", u32(0), u32(2), ByteBuffer.allocate(16).putLong(mdatStart.toLong()).putLong(mdatStart + 5L).array())
        } else {
            box("stco", u32(0), u32(2), u32(mdatStart), u32(mdatStart + 5))
        }
        val stbl = box("stbl", box("stsd", u32(0), u32(0)), box("stts", u32(0), u32(0)), box("stsz", u32(0), u32(0), u32(0)), offsets)
        val tkhd = box("tkhd", u32(7), u32(0), u32(0), u32(1), u32(0), u32(durationMs), ByteArray(60))
        val mdhd = box("mdhd", u32(0), u32(0), u32(0), u32(24000), u32(durationMs * 24), ByteArray(4))
        val trak = box("trak", tkhd, box("mdia", mdhd, box("minf", stbl)))
        val mvhd = box("mvhd", u32(0), u32(0), u32(0), u32(1000), u32(durationMs), ByteArray(80), u32(2))
        file.writeBytes(ftyp + box("mdat", payload) + box("moov", mvhd, trak))
        return mdatStart
    }

    private class Node(val type: String, val offset: Int, val header: Int, val size: Int)

    private fun nodes(data: ByteArray, from: Int = 0, to: Int = data.size): List<Node> {
        val out = ArrayList<Node>()
        var at = from
        while (at + 8 <= to) {
            val size = ByteBuffer.wrap(data, at, 4).int
            out += Node(String(data, at + 4, 4, Charsets.ISO_8859_1), at, 8, size)
            at += size
        }
        assertEquals("hộp không tràn ra ngoài cha", to, at)
        return out
    }

    private fun child(data: ByteArray, parent: Node, type: String): Node? = nodes(data, parent.offset + parent.header, parent.offset + parent.size).firstOrNull { it.type == type }

    private fun path(data: ByteArray, vararg names: String): Node? {
        var current = nodes(data).firstOrNull { it.type == names[0] } ?: return null
        for (name in names.drop(1)) current = child(data, current, name) ?: return null
        return current
    }

    private fun payload(data: ByteArray, node: Node) = data.copyOfRange(node.offset + node.header, node.offset + node.size)

    /** Các mục của `moov/udta/meta/ilst` (sau 4 byte phiên bản của meta và hộp hdlr 33 byte). */
    private fun tagItems(data: ByteArray): List<Node> {
        val meta = path(data, "moov", "udta", "meta")!!
        val ilst = nodes(data, meta.offset + 12 + 33, meta.offset + meta.size).single { it.type == "ilst" }
        return nodes(data, ilst.offset + 8, ilst.offset + ilst.size)
    }

    private val marks = listOf(
        Mp4Finish.Mark("Chương 1: Mở đầu", 0, 400),
        Mp4Finish.Mark("Chương 2 · Về nhà", 400, 900),
        Mp4Finish.Mark("Chương 3", 900, 1500),
    )

    private fun finished(wide: Boolean = false, cover: Id3Tag.Cover? = null, artist: String = "Đức Trí", marked: List<Mp4Finish.Mark> = marks,
                         delay: Int = 0): Pair<ByteArray, ByteArray> {
        val data = ByteArray(300) { (it * 7).toByte() }
        val source = File(scratch, "audio.m4a")
        muxerFile(data, source, wide = wide)
        val out = ByteArrayOutputStream()
        Mp4Finish.finish(source, out, Mp4Finish.Tags("Sách thử: Tập 1", artist, cover), marked, delay)
        return data to out.toByteArray()
    }

    // ---- Mp4Finish -----------------------------------------------------------------------------------------------

    @Test
    fun brandAndLayoutAreAnAudiobook() {
        val (_, result) = finished()
        assertEquals(listOf("ftyp", "mdat", "moov"), nodes(result).map { it.type })
        val ftyp = payload(result, nodes(result)[0])
        assertEquals("M4B ", String(ftyp, 0, 4, Charsets.ISO_8859_1))
        assertEquals(512, ByteBuffer.wrap(ftyp, 4, 4).int)
        assertEquals("M4B mp42isom", String(ftyp, 8, 12, Charsets.ISO_8859_1))
    }

    @Test
    fun audioSamplesAreCopiedAndChunkOffsetsFollowThem() {
        for (wide in listOf(false, true)) {
            val (data, result) = finished(wide)
            val mdat = nodes(result).first { it.type == "mdat" }
            // Âm thanh vẫn nguyên vẹn ở đầu mdat, theo sau là các mẫu văn bản chương.
            assertArrayEquals(data, result.copyOfRange(mdat.offset + 8, mdat.offset + 8 + data.size))
            val table = path(result, "moov", "trak", "mdia", "minf", "stbl")!!
            val body = if (wide) payload(result, child(result, table, "co64")!!) else payload(result, child(result, table, "stco")!!)
            val first = if (wide) ByteBuffer.wrap(body, 8, 8).long else ByteBuffer.wrap(body, 8, 4).int.toLong()
            val second = if (wide) ByteBuffer.wrap(body, 16, 8).long else ByteBuffer.wrap(body, 12, 4).int.toLong()
            assertEquals((mdat.offset + 8).toLong(), first)
            assertEquals((mdat.offset + 8 + 5).toLong(), second)
        }
    }

    @Test
    fun chapterListIsTheDesktopChpl() {
        val (_, result) = finished()
        val udta = path(result, "moov", "udta")!!
        val chpl = payload(result, child(result, udta, "chpl")!!)
        val buffer = ByteBuffer.wrap(chpl)
        assertEquals(1, buffer.get().toInt()) // phiên bản 1 như ffmpeg
        buffer.position(8) // cờ + 4 byte dành riêng
        assertEquals(3, buffer.get().toInt() and 0xFF)
        val seen = ArrayList<Pair<Long, String>>()
        repeat(3) {
            val start = buffer.long
            val length = buffer.get().toInt() and 0xFF
            val title = ByteArray(length).also(buffer::get)
            seen += start to String(title, Charsets.UTF_8)
        }
        assertEquals(listOf(0L to "Chương 1: Mở đầu", 4_000_000L to "Chương 2 · Về nhà", 9_000_000L to "Chương 3"), seen)
        assertEquals(0, buffer.remaining())
    }

    @Test
    fun chapterTextTrackIsLinkedAndItsSamplesAreTheTitles() {
        val (_, result) = finished()
        val moov = path(result, "moov")!!
        val tracks = nodes(result, moov.offset + 8, moov.offset + moov.size).filter { it.type == "trak" }
        assertEquals(2, tracks.size)
        // Track âm thanh trỏ tới track chương bằng tref/chap; mvhd báo mã track kế tiếp sau cả hai.
        val reference = payload(result, child(result, child(result, tracks[0], "tref")!!, "chap")!!)
        val textId = ByteBuffer.wrap(reference).int
        val tkhd = payload(result, child(result, tracks[1], "tkhd")!!)
        assertEquals(textId, ByteBuffer.wrap(tkhd, 12, 4).int)
        assertEquals(2, textId) // sau mã track âm thanh (1)
        val mvhd = payload(result, child(result, moov, "mvhd")!!)
        assertEquals(textId + 1, ByteBuffer.wrap(mvhd, mvhd.size - 4, 4).int)
        val audioId = ByteBuffer.wrap(payload(result, child(result, tracks[0], "tkhd")!!), 12, 4).int
        assertEquals(1, audioId)
        assertEquals(1500, ByteBuffer.wrap(tkhd, 20, 4).int) // theo thang thời gian của phim (mili giây)
        // Mẫu văn bản: mỗi chương một mẫu "độ dài + chữ UTF-8" nằm đúng chỗ stco chỉ, cỡ theo stsz, thời lượng theo stts.
        val table = child(result, child(result, child(result, tracks[1], "mdia")!!, "minf")!!, "stbl")!!
        val stco = payload(result, child(result, table, "stco")!!)
        val stsz = payload(result, child(result, table, "stsz")!!)
        val stts = payload(result, child(result, table, "stts")!!)
        assertEquals(3, ByteBuffer.wrap(stsz, 8, 4).int)
        var at = ByteBuffer.wrap(stco, 8, 4).int
        val titles = ArrayList<String>()
        for (index in 0 until 3) {
            val size = ByteBuffer.wrap(stsz, 12 + index * 4, 4).int
            val length = ByteBuffer.wrap(result, at, 2).short.toInt() and 0xFFFF
            titles += String(result, at + 2, length, Charsets.UTF_8)
            at += size
        }
        assertEquals(marks.map { it.title }, titles)
        // Nằm sau âm thanh, trong mdat, và mdat kết thúc ngay sau mẫu cuối.
        val mdat = nodes(result).first { it.type == "mdat" }
        assertEquals(mdat.offset + mdat.size, at)
        // 400, 500, 600 ms: không hai chương liền nhau cùng dài nên ba mục.
        assertEquals(3, ByteBuffer.wrap(stts, 4, 4).int)
        assertEquals(listOf(1, 400, 1, 500, 1, 600), (0 until 6).map { ByteBuffer.wrap(stts, 8 + it * 4, 4).int })
    }

    @Test
    fun tagsAreTheDesktopTags() {
        val cover = Id3Tag.Cover.of(File(Id3TagTest.dir, "cover.jpg").readBytes())!!
        val (_, result) = finished(cover = cover)
        val items = tagItems(result)
        fun text(item: Node): String = String(result, item.offset + 24, item.size - 24, Charsets.UTF_8)
        assertEquals(listOf("©nam", "©ART", "aART", "©alb", "©gen", "covr"), items.map { String(result, it.offset + 4, 4, Charsets.ISO_8859_1) })
        assertEquals(listOf("Sách thử: Tập 1", "Đức Trí", "Đức Trí", "Sách thử: Tập 1", "Audiobook"), items.take(5).map(::text))
        val picture = items.last()
        assertEquals(13, ByteBuffer.wrap(result, picture.offset + 16, 4).int) // 13 = JPEG
        assertArrayEquals(cover.bytes, result.copyOfRange(picture.offset + 24, picture.offset + picture.size))
    }

    @Test
    fun withoutNarratorOrCoverTheseTagsAreLeftOut() {
        val (_, result) = finished(artist = "")
        assertEquals(listOf("©nam", "©alb", "©gen"), tagItems(result).map { String(result, it.offset + 4, 4, Charsets.ISO_8859_1) })
    }

    @Test
    fun aBookWithoutChaptersStillGetsItsTags() {
        val (data, result) = finished(marked = emptyList())
        val moov = path(result, "moov")!!
        assertEquals(1, nodes(result, moov.offset + 8, moov.offset + moov.size).count { it.type == "trak" })
        assertNull(path(result, "moov", "udta", "chpl"))
        assertNotNull(path(result, "moov", "udta", "meta"))
        assertEquals(data.size + 8, nodes(result).first { it.type == "mdat" }.size)
    }

    private fun assertNull(node: Node?) = assertTrue(node == null)

    @Test
    fun theEncoderDelayIsCutByAnEditList() {
        for (marked in listOf(marks, emptyList())) {
            val (_, result) = finished(marked = marked, delay = 2048)
            val moov = path(result, "moov")!!
            val audio = nodes(result, moov.offset + 8, moov.offset + moov.size).first { it.type == "trak" }
            val elst = payload(result, child(result, child(result, audio, "edts")!!, "elst")!!)
            assertEquals(1, ByteBuffer.wrap(elst, 4, 4).int)
            val segment = ByteBuffer.wrap(elst, 8, 4).int
            assertEquals((24000 - 2048) * 1000 / 24000, segment) // thời lượng sau khi cắt, theo thang thời gian của phim
            assertEquals(2048, ByteBuffer.wrap(elst, 12, 4).int) // bỏ 2048 mẫu đầu của luồng
            assertEquals(1, ByteBuffer.wrap(elst, 16, 2).short.toInt())
            assertEquals(segment, ByteBuffer.wrap(payload(result, child(result, audio, "tkhd")!!), 20, 4).int)
            assertEquals(segment, ByteBuffer.wrap(payload(result, child(result, moov, "mvhd")!!), 16, 4).int)
            // edts đứng trước mdia (và trước tref nếu có chương).
            assertEquals(listOf("tkhd", "edts") + (if (marked.isEmpty()) emptyList() else listOf("tref")) + "mdia",
                nodes(result, audio.offset + 8, audio.offset + audio.size).map { it.type })
        }
    }

    @Test
    fun withoutADelayThereIsNoEditList() {
        val (_, result) = finished()
        val moov = path(result, "moov")!!
        val audio = nodes(result, moov.offset + 8, moov.offset + moov.size).first { it.type == "trak" }
        assertNull(child(result, audio, "edts"))
    }

    @Test
    fun longChapterTitlesAreCutOnACharacterBoundary() {
        val title = "Chương " + "Ặ".repeat(200) // mỗi Ặ 3 byte: 600+ byte
        val (_, result) = finished(marked = listOf(Mp4Finish.Mark(title, 0, 500)))
        val chpl = payload(result, path(result, "moov", "udta", "chpl")!!)
        val length = chpl[8 + 1 + 8].toInt() and 0xFF
        assertTrue(length <= 255)
        val shown = String(chpl, 8 + 1 + 8 + 1, length, Charsets.UTF_8)
        assertFalse("không ký tự hỏng", shown.contains('�'))
        assertTrue(title.startsWith(shown))
    }

    @Test
    fun aBrokenIntermediateFileIsRefusedWithAMessage() {
        val source = File(scratch, "bad.m4a")
        source.writeBytes(ByteArray(40))
        try {
            Mp4Finish.finish(source, ByteArrayOutputStream(), Mp4Finish.Tags("x", "", null), marks)
            fail("phải từ chối")
        } catch (error: Mp3Export.Refused) {
            assertTrue(error.message!!.isNotEmpty())
        }
    }

    // ---- PcmConverter ------------------------------------------------------------------------------------------------

    private fun converter(fromRate: Int, fromChannels: Int, toRate: Int, toChannels: Int) = M4bExport.PcmConverter(fromRate, fromChannels, toRate, toChannels)

    @Test
    fun sameFormatPassesThrough() {
        val pcm = ShortArray(100) { (it * 300 - 15000).toShort() }
        assertArrayEquals(pcm, converter(24000, 1, 24000, 1).convert(pcm, pcm.size))
    }

    @Test
    fun channelsAreMixedLikeFfmpeg() {
        assertArrayEquals(shortArrayOf(1500, -250), converter(24000, 2, 24000, 1).convert(shortArrayOf(1000, 2000, -500, 0), 4))
        assertArrayEquals(shortArrayOf(7, 7, -3, -3), converter(24000, 1, 24000, 2).convert(shortArrayOf(7, -3), 2))
        assertArrayEquals(shortArrayOf(10, 20), converter(24000, 3, 24000, 2).convert(shortArrayOf(10, 20, 999), 3))
    }

    @Test
    fun resamplingKeepsDurationAndDoesNotDependOnHowTheBlocksAreCut() {
        val source = ShortArray(24000) { (Math.sin(it * 0.05) * 12000).toInt().toShort() }
        for ((from, to) in listOf(24000 to 48000, 22050 to 24000, 48000 to 24000)) {
            val whole = converter(from, 1, to, 1).convert(source, source.size)
            assertEquals(source.size.toDouble() * to / from, whole.size.toDouble(), 2.0)
            val cut = converter(from, 1, to, 1)
            val pieces = ArrayList<Short>()
            var at = 0
            for (size in generateSequence(997) { it }.takeWhile { at < source.size }) {
                val take = minOf(size, source.size - at)
                pieces += cut.convert(source.copyOfRange(at, at + take), take).toList()
                at += take
            }
            assertArrayEquals("$from -> $to", whole, pieces.toShortArray())
        }
    }

    @Test
    fun resamplingASineKeepsItsShape() {
        val source = ShortArray(2400) { (Math.sin(2 * Math.PI * 440 * it / 24000) * 10000).toInt().toShort() }
        val up = converter(24000, 1, 48000, 1).convert(source, source.size)
        var worst = 0.0
        for (index in 8 until up.size - 8) {
            worst = maxOf(worst, Math.abs(up[index] - Math.sin(2 * Math.PI * 440 * index / 48000) * 10000))
        }
        assertTrue("sai lệch $worst", worst < 120) // nội suy tuyến tính của sóng 440 Hz ở 24 kHz
    }

    // ---- lượt xuất ----------------------------------------------------------------------------------------------------

    private fun book(id: String, chapters: List<Pair<String, Boolean>>, cover: Boolean = true) {
        val dir = File(root, "books/$id").apply { mkdirs() }
        val list = JSONArray()
        chapters.forEachIndexed { index, (title, done) ->
            val chapter = JSONObject().put("id", index + 1).put("index", index + 1).put("fullTitle", title)
                .put("duration", if (done) 12.5 + index else 0.0).put("available", done)
            if (done) {
                File(dir, "chapters").mkdirs()
                File(Id3TagTest.dir, "source.mp3").copyTo(File(dir, "chapters/${index + 1}.mp3"))
                chapter.put("file", "chapters/${index + 1}.mp3")
            }
            list.put(chapter)
        }
        if (cover) File(Id3TagTest.dir, "cover.jpg").copyTo(File(dir, "cover.jpg"))
        File(dir, "book.json").writeText(JSONObject().put("format", "abook-book/1").put("title", "Sách thử: Tập 1")
            .put("narrator", "Đức Trí").put("chaptersTotal", chapters.size).put("chapters", list).toString())
    }

    /** Bộ mã hoá giả: ghi file MP4 tối thiểu và trả mốc 1 giây mỗi chương. */
    private fun fake(seen: MutableList<String> = ArrayList()) = M4bExport.AudioEncoder { plan, target, stopped, progress ->
        progress(0, plan.chapters.size, 0.0)
        val result = plan.chapters.mapIndexed { index, chapter ->
            if (stopped()) throw Mp3Export.Stopped()
            seen += chapter.fullTitle
            progress(index + 1, plan.chapters.size, (index + 1.0) / plan.chapters.size)
            Mp4Finish.Mark(chapter.fullTitle, index * 1000L, (index + 1) * 1000L)
        }
        muxerFile(ByteArray(64) { it.toByte() }, target, durationMs = plan.chapters.size * 1000)
        result
    }

    @Test
    fun theFileIsNamedAfterTheBookLikeTheDesktop() {
        assertEquals("Sách thử Tập 1.m4b", M4bExport.fileName("Sách thử: Tập 1"))
        assertTrue(M4bExport.fileName("Ạ".repeat(200)).toByteArray(Charsets.UTF_8).size <= 255)
        assertTrue(M4bExport.fileName("Ạ".repeat(200)).endsWith(".m4b"))
    }

    @Test
    fun exportsOnlyTheListenableChaptersWithTheirTitlesAndCover() {
        book("m1", listOf("Chương 1: Mở đầu" to true, "Chương 2" to false, "Chương 3 · Về nhà" to true))
        val plan = Mp3Export.plan("m1")
        val out = ByteArrayOutputStream()
        val work = File(scratch, "work.m4a")
        val progress = ArrayList<Triple<Int, Int, Double>>()
        val result = M4bExport.run(plan, work, out, fake(), progress = { done, total, fraction -> progress += Triple(done, total, fraction) })
        assertEquals("Sách thử Tập 1.m4b", result.name)
        assertEquals(2, result.chapters)
        assertEquals(3, result.chaptersTotal)
        assertEquals(out.size().toLong(), result.size)
        assertFalse("file trung gian dọn sau khi xong", work.exists())
        assertEquals(Triple(2, 2, 1.0), progress.last())
        val bytes = out.toByteArray()
        val chpl = payload(bytes, path(bytes, "moov", "udta", "chpl")!!)
        assertEquals(2, chpl[8].toInt())
        assertTrue(tagItems(bytes).any { String(bytes, it.offset + 4, 4, Charsets.ISO_8859_1) == "covr" })
    }

    @Test
    fun stoppingLeavesNothingBehind() {
        book("m2", listOf("Chương 1" to true, "Chương 2" to true))
        val out = ByteArrayOutputStream()
        val work = File(scratch, "work.m4a")
        var asked = 0
        try {
            M4bExport.run(Mp3Export.plan("m2"), work, out, fake(), stopped = { ++asked > 1 })
            fail("phải dừng")
        } catch (_: Mp3Export.Stopped) {
            assertFalse(work.exists())
        }
    }

    @Test
    fun aBookWithNothingToExportIsRefusedBeforeAnythingStarts() {
        book("m3", listOf("Chương 1" to false))
        try {
            Mp3Export.plan("m3")
            fail("phải từ chối")
        } catch (error: Mp3Export.Refused) {
            assertEquals("Sách chưa có chương nào nghe được để xuất", error.message)
        }
    }

    @Test
    fun estimateGrowsWithTheBook() {
        book("m4", listOf("Chương 1" to true, "Chương 2" to true))
        val small = M4bExport.estimatedBytes(Mp3Export.plan("m4"))
        assertTrue(small > (16L shl 20))
        assertTrue(small < (17L shl 20)) // 25 giây AAC mono: chưa tới 1 MB
    }
}
