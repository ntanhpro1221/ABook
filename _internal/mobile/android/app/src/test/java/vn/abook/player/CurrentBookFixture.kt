package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.file.Files
import java.util.zip.CRC32
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

/** Current metadata in temporary archives; every archived media/source byte stays unchanged. */
object CurrentBookFixture {
    fun build(source: File): File {
        val methods = HashMap<String, Int>()
        val content = ZipFile(source).use { archive ->
            archive.entries().toList().associate { methods[it.name] = it.method; it.name to archive.getInputStream(it).readBytes() }.toMutableMap()
        }
        val book = JSONObject(content.getValue("book.json").toString(Charsets.UTF_8))
        val chapters = book.optJSONArray("chapters") ?: JSONArray()
        for (i in 0 until chapters.length()) chapters.getJSONObject(i).put("volumeId", 1)
        book.remove("chapters")
        book.put("volumes", JSONArray().put(JSONObject().put("id", 1).put("number", 1)
            .put("title", S.s_volume_number(1)).put("cover", JSONObject.NULL).put("chapters", chapters)))
        book.getJSONObject("package").put("version", 6)
        content["book.json"] = book.toString().toByteArray(Charsets.UTF_8)
        content["project.json"]?.let { raw ->
            val project = JSONObject(raw.toString(Charsets.UTF_8))
            val bytes = content.getValue("book.json")
            project.getJSONObject("files").put("book.json", JSONObject().put("size", bytes.size).put("sha256", PackageFixtures.sha256(bytes)))
            content["project.json"] = project.toString().toByteArray(Charsets.UTF_8)
        }
        val target = File(Files.createTempDirectory("abook-fixture-").toFile(), source.name)
        ZipOutputStream(target.outputStream()).use { archive ->
            for ((name, bytes) in content) {
                val entry = ZipEntry(name)
                if (name == "mimetype" || methods[name] == ZipEntry.STORED) {
                    entry.method = ZipEntry.STORED
                    entry.size = bytes.size.toLong()
                    entry.compressedSize = bytes.size.toLong()
                    entry.crc = CRC32().also { it.update(bytes) }.value
                }
                archive.putNextEntry(entry)
                archive.write(bytes)
                archive.closeEntry()
            }
        }
        return target
    }
}
