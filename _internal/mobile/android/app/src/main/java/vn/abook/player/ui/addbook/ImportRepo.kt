package vn.abook.player.ui.addbook

import vn.abook.player.S

import android.content.Context
import android.graphics.pdf.PdfRenderer
import android.net.Uri
import android.os.Build
import android.os.ParcelFileDescriptor
import android.provider.DocumentsContract
import android.provider.OpenableColumns
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import vn.abook.player.AndroidCoverCodec
import vn.abook.player.BookEdits
import vn.abook.player.BookFileImport
import vn.abook.player.BookImport
import vn.abook.player.Store
import vn.abook.player.TextBook
import vn.abook.player.TextImports
import vn.abook.player.Work
import vn.abook.player.WorkSink
import vn.abook.player.WorkStep
import java.io.File

data class PreparedImport(val ref: String?, val name: String, val preview: ImportPreview? = null, val bookId: String? = null, val existing: Boolean = false, val packageReview: PackageReview? = null, val notice: String = "")

/** Narrow typed boundary. Tests inject it; production calls the core, never a Plugin or LocalStudio route. */
interface ImportSource {
    /** `progress` (cả ở [prepare]): tiến độ theo việc thật (byte đã chép / kiểm, số file, số trang), gọi từ luồng nền. */
    suspend fun replace(item: ImportItem, progress: WorkSink = {}): PreparedImport = error(S.s_chua_thay_duoc_sach_8eebed8f)
    suspend fun describe(item: ImportItem): String = item.name
    suspend fun prepare(item: ImportItem, progress: WorkSink = {}): PreparedImport
    suspend fun revise(ref: String, choices: ImportChoices): ImportPreview
    suspend fun add(ref: String, preview: ImportPreview, choices: ImportChoices): Pair<String, Boolean>
    suspend fun discard(ref: String)
}

class ImportRepo(private val context: Context) : ImportSource {
    private val pdfPages = HashMap<String, List<List<String>>>()
    private val created = HashMap<String, TextImports.Created>()

    override suspend fun describe(item: ImportItem): String = withContext(Dispatchers.IO) { name(document(item)) ?: item.name }

    private fun document(item: ImportItem): Uri {
        val uri = Uri.parse(item.source)
        return if (item.folder) DocumentsContract.buildDocumentUriUsingTree(uri, DocumentsContract.getTreeDocumentId(uri)) else uri
    }

    override suspend fun prepare(item: ImportItem, progress: WorkSink): PreparedImport = withContext(Dispatchers.IO) {
        Store.init(context)
        TextImports.codec = AndroidCoverCodec
        val uri = Uri.parse(item.source)
        val shown = name(document(item)) ?: item.name
        val mime = context.contentResolver.getType(document(item))
        val incoming = TextImports.incomingName(mime, shown)
        val head = { context.contentResolver.openInputStream(uri)?.use { input -> ByteArray(512).let { buffer -> buffer.copyOf(maxOf(0, input.read(buffer))) } } }
        // File chia sẻ qua kiểu chung (octet-stream, zip) mà không phải thứ app nhận: từ chối bằng lời của [TextImports.refuseShared].
        if (!item.folder) TextImports.refuseShared(mime, shown, head)?.let { throw BookImport.Failed(it) }
        val packageFile = !item.folder && (TextImports.isAppBookFile(mime, shown) || (incoming == null && BookFileImport.looksLikeBookFile(head() ?: ByteArray(0))))
        if (packageFile) {
            val result = BookFileImport.import(context, uri, progress = progress)
            if (result.how in setOf("older", "conflict")) return@withContext PreparedImport(null, shown,
                packageReview = PackageReview(result.id, result.title, result.incomingTitle, result.how))
            val notice = if (result.incomingTitle.isNotBlank() && result.incomingTitle != result.title) S.s_ten_trong_file_la_0_khac_ten_dang_dung_f6042eec(result.incomingTitle)
                else if (result.how == "updated") S.s_da_cap_nhat_0_627a2681(result.title) else S.s_da_them_0_ea40abe7(result.title)
            return@withContext PreparedImport(null, shown, bookId = result.id, existing = result.how == "existing", notice = notice)
        }
        val staged = if (item.folder) stageFolder(uri, progress) else TextImports.stageFile(incoming ?: shown, sizeOf(uri), progress) {
            context.contentResolver.openInputStream(uri)
        }
        try {
            staged.pdf?.let { pdfPages[staged.ref] = readPdf(it, progress) }
            // Tách chương, tìm lời chú: không có số đo trước được - thanh chạy liên tục, chữ nói "Đang đọc".
            progress(Work(WorkStep.Read, 0, 0, TextImports.STAGE_SHARE, 1f))
            PreparedImport(staged.ref, shown, preview = read(staged.ref, ImportChoices()))
        } catch (error: Exception) {
            TextImports.discard(staged.ref)
            pdfPages.remove(staged.ref)
            throw error
        }
    }

    override suspend fun revise(ref: String, choices: ImportChoices): ImportPreview = withContext(Dispatchers.IO) { read(ref, choices) }

    private fun read(ref: String, choices: ImportChoices): ImportPreview {
        val book = TextImports.prepare(ref, pdfPages[ref], splitChapters = choices.split,
            footnotes = BookImport.FootnoteChoice(choices.hideMarks, choices.notes))
        val picks = BookImport.defaultPicks(book)
        val exact = if (picks.isEmpty()) null else Store.findByChapters(TextBook.prints(BookImport.selectChapters(book, picks)))
        val same = TextImports.sameSource(ref)
        val existing = exact ?: same
        return ImportPreview(
            book.title, book.author.orEmpty(), book.chapters.mapIndexed { index, row ->
                ImportChapter(index + 1, row.name.ifEmpty { row.title }, !row.short && (book.keepMatter || row.matter.isEmpty()), row.matter)
            }, book.credits.map { Suggestion(it.first, it.second) }, book.notes.toList(),
            book.footnoteFound, book.footnoteMarks, book.footnoteExamples.firstOrNull()?.let { "${it.first}\n${it.second}" }.orEmpty(),
            book.splitOffer, book.splitHeadings, existing,
            existing?.let { Store.manifest(it)?.optString("title") }.orEmpty(),
            sameSource = exact == null && same != null,
            existingChapters = existing?.let { Store.manifest(it)?.optJSONArray("chapters")?.length() } ?: 0,
        )
    }

    override suspend fun add(ref: String, preview: ImportPreview, choices: ImportChoices): Pair<String, Boolean> = withContext(Dispatchers.IO) {
        require(choices.title.isNotBlank()) { S.s_ban_hay_nhap_ten_sach_da2b7a84 }
        require(choices.title.codePointCount(0, choices.title.length) <= BookEdits.TITLE_MAX) { S.s_ten_qua_dai_ban_hay_dung_toi_da_0_ky_tu_a84827da(BookEdits.TITLE_MAX) }
        val accepted = ImportLogic.accepted(preview, choices)
        val result = created[ref] ?: TextImports.createBook(ref, choices.title, context.cacheDir, choices.separate,
            ImportLogic.picks(preview, choices)).also { created[ref] = it }
        // Suggestions are opt-in. Source text is never rewritten by a skip edit.
        for (group in accepted) BookEdits.setSkipLine(Store.bookDir(result.id), group.chapters.map { it.toLong() }, group.line, true)
        pdfPages.remove(ref)
        created.remove(ref)
        result.id to (result.how == "existing")
    }

    override suspend fun discard(ref: String) = withContext(Dispatchers.IO) {
        TextImports.discard(ref)
        pdfPages.remove(ref)
        created.remove(ref)
        Unit
    }

    override suspend fun replace(item: ImportItem, progress: WorkSink): PreparedImport = withContext(Dispatchers.IO) {
        val result = BookFileImport.import(context, Uri.parse(item.source), allowOlder = true, progress = progress)
        PreparedImport(null, item.name, bookId = result.id, notice = S.s_da_them_0_ea40abe7(result.title))
    }

    private fun name(uri: Uri): String? {
        // ACTION_VIEW accepts file: as well as content:. A file URI has no document-provider display name.
        if (uri.scheme == "file") return uri.path?.let { File(it).name }
        return context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use {
            if (it.moveToFirst()) it.getString(0) else null
        } ?: uri.lastPathSegment
    }

    /** Cỡ file: độ dài thật của bộ mô tả trước (cột SIZE có thể cũ), không có thì cột SIZE; 0 = chưa biết. */
    private fun sizeOf(uri: Uri): Long = runCatching { context.contentResolver.openAssetFileDescriptor(uri, "r")?.use { it.length } }.getOrNull()?.takeIf { it > 0 }
        ?: runCatching {
            context.contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { if (it.moveToFirst() && !it.isNull(0)) it.getLong(0) else null }
        }.getOrNull()?.takeIf { it > 0 } ?: 0L

    private fun stageFolder(tree: Uri, progress: WorkSink): TextImports.Staged {
        val id = DocumentsContract.getTreeDocumentId(tree)
        val files = ArrayList<Pair<String, () -> java.io.InputStream?>>()
        val children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, id)
        context.contentResolver.query(children, arrayOf(DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE), null, null, null)?.use { cursor ->
            while (cursor.moveToNext()) {
                if (cursor.getString(2) == DocumentsContract.Document.MIME_TYPE_DIR) continue
                val uri = DocumentsContract.buildDocumentUriUsingTree(tree, cursor.getString(0))
                files += cursor.getString(1) to { context.contentResolver.openInputStream(uri) }
            }
        }
        return TextImports.stageFolder(name(DocumentsContract.buildDocumentUriUsingTree(tree, id)) ?: S.s_file_da_chon_e29eb975, files, progress)
    }

    private fun readPdf(file: File, progress: WorkSink): List<List<String>> {
        check(Build.VERSION.SDK_INT >= 35) { S.s_may_nay_chua_lay_chu_pdf_truc_tiep_duoc_ba_2d4d21bd }
        return pdfText(file, progress)
    }

    /** Lấy chữ từng trang; `progress`: số trang đã đọc / tổng trang, chiếm phần sau bước chép của thanh. */
    @android.annotation.TargetApi(35)
    private fun pdfText(file: File, progress: WorkSink): List<List<String>> =
        PdfRenderer(ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)).use { pdf ->
            require(pdf.pageCount <= 5000) { S.s_pdf_qua_nhieu_trang_ban_hay_chia_file_roi_92aad5ba }
            var chars = 0L
            val pages = pdf.pageCount.toLong()
            (0 until pdf.pageCount).map { index ->
                progress(Work(WorkStep.Read, index.toLong(), pages, TextImports.STAGE_SHARE, 1f, bytes = false))
                pdf.openPage(index).use { page ->
                    page.textContents.flatMap { it.text.lines() }.also { lines ->
                        chars += lines.sumOf { it.length.toLong() }
                        require(chars <= 16L * 1024 * 1024) { S.s_pdf_co_qua_nhieu_chu_ban_hay_chia_file_roi_8d90218e }
                    }
                }
            }
        }
}
