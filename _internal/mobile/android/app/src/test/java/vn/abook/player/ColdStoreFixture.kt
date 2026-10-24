package vn.abook.player

import android.content.Context
import android.content.ContextWrapper
import java.io.File
import java.lang.reflect.Field

/** Isolated singleton state and a files-only Context, without Android stub constructors. */
internal class ColdStoreFixture {
    private class FilesContext : ContextWrapper(null) {
        lateinit var directory: File
        override fun getFilesDir(): File = directory
        override fun getApplicationContext(): Context = this
    }
    val directory = BookEditsFixtures.tempDir("abook-init")
    val context = contextFor(directory)
    private val saved = linkedMapOf<Field, Any?>()

    init {
        for ((type, names) in listOf(
            Store::class.java to listOf("root", "initFilesDir", "initializingRoot", "recordsCache", "initRecovery"),
            Remote::class.java to listOf("context"),
            LibraryServer::class.java to listOf("devicesFile", "appContext", "server"),
        )) for (name in names) {
            // The new init fields need not exist when running the regression tests on the base implementation.
            val field = runCatching { type.getDeclaredField(name) }.getOrNull() ?: continue
            field.isAccessible = true
            saved[field] = field.get(null)
            if (name != "initRecovery") field.set(null, null)
        }
    }

    fun contextFor(dir: File): Context {
        val type = Class.forName("sun.misc.Unsafe")
        val unsafe = type.getDeclaredField("theUnsafe").apply { isAccessible = true }.get(null)
        return (type.getMethod("allocateInstance", Class::class.java).invoke(unsafe, FilesContext::class.java) as FilesContext)
            .apply { directory = dir }
    }

    fun field(type: Class<*>, name: String): Any? = type.getDeclaredField(name).apply { isAccessible = true }.get(null)
    fun setRoot(root: File?) = Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
    fun files(): List<String> = directory.walkTopDown().map { it.relativeTo(directory).path }.sorted().toList()
    fun restore() { saved.forEach { (field, value) -> field.set(null, value) } }
}
