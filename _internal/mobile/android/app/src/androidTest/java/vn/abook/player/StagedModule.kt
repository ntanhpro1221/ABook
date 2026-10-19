package vn.abook.player

import vn.abook.player.vieneu.VoiceModule
import java.io.File

/** A voice module's files pushed with adb (laid out as the module downloads them) put where [module] keeps them - the runtime parts (ort/, g2p/) in the folder every
 *  voice shares, the rest in the module's own - then accepted exactly as a real download: every file hashed against this app's pins, nothing fetched. */
object StagedModule {
    fun install(staged: File, module: VoiceModule, choices: List<String>) {
        fun home(path: String) = module.folderFor(path.substringBefore('/'))
        staged.walkTopDown().filter { it.isFile }.forEach { source ->
            val path = source.relativeTo(staged).invariantSeparatorsPath
            val target = File(home(path), path)
            if (target.length() != source.length()) {
                target.parentFile!!.mkdirs()
                target.delete()
                source.copyTo(target, overwrite = true)
            }
            if (target.name.endsWith(".so")) target.setReadOnly()
        }
        for ((folder, parts) in module.parts(choices).groupBy { home(it.name) }) PinnedFiles(folder, "", VoiceModule.STAMP).download(parts, object : PinnedFiles.Progress {
            override fun current(bytes: Long) = Unit
            override fun done(part: PinnedFiles.Part) = Unit
        })
    }
}
