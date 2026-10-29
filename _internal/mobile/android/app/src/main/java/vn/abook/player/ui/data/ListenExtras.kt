package vn.abook.player.ui.data

import androidx.compose.runtime.Immutable
import org.json.JSONArray
import org.json.JSONObject
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone

/*
 * Phần của trang sách mà bản WebView có và native từng chưa: lịch sử nghe, hồ sơ nghe, dàn nhân vật. Viết lại từ listen/BookScreen.tsx (HistoryTab, RecordPicker, CastList,
 * PersonRow), studio/CastEdits.tsx, studio/MergePeople.tsx, listen/voiceTone.ts - cùng chữ, cùng luật. Hàm thuần, không Android, không Compose ngoài @Immutable -
 * thử trên JVM (ListenExtrasTest).
 */

// ---- lịch sử nghe -----------------------------------------------------------------------------------------------------

/** Một lượt nghe đã ghi trong trạng thái của hồ sơ (`sessions` - ListeningSession của model.ts). Giây Unix. */
@Immutable
data class ListenSession(
    val id: String,
    val startedAt: Double,
    val endedAt: Double,
    val listened: Double,
    val fromChapter: Int,
    val fromSeconds: Double,
    val toChapter: Int,
    val toSeconds: Double,
)

/** Các lượt nghe của một ngày, nhãn ngày đã nói kiểu người ("Hôm nay"). */
@Immutable
data class SessionDay(val label: String, val sessions: List<ListenSession>)

object History {
    /** `state.sessions` -> lượt nghe theo thứ tự đã ghi (cũ trước); mục hỏng bị bỏ. */
    fun sessions(state: JSONObject?): List<ListenSession> {
        val list = state?.optJSONArray("sessions") ?: return emptyList()
        val out = ArrayList<ListenSession>(list.length())
        for (index in 0 until list.length()) {
            val item = list.optJSONObject(index) ?: continue
            val from = item.optJSONObject("from") ?: continue
            val to = item.optJSONObject("to") ?: continue
            val id = item.optString("id")
            if (id.isEmpty() || !item.has("startedAt") || !item.has("endedAt")) continue
            out += ListenSession(
                id, item.optDouble("startedAt"), item.optDouble("endedAt"), item.optDouble("listened", 0.0).takeIf { it.isFinite() } ?: 0.0,
                from.optInt("chapterId"), from.optDouble("seconds", 0.0), to.optInt("chapterId"), to.optDouble("seconds", 0.0),
            )
        }
        return out
    }

    private val WEEKDAYS = arrayOf("Chủ nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy")

    private fun midnight(ms: Long, zone: TimeZone): Long = Calendar.getInstance(zone).apply {
        timeInMillis = ms
        set(Calendar.HOUR_OF_DAY, 0)
        set(Calendar.MINUTE, 0)
        set(Calendar.SECOND, 0)
        set(Calendar.MILLISECOND, 0)
    }.timeInMillis

    /** "Hôm nay" / "Hôm qua" / "Thứ Sáu, 24/10" (BookScreen.tsx dayLabel). */
    fun dayLabel(epochSeconds: Double, nowMs: Long = System.currentTimeMillis(), zone: TimeZone = TimeZone.getDefault()): String {
        val then = (epochSeconds * 1000).toLong()
        val days = Math.round((midnight(nowMs, zone) - midnight(then, zone)) / 86_400_000.0).toInt()
        if (days == 0) return "Hôm nay"
        if (days == 1) return "Hôm qua"
        val date = Calendar.getInstance(zone).apply { timeInMillis = then }
        return "${WEEKDAYS[date.get(Calendar.DAY_OF_WEEK) - 1]}, ${date.get(Calendar.DAY_OF_MONTH)}/${date.get(Calendar.MONTH) + 1}"
    }

    /** "13:57" (giờ máy). */
    fun clockOf(epochSeconds: Double, zone: TimeZone = TimeZone.getDefault()): String {
        val date = Calendar.getInstance(zone).apply { timeInMillis = (epochSeconds * 1000).toLong() }
        return String.format(Locale.ROOT, "%02d:%02d", date.get(Calendar.HOUR_OF_DAY), date.get(Calendar.MINUTE))
    }

    /** Cùng phút thì một mốc giờ, không "13:57-13:57". */
    fun clockRange(session: ListenSession, zone: TimeZone = TimeZone.getDefault()): String {
        val start = clockOf(session.startedAt, zone)
        val end = clockOf(session.endedAt, zone)
        return if (start == end) start else "$start-$end"
    }

    /** Dòng đầu của một lượt: "13:57-14:20 · 23 phút". */
    fun headline(session: ListenSession, zone: TimeZone = TimeZone.getDefault()): String = "${clockRange(session, zone)} · ${Fmt.length(session.listened)}"

    /** Dòng phụ: "Chương 3 0:12 → Chương 4 1:05"; chương đã gỡ khỏi sách thì "chương đã gỡ". */
    fun route(session: ListenSession, titleOf: (Int) -> String?): String {
        val from = titleOf(session.fromChapter) ?: "chương đã gỡ"
        val to = titleOf(session.toChapter) ?: "chương đã gỡ"
        return "$from ${Fmt.clock(session.fromSeconds)} → $to ${Fmt.clock(session.toSeconds)}"
    }

    /** Nút của một lượt: nghe tiếp từ CUỐI lượt ấy. */
    fun resumeLabel(session: ListenSession): String = "Nghe tiếp từ ${Fmt.clock(session.toSeconds)}"

    /** Tổng thời gian nghe trong 7 ngày qua. */
    fun weekListened(sessions: List<ListenSession>, nowMs: Long = System.currentTimeMillis()): Double =
        sessions.filter { nowMs / 1000.0 - it.startedAt < 7 * 86_400 }.sumOf { it.listened }

    /** "7 ngày qua: 2 giờ nghe cuốn này." */
    fun weekLine(seconds: Double): String = "7 ngày qua: ${Fmt.length(seconds)} nghe cuốn này."

    /** Lượt mới nhất trước, gom theo ngày (thứ tự nhóm = thứ tự lần đầu gặp, tức ngày mới nhất trước). */
    fun byDay(sessions: List<ListenSession>, nowMs: Long = System.currentTimeMillis(), zone: TimeZone = TimeZone.getDefault()): List<SessionDay> {
        val groups = LinkedHashMap<String, MutableList<ListenSession>>()
        for (session in sessions.asReversed()) groups.getOrPut(dayLabel(session.startedAt, nowMs, zone)) { ArrayList() } += session
        return groups.map { SessionDay(it.key, it.value) }
    }

    /** "3 lượt nghe". */
    fun daySummary(day: SessionDay): String = "${day.sessions.size} lượt nghe"
}

// ---- hồ sơ nghe -------------------------------------------------------------------------------------------------------

/** Một hồ sơ nghe của cuốn (`Store.records`). `updatedAt`: giây Unix của lần nghe gần nhất, null khi chưa nghe. */
@Immutable
data class ListenRecord(val id: String, val name: String, val updatedAt: Double?, val active: Boolean)

/** Việc người nghe làm với hồ sơ ở hộp thoại (BookScreen.tsx RecordDialog). */
enum class RecordAction { Create, Rename, Delete, Move }

object Records {
    fun parse(list: JSONArray?): List<ListenRecord> {
        if (list == null) return emptyList()
        val out = ArrayList<ListenRecord>(list.length())
        for (index in 0 until list.length()) {
            val item = list.optJSONObject(index) ?: continue
            val id = item.optString("id")
            if (id.isEmpty()) continue
            val updated = if (item.isNull("updatedAt")) null else item.optDouble("updatedAt", 0.0).takeIf { it > 0 }
            out += ListenRecord(id, item.optString("name"), updated, item.optBoolean("active"))
        }
        return out
    }

    /** Tên gợi ý khi nghe lại từ đầu bằng hồ sơ mới: "Lần nghe 2". */
    fun suggestedName(count: Int): String = "Lần nghe ${count + 1}"

    const val NAME_MAX = 60

    /** Dòng phụ của một hồ sơ trong bộ chọn: "nghe gần nhất hôm qua" / "chưa nghe". */
    fun lastHeard(record: ListenRecord, nowMs: Long = System.currentTimeMillis(), zone: TimeZone = TimeZone.getDefault()): String =
        record.updatedAt?.let { "nghe gần nhất ${History.dayLabel(it, nowMs, zone).lowercase()}" } ?: "chưa nghe"

    fun createdNote(name: String): String = "Hồ sơ mới “${name.ifBlank { "không tên" }}” - nghe từ chương đầu"
    fun switchedNote(name: String): String = "Đang dùng hồ sơ “$name”"
    const val RENAMED_NOTE = "Đã đổi tên hồ sơ"
    fun deletedNote(name: String): String = "Đã xoá hồ sơ “$name”"
    fun movedNote(name: String, toTitle: String): String = "Đã chuyển hồ sơ “$name” sang “$toTitle”"

    fun title(action: RecordAction, activeName: String): String = when (action) {
        RecordAction.Create -> "Nghe lại từ đầu"
        RecordAction.Rename -> "Đổi tên hồ sơ"
        RecordAction.Move -> "Chuyển hồ sơ “$activeName” sang cuốn khác"
        RecordAction.Delete -> "Xoá hồ sơ “$activeName”?"
    }

    fun description(action: RecordAction, recordCount: Int): String? = when (action) {
        RecordAction.Create -> "Hồ sơ mới nghe từ đầu; hồ sơ cũ vẫn giữ nguyên."
        RecordAction.Move -> "Chỗ nghe, lịch sử đi theo hồ sơ sang cuốn kia." +
            if (recordCount > 1) " Cuốn này chuyển sang hồ sơ nghe gần nhất còn lại." else " Cuốn này sẽ như chưa nghe lần nào."
        RecordAction.Delete -> "Chỗ nghe, lịch sử của hồ sơ này mất hẳn trên mọi máy. Sách giữ nguyên" +
            if (recordCount > 1) " - cuốn chuyển sang hồ sơ nghe gần nhất còn lại." else "; đây là hồ sơ duy nhất nên cuốn sẽ như chưa nghe lần nào."
        RecordAction.Rename -> null
    }

    fun confirmLabel(action: RecordAction): String = when (action) {
        RecordAction.Create -> "Tạo và nghe"
        RecordAction.Delete -> "Xoá hồ sơ"
        RecordAction.Move -> "Chuyển"
        RecordAction.Rename -> "Lưu"
    }
}

// ---- dàn nhân vật -----------------------------------------------------------------------------------------------------

@Immutable
data class CastVoice(val key: String, val preset: String, val label: String, val tone: String) {
    /** Tên người nghe thấy ("Bảo Trang"), không phải khoá. */
    val shown: String get() = label.ifEmpty { preset }
}

@Immutable
data class PendingVoice(val preset: String, val label: String, val gender: String) {
    val shown: String get() = label.ifEmpty { preset }
}

@Immutable
data class CastMember(
    val name: String,
    val displayName: String,
    val originalName: String?,
    val gender: String,
    val lines: Int,
    val seconds: Double,
    val voice: CastVoice?,
    val sampleId: Int?,
    val firstChapter: String,
    val pendingVoice: PendingVoice?,
    val mergedInto: String?,
)

@Immutable
data class Narrator(val voice: String, val lines: Int, val seconds: Double, val pendingVoice: PendingVoice?, val redo: Int)

@Immutable
class CastView(val narrator: Narrator, val characters: List<CastMember>, val extras: List<CastMember>) {
    val isEmpty: Boolean get() = characters.isEmpty() && extras.isEmpty()
}

object Cast {
    /** `cast.json` như người nghe thấy (lớp sửa phủ lên) -> dàn nhân vật; null khi không đọc được. Sách chỉ có chữ (không có file) là dàn rỗng. */
    fun parse(text: String?): CastView? {
        if (text.isNullOrBlank()) return CastView(Narrator("", 0, 0.0, null, 0), emptyList(), emptyList())
        val json = try {
            JSONObject(text)
        } catch (_: Exception) {
            return null
        }
        val narrator = json.optJSONObject("narrator")
        return CastView(
            Narrator(
                narrator?.optString("voice").orEmpty().cleanNull(), narrator?.optInt("lines") ?: 0, narrator?.optDouble("seconds", 0.0) ?: 0.0,
                pending(narrator?.optJSONObject("pendingVoice")), narrator?.optInt("redo") ?: 0,
            ),
            people(json.optJSONArray("characters")), people(json.optJSONArray("extras")),
        )
    }

    private fun String.cleanNull(): String = if (this == "null") "" else this

    private fun pending(json: JSONObject?): PendingVoice? =
        json?.let { PendingVoice(it.optString("preset").cleanNull(), it.optString("label").cleanNull(), it.optString("gender").cleanNull()) }

    private fun people(list: JSONArray?): List<CastMember> {
        if (list == null) return emptyList()
        val out = ArrayList<CastMember>(list.length())
        for (index in 0 until list.length()) {
            val item = list.optJSONObject(index) ?: continue
            val name = item.optString("name").cleanNull()
            if (name.isEmpty()) continue
            val voice = item.optJSONObject("voice")?.let { CastVoice(it.optString("key").cleanNull(), it.optString("preset").cleanNull(), it.optString("label").cleanNull(), it.optString("tone").cleanNull()) }
            out += CastMember(
                name = name,
                displayName = item.optString("displayName").cleanNull().ifEmpty { name },
                originalName = item.optString("originalName").cleanNull().ifEmpty { null },
                gender = item.optString("gender").cleanNull(),
                lines = item.optInt("lines"),
                seconds = item.optDouble("seconds", 0.0).takeIf { it.isFinite() } ?: 0.0,
                voice = voice,
                sampleId = if (item.isNull("sampleId") || !item.has("sampleId")) null else item.optInt("sampleId"),
                firstChapter = item.optString("firstChapter").cleanNull(),
                pendingVoice = pending(item.optJSONObject("pendingVoice")),
                mergedInto = item.optString("mergedInto").cleanNull().ifEmpty { null },
            )
        }
        return out
    }

    /** Tên hiển thị không lộ dữ liệu thô: gạch dưới thành dấu cách (BookScreen.tsx cleanName). */
    fun cleanName(name: String): String = name.replace('_', ' ').replace(Regex("\\s+"), " ").trim()

    private val ROMAN = Regex("^[IVXLCDM]+$")

    /** Hai chữ cái đầu của tên (bỏ số La Mã): "Thanh Bình" -> "TB". */
    fun initials(name: String): String =
        cleanName(name).split(Regex("\\s+")).filter { it.isNotEmpty() && !ROMAN.matches(it) }.take(2).joinToString("") { it.substring(0, it.offsetByCodePoints(0, 1)) }.uppercase()

    /** Sắc độ 0..359 của vòng tròn chữ cái, cố định theo giọng (hay tên) người ấy (BookScreen.tsx hueOf). */
    fun hue(text: String): Int {
        var value = 0
        var index = 0
        while (index < text.length) {
            val point = text.codePointAt(index)
            value = (value * 31 + text[index].code) % 360
            index += Character.charCount(point)
        }
        return value
    }

    private val FROM_BASE = setOf("trầm hẳn", "hơi trầm", "sáng hẳn", "hơi sáng")

    /** "trầm hẳn" -> "chỉnh trầm hẳn so với giọng gốc" (voiceTone.ts); nhãn lạ giữ nguyên. */
    fun toneLabel(tone: String): String {
        val text = tone.trim()
        return if (text in FROM_BASE) "chỉnh $text so với giọng gốc" else text
    }

    /** Dòng giọng của một người: "Bảo Trang · chỉnh trầm hẳn so với giọng gốc" / "Chưa có giọng". */
    fun voiceLine(person: CastMember): String {
        val voice = person.voice ?: return "Chưa có giọng"
        return voice.shown + if (voice.tone.isNotEmpty()) " · ${toneLabel(voice.tone)}" else ""
    }

    /** Điện thoại không có xưởng: thay đổi người nghe ghi chỉ chờ máy làm sách (PersonRow `waiting`). */
    const val WAITING = "Đang chờ máy làm sách"

    /** "Đang chờ máy làm sách: giọng Bảo Trang · nữ" (giọng/giới người nghe đã chọn mà chưa áp). null khi không chờ gì. */
    fun pendingLine(person: CastMember): String? {
        val pending = person.pendingVoice ?: return null
        val parts = listOfNotNull(pending.preset.takeIf { it.isNotEmpty() }?.let { "giọng ${pending.shown}" }, pending.gender.lowercase().takeIf { it.isNotEmpty() })
        return "$WAITING:" + if (parts.isEmpty()) "" else " ${parts.joinToString(" · ")}"
    }

    /** "Đang chờ máy làm sách: gộp vào Lucien". */
    fun mergeLine(person: CastMember): String? = person.mergedInto?.let { "$WAITING: gộp vào ${cleanName(it)}" }

    /** Dòng đếm câu: "12 câu · 1 phút · từ Chương 3". */
    fun countLine(person: CastMember): String {
        val parts = StringBuilder(Fmt.number(person.lines.toLong())).append(" câu")
        if (person.seconds > 0) parts.append(" · ").append(Fmt.length(person.seconds))
        if (person.firstChapter.isNotEmpty()) parts.append(" · từ ").append(person.firstChapter)
        return parts.toString()
    }

    fun narratorCountLine(narrator: Narrator): String {
        val text = StringBuilder(Fmt.number(narrator.lines.toLong())).append(" câu dẫn truyện")
        if (narrator.seconds > 0) text.append(" · ").append(Fmt.length(narrator.seconds))
        if (narrator.redo > 0) text.append(" · ").append(Fmt.number(narrator.redo.toLong())).append(" câu chờ thu lại")
        return text.toString()
    }

    fun narratorName(narrator: Narrator): String = narrator.voice.ifEmpty { "Mặc định" }

    /** Tên (ngắn và đầy đủ) của các chương từ đầu tới chương `until` (chưa nghe gì: tới chương đầu) - dàn chỉ lộ tới chỗ đang nghe. */
    fun reachedTitles(chapters: List<ChapterLine>, until: Int?): Set<String> {
        val titles = HashSet<String>()
        val last = until ?: chapters.firstOrNull()?.id
        for (chapter in chapters) {
            titles += chapter.title
            if (chapter.shortTitle.isNotEmpty()) titles += chapter.shortTitle
            if (chapter.id == last) break
        }
        return titles
    }

    /** Người chỉ xuất hiện SAU chỗ đang nghe. */
    fun ahead(people: List<CastMember>, reached: Set<String>): Int = people.count { it.firstChapter.isNotEmpty() && it.firstChapter !in reached }

    /** Người hiện ra: hết nếu đã bấm "Hiện chương sau" hay không có mốc; không thì chỉ người đã xuất hiện tới chỗ đang nghe. */
    fun visible(people: List<CastMember>, reached: Set<String>?, later: Boolean): List<CastMember> =
        people.filter { later || reached == null || it.firstChapter.isEmpty() || it.firstChapter in reached }

    fun laterLabel(later: Boolean, count: Int): String {
        val action = if (later) "Ẩn chương sau" else "Hiện chương sau"
        return "$action · $count người"
    }

    // ---- sửa một người (Đổi tên, Đổi giới tính, Gộp vào…) ----

    /** Giới người nghe đang thấy: giới chờ áp dụng nếu có, không thì giới trong sổ. */
    fun shownGender(person: CastMember?): Gender? {
        val label = person?.pendingVoice?.gender?.takeIf { it.isNotEmpty() } ?: person?.gender
        return when (label) {
            "Nam" -> Gender.Male
            "Nữ" -> Gender.Female
            else -> null
        }
    }

    /** Giọng người ấy SẼ đọc: giọng người nghe vừa chọn mà chưa áp, nếu có. */
    fun voiceToUse(person: CastMember): String = if (person.pendingVoice?.preset?.isNotEmpty() == true) person.pendingVoice.shown else person.voice?.shown.orEmpty()

    /** Những người nhận được phần gộp: có giọng, không phải chính người đang gộp, lọc theo chữ gõ. */
    fun mergeTargets(people: List<CastMember>, from: CastMember, query: String): List<CastMember> {
        val words = query.trim().lowercase()
        return people.filter { it.name != from.name && it.voice != null }.filter { words.isEmpty() || cleanName(it.displayName).lowercase().contains(words) }
    }

    fun mergeSummary(from: CastMember, into: CastMember): String =
        "${Fmt.number(from.lines.toLong())} câu của ${cleanName(from.displayName)} thành của ${cleanName(into.displayName)}, đọc bằng giọng ${voiceToUse(into)}" +
            (if (into.pendingVoice?.preset?.isNotEmpty() == true) " (giọng vừa chọn, chờ áp dụng)" else "") + "."

    /** Khoá so sánh tên hiển thị: bỏ gạch dưới, dấu cách thừa, hoa thường (workText.ts nameKey). */
    fun nameKey(name: String): String = cleanName(name).lowercase(Locale.forLanguageTag("vi"))

    /** Những tên xuất hiện ở từ hai dòng trở lên (ba "Lính gác 1" ở ba chương): dòng mang tên ấy ghi thêm chương đầu người ấy lên tiếng. */
    fun twins(people: List<CastMember>): Set<String> {
        val seen = HashMap<String, Int>()
        for (person in people) {
            val key = nameKey(person.displayName)
            if (key.isNotEmpty()) seen[key] = (seen[key] ?: 0) + 1
        }
        return seen.filterValues { it > 1 }.keys
    }

    fun mergeTargetLine(person: CastMember, twin: Boolean = false): String =
        voiceToUse(person) + (if (person.pendingVoice?.preset?.isNotEmpty() == true) " (chờ áp dụng)" else "") + " · ${Fmt.number(person.lines.toLong())} câu" +
            (if (twin && person.firstChapter.isNotEmpty()) " · ${person.firstChapter}" else "")

    fun renamedNote(shown: String, renamed: Boolean): String = if (renamed) "Đã đổi tên thành ${cleanName(shown)}" else "Đã trở về tên gốc: ${cleanName(shown)}"
    fun genderNote(name: String, gender: Gender): String = "Đã ghi: $name là nhân vật ${gender.word}"
    fun mergedNote(lines: Int, from: String, into: String): String = "Đã ghi: $lines câu của $from là của $into"
    fun genderUndone(name: String): String = "Đã hoàn tác. $name trở lại như trước khi đổi giới tính."

    fun genderCurrent(current: Gender?): String =
        if (current != null) "Hiện đang là nhân vật ${current.word}." else "Máy chưa xác định được giới của người này."
}

enum class Gender(val wire: String, val label: String, val word: String) {
    Male("male", "Nam", "nam"),
    Female("female", "Nữ", "nữ"),
}
