package vn.abook.player

import java.io.File
import java.io.RandomAccessFile
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToLong

/**
 * Đường mã hoá của "Xuất M4B" cho sách đã có tiếng (đường S, K2_SPEC 3.1 + mục 4 bậc 2): MỖI CHƯƠNG MỘT BỘ MÃ HOÁ AAC, rồi nối các khung
 * AAC thành MỘT luồng liền như mã hoá liền cả cuốn - không lặng thêm ở chỗ nối, độ dài đúng từng mẫu (LLM_Train/music/mixqa/aac_join.py).
 *
 * Lưới khung chung: khung giải mã `u` phủ mẫu gốc [FRAME*u - D, FRAME*(u+1) - D) (D = [Codec.delay], độ trễ mã hoá + giải mã). Chỗ nối
 * chương k là biên khung gần nhất `f_k = rint((c_k + D) / FRAME)` (c_k = mẫu đầu chương; f_0 = 0). Bộ mã hoá của chương k nhận mẫu gốc
 * [FRAME*f_k - P, FRAME*f_{k+1} - D + Q) - đệm trước P = ceil((D + FRAME) / FRAME) * FRAME lấy từ chương trước, đệm sau Q = 2 khung lấy
 * từ chương sau - bỏ P / FRAME khung đầu, giữ đúng khung [f_k, f_{k+1}). Hai khung kề chỗ nối mã hoá cùng một tín hiệu nên chồng-cộng
 * MDCT khử răng cưa. Mục lục chương theo biên khung (lệch tối đa nửa khung so với mẫu đầu chương thật).
 *
 * Đỉnh thật sau mã hoá (chính sách của máy tính, export.py `m4b_from_files`): giải mã lại, đo [TruePeak] từng chương; chương vượt
 * `exportCeilingDbtp` thì hạ CỘNG DỒN `vượt + MARGIN_DB` dB ([lowerOver]) và mã hoá lại RIÊNG khung [f_k - 1, f_{k+1} + 1) của nó từ
 * tín hiệu đã hạ (lề một khung mỗi bên - aac_splice.py: không có lề thì khung cũ bên cạnh chồng lên tín hiệu chưa hạ), ghép vào chỗ cũ.
 * Tối đa [RETRIES] lượt, mỗi lượt chỉ tốn chương vượt; còn vượt thì vẫn xong và báo [Encoded.peakOver]. Chương không vượt: khung y nguyên.
 *
 * Phần này không biết gì về Android: giải mã / mã hoá / ghi MP4 là một [Codec] (MediaCodec: [M4bAudio]; test JVM: bộ giả).
 */
object AacJoin {
    /** Số mẫu PCM mỗi khung AAC-LC. */
    const val FRAME = 1024

    /** Đệm sau Q của mỗi mảnh: 2 khung lấy từ chương sau. */
    const val TAIL = 2 * FRAME

    /** Số lượt mã hoá lại tối đa (export.py `_PEAK_RETRIES`). */
    const val RETRIES = 4

    /** Hạ thêm chừng này dB quá phần vượt (export.py `_PEAK_MARGIN_DB`). */
    const val MARGIN_DB = 0.1

    /** Đệm trước P: bội FRAME, đủ phủ độ trễ D và một khung chồng-cộng. */
    fun lead(delay: Int): Int = (delay + FRAME + FRAME - 1) / FRAME * FRAME

    /** Biên khung của chỗ nối ở mẫu gốc `sample` (rint = chẵn gần nhất, như `round` của Python). */
    fun boundary(sample: Long, delay: Int): Int = Math.rint((sample + delay).toDouble() / FRAME).toInt()

    /** Số khung của cả luồng `samples` mẫu (như mã hoá liền: phủ hết mẫu cộng độ trễ). */
    fun units(samples: Long, delay: Int): Int = ((samples + delay + FRAME - 1) / FRAME).toInt()

    /** Mép giữ lại của mỗi chương (đầu và cuối, mẫu): đủ cho đệm của lần mã hoá lại chương kề, kể cả lề một khung. */
    fun edge(delay: Int): Int = lead(delay) + TAIL + 2 * FRAME

    /**
     * Chương có đỉnh vượt `ceiling`: `lowered[i] += đỉnh - trần + MARGIN_DB` (CỘNG DỒN - chương đã hạ ở lượt trước giữ mức ấy, lượt này chỉ
     * hạ thêm; mức chỉ giảm nên hội tụ). Trả chỉ số các chương vượt. Chung cho đường S (cả cuốn) và đường L (từng chương).
     */
    fun lowerOver(peaks: DoubleArray, ceiling: Double, lowered: DoubleArray): List<Int> {
        val over = peaks.indices.filter { peaks[it] > ceiling }
        for (index in over) lowered[index] += peaks[index] - ceiling + MARGIN_DB
        return over
    }

    /** Bộ giải mã / mã hoá / ghi MP4 của một lượt xuất. */
    interface Codec {
        /** Độ trễ mã hoá + giải mã (mẫu): tiếng ra khỏi bộ giải mã trễ chừng này so với tiếng vào bộ mã hoá. */
        val delay: Int

        /** (tần số, số kênh 1|2) của file chương. */
        fun layout(file: File): Pair<Int, Int>

        /** Giải mã file chương ra PCM 16-bit xen kẽ ở (`rate`, `channels`), từng khối `write(mẫu, số mẫu)`; `fraction(0..1)` theo vị trí đọc. */
        fun decode(file: File, rate: Int, channels: Int, stopped: () -> Boolean, fraction: (Double) -> Unit, write: (ShortArray, Int) -> Unit)

        /** Một bộ mã hoá AAC-LC: PCM vào, từng khung AAC (không kể khối cấu hình) ra `unit` theo thứ tự. */
        fun encoder(rate: Int, channels: Int, unit: (ByteArray) -> Unit): ListenExport.PcmOutput

        /** Giải mã các khung `units` (của chính bộ mã hoá này, từ khung bất kỳ): đúng FRAME khung PCM mỗi khung AAC, theo thứ tự. */
        fun decodeUnits(units: Iterator<ByteArray>, rate: Int, channels: Int, stopped: () -> Boolean, write: (ShortArray, Int) -> Unit)

        /** Ghi các khung thành file MP4 một track (`target`), khung thứ i ở mốc i * FRAME mẫu. */
        fun mux(target: File, rate: Int, channels: Int, units: Iterator<ByteArray>, stopped: () -> Boolean)
    }

    /** Tin pha cho giao diện: "music" (trộn nhạc chương `chapter`, từ 1), "peaks" (đo đỉnh, lượt `round`), "reencode" (mã hoá lại lượt
     *  `round` vì `over` chương vượt); null = mã hoá thường. */
    fun interface Watch {
        fun phase(name: String?, chapter: Int, round: Int, over: Int)
    }

    /** Mốc chương cho [Mp4Finish] và các chương còn vượt trần sau [RETRIES] lượt: (chương từ 1, dBTP). */
    class Encoded(val marks: List<Mp4Finish.Mark>, val peakOver: List<Pair<Int, Double>>)

    /**
     * Kho khung AAC của luồng cả cuốn: file ghi nối (khung thay thế ghi thêm ở cuối) + chỉ mục khung -> chỗ trong file. [close] xoá file.
     */
    class Units(private val file: File) : AutoCloseable {
        private val data = RandomAccessFile(file, "rw")
        private var offsets = LongArray(4096)
        private var sizes = IntArray(4096)
        private var length = 0L

        fun put(index: Int, unit: ByteArray) {
            require(unit.isNotEmpty()) { "khung AAC rỗng" }
            if (index >= sizes.size) {
                val grown = max(index + 1, sizes.size * 2)
                offsets = offsets.copyOf(grown)
                sizes = sizes.copyOf(grown)
            }
            data.seek(length)
            data.write(unit)
            offsets[index] = length
            sizes[index] = unit.size
            length += unit.size
        }

        fun has(index: Int): Boolean = index in sizes.indices && sizes[index] > 0

        operator fun get(index: Int): ByteArray {
            check(has(index)) { "thiếu khung $index" }
            val out = ByteArray(sizes[index])
            data.seek(offsets[index])
            data.readFully(out)
            return out
        }

        fun range(from: Int, to: Int): Iterator<ByteArray> = (from until to).asSequence().map { get(it) }.iterator()

        override fun close() {
            runCatching { data.close() }
            file.delete()
        }
    }

    /** Ống PCM chỉ chuyển tiếp (cho [MusicExport.Mixer.wrap]). */
    private class Pass(private val write: (ShortArray, Int) -> Unit, private val channels: Int) : ListenExport.PcmOutput {
        override var frames = 0L
            private set

        override fun write(pcm: ShortArray, count: Int) {
            write.invoke(pcm, count)
            frames += count / channels
        }

        override fun finish() {}
        override fun abort() {}
    }

    /**
     * Cả cuốn `plan` thành MP4 trần `target` (khung AAC liền, mục lục do [Mp4Finish] ghi sau). `plan.music`: chương có nhạc được trộn
     * trước khi mã hoá; `plan.guard`: hằng số đo đỉnh (null = không kiểm đỉnh). `progress(chương đã xong, tổng, phần 0..1 của lượt đầu)`.
     */
    fun encode(plan: Mp3Export.Plan, target: File, codec: Codec, stopped: () -> Boolean, progress: (Int, Int, Double) -> Unit,
               watch: Watch = Watch { _, _, _, _ -> }): Encoded {
        val units = Units(File(target.path + ".units"))
        try {
            return Book(plan, codec, units, stopped, progress, watch).run(target)
        } finally {
            units.close()
        }
    }

    private class Book(
        private val plan: Mp3Export.Plan,
        private val codec: Codec,
        private val units: Units,
        private val stopped: () -> Boolean,
        private val progress: (Int, Int, Double) -> Unit,
        private val watch: Watch,
    ) {
        private val n = plan.chapters.size
        private val delay = codec.delay
        private val lead = lead(delay)
        private val skip = lead / FRAME
        private val keep = edge(delay)
        private val rate: Int
        private val channels: Int
        private val starts = LongArray(n + 1)   // mẫu đầu từng chương (c_k), starts[n] = cả luồng
        private val bounds = IntArray(n + 1)    // khung đầu từng chương (f_k), bounds[n] = số khung
        private val heads = arrayOfNulls<ShortArray>(n)
        private val tails = arrayOfNulls<ShortArray>(n)
        private val lowered = DoubleArray(n)
        private val open = ArrayList<Piece>()

        init {
            val (r, c) = codec.layout(plan.chapters.first().file)
            rate = r
            channels = c
        }

        /** Một bộ mã hoá cho khung [first, last) (last chưa biết = MAX), nhận mẫu gốc [start, end). */
        private inner class Piece(val first: Int, val start: Long) {
            var last = Int.MAX_VALUE
            var end = Long.MAX_VALUE
            var fed = start
            var written = 0
            private var emitted = 0
            val encoder: ListenExport.PcmOutput = codec.encoder(rate, channels) { unit ->
                val index = first + emitted++ - skip
                if (index >= first && index < last) {
                    units.put(index, unit)
                    written++
                }
            }

            /** Mẫu gốc [at, at + frames) nằm trong `pcm`: phần thuộc [fed, end) vào bộ mã hoá. */
            fun feed(pcm: ShortArray, at: Long, frames: Int) {
                val from = max(fed, at)
                val to = min(end, at + frames)
                if (to <= from) return
                val offset = ((from - at) * channels).toInt()
                val count = ((to - from) * channels).toInt()
                encoder.write(if (offset == 0) pcm else pcm.copyOfRange(offset, offset + count), count)
                fed = to
            }

            /** Phần trước mẫu 0 của luồng (chương đầu, hay đệm trước dài hơn các chương trước): lặng. */
            fun silenceBefore(zero: Long) {
                var left = min(zero, end) - fed
                val block = ShortArray(FRAME * channels)
                while (left > 0) {
                    val take = min(left, FRAME.toLong()).toInt()
                    feed(block, fed, take)
                    left -= take
                }
            }
        }

        private var position = 0L // mẫu gốc đã qua

        /** Vòng giữ [keep] mẫu cuối của luồng: đệm trước của chương mới, mép cuối của chương vừa xong. */
        private val history = ShortArray(keep * channels)

        private fun remember(pcm: ShortArray, count: Int) {
            val size = history.size
            var i = 0
            var at = ((position * channels) % size).toInt()
            while (i < count) {
                val take = min(count - i, size - at)
                System.arraycopy(pcm, i, history, at, take)
                i += take
                at = (at + take) % size
            }
        }

        /** Mẫu gốc [from, to) vừa qua (phải còn trong vòng). */
        private fun recent(from: Long, to: Long): ShortArray {
            val size = history.size
            val out = ShortArray(((to - from) * channels).toInt())
            check(from >= 0 && (position - from) * channels <= size && to <= position) { "vòng đệm không đủ" }
            var at = ((from * channels) % size).toInt()
            var i = 0
            while (i < out.size) {
                val take = min(out.size - i, size - at)
                System.arraycopy(history, at, out, i, take)
                i += take
                at = (at + take) % size
            }
            return out
        }

        /** PCM của chương `index` (đã trộn nhạc nếu có) đổ vào `write`. */
        private fun render(index: Int, fraction: (Double) -> Unit, write: (ShortArray, Int) -> Unit) {
            val chapter = plan.chapters[index]
            val mixer = plan.music
            if (mixer != null && mixer.has(chapter.id)) {
                val mixed = mixer.wrap(chapter.id, Pass(write, channels), rate, channels, null)
                codec.decode(chapter.file, rate, channels, stopped, fraction) { pcm, count -> mixed.write(pcm, count) }
                mixed.finish()
            } else {
                codec.decode(chapter.file, rate, channels, stopped, fraction, write)
            }
        }

        private fun finishPassed() {
            val done = open.filter { it.fed >= it.end }
            for (piece in done) {
                piece.encoder.finish()
                open.remove(piece)
            }
        }

        fun run(target: File): Encoded {
            try {
                firstPass()
                val left = peaks()
                if (stopped()) throw Mp3Export.Stopped()
                codec.mux(target, rate, channels, units.range(0, bounds[n]), stopped)
                return Encoded(marks(), left)
            } catch (error: Throwable) {
                for (piece in open) runCatching { piece.encoder.abort() }
                open.clear()
                target.delete()
                throw error
            }
        }

        // ---- lượt đầu: mỗi chương một bộ mã hoá, nạp liền luồng PCM -------------------------------------------------------------

        private fun firstPass() {
            val weights = plan.chapters.map { it.duration.coerceAtLeast(0.0) }
            val weighted = weights.sum() > 0.0
            val sum = if (weighted) weights.sum() else n.toDouble()
            val shares = weights.map { (if (weighted) it else 1.0) / sum }
            var before = 0.0
            progress(0, n, 0.0)
            for (index in 0 until n) {
                if (stopped()) throw Mp3Export.Stopped()
                starts[index] = position
                bounds[index] = if (index == 0) 0 else max(bounds[index - 1], boundary(position, delay))
                if (index > 0) {
                    val previous = open.last()
                    previous.last = bounds[index]
                    previous.end = FRAME.toLong() * bounds[index] - delay + TAIL
                    finishPassed()
                }
                val piece = Piece(bounds[index], FRAME.toLong() * bounds[index] - lead)
                open += piece
                piece.silenceBefore(0)
                if (piece.fed < position) {
                    val from = piece.fed
                    piece.feed(recent(from, position), from, (position - from).toInt())
                }
                val music = plan.music?.has(plan.chapters[index].id) == true
                watch.phase(if (music) "music" else null, index + 1, 0, 0)
                val head = ArrayList<ShortArray>()
                var headFrames = 0
                val base = before
                render(index, { fraction -> progress(index, n, (base + shares[index] * fraction).coerceAtMost(0.99)) }) { pcm, count ->
                    val frames = count / channels
                    if (frames > 0) {
                        val block = if (count == pcm.size) pcm else pcm.copyOf(count)
                        for (piece in open.toList()) piece.feed(block, position, frames)
                        if (headFrames < keep) {
                            val take = min(frames, keep - headFrames)
                            head += block.copyOf(take * channels)
                            headFrames += take
                        }
                        remember(block, count)
                        position += frames
                        finishPassed()
                    }
                }
                heads[index] = concat(head)
                tails[index] = recent(max(starts[index], position - keep), position)
                before += shares[index]
                progress(index + 1, n, before.coerceAtMost(0.99))
            }
            starts[n] = position
            if (position == 0L) throw Mp3Export.Refused("Không có âm thanh nào để ghi")
            val total = units(position, delay)
            bounds[n] = total
            for (index in 1 until n) bounds[index] = min(bounds[index], total)
            open.lastOrNull()?.last = total
            for (piece in open.toList()) {
                piece.encoder.finish()
                open.remove(piece)
            }
            // Bộ mã hoá có thể xả thiếu khung cuối (không đủ đệm sau ở cuối luồng): luồng ngắn lại chừng ấy; thiếu ở giữa là hỏng.
            val missing = (0 until total).firstOrNull { !units.has(it) } ?: total
            if (missing < total) {
                if (missing <= bounds[n - 1] || (missing until total).any { units.has(it) }) {
                    throw Mp3Export.Refused("Bộ mã hoá AAC bỏ sót một đoạn - xuất lại")
                }
                bounds[n] = missing
            }
        }

        private fun concat(parts: List<ShortArray>): ShortArray {
            val out = ShortArray(parts.sumOf { it.size })
            var at = 0
            for (part in parts) {
                System.arraycopy(part, 0, out, at, part.size)
                at += part.size
            }
            return out
        }

        // ---- đỉnh thật sau mã hoá ------------------------------------------------------------------------------------------------

        // Mỗi chương ba đoạn đo: đầu (4 khung), thân, cuối (3 khung) - ghép một chương chỉ đổi khung cuối của chương trước và khung đầu của
        // chương sau (lề một khung, chồng-cộng và chân bộ lọc), nên đo lại chỉ cần đoạn đầu/cuối của chương kề, không cả chương.
        private val segStarts = IntArray(3 * n)
        private val segPeaks = DoubleArray(3 * n) { Double.NEGATIVE_INFINITY }

        private fun layoutSegments() {
            for (k in 0 until n) {
                val f0 = bounds[k]
                val f1 = bounds[k + 1]
                val headEnd = min(f0 + 4, f1)
                val tailStart = max(headEnd, f1 - 3)
                segStarts[3 * k] = f0
                segStarts[3 * k + 1] = headEnd
                segStarts[3 * k + 2] = tailStart
            }
        }

        private fun segEnd(index: Int): Int = if (index + 1 < segStarts.size) segStarts[index + 1] else bounds[n]

        /** Giải mã lại đủ khung và đo các đoạn [from, to); hai khung trước làm nóng bộ giải mã + chân bộ lọc, một khung sau cho chân bộ lọc. */
        private fun measure(from: Int, to: Int) {
            val begin = max(0, segStarts[from] - 2)
            val finish = min(bounds[n], segEnd(to - 1) + 1)
            val marks = LongArray(to - from + 2)
            marks[0] = 0
            for (i in from until to) marks[i - from + 1] = (segStarts[i] - begin).toLong() * FRAME
            marks[to - from + 1] = (segEnd(to - 1) - begin).toLong() * FRAME
            val meter = TruePeak(plan.guard!!, channels, marks)
            codec.decodeUnits(units.range(begin, finish), rate, channels, stopped) { pcm, count -> meter.feed(pcm, count) }
            val found = meter.finish()
            for (i in from until to) segPeaks[i] = found[i - from + 1]
        }

        private fun chapterPeak(k: Int): Double = max(segPeaks[3 * k], max(segPeaks[3 * k + 1], segPeaks[3 * k + 2]))

        private fun peaks(): List<Pair<Int, Double>> {
            val guard = plan.guard ?: return emptyList()
            layoutSegments()
            watch.phase("peaks", 0, 0, 0)
            measure(0, segStarts.size)
            for (round in 1..RETRIES) {
                val over = lowerOver(DoubleArray(n) { chapterPeak(it) }, guard.ceilingDbtp, lowered)
                if (over.isEmpty()) break
                watch.phase("reencode", 0, round, over.size)
                for (k in over) splice(k)
                watch.phase("peaks", 0, round, 0)
                for (k in over) remeasure(k)
            }
            return (0 until n).filter { chapterPeak(it) > guard.ceilingDbtp }.map { it + 1 to chapterPeak(it) }
        }

        /** Đo lại sau khi ghép chương k: mọi đoạn chạm khung [f_k - 3, f_{k+1} + 4). */
        private fun remeasure(k: Int) {
            val low = max(0, bounds[k] - 3)
            val high = min(bounds[n], bounds[k + 1] + 4)
            var from = 0
            while (from + 1 < segStarts.size && segStarts[from + 1] <= low) from++
            var to = from + 1
            while (to < segStarts.size && segStarts[to] < high) to++
            measure(from, to)
        }

        // ---- mã hoá lại một chương ----------------------------------------------------------------------------------------------

        /** Hạ mức của các chương đã hạ trên khối mẫu gốc [at, at + frames): chương k là vùng khung của nó [FRAME*f_k - D, FRAME*f_{k+1} - D). */
        private fun lowered(pcm: ShortArray, count: Int, at: Long): ShortArray {
            val out = pcm.copyOf(count)
            val frames = count / channels
            for (k in 0 until n) {
                if (lowered[k] == 0.0) continue
                val from = if (k == 0) Long.MIN_VALUE else FRAME.toLong() * bounds[k] - delay
                val to = if (k == n - 1) Long.MAX_VALUE else FRAME.toLong() * bounds[k + 1] - delay
                val a = max(from, at)
                val b = min(to, at + frames)
                if (b <= a) continue
                TruePeak.lower(out, lowered[k], ((b - a) * channels).toInt(), ((a - at) * channels).toInt())
            }
            return out
        }

        /**
         * Mã hoá lại khung [f_k - 1, f_{k+1} + 1) từ tín hiệu ĐÃ HẠ (mọi chương theo mức hiện tại): chương k giải mã (và trộn) lại, đệm từ
         * mép đã giữ của chương kề; khung mới thay khung cũ.
         */
        private fun splice(k: Int) {
            if (stopped()) throw Mp3Export.Stopped()
            val total = bounds[n]
            val first = max(0, bounds[k] - 1)
            val last = min(total, bounds[k + 1] + 1)
            val piece = Piece(first, FRAME.toLong() * first - lead)
            piece.last = last
            val end = min(starts[n], FRAME.toLong() * last - delay + TAIL)
            piece.end = end
            open += piece
            piece.silenceBefore(0)
            for (j in 0 until n) {
                val from = max(piece.start, starts[j])
                val to = min(end, starts[j + 1])
                if (to <= from) continue
                if (j == k || !edgeCovers(j, from, to)) {
                    var at = starts[j]
                    render(j, {}) { pcm, count ->
                        val frames = count / channels
                        if (frames > 0 && at + frames > from && at < to) piece.feed(lowered(pcm, count, at), at, frames)
                        at += frames
                    }
                } else {
                    feedEdge(piece, j, from, to)
                }
            }
            piece.encoder.finish()
            open.remove(piece)
            if (piece.written < last - first) throw Mp3Export.Refused("Bộ mã hoá AAC bỏ sót một đoạn - xuất lại")
        }

        private fun edgeCovers(j: Int, from: Long, to: Long): Boolean {
            val length = starts[j + 1] - starts[j]
            val head = heads[j]!!.size / channels
            val tail = tails[j]!!.size / channels
            return to - starts[j] <= head || from - starts[j] >= length - tail
        }

        private fun feedEdge(piece: Piece, j: Int, from: Long, to: Long) {
            val length = starts[j + 1] - starts[j]
            val head = heads[j]!!
            val tail = tails[j]!!
            val (source, origin) = if (to - starts[j] <= head.size / channels) head to starts[j] else tail to starts[j] + length - tail.size / channels
            val offset = ((from - origin) * channels).toInt()
            val count = ((to - from) * channels).toInt()
            val block = source.copyOfRange(offset, offset + count)
            piece.feed(lowered(block, count, from), from, (to - from).toInt())
        }

        // ---- mục lục -------------------------------------------------------------------------------------------------------------

        /** Chương k bắt đầu ở khung f_k = mẫu gốc FRAME*f_k - D (chương đầu ở 0); chương cuối hết ở hết luồng. */
        private fun marks(): List<Mp4Finish.Mark> = (0 until n).map { k ->
            val start = max(0L, FRAME.toLong() * bounds[k] - delay)
            val end = if (k + 1 < n) max(0L, FRAME.toLong() * bounds[k + 1] - delay) else starts[n]
            Mp4Finish.Mark(plan.chapters[k].fullTitle, millis(start), millis(end))
        }

        private fun millis(samples: Long) = (samples * 1000.0 / rate).roundToLong()
    }
}
