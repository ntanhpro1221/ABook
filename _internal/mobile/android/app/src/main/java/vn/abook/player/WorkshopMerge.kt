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
 */
object WorkshopMerge {
    const val OVERRIDES = "overrides.json"
    const val REVIEWS = "reviews.json"
    const val ALIASES = "aliases.json"
    const val BRACKET_RULE = "bracket_rule.json"
    const val NARRATOR_SECTIONS = "narrator_sections.json"
    private val FILES = listOf(OVERRIDES, REVIEWS, ALIASES, BRACKET_RULE, NARRATOR_SECTIONS)
    private const val MERGED_AT = "merged_at"
    private const val RULE = "rule"
    private val NOT_VALUE = setOf("requested_at", "at", MERGED_AT, "replaced")

    class Counted(val merged: JSONObject, val taken: Int, val kept: Int)

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
    fun overrides(mine: JSONObject, theirs: JSONObject, now: Double): Counted {
        val merged = copy(mine)
        var taken = 0
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
    fun file(name: String, mine: JSONObject, theirs: JSONObject, now: Double): Counted {
        if (name == OVERRIDES) return overrides(mine, theirs, now)
        val result = entries(entriesOf(name, mine), entriesOf(name, theirs), "at", null)
        return Counted(contentOf(name, result.merged), result.taken, result.kept)
    }

    /** `merge_files`: {tên file: nội dung} -> (kết quả, {merged, kept}) - hình dạng ca hợp đồng. */
    fun files(mine: JSONObject, theirs: JSONObject, now: Double): Pair<JSONObject, JSONObject> {
        val merged = JSONObject()
        var taken = 0
        var kept = 0
        for (name in (mine.keys().asSequence() + theirs.keys().asSequence()).toSortedSet()) {
            val result = file(name, mine.optJSONObject(name) ?: JSONObject(), theirs.optJSONObject(name) ?: JSONObject(), now)
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
        for (name in FILES) {
            val incoming = parse(theirs(name))?.takeIf { it.length() > 0 }
            val local = parse(mine(name))
            if (incoming == null && local == null) continue
            val result = file(name, local ?: JSONObject(), incoming ?: JSONObject(), now)
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
