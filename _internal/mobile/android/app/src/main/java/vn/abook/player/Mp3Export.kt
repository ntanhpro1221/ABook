package vn.abook.player

import org.json.JSONObject
import java.io.File
import java.io.OutputStream

/**
 * "Xuất MP3 để nghe ở app khác" trên điện thoại - cùng bản xuất với máy tính (webui/export.py `export_book`): một thư mục mang
 * tên sách, mỗi chương ĐÃ XONG một file MP3 cùng tên file, cùng tag (Id3Tag), cùng ảnh bìa, kèm `cover.jpg` (hay `cover.png` -
 * bìa giao diện tự vẽ) và danh sách phát `.m3u8`. Audio chương trong sách đã là MP3: chép rồi gắn tag lại, không mã hoá lại.
 *
 * Phần này không biết gì về Android: chỗ ghi là một [Destination] (Mp3ExportWorker ghi qua thư mục người dùng chọn bằng bộ chọn của
 * hệ thống; test JVM ghi ra thư mục thường).
 */
object Mp3Export {
    private val UNSAFE = Regex("""[<>:"/\\|?*\u0000-\u001f]""")
    /** Tên một file trên ext4 / FAT của điện thoại: tối đa 255 byte UTF-8. */
    private const val NAME_BYTES = 255

    /** Người dùng bấm "Dừng" (hay việc bị thay bằng lượt xuất mới). */
    class Stopped : Exception("Đã dừng xuất")

    /** Câu cho người dùng: sách không có gì để xuất, chỗ lưu không ghi được. */
    class Refused(message: String) : Exception(message)

    /** Thư mục bản xuất: ghi một file (thay file cùng tên). Chưa ghi xong thì không để lại file dở - cách làm tuỳ nơi ghi. */
    interface Folder {
        /** Tên hiện cho người dùng (vd "Music/Sách thử"). */
        val label: String

        /** Địa chỉ để mở thư mục này bằng app Tệp của hệ thống (thư mục SAF); null khi nơi ghi không có (test, thư mục thường). */
        val uri: String? get() = null
        fun write(name: String, body: (OutputStream) -> Unit)
    }

    /** Nơi lưu bản xuất: tạo (hay mở lại) thư mục con `name`. */
    fun interface Destination {
        fun folder(name: String): Folder
    }

    /** Nơi lưu là một thư mục thường (test JVM, bài thử trên máy): "<tên>.part" rồi đổi tên, như máy tính. */
    class FileDestination(private val root: File) : Destination {
        override fun folder(name: String): Folder {
            val dir = File(root, name).apply { mkdirs() }
            return object : Folder {
                override val label = "${root.name}/$name"
                override fun write(name: String, body: (OutputStream) -> Unit) {
                    val part = File(dir, "$name.part")
                    try {
                        part.outputStream().buffered().use(body)
                    } catch (error: Throwable) {
                        part.delete()
                        throw error
                    }
                    val final = File(dir, name)
                    if (!part.renameTo(final)) {
                        final.delete()
                        if (!part.renameTo(final)) throw Refused("Không ghi được $name")
                    }
                }
            }
        }
    }

    class Chapter(val number: Int, val fullTitle: String, val duration: Double, val file: File)

    /**
     * Việc xuất một cuốn: tên sách, giọng kể, các chương sẽ ghi, số chương nghe được (`numbered` - số thứ tự "n/tổng" đếm trên chúng,
     * như máy tính), tổng số chương của sách, bìa.
     */
    class Plan(val title: String, val narrator: String, val chapters: List<Chapter>, val numbered: Int, val chaptersTotal: Int,
               val cover: Id3Tag.Cover?, val coverName: String)

    class Result(val folder: String, val files: Int, val chaptersTotal: Int, val uri: String? = null)

    /** `safe_name` của máy tính: bỏ ký tự Windows cấm, gộp khoảng trắng, cắt `limit` ký tự, giữ nguyên chữ tiếng Việt. */
    fun safeName(text: String, limit: Int = 120): String {
        val cleaned = BookEdits.pyStrip(UNSAFE.replace(text, " ")).trim('.')
        val collapsed = StringBuilder(cleaned.length)
        var space = false
        for (char in cleaned) {
            if (BookEdits.isSpace(char)) {
                if (!space) collapsed.append(' ')
                space = true
            } else {
                collapsed.append(char)
                space = false
            }
        }
        return BookEdits.cut(collapsed.toString(), limit).trimEnd { BookEdits.isSpace(it) }.ifEmpty { "Sach" }
    }

    /** Tên file của chương thứ `number` trong `total` chương xuất: "01 - Chương 1 · Mở đầu.mp3" (`chapter_file_name`). */
    fun chapterFileName(number: Int, total: Int, fullTitle: String): String {
        val width = maxOf(2, total.toString().length)
        return fitName("${number.toString().padStart(width, '0')} - ", safeName(fullTitle, 90), ".mp3")
    }

    /** Tên thư mục của bản xuất (tên sách). */
    fun folderName(title: String): String = fitName("", safeName(title), "")

    /** Tên danh sách phát. */
    fun playlistName(title: String): String = fitName("", safeName(title), ".m3u8")

    /**
     * Máy tính (NTFS) nhận tên tới 255 ký tự UTF-16, điện thoại chỉ 255 byte UTF-8: tên tiếng Việt dài gần 90 ký tự có dấu có thể quá.
     * Chỉ khi ấy mới cắt bớt phần tên - mọi tên vừa thì giống hệt máy tính.
     */
    private fun fitName(prefix: String, name: String, suffix: String): String {
        var cut = name
        while (cut.length > 1 && (prefix + cut + suffix).toByteArray(Charsets.UTF_8).size > NAME_BYTES) {
            cut = BookEdits.cut(cut, cut.codePointCount(0, cut.length) - 1).trimEnd { BookEdits.isSpace(it) }
        }
        return prefix + cut + suffix
    }

    /** Danh sách phát `.m3u8` (`playlist_text`): mỗi chương một dòng #EXTINF (giây làm tròn như Python) và tên file. */
    fun playlist(title: String, entries: List<Triple<Double, String, String>>): String {
        val lines = mutableListOf("#EXTM3U", "#PLAYLIST:$title")
        for ((duration, fullTitle, name) in entries) {
            lines += "#EXTINF:${Math.rint(duration).toLong()},$fullTitle"
            lines += name
        }
        return lines.joinToString("\n") + "\n"
    }

    /**
     * Việc xuất cuốn `id` như người nghe thấy nó (Store.manifest: tên sách, tên chương, bìa đã sửa). Chỉ chương nghe được - như máy
     * tính, số thứ tự đếm trên các chương ấy. `drawnCover`: PNG bìa giao diện tự vẽ, chỉ dùng khi sách không có bìa thật.
     */
    fun plan(id: String, drawnCover: ByteArray? = null): Plan {
        val book = Store.manifest(id) ?: throw Refused("Không tìm thấy sách này trên điện thoại")
        val chapters = book.optJSONArray("chapters")
        val listenable = ArrayList<JSONObject>()
        for (index in 0 until (chapters?.length() ?: 0)) {
            val chapter = chapters!!.optJSONObject(index) ?: continue
            if (chapter.optBoolean("available") && chapter.optString("file").isNotEmpty()) listenable += chapter
        }
        if (listenable.isEmpty()) throw Refused("Sách chưa có chương nào nghe được để xuất")
        val planned = listenable.mapIndexedNotNull { index, chapter ->
            val file = runCatching { Store.file(id, chapter.optString("file")) }.getOrNull()?.takeIf { it.isFile } ?: return@mapIndexedNotNull null
            Chapter(index + 1, chapter.optString("fullTitle"), chapter.optDouble("duration", 0.0).takeIf { !it.isNaN() } ?: 0.0, file)
        }
        val real = Store.coverFile(id)?.let { runCatching { Id3Tag.Cover.of(it.readBytes()) }.getOrNull() }
        val cover = real ?: drawnCover?.let(Id3Tag.Cover::of)?.takeIf { it.mime == "image/png" }
        return Plan(
            title = book.optString("title").ifEmpty { id },
            narrator = book.optString("narrator"),
            chapters = planned,
            numbered = listenable.size,
            chaptersTotal = book.optInt("chaptersTotal", chapters?.length() ?: 0),
            cover = cover,
            // Như máy tính: bìa thật chép thành covers.COVER_FILE, bìa tự vẽ thành cover.png.
            coverName = if (real != null) "cover.jpg" else "cover.png",
        )
    }

    /**
     * Ghi bản xuất vào `destination`: bìa, từng chương, danh sách phát. `progress(đã xong, tổng)` sau mỗi chương; `stopped` được hỏi
     * suốt lúc chép - true thì dừng ngay (ném [Stopped]), chương đang chép dở không để lại file, các chương đã xong vẫn còn.
     */
    fun run(plan: Plan, destination: Destination, progress: (Int, Int) -> Unit = { _, _ -> }, stopped: () -> Boolean = { false }): Result {
        val folder = destination.folder(folderName(plan.title))
        plan.cover?.let { cover -> folder.write(plan.coverName) { it.write(cover.bytes) } }
        val listed = plan.chapters.size
        val entries = ArrayList<Triple<Double, String, String>>()
        progress(0, listed)
        for (chapter in plan.chapters) {
            if (stopped()) throw Stopped()
            val name = chapterFileName(chapter.number, plan.numbered, chapter.fullTitle)
            val fields = Id3Tag.Fields(chapter.fullTitle, plan.title, plan.narrator, chapter.number, plan.numbered, plan.cover)
            folder.write(name) { out -> Id3Tag.write(chapter.file, out, fields, stopped) }
            entries += Triple(chapter.duration, chapter.fullTitle, name)
            progress(entries.size, listed)
        }
        folder.write(playlistName(plan.title)) { it.write(playlist(plan.title, entries).toByteArray(Charsets.UTF_8)) }
        return Result(folder.label, entries.size, plan.chaptersTotal, folder.uri)
    }
}
