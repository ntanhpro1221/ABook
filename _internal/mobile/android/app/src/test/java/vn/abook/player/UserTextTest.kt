package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.FileNotFoundException
import java.io.IOException
import java.net.ConnectException

/** [UserText]: lời của app đi qua nguyên vẹn; chữ của Java/Android không bao giờ thành chữ trên màn hình. */
class UserTextTest {
    private val fallback = S.s_chua_lam_duoc_8b442a06

    @Test fun permissionDenialBecomesOneVietnameseSentence() {
        val denial = SecurityException("Permission Denial: reading com.android.providers.downloads.DownloadStorageProvider uri content://x from pid=1, uid=2 " +
            "requires that you obtain access using ACTION_OPEN_DOCUMENT or related APIs")
        val shown = UserText.of(denial, fallback)
        assertEquals(S.s_abook_khong_con_quyen_mo_file_nay_ban_hay_b7276dfc, shown)
        assertTrue(UserText.accessLost(IllegalStateException("x", denial)))
    }

    @Test fun appSentencesPassThroughEvenWithAPlatformCause() {
        assertEquals("File đang bận", UserText.of(IllegalStateException("File đang bận"), fallback))
        assertEquals(S.s_ban_hay_nhap_ten_sach_da2b7a84, UserText.of(IllegalArgumentException(S.s_ban_hay_nhap_ten_sach_da2b7a84, SecurityException("Permission Denial")), fallback))
    }

    @Test fun platformErrorsMapByKindAndUnknownOnesUseTheCallersWords() {
        assertEquals(S.s_ban_giai_phong_bo_nho_tren_dien_thoai_roi_17f5da65, UserText.of(IOException("write failed: ENOSPC (No space left on device)"), fallback))
        assertEquals(S.s_khong_thay_file_nua_co_the_no_da_bi_xoa_371f4e4f, UserText.of(FileNotFoundException("/sdcard/a.txt: open failed: ENOENT (No such file or directory)"), fallback))
        assertEquals(NetErrors.message(NetErrors.Kind.UNREACHABLE), UserText.of(ConnectException("Failed to connect to /192.0.2.10:47679"), fallback))
        assertEquals(fallback, UserText.of(IllegalStateException("boom"), fallback))
        assertEquals(fallback, UserText.of(NullPointerException(), fallback))
        assertEquals(fallback, UserText.of(null, fallback))
        assertEquals("Hỏng ở đây", UserText.of(RuntimeException("wrapper", IllegalStateException("Hỏng ở đây")), fallback))
    }

    @Test fun readableRejectsMachineTextEvenWithVietnameseAround() {
        assertTrue(UserText.readable("Chưa đọc được file."))
        assertFalse(UserText.readable("Không mở được: java.io.IOException: đọc lỗi"))
        assertFalse(UserText.readable("Permission Denial: quyền đọc"))
        assertFalse(UserText.readable("content://x/đ"))
        assertFalse(UserText.readable("Connection reset"))
        assertFalse(UserText.readable(""))
        assertEquals(fallback, UserText.text("Unable to resolve host", fallback))
        assertEquals("Máy kia đã bỏ ghép", UserText.text("Máy kia đã bỏ ghép", fallback))
    }
}
