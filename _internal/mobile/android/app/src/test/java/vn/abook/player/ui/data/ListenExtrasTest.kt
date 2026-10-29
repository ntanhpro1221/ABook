package vn.abook.player.ui.data

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.TimeZone

/** Lịch sử nghe, hồ sơ nghe, dàn nhân vật của trang sách (BookScreen.tsx HistoryTab / RecordPicker / CastList, CastEdits.tsx, MergePeople.tsx): chữ và luật y như bản web. */
class ListenExtrasTest {
    private val utc = TimeZone.getTimeZone("UTC")

    /** 2026-10-29 12:00 UTC. */
    private val now = 1_793_275_200_000L
    private val nowSeconds = now / 1000.0

    private fun session(id: String, startedAt: Double, minutes: Double = 10.0, from: Int = 1, to: Int = 2) = JSONObject()
        .put("id", id).put("startedAt", startedAt).put("endedAt", startedAt + minutes * 60).put("listened", minutes * 60)
        .put("from", JSONObject().put("chapterId", from).put("seconds", 12.0)).put("to", JSONObject().put("chapterId", to).put("seconds", 65.0))

    private fun state(vararg sessions: JSONObject) = JSONObject().put("sessions", JSONArray(sessions.toList()))

    // ---- lịch sử ----

    @Test
    fun `sessions are read in recorded order and broken ones are dropped`() {
        val broken = JSONObject().put("id", "x").put("startedAt", 1.0)
        val read = History.sessions(state(session("a", nowSeconds - 100), broken, session("b", nowSeconds - 50)))
        assertEquals(listOf("a", "b"), read.map { it.id })
        assertEquals(2, read[0].toChapter)
        assertEquals(65.0, read[0].toSeconds, 0.0)
        assertTrue(History.sessions(null).isEmpty())
        assertTrue(History.sessions(JSONObject()).isEmpty())
    }

    @Test
    fun `day labels say today and yesterday and otherwise the weekday with day and month`() {
        assertEquals("Hôm nay", History.dayLabel(nowSeconds - 3600, now, utc))
        assertEquals("Hôm qua", History.dayLabel(nowSeconds - 86_400, now, utc))
        // 2026-10-26 là thứ Hai.
        assertEquals("Thứ Hai, 26/10", History.dayLabel(nowSeconds - 3 * 86_400, now, utc))
        // Cuối ngày hôm qua vẫn là "Hôm qua", không phải "Hôm nay".
        assertEquals("Hôm qua", History.dayLabel(nowSeconds - 12 * 3600 - 60, now, utc))
    }

    @Test
    fun `sessions group by day with the newest first`() {
        val sessions = History.sessions(
            state(
                session("old", nowSeconds - 3 * 86_400),
                session("yesterday", nowSeconds - 86_400),
                session("morning", nowSeconds - 4 * 3600),
                session("noon", nowSeconds - 600),
            ),
        )
        val days = History.byDay(sessions, now, utc)
        assertEquals(listOf("Hôm nay", "Hôm qua", "Thứ Hai, 26/10"), days.map { it.label })
        assertEquals(listOf("noon", "morning"), days[0].sessions.map { it.id })
        assertEquals("2 lượt nghe", History.daySummary(days[0]))
        assertEquals("1 lượt nghe", History.daySummary(days[1]))
    }

    @Test
    fun `a session line shows one clock when it starts and ends in the same minute`() {
        val long = History.sessions(state(session("a", nowSeconds - 3600, minutes = 23.0)))[0]
        assertEquals("11:00-11:23", History.clockRange(long, utc))
        assertEquals("11:00-11:23 · 23 phút", History.headline(long, utc))
        val blink = History.sessions(state(session("b", nowSeconds - 3600, minutes = 0.2)))[0]
        assertEquals("11:00", History.clockRange(blink, utc))
    }

    @Test
    fun `a route names both chapters with their clocks and says when a chapter was removed`() {
        val one = History.sessions(state(session("a", nowSeconds, from = 1, to = 9)))[0]
        val titles = mapOf(1 to "Chương 1")
        assertEquals("Chương 1 0:12 → chương đã gỡ 1:05", History.route(one, titles::get))
        assertEquals("Nghe tiếp từ 1:05", History.resumeLabel(one))
    }

    @Test
    fun `the week total counts only sessions started in the last seven days`() {
        val sessions = History.sessions(state(session("recent", nowSeconds - 86_400, minutes = 30.0), session("stale", nowSeconds - 9 * 86_400, minutes = 60.0)))
        assertEquals(1800.0, History.weekListened(sessions, now), 0.0)
        assertEquals("7 ngày qua: 30 phút nghe cuốn này.", History.weekLine(1800.0))
    }

    // ---- hồ sơ ----

    private fun records() = JSONArray()
        .put(JSONObject().put("id", "r1").put("name", "Mặc định").put("updatedAt", nowSeconds - 86_400).put("active", true))
        .put(JSONObject().put("id", "r2").put("name", "Lần nghe 2").put("updatedAt", JSONObject.NULL).put("active", false))
        .put(JSONObject().put("name", "không mã"))

    @Test
    fun `records are read with their last heard day and the one in use`() {
        val read = Records.parse(records())
        assertEquals(listOf("r1", "r2"), read.map { it.id })
        assertTrue(read[0].active)
        assertFalse(read[1].active)
        assertNull(read[1].updatedAt)
        assertEquals("nghe gần nhất hôm qua", Records.lastHeard(read[0], now, utc))
        assertEquals("chưa nghe", Records.lastHeard(read[1], now, utc))
        assertTrue(Records.parse(null).isEmpty())
    }

    @Test
    fun `a new record is offered the next numbered name`() {
        assertEquals("Lần nghe 1", Records.suggestedName(0))
        assertEquals("Lần nghe 3", Records.suggestedName(2))
    }

    @Test
    fun `dialog words depend on the action and on whether another record would take over`() {
        assertEquals("Nghe lại từ đầu", Records.title(RecordAction.Create, "Mặc định"))
        assertEquals("Xoá hồ sơ “Mặc định”?", Records.title(RecordAction.Delete, "Mặc định"))
        assertEquals("Chuyển hồ sơ “Mặc định” sang cuốn khác", Records.title(RecordAction.Move, "Mặc định"))
        assertNull(Records.description(RecordAction.Rename, 3))
        assertTrue(Records.description(RecordAction.Delete, 1)!!.endsWith("đây là hồ sơ duy nhất nên cuốn sẽ như chưa nghe lần nào."))
        assertTrue(Records.description(RecordAction.Delete, 2)!!.endsWith("cuốn chuyển sang hồ sơ nghe gần nhất còn lại."))
        assertTrue(Records.description(RecordAction.Move, 1)!!.endsWith("Cuốn này sẽ như chưa nghe lần nào."))
        assertTrue(Records.description(RecordAction.Move, 2)!!.endsWith("Cuốn này chuyển sang hồ sơ nghe gần nhất còn lại."))
        assertEquals(listOf("Tạo và nghe", "Lưu", "Chuyển", "Xoá hồ sơ"), listOf(RecordAction.Create, RecordAction.Rename, RecordAction.Move, RecordAction.Delete).map(Records::confirmLabel))
    }

    @Test
    fun `notes after a record change say what happened`() {
        assertEquals("Hồ sơ mới “Lần nghe 2” - nghe từ chương đầu", Records.createdNote("Lần nghe 2"))
        assertEquals("Hồ sơ mới “không tên” - nghe từ chương đầu", Records.createdNote(""))
        assertEquals("Đang dùng hồ sơ “Mặc định”", Records.switchedNote("Mặc định"))
        assertEquals("Đã xoá hồ sơ “Lần nghe 2”", Records.deletedNote("Lần nghe 2"))
        assertEquals("Đã chuyển hồ sơ “A” sang “B”", Records.movedNote("A", "B"))
    }

    // ---- dàn nhân vật ----

    private fun person(name: String, lines: Int = 12, first: String = "Chương 1", voice: String? = "Bảo Trang", extra: JSONObject.() -> Unit = {}) = JSONObject()
        .put("name", name).put("displayName", name).put("gender", "Nữ").put("lines", lines).put("seconds", 90.0).put("firstChapter", first)
        .put("voice", if (voice == null) JSONObject.NULL else JSONObject().put("key", "k").put("preset", "bao_trang").put("label", voice).put("tone", "trầm hẳn"))
        .put("sampleId", 3).apply(extra)

    private fun cast(characters: List<JSONObject>, extras: List<JSONObject> = emptyList()) = JSONObject()
        .put("narrator", JSONObject().put("voice", "Hoài My").put("lines", 40).put("seconds", 3600.0).put("redo", 2))
        .put("characters", JSONArray(characters)).put("extras", JSONArray(extras)).toString()

    @Test
    fun `the cast is read with narrator characters and extras`() {
        val view = Cast.parse(cast(listOf(person("Thanh_Bình")), listOf(person("Lính gác 1", lines = 1))))!!
        assertEquals("Hoài My", Cast.narratorName(view.narrator))
        assertEquals("40 câu dẫn truyện · 1 giờ · 2 câu chờ thu lại", Cast.narratorCountLine(view.narrator))
        assertEquals(1, view.characters.size)
        assertEquals(1, view.extras.size)
        assertFalse(view.isEmpty)
        val first = view.characters[0]
        assertEquals("Bảo Trang · chỉnh trầm hẳn so với giọng gốc", Cast.voiceLine(first))
        assertEquals("12 câu · 2 phút · từ Chương 1", Cast.countLine(first))
        assertEquals(3, first.sampleId)
    }

    @Test
    fun `a book without cast file has an empty cast and a broken file has none`() {
        assertTrue(Cast.parse(null)!!.isEmpty)
        assertTrue(Cast.parse("")!!.isEmpty)
        assertNull(Cast.parse("{không phải json"))
        assertEquals("Mặc định", Cast.narratorName(Cast.parse(null)!!.narrator))
    }

    @Test
    fun `a person without a voice says so`() {
        val view = Cast.parse(cast(listOf(person("Ẩn danh", voice = null))))!!
        assertEquals("Chưa có giọng", Cast.voiceLine(view.characters[0]))
    }

    @Test
    fun `names lose underscores and initials skip roman numerals`() {
        assertEquals("Thanh Bình", Cast.cleanName("Thanh__Bình "))
        assertEquals("TB", Cast.initials("Thanh_Bình"))
        assertEquals("L", Cast.initials("Louis XIV"))
        assertTrue(Cast.hue("bao_trang") in 0..359)
        assertEquals(Cast.hue("bao_trang"), Cast.hue("bao_trang"))
    }

    @Test
    fun `waiting lines say the book maker will apply what the listener asked`() {
        val asked = Cast.parse(
            cast(listOf(person("A", extra = { put("pendingVoice", JSONObject().put("preset", "x").put("label", "Mai Phương").put("gender", "Nam")) }), person("B", extra = { put("mergedInto", "Thanh_Bình") }))),
        )!!.characters
        assertEquals("Đang chờ máy làm sách: giọng Mai Phương · nam", Cast.pendingLine(asked[0]))
        assertNull(Cast.pendingLine(asked[1]))
        assertEquals("Đang chờ máy làm sách: gộp vào Thanh Bình", Cast.mergeLine(asked[1]))
        assertEquals(Gender.Male, Cast.shownGender(asked[0]))
        assertEquals("Mai Phương", Cast.voiceToUse(asked[0]))
    }

    @Test
    fun `people from later chapters stay hidden until the listener asks`() {
        val chapters = listOf(
            ChapterLine(1, "Chương 1", 0.0, true, false, 0f, false, shortTitle = "Một"),
            ChapterLine(2, "Chương 2", 0.0, true, false, 0f, false),
            ChapterLine(3, "Chương 3", 0.0, true, false, 0f, false),
        )
        val reached = Cast.reachedTitles(chapters, 2)
        assertEquals(setOf("Chương 1", "Một", "Chương 2"), reached)
        // Chưa nghe gì: tới chương đầu.
        assertEquals(setOf("Chương 1", "Một"), Cast.reachedTitles(chapters, null))
        val people = Cast.parse(cast(listOf(person("A", first = "Chương 1"), person("B", first = "Chương 3"), person("C", first = ""))))!!.characters
        assertEquals(1, Cast.ahead(people, reached))
        assertEquals(listOf("A", "C"), Cast.visible(people, reached, later = false).map { it.name })
        assertEquals(3, Cast.visible(people, reached, later = true).size)
        assertEquals(3, Cast.visible(people, null, later = false).size)
        assertEquals("Hiện chương sau · 1 người", Cast.laterLabel(false, 1))
        assertEquals("Ẩn chương sau · 1 người", Cast.laterLabel(true, 1))
    }

    @Test
    fun `merge targets exclude the person and those without a voice and follow the search words`() {
        val people = Cast.parse(cast(listOf(person("An"), person("Bình"), person("Cúc", voice = null), person("Bình An"))))!!.characters
        val from = people[0]
        assertEquals(listOf("Bình", "Bình An"), Cast.mergeTargets(people, from, "").map { it.name })
        assertEquals(listOf("Bình An"), Cast.mergeTargets(people, from, " an ").map { it.name })
        assertTrue(Cast.mergeTargets(people, from, "xyz").isEmpty())
    }

    @Test
    fun `twins are names seen on two lines and add the first chapter to the merge line`() {
        val people = Cast.parse(cast(listOf(person("Lính gác", first = "Chương 1"), person("lính_gác", first = "Chương 7"), person("An"))))!!.characters
        val twins = Cast.twins(people)
        assertEquals(setOf("lính gác"), twins)
        assertEquals("Bảo Trang · 12 câu · Chương 7", Cast.mergeTargetLine(people[1], Cast.nameKey(people[1].displayName) in twins))
        assertEquals("Bảo Trang · 12 câu", Cast.mergeTargetLine(people[2], false))
    }

    @Test
    fun `merge summary names the voice the lines will be read in`() {
        val people = Cast.parse(
            cast(listOf(person("An", lines = 5), person("Bình", extra = { put("pendingVoice", JSONObject().put("preset", "p").put("label", "Mai Phương").put("gender", "")) }))),
        )!!.characters
        assertEquals("5 câu của An thành của Bình, đọc bằng giọng Mai Phương (giọng vừa chọn, chờ áp dụng).", Cast.mergeSummary(people[0], people[1]))
        assertEquals("5 câu của Bình thành của An, đọc bằng giọng Bảo Trang.", Cast.mergeSummary(people[1].copy(lines = 5), people[0]))
    }

    @Test
    fun `notes after editing a person say what was recorded and how to undo it`() {
        assertEquals("Đã đổi tên thành Thanh Bình", Cast.renamedNote("Thanh_Bình", true))
        assertEquals("Đã trở về tên gốc: Thanh Bình", Cast.renamedNote("Thanh_Bình", false))
        assertEquals("Đã ghi: An là nhân vật nữ", Cast.genderNote("An", Gender.Female))
        assertEquals("Đã ghi: 12 câu của An là của Bình", Cast.mergedNote(12, "An", "Bình"))
        assertEquals("Đã hoàn tác. An trở lại như trước khi đổi giới tính.", Cast.genderUndone("An"))
        assertEquals("Hiện đang là nhân vật nam.", Cast.genderCurrent(Gender.Male))
        assertEquals("Máy chưa xác định được giới của người này.", Cast.genderCurrent(null))
    }
}
