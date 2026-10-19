package vn.abook.player

import org.json.JSONObject

/**
 * Large plugin-call options kept in memory while a system picker is open.
 *
 * Capacitor writes the options of the call that started an activity for result into the activity's saved state
 * (`capacitorLastPluginCallOptions` + the plugin's `capacitorLastPluginCallBundle`, the same JSON twice). The UI sends a drawn cover
 * (a PNG data URL, ~130 KB) with the export calls, so the saved state crossed the 1 MB binder limit when the picker covered the app and
 * Android killed it with TransactionTooLargeException (a65). [take] moves every large field out of the call before the picker opens;
 * [putBack] returns them when the result arrives. One slot, like Capacitor's own "last call": a picker is opened one at a time. If the
 * process dies while the picker is open, the call comes back without those fields (export without the drawn cover) instead of crashing.
 */
class HeldCallFields {
    private var method: String? = null
    private var fields: JSONObject? = null

    /** Moves the fields of `data` larger than [LIMIT] characters into the slot (replacing whatever was held) for the call `method`. */
    @Synchronized
    fun take(method: String, data: JSONObject) {
        val large = JSONObject()
        for (key in data.keys().asSequence().toList()) {
            val value = data.opt(key) ?: continue
            if (value.toString().length > LIMIT) large.put(key, data.remove(key))
        }
        this.method = method
        this.fields = large.takeIf { it.length() > 0 }
    }

    /** Puts the held fields back into `data` when it is the answer to the call `method` that left them; empties the slot either way. */
    @Synchronized
    fun putBack(method: String, data: JSONObject) {
        val held = fields.takeIf { this.method == method }
        this.method = null
        this.fields = null
        held?.keys()?.forEach { key -> if (!data.has(key)) data.put(key, held.get(key)) }
    }

    companion object {
        /** Options up to this many characters stay in the call (ids, flags, titles); anything bigger is held in memory. */
        const val LIMIT = 4096
    }
}
