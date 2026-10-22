package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.w3c.dom.Element
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

/**
 * Soát a77 #5: nút Phát của tai nghe sau khi dịch vụ phát đã bị dọn (hay máy khởi động lại) chỉ khởi động lại được phiên qua `MediaButtonReceiver` của Media3 +
 * action MEDIA_BUTTON ở manifest - `onPlaybackResumption` một mình không đủ. Gradle chạy test ở mobile/android/app.
 */
class MediaButtonManifestTest {
    private fun manifest(): Element {
        val file = File("src/main/AndroidManifest.xml")
        check(file.isFile) { "không thấy ${file.absolutePath}" }
        return DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }.newDocumentBuilder().parse(file).documentElement
    }

    private fun android(element: Element, name: String) = element.getAttributeNS("http://schemas.android.com/apk/res/android", name)

    @Test fun mediaButtonReceiverIsDeclaredWithTheMediaButtonAction() {
        val receivers = manifest().getElementsByTagName("receiver")
        val found = (0 until receivers.length).map { receivers.item(it) as Element }
            .filter { android(it, "name") == "androidx.media3.session.MediaButtonReceiver" }
        assertEquals("khai báo MediaButtonReceiver đúng một lần", 1, found.size)
        val receiver = found.single()
        assertEquals("true", android(receiver, "exported")) // hệ thống gửi nút tai nghe từ ngoài app
        val actions = receiver.getElementsByTagName("action")
        val names = (0 until actions.length).map { android(actions.item(it) as Element, "name") }
        assertTrue(names.toString(), "android.intent.action.MEDIA_BUTTON" in names)
    }

    @Test fun thePlaybackServiceStillHasItsMediaSessionActions() {
        val actions = manifest().getElementsByTagName("action")
        val names = (0 until actions.length).map { android(actions.item(it) as Element, "name") }
        assertTrue("androidx.media3.session.MediaLibraryService" in names)
    }
}
