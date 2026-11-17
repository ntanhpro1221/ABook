package vn.abook.player

import android.content.Intent
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import java.io.File

/**
 * Lệnh nhập ngầm qua adb ([ImportReceiver]): đường dẫn ngoài thư mục nhập, `..`, file không phải sách đều bị từ chối, không lượt nào được xếp, và
 * không bao giờ có Activity nào được mở. Manifest khai receiver với quyền DUMP (chỉ shell / hệ thống gửi được).
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ImportReceiverTest {
    private val context get() = ApplicationProvider.getApplicationContext<AbookApplication>()

    private fun send(path: String?, action: String = BookImports.ACTION_IMPORT) {
        ImportReceiver().onReceive(context, Intent(action).apply { path?.let { putExtra("path", it) } })
    }

    @Test fun paths_outside_the_import_folder_are_refused_without_queueing_or_opening_the_app() {
        val inbox = requireNotNull(BookImports.inbox(context))
        inbox.mkdirs()
        val outside = File(context.filesDir, "books.abook").apply { writeText("x") }
        val sibling = File(inbox.parentFile, "bên cạnh.abook").apply { writeText("x") }
        val text = File(inbox, "ghi chú.txt").apply { writeText("x") }
        val before = BookImports.jobs.jobs.value
        for (path in listOf(outside.absolutePath, sibling.absolutePath, File(inbox, "../bên cạnh.abook").path, text.absolutePath, "bên cạnh.abook", "/sdcard/Download/x.abook")) {
            send(path)
        }
        send(sibling.absolutePath, action = "com.example.OTHER")
        assertEquals(before, BookImports.jobs.jobs.value)
        assertNull(shadowOf(context).nextStartedActivity)
        assertTrue(outside.isFile && sibling.isFile && text.isFile)
    }

    @Test fun an_empty_import_folder_queues_nothing() {
        val inbox = requireNotNull(BookImports.inbox(context))
        inbox.mkdirs()
        inbox.listFiles().orEmpty().forEach { it.delete() }
        val before = BookImports.jobs.jobs.value
        send(null)
        assertEquals(before, BookImports.jobs.jobs.value)
        assertNull(shadowOf(context).nextStartedActivity)
    }

    @Test fun the_manifest_guards_the_receiver_with_the_dump_permission() {
        val manifest = File("src/main/AndroidManifest.xml").readText()
        val block = Regex("""<receiver\s+android:name="\.ImportReceiver"[^>]*>""").find(manifest)?.value
        requireNotNull(block) { "không thấy ImportReceiver trong manifest" }
        assertTrue(block, "android:permission=\"android.permission.DUMP\"" in block)
        assertTrue(Regex("""<receiver android:name="\.ImportActionReceiver" android:exported="false" />""").containsMatchIn(manifest))
    }
}
