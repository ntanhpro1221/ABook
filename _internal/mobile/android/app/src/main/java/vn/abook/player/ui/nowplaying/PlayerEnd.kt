package vn.abook.player.ui.nowplaying

import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.ListenLogic

/**
 * Sau khi nghe hết chương cuối (web: PlayerViews `CaughtUpNotice`, `AfterTheEnd`, `useContinueIntoNextPart`; model.ts `continuingPart`, `otherBooksToHear`;
 * labels.ts `otherBookLine`): tập / phần kế của cùng bộ, và vài cuốn khác để mời. Hàm thuần - thử trên JVM (PlayerEndTest).
 */
object PlayerEnd {
    /** Một cuốn được mời: bấm là nghe tiếp từ chỗ đã dừng. `line`: dòng phụ (tiến độ hay độ dài). */
    class Pick(val id: String, val title: String, val line: String)

    /** `next`: tập / phần kế của bộ; `continues`: nó là PHẦN sau của cùng cuốn nên được nghe nối tự động. `others`: cuốn khác để mời. */
    class Choices(val next: Pick? = null, val continues: Boolean = false, val others: List<Pick> = emptyList())

    /** "Tập 17" / "Phần 2" - hay cả tên khi cuốn kế không đánh số. */
    fun nextLabel(title: String): String {
        val place = ListenLogic.seriesOf(title)
        val volume = place.volume ?: return title
        return "${place.unit.replaceFirstChar { it.uppercase() }} $volume"
    }

    /** Tập kế tiếp của cùng bộ trong thư viện (nghe xong Tập 16 thì mời Tập 17; phần đầu của "Làm tiếp cuốn này" mời Phần 2). */
    fun nextVolume(books: List<ListenBook>, bookId: String): ListenBook? {
        val places = ListenLogic.seriesIndex(books)
        val here = places[bookId] ?: return null
        val volume = here.volume ?: return null
        return books.filter { it.id != bookId && it.chaptersAvailable > 0 }
            .mapNotNull { book -> places[book.id]?.takeIf { it.key == here.key && (it.volume ?: 0) > volume }?.let { book to (it.volume ?: 0) } }
            .minByOrNull { it.second }?.first
    }

    /** Cuốn kế là PHẦN sau của cùng cuốn (có liên kết chuỗi, hay tên hậu tố "Phần N"): hết phần này là nghe nối sang nó. Tập khác của một bộ chỉ được mời. */
    fun continuingPart(next: ListenBook?): ListenBook? = next?.takeIf { it.series != null || ListenLogic.seriesOf(it.title).unit == "phần" }

    /** Cuốn khác để mời (tối đa `limit`): chưa nghe xong, nghe được ngay (có audio, hay chỉ có chữ mà máy có giọng đọc); đang nghe dở trước, mới nhất trước. */
    fun others(books: List<ListenBook>, currentId: String, speaks: Boolean, skipId: String? = null, limit: Int = 3): List<ListenBook> {
        val open = books.filter { book ->
            book.id != currentId && book.id != skipId && !book.progress.finished && !book.progress.caughtUp &&
                if (book.textOnly) speaks && book.chaptersTotal > 0 else book.chaptersAvailable > 0
        }
        val listening = open.filter { it.state.last != null }.sortedByDescending { it.state.last?.at ?: 0.0 }
        return (listening + open.filter { it.state.last == null }).take(limit)
    }

    /** Dòng dưới tên một cuốn được mời: đã nghe dở thì tiến độ (cùng lời với Đang nghe), chưa nghe thì độ dài. */
    fun line(book: ListenBook): String {
        val heard = book.progress.heardSeconds
        val total = book.progress.totalSeconds
        if (heard > 0 && total > 0) return PlayerText.bookProgress(book.complete, minOf(heard, total), total, 1.0, finished = false)
        return if (book.duration > 0) "Chưa nghe · ${Fmt.length(book.duration)}" else "Chưa nghe · ${book.chaptersTotal} chương"
    }

    fun choices(books: List<ListenBook>, currentId: String, speaks: Boolean): Choices {
        val next = nextVolume(books, currentId)
        fun pick(book: ListenBook) = Pick(book.id, book.title, line(book))
        return Choices(next?.let(::pick), continuingPart(next) != null, others(books, currentId, speaks, next?.id).map(::pick))
    }
}
