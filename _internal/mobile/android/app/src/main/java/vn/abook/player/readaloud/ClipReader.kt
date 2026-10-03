package vn.abook.player.readaloud

/**
 * Đọc MỘT đoạn chữ thành [Clip]: tìm trong [ClipCache] trước, không có thì giọng đã chọn đọc; giọng mạng (Edge) hỏng - hết mạng, quá hạn, dịch vụ từ chối - thì
 * đoạn ấy rơi về giọng của máy và việc nghe KHÔNG dừng. Edge vừa hỏng thì nghỉ [EDGE_BREAK_MS] mới thử lại (không để mỗi đoạn chờ hết hạn nối mạng). Cả hai giọng hỏng
 * thì ném [VoiceException] với câu nói thẳng cho người nghe. Chạy ở luồng nền.
 */
class ClipReader(
    private val cache: ClipCache,
    private val voiceFor: (String) -> Voice,
    private val fallback: () -> Voice?,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    companion object {
        const val EDGE_BREAK_MS = 120_000L
        const val ONLINE_ERROR_BREAK_MS = 30_000L
    }

    @Volatile private var onlineDownUntil = 0L

    fun read(text: String, voiceId: String): Clip {
        val primary = voiceFor(voiceId)
        cache.get(primary.id, text)?.let { return it }
        var problem: VoiceException? = null
        val online = !primary.id.startsWith("device:")
        if (!online || clock() >= onlineDownUntil) {
            try {
                return synthesize(primary, text)
            } catch (error: VoiceException) {
                problem = error
                if (!online) throw error
                onlineDownUntil = clock() + if (error.offline) EDGE_BREAK_MS else ONLINE_ERROR_BREAK_MS
            }
        }
        val backup = fallback() ?: throw problem ?: VoiceException("Không có giọng nào đọc được - kiểm tra mạng hoặc cài giọng tiếng Việt cho máy")
        if (backup.id == primary.id) throw problem ?: VoiceException("Giọng của máy không đọc được đoạn này")
        cache.get(backup.id, text)?.let { return it }
        try {
            return synthesize(backup, text)
        } catch (error: VoiceException) {
            throw VoiceException("${problem?.message ?: "Giọng mạng không dùng được"}; ${error.message}", problem?.offline ?: false, error)
        }
    }

    private fun synthesize(voice: Voice, text: String): Clip {
        val tmp = cache.temp(voice.extension)
        try {
            val clip = voice.synthesize(text, tmp)
            return cache.put(voice.id, text, tmp, voice.extension, clip.durationMs, clip.words)
        } catch (error: VoiceException) {
            tmp.delete()
            throw error
        } catch (error: Exception) {
            tmp.delete()
            throw VoiceException("Không đọc được đoạn này (${error.message})", cause = error)
        }
    }
}
