package vn.abook.player.vieneu

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.PinnedFiles
import vn.abook.player.PinnedFiles.Part
import vn.abook.player.Store
import java.io.File

/**
 * The runtime files every downloadable voice needs - ONNX Runtime's libraries ("ort") and sea-g2p ("g2p"), the same pins in every module - kept
 * ONCE on the phone in [dir] (`files/runtime`), whichever voice is downloaded first. A module looks here first, then in [elsewhere] (another
 * feature's folder with the same pinned files, used in place and never written: "Gói nhạc"), and only then downloads, into [dir].
 *
 * Who uses what is written in [dir] ([USERS]: part id -> module keys): a module adds itself when it starts a download and takes itself out when its
 * last choice needing a part is removed; the part's files go only when no module is left on it, so removing one voice never breaks another.
 * Downloads into [dir] hold [fetching], the users list and removals another lock - each the same object for every instance on the same folder,
 * and a removal never waits for a download (it cannot touch files being fetched: their module is already a user).
 */
class SharedRuntime(val dir: File, private val elsewhere: List<File> = emptyList()) {
    val pinned = PinnedFiles(dir, "", VoiceModule.STAMP)
    val fetching: Any = lockFor("fetch")
    private val lock: Any = lockFor("users")
    private val usersFile = File(dir, USERS)

    private fun lockFor(use: String): Any = synchronized(LOCKS) { LOCKS.getOrPut(dir.absolutePath + "#" + use) { Any() } }

    /** Every file of [parts] here (any version: an older one keeps working until updated). */
    fun has(parts: List<Part>): Boolean = parts.isNotEmpty() && parts.all { pinned.present(it) }

    /** When [dir] does not have [parts]: the first [elsewhere] folder holding every one at its pinned size, else null. */
    fun elsewhere(parts: List<Part>): File? = if (has(parts)) null else elsewhere.firstOrNull { folder ->
        parts.isNotEmpty() && parts.all { part -> File(folder, part.name).let { it.isFile && it.length() == part.size } }
    }

    /** Part id -> keys of the modules using it. */
    fun users(): Map<String, Set<String>> = try {
        val json = JSONObject(usersFile.readText(Charsets.UTF_8))
        json.keys().asSequence().associateWith { id -> json.getJSONArray(id).let { array -> (0 until array.length()).map { array.getString(it) }.toSet() } }
    } catch (_: Exception) {
        emptyMap()
    }

    private fun writeUsers(users: Map<String, Set<String>>) {
        val kept = users.filterValues { it.isNotEmpty() }
        if (kept.isEmpty()) {
            usersFile.delete()
            return
        }
        dir.mkdirs()
        Store.writeAtomic(usersFile, JSONObject().apply { kept.forEach { (id, keys) -> put(id, JSONArray(keys.sorted())) } }.toString())
    }

    /** Module [module] uses parts [ids]. */
    fun use(module: String, ids: Collection<String>) = synchronized(lock) {
        if (ids.isEmpty()) return@synchronized
        val users = users().toMutableMap()
        for (id in ids) users[id] = users[id].orEmpty() + module
        writeUsers(users)
    }

    /** Module [module] no longer uses the parts of [parts] (id -> files); those no other module uses are deleted. Returns their ids. */
    fun release(module: String, parts: Map<String, List<Part>>): List<String> = synchronized(lock) {
        if (parts.isEmpty()) return@synchronized emptyList()
        val users = users().toMutableMap()
        for (id in parts.keys) users[id] = users[id].orEmpty() - module
        writeUsers(users)
        val freed = parts.keys.filter { users[it].isNullOrEmpty() }
        val files = freed.flatMap { parts.getValue(it) }
        pinned.remove(files)
        files.map { it.name.substringBefore('/') }.distinct().forEach { File(dir, it).deleteRecursively() }
        freed
    }

    companion object {
        /** Part ids kept here rather than in a module's own folder. */
        val PARTS = setOf("ort", "g2p")
        const val USERS = "users.json"
        private val LOCKS = HashMap<String, Any>()

        /** This phone's: `files/runtime`, with "Gói nhạc"'s folder (its ONNX Runtime) to use in place. */
        fun of(ctx: Context) = SharedRuntime(File(ctx.filesDir, "runtime"), listOf(File(ctx.filesDir, "music/student")))
    }
}
