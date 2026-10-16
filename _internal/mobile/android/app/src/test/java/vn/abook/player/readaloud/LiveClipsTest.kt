package vn.abook.player.readaloud

import androidx.media3.common.C
import androidx.media3.common.DataReader
import androidx.media3.common.Format
import androidx.media3.common.util.ParsableByteArray
import androidx.media3.extractor.DefaultExtractorInput
import androidx.media3.extractor.Extractor
import androidx.media3.extractor.ExtractorOutput
import androidx.media3.extractor.PositionHolder
import androidx.media3.extractor.SeekMap
import androidx.media3.extractor.TrackOutput
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import vn.abook.player.Streaming
import java.io.File
import java.io.IOException
import java.io.InterruptedIOException
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/** Clip Edge đang lớn (uxfix57): đọc chờ / hết / hỏng / ngắt, đổi chỗ file, và bộ tách mp3 của ExoPlayer phát được + tua được trong phần đã ghi khi chưa biết độ dài. */
class LiveClipsTest {
    private val dir = java.nio.file.Files.createTempDirectory("live-clips").toFile()

    @After
    fun cleanUp() {
        dir.deleteRecursively()
    }

    private fun write(name: String, data: ByteArray) = File(dir, name).also { it.writeBytes(data) }

    @Test
    fun aReaderWaitsForBytesThatHaveNotBeenWrittenYet() {
        val entry = LiveClips.create()
        val file = write("a.mp3", ByteArray(10) { it.toByte() })
        entry.grew(file, 4)
        val reader = entry.reader(0)
        val buffer = ByteArray(100)
        assertEquals(4, reader.read(buffer, 0, 100)) // chỉ phần đã ghi
        val late = AtomicReference<Int>()
        val worker = Thread { late.set(reader.read(buffer, 4, 100)) }.also { it.start() }
        Thread.sleep(150)
        assertTrue("chưa có byte mới thì phải chờ", worker.isAlive)
        entry.grew(file, 10)
        worker.join(5_000)
        assertEquals(6, late.get())
        assertEquals((0 until 10).map { it.toByte() }, buffer.take(10))
        reader.close()
    }

    @Test
    fun endOfInputComesOnlyWhenTheClipIsDoneAndEverythingWasRead() {
        val entry = LiveClips.create()
        val file = write("b.mp3", ByteArray(10) { 5 })
        entry.grew(file, 10)
        val reader = entry.reader(0)
        val buffer = ByteArray(100)
        assertEquals(10, reader.read(buffer, 0, 100))
        val end = AtomicReference<Int>()
        val worker = Thread { end.set(reader.read(buffer, 0, 100)) }.also { it.start() }
        Thread.sleep(150)
        assertTrue(worker.isAlive) // hết byte mà clip chưa xong: chờ
        entry.finish(10)
        worker.join(5_000)
        assertEquals(-1, end.get())
        assertEquals(-1, entry.reader(10).read(buffer, 0, 100)) // mở lại sau khi xong, ở cuối file
        assertEquals(10, entry.reader(0).read(buffer, 0, 100)) // hay từ đầu
        assertTrue(entry.done)
    }

    @Test
    fun aReaderOpenedMidFileStartsThere() {
        val entry = LiveClips.create()
        entry.grew(write("c.mp3", ByteArray(10) { it.toByte() }), 10)
        entry.finish(10)
        val buffer = ByteArray(100)
        assertEquals(4, entry.reader(6).read(buffer, 0, 100))
        assertEquals(listOf<Byte>(6, 7, 8, 9), buffer.take(4))
    }

    @Test
    fun aFailedClipThrowsEvenWhenBytesAreLeft() {
        val entry = LiveClips.create()
        entry.grew(write("d.mp3", ByteArray(10)), 10)
        entry.fail(VoiceException("Mất mạng", offline = true))
        try {
            entry.reader(0).read(ByteArray(10), 0, 10)
            fail("đáng ra lỗi")
        } catch (error: IOException) {
            assertTrue(error.message!!.contains("Mất mạng"))
        }
        entry.finish(10) // hỏng rồi thì xong muộn không cứu được
        assertFalse(entry.done)
    }

    @Test
    fun aClipThatStopsGrowingEndsAsAnErrorAfterTheStallLimit() {
        val entry = LiveClips.create()
        entry.grew(write("e.mp3", ByteArray(4)), 4)
        val reader = entry.reader(4, stallMs = 300)
        val began = System.nanoTime()
        try {
            reader.read(ByteArray(10), 0, 10)
            fail("đáng ra lỗi")
        } catch (error: IOException) {
            assertTrue((System.nanoTime() - began) / 1_000_000 >= 250)
        }
    }

    @Test
    fun aReaderWaitingForBytesLeavesWhenItsThreadIsInterrupted() {
        val entry = LiveClips.create()
        entry.grew(write("f.mp3", ByteArray(4)), 4)
        val reader = entry.reader(4)
        val outcome = AtomicReference<Throwable>()
        val worker = Thread { try { reader.read(ByteArray(10), 0, 10) } catch (error: Throwable) { outcome.set(error) } }.also { it.start() }
        Thread.sleep(150)
        worker.interrupt()
        worker.join(5_000)
        assertTrue(outcome.get() is InterruptedIOException)
    }

    @Test
    fun aClipThatMovedIntoTheCacheIsReadFromItsNewPlace() {
        val entry = LiveClips.create()
        val data = ByteArray(10) { (it + 1).toByte() }
        val old = write("g.mp3.part", data)
        entry.grew(old, 10)
        entry.finish(10)
        val moved = write("g.mp3", data)
        entry.relocate(moved)
        old.delete()
        val buffer = ByteArray(10)
        assertEquals(10, entry.reader(0).read(buffer, 0, 10))
        assertTrue(buffer.contentEquals(data))
    }

    @Test
    fun theUriCarriesTheIdAndOnlyTheLastFewClipsAreKept() {
        val entry = LiveClips.create("abc-123")
        assertEquals("abooklive://abc-123", LiveClips.uri(entry.id))
        assertEquals("abc-123", LiveClips.idOf(LiveClips.uri(entry.id)))
        assertEquals(entry, LiveClips.get("abc-123"))
        repeat(20) { LiveClips.create() }
        assertNull(LiveClips.get("abc-123")) // quá cũ thì quên: ExoPlayer mở lại sẽ lỗi, người nghe được đọc lại
    }

    // ---- bộ tách mp3 của ExoPlayer trên file đang lớn -----------------------------------------------------------------------

    private class Samples : TrackOutput {
        val times = CopyOnWriteArrayList<Long>()
        override fun format(format: Format) {}
        override fun sampleData(input: DataReader, length: Int, allowEndOfInput: Boolean, sampleDataPart: Int): Int {
            val scratch = ByteArray(length)
            val read = input.read(scratch, 0, length)
            return read
        }
        override fun sampleData(data: ParsableByteArray, length: Int, sampleDataPart: Int) = data.skipBytes(length)
        override fun sampleMetadata(timeUs: Long, flags: Int, size: Int, offset: Int, cryptoData: TrackOutput.CryptoData?) {
            times += timeUs
        }
    }

    private class Output(val track: Samples) : ExtractorOutput {
        @Volatile var seekMap: SeekMap? = null
        override fun track(id: Int, type: Int): TrackOutput = track
        override fun endTracks() {}
        override fun seekMap(seekMap: SeekMap) { this.seekMap = seekMap }
    }

    private fun input(reader: LiveClips.Reader, position: Long) = DefaultExtractorInput(
        object : DataReader { override fun read(buffer: ByteArray, offset: Int, length: Int): Int = reader.read(buffer, offset, length).let { if (it < 0) C.RESULT_END_OF_INPUT else it } },
        position, C.LENGTH_UNSET.toLong(),
    )

    /** Media3 (ParsableByteArray) tự hỏi "đang chạy bài thử?" qua `Build.FINGERPRINT`, mà vỏ android.jar của bài thử JVM để null: đặt như Robolectric. */
    private fun pretendToBeUnderTest() {
        val unsafeClass = Class.forName("sun.misc.Unsafe")
        val unsafe = unsafeClass.getDeclaredField("theUnsafe").also { it.isAccessible = true }.get(null)
        val field = android.os.Build::class.java.getField("FINGERPRINT")
        val base = unsafeClass.getMethod("staticFieldBase", java.lang.reflect.Field::class.java).invoke(unsafe, field)
        val offset = unsafeClass.getMethod("staticFieldOffset", java.lang.reflect.Field::class.java).invoke(unsafe, field) as Long
        unsafeClass.getMethod("putObject", Any::class.java, Long::class.javaPrimitiveType, Any::class.java).invoke(unsafe, base, offset, "robolectric")
    }

    @Test
    fun theMp3ExtractorPlaysAndSeeksInsideWhatIsWrittenWithoutKnowingTheLength() {
        pretendToBeUnderTest()
        val frames = 200
        val entry = LiveClips.create()
        entry.grew(write("h.mp3", EdgeFake.mp3Frames(frames)), frames * 144L)
        val extractor = Streaming.liveExtractors().single()
        val samples = Samples()
        val output = Output(samples)
        val holder = PositionHolder()
        val reader = entry.reader(0)
        val source = input(reader, 0)
        assertTrue(extractor.sniff(source))
        extractor.init(output)
        // Đọc tới khi hết phần đã ghi: luồng đọc đứng chờ ở cuối (clip chưa xong) cho tới khi báo xong.
        val ended = AtomicReference<Int>()
        val done = CountDownLatch(1)
        val worker = Thread {
            var result = Extractor.RESULT_CONTINUE
            while (result == Extractor.RESULT_CONTINUE) result = extractor.read(source, holder)
            ended.set(result)
            done.countDown()
        }.also { it.start() }
        val end = System.nanoTime() + 5_000_000_000L
        while (samples.times.size < frames && System.nanoTime() < end) Thread.sleep(20)
        assertEquals("phát được mọi khung đã ghi", frames, samples.times.size)
        assertTrue("chưa xong thì còn chờ byte mới", worker.isAlive)
        entry.finish(frames * 144L)
        assertTrue(done.await(5, TimeUnit.SECONDS))
        assertEquals(Extractor.RESULT_END_OF_INPUT, ended.get())
        assertEquals(24_000L, samples.times[1] - samples.times[0]) // mỗi khung 24 ms
        // Tua: chưa biết độ dài mà vẫn tua được theo tốc độ bit không đổi.
        val seekMap = output.seekMap
        assertNotNull(seekMap)
        assertTrue(seekMap!!.isSeekable)
        val target = 100 * 24_000L
        val point = seekMap.getSeekPoints(target).first
        assertEquals(100 * 144L, point.position)
        // Như ProgressiveMediaPeriod: CÙNG bộ tách, seek tới vị trí của điểm tua, đầu đọc mới mở ở đó (clip đã xong ở đây nhưng độ dài vẫn chưa được báo cho bộ tách).
        samples.times.clear()
        extractor.seek(point.position, point.timeUs)
        val seekInput = input(entry.reader(point.position), point.position)
        var result = Extractor.RESULT_CONTINUE
        while (result == Extractor.RESULT_CONTINUE) result = extractor.read(seekInput, holder)
        assertEquals(Extractor.RESULT_END_OF_INPUT, result)
        assertEquals(frames - 100, samples.times.size)
        assertEquals(target, samples.times.first())
    }
}
