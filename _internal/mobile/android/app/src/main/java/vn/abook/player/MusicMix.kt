package vn.abook.player

import android.content.Context
import org.json.JSONObject

/**
 * Hằng số trộn nhạc nền: MỘT file `abook/webui/assets/music_mix.json` cho máy chủ (webui/music_mix.py), trình phát web
 * (ui/src/listen/musicBed.ts) và điện thoại. File nằm trong assets của app (app/build.gradle); [MusicBed] nạp qua `context.assets`
 * ([load]), test JVM nạp đúng file ấy từ đĩa ([parse]).
 */
class MusicMix(json: JSONObject) {
    val fadeMs = millis(json, "fadeSeconds")
    val siblingFadeMs = millis(json, "siblingFadeSeconds")
    val stepRampMs = millis(json, "stepRampSeconds")
    /** X của lặp mờ chéo: tới E - X thì phần tử mới của chính bài vào từ A (MIX_QA 3.2). */
    val loopCrossfadeSeconds = json.getDouble("loopCrossfadeSeconds")
    // Số giây đúng như trong file - dòng thời gian của bản xuất ([MusicTimeline]) tính bằng giây như máy tính, không qua ms làm tròn.
    val fadeSeconds = json.getDouble("fadeSeconds")
    val siblingFadeSeconds = json.getDouble("siblingFadeSeconds")
    val stepRampSeconds = json.getDouble("stepRampSeconds")
    /** Mốc cuối kết muộn nhất ở (độ dài chương - số này) để nhạc mờ xong trước khi giọng hết (music_plan.clamp_to_chapter). */
    val chapterEndFadeSeconds = json.getDouble("chapterEndFadeSeconds")

    companion object {
        const val FILE = "music_mix.json"

        private fun millis(json: JSONObject, key: String): Long = Math.round(json.getDouble(key) * 1000)

        fun parse(text: String): MusicMix = MusicMix(JSONObject(text))

        fun load(context: Context): MusicMix =
            context.assets.open(FILE).use { parse(it.readBytes().toString(Charsets.UTF_8)) }
    }
}
