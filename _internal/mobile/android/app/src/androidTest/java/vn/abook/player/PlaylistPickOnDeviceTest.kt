package vn.abook.player

import android.os.Bundle
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Máy tự chọn danh sách phát ([Playlists.pick]) trên máy Android THẬT (máy ảo): regex / Normalizer của ICU Android phải cho đúng mã và điểm như
 * Python trên bộ ví dụ dùng chung (tests/fixtures/playlist_picker/cases.json, assets của bài thử), luật đóng kèm đọc được từ asset của app
 * (`playlist_picker.json`), và đo thời gian `pick` trên ca dài nhất: 200 lần, in mili-giây mỗi lần (Log tag PICK_TIMING + kết quả của bài thử).
 */
@RunWith(AndroidJUnit4::class)
class PlaylistPickOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()

    private val shared: JSONObject by lazy { JSONObject(instrumentation.context.assets.open("cases.json").use { String(it.readBytes(), Charsets.UTF_8) }) }

    private fun chapters(item: JSONObject): Sequence<String> = (0 until item.getJSONArray("chapters").length()).asSequence().map { item.getJSONArray("chapters").getString(it) }

    @Test
    fun the_bundled_asset_is_the_reference_lexicon_and_every_shared_case_matches_python() {
        val bundled = DeviceMusic.bundledPicker(instrumentation.targetContext)
        assertNotNull("asset playlist_picker.json không có trong APK", bundled)
        assertTrue(StrictJson.equal(shared.getJSONObject("picker"), bundled!!))
        val cases = shared.getJSONArray("cases")
        for (index in 0 until cases.length()) {
            val item = cases.getJSONObject(index)
            val picker = if (item.has("picker")) item.opt("picker") as? JSONObject else bundled
            val expected = if (item.isNull("expect")) null else item.getString("expect")
            assertEquals(item.getString("name"), expected, Playlists.pick(picker, item.getString("title"), chapters(item)))
        }
        val selection = shared.getJSONArray("selection")
        for (index in 0 until selection.length()) {
            val item = selection.getJSONObject(index)
            val (picker, source) = Playlists.usablePicker(item.opt("manifest") as? JSONObject, bundled)
            assertEquals(item.getString("name"), item.getString("source"), source)
            assertEquals(item.getString("name"), item.getString("expect"), Playlists.pick(picker, item.getString("title"), chapters(item)))
        }
    }

    @Test
    fun pick_time_on_the_longest_case() {
        val bundled = DeviceMusic.bundledPicker(instrumentation.targetContext)!!
        val cases = shared.getJSONArray("cases")
        val longest = (0 until cases.length()).map { cases.getJSONObject(it) }.filter { !it.has("picker") }.maxByOrNull { item -> chapters(item).sumOf { it.length } }!!
        val title = longest.getString("title")
        repeat(20) { Playlists.pick(bundled, title, chapters(longest)) } // khởi động
        val started = System.nanoTime()
        repeat(200) { Playlists.pick(bundled, title, chapters(longest)) }
        val millis = (System.nanoTime() - started) / 1e6 / 200
        val line = "ca=${longest.getString("name")} ${"%.2f".format(millis)} ms mỗi lần (200 lần, ${chapters(longest).sumOf { it.length }} ký tự vào)"
        Log.i("PICK_TIMING", line)
        instrumentation.sendStatus(0, Bundle().apply { putString("PICK_TIMING", line) })
        println("PICK_TIMING $line")
        assertTrue("pick chậm: $millis ms", millis < 500)
    }
}
