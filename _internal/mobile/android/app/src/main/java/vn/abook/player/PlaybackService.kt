package vn.abook.player

import android.app.PendingIntent
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.annotation.OptIn
import androidx.core.content.FileProvider
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.ForwardingPlayer
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.Timeline
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.audio.AudioSink
import androidx.media3.exoplayer.audio.DefaultAudioSink
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.LoadControl
import androidx.media3.session.CommandButton
import androidx.media3.session.DefaultMediaNotificationProvider
import androidx.media3.session.LibraryResult
import androidx.media3.session.MediaLibraryService
import androidx.media3.session.MediaLibraryService.LibraryParams
import androidx.media3.session.MediaLibraryService.MediaLibrarySession
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import androidx.media3.session.SessionCommand
import androidx.media3.session.SessionError
import androidx.media3.session.SessionResult
import com.google.common.collect.ImmutableList
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture
import com.google.common.util.concurrent.SettableFuture
import java.util.concurrent.Executors
import java.util.concurrent.Executor
import java.io.File
import java.security.MessageDigest
import vn.abook.player.readaloud.ReadAloud
import vn.abook.player.ui.NativeActivity
import vn.abook.player.ui.nowplaying.SleepText

/**
 * Dịch vụ phát nền: giữ ExoPlayer sống khi tắt màn hình, hiện điều khiển ở thanh thông báo và màn hình khoá,
 * nhận nút tai nghe/Bluetooth, tự dừng khi rút tai nghe hoặc có cuộc gọi (audio focus).
 *
 * Thanh thông báo: lùi 15 giây · phát/dừng · tới 15 giây; mở rộng thêm Đóng (X), chương trước / chương sau và - khi đang hẹn giờ ngủ - "Hẹn lại N phút".
 * Dừng thì dịch vụ còn ở tiền cảnh [foregroundGraceMs] rồi mới rời (thẻ vuốt bỏ được từ lúc ấy); Đóng thì cất sách và tắt hẳn.
 *
 * Là MediaLibraryService: Android Auto và trình duyệt media của hệ thống duyệt được thư viện trên máy (LibraryTree:
 * sách -> chương) và chọn phát ngay trên màn hình xe.
 */
class PlaybackService : MediaLibraryService() {
    private var session: MediaLibrarySession? = null
    private val sleepButtons = SleepTimer.buttonsListener { refreshButtons() }
    private val libraryIo = Executors.newSingleThreadExecutor { Thread(it, "abook-library").apply { isDaemon = true } }
    private val playerLooper = Executor { task -> Playback.onMain { task.run() } }
    private var destroyed = false

    /** Read library, artwork and file stamps off the player looper; apply the prepared result on that looper. */
    private fun <T, R> libraryTask(read: () -> T, apply: (T) -> R): ListenableFuture<R> {
        val result = SettableFuture.create<R>()
        libraryIo.execute {
            try {
                val value = read()
                playerLooper.execute {
                    if (!result.isCancelled) {
                        if (destroyed) result.setException(IllegalStateException("Playback service destroyed"))
                        else try { result.set(apply(value)) } catch (error: Exception) { result.setException(error) }
                    }
                }
            } catch (error: Exception) { result.setException(error) }
        }
        return result
    }

    private data class QueueBook(val id: String, val title: String, val narrator: String, val chapters: List<Playback.Chapter>,
                                 val index: Int, val seconds: Double, val rate: Double, val prepared: Playback.PreparedBook)

    private fun prepareQueue(manifest: org.json.JSONObject, state: org.json.JSONObject, chapter: Int, seconds: Double, preview: Boolean = false): QueueBook {
        val id = manifest.getString("id")
        val title = manifest.optString("title")
        val narrator = manifest.optString("narrator")
        val chapters = Playback.chaptersOf(manifest)
        require(chapters.isNotEmpty()) { S.s_cuon_nay_khong_con_tren_may_de91299f }
        val prepared = Playback.prepareBook(id, title, narrator, chapters)
        return QueueBook(id, title, narrator, chapters, chapters.indexOfFirst { it.id == chapter }.coerceAtLeast(0), seconds,
            state.optDouble("rate", 1.0).takeIf { it.isFinite() && it > 0 } ?: 1.0,
            if (preview && chapters.any { it.isText }) prepared.copy(media = Playback.mediaItems(id, title, narrator, chapters)) else prepared)
    }

    private fun applyQueue(book: QueueBook, forPlayback: Boolean): MediaSession.MediaItemsWithStartPosition = with(book) {
        if (forPlayback) {
            check(Store.knownActiveRecord(id) == prepared.record) { S.s_cuon_nay_khong_con_tren_may_de91299f }
            val chapter = chapters[index].id
            if (chapters.any { it.isText }) {
                Playback.load(id, title, narrator, chapters, chapter, seconds, rate, prepared = prepared)
                return@with MediaSession.MediaItemsWithStartPosition(listOf(READ_ALOUD), 0, 0)
            }
            Playback.adopt(id, title, narrator, chapters, chapter, seconds, rate, prepared)
        }
        MediaSession.MediaItemsWithStartPosition(prepared.media, index, (seconds * 1000).toLong())
    }

    internal fun resumeQueue(forPlayback: Boolean): ListenableFuture<MediaSession.MediaItemsWithStartPosition> {
        if (forPlayback && ReadAloud.active) return readAloudQueue()
        return libraryTask({
            val (manifest, last) = Playback.lastListened() ?: throw UnsupportedOperationException(S.s_chua_nghe_sach_nao_f2635716)
            prepareQueue(manifest, Store.state(manifest.getString("id")), last.optInt("chapterId"), last.optDouble("seconds"), preview = !forPlayback)
        }) { applyQueue(it, forPlayback) }
    }

    companion object {
        /**
         * Âm thanh phải có sẵn (ms) trước khi ExoPlayer bắt đầu phát một nguồn KHÔNG nằm trên máy - đoạn Edge đang phát luồng (`abooklive://`), chương phát từ máy tính - và sau khi
         * cạn giữa chừng. media3 1.11.1 mặc định 1000 / 2000; đoạn luồng nhận tiếng nhanh hơn nghe nên chờ ít hơn là người nghe nghe sớm hơn chừng ấy (soát a59p). File trên máy giữ mặc định
         * của nó. Đo lại bằng LiveStreamOnDeviceTest (readyMs - firstByteMs) trước khi đổi.
         */
        const val STREAM_START_BUFFER_MS = 750
        const val STREAM_REBUFFER_MS = 1500

        /** Mức đệm của ExoPlayer phát sách (cả LiveStreamOnDeviceTest dùng, để số đo là của đúng cấu hình này). */
        @OptIn(UnstableApi::class)
        fun loadControl(): LoadControl = DefaultLoadControl.Builder().setBufferDurationsMsForStreaming(
            DefaultLoadControl.DEFAULT_MIN_BUFFER_MS, DefaultLoadControl.DEFAULT_MAX_BUFFER_MS, STREAM_START_BUFFER_MS, STREAM_REBUFFER_MS,
        ).build()

        val SLEEP_PLUS by lazy { SessionCommand("vn.abook.SLEEP_PLUS", Bundle.EMPTY) }
        // Chương trước/sau là lệnh riêng của app: Trước/Sau của phiên media (tai nghe, xe, đồng hồ) là lùi/tới 15 giây (HeadsetSkips).
        val PREVIOUS_CHAPTER by lazy { SessionCommand("vn.abook.PREVIOUS_CHAPTER", Bundle.EMPTY) }
        val NEXT_CHAPTER by lazy { SessionCommand("vn.abook.NEXT_CHAPTER", Bundle.EMPTY) }
        val CLOSE by lazy { SessionCommand("vn.abook.CLOSE", Bundle.EMPTY) }
        var instance: PlaybackService? = null
            private set

        /** Mục giả trả cho phiên media khi lõi đã tự nạp một cuốn có chương chữ (đọc to): [HeadsetSkips] bỏ qua nó thay vì đặt vào ExoPlayer. */
        private val READ_ALOUD by lazy { MediaItem.Builder().setMediaId("abook:read-aloud").build() }

        private fun isReadAloud(items: List<MediaItem>) = items.singleOrNull()?.mediaId == READ_ALOUD.mediaId

        private fun readAloudQueue(): ListenableFuture<MediaSession.MediaItemsWithStartPosition> =
            Futures.immediateFuture(MediaSession.MediaItemsWithStartPosition(listOf(READ_ALOUD), 0, 0))

        /**
         * Dừng rồi thì dịch vụ còn giữ tiền cảnh bao lâu. Android 12+ chỉ cho dịch vụ đã rời tiền cảnh lên lại khi NGƯỜI NGHE bấm (thông báo, widget, nút
         * media); các đường phát tiếp từ nền của app - lắc để nghe tiếp sau khi hẹn giờ tự dừng ([SleepTimer.SHAKE_RESUME_MS]), lật máy lên
         * ([Motion.FLIP_RESUME_MS], khi bật úp máy để dừng), lệnh phát từ máy tính ([Remote]) - phải tới trong lúc dịch vụ chưa rời. Hết hạn thì thẻ vuốt bỏ được như trước.
         */
        internal fun foregroundGraceMs(flipEnabled: Boolean, shakeEnabled: Boolean = SleepTimer.shakeEnabled): Long =
            if (flipEnabled || shakeEnabled) Motion.FLIP_RESUME_MS else SleepTimer.SHAKE_RESUME_MS
    }

    /** Đặt lại hạn giữ tiền cảnh theo công tắc úp máy hiện tại ([foregroundGraceMs]); ListenPrefs gọi khi công tắc đổi. */
    @OptIn(UnstableApi::class)
    fun applyForegroundGrace() = setForegroundServiceTimeoutMs(foregroundGraceMs(Motion.flipEnabled))

    /**
     * Android không cho dịch vụ lên lại tiền cảnh (phát tiếp từ nền khi đã quá [foregroundGraceMs]): tiếng chạy không có dịch vụ tiền cảnh thì ColorOS
     * đóng băng / giết tiến trình sau vài phút tắt màn hình, nghe giữa chừng là mất. Không để thế: ghi log rồi dừng đúng chỗ (lưu chỗ nghe) - nút Phát
     * trên thẻ thông báo là đường hệ thống cho phép, bấm là nghe tiếp đúng chỗ ấy. Không qua [Playback.pause]: đây không phải người nghe chạm máy (hẹn tự động không bị huỷ).
     */
    internal fun foregroundRefused() {
        AppLog.w("PlaybackService", S.s_android_khong_cho_phat_tiep_tu_nen_3c41e7a2)
        Playback.onMain {
            ReadAloud.onPause()
            Playback.fail(S.s_android_khong_cho_phat_tiep_tu_nen_3c41e7a2)
        }
    }

    @OptIn(UnstableApi::class)
    override fun onCreate() {
        super.onCreate()
        instance = this
        AppLog.i("PlaybackService", S.s_dich_vu_phat_bat_da10337c)
        Playback.init(this)
        ListenerActivity.start(this)
        Playback.addListener(sleepButtons)
        val renderers = object : DefaultRenderersFactory(this) {
            override fun buildAudioSink(context: android.content.Context, enableFloatOutput: Boolean, enableAudioTrackPlaybackParams: Boolean): AudioSink =
                DefaultAudioSink.Builder(context).setEnableFloatOutput(false)
                    .setEnableAudioOutputPlaybackParameters(false).setAudioProcessorChain(AudioFxChain()).build()
        }
        val player = ExoPlayer.Builder(this, renderers)
            .setAudioAttributes(
                AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_SPEECH).build(),
                true,
            )
            .setHandleAudioBecomingNoisy(true)
            .setWakeMode(C.WAKE_MODE_LOCAL)
            .setSeekBackIncrementMs(15_000)
            .setSeekForwardIncrementMs(15_000)
            .setLoadControl(loadControl())
            // Chương chưa tải thì phát thẳng từ máy tính (Streaming), có bộ đệm đĩa.
            .setMediaSourceFactory(Streaming.mediaSourceFactory(this))
            .build()
        player.addListener(object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                if (!isPlaying && player.playbackState == Player.STATE_READY && player.pauseAtEndOfMediaItems &&
                    player.duration - player.currentPosition < 1500
                ) {
                    SleepTimer.onPausedAtChapterEnd()
                }
                Playback.onPlayingChanged(isPlaying)
            }

            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) = Playback.onMediaTransition(mediaItem, reason == Player.MEDIA_ITEM_TRANSITION_REASON_SEEK)

            override fun onPositionDiscontinuity(oldPosition: Player.PositionInfo, newPosition: Player.PositionInfo, reason: Int) = Playback.onSeekSettled(reason)

            // Người nghe bấm phát / dừng bằng đường nào cũng được (thông báo, tai nghe, xe hơi): đọc to cần biết ở luồng nền để bỏ lần thử lại khi chẳng ai nghe.
            override fun onPlayWhenReadyChanged(playWhenReady: Boolean, reason: Int) {
                ReadAloud.onPlayWhenReadyChanged(playWhenReady, userRequested = reason == Player.PLAY_WHEN_READY_CHANGE_REASON_USER_REQUEST)
                Playback.onWantsChanged()
            }

            override fun onPlaybackParametersChanged(playbackParameters: androidx.media3.common.PlaybackParameters) {
                if (playbackParameters.pitch != AudioFx.pitchRatio()) player.playbackParameters = androidx.media3.common.PlaybackParameters(playbackParameters.speed, AudioFx.pitchRatio())
                Playback.onRateChanged(playbackParameters.speed)
            }

            override fun onDeviceVolumeChanged(volume: Int, muted: Boolean) = Playback.touched()

            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_ENDED) Playback.onEnded()
                if (state == Player.STATE_READY) Playback.onReady()
                Playback.onWantsChanged() // đang đệm thì nhạc chạy tiếp; chờ quá lâu ([BufferingGuard] -> IDLE) thì nhạc dừng theo
                Playback.emit("state")
            }

            override fun onPlayerError(error: PlaybackException) = Playback.onError(error)

            override fun onTimelineChanged(timeline: Timeline, reason: Int) {
                if (reason == Player.TIMELINE_CHANGE_REASON_PLAYLIST_CHANGED) Playback.onQueueReplaced()
            }
        })
        Playback.player = player
        player.playbackParameters = androidx.media3.common.PlaybackParameters(1f, AudioFx.pitchRatio())
        Playback.applyVolume()
        val openApp = PendingIntent.getActivity(
            this, 0, Intent(this, NativeActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        session = MediaLibrarySession.Builder(this, HeadsetSkips(player), Callback())
            .setSessionActivity(openApp)
            .setMediaButtonPreferences(buttons())
            .build()
        setMediaNotificationProvider(DefaultMediaNotificationProvider.Builder(this).build().apply { setSmallIcon(R.drawable.ic_notification) })
        // Dừng rồi còn giữ tiền cảnh một lúc ([foregroundGraceMs]) cho lắc / lật máy / máy tính phát tiếp; quá hạn thì thẻ vuốt bỏ được. Không còn gì để phát (Đóng, lỗi) thì không giữ thẻ.
        applyForegroundGrace()
        setListener(object : MediaSessionService.Listener {
            override fun onForegroundServiceStartNotAllowedException() = foregroundRefused()
        })
        setShowNotificationForIdlePlayer(SHOW_NOTIFICATION_FOR_IDLE_PLAYER_NEVER)
    }

    /**
     * Nút Đóng trên thông báo: dừng, lưu chỗ nghe, cất sách khỏi máy phát (hàng đợi rỗng nên thẻ biến mất) rồi tắt dịch vụ - phiên media
     * được gỡ ở [onDestroy] ngay khi không còn ai gắn vào (app đang mở thì đợi app rời).
     */
    @OptIn(UnstableApi::class)
    fun close() {
        AppLog.i("PlaybackService", S.s_dong_5d54c2a1)
        Playback.closeBook()
        pauseAllPlayersAndStopSelf()
    }

    /**
     * Nút trên thông báo; đổi theo trạng thái hẹn giờ (có "Hẹn lại N phút" chỉ khi đang hẹn - đứng đầu phần mở rộng để màn khoá luôn hiện).
     * Lùi/tới 15 giây chiếm ô trước/sau (dạng thu gọn). Media3 vì thế bỏ SKIP_TO_PREVIOUS/NEXT khỏi trạng thái phát cũ (MediaSessionLegacyStub;
     * hệ thống Android 13+ cũng chỉ vẽ biểu tượng ⏮⏭ cho hai hành động ấy) - LE Audio MediaControlProfile vẫn báo "base actions". Phím
     * Trước/Sau của tai nghe Bluetooth (AVRCP gửi phím media) vẫn tới [HeadsetSkips] vì Media3 xét lệnh của player, không xét trạng thái cũ.
     */
    @OptIn(UnstableApi::class)
    fun buttons(): List<CommandButton> {
        val list = mutableListOf(
            CommandButton.Builder(CommandButton.ICON_SKIP_BACK_15)
                .setPlayerCommand(Player.COMMAND_SEEK_BACK).setDisplayName(S.s_lui_15_giay_eb84ecc0).build(),
            CommandButton.Builder(CommandButton.ICON_SKIP_FORWARD_15)
                .setPlayerCommand(Player.COMMAND_SEEK_FORWARD).setDisplayName(S.s_toi_15_giay_77c8545b).build(),
        )
        if (SleepTimer.mode != SleepTimer.Mode.OFF) {
            list += CommandButton.Builder(CommandButton.ICON_PLUS)
                .setSessionCommand(SLEEP_PLUS).setDisplayName(SleepText.extendLabel(SleepTimer.extendTarget())).setSlots(CommandButton.SLOT_OVERFLOW).build()
        }
        // Đóng đứng ngay sau ba nút chính: thẻ media của Android 13+ và ColorOS chỉ vẽ năm ô (lùi · phát · tới + hai nút đầu phần mở rộng), nút thứ sáu
        // không bao giờ hiện. Media3 không có biểu tượng đóng: X riêng (make_icons.py).
        list += listOf(
            CommandButton.Builder(CommandButton.ICON_UNDEFINED).setCustomIconResId(R.drawable.ic_notification_close)
                .setSessionCommand(CLOSE).setDisplayName(S.s_dong_5d54c2a1).setSlots(CommandButton.SLOT_OVERFLOW).build(),
            CommandButton.Builder(CommandButton.ICON_PREVIOUS)
                .setSessionCommand(PREVIOUS_CHAPTER).setDisplayName(S.s_chuong_truoc_4750f9e9).setSlots(CommandButton.SLOT_OVERFLOW).build(),
            CommandButton.Builder(CommandButton.ICON_NEXT)
                .setSessionCommand(NEXT_CHAPTER).setDisplayName(S.s_chuong_sau_17d1bd20).setSlots(CommandButton.SLOT_OVERFLOW).build(),
        )
        return list
    }

    fun refreshButtons() {
        session?.setMediaButtonPreferences(buttons())
        (session?.player as? HeadsetSkips)?.refreshSleepReason()
    }

    /**
     * Lệnh "trước/sau" từ tai nghe Bluetooth, đồng hồ, xe hơi, màn hình khoá đều đi qua phiên media, tức qua lớp này.
     * Mặc định (tuỳ chọn "Nút tai nghe lùi/tới" bật) chúng là lùi/tới 15 giây - quy ước app sách nói, bấm nhầm không nhảy cả chương (Smart
     * AudioBook Player). Tắt thì "trước/sau" là [Playback.previous]/[Playback.next], đúng như nút chương trong app (đọc to:
     * theo danh sách chương; chương audio: mục kế, "trước" quá 5 giây thì về đầu chương). Nút trong app gọi thẳng player gốc.
     * `inText` = [ReadAloud.inText] (test JVM thay nó - lõi phát cần Looper của Android).
     */
    internal class HeadsetSkips(player: Player, private val inText: () -> Boolean = ReadAloud::inText) : ForwardingPlayer(player) {
        // Ở chương cuối không có "bài sau" nên Media3 coi lệnh ấy không khả dụng và bỏ phím trước khi tới đây (thấy
        // 27-09 trên máy ảo: "Trước" lùi 15 giây, "Sau" im). Hai lệnh luôn khả dụng: phiên media khai báo trước/sau cho tai nghe Bluetooth cả khi
        // chỉ có một chương (soát a69); "sau" ở chương cuối thì [Playback.next] không làm gì. Dựng khi cần (Commands cần Android - test JVM dựng lớp này được).
        private val skips by lazy {
            Player.Commands.Builder().addAll(
                Player.COMMAND_SEEK_TO_NEXT, Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM,
                Player.COMMAND_SEEK_TO_PREVIOUS, Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM,
            ).build()
        }

        private val metadataListeners = mutableSetOf<Player.Listener>()
        override fun addListener(listener: Player.Listener) { super.addListener(listener); metadataListeners.add(listener) }
        override fun removeListener(listener: Player.Listener) { super.removeListener(listener); metadataListeners.remove(listener) }
        fun refreshSleepReason() {
            metadataListeners.toList().forEach {
                it.onMediaMetadataChanged(mediaMetadata)
                it.onEvents(this, Player.Events(androidx.media3.common.FlagSet.Builder().add(Player.EVENT_MEDIA_METADATA_CHANGED).build()))
            }
        }

        override fun getMediaMetadata(): MediaMetadata {
            val reason = AutoSleepText.reason(SleepTimer.automaticReason)
            return if (reason.isEmpty()) super.getMediaMetadata() else super.getMediaMetadata().buildUpon()
                .setSubtitle(reason).setDescription(AutoSleepText.CONTINUE).build()
        }

        override fun getAvailableCommands(): Player.Commands {
            val builder = super.getAvailableCommands().buildUpon()
            for (index in 0 until skips.size()) builder.add(skips.get(index))
            return builder.build()
        }

        override fun isCommandAvailable(command: Int): Boolean = skips.contains(command) || super.isCommandAvailable(command)

        // Đọc to: hàng đợi có một mục mỗi đoạn, nên "mục kế" của ExoPlayer là đoạn kế - Trước/Sau và lùi/tới 15 giây phải đi theo chương và đồng hồ ảo
        // của ReadAloud ([Playback.next]/[Playback.previous] lo cả hai loại chương).
        override fun seekToNext() = if (Playback.headsetSkips) seekForward() else Playback.next()
        override fun seekToNextMediaItem() = seekToNext()
        override fun seekToPrevious() = if (Playback.headsetSkips) seekBack() else Playback.previous()
        override fun seekToPreviousMediaItem() = seekToPrevious()
        override fun seekForward() = if (inText()) Playback.skip(15.0) else super.seekForward()
        override fun seekBack() = if (inText()) Playback.skip(-15.0) else super.seekBack()

        // Đọc to: thanh tiến độ ở thông báo / màn hình khoá / xe hơi và lệnh tua của chúng đi theo đồng hồ ảo của CẢ chương (ReadAloud), không theo đoạn âm
        // thanh đang phát (mỗi đoạn chỉ vài giây). Chương audio: như ExoPlayer.
        // Đoạn đang phát luồng (`abooklive`, độ dài chưa biết) làm ExoPlayer coi mục là phát TRỰC TIẾP suốt đời mục: phiên media bỏ lệnh tua, báo tốc độ 0 - thông báo / màn khoá / xe mất thanh
        // tua, đồng hồ đứng (soát a59p). Ở chương chữ đồng hồ là của cả chương (ReadAloud), không bao giờ là trực tiếp.
        override fun isCurrentMediaItemLive(): Boolean = !inText() && super.isCurrentMediaItemLive()
        override fun isCurrentMediaItemDynamic(): Boolean = !inText() && super.isCurrentMediaItemDynamic()
        override fun getCurrentPosition(): Long = ReadAloud.positionMs() ?: super.getCurrentPosition()
        // Chờ đoạn đọc to kế (ReadAloud.starved): "đang tải", không phải "đã dừng" - thông báo giữ nút Tạm dừng và thanh tiến độ.
        override fun getPlaybackState(): Int = if (ReadAloud.starved()) Player.STATE_BUFFERING else super.getPlaybackState()
        override fun getPlayWhenReady(): Boolean = ReadAloud.starved() || super.getPlayWhenReady()
        override fun getContentPosition(): Long = ReadAloud.positionMs() ?: super.getContentPosition()
        override fun getDuration(): Long = ReadAloud.durationMs() ?: super.getDuration()
        override fun getContentDuration(): Long = ReadAloud.durationMs() ?: super.getContentDuration()
        override fun getBufferedPosition(): Long = ReadAloud.chapterMs(super.getBufferedPosition()) ?: super.getBufferedPosition()
        override fun getContentBufferedPosition(): Long = ReadAloud.chapterMs(super.getContentBufferedPosition()) ?: super.getContentBufferedPosition()
        override fun seekTo(positionMs: Long) = if (inText()) Playback.seekTo(positionMs / 1000.0) else super.seekTo(positionMs)
        override fun seekTo(mediaItemIndex: Int, positionMs: Long) =
            if (inText() && mediaItemIndex == currentMediaItemIndex) Playback.seekTo(positionMs / 1000.0) else super.seekTo(mediaItemIndex, positionMs)

        // Phát/dừng từ thông báo, màn hình khoá, tai nghe khi đang đọc to đi qua lõi (ReadAloud.onPlay/onPause): lúc chờ đọc đoạn đầu hàng đợi còn rỗng,
        // sau lỗi đọc thì bấm phát là thử lại đúng đoạn hỏng.
        // "Người nghe bấm phát tiếp" CHỈ có một đường: [Playback.play] (tự lùi, chuẩn bị lại sau lỗi, hẹn giờ ngủ) - nút trong app, thông báo, tai nghe, xe đều qua đó, sách audio cũng vậy (soát a77 #8).
        // Phục hồi tự động (hết đệm, focus trở lại) do ExoPlayer tự làm, không đi qua lớp này nên không bị lùi.
        override fun play() = if (Playback.player != null) Playback.play() else super.play()
        override fun pause() = if (ReadAloud.active) Playback.pause() else super.pause()
        override fun setPlayWhenReady(playWhenReady: Boolean) =
            if (playWhenReady) play() else if (ReadAloud.active) Playback.pause() else super.setPlayWhenReady(false)

        // Cuốn có chương chữ do lõi tự nạp (Playback.load) rồi trả [READ_ALOUD] cho phiên media: hàng đợi ấy không bao giờ vào ExoPlayer.
        override fun setMediaItems(mediaItems: MutableList<MediaItem>) { if (!isReadAloud(mediaItems)) super.setMediaItems(mediaItems) }
        override fun setMediaItems(mediaItems: MutableList<MediaItem>, resetPosition: Boolean) {
            if (!isReadAloud(mediaItems)) super.setMediaItems(mediaItems, resetPosition)
        }
        override fun setMediaItems(mediaItems: MutableList<MediaItem>, startIndex: Int, startPositionMs: Long) {
            if (!isReadAloud(mediaItems)) super.setMediaItems(mediaItems, startIndex, startPositionMs)
        }
    }


    private inner class Callback : MediaLibrarySession.Callback {
        override fun onMediaButtonEvent(session: MediaSession, controllerInfo: MediaSession.ControllerInfo, intent: Intent): Boolean {
            Playback.touched()
            return false
        }

        override fun onPlayerCommandRequest(session: MediaSession, controller: MediaSession.ControllerInfo, playerCommand: Int): Int {
            // Getters and automatic player events are not listener input.
            if (playerCommand in setOf(Player.COMMAND_PLAY_PAUSE, Player.COMMAND_PREPARE, Player.COMMAND_STOP,
                    Player.COMMAND_SEEK_IN_CURRENT_MEDIA_ITEM, Player.COMMAND_SEEK_TO_MEDIA_ITEM,
                    Player.COMMAND_SEEK_TO_NEXT, Player.COMMAND_SEEK_TO_PREVIOUS,
                    Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM, Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM,
                    Player.COMMAND_SEEK_BACK, Player.COMMAND_SEEK_FORWARD, Player.COMMAND_SET_SPEED_AND_PITCH,
                    Player.COMMAND_SET_VOLUME, Player.COMMAND_SET_DEVICE_VOLUME, Player.COMMAND_ADJUST_DEVICE_VOLUME,
                    Player.COMMAND_SET_DEVICE_VOLUME_WITH_FLAGS, Player.COMMAND_ADJUST_DEVICE_VOLUME_WITH_FLAGS)) Playback.touched()
            return SessionResult.RESULT_SUCCESS
        }

        override fun onConnect(session: MediaSession, controller: MediaSession.ControllerInfo): MediaSession.ConnectionResult {
            // Library commands plus sleep extension, previous/next chapter and Close.
            val commands = MediaSession.ConnectionResult.DEFAULT_SESSION_AND_LIBRARY_COMMANDS.buildUpon()
                .add(SLEEP_PLUS).add(PREVIOUS_CHAPTER).add(NEXT_CHAPTER).add(CLOSE).build()
            return MediaSession.ConnectionResult.AcceptedResultBuilder(session)
                .setAvailableSessionCommands(commands)
                .setMediaButtonPreferences(buttons())
                .build()
        }

        /** Tiếp tục phát từ điều khiển media của hệ thống / tai nghe Bluetooth sau khi app đã bị tắt hay máy khởi
         *  động lại: nạp lại cuốn nghe gần nhất đúng chỗ đang dở. */
        override fun onPlaybackResumption(
            mediaSession: MediaSession,
            controller: MediaSession.ControllerInfo,
            isForPlayback: Boolean,
        ): ListenableFuture<MediaSession.MediaItemsWithStartPosition> {
            return resumeQueue(isForPlayback)
        }

        override fun onGetLibraryRoot(
            session: MediaLibrarySession,
            browser: MediaSession.ControllerInfo,
            params: LibraryParams?,
        ): ListenableFuture<LibraryResult<MediaItem>> = Futures.immediateFuture(LibraryResult.ofItem(rootItem(), params))

        override fun onGetChildren(
            session: MediaLibrarySession,
            browser: MediaSession.ControllerInfo,
            parentId: String,
            page: Int,
            pageSize: Int,
            params: LibraryParams?,
        ): ListenableFuture<LibraryResult<ImmutableList<MediaItem>>> {
            return libraryTask({
                val nodes = children(parentId)
                if (nodes == null) LibraryResult.ofError<ImmutableList<MediaItem>>(SessionError.ERROR_BAD_VALUE)
                else {
                    val from = (page.toLong() * pageSize).coerceIn(0, nodes.size.toLong()).toInt()
                    LibraryResult.ofItemList(nodes.drop(from).take(pageSize.coerceAtLeast(1)).map { item(it, browser.packageName) }, params)
                }
            }) { it }
        }

        override fun onGetItem(
            session: MediaLibrarySession,
            browser: MediaSession.ControllerInfo,
            mediaId: String,
        ): ListenableFuture<LibraryResult<MediaItem>> {
            if (mediaId == LibraryTree.ROOT) return Futures.immediateFuture(LibraryResult.ofItem(rootItem(), null))
            return libraryTask({
                val book = LibraryTree.bookOf(mediaId)
                val node = book?.let { (children(LibraryTree.ROOT).orEmpty() + chaptersOf(it).orEmpty()) }
                    ?.firstOrNull { it.id == mediaId }
                if (node != null) LibraryResult.ofItem(item(node, browser.packageName), null)
                else LibraryResult.ofError<MediaItem>(SessionError.ERROR_BAD_VALUE)
            }) { it }
        }

        /**
         * Android Auto / trình duyệt media chọn một mục của cây: cả cuốn vào hàng đợi, bắt đầu đúng chỗ (LibraryTree.start).
         * Mục đã mang sẵn địa chỉ phát (trình điều khiển khác đặt hàng đợi của nó) thì để Media3 làm như thường.
         */
        override fun onSetMediaItems(
            mediaSession: MediaSession,
            controller: MediaSession.ControllerInfo,
            mediaItems: MutableList<MediaItem>,
            startIndex: Int,
            startPositionMs: Long,
        ): ListenableFuture<MediaSession.MediaItemsWithStartPosition> {
            val chosen = mediaItems.singleOrNull()?.takeIf { it.localConfiguration == null }?.mediaId
            val id = chosen?.let(LibraryTree::bookOf)
                ?: return super.onSetMediaItems(mediaSession, controller, mediaItems, startIndex, startPositionMs)
            return libraryTask({
                val manifest = Store.playableManifest(id) ?: throw IllegalArgumentException(S.s_cuon_nay_khong_con_tren_may_de91299f)
                val state = Store.state(id)
                val start = LibraryTree.start(chosen, manifest, state) ?: throw IllegalArgumentException(S.s_cuon_nay_khong_con_tren_may_de91299f)
                prepareQueue(manifest, state, start.chapterId, start.seconds)
            }) { applyQueue(it, true) }
        }

        override fun onCustomCommand(
            session: MediaSession,
            controller: MediaSession.ControllerInfo,
            customCommand: SessionCommand,
            args: Bundle,
        ): ListenableFuture<SessionResult> {
            if (customCommand.customAction == SLEEP_PLUS.customAction) {
                // extend() handles automatic timers before the general awake signal clears provenance.
                SleepTimer.extend()
                Playback.touched()
                return Futures.immediateFuture(SessionResult(SessionResult.RESULT_SUCCESS))
            }
            if (customCommand.customAction == CLOSE.customAction) {
                close()
                return Futures.immediateFuture(SessionResult(SessionResult.RESULT_SUCCESS))
            }
            Playback.touched()
            when (customCommand.customAction) {
                PREVIOUS_CHAPTER.customAction -> Playback.previous()
                NEXT_CHAPTER.customAction -> Playback.next()
            }
            return Futures.immediateFuture(SessionResult(SessionResult.RESULT_SUCCESS))
        }
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaLibrarySession? = session

    // ---- cây duyệt (LibraryTree) ------------------------------------------------------------------------------

    /** Con của một mục: gốc -> các cuốn; cuốn -> các chương. Chương không có con; mã lạ: null. */
    private fun children(parentId: String): List<LibraryTree.Node>? {
        if (parentId == LibraryTree.ROOT) {
            return LibraryTree.books(Store.playableBooks().map { it to Store.state(it.optString("id")) })
        }
        if (!LibraryTree.isBook(parentId)) return null
        return LibraryTree.bookOf(parentId)?.let(::chaptersOf)
    }

    private fun chaptersOf(bookId: String): List<LibraryTree.Node>? {
        val manifest = Store.playableManifest(bookId) ?: return null
        return LibraryTree.chapterNodes(manifest, Store.state(bookId))
    }

    private fun rootItem(): MediaItem = MediaItem.Builder()
        .setMediaId(LibraryTree.ROOT)
        .setMediaMetadata(
            MediaMetadata.Builder().setTitle(S.s_abook_1c37d334).setIsBrowsable(true).setIsPlayable(false)
                .setMediaType(MediaMetadata.MEDIA_TYPE_FOLDER_AUDIO_BOOKS).build(),
        )
        .build()

    private fun item(node: LibraryTree.Node, browser: String): MediaItem {
        val metadata = MediaMetadata.Builder()
            .setTitle(node.title)
            .setDisplayTitle(node.title)
            .setSubtitle(node.subtitle)
            .setIsBrowsable(node.browsable)
            .setIsPlayable(node.playable)
            .setMediaType(if (node.browsable) MediaMetadata.MEDIA_TYPE_AUDIO_BOOK else MediaMetadata.MEDIA_TYPE_AUDIO_BOOK_CHAPTER)
        // Bìa chỉ ở mục cuốn sách, và bằng ĐỊA CHỈ (content://) chứ không nhúng ảnh: danh sách nhiều cuốn mang ảnh 512 px
        // nhúng sẵn vượt giới hạn gói tin giữa hai tiến trình (~1 MB).
        if (node.browsable) coverUri(node, browser)?.let(metadata::setArtworkUri)
        return MediaItem.Builder().setMediaId(node.id).setMediaMetadata(metadata.build()).build()
    }

    /** Bìa của một cuốn ở bộ nhớ đệm, đặt tên theo nội dung (đổi bìa là đổi tên), qua FileProvider; cấp quyền đọc cho
     *  trình duyệt đang hỏi và cho Android Auto, giao diện hệ thống - nơi thật sự vẽ ảnh. */
    private fun coverUri(node: LibraryTree.Node, browser: String): Uri? = runCatching {
        val bytes = Artwork.cover(node.title, node.bookId)
        val png = bytes.size > 4 && bytes[1] == 'P'.code.toByte() && bytes[2] == 'N'.code.toByte() && bytes[3] == 'G'.code.toByte()
        val name = MessageDigest.getInstance("SHA-256").digest(bytes).take(12).joinToString("") { "%02x".format(it) }
        val file = File(File(cacheDir, "covers").apply { mkdirs() }, name + if (png) ".png" else ".jpg")
        if (!file.isFile) file.writeBytes(bytes)
        val uri = FileProvider.getUriForFile(this, "$packageName.fileprovider", file)
        for (reader in setOf(browser, "com.google.android.projection.gearhead", "com.android.systemui")) {
            runCatching { grantUriPermission(reader, uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
        }
        uri
    }.getOrNull()

    override fun onTaskRemoved(rootIntent: Intent?) {
        val player = session?.player
        AppLog.i("PlaybackService", S.s_vuot_app_khoi_danh_sach_gan_day_dang_phat_068f42f7(player?.playWhenReady == true))
        if (player == null || !player.playWhenReady || player.mediaItemCount == 0) stopSelf()
    }

    override fun onDestroy() {
        destroyed = true
        libraryIo.shutdown()
        AppLog.i("PlaybackService", S.s_dich_vu_phat_tat_a884c3ae)
        Playback.removeListener(sleepButtons)
        Playback.saveNow()
        // The process may go right after this: the last place must be on disk, not only handed to the writer.
        Playback.flushSaves()
        session?.run {
            player.release()
            release()
        }
        session = null
        MusicBed.stop()
        ReadAloud.stop()
        Playback.player = null
        ListenerActivity.stop()
        instance = null
        super.onDestroy()
    }
}
