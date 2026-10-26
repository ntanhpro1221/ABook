package vn.abook.player.ui.data

import java.text.Normalizer
import java.util.Locale

/** Bộ và số tập của một tên sách. `key`: "title:<tên>" (theo tên) hay "chain:<phần đầu>" (chuỗi "Làm tiếp cuốn này"). `unit`: "tập" / "quyển" / "phần". */
data class SeriesPlace(val key: String, val series: String, val volume: Int?, val unit: String)

/** Một phần tử để gom bộ: mã, tên, liên kết chuỗi, và có phải sách chỉ-chữ không. */
interface SeriesItem {
    val id: String
    val title: String
    val series: SeriesLink?
    val isText: Boolean
}

/**
 * Logic thuần của phần Nghe (model.ts + progress.ts): bỏ dấu, tìm, bộ sách, tiến độ, chỗ nghe tiếp.
 * Không Android - thử trên JVM (ListenModelTest, bê ca test của model.test.ts / progress.test.ts).
 */
object ListenLogic {
    /** Còn ít hơn chừng này giây là "nghe gần hết" một chương: nghe tiếp thì sang chương kế. */
    const val NEAR_END_SECONDS = 15.0

    /** Gần đuôi chương bao nhiêu giây thì tính là nghe hết chương (DONE_TAIL_SECONDS của máy tính). */
    const val DONE_TAIL_SECONDS = 20.0

    /** Lệch (giây) từ đó chỗ nghe của thiết bị khác mới là "chỗ khác". */
    const val ELSEWHERE_SECONDS = 30.0

    // ---- tìm không dấu ----------------------------------------------------------------------------------

    /** Tìm không dấu: "tap 16" khớp "Tập 16", "duc tri" khớp "Đức Trí". Vòng lặp thay cho regex (Android ICU, chuỗi dài). */
    fun fold(text: String): String {
        val decomposed = Normalizer.normalize(text, Normalizer.Form.NFD)
        val out = StringBuilder(decomposed.length)
        for (c in decomposed) {
            when {
                c in '̀'..'ͯ' -> Unit
                c == 'đ' || c == 'Đ' -> out.append('d')
                else -> out.append(c.lowercaseChar())
            }
        }
        return out.toString()
    }

    /** Ô "Tìm sách": khớp tên, tác giả hoặc giọng kể; `folded` đã qua [fold] (rỗng = khớp hết). */
    fun matches(book: ListenBook, folded: String): Boolean = folded.isEmpty() || book.haystack.contains(folded)

    // ---- bộ sách ----------------------------------------------------------------------------------------

    private val seriesPattern = Regex("""^(.*?)\s*[·|:—–-]\s*(Tập|Quyển|Phần|Vol\.?|Book)\s*(\d+)\b""", RegexOption.IGNORE_CASE)

    /** Bộ và số tập từ tên sách ("Throne of Magical Arcana · Tập 16" -> bộ "Throne of Magical Arcana", tập 16). */
    fun seriesOf(title: String): SeriesPlace {
        val match = seriesPattern.find(title)
            ?: return SeriesPlace("title:${title.trim()}", title.trim(), null, "tập")
        val word = match.groupValues[2].lowercase(Locale.ROOT)
        val series = match.groupValues[1].trim()
        val unit = if (word == "quyển" || word == "phần") word else "tập"
        return SeriesPlace("title:$series", series, match.groupValues[3].toInt(), unit)
    }

    /**
     * Bộ và số tập của mọi cuốn. Phần của một cuốn làm nhiều đợt đi theo chuỗi máy chủ biết (`series`); còn lại theo tên, cộng một luật:
     * cuốn KHÔNG đánh số mà tên đúng bằng tên một bộ có tập đánh số là tập 1 - chỉ khi có ĐÚNG MỘT cuốn như thế (hai bản cùng tên không
     * biết bản nào là tập 1). Có cả bản nghe được lẫn bản chỉ-chữ thì bản chỉ-chữ không tranh chỗ tập 1.
     */
    fun seriesIndex(books: List<SeriesItem>): Map<String, SeriesPlace> {
        val titles = books.associate { it.id to it.title }
        val places = HashMap<String, SeriesPlace>()
        for (book in books) {
            val link = book.series ?: continue
            val name = seriesOf(titles[link.root] ?: book.title).series
            places[book.id] = SeriesPlace("chain:${link.root}", name, link.part, "phần")
        }
        val roots = books.mapNotNull { it.series?.root }.toSet()
        for (book in books) {
            if (book.id !in places && book.id in roots) places[book.id] = SeriesPlace("chain:${book.id}", seriesOf(book.title).series, 1, "phần")
        }
        val byTitle = LinkedHashMap<String, SeriesPlace>()
        for (book in books) if (book.id !in places) byTitle[book.id] = seriesOf(book.title)
        val units = HashMap<String, String>()
        for (place in byTitle.values) if (place.volume != null && place.key !in units) units[place.key] = place.unit
        val isText = books.associate { it.id to it.isText }
        val candidates = LinkedHashMap<String, MutableList<String>>()
        for ((id, place) in byTitle) if (place.volume == null && place.key in units) candidates.getOrPut(place.key) { ArrayList() }.add(id)
        val first = HashSet<String>()
        for (ids in candidates.values) {
            val heard = ids.filter { isText[it] != true }
            val pool = heard.ifEmpty { ids }
            if (pool.size == 1) first += pool[0]
        }
        for ((id, place) in byTitle) places[id] = if (id in first) place.copy(volume = 1, unit = units.getValue(place.key)) else place
        return places
    }

    /** Nhãn tập cho cuốn trong bộ mà bìa không tự có: tên không mang số và không phải phần nối tiếp ("Tập 1" của cuốn không số). */
    fun volumeBadge(title: String, link: SeriesLink?, volume: Int?, unit: String): String? {
        if (volume == null || seriesOf(title).volume != null || (link?.part ?: 0) > 1) return null
        return unit.replaceFirstChar { it.titlecase(Locale.ROOT) } + " " + volume
    }

    /** Mã các cuốn mà thư viện còn một cuốn nữa CÙNG TÊN (hai bản của một truyện, hai lần thêm). */
    fun twinIds(books: List<ListenBook>): Set<String> {
        fun key(book: ListenBook) = fold(book.title.trim().replace(Regex("\\s+"), " "))
        val count = HashMap<String, Int>()
        for (book in books) count[key(book)] = (count[key(book)] ?: 0) + 1
        return books.filter { (count[key(it)] ?: 0) > 1 }.mapTo(HashSet()) { it.id }
    }

    // ---- tiến độ ----------------------------------------------------------------------------------------

    /** Phiên bản `a` mới hơn `b`? (readingPosition.ts newerReading): có bộ đếm thì so (epoch, counter, node), không thì so `at`. */
    fun newer(aRev: Rev?, aAt: Double, bRev: Rev?, bAt: Double): Boolean {
        val left = aRev ?: Rev(0, "")
        val right = bRev ?: Rev(0, "")
        if (left.counter != 0L || right.counter != 0L) {
            val le = left.epoch.orEmpty()
            val re = right.epoch.orEmpty()
            val cmp = le.compareTo(re)
            return cmp > 0 || (cmp == 0 && (left.counter > right.counter || (left.counter == right.counter && left.node > right.node)))
        }
        return aAt > bAt
    }

    /** Đã nghe bao nhiêu phần của cuốn (androidSource `bookProgress`); `chapters` chỉ gồm chương có audio. */
    fun bookProgress(state: ListenState, chapters: List<ChapterInfo>, complete: Boolean = true): Progress {
        val total = chapters.sumOf { it.duration }
        var heard = 0.0
        var done = 0
        for (chapter in chapters) {
            val record = state.chapters[chapter.id] ?: continue
            if (record.done) {
                heard += chapter.duration
                done += 1
            } else {
                heard += minOf(chapter.duration, record.heard)
            }
        }
        val allHeard = chapters.isNotEmpty() && done == chapters.size
        val marked = state.finished
        val rewound = (marked || allHeard) && isRewound(state, chapters)
        if (rewound && state.last != null) heard = positionSeconds(state.last, chapters)
        return Progress(
            heardSeconds = heard,
            totalSeconds = total,
            fraction = if (total > 0) (heard / total).toFloat().coerceIn(0f, 1f) else 0f,
            chaptersDone = done,
            finished = !rewound && (marked || (complete && allHeard)),
            caughtUp = !rewound && !complete && allHeard && !marked,
            rewound = rewound,
        )
    }

    private fun isRewound(state: ListenState, chapters: List<ChapterInfo>): Boolean {
        val last = state.last
        if (last == null || chapters.isEmpty()) return false
        if (state.finished && !newer(last.rev, last.at, state.finishedRev, state.finishedAt ?: 0.0)) return false
        val final = chapters.last()
        if (last.chapterId != final.id) return chapters.any { it.id == last.chapterId }
        return final.duration > 0 && final.duration - last.seconds > DONE_TAIL_SECONDS
    }

    private fun positionSeconds(last: Last, chapters: List<ChapterInfo>): Double {
        var before = 0.0
        for (chapter in chapters) {
            if (chapter.id == last.chapterId) return before + minOf(chapter.duration, last.seconds)
            before += chapter.duration
        }
        return before
    }

    /** Sách chỉ-có-chữ: không có độ dài audio, tiến độ theo chương (androidSource `textBookProgress`). */
    fun textBookProgress(state: ListenState, chapters: List<ChapterInfo>): Progress {
        var sum = 0.0
        var done = 0
        var heard = 0.0
        for (chapter in chapters) {
            val record = state.chapters[chapter.id] ?: continue
            heard += record.heard
            if (record.done) {
                sum += 1
                done += 1
            } else if (record.duration != null && record.duration > 0) {
                sum += (record.heard / record.duration).coerceIn(0.0, 1.0)
            }
        }
        val marked = state.finished
        val all = chapters.isNotEmpty() && done == chapters.size
        val fraction = if (chapters.isNotEmpty()) minOf(1.0, sum / chapters.size) else 0.0
        return Progress(heard, 0.0, if (marked) 1f else fraction.toFloat(), done, finished = marked || all)
    }

    // ---- chỗ nghe tiếp ----------------------------------------------------------------------------------

    /** Độ dài chương: của gói sách, hay - chương đọc to chưa có audio - độ dài trình phát đã ghi lúc nghe. */
    fun knownDuration(state: ListenState, chapter: ChapterInfo): Double =
        if (chapter.duration > 0) chapter.duration else (state.chapters[chapter.id]?.duration ?: 0.0)

    /** Phần đã nghe của một chương, 0..1 (model.ts `chapterHeard`): đã đánh dấu xong = 1; độ dài chưa biết thì 0. */
    fun chapterHeard(state: ListenState, chapter: ChapterInfo): Float {
        val record = state.chapters[chapter.id] ?: return 0f
        if (record.done) return 1f
        val length = knownDuration(state, chapter)
        return if (length > 0) minOf(1.0, record.heard / length).toFloat() else 0f
    }

    /** Giây nghe tiếp trong một chương khi vào nó không qua chỗ nghe cuối: chỗ xa nhất đã nghe nếu chương chưa xong và chưa gần hết. */
    private fun chapterResumeAt(state: ListenState, chapter: ChapterInfo): Double {
        val record = state.chapters[chapter.id]
        if (record == null || record.done || !(record.heard > 0)) return 0.0
        val length = knownDuration(state, chapter)
        return if (length > 0 && length - record.heard < NEAR_END_SECONDS) 0.0 else record.heard
    }

    /**
     * Chương nên phát khi bấm "Nghe": chỗ đang nghe dở nếu chương ấy còn nghe được (nghe gần hết thì sang chương kế, từ chỗ đã nghe tới trong
     * chương ấy), không thì chương đầu tiên chưa nghe xong, cuối cùng là chương đầu. null khi không chương nào nghe được.
     */
    fun resumePoint(state: ListenState, complete: Boolean, chapters: List<ChapterInfo>): ResumeSpot? {
        val playable = chapters.filter { it.playable }
        if (playable.isEmpty()) return null
        fun spot(chapter: ChapterInfo, at: Double) = ResumeSpot(chapter.id, chapter.title, at)
        val last = state.last
        if (last != null) {
            val index = playable.indexOfFirst { it.id == last.chapterId }
            if (index >= 0) {
                val chapter = playable[index]
                val length = knownDuration(state, chapter)
                val nearEnd = length > 0 && length - last.seconds < NEAR_END_SECONDS
                if (!nearEnd) return spot(chapter, last.seconds)
                playable.getOrNull(index + 1)?.let { return spot(it, chapterResumeAt(state, it)) }
                // Nghe tới cuối chương cuối ĐÃ CÓ của một cuốn còn đang làm: đứng yên ở đó, đừng quay về chương đầu.
                if (!complete) return spot(chapter, last.seconds)
            }
        }
        val unheard = playable.firstOrNull { state.chapters[it.id]?.done != true }
        return if (unheard != null) spot(unheard, chapterResumeAt(state, unheard)) else spot(playable[0], 0.0)
    }

    // ---- dòng trạng thái ---------------------------------------------------------------------------------

    /** Dòng trạng thái của một cuốn (androidSource-side `progressText`), không kèm dấu nguồn. */
    fun progressText(book: ListenBook): String {
        if (book.textOnly) {
            val lead = book.author.trim()
            return (if (lead.isNotEmpty()) "$lead · " else "") + "${book.chaptersTotal} chương"
        }
        val chapters = "${book.chaptersAvailable}/${book.chaptersTotal} chương"
        if (book.progress.finished) return "Đã nghe xong"
        if (book.progress.caughtUp) return "Đã nghe hết phần đã có · $chapters"
        if (!book.complete) return chapters
        val heard = book.progress.heardSeconds
        if (heard <= 0) return Fmt.length(book.duration)
        val left = maxOf(0.0, book.duration - heard)
        // Ở tốc độ của cuốn, làm tròn lên - như số giờ còn lại ở thanh phát.
        return "Còn " + Fmt.lengthUp(left / (book.state.rate ?: 1.0))
    }

    /** Tên máy giữ cuốn nghe thẳng, viết như "Trên máy tính". */
    fun remotePlace(book: ListenBook): String = "Trên ${book.remote?.deviceName ?: "máy tính"}"
}
