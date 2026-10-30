package vn.abook.player.ui.studio

import androidx.compose.runtime.Immutable
import org.json.JSONObject

/** Giọng đang đọc một người (web `VoiceProfile`): `preset` là khoá gửi lại máy, `label` là tên để hiện. */
@Immutable
data class VoiceProfile(val key: String, val preset: String, val label: String, val tone: String)

/** Giọng / giới người nghe đã chọn mà chưa vào sách. */
@Immutable
data class PendingVoice(val preset: String, val label: String, val gender: String)

/** Một nhân vật của cuốn (web `CastMember`). */
@Immutable
data class CastMember(
    val name: String,
    val displayName: String,
    /** Tên gốc khi người nghe đã đổi tên; null = chưa đổi. */
    val originalName: String?,
    val gender: String,
    val age: String,
    val lines: Int,
    val seconds: Double,
    val recorded: Int,
    val voice: VoiceProfile?,
    val sampleId: Int?,
    val firstChapter: String,
    val pendingVoice: PendingVoice?,
    /** Tên người mà nhân vật này đang chờ gộp vào ("Gộp vào…" chưa áp); null = không gộp. */
    val mergedInto: String?,
)

/** Người kể: giọng đang dùng và lựa chọn đang chờ. */
@Immutable
data class CastNarrator(val voice: String, val lines: Int, val seconds: Double, val profile: VoiceProfile?, val pendingVoice: PendingVoice?, val redo: Int)

/** Lời đáp của `GET /api/books/<id>/cast`: người kể, nhân vật chính, vai phụ, và dàn mang từ phần trước. */
@Immutable
data class Cast(val narrator: CastNarrator, val characters: List<CastMember>, val extras: List<CastMember>, val carried: List<CastMember>)

/** Nhân vật mà bảng giọng đang mở cho. */
@Immutable
data class VoiceCharacter(val value: String, val label: String, val gender: String, val lines: Int, val chapters: Int)

/** Một người đang dùng chung giọng với người này ở cùng chương. */
@Immutable
data class VoiceShare(val label: String, val chapters: Int)

/** Một giọng trong bảng "Đổi giọng" (web `VoiceOption` của VoicePicker.tsx). `key` là khoá duy nhất máy chủ nhận. */
@Immutable
data class VoiceEntry(
    val key: String,
    val name: String,
    val engine: String,
    val engineLabel: String,
    val installed: Boolean,
    val oneStep: Boolean,
    val sharedWith: List<VoiceShare>,
    val otherUsers: Int,
    /** "male" | "female". */
    val gender: String,
    val genderLabel: String,
    val region: String,
    val style: String,
    val preview: Boolean,
    val current: Boolean,
    val pending: Boolean,
    val suggested: Boolean,
    val description: String,
    val takenBy: List<String>,
    val takenNote: String?,
)

/** Lựa chọn giọng chưa vào sách: tên giọng nó sẽ thành ("" khi chưa biết) và mốc để bỏ đúng lần chọn ấy. */
@Immutable
data class PendingChoice(val name: String, val requestedAt: Double)

/** Câu "Nghe thử bằng câu của sách" sẽ đọc. */
@Immutable
data class TryLine(val segmentId: Int, val text: String)

/** Đổi giọng là thu lại mọi câu đã thu của người ấy. `measured` false: thời gian là số ước. */
@Immutable
data class Rerecord(val lines: Int, val seconds: Double, val measured: Boolean)

/** Lời đáp của `GET /api/books/<id>/voices?character=`. */
@Immutable
data class VoiceChoices(
    val character: VoiceCharacter,
    val current: String,
    val pending: PendingChoice?,
    val voices: List<VoiceEntry>,
    val tryLine: TryLine?,
    val rerecord: Rerecord?,
    /** Máy đọc khác chưa sẵn sàng trên máy tính: tên máy -> trạng thái ("missing", "downloading"...). */
    val moduleStates: Map<String, String>,
)

/** Bản nghe thử một câu của sách bằng một giọng (`POST /voice/preview`): `url` là đường `/media/...` của bản thu thử. */
@Immutable
data class VoicePreview(val url: String, val segmentId: Int, val text: String, val speaker: String, val cached: Boolean)

internal object StudioCastJson {
    private fun profile(json: JSONObject?): VoiceProfile? =
        json?.let { VoiceProfile(it.text("key"), it.text("preset"), it.text("label").ifEmpty { it.text("preset") }, it.text("tone")) }

    private fun pendingVoice(json: JSONObject?): PendingVoice? =
        json?.let { PendingVoice(it.text("preset"), it.text("label").ifEmpty { it.text("preset") }, it.text("gender")) }

    private fun member(json: JSONObject) = CastMember(
        name = json.text("name"),
        displayName = json.text("displayName").ifEmpty { json.text("name") },
        originalName = json.textOrNull("originalName")?.takeIf { it.isNotEmpty() },
        gender = json.text("gender"),
        age = json.text("age"),
        lines = json.optInt("lines"),
        seconds = json.optDouble("seconds", 0.0).let { if (it.isFinite()) it else 0.0 },
        recorded = json.optInt("recorded"),
        voice = profile(json.optJSONObject("voice")),
        sampleId = if (json.has("sampleId") && !json.isNull("sampleId")) json.optInt("sampleId") else null,
        firstChapter = json.text("firstChapter"),
        pendingVoice = pendingVoice(json.optJSONObject("pendingVoice")),
        mergedInto = json.textOrNull("mergedInto")?.takeIf { it.isNotEmpty() },
    )

    fun cast(json: JSONObject): Cast {
        val narrator = json.optJSONObject("narrator") ?: JSONObject()
        return Cast(
            narrator = CastNarrator(
                voice = narrator.text("voice"),
                lines = narrator.optInt("lines"),
                seconds = narrator.optDouble("seconds", 0.0).let { if (it.isFinite()) it else 0.0 },
                profile = profile(narrator.optJSONObject("profile")),
                pendingVoice = pendingVoice(narrator.optJSONObject("pendingVoice")),
                redo = narrator.optInt("redo"),
            ),
            characters = json.optJSONArray("characters").objects().map(::member),
            extras = json.optJSONArray("extras").objects().map(::member),
            carried = json.optJSONArray("carried").objects().map(::member),
        )
    }

    private fun entry(json: JSONObject) = VoiceEntry(
        key = json.text("key"),
        name = json.text("name"),
        engine = json.text("engine"),
        engineLabel = json.text("engineLabel"),
        installed = json.optBoolean("installed", true),
        oneStep = json.optBoolean("oneStep"),
        sharedWith = json.optJSONArray("sharedWith").objects().map { VoiceShare(it.text("label"), it.optInt("chapters")) },
        otherUsers = json.optInt("otherUsers"),
        gender = json.text("gender"),
        genderLabel = json.text("genderLabel"),
        region = json.text("region"),
        style = json.text("style"),
        preview = json.optBoolean("preview"),
        current = json.optBoolean("current"),
        pending = json.optBoolean("pending"),
        suggested = json.optBoolean("suggested"),
        description = json.text("description"),
        takenBy = json.optJSONArray("takenBy").strings(),
        takenNote = json.textOrNull("takenNote")?.takeIf { it.isNotEmpty() },
    )

    fun voices(json: JSONObject): VoiceChoices {
        val character = json.optJSONObject("character") ?: JSONObject()
        val rerecord = json.optJSONObject("rerecord")
        val modules = json.optJSONObject("modules")
        return VoiceChoices(
            character = VoiceCharacter(character.text("value"), character.text("label"), character.text("gender"), character.optInt("lines"), character.optInt("chapters")),
            current = json.text("current"),
            pending = json.optJSONObject("pending")?.let { PendingChoice(it.text("name"), it.optDouble("requestedAt")) },
            voices = json.optJSONArray("voices").objects().map(::entry),
            tryLine = json.optJSONObject("tryLine")?.let { TryLine(it.optInt("segmentId"), it.text("text")) },
            rerecord = rerecord?.let { Rerecord(it.optInt("lines"), it.optDouble("seconds", 0.0), if (it.has("measured")) it.optBoolean("measured") else true) },
            moduleStates = modules?.keys()?.asSequence()?.associateWith { modules.optJSONObject(it)?.text("state").orEmpty() }.orEmpty(),
        )
    }

    fun preview(json: JSONObject) = VoicePreview(json.text("url"), json.optInt("segmentId"), json.text("text"), json.text("speaker"), json.optBoolean("cached"))
}

/** Nhóm giọng theo máy đọc, giữ thứ tự máy chủ gửi (VieNeu trước). */
@Immutable
data class VoiceGroup(val engine: String, val label: String, val voices: List<VoiceEntry>)

/** Bộ lọc giới của bảng giọng. */
enum class GenderFilter(val key: String, val label: String) { Male("male", "Nam"), Female("female", "Nữ"), All("all", "Tất cả") }

/** Logic thuần của bảng "Đổi giọng" - port `voiceEngines.ts`, `voiceTryText.ts`, `previewText.ts`, `VoicePicker.tsx voiceMeta`. */
object VoiceLogic {
    fun groups(voices: List<VoiceEntry>): List<VoiceGroup> {
        val order = LinkedHashMap<String, MutableList<VoiceEntry>>()
        for (voice in voices) order.getOrPut(voice.engine) { ArrayList() } += voice
        return order.map { (engine, list) -> VoiceGroup(engine, list.first().engineLabel, list) }
    }

    /** Máy đọc chính (VieNeu) là "Giọng chính", các máy khác "Giọng thêm" (đánh số khi có hai nhóm thêm trở lên): tên máy đọc là chuyện nội bộ. */
    fun groupLabels(groups: List<VoiceGroup>): List<String> {
        val extras = groups.count { it.engine != "vieneu" }
        var seen = 0
        return groups.map { if (it.engine == "vieneu") "Giọng chính" else if (extras > 1) "Giọng thêm ${++seen}" else "Giọng thêm" }
    }

    fun byGender(voices: List<VoiceEntry>, filter: GenderFilter): List<VoiceEntry> = if (filter == GenderFilter.All) voices else voices.filter { it.gender == filter.key }

    /** Giới mở sẵn: giọng đang dùng, không thì giới của nhân vật, không thì nam. */
    fun defaultFilter(choices: VoiceChoices): GenderFilter {
        val now = choices.voices.firstOrNull { it.current }?.gender
        val gender = now ?: choices.character.gender
        return if (gender == "female") GenderFilter.Female else GenderFilter.Male
    }

    /** `current`: giọng người này đang đọc - không nói "Chưa ai dùng" về một giọng đang được dùng. */
    fun sharedText(voice: VoiceEntry, current: Boolean = false): String {
        val others = if (voice.otherUsers > 0) "${voice.otherUsers} người khác dùng, không cùng chương" else ""
        if (voice.sharedWith.isEmpty()) return others.ifEmpty { if (current) "Giọng đang đọc cho người này" else "Chưa ai dùng" }
        val people = voice.sharedWith.joinToString(", ") { "${it.label} (${it.chapters} chương)" }
        val after = if (voice.oneStep) "hai người sẽ nghe giống hệt nhau" else "máy lấy bậc âm sắc khác"
        return "Cùng chương với $people - $after${if (others.isNotEmpty()) " · $others" else ""}"
    }

    /** Hộp "Đổi giọng" của người kể: giọng nhân vật đang giữ không chọn được - nói của ai (tối đa ba tên). */
    fun takenText(takenBy: List<String>): String {
        val named = takenBy.take(3).joinToString(", ")
        val rest = if (takenBy.size > 3) " và ${takenBy.size - 3} người khác" else ""
        return "Đang là giọng của $named$rest - người kể cần giọng riêng"
    }

    /** Dòng phụ dưới tên giọng: chất giọng, rồi ai đang dùng chung (`voiceMeta`). */
    fun meta(voice: VoiceEntry, withGender: Boolean): String {
        val parts = if (voice.description.isNotEmpty()) listOf(voice.description) else listOf(if (voice.region.isNotEmpty()) "Miền ${voice.region}" else "", voice.style)
        val about = (listOf(if (withGender && voice.description.isEmpty()) voice.genderLabel else "") + parts).filter { it.isNotEmpty() }.joinToString(" · ")
        val alone = voice.current && voice.sharedWith.isEmpty() && voice.otherUsers == 0
        val use = voice.takenNote ?: if (voice.takenBy.isNotEmpty()) takenText(voice.takenBy) else if (alone) "" else sharedText(voice, voice.current)
        return listOf(about, use).filter { it.isNotEmpty() }.joinToString(" · ")
    }

    /** Thời gian thu lại: số đo của chính cuốn ("trên máy này"), hay số ước khi chưa đo được. */
    fun estimateText(seconds: Double, measured: Boolean): String {
        val length = if (seconds < 60) "chưa tới 1 phút" else "khoảng ${vn.abook.player.ui.data.Fmt.length(seconds)}"
        return if (!measured) "$length - ước chừng, vì cuốn chưa xong chương nào để đo" else "$length trên máy này"
    }

    /** Một dòng trong bảng "Đổi giọng": đổi giọng tốn gì. */
    fun rerecordText(name: String, cost: Rerecord): String =
        if (cost.lines == 0) "Chưa câu nào của $name được thu - đổi giọng không phải thu lại gì."
        else "Đổi giọng là thu lại ${vn.abook.player.ui.data.Fmt.number(cost.lines.toLong())} câu đã thu của $name, ${estimateText(cost.seconds, cost.measured)}."

    /** Khoá bản nghe thử trong phiên: cùng sách, cùng người, cùng giọng thì phát lại, không hỏi máy. */
    fun tryKey(bookId: String, character: String, preset: String): String = listOf(bookId, character, preset).joinToString("\u0000")

    /** Lời từ chối nghe thử theo mã `reason` của máy (previewText.ts `refusalText`); `named`: máy đã nói cuốn nào đang chặn - giữ lời máy. */
    fun refusalText(reason: String, fallback: String, named: Boolean): String {
        if (reason == "producing" && named) return fallback
        return when (reason) {
            "producing" -> "Máy đang làm sách; thử lại khi xong."
            "gpu" -> "Card đồ hoạ đang bận - thử lại sau ít phút"
            "studio" -> "Cài Studio để nghe thử."
            "busy" -> "Đang nghe thử câu khác - bấm lại sau ít giây"
            else -> fallback
        }
    }

    /** Dòng dưới nút sau khi nghe: lúc thu thật sẽ nghe gần như vậy, câu nào, giọng ai. */
    fun previewCaption(text: String, speaker: String): String =
        "Lúc thu thật sẽ nghe gần như vậy · câu “${text.replace(Regex("\\s+"), " ").trim()}”${if (speaker.isNotEmpty()) " · giọng $speaker" else ""}"
}
