package vn.abook.player

import org.json.JSONObject

/**
 * Mốc nhạc theo cảnh của chương đang nghe, đúng dạng [MusicBed] chơi (phần thuần dữ liệu của chế độ "Theo cảnh" trên điện thoại, tách riêng để test JVM chạy được).
 *
 * Mốc thô của máy ([DeviceScenes], giây ước) qua [SceneAnchor.Feed] thành mốc theo đồng hồ đọc của chương, rồi thành [MusicCues.Cue]: bài = link của danh mục, độ
 * khuếch đại tính từ số đo của bài trong danh mục ([MusicGain.cueGainDb], cùng công thức với hàng bài của danh sách phát), đoạn nghe được (`audibleStart` / `audibleEnd`)
 * nếu danh mục có. Mỗi nhịp [tick] hỏi đồng hồ đọc: clip về làm giây đoạn đổi thì đặt lại mốc cho khớp (`SceneCues.refresh` ở web); người nghe nhảy ([seeked]) về trước
 * chỗ nhạc được phép vào thì mốc theo cảnh chứa chỗ mới.
 *
 * `timingOf`: đồng hồ đọc của chương đang nghe ([vn.abook.player.readaloud.ReadAloud.segmentTiming]), null khi chưa có. Một luồng (luồng chính của [MusicBed]).
 */
class SceneBed(private val timingOf: () -> SceneAnchor.Timing?) {
    /** Trả lời của [DeviceScenes] đã chuẩn bị: mốc thô + độ dài ước + mức nhạc của cuốn + thông tin bài trong danh mục (gain, đoạn nghe được, ghi công). */
    class Arrival(val cues: List<SceneAnchor.Cue>, val estSeconds: Double, val levelDb: Double, val infos: Map<String, JSONObject>)

    private var latest: SceneAnchor.Timing? = null
    private var placedFor: SceneAnchor.Timing? = null
    private val feed = SceneAnchor.Feed { latest }
    private var levelDb = DEFAULT_LEVEL_DB
    private var infos: Map<String, JSONObject> = emptyMap()

    /** Mốc đang hiệu lực, giây theo đồng hồ đọc của chương. */
    var cues: List<MusicCues.Cue> = emptyList()
        private set

    /** Chương khác (hay đổi cuốn): quên mốc cũ. */
    fun reset() {
        feed.reset()
        latest = null
        placedFor = null
        cues = emptyList()
    }

    /** Mốc của chương vừa về lúc giọng đang ở giây `time`: nhạc vào ở đầu câu kế (không giữa câu). true khi `cues` đổi. */
    fun arrive(arrival: Arrival, time: Double): Boolean {
        levelDb = arrival.levelDb
        infos = arrival.infos
        latest = timingOf()
        placedFor = latest
        if (arrival.cues.isEmpty()) { // chương không nhạc: như web, đặt thẳng mốc rỗng
            feed.reset()
            return replace(emptyList())
        }
        return replace(feed.arrive(arrival.cues, arrival.estSeconds, time))
    }

    /** Mỗi nhịp của trình phát: đồng hồ đọc có giây mới (clip về, đổi giọng) thì đặt lại mốc; `seeked` (người nghe vừa nhảy tới `time`) thì xem nhạc có phải theo chỗ mới.
     *  true khi `cues` được đặt lại. */
    fun tick(time: Double, seeked: Boolean): Boolean {
        if (!feed.hasCues) return false
        val now = timingOf()
        latest = now
        var changed = false
        if (seeked) changed = replace(feed.seeked(time))
        val unchanged = if (now == null) placedFor == null else now.sameAs(placedFor)
        if (!unchanged) changed = replace(feed.refresh()) || changed
        return changed
    }

    /** Đặt mốc mới (null: chưa có gì để đặt - chưa có đồng hồ đọc của chương, giữ mốc cũ). */
    private fun replace(placed: List<SceneAnchor.Cue>?): Boolean {
        if (placed == null) return false
        placedFor = latest
        cues = placed.map { musicCue(it) }
        return true
    }

    private fun musicCue(cue: SceneAnchor.Cue): MusicCues.Cue {
        val info = infos[cue.link]
        val gain = MusicGain.cueGainDb(levelDb, number(info, "lufs"), number(info, "speechBand"), number(info, "s95"))
        return MusicCues.Cue(cue.start, cue.end, cue.link, gain, cue.steps, cue.sibling, cue.tail, number(info, "audibleStart"), number(info, "audibleEnd"),
            number(info, "loopStart"), number(info, "loopEnd"))
    }

    private fun number(info: JSONObject?, key: String): Double? = (info?.opt(key) as? Number)?.toDouble()?.takeIf { it.isFinite() }

    companion object {
        /** Mức nhạc dưới giọng (dB) khi lớp sửa của cuốn không nói (`music_plan.DEFAULT_LEVEL_DB`). */
        const val DEFAULT_LEVEL_DB = -20.0
    }
}
