package vn.abook.player

import java.math.BigDecimal
import java.math.RoundingMode

/** The single decimal formatter for visible Vietnamese numbers. Storage keeps numeric values. */
object UiNumber {
    fun decimal(value: Double, digits: Int = 2, fixed: Boolean = false): String {
        val rounded = BigDecimal.valueOf(if (value == 0.0) 0.0 else value).setScale(digits, RoundingMode.HALF_UP)
        return (if (fixed) rounded else rounded.stripTrailingZeros()).toPlainString().replace('.', ',')
    }

    fun balance(percent: Double): String = when {
        percent == 0.0 -> S.s_value_middle
        percent < 0 -> S.s_value_left(decimal(-percent, 0))
        else -> S.s_value_right(decimal(percent, 0))
    }
}
