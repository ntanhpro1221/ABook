package vn.abook.player.readaloud

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import vn.abook.player.vieneu.VieneuUnits

/**
 * Bộ nhớ đệm các đoạn đã đọc, trong thư mục cache của app (`readaloud/`): mỗi đoạn hai file `<khoá>.<mp3|wav>` + `<khoá>.json` (độ dài, mốc từng chữ), khoá =
 * sha256(phiên bản luật đọc | nhà cung cấp | giọng | chữ) - cùng chữ cùng giọng thì nghe lại không đọc lại, đổi giọng thì đoạn mới. Giọng VieNeu đọc tên Nhật / Hàn theo luật phiên âm
 * ([Names]): đoạn nào gốc của cuốn làm nghe khác thì khoá thêm "|gốc", đoạn khác không đổi khoá (tham số `origin` của các hàm dưới đây). Cách đọc riêng người nghe
 * đặt cho cuốn ([Readings], mọi giọng) cũng thế: chỉ đoạn có từ ấy thêm dấu của các cách đọc có mặt (tham số `readings`). Quá `capBytes` (300 MB) thì xoá đoạn lâu không
 * dùng nhất trước (LRU theo giờ sửa file, mỗi lần dùng được cập nhật) xuống còn [TRIM_TO] hạn mức; dưới hạn mức thì chỉ cộng tổng đang chạy, không quét thư mục
(soát a69: mỗi lần ghi quét cả thư mục). Hạn mức theo chỗ trống ([capFor], như máy tính `cache.default_limit`). Android tự dọn thư mục cache khi máy đầy, nên mất
đoạn nào cũng chỉ là đọc lại.
 *
 * Đoạn "Làm trước" ([PrepareAhead]) được GHIM (danh sách khoá trong `pinFile`, ngoài thư mục đệm): khi dọn, đoạn không ghim đi trước hết, đoạn ghim chỉ đi khi
 * chỉ còn chúng - nghe trực tiếp không đẩy được đoạn đã làm trước ra trước khi người nghe tới. Nghe tới đoạn nào thì bỏ ghim đoạn ấy ([unpin]); phần dành cho đoạn
 * ghim có trần ([PreparePlan.SHARE]) nên chúng không chiếm hết chỗ.
 *
 * Giọng có hai bậc ([VoiceSpeed]: Supertonic, VieNeu Nano): dấu bậc đứng cuối dấu cách đọc ("fast5"; bậc chất lượng không có dấu - khoá như máy tính). Mã giọng trần
 * là "bậc nghe trực tiếp lúc này" ([tierOf]), `<mã>#q` là bậc chất lượng (mọi bản xuất), `<mã>#fast<n>` là bậc nhanh; đoạn trả về luôn mang mã giọng trần. Nghe ở bậc nhanh nhận
 * cả clip bậc chất lượng (ưu tiên nó: tiếng tốt hơn) - đổi "Tốc độ giọng trên máy" giữa chương không bắt đọc lại đoạn đã có; bậc chất lượng / bản xuất chỉ nhận bậc chất lượng.
 *
 * Giọng chạy trên máy (VieNeu, Supertonic) có thêm dấu model ([markOf]) cuối khoá: cập nhật model hay đổi lịch đọc (số bước...) thì clip cũ không trúng nữa, đoạn được đọc lại.
 */
class ClipCache(
    private val dir: File,
    private val capBytes: Long = CAP_BYTES,
    private val pinFile: File? = null,
    /** Dấu bậc nghe trực tiếp của một giọng ([VoiceSpeed.liveTag]); "" = bậc chất lượng. */
    private val tierOf: (String) -> String = { "" },
    /** Dấu model của (mã giọng trần, dấu bậc) ([vn.abook.player.vieneu.VoiceModule.mark]; "" = giọng không có model trên máy). Tính sẵn trong mô-đun, không đọc file mỗi clip. */
    private val markOf: (String, String) -> String = { _, _ -> "" },
    private val clock: () -> Long = System::currentTimeMillis,
) {
    companion object {
        /** Hạn mức thấp nhất; [capFor]: [FREE_SHARE] chỗ trống của bộ nhớ, không quá [MAX_CAP_BYTES] (máy tính cùng luật, sàn 500 MB). */
        const val CAP_BYTES = 300L * 1024 * 1024
        const val MAX_CAP_BYTES = 2L * 1024 * 1024 * 1024
        const val FREE_SHARE = 0.05
        /** Vượt hạn mức thì dọn xuống còn chừng này phần hạn mức: các lần ghi sau không phải quét lại. */
        const val TRIM_TO = 0.9

        /** Hạn mức của bộ đệm trong [dir] theo chỗ trống lúc này (thư mục chưa có: [CAP_BYTES]). */
        fun capFor(dir: File): Long = (dir.usableSpace * FREE_SHARE).toLong().coerceIn(CAP_BYTES, MAX_CAP_BYTES)
        private val EXTENSIONS = setOf("mp3", "wav")

        /**
         * Luật đọc nằm trong khoá (`cache.py` `rules_version`): đổi luật thì clip làm trước / đã nghe KHÔNG còn trúng đệm - cách đọc mới được làm lại. Số riêng của mô-đun
         * có phiên bản ([Names.RULE_VERSION]) + [CACHE_RULES]; một thay đổi luật đọc mà mô-đun của nó không có số riêng thì tăng [CACHE_RULES], ở CẢ HAI nơi (cache.py `CACHE_RULES`).
         */
        const val CACHE_RULES = 4 // 4: chỗ nối giữa các mảnh Edge được cắt lặng đuôi (uxfix50) - cùng số với cache.py
        const val RULES = "${Names.RULE_VERSION}.$CACHE_RULES"

        /** `rules`: phiên bản luật đọc trong khoá (mặc định [RULES]; test đổi để thấy khoá đổi theo). */
        fun key(provider: String, voice: String, text: String, reading: String = "", rules: String = RULES): String =
            MessageDigest.getInstance("SHA-256").digest("$rules|$provider|$voice|$text${if (reading.isEmpty()) "" else "|$reading"}".toByteArray(Charsets.UTF_8))
                .joinToString("") { "%02x".format(it) }

        /**
         * Dấu cách đọc của đoạn trong khoá (`service.clip`): gốc của cuốn (`VieneuProvider.reading_tag` - chỉ giọng đọc tên theo gốc cuốn - VieNeu, Supertonic - và chỉ đoạn mà gốc làm nghe khác; giọng nhận chữ chuẩn hoá - Edge - thêm cả [SpokenText.TAG]) và
         * cách đọc riêng có mặt trong đoạn ([Readings.tag], mọi giọng), nối bằng "+"; không có gì thì "".
         */
        fun reading(voiceId: String, text: String, origin: String?, readings: Map<String, String>? = null): String =
            listOf(
                when {
                    SpokenText.normalises(voiceId) -> SpokenText.tag(text, origin)
                    origin != null && local(voiceId) -> VieneuUnits.readingTag(text, origin)
                    else -> ""
                },
                Readings.tag(text, readings),
                ClipLift.tag(voiceId), // giọng VieNeu / Supertonic: khúc dưới trần đỉnh thật, câu ngắn nhỏ được nâng trong clip (service.clip: loudness.clip_tag)
            ).filter { it.isNotEmpty() }.joinToString("+")

        /** Giọng chạy trên máy (VieNeu, Supertonic): đọc tên theo gốc cuốn, khoá có dấu model. */
        private fun local(voiceId: String) = voiceId.startsWith("vieneu:") || voiceId.startsWith("supertonic:")

        /** "edge:vi-VN-X" -> ("edge", "vi-VN-X"). */
        fun split(voiceId: String): Pair<String, String> = voiceId.substringBefore(':') to voiceId.substringAfter(':', "")
    }

    init { dir.mkdirs() }

    val cap: Long get() = capBytes

    /** Tổng byte của các đoạn (tổng đang chạy); null = chưa đếm từ đĩa. */
    private var total: Long? = null

    private val pinned: MutableSet<String> = pinFile?.takeIf { it.isFile }
        ?.let { file -> runCatching { file.readLines().map { it.trim() }.filter { it.isNotEmpty() } }.getOrNull() }
        ?.toMutableSet() ?: mutableSetOf()

    /** (mã giọng trần, dấu bậc) của [voiceId]: dấu ghi sẵn trong mã, không có thì bậc nghe trực tiếp lúc này. */
    private fun tier(voiceId: String): Pair<String, String> = VoiceSpeed.split(voiceId).let { (base, tag) ->
        base to when {
            tag == VoiceSpeed.QUALITY_TAG -> ""
            tag.isNotEmpty() -> tag
            VoiceSpeed.family(base).isEmpty() -> ""
            else -> tierOf(base)
        }
    }

    /** Mã giọng đọc đúng bậc của khoá ([ClipReader] đưa cho giọng): giọng có hai bậc luôn mang dấu bậc, giọng khác giữ nguyên. */
    fun resolve(voiceId: String): String = tier(voiceId).let { (base, tag) -> VoiceSpeed.explicit(base, tag) }

    private fun keyOf(voiceId: String, text: String, origin: String?, readings: Map<String, String>?): String =
        tier(voiceId).let { (base, tag) -> keyAt(base, tag, text, origin, readings) }

    /** Khoá của đoạn đọc bằng giọng [base] ở bậc [tag]: dấu cách đọc, dấu bậc, dấu model (như `service.clip` của máy tính). */
    private fun keyAt(base: String, tag: String, text: String, origin: String?, readings: Map<String, String>?): String {
        val mark = if (local(base)) markOf(base, tag) else ""
        val marks = listOf(reading(base, text, origin, readings), tag, mark).filter { it.isNotEmpty() }.joinToString("+")
        return split(base).let { (provider, voice) -> key(provider, voice, text, marks) }
    }

    /** Các khoá có thể chứa clip dùng được cho [voiceId], theo thứ tự ưu tiên: bậc nhanh tìm bậc chất lượng trước rồi mới tới chính nó; bậc khác chỉ chính nó. */
    private fun lookupKeys(voiceId: String, text: String, origin: String?, readings: Map<String, String>?): List<String> {
        val (base, tag) = tier(voiceId)
        val own = keyAt(base, tag, text, origin, readings)
        return if (VoiceSpeed.isFast(tag)) listOf(keyAt(base, "", text, origin, readings), own) else listOf(own)
    }

    private fun present(key: String): Boolean = File(dir, "$key.json").isFile && EXTENSIONS.any { File(dir, "$key.$it").length() > 0L }

    private fun savePins() {
        val file = pinFile ?: return
        val part = File(file.path + ".part")
        part.writeBytes(pinned.joinToString("\n").toByteArray(Charsets.UTF_8))
        file.delete()
        part.renameTo(file)
    }

    /** Ghim đoạn (đã có hay sắp đọc): dọn bộ đệm chỉ đụng tới nó khi không còn đoạn không ghim nào. */
    @Synchronized
    fun pin(voiceId: String, text: String, origin: String? = null, readings: Map<String, String>? = null) {
        if (pinned.add(keyOf(voiceId, text, origin, readings))) savePins()
    }

    /** Người nghe đã tới đoạn này: nó lại là đoạn thường. */
    @Synchronized
    fun unpin(voiceId: String, text: String, origin: String? = null, readings: Map<String, String>? = null) {
        if (pinned.remove(keyOf(voiceId, text, origin, readings))) savePins()
    }

    @Synchronized
    fun clearPins() {
        if (pinned.isEmpty()) return
        pinned.clear()
        savePins()
    }

    @Synchronized
    fun isPinned(voiceId: String, text: String, origin: String? = null, readings: Map<String, String>? = null): Boolean =
        keyOf(voiceId, text, origin, readings) in pinned

    @Synchronized
    private fun pinnedKeys(): Set<String> = pinned.toSet()

    /** Byte các đoạn ghim đang chiếm. */
    fun pinnedBytes(): Long {
        val keys = pinnedKeys()
        if (keys.isEmpty()) return 0L
        return dir.listFiles()?.filter { it.isFile && !it.name.endsWith(".part") && it.name.substringBefore('.') in keys }?.sumOf { it.length() } ?: 0L
    }

    /** Đoạn đã có trong bộ đệm (không tính là một lần dùng - không đổi thứ tự dọn). */
    fun contains(voiceId: String, text: String, origin: String? = null, readings: Map<String, String>? = null): Boolean =
        lookupKeys(voiceId, text, origin, readings).any(::present)

    /** Độ dài (ms) clip của đoạn nếu đã có trong bộ đệm, null nếu chưa ("Xuất sách nói" ước độ dài cuốn từ clip thật); như [contains], không tính là một lần dùng. */
    fun durationMs(voiceId: String, text: String, origin: String? = null, readings: Map<String, String>? = null): Long? {
        val key = lookupKeys(voiceId, text, origin, readings).firstOrNull(::present) ?: return null
        return runCatching { JSONObject(File(dir, "$key.json").readText()).getLong("duration") }.getOrNull()
    }

    /** File tạm cho giọng ghi vào (cùng thư mục để đổi tên không phải chép). Không tính vào bộ nhớ đệm tới khi [put]. */
    fun temp(extension: String): File = File(dir, "tmp-${java.util.UUID.randomUUID()}.$extension.part")

    fun get(voiceId: String, text: String, origin: String? = null, readings: Map<String, String>? = null): Clip? =
        lookupKeys(voiceId, text, origin, readings).firstNotNullOfOrNull { load(it, voiceId) }

    private fun load(key: String, voiceId: String): Clip? {
        val meta = File(dir, "$key.json")
        if (!meta.isFile) return null
        return try {
            val json = JSONObject(meta.readText())
            val audio = File(dir, "$key.${json.getString("ext")}")
            if (!audio.isFile || audio.length() == 0L) return null
            val array = json.getJSONArray("words")
            val words = (0 until array.length()).map { array.getJSONArray(it).let { pair -> Span(pair.getLong(0), pair.getLong(1)) } }
            val now = clock()
            audio.setLastModified(now)
            meta.setLastModified(now)
            Clip(audio, json.getLong("duration"), words, VoiceSpeed.split(voiceId).first)
        } catch (error: Exception) {
            null // json hỏng / thiếu file: coi như chưa có, đọc lại sẽ ghi đè
        }
    }

    /** Nhận file `tmp` (đã ghi xong) vào bộ nhớ đệm; trả đoạn trỏ tới file chính thức. */
    fun put(
        voiceId: String, text: String, tmp: File, extension: String, durationMs: Long, words: List<Span>, origin: String? = null,
        readings: Map<String, String>? = null,
    ): Clip {
        require(extension in EXTENSIONS) { "đuôi file lạ: $extension" }
        val key = keyOf(voiceId, text, origin, readings)
        val voice = VoiceSpeed.split(voiceId).first
        val audio = File(dir, "$key.$extension")
        audio.delete()
        if (!tmp.renameTo(audio)) {
            tmp.copyTo(audio, overwrite = true)
            tmp.delete()
        }
        val array = JSONArray()
        words.forEach { array.put(JSONArray().put(it.start).put(it.end)) }
        val meta = File(dir, "$key.json")
        val part = File(dir, "$key.json.part")
        part.writeBytes(JSONObject().put("ext", extension).put("duration", durationMs).put("words", array).put("voice", voice).toString().toByteArray(Charsets.UTF_8))
        meta.delete()
        part.renameTo(meta)
        val now = clock()
        audio.setLastModified(now)
        meta.setLastModified(now)
        added(audio.length() + meta.length())
        return Clip(audio, durationMs, words, voice)
    }

    /** Một đoạn vừa vào bộ đệm ([bytes] cả cặp): cộng vào tổng đang chạy, quá hạn mức mới dọn. Đoạn ghi đè đoạn cũ cùng khoá làm tổng dư - lần dọn đếm lại từ đĩa. */
    @Synchronized
    private fun added(bytes: Long) {
        val now = total
        if (now == null) {
            trim()
            return
        }
        total = now + bytes
        if (now + bytes > capBytes) trim()
    }

    /** Dọn tới khi còn [TRIM_TO] hạn mức (chưa quá hạn mức thì thôi): xoá cả cặp (âm thanh + json) của đoạn dùng lâu nhất - đoạn không ghim trước; file mồ côi và file tạm cũ
     *  xoá luôn. Đếm lại tổng từ đĩa. */
    @Synchronized
    fun trim() {
        val files = dir.listFiles()?.filter { it.isFile } ?: return
        val now = clock()
        files.filter { it.name.endsWith(".part") && now - it.lastModified() > 10 * 60_000L }.forEach { it.delete() }
        val groups = files.filter { !it.name.endsWith(".part") }.groupBy { it.name.substringBefore('.') }
        var sum = groups.values.sumOf { group -> group.sumOf { it.length() } }
        if (sum > capBytes) {
            val target = (capBytes * TRIM_TO).toLong()
            val keep = pinnedKeys()
            val order = compareBy<Map.Entry<String, List<File>>> { it.key in keep }.thenBy { (_, group) -> group.maxOf { it.lastModified() } }
            for ((_, group) in groups.entries.sortedWith(order)) {
                if (sum <= target) break
                sum -= group.sumOf { it.length() }
                group.forEach { it.delete() }
            }
        }
        total = sum
    }

    fun sizeBytes(): Long = dir.listFiles()?.filter { it.isFile }?.sumOf { it.length() } ?: 0L

    /** "Dọn bản đọc đã làm" (Cài đặt > Giọng đọc): xoá mọi đoạn đã đọc và bỏ mọi ghim; file tạm của đoạn đang được ghi ở lại (giọng đang đọc dở không mất file). Trả số byte giải phóng. */
    @Synchronized
    fun clear(): Long {
        var freed = 0L
        dir.listFiles()?.filter { it.isFile && !it.name.endsWith(".part") }?.forEach {
            val size = it.length()
            if (it.delete()) freed += size
        }
        clearPins()
        total = null
        return freed
    }
}
