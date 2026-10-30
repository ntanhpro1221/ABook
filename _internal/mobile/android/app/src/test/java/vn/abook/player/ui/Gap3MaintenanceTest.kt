package vn.abook.player.ui

import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test
import vn.abook.player.ui.data.*
import vn.abook.player.ui.devices.*

class Gap3MaintenanceTest {
    @Test fun recoveryExportsAndDeletesOnlyOnExplicitActionsAndReportsFailure() = runBlocking {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        var files = listOf(OldSave("B.abook", 1024, 0))
        val exports = mutableListOf<String>()
        var deletes = 0
        val core = object : SettingsCore by FakeSettingsCore() {
            override fun oldSaves() = files
            override fun exportOldSave(name: String, uri: String) { exports += "$name $uri" }
            override fun deleteOldSave(name: String) { deletes++; if (deletes == 1) error("Chỗ lưu đang bận"); files = emptyList() }
        }
        try {
            val repo = SettingsRepo(core, scope, Dispatchers.Unconfined)
            repo.loadMaintenance(); assertEquals(1, repo.oldSaves.value.size)
            assertEquals(0, deletes); assertTrue(exports.isEmpty())
            repo.exportOldSave("B.abook", "content://chosen")
            assertEquals(listOf("B.abook content://chosen"), exports)
            repo.deleteOldSave("B.abook")
            assertTrue(repo.problem.value.contains("Chỗ lưu đang bận")); assertEquals(1, repo.oldSaves.value.size)
            repo.deleteOldSave("B.abook")
            assertTrue(repo.oldSaves.value.isEmpty()); assertEquals("Đã xoá bản lưu cũ", repo.notice.value)
        } finally { scope.cancel() }
    }
    @Test fun releaseNoticeOnlyOffersANewerVersion() = runBlocking {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        var release = AppRelease("0.4.99", "page", null)
        val core = object : SettingsCore by FakeSettingsCore() { override fun release() = release }
        try {
            val repo = SettingsRepo(core, scope, Dispatchers.Unconfined)
            repo.loadMaintenance(); assertNull(repo.update.value)
            release = AppRelease("0.4.150", "page", "apk")
            repo.loadMaintenance(); assertEquals(release, repo.update.value)
        } finally { scope.cancel() }
    }
    @Test fun noticesRetainTheToggleAndExplainFailure() = runBlocking {
        val core = object : CompanionCore by FakeCompanionCore() {
            override suspend fun setNotices(enabled: Boolean): StudioNoticeState = error("Máy tính đang tắt")
        }
        val repo = CompanionRepo(core) { 1000 }
        assertFalse(repo.setNotices(true)); assertFalse(repo.state.value.notices.enabled)
        assertEquals("Chưa đổi được. Máy tính đang tắt", repo.state.value.problem)
    }
    @Test fun sharingCodeStopsPollingWhenItsScreenIsHidden() = runBlocking {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val fake = FakeDevicesSource().also { it.share = Share(running=true, code=Code("123456", 9999999999.0)) }
        var reads = 0
        val source = object : DevicesSource by fake { override suspend fun share(): Share { reads++; return fake.share } }
        try {
            val state = DevicesState(source, scope, pollMs=10)
            state.openShare(); delay(35); assertTrue(reads > 1)
            state.closeShare(); val stoppedAt = reads
            delay(35); assertEquals(stoppedAt, reads)
        } finally { scope.cancel() }
    }
}
