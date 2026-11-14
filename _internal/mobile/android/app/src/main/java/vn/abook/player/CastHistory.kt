package vn.abook.player

import java.io.File
import java.nio.ByteBuffer
import java.security.MessageDigest
import java.util.UUID
import org.json.JSONArray
import org.json.JSONObject

/** Portable history carries references, never trusted before-state from another device. */
object CastHistory {
    fun undoId(original: String): String {
        require(Regex("[0-9a-f]{32}").matches(original))
        val namespace = UUID.fromString(original.replace(Regex("(.{8})(.{4})(.{4})(.{4})(.{12})"), "$1-$2-$3-$4-$5"))
        val bytes = ByteBuffer.allocate(16).putLong(namespace.mostSignificantBits).putLong(namespace.leastSignificantBits).array()
        val digest = MessageDigest.getInstance("SHA-1").digest(bytes + "undo-cast-v1".toByteArray(Charsets.UTF_8))
        digest[6] = ((digest[6].toInt() and 0x0f) or 0x50).toByte()
        digest[8] = ((digest[8].toInt() and 0x3f) or 0x80).toByte()
        return digest.take(16).joinToString("") { "%02x".format(it.toInt() and 0xff) }
    }

    fun view(folder: File): JSONObject {
        val cast = BookEdits.cast(folder, BookEdits.rawBook(folder))
        val history = cast.optJSONObject("castHistory") ?: JSONObject().put("items", JSONArray()).put("manualOnly", true)
        val pending = BookEdits.load(folder).optJSONObject("wishes")?.optJSONObject("cast_undos")
        val items = history.optJSONArray("items") ?: JSONArray()
        for (i in 0 until items.length()) {
            val item = items.optJSONObject(i) ?: continue
            val original = item.optString("operationId")
            if (Regex("[0-9a-f]{32}").matches(original) && pending?.has(undoId(original)) == true) item.put("state", "pending")
        }
        return history
    }
}
