package vn.abook.player

import org.json.JSONObject
import java.io.File
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Bộ phân tích "trò" của Nhạc của tôi trên điện thoại - bản Kotlin của đường ONNX trong `abook/webui/music_student.py`
 * (docs/MUSIC_IMPORT.md "Phân tích"): CHỈ NGHE, không dò "có lời", không chặn bài nào. Giải mã -> 48 kHz -> tối đa ba cửa sổ 10
 * giây ở 20 / 50 / 80% bài -> log-mel ([MusicMel]) -> tháp CLAP (ONNX, [ClapTower]) -> chuẩn hoá L2 từng cửa sổ, trung bình, chuẩn
 * hoá L2 -> đầu trò A ([StudentHead]). Kết quả có hình bài danh mục (qua [MusicStore.cleanAnalysis]); không có `loudness.speechBand`
 * (cần âm học). Bài không giải mã được hay ngắn hơn 3 giây -> null: bài ở "chưa phân tích", KHÔNG BAO GIỜ bịa số.
 */
class MusicStudent(
    private val head: StudentHead,
    private val tower: ClapTower,
    private val decoder: AudioDecoder,
) {
    private val run = Any() // một lượt phân tích một lúc (CPU của điện thoại)

    fun analyze(file: File): JSONObject? = synchronized(run) {
        val source = decoder.decode(file) ?: return null
        source.use {
            val windows = windows(source)
            if (windows.isEmpty()) return null
            head.predict(embedding(windows.map { tower.embed(MusicMel.logMel(it)) }))
        }
    }

    /** Các cửa sổ 48 kHz của bài (tối đa ba, bỏ cửa sổ ngắn hơn 3 giây). */
    private fun windows(source: PcmSource): List<FloatArray> {
        val total = Resampler.outputFrames(source.frames, source.rate)
        if (total > Int.MAX_VALUE) return emptyList()
        return clapStarts(total.toInt()).mapNotNull { start ->
            val length = min(WINDOW, total.toInt() - start)
            if (length < MIN_WINDOW) null else Resampler.window(source, start.toLong(), length)
        }
    }

    companion object {
        const val WINDOW = MusicMel.SAMPLE_RATE * 10
        const val MIN_WINDOW = MusicMel.SAMPLE_RATE * 3
        const val CONFIDENCE = 0.5 // chỉ nghe, không có chữ để đối chiếu: cố định (music_student.CONFIDENCE)

        /** `_clap_windows`: bài không dài hơn 10 giây -> cả bài; không thì 20 / 50 / 80% bài, mỗi cửa sổ 10 giây quanh điểm ấy, kẹp trong bài. */
        fun clapStarts(n: Int): List<Int> {
            if (n <= WINDOW) return listOf(0)
            return listOf(0.2, 0.5, 0.8).map { min(max((n * it).toInt() - WINDOW / 2, 0), n - WINDOW) }.distinct().sorted()
        }

        /** Chuẩn hoá L2 từng cửa sổ, trung bình, chuẩn hoá L2 (double cả đoạn sau tháp). */
        fun embedding(perWindow: List<DoubleArray>): DoubleArray {
            val mean = DoubleArray(perWindow.first().size)
            for (row in perWindow) {
                val norm = sqrt(row.sumOf { it * it })
                for (i in mean.indices) mean[i] += row[i] / norm
            }
            val norm = sqrt(mean.sumOf { (it / perWindow.size) * (it / perWindow.size) })
            return DoubleArray(mean.size) { mean[it] / perWindow.size / norm }
        }
    }
}

/** Tháp âm thanh CLAP: log-mel [1001 * 64] của một cửa sổ -> 512 số (chưa chuẩn hoá). */
fun interface ClapTower {
    fun embed(logMel: FloatArray): DoubleArray
}

/**
 * Đầu trò A (`student_head_A.npz`, music_student._Head): z-score 512 chiều CLAP, hồi quy tuyến tính 16 hàng (13 cường độ cảm xúc
 * = sigmoid; valence / arousal / tension kẹp -1..1 rồi hiệu chỉnh cho kho trộn - [CALIBRATION], kèm `vetVar`), `fitsUnderNarration`
 * và `family` đọc thẳng từ vector nhúng so với vector chữ đã tính sẵn. Mọi phép tính bằng double.
 */
class StudentHead(arrays: Map<String, NpyArray>) {
    private val mu = array(arrays, "mu").doubles()
    private val sd = array(arrays, "sd").doubles()
    private val coef = array(arrays, "coef")
    private val coefValues = coef.doubles()
    private val intercept = array(arrays, "intercept").doubles()
    private val emotions = array(arrays, "emos").texts()
    private val background = array(arrays, "background_text")
    private val familyNames = array(arrays, "family_names").texts()
    private val familyText = array(arrays, "family_text")

    init {
        // Đầu A không có cột âm học (`names` rỗng): 512 chiều CLAP và thế thôi.
        if (arrays.containsKey("names") && arrays.getValue("names").size > 0) throw IllegalArgumentException("đầu của đường onnx phải là đầu A (chỉ 512 chiều CLAP)")
        if (mu.size != EMBEDDING || sd.size != EMBEDDING || coef.shape.size != 2 || coef.shape[0] != emotions.size + 3 ||
            coef.shape[1] != EMBEDDING || intercept.size != emotions.size + 3 || background.shape.toList() != listOf(2, EMBEDDING) ||
            familyText.shape.toList() != listOf(familyNames.size, EMBEDDING)
        ) {
            throw IllegalArgumentException("gói model không đúng hình đầu trò")
        }
    }

    private fun array(arrays: Map<String, NpyArray>, name: String) = arrays[name] ?: throw IllegalArgumentException("gói model thiếu “$name”")

    /** Kết quả cho một vector nhúng (512, đã chuẩn hoá L2): đúng khoá của `_Head.predict` với hiệu chỉnh của đường onnx. */
    fun predict(embedding: DoubleArray): JSONObject {
        require(embedding.size == EMBEDDING) { "vector nhúng phải có $EMBEDDING chiều" }
        val z = DoubleArray(EMBEDDING) { (embedding[it] - mu[it]) / sd[it] }
        val rows = emotions.size + 3
        val out = DoubleArray(rows) { row ->
            var sum = 0.0
            val base = row * EMBEDDING
            for (i in 0 until EMBEDDING) sum += z[i] * coefValues[base + i]
            sum + intercept[row]
        }
        val intensity = JSONObject()
        for ((index, name) in emotions.withIndex()) intensity.put(name, 1.0 / (1.0 + exp(-out[index])))
        val vet = JSONObject()
        val variance = JSONObject()
        for ((offset, axis) in listOf("valence", "arousal", "tension").withIndex()) {
            val (shift, slope, residual) = CALIBRATION.getValue(axis)
            // kẹp trước rồi mới hiệu chỉnh, đúng thứ tự lúc khớp CALIBRATION
            vet.put(axis, (shift + slope * out[emotions.size + offset].coerceIn(-1.0, 1.0)).coerceIn(-1.0, 1.0))
            variance.put(axis, residual)
        }
        val pair = DoubleArray(2) { 100.0 * dot(background.doubles(), it, embedding) }
        val top = max(pair[0], pair[1])
        val weights = pair.map { exp(it - top) }
        var best = 0
        var bestScore = Double.NEGATIVE_INFINITY
        for (index in familyNames.indices) {
            val score = dot(familyText.doubles(), index, embedding)
            if (score > bestScore) {
                bestScore = score
                best = index
            }
        }
        val family = familyNames[best]
        return JSONObject().put("valence", vet.get("valence")).put("arousal", vet.get("arousal")).put("tension", vet.get("tension"))
            .put("vetVar", variance).put("emotions", intensity).put("confidence", MusicStudent.CONFIDENCE)
            .put("fitsUnderNarration", weights[0] / weights.sum())
            // Họ phong cách ngoài danh sách của app (vd "rock") là "other" - như danh mục.
            .put("family", if (family in FAMILIES) family else "other")
    }

    private fun dot(matrix: DoubleArray, row: Int, vector: DoubleArray): Double {
        var sum = 0.0
        val base = row * EMBEDDING
        for (i in 0 until EMBEDDING) sum += matrix[base + i] * vector[i]
        return sum
    }

    companion object {
        const val EMBEDDING = 512
        val FAMILIES = setOf("eastern", "orchestral", "piano", "ambient", "acoustic", "electronic", "other") // music_plan.FAMILIES

        /**
         * Hiệu chỉnh số của trò cho kho TRỘN (music_student.CALIBRATION["onnx"] - một bảng cho mọi đường, đầu A mới 05-10): mỗi trục (a, b, var):
         * v' = kẹp(a + b*v, -1, 1) và `vetVar` = var.
         */
        val CALIBRATION = mapOf(
            "valence" to Triple(-0.057, 1.264, 0.0728),
            "arousal" to Triple(-0.012, 1.100, 0.0316),
            "tension" to Triple(0.001, 1.264, 0.0402),
        )

        fun load(file: File): StudentHead = StudentHead(Npz.read(file))
    }
}
