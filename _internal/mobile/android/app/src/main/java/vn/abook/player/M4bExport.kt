package vn.abook.player

import java.io.File
import java.io.FilterOutputStream
import java.io.OutputStream

/**
 * "Xuất M4B cho app sách nói" trên điện thoại - cùng bản xuất với máy tính (webui/export.py `export_m4b`): cả cuốn trong MỘT file
 * `<tên sách>.m4b`, AAC, mỗi chương một mục (tên chương thật), bìa và tag. Chỉ chương nghe được, như mọi kiểu xuất - việc chọn chương, tên,
 * bìa dùng chung [Mp3Export.plan].
 *
 * Audio chương trong sách trên điện thoại luôn là MP3 nên mỗi chương được giải mã ra PCM rồi đổ liên tục vào MỘT bộ mã hoá AAC ([M4bAudio]
 * - MediaCodec/MediaMuxer có sẵn của Android, không thêm thư viện vào app): mốc chương đếm theo số mẫu đi qua nên đúng tới từng mẫu, không
 * có khoảng câm hay lệch như nối các đoạn AAC mã hoá riêng. Lượt hai ([Mp4Finish]) chép luồng sang file cuối kèm mục lục chương, tag, bìa.
 *
 * Phần này không biết gì về Android: bộ mã hoá là một [AudioEncoder], nơi ghi là một [OutputStream].
 */
object M4bExport {
    /** Bộ mã hoá cả cuốn: ghi luồng AAC của `plan` vào `target` (MP4 trần) và trả mốc từng chương. Dừng thì ném [Mp3Export.Stopped]. */
    fun interface AudioEncoder {
        /** `progress(số chương đã xong, tổng, phần đã làm 0..1 của cả cuốn)`. */
        fun encode(plan: Mp3Export.Plan, target: File, stopped: () -> Boolean, progress: (Int, Int, Double) -> Unit): List<Mp4Finish.Mark>

        /** Số mẫu đầu luồng là độ trễ của bộ mã hoá (không phải tiếng): file ghi bảng cắt để trình phát bỏ qua, mốc chương mới khớp tiếng. */
        val delay: Int get() = 0
    }

    class Result(val name: String, val size: Long, val chapters: Int, val chaptersTotal: Int)

    /** Tên file mặc định: "<tên sách>.m4b" (cùng `safe_name` với máy tính). */
    fun fileName(title: String): String = Mp3Export.bookFileName(title, ".m4b")

    /**
     * Chỗ trống cần cho file trung gian (AAC mono 64 kb/s theo thời lượng các chương, dư 25% vì thời lượng trong sách chỉ là ước lượng,
     * cộng ít byte cho phần đầu cuối). Sách stereo cần nhiều hơn, nhưng hết chỗ thật sự vẫn được bắt ở lúc ghi.
     */
    fun estimatedBytes(plan: Mp3Export.Plan): Long = (plan.chapters.sumOf { it.duration } * 8000 * 1.25).toLong() + (16L shl 20)

    private class Counting(out: OutputStream) : FilterOutputStream(out) {
        var written = 0L
        override fun write(b: Int) {
            out.write(b)
            written++
        }

        override fun write(b: ByteArray, off: Int, len: Int) {
            out.write(b, off, len)
            written += len
        }
    }

    /**
     * Làm file M4B của `plan` ghi vào `out` (người gọi mở và đóng; hỏng hay dừng giữa chừng thì người gọi xoá phần dở). `work` là file
     * trung gian, luôn xoá khi xong. `progress` như [AudioEncoder.encode]; `stopped` được hỏi suốt lúc mã hoá và lúc chép.
     */
    fun run(plan: Mp3Export.Plan, work: File, out: OutputStream, encoder: AudioEncoder, progress: (Int, Int, Double) -> Unit = { _, _, _ -> },
            stopped: () -> Boolean = { false }): Result {
        try {
            val marks = encoder.encode(plan, work, stopped, progress)
            val counted = Counting(out)
            Mp4Finish.finish(work, counted, Mp4Finish.Tags(plan.title, plan.narrator, plan.cover), marks, encoder.delay, stopped)
            counted.flush()
            progress(plan.chapters.size, plan.chapters.size, 1.0)
            return Result(fileName(plan.title), counted.written, marks.size, plan.chaptersTotal)
        } finally {
            work.delete()
        }
    }

    /**
     * Đổi PCM 16-bit xen kẽ từ (`fromRate`, `fromChannels`) sang (`toRate`, `toChannels` = 1|2) từng khối một. Kênh: 2 -> 1 lấy trung
     * bình, 1 -> 2 nhân đôi, hơn hai kênh chỉ dùng hai kênh đầu. Tần số khác nhau (hiếm: các chương của một cuốn thường cùng một bộ
     * máy đọc) nội suy tuyến tính - cho tiếng nói là đủ; cùng tần số thì không đụng tới mẫu.
     */
    class PcmConverter(private val fromRate: Int, private val fromChannels: Int, private val toRate: Int, private val toChannels: Int) {
        private val step = fromRate.toDouble() / toRate
        private var carry: FloatArray? = null
        private var base = 0L // chỉ số (toàn cục) của khung đầu tiên trong "carry + khối mới"
        private var next = 0.0 // vị trí (toàn cục, theo khung nguồn) của mẫu ra kế tiếp

        /** `count` mẫu đầu của `src` (mọi kênh của một khung liền nhau, `count` chia hết cho `fromChannels`). */
        fun convert(src: ShortArray, count: Int): ShortArray {
            val frames = count / fromChannels
            val mixed = FloatArray(frames * toChannels)
            for (frame in 0 until frames) {
                val left = src[frame * fromChannels].toFloat()
                val right = if (fromChannels > 1) src[frame * fromChannels + 1].toFloat() else left
                if (toChannels == 1) {
                    mixed[frame] = if (fromChannels > 1) (left + right) / 2f else left
                } else {
                    mixed[frame * 2] = left
                    mixed[frame * 2 + 1] = right
                }
            }
            if (fromRate == toRate) return ShortArray(mixed.size) { clip(mixed[it]) }
            val held = carry
            val all = if (held == null) mixed else held + mixed
            val total = all.size / toChannels
            val out = ArrayList<Short>(frames * toRate / fromRate + 2)
            while (true) {
                val whole = Math.floor(next).toLong()
                val at = (whole - base).toInt()
                if (at + 1 >= total) break
                val fraction = (next - whole).toFloat()
                for (channel in 0 until toChannels) {
                    val a = all[at * toChannels + channel]
                    val b = all[(at + 1) * toChannels + channel]
                    out += clip(a + (b - a) * fraction)
                }
                next += step
            }
            carry = all.copyOfRange((total - 1) * toChannels, total * toChannels)
            base += total - 1
            return out.toShortArray()
        }

        private fun clip(value: Float): Short = Math.round(value).coerceIn(-32768, 32767).toShort()
    }
}
