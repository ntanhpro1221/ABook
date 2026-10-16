package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest

/**
 * Plan nhạc theo cảnh của MỘT cuốn chỉ có chữ, đường N0 - bản Kotlin của `music_nnscene.SceneBook` + `build_chapter` + `chapter_cues`: dựng TỪNG chương khi cần
 * (câu của chương -> đoạn nhạc -> bài), nhớ bản ghi mỗi chương một file trong `directory` (tên thư mục mang khoá: đổi khoá là dựng lại từ đầu).
 *
 * Chương dựng sau các chương liền trước ĐÃ dựng thì tiếp "bài vừa dùng" của chúng (`recent`, cửa sổ [SceneChooser.RECENT_SCENES]), nên dựng lần lượt từ chương
 * đầu ra đúng như dựng một lượt cả cuốn; nhảy tới chương xa thì chương ấy dựng không lịch sử. Nhánh `keep` / `kept_siblings` của Python (nối chương bằng bài
 * đã chọn) không cần ở đây: bản ghi của chương trước ĐÃ là kết quả chọn, chỉ lấy lại dòng bài.
 *
 * Không đụng Android: chữ chương, danh mục bài và việc "bài này dùng được không" đều do người gọi đưa vào ([DeviceScenes] làm phần máy thật).
 */
class SceneBook(
    private val directory: File,
    private val order: List<Int>,
    /** Chữ chương đã bỏ các dòng người nghe chọn bỏ ([vn.abook.player.readaloud.Paragraphs.withoutLines]); null = chương chưa có chữ ở máy này. */
    private val body: (Int) -> String?,
    private val choice: SceneChoice,
    /** Bài quanh đích êm, đúng thứ tự `near` của danh mục (ô rồi bài trong ô). */
    private val candidates: () -> List<SceneTrack>,
) {
    private val lock = Any()

    private fun file(chapterId: Int) = File(directory, "$chapterId.json")

    /** Mã băm chữ chương sau khi bỏ dòng `skip` - đổi chữ hay dòng bỏ thì bản ghi chương dựng lại (`music_nnscene.text_sha`). */
    fun textSha(chapterId: Int): String? = body(chapterId)?.let { sha1(it.toByteArray(Charsets.UTF_8)) }

    /** Bản ghi đã dựng của chương, hay null (chưa dựng, hỏng, hay chữ chương đã đổi). */
    fun read(chapterId: Int): JSONObject? = read(chapterId, textSha(chapterId))

    private fun read(chapterId: Int, sha: String?): JSONObject? {
        if (sha == null) return null
        val record = try {
            JSONObject(file(chapterId).readText(Charsets.UTF_8))
        } catch (_: Exception) {
            return null
        }
        return record.takeIf { it.optString("textSha") == sha && it.optInt("version") == FORMAT_VERSION }
    }

    /** Bỏ bản ghi của chương (dựng lại lần hỏi kế): bài đã chọn mà máy này hoá ra không dùng được (quá cỡ khi tải) - `music_nnscene.SceneBook.discard`. */
    fun discard(chapterId: Int) {
        synchronized(lock) { file(chapterId).delete() }
    }

    /** Các bài (chính + bài anh em) mà một bản ghi dùng. */
    fun links(record: JSONObject): Set<String> {
        val found = LinkedHashSet<String>()
        val list = record.optJSONArray("scenes") ?: return found
        for (index in 0 until list.length()) {
            val scene = list.optJSONObject(index) ?: continue
            scene.optString("link", "").takeIf { it.isNotEmpty() && it != "null" }?.let { found.add(it) }
            val siblings = scene.optJSONArray("siblings") ?: continue
            for (at in 0 until siblings.length()) siblings.optJSONObject(at)?.optString("link", "")?.takeIf { it.isNotEmpty() }?.let { found.add(it) }
        }
        return found
    }

    /** Dựng (hay lấy lại) bản ghi của chương; null khi chương không có chữ. Danh mục không tải được thì ném lỗi (người gọi thử lại sau). */
    fun build(chapterId: Int): JSONObject? = synchronized(lock) {
        val text = body(chapterId) ?: return null
        val sha = sha1(text.toByteArray(Charsets.UTF_8))
        read(chapterId, sha)?.let { return it }
        val segments = SceneSegmenter.script(text)
        val scenes = SceneScenes.chapterScenes(chapterId, segments)
        val paragraphs = SceneSegmenter.paragraphIds(segments.map { it.text }, text)
        val paragraphOf = HashMap<Int, Int>()
        for ((index, segment) in segments.withIndex()) paragraphOf[segment.id] = paragraphs[index] // trùng id: câu sau thắng (dict của Python)
        val tracks = candidates()
        val chosen = SceneChooser(choice) { _, _ -> tracks }.choose(scenes, recentBefore(chapterId))
        var seconds = 0.0
        for (length in SceneScenes.durations(segments)) seconds += length // sum() của Python 3.11: cộng lần lượt
        val record = JSONObject().put("version", FORMAT_VERSION).put("chapterId", chapterId).put("textSha", sha).put("segments", segments.size)
            .put("seconds", Py.round(seconds, 3))
            .put("scenes", JSONArray(chosen.map { sceneJson(it, paragraphOf[it.scene.firstSegment] ?: 0) }))
        directory.mkdirs()
        Store.writeAtomic(file(chapterId), record.toString().toByteArray(Charsets.UTF_8))
        record
    }

    /**
     * Các bài vừa dùng ở những chương liền trước đã dựng (liền một mạch, theo thứ tự sách), vừa đủ cho cửa sổ của [SceneChooser]; chương liền trước
     * chưa dựng thì không có lịch sử (`SceneBook.history`).
     */
    private fun recentBefore(chapterId: Int): MutableList<String> {
        val position = order.indexOf(chapterId)
        val recent = ArrayList<String>()
        if (position <= 0) return recent
        val found = ArrayList<JSONObject>()
        var runs = 0
        for (previous in order.subList(0, position).asReversed()) {
            val record = read(previous, textSha(previous)) ?: break
            found.add(0, record)
            runs = linkRuns(found).size
            if (runs > SceneChooser.RECENT_SCENES) break
        }
        return linkRuns(found).toMutableList()
    }

    private fun linkRuns(records: List<JSONObject>): List<String> {
        val runs = ArrayList<String>()
        for (record in records) {
            val scenes = record.optJSONArray("scenes") ?: continue
            for (index in 0 until scenes.length()) {
                val link = scenes.getJSONObject(index).optString("link", "").takeIf { it.isNotEmpty() && it != "null" } ?: continue
                if (runs.isEmpty() || runs.last() != link) runs.add(link)
            }
        }
        return runs
    }

    private fun sceneJson(chosen: ChosenScene, paragraph: Int): JSONObject {
        val scene = chosen.scene
        val out = JSONObject().put("chapterId", scene.chapterId).put("firstSegment", scene.firstSegment).put("lastSegment", scene.lastSegment)
            .put("start", scene.start).put("end", scene.end).put("reason", scene.reason).put("lines", scene.lines).put("key", chosen.key)
            .put("pinned", chosen.pinned).put("link", chosen.link ?: JSONObject.NULL).put("distance", chosen.distance ?: JSONObject.NULL)
            .put("continued", chosen.continued).put("silenced", chosen.silenced).put("pinUnavailable", chosen.pinUnavailable)
            .put("stepDb", chosen.stepDb ?: JSONObject.NULL).put("stopAt", chosen.stopAt ?: JSONObject.NULL).put("paragraph", paragraph)
        out.put("siblings", JSONArray(chosen.siblings.map { JSONObject().put("at", it.at).put("link", it.link) }))
        return out
    }

    private fun chosenOf(json: JSONObject): ChosenScene {
        val scene = SceneScene(
            json.getInt("chapterId"), json.getInt("firstSegment"), json.getInt("lastSegment"), json.getDouble("start"), json.getDouble("end"),
            json.getString("reason"), json.optInt("lines"),
        )
        return ChosenScene(scene).also { chosen ->
            chosen.key = json.getString("key")
            chosen.pinned = json.optBoolean("pinned")
            chosen.link = json.optString("link", "").takeIf { it.isNotEmpty() && it != "null" }
            chosen.distance = if (json.isNull("distance")) null else json.optDouble("distance")
            chosen.continued = json.optBoolean("continued")
            chosen.silenced = json.optBoolean("silenced")
            chosen.pinUnavailable = json.optBoolean("pinUnavailable")
            chosen.stepDb = if (json.isNull("stepDb")) null else json.optDouble("stepDb")
            chosen.stopAt = if (json.isNull("stopAt")) null else json.optDouble("stopAt")
            val siblings = json.optJSONArray("siblings")
            if (siblings != null) for (index in 0 until siblings.length()) {
                val sibling = siblings.getJSONObject(index)
                chosen.siblings.add(SceneSibling(sibling.getDouble("at"), sibling.getString("link")))
            }
        }
    }

    /**
     * Trả lời của `musicSceneCues` cho một bản ghi (hình của tuyến máy tính `_scene_cues`): `cues` = mốc nhạc của chương theo giây ƯỚC
     * (`music_plan.chapter_cues`, kẹp ở độ dài ước), mốc mở một cảnh mang `firstSegment` = mã đoạn màn đọc nơi cảnh bắt đầu (`music_nnscene.chapter_cues`;
     * mốc nối bài anh em không có); thêm `scenes` (lý do, câu đầu / cuối, đoạn, bài, vòng lặp của bài) cho giao diện.
     */
    fun response(record: JSONObject): JSONObject {
        val chapterId = record.getInt("chapterId")
        val seconds = record.getDouble("seconds")
        val list = record.optJSONArray("scenes") ?: JSONArray()
        val chosen = (0 until list.length()).map { chosenOf(list.getJSONObject(it)) }
        val heads = HashMap<String, Int>()
        for (index in 0 until list.length()) heads[chosen[index].key] = list.getJSONObject(index).optInt("paragraph")
        val cues = JSONArray()
        for (cue in SceneMusic.chapterCues(chosen, chapterId, seconds)) {
            val item = JSONObject().put("start", cue.start).put("end", cue.end).put("link", cue.link).put("key", cue.key)
            if (cue.sibling) item.put("sibling", true)
            if (cue.tail) item.put("tail", true)
            if (cue.steps.isNotEmpty()) item.put("steps", JSONArray(cue.steps.map { JSONObject().put("at", it.at).put("db", it.db) }))
            if (!cue.sibling) heads[cue.key]?.let { item.put("firstSegment", it) }
            cues.put(item)
        }
        val byLink = HashMap<String, SceneTrack>()
        for (track in candidates()) byLink.putIfAbsent(track.link, track)
        val scenes = JSONArray()
        for (index in 0 until list.length()) {
            val json = list.getJSONObject(index)
            val item = JSONObject().put("key", json.getString("key")).put("firstSegment", json.getInt("firstSegment"))
                .put("lastSegment", json.getInt("lastSegment")).put("paragraph", json.optInt("paragraph")).put("reason", json.getString("reason"))
                .put("start", json.getDouble("start")).put("end", json.getDouble("end")).put("link", json.opt("link") ?: JSONObject.NULL)
            chosen[index].link?.let { link -> item.put("loop", loopJson(byLink[link])) }
            scenes.put(item)
        }
        return JSONObject().put("cues", cues).put("scene", true).put("estSeconds", seconds).put("scenes", scenes)
    }

    /** Vòng lặp của bài ([MusicCues.loopBounds], cùng hàm với trình phát); vô cực (chưa biết độ dài) ghi null. */
    private fun loopJson(track: SceneTrack?): JSONObject {
        val bounds = MusicTimeline.loopBounds(MusicTimeline.TrackInfo(track?.seconds?.takeIf { it != 0.0 } ?: track?.duration, track?.audibleStart, track?.audibleEnd))
        fun finite(value: Double): Any = if (value.isInfinite() || value.isNaN()) JSONObject.NULL else value
        return JSONObject().put("start", finite(bounds.start)).put("end", finite(bounds.end)).put("period", finite(bounds.period)).put("crossfade", bounds.crossfade)
    }

    companion object {
        /** Đổi khi cách tách câu / dựng đoạn / chọn bài / ánh xạ sang đoạn màn đọc đổi: bản ghi đã dựng không dùng lại. */
        const val ENGINE_VERSION = 2 // 2: plan cũ có thể chọn bài quá cỡ (cỡ chỉ có ở mảnh tracks/, ô cells/ không có)
        const val FORMAT_VERSION = 1

        fun sha1(bytes: ByteArray): String = MessageDigest.getInstance("SHA-1").digest(bytes).joinToString("") { "%02x".format(it) }
    }
}
