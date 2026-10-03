package vn.abook.player.readaloud

/**
 * Tua trong chương đọc to, phần quyết định (thuần tính toán, SeekPlanTest): tua tới `ms` của chương hay tới chữ `word` của đoạn `segment` (`segment`/`word` thắng `ms`)
 * thì (a) nhảy thẳng trong hàng đợi tới ĐÚNG chỗ trong đoạn âm thanh đã có, hay (b) phải đọc đoạn ấy trước (trạng thái chờ), rồi mới phát từ chỗ đó.
 *
 * Chỗ được quyết ngay lúc tua, theo đồng hồ ảo LÚC ĐÓ (cùng đồng hồ với `ReadAloud.script`): các đoạn trước đoạn đích có thể còn là ước lượng, nhưng mốc đầu đoạn đích
 * đã chốt thành (đoạn, ms trong đoạn) nên đọc xong đoạn đích mà đồng hồ có co giãn thì người nghe vẫn nghe đúng chỗ đã chạm.
 */
object SeekPlan {
    sealed class Plan {
        /** Đoạn có âm thanh và đang nằm trong hàng đợi: `exo.seekTo(đoạn đó, positionMs)`. */
        class InClip(val segment: Int, val positionMs: Long) : Plan()
        /** Phải đọc đoạn `segment` trước; xong thì phát từ [offsetIn] (`word` >= 0 thắng `offsetMs`). */
        class Synthesize(val segment: Int, val offsetMs: Long, val word: Int) : Plan()
    }

    fun plan(timeline: VirtualTimeline, clip: (Int) -> Clip?, queued: (Int) -> Boolean, ms: Long, segment: Int, word: Int): Plan {
        val last = (timeline.size - 1).coerceAtLeast(0)
        val seg = if (segment >= 0) segment.coerceIn(0, last) else timeline.segmentAt(ms)
        val known = clip(seg)
        val within = if (segment >= 0) 0L else (ms - timeline.startOf(seg)).coerceAtLeast(0)
        if (known != null && queued(seg)) return Plan.InClip(seg, offsetIn(known, word, within))
        return Plan.Synthesize(seg, within, word)
    }

    /** Chỗ bắt đầu phát trong `clip`: đầu chữ `word` nếu có, không thì `offsetMs`; kẹp vào trong đoạn. */
    fun offsetIn(clip: Clip, word: Int, offsetMs: Long): Long {
        val raw = if (word >= 0) clip.words.getOrNull(word)?.start ?: 0L else offsetMs
        return raw.coerceIn(0L, (clip.durationMs - 1).coerceAtLeast(0))
    }
}
