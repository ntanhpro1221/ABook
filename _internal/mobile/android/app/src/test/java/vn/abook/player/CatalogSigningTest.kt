package vn.abook.player

import java.io.File
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Danh mục nhạc nền có chữ ký (MusicCatalog) - cùng luật và cùng bộ ca với tests/test_music_catalog_signing.py (tests/fixtures/catalog_signing,
 * khoá TEST): mục lục ký Ed25519, `issued` không lùi, mọi mảnh phải khớp sha256 trong `files`.
 */
class CatalogSigningTest {
    private lateinit var root: File
    private val calm = "https://x/calm.mp3"
    private val battle = "https://x/battle.mp3"
    private val cases = JSONObject(File(CatalogSigning.fixture, "cases.json").readText())
    private val logged = mutableListOf<String>()
    private var now = System.currentTimeMillis()

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-catalog-signing")
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
    }

    private fun catalog(cloud: File, publicKey: ByteArray = CatalogSigning.publicKey) =
        MusicCatalog(File(root, "cache"), cloud.path, clock = { now }, publicKey = publicKey, log = { logged += it })

    /** Qua 25 giờ: mục lục đã cất hết "tươi", lần gọi kế phải tải lại. */
    private fun nextDay() {
        now += 25L * 3600 * 1000
    }

    private fun cached(name: String) = File(root, "cache/$name")

    private fun problem(block: () -> Any?): String? = runCatching { block() }.exceptionOrNull()?.let { it as? MusicCatalog.CatalogError }?.message

    @Test
    fun a_signed_catalog_is_read_and_its_bytes_and_signature_are_kept() {
        val catalog = catalog(CatalogSigning.cloud(root))
        assertEquals(cases.getJSONObject("good").getString("revision"), catalog.manifest().getString("revision"))
        assertEquals(setOf(calm, battle), catalog.lookup(listOf(calm, battle)).keys)
        for (name in listOf("manifest.json", "manifest.json.sig")) {
            assertEquals("cất nguyên byte gốc + chữ ký", File(CatalogSigning.fixture, "good/$name").readText(), cached(name).readText())
        }
    }

    @Test
    fun the_app_key_does_not_accept_a_catalog_signed_with_the_test_key() {
        val message = problem { catalog(CatalogSigning.cloud(root), publicKey = RemoteConfig.PUBLIC_KEY).manifest() }
        assertTrue(message.toString(), message?.contains("chữ ký") == true)
    }

    @Test
    fun a_first_start_refuses_a_manifest_with_a_bad_signature_and_keeps_nothing() {
        for (case in listOf("bad_signature", "tampered_manifest")) {
            root.deleteRecursively()
            val message = problem { catalog(CatalogSigning.cloud(root, case)).manifest() }
            assertTrue("$case: $message", message?.contains("chữ ký") == true)
            assertFalse(cached("manifest.json").exists())
        }
    }

    @Test
    fun a_bad_signature_later_keeps_the_catalog_already_downloaded() {
        val cloud = CatalogSigning.cloud(root)
        val catalog = catalog(cloud)
        assertEquals("r1", catalog.manifest().getString("revision"))
        for (case in listOf("bad_signature", "tampered_manifest")) {
            CatalogSigning.cloud(root, case)
            nextDay()
            assertEquals("r1", catalog.manifest().getString("revision"))
            assertTrue(calm in catalog.lookup(listOf(calm)))
            assertEquals(File(CatalogSigning.fixture, "good/manifest.json").readText(), cached("manifest.json").readText())
            CatalogSigning.cloud(root, "good")
        }
        assertTrue(logged.any { it.contains("chữ ký") })
    }

    @Test
    fun an_older_signed_manifest_cannot_roll_the_catalog_back() {
        val cloud = CatalogSigning.cloud(root)
        val catalog = catalog(cloud)
        assertEquals(cases.getJSONObject("good").getString("issued"), catalog.manifest().getString("issued"))
        CatalogSigning.cloud(root, "older")
        nextDay()
        assertEquals("bản cũ hơn có chữ ký đúng vẫn bị bỏ", "r1", catalog.manifest().getString("revision"))
        CatalogSigning.cloud(root, "newer")
        nextDay()
        assertEquals("r2", catalog.manifest().getString("revision"))
        CatalogSigning.cloud(root, "good")
        nextDay()
        assertEquals("cả sau khi khởi động lại: mốc nằm trong bản đã cất", "r2", catalog(cloud).manifest().getString("revision"))
    }

    @Test
    fun the_cached_manifest_is_verified_again_when_read() {
        val cloud = CatalogSigning.cloud(root)
        catalog(cloud).manifest()
        val raw = cached("manifest.json").readBytes()
        raw[String(raw, Charsets.UTF_8).indexOf("\"r1\"") + 2] = '9'.code.toByte()
        cached("manifest.json").writeBytes(raw)
        cloud.deleteRecursively() // mất mạng
        assertNotNull(problem { catalog(cloud).manifest() })
    }

    @Test
    fun a_part_that_does_not_match_its_sha256_is_not_used() {
        val catalog = catalog(CatalogSigning.cloud(root, "tampered_part"))
        val found = catalog.lookup(listOf(calm, battle))
        assertEquals("link của mảnh bị tráo coi như không có - không bao giờ có link lạ", setOf(battle), found.keys)
        val file = cases.getJSONObject("tampered_part").getString("file")
        assertTrue(logged.any { it.contains(file) })
        assertFalse("mảnh hỏng không được cất", File(root, "cache/r1/$file").exists())
    }

    @Test
    fun a_part_missing_from_the_signed_files_is_not_used() {
        val catalog = catalog(CatalogSigning.cloud(root, "unlisted_part"))
        assertEquals(setOf(battle), catalog.lookup(listOf(calm, battle)).keys)
        assertTrue(logged.any { it.contains(cases.getJSONObject("unlisted_part").getString("unlisted")) })
    }

    @Test
    fun a_cached_part_that_was_changed_on_disk_is_downloaded_again() {
        val cloud = CatalogSigning.cloud(root)
        assertTrue(calm in catalog(cloud).lookup(listOf(calm)))
        val shard = MusicCatalog.shardOf(calm)
        val cachedPart = File(root, "cache/r1/tracks/$shard.json")
        cachedPart.writeText(cachedPart.readText().replace(calm, "https://y/calm.mp3"))
        assertEquals("mảnh đã cất bị sửa trên đĩa: tải lại bản đúng", setOf(calm), catalog(cloud).lookup(listOf(calm)).keys)
        assertEquals(File(CatalogSigning.fixture, "good/tracks/$shard.json").readText(), cachedPart.readText())
        cloud.deleteRecursively() // mất mạng, mảnh cất lại hỏng: bỏ chứ không dùng
        cachedPart.writeText("{}")
        val message = problem { catalog(cloud).lookup(listOf(calm)) }
        assertTrue(message.toString(), message?.contains("mạng") == true)
    }

    @Test
    fun the_signature_check_rejects_garbage_instead_of_throwing() {
        val raw = File(CatalogSigning.fixture, "good/manifest.json").readBytes()
        val signature = File(CatalogSigning.fixture, "good/manifest.json.sig").readBytes()
        assertTrue(Signatures.verifyBase64(CatalogSigning.publicKey, raw, signature))
        assertFalse(Signatures.verifyBase64(CatalogSigning.publicKey, raw, "khong phai base64!!".toByteArray()))
        assertFalse(Signatures.verifyBase64(CatalogSigning.publicKey, raw, ByteArray(0)))
        assertFalse(Signatures.verifyBase64(CatalogSigning.publicKey, raw + " ".toByteArray(), signature))
        assertFalse(Signatures.verify(ByteArray(5), raw, ByteArray(64)))
    }

    @Test
    fun the_embedded_app_key_is_the_one_the_desktop_app_carries() {
        val python = File("../../../abook/webui/remote_config.py").readText()
        val hex = Regex("""PUBLIC_KEY = bytes\.fromhex\("([0-9a-f]{64})"\)""").find(python)!!.groupValues[1]
        assertEquals(hex, RemoteConfig.PUBLIC_KEY.joinToString("") { "%02x".format(it) })
    }
}
