package vn.abook.player

import java.io.File
import java.io.OutputStream
import java.nio.ByteOrder
import java.nio.channels.FileChannel
import java.security.MessageDigest

/**
 * Bài nhạc đã giải mã cho bản xuất kèm nhạc nền, trên ĐĨA. Máy tính giữ PCM bài trong RAM (tới 768 MB); điện thoại không đủ (bài dài
 * nhất 59 phút mono 48 kHz = 340 MB) nên mỗi (bài, tần số, kênh) giải mã MỘT lần ra file thô 16-bit LE trong [dir], đọc ngẫu nhiên
 * qua `FileChannel.map` ([MusicRender.ShortPcm]). Dùng lại giữa các chương của một lượt xuất; quá [limitBytes] thì bỏ bài dùng lâu nhất
 * (không bao giờ bài vừa lấy); [close] xoá cả thư mục khi lượt xuất kết thúc (xong, lỗi hay dừng).
 *
 * Bài không giải mã được ([TrackDecoder.decode] ném lỗi hay không ra mẫu nào) = null, nhớ lại để không thử lần nữa trong lượt -
 * [MusicRender.renderBus] cho phần tử ấy im và báo tên bài.
 */
class TrackPcmCache(private val dir: File, private val decoder: TrackDecoder, private val limitBytes: Long = 1L shl 30) : AutoCloseable {
    /**
     * Giải mã `track` ra PCM 16-bit LE xen kẽ kênh ở đúng `rate`/`channels` vào `out` (Android: [M4bAudio.trackDecoder]). Bù gộp một kênh
     * không nằm ở đây: nó theo đoạn chương phát ([MusicExport.FoldOffset]).
     */
    fun interface TrackDecoder {
        fun decode(track: String, rate: Int, channels: Int, out: OutputStream)
    }

    private class Entry(val file: File, val pcm: MusicRender.Pcm, val bytes: Long)

    private val entries = LinkedHashMap<String, Entry>(16, 0.75f, true) // thứ tự truy cập: đầu = lâu nhất
    private val failed = HashSet<String>()
    private val leftovers = ArrayList<File>() // file bị bỏ mà hệ điều hành chưa cho xoá (Windows: còn map) - xoá ở [close]
    private var total = 0L

    /** Tổng byte các bài đang giữ. */
    val bytes: Long get() = total

    fun get(track: String, rate: Int, channels: Int): MusicRender.Pcm? {
        val key = "$track\u0000$rate\u0000$channels"
        entries[key]?.let { return it.pcm }
        if (key in failed) return null
        dir.mkdirs()
        val file = File(dir, "${name(track)}-$rate-$channels.pcm")
        val part = File(dir, file.name + ".part")
        val ok = try {
            part.outputStream().buffered(1 shl 16).use { decoder.decode(track, rate, channels, it) }
            part.length() >= 2L * channels && (file.delete() || !file.exists()) && part.renameTo(file)
        } catch (e: Exception) {
            false
        }
        if (!ok) {
            part.delete()
            failed.add(key)
            return null
        }
        val frames = file.length() / (2L * channels)
        val buffer = FileChannel.open(file.toPath()).use { channel ->
            channel.map(FileChannel.MapMode.READ_ONLY, 0, frames * 2 * channels).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
        }
        val entry = Entry(file, MusicRender.ShortPcm(buffer, channels), file.length())
        entries[key] = entry
        total += entry.bytes
        evict(keep = key)
        return entry.pcm
    }

    private fun evict(keep: String) {
        val iterator = entries.entries.iterator()
        while (total > limitBytes && iterator.hasNext()) {
            val (key, entry) = iterator.next()
            if (key == keep) continue
            iterator.remove()
            total -= entry.bytes
            if (!entry.file.delete()) leftovers.add(entry.file)
        }
    }

    /** Xoá mọi file của lượt xuất. Gọi một lần ở `finally`. */
    override fun close() {
        entries.clear()
        total = 0
        leftovers.clear()
        dir.listFiles()?.forEach { it.delete() }
        dir.delete()
    }

    private fun name(track: String): String =
        MessageDigest.getInstance("SHA-1").digest(track.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }

    companion object {
        /** Cỡ PCM của bài dài `seconds` ở `rate`/`channels` - cho ước lượng chỗ trống của bản xuất (bài lớn nhất x3). */
        fun bytesFor(seconds: Double, rate: Int, channels: Int): Long = Math.ceil(seconds * rate).toLong() * 2 * channels
    }
}

