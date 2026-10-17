package vn.abook.player

import kotlin.math.abs
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow

/**
 * Dòng thời gian nhạc của MỘT chương cho bản xuất kèm nhạc nền - port 1-1 của `music_mix.music_timeline` (+ `music_plan.clamp_to_chapter`)
 * theo "mô hình lặp chung" của lô 2: mờ vào/ra, mờ chéo anh em, bước âm lượng trượt, lặp mờ chéo trong đoạn nghe được [A, E), vòng cuối
 * của mốc `tail`, vào sớm. Hàm thuần, không âm thanh; ra các phần tử ĐÃ làm tròn như `_Element.shape` của Python (giây 3 số lẻ, dB 2
 * số lẻ, chẵn gần nhất) - bản xuất dựng âm thanh từ đúng các số ấy ([MusicRender.renderBus]), như máy tính. Kiểm bằng nguyên phần
 * `timeline` của mọi fixture `tests/fixtures/music_timeline`. Hằng số: [MusicCues.mix].
 */
object MusicTimeline {
    private const val EPS = 1e-6

    /** Bài của một mốc: độ dài thật (giây; null = chưa biết), đoạn nghe được [A, E) (null = 0 / độ dài) và điểm vòng (null = không có). */
    class TrackInfo(
        val seconds: Double?,
        val audibleStart: Double? = null,
        val audibleEnd: Double? = null,
        val loopStart: Double? = null,
        val loopEnd: Double? = null,
    )

    /** Một phần tử của dòng thời gian: mốc sinh ra nó (`cue`, chỉ số sau khi xếp), cách vào ("start", "loop", "early") và phần dựng. */
    class Shaped(val cue: Int, val enter: String, val element: MusicRender.Element)

    /** Mốc kết muộn nhất ở `duration - chapterEndFadeSeconds`; mốc vì thế rỗng thì bỏ; mốc bị kẹp mất `tail`. Không có độ dài thì để nguyên. */
    fun clampToChapter(cues: List<MusicCues.Cue>, duration: Double?): List<MusicCues.Cue> {
        if (duration == null) return cues
        val limit = duration - MusicCues.mix.chapterEndFadeSeconds
        return cues.map { if (it.end > limit) it.copy(end = limit, tail = false) else it }.filter { it.end > it.start }
    }

    /** (A, E, P, lặp mờ chéo?) của bài dài `seconds` - `music_mix.loop_bounds`, cùng hàm với trình phát ([MusicCues.loopBounds]). */
    fun loopBounds(info: TrackInfo?): MusicCues.Loop =
        MusicCues.loopBounds(
            MusicCues.Cue(0.0, 0.0, "", null, audibleStart = info?.audibleStart, audibleEnd = info?.audibleEnd,
                loopStart = info?.loopStart, loopEnd = info?.loopEnd),
            info?.seconds ?: Double.NaN,
        )

    private fun stepDb(cue: MusicCues.Cue, seconds: Double): Double {
        var db = 0.0
        for (step in cue.steps.sortedBy { it.at }) {
            if (seconds < step.at) break
            db = step.db
        }
        return db
    }

    /** Biên độ đích (tuyến tính) của mốc tại `seconds`: gainDb + bước, <= 0 dB như trình phát. */
    private fun level(cue: MusicCues.Cue, seconds: Double): Double = 10.0.pow(min(0.0, (cue.gainDb ?: 0.0) + stepDb(cue, seconds)) / 20)

    private class Point(val t: Double, val a: Double)

    private class Element(val track: String, val cue: Int, val enter: String, val begin: Double, val position: Double, val bounds: MusicCues.Loop) {
        var points: List<Point> = emptyList()
        var to: Double? = null

        fun at(seconds: Double): Double = position + seconds - begin

        fun amplitude(seconds: Double): Double {
            if (points.isEmpty()) return 0.0
            if (seconds <= points[0].t) return points[0].a
            for (i in 0 until points.size - 1) {
                val (t0, a0) = points[i].let { it.t to it.a }
                val (t1, a1) = points[i + 1].let { it.t to it.a }
                if (seconds <= t1) return if (t1 > t0) a0 + (a1 - a0) * (seconds - t0) / (t1 - t0) else a1
            }
            return points.last().a
        }

        fun ramp(seconds: Double, target: Double, length: Double) {
            val now = amplitude(seconds)
            points = points.filter { it.t < seconds - EPS } + Point(seconds, now) + Point(seconds + length, target)
        }

        fun shape(): Shaped {
            val until = to ?: Double.POSITIVE_INFINITY
            return Shaped(cue, enter, MusicRender.Element(
                track, round(begin, 3), if (until.isFinite()) round(until, 3) else until, round(position, 3),
                DoubleArray(points.size) { round(points[it].t, 3) },
                Array(points.size) { points[it].a.let { a -> if (a > 1e-9) round(20 * log10(a), 2) else null } },
                loop = !bounds.crossfade,
            ))
        }
    }

    private fun round(x: Double, digits: Int): Double = MusicRender.round(x, digits)

    /** Lặp thường, mốc `tail`: hết vòng nào cách hết mốc dưới nửa vòng thì đó là vòng cuối. */
    private fun finalPass(element: Element, period: Double, end: Double): Double {
        var natural = element.begin + (period - element.position)
        while (period.isFinite() && end - natural >= period / 2) natural += period
        return natural
    }

    /**
     * Dòng thời gian của chương: `cues` của chương (thứ tự bất kỳ), `chapterSeconds` = độ dài chương (mốc cuối kẹp; null = để nguyên),
     * `tracks` = bài -> [TrackInfo]. Ra các phần tử theo thứ tự vào.
     */
    fun build(cues: List<MusicCues.Cue>, chapterSeconds: Double?, tracks: Map<String, TrackInfo>): List<Shaped> {
        val mix = MusicCues.mix
        val fade = mix.fadeSeconds
        val siblingFade = mix.siblingFadeSeconds
        val rampLength = mix.stepRampSeconds
        val crossfade = mix.loopCrossfadeSeconds
        val sorted = clampToChapter(cues.sortedBy { it.start }, chapterSeconds)
        val out = ArrayList<Element>()
        var current: Element? = null // phần tử còn kêu ở cuối mốc trước (chơi tiếp sang mốc kề cùng bài)
        var ended: Element? = null   // phần tử của mốc trước đã chơi tới E trước khi mốc ấy hết (vòng cuối)
        for ((index, cue) in sorted.withIndex()) {
            val start = cue.start
            val end = cue.end
            val bounds = loopBounds(tracks[cue.track])
            val first = bounds.start
            val last = bounds.end
            val period = bounds.period
            val crossfading = bounds.crossfade
            var element: Element
            val playing = current
            if (playing != null && playing.track == cue.track) {
                element = playing // cùng bài sang mốc kề: chơi tiếp, mức theo mốc mới
                if (abs(element.amplitude(start) - level(cue, start)) > 1e-9) element.ramp(start, level(cue, start), rampLength)
            } else {
                val previous = if (index > 0) sorted[index - 1] else null
                val done = ended
                val doneAt = done?.to
                val early = done != null && previous != null && previous.tail && done.track != cue.track &&
                    abs(previous.end - start) < EPS && doneAt != null && doneAt < start - EPS
                val begin = if (early) doneAt!! else start
                element = Element(cue.track, index, if (early) "early" else "start", begin, first, bounds)
                element.points = listOf(Point(begin, 0.0), Point(begin + (if (cue.sibling) siblingFade else fade), level(cue, max(begin, start))))
                out.add(element)
            }
            current = null
            ended = null
            val steps = cue.steps.map { it.at }.filter { start < it && it < end }.sorted().toMutableList()
            while (true) {
                val natural: Double
                val lastPass: Boolean
                if (crossfading) {
                    // Vòng cuối (tính theo E): phần còn lại của mốc hơn phần còn lại của bài chưa tới nửa chu kỳ.
                    natural = element.begin + (last - element.position)
                    lastPass = cue.tail && end - natural < period / 2
                } else { // lặp thường cả file: chỉ mốc `tail` có vòng cuối
                    lastPass = cue.tail
                    natural = if (lastPass) finalPass(element, period, end) else Double.POSITIVE_INFINITY
                }
                val spawn = if (crossfading && !lastPass) element.begin + (bounds.loopEnd - crossfade - element.position) else Double.POSITIVE_INFINITY
                val stop = minOf(spawn, if (lastPass) natural else Double.POSITIVE_INFINITY, end)
                while (steps.isNotEmpty() && steps[0] < stop) {
                    val at = steps.removeAt(0)
                    element.ramp(at, level(cue, at), rampLength)
                }
                if (spawn < end && spawn <= stop) {
                    element.ramp(spawn, 0.0, crossfade)
                    element.to = spawn + crossfade
                    element = Element(cue.track, index, "loop", spawn, bounds.loopStart, bounds)
                    element.points = listOf(Point(spawn, 0.0), Point(spawn + crossfade, level(cue, spawn)))
                    out.add(element)
                    continue
                }
                if (lastPass && natural <= end + EPS) {
                    val stopAt = Point(natural, element.amplitude(natural))
                    element.points = element.points.filter { it.t < natural - EPS } + stopAt
                    element.to = natural // chơi tới E là hết: không mờ, phần sau E đã im
                    ended = element
                    break
                }
                val following = sorted.getOrNull(index + 1)?.takeIf { abs(it.start - end) < EPS }
                if (following != null && following.track == element.track) {
                    current = element
                    break
                }
                var length = fade
                if (following != null && following.sibling) length = max(EPS, min(siblingFade, last - element.at(end))) // hết phần còn lại thật của bài
                element.ramp(end, 0.0, length)
                element.to = end + length
                break
            }
        }
        return out.map { it.shape() }
    }
}
