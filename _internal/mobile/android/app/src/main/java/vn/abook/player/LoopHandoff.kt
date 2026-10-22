package vn.abook.player

import android.os.Handler

/**
 * Giờ vào bản lặp của nhạc nền (PLAN_loop §29-35; máy tính: ui/src/listen/musicBed.ts `crossLoop`). Mờ chéo lặp giả định bản mới vào ở loopStart ĐÚNG lúc
 * bản cũ ở loopEnd - X; chỉ kiểm lúc đồng bộ với giọng (mỗi [MusicCues.SYNC_TICK_SECONDS]) thì bản mới vào trễ tới một nhịp, hai bản lệch pha suốt
 * X giây mờ chéo - nghe ra đánh đôi phách. Nên:
 *  - bước 0: còn dưới [MusicCues.LOOP_STANDBY_SECONDS] tới hạn thì tạo SẴN bản lặp (`prepare`: ExoPlayer đã `prepare()` + seek tới loopStart, câm, chưa phát) -
 *    mở trình phát mới mất cả trăm mili giây, tới hạn chỉ còn phát nó;
 *  - bước 1: sắp tới hạn (dưới 1,5 nhịp) thì hẹn MỘT lần ([MusicCues.loopHandoffDelay]), vé huỷ khi tua / đổi bài / dừng ([reset]);
 *  - bước 2: vào muộn thì bản mới ở chỗ đã bù ([MusicCues.loopStartAt]) - `enter` nhận bản tạo sẵn (nếu có) và đặt lại chỗ;
 *  - bước 3 (MusicBed): bản mới có tiếng thì sửa pha một lần ([MusicCues.loopSettle]).
 *
 * Lớp này chỉ lo QUYẾT ĐỊNH, vé và vòng đời bản tạo sẵn `R`; trạng thái bài đang kêu lấy qua [look], MusicBed lo ExoPlayer thật ([prepare], [discard], [enter]).
 */
class LoopHandoff<R : Any>(
    private val main: Handler,
    private val look: () -> Snapshot?,
    private val prepare: (Snapshot) -> R?,
    private val discard: (R) -> Unit,
    private val enter: (Snapshot, R?) -> Unit,
) {
    /** Bài đang kêu (`owner`): vòng của nó, chỗ đang tới (giây trong bài), có đang chạy không (đứng yên thì không hẹn). */
    class Snapshot(val owner: Any, val bounds: MusicCues.Loop, val position: Double, val playing: Boolean)

    private var ticket: Runnable? = null
    private var ready: R? = null
    private var readyOwner: Any? = null

    /** Bản đã tạo sẵn (null = chưa có). */
    fun prepared(): R? = ready

    /** Huỷ vé đang hẹn. */
    fun cancel() {
        ticket?.let(main::removeCallbacks)
        ticket = null
    }

    /** Nhả bản tạo sẵn (không vào bản lặp nữa: tua, đổi bài, dừng, bài hỏng, vòng cuối). */
    fun discardReady() {
        val old = ready ?: return
        ready = null
        readyOwner = null
        discard(old)
    }

    /** Huỷ cả vé lẫn bản tạo sẵn: tua, đổi bài, dừng, chương mới. */
    fun reset() {
        cancel()
        discardReady()
    }

    /** Kiểm một lần (mỗi lần đồng bộ, hay `fromTimer` khi vé nổ): tới hạn thì vào bản lặp, sắp tới hạn thì tạo sẵn và hẹn vé. Vé nổ mà bài chưa tới hạn
     *  (đang đứng chờ tải) thì không hẹn lại - lần đồng bộ kế hẹn tiếp. */
    fun check(fromTimer: Boolean = false) {
        cancel()
        val snap = look()
        if (snap == null) {
            discardReady()
            return
        }
        val due = MusicCues.loopDue(snap.bounds, snap.position) ||
            (fromTimer && snap.playing && snap.position >= snap.bounds.loopEnd - MusicCues.mix.loopCrossfadeSeconds - TIMER_SLACK_SECONDS)
        if (due) {
            val mine = ready?.takeIf { readyOwner === snap.owner }
            if (mine == null) discardReady()
            ready = null
            readyOwner = null
            enter(snap, mine)
            return
        }
        if (snap.bounds.crossfade && snap.bounds.loopEnd - MusicCues.mix.loopCrossfadeSeconds - snap.position < MusicCues.LOOP_STANDBY_SECONDS) {
            if (readyOwner !== snap.owner) {
                discardReady()
                ready = prepare(snap)
                readyOwner = if (ready != null) snap.owner else null
            }
        } else {
            discardReady()
        }
        if (fromTimer || !snap.playing) return
        val delay = MusicCues.loopHandoffDelay(snap.bounds, snap.position, MusicCues.SYNC_TICK_SECONDS) ?: return
        val job = Runnable {
            ticket = null
            check(fromTimer = true)
        }
        ticket = job
        main.postDelayed(job, Math.round(delay * 1000))
    }

    private companion object {
        /** Vé nổ mà bài cũ còn thiếu chút ít tới hạn (đồng hồ bài lệch đồng hồ máy) vẫn tính là tới hạn. */
        const val TIMER_SLACK_SECONDS = 0.05
    }
}
