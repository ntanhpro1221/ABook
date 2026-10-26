package vn.abook.player.ui.data

import androidx.compose.runtime.Immutable
import java.math.BigInteger

/** Bộ lọc của hàng chữ có gạch chân hổ phách (DESIGN.md §6): thứ tự là thứ tự trượt. */
enum class LibraryFilter(val label: String, val tag: String) {
    All("Tất cả", "filter_all"),
    Listening("Nghe dở", "filter_listening"),
    New("Chưa nghe", "filter_new"),
    Finished("Xong", "filter_finished"),
}

/** Cách xếp (librarySort.ts): mặc định "Nghe gần đây". */
enum class LibrarySort(val label: String) {
    Recent("Nghe gần đây"),
    Title("Tên sách"),
    Author("Tác giả"),
    Added("Mới thêm"),
}

/** Một ô của lưới: cuốn lẻ, hay MỘT bìa cho cả bộ nhiều tập (chạm mở bộ). `key` ổn định cho LazyGrid. */
@Immutable
sealed interface ShelfTile {
    val key: String

    @Immutable
    class Single(val book: ListenBook, val badge: String?, val twin: Boolean) : ShelfTile {
        override val key: String get() = "book:${book.id}"
    }

    /** `books` đã xếp theo số tập; bìa bộ = bìa cuốn đầu. */
    @Immutable
    class Series(override val key: String, val label: String, val unit: String, val books: List<ListenBook>, val badges: Map<String, String>) : ShelfTile {
        val first: ListenBook get() = books[0]
        val hasRemote: Boolean get() = books.any { it.remote != null }

        /** Tập phát khi giữ bìa bộ: tập nghe dở gần nhất, không thì tập đầu chưa nghe xong, không nữa thì tập đầu. */
        val playTarget: ListenBook
            get() = books.filter { it.state.last != null && !it.progress.finished }.maxByOrNull { it.state.last!!.at }
                ?: books.firstOrNull { !it.progress.finished } ?: books[0]
    }
}

/** Kết quả đã lọc + xếp + gom bộ: cái màn Thư viện vẽ. */
@Immutable
class LibraryView(
    val tiles: List<ShelfTile>,
    /** Số cuốn khớp bộ lọc + ô tìm, và số cuốn cả thư viện. */
    val shown: Int,
    val total: Int,
) {
    companion object {
        val Empty = LibraryView(emptyList(), 0, 0)
    }
}

/** Lọc, xếp, gom bộ - hàm thuần (librarySort.ts, LibraryScreen.tsx `stateOf` / `librarySections`). */
object Library {
    fun stateOf(book: ListenBook): LibraryFilter = when {
        book.progress.finished -> LibraryFilter.Finished
        book.progress.heardSeconds > 0 || book.state.last != null -> LibraryFilter.Listening
        else -> LibraryFilter.New
    }

    /** "Nghe gần đây" của nguồn tự gộp nhiều chỗ: lần nghe cuối mới nhất đứng đầu, cùng mốc thì lần cập nhật cuối, rồi giữ thứ tự nhận vào. */
    fun recentFirst(books: List<ListenBook>): List<ListenBook> =
        books.sortedWith(compareByDescending<ListenBook> { it.state.last?.at ?: 0.0 }.thenByDescending { it.updatedAt ?: 0.0 })

    /** So tên theo tiếng Việt: bỏ dấu khi so, "Tập 2" đứng trước "Tập 10". */
    fun compareNames(a: String, b: String): Int = natural(ListenLogic.fold(a), ListenLogic.fold(b))

    private fun natural(a: String, b: String): Int {
        var i = 0
        var j = 0
        while (i < a.length && j < b.length) {
            val ca = a[i]
            val cb = b[j]
            if (ca.isDigit() && cb.isDigit()) {
                var ei = i
                while (ei < a.length && a[ei].isDigit()) ei++
                var ej = j
                while (ej < b.length && b[ej].isDigit()) ej++
                val cmp = BigInteger(a.substring(i, ei)).compareTo(BigInteger(b.substring(j, ej)))
                if (cmp != 0) return cmp
                i = ei
                j = ej
            } else {
                if (ca != cb) return ca.compareTo(cb)
                i++
                j++
            }
        }
        return (a.length - i).compareTo(b.length - j)
    }

    /**
     * Xếp sách theo `sort`. "Nghe gần đây" giữ nguyên thứ tự nhận vào (nguồn đã xếp). Các kiểu khác ổn định: cùng khoá giữ thứ tự cũ; sách không
     * tác giả đứng sau, theo tên. "Mới thêm": cuốn vừa vào lên đầu (không có mốc thì lần cập nhật cuối, không có nữa thì cuối).
     */
    fun sort(books: List<ListenBook>, sort: LibrarySort): List<ListenBook> = when (sort) {
        LibrarySort.Recent -> books
        LibrarySort.Title -> books.sortedWith { a, b -> compareNames(a.title, b.title) }
        LibrarySort.Author -> books.sortedWith { a, b ->
            val left = a.author.trim()
            val right = b.author.trim()
            when {
                left.isEmpty() != right.isEmpty() -> if (left.isNotEmpty()) -1 else 1
                else -> compareNames(left, right).takeIf { it != 0 } ?: compareNames(a.title, b.title)
            }
        }
        LibrarySort.Added -> books.sortedByDescending { it.addedAt ?: it.updatedAt ?: 0.0 }
    }

    /** Gom theo bộ nhưng giữ vị trí của cuốn đầu tiên trong thứ tự đang chọn; bộ một cuốn hiện như cuốn lẻ. */
    fun tiles(books: List<ListenBook>, twins: Set<String>): List<ShelfTile> {
        val places = ListenLogic.seriesIndex(books)
        val groups = LinkedHashMap<String, MutableList<ListenBook>>()
        for (book in books) {
            val place = places.getValue(book.id)
            val key = if (place.volume != null) place.key else "book:${book.id}"
            groups.getOrPut(key) { ArrayList() }.add(book)
        }
        return groups.map { (key, members) ->
            val items = members.sortedBy { places.getValue(it.id).volume ?: 0 }
            val badges = HashMap<String, String>()
            for (book in items) {
                val place = places.getValue(book.id)
                ListenLogic.volumeBadge(book.title, book.series, place.volume, place.unit)?.let { badges[book.id] = it }
            }
            if (items.size > 1) {
                ShelfTile.Series(key, places.getValue(items[0].id).series, places.getValue(items[0].id).unit, items, badges)
            } else {
                ShelfTile.Single(items[0], badges[items[0].id], items[0].id in twins)
            }
        }
    }

    /**
     * Cái màn vẽ: sách chỉ có chữ hay nghe được vào lưới; lọc theo bộ lọc + ô tìm (không dấu), xếp, gom bộ.
     */
    fun view(books: List<ListenBook>, filter: LibraryFilter, query: String, sort: LibrarySort): LibraryView {
        val folded = ListenLogic.fold(query.trim())
        val twins = ListenLogic.twinIds(books)
        val shown = sort(
            books.filter { (filter == LibraryFilter.All || stateOf(it) == filter) && ListenLogic.matches(it, folded) },
            sort,
        )
        return LibraryView(tiles(shown, twins), shown.size, books.size)
    }
}
