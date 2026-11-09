package vn.abook.player.ui.components

import vn.abook.player.S
import java.math.BigDecimal
import java.math.RoundingMode
import kotlin.math.abs
import kotlin.math.round

/**
 * Bộ chọn giá trị số - phần tính toán. MỘT hợp đồng cho ba nền (tests/fixtures/value_picker/cases.json): web shared/valuePickerLogic.ts,
 * Qt ValuePickerLogic.js. Luật DESIGN mục 6 "Chọn giá trị": mọi giá trị số = chip tiêu biểu + chọn tự do (kéo thước, -/+ một bước, gõ số).
 *
 * `scale`: mốc (vị trí 0..1, giá trị) của thước; rỗng = thẳng min..max.
 */
data class ValueSpec(
    val min: Double,
    val max: Double,
    val step: Double,
    val typical: List<Double>,
    val scale: List<Pair<Double, Double>> = emptyList(),
) {
    /** Bản kẹp trần thấp hơn ("Giữ khoảng nghỉ" không quá "Dài tối thiểu"). */
    fun cappedAt(top: Double): ValueSpec {
        val capped = minOf(max, top)
        return copy(max = capped, typical = typical.filter { it <= capped })
    }
}

data class Parsed(val value: Double, val clamped: Boolean)

object ValueSpecs {
    private fun spec(min: Number, max: Number, step: Number, typical: List<Number>, scale: List<Pair<Number, Number>> = emptyList()) =
        ValueSpec(min.toDouble(), max.toDouble(), step.toDouble(), typical.map { it.toDouble() }, scale.map { it.first.toDouble() to it.second.toDouble() })

    val sleepMinutes = spec(1, 240, 1, listOf(5, 10, 15, 30, 45, 60, 90), listOf(0 to 1, 0.5 to 60, 0.75 to 120, 1 to 240))
    val sleepChapters = spec(1, 10, 1, listOf(1, 2, 3))
    val speed = spec(0.5, 3, 0.05, listOf(0.8, 1, 1.25, 1.5, 2), listOf(0 to 0.5, 0.6 to 1.5, 1 to 3))
    val readSize = spec(12, 40, 1, listOf(16, 18, 20, 22, 24))
    val readLeading = spec(1.2, 2.4, 0.05, listOf(1.5, 1.7, 1.9))
    val sleepFadeSeconds = spec(5, 120, 5, listOf(10, 30, 60))
    val sleepExtendMinutes = spec(1, 60, 1, listOf(5, 10, 15, 30))
    val scheduleMinutes = spec(5, 240, 5, listOf(15, 30, 45, 60, 90))
    val volume = spec(0, 100, 1, listOf(25, 50, 75, 100))
    val boost = spec(0, 12, 1, listOf(0, 3, 6))
    val pitch = spec(-6, 6, 0.5, listOf(-2, 0, 2))
    val balance = spec(-100, 100, 1, listOf(-50, 0, 50))
    val silenceDb = spec(-80, -45, 1, listOf(-70, -60, -50))
    val silenceSeconds = spec(2, 10, 0.5, listOf(3, 5))
    val keepSeconds = spec(1.5, 3, 0.1, listOf(1.5, 2))
    val eqBand = spec(-12, 12, 1, listOf(-6, 0, 6))
    val bass = spec(0, 12, 1, listOf(0, 4, 8))

    /** Theo tên trong fixture (test so bảng). */
    val all: Map<String, ValueSpec> = mapOf(
        "sleepMinutes" to sleepMinutes, "sleepChapters" to sleepChapters, "speed" to speed, "readSize" to readSize, "readLeading" to readLeading,
        "sleepFadeSeconds" to sleepFadeSeconds, "sleepExtendMinutes" to sleepExtendMinutes, "scheduleMinutes" to scheduleMinutes,
        "volume" to volume, "boost" to boost, "pitch" to pitch, "balance" to balance, "silenceDb" to silenceDb, "silenceSeconds" to silenceSeconds,
        "keepSeconds" to keepSeconds, "eqBand" to eqBand, "bass" to bass,
    )
}

object ValuePickerLogic {
    /** Nấc hút: giá trị tiêu biểu "rộng" thêm chừng này bước khi kéo - đủ để dừng đúng nấc mà không nuốt bước kề. */
    const val SNAP_STEPS = 0.75
    /** PageUp / PageDown đổi chừng này bước. */
    const val PAGE_STEPS = 10

    fun decimalsOf(step: Double): Int = BigDecimal.valueOf(step).stripTrailingZeros().scale().coerceAtLeast(0)

    private fun roundTo(value: Double, decimals: Int): Double {
        val result = BigDecimal.valueOf(value).setScale(decimals, RoundingMode.HALF_UP).toDouble()
        return if (result == 0.0) 0.0 else result
    }

    /** Kẹp vào biên rồi về lưới min + n*step. */
    fun quantize(spec: ValueSpec, value: Double): Double {
        val decimals = maxOf(decimalsOf(spec.step), decimalsOf(spec.min))
        val clamped = value.coerceIn(spec.min, spec.max)
        var result = roundTo(spec.min + round((clamped - spec.min) / spec.step) * spec.step, decimals)
        if (result > spec.max) result = roundTo(result - spec.step, decimals)
        return result
    }

    fun clamp(spec: ValueSpec, value: Double): Parsed = Parsed(quantize(spec, value), value < spec.min || value > spec.max)

    fun step(spec: ValueSpec, value: Double, steps: Int): Double = quantize(spec, quantize(spec, value) + steps * spec.step)

    private fun scaleOf(spec: ValueSpec) = spec.scale.ifEmpty { listOf(0.0 to spec.min, 1.0 to spec.max) }

    /** Giá trị thô (chưa về lưới) ở vị trí `fraction` của thước. */
    fun rawAt(spec: ValueSpec, fraction: Double): Double {
        val scale = scaleOf(spec)
        val f = fraction.coerceIn(0.0, 1.0)
        for (i in 1 until scale.size) {
            val (f0, v0) = scale[i - 1]
            val (f1, v1) = scale[i]
            if (f <= f1 || i == scale.size - 1) return v0 + (f - f0) / (f1 - f0) * (v1 - v0)
        }
        return spec.max
    }

    /** Giá trị khi kéo tới `fraction`: hút về giá trị tiêu biểu gần (nấc), không thì về lưới. */
    fun fromFraction(spec: ValueSpec, fraction: Double): Double {
        val raw = rawAt(spec, fraction)
        val nearest = spec.typical.minByOrNull { abs(it - raw) }
        if (nearest != null && abs(nearest - raw) <= SNAP_STEPS * spec.step) return nearest
        return quantize(spec, raw)
    }

    /** Vị trí 0..1 của `value` trên thước. */
    fun toFraction(spec: ValueSpec, value: Double): Double {
        val scale = scaleOf(spec)
        val v = value.coerceIn(spec.min, spec.max)
        for (i in 1 until scale.size) {
            val (f0, v0) = scale[i - 1]
            val (f1, v1) = scale[i]
            if (v <= v1 || i == scale.size - 1) return f0 + (v - v0) / (v1 - v0) * (f1 - f0)
        }
        return 1.0
    }

    /** Chữ người gõ: null khi không ra số (giữ giá trị cũ). */
    fun parse(spec: ValueSpec, text: String): Parsed? {
        val cleaned = text.filter { it.isDigit() && it in '0'..'9' || it == ',' || it == '.' || it == '-' }.replace(',', '.')
        if (cleaned.isEmpty()) return null
        // Như Number() của JS: cả chuỗi phải là MỘT số ("1.2.3", "1-2" không phải số).
        if (!Regex("""-?(\d+\.?\d*|\.\d+)""").matches(cleaned)) return null
        val parsed = cleaned.toDoubleOrNull() ?: return null
        return clamp(spec, parsed)
    }

    fun chipIndex(spec: ValueSpec, value: Double): Int = spec.typical.indexOfFirst { abs(it - value) < spec.step / 2 }

    /** Rung / tiếng nấc: vừa tới một giá trị tiêu biểu. */
    fun isDetent(spec: ValueSpec, previous: Double, next: Double): Boolean = next != previous && chipIndex(spec, next) >= 0

    /** Số kiểu Việt: "1,35", "1,5", "1". */
    fun format(spec: ValueSpec, value: Double): String =
        BigDecimal.valueOf(roundTo(value, decimalsOf(spec.step))).stripTrailingZeros().toPlainString().replace('.', ',')

    /** Số giây kiểu người đọc: "45 giây", tròn phút thì "1 phút", "2 phút". */
    fun secondsLabel(seconds: Int): String =
        if (seconds >= 60 && seconds % 60 == 0) S.s_0_phut_2596d212(seconds / 60) else S.s_0_giay_daac30d3(seconds)
}
