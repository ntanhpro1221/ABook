package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.w3c.dom.Element
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

/**
 * Bản -PnativeUi: MainActivity (WebView) mất mọi bộ lọc "Mở bằng" / chia sẻ, NativeActivity giữ đúng những bộ lọc ấy (không thì "Mở bằng" ra trang trắng của WebView).
 * Hai bản chép trong hai manifest phải khớp nhau từng dòng - sửa một bên mà quên bên kia là test này đỏ.
 */
class NativeManifestFiltersTest {
    private fun manifest(name: String): Element {
        val file = listOf(File("src/$name/AndroidManifest.xml"), File("app/src/$name/AndroidManifest.xml")).first { it.isFile }
        return DocumentBuilderFactory.newInstance().apply { isNamespaceAware = false }.newDocumentBuilder().parse(file).documentElement
    }

    private fun activity(root: Element, name: String): Element {
        val nodes = root.getElementsByTagName("activity")
        return (0 until nodes.length).map { nodes.item(it) as Element }.first { it.getAttribute("android:name") == name }
    }

    /** Mỗi bộ lọc thành một chuỗi các dòng "thẻ|thuộc tính=giá trị" đã sắp; bỏ bộ lọc MAIN (màn mở app, không phải "Mở bằng"). */
    private fun filters(activity: Element): List<String> {
        val nodes = activity.getElementsByTagName("intent-filter")
        return (0 until nodes.length).map { nodes.item(it) as Element }.map { filter ->
            val lines = ArrayList<String>()
            for (index in 0 until filter.childNodes.length) {
                val child = filter.childNodes.item(index) as? Element ?: continue
                val attributes = (0 until child.attributes.length).map { child.attributes.item(it) }.map { "${it.nodeName}=${it.nodeValue}" }.sorted()
                lines += child.tagName + "|" + attributes.joinToString(",")
            }
            lines.sorted().joinToString("\n")
        }.filter { !it.contains("android.intent.action.MAIN") }.sorted()
    }

    @Test fun nativeActivityReceivesExactlyTheFiltersMainActivityLoses() {
        val main = filters(activity(manifest("main"), ".MainActivity"))
        val native = filters(activity(manifest("nativeUi"), ".ui.NativeActivity"))
        assertTrue("MainActivity phải có bộ lọc \"Mở bằng\" ở manifest chính", main.isNotEmpty())
        assertEquals(main, native)
        val removed = activity(manifest("nativeUi"), ".MainActivity").getElementsByTagName("intent-filter")
        assertEquals("overlay chỉ có một lệnh gỡ hết bộ lọc của MainActivity", 1, removed.length)
        assertEquals("removeAll", (removed.item(0) as Element).getAttribute("tools:node"))
    }
}
