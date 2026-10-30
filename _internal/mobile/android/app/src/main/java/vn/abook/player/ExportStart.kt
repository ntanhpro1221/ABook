package vn.abook.player

import android.content.Context
import android.content.Intent
import android.net.Uri
import org.json.JSONObject
import vn.abook.player.readaloud.ReadAloud
import vn.abook.player.readaloud.VoiceSpeed
import java.io.File
import java.util.UUID

/**
 * Mở đầu và kết của ba kiểu xuất (MP3, M4B, sách nói) sau khi người dùng đã chọn nơi lưu: kiểm sách có gì để xuất, dựng ước, giữ quyền ghi, đẩy việc nền.
 * Một nơi cho `ui/export` gọi, không chép lại ở đâu khác.
 */
object ExportStart {
    /** Kết quả bắt đầu một lượt: mã lượt (tin của lượt mang mã này) và những gì giao diện cần nói ra ngay. */
    class Started(val run: String, val folder: String? = null, val name: String? = null, val chapters: Int? = null)

    /** Bìa tự vẽ của giao diện lưu thành file tạm cho việc nền (chỉ khi có); việc nền xoá khi xong. */
    private fun coverFile(context: Context, folder: String, drawn: ByteArray?): File? = drawn?.let { bytes ->
        File(context.cacheDir, folder).apply { mkdirs() }.let { File(it, "${UUID.randomUUID()}.png") }.also { it.writeBytes(bytes) }
    }

    // ---- MP3 --------------------------------------------------------------------------------------------------------------

    /** Sách đã có trên máy; không thì câu cho người dùng. */
    fun requireBook(id: String) {
        if (Store.manifest(id) == null) throw Mp3Export.Refused("Sách này chưa tải về điện thoại")
    }

    /** Bắt đầu xuất cuốn `bookId` thành thư mục MP3 trong `tree`; `chapterIds`: chỉ các chương ấy; sách không có gì để xuất thì [Mp3Export.Refused] ngay, chưa bắt đầu việc nền. */
    fun mp3(context: Context, bookId: String, tree: Uri, drawn: ByteArray?, chapterIds: List<Int>?, music: Boolean): Started {
        val plan = Mp3Export.plan(bookId, drawn, chapterIds)
        val treeName = Mp3Exports.treeName(context, tree) ?: throw Mp3Export.Refused("Không mở được thư mục đã chọn - chọn lại nơi lưu")
        val run = Mp3Exports.start(context, bookId, tree, coverFile(context, "mp3-export", drawn), chapterIds, music)
        return Started(run, folder = "$treeName/${Mp3Export.folderName(plan.title)}", chapters = plan.chapters.size)
    }

    // ---- M4B --------------------------------------------------------------------------------------------------------------

    /** Tên sách để hệ thống hỏi tên file; sách chưa có chương nghe được thì từ chối ngay, TRƯỚC khi hỏi chỗ lưu. */
    fun m4bTitle(bookId: String): String {
        requireBook(bookId)
        return Mp3Export.plan(bookId).title
    }

    /** Bắt đầu xuất cuốn `bookId` thành MỘT file M4B vào `file` (người dùng vừa tạo ở hộp "tạo file" của hệ thống). Không bắt đầu được thì file rỗng vừa tạo bị bỏ. */
    fun m4b(context: Context, bookId: String, file: Uri, drawn: ByteArray?, music: Boolean): Started {
        try {
            val plan = Mp3Export.plan(bookId, drawn)
            M4bExports.remember(context, file)
            val run = M4bExports.start(context, bookId, file, coverFile(context, "m4b-export", drawn), music)
            return Started(run, name = M4bExport.fileName(plan.title), chapters = plan.chapters.size)
        } catch (error: Exception) {
            M4bExports.discard(context, file)
            throw error
        }
    }

    // ---- sách nói (sách chỉ có chữ) -----------------------------------------------------------------------------------------

    private fun reading(id: String, voice: String) = ListenExport.Reading(voice, ReadAloud.originNow(id), ReadAloud.readingsOf(id))

    /** Tên sách để hệ thống hỏi tên file; sách chưa tải hay không có chương nào đọc được thì từ chối ngay, TRƯỚC khi hỏi chỗ lưu. */
    fun audiobookTitle(bookId: String): String {
        val book = Store.manifest(bookId) ?: throw Mp3Export.Refused("Sách này chưa tải về điện thoại")
        if (ListenExport.chapters(bookId).isEmpty()) throw Mp3Export.Refused("Sách chưa có chương nào có chữ để đọc")
        return book.optString("title").ifEmpty { bookId }
    }

    /**
     * Cho màn Xuất sách nói: số chương, số chữ, giờ nghe (từ clip đã có + phần chưa có ước theo tốc độ đo), ước thời gian máy làm, phần đã có sẵn và chỗ trống cần, kèm ô nhạc
     * `music` {available, enabled}. `wanted`: ô "Kèm nhạc nền" người dùng chọn (null = mặc định theo cuốn). Đọc chữ nên gọi ở luồng nền, sau [Playback.init].
     */
    fun audiobookPlan(context: Context, bookId: String, voice: String, wanted: Boolean?): JSONObject {
        val chapters = ListenExport.chapters(bookId)
        val speed = runCatching { ReadAloud.speeds().secondsPerChar(voice) }.getOrNull()
        val (available, enabled) = BookMusic.exportState(bookId)
        val (music, extra) = if (available && (wanted ?: enabled)) ExportMusic.listenPlan(context, bookId, chapters) else emptyMap<Int, MusicExport.ChapterMusic>() to 0L
        val reading = reading(bookId, voice)
        val cache = ReadAloud.cache()
        val plan = ListenExport.plan(chapters, reading, ListenExport.workFolder(ListenExports.workRoot(context), bookId), speed,
            music = { MusicExport.audible(music, it) }, cachedMs = { text -> cache.durationMs(VoiceSpeed.quality(voice), text, reading.origin, reading.readings) }, extra = extra)
        return plan.toJson().put("music", JSONObject().put("available", available).put("enabled", enabled))
    }

    /** Bắt đầu đọc cả cuốn `bookId` bằng giọng `voice` rồi ghép thành MỘT file M4B vào `file`. Không bắt đầu được thì file rỗng vừa tạo bị bỏ. */
    fun audiobook(context: Context, bookId: String, voice: String, file: Uri, drawn: ByteArray?, music: Boolean): Started {
        try {
            val title = Store.manifest(bookId)?.optString("title").orEmpty().ifEmpty { bookId }
            M4bExports.remember(context, file)
            val run = ListenExports.start(context, bookId, voice, file, coverFile(context, "audiobook-export", drawn), music)
            return Started(run, name = M4bExport.fileName(title))
        } catch (error: Exception) {
            M4bExports.discard(context, file)
            throw error
        }
    }

    // ---- mở kết quả ---------------------------------------------------------------------------------------------------------

    /** Mở file vừa xuất bằng app nghe sách nói của máy. Chỉ địa chỉ `content:` của nơi lưu người dùng chọn, không phải của chính app. */
    fun openFile(context: Context, uri: Uri): Boolean {
        val allowed = uri.scheme == "content" && uri.authority != "${context.packageName}.fileprovider"
        return allowed && ListenExports.open(context, uri)
    }

    /**
     * Mở thư mục bản xuất bằng app Tệp của hệ thống. Chỉ nhận địa chỉ nằm trong thư mục người dùng đã cấp cho ABook (không mở địa chỉ tuỳ ý); máy không có app nào mở được
     * thì false - giao diện nói đường đi bằng chữ.
     */
    fun openFolder(context: Context, uri: Uri): Boolean {
        val allowed = uri.scheme == "content" && context.contentResolver.persistedUriPermissions.any { uri.toString().startsWith(it.uri.toString()) }
        if (!allowed) return false
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, android.provider.DocumentsContract.Document.MIME_TYPE_DIR)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
        return runCatching { context.startActivity(intent) }.isSuccess
    }
}
