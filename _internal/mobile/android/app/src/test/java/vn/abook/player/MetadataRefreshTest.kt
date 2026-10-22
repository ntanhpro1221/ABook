package vn.abook.player

import java.io.File
import java.math.BigInteger
import java.nio.file.Files
import java.security.MessageDigest
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Soát a97: đổi riêng tên / tác giả / người đọc / liên kết bộ / tên chương ở máy tính thì bản đã tải trên điện thoại nhận phần mô tả mới mà
 * giữ audio và lớp sửa (V1); phiên bản bìa theo nội dung, cùng công thức với máy tính (T2).
 */
class MetadataRefreshTest {
    private lateinit var root: File

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-meta").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
    }

    private fun chapter(id: Int, title: String, sha: String) =
        JSONObject().put("id", id).put("title", title).put("fullTitle", "Chương $id $title").put("sha256", sha).put("file", "chapters/$id.mp3").put("available", true)

    private fun book(title: String, meta: String, vararg chapters: JSONObject) = JSONObject().put("id", "b1").put("title", title).put("narrator", "Đức Trí")
        .put("metaVersion", meta).put("audioVersion", "audio-1").put("chapters", JSONArray(chapters.toList()))

    @Test fun a_changed_name_or_stamp_is_stale_but_a_computer_without_stamps_never_is() {
        val local = book("Tên cũ", "m1", chapter(1, "Một", "a"))
        assertTrue(StreamRefresh.metadataStale(local, JSONObject().put("metaVersion", "m2")))
        assertFalse(StreamRefresh.metadataStale(local, JSONObject().put("metaVersion", "m1")))
        assertFalse(StreamRefresh.metadataStale(local, JSONObject()))
        assertFalse(StreamRefresh.metadataStale(null, JSONObject().put("metaVersion", "m2")))
        // Sách nghe thẳng: dấu mô tả đổi là làm mới gói đã cất dù tên, tác giả và số chương không đổi.
        assertTrue(StreamRefresh.stale(local, JSONObject().put("metaVersion", "m2").put("title", "Tên cũ").put("chaptersAvailable", 0)))
    }

    @Test fun the_new_description_replaces_names_and_series_but_keeps_audio_and_edits_untouched() {
        val local = book("Tên cũ", "m1", chapter(1, "Một", "a"), chapter(2, "Hai", "b"))
            .put("author", "Tác giả cũ").put("series", JSONObject().put("root", "r").put("part", 2)).put("cover", JSONObject().put("version", 5))
        val fresh = book("Tên mới", "m2", chapter(1, "Một mới", "DIFFERENT"), chapter(3, "Ba", "c")).put("narrator", "Xuân Vĩnh")
            .put("audioVersion", "audio-2").put("series", JSONObject.NULL)
        val result = StreamRefresh.withMetadata(local, fresh)
        assertEquals("Tên mới", result.getString("title"))
        assertEquals("Xuân Vĩnh", result.getString("narrator"))
        assertEquals("m2", result.getString("metaVersion"))
        assertFalse(result.has("author"))
        assertFalse(result.has("series"))
        val chapters = result.getJSONArray("chapters")
        assertEquals("Một mới", chapters.getJSONObject(0).getString("title"))
        assertEquals("Chương 1 Một mới", chapters.getJSONObject(0).getString("fullTitle"))
        assertEquals("Hai", chapters.getJSONObject(1).getString("title"))  // chương máy kia không còn: giữ nguyên
        // Audio và bìa của máy này không đổi: nút "Cập nhật bản thu" vẫn là cách duy nhất để tải audio mới.
        assertEquals("audio-1", result.getString("audioVersion"))
        assertEquals("a", chapters.getJSONObject(0).getString("sha256"))
        assertEquals(5, result.getJSONObject("cover").getInt("version"))
    }

    @Test fun the_series_link_arrives_with_the_description() {
        val fresh = book("Ngày trở về", "m2", chapter(1, "Một", "a")).put("series", JSONObject().put("root", "first").put("part", 2))
        val result = StreamRefresh.withMetadata(book("Ngày trở về", "m1", chapter(1, "Một", "a")), fresh)
        assertEquals("first", result.getJSONObject("series").getString("root"))
    }

    @Test fun a_paired_devices_series_root_becomes_the_local_id_of_that_book() {
        val manifest = book("Ngày trở về", "m1").put("series", JSONObject().put("root", "first").put("part", 2))
        Peers.localizeSeries(manifest, "abc123")
        assertEquals(Peers.localId("abc123", "first"), manifest.getJSONObject("series").getString("root"))
        assertEquals(2, manifest.getJSONObject("series").getInt("part"))
        val none = book("Lẻ", "m1")
        assertFalse(Peers.localizeSeries(none, "abc123").has("series"))
        val broken = book("Hỏng", "m1").put("series", JSONObject().put("root", "../x").put("part", 2))
        assertFalse(Peers.localizeSeries(broken, "abc123").has("series"))
    }

    @Test fun rewriting_the_manifest_keeps_the_file_time_so_the_book_does_not_jump_to_new_additions() {
        val file = File(root, "books/b1/book.json").apply { parentFile.mkdirs() }
        file.writeText(book("Tên cũ", "m1", chapter(1, "Một", "a")).toString())
        file.setLastModified(1_700_000_000_000L)
        assertTrue(Store.rewriteManifest("b1") { StreamRefresh.withMetadata(it, book("Tên mới", "m2", chapter(1, "Một", "a"))) })
        assertEquals("Tên mới", JSONObject(file.readText()).getString("title"))
        assertEquals(1_700_000_000_000L, file.lastModified())
        assertFalse(Store.rewriteManifest("missing") { it })
    }

    @Test fun the_cover_version_is_a_function_of_the_picture_bytes_like_the_computer() {
        // Cùng vector với tests/test_library_management_a97.py: SHA-256("abc") bắt đầu ba7816bf8f01cfea.
        val digest = MessageDigest.getInstance("SHA-256").digest("abc".toByteArray())
        assertEquals(BigInteger(1, digest.copyOf(8)).mod(BigInteger.TEN.pow(10)).toLong(), CoverVersion.of("abc".toByteArray()))
        assertEquals(BigInteger("ba7816bf8f01cfea", 16).mod(BigInteger.TEN.pow(10)).toLong(), CoverVersion.of("abc".toByteArray()))
        assertTrue(CoverVersion.of("abc".toByteArray()) != CoverVersion.of("abd".toByteArray()))
    }
}
