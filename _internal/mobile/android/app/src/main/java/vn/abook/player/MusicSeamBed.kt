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

        /** Thời gian dựng Nối (ms) và nguồn của nó: `built` = vừa giải mã (buildMs = thời gian render ở nền), `cache` = lấy từ cacheDir (buildMs = thời gian [LoopSeam.plan]). Chỉ có nghĩa khi READY (dòng `attach` của testEvents). */
        @Volatile var buildMs = 0L
        @Volatile var source = "cache"
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
            built.buildMs = built.seam.buildMs
            built.state = State.READY
        } else {
            async(Runnable {
                try {
                    val began = System.nanoTime()
                    render(built)
                    built.buildMs = (System.nanoTime() - began) / 1_000_000
                    built.source = "built"
                    synchronized(this) { if (built.state == State.BUILDING) built.state = State.READY }
                } catch (t: Throwable) {
                    reject(built, "dựng Nối lỗi (${t.message})")
                }
            })
        }
        return Choice.Use(built)
    }

    /** Quên các Nối đã chọn (đổi / dừng sách): lần chọn sau lập lại hình học, WAV trong bộ nhớ đệm trên đĩa vẫn dùng được. */
    fun clear() {
        synchronized(this) { entries.clear() }
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

/** Lý do một từ của dòng `demote` (testEvents): late = Nối chưa dựng kịp, fail = dựng hỏng, seek = tua tới chỗ chưa có Nối, error = lỗi phát. */
enum class DemoteReason(val word: String) { LATE("late"), FAIL("fail"), SEEK("seek"), ERROR("error") }

/**
 * Định dạng các dòng sự kiện đo của [MusicBed.testEvents] (SPEC_loop_p3w_bed.md §1); mọi dòng KHÔNG có `EV <ns>` đứng trước (bên đo tự thêm). Giây 6 chữ số thập phân như dòng SEAM của §41.
 * - `open <k> p3|a87 <track>`; `plan <k> <sr> <ch> <audibleStart'> <loopStart'> <loopEnd'> <xFrames>` (ngay sau `open ... p3`)
 * - `attach <k> <số mục sau khi thêm> <buildMs> <built|cache>`
 * - `demote <k> late|fail|seek|error`
 * - `seek <k> <sinceSeconds> <mụcIndex> <clip0|seam|clip> <expSample>` (expSample trên trục danh nghĩa của mục, như `EV seek` của MusicLoopSeamTest). Đích theo bản đồ chung [SeamClock.target]:
 *   giây bài của đích (plan + kind + expSample) trùng `alignedA87` (vòng khai báo) của cùng `sinceSeconds`, gấp chu kỳ P', tới 1 mẫu (trước audibleStart' thì kẹp ở mẫu 0, < 1 khung)
 * - `pos <k> <trackSecondsP3> <alignedA87>`, `item <k> <index> <reason> <kind>`, `audiotrack <k> <sr> <ch>`
 * - `vol <k> <v>`: MỖI lần MusicBed đặt volume của trình phát k (kể cả từng nhịp mờ; v 6 chữ số thập phân)
 * - `promote <k> loop <viTriA87Giay>`: viTriA87Giay = vị trí của trình phát a87 (giây trong bài, 6 chữ số) mà promoteTo dùng để tính đích Nối. Bài a87 (mở vào giữa vòng khi chưa có Nối) chuyển sang P3 ở ranh lặp; k = trình phát P3 mới (dòng `open <k> p3` + `plan` + `attach` của nó đứng TRƯỚC, lúc tạo sẵn ~3 s trước ranh).
 *   Dòng này chỉ báo QUYẾT ĐỊNH chuyển, chưa đổi tiếng: a87 vẫn kêu ở âm lượng cũ, P3 khởi động CÂM ([SeamHandover]). Sau nó: `seek <k> ...` (mục 1 = Nối, mẫu = chỗ a87 sẽ ở khi P3 ra loa, [SeamHandover.target]) và `vol <k> 0`;
 *   P3 có thể được tua lại (thêm `seek <k> ...`) cho tới khi pha khớp. Rồi MỘT trong hai: `handover` (êm) hay `demote <k> late|error` (a87 lặp mờ chéo như khi không có Nối).
 * - `handover <k> <viTriA87Giay> <viTriP3Giay>`: lúc thực sự chuyển tiếng sang P3 (|P3 - a87| <= [SeamHandover.TOLERANCE_MS]). Cả hai vị trí tính trên TRỤC a87 (giây trong bài, 6 chữ số), cùng một cách đo:
 *   a87 = giây bài của khung đầu AudioTrack hiện tại của a87 + framePosition của nó / sr ([SeamHandover.legacySeconds]; máy không cho timestamp thì currentPosition như trước), P3 = (loopEnd' - X' + mẫu đích của lần tua cuối + framePosition của AudioTrack P3) / sr,
 *   nên hiệu hai số là pha lệch lúc chuyển (chỉ để đối chiếu). Ngay sau: `vol <k> <âm lượng của a87>` (> 0) rồi `vol <k cũ> 0` (lần đầu a87 về 0 nằm SAU lúc P3 ra loa); không có `demote`.
 * - `hread <k> <deltaMs> <playedMs>`: MỖI lần đọc pha được tính vào quyết định ([SeamHandover.reading] khác null), giữa `promote` và `handover` / `demote`: deltaMs = P3 - a87 (ms, cùng cách đo
 *   như `handover`), playedMs = P3 đã phát bao lâu kể từ lần xả sau lần tua cuối ([SeamHandover.played]); 3 chữ số thập phân. Danh sách lần đọc bắt đầu lại sau mỗi `seek <k>`.
 *   Thước so pha theo dòng `ts` thì chỉ lấy timestamp có nanoTime sau dòng `audiotrack <k>` đầu tiên sau lần tua cuối (như [SeamHandover.fresh]).
 * Bên đo tự thêm `scenario <Sx>`, `scenario_end`, `sync <t> <nhảy 0|1>`, `FMT`, `PCM`.
 */
object SeamEvents {
    private fun f(v: Double, digits: Int = 6) = String.format(java.util.Locale.ROOT, "%.${digits}f", v)

    fun kindOf(index: Int) = if (index == 0) "clip0" else if (index % 2 == 1) "seam" else "clip"
    fun open(k: Int, p3: Boolean, track: String) = "open $k ${if (p3) "p3" else "a87"} $track"
    fun plan(k: Int, seam: LoopSeam.Seam) =
        "plan $k ${seam.sampleRate} ${seam.channels} ${f(seam.audibleStart)} ${f(seam.loopStart)} ${f(seam.loopEnd)} ${seam.xFrames}"
    fun attach(k: Int, items: Int, built: SeamPicker.Built) = "attach $k $items ${built.buildMs} ${built.source}"
    fun demote(k: Int, reason: DemoteReason) = "demote $k ${reason.word}"
    fun seek(k: Int, sinceSeconds: Double, target: SeamClock.Target) = "seek $k ${f(sinceSeconds, 3)} ${target.index} ${kindOf(target.index)} ${target.sample}"
    fun pos(k: Int, trackSecondsP3: Double, alignedA87: Double) = "pos $k ${f(trackSecondsP3)} ${f(alignedA87)}"
    fun item(k: Int, index: Int, reason: Int, kind: String) = "item $k $index $reason $kind"
    fun audioTrack(k: Int, sampleRate: Int, channels: Int) = "audiotrack $k $sampleRate $channels"
    fun volume(k: Int, v: Float) = "vol $k ${f(v.toDouble(), 6)}"
    fun promote(k: Int, legacyPositionSeconds: Double) = "promote $k loop ${f(legacyPositionSeconds)}"
    fun handover(k: Int, legacySeconds: Double, p3Seconds: Double) = "handover $k ${f(legacySeconds)} ${f(p3Seconds)}"
    fun handoverReading(k: Int, deltaMs: Double, playedMs: Double) = "hread $k ${f(deltaMs, 3)} ${f(playedMs, 3)}"
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
     * Đích của `sinceSeconds` giây kể từ đầu mốc. Bản đồ vị trí CHUNG với a87: giây trong bài là [MusicCues.loopPosition] trên vòng KHAI BÁO `bounds` (như [MusicCues.alignedPosition] của a87,
     * dòng `pos`), rồi đặt chỗ ấy lên hình học căn khung của Nối: vòng đầu tính từ audibleStart', các vòng sau từ loopStart', gấp theo P' = loopEnd' - loopStart' - X' mẫu, mỗi chu kỳ là
     * [Nối X' mẫu, Clip lặp]. Không đếm chu kỳ theo P' từ đầu mốc: P' lệch P tới 1,5 khung nên mỗi vòng trôi thêm chừng ấy (vòng 2 đã 32-44 ms, PLAN §43.2).
     * Nối / Clip lặp luôn tua vào mục 1 / 2 (hai mục này luôn có trong hàng, [stale] chỉ bỏ từ mục 2 trở đi sau khi qua).
     */
    fun target(seam: LoopSeam.Seam, bounds: MusicCues.Loop, sinceSeconds: Double): Target {
        val t = sinceSeconds.coerceAtLeast(0.0)
        val n = Math.round(MusicCues.loopPosition(bounds, t) * seam.sampleRate) // giây trong bài -> mẫu trên trục giải mã liền
        val clip0 = seam.loopEndSamples - seam.xFrames - seam.audibleStartSamples
        val j = if (MusicCues.firstPass(bounds, t)) {
            val m = n - seam.audibleStartSamples
            if (m < clip0) return Target(0, m.coerceAtLeast(0)) // trước audibleStart' (A' làm tròn lên): đầu Clip đầu, lệch < 1 khung
            m - clip0 // A + t đã qua loopEnd' - X' (biên khai báo muộn hơn biên khung): phần đầu Nối, nội dung bài cũ đúng chỗ
        } else {
            n - seam.loopStartSamples
        }
        val period = seam.loopEndSamples - seam.loopStartSamples - seam.xFrames
        val r = Math.floorMod(j, period) // trước loopStart' (biên khung muộn hơn biên khai báo): cuối Clip lặp của chu kỳ trước, cùng nội dung
        return if (r < seam.xFrames) Target(1, r) else Target(2, r - seam.xFrames)
    }

    /** Mục đã qua cần bỏ khỏi hàng (cho `removeMediaItems`): giữ Clip đầu + Nối + vòng đang phát, bỏ cặp (2, 3) mỗi khi sang mục >= 4: hàng không dài ra theo số vòng, chẵn lẻ của mục giữ nguyên. */
    fun stale(currentIndex: Int): IntRange? = if (currentIndex >= 4) 2..3 else null

    enum class Gate { WAIT, ATTACH, DEMOTE, DONE }

    /** Lý do rơi về của [Gate.DEMOTE]: dựng hỏng -> fail, còn lại (hết hạn chót) -> late. */
    fun demoteReason(state: SeamPicker.State): DemoteReason = if (state == SeamPicker.State.DEAD) DemoteReason.FAIL else DemoteReason.LATE

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

    /**
     * Bài mở ở `offsetSeconds` (kể từ đầu mốc) có phát bằng P3 ngay được không: Nối đã xong (READY: P3 tua tới đúng mục / mẫu, [target]) hoặc chỗ vào còn trong Clip đầu (Clip đầu không cần Nối).
     * Không thì a87 phục vụ chỗ vào, Nối dựng nền và P3 nhận ở ranh lặp kế ([Promote]).
     */
    fun servesEntry(built: SeamPicker.Built, offsetSeconds: Double): Boolean =
        built.state == SeamPicker.State.READY || target(built.seam, built.bounds, offsetSeconds).index == 0

    /** Bài a87 đang chờ Nối: NOW = Nối xong, nhận ở ranh lặp này; WAIT = chưa xong, để ranh lặp sau (a87 tự mờ chéo bản lặp của nó); NEVER = hỏng, ở lại a87. */
    enum class Promote { NOW, WAIT, NEVER }

    fun promote(state: SeamPicker.State): Promote = when (state) {
        SeamPicker.State.READY -> Promote.NOW
        SeamPicker.State.BUILDING -> Promote.WAIT
        SeamPicker.State.DEAD -> Promote.NEVER
    }

    /** Mẫu của Nối (từ đầu Nối) ứng với bài a87 ở `legacySeconds` (giây trong bài, trong [loopEnd' - X', loopEnd']): Nối bắt đầu ở loopEnd' - X' của a87. Có thể âm / vượt X' (chưa kẹp). */
    fun legacySample(seam: LoopSeam.Seam, legacySeconds: Double): Long =
        Math.round(legacySeconds * seam.sampleRate) - (seam.loopEndSamples - seam.xFrames)
}

/**
 * a87 -> P3 không để quãng im, ở ranh lặp của bài a87 mở vào giữa vòng (trình phát P3 đã dựng sẵn, đứng ở đầu Nối). P3 khởi động mất 70-450 ms mới ra loa nên KHÔNG đổi tiếng ngay:
 * a87 cứ kêu ở âm lượng cũ, P3 tua tới chỗ a87 SẼ ở khi P3 ra loa (vị trí a87 + trễ khởi động ước lượng) rồi phát CÂM; khi AudioTrack của P3 thật sự chạy (timestamp phần cứng, không hẹn giờ)
 * thì đo pha: vị trí P3 trên trục a87 (mẫu đích của lần tua cuối + framePosition / sr) trừ vị trí a87, đo ĐỐI XỨNG ([legacySeconds]: mốc đầu AudioTrack a87 + framePosition của nó / sr; không có timestamp
 * thì currentPosition). Lệch <= [TOLERANCE_MS] ([STEADY_READINGS] lần đọc liền) thì mới đổi tiếng; [STEADY_READINGS] lần đọc ỔN ĐỊNH mà lệch hơn thì tua lại P3 (vẫn câm, a87 vẫn kêu)
 * với trễ đã sửa theo pha trung bình (trễ mới = trễ cũ - lệch), tối đa [MAX_RETUNES] lần. Chỉ đọc timestamp của AudioTrack sinh ra SAU lần tua cuối ([fresh]).
 * Quá [DEADLINE_MS] hay a87 gần hết Nối ([GUARD_MS]) thì bỏ: a87 lặp mờ chéo như khi không có Nối. Thuần số học, [MusicBed] lo trình phát.
 *
 * Nhịp một lần tua: xả + AudioTrack mới ra loa (máy ảo 70-200 ms, máy thật 160-450 ms) + [SETTLE_MS] + [STEADY_READINGS] x [POLL_MS] = ~150-300 ms trên máy ảo, tới ~550 ms máy thật nguội.
 * [DEADLINE_MS] 1,5 s chứa đủ lần tua đầu + [MAX_RETUNES] lần sửa trên máy ảo, và vẫn nằm trong Nối (X = 2 s trừ [GUARD_MS]); máy thật thì từ ranh thứ hai trễ đã học nên thường một lần sửa là khớp.
 */
object SeamHandover {
    /** Từ lúc quyết định chuyển; quá chừng này mà P3 chưa khớp thì ở lại đường a87. */
    const val DEADLINE_MS = 1500L

    /** Pha lệch tối đa giữa P3 và a87 lúc đổi tiếng (luật f6b). */
    const val TOLERANCE_MS = 10.0

    /** P3 phải đã phát ít nhất chừng này (theo AudioTrack) thì số đo mới tin. */
    const val SETTLE_MS = 60.0

    /** Số lần đọc liền (mỗi [POLL_MS]) trong dung sai trước khi đổi tiếng; cũng là số lần đọc ổn định cần có trước khi tua lại. */
    const val STEADY_READINGS = 3

    /** Còn chừng này (ms) tới hết Nối (a87 tới loopEnd') thì không chuyển nữa. */
    const val GUARD_MS = 150L
    const val MAX_RETUNES = 3
    const val POLL_MS = 10L

    /** Trễ khởi động P3 ước lượng lúc chưa đo (ms, từ lệnh tua / phát tới khi ra loa); máy thật 160-450 ms, máy ảo ~100 ms. [MusicBed] giữ số đã đo. */
    const val DEFAULT_LAG_MS = 250L
    private const val MIN_LAG_MS = 20L
    private const val MAX_LAG_MS = 900L

    enum class Act { WAIT, SWITCH, RETUNE, FALLBACK }

    /** Trễ khởi động sau khi đo: P3 ở trước a87 `deltaMs` (dương) nghĩa là trễ ước lượng quá lớn chừng ấy. */
    fun nextLag(lagMs: Long, deltaMs: Double): Long = Math.round(lagMs - deltaMs).coerceIn(MIN_LAG_MS, MAX_LAG_MS)

    /** Đích tua của P3 khi a87 đang ở `legacySeconds`: chỗ a87 sẽ ở sau `lagMs`. Null khi chỗ ấy đã sát hết Nối (còn < [GUARD_MS]): không còn đủ chỗ để chuyển. */
    fun target(seam: LoopSeam.Seam, legacySeconds: Double, lagMs: Long): SeamClock.Target? {
        val n = SeamClock.legacySample(seam, legacySeconds + lagMs / 1000.0).coerceAtLeast(0L)
        return if (n > seam.xFrames - GUARD_MS * seam.sampleRate / 1000) null else SeamClock.Target(1, n)
    }

    /** Còn bao nhiêu ms tới hết Nối (a87 tới loopEnd'). */
    fun remainingMs(seam: LoopSeam.Seam, legacySeconds: Double): Double = (seam.loopEndSamples - legacySeconds * seam.sampleRate) * 1000.0 / seam.sampleRate

    /** Vị trí P3 trên trục a87 (giây trong bài): P3 tua tới mẫu `targetSample` của Nối rồi AudioTrack đã phát `framesPlayed` khung. */
    fun p3Seconds(seam: LoopSeam.Seam, targetSample: Long, framesPlayed: Long): Double =
        (seam.loopEndSamples - seam.xFrames + targetSample + framesPlayed).toDouble() / seam.sampleRate

    /** Vị trí a87 (giây trong bài) đo cùng cách với P3: mốc đầu AudioTrack hiện tại của a87 (giây bài của khung đầu tiên ghi vào nó sau lần xả cuối, µs) + số khung nó đã phát / sr. */
    fun legacySeconds(startUs: Long, framesPlayed: Long, sampleRate: Int): Double = startUs / 1_000_000.0 + framesPlayed.toDouble() / sampleRate

    /**
     * Timestamp AudioTrack này nói về tiếng SAU mốc `sinceNano` không: phải có một lần xả bộ đệm (tua) ở sau mốc (`flushedNano`), timestamp chụp sau lần xả ấy và AudioTrack đã chạy.
     * Lần tua của P3 tới luồng phát muộn vài ms; trong lúc ấy AudioTrack CŨ vẫn chạy và cho timestamp mới với framePosition lớn - đọc nó là ra pha rác (PLAN §43.2 g6: tua lại sau 11-13 ms).
     */
    fun fresh(sinceNano: Long, flushedNano: Long, stampNano: Long, framePosition: Long): Boolean =
        flushedNano >= sinceNano && stampNano > flushedNano && framePosition > 0

    /** Một lần đọc AudioTrack ([MusicBed] gọi getTimestamp): framePosition + nanoTime của timestamp, tần số của AudioTrack, [System.nanoTime] của lần xả bộ đệm cuối của trình phát. */
    class Stamp(val framePosition: Long, val nanoTime: Long, val sampleRate: Int, val flushedNano: Long) {
        /** Số khung đã phát ngoại suy tới `nowNano`. */
        fun framesAt(nowNano: Long): Long = framePosition + (nowNano - nanoTime) * sampleRate / 1_000_000_000L
    }

    /** Vị trí a87 theo AudioTrack của nó ([legacySeconds]); null khi timestamp không tin được (người gọi dùng currentPosition). */
    fun legacySeconds(startUs: Long, stamp: Stamp, nowNano: Long): Double? =
        if (fresh(0L, stamp.flushedNano, stamp.nanoTime, stamp.framePosition)) legacySeconds(startUs, stamp.framesAt(nowNano), stamp.sampleRate) else null

    /**
     * Một lần đọc pha P3 - a87 (ms) ở nhịp `nowNano`: P3 đã tua tới `targetSample` lúc `issuedNano`, `stamp` là AudioTrack hiện tại của P3, a87 ở `legacySeconds`.
     * Null (không tính vào [decide]) khi timestamp không [fresh] - kể cả AudioTrack CŨ còn chạy ngay sau lần tua - hay P3 mới phát < [SETTLE_MS] kể từ lần xả sau lần tua.
     */
    fun reading(seam: LoopSeam.Seam, targetSample: Long, issuedNano: Long, stamp: Stamp, nowNano: Long, legacySeconds: Double): Double? {
        if (!fresh(issuedNano, stamp.flushedNano, stamp.nanoTime, stamp.framePosition)) return null
        val played = played(seam, stamp, nowNano)
        if (played * 1000.0 / seam.sampleRate < SETTLE_MS) return null
        return (p3Seconds(seam, targetSample, played) - legacySeconds) * 1000.0
    }

    /** Số khung AudioTrack P3 đã phát tới `nowNano` (ngoại suy từ `stamp`), quy về tần số của Nối: cái [reading] cộng vào mẫu đích; dòng `hread` ghi nó theo ms. */
    fun played(seam: LoopSeam.Seam, stamp: Stamp, nowNano: Long): Long =
        stamp.framesAt(nowNano).let { if (stamp.sampleRate == seam.sampleRate) it else it * seam.sampleRate / stamp.sampleRate }

    /** Các lần đọc cuối chênh nhau không quá chừng này (ms) mới coi là pha đã ổn định (tua lại theo trung bình của chúng). */
    const val STABLE_MS = 5.0

    /** Pha trung bình (ms) của [STEADY_READINGS] lần đọc cuối khi chúng ổn định (chênh nhau <= [STABLE_MS]); null = chưa đủ / chưa ổn định. */
    fun settled(readings: List<Double>): Double? {
        if (readings.size < STEADY_READINGS) return null
        val last = readings.subList(readings.size - STEADY_READINGS, readings.size)
        return if (last.max() - last.min() <= STABLE_MS) last.average() else null
    }

    /**
     * Việc cần làm ở mỗi nhịp. `readings` = pha P3 - a87 (ms) của các lần đọc tin được kể từ lần tua cuối (AudioTrack mới của P3 đã phát >= [SETTLE_MS], [fresh]), cũ trước.
     * SWITCH khi [STEADY_READINGS] lần cuối đều trong [TOLERANCE_MS]; RETUNE (tua lại P3, câm, theo [settled]) chỉ khi [STEADY_READINGS] lần cuối ỔN ĐỊNH mà lệch - một lần đọc lẻ không bao giờ đủ để tua;
     * FALLBACK = bỏ, ở lại đường a87.
     */
    fun decide(elapsedMs: Long, remainingMs: Double, retunes: Int, readings: List<Double>): Act {
        if (elapsedMs >= DEADLINE_MS || remainingMs <= GUARD_MS) return Act.FALLBACK
        if (readings.size < STEADY_READINGS) return Act.WAIT
        if (readings.subList(readings.size - STEADY_READINGS, readings.size).all { Math.abs(it) <= TOLERANCE_MS }) return Act.SWITCH
        if (settled(readings) == null) return Act.WAIT
        return if (retunes >= MAX_RETUNES) Act.FALLBACK else Act.RETUNE
    }
}
