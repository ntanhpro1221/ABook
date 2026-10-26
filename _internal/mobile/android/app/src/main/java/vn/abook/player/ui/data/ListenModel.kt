package vn.abook.player.ui.data

import androidx.compose.runtime.Immutable

/*
 * Mô hình dữ liệu phía NGHE của giao diện native - viết lại bằng Kotlin từ ui/src/listen/model.ts, ui/src/android/progress.ts và
 * ui/src/android/androidSource.ts (toListenBook), mang theo ca test của chúng (ListenModelTest). Mọi lớp bất biến; không Android, không Compose
 * ngoài chú thích @Immutable - thử được trên JVM.
 */

/** Phiên bản của một lần ghi chỗ nghe (ListeningRevision.kt / readingPosition.ts): đủ để so "ai mới hơn". */
@Immutable
data class Rev(val counter: Long, val node: String, val epoch: String? = null)

/** Chỗ nghe cuối đã lưu. `at` = giây Unix. */
@Immutable
data class Last(val chapterId: Int, val seconds: Double, val at: Double, val rev: Rev? = null)

@Immutable
data class ChapterRecord(val heard: Double, val done: Boolean, val duration: Double? = null)

/** Trạng thái nghe của hồ sơ đang dùng (Store.state). */
@Immutable
class ListenState(
    val last: Last? = null,
    val chapters: Map<Int, ChapterRecord> = emptyMap(),
    val rate: Double? = null,
    val finished: Boolean = false,
    val finishedAt: Double? = null,
    val finishedRev: Rev? = null,
    val updatedAt: Double? = null,
) {

    companion object {
        val Empty = ListenState()
    }
}

/** Một chương nghe được: có audio, hay chỉ có chữ (giọng máy đọc to). */
@Immutable
data class ChapterInfo(val id: Int, val title: String, val duration: Double, val available: Boolean, val textOnly: Boolean = false) {
    /** Bấm nghe được: chương có audio, hay chương chỉ có chữ (lõi native luôn đọc to được). */
    val playable: Boolean get() = available || textOnly
}

/** Chỗ nghe tiếp: chương + giây. */
@Immutable
data class ResumeSpot(val chapterId: Int, val chapterTitle: String, val at: Double)

@Immutable
data class Progress(
    val heardSeconds: Double,
    val totalSeconds: Double,
    val fraction: Float,
    val chaptersDone: Int,
    val finished: Boolean,
    /** Sách đang làm dở, đã nghe hết phần đã có - chưa phải "nghe xong". */
    val caughtUp: Boolean = false,
    /** Đã nghe hết rồi quay lại nghe một đoạn: tiến độ theo chỗ đang nghe. */
    val rewound: Boolean = false,
) {

    companion object {
        val None = Progress(0.0, 0.0, 0f, 0, finished = false)
    }
}

/** Phần nối tiếp của "Làm tiếp cuốn này": mã phần đầu + thứ tự phần. */
@Immutable
data class SeriesLink(val root: String, val part: Int)

/** Ảnh bìa thật của cuốn: file trên máy + dấu thời gian (đổi bìa thì khoá bộ nhớ đệm đổi). */
@Immutable
data class CoverRef(val path: String, val stamp: Long)

/** Cuốn nằm ở máy khác (nghe thẳng, chưa tải): `deviceName` = "máy tính" hay tên thiết bị ghép. */
@Immutable
data class RemoteRef(val deviceName: String)

/**
 * Một cuốn trong Thư viện - đúng phần màn vẽ và lọc/xếp. Tiến độ + chỗ nghe tiếp tính sẵn lúc đọc (luồng nền), nên cuộn lưới không tính gì.
 */
@Immutable
class ListenBook(
    override val id: String,
    override val title: String,
    val author: String = "",
    val narrator: String = "",
    val duration: Double = 0.0,
    val chaptersTotal: Int = 0,
    val chaptersAvailable: Int = 0,
    val complete: Boolean = true,
    /** Sách chỉ có chữ (chưa chương nào có audio): giọng máy đọc. */
    val textOnly: Boolean = false,
    val updatedAt: Double? = null,
    val addedAt: Double? = null,
    val state: ListenState = ListenState.Empty,
    val progress: Progress = Progress.None,
    val resume: ResumeSpot? = null,
    val lastChapterTitle: String = "",
    val cover: CoverRef? = null,
    override val series: SeriesLink? = null,
    val remote: RemoteRef? = null,
    /** Số phần/tập thật của file cả bộ (BookCover nhãn "Phần 2"). */
    val part: Int? = null,
) : SeriesItem {
    override val isText: Boolean get() = textOnly

    /** Chuỗi tìm kiếm đã bỏ dấu (tên, tác giả, giọng kể) - tính một lần, gõ từng chữ chỉ còn `contains`. */
    val haystack: String by lazy(LazyThreadSafetyMode.PUBLICATION) { ListenLogic.fold("$title $author $narrator") }

    /** Chỉ lưu trong bộ nhớ app: so hai cuốn bằng nội dung hiển thị (mã + mốc cập nhật + tiến độ). */
    override fun equals(other: Any?): Boolean = other is ListenBook && other.id == id && other.title == title && other.author == author &&
        other.updatedAt == updatedAt && other.progress == progress && other.cover == cover && other.state.last == state.last &&
        other.resume == resume && other.remote == remote && other.chaptersAvailable == chaptersAvailable && other.series == series

    override fun hashCode(): Int = id.hashCode() * 31 + (state.last?.hashCode() ?: 0)
}
