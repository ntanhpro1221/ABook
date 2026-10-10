package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Hàng bài của danh sách phát khi tải hỏng (PlaylistQueue + MusicFailures, phần dữ liệu của MusicBed): bài tải hỏng rút khỏi hàng,
 * tới hạn (5, 10, 20 phút) thì về hàng ở chỗ đổi bài. Mở sách lúc mất mạng (mọi bài tải hỏng) hay chỉ còn một bài lặp mãi cũng phải
 * có nhạc lại khi mạng về - trước đây hai lúc ấy không bao giờ có "chỗ đổi bài" nên im / lặp một bài tới khi mở lại cuốn.
 */
class PlaylistQueueTest {
    private var clock = 1_000_000L
    private val failures = MusicFailures { clock }
    private val queue = PlaylistQueue(failures)
    private val a = Playlists.Track("https://x/a.mp3", 100.0, -8.0)
    private val b = Playlists.Track("https://x/b.mp3", 100.0, -8.0)
    private var online = false
    private val cached = mutableSetOf<String>()
    private var playing: String? = null

    /** Một nhịp `syncPlaylist` của MusicBed ở giây `seconds` của đồng hồ nhạc: sang bài mới thì tải (mất mạng: bài ấy bị bỏ tạm). */
    private fun sync(seconds: Double): String? {
        while (true) {
            val (span, _) = queue.at(seconds, playing) ?: return null.also { playing = null }
            if (span.index == queue.currentSpan) return playing
            val link = span.track.link
            if (online || link in cached) {
                cached += link
                queue.currentSpan = span.index
                playing = link
                return playing
            }
            failures.dropDownload(link)
            queue.drop(link, playing)
        }
    }

    @Test
    fun a_playlist_opened_offline_plays_once_the_network_is_back() {
        queue.load(listOf(a, b))
        assertNull(sync(0.0))
        assertEquals(emptyList<Playlists.Span>(), queue.spans)
        online = true
        clock += MusicFailures.RETRY_MS
        assertEquals(a.link, sync(1.0))
    }

    @Test
    fun the_dropped_track_rejoins_when_the_only_track_left_loops_not_in_the_middle_of_it() {
        cached += a.link
        queue.load(listOf(a, b))
        assertEquals(a.link, sync(0.0))
        assertEquals(a.link, sync(98.5)) // tới chỗ đổi bài, b tải hỏng -> chỉ còn a, lặp
        assertEquals(1, queue.spans.size)
        online = true
        clock += MusicFailures.RETRY_MS
        assertEquals(a.link, sync(148.0)) // giữa bài a: không đổi hàng, nhạc không nhảy
        assertEquals(1, queue.spans.size)
        assertEquals(a.link, sync(201.0)) // a quay lại đầu = chỗ đổi bài: b về hàng (sau a)
        assertEquals(2, queue.spans.size)
        assertEquals(b.link, sync(295.0))
    }

    @Test
    fun retries_back_off_five_ten_twenty_minutes_then_stop_for_the_session() {
        queue.load(listOf(a))
        assertNull(sync(0.0))
        for (wait in listOf(1L, 2L, 4L)) {
            clock += MusicFailures.RETRY_MS * wait - 1
            assertNull(sync(1.0))
            clock += 1
            assertNull(sync(2.0)) // tới hạn: thử lại, vẫn mất mạng -> chờ gấp đôi
        }
        online = true
        clock += MusicFailures.RETRY_MS * 100
        assertNull(sync(3.0)) // quá ba lần thử: bỏ tới phiên sau
    }
}
