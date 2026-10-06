package vn.abook.player

/** Một chương đưa cho thiết bị: [url] đã qua [Dlna.Media], [art] là URL bìa (hay ""). Như `cast.Track` của máy tính. */
data class CastTrack(
    val url: String,
    val title: String,
    val album: String,
    val duration: Double,
    val size: Long,
    val mime: String,
    val art: String = "",
)

/**
 * Thiết bị đang làm gì, nói theo từ vựng UPnP cho mọi giao thức: state PLAYING | PAUSED_PLAYBACK | TRANSITIONING | STOPPED |
 * NO_MEDIA_PRESENT. [uri] là thứ nó đang phát ("" = không biết); [reason] khi nó dừng và biết vì sao: "finished" (hết
 * chương), "interrupted" (có người khác chiếm máy), "error" (không phát được).
 */
data class CastStatus(val state: String, val position: Double, val duration: Double, val uri: String, val reason: String = "")

/**
 * Nói chuyện với MỘT thiết bị bằng một giao thức - như `cast.Backend` của máy tính: DLNA ([DlnaBackend]), Google Cast
 * ([GoogleCast]). Mọi lệnh lỗi -> [Dlna.Failure] câu tiếng Việt; [status] phải trả ngay (đọc bản chụp hay hỏi một lượt),
 * thiết bị im lặng thì [Dlna.Failure] - [DlnaPlayers] lo phần còn lại (phiên, sang chương).
 */
interface CastBackend {
    /** Đưa chương và phát từ [seconds] -> vị trí thật đã bắt đầu (0 nếu không tua được). */
    fun load(track: CastTrack, seconds: Double): Double

    fun play()

    /** true: thiết bị không có Pause nên đã dừng hẳn - "phát" phải đưa lại chương. */
    fun pause(): Boolean

    fun stop(timeoutMs: Int = 5000)

    fun seek(seconds: Double)

    fun status(): CastStatus

    /** Bỏ kết nối; [release]: trả luôn thiết bị về nguyên trạng (Cast: đóng ứng dụng phát nếu máy này đã mở nó). */
    fun close(release: Boolean = false) {}

    /** Âm lượng của thiết bị 0-100; null: thiết bị không cho chỉnh từ xa (hay chưa nói) - phím âm lượng để yên cho điện thoại. */
    fun volume(): Int? = null

    fun setVolume(percent: Int) {
        throw Dlna.Failure("thiết bị không chỉnh được âm lượng từ xa")
    }
}

/** DLNA / UPnP AV: SOAP AVTransport tới địa chỉ điều khiển của thiết bị; không giữ kết nối nên `close` không việc gì. */
class DlnaBackend(private val renderer: Dlna.Renderer) : CastBackend {
    private fun call(action: String, vararg arguments: Pair<String, Any>, timeoutMs: Int = 5000): Map<String, String> =
        Dlna.soap(renderer.avUrl, renderer.avType, action, listOf<Pair<String, Any>>("InstanceID" to 0) + arguments, timeoutMs)

    override fun load(track: CastTrack, seconds: Double): Double {
        val metadata = Dlna.didl(track.url, track.title, track.album, track.duration, track.size, track.mime)
        val arguments = arrayOf<Pair<String, Any>>("CurrentURI" to track.url, "CurrentURIMetaData" to metadata)
        try {
            call("SetAVTransportURI", *arguments)
        } catch (error: Dlna.Failure) {
            if (error.code != 701 && error.code != 705) throw error
            call("Stop") // có TV không nhận bài mới khi đang phát bài cũ
            call("SetAVTransportURI", *arguments)
        }
        call("Play", "Speed" to "1")
        return if (seconds >= 1) seekWhenReady(seconds) else 0.0
    }

    /** Phần lớn TV chỉ tua được khi đã chạy: đợi PLAYING (tới 8 giây) rồi tua. Không tua được thì phát từ đầu. */
    private fun seekWhenReady(seconds: Double): Double {
        val deadline = System.currentTimeMillis() + 8000
        while (System.currentTimeMillis() < deadline) {
            val state = runCatching { call("GetTransportInfo")["CurrentTransportState"] }.getOrNull().orEmpty()
            if (state == "PLAYING" || state == "PAUSED_PLAYBACK") {
                return try {
                    seek(seconds)
                    seconds
                } catch (_: Dlna.Failure) {
                    0.0
                }
            }
            Thread.sleep(300)
        }
        return 0.0
    }

    override fun play() {
        call("Play", "Speed" to "1")
    }

    override fun pause(): Boolean {
        try {
            call("Pause")
        } catch (error: Dlna.Failure) {
            if (error.code != 401 && error.code != 701) throw error
            call("Stop") // thiết bị không có Pause: dừng hẳn, "phát" sẽ đưa lại đúng chỗ
            return true
        }
        return false
    }

    override fun stop(timeoutMs: Int) {
        call("Stop", timeoutMs = timeoutMs)
    }

    override fun seek(seconds: Double) {
        call("Seek", "Unit" to "REL_TIME", "Target" to Dlna.clock(seconds))
    }

    /** RenderingControl GetVolume (kênh Master) - chỉ khi thiết bị có dịch vụ ấy; hỏi một lượt qua mạng. */
    override fun volume(): Int? {
        if (renderer.rcUrl.isEmpty()) return null
        val value = rendering("GetVolume")["CurrentVolume"]?.trim()?.toIntOrNull() ?: return null
        return value.coerceIn(0, 100)
    }

    override fun setVolume(percent: Int) {
        if (renderer.rcUrl.isEmpty()) super.setVolume(percent)
        rendering("SetVolume", "DesiredVolume" to percent.coerceIn(0, 100))
    }

    private fun rendering(action: String, vararg arguments: Pair<String, Any>): Map<String, String> =
        Dlna.soap(renderer.rcUrl, renderer.rcType, action, listOf<Pair<String, Any>>("InstanceID" to 0, "Channel" to "Master") + arguments)

    override fun status(): CastStatus {
        val state = call("GetTransportInfo")["CurrentTransportState"].orEmpty().trim().uppercase()
        val info = call("GetPositionInfo")
        return CastStatus(state, Dlna.secondsOf(info["RelTime"]), Dlna.secondsOf(info["TrackDuration"]), info["TrackURI"].orEmpty())
    }
}

fun backendFor(renderer: Dlna.Renderer): CastBackend = if (renderer.protocol == "gcast") GoogleCast(renderer) else DlnaBackend(renderer)
