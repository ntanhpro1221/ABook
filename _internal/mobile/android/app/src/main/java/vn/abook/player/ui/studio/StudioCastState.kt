package vn.abook.player.ui.studio

import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject
import vn.abook.player.ClipSpec
import vn.abook.player.ClipState
import vn.abook.player.StudioErrors
import vn.abook.player.StudioPaths
import vn.abook.player.StudioPoller
import vn.abook.player.StudioPolling

/**
 * Tab "Nhân vật" (NATIVE_REMOTE_STUDIO.md §6.6): người kể, nhân vật chính, vai phụ; mỗi người một hàng có giọng đang đọc và nút nghe thử. Chạm một hàng mở bảng
 * giọng ([VoiceSheetState]). Hỏi `GET /cast` khi mở tab và mỗi 15 giây khi sách đang chạy.
 */
@Stable
class StudioCastState(private val project: StudioProjectState, pause: suspend (Long) -> Unit = { delay(it) }) {
    private val session get() = project.session
    private val poller = StudioPoller<Cast>(
        { session.source.cast(session.computer, project.bookId) },
        { if (project.live) StudioWorkState.PRODUCING_REFRESH_MS else null },
        pause,
    )
    val poll: StateFlow<StudioPolling.Poll<Cast>> get() = poller.state

    val clip: StateFlow<ClipState>? get() = session.clips?.state

    suspend fun run() = poller.run()

    suspend fun refresh() = poller.refresh()

    fun refreshSoon() {
        session.scope.launch { poller.refresh() }
    }

    /** Nghe một câu của người này (bản thu riêng của câu mẫu); bấm lại để dừng. */
    fun playSample(member: CastMember) {
        val id = member.sampleId ?: return
        session.clips?.toggle(sampleId(member), ClipSpec(session.computer, StudioPaths.sample(project.bookId, id)))
    }

    fun release() {
        session.clips?.stop()
    }

    /** Bảng giọng của một người (`character` = khoá sổ, "NARRATOR" cho người kể). */
    fun voiceSheet(character: String, displayName: String) = VoiceSheetState(project, character, displayName)

    companion object {
        fun sampleId(member: CastMember) = "cast-${member.name}"
    }
}

/**
 * Bảng "Đổi giọng" một nhân vật (web `VoicePicker.tsx`): mọi giọng dùng được, nghe thử từng giọng (câu mẫu chung, hay một câu của chính nhân vật), lọc theo giới,
 * chọn. Chọn xong đi đúng đường của thẻ "Nam hay nữ" (`POST /voice`) và giữ 15 giây cho "Hoàn tác" như mọi quyết định ([StudioDecisions]). Giọng khác giới với nhân
 * vật thì hỏi trước (đổi giọng khác giới là đổi luôn giới).
 */
@Stable
class VoiceSheetState(private val project: StudioProjectState, val character: String, val displayName: String) {
    private val session get() = project.session

    var choices by mutableStateOf<VoiceChoices?>(null)
        private set

    /** Lỗi tải danh sách giọng ("" = không có). */
    var problem by mutableStateOf("")
        private set

    var loading by mutableStateOf(true)
        private set

    private var gender by mutableStateOf<GenderFilter?>(null)

    /** Giọng khác giới đang chờ người nghe đồng ý. */
    var crossing by mutableStateOf<VoiceEntry?>(null)
        private set

    /** Khoá (giọng) đang chờ máy đọc thử; một lúc một giọng. */
    var asking by mutableStateOf<String?>(null)
        private set

    /** Một dòng nói máy đang làm gì / đã đọc câu nào / vì sao chưa nghe được ("" = không có). */
    var said by mutableStateOf("")
        private set

    val clip: StateFlow<ClipState>? get() = session.clips?.state

    private val heard = HashMap<String, VoicePreview>()

    val narrator: Boolean get() = character == "NARRATOR"

    val filter: GenderFilter get() = gender ?: choices?.let(VoiceLogic::defaultFilter) ?: GenderFilter.Male

    fun pickFilter(next: GenderFilter) {
        gender = next
    }

    suspend fun load() {
        loading = true
        problem = ""
        try {
            choices = session.source.voices(session.computer, project.bookId, character)
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Throwable) {
            val failure = StudioErrors.of(error)
            session.note(failure)
            problem = StudioText.failure(failure)
        } finally {
            loading = false
        }
    }

    // ---- chọn ----

    /** Chọn một giọng: cùng giới (hay chưa biết giới) ghi luôn; khác giới thì hỏi trước. Người kể không có giới để đổi. Trả true khi đã ghi (bảng đóng được). */
    fun choose(voice: VoiceEntry): Boolean {
        val known = choices?.character?.gender
        if (!narrator && (known == "male" || known == "female") && known != voice.gender) {
            crossing = voice
            return false
        }
        commit(voice, withGender = false)
        return true
    }

    fun answerCrossing(withGender: Boolean): Boolean {
        val voice = crossing ?: return false
        crossing = null
        if (!withGender) return false
        commit(voice, withGender = true)
        return true
    }

    private fun commit(voice: VoiceEntry, withGender: Boolean) {
        val now = choices ?: return
        project.decisions.hold(
            WorkDecisions.voicePick(now.character.value, displayName, voice.name, voice.key, if (withGender) voice.gender else null, now.pending?.requestedAt ?: 0.0),
        )
    }

    /** Bỏ lựa chọn chưa vào sách (giữ giọng đang dùng): gửi ngay, không giữ 15 giây. */
    fun keepCurrent() {
        val pending = choices?.pending ?: return
        project.decisions.hold(WorkDecisions.voiceWithdraw(character, pending.requestedAt))
    }

    // ---- nghe ----

    /** ▶: câu mẫu chung của giọng. */
    fun playSample(voice: VoiceEntry) {
        if (!voice.preview) return
        session.clips?.toggle(sampleClip(voice), ClipSpec(session.computer, StudioPaths.voiceSample(voice.key)))
    }

    /** Nút sách: máy đọc một câu của chính nhân vật bằng giọng này. Đã nghe giọng này rồi thì phát lại, không hỏi máy. */
    fun tryVoice(voice: VoiceEntry) {
        val now = choices ?: return
        val key = VoiceLogic.tryKey(project.bookId, now.character.value, voice.key)
        heard[key]?.let {
            play(it, voice.name)
            return
        }
        if (asking != null) return
        session.clips?.stop()
        asking = voice.key
        said = "Máy đang đọc thử giọng ${voice.name} - lần đầu có thể mất vài chục giây"
        session.scope.launch {
            try {
                val step = WorkStep("voice/preview", JSONObject().put("character", now.character.value).put("preset", voice.key))
                when (val outcome = session.preview(project.bookId, step)) {
                    is PreviewOutcome.Ready -> {
                        heard[key] = outcome.preview
                        play(outcome.preview, voice.name)
                    }
                    is PreviewOutcome.Rejected -> said = outcome.message
                    is PreviewOutcome.Refused -> if (outcome.reason == "no-line" && voice.preview) {
                        playSample(voice)
                        said = "Người này chưa có câu nào để đọc thử - đang phát câu mẫu chung của giọng"
                    } else {
                        said = if (voice.preview) "${outcome.text} - nút phát vẫn nghe được câu mẫu chung của giọng" else outcome.text
                    }
                }
            } finally {
                asking = null
            }
        }
    }

    private fun play(preview: VoicePreview, voiceName: String) {
        session.clips?.toggle(tryClip(preview), ClipSpec(session.computer, preview.url))
        said = VoiceLogic.previewCaption(preview.text, voiceName)
    }

    /** Mã clip của bản đã nghe cho giọng này (để hàng biết nó đang phát). */
    fun heardClip(voice: VoiceEntry): String? {
        val now = choices ?: return null
        return heard[VoiceLogic.tryKey(project.bookId, now.character.value, voice.key)]?.let(::tryClip)
    }

    fun sampleClip(voice: VoiceEntry) = "voice-${voice.name}"

    private fun tryClip(preview: VoicePreview) = "voice-try-${preview.url}"

    /** Đóng bảng: dừng tiếng. */
    fun release() {
        session.clips?.stop()
    }
}
