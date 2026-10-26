package vn.abook.player.ui.voice

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

/**
 * Thêm nhạc vào Nhạc của tôi: MỘT lượt mỗi lúc cho cả app. Hai nơi bấm (Cài đặt > Nhạc của tôi, bảng Nhạc nền của từng cuốn) cùng đi qua đây nên nơi nào
 * cũng thấy lượt đang chạy, không nơi nào mở lượt thứ hai chồng lên, và xong thì mọi nơi cùng đọc lại kho. `owner`: nơi đã bấm ([MY_MUSIC] hay mã cuốn) -
 * câu báo của lượt chỉ hiện ở đó.
 */
@Stable
class MineImports(private val source: VoiceSource, private val scope: CoroutineScope) {
    @Immutable
    data class Turn(val owner: String, val done: Int, val total: Int)

    /** Người nghe của lượt: `changed` mỗi khi tiến độ đổi (null = không có lượt nào), `finished` khi lượt xong (sau `changed(null)`). */
    interface Listener {
        fun changed(turn: Turn?)
        fun finished(owner: String, result: Result<MusicImportResult>)
    }

    @Volatile
    var turn: Turn? = null
        private set
    private val listeners = ArrayList<Listener>()

    fun listen(listener: Listener) {
        listeners += listener
        listener.changed(turn)
    }

    /** Bắt đầu một lượt; đang có lượt (từ nơi nào cũng vậy) hay không chọn file nào thì bỏ qua và trả false. */
    fun start(owner: String, uris: List<String>): Boolean {
        if (uris.isEmpty() || turn != null) return false
        set(Turn(owner, 0, uris.size))
        scope.launch {
            val result = try {
                Result.success(source.importMusic(uris) { done, total -> set(Turn(owner, done, total)) })
            } catch (cancelled: CancellationException) {
                set(null)
                throw cancelled
            } catch (error: Exception) {
                Result.failure(error)
            }
            set(null)
            listeners.forEach { it.finished(owner, result) }
        }
        return true
    }

    private fun set(value: Turn?) {
        turn = value
        listeners.forEach { it.changed(value) }
    }

    companion object {
        /** Lượt bấm từ màn Nhạc của tôi (không thuộc cuốn nào). */
        const val MY_MUSIC = ""
    }
}
