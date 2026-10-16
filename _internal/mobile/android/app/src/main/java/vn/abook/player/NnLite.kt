package vn.abook.player

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.text.Normalizer
import java.util.Locale
import kotlin.math.ln1p
import kotlin.math.sqrt

/** Mục học sinh của MỘT đoạn nhạc (`ChapterStudent.chapter` / `music_nnlite.Model.chapter_items`): độ lệch V / E / T trong chương và mức V của chương. */
class StudentItem(
    val chapterId: Int,
    val firstSegment: Int,
    val lastSegment: Int,
    val dV: Double,
    val dE: Double,
    val dT: Double,
    /** Cùng giá trị ở mọi đoạn của chương; null = học sinh không có đầu mức chương (mức V về nhãn câu). */
    val chapterV: Double?,
    /** (pV, pE, pT, q) THÔ của chương (trung bình theo [weight], chưa cộng `c_c`), cùng giá trị ở mọi đoạn; null = mục không có (LVJ không chạy). */
    val chapterP: DoubleArray? = null,
)

/**
 * NN-lite - bản Kotlin của `music_nnlite.py` (Corpus research/music/SPEC_nnlite_app.md): học sinh nhỏ (2 MB, chỉ chữ) cho nhạc nền theo cảnh khi máy không có gói q06.
 * Cùng file `nnlite.bin` (asset `abook/webui/assets/nnlite.bin`, dùng chung với máy tính) và PHẢI ra cùng số: bộ ví dụ `tests/fixtures/music/nnlite/` (token và ô băm
 * tuyệt đối, đặc trưng sai < 1e-12, 4 số và mục chương sai < 1e-3).
 *
 * Chữ -> đặc trưng định nghĩa theo ĐIỂM MÃ, không theo đơn vị UTF-16: mọi vòng duyệt ở đây đi bằng `codePointAt`. Phép tính sau khi đọc file là Double; trọng số fp16 giải mã
 * bằng [halfToDouble] (không dùng `android.util.Half` để bài thử JVM chạy được).
 */
class NnLite private constructor(
    private val buckets: Int,
    /** Wh: hàng = ô băm, cột pV, pE, pT, q - giữ fp16 (2 MB), giải mã khi dùng. */
    private val wh: ShortArray,
    private val wd: DoubleArray,
    private val b: DoubleArray,
    private val dmu: DoubleArray,
    private val dsd: DoubleArray,
    private val ymu: DoubleArray,
    private val ysd: DoubleArray,
    private val c: DoubleArray,
    private val cC: Double,
) {
    /** (pV, pE, pT, q) thang thầy của chữ một cảnh. */
    fun scene(text: String): DoubleArray {
        val z = b.copyOf()
        val found = features(text, buckets)
        for ((slot, value) in found) for (column in 0 until N_OUT) z[column] += value * halfToDouble(wh[slot * N_OUT + column].toInt())
        val d = dense(text)
        for (column in 0 until N_OUT) {
            var sum = 0.0
            for (row in 0 until N_DENSE) sum += (d[row] - dmu[row]) / dsd[row] * wd[row * N_OUT + column]
            z[column] += sum
        }
        return DoubleArray(N_OUT) { z[it] * ysd[it] + ymu[it] }
    }

    /**
     * dV, dE, dT (căn giữa theo trọng số [weight] rồi cộng `c`; chương một cảnh: 0), chapterV và chapterP (pV, pE, pT, q thô của chương, cho LVJ) của MỘT chương theo thứ tự cảnh:
     * mỗi cảnh `[dV, dE, dT, chapterV, pV, pE, pT, q]`.
     */
    fun chapter(texts: List<String>): List<DoubleArray> {
        if (texts.isEmpty()) return emptyList()
        val y = texts.map { scene(it) }
        val w = texts.map { weight(it).toDouble() }
        var total = 0.0
        for (value in w) total += value
        val mean = DoubleArray(4)
        for (axis in 0 until 4) {
            var sum = 0.0
            for (index in y.indices) sum += w[index] * y[index][axis]
            mean[axis] = sum / total
        }
        val level = mean[3] + cC
        return y.map { row ->
            if (y.size < 2) doubleArrayOf(0.0, 0.0, 0.0, level, mean[0], mean[1], mean[2], mean[3])
            else doubleArrayOf(row[0] - mean[0] + c[0], row[1] - mean[1] + c[1], row[2] - mean[2] + c[2], level, mean[0], mean[1], mean[2], mean[3])
        }
    }

    /**
     * Mục học sinh của từng đoạn `scenes` của chương (đoạn của đường N0, [SceneScenes.chapterScenes]); null khi có đoạn không khớp câu của chương (`music_moods.scene_texts`):
     * chương ấy đi đường N0.
     */
    fun chapterItems(chapterId: Int, segments: List<SceneSegment>, scenes: List<SceneScene>): List<StudentItem>? {
        if (scenes.isEmpty()) return null
        val position = HashMap<Int, Int>()
        for ((index, segment) in segments.withIndex()) position[segment.id] = index // trùng id: câu sau thắng (dict của Python)
        val texts = ArrayList<String>()
        for (scene in scenes) {
            val first = position[scene.firstSegment] ?: return null
            val last = position[scene.lastSegment] ?: return null
            texts.add(sceneText(segments, first, last))
        }
        return chapter(texts).mapIndexed { index, item ->
            StudentItem(chapterId, scenes[index].firstSegment, scenes[index].lastSegment, item[0], item[1], item[2], item[3], doubleArrayOf(item[4], item[5], item[6], item[7]))
        }
    }

    /** Hồ sơ từng khối (`music_nnlite.Model.block_profile`): (pV, pE, pT) của chữ khối chia độ lệch chuẩn đích `ysd`. */
    fun blockProfile(segments: List<SceneSegment>, spans: List<Pair<Int, Int>>): List<DoubleArray> =
        spans.map { (first, last) ->
            val y = scene(sceneText(segments, first, last))
            DoubleArray(3) { y[it] / ysd[it] }
        }

    /** `id` câu đầu mỗi khối mở đoạn mới, trừ đoạn đầu (LB, `music_nnlite.Model.scene_bounds`), theo thứ tự chương. */
    fun boundIds(segments: List<SceneSegment>): List<Int> {
        val spans = blocks(segments)
        return partition(blockProfile(segments, spans)).map { segments[spans[it].first].id }
    }

    /** Nguồn ranh "lite" của [SceneBook.chapterScenes] (`music_nnlite.scene_bounds`): {id câu mở cảnh mới: "mood_shift"}. */
    fun sceneBounds(segments: List<SceneSegment>): Map<Int, String> {
        val out = LinkedHashMap<Int, String>()
        for (id in boundIds(segments)) out[id] = LB_REASON
        return out
    }

    companion object {
        const val N_OUT = 4
        const val N_DENSE = 4
        /** LB (SPEC_lb_app mục 2): phạt mỗi ranh, chữ tối thiểu một khối, khối tối thiểu một đoạn; tên nguồn ranh và lý do của đoạn mới. */
        const val LB_LAMBDA = 2.0
        const val LB_BLOCK_WORDS = 150
        const val LB_MIN_BLOCKS = 2
        const val LB_SOURCE = "lite"
        const val LB_REASON = "mood_shift"
        private val MAGIC = byteArrayOf('N'.code.toByte(), 'N'.code.toByte(), 'L'.code.toByte(), '1'.code.toByte())
        private const val FNV_OFFSET = 2166136261L
        private const val FNV_PRIME = 16777619L

        private val WORD_TYPES = setOf(
            Character.UPPERCASE_LETTER, Character.LOWERCASE_LETTER, Character.TITLECASE_LETTER, Character.MODIFIER_LETTER, Character.OTHER_LETTER,
            Character.NON_SPACING_MARK, Character.COMBINING_SPACING_MARK, Character.DECIMAL_DIGIT_NUMBER, Character.LETTER_NUMBER, Character.OTHER_NUMBER,
        ).map { it.toInt() }.toSet()
        internal val PUNCT: Set<Int> = "!?…\"“”«»—–-~".codePoints().toArray().toSet()
        internal val DIALOG: Set<Int> = "\"“«-–—".codePoints().toArray().toSet()

        /** Đọc `nnlite.bin`; ném [IllegalArgumentException] khi sai magic / hình / cỡ (người gọi coi như không có model và quay về N0). */
        fun parse(raw: ByteArray): NnLite {
            require(raw.size >= 16 && MAGIC.indices.all { raw[it] == MAGIC[it] }) { "không phải file NN-lite" }
            val head = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN)
            val buckets = head.getInt(4).toLong() and 0xFFFFFFFFL
            require(head.getInt(8) == N_OUT && head.getInt(12) == N_DENSE) { "hình model lạ" }
            val tail = N_DENSE * N_OUT + 5 * N_OUT + 3 + 1
            require(buckets in 1..(Int.MAX_VALUE / N_OUT).toLong() && 16L + buckets * N_OUT * 2 + tail * 4 == raw.size.toLong()) { "cỡ file sai" }
            val count = buckets.toInt()
            val wh = ShortArray(count * N_OUT)
            head.position(16)
            head.asShortBuffer().get(wh)
            val floats = head.position(16 + count * N_OUT * 2).let { head.asFloatBuffer() }
            val rest = DoubleArray(tail) { floats.get(it).toDouble() }
            fun part(from: Int, size: Int) = rest.copyOfRange(from, from + size)
            val wd = part(0, N_DENSE * N_OUT)
            val base = N_DENSE * N_OUT
            return NnLite(
                count, wh, wd, part(base, 4), part(base + 4, 4), part(base + 8, 4), part(base + 12, 4), part(base + 16, 4), part(base + 20, 3), rest[base + 23],
            )
        }

        /** fp16 (16 bit IEEE 754 nhị phân) -> Double, chính xác; tự giải mã để không cần `android.util.Half` (API 26+) trong bài thử JVM. */
        fun halfToDouble(raw: Int): Double {
            val bits = raw and 0xFFFF
            val sign = if (bits and 0x8000 != 0) -1.0 else 1.0
            val exponent = (bits shr 10) and 0x1F
            val mantissa = bits and 0x3FF
            return when (exponent) {
                0 -> sign * mantissa * Math.scalb(1.0, -24)
                0x1F -> if (mantissa == 0) sign * Double.POSITIVE_INFINITY else Double.NaN
                else -> sign * (1.0 + mantissa / 1024.0) * Math.scalb(1.0, exponent - 15)
            }
        }

        // ---- chữ -> đặc trưng ---------------------------------------------------------------------------------------------------------------
        fun normalize(text: String): String = Normalizer.normalize(text, Normalizer.Form.NFC).lowercase(Locale.ROOT)

        /** WORD: điểm mã loại Lu Ll Lt Lm Lo Mn Mc Nd Nl No liền nhau; PUNCT: mỗi điểm mã một token; còn lại chỉ cắt. */
        fun tokens(norm: String): List<String> {
            val out = ArrayList<String>()
            val current = StringBuilder()
            var at = 0
            while (at < norm.length) {
                val cp = norm.codePointAt(at)
                at += Character.charCount(cp)
                if (Character.getType(cp) in WORD_TYPES) {
                    current.appendCodePoint(cp)
                    continue
                }
                if (current.isNotEmpty()) {
                    out.add(current.toString())
                    current.setLength(0)
                }
                if (cp in PUNCT) out.add(String(Character.toChars(cp)))
            }
            if (current.isNotEmpty()) out.add(current.toString())
            return out
        }

        /** FNV-1a 32 bit trên byte UTF-8 (Long để giữ giá trị không dấu). */
        fun fnv1a(entry: String): Long {
            var hash = FNV_OFFSET
            for (byte in entry.toByteArray(Charsets.UTF_8)) hash = ((hash xor (byte.toLong() and 0xFF)) * FNV_PRIME) and 0xFFFFFFFFL
            return hash
        }

        fun entries(words: List<String>): List<String> {
            val out = ArrayList<String>(words.size * 2)
            for (word in words) out.add("1|$word")
            for (index in 0 until words.size - 1) out.add("2|${words[index]} ${words[index + 1]}")
            return out
        }

        /** {ô băm: giá trị} theo ô tăng dần; cảnh không token -> rỗng. Chuẩn L2 cộng theo thứ tự ô xuất hiện (như Python). */
        fun features(text: String, buckets: Int): List<Pair<Int, Double>> {
            val counts = LinkedHashMap<Int, Int>()
            for (entry in entries(tokens(normalize(text)))) {
                val slot = (fnv1a(entry) % buckets).toInt()
                counts[slot] = (counts[slot] ?: 0) + 1
            }
            val values = LinkedHashMap<Int, Double>()
            for ((slot, count) in counts) values[slot] = ln1p(count.toDouble())
            var sum = 0.0
            for (value in values.values) sum += value * value
            val norm = sqrt(sum)
            if (!(norm > 0)) return emptyList()
            return values.entries.sortedBy { it.key }.map { it.key to it.value / norm }
        }

        private fun isPunctToken(word: String): Boolean = word.codePointCount(0, word.length) == 1 && word.codePointAt(0) in PUNCT

        /** Bốn số dày của chữ đã NFC (chưa hạ chữ): tỉ lệ dòng mở bằng thoại, "!" và "?" trên số token WORD, log1p(số token WORD) / 10. */
        fun dense(text: String): DoubleArray {
            val nfc = Normalizer.normalize(text, Normalizer.Form.NFC)
            val lines = nfc.split("\n").map { Py.strip(it) }.filter { it.isNotEmpty() }
            val words = tokens(nfc.lowercase(Locale.ROOT)).count { !isPunctToken(it) }
            val first = if (lines.isEmpty()) 0.0 else lines.count { it.codePointAt(0) in DIALOG }.toDouble() / lines.size
            val scale = maxOf(1, words).toDouble()
            return doubleArrayOf(first, nfc.count { it == '!' } / scale, nfc.count { it == '?' } / scale, ln1p(words.toDouble()) / 10.0)
        }

        /** Trọng số cảnh: số mẩu `str.split()` (khoảng trắng của Python, [Py.split]), ít nhất 1. */
        fun weight(text: String): Int = maxOf(1, Py.split(text).size)

        /**
         * `music_nnlite.blocks`: khối (vị trí câu đầu, câu cuối): cộng số chữ `split()` theo câu ([Py.split]), đủ [blockWords] thì đóng khối ở câu ấy; phần dư cuối
         * < một nửa và đã có khối thì gộp vào khối trước.
         */
        fun blocks(segments: List<SceneSegment>, blockWords: Int = LB_BLOCK_WORDS): List<Pair<Int, Int>> {
            val out = ArrayList<Pair<Int, Int>>()
            var start = 0
            var count = 0
            for ((index, segment) in segments.withIndex()) {
                count += Py.split(segment.text).size
                if (count >= blockWords) {
                    out.add(start to index)
                    start = index + 1
                    count = 0
                }
            }
            if (start < segments.size) {
                if (out.isNotEmpty() && count < blockWords / 2.0) out[out.size - 1] = out.last().first to segments.size - 1
                else out.add(start to segments.size - 1)
            }
            return out
        }

        /**
         * `music_nnlite.partition`: chỉ số khối MỞ mỗi đoạn (trừ đoạn đầu), cực tiểu Σ SSE(đoạn) + lam·(số đoạn − 1), mỗi đoạn >= [minBlocks] khối; dưới 2·[minBlocks] khối: không ranh.
         * SSE qua tổng tiền tố (Double, cùng thứ tự phép tính với Python); duyệt j tăng rồi i tăng, chỉ thay khi nhỏ hơn hẳn.
         */
        fun partition(profile: List<DoubleArray>, lam: Double = LB_LAMBDA, minBlocks: Int = LB_MIN_BLOCKS): List<Int> {
            val n = profile.size
            if (n < 2 * minBlocks) return emptyList()
            val prefix = Array(n + 1) { DoubleArray(3) }
            val prefix2 = DoubleArray(n + 1)
            for ((index, row) in profile.withIndex()) {
                for (axis in 0 until 3) prefix[index + 1][axis] = prefix[index][axis] + row[axis]
                prefix2[index + 1] = prefix2[index] + (row[0] * row[0] + row[1] * row[1] + row[2] * row[2])
            }
            val best = DoubleArray(n + 1) { Double.POSITIVE_INFINITY }
            val back = IntArray(n + 1)
            best[0] = -lam
            for (j in minBlocks..n) {
                for (i in 0..j - minBlocks) {
                    if (best[i] < Double.POSITIVE_INFINITY) {
                        val s0 = prefix[j][0] - prefix[i][0]
                        val s1 = prefix[j][1] - prefix[i][1]
                        val s2 = prefix[j][2] - prefix[i][2]
                        val value = best[i] + lam + (prefix2[j] - prefix2[i] - (s0 * s0 + s1 * s1 + s2 * s2) / (j - i))
                        if (value < best[j]) {
                            best[j] = value
                            back[j] = i
                        }
                    }
                }
            }
            val cuts = ArrayList<Int>()
            var j = n
            while (j > 0) {
                j = back[j]
                if (j > 0) cuts.add(j)
            }
            return cuts.sorted()
        }

        /** `music_moods.scene_text`: chữ các câu từ vị trí `first` tới `last` (gồm cả hai), mỗi câu một dòng, khoảng trắng gộp một dấu cách. */
        fun sceneText(segments: List<SceneSegment>, first: Int, last: Int): String =
            if (last < first) "" else segments.subList(first, last + 1).joinToString("\n") { Py.split(it.text).joinToString(" ") }
    }
}
