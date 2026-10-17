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
     * mốc 0 của đoạn đã là chỗ ấy); đúng đầu đoạn (`withinMs` = 0) là "về đầu đoạn" nên bỏ clip đuôi. Clip đầy đủ phục vụ mọi chỗ. Clip nối sau phần đã về ([Clip.baseMs] > 0) chỉ phục vụ chỗ từ `baseMs`
     * trở đi: phần trước đó đã phát xong ở mục ExoPlayer khác (và không còn file nào giữ nó).
     */
    fun serves(clip: Clip, word: Int, withinMs: Long): Boolean {
        val tailOk = clip.fromWord == 0 || (if (word >= 0) word >= clip.fromWord else withinMs > 0)
        val baseOk = clip.baseMs == 0L || (if (word >= 0) (clip.words.getOrNull(word)?.start ?: 0L) else withinMs) >= clip.baseMs
        return tailOk && baseOk
    }

    /** Chỗ bắt đầu phát trong file của `clip`: đầu chữ `word` nếu có, không thì `offsetMs`; tính từ đầu file ([Clip.baseMs] trừ đi) và kẹp vào trong file. */
    fun offsetIn(clip: Clip, word: Int, offsetMs: Long): Long {
        val raw = if (word >= 0) clip.words.getOrNull(word)?.start ?: 0L else offsetMs
        return (raw - clip.baseMs).coerceIn(0L, (clip.durationMs - clip.baseMs - 1).coerceAtLeast(0))
    }

    /**
     * Chữ bắt đầu clip đuôi khi người nghe bấm chữ `word` của đoạn `text` (chưa có clip): `word` nếu đoạn sẽ phát luồng (`streams`) và đó là một chữ giữa đoạn (1 tới chữ cuối); 0 = đọc cả đoạn.
     * Cách đếm chữ là của [WordTokens] (`\S+`) - cùng với `words` của clip.
     */
    fun tailFrom(word: Int, text: String, streams: Boolean): Int = if (streams && word > 0 && word < WordTokens.count(text)) word else 0

    /** Chuỗi từ chữ thứ `from` tới hết `text` (đúng chữ gửi đi đọc cho clip đuôi; khoá bộ đệm của clip đuôi theo chính chuỗi này). */
    fun tailText(text: String, from: Int): String = text.substring(WordTokens.tokens(text)[from].first)

    /**
     * `words` của đoạn cho clip đuôi: chữ trước `from` mốc [0, 0], rồi mốc của clip đuôi (`tail`: mốc từng chữ của chuỗi [tailText], từ đầu clip đuôi).
     * Chữ `from` (chữ người nghe bấm) coi như bắt đầu ngay đầu clip dù clip mở đầu bằng quãng lặng (~0,14 giây): không thì trong quãng ấy chữ liền trước (mốc [0, 0]) là "chữ đã bắt đầu cuối cùng" và sáng lóe (a58).
     */
    fun tailWords(from: Int, tail: List<Span>, baseMs: Long = 0L, prefix: List<Span> = emptyList()): List<Span> {
        val shifted = tail.mapIndexed { i, span -> Span(baseMs + if (i == 0) 0L else span.start, baseMs + span.end) }
        // `prefix` (uxfix58): mốc các chữ đã nghe của phần đã về, trên cùng đồng hồ; thiếu thì [0, 0]. Clip nối bắt đầu ở `baseMs` của đoạn.
        val head = prefix.take(from) + List((from - prefix.size).coerceAtLeast(0)) { Span(0, 0) }
        return head + shifted
    }

    /**
     * Clip phát luồng đứt giữa chừng (uxfix58; máy tính: listen/readAloud.ts `firstUnheard`): chữ đầu tiên từ `first` trở đi mà người nghe CHƯA nghe hết - chữ kết thúc sau chỗ đã nghe tới (`heardMs`: hết mốc thật
     * cuối cùng, và không quá phần âm thanh đã về), hay bắt đầu từ đó (chữ chưa tới bị dồn vào cuối âm thanh đã có nên có thể rộng 0 - [WordTokens.map]). Chưa có mốc nào: chữ `first` (đầu clip); nghe hết rồi mà
     * clip vẫn đứt: nhắc lại chữ cuối, không bỏ trống. Chữ trước `first` (mốc [0, 0] của clip đuôi) không bao giờ được chọn.
     */
    fun resumeWord(words: List<Span>, heardMs: Long, first: Int): Int {
        if (words.size <= first) return first
        for (i in first until words.size) if (words[i].end > heardMs || words[i].start >= heardMs) return i
        return words.size - 1
    }
}
