package vn.abook.player.ui.nowplaying

import androidx.compose.runtime.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import org.json.JSONObject
import vn.abook.player.S
import java.text.Normalizer
import java.util.Locale
import vn.abook.player.ui.studio.*

data class PlayerLineSnapshot(val script: ChapterScript, val blocked: String = "", val retake: Boolean = false,
    val writer: StudioSource? = null, val refresh: (suspend () -> PlayerLineSnapshot)? = null)

/** Bind both writes and refreshes to the project selected before editing, including receipt-bound Undo. */
object PlayerLineRemote {
    suspend fun load(source: StudioSource, computer: String, project: String, chapter: Int, paragraph: ReadParagraph): PlayerLineSnapshot {
        val script = source.castingChapter(computer, project, chapter)
        val original = paragraph.line
        val line = script.lines.singleOrNull { script.chapterId == chapter && original != null && original.stableId.isNotEmpty() && original.textSha256.isNotEmpty() &&
            it.stableId == original.stableId && it.textSha256 == original.textSha256 }
            // Studio's editable flag is for assigning speech; an identified narration can still change its reading kind.
            ?.let { it.copy(editable = true, hasAudio = it.hasAudio || paragraph.timed) }
        val targetComputer = computer
        val writer = object : StudioSource by source {
            override suspend fun write(computer: String, id: String, step: WorkStep, slow: Boolean): JSONObject =
                source.write(computer = targetComputer, id = project, step = step, slow = slow)
        }
        return PlayerLineSnapshot(script.copy(lines = listOfNotNull(line)),
            blocked = if (line == null) WorkText.STALE else "", retake = line?.retake == "pending", writer = writer,
            refresh = { load(source, computer, project, chapter, paragraph) })
    }
}

/** Local wishes and remote Studio share the same request builder and decision/undo owner. */
interface PlayerLineSource {
    val decisionsSource: StudioSource
    suspend fun load(bookId: String, chapter: Int, paragraph: ReadParagraph): PlayerLineSnapshot
    suspend fun sample(bookId: String, chapter: Int, paragraph: ReadParagraph) {}
    fun stopSample() {}
}

object PlayerLineLogic {
    private val WORD = Regex("[\\p{L}\\p{M}\\p{N}]+(?:['\u2019-][\\p{L}\\p{M}\\p{N}]+)*")
    private val VI = Locale.forLanguageTag("vi")

    /** Các từ của câu cho bước "Sửa cách đọc một từ" - đúng wordsOf của LineWishes.tsx: chữ, dấu, số, nối bằng nháy hay gạch; mỗi từ một lần không kể hoa thường. */
    fun words(text: String): List<String> {
        val seen = HashSet<String>()
        return WORD.findAll(Normalizer.normalize(text, Normalizer.Form.NFC)).map { it.value }.filter { seen.add(it.lowercase(VI)) }.toList()
    }

    fun people(cast: JSONObject, wishes: JSONObject): List<ScriptPerson> = buildList {
        val seen = HashSet<String>()
        for (key in listOf("characters", "extras", "carried")) {
            val entries = cast.optJSONArray(key) ?: continue
            for (i in 0 until entries.length()) {
                val person = entries.optJSONObject(i) ?: continue
                val name = person.optString("name")
                if (!person.has("voice") || person.isNull("voice") || !seen.add(name)) continue
                add(ScriptPerson(name, person.optString("displayName").ifEmpty { name }, person.optInt("lines")))
            }
        }
        val lines = wishes.optJSONObject("lines") ?: JSONObject()
        for (key in lines.keys()) {
            val person = lines.optJSONObject(key)?.optJSONObject("speaker") ?: continue
            val name = person.optString("name")
            if (person.optString("newGender").isEmpty() || !seen.add(name)) continue
            add(ScriptPerson(name, person.optString("shown"), 0, person.optString("newGender")))
        }
    }

    fun snapshot(chapter: Int, paragraph: ReadParagraph, cast: JSONObject, wishes: JSONObject, blocked: String = ""): PlayerLineSnapshot {
        val people = people(cast, wishes)
        val original = paragraph.line ?: ScriptLine(0, "", "", 0, paragraph.text, "narration", "NARRATOR", "", false, paragraph.timed, null, null, null, null)
        val pending = wishes.optJSONObject("lines")?.optJSONObject(original.stableId)
        val speaker = pending?.optJSONObject("speaker")
        val delivery = pending?.optJSONObject("delivery")
        val person = people.firstOrNull { it.value == original.current || it.label.equals(original.label, ignoreCase = true) }
        val line = original.copy(current = person?.value ?: original.current, label = person?.label ?: original.label.ifEmpty { S.s_nguoi_ke_fd36cd15 },
            wish = speaker?.let { ScriptWish(it.optString("name"), it.optString("shown"), "pending", null, it.optBoolean("held")) },
            lineWish = delivery?.let { ScriptLineWish(it.optString("kind"), it.optString("emotion"), if (it.isNull("intensity")) null else it.optInt("intensity"), if (it.isNull("spoken")) null else it.optString("spoken"), "pending") })
        return PlayerLineSnapshot(ChapterScript(chapter, 0, "", null, null, true, people, emptyList(), listOf(line)), blocked, pending?.has("retake") == true)
    }
}

@Stable
class PlayerLineEditor(private val source: PlayerLineSource, private val scope: CoroutineScope) {
    data class Selection(val bookId: String, val chapter: Int, val paragraph: ReadParagraph)
    var selected by mutableStateOf<Selection?>(null)
        private set
    var snapshot by mutableStateOf<PlayerLineSnapshot?>(null)
        private set
    var problem by mutableStateOf("")
        private set
    var loading by mutableStateOf(false)
        private set
    var notice by mutableStateOf("")
        private set
    var step by mutableStateOf("menu")
    /** Từ đang sửa cách đọc (bước "word"); rỗng: chưa chọn. */
    var word by mutableStateOf("")
        private set
    /** Ô cách đọc một từ dùng đúng ô của Studio ("Cách đọc tên"), ghi qua cùng nơi với các sửa khác của câu. */
    var readings by mutableStateOf<StudioReadingsState?>(null)
        private set
    private var generation = 0
    private var session: StudioSession? = null
    private var refresh: (suspend () -> PlayerLineSnapshot)? = null
    var decisions by mutableStateOf<StudioDecisions?>(null)
        private set
    val line: ScriptLine? get() = snapshot?.script?.let { ScriptLogic.withHeld(it, decisions?.held?.decision) }?.lines?.singleOrNull()
    val enabled: Boolean get() = !loading && decisions != null && decisions?.busy != true && problem.isEmpty() && snapshot?.blocked.orEmpty().isEmpty() && session?.listenOnly != true && line?.editable == true
    /** "Sửa cách đọc một từ" không cần câu được nhận ra (file ABook bản cũ vẫn sửa được) - như web (soát 0.4.173 B10). */
    val wordsEnabled: Boolean get() = !loading && readings != null && problem.isEmpty() && session?.listenOnly != true && words.isNotEmpty()
    val words: List<String> get() = selected?.paragraph?.text?.let(PlayerLineLogic::words).orEmpty()

    fun open(bookId: String, chapter: Int, paragraph: ReadParagraph) {
        close()
        selected = Selection(bookId, chapter, paragraph)
        step = "menu"; word = ""; problem = ""; notice = ""; snapshot = null
        decisions = null; session = null; refresh = null; readings = null
        scope.launch { reload() }
    }

    private fun bind(selection: Selection, loaded: PlayerLineSnapshot) {
        val boundSession = StudioSession("", loaded.writer ?: source.decisionsSource, scope)
        session = boundSession
        refresh = loaded.refresh
        lateinit var owner: StudioDecisions
        owner = StudioDecisions(boundSession, selection.bookId, after = {
            owner.forgetSent(owner.away)
            if (selected === selection) {
                if (owner.notice.isNotEmpty()) notice = owner.notice
                reload()
            }
        })
        decisions = owner
        owner.persistImmediately = true
        readings = StudioReadingsState(boundSession, selection.bookId)
    }

    fun openWords() { if (wordsEnabled) { word = ""; step = "word" } }

    /** Chạm một từ: mở ô sửa cách đọc của từ ấy (chạm lại thì khép); hỏi ngay từ ấy chạm tới bao nhiêu câu. */
    fun pickWord(picked: String) {
        word = if (word == picked) "" else picked
        if (word.isNotEmpty()) readings?.askReach(word)
    }

    suspend fun reload() {
        val selection = selected ?: return
        val mine = ++generation
        loading = true
        try {
            val loaded = refresh?.invoke() ?: source.load(selection.bookId, selection.chapter, selection.paragraph)
            if (mine == generation) {
                if (decisions == null) bind(selection, loaded)
                snapshot = loaded; problem = ""
            }
        } catch (cancelled: CancellationException) { throw cancelled }
        catch (failure: Throwable) { if (mine == generation) problem = if (failure is vn.abook.player.StudioError) StudioText.failure(failure) else failure.message.orEmpty().ifEmpty { S.s_chua_ghi_duoc_9fa87a7d } }
        finally { if (mine == generation) loading = false }
    }

    fun assign(person: ScriptPerson) { if (enabled) line?.takeIf(ScriptLogic::isSpeech)?.let { decisions?.hold(ScriptEdits.assign(listOf(it), person)); step = "menu" } }

    fun delivery(kind: String, emotion: String, intensity: Int, person: ScriptPerson?, spoken: String): Boolean {
        val line = line ?: return false
        if (!enabled) return false
        val delivery = ScriptEdits.delivery(line, kind, emotion, intensity, person)
        val reading = ScriptLogic.spokenChange(line, spoken)
        if (delivery == null && reading == null) return false
        val decision = delivery ?: ScriptLogic.speak(line, reading!!)
        if (reading != null) decision.steps.first().body.put("spoken", reading)
        decisions?.hold(decision)
        step = "menu"
        return true
    }

    fun retake() {
        val line = line ?: return
        val selection = selected ?: return
        if (!enabled || !line.hasAudio || snapshot?.retake == true) return
        val body = JSONObject().put("lines", org.json.JSONArray().put(JSONObject().put("stableId", line.stableId))).put("chapterId", selection.chapter).put("verdict", "redo")
            .put("seen", JSONObject().put(line.stableId, if (snapshot?.retake == true) "redo" else ""))
        decisions?.hold(WorkDecision("retake:${line.stableId}", S.s_da_ghi_thu_lai_cau_nay_9c9b1e4b, listOf(WorkStep("review", body))))
    }

    fun sample() {
        val selection = selected ?: return
        scope.launch { try { source.sample(selection.bookId, selection.chapter, selection.paragraph) }
            catch (cancelled: CancellationException) { throw cancelled }
            catch (failure: Throwable) { notice = failure.message.orEmpty().ifEmpty { S.s_chua_nghe_thu_duoc_f7601d1f } } }
    }

    fun back() { if (step != "menu") step = "menu" else close() }
    fun close() { ++generation; selected = null; decisions?.flush(); readings?.let { it.cancelTry(); it.decisions.flush() }; source.stopSample(); loading = false }
}
