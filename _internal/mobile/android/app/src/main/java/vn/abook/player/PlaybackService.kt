package vn.abook.player

import android.app.PendingIntent
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.core.content.FileProvider
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.ForwardingPlayer
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.Timeline
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.CommandButton
import androidx.media3.session.LibraryResult
import androidx.media3.session.MediaLibraryService
import androidx.media3.session.MediaLibraryService.LibraryParams
import androidx.media3.session.MediaLibraryService.MediaLibrarySession
import androidx.media3.session.MediaSession
import androidx.media3.session.SessionCommand
import androidx.media3.session.SessionError
import androidx.media3.session.SessionResult
import com.google.common.collect.ImmutableList
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture
import java.io.File
import java.security.MessageDigest
import vn.abook.player.readaloud.ReadAloud

/**
 * Dịch vụ phát nền: giữ ExoPlayer sống khi tắt màn hình, hiện điều khiển ở thanh thông báo và màn hình khoá,
 * nhận nút tai nghe/Bluetooth, tự dừng khi rút tai nghe hoặc có cuộc gọi (audio focus).
 *
 * Thanh thông báo: lùi 15 giây · phát/dừng · tới 15 giây, cộng "dấu trang" và - khi đang hẹn giờ ngủ - "+10 phút".
 *
 * Là MediaLibraryService: Android Auto và trình duyệt media của hệ thống duyệt được thư viện trên máy (LibraryTree:
 * sách -> chương) và chọn phát ngay trên màn hình xe.
 */
class PlaybackService : MediaLibraryService() {
    private var session: MediaLibrarySession? = null

    companion object {
        val BOOKMARK = SessionCommand("vn.abook.BOOKMARK", Bundle.EMPTY)
        val SLEEP_PLUS = SessionCommand("vn.abook.SLEEP_PLUS", Bundle.EMPTY)
        var instance: PlaybackService? = null
            private set

        /** Mục giả trả cho phiên media khi lõi đã tự nạp một cuốn có chương chữ (đọc to): [HeadsetSkips] bỏ qua nó thay vì đặt vào ExoPlayer. */
        private val READ_ALOUD = MediaItem.Builder().setMediaId("abook:read-aloud").build()

        private fun isReadAloud(items: List<MediaItem>) = items.singleOrNull()?.mediaId == READ_ALOUD.mediaId

        private fun readAloudQueue(): ListenableFuture<MediaSession.MediaItemsWithStartPosition> =
            Futures.immediateFuture(MediaSession.MediaItemsWithStartPosition(listOf(READ_ALOUD), 0, 0))
    }

    override fun onCreate() {
        super.onCreate()
        instance = this
        Playback.init(this)
        val player = ExoPlayer.Builder(this)
            .setAudioAttributes(
                AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_SPEECH).build(),
                true,
            )
            .setHandleAudioBecomingNoisy(true)
            .setWakeMode(C.WAKE_MODE_LOCAL)
            .setSeekBackIncrementMs(15_000)
            .setSeekForwardIncrementMs(15_000)
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

            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) = Playback.onMediaTransition(mediaItem)

            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_ENDED) Playback.onEnded()
                Playback.emit("state")
            }

            override fun onPlayerError(error: PlaybackException) = Playback.onError(error)

            override fun onTimelineChanged(timeline: Timeline, reason: Int) {
                if (reason == Player.TIMELINE_CHANGE_REASON_PLAYLIST_CHANGED) Playback.onQueueReplaced()
            }
        })
        Playback.player = player
        val openApp = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        session = MediaLibrarySession.Builder(this, HeadsetSkips(player), Callback())
            .setSessionActivity(openApp)
            .setMediaButtonPreferences(buttons())
            .build()
    }

    /** Nút trên thông báo; đổi theo trạng thái hẹn giờ (có "+10 phút" chỉ khi đang hẹn). */
    fun buttons(): List<CommandButton> {
        val list = mutableListOf(
            CommandButton.Builder(CommandButton.ICON_SKIP_BACK_15)
                .setPlayerCommand(Player.COMMAND_SEEK_BACK).setDisplayName("Lùi 15 giây").build(),
            CommandButton.Builder(CommandButton.ICON_SKIP_FORWARD_15)
                .setPlayerCommand(Player.COMMAND_SEEK_FORWARD).setDisplayName("Tới 15 giây").build(),
            CommandButton.Builder(CommandButton.ICON_BOOKMARK_UNFILLED)
                .setSessionCommand(BOOKMARK).setDisplayName("Thêm dấu trang").build(),
        )
        if (SleepTimer.mode != SleepTimer.Mode.OFF) {
            list += CommandButton.Builder(CommandButton.ICON_PLUS)
                .setSessionCommand(SLEEP_PLUS).setDisplayName("Nghe thêm ${SleepTimer.extendMinutes} phút").build()
        }
        return list
    }

    fun refreshButtons() {
        session?.setMediaButtonPreferences(buttons())
    }

    /**
     * Lệnh "trước/sau" từ tai nghe Bluetooth, đồng hồ, xe hơi, màn hình khoá đều đi qua phiên media, tức qua lớp này.
     * Bật "Nút tai nghe lùi/tới" thì chúng thành lùi/tới 15 giây (sách nói hiếm khi cần nhảy cả chương - Smart
     * AudioBook Player có tuỳ chọn này). Nút trong app gọi thẳng player gốc nên vẫn nhảy chương như cũ.
     */
    private class HeadsetSkips(player: Player) : ForwardingPlayer(player) {
        // Ở chương cuối không có "bài sau" nên Media3 coi lệnh ấy không khả dụng và bỏ phím trước khi tới đây (thấy
        // 27-09 trên máy ảo: "Trước" lùi 15 giây, "Sau" im). Bật tuỳ chọn thì hai lệnh luôn khả dụng.
        private val skips = Player.Commands.Builder().addAll(
            Player.COMMAND_SEEK_TO_NEXT, Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM,
            Player.COMMAND_SEEK_TO_PREVIOUS, Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM,
        ).build()

        override fun getAvailableCommands(): Player.Commands {
            val base = super.getAvailableCommands()
            if (!Playback.headsetSkips && !ReadAloud.active) return base
            val builder = base.buildUpon()
            for (index in 0 until skips.size()) builder.add(skips.get(index))
            return builder.build()
        }

        override fun isCommandAvailable(command: Int): Boolean =
            ((Playback.headsetSkips || ReadAloud.active) && skips.contains(command)) || super.isCommandAvailable(command)

        // Đọc to: hàng đợi có một mục mỗi đoạn, nên "mục kế" của ExoPlayer là đoạn kế - Trước/Sau và lùi/tới 15 giây phải đi theo chương và đồng hồ ảo của ReadAloud.
        override fun seekToNext() = if (Playback.headsetSkips) seekForward() else if (ReadAloud.active) Playback.next() else super.seekToNext()
        override fun seekToNextMediaItem() = if (Playback.headsetSkips) seekForward() else if (ReadAloud.active) Playback.next() else super.seekToNextMediaItem()
        override fun seekToPrevious() = if (Playback.headsetSkips) seekBack() else if (ReadAloud.active) Playback.previous() else super.seekToPrevious()
        override fun seekToPreviousMediaItem() = if (Playback.headsetSkips) seekBack() else if (ReadAloud.active) Playback.previous() else super.seekToPreviousMediaItem()
        override fun seekForward() = if (ReadAloud.inText()) Playback.skip(15.0) else super.seekForward()
        override fun seekBack() = if (ReadAloud.inText()) Playback.skip(-15.0) else super.seekBack()

        // Đọc to: thanh tiến độ ở thông báo / màn hình khoá / xe hơi và lệnh tua của chúng đi theo đồng hồ ảo của CẢ chương (ReadAloud), không theo đoạn âm
        // thanh đang phát (mỗi đoạn chỉ vài giây). Chương audio: như ExoPlayer.
        override fun getCurrentPosition(): Long = ReadAloud.positionMs() ?: super.getCurrentPosition()
        // Chờ đoạn đọc to kế (ReadAloud.starved): "đang tải", không phải "đã dừng" - thông báo giữ nút Tạm dừng và thanh tiến độ.
        override fun getPlaybackState(): Int = if (ReadAloud.starved()) Player.STATE_BUFFERING else super.getPlaybackState()
        override fun getPlayWhenReady(): Boolean = ReadAloud.starved() || super.getPlayWhenReady()
        override fun getContentPosition(): Long = ReadAloud.positionMs() ?: super.getContentPosition()
        override fun getDuration(): Long = ReadAloud.durationMs() ?: super.getDuration()
        override fun getContentDuration(): Long = ReadAloud.durationMs() ?: super.getContentDuration()
        override fun getBufferedPosition(): Long = ReadAloud.chapterMs(super.getBufferedPosition()) ?: super.getBufferedPosition()
        override fun getContentBufferedPosition(): Long = ReadAloud.chapterMs(super.getContentBufferedPosition()) ?: super.getContentBufferedPosition()
        override fun seekTo(positionMs: Long) = if (ReadAloud.inText()) Playback.seekTo(positionMs / 1000.0) else super.seekTo(positionMs)
        override fun seekTo(mediaItemIndex: Int, positionMs: Long) =
            if (ReadAloud.inText() && mediaItemIndex == currentMediaItemIndex) Playback.seekTo(positionMs / 1000.0) else super.seekTo(mediaItemIndex, positionMs)

        // Phát/dừng từ thông báo, màn hình khoá, tai nghe khi đang đọc to đi qua lõi (ReadAloud.onPlay/onPause): lúc chờ đọc đoạn đầu hàng đợi còn rỗng,
        // sau lỗi đọc thì bấm phát là thử lại đúng đoạn hỏng.
        override fun play() = if (ReadAloud.active) Playback.play() else super.play()
        override fun pause() = if (ReadAloud.active) Playback.pause() else super.pause()
        override fun setPlayWhenReady(playWhenReady: Boolean) =
            if (ReadAloud.active) { if (playWhenReady) Playback.play() else Playback.pause() } else super.setPlayWhenReady(playWhenReady)

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
        override fun onConnect(session: MediaSession, controller: MediaSession.ControllerInfo): MediaSession.ConnectionResult {
            // Lệnh thư viện (duyệt cây) cho Android Auto và trình duyệt media của hệ thống, cộng hai nút riêng của app.
            val commands = MediaSession.ConnectionResult.DEFAULT_SESSION_AND_LIBRARY_COMMANDS.buildUpon()
                .add(BOOKMARK).add(SLEEP_PLUS).build()
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
            // Cuốn đọc to đã nạp, hàng đợi rỗng vì đang chờ đọc đoạn đầu: không nạp lại gì, lệnh phát đi tiếp qua HeadsetSkips.play.
            if (isForPlayback && ReadAloud.active) return readAloudQueue()
            val recent = Playback.lastListened()
                ?: return Futures.immediateFailedFuture(UnsupportedOperationException("chưa nghe sách nào"))
            val (manifest, last) = recent
            val chapters = Playback.chaptersOf(manifest)
            // Hệ thống chỉ hỏi để vẽ thẻ "nghe tiếp" (isForPlayback false): đừng nạp, đừng phát.
            if (isForPlayback) Playback.onMain { Playback.resumeLast() }
            if (isForPlayback && chapters.any { it.isText }) return readAloudQueue()
            val index = chapters.indexOfFirst { it.id == last.optInt("chapterId") }.coerceAtLeast(0)
            val items = Playback.mediaItems(manifest.getString("id"), manifest.optString("title"), manifest.optString("narrator"), chapters)
            return Futures.immediateFuture(
                MediaSession.MediaItemsWithStartPosition(items, index, (last.optDouble("seconds") * 1000).toLong()),
            )
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
            val nodes = children(parentId)
                ?: return Futures.immediateFuture(LibraryResult.ofError(SessionError.ERROR_BAD_VALUE))
            val from = (page.toLong() * pageSize).coerceIn(0, nodes.size.toLong()).toInt()
            val items = nodes.drop(from).take(pageSize.coerceAtLeast(1)).map { item(it, browser.packageName) }
            return Futures.immediateFuture(LibraryResult.ofItemList(items, params))
        }

        override fun onGetItem(
            session: MediaLibrarySession,
            browser: MediaSession.ControllerInfo,
            mediaId: String,
        ): ListenableFuture<LibraryResult<MediaItem>> {
            if (mediaId == LibraryTree.ROOT) return Futures.immediateFuture(LibraryResult.ofItem(rootItem(), null))
            val book = LibraryTree.bookOf(mediaId)
            val node = book?.let { (children(LibraryTree.ROOT).orEmpty() + chaptersOf(it).orEmpty()) }
                ?.firstOrNull { it.id == mediaId }
            return Futures.immediateFuture(
                if (node != null) LibraryResult.ofItem(item(node, browser.packageName), null)
                else LibraryResult.ofError(SessionError.ERROR_BAD_VALUE),
            )
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
            val manifest = Store.playableManifest(id)
            val state = Store.state(id)
            val start = manifest?.let { LibraryTree.start(chosen, it, state) }
            if (manifest == null || start == null) {
                return Futures.immediateFailedFuture(IllegalArgumentException("Cuốn này không còn trên máy"))
            }
            val chapters = LibraryTree.chapters(manifest)
            val title = manifest.optString("title")
            val narrator = manifest.optString("narrator")
            val rate = state.optDouble("rate", 1.0).takeIf { !it.isNaN() && it > 0 } ?: 1.0
            if (chapters.any { it.isText }) {
                // Có chương chữ: lõi tự nạp và đọc (ReadAloud) - hàng đợi mỗi đoạn một mục, không phải mỗi chương một file.
                Playback.load(id, title, narrator, chapters, start.chapterId, start.seconds, rate)
                return readAloudQueue()
            }
            Playback.adopt(id, title, narrator, chapters, start.chapterId, start.seconds, rate)
            return Futures.immediateFuture(
                MediaSession.MediaItemsWithStartPosition(
                    Playback.mediaItems(id, title, narrator, chapters),
                    chapters.indexOfFirst { it.id == start.chapterId }.coerceAtLeast(0),
                    (start.seconds * 1000).toLong(),
                ),
            )
        }

        override fun onCustomCommand(
            session: MediaSession,
            controller: MediaSession.ControllerInfo,
            customCommand: SessionCommand,
            args: Bundle,
        ): ListenableFuture<SessionResult> {
            when (customCommand.customAction) {
                BOOKMARK.customAction -> Playback.addBookmark("")
                SLEEP_PLUS.customAction -> SleepTimer.extend()
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
            MediaMetadata.Builder().setTitle("ABook").setIsBrowsable(true).setIsPlayable(false)
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
        if (player == null || !player.playWhenReady || player.mediaItemCount == 0) stopSelf()
    }

    override fun onDestroy() {
        Playback.saveNow()
        session?.run {
            player.release()
            release()
        }
        session = null
        MusicBed.stop()
        ReadAloud.stop()
        Playback.player = null
        instance = null
        super.onDestroy()
    }
}
