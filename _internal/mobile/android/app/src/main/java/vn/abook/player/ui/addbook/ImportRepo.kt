package vn.abook.player.ui.addbook

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
import java.io.File

data class PreparedImport(val ref: String?, val name: String, val preview: ImportPreview? = null, val bookId: String? = null, val existing: Boolean = false, val packageReview: PackageReview? = null, val notice: String = "")

/** Narrow typed boundary. Tests inject it; production calls the core, never a Plugin or LocalStudio route. */
interface ImportSource {
    suspend fun replace(item: ImportItem): PreparedImport = error("Chưa thay được sách")
    suspend fun describe(item: ImportItem): String = item.name
    suspend fun prepare(item: ImportItem): PreparedImport
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

    override suspend fun prepare(item: ImportItem): PreparedImport = withContext(Dispatchers.IO) {
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
            val result = BookFileImport.import(context, uri)
            if (result.how in setOf("older", "conflict")) return@withContext PreparedImport(null, shown,
                packageReview = PackageReview(result.id, result.title, result.incomingTitle, result.how))
            val notice = if (result.incomingTitle.isNotBlank() && result.incomingTitle != result.title) "Tên trong file là “${result.incomingTitle}”, khác tên đang dùng." else "Đã thêm “${result.title}”"
            return@withContext PreparedImport(null, shown, bookId = result.id, existing = result.how == "existing", notice = notice)
        }
        val staged = if (item.folder) stageFolder(uri) else TextImports.stageFile(incoming ?: shown) {
            context.contentResolver.openInputStream(uri)
        }
        try {
            staged.pdf?.let { pdfPages[staged.ref] = readPdf(it) }
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
        require(choices.title.isNotBlank()) { "Bạn hãy nhập tên sách." }
        require(choices.title.codePointCount(0, choices.title.length) <= BookEdits.TITLE_MAX) { "Tên quá dài. Bạn hãy dùng tối đa ${BookEdits.TITLE_MAX} ký tự." }
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

    override suspend fun replace(item: ImportItem): PreparedImport = withContext(Dispatchers.IO) {
        val result = BookFileImport.import(context, Uri.parse(item.source), allowOlder = true)
        PreparedImport(null, item.name, bookId = result.id, notice = "Đã thêm “${result.title}”")
    }

    private fun name(uri: Uri): String? {
        // ACTION_VIEW accepts file: as well as content:. A file URI has no document-provider display name.
        if (uri.scheme == "file") return uri.path?.let { File(it).name }
        return context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use {
            if (it.moveToFirst()) it.getString(0) else null
        } ?: uri.lastPathSegment
    }

    private fun stageFolder(tree: Uri): TextImports.Staged {
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
        return TextImports.stageFolder(name(DocumentsContract.buildDocumentUriUsingTree(tree, id)) ?: "File đã chọn", files)
    }

    private fun readPdf(file: File): List<List<String>> {
        check(Build.VERSION.SDK_INT >= 35) { "Máy này chưa lấy chữ PDF trực tiếp được. Bạn hãy chọn EPUB, DOCX hoặc TXT." }
        return pdfText(file)
    }

    @android.annotation.TargetApi(35)
    private fun pdfText(file: File): List<List<String>> =
        PdfRenderer(ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)).use { pdf ->
            require(pdf.pageCount <= 5000) { "PDF quá nhiều trang. Bạn hãy chia file rồi thử lại." }
            var chars = 0L
            (0 until pdf.pageCount).map { index ->
                pdf.openPage(index).use { page ->
                    page.textContents.flatMap { it.text.lines() }.also { lines ->
                        chars += lines.sumOf { it.length.toLong() }
                        require(chars <= 16L * 1024 * 1024) { "PDF có quá nhiều chữ. Bạn hãy chia file rồi thử lại." }
                    }
                }
            }
        }
}
