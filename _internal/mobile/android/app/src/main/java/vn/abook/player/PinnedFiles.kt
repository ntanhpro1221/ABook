package vn.abook.player

import org.json.JSONObject
import java.io.EOFException
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.InterruptedIOException
import java.net.HttpURLConnection
import java.net.SocketException
import java.net.UnknownHostException
import vn.abook.player.net.FastConnect
import java.security.MessageDigest
import java.util.zip.GZIPInputStream
import java.util.zip.ZipInputStream
import javax.net.ssl.SSLException

/**
 * Files a downloadable module needs ("Gói nhạc" [MusicStudentSetup], "Giọng VieNeu" [vn.abook.player.vieneu.VieneuModule]): each one pinned by
 * size + SHA-256, fetched over plain HTTPS into `.part`, resumed with Range after a cut, checked, and only then renamed - a file under its real
 * name in [dir] has always been checked. A stamp ([STAMP]: name -> pinned SHA-256 at download time) tells which files a newer app pins
 * differently, without hashing hundreds of MB at every start.
 */
class PinnedFiles(private val dir: File, private val base: String, private val stampName: String = STAMP,
                  private val freeBytes: (File) -> Long = { it.usableSpace },
                  private val output: (File) -> java.io.OutputStream = { it.outputStream() }) {
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
    class SpaceError : IOException("Bạn giải phóng bộ nhớ trên điện thoại rồi bấm Thử lại.")

    /** The connection ended before the whole file came (a cut without an error): the network, not the file. */
    class ShortRead(message: String) : IOException(message)

    /** What the listener reads when a download failed ([message], next to the Thử lại button) and the raw cause for "Chi tiết" ([detail]; empty
     *  when the sentence says it all). */
    class Failure(val message: String, val detail: String)

    /** The download was stopped on request ([Progress.cancelled]): not an error, and never retried. */
    class Cancelled : Exception("đã huỷ")

    private val stampFile get() = File(dir, stampName)

    fun file(part: Part) = File(dir, part.name)

    fun hasBytes(part: Part): Boolean = artifacts(part).any { it.isFile && it.length() > 0 }

    private fun artifacts(part: Part): List<File> = listOf(file(part), wireFile(part)).distinct().flatMap {
        listOf(it, File(it.path + ".part"), File(it.path + ".part.etag"))
    }

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

    /** Bytes of [part] still to cross the network: 0 when current, else its wire size less what a cut download left in `.part` (resumed with
     *  Range) - the size on "Tải" / "Cập nhật" / resume after Huỷ. */
    fun left(part: Part, stamp: Map<String, String> = readStamp()): Long {
        if (isCurrent(part, stamp)) return 0L
        val have = PartResume.point(File(wireFile(part).path + ".part"), part.wireSize).first
        return if (have > part.wireSize) part.wireSize else part.wireSize - have
    }

    /** Where [part]'s wire form is fetched to: the file itself, or its gzip / zip next to it. */
    private fun wireFile(part: Part): File {
        val packed = part.packed ?: return file(part)
        return File(file(part).path + if (packed.member != null) ".zip" else ".gz")
    }

    /** Of [parts], those this app pins differently from what was downloaded (none when nothing was ever downloaded: "missing", not "old"). */
    fun outdated(parts: List<Part>): List<Part> {
        val stamp = readStamp()
        return if (stamp.isEmpty()) emptyList() else parts.filter { !isCurrent(it, stamp) }
    }

    /** Fetch every part of [parts] that is not current; the stamp is written after each file, so a stop keeps what is done. */
    fun download(parts: List<Part>, progress: Progress) {
        dir.mkdirs()
        val needed = parts.filter { !isCurrent(it) }.sumOf { left(it) + if (it.packed != null) it.size else 0L }
        if (needed > 0 && freeBytes(dir) < needed + DownloadSpace.MARGIN) throw SpaceError()
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
            artifacts(part).forEach { it.delete() }
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
        val wire = wireFile(part)
        val partial = File(wire.path + ".part")
        if (packed == null || !wire.isFile || wire.length() != part.wireSize || sha256(wire) != packed.sha256) {
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
            PartResume.tagFile(partial).delete()
        }
        if (packed != null) {
            val raw = File(target.path + ".part")
            try {
                if (packed.member == null) {
                    GZIPInputStream(wire.inputStream().buffered()).use { input -> output(raw).use { input.copyTo(it, 1 shl 16) } }
                } else {
                    ZipInputStream(wire.inputStream().buffered()).use { zip ->
                        while (true) {
                            val entry = zip.nextEntry ?: throw IOException("thiếu ${packed.member}")
                            if (entry.name == packed.member) break
                        }
                        output(raw).use { zip.copyTo(it, 1 shl 16) }
                    }
                }
            } catch (failure: IOException) {
                raw.delete()
                if (failure is java.util.zip.ZipException || failure is EOFException) {
                    wire.delete()
                    throw ChecksumError()
                }
                throw failure
            }
            if (raw.length() != part.size || sha256(raw) != part.sha256) {
                raw.delete()
                wire.delete()
                throw ChecksumError()
            }
            promote(raw, target, part.name)
            wire.delete()
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
        // Phần dở chỉ nối tiếp khi biết nó thuộc phiên bản nào (ETag cạnh nó, PartResume); không thì tải lại - băm cuối vẫn bắt file sai.
        var (have, tag) = PartResume.point(partial, size)
        if (have == 0L) PartResume.discard(partial)
        progress.current(have) // what a cut download left, even when it is already whole: the first report of a file is what was there
        if (have < size) {
            val url = if (remote.startsWith("https://") || remote.startsWith("http://")) remote else base + remote
            val connection = FastConnect.get(url, 20_000) { // theo chuyển hướng (CDN), Range đi lại ở từng chặng
                it.readTimeout = 30_000
                if (have > 0) {
                    it.setRequestProperty("Range", "bytes=$have-")
                    it.setRequestProperty("If-Range", tag)
                }
            }
            try {
                val code = connection.responseCode
                if (code == 416 && have > 0) {
                    // The part is longer than the file the server holds now: drop it; the retry asks for the whole file.
                    PartResume.discard(partial)
                    throw ShortRead("phần tải dở không còn khớp file trên máy chủ - tải lại từ đầu")
                }
                if (code != HttpURLConnection.HTTP_PARTIAL && code != HttpURLConnection.HTTP_OK) throw IOException("máy chủ trả mã $code")
                when (PartResume.answer(code, connection.getHeaderField("Content-Range"), connection.getHeaderField("ETag"), have, tag)) {
                    PartResume.Answer.RESUME -> {}
                    PartResume.Answer.WHOLE -> have = 0 // the server ignored Range, or the file changed: start over
                    // A 206 that is not the tail of the file the part came from: drop the part; the retry asks for the whole file.
                    PartResume.Answer.STALE_TAIL -> {
                        PartResume.discard(partial)
                        throw ShortRead("phần tải dở không còn khớp file trên máy chủ - tải lại từ đầu")
                    }
                }
                connection.inputStream.use { input ->
                    FileOutputStream(partial, have > 0).use { output ->
                        // The version goes down AFTER the part was cut, so an old part never carries a new tag.
                        if (have == 0L) PartResume.stamp(partial, connection.getHeaderField("ETag"))
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
        if (partial.length() != size) throw ShortRead("tải chưa đủ (${partial.length()}/$size byte)")
        if (sha256(partial) != expected) {
            PartResume.discard(partial)
            throw ChecksumError()
        }
    }

    companion object {
        const val STAMP = "bundle.json"
        private const val RETRIES = 3

        /** A download that could not reach the server (no name lookup, timeout, connection cut) - same sentence as the desktop
         *  (abook/webui/studio_setup.py NETWORK_FAILURE). */
        const val NETWORK_FAILURE = "Chưa kết nối được tới máy chủ tải. Kiểm tra mạng rồi bấm Thử lại."

        /** The network, not the file or the phone, failed: anywhere in the cause chain. */
        fun isNetwork(error: Throwable): Boolean = generateSequence(error) { it.cause }.take(5).any {
            it is UnknownHostException || it is InterruptedIOException || it is SocketException || it is SSLException || it is EOFException || it is ShortRead
        }

        /** The listener's sentence for a failed download of [what] ("giọng VieNeu"): network -> [NETWORK_FAILURE]; a damaged file -> say so; anything
         *  else -> a plain Vietnamese sentence, with the raw error kept for "Chi tiết" (a66: "Unable to resolve host …" was shown as is). Same rule as
         *  the desktop's `studio_setup.download_failure`. */
        fun failure(what: String, error: Throwable): Failure = when {
            generateSequence(error) { it.cause }.take(5).any {
                it is SpaceError || it.message.orEmpty().contains("ENOSPC", true) || it.message.orEmpty().contains("No space left", true)
            } -> Failure("Bạn giải phóng bộ nhớ trên điện thoại rồi bấm Thử lại.", technical(error))
            error is ChecksumError -> Failure("$what tải về bị hỏng — bạn bấm Thử lại để tải lại.", "")
            isNetwork(error) -> Failure(NETWORK_FAILURE, technical(error))
            else -> Failure("Chưa tải được $what — bạn bấm Thử lại hoặc xem Chi tiết để nhờ hỗ trợ.", technical(error))
        }

        /** The raw error, short enough for a folded "Chi tiết". */
        fun technical(error: Throwable): String = "${error.javaClass.simpleName}: ${error.message.orEmpty()}".trimEnd(' ', ':').take(300)

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
