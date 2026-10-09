package vn.abook.player

import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.zip.GZIPInputStream
import java.util.zip.ZipInputStream

/**
 * Files a downloadable module needs ("Gói nhạc" [MusicStudentSetup], "Giọng VieNeu" [vn.abook.player.vieneu.VieneuModule]): each one pinned by
 * size + SHA-256, fetched over plain HTTPS into `.part`, resumed with Range after a cut, checked, and only then renamed - a file under its real
 * name in [dir] has always been checked. A stamp ([STAMP]: name -> pinned SHA-256 at download time) tells which files a newer app pins
 * differently, without hashing hundreds of MB at every start.
 */
class PinnedFiles(private val dir: File, private val base: String, private val stampName: String = STAMP) {
    /** One file. [name] is its path inside [dir] (subfolders allowed); [remote] its path under the base URL, or a full `https://` URL.
     *  [packed]: the server holds a gzip of it, or a zip (a wheel) it is one [Packed.member] of - fetched, checked, unpacked, checked again. */
    class Part(
        val name: String,
        val sha256: String,
        val size: Long,
        val remote: String = name,
        val packed: Packed? = null,
        /** A runtime library must match the code in the APK: an old one cannot run, an old model still can. */
        val blocking: Boolean = false,
        /** What the listener calls this part ("có bản mới" card). */
        val label: String = "Model nghe nhạc",
    ) {
        /** Bytes that cross the network for this file. */
        val wireSize get() = packed?.size ?: size
    }

    /** The wire form of a [Part]: gzip of the file, or (with [member]) a zip archive holding it under that path. */
    class Packed(val sha256: String, val size: Long, val member: String? = null)

    /** Bytes of the file being fetched ([current]) and of a file just finished ([done], its wire size). */
    interface Progress {
        fun current(bytes: Long)
        fun done(part: Part)

        /** The listener tapped Huỷ: the download stops at the next read (the `.part` stays, the next download resumes it with Range). */
        fun cancelled(): Boolean = false
    }

    class ChecksumError : IOException("sai mã kiểm")

    /** The download was stopped on request ([Progress.cancelled]): not an error, and never retried. */
    class Cancelled : Exception("đã huỷ")

    private val stampFile get() = File(dir, stampName)

    fun file(part: Part) = File(dir, part.name)

    /** Present with the pinned size (usable even when a newer pin exists: the old file keeps working until the listener updates). */
    fun present(part: Part): Boolean = file(part).let { it.isFile && it.length() == part.size }

    fun readStamp(): Map<String, String> = try {
        val parts = JSONObject(stampFile.readText(Charsets.UTF_8)).getJSONObject("parts")
        parts.keys().asSequence().associateWith { parts.getString(it) }
    } catch (_: Exception) {
        emptyMap()
    }

    fun writeStamp(parts: Map<String, String>) {
        val listed = JSONObject()
        parts.forEach { (name, sha) -> listed.put(name, sha) }
        dir.mkdirs()
        Store.writeAtomic(stampFile, JSONObject().put("version", 1).put("parts", listed).toString())
    }

    fun isCurrent(part: Part, stamp: Map<String, String> = readStamp()) = stamp[part.name] == part.sha256 && present(part)

    /** Of [parts], those this app pins differently from what was downloaded (none when nothing was ever downloaded: "missing", not "old"). */
    fun outdated(parts: List<Part>): List<Part> {
        val stamp = readStamp()
        return if (stamp.isEmpty()) emptyList() else parts.filter { !isCurrent(it, stamp) }
    }

    /** Fetch every part of [parts] that is not current; the stamp is written after each file, so a stop keeps what is done. */
    fun download(parts: List<Part>, progress: Progress) {
        dir.mkdirs()
        val stamp = readStamp().toMutableMap()
        for (part in parts) {
            if (progress.cancelled()) throw Cancelled()
            if (isCurrent(part, stamp)) continue
            // A file of the right size without a stamp (fetched before stamps existed): hash it once and accept it if it matches.
            if (!(present(part) && sha256(file(part)) == part.sha256)) fetch(part, progress)
            stamp[part.name] = part.sha256
            writeStamp(stamp)
            progress.done(part)
        }
    }

    /** Delete [parts] and forget them in the stamp. */
    fun remove(parts: List<Part>) {
        val stamp = readStamp().toMutableMap()
        for (part in parts) {
            file(part).delete()
            stamp.remove(part.name)
        }
        if (stamp.isEmpty()) stampFile.delete() else writeStamp(stamp)
    }

    /** Delete [parts] and the stamp (a module that downloaded fine but cannot be opened: the next tap starts clean). */
    fun wipe(parts: List<Part>) {
        parts.forEach { file(it).delete() }
        stampFile.delete()
    }

    /**
     * One file: `.part`, resumed with Range when part of it is there, size + SHA-256 checked, then renamed. A packed file is fetched in its wire
     * form (checked on its own), unpacked into `.part`, the real file checked, then renamed. A cut connection is retried a few times.
     */
    private fun fetch(part: Part, progress: Progress) {
        val target = file(part).also { it.parentFile?.mkdirs() }
        val packed = part.packed
        val wire = if (packed == null) target else File(target.path + if (packed.member != null) ".zip" else ".gz")
        val partial = File(wire.path + ".part")
        var attempts = 0
        while (true) {
            if (progress.cancelled()) throw Cancelled()
            try {
                transfer(part.remote, packed?.sha256 ?: part.sha256, part.wireSize, partial, progress)
                break
            } catch (failure: IOException) {
                if (failure is ChecksumError || ++attempts >= RETRIES) throw failure
            }
        }
        promote(partial, wire, part.name)
        if (packed != null) {
            val raw = File(target.path + ".part")
            try {
                if (packed.member == null) {
                    GZIPInputStream(wire.inputStream().buffered()).use { input -> raw.outputStream().use { input.copyTo(it, 1 shl 16) } }
                } else {
                    ZipInputStream(wire.inputStream().buffered()).use { zip ->
                        while (true) {
                            val entry = zip.nextEntry ?: throw IOException("thiếu ${packed.member}")
                            if (entry.name == packed.member) break
                        }
                        raw.outputStream().use { zip.copyTo(it, 1 shl 16) }
                    }
                }
            } catch (failure: IOException) {
                raw.delete()
                wire.delete()
                throw ChecksumError()
            }
            wire.delete()
            if (raw.length() != part.size || sha256(raw) != part.sha256) {
                raw.delete()
                throw ChecksumError()
            }
            promote(raw, target, part.name)
        }
        // Dynamically loaded code (.so) is made read-only, as Android 14+ requires.
        if (part.name.endsWith(".so")) target.setReadOnly()
    }

    private fun promote(from: File, to: File, name: String) {
        if (from.renameTo(to)) return
        to.delete()
        if (!from.renameTo(to)) throw IOException("không ghi được file $name")
    }

    private fun transfer(remote: String, expected: String, size: Long, partial: File, progress: Progress) {
        var have = partial.length()
        if (have > size) {
            partial.delete()
            have = 0
        }
        if (have < size) {
            val url = if (remote.startsWith("https://") || remote.startsWith("http://")) remote else base + remote
            val connection = URL(url).openConnection() as HttpURLConnection
            try {
                connection.connectTimeout = 20_000
                connection.readTimeout = 30_000
                connection.instanceFollowRedirects = true
                if (have > 0) connection.setRequestProperty("Range", "bytes=$have-")
                when (val code = connection.responseCode) {
                    HttpURLConnection.HTTP_PARTIAL -> {}
                    HttpURLConnection.HTTP_OK -> have = 0 // the server ignored Range: start over
                    else -> throw IOException("máy chủ trả mã $code")
                }
                connection.inputStream.use { input ->
                    FileOutputStream(partial, have > 0).use { output ->
                        val buffer = ByteArray(1 shl 16)
                        var written = have
                        progress.current(written)
                        while (true) {
                            if (progress.cancelled()) throw Cancelled()
                            val read = input.read(buffer)
                            if (read < 0) break
                            if (written + read > size) throw IOException("file lớn hơn dự kiến")
                            output.write(buffer, 0, read)
                            written += read
                            progress.current(written)
                        }
                    }
                }
            } finally {
                connection.disconnect()
            }
        }
        if (partial.length() != size) throw IOException("tải chưa đủ (${partial.length()}/$size byte)")
        if (sha256(partial) != expected) {
            partial.delete()
            throw ChecksumError()
        }
    }

    companion object {
        const val STAMP = "bundle.json"
        private const val RETRIES = 3

        fun sha256Of(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

        fun sha256(file: File): String {
            val digest = MessageDigest.getInstance("SHA-256")
            file.inputStream().use { input ->
                val buffer = ByteArray(1 shl 16)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    digest.update(buffer, 0, read)
                }
            }
            return digest.digest().joinToString("") { "%02x".format(it) }
        }
    }
}
