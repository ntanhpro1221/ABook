package vn.abook.player

import android.content.Context
import vn.abook.player.PinnedFiles.Part
import vn.abook.player.readaloud.SupertonicModule
import vn.abook.player.vieneu.VieneuModule
import vn.abook.player.vieneu.VoiceModule
import java.io.File

/**
 * The runtime files every downloadable module needs - ONNX Runtime's libraries ("ort") and sea-g2p ("g2p"), the same pins everywhere - kept ONCE
 * on the phone in [dir] (`files/runtime`), whichever of "Gói nhạc", "Giọng VieNeu" or "Giọng Supertonic" is downloaded first; the others find
 * them here and do not count or fetch them again.
 *
 * Nothing records who uses what: when a module is removed, the parts it leaves go only if no other module that is installed AT THAT MOMENT needs
 * them ([users]: each module's own folder and stamp, read from disk) and no download in flight has claimed them ([claim]) - so no record can be
 * lost or go stale. Downloads into [dir] hold [fetching] (two taps at once: the second finds the files current); a removal holds another lock
 * and never waits for a download. Both locks are the same objects for every instance on the same folder.
 */
class SharedRuntime(val dir: File, private val users: List<User>) {
    /** A module that keeps its own files in [folder] (listed in its stamp [stamp]) and needs runtime parts [needs] while any of them is there. */
    class User(val folder: File, val stamp: String, val needs: Set<String>) {
        /** Any of its own files on disk (a runtime part listed by an older layout does not count). */
        fun installed(): Boolean = PinnedFiles(folder, "", stamp).readStamp().keys.any { name ->
            name.substringBefore('/') !in PARTS && File(folder, name).isFile
        }
    }

    val pinned = pinnedFrom("")
    val fetching: Any = lockFor("fetch")
    private val lock: Any = lockFor("remove")
    private val claims: MutableMap<String, Set<String>> = synchronized(CLAIMS) { CLAIMS.getOrPut(dir.absolutePath) { HashMap() } }

    private fun lockFor(use: String): Any = synchronized(LOCKS) { LOCKS.getOrPut(dir.absolutePath + "#" + use) { Any() } }

    /** The files here, fetched from [base] when a part names only a path. */
    fun pinnedFrom(base: String) = PinnedFiles(dir, base, VoiceModule.STAMP)

    /** Every file of [parts] here (any version: an older one keeps working until updated). */
    fun has(parts: List<Part>): Boolean = parts.isNotEmpty() && parts.all { pinned.present(it) }

    /** A download by module [key] is about to use parts [ids]: a removal meanwhile keeps them. Held in memory until [done]. */
    fun claim(key: String, ids: Collection<String>) = synchronized(lock) {
        if (ids.isNotEmpty()) claims[key] = claims[key].orEmpty() + ids
    }

    fun done(key: String) = synchronized(lock) { claims.remove(key) }

    /** Part ids some installed module or some download in flight needs now. */
    fun inUse(): Set<String> = synchronized(lock) { users.filter { it.installed() }.flatMap { it.needs }.toSet() + claims.values.flatten() }

    /** A module has removed its own files and no longer needs [parts] (id -> files): those [inUse] does not name are deleted. Returns their ids. */
    fun release(parts: Map<String, List<Part>>): List<String> = synchronized(lock) {
        val needed = inUse()
        val freed = parts.keys.filter { it !in needed }
        val files = freed.flatMap { parts.getValue(it) }
        pinned.remove(files)
        files.map { it.name.substringBefore('/') }.distinct().forEach { File(dir, it).deleteRecursively() }
        freed
    }

    companion object {
        /** Part ids kept here rather than in a module's own folder (a part's files sit under the folder of the same name). */
        val PARTS = setOf("ort", "g2p")
        private val LOCKS = HashMap<String, Any>()
        private val CLAIMS = HashMap<String, MutableMap<String, Set<String>>>()

        /** Runtime parts among [ids]. */
        fun runtimeOf(ids: Collection<String>): Set<String> = ids.filter { it in PARTS }.toSet()

        /** ONNX Runtime's two libraries for [abi] from "Gói nhạc"'s server, as full URLs (empty when this ABI has no build). */
        fun ortParts(abi: String?): List<Part> =
            OrtRuntime.parts(abi).map { Part(it.name, it.sha256, it.size, MusicStudentSetup.BASE + it.remote, it.packed, true, it.label) }

        /** This phone's: `files/runtime`, used by the music package and both voices. */
        fun of(ctx: Context): SharedRuntime = inFiles(ctx.filesDir)

        /** The runtime folder and its users as laid out under the app's [files] folder. */
        fun inFiles(files: File): SharedRuntime =
            SharedRuntime(File(files, "runtime"), listOf(
                User(File(files, MusicStudentSetup.FOLDER), PinnedFiles.STAMP, setOf("ort")),
                User(File(files, VieneuModule.FOLDER), VoiceModule.STAMP, runtimeOf(VieneuModule.NEEDS.values.flatten())),
                User(File(files, SupertonicModule.FOLDER), VoiceModule.STAMP, runtimeOf(SupertonicModule.NEEDS)),
            ))
    }
}
