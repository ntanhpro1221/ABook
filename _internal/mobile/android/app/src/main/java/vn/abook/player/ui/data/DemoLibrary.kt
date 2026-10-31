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

    private fun book(n: Int, title: String, author: String): ListenBook {
        val duration = 3600.0 * (2 + n % 9)
        val kind = n % 7
        val heard = when (kind) {
            1 -> duration * 0.35
            3 -> duration * 0.8
            5 -> duration
            else -> 0.0
        }
        val chapter = ChapterInfo(1, "Chương ${1 + n % 12}", duration, available = true)
        // Cuốn đã xong dừng ở đuôi chương cuối (cách cuối 5 giây); cuốn nghe dở dừng giữa chừng.
        val stop = if (kind == 5) duration - 5 else heard.coerceAtMost(duration - 60)
        val last = if (heard > 0) Last(1, stop, 1_760_000_000.0 - n * 3600.0) else null
        val state = ListenState(last = last, chapters = if (kind == 5) mapOf(1 to ChapterRecord(duration, true)) else emptyMap(), updatedAt = last?.at)
        val progress = ListenLogic.bookProgress(state, listOf(chapter), complete = true)
        return ListenBook(
            id = "demo-$n",
            title = title,
            author = author,
            duration = duration,
            chaptersTotal = 12,
            chaptersAvailable = 12,
            textOnly = n % 11 == 8,
            addedAt = 1_750_000_000.0 + n * 86_400.0,
            updatedAt = last?.at,
            state = state,
            progress = progress,
            resume = ListenLogic.resumePoint(state, true, listOf(chapter)),
            lastChapterTitle = if (last != null) chapter.title else "",
            remote = if (n % 9 == 6) RemoteRef("máy tính") else null,
        )
    }
}
