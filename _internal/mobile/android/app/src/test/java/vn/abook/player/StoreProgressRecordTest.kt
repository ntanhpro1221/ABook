package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Before
import org.junit.Test

/** Soát a104 F1: loa / TV ghi chỗ nghe vào hồ sơ đã chốt lúc "Phát trên…", không theo hồ sơ vừa được chọn sau đó. */
class StoreProgressRecordTest {
    @Before fun setup() {
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("progress-record"))
    }

    private fun records(book: String) = Store.records(book).let { rows -> (0 until rows.length()).map { rows.getJSONObject(it).getString("id") } }

    @Test fun aPinnedProfileKeepsReceivingTheSavesAfterAnotherIsChosen() {
        val first = Store.activeRecord("sach")
        Store.createRecord("sach", "Người B")
        val second = records("sach").first { it != first }
        Store.activateRecord("sach", second)
        Store.progress("sach", 1, 150.0, 300.0)
        Store.progress("sach", 1, 30.0, 300.0, recordId = first) // TV vẫn phát phiên của hồ sơ đầu
        assertEquals(150.0, Store.state("sach").getJSONObject("last").getDouble("seconds"), 0.001) // hồ sơ đang dùng không bị ghi đè
        Store.activateRecord("sach", first)
        assertEquals(30.0, Store.state("sach").getJSONObject("last").getDouble("seconds"), 0.001)
    }

    @Test fun aProfileThatLeftTheBookDropsTheSave() {
        Store.progress("sach", 1, 10.0, 300.0)
        Store.progress("sach", 1, 99.0, 300.0, recordId = "r-khong-con")
        assertEquals(10.0, Store.state("sach").getJSONObject("last").getDouble("seconds"), 0.001)
        assertFalse(records("sach").contains("r-khong-con"))
    }
}
