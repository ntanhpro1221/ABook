package vn.abook.player

import android.content.Context
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import vn.abook.player.ui.voice.SamplePlayer
import java.io.File
import java.io.IOException
import java.security.MessageDigest

/** Một thứ để nghe: file `path` (`/media/...`) trên máy `computer`, hay chỉ đoạn [startMs, endMs) của nó (một câu trong file chương). */
data class ClipSpec(val computer: String, val path: String, val startMs: Int = 0, val endMs: Int = 0)

/** Vì sao một clip không nghe được. */
enum class ClipFailure { Offline, Missing }

/** `playing`: mã clip đang phát; `loading`: mã clip đang tải về; `failure`: lần bấm gần nhất hỏng vì sao (null = không hỏng). */
data class ClipState(val playing: String? = null, val loading: String? = null, val failure: ClipFailure? = null)

/**
 * Nghe thử trong Studio từ xa (NATIVE_REMOTE_STUDIO.md §3.2-B): trình phát hệ thống không ghim được vân tay của máy tính nên clip được TẢI VỀ
 * `dir` (cache, nối lại được khi rớt mạng) rồi phát bằng [SamplePlayer]. Mọi câu cùng chương dùng lại một file chương. Cache giữ tối đa [limitBytes]
 * (xoá file cũ nhất trước) khi khởi động và khi đóng màn. Một lúc chỉ một clip (bấm clip khác thì clip cũ dừng); gọi từ luồng chính.
 *
 * `fetch(computer, path, partial)` tải HẾT file vào `partial` (hay ném lỗi, để lại phần dở cho lần sau); bản thật: [StudioDownloads.fetch].
 */
class StudioClips(
    private val dir: File,
    private val fetch: suspend (computer: String, path: String, partial: File) -> Unit,
    private val player: SamplePlayer,
    private val scope: CoroutineScope,
    private val limitBytes: Long = CACHE_BYTES,
) {
    private val flow = MutableStateFlow(ClipState())
    val state: StateFlow<ClipState> get() = flow
    private var job: Job? = null

    /** Lượt bấm hiện tại: lời gọi lại của lượt cũ (tải xong muộn, phát hết sau khi đã bấm clip khác) bị bỏ. */
    private var turn = 0

    /**
     * Bấm clip `id`: đang phát / đang tải chính nó thì dừng, không thì dừng clip khác rồi tải + phát. `onEnded` chạy khi clip phát HẾT (không khi bị dừng
     * hay hỏng) - "Phát tiếp" sang câu kế.
     */
    fun toggle(id: String, spec: ClipSpec, onEnded: () -> Unit = {}) {
        if (flow.value.playing == id || flow.value.loading == id) {
            stop()
            return
        }
        stop()
        val mine = ++turn
        flow.value = ClipState(loading = id)
        job = scope.launch {
            val file = try {
                withContext(Dispatchers.IO) { cached(spec) }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                if (mine == turn) flow.value = ClipState(failure = if (error is IOException && error !is java.io.FileNotFoundException) ClipFailure.Offline else ClipFailure.Missing)
                return@launch
            }
            if (mine != turn) return@launch
            flow.value = ClipState(playing = id)
            player.playRange(
                file.path, spec.startMs, spec.endMs,
                onEnded = { if (mine == turn) { flow.value = ClipState(); onEnded() } },
                onFailed = { if (mine == turn) flow.value = ClipState(failure = ClipFailure.Missing) },
            )
        }
    }

    /** Dừng clip đang phát / đang tải. */
    fun stop() {
        turn++
        job?.cancel()
        job = null
        player.stop()
        if (flow.value.playing != null || flow.value.loading != null) flow.value = ClipState()
    }

    /** Đóng màn: dừng, rồi dọn cache về trần. */
    fun release() {
        stop()
        trim()
    }

    /** File đã tải đủ của `spec` trong cache; chưa có thì tải (nối tiếp phần dở) rồi đổi tên. Chạy ở luồng IO. */
    private suspend fun cached(spec: ClipSpec): File {
        dir.mkdirs()
        val target = File(dir, name(spec))
        if (target.isFile && target.length() > 0) {
            target.setLastModified(System.currentTimeMillis())
            return target
        }
        val partial = File(target.path + ".part")
        fetch(spec.computer, spec.path, partial)
        PartResume.tagFile(partial).delete()
        if (!partial.renameTo(target)) throw IOException("Chưa ghi được bản thu vào bộ nhớ đệm")
        trim(keep = target)
        return target
    }

    /** Xoá file cũ nhất cho tới khi cache không vượt trần; `keep`: file đang dùng, không bao giờ xoá. */
    fun trim(keep: File? = null) {
        val files = dir.listFiles()?.filter { it.isFile && it != keep } ?: return
        var total = files.sumOf { it.length() } + (keep?.length() ?: 0L)
        for (file in files.sortedBy { it.lastModified() }) {
            if (total <= limitBytes) break
            total -= file.length()
            file.delete()
        }
    }

    companion object {
        /** Trần cache clip (NATIVE_REMOTE_STUDIO.md §3.2-B). */
        const val CACHE_BYTES = 50L * 1024 * 1024

        /** Tên file cache của một clip: băm của (máy, đường) - cùng đường thì cùng file, ký tự lạ không lọt vào tên. */
        fun name(spec: ClipSpec): String {
            val digest = MessageDigest.getInstance("SHA-1").digest("${spec.computer}\u0000${spec.path}".toByteArray(Charsets.UTF_8))
            return digest.joinToString("") { "%02x".format(it) }.take(24) + ".clip"
        }
    }
}

/** Phần tải thật của [StudioClips]: GET có ghim vân tay + nối lại (SyncLink.download, PeerTransfer.fetchResumable). */
object StudioDownloads {
    /** Trần một clip: một chương dài ~60 MB (docs 13.1-3: tải cả chương một lần). */
    const val LIMIT_BYTES = 256L * 1024 * 1024

    fun fetch(context: Context, computer: String, path: String, partial: File) {
        require(StudioPaths.safeMedia(path)) { "Đường không hợp lệ" }
        val link = StudioLink.link(context, computer) ?: throw StudioError.Unauthorized()
        val dir = partial.parentFile ?: throw IOException("Thiếu thư mục cache")
        PeerTransfer.fetchResumable({ from, tag -> SyncLink.download(context, link, path, from, tag) }, path, partial, 0, LIMIT_BYTES, dir)
    }
}
