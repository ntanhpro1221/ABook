package vn.abook.player

import java.io.File
import java.io.ByteArrayInputStream
import java.util.zip.ZipInputStream
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class A116DiagnosticsTest {
    @Test fun workProgressIncludesDoneTotalAndPhaseThroughCollector() {
        val entry = Diagnostics.workEntry("work", "RUNNING", setOf("BookDownloadWorker"), 0, 0,
            mapOf("done" to "3", "total" to "10", "phase" to "download"))
        val saved = Diagnostics.fit(Diagnostics.assemble(listOf("work" to { JSONArray().put(entry) })))
        val progress = saved.getJSONArray("work").getJSONObject(0).getJSONObject("progress")
        assertEquals("3", progress.getString("done"))
        assertEquals("10", progress.getString("total"))
        assertEquals("download", progress.getString("phase"))
    }
    @Test fun realCastTokenAndDesktopUrlSafeCapabilityAreScrubbed() {
        val token = Dlna.Media("127.0.0.1").newToken()
        assertEquals(32, token.length)
        val desktop = java.util.Base64.getUrlEncoder().withoutPadding().encodeToString(ByteArray(16).also(java.security.SecureRandom()::nextBytes))
        for (capability in listOf(token, desktop)) for (suffix in listOf("", ".mp3")) {
            val safe = AppLog.scrub("http://192.168.1.2/c/$capability$suffix")
            assertFalse(safe.contains(capability))
            assertTrue(safe.contains("/c/***"))
        }
    }
    @Test fun privatePathsAndSourceFramesUseSharedFixture() {
        val cases = JSONArray(File("../../../tests/fixtures/diagnostics_paths.json").readText())
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            assertEquals(case.getString("raw"), case.getString("safe"), AppLog.scrub(case.getString("raw")))
        }
    }
    @Test fun recoveryMetadataIncludesPendingAndBlockedWithoutReadingProfiles() {
        val root = BookEditsFixtures.tempDir("a116-recovery")
        BookEditsFixtures.useStoreRoot(root)
        val broken = File(root, "state/private.json").apply { parentFile!!.mkdirs(); writeText("PROFILE-CONTENT") }
        Store.preserveCorrupt(broken, copyOnly = true)
        @Suppress("UNCHECKED_CAST")
        val blocked = Store::class.java.getDeclaredField("unpreservedData").apply { isAccessible = true }.get(null) as MutableSet<String>
        @Suppress("UNCHECKED_CAST")
        val pending = Store::class.java.getDeclaredField("pendingDataNotices").apply { isAccessible = true }.get(null) as MutableSet<String>
        try {
            blocked.add(broken.absolutePath)
            pending.add("PRIVATE-NOTICE")
            val report = Diagnostics.fit(Diagnostics.assemble(listOf("dataRecovery" to { Store.dataDiagnostics() })))
            val recovery = report.getJSONObject("dataRecovery")
            assertTrue(recovery.getBoolean("savingBlocked"))
            val rows = recovery.getJSONArray("notices")
            assertTrue((0 until rows.length()).any { rows.getJSONObject(it).optString("preservedFile").startsWith("private.json.corrupt-") })
            assertTrue((0 until rows.length()).any { rows.getJSONObject(it).optBoolean("pending") })
            assertFalse(report.toString().contains("PROFILE-CONTENT"))
            assertFalse(report.toString().contains("PRIVATE-NOTICE"))
            assertFalse(report.toString().contains(broken.absolutePath))
        } finally { blocked.clear(); pending.clear() }
    }

    @Test fun threeHundredLinesSurviveAssembleFitAndBundleWhileMetadataStaysBounded() {
        val log = (0 until 300).map { "line $it" }
        val cat = (0 until 300).map { "I/AudioTrack: line $it" }
        val report = Diagnostics.fit(Diagnostics.assemble(listOf(
            "log" to { JSONArray(log) }, "logcat" to { JSONArray(cat) }, "metadata" to { JSONArray(log) }
        )))
        ZipInputStream(ByteArrayInputStream(Diagnostics.bundle(report))).use { zip ->
            assertEquals("chan-doan.json", zip.nextEntry.name)
            val saved = JSONObject(zip.readBytes().toString(Charsets.UTF_8))
            assertEquals(log, (0 until 300).map { saved.getJSONArray("log").getString(it) })
            assertEquals(cat, (0 until 300).map { saved.getJSONArray("logcat").getString(it) })
            assertEquals(200, saved.getJSONArray("metadata").length())
            assertEquals("nhat-ky.txt", zip.nextEntry.name)
            val text = zip.readBytes().toString(Charsets.UTF_8)
            assertTrue(text.contains("line 0\nline 1\n"))
            assertTrue(text.contains("I/AudioTrack: line 299"))
        }
    }
}
