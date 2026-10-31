package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.w3c.dom.Element
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

/**
 * Manifest: NativeActivity là màn mở app duy nhất và là nơi nhận mọi "Mở bằng" / chia sẻ file sách (không thì "Mở bằng" ra nơi không ai nhận).
 */
class NativeManifestFiltersTest {
    private fun manifest(): Element {
        val file = listOf(File("src/main/AndroidManifest.xml"), File("app/src/main/AndroidManifest.xml")).first { it.isFile }
        return DocumentBuilderFactory.newInstance().apply { isNamespaceAware = false }.newDocumentBuilder().parse(file).documentElement
    }

    private fun activities(root: Element): List<Element> {
        val nodes = root.getElementsByTagName("activity")
        return (0 until nodes.length).map { nodes.item(it) as Element }
    }

    private fun filters(activity: Element): List<Element> {
        val nodes = activity.getElementsByTagName("intent-filter")
        return (0 until nodes.length).map { nodes.item(it) as Element }
    }

    private fun values(filter: Element, tag: String, attribute: String): Set<String> {
        val nodes = filter.getElementsByTagName(tag)
        return (0 until nodes.length).map { (nodes.item(it) as Element).getAttribute(attribute) }.toSet()
    }

    @Test fun nativeActivityIsTheOnlyActivityAndTheLauncher() {
        val all = activities(manifest())
        assertEquals(listOf(".ui.NativeActivity"), all.map { it.getAttribute("android:name") })
        val launcher = filters(all.single()).filter { "android.intent.action.MAIN" in values(it, "action", "android:name") }
        assertEquals(1, launcher.size)
        assertTrue("android.intent.category.LAUNCHER" in values(launcher.single(), "category", "android:name"))
    }

    @Test fun nativeActivityReceivesBookFilesFromOpenWithAndShare() {
        val received = filters(activities(manifest()).single()).filter { "android.intent.action.MAIN" !in values(it, "action", "android:name") }
        val types = received.flatMap { values(it, "data", "android:mimeType") }.toSet()
        for (type in listOf("application/vnd.ngdtuanh.abook+zip", "application/vnd.ngdtuanh.abookproj+zip", "application/epub+zip", "application/pdf", "text/plain")) {
            assertTrue("thiếu bộ lọc cho $type", type in types)
        }
        val actions = received.flatMap { values(it, "action", "android:name") }.toSet()
        assertTrue("android.intent.action.VIEW" in actions)
        assertTrue("android.intent.action.SEND" in actions)
        assertFalse("không nhận \"*/*\"", "*/*" in types)
    }
}
