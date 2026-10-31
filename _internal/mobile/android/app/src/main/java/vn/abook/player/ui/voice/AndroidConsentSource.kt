package vn.abook.player.ui.voice

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import vn.abook.player.Playback
import vn.abook.player.Store
import vn.abook.player.readaloud.ReadAloud

/**
 * Nguồn thật của hộp hỏi đồng ý: gọi thẳng [ReadAloud] . Việc đổi trạng thái của lõi chạy ở luồng chính, theo đúng thứ tự
 * với lệnh phát đi sau (cả hai cùng xếp hàng ở [Playback.onMain]).
 */
class AndroidConsentSource(context: Context) : ConsentSource {
    private val app = context.applicationContext

    private suspend fun <T> io(block: () -> T): T = withContext(Dispatchers.IO) {
        Playback.init(app)
        Store.init(app)
        block()
    }

    override suspend fun voices(): List<ConsentVoice> = io {
        ReadAloud.voices(app).map { ConsentVoice(it.optString("id"), it.optString("name"), it.optString("provider"), it.optBoolean("online"), it.optString("gender")) }
    }

    override suspend fun chosen(bookId: String): String = io { ReadAloud.voiceForBook(bookId, Store.activeRecord(bookId)) }

    override suspend fun consents(): Set<String> = io { ReadAloud.onlineConsents().toSet() }

    override suspend fun grant(provider: String) {
        Playback.onMain { ReadAloud.grantOnline(provider) }
    }

    override suspend fun choose(bookId: String, voiceId: String) {
        val record = io { Store.activeRecord(bookId) }
        Playback.onMain { ReadAloud.chooseFor(bookId, voiceId, record) }
    }
}
