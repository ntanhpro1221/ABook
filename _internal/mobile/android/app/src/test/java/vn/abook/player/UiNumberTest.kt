package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Test

class UiNumberTest {
    @Test fun decimalAndBalanceUseVietnameseNumbers() {
        assertEquals(listOf("0", "0", "0,5", "-2,5", "1,35"), listOf(0.0, -0.0, .5, -2.5, 1.35).map { UiNumber.decimal(it) })
        assertEquals(listOf("Trái 30 %", "Giữa", "Phải 30 %"), listOf(-30.0, 0.0, 30.0).map { UiNumber.balance(it) })
        assertEquals("1,0", UiNumber.decimal(1.0, 1, fixed = true))
    }
}
