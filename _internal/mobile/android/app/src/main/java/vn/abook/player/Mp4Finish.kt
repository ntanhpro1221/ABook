package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import java.io.OutputStream
import java.io.RandomAccessFile
import java.nio.ByteBuffer

/**
 * Hoàn thiện file .m4b của "Xuất M4B": MediaMuxer chỉ ghi luồng AAC trần, không có mục lục chương, tag, bìa. Phần này chép luồng ấy
 * sang file cuối (không mã hoá lại) và gắn đúng những gì ffmpeg gắn ở máy tính (webui/export.py `export_m4b`, `-f ipod -brand "M4B "`):
 * - `ftyp` nhãn "M4B " để Apple Books / iTunes xếp vào sách nói;
 * - `moov/udta/chpl` (mục lục chương kiểu Nero - app đọc sách nói như Audiobookshelf, VLC, Smart AudioBook Player dùng) và một track
 *   văn bản QuickTime nối vào track âm thanh bằng `tref/chap` (Apple Books / BookPlayer dùng), cả hai cùng mốc;
 * - `moov/udta/meta/ilst`: tên sách (©nam, ©alb), giọng kể (©ART, aART), thể loại "Audiobook", bìa (covr).
 *
 * File cuối xếp `ftyp, mdat, moov`: các mẫu văn bản chương nối vào cuối `mdat`, `moov` mới ghi sau cùng nên không phải dời mẫu âm thanh,
 * chỉ cộng một độ lệch vào bảng `stco`/`co64` của track âm thanh (đầu `mdat` đổi chỗ vì `ftyp` đổi cỡ). Thuần Kotlin, không biết Android.
 */
object Mp4Finish {
    /** Một chương: tên và mốc đầu/cuối, tính bằng mili giây từ đầu file. */
    class Mark(val title: String, val startMs: Long, val endMs: Long)

    /** Tag của file: `title` là tên sách (vừa là tên vừa là album, như máy tính), `artist` giọng kể (rỗng thì không có tag). */
    class Tags(val title: String, val artist: String, val cover: Id3Tag.Cover?)

    private class Box(val type: String, val offset: Int, val header: Int, val size: Int)

    /** Hộp ở mức cao nhất của file (có thể quá 2 GB). */
    private class Span(val offset: Long, val header: Int, val size: Long)

    private fun broken() = Mp3Export.Refused("File âm thanh trung gian không hợp lệ")

    private const val GENRE = "Audiobook"
    /** Tên chương dài hơn thì cắt (chpl chỉ có một byte cho độ dài, ffmpeg cũng cắt ở 255); chpl chỉ chứa tối đa 255 chương. */
    private const val TITLE_BYTES = 255
    private const val CHPL_MAX = 255
    private const val MAX_FILE = 0xFFFFFFFFL - (16L shl 20)

    // Mô tả mẫu văn bản chương của ffmpeg (stsd 'text', cỡ 75) và hộp gmhd (cỡ 76): chép nguyên byte để mọi trình phát đọc như file máy tính.
    private val TEXT_STSD = hex("0000004b7374736400000000000000010000003b7465787400000000000000010000000100000000000000000000000000000000000000010000000000000000000d667461620001000100")
    private val TEXT_GMHD = hex("0000004c676d686400000018676d696e000000000040800080008000000000000000002c74657874000100000000000000000000000000000001000000000000000000000000000040000000")
    private val ENCD = hex("0000000c656e636400000100") // dấu "văn bản UTF-8" ffmpeg đặt sau tên mỗi chương
    private val MATRIX = ByteBuffer.allocate(36).apply { intArrayOf(0x10000, 0, 0, 0, 0x10000, 0, 0, 0, 0x40000000).forEach(::putInt) }.array()

    private fun hex(text: String) = ByteArray(text.length / 2) { text.substring(it * 2, it * 2 + 2).toInt(16).toByte() }

    // ---- dựng hộp ---------------------------------------------------------------------------------------------

    private fun u8(value: Int) = byteArrayOf(value.toByte())
    private fun u16(value: Int) = byteArrayOf((value shr 8).toByte(), value.toByte())
    private fun u32(value: Long) = ByteBuffer.allocate(4).putInt(value.toInt()).array()
    private fun u32(value: Int) = u32(value.toLong())
    private fun u64(value: Long) = ByteBuffer.allocate(8).putLong(value).array()
    private fun fourcc(name: String) = ByteArray(4) { name[it].code.toByte() }

    private fun box(type: String, vararg parts: ByteArray): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(u32(8 + parts.sumOf { it.size }))
        out.write(fourcc(type))
        parts.forEach(out::write)
        return out.toByteArray()
    }

    /** `©nam` & co: tên hộp có byte 0xA9 đầu. */
    private fun item(name: String, kind: Int, payload: ByteArray): ByteArray {
        val out = ByteArrayOutputStream()
        val data = box("data", u32(kind), u32(0), payload)
        out.write(u32(8 + data.size))
        out.write(ByteArray(4) { if (name[it] == '©') 0xA9.toByte() else name[it].code.toByte() })
        out.write(data)
        return out.toByteArray()
    }

    private fun clip(title: String): ByteArray {
        val bytes = title.toByteArray(Charsets.UTF_8)
        if (bytes.size <= TITLE_BYTES) return bytes
        var end = TITLE_BYTES
        while (end > 0 && bytes[end].toInt() and 0xC0 == 0x80) end-- // không cắt giữa một ký tự
        return bytes.copyOf(end)
    }

    internal fun udta(tags: Tags, marks: List<Mark>): ByteArray {
        val list = ByteArrayOutputStream()
        fun text(name: String, value: String) {
            if (value.isNotEmpty()) list.write(item(name, 1, value.toByteArray(Charsets.UTF_8)))
        }
        text("©nam", tags.title)
        text("©ART", tags.artist)
        text("aART", tags.artist)
        text("©alb", tags.title)
        text("©gen", GENRE)
        tags.cover?.let { list.write(item("covr", if (it.mime == "image/png") 14 else 13, it.bytes)) }
        val handler = box("hdlr", u32(0), u32(0), fourcc("mdir"), fourcc("appl"), u32(0), u32(0), u8(0))
        val meta = box("meta", u32(0), handler, box("ilst", list.toByteArray()))
        val parts = mutableListOf(meta)
        if (marks.isNotEmpty()) {
            val entries = ByteArrayOutputStream()
            for (mark in marks.take(CHPL_MAX)) {
                val title = clip(mark.title)
                entries.write(u64(mark.startMs * 10_000)) // đơn vị 100 ns
                entries.write(u8(title.size))
                entries.write(title)
            }
            parts += box("chpl", byteArrayOf(1, 0, 0, 0), u32(0), u8(minOf(marks.size, CHPL_MAX)), entries.toByteArray())
        }
        return box("udta", *parts.toTypedArray())
    }

    /** Track văn bản chương: một mẫu cho mỗi chương, `chunkOffset` là chỗ các mẫu nằm trong file, mẫu i dài `sizes[i]`. */
    internal fun textTrack(trackId: Int, movieTimescale: Int, marks: List<Mark>, sizes: List<Int>, chunkOffset: Long): ByteArray {
        val total = marks.last().endMs
        val tkhd = box("tkhd", u32(2), u32(0), u32(0), u32(trackId), u32(0), u32(total * movieTimescale / 1000), u32(0), u32(0),
            u16(0), u16(0), u16(0), u16(0), MATRIX, u32(0), u32(0))
        val mdhd = box("mdhd", u32(0), u32(0), u32(0), u32(1000), u32(total), u16(0x55C4), u16(0))
        val hdlr = box("hdlr", u32(0), u32(0), fourcc("text"), u32(0), u32(0), u32(0), "SubtitleHandler".toByteArray(), u8(0))
        val dinf = box("dinf", box("dref", u32(0), u32(1), box("url ", u32(1))))
        val stts = ByteArrayOutputStream()
        var runs = 0
        var index = 0
        while (index < marks.size) {
            val length = marks[index].endMs - marks[index].startMs
            var count = 1
            while (index + count < marks.size && marks[index + count].endMs - marks[index + count].startMs == length) count++
            stts.write(u32(count))
            stts.write(u32(length))
            runs++
            index += count
        }
        val stsz = ByteArrayOutputStream().apply { sizes.forEach { write(u32(it)) } }
        val stbl = box("stbl", TEXT_STSD, box("stts", u32(0), u32(runs), stts.toByteArray()),
            box("stsc", u32(0), u32(1), u32(1), u32(marks.size), u32(1)),
            box("stsz", u32(0), u32(0), u32(marks.size), stsz.toByteArray()),
            box("stco", u32(0), u32(1), u32(chunkOffset)))
        val minf = box("minf", TEXT_GMHD, dinf, stbl)
        return box("trak", tkhd, box("mdia", mdhd, hdlr, minf))
    }

    private fun textSample(mark: Mark): ByteArray {
        val title = clip(mark.title)
        return u16(title.size) + title + ENCD
    }

    // ---- đọc hộp ---------------------------------------------------------------------------------------------

    private fun be32(buffer: ByteArray, at: Int) = ByteBuffer.wrap(buffer, at, 4).int.toLong() and 0xFFFFFFFFL
    private fun be64(buffer: ByteArray, at: Int) = ByteBuffer.wrap(buffer, at, 8).long
    private fun type(buffer: ByteArray, at: Int) = String(buffer, at, 4, Charsets.ISO_8859_1)

    /** Các hộp con nằm giữa `start` và `end` của `buffer`. */
    private fun children(buffer: ByteArray, start: Int, end: Int): List<Box> {
        val out = ArrayList<Box>()
        var at = start
        while (at + 8 <= end) {
            var size = be32(buffer, at)
            var header = 8
            if (size == 1L) {
                size = be64(buffer, at + 8)
                header = 16
            } else if (size == 0L) {
                size = (end - at).toLong()
            }
            if (size < header || at + size > end) throw broken()
            out += Box(type(buffer, at + 4), at, header, size.toInt())
            at += size.toInt()
        }
        return out
    }

    private fun find(buffer: ByteArray, parent: Box, vararg path: String): Box? {
        var current = parent
        for (name in path) current = children(buffer, current.offset + current.header, current.offset + current.size).firstOrNull { it.type == name } ?: return null
        return current
    }

    /** Cộng `delta` vào mọi chỗ bảng `stco`/`co64` của một track chỉ vào `mdat`. Sửa tại chỗ. */
    private fun shiftChunks(buffer: ByteArray, track: Box, delta: Long) {
        val table = find(buffer, track, "mdia", "minf", "stbl") ?: return
        for (box in children(buffer, table.offset + table.header, table.offset + table.size)) {
            val wide = box.type == "co64"
            if (!wide && box.type != "stco") continue
            val body = box.offset + box.header
            val count = be32(buffer, body + 4).toInt()
            for (entry in 0 until count) {
                if (wide) {
                    val at = body + 8 + entry * 8
                    ByteBuffer.wrap(buffer, at, 8).putLong(be64(buffer, at) + delta)
                } else {
                    val at = body + 8 + entry * 4
                    val moved = be32(buffer, at) + delta
                    if (moved !in 0..0xFFFFFFFFL) throw Mp3Export.Refused("File M4B quá lớn (hơn 4 GB)")
                    ByteBuffer.wrap(buffer, at, 4).putInt(moved.toInt())
                }
            }
        }
    }

    private fun trackId(buffer: ByteArray, track: Box): Int {
        val header = find(buffer, track, "tkhd") ?: throw broken()
        val body = header.offset + header.header
        return be32(buffer, body + if (buffer[body].toInt() == 1) 20 else 12).toInt()
    }

    /** (thang thời gian, thời lượng) của track theo `mdhd`, tính bằng mẫu. */
    private fun mediaTiming(buffer: ByteArray, track: Box): Pair<Long, Long> {
        val header = find(buffer, track, "mdia", "mdhd") ?: throw broken()
        val body = header.offset + header.header
        return if (buffer[body].toInt() == 1) be32(buffer, body + 20) to be64(buffer, body + 24) else be32(buffer, body + 12) to be32(buffer, body + 16)
    }

    /**
     * Chép track âm thanh `track` kèm: bảng cắt `edts/elst` bỏ `delay` mẫu đầu (độ trễ của bộ mã hoá AAC - ffmpeg cũng ghi bảng này, không
     * thì trình phát đọc cả đoạn câm đầu file và mọi mốc chương lệch đúng bằng ấy); hộp `tref/chap` trỏ tới track chương `chapterTrack`
     * nếu có. Hai hộp đặt ngay trước `mdia`; hộp `edts` cũ (nếu MediaMuxer đã ghi) bị thay.
     */
    private fun rebuildAudioTrack(buffer: ByteArray, track: Box, chapterTrack: Int?, delay: Int, movieTimescale: Int): ByteArray {
        val inner = ByteArrayOutputStream()
        val (mediaScale, mediaDuration) = mediaTiming(buffer, track)
        val kept = (mediaDuration - delay).coerceAtLeast(0)
        val segment = kept * movieTimescale / mediaScale.coerceAtLeast(1)
        for (part in children(buffer, track.offset + track.header, track.offset + track.size)) {
            when {
                part.type == "tref" -> Unit
                part.type == "edts" && delay > 0 -> Unit
                part.type == "mdia" -> {
                    if (delay > 0) inner.write(box("edts", box("elst", u32(0), u32(1), u32(segment), u32(delay), u16(1), u16(0))))
                    if (chapterTrack != null) inner.write(box("tref", box("chap", u32(chapterTrack))))
                    inner.write(buffer, part.offset, part.size)
                }
                part.type == "tkhd" && delay > 0 -> {
                    // Thời lượng của track = thời lượng sau khi bỏ đoạn đầu (phần thân tkhd phiên bản 0: duration ở byte 20, phiên bản 1: byte 28).
                    val copy = buffer.copyOfRange(part.offset, part.offset + part.size)
                    val body = part.header
                    if (copy[body].toInt() == 1) ByteBuffer.wrap(copy, body + 28, 8).putLong(segment) else ByteBuffer.wrap(copy, body + 20, 4).putInt(segment.toInt())
                    inner.write(copy)
                }
                else -> inner.write(buffer, part.offset, part.size)
            }
        }
        return box("trak", inner.toByteArray())
    }

    // ---- ghép file --------------------------------------------------------------------------------------------

    /**
     * Chép `source` (đầu ra của MediaMuxer) sang `out` kèm nhãn M4B, mục lục chương, tag và bìa. `delay`: số mẫu đầu luồng là độ trễ của
     * bộ mã hoá (không phải tiếng) - file ghi bảng cắt để trình phát bỏ qua. `stopped` được hỏi khi chép luồng
     * (tệp có thể vài trăm MB): true thì ném [Mp3Export.Stopped]. `out` do người gọi mở và đóng; hỏng giữa chừng thì người gọi xoá phần dở.
     */
    fun finish(source: File, out: OutputStream, tags: Tags, marks: List<Mark>, delay: Int = 0, stopped: () -> Boolean = { false }) {
        RandomAccessFile(source, "r").use { file ->
            if (file.length() > MAX_FILE) throw Mp3Export.Refused("File M4B quá lớn (hơn 4 GB)")
            val head = ByteArray(16)
            var mdat: Span? = null
            var moov: Span? = null
            var at = 0L
            while (at + 8 <= file.length()) {
                file.seek(at)
                val n = file.read(head, 0, 16)
                var size = be32(head, 0)
                var header = 8
                if (size == 1L && n >= 16) {
                    size = be64(head, 8)
                    header = 16
                } else if (size == 0L) {
                    size = file.length() - at
                }
                if (size < header || at + size > file.length()) throw broken()
                when (type(head, 4)) {
                    "mdat" -> mdat = Span(at, header, size)
                    "moov" -> moov = Span(at, header, size)
                }
                at += size
            }
            if (mdat == null || moov == null) throw broken()
            val buffer = ByteArray(moov.size.toInt())
            file.seek(moov.offset)
            file.readFully(buffer)
            val whole = Box("moov", 0, moov.header, buffer.size)
            val parts = children(buffer, whole.header, whole.size)

            val brand = box("ftyp", fourcc("M4B "), u32(512), fourcc("M4B "), fourcc("mp42"), fourcc("isom"))
            val payload = mdat.size - mdat.header
            val marked = marks.filter { it.endMs > it.startMs }
            val samples = marked.map(::textSample)
            val extra = samples.sumOf { it.size }
            val mdatHeader = if (8L + payload + extra > 0xFFFFFFFFL) 16 else 8
            val newStart = (brand.size + mdatHeader).toLong()
            val delta = newStart - (mdat.offset + mdat.header)

            val mvhd = parts.firstOrNull { it.type == "mvhd" } ?: throw broken()
            val mvhdBody = mvhd.offset + mvhd.header
            val timescale = be32(buffer, mvhdBody + if (buffer[mvhdBody].toInt() == 1) 20 else 12).toInt().coerceAtLeast(1)
            val nextId = be32(buffer, mvhd.offset + mvhd.size - 4).toInt()
            val chapterId = nextId.coerceAtLeast(2)

            val tracks = parts.filter { it.type == "trak" }
            if (tracks.isEmpty()) throw broken()
            tracks.forEach { shiftChunks(buffer, it, delta) }
            if (delay > 0 && buffer[mvhdBody].toInt() == 0) {
                // Thời lượng phim cũng bớt đoạn đầu đã cắt (mvhd phiên bản 0: duration ở byte 16 của phần thân).
                val (mediaScale, mediaDuration) = mediaTiming(buffer, tracks.first())
                ByteBuffer.wrap(buffer, mvhdBody + 16, 4).putInt(((mediaDuration - delay).coerceAtLeast(0) * timescale / mediaScale.coerceAtLeast(1)).toInt())
            }

            val moovBody = ByteArrayOutputStream()
            var chaptered = false
            for (part in parts) {
                when {
                    part.type == "udta" -> Unit // thay bằng udta của mình
                    part.type == "mvhd" -> {
                        if (marked.isNotEmpty()) ByteBuffer.wrap(buffer, mvhd.offset + mvhd.size - 4, 4).putInt(chapterId + 1)
                        moovBody.write(buffer, part.offset, part.size)
                    }
                    part.type == "trak" && !chaptered && (marked.isNotEmpty() || delay > 0) -> {
                        chaptered = true
                        moovBody.write(rebuildAudioTrack(buffer, part, if (marked.isNotEmpty()) chapterId else null, delay, timescale))
                    }
                    else -> moovBody.write(buffer, part.offset, part.size)
                }
            }
            val textOffset = newStart + payload
            if (marked.isNotEmpty()) moovBody.write(textTrack(chapterId, timescale, marked, samples.map { it.size }, textOffset))
            moovBody.write(udta(tags, marked))
            val newMoov = box("moov", moovBody.toByteArray())

            out.write(brand)
            val total = mdatHeader + payload + extra
            if (mdatHeader == 16) {
                out.write(u32(1))
                out.write(fourcc("mdat"))
                out.write(u64(total))
            } else {
                out.write(u32(total))
                out.write(fourcc("mdat"))
            }
            file.seek(mdat.offset + mdat.header)
            val block = ByteArray(256 * 1024)
            var left = payload
            while (left > 0) {
                if (stopped()) throw Mp3Export.Stopped()
                val read = file.read(block, 0, minOf(block.size.toLong(), left).toInt())
                if (read < 0) throw broken()
                out.write(block, 0, read)
                left -= read
            }
            samples.forEach(out::write)
            out.write(newMoov)
        }
    }
}
