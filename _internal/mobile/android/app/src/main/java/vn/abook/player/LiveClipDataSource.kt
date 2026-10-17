package vn.abook.player

import android.net.Uri
import androidx.annotation.OptIn
import androidx.media3.common.C
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.BaseDataSource
import androidx.media3.datasource.DataSource
import androidx.media3.datasource.DataSpec
import androidx.media3.datasource.TransferListener
import vn.abook.player.readaloud.LiveClips
import java.io.IOException

/**
 * Nguồn dữ liệu của ExoPlayer cho clip Edge ĐANG ĐƯỢC GHI (`abooklive://<id>`, [LiveClips]): đọc đúng file đang lớn, hết byte mà clip chưa xong thì chờ (có hạn, ngắt được), xong và hết byte
 * thì [C.RESULT_END_OF_INPUT]; clip hỏng giữa chừng (uxfix58) thì byte cuối cùng đã ghi là hết dữ liệu (phần đã về phát tới cùng, phần tiếp do ReadAloud nối sau),
 * chưa có byte nào mà hỏng thì [IOException]. Không mạng. Độ dài chưa biết ([C.LENGTH_UNSET]) cho tới khi clip xong - cần bộ tách mp3 tua theo tốc độ bit không đổi
 * ([Streaming.liveExtractors]).
 */
@OptIn(UnstableApi::class)
class LiveClipDataSource : BaseDataSource(false) {
    private var uri: Uri? = null
    private var reader: LiveClips.Reader? = null
    private var opened = false

    override fun open(dataSpec: DataSpec): Long {
        uri = dataSpec.uri
        transferInitializing(dataSpec)
        val entry = LiveClips.get(LiveClips.idOf(dataSpec.uri.toString())) ?: throw IOException("Clip đang đọc không còn")
        reader = entry.reader(dataSpec.position)
        opened = true
        transferStarted(dataSpec)
        val known = entry.remainingFrom(dataSpec.position) ?: C.LENGTH_UNSET.toLong()
        return when {
            dataSpec.length != C.LENGTH_UNSET.toLong() -> if (known >= 0) minOf(known, dataSpec.length) else dataSpec.length
            else -> known
        }
    }

    override fun read(buffer: ByteArray, offset: Int, length: Int): Int {
        if (length == 0) return 0
        val got = (reader ?: throw IOException("Chưa mở")).read(buffer, offset, length)
        if (got < 0) return C.RESULT_END_OF_INPUT
        bytesTransferred(got)
        return got
    }

    override fun getUri(): Uri? = uri

    override fun close() {
        reader?.close()
        reader = null
        uri = null
        if (opened) {
            opened = false
            transferEnded()
        }
    }
}

/**
 * Chọn nguồn theo scheme lúc mở: `abooklive://` -> [LiveClipDataSource], còn lại `other` (file, mạng + bộ đệm đĩa của [Streaming]). Một đối tượng cho mỗi lần tạo của ExoPlayer, nên lắng nghe truyền byte
 * được gắn vào cả hai.
 */
@OptIn(UnstableApi::class)
class LiveRoutingDataSource(private val live: DataSource, private val other: DataSource) : DataSource {
    private var current: DataSource? = null

    override fun addTransferListener(listener: TransferListener) {
        live.addTransferListener(listener)
        other.addTransferListener(listener)
    }

    override fun open(dataSpec: DataSpec): Long {
        val chosen = if (dataSpec.uri.scheme == LiveClips.SCHEME) live else other
        current = chosen
        return chosen.open(dataSpec)
    }

    override fun read(buffer: ByteArray, offset: Int, length: Int): Int = (current ?: throw IOException("Chưa mở")).read(buffer, offset, length)

    override fun getUri(): Uri? = current?.uri

    override fun getResponseHeaders(): Map<String, List<String>> = current?.responseHeaders ?: emptyMap()

    override fun close() {
        val chosen = current ?: return
        current = null
        chosen.close()
    }
}
