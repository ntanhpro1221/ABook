package vn.abook.player.readaloud

import android.content.Context
import android.net.Uri
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.Artwork
import vn.abook.player.Playback
import vn.abook.player.SleepTimer
import vn.abook.player.Store
import java.io.File
import java.util.concurrent.Executors

/**
 * "Nghe ngay" cho chương CHỈ CÓ CHỮ (docs/LISTEN_ANYTHING.md mục 1 và 3): một giọng máy đọc chương, không phân tích. Sống trong lõi phát (như chương audio) vì
 * tắt màn hình thì WebView bị treo - sang đoạn kế, sang chương kế, hẹn giờ ngủ, nút tai nghe, lưu vị trí đều phải chạy không cần JavaScript.
 *
 * Cách làm: chương chia thành các đoạn ([Paragraphs.of], đúng như màn đọc), mỗi đoạn một đoạn âm thanh ([Clip]) do [ClipReader] đọc ở luồng nền. Chỉ đọc đoạn đang
 * nghe + [AHEAD] đoạn sau; đoạn nào xong thì nối thêm vào hàng đợi của ExoPlayer (một MediaItem mỗi đoạn, `mediaId` = mã chương, `tag` = [Slot]) nên chuyển đoạn
 * liền mạch, và sang chương kế cũng chỉ là nối tiếp đoạn. Chương audio xen giữa (sách nửa chữ nửa tiếng) nối vào cùng hàng đợi. Giao diện thấy MỘT đồng hồ
 * chương ([VirtualTimeline]): vị trí = mốc đầu đoạn + vị trí trong đoạn.
 *
 * Mọi trạng thái chỉ đụng ở luồng chính; luồng nền chỉ đọc đoạn rồi `Playback.onMain` trả kết quả. Mỗi lần nhảy (tua, đổi chương, đổi giọng) tăng `generation`: kết
 * quả của việc cũ tới muộn bị bỏ.
 */
object ReadAloud {
    const val DEFAULT_VOICE = "edge:vi-VN-HoaiMyNeural"
    /** Đoạn đọc trước: đang nghe + chừng này đoạn sau. */
    const val AHEAD = 2

    /** Gắn vào MediaItem của một đoạn: chương (vị trí trong danh sách chương), đoạn, độ to của giọng đã đọc. `segment` -1 = không dùng. */
    class Slot(val chapterIndex: Int, val segment: Int, val gainDb: Double)

    private class Chap(val index: Int, val paragraphs: List<String>) {
        val timeline = VirtualTimeline(IntArray(paragraphs.size) { paragraphs[it].length })
        val clips = arrayOfNulls<Clip>(paragraphs.size)
    }

    /** Chỗ cần phát mà chưa có đoạn âm thanh để đặt vào ExoPlayer: đang chờ đọc. `word` >= 0 thắng `offsetMs` (bắt đầu đúng chữ ấy). */
    private class Target(val chapterIndex: Int, val segment: Int, val offsetMs: Long, val word: Int, var play: Boolean)

    private var context: Context? = null
    private var reader: ClipReader? = null
    // Hai luồng: lần tua mới không phải đợi việc cũ (Edge có thể treo tới hạn 45 giây); giọng của máy tự xếp hàng riêng (DeviceEngine).
    private val worker = Executors.newFixedThreadPool(2) { Thread(it, "read-aloud").apply { isDaemon = true } }

    /** Giọng đang chọn ("edge:..." / "device:..."); đổi bằng [setVoice]. */
    var voiceId: String = DEFAULT_VOICE
        private set

    /** Cuốn đang nạp có chương chữ: hàng đợi do lõi này quản (không phải bản ExoPlayer tự chạy hết danh sách chương). */
    var active = false
        private set

    private val chaps = HashMap<Int, Chap>()
    private var generation = 0
    private var inFlight = false
    private var feedChapter = 0
    private var feedSegment = 0
    private var waiting: Target? = null
    private var failure: String? = null
    private var artwork: ByteArray? = null
    private val scriptListeners = mutableSetOf<(String, Int) -> Unit>()

    fun init(appContext: Context) {
        if (context != null) return
        context = appContext.applicationContext
        choices = VoiceChoices(File(appContext.applicationContext.filesDir, "readaloud-voices.json"))
    }

    /** Giọng đã chọn của từng cuốn, nhớ trong lõi ([VoiceChoices]). */
    private var choices: VoiceChoices? = null

    private var cache: ClipCache? = null

    @Synchronized
    private fun cache(): ClipCache = cache ?: run {
        val ctx = context ?: throw VoiceException("Chưa khởi động")
        ClipCache(File(ctx.cacheDir, "readaloud")).also { cache = it }
    }

    @Synchronized
    private fun reader(): ClipReader = reader ?: run {
        val ctx = context ?: throw VoiceException("Chưa khởi động")
        // Giọng dùng khoá hỏng (khoá bị từ chối, hết hạn mức, mất mạng): Edge đỡ trước giọng của máy; mỗi chuyện báo người nghe một lần.
        ClipReader(cache(), ::voiceFor, { fallbackVoice(ctx) }, onlineFallback = { EdgeTts("vi-VN-HoaiMyNeural") }, notice = ::notice).also { reader = it }
    }

    private fun voiceFor(id: String): Voice {
        val (provider, name) = ClipCache.split(id)
        return when (provider) {
            "edge" -> EdgeTts(name.ifEmpty { "vi-VN-HoaiMyNeural" })
            "device" -> DeviceTts(context ?: throw VoiceException("Chưa khởi động"), name)
            else -> OnlineVoices.voiceFor(context ?: throw VoiceException("Chưa khởi động"), id) ?: throw VoiceException("Giọng lạ: $id")
        }
    }

    private fun fallbackVoice(ctx: Context): Voice? =
        DeviceTts.defaultId(ctx)?.let { DeviceTts(ctx, it.removePrefix("device:")) }

    fun addScriptListener(listener: (String, Int) -> Unit) { scriptListeners += listener }
    fun removeScriptListener(listener: (String, Int) -> Unit) { scriptListeners -= listener }

    private val noticeListeners = mutableSetOf<(String) -> Unit>()
    fun addNoticeListener(listener: (String) -> Unit) { noticeListeners += listener }
    fun removeNoticeListener(listener: (String) -> Unit) { noticeListeners -= listener }
    private fun notice(message: String) = Playback.onMain { noticeListeners.toList().forEach { runCatching { it(message) } } }

    /** "Thử giọng" (Cài đặt): đúng giọng này đọc `text` (qua bộ đệm), trả file âm thanh. Chạy ở luồng nền. */
    fun sample(id: String, text: String): File = reader().readExactly(text, id).file

    // ---- giọng ----------------------------------------------------------------------------------------------

    /** Danh sách giọng cho giao diện (chạy ở luồng nền - hỏi bộ đọc của máy có thể chờ). */
    fun voices(ctx: Context): List<JSONObject> {
        val list = ArrayList<VoiceInfo>()
        list.add(VoiceInfo("edge:vi-VN-HoaiMyNeural", "Hoài My (Edge)", "edge", true, true, "female"))
        list.add(VoiceInfo("edge:vi-VN-NamMinhNeural", "Nam Minh (Edge)", "edge", true, false, "male"))
        list.addAll(OnlineVoices.voices(ctx)) // giọng dùng khoá của người dùng: chỉ khi khoá đã kiểm tra được
        list.addAll(DeviceTts.voices(ctx))
        return list.map {
            JSONObject().put("id", it.id).put("name", it.name).put("provider", it.provider).put("online", it.online)
                .put("default", it.default).put("gender", it.gender).put("gainDb", VoiceGain.db(it.id))
        }
    }

    /** Giao diện gửi giọng của cuốn `bookId` (lúc nạp, lúc người nghe đổi): nhớ cho cuốn ấy; cuốn ấy đang nạp thì đổi ngay. */
    fun chooseFor(bookId: String, id: String) {
        choices?.remember(bookId, id)
        if (bookId.isEmpty() || bookId == Playback.bookId) setVoice(id)
    }

    /** Nạp một cuốn - bằng bất cứ đường nào (giao diện, widget, xe hơi, máy tính điều khiển): đọc bằng giọng đã nhớ của cuốn ấy. Chỉ đặt giọng;
     *  [begin] / [stop] ngay sau đó dựng lại hàng đợi. */
    fun useVoiceOf(bookId: String) {
        voiceId = choices?.voiceFor(bookId)?.ifBlank { null } ?: DEFAULT_VOICE
    }

    /** Đổi giọng: các đoạn đã đọc sẵn mà chưa tới thì bỏ, đoạn kế đọc bằng giọng mới. */
    fun setVoice(id: String) {
        val value = id.ifBlank { DEFAULT_VOICE }
        if (value == voiceId) return
        voiceId = value
        if (!active) return
        val exo = Playback.player ?: return
        val slot = currentSlot() ?: return
        if (slot.segment < 0) return
        generation += 1
        inFlight = false
        failure = null
        val index = exo.currentMediaItemIndex
        if (exo.mediaItemCount > index + 1) exo.removeMediaItems(index + 1, exo.mediaItemCount)
        feedChapter = slot.chapterIndex
        feedSegment = slot.segment + 1
        pump()
    }

    // ---- trạng thái cho Playback ---------------------------------------------------------------------------

    private fun currentSlot(): Slot? = Playback.player?.currentMediaItem?.localConfiguration?.tag as? Slot

    /** Đang ở chương chữ (đoạn đang phát hay đang chờ đọc đoạn đầu). */
    fun inText(): Boolean = active && (currentSlot()?.segment?.let { it >= 0 } == true || waiting?.let { chapters().getOrNull(it.chapterIndex)?.isText } == true)

    private fun chapters() = Playback.chapters

    private fun chapterIndexNow(): Int? = currentSlot()?.takeIf { it.segment >= 0 }?.chapterIndex ?: waiting?.chapterIndex

    /** Mã chương đang chờ đọc (ExoPlayer chưa có gì để phát). */
    fun waitingChapterId(): Int? = waiting?.let { chapters().getOrNull(it.chapterIndex)?.id }

    val isWaiting: Boolean get() = waiting != null && failure == null

    /** Người nghe muốn đang phát (kể cả lúc chờ đọc đoạn). */
    fun wantsPlay(): Boolean = waiting?.play ?: (Playback.player?.playWhenReady == true)

    /** Vị trí ảo trong chương (ms), null nếu không ở chương chữ. */
    fun positionMs(): Long? = chapterMs(Playback.player?.currentPosition ?: 0L)

    /**
     * Mốc `clipMs` của đoạn đang phát, đổi sang đồng hồ ảo của chương (ms); đang chờ đọc đoạn thì là chỗ sẽ bắt đầu. null nếu không ở chương chữ. Cũng dùng cho
     * mốc đã đệm tới (thanh tiến độ ở thông báo / màn hình khoá - PlaybackService).
     */
    fun chapterMs(clipMs: Long): Long? {
        if (!active) return null
        val slot = currentSlot()
        if (slot != null && slot.segment >= 0) {
            val chap = chaps[slot.chapterIndex] ?: return null
            val clip = chap.clips[slot.segment]
            val inClip = clipMs.coerceIn(0L, clip?.durationMs ?: Long.MAX_VALUE)
            return chap.timeline.startOf(slot.segment) + inClip
        }
        val target = waiting ?: return null
        val chap = chaps[target.chapterIndex] ?: return null
        if (!chapters().getOrNull(target.chapterIndex)!!.isText) return null
        return chap.timeline.startOf(target.segment) + target.offsetMs
    }

    /** Độ dài ảo của chương (ms): phần đã đọc + ước lượng phần còn lại. */
    fun durationMs(): Long? {
        if (!active) return null
        val index = chapterIndexNow() ?: return null
        return chaps[index]?.timeline?.totalMs()
    }

    /** Hệ số to/nhỏ của giọng đang phát (1 nếu không phải đoạn đọc to). */
    fun gainFactor(): Float = currentSlot()?.takeIf { it.segment >= 0 }?.let { VoiceGain.factor(it.gainDb) } ?: 1f

    // ---- nạp / dừng -----------------------------------------------------------------------------------------

    /** Nạp cuốn có chương chữ: bắt đầu ở chương `index`, `offsetMs` trong chương. */
    fun begin(index: Int, offsetMs: Long, autoplay: Boolean) {
        reset()
        active = true
        artwork = Artwork.cover(Playback.bookTitle, Playback.bookId)
        startAt(index, offsetMs, autoplay)
    }

    /** Hết cuốn / sang cuốn khác / dịch vụ tắt: bỏ việc đang làm, quên mọi chương. */
    fun stop() {
        reset()
    }

    private fun reset() {
        active = false
        generation += 1
        inFlight = false
        waiting = null
        failure = null
        chaps.clear()
        feedChapter = 0
        feedSegment = 0
    }

    private fun chapFor(index: Int): Chap? {
        chaps[index]?.let { return it }
        val chapter = chapters().getOrNull(index) ?: return null
        if (!chapter.isText) return null
        return try {
            val text = Store.file(Playback.bookId, chapter.text).readText(Charsets.UTF_8)
            Chap(index, Paragraphs.of(text)).also {
                fromCache(it)
                chaps[index] = it
            }
        } catch (error: Exception) {
            null
        }
    }

    /**
     * Phát từ chương `index`: `segment` >= 0 thì từ đoạn ấy (`word` >= 0: từ đúng chữ ấy), không thì từ mốc `offsetMs` của chương. Chương chữ: xoá hàng đợi và đợi đoạn
     * âm thanh đầu tiên (giao diện thấy `buffering`); chương audio: đặt ngay.
     */
    fun startAt(index: Int, offsetMs: Long, play: Boolean, segment: Int = -1, word: Int = -1, within: Long = 0) {
        val exo = Playback.player ?: return
        val chapter = chapters().getOrNull(index) ?: return
        generation += 1
        inFlight = false
        failure = null
        feedChapter = index
        feedSegment = 0
        if (!chapter.isText) {
            waiting = Target(index, 0, offsetMs, -1, play)
            pump()
            return
        }
        val chap = chapFor(index)
        if (chap == null) {
            waiting = Target(index, 0, 0, -1, play)
            fail("Không đọc được chữ của chương “${chapter.title}”")
            return
        }
        val seg = if (chap.paragraphs.isEmpty()) 0 else if (segment >= 0) segment.coerceIn(0, chap.paragraphs.size - 1) else chap.timeline.segmentAt(offsetMs)
        val inside = if (chap.paragraphs.isEmpty()) 0L else if (segment >= 0) within else (offsetMs - chap.timeline.startOf(seg)).coerceAtLeast(0)
        waiting = Target(index, seg, inside, word, play)
        feedSegment = seg
        exo.pauseAtEndOfMediaItems = false
        exo.clearMediaItems()
        exo.playWhenReady = play
        Playback.emit("state")
        pump()
    }

    /**
     * Tua trong chương hiện tại tới `ms` (hay tới chữ `word` của đoạn `segment`). Đoạn đã có âm thanh và đang nằm trong hàng đợi: nhảy thẳng tới ĐÚNG chỗ trong đoạn
     * (không về đầu đoạn). Chưa có (chưa đọc, hay đã bỏ khỏi hàng đợi): đọc đoạn ấy rồi mới phát từ chỗ đó. Trả false nếu đang ở chương audio (để ExoPlayer tự tua).
     */
    fun seekMs(ms: Long, segment: Int = -1, word: Int = -1): Boolean {
        if (!active) return false
        val exo = Playback.player ?: return false
        val index = chapterIndexNow() ?: return false
        val chap = chaps[index] ?: return false
        val plan = SeekPlan.plan(
            chap.timeline, { chap.clips.getOrNull(it) },
            { seg -> (0 until exo.mediaItemCount).any { i -> (exo.getMediaItemAt(i).localConfiguration?.tag as? Slot)?.let { it.chapterIndex == index && it.segment == seg } == true } },
            ms, segment, word,
        )
        when (plan) {
            is SeekPlan.Plan.InClip -> {
                val at = (0 until exo.mediaItemCount).first { i -> (exo.getMediaItemAt(i).localConfiguration?.tag as? Slot)?.let { it.chapterIndex == index && it.segment == plan.segment } == true }
                exo.seekTo(at, plan.positionMs)
            }
            is SeekPlan.Plan.Synthesize -> startAt(index, 0, wantsPlay(), plan.segment, plan.word, plan.offsetMs)
        }
        return true
    }

    /** Sang chương `index` (nút Sau/Trước, danh sách chương, giao diện nhảy thẳng tới chữ). */
    fun jump(index: Int, ms: Long, segment: Int = -1, word: Int = -1) {
        if (index == chapterIndexNow() && seekMs(ms, segment, word)) {
            waiting?.play = true
            Playback.player?.play()
            return
        }
        startAt(index, ms, true, segment, word)
    }

    // ---- nạp đoạn -------------------------------------------------------------------------------------------

    /** Giữ hàng đợi có đoạn kế: gọi mỗi khi đoạn đổi, đoạn mới sẵn sàng, đổi giọng, hủy hẹn giờ. */
    fun pump() {
        if (!active || inFlight || failure != null) return
        val exo = Playback.player ?: return
        val all = chapters()
        var guard = 0
        while (guard++ < 8) {
            val ahead = if (waiting != null) 0 else (exo.mediaItemCount - 1 - exo.currentMediaItemIndex).coerceAtLeast(0)
            if (ahead >= AHEAD) return
            if (feedChapter >= all.size) return
            val chapter = all[feedChapter]
            if (!chapter.isText) {
                appendAudioRun(all)
                continue
            }
            val chap = chapFor(feedChapter)
            if (chap == null) {
                fail("Không đọc được chữ của chương “${chapter.title}”")
                return
            }
            if (feedSegment >= chap.paragraphs.size) {
                if (feedChapter + 1 >= all.size) {
                    if (waiting != null) fail("Chương “${chapter.title}” không có chữ để đọc")
                    return
                }
                // Hẹn giờ "hết chương": dừng nạp ở cuối chương này để ExoPlayer tự dừng đúng chỗ (handleEnded).
                if (SleepTimer.mode == SleepTimer.Mode.CHAPTER && waiting == null) return
                feedChapter += 1
                feedSegment = 0
                continue
            }
            startJob(chap, feedSegment)
            return
        }
    }

    private fun appendAudioRun(all: List<Playback.Chapter>) {
        var end = feedChapter
        while (end < all.size && !all[end].isText) end += 1
        val run = all.subList(feedChapter, end)
        val items = Playback.mediaItems(Playback.bookId, Playback.bookTitle, Playback.narrator, run)
        val offset = waiting?.takeIf { it.chapterIndex == feedChapter }?.offsetMs ?: 0L
        feedChapter = end
        feedSegment = 0
        deliver(items, offset)
    }

    /** Đặt `items` vào ExoPlayer: đang chờ chỗ bắt đầu thì thay cả hàng đợi, không thì nối đuôi. */
    private fun deliver(items: List<MediaItem>, offsetMs: Long) {
        val exo = Playback.player ?: return
        val target = waiting
        if (target != null) {
            waiting = null
            exo.setMediaItems(items, 0, offsetMs)
            exo.prepare()
            exo.playWhenReady = target.play
        } else {
            exo.addMediaItems(items)
            // Hàng đợi vừa cạn (đọc chậm hơn nghe): ExoPlayer đã ENDED, nối thêm không chắc tự phát tiếp - đặt chỗ phát rõ ràng.
            if (exo.playbackState == Player.STATE_ENDED) exo.seekTo(exo.mediaItemCount - items.size, 0)
        }
    }

    private fun startJob(chap: Chap, segment: Int) {
        val token = generation
        val text = chap.paragraphs[segment]
        val voice = voiceId
        inFlight = true
        worker.execute {
            val result = runCatching { reader().read(text, voice) }
            Playback.onMain { onClipReady(token, chap, segment, result) }
        }
    }

    private fun onClipReady(token: Int, chap: Chap, segment: Int, result: Result<Clip>) {
        if (token != generation || !active) return
        inFlight = false
        val clip = result.getOrElse { error ->
            fail((error as? VoiceException)?.message ?: "Không đọc được đoạn này (${error.message})")
            return
        }
        chap.clips[segment] = clip
        chap.timeline.setDuration(segment, clip.durationMs)
        val item = clipItem(chap, segment, clip)
        val target = waiting
        // Dời chỗ nạp TRƯỚC khi đặt vào ExoPlayer: setMediaItems báo đổi mục ngay trong lúc gọi (onMediaTransition -> onClipChanged -> pump), và pump lúc ấy
        // mà còn thấy đoạn này là "đoạn kế" thì đọc lại nó - hàng đợi có hai lần cùng một đoạn, đồng hồ ảo lùi về đầu đoạn (thấy 03-10 trên máy thật).
        feedSegment = segment + 1
        deliver(listOf(item), if (target != null) SeekPlan.offsetIn(clip, target.word, target.offsetMs) else 0L)
        notifyScript(chap)
        prune()
        pump()
        Playback.emit("state")
    }

    private fun clipItem(chap: Chap, segment: Int, clip: Clip): MediaItem {
        val chapter = chapters()[chap.index]
        val metadata = MediaMetadata.Builder()
            .setTitle(chapter.title).setArtist(Playback.narrator.ifBlank { null }).setAlbumTitle(Playback.bookTitle)
            .setDisplayTitle(chapter.title).setSubtitle(Playback.bookTitle)
        artwork?.let { metadata.setArtworkData(it, MediaMetadata.PICTURE_TYPE_FRONT_COVER) }
        return MediaItem.Builder()
            .setMediaId(chapter.id.toString())
            .setUri(Uri.fromFile(clip.file))
            .setTag(Slot(chap.index, segment, VoiceGain.db(clip.voice)))
            .setMediaMetadata(metadata.build())
            .build()
    }

    /** Bỏ các đoạn đã phát xa (chỉ giữ một đoạn ngay trước đoạn đang nghe để tua lùi ngắn) cho hàng đợi không dài ra mãi. */
    private fun prune() {
        val exo = Playback.player ?: return
        val index = exo.currentMediaItemIndex
        if (index > 1) exo.removeMediaItems(0, index - 1)
    }

    /** ExoPlayer vừa sang một đoạn (hay mục) khác. */
    fun onClipChanged() {
        if (!active) return
        val live = currentSlot()?.takeIf { it.segment >= 0 }?.chapterIndex
        chaps.keys.retainAll { it == live || it == feedChapter || it == waiting?.chapterIndex }
        prune()
        pump()
    }

    /**
     * ExoPlayer chạy hết hàng đợi. True = đã xử lý (đang chờ đọc đoạn kế, hay dừng vì hẹn giờ, hay sang chương kế); false = hết cuốn thật.
     */
    fun handleEnded(): Boolean {
        if (!active) return false
        if (waiting != null || inFlight || failure != null) return true
        pump()
        if (inFlight || waiting != null || failure != null) return true
        if (SleepTimer.mode == SleepTimer.Mode.CHAPTER) {
            SleepTimer.onPausedAtChapterEnd()
            Playback.saveNow()
            Playback.emit("pause")
            return true
        }
        val current = Playback.currentChapter ?: return false
        val index = chapters().indexOfFirst { it.id == current.id }
        if (index in 0 until chapters().size - 1 && feedChapter > index) {
            startAt(index + 1, 0, true)
            return true
        }
        return false
    }

    /** Hẹn giờ "hết chương" vừa bật lúc đang đọc to: bỏ các đoạn của chương SAU đã nạp sẵn để hàng đợi cạn đúng cuối chương này. */
    fun stopAtChapterEnd() {
        val exo = Playback.player ?: return
        val slot = currentSlot()?.takeIf { it.segment >= 0 } ?: return
        var first = -1
        for (i in exo.currentMediaItemIndex + 1 until exo.mediaItemCount) {
            val other = exo.getMediaItemAt(i).localConfiguration?.tag as? Slot
            if (other == null || other.chapterIndex != slot.chapterIndex) {
                first = i
                break
            }
        }
        if (first >= 0) exo.removeMediaItems(first, exo.mediaItemCount)
        if (first >= 0 || feedChapter != slot.chapterIndex) {
            generation += 1
            inFlight = false
            val last = (exo.getMediaItemAt(exo.mediaItemCount - 1).localConfiguration?.tag as? Slot)?.takeIf { it.chapterIndex == slot.chapterIndex }
            feedChapter = slot.chapterIndex
            feedSegment = (last?.segment ?: slot.segment) + 1
        }
    }

    /** Chưa biết đang ở đâu trong chương (chương chữ không đọc được chữ): đừng lưu vị trí 0 đè chỗ nghe dở. */
    fun unknownPlace(): Boolean = active && Playback.player?.currentMediaItem == null && positionMs() == null

    /**
     * Người nghe bấm phát. True = đã xử lý hết (lỗi đọc: thử lại đúng đoạn hỏng; hàng đợi đã chạy hết: đọc lại từ chỗ đang đứng); false = để Playback phát như thường
     * (đang chờ đọc đoạn thì chỉ ghi nhớ là muốn phát).
     */
    fun onPlay(): Boolean {
        if (!active) return false
        if (retryAfterFailure()) return true
        waiting?.play = true
        val exo = Playback.player ?: return false
        if (waiting == null && !inFlight && exo.playbackState == Player.STATE_ENDED && inText()) {
            val index = chapterIndexNow() ?: return false
            val ms = positionMs() ?: return false
            startAt(index, ms, true)
            return true
        }
        return false
    }

    /** Người nghe bấm dừng lúc đang chờ đọc đoạn đầu: khi đoạn tới thì đừng tự phát. */
    fun onPause() {
        waiting?.play = false
    }

    private var recoveries = ArrayDeque<Long>()

    /** ExoPlayer lỗi lúc phát một đoạn (file đã bị dọn khỏi bộ nhớ đệm...): đọc lại đúng chỗ, tối đa 3 lần trong 30 giây. True nếu đã xử lý. */
    fun recoverFromPlayerError(): Boolean {
        if (!active || currentSlot()?.segment?.let { it >= 0 } != true) return false
        val now = System.currentTimeMillis()
        while (recoveries.isNotEmpty() && now - recoveries.first() > 30_000) recoveries.removeFirst()
        if (recoveries.size >= 3) return false
        recoveries.addLast(now)
        val index = chapterIndexNow() ?: return false
        val ms = positionMs() ?: return false
        val slot = currentSlot()!!
        chaps[index]?.clips?.set(slot.segment, null)
        startAt(index, ms, true)
        return true
    }

    /** Bấm phát sau một lỗi đọc: thử lại đúng chỗ đã hỏng. True nếu đã nhận. */
    fun retryAfterFailure(): Boolean {
        if (!active || failure == null) return false
        failure = null
        Playback.clearError()
        val target = waiting
        if (target != null) startAt(target.chapterIndex, 0, true, target.segment, target.word, target.offsetMs)
        else {
            Playback.player?.playWhenReady = true
            pump()
        }
        return true
    }

    private fun fail(message: String) {
        failure = message
        inFlight = false
        Playback.fail(message)
    }

    // ---- kịch bản (mốc thời gian) cho màn đọc -----------------------------------------------------------------

    private fun notifyScript(chap: Chap) {
        val id = chapters().getOrNull(chap.index)?.id ?: return
        val book = Playback.bookId
        scriptListeners.toList().forEach { runCatching { it(book, id) } }
    }

    /**
     * Mốc các đoạn của một chương cho màn đọc (cùng đồng hồ với kịch bản audio của Studio: giây từ đầu chương cho câu, ms từ đầu chương cho từng chữ). Đoạn
     * chưa đọc: `words` rỗng, `start`/`end` là ước lượng. Chương đang nạp lấy từ đồng hồ ảo; chương khác chỉ thấy các đoạn còn trong bộ nhớ đệm. Phải gọi trên
     * luồng chính nếu cuốn đang nạp.
     */
    fun script(bookId: String, chapterId: Int): JSONObject {
        val chap = if (bookId == Playback.bookId && active) {
            chapters().indexOfFirst { it.id == chapterId }.takeIf { it >= 0 }?.let(::chapFor)
        } else {
            peek(bookId, chapterId)
        }
        val segments = JSONArray()
        if (chap != null) {
            for (i in chap.paragraphs.indices) {
                val start = chap.timeline.startOf(i)
                val words = JSONArray()
                chap.clips[i]?.words?.forEach { words.put(JSONArray().put(start + it.start).put(start + it.end)) }
                segments.put(JSONObject().put("index", i).put("start", start / 1000.0).put("end", chap.timeline.endOf(i) / 1000.0).put("words", words)
                    .put("timed", chap.clips[i] != null))
            }
        }
        return JSONObject().put("segments", segments)
    }

    /**
     * Đoạn nào đã đọc bằng giọng đang chọn (còn trong bộ nhớ đệm) thì đồng hồ ảo dùng độ dài thật ngay từ lúc nạp chương: nghe tiếp từ giây đã lưu (widget, xe
     * hơi, mở lại app) rơi đúng đoạn đã nghe, không lệch theo ước lượng 14 ký tự/giây.
     */
    private fun fromCache(chap: Chap) {
        val cache = runCatching { cache() }.getOrNull() ?: return
        for (i in chap.paragraphs.indices) cache.get(voiceId, chap.paragraphs[i])?.let {
            chap.clips[i] = it
            chap.timeline.setDuration(i, it.durationMs)
        }
    }

    /** Chương của một cuốn không đang nạp: chữ từ gói sách, mốc từ bộ nhớ đệm (nếu đoạn đã từng được đọc bằng giọng đang chọn). */
    private fun peek(bookId: String, chapterId: Int): Chap? {
        return try {
            val array = Store.manifest(bookId)?.optJSONArray("chapters") ?: return null
            val chapter = (0 until array.length()).map { array.getJSONObject(it) }.firstOrNull { it.optInt("id") == chapterId } ?: return null
            val entry = chapter.optString("text").takeIf { it.startsWith("texts/") } ?: return null
            Chap(-1, Paragraphs.of(Store.file(bookId, entry).readText(Charsets.UTF_8))).also(::fromCache)
        } catch (error: Exception) {
            null
        }
    }
}
