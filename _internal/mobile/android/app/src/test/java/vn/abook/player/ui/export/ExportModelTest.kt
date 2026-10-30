package vn.abook.player.ui.export

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Chữ và mô hình của màn Xuất: chữ và số của ba kiểu xuất (M4B, MP3, sách nói).
 */
class ExportModelTest {
    private fun plan(chapters: Int = 12, audio: Long = 36_000, estimate: Long? = null, ready: Int = 0, readySeconds: Long = 0, rereads: Int = 0, bytes: Long = 0) =
        AudiobookPlan(chapters, audio, estimate, ready, readySeconds, bytes, rereads, ExportMusic())

    private fun event(kind: ExportKind = ExportKind.M4b, block: ExportEvent.() -> ExportEvent = { this }) = ExportEvent(kind, "b", "r").block()

    // ---- ước của sách nói ----

    @Test
    fun `plan says how long the book is and how long the machine needs only when measured`() {
        assertTrue(Regex("""^12 chương · .*nghe\.$""").matches(ExportText.planText(plan())))
        assertFalse(ExportText.planText(plan()).contains("máy cần"))
        assertTrue(Regex("""nghe · máy cần .+\.$""").containsMatchIn(ExportText.planText(plan(estimate = 18_000))))
    }

    @Test
    fun `spoken duration`() {
        assertEquals("dưới 1 phút", ExportText.spokenDuration(20))
        assertEquals("khoảng 12 phút", ExportText.spokenDuration(12 * 60L))
        assertEquals("khoảng 1 giờ 20 phút", ExportText.spokenDuration(80 * 60L))
        assertEquals("khoảng 2 giờ", ExportText.spokenDuration(2 * 3600L))
    }

    @Test
    fun `resume text tells what is already read`() {
        assertEquals("", ExportText.resumeText(plan()))
        assertEquals("Đã đọc sẵn cả cuốn - chỉ còn ghép thành file, không đọc lại.", ExportText.resumeText(plan(ready = 12)))
        assertEquals("Đã đọc sẵn khoảng 52% - phần này xuất ngay, không đọc lại.", ExportText.resumeText(plan(chapters = 3, ready = 1, readySeconds = 187, audio = 360)))
        assertEquals("Đã đọc sẵn khoảng 1% - phần này xuất ngay, không đọc lại.", ExportText.resumeText(plan(readySeconds = 400)))
        assertEquals("", ExportText.resumeText(plan(readySeconds = 40)))
        // Chưa đủ cả cuốn thì không nói 100%.
        assertEquals("Đã đọc sẵn khoảng 99% - phần này xuất ngay, không đọc lại.", ExportText.resumeText(plan(chapters = 3, ready = 2, readySeconds = 359, audio = 360)))
    }

    @Test
    fun `space text names the free space needed`() {
        assertTrue(ExportText.spaceText(plan(bytes = 600L * 1048576)).contains("600 MB"))
        assertTrue(ExportText.spaceText(plan(bytes = 3L * 1073741824)).contains("3 GB"))
    }

    @Test
    fun `long music runs suggest the charger and never block`() {
        assertTrue(ExportText.chargerHint(true, 21).contains("cắm sạc"))
        assertEquals("", ExportText.chargerHint(true, 20))
        assertEquals("", ExportText.chargerHint(false, 99))
    }

    @Test
    fun `reread text only when there are rereads`() {
        assertEquals("12 đoạn phải đọc lại vì đổi nhạc nền (bản đọc cũ đã được dọn khỏi máy).", ExportText.rereadText(plan(rereads = 12)))
        assertEquals("", ExportText.rereadText(plan(rereads = 0)))
    }

    @Test
    fun `an online voice names where the whole book goes`() {
        assertEquals("", ExportText.wholeBookNotice(ExportVoice("x", "Giọng", "device", online = false)))
        assertTrue(Regex("cả cuốn.*Microsoft").containsMatchIn(ExportText.wholeBookNotice(ExportVoice("x", "Giọng", "edge", online = true))))
        assertTrue(Regex("Azure Speech.*khoá của bạn").containsMatchIn(ExportText.wholeBookNotice(ExportVoice("x", "Giọng", "azure", online = true))))
        assertTrue(ExportText.wholeBookNotice(ExportVoice("x", "Giọng", "khac", online = true)).contains("dịch vụ ngoài"))
    }

    @Test
    fun `background help points the way by maker`() {
        for (maker in listOf("OPPO", "realme", "OnePlus")) {
            assertEquals("Trong trang mở ra: Pin → bật “Cho phép hoạt động dưới nền” và “Cho phép tự động khởi chạy”.", ExportText.backgroundHelp(maker))
        }
        assertTrue(ExportText.backgroundHelp("Xiaomi").startsWith("Trong trang mở ra: Tiết kiệm pin → chọn “Không hạn chế”"))
        assertTrue(ExportText.backgroundHelp("samsung").startsWith("Trong trang mở ra: Pin → chọn “Không hạn chế”"))
        assertTrue(ExportText.backgroundHelp("Google").contains("tuỳ máy"))
        assertTrue(ExportText.backgroundHelp("").contains("tuỳ máy"))
    }

    // ---- tiến độ ----

    @Test
    fun `progress counts chapters and the percent of the whole book`() {
        assertEquals("12 chương", ExportText.progress(event(), 12).text)
        assertEquals("Đang chuẩn bị", ExportText.progress(event(), 0).text)
        assertEquals("3/12 chương · 27%", ExportText.progress(event { copy(done = 3, total = 12, percent = 27) }, 12).text)
        assertEquals("12/12 chương · 99%", ExportText.progress(event { copy(done = 12, total = 12, percent = 100) }, 12).text)
        assertEquals("0/12 chương", ExportText.progress(event { copy(done = 0, total = 12) }, 12).text)
    }

    @Test
    fun `progress fraction follows the percent or the chapters done`() {
        assertEquals(0.27f, ExportText.progress(event { copy(done = 3, total = 12, percent = 27) }).fraction!!, 0.001f)
        assertEquals(0.25f, ExportText.progress(event(ExportKind.Mp3) { copy(done = 3, total = 12) }).fraction!!, 0.001f)
        assertNull(ExportText.progress(event()).fraction)
    }

    @Test
    fun `audiobook progress names the chapter, the percent and what it waits for`() {
        val base = event(ExportKind.Audiobook) { copy(phase = "voice", chapter = 3, chapters = 12, percent = 27) }
        assertEquals("Chương 3/12 · 27%", ExportText.progress(base).text)
        assertEquals("Chương 3/12 · 27% · còn khoảng 2 giờ", ExportText.progress(base.copy(secondsLeft = 7200)).text)
        assertEquals("Chương 3/12 · 27% · nhường cho chương đang nghe", ExportText.progress(base.copy(waiting = "listening")).text)
        assertEquals("Chương 3/12 · 27% · Đang chờ mạng", ExportText.progress(base.copy(waiting = "network")).text)
        assertEquals("Tạm nhường cho chương đang nghe", ExportText.progress(base.copy(waiting = "listening")).spoken)
        assertEquals("Đang ghép file âm thanh · Chương 12/12", ExportText.progress(base.copy(phase = "encode", chapter = 12)).text)
    }

    @Test
    fun `music phases are named like the computer`() {
        assertEquals("Đang trộn nhạc chương 3/12", ExportText.progress(event { copy(phase = "music", chapter = 3, chapters = 12, percent = 40) }).text)
        assertEquals("Đang tải nhạc nền 2/3 bài", ExportText.progress(event { copy(phase = "music-fetch", done = 1, total = 3) }).text)
        assertEquals("Đang kiểm đỉnh âm", ExportText.progress(event { copy(phase = "peaks", peakRound = 1) }).text)
        assertEquals("Mã hoá lại vì 2 chương vượt đỉnh (lượt 1)", ExportText.progress(event { copy(phase = "reencode", peakRound = 1, peakOver = 2) }).text)
        assertEquals(
            "Mã hoá lại vì 1 chương vượt đỉnh (lượt 2) · Đang trộn nhạc chương 3/12",
            ExportText.progress(event { copy(phase = "music", chapter = 3, chapters = 12, peakRound = 2, peakOver = 1) }).text,
        )
    }

    @Test
    fun `mp3 chapters phase names the chapter being written`() {
        val progress = ExportText.progress(event(ExportKind.Mp3) { copy(phase = "chapters", chapter = 3, chapters = 10) })
        assertEquals("Đang ghi chương 3/10", progress.text)
        assertEquals(0.2f, progress.fraction!!, 0.001f)
    }

    @Test
    fun `spoken progress only changes at the quarter marks`() {
        assertEquals("Đang xuất sách", ExportText.busy(ExportKind.Mp3))
        assertEquals("Đã dừng xuất M4B", ExportText.stoppedTitle(ExportKind.M4b))
        assertEquals("Đã dừng xuất sách nói", ExportText.stoppedTitle(ExportKind.Audiobook))
        assertEquals("Không xuất được", ExportText.failedTitle(ExportKind.Mp3))
        assertEquals("Không xuất được sách nói", ExportText.failedTitle(ExportKind.Audiobook))
        assertEquals("Máy không mở được thư mục - mở app Tệp rồi vào Music", ExportText.noFolderOpener("Music"))
        assertEquals("Đang xuất", ExportText.spokenProgress("Đang xuất", null))
        assertEquals("Đang xuất", ExportText.spokenProgress("Đang xuất", 0.1f))
        assertEquals("Đang xuất · 25%", ExportText.spokenProgress("Đang xuất", 0.3f))
        assertEquals("Đang xuất · 75%", ExportText.spokenProgress("Đang xuất", 0.99f))
        assertEquals("Đang xuất · 100%", ExportText.spokenProgress("Đang xuất", 1f))
        assertEquals(ExportText.progress(event { copy(done = 3, total = 12, percent = 30) }).spoken, ExportText.progress(event { copy(done = 3, total = 12, percent = 40) }).spoken)
    }

    // ---- kết thúc ----

    @Test
    fun `m4b finished names the file and its size`() {
        val done = ExportText.finished(event { copy(finished = true, name = "Truyện.m4b", size = 3L * 1048576, chapters = 6, chaptersTotal = 6) })
        assertEquals("Đã xuất M4B", done.title)
        assertEquals(listOf("Truyện.m4b · 3 MB"), done.lines)
        assertTrue(done.notes.isEmpty())
    }

    @Test
    fun `m4b with chapters still missing says how many are in the file`() {
        val done = ExportText.finished(event { copy(finished = true, name = "Truyện.m4b", size = 3L * 1048576, chapters = 4, chaptersTotal = 6) })
        assertEquals(listOf("4/6 chương - chương chưa xong không có trong file"), done.notes)
    }

    @Test
    fun `missing music is a note`() {
        val done = ExportText.finished(event(ExportKind.Audiobook) { copy(finished = true, name = "A.m4b", size = 1048576, musicMissing = 3) })
        assertEquals("Đã xuất sách nói", done.title)
        assertEquals(listOf("3 đoạn thiếu nhạc vì chưa tải được bài"), done.notes)
    }

    @Test
    fun `mp3 finished names the chapters and the folder`() {
        val done = ExportText.finished(event(ExportKind.Mp3) { copy(finished = true, files = 12, chaptersTotal = 12, folder = "Music/Sách thử", uri = "content://x") })
        assertEquals("Đã xuất 12 chương", done.title)
        assertEquals(listOf("Vào Music/Sách thử"), done.lines)
        assertTrue(done.notes.isEmpty())
        assertEquals("content://x", done.uri)
    }

    @Test
    fun `mp3 with chapters unfinished warns but a chosen selection does not`() {
        val partial = ExportText.finished(event(ExportKind.Mp3) { copy(finished = true, files = 3, chaptersTotal = 5, folder = "Music/Sách thử") })
        assertEquals(listOf("Các chương chưa làm xong sẽ không có trong bản xuất."), partial.notes)
        val chosen = ExportText.finished(event(ExportKind.Mp3) { copy(finished = true, files = 2, chaptersTotal = 5, selection = true) })
        assertTrue(chosen.notes.isEmpty())
    }

    @Test
    fun `what is left after stopping depends on the kind`() {
        assertEquals("4 chương đã ghi", ExportText.stoppedNote(event(ExportKind.Mp3) { copy(stopped = true, files = 4) }))
        assertEquals("File dở đã xoá", ExportText.stoppedNote(event()))
        assertTrue(ExportText.stoppedNote(event(ExportKind.Audiobook)).contains("làm tiếp"))
    }

    // ---- JSON của lõi ----

    @Test
    fun `core events become typed events and null fields stay null`() {
        val json = JSONObject("""{"bookId":"b","run":"r1","kind":"audiobook","phase":"voice","chapter":3,"chapters":12,"percent":27,"waiting":null,"secondsLeft":null}""")
        val parsed = ExportJson.event(json)!!
        assertEquals(ExportKind.Audiobook, parsed.kind)
        assertEquals(3, parsed.chapter)
        assertNull(parsed.waiting)
        assertNull(parsed.secondsLeft)
        assertFalse(parsed.ended)
        assertEquals("Chương 3/12 · 27%", ExportText.progress(parsed).text)
    }

    @Test
    fun `an event without a run or with an unknown kind is dropped`() {
        assertNull(ExportJson.event(JSONObject("""{"bookId":"b","kind":"mp3"}""")))
        assertNull(ExportJson.event(JSONObject("""{"bookId":"b","run":"r","kind":"abook"}""")))
        assertNotNull(ExportJson.event(JSONObject("""{"bookId":"b","run":"r"}"""), ExportKind.Mp3))
    }

    @Test
    fun `finished stopped and error events are the ones that end a run`() {
        assertTrue(event { copy(finished = true) }.ended)
        assertTrue(event { copy(stopped = true) }.ended)
        assertTrue(event { copy(error = "x") }.ended)
        assertFalse(event().ended)
    }

    @Test
    fun `a past export is stale when chapters changed since`() {
        val json = JSONObject("""{"kind":"mp3","target":"content://x/tree/primary%3AMusic/document/primary%3AMusic%2FS%C3%A1ch","changed":[2,5]}""")
        val past = ExportJson.past(json)!!
        assertTrue(past.stale)
        assertEquals("MP3 · Sách", ExportText.pastTitle(past))
        assertEquals("2 chương đã đổi từ lần xuất này", ExportText.pastLine(past))
        assertEquals("Còn mới", ExportText.pastLine(past.copy(changed = emptyList())))
        assertEquals("1 chương đã đổi - cần dựng lại cả file", ExportText.pastLine(PastExport(ExportKind.M4b, "x", listOf(1))))
        assertNull(ExportJson.past(JSONObject("""{"kind":"abook","target":"x","changed":[]}""")))
    }

    @Test
    fun `the menu row says what is going on`() {
        val running = ExportPhase.Running(ExportKind.Mp3, "r")
        assertEquals("Đang xuất · 27%", ExportText.menuHint(running, 0.27f))
        assertEquals("Đang xuất", ExportText.menuHint(running, null))
        assertEquals("Đã xuất xong", ExportText.menuHint(ExportPhase.Done(ExportResult(ExportKind.Mp3, "t", emptyList(), emptyList(), null)), null))
        assertNull(ExportText.menuHint(ExportPhase.Idle, null))
    }

    @Test
    fun `text only books export through the audiobook kind and only as m4b`() {
        assertEquals(ExportKind.Audiobook, ExportFormat.Mp3.kind(textOnly = true))
        assertEquals(ExportKind.Mp3, ExportFormat.Mp3.kind(textOnly = false))
        assertEquals(ExportKind.M4b, ExportFormat.M4b.kind(textOnly = false))
    }
}
