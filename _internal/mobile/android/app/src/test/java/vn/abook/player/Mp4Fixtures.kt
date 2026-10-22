package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer

/** File MP4 tối thiểu dựng tay cho các bài thử ghi M4B / .m4a (M4bExportTest, MixedMp3ExportTest): cùng bố cục MediaMuxer ghi - ftyp, mdat, moov. */
object Mp4Fixtures {
    fun u32(value: Int): ByteArray = ByteBuffer.allocate(4).putInt(value).array()

    fun box(type: String, vararg parts: ByteArray): ByteArray {
        val body = ByteArrayOutputStream().also { out -> parts.forEach(out::write) }.toByteArray()
        return u32(8 + body.size) + type.toByteArray(Charsets.ISO_8859_1) + body
    }

    /** MP4 một track âm thanh như MediaMuxer ghi: `mdat` giữa, `moov` sau cùng; chunk đầu của track ở đầu `mdat`. */
    fun muxerFile(payload: ByteArray, file: File, durationMs: Int = 1000, wide: Boolean = false): Int {
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
}
