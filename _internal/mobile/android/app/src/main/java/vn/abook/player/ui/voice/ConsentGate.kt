package vn.abook.player.ui.voice

import androidx.compose.runtime.Stable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * Việc của hộp hỏi trước khi đọc bằng giọng trực tuyến với các lõi (ReadAloud): tách khỏi giao diện để thử bằng nguồn giả. Nguồn thật: [AndroidConsentSource].
 * Hàm suspend tự chạy ở luồng nền.
 */
interface ConsentSource {
    /** Mọi giọng máy này đọc được, kể cả giọng trực tuyến. */
    suspend fun voices(): List<ConsentVoice>

    /** Mã giọng cuốn `bookId` sẽ đọc (đã chọn riêng, hay giọng chung / mặc định). */
    suspend fun chosen(bookId: String): String
    suspend fun consents(): Set<String>

    /** Bạn đồng ý gửi chữ cho nhà cung cấp này. */
    suspend fun grant(provider: String)

    /** Bạn chọn giọng này cho riêng cuốn `bookId`. */
    suspend fun choose(bookId: String, voiceId: String)
}

/** Một câu hỏi đang chờ bạn. `answer(giọng)`: đọc bằng giọng ấy (`chosen`: bạn tự chọn trong danh sách); `answer(null)`: bạn đóng hộp - không phát. Trả lời lần hai bị bỏ. */
@Stable
class ConsentRequest(val voice: ConsentVoice, val voices: List<ConsentVoice>, private val reply: (ConsentAnswer?) -> Unit) {
    fun answer(picked: ConsentVoice?, chosen: Boolean = false) = reply(picked?.let { ConsentAnswer(it, chosen) })
}

/**
 * Cửa trước lệnh phát của trình phát: chương chỉ có chữ mà giọng của cuốn gửi chữ ra ngoài và bạn chưa đồng ý với nhà cung cấp ấy thì HỎI TRƯỚC - chưa chữ nào rời máy khi
 * chưa có câu trả lời (player.tsx `withConsent`). Lệnh mới thay lệnh cũ (câu hỏi cũ đóng), nên không có câu trả lời nào phát nhầm lệnh đã bỏ.
 */
interface PlayGate {
    /** Câu hỏi đang hiện (một lúc một câu); giao diện vẽ nó. */
    val request: StateFlow<ConsentRequest?>

    /** Chạy `go` khi được phép phát: ngay nếu chương không phải chương chữ hay không cần hỏi, không thì sau khi bạn đồng ý; bạn đóng hộp thì không chạy. */
    fun before(bookId: String, textChapter: Boolean, go: () -> Unit)

    /** Bạn đã làm việc khác (dừng, đóng sách): lệnh phát đang chờ bị bỏ. */
    fun cancel()

    /** Không hỏi gì (bản thử, bản chạy thử). */
    object Open : PlayGate {
        override val request: StateFlow<ConsentRequest?> = MutableStateFlow(null)
        override fun before(bookId: String, textChapter: Boolean, go: () -> Unit) = go()
        override fun cancel() = Unit
    }
}

@Stable
class ConsentGate(private val source: ConsentSource, private val scope: CoroutineScope) : PlayGate {
    private val flow = MutableStateFlow<ConsentRequest?>(null)
    override val request: StateFlow<ConsentRequest?> get() = flow
    private var ticket = 0
    private var waiting: CompletableDeferred<ConsentAnswer?>? = null

    override fun before(bookId: String, textChapter: Boolean, go: () -> Unit) {
        val mine = supersede()
        if (!textChapter) {
            go()
            return
        }
        scope.launch {
            val ask = try {
                needed(bookId)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                null // không biết giọng nào: lõi vẫn tự dừng và báo khi chữ sắp rời máy (ReadAloud.CONSENT_NOTICE)
            }
            if (mine != ticket) return@launch
            if (ask == null) {
                go()
                return@launch
            }
            val answer = ask(ask.first, ask.second) ?: return@launch
            if (mine != ticket) return@launch
            try {
                if (answer.voice.online) source.grant(answer.voice.provider)
                if (answer.chosen) source.choose(bookId, answer.voice.id)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                // không nhớ được thì lõi vẫn chưa gửi chữ nào; lần sau hỏi lại
            }
            if (mine == ticket) go()
        }
    }

    override fun cancel() {
        supersede()
    }

    private fun supersede(): Int {
        ticket++
        waiting?.complete(null)
        return ticket
    }

    /** Giọng của cuốn và danh sách giọng khi cần hỏi; null khi không cần. */
    private suspend fun needed(bookId: String): Pair<ConsentVoice, List<ConsentVoice>>? {
        val voices = source.voices()
        val voice = OnlineConsent.resolve(voices, source.chosen(bookId)) ?: return null
        return if (OnlineConsent.needsPrompt(voice, source.consents())) voice to voices else null
    }

    private suspend fun ask(voice: ConsentVoice, voices: List<ConsentVoice>): ConsentAnswer? {
        val reply = CompletableDeferred<ConsentAnswer?>()
        waiting = reply
        val shown = ConsentRequest(voice, voices) { reply.complete(it) }
        flow.value = shown
        try {
            return reply.await()
        } finally {
            if (flow.value === shown) flow.value = null
            if (waiting === reply) waiting = null
        }
    }
}
