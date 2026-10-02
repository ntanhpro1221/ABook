package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.math.BigDecimal
import java.math.BigInteger

/**
 * JSON chặt như `json.loads` của Python và ghi ra như `json.dumps(indent=1, ensure_ascii=False)`: lớp sửa của người nghe
 * (BookEdits) là dữ liệu của người lạ nên phải đọc giống hệt bên Python - org.json lỏng hơn (chú thích, nháy đơn, khoá không
 * nháy, NaN) và khác nhau giữa Android với bản JVM. Đọc ra các kiểu của org.json (JSONObject / JSONArray / String / Boolean /
 * Long / BigInteger / Double / JSONObject.NULL), nên phần còn lại của app dùng được ngay.
 */
object StrictJson {
    class ParseError(message: String) : Exception(message)

    /** Số vô hạn ("1e999"): Python đọc ra float inf, org.json không cất được - giữ bằng dấu này, mọi phép kiểm coi là "không phải số". */
    object NonFinite {
        override fun toString() = "inf"
    }

    private const val MAX_DEPTH = 64

    fun parse(text: String): Any? {
        val reader = Reader(text)
        reader.skipSpace()
        val value = reader.value(0)
        reader.skipSpace()
        if (!reader.done()) throw ParseError("thừa chữ sau giá trị JSON")
        return value
    }

    private class Reader(private val text: String) {
        private var at = 0

        fun done() = at >= text.length

        fun skipSpace() {
            while (at < text.length && (text[at] == ' ' || text[at] == '\t' || text[at] == '\n' || text[at] == '\r')) at++
        }

        private fun fail(): Nothing = throw ParseError("JSON không hợp lệ ở vị trí $at")

        fun value(depth: Int): Any? {
            if (depth > MAX_DEPTH) fail()
            if (at >= text.length) fail()
            return when (text[at]) {
                '{' -> obj(depth)
                '[' -> array(depth)
                '"' -> string()
                't' -> literal("true", true)
                'f' -> literal("false", false)
                'n' -> literal("null", JSONObject.NULL)
                else -> number()
            }
        }

        private fun literal(word: String, value: Any): Any {
            if (!text.startsWith(word, at)) fail()
            at += word.length
            return value
        }

        private fun obj(depth: Int): JSONObject {
            val out = JSONObject()
            at++
            skipSpace()
            if (at < text.length && text[at] == '}') {
                at++
                return out
            }
            while (true) {
                skipSpace()
                if (at >= text.length || text[at] != '"') fail()
                val key = string()
                skipSpace()
                if (at >= text.length || text[at] != ':') fail()
                at++
                skipSpace()
                out.put(key, value(depth + 1)) // khoá trùng: bản sau thắng, như Python
                skipSpace()
                if (at >= text.length) fail()
                when (text[at++]) {
                    ',' -> continue
                    '}' -> return out
                    else -> fail()
                }
            }
        }

        private fun array(depth: Int): JSONArray {
            val out = JSONArray()
            at++
            skipSpace()
            if (at < text.length && text[at] == ']') {
                at++
                return out
            }
            while (true) {
                skipSpace()
                out.put(value(depth + 1))
                skipSpace()
                if (at >= text.length) fail()
                when (text[at++]) {
                    ',' -> continue
                    ']' -> return out
                    else -> fail()
                }
            }
        }

        private fun string(): String {
            at++ // dấu nháy mở
            val out = StringBuilder()
            while (true) {
                if (at >= text.length) fail()
                val char = text[at++]
                when {
                    char == '"' -> return out.toString()
                    char < ' ' -> fail() // ký tự điều khiển thô không được nằm trong chuỗi JSON
                    char == '\\' -> {
                        if (at >= text.length) fail()
                        when (val escaped = text[at++]) {
                            '"', '\\', '/' -> out.append(escaped)
                            'b' -> out.append('\b')
                            'f' -> out.append('\u000c')
                            'n' -> out.append('\n')
                            'r' -> out.append('\r')
                            't' -> out.append('\t')
                            'u' -> {
                                if (at + 4 > text.length) fail()
                                val code = text.substring(at, at + 4).takeIf { digits -> digits.all { it in '0'..'9' || it in 'a'..'f' || it in 'A'..'F' } }
                                    ?: fail()
                                out.append(code.toInt(16).toChar())
                                at += 4
                            }
                            else -> fail()
                        }
                    }
                    else -> out.append(char)
                }
            }
        }

        private fun number(): Any {
            val start = at
            if (at < text.length && text[at] == '-') at++
            if (at >= text.length) fail()
            if (text[at] == '0') at++
            else if (text[at] in '1'..'9') while (at < text.length && text[at] in '0'..'9') at++
            else fail()
            var integral = true
            if (at < text.length && text[at] == '.') {
                integral = false
                at++
                val from = at
                while (at < text.length && text[at] in '0'..'9') at++
                if (at == from) fail()
            }
            if (at < text.length && (text[at] == 'e' || text[at] == 'E')) {
                integral = false
                at++
                if (at < text.length && (text[at] == '+' || text[at] == '-')) at++
                val from = at
                while (at < text.length && text[at] in '0'..'9') at++
                if (at == from) fail()
            }
            val token = text.substring(start, at)
            if (integral) {
                val big = BigInteger(token)
                return if (big.bitLength() < 64) big.toLong() else big
            }
            val number = token.toDouble()
            return if (number.isInfinite()) NonFinite else number
        }
    }

    // ---- ghi ra -------------------------------------------------------------------------------------------------

    /** Như `json.dumps(value, ensure_ascii=False, indent=indent)`: khoá theo thứ tự `keys()` / `Map`, rỗng là `{}` / `[]`. */
    fun dumps(value: Any?, indent: Int = 1): String = StringBuilder().also { write(it, value, indent, 0) }.toString()

    private fun write(out: StringBuilder, value: Any?, indent: Int, level: Int) {
        when {
            value == null || value === JSONObject.NULL -> out.append("null")
            value is Boolean -> out.append(if (value) "true" else "false")
            value is Double -> out.append(pyFloat(value))
            value is Float -> out.append(pyFloat(value.toDouble()))
            value is Number -> out.append(value.toString())
            value is JSONObject -> writeMap(out, value.keys().asSequence().map { it to value.opt(it) }.toList(), indent, level)
            value is Map<*, *> -> writeMap(out, value.entries.map { it.key.toString() to it.value }, indent, level)
            value is JSONArray -> writeList(out, (0 until value.length()).map { value.opt(it) }, indent, level)
            value is List<*> -> writeList(out, value, indent, level)
            else -> quote(out, value.toString())
        }
    }

    private fun writeMap(out: StringBuilder, entries: List<Pair<String, Any?>>, indent: Int, level: Int) {
        if (entries.isEmpty()) {
            out.append("{}")
            return
        }
        out.append('{')
        entries.forEachIndexed { index, (key, item) ->
            if (index > 0) out.append(',')
            newline(out, indent, level + 1)
            quote(out, key)
            out.append(": ")
            write(out, item, indent, level + 1)
        }
        newline(out, indent, level)
        out.append('}')
    }

    private fun writeList(out: StringBuilder, items: List<Any?>, indent: Int, level: Int) {
        if (items.isEmpty()) {
            out.append("[]")
            return
        }
        out.append('[')
        items.forEachIndexed { index, item ->
            if (index > 0) out.append(',')
            newline(out, indent, level + 1)
            write(out, item, indent, level + 1)
        }
        newline(out, indent, level)
        out.append(']')
    }

    private fun newline(out: StringBuilder, indent: Int, level: Int) {
        out.append('\n')
        repeat(indent * level) { out.append(' ') }
    }

    private fun quote(out: StringBuilder, text: String) {
        out.append('"')
        for (char in text) {
            when {
                char == '"' -> out.append("\\\"")
                char == '\\' -> out.append("\\\\")
                char == '\n' -> out.append("\\n")
                char == '\r' -> out.append("\\r")
                char == '\t' -> out.append("\\t")
                char == '\b' -> out.append("\\b")
                char == '\u000c' -> out.append("\\f")
                char < ' ' -> out.append("\\u").append("%04x".format(char.code))
                else -> out.append(char)
            }
        }
        out.append('"')
    }

    /** `repr(float)` của Python: số ngắn nhất đọc lại đúng, "20.0" chứ không "20", mũ như "1e-05" ngoài khoảng 1e-4..1e16. */
    fun pyFloat(number: Double): String {
        if (number == 0.0) return if (1.0 / number < 0) "-0.0" else "0.0"
        val digits = BigDecimal(number.toString())
        val magnitude = Math.abs(number)
        if (magnitude >= 1e-4 && magnitude < 1e16) {
            val plain = digits.stripTrailingZeros().toPlainString()
            return if (plain.contains('.')) plain else "$plain.0"
        }
        val unscaled = digits.unscaledValue().abs().toString().trimEnd('0').ifEmpty { "0" }
        val exponent = digits.precision() - digits.scale() - 1
        val mantissa = if (unscaled.length > 1) unscaled[0] + "." + unscaled.substring(1) else unscaled
        val sign = if (number < 0) "-" else ""
        val exponentText = (if (exponent < 0) "-" else "+") + Math.abs(exponent).toString().padStart(2, '0')
        return "$sign${mantissa}e$exponentText"
    }

    // ---- so sánh ------------------------------------------------------------------------------------------------

    /** Bằng nhau theo cấu trúc, số so bằng giá trị (20 == 20.0 như Python; org.json in 20.0 thành 20). */
    fun equal(first: Any?, second: Any?): Boolean {
        val a = if (first === JSONObject.NULL) null else first
        val b = if (second === JSONObject.NULL) null else second
        return when {
            a == null || b == null -> a == null && b == null
            a is Boolean || b is Boolean -> a == b
            a is Number && b is Number ->
                if (a is BigInteger || b is BigInteger || a is Long || b is Long || a is Int || b is Int) {
                    val integral = { value: Number -> value is Int || value is Long || value is BigInteger }
                    if (integral(a) && integral(b)) a.toString() == b.toString() else a.toDouble() == b.toDouble()
                } else {
                    a.toDouble() == b.toDouble()
                }
            a is String || b is String -> a == b
            a is JSONObject && b is JSONObject -> {
                val keys = a.keys().asSequence().toSet()
                keys == b.keys().asSequence().toSet() && keys.all { equal(a.opt(it), b.opt(it)) }
            }
            a is JSONArray && b is JSONArray -> a.length() == b.length() && (0 until a.length()).all { equal(a.opt(it), b.opt(it)) }
            else -> false
        }
    }
}
