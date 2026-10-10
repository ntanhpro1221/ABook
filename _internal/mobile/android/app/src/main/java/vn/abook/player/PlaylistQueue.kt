package vn.abook.player

/**
 * Hàng bài của danh sách phát trên đồng hồ nhạc ("Nghe ngay"; phần dữ liệu của MusicBed, thử được trên JVM): cả hàng bài, trừ bài đang
 * bị bỏ tạm trong [failures] (tải hỏng lúc mất mạng: 5, 10, 20 phút). Bài bị bỏ rút khỏi hàng ngay - bài sau dồn lên thay vì im lặng
 * suốt khoảng của nó; bài tới hạn thử lại về hàng ở CHỖ ĐỔI BÀI, không giữa bài (nhạc không nhảy).
 */
class PlaylistQueue(private val failures: MusicFailures) {
    /** Cả hàng bài của danh sách, kể cả bài đang bị bỏ tạm. */
    var tracks: List<Playlists.Track> = emptyList()
        private set

    /** Các bài trên đồng hồ nhạc: hàng bài trừ bài đang bị bỏ tạm. */
    var spans: List<Playlists.Span> = emptyList()
        private set

    /** Mốc (chỉ số trong [spans]) của bài đang kêu; -1 = chưa có bài nào kêu. */
    var currentSpan = -1

    fun load(tracks: List<Playlists.Track>) {
        this.tracks = tracks
        spans = Playlists.timeline(tracks.filter { !failures.isFailed(it.link) })
        currentSpan = -1
        lastOffset = -1.0
    }

    fun clear() = load(emptyList())

    /** Bài `link` vừa bị bỏ (đã ghi vào [failures]): rút khỏi hàng. `playing`: bài đang kêu, để [currentSpan] theo chỉ số mới. */
    fun drop(link: String, playing: String?) {
        if (spans.none { it.track.link == link }) return
        rebuild(playing)
    }

    /** Bài ở giây `seconds` của đồng hồ nhạc + giây trong bài ấy (null = không bài nào). Ở chỗ đổi bài, bài bỏ tạm đã tới hạn về hàng trước.
     *  Chỗ đổi bài gồm cả lúc hàng rỗng (mọi bài tải hỏng khi mở sách lúc mất mạng) và lúc bài duy nhất còn lại quay về đầu: không tính
     *  hai lúc ấy thì bài bỏ tạm không bao giờ về - im lặng / lặp một bài tới khi mở lại cuốn. */
    fun at(seconds: Double, playing: String?): Pair<Playlists.Span, Double>? {
        val found = Playlists.at(spans, seconds)
        val lapped = found != null && found.first.index == currentSpan && found.second < lastOffset
        val changing = found == null || found.first.index != currentSpan || lapped
        val result = if (changing && retryDue(playing)) Playlists.at(spans, seconds) else found
        lastOffset = result?.second ?: -1.0
        return result
    }

    // Giây trong bài ở lần [at] trước: lùi lại trong cùng một mốc = bài đã quay về đầu (đồng hồ nhạc chỉ đi tới).
    private var lastOffset = -1.0

    /** Bỏ các bài đã hết hạn chờ khỏi danh sách hỏng; true nếu vì thế hàng bài đổi. */
    private fun retryDue(playing: String?): Boolean {
        val due = failures.takeDue()
        if (due.isEmpty() || tracks.none { it.link in due }) return false
        rebuild(playing)
        return true
    }

    private fun rebuild(playing: String?) {
        spans = Playlists.timeline(tracks.filter { !failures.isFailed(it.link) })
        currentSpan = spans.firstOrNull { it.track.link == playing }?.index ?: -1
    }
}
