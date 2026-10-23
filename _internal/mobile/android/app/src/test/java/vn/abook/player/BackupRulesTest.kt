package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.w3c.dom.Element
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

/**
 * Soát a107 F3: Auto Backup / chuyển máy không được mang mã ghép nối, vân tay TLS và danh sách máy chia sẻ sang máy mới mà thiếu khoá Keystore của chúng.
 * Hai danh sách (Android 12+ và Android 11 trở xuống) phải giống nhau, manifest phải trỏ tới cả hai, và sách / chỗ nghe vẫn được sao lưu.
 * Gradle chạy test ở mobile/android/app.
 */
class BackupRulesTest {
    private fun parse(path: String): Element {
        val file = File(path)
        check(file.isFile) { "không thấy ${file.absolutePath}" }
        return DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }.newDocumentBuilder().parse(file).documentElement
    }

    private fun excluded(root: Element): List<String> {
        val nodes = root.getElementsByTagName("exclude")
        return (0 until nodes.length).map { (nodes.item(it) as Element).let { e -> e.getAttribute("domain") + ":" + e.getAttribute("path") } }
    }

    private val secrets = listOf("sharedpref:sync.xml", "sharedpref:peers.xml", "sharedpref:abook_self.xml", "sharedpref:readaloud-online-keys.xml", "file:share.json")

    @Test fun pairingAndShareFilesAreLeftOutOfEveryKindOfBackup() {
        val rules = parse("src/main/res/xml/data_extraction_rules.xml")
        for (kind in listOf("cloud-backup", "device-transfer")) {
            val section = rules.getElementsByTagName(kind).item(0) as Element
            assertTrue("$kind: ${excluded(section)}", excluded(section).containsAll(secrets))
        }
        assertTrue(excluded(parse("src/main/res/xml/backup_rules.xml")).containsAll(secrets))
    }

    @Test fun theAndroid11AndAndroid12ListsAgree() {
        val old = excluded(parse("src/main/res/xml/backup_rules.xml")).sorted()
        val rules = parse("src/main/res/xml/data_extraction_rules.xml")
        for (kind in listOf("cloud-backup", "device-transfer")) {
            assertEquals(old, excluded(rules.getElementsByTagName(kind).item(0) as Element).sorted())
        }
    }

    @Test fun booksAndListeningStayInTheBackup() {
        // Chỉ loại các mục nêu tên; không loại cả thư mục (sách nằm ở filesDir/library, chỗ nghe trong book.json / state của từng cuốn).
        val all = excluded(parse("src/main/res/xml/backup_rules.xml"))
        assertFalse(all.any { it.startsWith("file:library") || it.endsWith(":.") || it.endsWith(":/") || it.endsWith(":") })
        assertFalse(all.any { it.startsWith("root:") || it.startsWith("database:") })
    }

    @Test fun theManifestPointsAtBothLists() {
        val app = parse("src/main/AndroidManifest.xml").getElementsByTagName("application").item(0) as Element
        val ns = "http://schemas.android.com/apk/res/android"
        assertEquals("@xml/data_extraction_rules", app.getAttributeNS(ns, "dataExtractionRules"))
        assertEquals("@xml/backup_rules", app.getAttributeNS(ns, "fullBackupContent"))
    }

    @Test fun theNamesMatchWhereTheCodeKeepsThem() {
        // Tên file preferences = tên truyền cho getSharedPreferences; share.json = LibraryServer.devicesFile.
        val code = File("src/main/java/vn/abook/player").walkTopDown().filter { it.extension == "kt" }.joinToString("\n") { it.readText(Charsets.UTF_8) }
        for (name in listOf("sync", "peers", "abook_self", "readaloud-online-keys")) {
            assertTrue("getSharedPreferences(\"$name\"", code.contains("getSharedPreferences(\"$name\""))
        }
        assertTrue(code.contains("File(context.filesDir, \"share.json\")"))
    }
}
