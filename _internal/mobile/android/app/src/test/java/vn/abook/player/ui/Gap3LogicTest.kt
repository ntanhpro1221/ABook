package vn.abook.player.ui

import kotlinx.coroutines.*
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import vn.abook.player.ui.addbook.*
import vn.abook.player.ui.data.*
import vn.abook.player.ui.devices.*
import vn.abook.player.ui.editbook.SyncText
import vn.abook.player.ui.nowplaying.PrepareText
import vn.abook.player.ui.voice.VoiceText

class Gap3LogicTest {
    @Test fun bulkImportKeepsTheCurrentChoiceAndContinuesAfterAnIndividualFailure() = runBlocking {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val preview = ImportPreview("B", chapters=listOf(ImportChapter(1,"C")), suggestions=listOf(Suggestion(1,"Dịch: X")))
        val choices = mutableListOf<Set<String>>()
        var discarded = 0
        val source = object : ImportSource by FakeImportSource(preview) {
            override suspend fun add(ref: String, preview: ImportPreview, choice: ImportChoices): Pair<String,Boolean> {
                choices += choice.skipped
                if (choices.size == 1) error("File đang bận")
                return "b${choices.size}" to false
            }
            override suspend fun discard(ref: String) { discarded++ }
        }
        try {
            val queue = ImportQueue(source, scope)
            queue.enqueue(listOf("one","two","three"))
            queue.choose { it.copy(skipped=setOf("Dịch: X")) }
            queue.addRest()
            assertEquals(listOf(setOf("Dịch: X"), emptySet<String>(), emptySet<String>()), choices)
            assertEquals(1, discarded)
            assertEquals(listOf(ImportStage.Error,ImportStage.Added,ImportStage.Added), queue.state.value.items.map { it.stage })
            assertTrue(queue.state.value.items.first().problem.contains("File đang bận"))
            assertEquals("Đã thêm 2 sách", ImportLogic.summary(queue.state.value.items))
            assertFalse(queue.state.value.addingRest)
        } finally { scope.cancel() }
    }
    @Test fun productionReadsTheActualLibraryArrayAndAllLiveFields() {
        val rows = Production.catalogue("""[{"id":"b","producing":true,"paused":false,"pauseReason":"listener","eta":{"phase":"speaker","seconds":300}},{"id":"c","producing":false,"paused":true},null]""")
        assertEquals(setOf("b", "c"), rows.keys)
        assertEquals(Production(true, false, "listener", "speaker", 300.0), rows["b"])
        assertEquals(Production(false, true, null, null, null), rows["c"])
        assertTrue(Production.catalogue("[]").isEmpty())
        assertEquals("Đang làm · chương đầu nghe được sau khoảng 15 phút", ProductionText.upcoming(ListenBook("b", "B", producing=true, etaPhase="analysis", etaSeconds=300.0)))
    }
    @Test fun livePhaseAndCompletionChangesReachStateFlowSubscribers() {
        assertNotEquals(ListenBook("b", "B", producing=true, etaPhase="analysis", etaSeconds=1.0), ListenBook("b", "B", producing=true, etaPhase="tts", etaSeconds=1.0))
        assertNotEquals(ListenBook("b", "B", complete=false), ListenBook("b", "B", complete=true))
    }
    @Test fun aFinishedBulkImportDoesNotAutoAcceptTheNextFile() = runBlocking {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        try {
            val source = FakeImportSource(ImportPreview("B", chapters=listOf(ImportChapter(1,"C"))))
            val queue = ImportQueue(source, scope)
            queue.enqueue(listOf("one", "two")); queue.addRest()
            assertFalse(queue.state.value.addingRest)
            queue.enqueue(listOf("three"))
            assertNotNull(queue.state.value.preview)
            assertEquals(2, source.adds)
        } finally { scope.cancel() }
    }
    @Test fun releasesCompareNumericPartsAndHandleMissingAssets() {
        assertTrue(AppRelease.newer("v0.4.150", "0.4.99"))
        assertFalse(AppRelease.newer("0.4.9", "0.4.99"))
        assertFalse(AppRelease.newer("0.4.99", "v0.4.99.0"))
        assertNull(AppRelease.parse(JSONObject()))
        assertEquals(AppRelease("0.4.150", "page", null), AppRelease.parse(JSONObject().put("tag_name", "v0.4.150").put("html_url", "page")))
    }
    @Test fun recoveryCopyTitlePreservesBookDigits() {
        assertEquals("Tập 12", OldSave("Tập 12 20261029-123456-2.abookproj", 500, 0).title)
        assertEquals("Tập 12", OldSave("Tập 12.abook", 500, 0).title)
    }
    @Test fun productionComesFromFieldsAndDoesNotGuessRunningFromMissingAudio() {
        val p = Production.parse(JSONObject().put("producing", true).put("paused", false).put("pauseReason", "battery"))
        assertTrue(p.producing); assertEquals("battery", p.pauseReason)
        val stopped = ListenBook("b", "B", complete=false, remote=RemoteRef("Máy A"))
        assertEquals("Chưa có chương nghe được · làm trên Máy A", ProductionText.upcoming(stopped))
        val running = ListenBook("b", "B", complete=false, remote=RemoteRef("Máy A"), producing=true, pauseReason="battery")
        assertEquals("Đang tạm dừng trên Máy A", ProductionText.upcoming(running))
        assertEquals("Đang thu âm", BookPage.chapterLine(ChapterLine(1,"C",0.0,false,false,0f,false),true))
    }
    @Test fun onlinePreparationStatesWhereTextGoesAndWhatCanBeHeardOffline() {
        assertTrue(PrepareText.canPrepare("edge:vi-VN-HoaiMyNeural"))
        assertFalse(PrepareText.canPrepare("device:vi"))
        assertEquals("Làm trước để nghe khi không có mạng; chữ sẽ được gửi tới máy chủ Microsoft.", PrepareText.intro("edge:vi"))
        assertTrue(PrepareText.label(PrepareStatus(state="done",online=true)).contains("nghe được cả khi không có mạng"))
    }
    @Test fun studioBlockExplainsAllTheComputers() {
        assertEquals("Chưa ghép với máy tính nào", DeviceText.studioBlocked(emptyList()))
        assertTrue(DeviceText.studioBlocked(listOf("A","B")).startsWith("Máy tính A và B đều chỉ cho nghe"))
        assertTrue(DeviceText.studioBlocked(listOf("A","B","C")).startsWith("Các máy tính đã ghép"))
    }
    @Test fun voiceNoticesUseRealProviderAndGender() {
        assertEquals("Nam", VoiceText.gender("male")); assertEquals("Nữ", VoiceText.gender("female")); assertNull(VoiceText.gender(""))
        assertTrue(VoiceText.onlineNotice("azure")!!.contains("bằng khoá của bạn"))
        assertNull(VoiceText.onlineNotice("device"))
    }
    @Test fun syncKeepsPendingWarningsAndReceiptDetails() {
        val note=SyncText.note(JSONObject().put("pending",0).put("last",JSONObject().put("state","sent").put("at",1).put("waiting",2)),"Máy A")
        assertTrue(note.contains("Đã gửi về Máy A")); assertTrue(note.contains("2 việc đang chờ duyệt"))
        assertEquals("Đã gửi về A. Còn 2 thay đổi chưa gửi được - sẽ thử lại khi tới được A.",SyncText.sent(2,"A"))
    }
    @Test fun bulkImportsUseDefaultsAndNeverAcceptSuggestionsAutomatically() = runBlocking {
        val preview = ImportPreview("B",chapters=listOf(ImportChapter(1,"C")), suggestions=listOf(Suggestion(1,"Dịch: X")))
        val source=FakeImportSource(preview)
        val scope=CoroutineScope(SupervisorJob()+Dispatchers.Unconfined)
        try {
            val queue=ImportQueue(source,scope); queue.enqueue(listOf("one","two","three")); queue.choose { it.copy(skipped=setOf("Dịch: X")) }; queue.addRest()
            assertEquals(3,source.adds); assertTrue(source.addedChoices!!.skipped.isEmpty())
            assertEquals("Đã thêm 3 sách",ImportLogic.summary(queue.state.value.items))
        } finally { scope.cancel() }
    }
    @Test fun conflictingPackageWaitsForExplicitReplacement() = runBlocking {
        val scope=CoroutineScope(SupervisorJob()+Dispatchers.Unconfined)
        var replacements=0
        val source=object: ImportSource by FakeImportSource(ImportPreview("B",chapters=emptyList())) {
            override suspend fun prepare(item:ImportItem)=PreparedImport(null,"B.abook",packageReview=PackageReview("b","B","C","older"))
            override suspend fun replace(item:ImportItem): PreparedImport { replacements++; return PreparedImport(null,item.name,bookId="b") }
        }
        try {
            val queue=ImportQueue(source,scope); queue.enqueue(listOf("uri"))
            assertEquals(ImportStage.Review,queue.state.value.items[0].stage); assertEquals(0,replacements)
            queue.add(); assertEquals(1,replacements); assertEquals("b",queue.state.value.items[0].bookId)
        } finally { scope.cancel() }
    }
}
