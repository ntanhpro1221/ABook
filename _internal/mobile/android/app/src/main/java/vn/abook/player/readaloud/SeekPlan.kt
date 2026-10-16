package vn.abook.player.readaloud

/**
 * Tua trong chương đọc to, phần quyết định (thuần tính toán, SeekPlanTest): tua tới `ms` của chương hay tới chữ `word` của đoạn `segment` (`segment`/`word` thắng `ms`)
 * thì (a) nhảy thẳng trong hàng đợi tới ĐÚNG chỗ trong đoạn âm thanh đã có, hay (b) phải đọc đoạn ấy trước (trạng thái chờ), rồi mới phát từ chỗ đó.
 *
 * Chỗ được quyết ngay lúc tua, theo đồng hồ ảo LÚC ĐÓ (cùng đồng hồ với `ReadAloud.script`): các đoạn trước đoạn đích có thể còn là ước lượng, nhưng mốc đầu đoạn đích
 * đã chốt thành (đoạn, ms trong đoạn) nên đọc xong đoạn đích mà đồng hồ có co giãn thì người nghe vẫn nghe đúng chỗ đã chạm.
 *
 * Clip ĐUÔI (uxfix57; máy tính: listen/readAloud.ts `fromWord`): bấm chữ `word` > 0 của đoạn chưa đọc mà đoạn sẽ phát luồng ([tailFrom]) thì chỉ đọc từ chữ ấy tới hết đoạn - byte đầu về sớm hơn
 * nhiều so với đọc cả đoạn. Clip đuôi ([Clip.fromWord]) chỉ phục vụ chỗ nghe nằm TRONG nó ([serves]); mọi lần vào đoạn ấy ở chỗ trước chữ `fromWord` (bấm chữ trước đó, tua thanh thời gian về đầu
 * đoạn) bỏ nó và đọc đầy đủ.
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
        val within = if (segment >= 0) 0L else (ms - timeline.startOf(seg)).coerceAtLeast(0)
        val known = clip(seg)?.takeIf { serves(it, word, within) }
        if (known != null && queued(seg)) return Plan.InClip(seg, offsetIn(known, word, within))
        return Plan.Synthesize(seg, within, word)
    }

    /**
     * Clip đuôi (`fromWord` > 0) có phục vụ được chỗ nghe này không? Bấm chữ: chỉ chữ từ `fromWord` trở đi. Tua theo thời gian trong đoạn: mọi chỗ sau đầu đoạn (clip đuôi bắt đầu ở chữ `fromWord`,
     * mốc 0 của đoạn đã là chỗ ấy); đúng đầu đoạn (`withinMs` = 0) là "về đầu đoạn" nên bỏ clip đuôi. Clip đầy đủ phục vụ mọi chỗ.
     */
    fun serves(clip: Clip, word: Int, withinMs: Long): Boolean = clip.fromWord == 0 || (if (word >= 0) word >= clip.fromWord else withinMs > 0)

    /** Chỗ bắt đầu phát trong `clip`: đầu chữ `word` nếu có, không thì `offsetMs`; kẹp vào trong đoạn. */
    fun offsetIn(clip: Clip, word: Int, offsetMs: Long): Long {
        val raw = if (word >= 0) clip.words.getOrNull(word)?.start ?: 0L else offsetMs
        return raw.coerceIn(0L, (clip.durationMs - 1).coerceAtLeast(0))
    }

    /**
     * Chữ bắt đầu clip đuôi khi người nghe bấm chữ `word` của đoạn `text` (chưa có clip): `word` nếu đoạn sẽ phát luồng (`streams`) và đó là một chữ giữa đoạn (1 tới chữ cuối); 0 = đọc cả đoạn.
     * Cách đếm chữ là của [WordTokens] (`\S+`) - cùng với `words` của clip.
     */
    fun tailFrom(word: Int, text: String, streams: Boolean): Int = if (streams && word > 0 && word < WordTokens.count(text)) word else 0

    /** Chuỗi từ chữ thứ `from` tới hết `text` (đúng chữ gửi đi đọc cho clip đuôi; khoá bộ đệm của clip đuôi theo chính chuỗi này). */
    fun tailText(text: String, from: Int): String = text.substring(WordTokens.tokens(text)[from].first)

    /** `words` của đoạn cho clip đuôi: chữ trước `from` mốc [0, 0], rồi mốc của clip đuôi (`tail`: mốc từng chữ của chuỗi [tailText], từ đầu clip đuôi). */
    fun tailWords(from: Int, tail: List<Span>): List<Span> = List(from) { Span(0, 0) } + tail
}
