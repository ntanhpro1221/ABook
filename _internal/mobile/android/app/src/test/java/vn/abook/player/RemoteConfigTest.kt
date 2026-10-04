package vn.abook.player

import java.io.File
import java.security.PrivateKey
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Cấu hình từ xa trên điện thoại (RemoteConfig) - cùng luật với tests/test_remote_config.py: chỉ nhận file ký đúng, không quay lui, mất mạng vẫn chạy. */
class RemoteConfigTest {
    private lateinit var root: File
    private var now = System.currentTimeMillis()
    private val defaults = listOf(MusicCatalog.DEFAULT_SOURCE)

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-remote-config")
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
    }

    private fun publish(name: String, key: PrivateKey, issued: String, catalog: String, version: Int = 1): String {
        val folder = File(root, name).apply { mkdirs() }
        val raw = JSONObject().put("format", "abook-remote-config").put("version", version).put("issued", issued)
            .put("music", JSONObject().put("catalogs", org.json.JSONArray(listOf(catalog)))).toString().toByteArray()
        File(folder, "remote-config.json").writeBytes(raw)
        File(folder, "remote-config.json.sig").writeBytes(CatalogSigning.sign(raw, key))
        return File(folder, "remote-config.json").path
    }

    private fun config(vararg sources: String, open: (String) -> java.io.InputStream = MusicCatalog.Companion::openUrl) =
        RemoteConfig(File(root, "cache"), sources.toList(), CatalogSigning.publicKey, open, { now })

    @Test
    fun a_signed_config_moves_the_catalog_without_an_app_update() {
        val source = publish("github", CatalogSigning.testKey, "2026-10-02T01:00:00Z", "https://moi.example/")
        assertEquals(listOf("https://moi.example/"), config(source).musicCatalogs())
    }

    @Test
    fun a_config_signed_by_someone_else_is_ignored() {
        val source = publish("github", CatalogSigning.strangerKey(), "2026-10-02T01:00:00Z", "https://ke-xau.example/")
        assertEquals(defaults, config(source).musicCatalogs())
    }

    @Test
    fun an_older_signed_file_cannot_roll_the_app_back() {
        val new = publish("new", CatalogSigning.testKey, "2026-10-05T00:00:00Z", "https://moi.example/")
        assertEquals(listOf("https://moi.example/"), config(new).musicCatalogs())
        val old = publish("old", CatalogSigning.testKey, "2026-10-01T00:00:00Z", "https://cu.example/")
        assertEquals(listOf("https://moi.example/"), config(old).musicCatalogs())
    }

    @Test
    fun offline_uses_the_last_good_config_then_the_built_in_one() {
        val source = publish("github", CatalogSigning.testKey, "2026-10-02T01:00:00Z", "https://moi.example/")
        assertEquals(listOf("https://moi.example/"), config(source).musicCatalogs())
        File(source).delete() // mất mạng: bản đã cất (cả byte gốc lẫn .sig) còn dùng được
        assertEquals(listOf("https://moi.example/"), config(source).musicCatalogs())
        assertEquals("cất nguyên byte gốc", File(root, "github/remote-config.json.sig").readText(), File(root, "cache/remote-config.json.sig").readText())
        assertEquals(defaults, RemoteConfig(File(root, "chua_co"), listOf(source), CatalogSigning.publicKey, MusicCatalog.Companion::openUrl, { now }).musicCatalogs())
    }

    @Test
    fun a_tampered_cached_config_is_not_trusted() {
        val source = publish("github", CatalogSigning.testKey, "2026-10-02T01:00:00Z", "https://moi.example/")
        config(source).musicCatalogs()
        val cached = File(root, "cache/remote-config.json")
        cached.writeText(cached.readText().replace("moi.example", "ke-xau.example"))
        assertEquals(defaults, config(File(root, "khong_co").path).musicCatalogs())
    }

    @Test
    fun a_newer_format_than_the_app_understands_is_ignored() {
        val source = publish("github", CatalogSigning.testKey, "2026-10-02T01:00:00Z", "https://moi.example/", version = 2)
        assertEquals(defaults, config(source).musicCatalogs())
    }

    @Test
    fun only_web_addresses_are_accepted_for_the_catalog() {
        val source = publish("github", CatalogSigning.testKey, "2026-10-02T01:00:00Z", "file:///etc/passwd")
        assertEquals(defaults, config(source).musicCatalogs())
    }

    @Test
    fun the_network_is_asked_again_only_after_six_hours_or_on_demand() {
        val source = publish("github", CatalogSigning.testKey, "2026-10-02T01:00:00Z", "https://moi.example/")
        var opened = 0
        val counted = config(source, open = { url -> opened++; MusicCatalog.openUrl(url) })
        counted.get()
        assertEquals("một lần kiểm = đọc file + .sig", 2, opened)
        counted.get()
        assertEquals(2, opened)
        now += RemoteConfig.REFRESH_MS + 1
        counted.get()
        assertEquals(4, opened)
        counted.get(refresh = true)
        assertTrue(opened == 6)
    }

    @Test
    fun the_built_in_defaults_name_the_default_catalog() {
        assertEquals(defaults, RemoteConfig.DEFAULTS.getJSONObject("music").getJSONArray("catalogs").let { list -> (0 until list.length()).map { list.getString(it) } })
        assertEquals("", RemoteConfig.DEFAULTS.getString("issued"))
    }
}
