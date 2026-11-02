package vn.abook.player.ui.data

/**
 * Thư viện giả CHỈ cho đo đạc và ảnh chụp: extra `abook.demo.books` của NativeActivity (đo đạc) và test.
 * Có bộ nhiều tập, sách chỉ-chữ, sách trên máy tính, cuốn đang nghe dở, cuốn đã xong - đủ mọi dáng của lưới. Cố định theo chỉ số: cùng số sách, cùng ảnh.
 */
object DemoLibrary {
    private val bases = arrayOf("Tắt đèn", "Chí Phèo", "Đêm trắng", "Dế Mèn phiêu lưu ký", "Nhật ký trong tù", "Số đỏ", "Truyện Kiều", "Lão Hạc", "Cánh đồng bất tận")
    private val authors = arrayOf("Ngô Tất Tố", "Nam Cao", "Dostoevsky", "Tô Hoài", "Hồ Chí Minh", "Vũ Trọng Phụng", "Nguyễn Du", "Nguyễn Huy Thiệp", "")

    fun books(count: Int): List<ListenBook> {
        val list = ArrayList<ListenBook>(count)
        var index = 0
        while (list.size < count) {
            val base = bases[index % bases.size]
            // Cứ mười ba cuốn có một bộ ba tập: ba bìa gom thành một.
            if (index % 13 == 4 && list.size + 3 <= count) {
                val name = "$base ${index / bases.size + 1}"
                for (volume in 1..3) list += book(list.size, "$name · Tập $volume", authors[index % authors.size])
            } else {
                list += book(list.size, "$base ${index + 1}", authors[index % authors.size])
            }
            index++
        }
        return list
    }

    /** Số chương của mỗi cuốn giả: trang sách của bản thử ([DemoBookSource]) liệt kê đủ chừng này chương. */
    private const val CHAPTERS = 12

    /** Chương của cuốn giả: 12 chương cùng dài, ["Chương i"]. Sách chỉ-chữ: chương chỉ có chữ, độ dài chưa biết. */
    private fun chapterInfos(n: Int, duration: Double): List<ChapterInfo> {
        val textOnly = n % 11 == 8
        return (1..CHAPTERS).map { ChapterInfo(it, "Chương $it", if (textOnly) 0.0 else duration / CHAPTERS, available = !textOnly, textOnly = textOnly) }
    }

    private fun book(n: Int, title: String, author: String): ListenBook {
        val duration = 3600.0 * (2 + n % 9)
        val kind = n % 7
        val share = when (kind) {
            1 -> 0.35
            3 -> 0.8
            5 -> 1.0
            else -> 0.0
        }
        val chapters = chapterInfos(n, duration)
        val each = duration / CHAPTERS
        // Nghe dở tới `share` của cả cuốn: các chương trước đã xong, chương đang nghe dừng giữa chừng; cuốn đã xong dừng ở đuôi chương cuối (cách cuối 5 giây).
        val reached = (share * CHAPTERS).coerceAtMost(CHAPTERS.toDouble())
        val chapterAt = if (share >= 1.0) CHAPTERS else (reached.toInt() + 1)
        val inside = if (share >= 1.0) each - 5 else ((reached - reached.toInt()) * each).coerceAtMost(each - 60).coerceAtLeast(0.0)
        val last = if (share > 0) Last(chapterAt, inside, 1_760_000_000.0 - n * 3600.0) else null
        val records = if (share > 0) chapters.filter { it.id < chapterAt || share >= 1.0 }.associate { it.id to ChapterRecord(each, true) } +
            (if (share < 1.0) mapOf(chapterAt to ChapterRecord(inside, false)) else emptyMap()) else emptyMap()
        val state = ListenState(last = last, chapters = records, updatedAt = last?.at)
        val progress = ListenLogic.bookProgress(state, chapters, complete = true)
        return ListenBook(
            id = "demo-$n",
            title = title,
            author = author,
            duration = duration,
            chaptersTotal = CHAPTERS,
            chaptersAvailable = CHAPTERS,
            textOnly = n % 11 == 8,
            addedAt = 1_750_000_000.0 + n * 86_400.0,
            updatedAt = last?.at,
            state = state,
            progress = progress,
            resume = ListenLogic.resumePoint(state, true, chapters),
            lastChapterTitle = if (last != null) "Chương $chapterAt" else "",
            remote = if (n % 9 == 6) RemoteRef("máy tính") else null,
        )
    }

    /**
     * Trang sách của một cuốn giả: đủ [CHAPTERS] chương (đã nghe / đang nghe / chưa nghe theo đúng trạng thái của cuốn) và vài lượt nghe cho tab Lịch sử.
     * Bản thử không có kho, nên không có nó thì trang sách ở bản thử trống: chương không hiện, Tìm / Từ đầu mờ, Lịch sử chờ mãi.
     */
    fun detail(book: ListenBook): BookDetail {
        val n = book.id.removePrefix("demo-").toIntOrNull() ?: 0
        val infos = chapterInfos(n, book.duration)
        val lines = infos.map { info ->
            val heard = ListenLogic.chapterHeard(book.state, info)
            ChapterLine(
                id = info.id, title = info.title, duration = info.duration, available = info.available, textOnly = info.textOnly,
                heard = heard, done = heard >= 1f, textPath = if (info.textOnly) "texts/${info.id}.txt" else "",
                resumeAt = if (heard > 0f && heard < 1f) book.state.chapters[info.id]?.heard ?: 0.0 else 0.0, shortTitle = info.title,
            )
        }
        val last = book.state.last
        val sessions = if (last == null) emptyList() else listOf(
            ListenSession("demo-$n-a", last.at - 5400.0, last.at - 3600.0, 1800.0, 1, 0.0, maxOf(1, last.chapterId - 1), 600.0),
            ListenSession("demo-$n-b", last.at - 1800.0, last.at, 1500.0, maxOf(1, last.chapterId - 1), 600.0, last.chapterId, last.seconds),
        )
        return BookDetail(book, lines, sessions = sessions)
    }
}

/** [BookSource] của bản thử (`abook.demo.books`): trang sách đọc từ chính cuốn giả của Thư viện, mọi việc ghi không làm gì ([BookSource.None]). */
class DemoBookSource(private val books: () -> List<ListenBook>) : BookSource by BookSource.None {
    override suspend fun detail(id: String): BookDetail? = books().firstOrNull { it.id == id }?.let(DemoLibrary::detail)
}
