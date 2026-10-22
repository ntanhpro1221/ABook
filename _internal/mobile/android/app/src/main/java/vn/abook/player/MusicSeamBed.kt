package vn.abook.player

import java.io.File

/**
 * Đường P3 của nhạc nền ([LoopSeam], tuỳ chọn thử nghiệm `MusicBed.musicSeamP3`, mặc định tắt) - phần thuần dữ liệu, không ExoPlayer, để test JVM chạy được.
 *
 * Bài lặp phát bằng MỘT ExoPlayer [Clip đầu, Nối, Clip lặp, Nối, ...] thay vì mở trình phát mới ở mỗi chỗ lặp. Nhạc KHÔNG chờ dựng Nối: Clip đầu phát ngay khi mốc bắt đầu,
 * Nối dựng song song ở luồng nền ([SeamPicker]); dựng xong thì [MusicBed] nối thêm mục Nối / Clip lặp vào hàng phát ([Gate.ATTACH]). Tới gần hết Clip đầu mà Nối chưa xong, hay dựng
 * lỗi, thì bài rơi về đường cũ (a87: trình phát mới mờ chéo ở loopEnd - X) - [Gate.DEMOTE], có ghi logcat, không im lặng.
 */
class SeamPicker(
    private val enabled: () -> Boolean,
    /** Chạy việc nền (luồng worker của [MusicBed]); trong test chạy tay. */
    private val async: (Runnable) -> Unit,
    /** Hình học của Nối ([LoopSeam.plan], cỡ mili giây); null = bài này không cần / không dùng được Nối (không mờ chéo). Ném lỗi = không dùng được. */
    private val plan: (File, MusicCues.Cue) -> Built?,
    /** Giải mã dựng WAV Nối ([LoopSeam.render]); chạy ở `async`. Ném lỗi = không dùng được. */
    private val render: (Built) -> Unit,
    private val note: (String) -> Unit,
) {
    enum class State { BUILDING, READY, DEAD }

    /** Nối của một bài + vòng của nó; `state` đổi một chiều BUILDING -> READY | DEAD (DEAD cuối cùng, dựng muộn không làm nó sống lại). */
    class Built(val seam: LoopSeam.Seam, val bounds: MusicCues.Loop, val durationSeconds: Double, val key: String) {
        @Volatile var state = State.BUILDING
    }

    sealed class Choice {
        /** Bài phát bằng đường cũ (a87): cờ tắt, mốc `tail`, không phải mp3, không mờ chéo, dựng hỏng. */
        object Legacy : Choice()

        /** Bài phát bằng P3; `built.state` cho biết Nối đã xong chưa. */
        class Use(val built: Built) : Choice()
    }

    private val entries = HashMap<String, Built>()

    /** Chọn đường cho bài `file` của mốc `cue`. Không bao giờ chờ: lần đầu chỉ làm phần hình học (ms) rồi giao việc giải mã cho nền. */
    fun choose(file: File, cue: MusicCues.Cue): Choice {
        if (!enabled()) return Choice.Legacy
        if (!eligible(file, cue)) return Choice.Legacy
        val key = keyOf(file, cue)
        synchronized(this) { entries[key] }?.let { return if (it.state == State.DEAD) Choice.Legacy else Choice.Use(it) }
        val built = try {
            plan(file, cue)
        } catch (t: Throwable) {
            dead(key, "dựng hình học Nối lỗi (${t.message}), phát bằng đường cũ")
            return Choice.Legacy
        }
        if (built == null) {
            dead(key, "bài không lặp mờ chéo, phát bằng đường cũ")
            return Choice.Legacy
        }
        synchronized(this) { entries[key] = built }
        if (built.seam.cached) {
            built.state = State.READY
        } else {
            async(Runnable {
                try {
                    render(built)
                    synchronized(this) { if (built.state == State.BUILDING) built.state = State.READY }
                } catch (t: Throwable) {
                    reject(built, "dựng Nối lỗi (${t.message})")
                }
            })
        }
        return Choice.Use(built)
    }

    /** Bỏ Nối này cho cả phiên (lỗi giữa chừng khi phát, dựng hỏng): lần chọn sau là [Choice.Legacy]. */
    fun reject(built: Built, why: String) {
        synchronized(this) { built.state = State.DEAD }
        note("Nối ${built.key}: $why - phát bằng đường cũ")
    }

    private fun dead(key: String, why: String) {
        val stub = Built(LoopSeam.Seam(File(""), File(""), 0, 0, 0, 0, 0, 0, 0, 0), MusicCues.Loop(0.0, 0.0, 0.0, false), 0.0, key)
        stub.state = State.DEAD
        synchronized(this) { entries[key] = stub }
        note("Nối $key: $why")
    }

    companion object {
        fun eligible(file: File, cue: MusicCues.Cue): Boolean = !cue.tail && file.name.endsWith(".mp3", ignoreCase = true)

        /** Hai mốc cùng bài dùng chung một Nối khi vòng của chúng như nhau và mốc mới không phải `tail` (vòng cuối chơi qua loopEnd tới E: đường cũ lo). */
        fun compatible(built: Built, cue: MusicCues.Cue): Boolean = !cue.tail && MusicCues.loopBounds(cue, built.durationSeconds) == built.bounds

        fun keyOf(file: File, cue: MusicCues.Cue): String =
            "${file.absolutePath}|${file.length()}|${file.lastModified()}|${cue.audibleStart}|${cue.audibleEnd}|${cue.loopStart}|${cue.loopEnd}"
    }
}

/** Đồng hồ nhạc và tua của đường P3: tính theo (mục, vị trí trong mục) của ExoPlayer; bảng mục: 0 = Clip đầu, lẻ = Nối, chẵn >= 2 = Clip lặp ([LoopSeam]). */
object SeamClock {
    /** Còn chừng này (ms) tới hết Clip đầu mà Nối chưa xong thì rơi về đường cũ: đủ để trình phát đường cũ mở và mờ vào trước loopEnd - X. */
    const val DEADLINE_MS = 2500L

    /** Vị trí nhạc (giây TRONG BÀI) của mục `index` ở vị trí `positionMs` (ms trong mục, thang của ExoPlayer). Khớp [MusicCues.loopPosition]: Nối là chỗ bản lặp mới vừa vào (loopStart + t). */
    fun trackSeconds(seam: LoopSeam.Seam, index: Int, positionMs: Long): Double = when {
        index == 0 -> (seam.clip0StartMs + positionMs.coerceAtLeast(0)) / 1000.0
        index % 2 == 1 -> seam.loopStart + positionMs.coerceIn(0, seam.seamMs) / 1000.0
        // Clip lặp mở sớm `loopClipLeadMs` (phần preroll bị cắt ở sink): trước đó vẫn tính là đầu Clip.
        else -> (seam.loopStartSamples + seam.xFrames).toDouble() / seam.sampleRate + (positionMs - seam.loopClipLeadMs).coerceAtLeast(0.0) / 1000.0
    }

    /** Còn bao nhiêu ms tới hết Clip đầu; null khi đã qua Clip đầu. */
    fun clip0RemainingMs(seam: LoopSeam.Seam, index: Int, positionMs: Long): Long? = if (index == 0) seam.clip0Ms - positionMs else null

    /** Đích tua: mục `index`, mẫu `sample` trên trục danh nghĩa của mục ([LoopSeam.seekToSample]). */
    class Target(val index: Int, val sample: Long)

    /**
     * Đích của `sinceSeconds` giây kể từ đầu mốc (bài vào từ A = audibleStart' ở giây 0 của mốc): hết Clip đầu thì chu kỳ P' = loopEnd' - loopStart' - X' mẫu, mỗi chu kỳ
     * là [Nối X mẫu, Clip lặp]. Tương đương [MusicCues.loopPosition] (cùng mod P). Nối / Clip lặp luôn tua vào mục 1 / 2 (hai mục này luôn có trong hàng, [stale] chỉ bỏ từ mục 2 trở đi sau khi qua).
     */
    fun target(seam: LoopSeam.Seam, sinceSeconds: Double): Target {
        val n = Math.round(sinceSeconds.coerceAtLeast(0.0) * seam.sampleRate)
        val clip0 = seam.loopEndSamples - seam.xFrames - seam.audibleStartSamples
        if (n < clip0) return Target(0, n)
        val period = seam.loopEndSamples - seam.loopStartSamples - seam.xFrames
        val r = (n - clip0) % period
        return if (r < seam.xFrames) Target(1, r) else Target(2, r - seam.xFrames)
    }

    /** Mục đã qua cần bỏ khỏi hàng (cho `removeMediaItems`): giữ Clip đầu + Nối + vòng đang phát, bỏ cặp (2, 3) mỗi khi sang mục >= 4: hàng không dài ra theo số vòng, chẵn lẻ của mục giữ nguyên. */
    fun stale(currentIndex: Int): IntRange? = if (currentIndex >= 4) 2..3 else null

    enum class Gate { WAIT, ATTACH, DEMOTE, DONE }

    /**
     * Việc cần làm ở mỗi nhịp đồng bộ với bài P3: `attached` = đã nối Nối / Clip lặp vào hàng; `remainingMs` = [clip0RemainingMs]. Dựng xong thì nối vào ngay (xa loopEnd bao nhiêu cũng được);
     * dựng hỏng thì rơi về đường cũ ngay; chưa xong mà còn dưới [DEADLINE_MS] tới hết Clip đầu thì rơi về đường cũ cho chỗ lặp này.
     */
    fun gate(state: SeamPicker.State, attached: Boolean, remainingMs: Long?): Gate = when {
        attached -> Gate.DONE
        state == SeamPicker.State.READY -> Gate.ATTACH
        state == SeamPicker.State.DEAD -> Gate.DEMOTE
        remainingMs != null && remainingMs <= DEADLINE_MS -> Gate.DEMOTE
        else -> Gate.WAIT
    }
}
