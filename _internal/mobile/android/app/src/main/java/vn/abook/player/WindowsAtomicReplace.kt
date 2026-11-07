package vn.abook.player

import android.annotation.SuppressLint
import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/** Kept in its own class so Android API 24 never loads the host JVM's NIO replacement path. */
@SuppressLint("NewApi")
internal object WindowsAtomicReplace {
    fun move(source: File, target: File) {
        // Both paths are siblings. Refuse unsupported atomic moves instead of deleting the old target
        // or falling back to a copy. Windows' atomic move replaces an existing file in one operation.
        Files.move(source.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
    }
}
