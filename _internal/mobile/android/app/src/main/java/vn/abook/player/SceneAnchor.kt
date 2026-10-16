package vn.abook.player

import org.json.JSONObject

/**
 * Nhạc nền THEO CẢNH của sách chỉ có chữ, đặt mốc theo đồng hồ đọc - bản Kotlin của ui/src/listen/sceneCues.ts (`warpOf`, `anchorSceneCues`, `fromSegment`,
 * `nextSegment`, lớp `SceneCues`), phải ra GIỐNG HỆT (tests/fixtures/music/anchor/ (các file .json) do sceneCues.fixtures.test.ts sinh, SceneAnchorTest so).
 *
 * [DeviceScenes] dựng mốc theo giây ƯỚC của kế hoạch; mốc mở một cảnh mang `firstSegment` = mã đoạn của màn đọc nơi cảnh bắt đầu. Giọng đọc chạy theo đồng hồ ảo
 * ([vn.abook.player.readaloud.VirtualTimeline]: giây thật của đoạn đã đọc, ước cho đoạn chưa) - mốc được đặt lại để bài đổi đúng lúc ĐOẠN ĐẦU CẢNH BẮT ĐẦU PHÁT, không
 * giữa câu; mốc nối bài anh em và bước âm lượng co giãn theo các mốc đoạn ấy. Phần còn lại (mờ chéo, lặp, nhảy) là của [MusicBed] như nhạc của sách Studio.
 *
 * Thuần tính toán: không đụng Android (test JVM).
 */
object SceneAnchor {
    /** Mốc theo cảnh của máy (`DeviceScenes.cues`): giây ước hoặc (sau [anchor]) giây của đồng hồ đọc. `firstSegment` chỉ có ở mốc mở cảnh. */
    data class Cue(
        val start: Double,
        val end: Double,
        val link: String,
        val key: String,
        val sibling: Boolean = false,
        val tail: Boolean = false,
        val steps: List<MusicCues.Step> = emptyList(),
        val firstSegment: Int? = null,
    )

    /** Giây bắt đầu từng đoạn của chương trên đồng hồ đọc và tổng độ dài (`segmentStarts` của sceneCues.ts). */
    class Timing(val starts: DoubleArray, val total: Double) {
        fun sameAs(other: Timing?): Boolean = other != null && total == other.total && starts.contentEquals(other.starts)
    }

    /** Mốc từ JSON của `musicSceneCues`; mốc hỏng (thiếu link / giây) bỏ. */
    fun cuesOf(response: JSONObject): List<Cue> {
        val list = response.optJSONArray("cues") ?: return emptyList()
        return (0 until list.length()).mapNotNull { index ->
            val cue = list.optJSONObject(index) ?: return@mapNotNull null
            val link = cue.optString("link")
            val start = cue.optDouble("start", Double.NaN)
            val end = cue.optDouble("end", Double.NaN)
            if (link.isEmpty() || !start.isFinite() || !end.isFinite()) return@mapNotNull null
            val steps = cue.optJSONArray("steps")?.let { array ->
                (0 until array.length()).mapNotNull { at ->
                    val step = array.optJSONObject(at) ?: return@mapNotNull null
                    val time = step.optDouble("at", Double.NaN)
                    val db = step.optDouble("db", Double.NaN)
                    if (time.isFinite() && db.isFinite()) MusicCues.Step(time, db) else null
                }
            } ?: emptyList()
            Cue(start, end, link, cue.optString("key"), cue.optBoolean("sibling", false), cue.optBoolean("tail", false), steps,
                if (cue.has("firstSegment") && !cue.isNull("firstSegment")) cue.optInt("firstSegment") else null)
        }
    }

    /** Hàm co giãn giây ước -> giây của đồng hồ đọc, tuyến tính từng khúc qua các mốc (giây ước mở cảnh, giây bắt đầu đoạn đầu cảnh). Ngoài khúc cuối thì dịch theo. */
    fun warpOf(anchors: List<Pair<Double, Double>>): (Double) -> Double {
        val ests = ArrayList<Double>().apply { add(0.0) }
        val reals = ArrayList<Double>().apply { add(0.0) }
        for ((est, real) in anchors.sortedBy { it.first }) { // sortedBy ổn định, như Array.sort của JS
            val last = ests.size - 1
            if (est <= ests[last]) {
                if (est == ests[last]) reals[last] = maxOf(reals[last], real)
                continue
            }
            ests.add(est)
            reals.add(maxOf(real, reals[last]))
        }
        return { est ->
            if (est <= 0) maxOf(0.0, est)
            else {
                var at = 0
                while (at + 1 < ests.size && ests[at + 1] <= est) at += 1
                if (at + 1 >= ests.size) reals[at] + (est - ests[at])
                else reals[at] + ((est - ests[at]) / (ests[at + 1] - ests[at])) * (reals[at + 1] - reals[at])
            }
        }
    }

    /** Đặt mốc theo đồng hồ đọc: mốc mở cảnh bắt đầu đúng lúc đoạn `firstSegment` bắt đầu phát; mọi giây khác trong mốc (kết, bước âm lượng, mốc nối bài anh em) co
     *  theo. `estSeconds`: độ dài chương theo giây ước của máy. */
    fun anchor(cues: List<Cue>, estSeconds: Double, timing: Timing): List<Cue> {
        val starts = timing.starts
        if (starts.isEmpty()) return emptyList()
        val anchors = cues.mapNotNull { cue ->
            val segment = cue.firstSegment
            if (segment != null && segment >= 0 && segment < starts.size) cue.start to starts[segment] else null
        }
        val end = cues.fold(estSeconds) { most, cue -> maxOf(most, cue.end) }
        val warp = warpOf(anchors + (end to maxOf(timing.total, anchors.lastOrNull()?.second ?: 0.0)))
        return cues.map { cue ->
            cue.copy(start = warp(cue.start), end = warp(cue.end), steps = cue.steps.map { MusicCues.Step(warp(it.at), it.db) })
        }
    }

    /** Chỉ giữ nhạc từ đoạn `index` trở đi (đã đặt theo đồng hồ đọc): mốc kết trước đó bỏ, mốc chứa chỗ ấy bắt đầu đúng ở đầu đoạn `index`. Mốc tới muộn - chương
     *  dựng xong khi giọng đã đọc dở - nhờ đây vào ở đầu câu kế, không xen giữa câu. */
    fun fromSegment(cues: List<Cue>, timing: Timing, index: Int): List<Cue> {
        if (index <= 0) return cues
        val at = timing.starts.getOrNull(index) ?: return emptyList()
        return cues.filter { it.end > at }.map { if (it.start < at) it.copy(start = at) else it }
    }

    /** Chỉ số đoạn đầu tiên bắt đầu SAU giây `time` của đồng hồ đọc (câu kế), hay số đoạn khi đang ở đoạn cuối. */
    fun nextSegment(timing: Timing, time: Double): Int {
        val found = timing.starts.indexOfFirst { it > time + 1e-6 }
        return if (found < 0) timing.starts.size else found
    }

    /**
     * Bộ nhận mốc theo cảnh của một chương (`SceneCues` của sceneCues.ts). Giữ mốc thô của máy rồi đặt lại mỗi khi kịch bản có giây mới (clip về) hay người nghe nhảy.
     * Mỗi hàm trả mốc đã đặt để đưa cho [MusicBed], hay null khi chưa có gì để đặt (chưa có mốc thô / chưa có đồng hồ đọc của chương).
     * `timing`: đồng hồ đọc của chương đang nghe, null khi chưa có.
     */
    class Feed(private val timing: () -> Timing?) {
        private var raw: List<Cue> = emptyList()
        private var estSeconds = 0.0
        /** Đoạn đầu tiên nhạc được phép vào (0 = từ đầu chương): mốc tới giữa chừng chờ câu kế. */
        private var floor = 0

        /** Chương khác: quên mốc cũ. */
        fun reset() {
            raw = emptyList()
            floor = 0
        }

        /** Có mốc thô nào chưa (đã `arrive` với mốc). */
        val hasCues: Boolean get() = raw.isNotEmpty()

        /** Mốc của chương vừa về lúc giọng đang ở giây `time`: nhạc vào ở đầu câu kế (không giữa câu). */
        fun arrive(cues: List<Cue>, estSeconds: Double, time: Double): List<Cue>? {
            raw = cues
            this.estSeconds = estSeconds
            val now = timing()
            floor = if (now != null && time > 0.25) nextSegment(now, time) else 0
            return push()
        }

        /** Kịch bản có giây mới (clip về, đổi giọng): đặt lại mốc cho khớp. */
        fun refresh(): List<Cue>? = if (raw.isNotEmpty()) push() else null

        /** Người nghe nhảy tới giây `time`: về trước chỗ nhạc được phép vào thì nhạc theo cảnh chứa chỗ mới, như sách Studio. */
        fun seeked(time: Double): List<Cue>? {
            val now = timing()
            if (raw.isEmpty() || now == null || floor == 0) return null
            if (time < (now.starts.getOrNull(floor) ?: Double.POSITIVE_INFINITY)) {
                floor = 0
                return push()
            }
            return null
        }

        private fun push(): List<Cue>? {
            val now = timing()
            if (now == null || now.starts.isEmpty()) return null
            return fromSegment(anchor(raw, estSeconds, now), now, floor)
        }
    }
}
