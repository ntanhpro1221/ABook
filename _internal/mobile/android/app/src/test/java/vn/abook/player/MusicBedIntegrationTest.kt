package vn.abook.player

import android.os.Handler
import androidx.media3.common.Player
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.io.File
import java.lang.reflect.Proxy

/** Exercise MusicBed's real scheduled fade and release with a delayed ExoPlayer double.
 * Reflection installs the private Bed, avoiding codecs, network and production test hooks. */
class MusicBedIntegrationTest {
    private class FakePlayer {
        var state = Player.STATE_IDLE
        var volume = 0f
        var playing = true
        /** Ý định phát tách khỏi `isPlaying`: bài đang đệm có playWhenReady = true mà isPlaying = false (ExoPlayer thật). */
        var playWhenReady = false
        var released = 0
        var buffered = ByteArray(8192)
        var position = 10_000L
        var bufferedPosition = 0L
        var loading = true
        var seeks = 0
        var item: MediaItem? = null
        val listeners = mutableListOf<Player.Listener>()
        val player: ExoPlayer = Proxy.newProxyInstance(ExoPlayer::class.java.classLoader, arrayOf(ExoPlayer::class.java)) { proxy, method, args ->
            when (method.name) {
                "prepare" -> { state = Player.STATE_BUFFERING; null }
                "getPlaybackState" -> state
                "getVolume" -> volume
                "setVolume" -> { volume = args!![0] as Float; null }
                "getDuration" -> 200_000L
                "getCurrentPosition" -> position
                "getBufferedPosition" -> bufferedPosition
                "isLoading" -> loading
                "getCurrentMediaItem" -> item
                "seekTo" -> { seeks++; position = args!!.last() as Long; null }
                "isPlaying" -> playing
                "getPlayWhenReady" -> playWhenReady
                "play" -> { playWhenReady = true; playing = state == Player.STATE_READY; null }
                "pause" -> { playWhenReady = false; playing = false; null }
                "addListener" -> { listeners.add(args!![0] as Player.Listener); null }
                "removeListener" -> { listeners.remove(args!![0] as Player.Listener); null }
                "release" -> { check(listeners.isEmpty()) { "listeners must be removed before release" }; released++; buffered = byteArrayOf(); null }
                "equals" -> args!![0] === proxy
                "hashCode" -> System.identityHashCode(this)
                "toString" -> "FakeMusicPlayer"
                else -> when (method.returnType) {
                    java.lang.Boolean.TYPE -> false
                    java.lang.Integer.TYPE -> 0
                    java.lang.Long.TYPE -> 0L
                    java.lang.Float.TYPE -> 0f
                    else -> null
                }
            }
        } as ExoPlayer
    }

    private fun field(name: String) = MusicBed::class.java.getDeclaredField(name).also { it.isAccessible = true }
    private fun invoke(name: String) = MusicBed::class.java.getDeclaredMethod(name).also { it.isAccessible = true }.invoke(MusicBed)
    private fun bed(fake: FakePlayer, cue: MusicCues.Cue? = null): Any {
        val type = Class.forName("vn.abook.player.MusicBed\$Bed")
        return type.declaredConstructors.single().also { it.isAccessible = true }
            .newInstance("music/a.mp3", fake.player, 0.1f, 0.0025f, cue, 2000L)
    }

    private fun logical(bed: Any) = bed.javaClass.getDeclaredField("volume").also { it.isAccessible = true }.getFloat(bed)
    private fun setLogical(bed: Any, v: Float) = bed.javaClass.getDeclaredField("volume").also { it.isAccessible = true }.setFloat(bed, v)
    private fun setFadeStep(bed: Any, v: Float) = bed.javaClass.getDeclaredField("fadeStep").also { it.isAccessible = true }.setFloat(bed, v)

    @Before fun setup() {
        field("sleepFactor").setFloat(MusicBed, 1f)
        Handler.reset()
        MusicCues.mix = MusicMix.parse(File("../../../abook/webui/assets/music_mix.json").readText())
        MusicBed.stop()
        field("fadingTicker").setBoolean(MusicBed, false)
    }
    @After fun cleanup() { field("sleepFactor").setFloat(MusicBed, 1f); field("context").set(MusicBed, null); MusicBed.stop(); Playback.player = null; Handler.reset() }

    @Test fun prepareLongerThanFadeStillFadesFromSilenceToTheGoal() {
        val fake = FakePlayer()
        fake.player.prepare()
        val current = bed(fake)
        field("current").set(MusicBed, current)
        invoke("startFade")
        Handler.advance(10_000) // 5x the fade duration, still preparing
        assertEquals(0f, fake.volume, 0f)
        assertTrue(current.javaClass.getDeclaredField("entering").also { it.isAccessible = true }.getBoolean(current))
        fake.state = Player.STATE_READY
        Handler.advance(50)
        assertEquals("first audible tick must not jump", 0.0025f, fake.volume, 1e-6f)
        Handler.advance(950)
        assertEquals(0.05f, fake.volume, 1e-5f)
        Handler.advance(1000)
        assertEquals("must not get stuck at zero", 0.1f, fake.volume, 1e-6f)
        assertFalse(current.javaClass.getDeclaredField("entering").also { it.isAccessible = true }.getBoolean(current))
    }

    /** Bài mới đang mờ vào (0,1 trong 2 s: 0,0025 mỗi nhịp 50 ms), còn đệm ở nhịp đầu (t = 0); tới t = 20 ms (giữa hai nhịp) nó READY và chạy. Trả trình phát giả. */
    private fun newBedStartsPlayingBetweenTicks(fire: Boolean): FakePlayer {
        val fake = FakePlayer().also { it.state = Player.STATE_BUFFERING; it.playing = false }
        val current = bed(fake)
        field("current").set(MusicBed, current)
        MusicBed::class.java.getDeclaredMethod("watchPlaying", current.javaClass).also { it.isAccessible = true }.invoke(MusicBed, current) // như open()
        invoke("startFade")
        Handler.advance(0)
        assertEquals("còn đệm: chưa nhích", 0f, fake.volume, 0f)
        Handler.advance(20)
        fake.state = Player.STATE_READY
        fake.playing = true
        if (fire) fake.listeners.toList().forEach { it.onIsPlayingChanged(true) }
        Handler.advance(0)
        return fake
    }

    @Test fun fadeInStartsTheMomentTheNewPlayerActuallyPlays() {
        val fake = newBedStartsPlayingBetweenTicks(fire = true)
        assertEquals("nhích ngay, không chờ nhịp 50 ms", 0.0025f, fake.volume, 1e-6f)
        Handler.advance(30) // t = 50: nhịp cũ đã bị huỷ, pha ticker tính lại từ t = 20
        assertEquals(0.0025f, fake.volume, 1e-6f)
        Handler.advance(20) // t = 70
        assertEquals("bước mờ không đổi", 0.005f, fake.volume, 1e-6f)
        Handler.advance(2000)
        assertEquals(0.1f, fake.volume, 1e-6f)
        assertFalse(field("fadingTicker").getBoolean(MusicBed))
    }

    @Test fun withoutThePlayingEventTheFadeInWaitsForTheNextTick() {
        val fake = newBedStartsPlayingBetweenTicks(fire = false)
        assertEquals(0f, fake.volume, 0f)
        Handler.advance(29) // t = 49
        assertEquals(0f, fake.volume, 0f)
        Handler.advance(1) // t = 50
        assertEquals(0.0025f, fake.volume, 1e-6f)
    }

    @Test fun closingReleasesCurrentAndFadingPlayersAndTheirBuffers() {
        val players = listOf(FakePlayer(), FakePlayer())
        val beds = players.map { bed(it) }
        val listener = object : Player.Listener {}
        for ((index, current) in beds.withIndex()) {
            @Suppress("UNCHECKED_CAST")
            val registered = current.javaClass.getDeclaredField("listeners").also { it.isAccessible = true }.get(current) as MutableList<Player.Listener>
            registered.add(listener)
            players[index].player.addListener(listener)
        }
        field("book").set(MusicBed, "closed-book")
        field("current").set(MusicBed, beds[0])
        @Suppress("UNCHECKED_CAST")
        (field("fading").get(MusicBed) as MutableList<Any>).add(beds[1])
        invoke("startFade")
        // The close button calls this lifecycle entry.
        MusicBed.release()
        assertNull(MusicBed.activeTrack)
        assertEquals("closed-book", field("closedBook").get(MusicBed))
        for (fake in players) { assertEquals(1, fake.released); assertEquals(0, fake.buffered.size); assertTrue(fake.listeners.isEmpty()) }
        Handler.advance(10_000) // queued fade must not revive or release the players twice
        assertEquals(listOf(1, 1), players.map { it.released })
        assertTrue((field("fading").get(MusicBed) as List<*>).isEmpty())
    }

    /** Context chỉ là phép kiểm "có"; SharedPreferences của đồng hồ nhạc ([MusicBed.saveClock]) là bản giả nuốt mọi ghi. */
    private class PrefsContext : android.content.ContextWrapper(null) {
        private val prefs = Proxy.newProxyInstance(javaClass.classLoader, arrayOf(android.content.SharedPreferences::class.java, android.content.SharedPreferences.Editor::class.java)) { proxy, method, _ ->
            when (method.name) { "edit", "putFloat", "putBoolean" -> proxy; else -> null }
        } as android.content.SharedPreferences
        override fun getSharedPreferences(name: String?, mode: Int) = prefs
    }

    private fun installContext() {
        field("context").set(MusicBed, PrefsContext())
    }

    @Test fun pausingTheVoiceAlsoPausesMusicThatIsStillBufferingWithPlayWhenReady() {
        val music = FakePlayer().also { it.state = Player.STATE_BUFFERING; it.playing = false; it.playWhenReady = true }
        val current = bed(music)
        field("current").set(MusicBed, current)
        field("playing").setBoolean(MusicBed, false) // giọng đã dừng
        invoke("applyPlaying")
        assertFalse("nhạc đang đệm không được tự phát khi đệm xong", music.playWhenReady)
        // Đối chứng: giọng đang chạy thì nhạc chưa phát (đang đệm) vẫn được phép phát.
        field("playing").setBoolean(MusicBed, true)
        invoke("applyPlaying")
        assertTrue(music.playWhenReady)
    }

    @Test fun listenerStopPausesPlaylistMusicAtOnceButAGapBetweenSegmentsWaitsForTheGrace() {
        installContext()
        val syncPlaylist = MusicBed::class.java.getDeclaredMethod("syncPlaylist", Boolean::class.javaPrimitiveType, Boolean::class.javaPrimitiveType)
            .also { it.isAccessible = true }
        field("playing").setBoolean(MusicBed, true)
        syncPlaylist.invoke(MusicBed, false, false) // khoảng nối đoạn: chờ
        assertTrue(field("playing").getBoolean(MusicBed))
        Handler.advance(2_000)
        assertTrue(field("playing").getBoolean(MusicBed))
        Handler.advance(600)
        assertFalse("hết 2,5 giây thì dừng", field("playing").getBoolean(MusicBed))
        field("playing").setBoolean(MusicBed, true)
        syncPlaylist.invoke(MusicBed, false, true) // người nghe / focus / rút tai nghe / cuộc gọi: dừng ngay
        assertFalse(field("playing").getBoolean(MusicBed))
    }

    @Test fun playbackTellsTheMusicWhetherTheListenerStoppedTheVoice() {
        installContext()
        val voice = FakePlayer().also { it.state = Player.STATE_READY; it.playing = false }
        Playback.player = voice.player
        Playback::class.java.getDeclaredField("bookId").also { it.isAccessible = true }.set(Playback, "stop-book")
        field("book").set(MusicBed, "stop-book")
        field("closedBook").set(MusicBed, "")
        field("playlist").set(MusicBed, "p")
        val sync = Playback::class.java.getDeclaredMethod("syncMusic", Boolean::class.javaPrimitiveType).also { it.isAccessible = true }
        field("playing").setBoolean(MusicBed, true)
        voice.playWhenReady = true // giọng đang đệm / chờ đoạn kế: chỉ là khe nối
        sync.invoke(Playback, false)
        assertTrue(field("playing").getBoolean(MusicBed))
        voice.playWhenReady = false // người nghe (hay hệ thống thay họ) đã dừng
        sync.invoke(Playback, false)
        assertFalse(field("playing").getBoolean(MusicBed))
        Playback::class.java.getDeclaredField("bookId").also { it.isAccessible = true }.set(Playback, "")
    }

    @Test fun theVoiceEndingTheBookFadesTheMusicOutInsteadOfCuttingIt() {
        // 01-11 (audio_sink trên Qt 0.4.152): nhạc dừng cùng giọng lúc giọng tự hết -> -30 -> -91 dB trong 6 ms. ExoPlayer ENDED: nhạc mờ ra rồi được nhả.
        installContext()
        for (listenerStopped in listOf(false, true)) {
            Handler.reset()
            MusicBed.stop()
            field("fadingTicker").setBoolean(MusicBed, false)
            val voice = FakePlayer().also { it.playing = false; it.playWhenReady = !listenerStopped; it.state = if (listenerStopped) Player.STATE_READY else Player.STATE_ENDED }
            Playback.player = voice.player
            Playback::class.java.getDeclaredField("bookId").also { it.isAccessible = true }.set(Playback, "end-book")
            field("book").set(MusicBed, "end-book")
            field("closedBook").set(MusicBed, "")
            field("playlist").set(MusicBed, null)
            val music = FakePlayer().also { it.state = Player.STATE_READY; it.playWhenReady = true }
            val current = bed(music)
            setLogical(current, 0.1f)
            music.volume = 0.1f
            field("current").set(MusicBed, current)
            field("playing").setBoolean(MusicBed, true)
            Playback::class.java.getDeclaredMethod("syncMusic", Boolean::class.javaPrimitiveType).also { it.isAccessible = true }.invoke(Playback, false)
            if (listenerStopped) {
                assertFalse("người nghe dừng: nhạc dừng ngay", music.playWhenReady)
                continue
            }
            assertNull(field("current").get(MusicBed))
            assertTrue("giọng tự hết: nhạc không dừng cùng giọng", music.playWhenReady)
            Handler.advance(500)
            assertTrue(music.volume in 0.001f..0.099f)
            Handler.advance(MusicCues.mix.fadeMs + 500)
            assertEquals(1, music.released)
        }
        Playback::class.java.getDeclaredField("bookId").also { it.isAccessible = true }.set(Playback, "")
    }

    private fun playbackField(name: String) = Playback::class.java.getDeclaredField(name).also { it.isAccessible = true }

    @Test fun aVoiceStalledPastTheLimitFadesTheMusicDownAndLetsItBackWhenTheVoiceMoves() {
        // Mạng hỏng hẳn: giọng đệm tới HostWait.STALL_MS (215 s) - nhạc không được kêu một mình suốt chừng ấy. Quá voiceStallFadeAfterSeconds thì mờ xuống
        // (không tắt phụt), giọng có tiếng lại thì nhạc theo. Cả nhạc theo mốc lẫn danh sách phát.
        installContext()
        val stallMs = MusicCues.mix.voiceStallMs
        for ((index, playlist) in listOf(null, "p").withIndex()) {
            Handler.reset()
            MusicBed.stop()
            field("fadingTicker").setBoolean(MusicBed, false)
            playbackField("ticking").setBoolean(Playback, true) // nhịp 500 ms của Playback không chạy ở đây: test gọi syncMusic như nhịp ấy
            val voice = FakePlayer().also { it.playing = false; it.playWhenReady = true; it.state = Player.STATE_BUFFERING; it.position = 30_123L + index }
            Playback.player = voice.player
            playbackField("bookId").set(Playback, "stall-book")
            field("book").set(MusicBed, "stall-book")
            field("closedBook").set(MusicBed, "")
            field("playlist").set(MusicBed, playlist)
            val music = FakePlayer().also { it.state = Player.STATE_READY; it.playWhenReady = true }
            // Mốc / hàng bài có đúng bài đang kêu ở chỗ giọng đứng: lúc chưa quá hạn nhạc chạy tiếp như thường.
            val cue = MusicCues.Cue(0.0, 100.0, "music/a.mp3", -20.0)
            field("cues").set(MusicBed, listOf(cue))
            field("lastSeconds").setDouble(MusicBed, 30.0)
            val queue = field("queue").get(MusicBed) as PlaylistQueue
            queue.load(listOf(Playlists.Track("music/a.mp3", 600.0, -20.0)))
            queue.currentSpan = 0
            val current = bed(music, if (playlist == null) cue else null)
            current.javaClass.getDeclaredField("entering").also { it.isAccessible = true }.setBoolean(current, false)
            setLogical(current, 0.1f)
            music.volume = 0.1f
            field("current").set(MusicBed, current)
            field("playing").setBoolean(MusicBed, true)
            val sync = Playback::class.java.getDeclaredMethod("syncMusic", Boolean::class.javaPrimitiveType).also { it.isAccessible = true }
            sync.invoke(Playback, false)
            Handler.advance(stallMs - 500)
            sync.invoke(Playback, false)
            assertSame("$playlist: khe chưa tới hạn - nhạc chạy tiếp", current, field("current").get(MusicBed))
            assertEquals(0.1f, music.volume, 1e-6f)
            Handler.advance(500)
            sync.invoke(Playback, false)
            assertNull("$playlist: quá hạn - nhạc mờ ra", field("current").get(MusicBed))
            assertTrue("$playlist: mờ, không dừng phụt", music.playWhenReady)
            Handler.advance(500)
            assertTrue(music.volume in 0.001f..0.099f)
            Handler.advance(MusicCues.mix.fadeMs + 500)
            assertEquals(1, music.released)
            sync.invoke(Playback, false)
            assertFalse(field("playing").getBoolean(MusicBed))
            voice.position += 500 // có tiếng lại
            voice.playing = true
            voice.state = Player.STATE_READY
            // Mốc / bài ở chỗ ấy mở lại và mờ vào như lúc vào mốc (startCue mở file - test JVM không mở được): ở đây chỉ xem nhạc đã theo giọng.
            field("cues").set(MusicBed, emptyList<MusicCues.Cue>())
            queue.clear()
            sync.invoke(Playback, true)
            assertTrue("$playlist: giọng chạy lại thì nhạc theo", field("playing").getBoolean(MusicBed))
        }
        playbackField("ticking").setBoolean(Playback, false)
        playbackField("bookId").set(Playback, "")
    }

    @Test fun theOldSongHoldsItsPlaceWhileTheNextSceneSongIsStillDownloading() {
        // Soát nghe 02-11 (nguồn nhạc 11 KB/s): bài của mốc mới chưa có file thì bài trước mờ đi và cả cảnh câm suốt lúc tải (bài 29 MB ~45 phút).
        // Bài đang kêu giữ chỗ ở mức của nó; bài mới vào khi có file. Như musicbed.cpp / musicBed.ts.
        installContext()
        val root = BookEditsFixtures.tempDir("music-hold-old")
        val deviceCatalog = DeviceMusic::class.java.getDeclaredField("catalog").also { it.isAccessible = true }
        try {
            deviceCatalog.set(DeviceMusic, MusicCatalog(File(root, "catalog"), "file:///none"))
            field("book").set(MusicBed, "hold-book")
            field("closedBook").set(MusicBed, "")
            field("playlist").set(MusicBed, null)
            field("sceneMode").setBoolean(MusicBed, true)
            field("chapter").setInt(MusicBed, 1)
            field("lastSeconds").setDouble(MusicBed, 59.5)
            val old = MusicCues.Cue(0.0, 50.0, "music/a.mp3", -20.0)
            field("cues").set(MusicBed, listOf(old, MusicCues.Cue(50.0, 100.0, "music/b.mp3", -20.0)))
            @Suppress("UNCHECKED_CAST") (field("downloading").get(MusicBed) as MutableSet<String>).add("music/b.mp3") // đang tải dở
            val music = FakePlayer().also { it.state = Player.STATE_READY; it.playWhenReady = true }
            val current = bed(music, old)
            current.javaClass.getDeclaredField("entering").also { it.isAccessible = true }.setBoolean(current, false)
            setLogical(current, 0.1f)
            music.volume = 0.1f
            field("current").set(MusicBed, current)
            field("playing").setBoolean(MusicBed, true)
            MusicBed.sync("hold-book", 1, 60.0, true)
            assertSame("bài mới chưa có file: bài cũ giữ chỗ", current, field("current").get(MusicBed))
            Handler.advance(MusicCues.mix.fadeMs + 500L)
            assertTrue("không mờ, không dừng", music.playWhenReady)
            assertEquals(0.1f, music.volume, 1e-6f)
            assertEquals(0, music.released)
        } finally {
            deviceCatalog.set(DeviceMusic, null)
            field("sceneMode").setBoolean(MusicBed, false)
            (field("downloading").get(MusicBed) as MutableSet<*>).clear()
            root.deleteRecursively()
        }
    }

    /** ExoPlayer phát dần một bài stream: đệm tăng `rate` giây bài mỗi giây (cả lúc tạm dừng - trình phát vẫn tải), đang phát thì con trỏ chạy tới khi hết đệm thì đứng
     *  (BUFFERING), đệm lại 5 s thì chạy tiếp; tạm dừng thì đứng yên. Trả các lần đứng / chạy lại kèm âm lượng lúc ấy. */
    private fun stream(music: FakePlayer, ms: Long, rate: () -> Double): List<Pair<String, Float>> {
        val out = mutableListOf<Pair<String, Float>>()
        repeat((ms / 50).toInt()) {
            Handler.advance(50)
            music.bufferedPosition = minOf(200_000L, music.bufferedPosition + (rate() * 50).toLong())
            music.loading = music.bufferedPosition < 200_000L
            val ahead = music.bufferedPosition - music.position
            if (!music.playWhenReady) {
                music.playing = false
                if (music.state == Player.STATE_BUFFERING && (ahead >= 2500 || !music.loading)) music.state = Player.STATE_READY
            } else if (music.state == Player.STATE_READY) {
                if (ahead < 50 && music.loading) { music.state = Player.STATE_BUFFERING; music.playing = false; out += "đứng" to music.volume }
                else { music.playing = true; music.position += minOf(50L, ahead) }
            } else if (ahead >= 5000 || !music.loading) {
                music.state = Player.STATE_READY; music.playing = true; out += "chạy" to music.volume
            }
        }
        return out
    }

    private fun streamedBed(music: FakePlayer): Any = bed(music).also { b ->
        b.javaClass.getDeclaredField("streamed").also { it.isAccessible = true }.setBoolean(b, true)
    }

    @Test fun aStreamedSongFallingBehindFadesOutPausesInPlaceAndFadesBackInWhenItCanPlayThrough() {
        // Nhạc của sách nghe thẳng từ máy tính (http): ExoPlayer phát dần, mạng tụt giữa bài thì đệm cạn - trước đây tắt phụt ở đủ mức rồi bật phụt (như Qt
        // NA1 01-11: 14 lần). Bản sửa: đệm trước < 1 s mà không còn phát được tới hết bài thì mờ ra 0,3 s, tạm dừng tại chỗ trước khi cạn, phát được tới hết bài
        // (cùng công thức với Qt / web) thì chạy tiếp từ đúng chỗ ấy, mờ vào 0,3 s.
        val music = FakePlayer().also { it.state = Player.STATE_READY; it.playWhenReady = true; it.bufferedPosition = it.position + 20_000 }
        val current = streamedBed(music)
        current.javaClass.getDeclaredField("entering").also { it.isAccessible = true }.setBoolean(current, false)
        current.javaClass.getDeclaredField("admitted").also { it.isAccessible = true }.setBoolean(current, true)
        setLogical(current, 0.1f)
        music.volume = 0.1f
        field("current").set(MusicBed, current)
        field("playing").setBoolean(MusicBed, true)
        invoke("startFade")
        var rate = 2.0
        assertTrue("tải nhanh: không hụt", stream(music, 10_000) { rate }.isEmpty())
        rate = 0.4 // mạng tụt
        val fell = stream(music, 60_000) { rate }
        assertTrue("không lần nào đệm cạn: mờ ra rồi tạm dừng trước khi cạn ($fell)", fell.isEmpty())
        assertFalse("tạm dừng tại chỗ", music.playWhenReady)
        assertEquals(0f, music.volume, 0f)
        val at = music.position
        assertTrue("dừng trước khi đệm cạn (vị trí $at, đệm ${music.bufferedPosition})", music.bufferedPosition > at)
        assertTrue("0,4x không bao giờ phát được tới hết bài: vẫn đứng yên, im", stream(music, 20_000) { rate }.isEmpty())
        assertEquals(at, music.position)
        assertEquals(0f, music.volume, 0f)
        rate = 2.0 // mạng lại nhanh
        stream(music, 9_000) { rate } // trung bình trượt 8 s mới thấy tốc độ mới
        assertEquals("phát được tới hết bài: về đủ mức", 0.1f, music.volume, 1e-4f)
        val back = mutableListOf<Float>()
        rate = 0.4
        assertTrue(stream(music, 60_000) { rate }.isEmpty())
        assertFalse("hụt lần hai: lại tạm dừng tại chỗ", music.playWhenReady)
        rate = 2.0
        repeat(200) { assertTrue(stream(music, 50) { rate }.isEmpty()); back += music.volume }
        val firstSound = back.indexOfFirst { it > 0f }
        assertTrue("vào lại mờ dần, không bật phụt ($back)", firstSound >= 0 && back[firstSound] < 0.05f)
        val full = back.indexOfFirst { it >= 0.0999f }
        assertTrue("mờ vào trong ~0,3 s (${(full - firstSound) * 50} ms)", full - firstSound in 4..8)
    }

    @Test fun aStreamedSongThatCannotKeepUpWaitsPausedAndEntersOnceItCanPlayThrough() {
        // Bài stream mới tải chậm hơn phát (0,6x): đứng yên ở chỗ vào (bài trước giữ chỗ ở mức của nó) cho tới khi phát được tới hết bài - không vào rồi hụt
        // giữa chừng, cũng không chờ tải trọn: vào khi đã có ~54 % (200 - 0,6 x 200 / 1,3 giây).
        val old = FakePlayer().also { it.state = Player.STATE_READY; it.playWhenReady = true }
        val oldBed = bed(old)
        setLogical(oldBed, 0.1f)
        old.volume = 0.1f
        oldBed.javaClass.getDeclaredField("fadeStep").also { it.isAccessible = true }.setFloat(oldBed, 0.1f * 50 / 2000)
        @Suppress("UNCHECKED_CAST") (field("fading").get(MusicBed) as MutableList<Any>).add(oldBed)
        val music = FakePlayer().also { it.state = Player.STATE_BUFFERING; it.playWhenReady = true; it.position = 0; it.bufferedPosition = 3_000 }
        field("current").set(MusicBed, streamedBed(music))
        field("playing").setBoolean(MusicBed, true)
        invoke("startFade")
        stream(music, 40_000) { 0.6 }
        assertEquals("chưa phát được tới hết bài: bài mới chưa kêu", 0f, music.volume, 0f)
        assertFalse("đứng yên ở chỗ vào, không phát câm", music.playWhenReady)
        assertEquals(0L, music.position)
        assertEquals("bài trước giữ chỗ", 0.1f, old.volume, 1e-6f)
        assertEquals(0, old.released)
        var entered = -1L
        val after = mutableListOf<Pair<String, Float>>()
        repeat(4_000) {
            val events = stream(music, 50) { 0.6 }
            if (entered < 0 && music.volume > 0f) entered = music.bufferedPosition
            if (entered >= 0) after += events
        }
        assertTrue("vào khi đã có ~54 % bài ($entered)", entered in 104_000L..112_000L)
        assertTrue("đã vào thì không hụt lần nào ($after)", after.none { it.first == "đứng" })
        Handler.advance(MusicCues.mix.fadeMs + 500L)
        assertEquals("bài mới đủ mức", 0.1f, music.volume, 1e-4f)
        assertEquals("bài trước mờ đi rồi nhả", 1, old.released)
    }

    @Test fun aStreamedSongOnlyNeedsToKeepUpUntilItsCueStopsUsingIt() {
        // Cùng bài 200 s tải 0,6x, nhưng mốc chỉ dùng nó tới giây 60 (mốc khác bài vào ở 60, mờ ra fadeSeconds): chỉ cần tải kịp tới 62 s của bài -
        // vào khi đã có ~33 s (62 - 0,6 x 62 / 1,3) thay vì ~108 s của bản tới-hết-bài (U30F 02-11: bài 863 s mà mốc dùng 342 s, nhạc vào ở 350 s thay vì 98 s).
        val cue = MusicCues.Cue(0.0, 60.0, "music/a.mp3", null)
        field("lastSeconds").setDouble(MusicBed, 0.0)
        field("cues").set(MusicBed, listOf(cue, MusicCues.Cue(60.0, 300.0, "music/b.mp3", null)))
        val music = FakePlayer().also { it.state = Player.STATE_BUFFERING; it.playWhenReady = true; it.position = 0; it.bufferedPosition = 3_000 }
        field("current").set(MusicBed, bed(music, cue).also { b -> b.javaClass.getDeclaredField("streamed").also { it.isAccessible = true }.setBoolean(b, true) })
        field("playing").setBoolean(MusicBed, true)
        invoke("startFade")
        var entered = -1L
        val after = mutableListOf<Pair<String, Float>>()
        repeat(2_000) {
            val events = stream(music, 50) { 0.6 }
            if (entered < 0 && music.volume > 0f) entered = music.bufferedPosition
            if (entered >= 0 && music.position < 40_000) after += events
        }
        assertTrue("vào khi đã có ~33 s ($entered)", entered in 31_000L..37_000L)
        assertTrue("đã vào thì không hụt trong phần mốc dùng ($after)", after.none { it.first == "đứng" })
    }

    @Test fun whereTheStreamedSongStopsSoundingIsRecomputedWhenTheCuesChange() {
        // Mốc dùng cả bài 200 s (tới-hết-bài: ~108 s mới vào); giữa lúc chờ, chuỗi mốc đổi (sửa mốc, đổi chương - sync đặt `cues` và `cue` của bài đang
        // chờ, dòng "cùng bài sang mốc kề"): mốc chỉ còn tới giây 60 chương, giọng ở 20 -> cần tải kịp 42 + 2 s mờ ra: vào khi có ~24 s, không giữ số cũ.
        val whole = MusicCues.Cue(0.0, 1000.0, "music/a.mp3", null)
        field("lastSeconds").setDouble(MusicBed, 0.0)
        field("cues").set(MusicBed, listOf(whole))
        val music = FakePlayer().also { it.state = Player.STATE_BUFFERING; it.playWhenReady = true; it.position = 0; it.bufferedPosition = 3_000 }
        val waiting = bed(music, whole).also { b -> b.javaClass.getDeclaredField("streamed").also { it.isAccessible = true }.setBoolean(b, true) }
        field("current").set(MusicBed, waiting)
        field("playing").setBoolean(MusicBed, true)
        invoke("startFade")
        stream(music, 20_000) { 0.6 }
        assertEquals("mốc dùng cả bài: chưa vào", 0f, music.volume, 0f)
        val short = MusicCues.Cue(0.0, 60.0, "music/a.mp3", null)
        field("cues").set(MusicBed, listOf(short, MusicCues.Cue(60.0, 300.0, "music/b.mp3", null)))
        waiting.javaClass.getDeclaredField("cue").also { it.isAccessible = true }.set(waiting, short)
        field("lastSeconds").setDouble(MusicBed, 20.0)
        var entered = -1L
        repeat(600) {
            stream(music, 50) { 0.6 }
            if (entered < 0 && music.volume > 0f) entered = music.bufferedPosition
        }
        assertTrue("vào khi đã có ~24 s ($entered)", entered in 22_000L..27_000L)
    }

    @Test fun aHeldStreamedSongAboutToRunOutFadesOutInsteadOfStoppingAtFullLevel() {
        // Web MSE 02-11 (11 KB/s): mốc mới chờ cổng nên bài cũ giữ chỗ quá chỗ thôi kêu của nó; nó cũng đang tải dở rồi đứt - đệm cạn ở đủ mức, 8 lần cụt.
        // Bài cũ sắp hết đệm (dưới underrunLowMs) thì thôi giữ, mờ hết trong underrunFadeMs trước khi cạn. Như musicBed.ts / musicbed.cpp.
        val old = FakePlayer().also { it.state = Player.STATE_READY; it.playWhenReady = true; it.position = 100_000; it.bufferedPosition = 107_000 }
        val oldBed = streamedBed(old)
        setLogical(oldBed, 0.1f)
        old.volume = 0.1f
        oldBed.javaClass.getDeclaredField("fadeStep").also { it.isAccessible = true }.setFloat(oldBed, 0.1f * 50 / MusicCues.mix.fadeMs)
        @Suppress("UNCHECKED_CAST") (field("fading").get(MusicBed) as MutableList<Any>).add(oldBed)
        val music = FakePlayer().also { it.state = Player.STATE_BUFFERING; it.playWhenReady = true; it.position = 0; it.bufferedPosition = 3_000 }
        field("current").set(MusicBed, streamedBed(music))
        field("playing").setBoolean(MusicBed, true)
        invoke("startFade")
        var dry: Float? = null
        var held = -1f
        repeat(240) { step ->
            Handler.advance(50)
            music.bufferedPosition += 5 // 0,1x: bài mới chờ cổng suốt lượt
            if (old.released == 0) {
                if (old.bufferedPosition - old.position >= 50) old.position += 50 else if (dry == null) dry = old.volume // bài cũ đứt tải: đệm cạn
            }
            if (step == 60) held = old.volume // còn ~4 s phía trước
        }
        assertEquals("còn đệm: vẫn giữ chỗ", 0.1f, held, 1e-6f)
        assertTrue("mờ hết trước khi đệm cạn (âm lượng lúc cạn: $dry)", dry == null || dry!! < 0.001f)
        assertEquals("bài cũ mờ hết thì nhả", 1, old.released)
        assertEquals("bài mới vẫn chờ cổng", 0f, music.volume, 0f)
    }

    @Test fun streamPaceFoldsTheFirstBurstAndNeedsASecondOfMeasurement() {
        val pace = StreamPace()
        pace.add(0, 0)
        pace.add(200, 30_000) // phần đã có sẵn dồn về một lèo: không phải tốc độ tải
        assertNull(pace.rate(900))
        for (t in 300L..3_000L step 100) pace.add(t, 30_000 + (t - 200) / 2) // mốc gốc là cuối đợt dồn
        assertEquals(0.5, pace.rate(3_000)!!, 0.01)
        assertFalse(pace.playsThrough(3_000, 31_400, 0, 200_000))
        // 0,5x từ đầu bài 200 s: cần đã có 200 - 0,5 x 200 / 1,3 = 123 s.
        assertTrue(pace.playsThrough(3_000, 124_000, 0, 200_000))
        assertFalse(pace.playsThrough(3_000, 122_000, 0, 200_000))
        val fast = StreamPace()
        for (t in 0L..2_000L step 100) fast.add(t, 10 * t) // 10x
        assertTrue(fast.playsThrough(2_000, 100_000, 98_000, 200_000))
        assertFalse("chưa có đủ 2 giây trước con trỏ", fast.playsThrough(2_000, 100_000, 98_500, 200_000))
        assertTrue("tải trọn thì phát được", pace.playsThrough(3_000, 200_000, 0, 200_000))
        assertFalse("chưa đo được tốc độ thì chưa chắc", StreamPace().playsThrough(0, 124_000, 0, 200_000))
    }

    @Test fun smallSeeksThroughPlaybackDoNotSeekTheMusicOrRestartItsFade() {
        val voice = FakePlayer().also { it.state = Player.STATE_READY; it.item = MediaItem.Builder().setMediaId("1").build() }
        val music = FakePlayer().also { it.state = Player.STATE_READY; it.volume = 0.1f; it.position = 50_000 }
        val cue = MusicCues.Cue(0.0, 100.0, "music/a.mp3", -20.0)
        field("book").set(MusicBed, "seek-book")
        field("closedBook").set(MusicBed, "")
        field("chapter").setInt(MusicBed, 1)
        field("cues").set(MusicBed, listOf(cue))
        field("lastSeconds").setDouble(MusicBed, 10.0)
        val current = bed(music, cue)
        current.javaClass.getDeclaredField("entering").also { it.isAccessible = true }.setBoolean(current, false)
        setLogical(current, 0.1f)
        field("current").set(MusicBed, current)
        // Context is only a presence check on this already-open, already-cached path.
        val unsafeClass = Class.forName("sun.misc.Unsafe")
        val unsafe = unsafeClass.getDeclaredField("theUnsafe").also { it.isAccessible = true }.get(null)
        field("context").set(MusicBed, unsafeClass.getMethod("allocateInstance", Class::class.java).invoke(unsafe, android.content.ContextWrapper::class.java))
        Playback.player = voice.player
        Playback::class.java.getDeclaredField("bookId").also { it.isAccessible = true }.set(Playback, "seek-book")
        Playback::class.java.getDeclaredField("chapters").also { it.isAccessible = true }.set(Playback, listOf(Playback.Chapter(1, "Chapter", "1.mp3", 100.0)))
        val sync = Playback::class.java.getDeclaredMethod("syncMusic", Boolean::class.javaPrimitiveType).also { it.isAccessible = true }
        for (seconds in listOf(13.0, 10.0, 10.5)) {
            Playback.seekTo(seconds)
            sync.invoke(Playback, true) // same callback used by Playback's voice ticker
            assertEquals(0, music.seeks)
            assertEquals(50_000L, music.position)
            assertEquals(0.1f, music.volume, 1e-6f)
            assertEquals(0, music.released)
        }
        Playback.seekTo(15.0) // positive control: > 3 s must realign the music
        sync.invoke(Playback, true)
        assertEquals(1, music.seeks)
        assertEquals(15_000L, music.position)
    }

    // ---- Hẹn giờ ngủ: nhạc nền nhỏ dần cùng giọng (a103 F6) ----

    @Test fun sleepFadeScalesThePhysicalVolumeButTheFadeInStillEndsAtTheLogicalGoal() {
        val fake = FakePlayer().also { it.state = Player.STATE_READY }
        val current = bed(fake)
        field("current").set(MusicBed, current)
        MusicBed.setSleepFade(0.5f)
        Handler.advance(0)
        invoke("startFade")
        Handler.advance(3000) // mờ vào 2 s
        assertEquals("mức logic tới đích", 0.1f, logical(current), 1e-6f)
        assertEquals("âm lượng thật = đích x hệ số", 0.05f, fake.volume, 1e-6f)
        assertFalse("mờ vào xong thì ngừng (không tính theo mức đã nhân)", current.javaClass.getDeclaredField("entering").also { it.isAccessible = true }.getBoolean(current))
        assertFalse("ticker đã nghỉ", field("fadingTicker").getBoolean(MusicBed))
    }

    @Test fun fadeOutTakesTheSameTimeWhateverTheSleepFactor() {
        for (factor in listOf(1f, 0.25f)) {
            Handler.reset()
            field("fadingTicker").setBoolean(MusicBed, false)
            field("sleepFactor").setFloat(MusicBed, factor)
            val fake = FakePlayer().also { it.state = Player.STATE_READY }
            val old = bed(fake)
            setLogical(old, 0.1f)
            fake.volume = 0.1f * factor
            setFadeStep(old, 0.0025f) // 40 nhịp = 2 s
            @Suppress("UNCHECKED_CAST")
            (field("fading").get(MusicBed) as MutableList<Any>).add(old)
            invoke("startFade")
            Handler.advance(990) // 20 nhịp (t = 0..950): đã bớt một nửa
            assertEquals("giữa chừng ($factor)", 0.05f * factor, fake.volume, 1e-5f)
            assertEquals(0, fake.released)
            Handler.advance(1100) // quá nhịp thứ 40 (t = 1950)
            assertEquals("hết đúng lúc ($factor)", 1, fake.released)
        }
    }

    @Test fun handoverCopiesTheLogicalLevelSoTheSleepFactorIsAppliedOnlyOnce() {
        val oldFake = FakePlayer().also { it.state = Player.STATE_READY }
        val p3Fake = FakePlayer().also { it.state = Player.STATE_READY }
        val old = bed(oldFake)
        val p3 = bed(p3Fake)
        setLogical(old, 0.1f)
        field("sleepFactor").setFloat(MusicBed, 0.5f)
        oldFake.volume = 0.05f
        val handoverClass = Class.forName("vn.abook.player.MusicBed\$Handover")
        val handover = handoverClass.declaredConstructors.single().also { it.isAccessible = true }.newInstance(p3, old, 0L, 0L)
        MusicBed::class.java.declaredMethods.single { it.name == "completeHandover" }.also { it.isAccessible = true }.invoke(MusicBed, handover, 1.0, 1.0)
        assertEquals("mức logic sang P3 nguyên vẹn", 0.1f, logical(p3), 1e-6f)
        assertEquals("P3 nhân hệ số đúng một lần", 0.05f, p3Fake.volume, 1e-6f)
        assertEquals("a87 cũ tắt", 0f, oldFake.volume, 0f)
    }

    @Test fun cancellingTheSleepFadeRestoresTheMusicForCurrentAndFadingBeds() {
        val a = FakePlayer().also { it.state = Player.STATE_READY }
        val b = FakePlayer().also { it.state = Player.STATE_READY }
        val current = bed(a)
        val leaving = bed(b)
        setLogical(current, 0.1f)
        setLogical(leaving, 0.06f)
        field("current").set(MusicBed, current)
        @Suppress("UNCHECKED_CAST")
        (field("fading").get(MusicBed) as MutableList<Any>).add(leaving)
        MusicBed.setSleepFade(0.2f)
        Handler.advance(0)
        assertEquals(0.02f, a.volume, 1e-6f)
        assertEquals("bài đang mờ chéo cũng nhỏ dần", 0.012f, b.volume, 1e-6f)
        MusicBed.setSleepFade(1f)
        Handler.advance(0)
        assertEquals(0.1f, a.volume, 1e-6f)
        assertEquals(0.06f, b.volume, 1e-6f)
    }
}
