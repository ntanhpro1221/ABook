package vn.abook.player.vieneu

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.Normalizer

/**
 * The byte-level BPE tokenizer of Turbo's `tokenizer.json`, the phone's copy of `vieneu_engine.ByteBPE` (shared fixture
 * tests/fixtures/vieneu/android/tokens.json): special tokens split out, NFC, the GPT-2 style pre-split regex (Split, Isolated), bytes
 * mapped to characters, merges applied lowest rank first, unknown pieces -> unk.
 */
class ByteBpe(spec: JSONObject) {
    constructor(file: File) : this(JSONObject(file.readText(Charsets.UTF_8)))

    private val vocab = HashMap<String, Int>()
    private val ranks = HashMap<String, Int>() // "left\u0000right" -> rank
    private val unk: Int?
    private val nfc: Boolean
    private val added = HashMap<String, Int>()
    private val special: Regex?
    private val split: Regex
    private val byteMap = bytesToUnicode()
    private val cache = HashMap<String, IntArray>()

    init {
        val model = spec.getJSONObject("model")
        val normalizer = spec.optJSONObject("normalizer")?.optString("type")
        require(model.optString("type") == "BPE" && (normalizer == null || normalizer == "NFC")) { "tokenizer.json không phải ByteLevel-BPE + NFC như VieNeu 3.8.1" }
        val words = model.getJSONObject("vocab")
        for (key in words.keys()) vocab[key] = words.getInt(key)
        val merges = model.optJSONArray("merges") ?: JSONArray()
        for (rank in 0 until merges.length()) {
            val item = merges.get(rank)
            val (left, right) = if (item is JSONArray) item.getString(0) to item.getString(1) else (item as String).split(" ", limit = 2).let { it[0] to it[1] }
            ranks.putIfAbsent("$left\u0000$right", rank)
        }
        unk = if (model.isNull("unk_token")) null else vocab[model.optString("unk_token")]
        nfc = normalizer == "NFC"
        val tokens = spec.optJSONArray("added_tokens") ?: JSONArray()
        val contents = (0 until tokens.length()).map { tokens.getJSONObject(it) }
        contents.forEach { added[it.getString("content")] = it.getInt("id") }
        special = contents.map { it.getString("content") }.sortedByDescending { it.length }.takeIf { it.isNotEmpty() }
            ?.let { list -> Regex(list.joinToString("|") { Regex.escape(it) }) }
        val w = WHITE
        split = Regex("(?iu:'s|'t|'re|'ve|'m|'ll|'d)|[^\\r\\n\\p{L}\\p{N}]?\\p{L}+|\\p{N}| ?[^$w\\p{L}\\p{N}]+[\\r\\n]*|[$w]*[\\r\\n]+|[$w]+(?![^$w])|[$w]+")
    }

    private fun bpe(word: String): IntArray {
        cache[word]?.let { return it }
        val parts = ArrayList<String>()
        var at = 0
        while (at < word.length) {
            val end = at + Character.charCount(word.codePointAt(at))
            parts.add(word.substring(at, end))
            at = end
        }
        while (parts.size > 1) {
            var best = Int.MAX_VALUE
            var index = -1
            for (i in 0 until parts.size - 1) {
                val rank = ranks["${parts[i]}\u0000${parts[i + 1]}"] ?: continue
                if (rank < best) {
                    best = rank
                    index = i
                }
            }
            if (index < 0) break
            parts[index] = parts[index] + parts[index + 1]
            parts.removeAt(index + 1)
        }
        val ids = parts.mapNotNull { vocab[it] ?: unk }.toIntArray()
        if (cache.size < 50_000) cache[word] = ids
        return ids
    }

    @Synchronized
    fun encode(text: String): IntArray {
        val out = ArrayList<Int>()
        fun plain(piece: String) {
            if (piece.isEmpty()) return
            val normal = if (nfc) Normalizer.normalize(piece, Normalizer.Form.NFC) else piece
            for (match in split.findAll(normal)) {
                val mapped = StringBuilder()
                for (b in match.value.toByteArray(Charsets.UTF_8)) mapped.append(byteMap[b.toInt() and 0xFF])
                bpe(mapped.toString()).forEach { out.add(it) }
            }
        }
        var at = 0
        special?.findAll(text)?.forEach { match ->
            plain(text.substring(at, match.range.first))
            out.add(added.getValue(match.value))
            at = match.range.last + 1
        }
        plain(text.substring(at))
        return out.toIntArray()
    }

    companion object {
        /** Unicode White_Space, as `vieneu_engine._WHITE` (escaped for a character class). */
        private const val WHITE = "\\t\\n\\x0b\\x0c\\r \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000"

        private fun bytesToUnicode(): Array<String> {
            val keep = ArrayList<Int>().apply { addAll('!'.code..'~'.code); addAll('¡'.code..'¬'.code); addAll('®'.code..'ÿ'.code) }
            val chars = ArrayList(keep)
            var extra = 0
            for (byte in 0 until 256) {
                if (byte !in keep) {
                    keep.add(byte)
                    chars.add(256 + extra)
                    extra++
                }
            }
            val map = arrayOfNulls<String>(256)
            for (i in keep.indices) map[keep[i]] = String(Character.toChars(chars[i]))
            return map.requireNoNulls()
        }
    }
}
