package vn.abook.player

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/** Mốc nhạc của chương cho trình phát (`music_plan.chapter_cues`): giây ƯỚC trong chương, bài theo link danh mục. */
class SceneCue(
    val start: Double,
    val end: Double,
    val link: String,
    /** Khoá đoạn (`"{chapterId}:{firstSegment}"`) mà mốc này thuộc về. */
    val key: String,
    /** Mốc nối bài anh em ở điểm kết bài trong cùng cảnh (mờ chéo dài hơn). */
    val sibling: Boolean,
    /** Mốc kết đúng ở điểm kết bài đã lập lịch (bài anh em vào ngay sau, hay bài kết sớm ở `stopAt`): vòng cuối thôi lặp. */
    val tail: Boolean,
    /** Bước âm lượng trong cảnh: mức (dB, cộng vào `gainDb`) từ giây `at` của chương. */
    val steps: List<MusicCues.Step>,
)

/**
 * Phần thuần của nhạc theo cảnh đường N0 nằm giữa danh mục và trình phát: ô danh mục ([cellOf], [near]) và mốc của chương ([chapterCues]).
 * Dựng đoạn: [SceneScenes]; chọn bài: [SceneChooser]; tách câu: [SceneSegmenter].
 */
object SceneMusic {
    /** `music_catalog.cell_of`: chỉ số ô (valence, arousal) trên lưới `grid` x `grid`; `int()` của Python cắt về 0. */
    fun cellOf(valence: Double, arousal: Double, grid: Int = 5): Pair<Int, Int> {
        fun index(value: Double): Int = min(grid - 1, max(0, ((value + 1.0) / 2.0 * grid).toInt()))
        return index(valence) to index(arousal)
    }

    /**
     * `MusicCatalog.near`: bài trong ô của (valence, arousal) và các ô kề trong bán kính `radius`, theo thứ tự vòng lặp v (ngoài) rồi a (trong), KHÔNG khử trùng.
     * Thứ tự này là thứ tự hoà của `rank` (sort ổn định): phải đúng từng bài.
     */
    fun <T> near(grid: Int, valence: Double, arousal: Double, radius: Int, cell: (Int, Int) -> List<T>): List<T> {
        val (vi, ai) = cellOf(valence, arousal, grid)
        val items = ArrayList<T>()
        for (v in max(0, vi - radius) until min(grid, vi + radius + 1)) {
            for (a in max(0, ai - radius) until min(grid, ai + radius + 1)) items.addAll(cell(v, a))
        }
        return items
    }

    private class Draft(val start: Double, var end: Double, val link: String, val key: String, val sibling: Boolean) {
        var tail = false
        val steps = ArrayList<MusicCues.Step>()
    }

    /**
     * `music_plan.chapter_cues` + `clamp_to_chapter`: mốc nhạc của chương `chapterId` (đoạn im lặng thì không có). Hai đoạn liền nhau cùng bài gộp làm một; bài anh em
     * tách mốc đúng ở điểm kết bài (`sibling`); bước âm lượng của mảnh nối tiếp thành `steps`; mốc kết đúng ở điểm kết bài đã lập lịch mang `tail`.
     * `duration` (giây ƯỚC của chương): mốc kết muộn nhất ở `duration - chapterEndFadeSeconds`, mốc vì thế rỗng thì bỏ; null thì không kẹp.
     */
    fun chapterCues(scenes: List<ChosenScene>, chapterId: Int, duration: Double?): List<SceneCue> {
        val mergeGap = MusicCues.mix.cueMergeGapSeconds
        val drafts = ArrayList<Draft>()
        var rested = false // mốc trước kết sớm (`stopAt`): mốc sau dù cùng bài vẫn là bài mở lại sau quãng lặng, không gộp
        for (chosen in scenes) {
            val scene = chosen.scene
            val link = chosen.link
            if (scene.chapterId != chapterId || link == null) continue
            val level = chosen.stepDb ?: 0.0
            val spans = ArrayList<Triple<Double, String, Boolean>>()
            spans.add(Triple(scene.start, link, false))
            for (sibling in chosen.siblings) spans.add(Triple(sibling.at, sibling.link, true))
            for ((index, span) in spans.withIndex()) {
                val (start, spanLink, sibling) = span
                // `stopAt`: bài kết sớm trước ranh giới (TAIL_MIN_SECONDS), phần còn lại của mảnh lặng.
                val stopAt = chosen.stopAt
                val last = if (stopAt == null) scene.end else min(scene.end, stopAt)
                val end = if (index + 1 < spans.size) spans[index + 1].first else last
                val tail = index + 1 < spans.size || (stopAt != null && end == stopAt)
                val draft: Draft
                val before = drafts.lastOrNull()
                if (before != null && !rested && before.link == spanLink && abs(before.end - start) < mergeGap) {
                    draft = before
                    draft.end = end
                } else {
                    draft = Draft(start, end, spanLink, chosen.key, sibling)
                    drafts.add(draft)
                }
                draft.tail = tail
                val currentLevel = draft.steps.lastOrNull()?.db ?: 0.0
                if (level != currentLevel) draft.steps.add(MusicCues.Step(Py.round(start, 3), level))
                rested = false
            }
            rested = chosen.stopAt != null
        }
        val clamped = MusicTimeline.clampToChapter(
            drafts.map { MusicCues.Cue(it.start, it.end, it.link, null, it.steps, it.sibling, it.tail) }, duration,
        )
        var from = 0
        return clamped.map { cue ->
            while (drafts[from].start != cue.start || drafts[from].link != cue.track) from++ // clampToChapter giữ thứ tự, `start` và bài
            val draft = drafts[from++]
            SceneCue(cue.start, cue.end, draft.link, draft.key, draft.sibling, cue.tail, draft.steps)
        }
    }
}
