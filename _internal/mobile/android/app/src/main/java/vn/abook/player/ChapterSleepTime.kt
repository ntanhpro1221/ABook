package vn.abook.player

/** Phần đồng hồ chương tách khỏi trình phát để kiểm trên JVM, không cần Handler/ExoPlayer. */
internal object ChapterSleepTime {
    // Cùng player.tsx: thời lượng audio chia tốc độ thành thời gian nghe thực, sàn tốc độ 0,25.
    fun remainingMs(duration: Long, position: Long, speed: Double): Long =
        ((duration - position).coerceAtLeast(0L) / maxOf(0.25, speed)).toLong()
}
