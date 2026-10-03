package vn.abook.player.readaloud

import java.util.concurrent.ConcurrentHashMap

/**
 * Đọc MỘT đoạn chữ thành [Clip]: tìm trong [ClipCache] trước, không có thì giọng đã chọn đọc; giọng mạng hỏng - hết mạng, quá hạn, dịch vụ từ chối, khoá của người
 * dùng bị từ chối hay hết hạn mức - thì đoạn ấy rơi sang giọng kế và việc nghe KHÔNG dừng: giọng dùng khoá -> giọng Edge mặc định ([onlineFallback]) -> giọng của máy
 * ([fallback]); Edge -> giọng của máy. Nhà cung cấp vừa hỏng thì nghỉ một lúc mới thử lại ([EDGE_BREAK_MS] khi mất mạng, [KEY_BREAK_MS] khi khoá bị từ chối / hết
 * hạn mức) - không để mỗi đoạn chờ hết hạn nối mạng. Mỗi chuyện nói với người nghe MỘT lần ([notice]). Giọng VieNeu (đọc trên máy) hỏng thì rơi thẳng sang giọng
 * của máy, KHÔNG qua giọng mạng: người chọn VieNeu được hứa chữ của sách không rời điện thoại. Mọi giọng hỏng thì ném [VoiceException] với câu nói thẳng
 * cho người nghe. Chạy ở luồng nền.
 */
class ClipReader(
    private val cache: ClipCache,
    private val voiceFor: (String) -> Voice,
    private val fallback: () -> Voice?,
    private val clock: () -> Long = System::currentTimeMillis,
    private val onlineFallback: () -> Voice? = { null },
    private val notice: (String) -> Unit = {},
) {
    companion object {
        const val EDGE_BREAK_MS = 120_000L
        const val ONLINE_ERROR_BREAK_MS = 30_000L
        const val KEY_BREAK_MS = 600_000L
        /** Mất mạng mà máy không có giọng nào đọc được khi không có mạng (không giọng tiếng Việt của máy, chưa tải VieNeu): một câu ngắn thay cho câu của giọng mạng
         *  (trước đây "... - đọc bằng giọng của máy" rồi dừng - thấy 03-10 trên máy ảo không có giọng tiếng Việt). Giao diện nhận ra nó nhờ [NO_OFFLINE_LEAD]
         *  (readAloudVoice.ts), thay "đang chọn" bằng tên giọng và đưa nút theo tình huống: "Đọc bằng …" nếu đã có giọng chạy trên máy, "Tải giọng VieNeu" nếu chưa. */
        const val NO_OFFLINE_LEAD = "Không có mạng - giọng "
        const val NO_OFFLINE_VOICE = "${NO_OFFLINE_LEAD}đang chọn cần mạng."

        private fun provider(voice: Voice) = voice.id.substringBefore(':')
        /** Đọc trên máy nhưng có thể chưa sẵn sàng (mô-đun tải thêm): hỏng thì đỡ bằng giọng của máy. */
        private fun local(voice: Voice) = provider(voice) == "vieneu"
        private fun online(voice: Voice) = provider(voice) != "device" && !local(voice)

        /** Câu cho người nghe khi đoạn này đọc tạm bằng `next` thay cho `failed` (cùng lời với giao diện máy tính, readAloudVoice.ts). */
        fun noticeFor(failed: Voice, problem: VoiceException, next: Voice): String {
            val keyed = OnlineVoices.NAMES[provider(failed)]
            val instead = if (provider(next) == "edge") "giọng Edge" else "giọng của máy"
            return when {
                local(failed) -> "Giọng VieNeu chưa đọc được lúc này - tạm đọc bằng $instead."
                keyed == null -> "Không dùng được giọng trực tuyến - tạm đọc bằng $instead."
                problem.reason == "auth" -> "Khóa $keyed không dùng được - tạm đọc bằng $instead. Kiểm tra lại khóa trong Cài đặt."
                problem.reason == "quota" -> "Khóa $keyed đã hết hạn mức - tạm đọc bằng $instead."
                else -> "Không dùng được giọng $keyed lúc này - tạm đọc bằng $instead."
            }
        }
    }

    private val downUntil = ConcurrentHashMap<String, Long>()
    private val downBecause = ConcurrentHashMap<String, VoiceException>()
    private val told = ConcurrentHashMap.newKeySet<String>()

    private fun tell(failed: Voice, problem: VoiceException, next: Voice) {
        val kind = if (problem.reason == "auth" || problem.reason == "quota") problem.reason else "network"
        if (told.add("${provider(failed)}:$kind")) runCatching { notice(noticeFor(failed, problem, next)) }
    }

    fun read(text: String, voiceId: String, origin: String? = null): Clip {
        val primary = voiceFor(voiceId)
        cache.get(primary.id, text, origin)?.let { return it }
        val chain = ArrayList<Voice>().apply {
            add(primary)
            if (online(primary)) {
                if (provider(primary) != "edge") onlineFallback()?.let { add(it) }
                fallback()?.let { add(it) }
            } else if (local(primary)) {
                fallback()?.let { add(it) }
            }
        }.distinctBy { it.id }
        val noOfflineVoice = chain.all { online(it) }
        fun offlineHelp(error: VoiceException?) =
            if (noOfflineVoice && error?.offline == true) VoiceException(NO_OFFLINE_VOICE, offline = true, cause = error, reason = error.reason) else null
        var first: VoiceException? = null // lỗi của giọng đã chọn: câu chính khi mọi giọng đều hỏng
        var failed: Voice? = null
        var problem: VoiceException? = null
        for ((index, voice) in chain.withIndex()) {
            if (index > 0) cache.get(voice.id, text, origin)?.let { clip ->
                if (failed != null && problem != null) tell(failed!!, problem!!, voice)
                return clip
            }
            if ((online(voice) || local(voice)) && clock() < (downUntil[provider(voice)] ?: 0L)) {
                // Vừa hỏng: không thử lại ở mỗi đoạn, đi thẳng sang giọng kế.
                val reason = downBecause[provider(voice)]
                if (problem == null && reason != null) {
                    failed = voice
                    problem = reason
                }
                continue
            }
            if (failed != null && problem != null) tell(failed!!, problem!!, voice)
            try {
                return synthesize(voice, text, origin)
            } catch (error: VoiceException) {
                val earlier = first
                if (!(online(voice) || local(voice)) || index == chain.lastIndex) {
                    offlineHelp(earlier ?: error)?.let { throw it }
                    if (earlier == null) throw error
                    throw VoiceException("${earlier.message}; ${error.message}", earlier.offline, error, earlier.reason)
                }
                downUntil[provider(voice)] = clock() + when {
                    error.reason == "auth" || error.reason == "quota" -> KEY_BREAK_MS
                    error.offline -> EDGE_BREAK_MS
                    else -> ONLINE_ERROR_BREAK_MS
                }
                downBecause[provider(voice)] = error
                if (first == null) first = error
                failed = voice
                problem = error
            }
        }
        throw offlineHelp(first ?: problem) ?: first ?: problem ?: VoiceException("Không có giọng nào đọc được - kiểm tra mạng hoặc cài giọng tiếng Việt cho máy")
    }

    /** Đúng giọng này, không rơi sang giọng khác ("Thử giọng" trong Cài đặt: người nghe muốn nghe chính giọng ấy, hỏng thì phải thấy lỗi). */
    fun readExactly(text: String, voiceId: String, origin: String? = null): Clip {
        val voice = voiceFor(voiceId)
        return cache.get(voice.id, text, origin) ?: synthesize(voice, text, origin)
    }

    private fun synthesize(voice: Voice, text: String, origin: String?): Clip {
        val tmp = cache.temp(voice.extension)
        try {
            val clip = voice.synthesize(text, tmp, origin)
            return cache.put(voice.id, text, tmp, voice.extension, clip.durationMs, clip.words, origin)
        } catch (error: VoiceException) {
            tmp.delete()
            throw error
        } catch (error: Exception) {
            tmp.delete()
            throw VoiceException("Không đọc được đoạn này (${error.message})", cause = error)
        }
    }
}
