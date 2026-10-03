package vn.abook.player.readaloud

/**
 * Bấm Phát khi ExoPlayer đã chạy hết hàng đợi đọc to, phần quyết định (thuần tính toán, EndPlanTest): phát lại từ đâu.
 *
 * Chương cuối của cuốn vừa đọc xong: Phát ở màn hình khoá / thông báo làm như nút "Nghe lại" trong app (BookScreen.restart) - về chương đầu, từ đầu.
 * Trước đây đọc lại "từ chỗ đang đứng", mà chỗ đứng khi hết hàng đợi là CUỐI đoạn cuối: lần bấm đầu phát vào đúng cái đuôi ấy rồi hết ngay (không thấy gì xảy ra),
 * lần hai rơi giữa đoạn cuối vì đồng hồ ảo vừa được co giãn theo độ dài thật (soát máy thật 03-10).
 * Hàng đợi cạn giữa cuốn (đọc chậm hơn nghe) - kể cả giữa chương cuối - thì vẫn đọc lại từ chỗ đang đứng: "hết cuốn" là chương cuối VÀ đứng trong
 * [END_SLACK_MS] cuối chương.
 */
object EndPlan {
    class Spot(val chapterIndex: Int, val offsetMs: Long)

    const val END_SLACK_MS = 2_000L

    fun restartSpot(chapterIndex: Int, chapterCount: Int, positionMs: Long, durationMs: Long): Spot =
        if (chapterIndex >= chapterCount - 1 && positionMs >= durationMs - END_SLACK_MS) Spot(0, 0L) else Spot(chapterIndex, positionMs)
}
