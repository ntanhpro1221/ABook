package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest

/**
 * Nhập file dự án `.abookproj` của CÙNG cuốn đã có trên máy (soát UX a25 T5): sửa trong xưởng - yêu cầu chờ Studio
 * (`project/overrides.json`), phán quyết "Cần nghe lại" (`project/reviews.json`) và thẻ đã quyết ghi ở file riêng (`aliases.json`,
 * `bracket_rule.json`, `narrator_sections.json`) - của bản trên máy và của file được GỘP, không bản nào bị bỏ im lặng khi bản kia
 * được giữ. Điện thoại không bao giờ đọc chúng; nó chỉ mang chúng tới lần "Lưu" sau.
 *
 * Đúng luật của máy tính (abook/webui/workshop_merge.py; hai bên đáp chung tests/fixtures/book_edits/workshop_merge/): mục chỉ có
 * ở một bên thì lấy; cùng khoá khác giá trị thì bản có mốc của mục mới hơn thắng (`requested_at` / `at`; thiếu mốc = cũ nhất),
 * bằng nhau thì giữ bản trên máy. Mục lấy từ file của `overrides.json` mang thêm `merged_at`.
 *
 * Yêu cầu đã RÚT ở một bên không sống lại (soát a89 V6): bia ở `cancelled.json` (cancelled.py của máy tính, cùng luật so, ca chung
 * `cancelled_requests.json`) chôn mục tương ứng ở cả hai bên trước khi gộp. Cùng yêu cầu (`requested_at` bằng đúng) thì luôn chết; mục cũ hơn
 * chết khi bia không `exact`, hợp lý (`requested_at <= cancelled_at`) và `cancelled_at` không vượt giờ máy này quá một ngày - không tin đồng hồ
 * máy kia mù quáng; mục mới hơn luôn sống. Mục của máy này bị chôn tính là một mục gộp; bia hợp hai bên và không được đếm.
 */
object WorkshopMerge {
    const val OVERRIDES = "overrides.json"
    const val REVIEWS = "reviews.json"
    const val ALIASES = "aliases.json"
    const val BRACKET_RULE = "bracket_rule.json"
    const val NARRATOR_SECTIONS = "narrator_sections.json"
    const val CANCELLED = "cancelled.json"
    private val FILES = listOf(OVERRIDES, REVIEWS, ALIASES, BRACKET_RULE, NARRATOR_SECTIONS, CANCELLED)
    private val REQUEST_SECTIONS = listOf("pronunciations", "speakers", "lines", "voices", "retakes")
    private const val SKEW_SECONDS = 86400.0
    private const val MERGED_AT = "merged_at"
    private const val RULE = "rule"
    private val NOT_VALUE = setOf("requested_at", "at", MERGED_AT, "replaced")

    class Counted(val merged: JSONObject, val taken: Int, val kept: Int)

    /** Một bia: mốc của yêu cầu bị rút, lúc rút, và `exact` (yêu cầu cũ hơn đã trở lại nên chỉ luật "cùng yêu cầu" áp). */
    class Tomb(val requested: Double, val cancelled: Double, val exact: Boolean)

    /** `cancelled.entries_of`: nội dung file -> {khoá "<phần>:<khoá>": bia}; mục sai hình bị bỏ. */
    fun tombsOf(content: JSONObject?): Map<String, Tomb> {
        val rows = content?.optJSONObject("cancelled") ?: return emptyMap()
        val out = HashMap<String, Tomb>()
        for (name in rows.keys()) {
            val row = rows.opt(name) as? JSONObject ?: continue
            val requested = (row.opt("requested_at") as? Number)?.toDouble() ?: continue
            val cancelled = (row.opt("cancelled_at") as? Number)?.toDouble() ?: continue
            if (":" in name) out[name] = Tomb(requested, cancelled, row.opt("exact") == true)
        }
        return out
    }

    /** `cancelled.union`: mỗi khoá giữ bia của yêu cầu mới hơn, bằng nhau thì lần rút muộn hơn. */
    fun unionTombs(mine: Map<String, Tomb>, theirs: Map<String, Tomb>): Map<String, Tomb> {
        val merged = HashMap(mine)
        for ((name, row) in theirs) {
            val local = merged[name]
            if (local == null || row.requested > local.requested || (row.requested == local.requested && row.cancelled > local.cancelled)) merged[name] = row
        }
        return merged
    }

    private fun tombsContent(tombs: Map<String, Tomb>): JSONObject {
        val rows = JSONObject()
        for (name in tombs.keys.sorted()) {
            val tomb = tombs.getValue(name)
            rows.put(name, JSONObject().put("requested_at", tomb.requested).put("cancelled_at", tomb.cancelled).also { if (tomb.exact) it.put("exact", true) })
        }
        return JSONObject().put("version", 1).put("cancelled", rows)
    }

    /** `cancelled.is_dead`. */
    private fun dead(section: String, key: String, entry: Any?, tombs: Map<String, Tomb>, now: Double): Boolean {
        val tomb = tombs["$section:$key"] ?: return false
        val stamp = ((entry as? JSONObject)?.opt("requested_at") as? Number)?.toDouble() ?: return false
        if (stamp == tomb.requested) return true
        return !tomb.exact && stamp < tomb.requested && tomb.requested <= tomb.cancelled && tomb.cancelled <= now + SKEW_SECONDS
    }

    /** `cancelled.bury`: `overrides` không còn mục bị bia chôn -> (bản mới, số mục bỏ). */
    private fun bury(overrides: JSONObject, tombs: Map<String, Tomb>, now: Double): Pair<JSONObject, Int> {
        val out = copy(overrides)
        var removed = 0
        for (section in REQUEST_SECTIONS) {
            val entries = out.optJSONObject(section) ?: continue
            val keep = JSONObject()
            for (key in entries.keys()) if (!dead(section, key, entries.opt(key), tombs, now)) keep.put(key, entries.opt(key))
            if (keep.length() != entries.length()) {
                removed += entries.length() - keep.length()
                out.put(section, keep)
            }
        }
        return out to removed
    }

    private fun stamp(entry: JSONObject, field: String): Double =
        (entry.opt(field) as? Number)?.toDouble() ?: Double.NEGATIVE_INFINITY

    private fun value(entry: JSONObject): JSONObject {
        val out = JSONObject()
        for (key in entry.keys()) if (key !in NOT_VALUE) out.put(key, entry.opt(key))
        return out
    }

    private fun copy(entry: JSONObject): JSONObject = JSONObject(entry.toString())

    private fun integer(value: Any?): Long? = when (value) {
        is Int -> value.toLong()
        is Long -> value
        else -> null
    }

    private fun rows(array: Any?): List<JSONObject> =
        (array as? JSONArray)?.let { list -> (0 until list.length()).mapNotNull { list.opt(it) as? JSONObject } } ?: emptyList()

    /** Nội dung một file -> {khoá: mục} (`_aliases_in`, `_rule_in`, `_sections_in` của máy tính). */
    private fun entriesOf(name: String, content: JSONObject): JSONObject = when (name) {
        ALIASES -> JSONObject().also { out ->
            for (row in rows(content.opt("aliases"))) {
                val alias = row.opt("alias") as? String ?: continue
                if (alias.isNotBlank()) out.put(BookWishes.aliasKey(alias), row)
            }
        }
        BRACKET_RULE -> if ((content.opt("speaker") as? String).orEmpty().isNotBlank()) JSONObject().put(RULE, content) else JSONObject()
        NARRATOR_SECTIONS -> JSONObject().also { out ->
            val sections = content.optJSONObject("sections") ?: return@also
            for (chapter in sections.keys()) {
                for (row in rows(sections.opt(chapter))) {
                    val first = integer(row.opt("from_seq")) ?: continue
                    val last = integer(row.opt("to_seq")) ?: continue
                    out.put("$chapter:$first:$last", row)
                }
            }
        }
        else -> content
    }

    /** {khoá: mục} -> nội dung file (`_aliases_out`, `_rule_out`, `_sections_out`). */
    private fun contentOf(name: String, entries: JSONObject): JSONObject = when (name) {
        ALIASES -> JSONObject().put("version", 1).put("aliases", JSONArray(entries.keys().asSequence().sorted().map { entries.get(it) }.toList()))
        BRACKET_RULE -> entries.optJSONObject(RULE)?.let(::copy) ?: JSONObject()
        NARRATOR_SECTIONS -> {
            val sections = JSONObject()
            for ((chapter, keys) in entries.keys().asSequence().toList().groupBy { it.substringBefore(':') }) {
                sections.put(chapter, JSONArray(keys.map { entries.getJSONObject(it) }.sortedBy { integer(it.opt("from_seq")) }))
            }
            JSONObject().put("version", 1).put("sections", sections)
        }
        else -> entries
    }

    /** `merge_entries`: {khoá: mục} của máy này gộp với của file. `now`: có thì mục lấy từ file mang `merged_at`. */
    fun entries(mine: JSONObject, theirs: JSONObject, field: String, now: Double?): Counted {
        val merged = copy(mine)
        var taken = 0
        var kept = 0
        for (key in theirs.keys()) {
            val entry = theirs.opt(key) as? JSONObject ?: continue
            val local = merged.opt(key) as? JSONObject
            if (local != null) {
                if (StrictJson.equal(value(local), value(entry))) continue
                if (stamp(entry, field) <= stamp(local, field)) {
                    kept++
                    continue
                }
            }
            merged.put(key, copy(entry).also { if (now != null) it.put(MERGED_AT, now) })
            taken++
        }
        return Counted(merged, taken, kept)
    }

    /** `merge_overrides`: gộp từng mục của mọi phần; phần khác (`version`) giữ của máy này. */
    fun overrides(mineIn: JSONObject, theirsIn: JSONObject, now: Double, tombs: Map<String, Tomb> = emptyMap()): Counted {
        val (mine, buried) = bury(mineIn, tombs, now)
        val theirs = bury(theirsIn, tombs, now).first
        val merged = copy(mine)
        var taken = buried
        var kept = 0
        for (section in theirs.keys()) {
            val entries = theirs.opt(section) as? JSONObject ?: continue
            val result = entries(merged.opt(section) as? JSONObject ?: JSONObject(), entries, "requested_at", now)
            merged.put(section, result.merged)
            taken += result.taken
            kept += result.kept
        }
        return Counted(merged, taken, kept)
    }

    /** `merge_file`: nội dung một file của máy này gộp với của file dự án. */
    fun file(name: String, mine: JSONObject, theirs: JSONObject, now: Double, tombs: Map<String, Tomb> = emptyMap()): Counted {
        if (name == OVERRIDES) return overrides(mine, theirs, now, tombs)
        if (name == CANCELLED) return Counted(tombsContent(unionTombs(tombsOf(mine), tombsOf(theirs))), 0, 0)
        val result = entries(entriesOf(name, mine), entriesOf(name, theirs), "at", null)
        return Counted(contentOf(name, result.merged), result.taken, result.kept)
    }

    /** `merge_files`: {tên file: nội dung} -> (kết quả, {merged, kept}) - hình dạng ca hợp đồng. */
    fun files(mine: JSONObject, theirs: JSONObject, now: Double): Pair<JSONObject, JSONObject> {
        val merged = JSONObject()
        var taken = 0
        var kept = 0
        val tombs = unionTombs(tombsOf(mine.optJSONObject(CANCELLED)), tombsOf(theirs.optJSONObject(CANCELLED)))
        for (name in (mine.keys().asSequence() + theirs.keys().asSequence()).toSortedSet()) {
            val result = file(name, mine.optJSONObject(name) ?: JSONObject(), theirs.optJSONObject(name) ?: JSONObject(), now, tombs)
            merged.put(name, result.merged)
            taken += result.taken
            kept += result.kept
        }
        return merged to JSONObject().put("merged", taken).put("kept", kept)
    }

    private fun parse(bytes: ByteArray?): JSONObject? =
        bytes?.let { runCatching { StrictJson.parse(it.toString(Charsets.UTF_8)) as? JSONObject }.getOrNull() }

    /**
     * Gộp xưởng vào thư mục cuốn `target` (đã có `project.json`): `mine(tên)` / `theirs(tên)` -> byte của `project/<tên>` ở bản trên
     * máy / bản của file (null khi không có). Ghi kết quả vào `target/project/<tên>` và sửa cỡ + mã băm của mục ấy trong
     * `target/project.json` - lần "Lưu" sau mang đúng byte mới. Trả {merged, kept}.
     */
    fun mergeInto(target: File, mine: (String) -> ByteArray?, theirs: (String) -> ByteArray?, now: Double): JSONObject {
        var taken = 0
        var kept = 0
        val written = LinkedHashMap<String, ByteArray>()
        val tombs = unionTombs(tombsOf(parse(mine(CANCELLED))), tombsOf(parse(theirs(CANCELLED))))
        for (name in FILES) {
            val incoming = parse(theirs(name))?.takeIf { it.length() > 0 }
            val local = parse(mine(name))
            if (incoming == null && local == null) continue
            val result = file(name, local ?: JSONObject(), incoming ?: JSONObject(), now, tombs)
            taken += result.taken
            kept += result.kept
            val current = File(target, "project/$name").takeIf { it.isFile }?.let { parse(it.readBytes()) }
            if (current == null || !StrictJson.equal(current, result.merged)) {
                written[name] = StrictJson.dumps(result.merged, 1).toByteArray(Charsets.UTF_8)
            }
        }
        if (written.isNotEmpty()) {
            val manifestFile = File(target, ProjectDocument.MANIFEST)
            val manifest = JSONObject(manifestFile.readText(Charsets.UTF_8))
            val files = manifest.getJSONObject("files")
            for ((name, bytes) in written) {
                Store.writeAtomic(File(target, "project/$name"), bytes)
                val sha = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
                files.put("project/$name", JSONObject().put("size", bytes.size.toLong()).put("sha256", sha))
            }
            Store.writeAtomic(manifestFile, StrictJson.dumps(manifest, 1))
        }
        return JSONObject().put("merged", taken).put("kept", kept)
    }
}
