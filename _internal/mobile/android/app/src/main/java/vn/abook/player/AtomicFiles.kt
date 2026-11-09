package vn.abook.player

import java.io.File
import java.io.IOException

/** Publish a closed temporary file without deleting the previously committed destination. */
internal object AtomicFiles {
    fun replace(source: File, target: File) {
        // Android's POSIX rename replaces existing files. Windows File.renameTo may refuse them.
        // Keep the host NIO implementation separate so Android API 24 never loads its API 26 calls.
        if (File.separatorChar == '\\') {
            WindowsAtomicReplace.move(source, target)
        } else if (!source.renameTo(target)) {
            throw IOException(S.s_chua_thay_duoc_file_0_50ad2750(target.name))
        }
    }
}
