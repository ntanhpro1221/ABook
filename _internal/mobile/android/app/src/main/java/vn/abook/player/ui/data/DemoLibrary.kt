package vn.abook.player.ui.data

import vn.abook.player.S

/**
 * Thư viện giả CHỈ cho đo đạc và ảnh chụp: extra `abook.demo.books` của NativeActivity (đo đạc) và test.
 * Có bộ nhiều tập, sách chỉ-chữ, sách trên máy tính, cuốn đang nghe dở, cuốn đã xong - đủ mọi dáng của lưới. Cố định theo chỉ số: cùng số sách, cùng ảnh.
 */
object DemoLibrary {
    private val bases = arrayOf(S.s_tat_den_e8abef9d, S.s_chi_pheo_92401a7e, S.s_dem_trang_aedad6e4, S.s_de_men_phieu_luu_ky_4e0a5b60, S.s_nhat_ky_trong_tu_da8fe5b2, S.s_so_do_8c497a89, S.s_truyen_kieu_1a35c271, S.s_lao_hac_042cebe1, S.s_canh_dong_bat_tan_d273c661)
    private val authors = arrayOf(S.s_ngo_tat_to_354f581c, "Nam Cao", "Dostoevsky", S.s_to_hoai_5ed4f544, S.s_ho_chi_minh_d8678887, S.s_vu_trong_phung_b3c8fd0d, S.s_nguyen_du_34215116, S.s_nguyen_huy_thiep_58945098, "")

    fun books(count: Int): List<ListenBook> {
        val list = ArrayList<ListenBook>(count)
        var index = 0
        while (list.size < count) {
            val base = bases[index % bases.size]
            // Cứ mười ba cuốn có một bộ ba tập: ba bìa gom thành một.
            if (index % 13 == 4 && list.size + 3 <= count) {
                val name = "$base ${index / bases.size + 1}"
                for (volume in 1..3) list += book(list.size, S.s_0_tap_1_c13c39ff(name, volume), authors[index % authors.size])
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
        return (1..CHAPTERS).map { ChapterInfo(it, S.s_chuong_0_268b0521(it), if (textOnly) 0.0 else duration / CHAPTERS, available = !textOnly, textOnly = textOnly) }
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
            lastChapterTitle = if (last != null) S.s_chuong_0_268b0521(chapterAt) else "",
            remote = if (n % 9 == 6) RemoteRef(S.s_may_tinh_8eafc226) else null,
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
