package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

/** `z_distance` dùng độ lệch chuẩn `sd` và phương sai dư `vetVar` của bài như bản Python (webui/music_select.py) - số mong đợi lấy từ `z_distance`. */
class SceneChooseAxesTest {
    private val target = doubleArrayOf(0.1, 0.1, 0.2)
    private val sigma = doubleArrayOf(0.2, 0.3, 0.25)

    @Test
    fun aTracksOwnSpreadAndVetVarianceChangeTheDistanceLikeOnTheDesktop() {
        val plain = SceneTrack.of(JSONObject("""{"link": "https://x/a.mp3", "valence": 0.3, "arousal": -0.2, "tension": 0.5}"""))!!
        val rich = SceneTrack.of(JSONObject("""{"link": "https://x/a.mp3", "valence": 0.3, "arousal": -0.2, "tension": 0.5,
            "sd": {"valence": 0.05, "arousal": 0.4}, "vetVar": {"valence": 0.2, "tension": 0.6}}"""))!!
        assertEquals(1.2447987024108795, SceneChooser.zDistance(plain, target, sigma), 1e-12)
        assertEquals(1.4486320438727007, SceneChooser.zDistance(rich, target, sigma), 1e-12)
    }
}
