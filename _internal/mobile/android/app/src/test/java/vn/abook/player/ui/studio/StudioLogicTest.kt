package vn.abook.player.ui.studio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Logic thuần của Studio: nút chính theo trạng thái, nhãn / màu, nhóm, chương, và các chữ có số (port của ui/src/studio). */
class StudioLogicTest {
    private fun kind(book: StudioBook) = StudioLogic.primaryKind(book)

    @Test fun primaryButtonFollowsTheBookState() {
        assertEquals(PrimaryKind.Start, kind(studioBook(phase = "idle", chaptersCompleted = 0)))
        assertEquals(PrimaryKind.Starting, kind(studioBook(starting = true)))
        assertEquals(PrimaryKind.Stopping, kind(studioBook(running = true, stopping = true, canPause = true)))
        assertEquals(PrimaryKind.Unpause, kind(studioBook(running = true, paused = StudioPause.Listener, canPause = true)))
        assertEquals(PrimaryKind.Pause, kind(studioBook(running = true, canPause = true)))
        // Đang chạy mà không tạm dừng được: chỉ còn nghe phần đã xong, hay không có gì.
        assertEquals(PrimaryKind.Listen, kind(studioBook(running = true, canPause = false)))
        assertNull(kind(studioBook(running = true, canPause = false, chaptersCompleted = 0)))
        assertEquals(PrimaryKind.Dequeue, kind(studioBook(queuePosition = 2)))
        assertEquals(PrimaryKind.Record, kind(studioBook(phase = "casting", precastHeld = true)))
        assertEquals(PrimaryKind.Continue, kind(studioBook(phase = "synthesis")))
        assertEquals(PrimaryKind.Resume, kind(studioBook(phase = "analysis", analysisInterrupted = true)))
        assertEquals(PrimaryKind.Apply, kind(studioBook(phase = "done", pendingChanges = 3)))
        assertEquals(PrimaryKind.Continue, kind(studioBook(phase = "done", chaptersRedo = 2)))
        assertEquals(PrimaryKind.Listen, kind(studioBook(phase = "done")))
        assertNull(kind(studioBook(phase = "done", chaptersCompleted = 0)))
    }

    @Test fun resumeAsksOnlyWhileAnalysisIsCut() {
        assertTrue(StudioLogic.asksBeforeResume(studioBook(phase = "analysis", analysisInterrupted = true)))
        // Sau pha phân tích dừng thoải mái (AGENTS.md): không hỏi.
        assertFalse(StudioLogic.asksBeforeResume(studioBook(phase = "done", analysisInterrupted = true)))
        assertFalse(StudioLogic.asksBeforeResume(studioBook(phase = "synthesis")))
    }

    @Test fun statusSaysWhatIsHappeningAndHowLoudly() {
        assertEquals(StudioStatus("Còn 2 việc trước", StudioTone.Warning, false), StudioLogic.status(studioBook(queuePosition = 3)))
        assertEquals("Sắp tới lượt", StudioLogic.status(studioBook(queuePosition = 1)).label)
        assertEquals(StudioStatus("Đang khởi động", StudioTone.Accent, true), StudioLogic.status(studioBook(starting = true)))
        assertEquals(StudioStatus("Chờ bạn duyệt", StudioTone.Warning, false), StudioLogic.status(studioBook(phase = "casting", precastHeld = true)))
        assertEquals(StudioStatus("Đang thu âm", StudioTone.Accent, true), StudioLogic.status(studioBook(running = true)))
        // Tạm dừng và đang dừng: vẫn "làm" nhưng không còn chạy thật.
        assertFalse(StudioLogic.status(studioBook(running = true, paused = StudioPause.Battery)).live)
        assertFalse(StudioLogic.status(studioBook(running = true, stopping = true)).live)
        assertEquals(StudioTone.Success, StudioLogic.status(studioBook(phase = "done", statusLabel = "Đã xong")).tone)
        assertEquals(StudioTone.Danger, StudioLogic.status(studioBook(phase = "error")).tone)
        assertEquals(StudioTone.Warning, StudioLogic.status(studioBook(phase = "stopped")).tone)
        assertEquals(StudioTone.Muted, StudioLogic.status(studioBook(phase = "idle")).tone)
        val broken = StudioLogic.status(studioBook(broken = "Sổ làm việc hỏng"))
        assertEquals("Sổ làm việc hỏng", broken.label)
        assertEquals(StudioTone.Danger, broken.tone)
    }

    @Test fun onlyChaptersThatDeviateGetAMark() {
        assertNull(StudioLogic.chapterMark(studioChapter(1)))
        assertNull(StudioLogic.chapterMark(studioChapter(2, status = "pending", statusLabel = "Chờ")))
        assertNull(StudioLogic.chapterMark(studioChapter(3, status = "synthesizing", statusLabel = "Đang thu")))
        assertEquals(StudioMark("Chờ thu lại", StudioTone.Muted), StudioLogic.chapterMark(studioChapter(4, redo = true, statusLabel = "Chờ thu lại")))
        assertEquals(StudioTone.Danger, StudioLogic.chapterMark(studioChapter(5, status = "failed", statusLabel = "Lỗi"))?.tone)
        assertEquals(StudioTone.Warning, StudioLogic.chapterMark(studioChapter(6, status = "warning", statusLabel = "Cần xem"))?.tone)
        assertEquals(StudioTone.Warning, StudioLogic.chapterMark(studioChapter(7, statusLabel = "Mất file audio"))?.tone)
    }

    @Test fun groupsPutWhatNeedsYouFirstAndKeepOrder() {
        val working = studioBook("a", running = true)
        val queued = studioBook("b", queuePosition = 1)
        val held = studioBook("c", phase = "casting", precastHeld = true)
        val pending = studioBook("d", phase = "done", pendingChanges = 2)
        val rest = studioBook("e", phase = "done")
        val restTwo = studioBook("f", phase = "idle")
        val groups = StudioLogic.groups(listOf(rest, working, held, restTwo, queued, pending))
        assertEquals(listOf(StudioGroup.Working, StudioGroup.Review, StudioGroup.Rest), groups.map { it.first })
        assertEquals(listOf("a", "b"), groups[0].second.map { it.id })
        assertEquals(listOf("c", "d"), groups[1].second.map { it.id })
        assertEquals(listOf("e", "f"), groups[2].second.map { it.id })
        assertTrue(StudioLogic.groups(emptyList()).isEmpty())
    }

    @Test fun pollingBaseFollowsWhetherTheMachineIsWorking() {
        assertEquals(3000L, StudioLogic.bookInterval(StudioPage(studioBook(running = true), emptyList())))
        assertEquals(15000L, StudioLogic.bookInterval(StudioPage(studioBook(), emptyList())))
        assertEquals(15000L, StudioLogic.bookInterval(null))
        assertEquals(5000L, StudioLogic.listInterval(listOf(studioBook(), studioBook("x", running = true))))
        assertEquals(15000L, StudioLogic.listInterval(listOf(studioBook())))
        assertEquals(15000L, StudioLogic.listInterval(null))
    }

    @Test fun percentNeverClaimsDoneBeforeItIs() {
        assertEquals("0%", StudioText.percent(0f))
        assertEquals("<1%", StudioText.percent(0.004f))
        assertEquals("40%", StudioText.percent(0.4f))
        assertEquals("99%", StudioText.percent(0.998f))
        assertEquals("100%", StudioText.percent(1f))
        assertEquals("0%", StudioText.percent(Float.NaN))
        assertEquals("100%", StudioText.percent(7f))
    }

    @Test fun etaSpeaksLikeTheWeb() {
        assertEquals("sắp xong", StudioText.eta(30.0))
        assertEquals("sắp xong", StudioText.eta(30.0, 0.9f))
        assertEquals("còn dưới 2 phút", StudioText.eta(30.0, 0.2f))
        assertEquals("còn khoảng 2 phút", StudioText.eta(120.0))
        assertEquals("còn khoảng 1 giờ 5 phút", StudioText.eta(3900.0))
        assertNull(StudioText.etaOf(studioBook()))
        assertEquals("pha thu âm còn khoảng 5 phút", StudioText.etaOf(studioBook(eta = StudioEta("synthesis", 300.0))))
        assertEquals("pha phân tích sắp xong", StudioText.etaOf(studioBook(eta = StudioEta("analysis", 20.0), overall = 0.9f)))
        assertTrue(StudioText.etaOf(studioBook(eta = StudioEta("speaker", 600.0)))!!.startsWith("pha xác định người nói"))
    }

    @Test fun progressNoteHasOneVoicePerState() {
        assertEquals("đang dừng", StudioText.progressNote(studioBook(running = true, stopping = true)))
        assertEquals("", StudioText.progressNote(studioBook(running = true, paused = StudioPause.Listener)))
        assertEquals("chờ bạn duyệt rồi bấm Thu âm", StudioText.progressNote(studioBook(running = true, paused = StudioPause.Listener, precastHeld = true)))
        assertEquals("đang ước tính thời gian", StudioText.progressNote(studioBook(running = true)))
        assertEquals("", StudioText.progressNote(studioBook()))
        assertEquals("pha thu âm còn khoảng 5 phút", StudioText.progressNote(studioBook(running = true, eta = StudioEta("synthesis", 300.0))))
    }

    @Test fun statusLineAddsChaptersOnlyWhenThereAreSome() {
        assertEquals("Đang thu âm · 4/10 chương", StudioText.statusLine(studioBook()))
        assertEquals("Chưa bắt đầu", StudioText.statusLine(studioBook(phase = "idle", statusLabel = "Chưa bắt đầu")))
        assertEquals("Đang thu âm", StudioText.statusLine(studioBook(chaptersTotal = 0)))
    }

    @Test fun stopWarnsAboutAnalysisAndPutsPauseFirst() {
        val analysis = studioBook(phase = "analysis", running = true, canPause = true)
        assertEquals("Dừng phân tích?", StudioText.stopTitle(analysis))
        assertEquals("Vẫn dừng", StudioText.stopConfirm(analysis))
        val lines = StudioText.stopLines(analysis)
        assertTrue(lines.first().contains(StudioText.ANALYSIS_CUT_COST))
        assertTrue(lines.last().contains("Tạm dừng"))
        val synthesis = studioBook(running = true)
        assertEquals("Dừng thu âm?", StudioText.stopTitle(synthesis))
        assertEquals("Dừng", StudioText.stopConfirm(synthesis))
        // Đã tạm dừng thì không mời bấm "Tạm dừng" lần nữa.
        assertFalse(StudioText.stopLines(studioBook(phase = "analysis", running = true, paused = StudioPause.Listener)).last().contains("bấm Tạm dừng"))
    }

    @Test fun buttonLabelsAreShortAndAddressNobodyTechnically() {
        val book = studioBook(pendingChanges = 3)
        for (kind in PrimaryKind.entries) {
            val label = StudioText.label(kind, book)
            val words = label.trim().split(Regex("\\s+")).size
            assertTrue("\"$label\" quá dài", words in 1..5)
            for (word in listOf("API", "JSON", "HTTP", "poll", "checkpoint", "listenOnly")) assertFalse("\"$label\" có \"$word\"", label.contains(word, ignoreCase = true))
        }
        assertEquals("Áp dụng 3 thay đổi", StudioText.label(PrimaryKind.Apply, book))
        assertEquals("Thu âm", StudioText.label(PrimaryKind.Unpause, studioBook(precastHeld = true)))
        assertTrue(StudioText.inert(PrimaryKind.Starting) && StudioText.inert(PrimaryKind.Stopping) && !StudioText.inert(PrimaryKind.Pause))
    }

    @Test fun noStudioTextBreaksTheCopyRules() {
        val texts = buildList {
            add(StudioText.PERMISSION_TITLE); add(StudioText.permissionLine("Máy bàn")); add(StudioText.MISMATCH); add(StudioText.NO_PROJECTS_HINT)
            add(StudioText.UNPAIRED); add(StudioText.GONE); add(StudioText.OFFLINE); addAll(StudioText.resumeLines(studioBook())); add(StudioText.APPLY_LINE)
        }
        for (text in texts) {
            assertFalse(text, text.endsWith("..."))
            assertFalse(text, text.contains("…"))
            for (mark in listOf("hòa", "khóa", "xóa", "tùy", "thúy")) assertFalse("$text có dấu kiểu mới \"$mark\"", text.contains(mark))
        }
    }

    @Test fun permissionLineNamesTheMachineMidSentence() {
        assertEquals("Bật “Cho phép điều khiển sản xuất” trên máy NGDtuanh-Lecoo rồi quay lại.", StudioText.permissionLine("NGDtuanh-Lecoo"))
        assertEquals("Bật “Cho phép điều khiển sản xuất” trên máy bàn rồi quay lại.", StudioText.permissionLine("Máy bàn"))
    }
}
