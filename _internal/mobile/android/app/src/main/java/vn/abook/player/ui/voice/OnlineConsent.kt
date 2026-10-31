package vn.abook.player.ui.voice

import vn.abook.player.formatSize

import androidx.compose.runtime.Immutable

/*
 * Phần thuần của hộp hỏi trước khi đọc bằng giọng trực tuyến và của khối lỗi "giọng đang chọn không đọc được" của trình phát.
 * Không Android: thử trên JVM.
 */

/** Một giọng như hộp hỏi thấy: `online` = chữ của sách rời máy khi đọc bằng nó. */
@Immutable
data class ConsentVoice(val id: String, val name: String, val provider: String, val online: Boolean, val gender: String = "")

/** Trả lời của hộp: giọng sẽ đọc, và `chosen` = bạn tự chọn nó trong danh sách "Chọn giọng đọc" (khác "Nghe": đó là lựa chọn giọng của cuốn). */
@Immutable
data class ConsentAnswer(val voice: ConsentVoice, val chosen: Boolean)

object OnlineConsent {
    /** Giọng cuốn sẽ đọc: mã đã nhớ nếu còn trong danh sách, không thì giọng mặc định của app, không thì giọng đầu tiên (readAloudVoice.ts `resolveVoice`). */
    fun resolve(voices: List<ConsentVoice>, id: String): ConsentVoice? =
        voices.firstOrNull { it.id == id } ?: voices.firstOrNull { it.id == VoiceState.ONLINE_VOICE } ?: voices.firstOrNull()

    /** Có phải hỏi trước khi đọc bằng giọng này không: giọng gửi chữ đi mà bạn chưa đồng ý với nhà cung cấp ấy (onlineConsent.ts `needsOnlineConsent`). */
    fun needsPrompt(voice: ConsentVoice?, consents: Set<String>): Boolean = voice != null && voice.online && voice.provider !in consents

    /** Lời trong bước "Chọn giọng đọc": chỉ nói "không gửi chữ" khi trong danh sách có giọng chạy trên máy, giọng trực tuyến thì nói chữ được gửi tới đâu (onlineConsent.ts `chooseVoiceText`). */
    fun chooseText(voices: List<ConsentVoice>, current: ConsentVoice): String {
        val hasLocal = voices.any { !it.online }
        val hasOnline = voices.any { it.online }
        val local = "Giọng của máy đọc ngay trên máy này, không gửi chữ đi đâu."
        val ask = VoiceText.consent(current.name, current.provider)
        if (!hasOnline) return local
        return if (hasLocal) "$local $ask" else ask
    }

    /** Chữ nhỏ dưới tên một giọng trong danh sách: nơi đọc, kèm " · đang chọn" cho giọng đang được hỏi. */
    fun tag(voice: ConsentVoice, currentId: String): String =
        (if (voice.online) "trực tuyến" else "của máy") + if (voice.id == currentId) " · đang chọn" else ""

    /** Tên nút nghe thử của một giọng cho trình đọc màn hình. */
    fun sampleLabel(playing: Boolean, name: String): String = (if (playing) "Dừng" else "Nghe thử") + " giọng " + VoiceText.spokenName(name)

    /** Chương mà một lệnh "chương trước / sau" sẽ tới (id), hay null nếu không có. `previous` quá 5 giây thì về đầu chính chương này (Playback.previous). */
    fun stepTarget(chapterIds: List<Int>, currentId: Int?, delta: Int, positionMs: Long): Int? {
        val index = chapterIds.indexOf(currentId ?: return null)
        if (index < 0) return null
        if (delta < 0 && positionMs > 5000) return chapterIds[index]
        return chapterIds.getOrNull(index + delta)
    }
}

/** Khối lỗi của trình phát khi giọng đang chọn không đọc được: lời báo ngắn nói tên giọng, và nút theo tình huống (readAloudVoice.ts `isVoiceStuck`, `localVoiceFor`). */
object VoiceStuck {
    /** Mở đầu chung của lời báo mất mạng (ClipReader.NO_OFFLINE_LEAD). */
    const val NO_OFFLINE_LEAD = "Không có mạng - giọng "
    private val UNUSABLE = Regex("^Giọng .+ đang không dùng được[.]$")

    fun isNoOffline(message: String): Boolean = message.startsWith(NO_OFFLINE_LEAD)

    /** "Giọng … đang không dùng được." (ClipReader.NO_USABLE_VOICE) - giọng trực tuyến có mạng mà vẫn hỏng. */
    fun isUnusable(message: String): Boolean = UNUSABLE.matches(message)

    /** Mất mạng, hay giọng hỏng, mà máy không có giọng nào khác đọc được. */
    fun isStuck(message: String): Boolean = isNoOffline(message) || isUnusable(message)

    /** Giọng đang đọc, viết cho người nghe: tên người, không kèm tên bộ máy đọc; giọng của máy (hay chưa biết) thì "Giọng đọc của máy" (readAloudVoice.ts `voiceCaption`). */
    fun caption(voice: ConsentVoice?): String =
        if (voice == null || voice.provider == "device") "Giọng đọc của máy" else VoiceText.spokenName(voice.name)

    fun noOfflineMessage(name: String): String = "$NO_OFFLINE_LEAD$name cần mạng."

    fun unusableMessage(name: String): String = "Giọng $name đang không dùng được."

    /** Lời hiện cho bạn: lõi chưa biết tên giọng ("đang chọn") nên giao diện thay bằng tên thật. */
    fun shown(error: String, voiceName: String?): String = when {
        voiceName == null || !isStuck(error) -> error
        isNoOffline(error) -> noOfflineMessage(VoiceText.spokenName(voiceName))
        else -> unusableMessage(VoiceText.spokenName(voiceName))
    }

    /** Giọng chạy trên máy đã tải (VieNeu, Supertonic; giọng của máy đã tự đỡ) để đổi sang khi mất mạng; cùng giới với giọng đang chọn nếu có. */
    fun localVoiceFor(voices: List<ConsentVoice>, current: ConsentVoice?): ConsentVoice? {
        val local = voices.filter { !it.online && it.provider != "device" }
        return local.firstOrNull { current != null && current.gender.isNotEmpty() && it.gender == current.gender } ?: local.firstOrNull()
    }
}

/** Việc tải giọng VieNeu ngay trong khối lỗi: một giọng nhẹ nhất đủ đọc là nút chính, gói đánh dấu sẵn của Cài đặt là nút phụ (vieneuModule.ts `offlineChoices`). */
data class OfflineOffer(val light: List<String>, val full: List<String>) {
    /** Cái cần tải cho nút chính: giọng nhẹ nhất, không có thì cả gói. */
    val missing: List<String> get() = light.ifEmpty { full }

    companion object {
        fun of(status: ModuleStatus): OfflineOffer {
            fun missing(ids: List<String>) = ids.filter { id -> status.choice(id)?.installed == false }
            val tier = if (status.recommended == "nano") "nano" else "turbo"
            val light = if (status.choice(tier) != null) missing(listOf(tier)) else emptyList()
            val full = missing(status.choices.filter { it.installed || it.ticked }.map { it.id })
            return OfflineOffer(light, full)
        }

        /** Byte phải tải cho các lựa chọn `ids` (mỗi lựa chọn chỉ tính phần của riêng nó). */
        fun bytes(status: ModuleStatus, ids: List<String>): Long = status.choices.filter { it.id in ids }.sumOf { it.bytes }

        /** Chữ trên nút tải: "Thử lại" sau lỗi, không thì `button` kèm cỡ cần tải. */
        fun label(button: String, failed: Boolean, bytes: Long): String =
            if (failed) "Thử lại" else if (bytes > 0) "$button (${formatSize(bytes)})" else button

        fun fullLabel(bytes: Long): String = "Gói đầy đủ (" + formatSize(bytes) + ")"
    }
}
