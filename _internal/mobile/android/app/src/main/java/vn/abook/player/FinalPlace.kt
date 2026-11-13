package vn.abook.player

import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.UUID

/** Small teardown journal, independent of Store's monitor and its potentially large imports.
 * Only this owned snapshot is synced on main. Record updates and queue drains stay on the writers.
 * A process killed after service destruction replays the journal before publishing Store.root.
 */
internal object FinalPlace {
    private const val PREFIX = ".final-place-"
    private val writer = UUID.randomUUID().toString()

    fun token(sequence: Long): JSONObject = JSONObject().put("writer", writer).put("sequence", sequence)

    fun retire(file: File) { check(file.delete()) { "Could not retire final place journal" } }

    fun persist(root: File, sequence: Long, book: String, record: String?, chapter: Int,
                position: Long, duration: Double, anchor: String?): File {
        val target = File(root, "$PREFIX${System.currentTimeMillis()}-${sequence.toString().padStart(20, '0')}-${UUID.randomUUID()}.json")
        val temporary = File(root, target.name + ".part")
        val text = JSONObject().put("book", book).put("record", record).put("chapter", chapter)
            .put("position", position).put("duration", duration).put("anchor", anchor).put("checkpoint", token(sequence)).toString()
        FileOutputStream(temporary).use { stream ->
            stream.write(text.toByteArray(Charsets.UTF_8))
            stream.fd.sync()
        }
        AtomicFiles.replace(temporary, target)
        return target
    }

    /** Called under Store's monitor during cold recovery; delete only after a successful record write.
     * Failed/corrupt journals remain available for diagnosis and make init fail instead of losing the place.
     */
    fun recover(root: File) {
        val journals = root.listFiles { file -> file.name.startsWith(PREFIX) && file.name.endsWith(".json") }.orEmpty().sortedBy { it.name }
        for (file in journals) {
            val data = JSONObject(file.readText(Charsets.UTF_8))
            val book = Store.requireBookId(data.getString("book"))
            val record = data.optString("record").ifEmpty { null }
            // Deleted/moved profiles must never resurrect or write into the replacement profile.
            if (record == null || Store.holds(book, record)) {
                Store.progress(book, data.getInt("chapter"), data.getLong("position") / 1000.0,
                    data.getDouble("duration"), data.optString("anchor").ifEmpty { null }?.let(::JSONObject), record,
                    localCheckpoint = data.getJSONObject("checkpoint"))
            }
            retire(file)
        }
    }
}
