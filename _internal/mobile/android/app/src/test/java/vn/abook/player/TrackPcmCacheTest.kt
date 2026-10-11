package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.DataOutputStream

/** [TrackPcmCache]: bài đã giải mã trên đĩa cho bản xuất kèm nhạc. */
class TrackPcmCacheTest {
    @get:Rule
    val temp = TemporaryFolder()

    /** Bộ giải mã giả: bài "t<n>" = n giây của mẫu k -> (k % 1000) - 500 ở mọi kênh; bài "hỏng" ném lỗi; đếm số lần gọi. */
    private class Fake : TrackPcmCache.TrackDecoder {
        val calls = ArrayList<String>()
        override fun decode(track: String, rate: Int, channels: Int, out: java.io.OutputStream) {
            calls.add("$track@$rate/$channels")
            if (track == "hỏng") error("giải mã hỏng")
            val frames = track.removePrefix("t").toInt() * rate
            val data = DataOutputStream(out)
            for (k in 0 until frames) repeat(channels) {
                val s = (k % 1000) - 500
                data.write(s and 0xff)
                data.write((s shr 8) and 0xff)
            }
            data.flush()
        }
    }

    @Test
    fun a_track_is_decoded_once_per_rate_and_channels_and_reads_little_endian_shorts() {
        val fake = Fake()
        TrackPcmCache(temp.newFolder("pcm"), fake).use { cache ->
            val pcm = cache.get("t2", 100, 2)!!
            assertEquals(200, pcm.frames)
            assertEquals(2, pcm.channels)
            assertEquals(-500 / 32768.0, pcm.sample(0, 1), 0.0)
            assertEquals((199 - 500) / 32768.0, pcm.sample(199, 0), 0.0)
            cache.get("t2", 100, 2)
            assertEquals(-500 / 32768.0, cache.get("t2", 50, 1)!!.sample(0, 0), 0.0)
            assertEquals(listOf("t2@100/2", "t2@50/1"), fake.calls)
            assertEquals(200L * 2 * 2 + 100L * 2, cache.bytes)
        }
    }

    @Test
    fun a_track_that_does_not_decode_is_null_and_not_tried_again() {
        val fake = Fake()
        val dir = temp.newFolder("pcm")
        TrackPcmCache(dir, fake).use { cache ->
            assertNull(cache.get("hỏng", 100, 1))
            assertNull(cache.get("hỏng", 100, 1))
            assertNull(cache.get("t0", 100, 1)) // không ra mẫu nào cũng là không lấy được
            assertEquals(listOf("hỏng@100/1", "t0@100/1"), fake.calls)
            assertTrue(dir.listFiles()!!.none { it.name.endsWith(".part") })
        }
    }

    @Test
    fun over_the_limit_the_least_recently_used_track_goes_never_the_one_just_taken() {
        val fake = Fake()
        val one = TrackPcmCache.bytesFor(1.0, 100, 1) // 200 byte
        TrackPcmCache(temp.newFolder("pcm"), fake, limitBytes = 2 * one).use { cache ->
            cache.get("t1", 100, 1) // a
            cache.get("t1", 50, 1)  // b (100 byte)
            cache.get("t1", 100, 1) // a dùng lại -> b là lâu nhất
            cache.get("t2", 100, 1) // c 400 byte: bỏ b rồi a, giữ c dù tự nó đã quá trần
            assertEquals(2 * one, cache.bytes)
            cache.get("t1", 50, 1)  // b phải giải mã lại
            assertEquals(listOf("t1@100/1", "t1@50/1", "t2@100/1", "t1@50/1"), fake.calls)
        }
    }
}
